/* server/worker/src/api.js — ядро API: вход, витрина, спины, мины (b463)
 *
 * Как это работает простыми словами
 * ---------------------------------
 * Клиент больше НЕ считает деньги и НЕ знает, где лежат мины. Он отправляет
 * «крутить со ставкой N» — а сервер:
 *   1. проверяет токен устройства (подделать нельзя, см. crypto.js);
 *   2. проверяет, что игрок не заблокирован админом;
 *   3. списывает ставку ОДНОЙ атомарной операцией (не хватило — отказ);
 *   4. кладёт взнос в общий банк (процент из настроек Студии);
 *   5. крутит СВОИМ криптогенератором и считает выплату по общим правилам
 *      (assets/nx-rules.js — тот же файл, что грузит браузер);
 *   6. при трёх JACKPOT — выплачивает банк и пишет победителя в зал славы;
 *   7. возвращает результат, новый баланс и состояние банка.
 *
 * Редкости карт сервер берёт из СВОЕГО каталога комнаты, а не из слов клиента:
 * сказать «у меня все карты легендарные» больше не получится.
 *
 * Каждый запрос можно повторить с тем же oid (ключ операции) — второй раз
 * деньги не спишутся и не начислятся: сервер помнит ключ сутки (store.opsPut).
 */

import { M, S, N, json, err, now, rndId, secureRng, money } from './util.js';
import { verifyDeviceToken, verifyAdminToken, issueDeviceToken } from './crypto.js';
import { economyHandlers } from './economy.js';
import { adminHandlers } from './admin.js';

/** Правила, общие для браузера и сервера. */
export function rules() {
    return globalThis.NXR;
}

export function makeApi({ store, env }) {
    const R = rules();
    const secret = () => String(env.NX_SECRET || '');
    const rng = secureRng();

    // ---------------- контекст запроса ----------------
    function roomOf(body, headers) {
        const r = String((body && body.room) || headers.get('x-nx-room') || env.NX_ROOM || 'site').slice(0, 40);
        return r || 'site';
    }

    async function authPlayer(req, body) {
        if (!secret()) return { error: 'server_secret_missing' };
        const hdr = req.headers.get('authorization') || '';
        const tok = (hdr.indexOf('Bearer ') === 0 ? hdr.slice(7) : (body && body.token) || '');
        const cid = await verifyDeviceToken(secret(), tok);
        if (!cid) return { error: 'unauthorized' };
        const p = await store.playerGet(cid);
        if (!p) return { error: 'unknown_player' };
        if (p.del) return { error: 'deleted', blocked: true };
        if (p.blocked) return { error: 'blocked', blocked: true };
        return { cid, p };
    }

    async function authAdmin(req, body) {
        if (!secret()) return { error: 'server_secret_missing' };
        const hdr = req.headers.get('x-nx-admin') || req.headers.get('authorization') || '';
        const tok = hdr.indexOf('Bearer ') === 0 ? hdr.slice(7) : hdr;
        const login = await verifyAdminToken(secret(), tok || (body && body.adminToken));
        if (!login) return { error: 'admin_required' };
        return { login };
    }

    // ---------------- каталог комнаты ----------------
    async function catalog(room) {
        const c = await store.catalogGet(room);
        if (!c || !Array.isArray(c.cards)) return null;
        return c;
    }

    /** id карты → редкость по КАТАЛОГУ СЕРВЕРА. Неизвестная карта = common. */
    function cardIndex(cat) {
        const m = new Map();
        if (cat && Array.isArray(cat.cards)) {
            for (const c of cat.cards) {
                if (c && c.id) m.set(String(c.id), c);
            }
        }
        return m;
    }

    /** Собираем таблицу символов для барабанов: карты игрока + JACKPOT. */
    function resolveSymbols(cat, ids) {
        const idx = cardIndex(cat);
        const cards = [];
        const seen = {};
        for (const raw of (Array.isArray(ids) ? ids : [])) {
            const id = String(raw || '').slice(0, 80);
            if (!id || seen[id]) continue;
            seen[id] = 1;
            const c = idx.get(id);
            // редкость — только из каталога; неизвестную карту считаем обычной,
            // чтобы «нарисовать себе легендарку» в запросе было нельзя
            cards.push({
                id,
                rarity: (c && R.RARITY_WEIGHTS[c.rarity]) ? c.rarity : 'common',
                name: (c && c.name) || id,
                image: (c && c.image) || ''
            });
            if (cards.length >= 5) break;
        }
        return R.buildSymbols(cards);
    }

    // ---------------- настройки джекпота + гарантия ----------------
    async function jpcCfg(room) {
        const raw = await store.jpcGet(room);
        return R.jpcNorm(raw || null);
    }

    async function bumpPlayer(cid, fn) {
        return store.mutate(store.NS.PLAYER, cid, (p) => { fn(p); return p; });
    }

    /** Счётчики для заданий/достижений: сервер ведёт их сам, клиенту не верит. */
    function stBump(p, key, delta) {
        p.st = p.st || {};
        const cur = Number(p.st[key]) || 0;
        p.st[key] = Math.max(0, cur + Math.floor(Number(delta) || 0));
    }
    function stMax(p, key, val) {
        p.st = p.st || {};
        const v = Math.floor(Number(val) || 0);
        if (v > (Number(p.st[key]) || 0)) p.st[key] = v;
    }
    /** Прогресс заданий за сегодня: отдельный дневной срез counters. */
    function msnBump(p, type, delta) {
        const day = new Date().toISOString().slice(0, 10);
        p.msnDay = (p.msnDay && p.msnDay.d === day) ? p.msnDay : { d: day, c: {} };
        const key = R.MISSION_COUNTER[type];
        if (!key) return;
        p.msnDay.c[key] = Math.max(0, (Number(p.msnDay.c[key]) || 0) + Math.floor(Number(delta) || 0));
    }
    function msnGet(p, type) {
        const day = new Date().toISOString().slice(0, 10);
        if (!p.msnDay || p.msnDay.d !== day) return 0;
        const key = R.MISSION_COUNTER[type];
        return key ? (Number(p.msnDay.c[key]) || 0) : 0;
    }

    function playerView(p) {
        return {
            cid: p.cid, name: p.name || '', bal: money(M(p.bal)), blocked: !!p.blocked,
            zeroAt: Number(p.zeroAt) || 0, del: !!p.del,
            minerLvl: Number(p.minerLvl) || 1, minerLast: Number(p.minerLast) || 0,
            minerTotal: money(M(p.minerTotal || 0)), pity: Number(p.pity) || 0,
            pityG: p.pityG || {}, st: p.st || {}, msnDay: p.msnDay || null,
            ach: p.ach || {}, daily: p.daily || null
        };
    }

    function bankPublic(room, bank) {
        const v = store.bankView(bank);
        return { pot: v.pot, potN: v.potN, floor: v.floor, fed: v.fed, won: v.won, wins: v.wins, at: v.at };
    }

    // ================= ENDPOINTS =================

    /** POST /api/boot — первый вход: выдаём токен устройства и всё состояние. */
    async function boot(req, body, headers) {
        const cid = String((body && body.cid) || '').slice(0, 40);
        if (!/^[A-Za-z0-9_-]{4,40}$/.test(cid)) return err('bad_cid');
        if (!secret()) return err('server_secret_missing', 500);
        const room = roomOf(body, headers);
        const p = await store.playerEnsure(cid, {
            name: body && body.name, ip: headers.get('cf-connecting-ip') || '',
            dev: body && body.dev, did: body && body.did, prof: body && body.prof
        });
        const token = await issueDeviceToken(secret(), cid);
        const bank = await store.bankGet();
        const cfg = await jpcCfg(room);
        const hall = await store.hallGet();
        await syncStatsMirror(cid, p, room);
        return json({
            ok: true, token: token, cid: cid, room: room,
            player: playerView(p),
            bank: bankPublic(room, bank),
            cfg: cfg,
            hall: hall.slice(0, 40),
            top: topWins(hall),
            catalog: !!(await catalog(room)),
            serverMode: true
        });
    }

    function topWins(hall, windowMs) {
        const w = windowMs || 86400000;
        const cut = now() - w;
        return (hall || [])
            .filter(h => h && h.t >= cut && h.nm)
            .sort((a, b) => Number(M(b.a)) - Number(M(a.a)) === 0 ? 0 : (Number(M(b.a)) > Number(M(a.a)) ? 1 : -1))
            .slice(0, 3)
            .map(h => ({ n: h.n, a: S(M(h.a)), aN: N(M(h.a)), t: h.t, c: h.c }));
    }

    /** GET /api/public — витрина банка/зала славы для всех (без токена). */
    async function publicState(req, body, headers) {
        const room = roomOf(body || {}, headers);
        const bank = await store.bankGet();
        const hall = await store.hallGet();
        const cfg = await jpcCfg(room);
        const players = await store.drv.count(store.NS.PLAYER);
        return json({
            ok: true, room: room, bank: bankPublic(room, bank), cfg: cfg,
            hall: hall.slice(0, 40), top: topWins(hall), players: players,
            hasCatalog: !!(await catalog(room))
        });
    }

    /** Зеркало реестра игроков — его читает таблица «Пользователи» в Студии. */
    async function syncStatsMirror(cid, p, room) {
        try {
            const e = {
                cid: cid, n: p.name || ('Игрок-' + String(cid).slice(1, 5)),
                bal: S(M(p.bal)), balN: N(M(p.bal)),
                op: Number(p.st && p.st.packsOpened) || 0,
                jp: Number(p.st && p.st.jackpots) || 0,
                fed: S(M(p.fed || 0)), won: S(M(p.won || 0)),
                at: Number(p.seen) || now(),
                ip: p.ip || '', dev: p.dev || '', did: p.did || '', prof: p.prof || '',
                pk: p.pk || {}, alb: p.alb || {}
            };
            await store.statsPut(cid, e);
        } catch (e) {}
    }

    // ---------------- СПИНЫ ----------------

    /**
     * POST /api/spin {game, bet, cards?, room?, oid?}
     * game: slots | grid | lines | wheel
     */
    async function spin(req, body, headers) {
        const a = await authPlayer(req, body);
        if (a.error) return err(a.error, a.blocked ? 403 : 401);
        const { cid, p } = a;
        const room = roomOf(body, headers);
        const game = String(body.game || '');
        if (['slots', 'grid', 'lines', 'wheel'].indexOf(game) < 0) return err('bad_game');

        const cat = await catalog(room);
        if (!cat) return json({ ok: false, error: 'no_catalog', fallback: true }, 200);

        const bet = R.normBet(body.bet);
        if (!(bet >= 1)) return err('bad_bet');

        // Повторная доставка того же запроса: ключ операции занимаем ДО списания.
        // Если ключ уже занят — значит запрос уже обработан (или обрабатывается),
        // и второй раз ставка не спишется, а выигрыш не начислится.
        const oid = String(body.oid || '').slice(0, 80);
        if (oid) {
            const prev = await store.opsGet(oid);
            if (prev) {
                let cached = null;
                try { cached = JSON.parse(prev.v); } catch (e) { cached = null; }
                if (cached && cached.d && cached.d.ok) return json(cached.d);
                if (cached && !cached.d) return json({ ok: false, error: 'duplicate_in_progress', retry: true }, 200);
            }
            const claimed = await store.opsClaim(oid);
            if (!claimed) return json({ ok: false, error: 'duplicate', retry: true }, 200);
        }

        // денег хватает? списываем ставку атомарно
        const spent = await store.spend(cid, bet);
        if (!spent.ok) return json({ ok: false, error: 'not_enough', bal: money(M(spent.bal)) }, 200);

        const cfg = await jpcCfg(room);
        const GAME = game === 'slots' ? 'Slots' : game === 'grid' ? 'Grid' : game === 'lines' ? 'Lines' : 'Wheel';
        const pityIn = Number((p.pityG || {})[GAME]) || 0;
        const pct = R.jpcSpinPct(cfg, GAME, pityIn);

        // взнос ставки в общий банк (feedBet % — как jackpotFeed на клиенте)
        const feed = R.bankFeed(cfg, bet, 'bet');
        if (feed > 0) await store.bankFeed(feed);

        const syms = resolveSymbols(cat, body.cards);
        let out = { ok: true, id: rndId('sp'), game: game, bet: bet, win: 0, jpHit: false, pity: pityIn };

        if (game === 'slots') {
            const res = [0, 1, 2].map(() => R.pickSymbol(rng, syms, pct));
            const pay = R.slotsPayout(res, syms, bet);
            out.res = res;
            out.win = pay.win;
            out.mult = pay.mult;
            out.kind = pay.kind;
            out.jpHit = !!pay.jpHit;
            out.pity = R.jpcPityNext(cfg, GAME, pityIn, out.jpHit);
        } else if (game === 'grid') {
            const sim = R.gridSimulate(rng, syms, bet, pct, pityIn, cfg);
            out.res = { cells: sim.cells, steps: sim.steps };
            out.win = sim.total;
            out.chain = sim.chain;
            out.jpHit = !!sim.jpHit;
            out.pity = sim.pity;
        } else if (game === 'lines') {
            // пул линий: 3 карты + JACKPOT последним (app.js: linesMakePool)
            const idx = cardIndex(cat);
            const pick = [];
            const seen = {};
            for (const raw of (Array.isArray(body.cards) ? body.cards : [])) {
                const id = String(raw || '').slice(0, 80);
                if (!id || seen[id]) continue;
                seen[id] = 1;
                const c = idx.get(id);
                pick.push({ id: id, rarity: (c && R.RARITY_WEIGHTS[c.rarity]) ? c.rarity : 'common', name: (c && c.name) || id, image: (c && c.image) || '' });
                if (pick.length >= 3) break;
            }
            while (pick.length < 3) pick.push({ id: 'sym-x' + pick.length, name: 'Джокер', rarity: 'legendary', image: '' });
            const pool = pick.concat([{ id: 'sym-jackpot', name: 'JACKPOT', rarity: 'legendary', image: '', jackpot: true }]);
            const final = [];
            for (let i = 0; i < R.LINES_CELLS; i++) {
                final.push((pct > 0 && rng() * 100 < pct) ? 3 : Math.min(2, Math.floor(rng() * 3)));
            }
            const pay = R.linesPayout(final, pool, bet);
            out.res = final;
            out.pool = pool.map(s => s.id);
            out.win = pay.total;
            out.winCells = pay.winCells;
            out.winLines = pay.winLines;
            out.jpHit = !!pay.jpHit;
            out.pity = R.jpcPityNext(cfg, GAME, pityIn, out.jpHit);
        } else { // wheel
            const idx = R.wheelPickIdx(rng, pct);
            const sec = R.WHEEL_SECTORS[idx];
            out.res = idx;
            out.sector = sec;
            out.jpHit = sec.t === 'jackpot';
            out.pity = R.jpcPityNext(cfg, GAME, pityIn, out.jpHit);
            if (sec.t === 'mult') {
                out.win = Math.round(bet * (sec.m || 0));
            } else if (sec.t === 'card') {
                // карта в приз: берём случайный пак каталога и крутим одну карту
                const packs = (cat.packs || []).filter(pk => pk && pk.id);
                let card = null;
                if (packs.length) {
                    const pk = packs[Math.floor(rng() * packs.length)];
                    const pc = (cat.cards || []).filter(c => c && c.packId === pk.id);
                    if (pc.length) card = R.rollCardFromPack(rng, pc, false);
                }
                if (!card) {
                    const all = (cat.cards || []).filter(c => c && c.id);
                    if (all.length) card = all[Math.floor(rng() * all.length)];
                }
                if (card) {
                    out.card = { id: card.id, rarity: card.rarity || 'common', name: card.name || card.id, image: card.image || '', packId: card.packId || '' };
                } else {
                    out.win = bet; // паков с картами нет — возвращаем ставку (как на клиенте)
                }
            } else if (sec.t === 'mine') {
                out.minerLvlUp = 1; // кирка +1 — уровень поднимем в записи игрока
            }
        }

        // ---- деньги: выигрыш, джекпот или взнос проигрыша в банк ----
        let prize = 0n, secured = 0n, hallEntry = null;
        const bank0 = await store.bankGet();
        if (out.jpHit) {
            const pool = M(store.bankView(bank0).pot);
            const pz = BigInt(R.bankPrize(cfg, N(pool)));
            const paid = await store.bankPay(pz);
            prize = M(pz); secured = paid.secured;
            const wname = String(p.name || ('Игрок-' + String(cid).slice(1, 5))).slice(0, 24);
            hallEntry = { n: wname, a: S(prize), t: now(), c: cid, nm: p.name ? 1 : 0 };
            await store.hallPush(hallEntry);
            out.jp = { prize: S(prize), prizeN: N(prize), secured: S(secured) };
        }

        let credited = 0n;
        if (prize > 0n) credited += prize;
        if (out.win > 0) credited += BigInt(out.win);
        if (credited > 0n) await store.credit(cid, credited);

        // проигрыш кормит банк (feedLoss % — как jackpotOnLoss на клиенте)
        if (!out.jpHit && !(out.win > 0)) {
            const loss = game === 'wheel' && out.sector && out.sector.t === 'mult'
                ? Math.max(0, bet - (out.win || 0)) : bet;
            const add = R.bankFeed(cfg, loss, 'loss');
            if (add > 0) await store.bankFeed(add);
            out.fedLoss = add;
        }

        // ---- карта в приз (колесо) — в инвентарь и в статистику ----
        let dupeRefund = 0;
        if (out.card) {
            const copies = await store.invGet(cid, out.card.id);
            await store.invAdd(cid, out.card.id, 1);
            if (copies > 0) {
                dupeRefund = R.DUPE_REFUND[out.card.rarity] || 20;
                await store.credit(cid, dupeRefund);
                credited += BigInt(dupeRefund);
                out.card.dup = true;
                out.card.refund = dupeRefund;
            } else {
                out.card.dup = false;
            }
        }

        // ---- счётчики игрока, гарантия, задания ----
        const bankAfter = await store.bankGet();
        const pAfter = await bumpPlayer(cid, (pl) => {
            pl.st = pl.st || {};
            pl.pityG = pl.pityG || {};
            pl.pityG[GAME] = Number(out.pity) || 0;
            if (game === 'slots') { stBump(pl, 'slotsSpins', 1); if (out.win > 0) stBump(pl, 'slotsWins', 1); if (out.win > 0) stBump(pl, 'slotsCoins', out.win); }
            if (game === 'grid') { stBump(pl, 'gridSpins', 1); if (out.win > 0) { stBump(pl, 'gridWins', 1); stBump(pl, 'gridCoins', out.win); } stMax(pl, 'bestGridChain', out.chain || 0); }
            if (game === 'lines') { stBump(pl, 'linesSpins', 1); if (out.win > 0) { stBump(pl, 'linesWins', 1); stBump(pl, 'linesCoins', out.win); } }
            if (game === 'wheel') { stBump(pl, 'wheelSpins', 1); if (out.win > 0) stBump(pl, 'wheelCoins', out.win); }
            if (out.minerLvlUp) { pl.minerLvl = (Number(pl.minerLvl) || 1) + 1; stMax(pl, 'minerLvl', pl.minerLvl); }
            if (out.jpHit) stBump(pl, 'jackpots', 1);
            if (out.card) {
                stBump(pl, 'cardsGot', 1);
                if (!out.card.dup) stBump(pl, 'newCards', 1);
                if (out.card.rarity === 'rare' || out.card.rarity === 'epic' || out.card.rarity === 'legendary') stBump(pl, 'rarePlusFound', 1);
                if (out.card.rarity === 'epic' || out.card.rarity === 'legendary') stBump(pl, 'epicPlusFound', 1);
                if (out.card.rarity === 'legendary') stBump(pl, 'legendariesFound', 1);
                if (out.card.dup) { stBump(pl, 'dupesSold', 1); stBump(pl, 'dupeCoins', dupeRefund); }
            }
            pl.spins = (Number(pl.spins) || 0) + 1;
            if (out.win > 0 || out.jpHit) pl.wins = (Number(pl.wins) || 0) + 1;
            pl.fed = S(M(pl.fed || 0) + BigInt(feed || 0));
            if (prize > 0n) pl.won = S(M(pl.won || 0) + secured);
            pl.seen = now();
            // задания дня
            if (game === 'slots') { msnBump(pl, 'spin_slots', 1); if (out.win > 0) { msnBump(pl, 'win_slots', 1); msnBump(pl, 'slots_coins', out.win); } }
            if (game === 'grid') { msnBump(pl, 'spin_grid', 1); if (out.win > 0) { msnBump(pl, 'win_grid', 1); msnBump(pl, 'grid_coins', out.win); } }
            if (game === 'lines') { msnBump(pl, 'spin_lines', 1); if (out.win > 0) { msnBump(pl, 'win_lines', 1); msnBump(pl, 'lines_coins', out.win); } }
            if (game === 'wheel') { msnBump(pl, 'wheel_spin', 1); if (out.win > 0) msnBump(pl, 'wheel_coins', out.win); }
        });

        out.bal = money(M(pAfter ? pAfter.bal : 0));
        out.bank = bankPublic(room, bankAfter);
        out.hall = hallEntry ? (await store.hallGet()).slice(0, 40) : undefined;
        out.top = topWins(out.hall || (await store.hallGet()));
        out.st = (pAfter && pAfter.st) || {};
        out.msn = { spin_slots: msnGet(pAfter || {}, 'spin_slots') };
        out.msnDay = (pAfter && pAfter.msnDay) || null;
        out.minerLvl = Number(pAfter && pAfter.minerLvl) || 1;
        out.pityG = (pAfter && pAfter.pityG) || {};
        out.inv = out.card ? { [out.card.id]: await store.invGet(cid, out.card.id) } : undefined;

        await syncStatsMirror(cid, pAfter || p, room);
        // ответ кладём рядом с ключом операции: при повторной доставке клиент
        // получит ТОТ ЖЕ результат, а не второй спин
        if (oid) {
            try { await store.opsSettle(oid, out); } catch (e) {}
        }

        const resp = json(out);
        return resp;
    }

    // ---------------- МИНЫ ----------------
    /**
     * POST /api/mines {act:'start'|'pick'|'cashout', bet?, m?, id?, i?, oid?}
     * Раскладка мин клиенту НЕ отдаётся — он узнаёт только про открытую плитку.
     */
    async function mines(req, body, headers) {
        const a = await authPlayer(req, body);
        if (a.error) return err(a.error, a.blocked ? 403 : 401);
        const { cid } = a;
        const room = roomOf(body, headers);
        const cfg = await jpcCfg(room);
        const act = String(body.act || '');

        if (act === 'start') {
            const bet = R.normBet(body.bet);
            const m = R.MINES_COUNTS.indexOf(Number(body.m)) >= 0 ? Number(body.m) : 5;
            const spent = await store.spend(cid, bet);
            if (!spent.ok) return json({ ok: false, error: 'not_enough', bal: money(M(spent.bal)) }, 200);
            const feed = R.bankFeed(cfg, bet, 'bet');
            if (feed > 0) await store.bankFeed(feed);
            const id = rndId('mn');
            const layout = R.minesLayout(rng, m);
            await store.minesPut({ id: id, cid: cid, bet: bet, m: m, mines: layout, picked: [], state: 'live', at: now(), room: room });
            await bumpPlayer(cid, (pl) => { pl.msnDay = pl.msnDay; msnBump(pl, 'mines_open', 0); });
            return json({ ok: true, act: 'start', id: id, bet: bet, m: m, mult: 1, tiles: R.MINES_TILES, bal: money(M(spent.bal)) });
        }

        const g = await store.minesGet(String(body.id || '').slice(0, 60));
        if (!g || g.cid !== cid || g.state !== 'live') return err('no_game', 404);
        const i = Math.floor(Number(body.i));

        if (act === 'pick') {
            if (!(i >= 0 && i < R.MINES_TILES)) return err('bad_tile');
            if (g.picked.indexOf(i) >= 0) return json({ ok: true, act: 'pick', i: i, repeat: true, mult: R.minesMult(g.picked.length, g.m), picked: g.picked.length });
            const boom = g.mines.indexOf(i) >= 0;
            if (boom) {
                g.state = 'bust'; g.picked.push(i); g.at = now();
                await store.minesPut(g);
                const add = R.bankFeed(cfg, g.bet, 'loss');
                if (add > 0) await store.bankFeed(add);
                const p = await bumpPlayer(cid, (pl) => { stBump(pl, 'minesBust', 1); });
                await store.minesDel(g.id);
                return json({
                    ok: true, act: 'pick', mine: true, i: i, mult: 0, win: 0, fedLoss: add,
                    mines: g.mines, bal: money(M(p ? p.bal : 0)), bank: bankPublic(room, await store.bankGet())
                });
            }
            g.picked.push(i); g.at = now();
            await store.minesPut(g);
            const k = g.picked.length;
            const p = await bumpPlayer(cid, (pl) => { stBump(pl, 'minesOpen', 1); msnBump(pl, 'mines_open', 1); });
            return json({ ok: true, act: 'pick', mine: false, i: i, picked: k, mult: R.minesMult(k, g.m), bal: money(M(p ? p.bal : 0)) });
        }

        if (act === 'cashout') {
            const k = g.picked.filter(x => g.mines.indexOf(x) < 0).length;
            if (k <= 0) return err('nothing_to_cashout');
            const mult = R.minesMult(k, g.m);
            const win = BigInt(Math.floor(Number(g.bet) * mult));
            g.state = 'paid'; g.at = now();
            await store.minesPut(g);
            const bal = await store.credit(cid, win);
            const p = await bumpPlayer(cid, (pl) => {
                stBump(pl, 'minesWins', 1); stBump(pl, 'minesCoins', N(win));
                msnBump(pl, 'mines_win', 1); msnBump(pl, 'mines_coins', N(win));
            });
            await store.minesDel(g.id);
            await syncStatsMirror(cid, p || {}, room);
            return json({ ok: true, act: 'cashout', win: S(win), winN: N(win), mult: mult, picked: k, bal: money(M(bal)) });
        }

        return err('bad_act');
    }

    const eco = economyHandlers({ store, env, R, rng, authPlayer, authAdmin, catalog, cardIndex, bumpPlayer, stBump, stMax, msnBump, msnGet, playerView, syncStatsMirror, bankPublic, roomOf, topWins });
    const adm = adminHandlers({ store, env, R, authAdmin, authPlayer, bankPublic, playerView, syncStatsMirror, topWins, roomOf });

    const routes = {
        'POST /api/boot': boot,
        'GET /api/public': publicState,
        'POST /api/spin': spin,
        'POST /api/mines': mines,
        'GET /api/state': async (req, body, headers) => eco.state(req, body || {}, headers),
        'POST /api/pack': (req, body, headers) => eco.pack(req, body, headers),
        'POST /api/miner': (req, body, headers) => eco.miner(req, body, headers),
        'POST /api/reward': (req, body, headers) => eco.reward(req, body, headers),
        'POST /api/market/list': (req, body, headers) => eco.marketList(req, body, headers),
        'POST /api/market/buy': (req, body, headers) => eco.marketBuy(req, body, headers),
        'POST /api/market/cancel': (req, body, headers) => eco.marketCancel(req, body, headers),
        'GET /api/market/lots': (req, body, headers) => eco.marketLots(req, body || {}, headers),
        'POST /api/studio/login': (req, body, headers) => adm.login(req, body, headers),
        'POST /api/studio/setup': (req, body, headers) => adm.setup(req, body, headers),
        'POST /api/admin': (req, body, headers) => adm.act(req, body, headers),
        'GET /api/admin/users': (req, body, headers) => adm.users(req, body || {}, headers),
        'POST /api/migrate': (req, body, headers) => adm.migrate(req, body, headers),
        'GET /api/health': async () => json({ ok: true, ts: now(), store: store.drv.kind, secret: !!secret() })
    };

    return { routes, handlers: { boot, publicState, spin, mines }, eco, adm, store, env };
}
