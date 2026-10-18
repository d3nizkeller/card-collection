/* server/worker/src/admin.js — Студия и админка на сервере (b463)
 *
 * ЭТАП 1: пароль Студии и все админ-действия переехали сюда.
 *
 * Как было: пароль комнаты (его хэш и соль) лежал в общем облачном документе,
 * клиент сам считал хэш и сам решал, пускать ли в Студию. Достаточно было
 * написать в консоли `studioUnlocked = true; cloudRole = 'owner'` — и вся
 * админка (обнуление балансов, блокировки, «Поставить банк», «Выдать ВСЕМ»)
 * открывалась. Сами действия тоже выполнялись на клиенте записью в общий
 * документ: любой игрок мог повторить их без всякой Студии.
 *
 * Как стало: клиент отправляет логин и пароль на /api/studio/login, сервер
 * сверяет их со своим хэшем (PBKDF2-SHA256, 150 000 итераций) и выдаёт
 * админ-токен на 12 часов. Каждое действие админки требует этот токен и
 * выполняется на сервере, с записью в журнал (audit). Пароля и его хэша в
 * клиентском коде больше нет вовсе.
 *
 * Перенос старого пароля: в общем документе комнаты хранится auth = {login, hash,
 * salt}, где hash — sha256-цепочка клиента (512 раундов). Миграция кладёт эту
 * запись на сервер как «устаревшую», и при первом входе сервер проверяет
 * пароль по старому алгоритму, а затем сразу пересохраняет его в PBKDF2.
 * Владелец входит тем же паролем, что и раньше, — ничего менять не нужно.
 */

import { M, S, N, json, err, now, money, makeRateLimiter } from './util.js';
import {
    makePasswordRecord, verifyPassword, issueAdminToken, normLogin, validateCreds, safeEq
} from './crypto.js';

const enc = new TextEncoder();

function hex(buf) {
    return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
}
async function sha256(str) {
    return crypto.subtle.digest('SHA-256', enc.encode(str));
}

/** Точный порт клиентского cloudHashPass: SHA-256 + соль, 512 раундов. */
export async function legacyHashPass(pass, salt) {
    const s = String(salt == null ? '' : salt);
    let h = await sha256(s + ':' + String(pass));
    for (let i = 0; i < 511; i++) h = await sha256(hex(h) + s);
    return 'sha256:' + hex(h);
}

/** Запасной слабый хэш клиента (cloudHashWeak) — для записей вида 'w1:…'. */
export function legacyWeakHash(str) {
    let h1 = 0x811c9dc5, h2 = 0x9e3779b9;
    for (let r = 0; r < 256; r++) {
        for (let i = 0; i < str.length; i++) {
            const c = (str.charCodeAt(i) + r) & 0xffff;
            h1 = (h1 ^ c) >>> 0; h1 = (h1 * 0x01000193) >>> 0;
            h2 = (h2 + c + (h1 >>> 13)) >>> 0; h2 = ((h2 << 7) | (h2 >>> 25)) >>> 0;
            h1 = (h1 ^ h2) >>> 0;
        }
    }
    return 'w1:' + h1.toString(16).padStart(8, '0') + h2.toString(16).padStart(8, '0');
}

export function adminHandlers(ctx) {
    const { store, env, R, authAdmin, bankPublic, playerView, syncStatsMirror, topWins, roomOf } = ctx;

    // Защита от подбора пароля: 8 попыток в минуту на IP+логин
    const loginLimiter = makeRateLimiter({ limit: 8, windowMs: 60000 });

    function credsKey(login) { return normLogin(login); }

    // =============== ВХОД В СТУДИЮ ===============
    async function login(req, body, headers) {
        const ip = headers.get('cf-connecting-ip') || 'local';
        const login = normLogin(body && body.login);
        if (!loginLimiter(ip + '|' + login)) return err('too_many_attempts', 429);

        const rec = await store.credsGet(credsKey(login));
        if (!rec) return json({ ok: false, error: 'Неверный логин или пароль' }, 200);

        const pass = String((body && body.pass) || '');
        let ok = false, upgraded = false;

        if (rec.hash && String(rec.hash).indexOf('pbkdf2$') === 0) {
            ok = await verifyPassword(pass, rec.hash);
        } else if (rec.legacyHash) {
            // старая запись из общего документа: проверяем прежним алгоритмом
            const calc = String(rec.legacyHash).indexOf('w1:') === 0
                ? legacyWeakHash(String(rec.legacySalt || '') + ':' + pass)
                : await legacyHashPass(pass, rec.legacySalt || '');
            ok = safeEq(calc, String(rec.legacyHash));
            if (ok) {
                // сразу переводим пароль на PBKDF2 — старый хэш больше не нужен
                rec.hash = await makePasswordRecord(pass);
                delete rec.legacyHash; delete rec.legacySalt;
                rec.at = now(); rec.upgradedAt = now();
                await store.credsSet(credsKey(login), rec);
                upgraded = true;
            }
        }

        if (!ok) {
            await store.audit({ who: 'anon', act: 'login_fail', target: login, detail: ip });
            return json({ ok: false, error: 'Неверный логин или пароль' }, 200);
        }

        const token = await issueAdminToken(String(env.NX_SECRET || ''), login);
        await store.audit({ who: login, act: 'login', target: login, detail: ip });
        return json({ ok: true, login: login, adminToken: token, upgraded: upgraded, ttl: 12 * 3600 * 1000 });
    }

    /**
     * POST /api/studio/setup — создать/сменить учётку Студии.
     * Создать можно, только если на сервере ещё нет ни одной учётки
     * (иначе любой посетитель назначил бы себя владельцем). Смена — по
     * админ-токену и с текущим паролем.
     */
    async function setup(req, body, headers) {
        const login = normLogin(body && body.login);
        const pass = String((body && body.pass) || '');
        const bad = validateCreds(login, pass);
        if (bad) return json({ ok: false, error: bad }, 200);

        const existing = await store.credsList();
        const a = await authAdmin(req, body);

        if (!existing.length) {
            // первая учётка: защищаем ключом развёртывания, если он задан
            const key = String(env.NX_SETUP_KEY || '');
            if (key && String(body.setupKey || '') !== key) return err('setup_key_required', 403);
            const rec = { login: login, hash: await makePasswordRecord(pass), at: now(), createdBy: 'first-run' };
            await store.credsSet(credsKey(login), rec);
            await store.audit({ who: login, act: 'setup_first', target: login });
            const token = await issueAdminToken(String(env.NX_SECRET || ''), login);
            return json({ ok: true, login: login, adminToken: token, first: true });
        }

        if (a.error) return err('admin_required', 403);

        // смена пароля существующей учётки
        const rec = await store.credsGet(credsKey(a.login));
        if (!rec) return err('no_creds', 404);
        const cur = String((body && body.currentPass) || '');
        const curOk = rec.hash ? await verifyPassword(cur, rec.hash) : false;
        if (!curOk) return json({ ok: false, error: 'Текущий пароль указан неверно' }, 200);
        rec.hash = await makePasswordRecord(pass);
        rec.at = now();
        delete rec.legacyHash; delete rec.legacySalt;
        await store.credsSet(credsKey(a.login), rec);
        await store.audit({ who: a.login, act: 'pass_change', target: a.login });
        return json({ ok: true, login: a.login, changed: true });
    }

    // =============== ДЕЙСТВИЯ АДМИНКИ ===============
    function cidsOf(body) {
        if (body.all) return null;                       // null = все игроки
        if (Array.isArray(body.cids) && body.cids.length) return body.cids.map(c => String(c).slice(0, 40));
        if (body.cid) return [String(body.cid).slice(0, 40)];
        return [];
    }

    async function grantOne(cid, amount, cfg, actor, room) {
        const p = await store.playerGet(cid);
        if (!p) return { cid: cid, ok: false, error: 'no_player' };
        if (amount > 0n) {
            const bal = await store.credit(cid, amount);
            await store.audit({ who: actor, act: 'grant', target: cid, detail: S(amount) });
            return { cid: cid, ok: true, amount: S(amount), bal: money(M(bal)) };
        }
        // 0 = весь банк по payout % — как обычный срыв джекпота
        const bank0 = await store.bankGet();
        const pool = M(store.bankView(bank0).pot);
        const prize = BigInt(R.bankPrize(cfg, N(pool)));
        if (prize <= 0n) return { cid: cid, ok: false, error: 'bank_empty' };
        const paid = await store.bankPay(prize);
        const bal = await store.credit(cid, prize);
        const wname = String(p.name || ('Игрок-' + String(cid).slice(1, 5))).slice(0, 24);
        const entry = { n: wname, a: S(prize), t: now(), c: cid, nm: p.name ? 1 : 0, admin: 1 };
        await store.hallPush(entry);
        await store.mutate(store.NS.PLAYER, cid, (pl) => {
            pl.won = S(M(pl.won || 0) + paid.secured);
            stBumpLocal(pl, 'jackpots', 1);
            return pl;
        });
        await syncStatsMirror(cid, await store.playerGet(cid), room);
        await store.audit({ who: actor, act: 'grant_bank', target: cid, detail: S(prize) });
        return { cid: cid, ok: true, amount: S(prize), bal: money(M(bal)), hall: entry };
    }

    function stBumpLocal(p, key, delta) {
        p.st = p.st || {};
        p.st[key] = Math.max(0, (Number(p.st[key]) || 0) + Math.floor(Number(delta) || 0));
    }

    async function act(req, body, headers) {
        const a = await authAdmin(req, body);
        if (a.error) return err(a.error, 403);
        const room = roomOf(body, headers);
        const what = String(body.act || '');
        const cfg = R.jpcNorm(await store.jpcGet(room));

        // ---- управление балансами игроков ----
        if (what === 'zero' || what === 'block' || what === 'unblock' || what === 'delete') {
            const cids = cidsOf(body);
            if (cids === null) {
                const all = await store.playerList();
                const done = [];
                for (const p of all) done.push(await applyUserAct(p.cid, what, a.login, room));
                return json({ ok: true, act: what, all: true, count: done.length, results: done.slice(0, 200) });
            }
            if (!cids.length) return err('no_target');
            const done = [];
            for (const cid of cids.slice(0, 500)) done.push(await applyUserAct(cid, what, a.login, room));
            return json({ ok: true, act: what, count: done.length, results: done });
        }

        // ---- выдача джекпота ----
        if (what === 'grant') {
            const amount = M(body.amount);
            if (amount < 0n) return err('bad_amount');
            const cids = cidsOf(body);
            if (cids === null || (cids.length === 1 && cids[0] === '*')) {
                // «Выдать ВСЕМ»: банк тратится последовательно и не уходит ниже пола
                const all = (await store.playerList()).filter(p => !p.del && !p.blocked);
                const done = [];
                for (const p of all.slice(0, 500)) done.push(await grantOne(p.cid, amount, cfg, a.login, room));
                return json({ ok: true, act: 'grant', all: true, count: done.length, results: done.slice(0, 200), bank: bankPublic(room, await store.bankGet()) });
            }
            if (!cids.length) return err('no_target');
            const done = [];
            for (const cid of cids.slice(0, 500)) done.push(await grantOne(cid, amount, cfg, a.login, room));
            return json({ ok: true, act: 'grant', count: done.length, results: done, bank: bankPublic(room, await store.bankGet()) });
        }

        // ---- банк ----
        if (what === 'poolSet') {
            const target = M(body.value);
            if (target < 0n) return err('bad_value');
            const b = await store.bankSetPool(target);
            await store.audit({ who: a.login, act: 'pool_set', target: 'bank', detail: S(target) });
            return json({ ok: true, act: 'poolSet', bank: bankPublic(room, b) });
        }
        if (what === 'poolNudge') {
            const d = M(body.delta);
            const b0 = await store.bankGet();
            const target = M(store.bankView(b0).pot) + d;
            const b = await store.bankSetPool(target < 0n ? 0n : target);
            await store.audit({ who: a.login, act: 'pool_nudge', target: 'bank', detail: S(d) });
            return json({ ok: true, act: 'poolNudge', bank: bankPublic(room, b) });
        }
        if (what === 'poolFloor') {
            const f = M(body.value !== undefined ? body.value : cfg.floor);
            const b = await store.bankSetFloor(f);
            await store.audit({ who: a.login, act: 'pool_floor', target: 'bank', detail: S(f) });
            return json({ ok: true, act: 'poolFloor', bank: bankPublic(room, b) });
        }
        if (what === 'hallReset') {
            await store.hallClear();
            await store.audit({ who: a.login, act: 'hall_reset', target: 'hall' });
            return json({ ok: true, act: 'hallReset', hall: [], top: [] });
        }

        // ---- настройки джекпота (вкладка «Джекпот» в Студии) ----
        if (what === 'cfg' || what === 'cfgReset') {
            const next = R.jpcNorm(what === 'cfgReset' ? null : body.cfg);
            next.at = now(); next.by = a.login;
            await store.jpcSet(room, next);
            await store.audit({ who: a.login, act: what, target: 'jpc', detail: JSON.stringify(next).slice(0, 400) });
            return json({ ok: true, act: what, cfg: next });
        }

        // ---- каталог комнаты: паки и карты (нужен серверу для честных вскрытий) ----
        if (what === 'catalog') {
            const packs = Array.isArray(body.packs) ? body.packs.slice(0, 200) : [];
            const cards = Array.isArray(body.cards) ? body.cards.slice(0, 20000) : [];
            if (!packs.length || !cards.length) return err('empty_catalog');
            const slim = cards.map(c => ({
                id: String((c && c.id) || '').slice(0, 80),
                packId: String((c && c.packId) || '').slice(0, 80),
                rarity: R.RARITY_WEIGHTS[c && c.rarity] ? c.rarity : 'common',
                name: String((c && c.name) || '').slice(0, 80),
                image: String((c && c.image) || '').slice(0, 300)
            })).filter(c => c.id);
            const slimPacks = packs.map(p => ({
                id: String((p && p.id) || '').slice(0, 80),
                title: String((p && p.title) || '').slice(0, 80),
                price: Math.max(0, Math.floor(Number(p && p.price) || 0)),
                retired: !!(p && p.retired),
                saleUntil: Number((p && p.saleUntil) || 0) || undefined,
                premiereAt: Number((p && p.premiereAt) || 0) || undefined,
                schedule: (p && p.schedule) || undefined
            })).filter(p => p.id);
            await store.catalogSet(room, { packs: slimPacks, cards: slim, by: a.login });
            await store.audit({ who: a.login, act: 'catalog', target: room, detail: 'паков ' + slimPacks.length + ', карт ' + slim.length });
            return json({ ok: true, act: 'catalog', packs: slimPacks.length, cards: slim.length });
        }

        // ---- журнал ----
        if (what === 'audit') {
            return json({ ok: true, act: 'audit', items: await store.auditList(200) });
        }

        return err('bad_act');
    }

    /** Обнулить / заблокировать / разблокировать / удалить игрока. */
    async function applyUserAct(cid, what, actor, room) {
        const p0 = await store.playerGet(cid);
        if (!p0) return { cid: cid, ok: false, error: 'no_player' };
        const t = now();
        const p = await store.mutate(store.NS.PLAYER, cid, (pl) => {
            if (what === 'zero') { pl.bal = '0'; pl.zeroAt = t; }
            if (what === 'block') { pl.blocked = 1; pl.blockAt = t; pl.bal = '0'; pl.zeroAt = t; }
            if (what === 'unblock') { pl.blocked = 0; pl.blockAt = 0; pl.del = 0; }
            if (what === 'delete') { pl.blocked = 1; pl.del = 1; pl.blockAt = t; pl.bal = '0'; pl.zeroAt = t; }
            pl.seen = t;
            return pl;
        });
        await syncStatsMirror(cid, p || p0, room);
        await store.audit({ who: actor, act: what, target: cid, detail: 'баланс ' + S(M(p ? p.bal : 0)) });
        return { cid: cid, ok: true, act: what, bal: money(M(p ? p.bal : 0)), blocked: !!(p && p.blocked), zeroAt: Number(p && p.zeroAt) || 0, del: !!(p && p.del) };
    }

    /** Таблица «Пользователи» в Студии: данные берёт с сервера, а не из документа. */
    async function users(req, body, headers) {
        const a = await authAdmin(req, {});
        if (a.error) return err(a.error, 403);
        const room = roomOf(body || {}, headers);
        const list = await store.playerList();
        const bank = await store.bankGet();
        const out = list.map(p => ({
            cid: p.cid, n: p.name || '', bal: S(M(p.bal)), balN: N(M(p.bal)),
            op: Number((p.st || {}).packsOpened) || 0,
            jp: Number((p.st || {}).jackpots) || 0,
            fed: S(M(p.fed || 0)), won: S(M(p.won || 0)),
            at: Number(p.seen) || 0, ip: p.ip || '', dev: p.dev || '', did: p.did || '', prof: p.prof || '',
            blocked: !!p.blocked, del: !!p.del, minerLvl: Number(p.minerLvl) || 1,
            pk: p.pk || {}, alb: p.alb || {}
        })).sort((x, y) => (y.at || 0) - (x.at || 0));
        return json({
            ok: true, room: room, players: out, count: out.length,
            bank: bankPublic(room, bank),
            cfg: R.jpcNorm(await store.jpcGet(room)),
            audit: await store.auditList(50)
        });
    }

    // =============== МИГРАЦИЯ ТЕКУЩИХ ДАННЫХ ===============
    /**
     * POST /api/migrate — перенос того, что уже лежит в общем облачном документе
     * (nexus-jackpot-v3 на textdb.dev или в Firebase-комнате): банк, зал славы,
     * настройки джекпота, реестр игроков с их балансами, блокировки, обнуления,
     * лоты биржи и квитанции. Плюс каталог комнаты (паки/карты).
     *
     * Данные НЕ ТЕРЯЮТСЯ: баланс каждого игрока переносится как есть, банк
     * пересчитывается по той же формуле (floor + Σвзносов − Σвыплат).
     * Повторный запуск безопасен: существующие игроки обновляются только если
     * их запись ещё не тронута игрой (force=1 перезаписывает балансы).
     */
    async function migrate(req, body, headers) {
        const a = await authAdmin(req, body);
        if (a.error) return err(a.error, 403);
        const room = roomOf(body, headers);
        const doc = (body && body.doc) || {};
        const jp = doc.jp || doc;
        const st = doc.st || {};
        const mk = doc.mk || {};
        const force = !!(body && body.force);
        const rep = { room: room, players: 0, skipped: 0, blocked: 0, zeroed: 0, hall: 0, lots: 0, ledger: 0, bank: null, cfg: null, catalog: null };

        // ---- банк: Σвзносов и Σвыплат из реестра (с разрядами cid#N) ----
        function ledgerSum(map) {
            let s = 0n;
            const per = {};
            for (const k in (map || {})) {
                const v = M(map[k]);
                if (v <= 0n) continue;
                const h = String(k).indexOf('#');
                const base = h > 0 ? k.slice(0, h) : String(k);
                per[base] = (per[base] || 0n) + v;
                s += v;
            }
            return { total: s, per: per };
        }
        const fed = ledgerSum(jp.led), won = ledgerSum(jp.won);
        const floor = M((doc.jpc && doc.jpc.floor) || 1000);
        await store.mutate(store.NS.BANK, 'main', (b) => {
            b.floor = S(floor);
            b.fed = S(fed.total);
            b.won = S(won.total);
            b.wins = Number(jp.wins ? Object.keys(jp.wins).reduce((s, k) => s + (Number(jp.wins[k]) || 0), 0) : 0) || 0;
            b.at = now();
            return b;
        }, { create: store.bankBlank });
        rep.bank = bankPublic(room, await store.bankGet());

        // ---- настройки джекпота ----
        if (doc.jpc && typeof doc.jpc === 'object') {
            const cfg = R.jpcNorm(doc.jpc);
            cfg.at = Number(doc.jpc.at) || now();
            cfg.by = String(doc.jpc.by || 'migrate');
            await store.jpcSet(room, cfg);
            rep.cfg = cfg;
        }

        // ---- зал славы ----
        if (Array.isArray(jp.hall)) {
            const cut = Math.floor(jp.hallCut) || 0;
            for (const h of jp.hall.slice(0, 40)) {
                if (!h || !h.t || h.t <= cut) continue;
                await store.hallPush({ n: String(h.n || '').slice(0, 24), a: S(M(h.a)), t: Number(h.t), c: String(h.c || '').slice(0, 40), nm: h.nm ? 1 : 0, migrated: 1 });
                rep.hall++;
            }
        }

        // ---- игроки: баланс, имя, статистика, блокировки, обнуления ----
        const registry = (st && st.p) || {};
        const blocks = (st && st.b) || {};
        const zeroes = (st && st.z) || {};
        for (const cid in registry) {
            const e = registry[cid] || {};
            const id = String(cid).slice(0, 40);
            if (!id) continue;
            const existed = await store.playerGet(id);
            const played = existed && (Number(existed.spins) || 0) > 0;
            if (existed && played && !force) { rep.skipped++; continue; }
            await store.mutate(store.NS.PLAYER, id, (pl) => {
                pl.name = String(e.n || pl.name || '').slice(0, 24);
                if (!played || force) pl.bal = S(M(e.bal));
                pl.st = pl.st || {};
                pl.st.packsOpened = Math.max(Number(pl.st.packsOpened) || 0, Number(e.op) || 0);
                pl.st.jackpots = Math.max(Number(pl.st.jackpots) || 0, Number(e.jp) || 0);
                pl.fed = S(M(e.fed) > M(pl.fed || 0) ? M(e.fed) : M(pl.fed || 0));
                pl.won = S(M(e.won) > M(pl.won || 0) ? M(e.won) : M(pl.won || 0));
                pl.ip = String(e.ip || pl.ip || '').slice(0, 45);
                pl.dev = String(e.dev || pl.dev || '').slice(0, 90);
                pl.did = String(e.did || pl.did || '').slice(0, 24);
                pl.prof = String(e.prof || pl.prof || '').slice(0, 24);
                pl.pk = (e.pk && typeof e.pk === 'object') ? e.pk : (pl.pk || {});
                pl.alb = (e.alb && typeof e.alb === 'object') ? e.alb : (pl.alb || {});
                pl.migrated = now();
                pl.seen = Number(e.at) || now();
                return pl;
            }, { create: () => store.playerBlank(id) });
            const b = blocks[id];
            const z = zeroes[id];
            if (b || z) {
                await store.mutate(store.NS.PLAYER, id, (pl) => {
                    if (b && b.on) { pl.blocked = 1; pl.blockAt = Number(b.at) || now(); pl.del = b.del ? 1 : 0; }
                    if (z) { pl.zeroAt = Number(z) || now(); if (!played || force) pl.bal = '0'; }
                    return pl;
                });
                if (b && b.on) rep.blocked++;
                if (z) rep.zeroed++;
            }
            await syncStatsMirror(id, await store.playerGet(id), room);
            rep.players++;
        }

        // ---- биржа: открытые лоты и неоплаченные квитанции ----
        const lots = Array.isArray(mk.lots) ? mk.lots : (Array.isArray(mk) ? mk : []);
        for (const l of lots.slice(0, 2000)) {
            if (!l || !l.id || !l.card) continue;
            const exists = await store.lotGet(String(l.id));
            if (exists) continue;
            const snap = Object.assign({}, l.card);
            if (typeof snap.image === 'string' && snap.image.indexOf('data:') === 0) snap.image = '';
            await store.lotPut({
                id: String(l.id).slice(0, 80), sid: String(l.sid || '').slice(0, 40),
                sname: String(l.sname || '').slice(0, 24), price: S(M(l.price)),
                card: snap, at: Number(l.at) || now(), status: 'open', migrated: 1
            });
            // копия карты уходит в эскроу сервера
            if (l.sid && snap.id) await store.invAdd(String(l.sid).slice(0, 40), String(snap.id), -1);
            rep.lots++;
        }
        const ledger = Array.isArray(mk.ledger) ? mk.ledger : [];
        for (const r of ledger.slice(0, 2000)) {
            if (!r || !r.id) continue;
            await store.ledgerAdd({
                id: String(r.id).slice(0, 80), sid: String(r.sid || '').slice(0, 40),
                amount: S(M(r.amount)), at: Number(r.at) || now(),
                bname: String(r.bname || '').slice(0, 24), paid: 0, migrated: 1
            });
            rep.ledger++;
        }

        // ---- каталог комнаты (паки/карты) — из body.catalog ----
        if (body.catalog && Array.isArray(body.catalog.cards)) {
            const cards = body.catalog.cards.slice(0, 20000).map(c => ({
                id: String((c && c.id) || '').slice(0, 80),
                packId: String((c && c.packId) || '').slice(0, 80),
                rarity: R.RARITY_WEIGHTS[c && c.rarity] ? c.rarity : 'common',
                name: String((c && c.name) || '').slice(0, 80),
                image: String((c && c.image) || '').slice(0, 300)
            })).filter(c => c.id);
            const packs = (Array.isArray(body.catalog.packs) ? body.catalog.packs : []).slice(0, 200).map(p => ({
                id: String((p && p.id) || '').slice(0, 80),
                title: String((p && p.title) || '').slice(0, 80),
                price: Math.max(0, Math.floor(Number(p && p.price) || 0)),
                retired: !!(p && p.retired),
                saleUntil: Number((p && p.saleUntil) || 0) || undefined,
                premiereAt: Number((p && p.premiereAt) || 0) || undefined,
                schedule: (p && p.schedule) || undefined
            })).filter(p => p.id);
            await store.catalogSet(room, { packs: packs, cards: cards, by: 'migrate' });
            rep.catalog = { packs: packs.length, cards: cards.length };
        }

        // ---- устаревшая учётка Студии (вход прежним паролем) ----
        const auth = (body.legacyAuth && typeof body.legacyAuth === 'object') ? body.legacyAuth : (doc.auth || null);
        if (auth && auth.login && auth.hash) {
            const key = credsKey(auth.login);
            const existed = await store.credsGet(key);
            if (!existed) {
                await store.credsSet(key, {
                    login: key, legacyHash: String(auth.hash).slice(0, 200),
                    legacySalt: String(auth.salt || '').slice(0, 40),
                    at: now(), createdBy: 'migrate'
                });
                rep.studioAuth = key;
            }
        }

        await store.audit({ who: a.login, act: 'migrate', target: room, detail: JSON.stringify({ players: rep.players, skipped: rep.skipped, lots: rep.lots }) });
        return json({ ok: true, migrate: rep });
    }

    return { login, setup, act, users, migrate, legacyHashPass, legacyWeakHash };
}
