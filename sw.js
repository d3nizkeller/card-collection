/* nx-media-sw v1 (b349): вечный cache-first для папки media/ — снимает нагрузку с GitHub Pages.
   Каждый арт скачивается с сервера ОДИН раз на браузер; дальше отдаётся из кэша мгновенно.
   Тихая сверка с сервером — не чаще раза в 7 дней на файл. Файлы media/ неизменяемы
   (новые арты приходят под новыми именами), поэтому вечный кэш безопасен. */
const CACHE = 'nx-media-v1';
const MAX_ENTRIES = 500;                       // страховка от раздувания кэша
const REVALIDATE_MS = 7 * 24 * 60 * 60 * 1000; // 7 дней

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;      // чужие хосты не трогаем
  if (url.pathname.indexOf('/media/') < 0) return;      // только арты
  const bypass = url.searchParams.has('nxcb');          // ретрай мимо кэша (лечение битого 404)
  e.respondWith(handle(e, bypass));
});

async function handle(e, bypass) {
  const cache = await caches.open(CACHE);
  if (!bypass) {
    const hit = await cache.match(e.request.url, { ignoreSearch: true });
    if (hit) {
      const ts = Number(hit.headers.get('x-nx-ts') || 0);
      if (Date.now() - ts > REVALIDATE_MS) e.waitUntil(refresh(cache, e.request)); // фоном, не тормозя ответ
      return hit;
    }
  }
  try {
    const resp = await fetch(e.request);
    if (resp.ok && !bypass) e.waitUntil(store(cache, e.request, resp.clone()));
    return resp;
  } catch (err) {
    const stale = await cache.match(e.request.url, { ignoreSearch: true });
    if (stale) return stale;   // сети нет совсем — отдаём то, что уже было: сайт живёт офлайн
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
