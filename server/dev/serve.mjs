/* server/dev/serve.mjs — локальный сервер для проверки без Cloudflare (b463)
 *
 * Зачем: тот же самый код API (src/api.js, economy.js, admin.js, store.js),
 * но вместо D1 — in-memory драйвер, а вместо воркера — обычный node:http.
 * Можно руками покрутить игру против http://127.0.0.1:8787 и прогнать тесты,
 * не деплоя ничего в облако.
 *
 * Запуск:
 *     node server/dev/serve.mjs                     # порт 8787, секрет dev-secret
 *     PORT=9000 NX_SECRET=xxx node server/dev/serve.mjs
 *     node server/dev/serve.mjs --seed server/dev/seed.json   # начать с готовыми данными
 *
 * В браузере: http://127.0.0.1:8787/api/health
 */

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');

// правила игры — тот же файл, что грузит браузер
await import(path.join(ROOT, 'assets', 'nx-rules.js'));

const { makeStore } = await import(path.join(HERE, '..', 'worker', 'src', 'store.js'));
const { makeMemDriver } = await import(path.join(HERE, '..', 'worker', 'src', 'driver-mem.js'));
const { makeApi } = await import(path.join(HERE, '..', 'worker', 'src', 'api.js'));

const PORT = Number(process.env.PORT || 8787);
const env = {
    NX_SECRET: process.env.NX_SECRET || 'dev-secret-do-not-use-in-prod',
    NX_ROOM: process.env.NX_ROOM || 'site',
    NX_ORIGINS: process.env.NX_ORIGINS || '*',
    NX_SETUP_KEY: process.env.NX_SETUP_KEY || ''
};

let seed = undefined;
const si = process.argv.indexOf('--seed');
if (si > 0 && process.argv[si + 1]) {
    seed = JSON.parse(fs.readFileSync(process.argv[si + 1], 'utf8'));
    console.log('seed:', process.argv[si + 1]);
}

const driver = makeMemDriver(seed);
const store = makeStore(driver);
const { api } = { api: makeApi({ store, env }) };

const CORS = {
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET, POST, OPTIONS',
    'access-control-allow-headers': 'content-type, authorization, x-nx-admin, x-nx-room, x-nx-oid',
    'access-control-max-age': '86400'
};

const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, 'http://localhost');
    if (req.method === 'OPTIONS') {
        res.writeHead(204, CORS); res.end(); return;
    }
    const send = (r) => {
        const h = Object.assign({}, CORS);
        r.headers.forEach((v, k) => { h[k] = v; });
        res.writeHead(r.status, h);
        r.body.getReader().read().then(({ value }) => { res.end(Buffer.from(value || '')); }).catch(() => res.end());
    };

    // служебные эндпоинты дев-сервера
    if (u.pathname === '/__dump') {
        res.writeHead(200, Object.assign({ 'content-type': 'application/json' }, CORS));
        res.end(JSON.stringify(driver.dump())); return;
    }

    const key = req.method.toUpperCase() + ' ' + (u.pathname.replace(/\/+$/, '') || '/');
    const handler = api.routes[key];
    if (!handler) {
        if (u.pathname === '/' || u.pathname === '/api') {
            res.writeHead(200, Object.assign({ 'content-type': 'application/json' }, CORS));
            res.end(JSON.stringify({ ok: true, service: 'nexus-card-collection-api (dev)', version: 'b463', endpoints: Object.keys(api.routes).sort() }));
            return;
        }
        res.writeHead(404, Object.assign({ 'content-type': 'application/json' }, CORS));
        res.end(JSON.stringify({ ok: false, error: 'not_found', path: u.pathname })); return;
    }

    let body = {};
    if (req.method === 'POST' || req.method === 'PUT') {
        const chunks = [];
        for await (const c of req) chunks.push(c);
        const text = Buffer.concat(chunks).toString('utf8');
        try { body = text ? JSON.parse(text) : {}; } catch (e) {
            res.writeHead(400, Object.assign({ 'content-type': 'application/json' }, CORS));
            res.end(JSON.stringify({ ok: false, error: 'bad_json' })); return;
        }
    }

    const headers = new Headers();
    for (const k in req.headers) if (typeof req.headers[k] === 'string') headers.set(k, req.headers[k]);
    headers.set('cf-connecting-ip', req.socket.remoteAddress || 'local');

    const reqCtx = { headers, query: Object.fromEntries(u.searchParams.entries()), method: req.method, url: req.url };
    try {
        send(await handler(reqCtx, body, headers));
    } catch (e) {
        console.error('DEV ' + key + ':', e);
        res.writeHead(500, Object.assign({ 'content-type': 'application/json' }, CORS));
        res.end(JSON.stringify({ ok: false, error: 'server_error', detail: String((e && e.message) || e) }));
    }
});

server.listen(PORT, () => {
    console.log('NX dev API: http://127.0.0.1:' + PORT + '  (store=mem, secret=' + (env.NX_SECRET ? 'задан' : 'НЕТ') + ')');
    console.log('  health:  http://127.0.0.1:' + PORT + '/api/health');
    console.log('  public:  http://127.0.0.1:' + PORT + '/api/public');
    console.log('  дамп БД: http://127.0.0.1:' + PORT + '/__dump');
});

export { store, api, driver, env };
