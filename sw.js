/* nx-media-sw v2 (nxmob14): cache-first для media/ и assets/, network-first для HTML.
   Арты и скрипты скачиваются с сервера ОДИН раз на браузер; дальше отдаются из
   кэша мгновенно — в Telegram Mini App повторное открытие становится мгновенным
   и работает без сети. Тихая сверка с сервером — не чаще раза в 7 дней на файл. */
const VERSION = 'nxmob14';
const CACHE_MEDIA = 'nx-media-v2';
const CACHE_ASSETS = 'nx-assets-' + VERSION;
const CACHE_PAGES = 'nx-pages-' + VERSION;
const MAX_ENTRIES = 500;
const REVALIDATE_MS = 7 * 24 * 60 * 60 * 1000;

self.addEventListener('install', e => {
    self.skipWaiting();
});
self.addEventListener('activate', e => {
    e.waitUntil((async () => {
        // старые версии кэшей не копятся: на слабом телефоне место на вес золота
        const keep = [CACHE_MEDIA, CACHE_ASSETS, CACHE_PAGES];
        for (const k of await caches.keys()) if (keep.indexOf(k) < 0) await caches.delete(k);
        await self.clients.claim();
    })());
});

self.addEventListener('message', e => {
    if (e && e.data === 'nx-skip-waiting') self.skipWaiting();
});

self.addEventListener('fetch', e => {
    const req = e.request;
    if (req.method !== 'GET') return;
    const url = new URL(req.url);
    if (url.origin !== self.location.origin) return;

    const p = url.pathname;
    if (p.indexOf('/media/') >= 0) { e.respondWith(mediaFirst(e, url, CACHE_MEDIA)); return; }
    if (p.indexOf('/assets/') >= 0) { e.respondWith(mediaFirst(e, url, CACHE_ASSETS)); return; }
    if (req.mode === 'navigate' || /\.html?$/.test(p) || p.endsWith('/')) {
        e.respondWith(pageFirst(e, req));
    }
});

/* вечный cache-first: файл неизменяем, сверяемся редко и только в фоне */
async function mediaFirst(e, url, cacheName) {
    const bypass = url.searchParams.has('nxcb');
    const cache = await caches.open(cacheName);
    if (!bypass) {
        const hit = await cache.match(e.request.url, { ignoreSearch: true });
        if (hit) {
            const ts = Number(hit.headers.get('x-nx-ts') || 0);
            if (Date.now() - ts > REVALIDATE_MS) e.waitUntil(refresh(cache, e.request));
            return hit;
        }
    }
    try {
        const resp = await fetch(e.request);
        if (resp.ok && !bypass) e.waitUntil(store(cache, e.request, resp.clone()));
        return resp;
    } catch (err) {
        const stale = await cache.match(e.request.url, { ignoreSearch: true });
        if (stale) return stale;
        throw err;
    }
}

/* HTML: сначала сеть (иначе игрок застрянет на старой версии), кэш — запасной выход */
async function pageFirst(e, req) {
    const cache = await caches.open(CACHE_PAGES);
    try {
        const resp = await fetch(req);
        if (resp.ok) e.waitUntil(cache.put(req, resp.clone()));
        return resp;
    } catch (err) {
        const stale = await cache.match(req) || await cache.match('./');
        if (stale) return stale;
        throw err;
    }
}

async function store(cache, req, resp) {
    try {
        const headers = new Headers(resp.headers);
        headers.set('x-nx-ts', String(Date.now()));
        const body = await resp.blob();
        await cache.put(req, new Response(body, { status: resp.status, statusText: resp.statusText, headers: headers }));
        await trim(cache);
    } catch (e) {}
}

async function refresh(cache, req) {
    try {
        const resp = await fetch(req, { cache: 'no-store' });
        if (resp.ok) await store(cache, req, resp.clone());
    } catch (e) {}
}

async function trim(cache) {
    try {
        const keys = await cache.keys();
        if (keys.length <= MAX_ENTRIES) return;
        const stamped = [];
        for (const k of keys) {
            const r = await cache.match(k);
            stamped.push([Number((r && r.headers.get('x-nx-ts')) || 0), k]);
        }
        stamped.sort((a, b) => a[0] - b[0]);
        const drop = keys.length - MAX_ENTRIES;
        for (let i = 0; i < drop; i++) await cache.delete(stamped[i][1]);
    } catch (e) {}
}
