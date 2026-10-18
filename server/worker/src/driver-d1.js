/* server/worker/src/driver-d1.js — драйвер хранилища поверх Cloudflare D1 (b463)
 *
 * Вся база — одна таблица kv(ns, k, v, ver). Такой выбор не случайный:
 *   • один и тот же код доменной логики (store.js) работает и на D1, и на
 *     in-memory драйвере для локальных тестов — расхождение исключено;
 *   • деньги лежат десятичной строкой в v, поэтому BigInt-суммы любой
 *     величины не упираются в 64-битный INTEGER;
 *   • ver — версия записи. Любое изменение денег/банка/лота идёт как
 *     «UPDATE … WHERE ver = ?»: если запись успел поменять кто-то ещё,
 *     изменений 0 → store.js повторяет операцию (оптимистичная блокировка).
 *     Два одновременных срыва джекпота больше не гасят друг друга.
 *
 * DDL лежит в server/worker/schema.sql и создаётся автоматически при первом
 * запросе (ensureSchema), поэтому отдельный шаг миграции не обязателен.
 */

const DDL = [
    `CREATE TABLE IF NOT EXISTS kv (
        ns  TEXT NOT NULL,
        k   TEXT NOT NULL,
        v   TEXT,
        ver INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (ns, k)
    )`,
    `CREATE INDEX IF NOT EXISTS ix_kv_ns ON kv (ns)`,
    `CREATE INDEX IF NOT EXISTS ix_kv_ns_k ON kv (ns, k)`
];

export function makeD1Driver(db) {
    let ready = null;

    async function ensure() {
        if (!ready) {
            ready = (async () => {
                for (const sql of DDL) await db.prepare(sql).run();
                return true;
            })().catch(e => { ready = null; throw e; });
        }
        return ready;
    }

    return {
        kind: 'd1',
        ensure,

        async get(ns, k) {
            await ensure();
            const r = await db.prepare('SELECT v, ver FROM kv WHERE ns = ?1 AND k = ?2').bind(ns, k).first();
            return r ? { v: r.v, ver: Number(r.ver) || 0 } : null;
        },

        /**
         * expectVer:
         *   null — записать безусловно;
         *   0    — только если записи ещё нет;
         *   >0   — только если версия совпала (иначе false → повтор).
         */
        async put(ns, k, v, expectVer) {
            await ensure();
            if (expectVer === 0) {
                const r = await db.prepare(
                    'INSERT INTO kv (ns, k, v, ver) VALUES (?1, ?2, ?3, 1) ON CONFLICT (ns, k) DO NOTHING'
                ).bind(ns, k, v).run();
                return Number(r.meta.changes || 0) === 1;
            }
            if (expectVer > 0) {
                const r = await db.prepare(
                    'UPDATE kv SET v = ?3, ver = ver + 1 WHERE ns = ?1 AND k = ?2 AND ver = ?4'
                ).bind(ns, k, v, expectVer).run();
                return Number(r.meta.changes || 0) === 1;
            }
            await db.prepare(
                'INSERT INTO kv (ns, k, v, ver) VALUES (?1, ?2, ?3, 1) ON CONFLICT (ns, k) DO UPDATE SET v = ?3, ver = ver + 1'
            ).bind(ns, k, v).run();
            return true;
        },

        async del(ns, k, expectVer) {
            await ensure();
            const sql = expectVer > 0
                ? 'DELETE FROM kv WHERE ns = ?1 AND k = ?2 AND ver = ?3'
                : 'DELETE FROM kv WHERE ns = ?1 AND k = ?2';
            const stmt = expectVer > 0 ? db.prepare(sql).bind(ns, k, expectVer) : db.prepare(sql).bind(ns, k);
            const r = await stmt.run();
            return Number(r.meta.changes || 0) > 0;
        },

        async list(ns, { limit = 1000, prefix = '' } = {}) {
            await ensure();
            if (prefix) {
                const esc = String(prefix).replace(/[%_]/g, c => '\\' + c);
                const r = await db.prepare(
                    "SELECT k, v, ver FROM kv WHERE ns = ?1 AND k LIKE ?2 ESCAPE '\\' ORDER BY k LIMIT ?3"
                ).bind(ns, esc + '%', limit).all();
                return (r.results || []).map(x => ({ k: x.k, v: x.v, ver: Number(x.ver) || 0 }));
            }
            const r = await db.prepare('SELECT k, v, ver FROM kv WHERE ns = ?1 ORDER BY k LIMIT ?2').bind(ns, limit).all();
            return (r.results || []).map(x => ({ k: x.k, v: x.v, ver: Number(x.ver) || 0 }));
        },

        async count(ns) {
            await ensure();
            const r = await db.prepare('SELECT COUNT(*) AS c FROM kv WHERE ns = ?1').bind(ns).first();
            return Number(r && r.c) || 0;
        }
    };
}
