/* server/worker/src/index.js — точка входа Cloudflare Worker (b463)
 *
 * Роутер + CORS + ограничения. Ничего лишнего: вся логика в api.js/economy.js/
 * admin.js, всё хранение в store.js.
 *
 * Деплой:  cd server/worker && npx wrangler deploy   (подробности в server/README.md)
 * Секрет:  npx wrangler secret put NX_SECRET
 * База:    npx wrangler d1 create nexus-bank  (таблица kv создаётся сама при первом запросе)
 */

import { json, err, makeRateLimiter } from './util.js';
import { makeStore } from './store.js';
import { makeD1Driver } from './driver-d1.js';
import { makeApi } from './api.js';

// CORS: сайт лежит на GitHub Pages, API — на workers.dev, поэтому без
// разрешённого происхождения браузер запросы не пустит.
const DEFAULT_ORIGINS = [
    'https://d3nizkeller.github.io',
    'http://localhost:8787',
    'http://localhost:8080',
    'http://127.0.0.1:8787'
];

function allowedOrigin(req, env) {
    const o = req.headers.get('origin') || '';
    const list = String(env.NX_ORIGINS || '').split(',').map(s => s.trim()).filter(Boolean).concat(DEFAULT_ORIGINS);
    if (!o) return null;                       // не-браузерный запрос (скрипт миграции)
    return list.indexOf(o) >= 0 ? o : null;
}

function corsHeaders(req, env) {
    const o = allowedOrigin(req, env);
    const h = {
        'access-control-allow-methods': 'GET, POST, OPTIONS',
        'access-control-allow-headers': 'content-type, authorization, x-nx-admin, x-nx-room, x-nx-oid',
        'access-control-max-age': '86400',
        'vary': 'Origin'
    };
    if (o) h['access-control-allow-origin'] = o;
    return h;
}

const spinLimiter = makeRateLimiter({ limit: 25, windowMs: 10000 });   // 25 спинов в 10 c
const writeLimiter = makeRateLimiter({ limit: 60, windowMs: 10000 });

export function createApp(env) {
    const driver = env && env.DB ? makeD1Driver(env.DB) : null;
    if (!driver) throw new Error('NX: не подключена база D1 (env.DB). См. server/README.md');
    const store = makeStore(driver);
    return { store, api: makeApi({ store, env: env || {} }) };
}

export default {
    async fetch(req, env, ctx) {
        const url = new URL(req.url);
        const cors = corsHeaders(req, env);

        if (req.method === 'OPTIONS') {
            return new Response(null, { status: 204, headers: cors });
        }
        if (!String(env.NX_SECRET || '')) {
            return withCors(json({ ok: false, error: 'server_not_configured', hint: 'npx wrangler secret put NX_SECRET' }, 500), cors);
        }

        const { api } = createApp(env);
        const method = req.method.toUpperCase();
        const path = url.pathname.replace(/\/+$/, '') || '/';

        let body = {};
        if (method === 'POST' || method === 'PUT') {
            try {
                const ct = req.headers.get('content-type') || '';
                const text = await req.text();
                body = text ? (ct.indexOf('application/json') >= 0 || text.trim()[0] === '{' ? JSON.parse(text) : JSON.parse(text)) : {};
            } catch (e) {
                return withCors(err('bad_json'), cors);
            }
        }

        // ограничения по частоте: отдельный, жёсткий — на спины
        const ip = req.headers.get('cf-connecting-ip') || 'local';
        if (path === '/api/spin' && !spinLimiter(ip)) return withCors(err('rate_limit', 429), cors);
        if (method === 'POST' && !writeLimiter(ip)) return withCors(err('rate_limit', 429), cors);

        const key = method + ' ' + path;
        const handler = api.routes[key];
        if (!handler) {
            if (path === '/' || path === '/api') {
                return withCors(json({
                    ok: true, service: 'nexus-card-collection-api', version: 'b463',
                    endpoints: Object.keys(api.routes).sort()
                }), cors);
            }
            return withCors(err('not_found', 404), cors);
        }

        const reqCtx = Object.assign({}, req, { query: Object.fromEntries(url.searchParams.entries()) });
        try {
            const res = await handler(reqCtx, body, req.headers);
            return withCors(res, cors);
        } catch (e) {
            // наружу — только код ошибки, детали в лог воркера
            console.error('NX ' + key + ': ' + ((e && e.stack) || e));
            return withCors(err('server_error', 500), cors);
        }
    },

    /** Периодическая чистка ключей операций (cron: 0 * * * *). */
    async scheduled(event, env, ctx) {
        try {
            const { store } = createApp(env);
            const rows = await store.drv.list(store.NS.OPS, { limit: 5000 });
            const minB = String(Math.floor((Date.now() - 26 * 3600 * 1000) / 3600000));
            let n = 0;
            for (const r of rows) {
                if (r.k.split(':')[0] < minB) { await store.drv.del(store.NS.OPS, r.k, 0); n++; }
            }
            console.log('NX sweep: удалено ключей операций — ' + n);
        } catch (e) { console.error('NX sweep: ' + e); }
    }
};

function withCors(res, cors) {
    const h = new Headers(res.headers);
    for (const k in cors) if (!h.has(k)) h.set(k, cors[k]);
    return new Response(res.body, { status: res.status, statusText: res.statusText, headers: h });
}
