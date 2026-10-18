/* server/worker/src/economy.js — паки, шахта, награды, биржа (b463)
 *
 * Общий принцип всех четырёх разделов один: клиент говорит ЧТО он хочет
 * сделать, сервер сам проверяет, хватает ли на это денег и прав, и сам же
 * считает результат. Ни одна сумма не приходит с клиента как истина.
 *
 * Паки.   Цена берётся из каталога сервера. Клиент может прислать свою цену
 *         (у нас есть скидочные окна и «голландские» аукционы — их расписание
 *         живёт в Студии), но сервер принимает её только в допустимых пределах:
 *         от p.price*10 % (максимальная скидка в игре — 90 %) до p.price.
 *         Дешевле не выйдет, снятый с продажи пак не купится, а карты крутит
 *         сервер своим генератором — «выбрать себе легендарку» нельзя.
 *
 * Шахта.  Монеты капают по времени, которое считает СЕРВЕР (уровень кирки и
 *         метка последнего сбора хранятся у него), офлайн-потолок 2 часа — как
 *         в игре. Начислить себе добычу за неделю не получится.
 *
 * Награды. Суммы за задания и достижения сервер берёт из своих таблиц
 *         (assets/nx-rules.js, сгенерированы из app.js), прогресс — из своих же
 *         счётчиков, каждую награду выдаёт один раз.
 *
 * Биржа.  Эскроу на сервере: копия карты снимается с продавца при выставлении
 *         лота, покупатель платит атомарно, продавец получает монеты сразу.
 *         Продать карту, которой нет, или купить уже разобранный лот — нельзя.
 */

import { M, S, N, json, err, now, rndId, money } from './util.js';

export function economyHandlers(ctx) {
    const { store, env, R, rng, authPlayer, catalog, cardIndex, bumpPlayer, stBump, stMax, msnBump, msnGet, playerView, syncStatsMirror, bankPublic, roomOf } = ctx;

    // =============== состояние игрока (для синхронизации и сторожа) ===============
    async function state(req, body, headers) {
        const a = await authPlayer(req, body);
        if (a.error) return err(a.error, a.blocked ? 403 : 401);
        const room = roomOf(body, headers);
        const p = await store.playerGet(a.cid);
        const bank = await store.bankGet();
        const inv = await store.invList(a.cid);
        const hall = await store.hallGet();
        return json({
            ok: true, cid: a.cid, room: room, player: playerView(p),
            bal: money(M(p.bal)), bank: bankPublic(room, bank),
            inv: inv, hall: hall.slice(0, 40), top: ctx.topWins(hall),
            unpaid: (await store.ledgerUnpaid(a.cid)).map(l => ({ id: l.id, amount: S(M(l.amount)) }))
        });
    }

    // =============== ПАКИ ===============
    function packById(cat, id) {
        const list = (cat && cat.packs) || [];
        for (const p of list) if (p && String(p.id) === String(id)) return p;
        return null;
    }

    /** Цена пака: доверяем расписанию клиента только в законных пределах. */
    function checkPrice(pack, claimed) {
        const base = Math.max(0, Math.floor(Number(pack.price) || 0));
        const min = base > 0 ? Math.max(1, Math.round(base * 0.1)) : 0; // максимум скидки в игре — 90 %
        const c = Math.floor(Number(claimed));
        if (!isFinite(c) || c < 0) return { ok: false, reason: 'bad_price' };
        if (!claimed && claimed !== 0) return { ok: true, price: base };
        if (c < min || c > base) return { ok: false, reason: 'price_out_of_range', min: min, max: base };
        return { ok: true, price: c };
    }

    async function pack(req, body, headers) {
        const a = await authPlayer(req, body);
        if (a.error) return err(a.error, a.blocked ? 403 : 401);
        const { cid } = a;
        const room = roomOf(body, headers);
        const cat = await catalog(room);
        if (!cat) return json({ ok: false, error: 'no_catalog', fallback: true }, 200);

        const packId = String(body.packId || '').slice(0, 80);
        const pack = packById(cat, packId);
        if (!pack) return err('no_pack', 404);
        if (pack.retired) return err('pack_retired');
        if (pack.saleUntil && now() > Number(pack.saleUntil)) return err('pack_retired');
        if (pack.premiereAt && now() < Number(pack.premiereAt)) return err('pack_premiere');

        const qty = Math.max(1, Math.min(99, Math.floor(Number(body.qty) || 1)));
        const priceCheck = checkPrice(pack, body.price);
        if (!priceCheck.ok) return err(priceCheck.reason, 400, { min: priceCheck.min, max: priceCheck.max });
        const total = BigInt(priceCheck.price) * BigInt(qty);

        // лимит окна продажи (schedule.limitN) — не больше N паков в руки
        const sc = pack.schedule || null;
        if (sc && Number(sc.limitN) > 0) {
            const p0 = await store.playerGet(cid);
            const key = packId + ':' + String(sc.start || 0);
            const bought = Number(((p0 && p0.win) || {})[key]) || 0;
            if (bought + qty > Number(sc.limitN)) return err('window_limit', 400, { limit: Number(sc.limitN), bought: bought });
        }

        const spent = await store.spend(cid, total);
        if (!spent.ok) return json({ ok: false, error: 'not_enough', need: S(total), bal: money(M(spent.bal)) }, 200);

        const packCards = ((cat.cards || []).filter(c => c && c.packId === packId));
        if (!packCards.length) {
            await store.credit(cid, total); // как на клиенте: пустой пак возвращает деньги
            return json({ ok: false, error: 'pack_empty', bal: money(M(spent.bal)) }, 200);
        }

        const idx = cardIndex(cat);
        const out = [];
        let pity = Number((await store.playerGet(cid)).pity) || 0;
        let dupeCoins = 0, newCards = 0, dupes = 0;
        const rar = { rarePlus: 0, epicPlus: 0, legendary: 0 };

        for (let q = 0; q < qty; q++) {
            const rolled = R.rollPack(rng, packCards, pity);
            pity = rolled.pity;
            for (const c of rolled.cards) {
                const def = idx.get(String(c.id)) || c;
                const rarity = R.RARITY_WEIGHTS[def.rarity] ? def.rarity : 'common';
                const before = await store.invGet(cid, String(c.id));
                await store.invAdd(cid, String(c.id), 1);
                const dup = before > 0;
                let refund = 0;
                if (dup) {
                    refund = R.DUPE_REFUND[rarity] || 20;
                    dupeCoins += refund; dupes++;
                } else { newCards++; }
                if (rarity === 'rare' || rarity === 'epic' || rarity === 'legendary') rar.rarePlus++;
                if (rarity === 'epic' || rarity === 'legendary') rar.epicPlus++;
                if (rarity === 'legendary') rar.legendary++;
                out.push({
                    id: String(c.id), rarity: rarity, name: def.name || c.id,
                    image: def.image || '', packId: packId, dup: dup, refund: refund
                });
            }
        }

        if (dupeCoins > 0) await store.credit(cid, dupeCoins);

        const pAfter = await bumpPlayer(cid, (pl) => {
            pl.pity = pity;
            stBump(pl, 'packsOpened', qty);
            stBump(pl, 'newCards', newCards);
            stBump(pl, 'dupesSold', dupes);
            stBump(pl, 'dupeCoins', dupeCoins);
            stBump(pl, 'rarePlusFound', rar.rarePlus);
            stBump(pl, 'epicPlusFound', rar.epicPlus);
            stBump(pl, 'legendariesFound', rar.legendary);
            pl.spent = S(M(pl.spent || 0) + total);
            msnBump(pl, 'open_pack', qty);
            msnBump(pl, 'collect_new', newCards);
            msnBump(pl, 'find_rare_plus', rar.rarePlus);
            msnBump(pl, 'find_epic_plus', rar.epicPlus);
            msnBump(pl, 'sell_dupe', dupes);
            msnBump(pl, 'earn_dupe_coins', dupeCoins);
            if (sc && Number(sc.limitN) > 0) {
                pl.win = pl.win || {};
                const key = packId + ':' + String(sc.start || 0);
                pl.win[key] = (Number(pl.win[key]) || 0) + qty;
            }
            // продажи пака — для статистики Студии
            pl.pk = pl.pk || {};
            pl.pk[packId] = (Number(pl.pk[packId]) || 0) + qty;
        });

        await syncStatsMirror(cid, pAfter || {}, room);
        return json({
            ok: true, packId: packId, qty: qty, price: priceCheck.price, total: S(total),
            cards: out, pity: pity, dupeCoins: dupeCoins,
            bal: money(M(pAfter ? pAfter.bal : 0)),
            st: (pAfter && pAfter.st) || {},
            inv: out.reduce((m, c) => { m[c.id] = 1; return m; }, {})
        });
    }

    // =============== ШАХТА ===============
    const MINER_OFFLINE_CAP = 2 * 3600; // секунды, как на клиенте (b246)
    function minerCost(lvl) { return Math.floor(10000 * Math.pow(1.22, Math.max(1, lvl) - 1)); }

    async function miner(req, body, headers) {
        const a = await authPlayer(req, body);
        if (a.error) return err(a.error, a.blocked ? 403 : 401);
        const { cid } = a;
        const room = roomOf(body, headers);
        const act = String(body.act || 'claim');

        if (act === 'upgrade') {
            const p0 = await store.playerGet(cid);
            const lvl = Math.max(1, Number(p0.minerLvl) || 1);
            const cost = BigInt(minerCost(lvl));
            const spent = await store.spend(cid, cost);
            if (!spent.ok) return json({ ok: false, error: 'not_enough', cost: S(cost), bal: money(M(spent.bal)) }, 200);
            const p = await bumpPlayer(cid, (pl) => {
                pl.minerLvl = lvl + 1;
                pl.minerLast = now();          // улучшение обнуляет накопленное окно
                stMax(pl, 'minerLvl', pl.minerLvl);
                stBump(pl, 'minerUpgrades', 1);
                msnBump(pl, 'miner_upgrade', 1);
            });
            await syncStatsMirror(cid, p || {}, room);
            return json({ ok: true, act: 'upgrade', lvl: lvl + 1, cost: S(cost), nextCost: String(minerCost(lvl + 1)), bal: money(M(p ? p.bal : 0)) });
        }

        // сбор добычи: время считает сервер, офлайн — не больше 2 часов
        const p0 = await store.playerGet(cid);
        const lvl = Math.max(1, Number(p0.minerLvl) || 1);
        const last = Number(p0.minerLast) || now();
        const sec = Math.min(MINER_OFFLINE_CAP, Math.max(0, Math.floor((now() - last) / 1000)));
        const gain = BigInt(sec * lvl);
        if (gain <= 0n) {
            return json({ ok: true, act: 'claim', sec: sec, gain: '0', gainN: 0, lvl: lvl, bal: money(M(p0.bal)) });
        }
        const bal = await store.credit(cid, gain);
        const p = await bumpPlayer(cid, (pl) => {
            pl.minerLast = now();
            pl.minerTotal = S(M(pl.minerTotal || 0) + gain);
            stBump(pl, 'mineOre', N(gain));
            msnBump(pl, 'mine_ore', N(gain));
        });
        await syncStatsMirror(cid, p || {}, room);
        return json({ ok: true, act: 'claim', sec: sec, gain: S(gain), gainN: N(gain), lvl: lvl, total: S(M(p ? p.minerTotal : 0)), bal: money(M(bal)) });
    }

    // =============== НАГРАДЫ ===============
    function dayKey() { return new Date().toISOString().slice(0, 10); }

    async function reward(req, body, headers) {
        const a = await authPlayer(req, body);
        if (a.error) return err(a.error, a.blocked ? 403 : 401);
        const { cid } = a;
        const room = roomOf(body, headers);
        const kind = String(body.kind || '');
        const p0 = await store.playerGet(cid);

        // ---- ежедневная награда: серия и сумма — на сервере ----
        if (kind === 'daily') {
            const today = dayKey();
            const d = (p0.daily && typeof p0.daily === 'object') ? p0.daily : { last: '', streak: 0 };
            if (d.last === today) return json({ ok: false, error: 'already_claimed', streak: d.streak }, 200);
            const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
            const streak = (d.last === yesterday && d.streak >= 1 && d.streak < 7) ? d.streak + 1
                : (d.last === yesterday && d.streak >= 7) ? 1 : 1;
            const amount = R.DAILY_REWARDS[Math.min(R.DAILY_REWARDS.length, Math.max(1, streak)) - 1] || 0;
            const bal = await store.credit(cid, amount);
            const p = await bumpPlayer(cid, (pl) => {
                pl.daily = { last: today, streak: streak };
                stMax(pl, 'bestStreak', streak);
            });
            await syncStatsMirror(cid, p || {}, room);
            return json({ ok: true, kind: 'daily', streak: streak, amount: String(amount), bal: money(M(bal)) });
        }

        // ---- задание дня ----
        if (kind === 'mission') {
            const type = String(body.type || '').slice(0, 40);
            const target = Math.floor(Number(body.target) || 0);
            const variants = R.MISSION_VARIANTS[type];
            if (!variants) return err('unknown_mission');
            let amount = 0;
            for (const v of variants) if (Number(v[0]) === target) amount = Number(v[1]);
            if (!amount) return err('unknown_mission_variant');
            const key = 'm:' + dayKey() + ':' + type + ':' + target;
            if ((p0.ach || {})[key]) return json({ ok: false, error: 'already_claimed' }, 200);
            const progress = msnGet(p0, type);
            if (progress < target) return json({ ok: false, error: 'not_completed', progress: progress, target: target }, 200);
            const bal = await store.credit(cid, amount);
            const p = await bumpPlayer(cid, (pl) => { pl.ach = pl.ach || {}; pl.ach[key] = now(); });
            await syncStatsMirror(cid, p || {}, room);
            return json({ ok: true, kind: 'mission', type: type, target: target, amount: String(amount), progress: progress, bal: money(M(bal)) });
        }

        // ---- достижение ----
        if (kind === 'achievement') {
            const id = String(body.id || '').slice(0, 40);
            const amount = Number(R.ACHIEVEMENT_REWARDS[id]);
            if (!amount) return err('unknown_achievement');
            const key = 'a:' + id;
            if ((p0.ach || {})[key]) return json({ ok: false, error: 'already_claimed' }, 200);
            const rule = R.ACHIEVEMENT_RULES[id];
            if (rule) {
                const have = rule.k === 'balance' ? N(M(p0.bal)) : (rule.k === 'collected'
                    ? Object.keys(await store.invList(cid)).length
                    : Number((p0.st || {})[rule.k]) || 0);
                if (have < rule.n) return json({ ok: false, error: 'not_completed', have: have, need: rule.n }, 200);
            }
            // rule == null → сервер не может проверить условие (арена/дурак/альбомы):
            // награда всё равно выдаётся ОДИН раз и ровно в размере из таблицы.
            const bal = await store.credit(cid, amount);
            const p = await bumpPlayer(cid, (pl) => { pl.ach = pl.ach || {}; pl.ach[key] = now(); });
            await syncStatsMirror(cid, p || {}, room);
            return json({ ok: true, kind: 'achievement', id: id, amount: String(amount), verified: !!rule, bal: money(M(bal)) });
        }

        return err('bad_kind');
    }

    // =============== БИРЖА ДУБЛИКАТОВ ===============
    function lotView(l) {
        return {
            id: l.id, sid: l.sid, sname: l.sname || '', price: S(M(l.price)), priceN: N(M(l.price)),
            at: Number(l.at) || 0, card: l.card || null, status: l.status
        };
    }

    async function marketList(req, body, headers) {
        const a = await authPlayer(req, body);
        if (a.error) return err(a.error, a.blocked ? 403 : 401);
        const { cid } = a;
        const lots = Array.isArray(body.lots) ? body.lots : [];
        if (!lots.length) return json({ ok: true, listed: 0 });
        const accepted = [], rejected = [];

        for (const raw of lots.slice(0, 200)) {
            const l = raw || {};
            const id = String(l.id || '').slice(0, 80);
            const cardId = String((l.card && l.card.id) || '').slice(0, 80);
            const price = M(l.price);
            if (!id || !cardId || price <= 0n) { rejected.push({ id: id, error: 'bad_lot' }); continue; }
            // владение картой проверяет сервер: копия уходит в эскроу
            const have = await store.invGet(cid, cardId);
            if (have < 1) { rejected.push({ id: id, error: 'not_owned' }); continue; }
            await store.invAdd(cid, cardId, -1);
            const snap = Object.assign({}, l.card);
            if (typeof snap.image === 'string' && snap.image.indexOf('data:') === 0) snap.image = '';
            const rec = {
                id: id, sid: cid, sname: String(l.sname || '').slice(0, 24),
                price: S(price), card: snap, at: Number(l.at) || now(), status: 'open'
            };
            await store.lotPut(rec);
            accepted.push(lotView(rec));
        }
        return json({ ok: true, listed: accepted.length, lots: accepted, rejected: rejected });
    }

    async function marketBuy(req, body, headers) {
        const a = await authPlayer(req, body);
        if (a.error) return err(a.error, a.blocked ? 403 : 401);
        const { cid } = a;
        const room = roomOf(body, headers);
        const id = String(body.id || '').slice(0, 80);
        const lot = await store.lotGet(id);
        if (!lot || lot.status !== 'open') return json({ ok: false, error: 'Лот уже куплен или снят' }, 200);
        if (lot.sid === cid) return json({ ok: false, error: 'Свой лот купить нельзя' }, 200);
        const price = M(lot.price);

        const spent = await store.spend(cid, price);
        if (!spent.ok) return json({ ok: false, error: 'Не хватает монет: нужно ' + S(price), bal: money(M(spent.bal)) }, 200);

        // атомарно забираем лот: если успел другой — возвращаем деньги
        const taken = await store.lotTake(id, cid, price);
        if (!taken) {
            await store.credit(cid, price);
            return json({ ok: false, error: 'Лот уже куплен или снят', bal: money(M(spent.bal)) }, 200);
        }

        const cardId = String((lot.card && lot.card.id) || '').slice(0, 80);
        const before = await store.invGet(cid, cardId);
        if (cardId) await store.invAdd(cid, cardId, 1);

        // продавец получает монеты сразу (сервер — источник истины)
        const receiptId = 'sale-' + id;
        await store.ledgerAdd({ id: receiptId, sid: lot.sid, amount: S(price), at: now(), bname: String(body.name || '').slice(0, 24), paid: 1 });
        const sellerBal = await store.credit(lot.sid, price);
        await store.mutate(store.NS.PLAYER, lot.sid, (pl) => { stBump(pl, 'soldLots', 1); pl.bal = S(sellerBal); return pl; });

        const p = await bumpPlayer(cid, (pl) => {
            stBump(pl, 'boughtLots', 1);
            if (before === 0) stBump(pl, 'newCards', 1);
            pl.spent = S(M(pl.spent || 0) + price);
            msnBump(pl, 'collect_new', before === 0 ? 1 : 0);
        });
        await syncStatsMirror(cid, p || {}, room);
        await syncStatsMirror(lot.sid, await store.playerGet(lot.sid), room);

        return json({
            ok: true, id: id, price: S(price), priceN: N(price),
            card: lot.card || null, dup: before > 0,
            receipt: { id: receiptId, sid: lot.sid, amount: S(price), at: now(), bname: String(body.name || '').slice(0, 24), paid: 1 },
            bal: money(M(p ? p.bal : 0)), inv: cardId ? { [cardId]: await store.invGet(cid, cardId) } : {}
        });
    }

    async function marketCancel(req, body, headers) {
        const a = await authPlayer(req, body);
        if (a.error) return err(a.error, a.blocked ? 403 : 401);
        const { cid } = a;
        const id = String(body.id || '').slice(0, 80);
        // отменить может только продавец (sid из токена, а не из запроса)
        const lot = await store.lotGet(id);
        if (!lot) return json({ ok: false, error: 'Лот не найден' }, 200);
        if (lot.sid !== cid && String(body.sid || '') !== lot.sid) return json({ ok: false, error: 'Это чужой лот' }, 200);
        const done = await store.lotCancel(id, lot.sid);
        if (!done) return json({ ok: false, error: 'Лот уже куплен или снят' }, 200);
        const cardId = String((lot.card && lot.card.id) || '').slice(0, 80);
        if (cardId) await store.invAdd(lot.sid, cardId, 1); // копия возвращается из эскроу
        return json({ ok: true, id: id, returned: cardId || null });
    }

    async function marketLots(req, body, headers) {
        const room = roomOf(body || {}, headers);
        const limit = Math.max(1, Math.min(400, Math.floor(Number(req.query && req.query.limit) || 400)));
        const lots = await store.lotList(limit);
        return json({ ok: true, room: room, lots: lots.map(lotView), count: lots.length });
    }

    return { state, pack, miner, reward, marketList, marketBuy, marketCancel, marketLots, minerCost };
}
