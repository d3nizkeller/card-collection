/* server/worker/src/util.js — общие мелочи воркера (b463)
 *
 * Деньги в игре — целые монеты, но ставки доходят до 1e15, а банк сайта
 * исторически рос до 1e17+. Обычный Number (double) точно хранит целое только
 * до 2^53 ≈ 9e15, поэтому на сервере все суммы считаются в BigInt и лежат в
 * базе десятичной строкой. Клиенту отдаём и строку (точно), и число (для
 * привычного fmtCoins) — так витрина не меняется, а подделать сумму нельзя.
 */

export const MONEY_MAX = 1000000000000000000n; // 1e18 — потолок баланса и банка

/** Любое входящее значение → BigInt монет (0, если мусор). */
export function M(v) {
    if (typeof v === 'bigint') return clampMoney(v);
    if (typeof v === 'number') {
        if (!isFinite(v)) return 0n;
        return clampMoney(BigInt(Math.trunc(v)));
    }
    const s = String(v == null ? '' : v).trim().replace(/\s|_/g, '');
    if (!s) return 0n;
    // поддерживаем те же «буквы», что и клиентский parseBetStr (k/m/b/t/q)
    const mm = /^(-?\d+(?:\.\d+)?)([kmbtq])?$/i.exec(s);
    if (mm) {
        const mult = { k: 1e3, m: 1e6, b: 1e9, t: 1e12, q: 1e15 }[(mm[2] || '').toLowerCase()];
        const n = mult ? Number(mm[1]) * mult : Number(mm[1]);
        if (!isFinite(n)) return 0n;
        return clampMoney(BigInt(Math.trunc(n)));
    }
    if (!/^-?\d+$/.test(s)) return 0n;
    try { return clampMoney(BigInt(s)); } catch (e) { return 0n; }
}

export function clampMoney(b) {
    if (b > MONEY_MAX) return MONEY_MAX;
    if (b < -MONEY_MAX) return -MONEY_MAX;
    return b;
}

/** BigInt → строка для базы и для клиента. */
export function S(b) { return String(M(b)); }

/** BigInt → число для витрины (с потерей точности выше 2^53, как и было). */
export function N(b) { return Number(M(b)); }

/** Представление баланса/банка для ответа клиенту. */
export function money(b) { return { s: S(b), n: N(b) }; }

export function json(data, status = 200, headers = {}) {
    return new Response(JSON.stringify(data), {
        status,
        headers: Object.assign({
            'content-type': 'application/json; charset=utf-8',
            'cache-control': 'no-store',
            // деньги и админка не должны кешироваться ни в браузере, ни в CDN
            'x-content-type-options': 'nosniff'
        }, headers)
    });
}

export function err(code, status = 400, extra = {}) {
    return json(Object.assign({ ok: false, error: code }, extra), status);
}

export function now() { return Date.now(); }

export function rndId(prefix) {
    const b = new Uint8Array(9);
    crypto.getRandomValues(b);
    let s = '';
    for (let i = 0; i < b.length; i++) s += b[i].toString(36).padStart(2, '0');
    return (prefix || 'id') + '-' + s.slice(0, 12);
}

/** Криптостойкий rng() → [0,1) — замена Math.random на сервере. */
export function secureRng() {
    let buf = new Uint32Array(0), pos = 0;
    return function () {
        if (pos >= buf.length) { buf = new Uint32Array(64); crypto.getRandomValues(buf); pos = 0; }
        // 53 бита энтропии, как у Math.random, но из crypto
        const hi = buf[pos++] >>> 5;           // 27 бит
        const lo = pos < buf.length ? buf[pos++] >>> 6 : (crypto.getRandomValues(new Uint32Array(1))[0] >>> 6); // 26 бит
        return (hi * 67108864 + lo) / 9007199254740992;
    };
}

/** Простая защита от перегрузки: не больше limit запросов за windowMs на ключ. */
export function makeRateLimiter({ limit = 30, windowMs = 10000, maxKeys = 5000 } = {}) {
    const hits = new Map();
    return function allow(key) {
        const t = Date.now();
        let rec = hits.get(key);
        if (!rec || t - rec.t0 > windowMs) {
            if (hits.size > maxKeys) hits.clear();
            rec = { t0: t, n: 0 };
        }
        rec.n++;
        hits.set(key, rec);
        return rec.n <= limit;
    };
}

/** Повтор оптимистичной транзакции (см. store.js: versioned read-modify-write). */
export async function withRetry(fn, tries = 6) {
    let lastErr;
    for (let i = 0; i < tries; i++) {
        try {
            return await fn();
        } catch (e) {
            lastErr = e;
            if (!e || e.name !== 'NXConflict') throw e;
            await new Promise(r => setTimeout(r, 4 + i * 8 + Math.floor(Math.random() * 10)));
        }
    }
    throw lastErr || new Error('retry failed');
}

export class NXConflict extends Error {
    constructor(msg) { super(msg || 'conflict'); this.name = 'NXConflict'; }
}
