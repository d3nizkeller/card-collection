/* server/worker/src/store.js — доменный слой поверх драйвера kv (b463)
 *
 * Здесь живут все правила хранения денег и банка. Главное свойство слоя:
 * любое изменение состояния — это «прочитал запись вместе с версией → посчитал
 * новое значение → записал, только если версия не изменилась». Если изменилась
 * (кто-то успел раньше), операция повторяется. Это и есть защита от гонки,
 * из-за которой раньше два одновременных срыва джекпота гасили друг друга,
 * а одна и та же ставка могла зачислиться дважды.
 *
 * Деньги — BigInt (см. util.js). В базе лежат десятичной строкой.
 */

import { M, S, N, NXConflict, withRetry, now, rndId, money } from './util.js';

export const NS = {
    PLAYER: 'p', BANK: 'bank', HALL: 'hall', JPC: 'jpc', CATALOG: 'catalog',
    CREDS: 'creds', CFG: 'cfg', OPS: 'ops', MINES: 'mines', LOTS: 'lots',
    LEDGER: 'ledger', INV: 'inv', AUDIT: 'audit', STATS: 'stats', MISSION: 'msn'
};

const OPS_TTL_MS = 26 * 3600 * 1000;   // ключ операции живёт сутки — дальше не нужен
const HALL_MAX = 40;                   // окно зала славы, как на клиенте (b431)
const AUDIT_MAX = 400;                 // журнал действий админки

export function makeStore(drv) {
    // ---------------- базовые операции ----------------
    async function read(ns, k) {
        const r = await drv.get(ns, k);
        if (!r) return null;
        let v = null;
        try { v = r.v == null ? null : JSON.parse(r.v); } catch (e) { v = null; }
        return { v, ver: r.ver };
    }

    async function write(ns, k, v, expectVer) {
        return drv.put(ns, k, JSON.stringify(v == null ? null : v), expectVer);
    }

    /**
     * Атомарная правка записи с повтором при гонке.
     * fn(obj) возвращает новое значение; если вернёт undefined — запись не меняется.
     */
    async function mutate(ns, k, fn, { create = null } = {}) {
        return withRetry(async () => {
            let cur = await read(ns, k);
            if (!cur && create !== null) {
                const fresh = typeof create === 'function' ? create() : JSON.parse(JSON.stringify(create));
                const ok = await write(ns, k, fresh, 0);
                if (!ok) throw new NXConflict('create ' + ns + '/' + k);
                cur = { v: fresh, ver: 1 };
            }
            if (!cur) return null;
            const next = await fn(cur.v, cur.ver);
            if (next === undefined) return cur.v;
            const ok = await write(ns, k, next, cur.ver);
            if (!ok) throw new NXConflict('update ' + ns + '/' + k);
            return next;
        });
    }

    async function get(ns, k, dflt = null) {
        const r = await read(ns, k);
        return r ? r.v : dflt;
    }
    async function set(ns, k, v) { return write(ns, k, v, null); }

    // ---------------- игрок ----------------
    function playerBlank(cid) {
        return {
            cid: String(cid).slice(0, 40),
            name: '',
            bal: '0',              // баланс — строкой (BigInt)
            blocked: 0,            // 1 — покупки и ставки отключены (b277/b334)
            zeroAt: 0,             // метка обнуления баланса админом
            del: 0,                // 1 — учётка удалена
            minerLvl: 1, minerLast: 0, minerTotal: '0',
            pity: 0,               // гарант паков (packsSinceEpic)
            pityG: { Slots: 0, Grid: 0, Lines: 0, Wheel: 0 }, // счётчики гарантии джекпота
            spins: 0, wins: 0, jpWins: 0, packs: 0, fed: '0', won: '0',
            msn: {},               // прогресс заданий (считает сервер)
            ach: {},               // полученные награды
            created: now(), seen: now(), ip: '', dev: '', did: '', prof: '',
            pk: {}, alb: {}
        };
    }

    async function playerGet(cid) { return get(NS.PLAYER, cid, null); }

    async function playerEnsure(cid, info) {
        return mutate(NS.PLAYER, cid, (p) => {
            let ch = false;
            if (info) {
                if (info.name && p.name !== String(info.name).slice(0, 24)) { p.name = String(info.name).slice(0, 24); ch = true; }
                if (info.ip && p.ip !== info.ip) { p.ip = String(info.ip).slice(0, 45); ch = true; }
                if (info.dev && p.dev !== info.dev) { p.dev = String(info.dev).slice(0, 90); ch = true; }
                if (info.did && p.did !== info.did) { p.did = String(info.did).slice(0, 24); ch = true; }
                if (info.prof && p.prof !== info.prof) { p.prof = String(info.prof).slice(0, 24); ch = true; }
            }
            if (p.seen !== undefined) { p.seen = now(); ch = true; }
            return ch ? p : undefined;
        }, { create: () => Object.assign(playerBlank(cid), info ? {
            name: String(info.name || '').slice(0, 24),
            ip: String(info.ip || '').slice(0, 45),
            dev: String(info.dev || '').slice(0, 90),
            did: String(info.did || '').slice(0, 24),
            prof: String(info.prof || '').slice(0, 24)
        } : {}) });
    }

    async function playerList() {
        const rows = await drv.list(NS.PLAYER, { limit: 5000 });
        const out = [];
        for (const r of rows) {
            try { const p = JSON.parse(r.v); if (p && p.cid) out.push(p); } catch (e) {}
        }
        return out;
    }

    /**
     * Снять/начислить монеты одной атомарной операцией.
     * Возвращает новый баланс (BigInt) или null, если монет не хватило.
     */
    async function balanceAdd(cid, delta, { allowNegative = false } = {}) {
        const d = M(delta);
        let ok = true;
        const p = await mutate(NS.PLAYER, cid, (pl) => {
            const next = M(pl.bal) + d;
            if (next < 0n && !allowNegative) { ok = false; return undefined; }
            pl.bal = S(next < 0n ? 0n : next);
            return pl;
        });
        if (!p || !ok) return null;
        return M(p.bal);
    }

    /** Строгая проверка «хватает ли монет» + списание одной атомарной операцией. */
    async function spend(cid, amount) {
        const a = M(amount);
        if (a <= 0n) return { ok: true, bal: M((await playerGet(cid))?.bal || 0) };
        let ok = false;
        const p = await mutate(NS.PLAYER, cid, (pl) => {
            const cur = M(pl.bal);
            if (cur < a) { ok = false; return undefined; }
            pl.bal = S(cur - a);
            ok = true;
            return pl;
        });
        return { ok: ok && !!p, bal: M(p ? p.bal : 0) };
    }

    async function credit(cid, amount) {
        const a = M(amount);
        if (a <= 0n) return M((await playerGet(cid))?.bal || 0);
        const p = await mutate(NS.PLAYER, cid, (pl) => { pl.bal = S(M(pl.bal) + a); return pl; });
        return M(p ? p.bal : 0);
    }

    async function setBalance(cid, value) {
        const p = await mutate(NS.PLAYER, cid, (pl) => { pl.bal = S(M(value)); return pl; });
        return M(p ? p.bal : 0);
    }

    // ---------------- общий банк ----------------
    function bankBlank() { return { pot: '0', floor: '1000', fed: '0', won: '0', wins: 0, at: now() }; }

    async function bankGet() {
        const b = await get(NS.BANK, 'main', null);
        return b || bankBlank();
    }

    /** Взнос в банк (ставка/проигрыш): fed += x, банк пересчитывается по формуле. */
    async function bankFeed(x) {
        const a = M(x);
        if (a <= 0n) return bankGet();
        return mutate(NS.BANK, 'main', (b) => {
            b.fed = S(M(b.fed) + a);
            b.at = now();
            return b;
        }, { create: bankBlank });
    }

    /**
     * Срыв банка: pot -= prize, но не ниже floor (app.js: jackpotWin + jpLedAdd).
     * Возвращает {bank, secured} — secured = часть выплаты, обеспеченная накопленным.
     */
    async function bankPay(prize) {
        const p = M(prize);
        if (p <= 0n) return { bank: await bankGet(), secured: 0n };
        let secured = 0n;
        const b = await mutate(NS.BANK, 'main', (bk) => {
            const fed = M(bk.fed), won = M(bk.won);
            const excess = fed - won > 0n ? fed - won : 0n;
            secured = excess < p ? excess : p;   // платим только тем, что реально накоплено
            bk.won = S(won + secured);
            bk.wins = (Number(bk.wins) || 0) + 1;
            bk.at = now();
            return bk;
        }, { create: bankBlank });
        return { bank: b || bankBlank(), secured };
    }

    /** «Поставить банк» из Студии: дельта уходит в fed (вверх) или won (вниз). */
    async function bankSetPool(target) {
        const t = M(target);
        return mutate(NS.BANK, 'main', (b) => {
            const floor = M(b.floor);
            const fed = M(b.fed), won = M(b.won);
            const excess = fed - won > 0n ? fed - won : 0n;
            const cur = floor + excess;
            const d = t - cur;
            if (d > 0n) b.fed = S(fed + d);
            else if (d < 0n) b.won = S(won + (-d > excess ? excess : -d));
            b.at = now();
            return b;
        }, { create: bankBlank });
    }

    async function bankSetFloor(floor) {
        return mutate(NS.BANK, 'main', (b) => { b.floor = S(M(floor)); b.at = now(); return b; }, { create: bankBlank });
    }

    /** Банк в привычном клиенту виде: pot = floor + max(0, fed − won). */
    function bankView(b) {
        const floor = M(b.floor), fed = M(b.fed), won = M(b.won);
        const excess = fed - won > 0n ? fed - won : 0n;
        const pot = floor + excess;
        return { floor: S(floor), fed: S(fed), won: S(won), wins: Number(b.wins) || 0, pot: S(pot), potN: N(pot), at: Number(b.at) || 0 };
    }

    // ---------------- зал славы и топ ----------------
    async function hallPush(entry) {
        return mutate(NS.HALL, 'main', (h) => {
            const arr = Array.isArray(h.arr) ? h.arr : [];
            // дедупликация по (cid, at, amount) — как на клиенте (b444)
            const dup = arr.some(x => x && x.c === entry.c && x.t === entry.t && String(x.a) === String(entry.a));
            if (!dup) arr.unshift(entry);
            h.arr = arr.slice(0, HALL_MAX);
            return h;
        }, { create: () => ({ arr: [], cut: 0 }) });
    }

    async function hallGet() {
        const h = await get(NS.HALL, 'main', { arr: [], cut: 0 });
        const cut = Number(h.cut) || 0;
        return (Array.isArray(h.arr) ? h.arr : []).filter(x => x && x.t && x.t > cut);
    }

    async function hallClear() { return mutate(NS.HALL, 'main', (h) => { h.arr = []; h.cut = now(); return h; }, { create: () => ({ arr: [], cut: 0 }) }); }

    // ---------------- идемпотентность операций ----------------
    function opsBucket(t) { return String(Math.floor((t || now()) / 3600000)); }

    /**
     * Занять ключ операции ДО выполнения: true = мы первые, операцию можно
     * проводить; false = такой запрос уже обработан или обрабатывается.
     * Так повторная доставка (сеть дрогнула, клиент повторил) не платит дважды.
     */
    async function opsClaim(oid) {
        if (!oid) return true;
        const k = opsBucket() + ':' + String(oid).slice(0, 80);
        const ok = await write(NS.OPS, k, { oid: String(oid), at: now(), d: null }, 0);
        opsSweepMaybe();
        return ok;
    }

    /** Положить ответ рядом с ключом — его вернём при повторной доставке. */
    async function opsSettle(oid, data) {
        if (!oid) return false;
        const k = opsBucket() + ':' + String(oid).slice(0, 80);
        return write(NS.OPS, k, { oid: String(oid), at: now(), d: data || null }, null);
    }

    /** Что мы уже знаем про этот ключ (ищем в текущем и предыдущем часовом поясе). */
    async function opsGet(oid) {
        const id = String(oid).slice(0, 80);
        const t = now();
        for (const b of [opsBucket(t), opsBucket(t - 3600000)]) {
            const rows = await drv.list(NS.OPS, { limit: 4, prefix: b + ':' + id });
            if (rows.length) return rows[0];
        }
        return null;
    }

    /** Совместимость со старым именем: занять ключ и сразу записать результат. */
    async function opsPut(oid, data) {
        const claimed = await opsClaim(oid);
        if (claimed) await opsSettle(oid, data);
        return claimed;
    }

    let lastSweep = 0;
    function opsSweepMaybe() {
        const t = now();
        if (t - lastSweep < 10 * 60 * 1000) return;
        lastSweep = t;
        (async () => {
            try {
                const rows = await drv.list(NS.OPS, { limit: 5000 });
                const minB = opsBucket(t - OPS_TTL_MS);
                for (const r of rows) if (r.k.split(':')[0] < minB) await drv.del(NS.OPS, r.k, 0);
            } catch (e) {}
        })();
    }

    // ---------------- мины ----------------
    async function minesPut(rec) { return set(NS.MINES, rec.id, rec); }
    async function minesGet(id) { return get(NS.MINES, String(id).slice(0, 60), null); }
    async function minesDel(id) { return drv.del(NS.MINES, String(id).slice(0, 60), null); }

    // ---------------- инвентарь (владение картами) ----------------
    async function invAdd(cid, cardId, n) {
        const k = cid + ':' + cardId;
        const r = await mutate(NS.INV, k, (o) => {
            const c = (Number(o.copies) || 0) + Math.floor(Number(n) || 0);
            if (c <= 0) return null;      // запись удаляем ниже
            o.copies = c;
            return o;
        }, { create: () => ({ cid, card: cardId, copies: 0 }) });
        if (!r || (Number(r.copies) || 0) <= 0) await drv.del(NS.INV, k, null);
        return Math.max(0, Number(r && r.copies) || 0);
    }

    async function invGet(cid, cardId) {
        const r = await get(NS.INV, cid + ':' + cardId, null);
        return r ? Math.max(0, Number(r.copies) || 0) : 0;
    }

    async function invList(cid) {
        const rows = await drv.list(NS.INV, { limit: 2000, prefix: cid + ':' });
        const out = {};
        for (const r of rows) {
            try {
                const o = JSON.parse(r.v);
                if (o && o.card && (Number(o.copies) || 0) > 0) out[o.card] = Number(o.copies);
            } catch (e) {}
        }
        return out;
    }

    // ---------------- биржа (эскроу) ----------------
    async function lotPut(lot) { return set(NS.LOTS, lot.id, lot); }
    async function lotGet(id) { return get(NS.LOTS, String(id).slice(0, 80), null); }

    async function lotList(limit = 400) {
        const rows = await drv.list(NS.LOTS, { limit: 5000 });
        const out = [];
        for (const r of rows) {
            try {
                const l = JSON.parse(r.v);
                if (l && l.id && l.status === 'open') out.push(l);
            } catch (e) {}
        }
        out.sort((a, b) => (Number(b.at) || 0) - (Number(a.at) || 0));
        return out.slice(0, limit);
    }

    /**
     * Купить лот: атомарно переводим status open → sold. Кто успел первым —
     * того и лот; второй получит ok:false («Лот уже куплен или снят»).
     */
    async function lotTake(id, buyer, pricePaid) {
        let taken = null;
        const l = await mutate(NS.LOTS, String(id).slice(0, 80), (lot) => {
            if (!lot || lot.status !== 'open') return undefined;
            lot.status = 'sold';
            lot.buyer = String(buyer).slice(0, 40);
            lot.soldAt = now();
            taken = lot;
            return lot;
        });
        if (!taken || !l) return null;
        return taken;
    }

    async function lotCancel(id, sid) {
        let cancelled = null;
        await mutate(NS.LOTS, String(id).slice(0, 80), (lot) => {
            if (!lot || lot.status !== 'open') return undefined;
            if (String(lot.sid) !== String(sid)) return undefined;
            lot.status = 'cancelled';
            lot.cancelAt = now();
            cancelled = lot;
            return lot;
        });
        return cancelled;
    }

    async function lotsBySeller(sid) {
        const rows = await drv.list(NS.LOTS, { limit: 5000 });
        const out = [];
        for (const r of rows) {
            try {
                const l = JSON.parse(r.v);
                if (l && l.sid === sid && l.status === 'open') out.push(l);
            } catch (e) {}
        }
        return out;
    }

    // ---------------- квитанции продавцам ----------------
    async function ledgerAdd(rec) { return set(NS.LEDGER, rec.id, Object.assign({ paid: 0, at: now() }, rec)); }

    async function ledgerUnpaid(cid) {
        const rows = await drv.list(NS.LEDGER, { limit: 2000 });
        const out = [];
        for (const r of rows) {
            try {
                const l = JSON.parse(r.v);
                if (l && l.sid === cid && !l.paid) out.push(l);
            } catch (e) {}
        }
        return out;
    }

    async function ledgerMarkPaid(ids) {
        for (const id of ids) {
            await mutate(NS.LEDGER, String(id).slice(0, 80), (l) => { l.paid = 1; l.paidAt = now(); return l; });
        }
    }

    // ---------------- настройки джекпота и каталог ----------------
    async function jpcGet(room) { return get(NS.JPC, room || 'site', null); }
    async function jpcSet(room, cfg) { return set(NS.JPC, room || 'site', cfg); }
    async function catalogGet(room) { return get(NS.CATALOG, room || 'site', null); }
    async function catalogSet(room, data) { return set(NS.CATALOG, room || 'site', Object.assign({ at: now() }, data)); }

    // ---------------- учётка Студии (пароль живёт ТОЛЬКО здесь) ----------------
    async function credsGet(login) { return get(NS.CREDS, String(login).toLowerCase(), null); }
    async function credsSet(login, rec) { return set(NS.CREDS, String(login).toLowerCase(), rec); }
    async function credsList() {
        const rows = await drv.list(NS.CREDS, { limit: 50 });
        return rows.map(r => { try { return JSON.parse(r.v); } catch (e) { return null; } }).filter(Boolean);
    }

    // ---------------- служебные настройки ----------------
    async function cfgGet(k, dflt = null) { const r = await get(NS.CFG, k, null); return r && r.v !== undefined ? r.v : dflt; }
    async function cfgSet(k, v) { return set(NS.CFG, k, { v }); }

    // ---------------- журнал админки ----------------
    async function audit(rec) {
        const id = String(now()) + '-' + Math.floor(Math.random() * 1e6);
        await set(NS.AUDIT, id, Object.assign({ id, at: now() }, rec));
        const rows = await drv.list(NS.AUDIT, { limit: 5000 });
        if (rows.length > AUDIT_MAX) {
            const del = rows.slice(0, rows.length - AUDIT_MAX);
            for (const r of del) await drv.del(NS.AUDIT, r.k, null);
        }
        return id;
    }

    async function auditList(limit = 100) {
        const rows = await drv.list(NS.AUDIT, { limit: 5000 });
        const out = [];
        for (const r of rows) { try { out.push(JSON.parse(r.v)); } catch (e) {} }
        out.sort((a, b) => (b.at || 0) - (a.at || 0));
        return out.slice(0, limit);
    }

    // ---------------- реестр игроков для таблицы Студии ----------------
    async function statsPut(cid, e) { return set(NS.STATS, String(cid).slice(0, 40), e); }
    async function statsList(limit = 150) {
        const rows = await drv.list(NS.STATS, { limit: 5000 });
        const out = [];
        for (const r of rows) { try { const e = JSON.parse(r.v); if (e && e.cid) out.push(e); } catch (err) {} }
        out.sort((a, b) => (b.at || 0) - (a.at || 0));
        return out.slice(0, limit);
    }

    return {
        drv, NS, read, write, mutate, get, set,
        playerBlank, playerGet, playerEnsure, playerList,
        balanceAdd, spend, credit, setBalance,
        bankGet, bankFeed, bankPay, bankSetPool, bankSetFloor, bankView, bankBlank,
        hallPush, hallGet, hallClear,
        opsPut, opsGet, opsClaim, opsSettle,
        minesPut, minesGet, minesDel,
        invAdd, invGet, invList,
        lotPut, lotGet, lotList, lotTake, lotCancel, lotsBySeller,
        ledgerAdd, ledgerUnpaid, ledgerMarkPaid,
        jpcGet, jpcSet, catalogGet, catalogSet,
        credsGet, credsSet, credsList,
        cfgGet, cfgSet, audit, auditList,
        statsPut, statsList,
        rndId, money, M, S, N
    };
}
