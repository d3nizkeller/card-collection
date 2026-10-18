/* server/worker/src/driver-mem.js — in-memory драйвер (b463)
 *
 * Тот же интерфейс, что у driver-d1.js, но данные живут в Map.
 * Нужен для двух вещей:
 *   1. server/dev/serve.mjs — локальный сервер на node без Cloudflare,
 *      чтобы прогнать игру и админку руками до деплоя;
 *   2. server/test/*.mjs — автотесты экономики (см. README).
 *
 * Семантика версий (expectVer) повторена один в один, поэтому тесты проверяют
 * ровно то поведение, которое будет на D1, включая гонки и повторы.
 */

export function makeMemDriver(seed) {
    const ns = new Map(); // ns -> Map(k -> {v, ver})

    function bucket(n) {
        let m = ns.get(n);
        if (!m) { m = new Map(); ns.set(n, m); }
        return m;
    }

    if (seed && typeof seed === 'object') {
        for (const n of Object.keys(seed)) {
            const m = bucket(n);
            for (const k of Object.keys(seed[n])) m.set(k, { v: JSON.stringify(seed[n][k]), ver: 1 });
        }
    }

    return {
        kind: 'mem',
        async ensure() { return true; },

        async get(n, k) {
            const r = bucket(n).get(k);
            return r ? { v: r.v, ver: r.ver } : null;
        },

        async put(n, k, v, expectVer) {
            const m = bucket(n);
            const cur = m.get(k);
            if (expectVer === 0) {
                if (cur) return false;
                m.set(k, { v, ver: 1 });
                return true;
            }
            if (expectVer > 0) {
                if (!cur || cur.ver !== expectVer) return false;
                m.set(k, { v, ver: cur.ver + 1 });
                return true;
            }
            m.set(k, { v, ver: cur ? cur.ver + 1 : 1 });
            return true;
        },

        async del(n, k, expectVer) {
            const m = bucket(n);
            const cur = m.get(k);
            if (!cur) return false;
            if (expectVer > 0 && cur.ver !== expectVer) return false;
            m.delete(k);
            return true;
        },

        async list(n, { limit = 1000, prefix = '' } = {}) {
            const out = [];
            for (const [k, r] of bucket(n).entries()) {
                if (prefix && k.indexOf(prefix) !== 0) continue;
                out.push({ k, v: r.v, ver: r.ver });
                if (out.length >= limit) break;
            }
            out.sort((a, b) => (a.k < b.k ? -1 : a.k > b.k ? 1 : 0));
            return out;
        },

        async count(n) { return bucket(n).size; },

        /** только для тестов/дева: снять слепок базы */
        dump() {
            const o = {};
            for (const [n, m] of ns.entries()) {
                o[n] = {};
                for (const [k, r] of m.entries()) o[n][k] = JSON.parse(r.v);
            }
            return o;
        }
    };
}
