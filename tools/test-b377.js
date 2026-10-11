/* b377: «у пользователей не загружаются картинки карт, особенно на мобильных».

   Что меряем. Каталог карт приходит из облака комнаты и ссылается на
   https://d3nizkeller.github.io/card-collection/media/card_*.png — мастера
   1080x1920 / 1152x2048 по 1.6-4.3 МБ. Альбом (вид «Сетка», он же вид по
   умолчанию) обязан показывать их через миниатюру media/t2/ 512px (~62 КБ),
   а не мастером.

   Стенд повторяет прод: эмуляция iPhone 12 (DPR 3, как в Telegram Mini App),
   36 РЕАЛЬНЫХ артов «Доктор Кто» из media/, абсолютные ссылки на боевой origin,
   который проксируется на локальный сервер. Считаем:
     · сколько запросов ушло в миниатюры (media/t, media/t2), а сколько в мастера (media/)
     · сколько байт реально скачано
     · сколько распакованных битмапов держит вкладка (naturalWidth*naturalHeight*4)
     · все ли <img> доехали (loaded/total)
     · упала ли вкладка (crash) — на телефоне это выглядит как «браузер закрылся»

   Запуск:
     python3 -m http.server 8123 &      # в корне репозитория
     node tools/test-b377.js [url] [port]
*/
const PW = process.env.PW_PATH || '/tmp/pw/node_modules/playwright-core';
const { chromium, devices } = require(PW);
const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(__dirname);
const MEDIA = path.join(ROOT, 'media');
// Страницу грузим С БОЕВОГО origin (он проксируется на локальный сервер через
// 302). Иначе документ на 127.0.0.1, а арты на d3nizkeller.github.io — и fetch()
// из imgCacheStoreFromNetwork ловит CORS, которого в проде не существует.
const GH = 'https://d3nizkeller.github.io/card-collection/';
const PORT = process.argv[3] || '8123';
const PAGE_URL = process.argv[2] || GH + 'index.html';
const NAME = process.argv[4] || 'run';
const OUT = process.env.SHOTS || '/tmp/shots-b377';
fs.mkdirSync(OUT, { recursive: true });

/* --- каталог из РЕАЛЬНЫХ облачных артов (как в проде) --- */
const MASTERS = fs.readdirSync(MEDIA)
    .filter(f => /^card_mv0[34][a-z0-9]*_\d{4}_doktor\.(png|jpg)$/.test(f))
    .sort();
if (MASTERS.length < 20) { console.error('мало мастеров card_mv03/04_*_doktor: ' + MASTERS.length); process.exit(2); }

const PACK = {
    id: 'pack-b377', title: 'Доктор Кто', description: 'Стенд b377',
    image: GH + 'media/g0.jpg', price: 100, color: 'black', shimmer: 'matte', musicOff: true
};
const CARDS = MASTERS.map((f, i) => ({
    id: 'card-b377-' + i, packId: PACK.id, name: 'Доктор #' + (i + 1),
    description: 'Стенд b377', rarity: ['common', 'rare', 'epic', 'legendary'][i % 4],
    image: GH + 'media/' + f, ord: i + 1, ordAt: 1790000000000 + i
}));
const COLLECTION = {}; CARDS.forEach(c => { COLLECTION[c.id] = 1; });

const INIT = `
window.__lt = { count: 0, total: 0, worst: 0 };
try {
    const po = new PerformanceObserver(l => { for (const e of l.getEntries()) {
        window.__lt.count++; window.__lt.total += e.duration;
        if (e.duration > window.__lt.worst) window.__lt.worst = e.duration; } });
    po.observe({ entryTypes: ['longtask'] });
} catch (e) { window.__lt.unsupported = true; }
window.__errs = [];
window.addEventListener('error', e => window.__errs.push('error: ' + (e.message || '')));
window.addEventListener('unhandledrejection', e => window.__errs.push('reject: ' + ((e.reason && e.reason.message) || e.reason)));
try { if (navigator.serviceWorker) navigator.serviceWorker.register = () => Promise.reject(new Error('sw off (стенд)')); } catch (e) {}
try {
    localStorage.setItem('nexus_packs',   ${JSON.stringify(JSON.stringify([PACK]))});
    localStorage.setItem('nexus_cards',   ${JSON.stringify(JSON.stringify(CARDS))});
    localStorage.setItem('nexus_collection', ${JSON.stringify(JSON.stringify(COLLECTION))});
    localStorage.setItem('nx_weak_gpu', '1');       // без WebGL — меряем DOM-путь
    localStorage.setItem('nexus_coins', '99999');
} catch (e) {}
`;

const SNAP = () => {
    let decoded = 0, loaded = 0, total = 0, broken = 0, worst = null, bigImgs = 0, bigBytes = 0;
    for (const im of document.images) {
        total++;
        if (im.complete && im.naturalWidth === 0 && im.src) broken++;
        if (!im.complete || !im.naturalWidth) continue;
        loaded++;
        const b = im.naturalWidth * im.naturalHeight * 4;
        decoded += b;
        const s = im.currentSrc || im.src || '';
        // «тяжёлая» картинка = распакованная битмапа больше 2 МБ. Считаем по
        // naturalWidth/Height, а не по URL: арт из IndexedDB приходит как blob:
        // и по ссылке уже не отличим от мастера.
        if (b > 2 * 1048576) { bigImgs++; bigBytes += b; }
        if (!worst || b > worst.bytes) {
            const r = im.getBoundingClientRect();
            worst = { bytes: b, nat: im.naturalWidth + 'x' + im.naturalHeight,
                      css: Math.round(r.width) + 'x' + Math.round(r.height),
                      src: s.slice(-62) };
        }
    }
    const pm = performance.memory;
    let thumbBytes = 0, masterBytes = 0, thumbN = 0, masterN = 0;
    for (const e of performance.getEntriesByType('resource')) {
        const n = e.name || '';
        if (!/\/media\//.test(n)) continue;
        const sz = e.encodedBodySize || e.transferSize || 0;
        if (/\/media\/t2?\//.test(n)) { thumbBytes += sz; thumbN++; }
        else if (/\.(png|jpg|jpeg|webp)$/i.test(n)) { masterBytes += sz; masterN++; }
    }
    return { thumbBytes, masterBytes, thumbN, masterN,
             imgsTotal: total, imgsLoaded: loaded, imgsBroken: broken, bigImgs,
             bigImgMB: +(bigBytes / 1048576).toFixed(1),
             decodedImgMB: +(decoded / 1048576).toFixed(1),
             heapMB: pm ? +(pm.usedJSHeapSize / 1048576).toFixed(1) : null,
             domNodes: document.getElementsByTagName('*').length, worst };
};

function sizeOf(rel) { try { return fs.statSync(path.join(ROOT, rel)).size; } catch (e) { return 0; } }

(async () => {
    const r = { name: NAME, cards: CARDS.length, ok: false, crashed: false, t: {},
                thumbReqs: 0, masterReqs: 0, thumbBytes: 0, masterBytes: 0,
                pageErrors: [], consoleErrors: [], failedReqs: [], snap: {} };

    const browser = await chromium.launch({
        args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox',
               '--disable-dev-shm-usage', '--js-flags=--max-old-space-size=512'],
    });
    const ctx = await browser.newContext({ ...devices['iPhone 12'], deviceScaleFactor: 3 });
    await ctx.addInitScript(INIT);
    if (process.env.TRACE) await ctx.addInitScript({ path: process.env.TRACE });

    // Боевой origin -> локальный сервер через 302 (как в tools/probe.js): тела
    // файлов НЕ буферизуются в node, иначе сам стенд падает по памяти на
    // тридцати шести мастерах по 3 МБ. Считаем только URL, байты берём из
    // Resource Timing внутри страницы (см. SNAP).
    await ctx.route(GH + '**', route => {
        const u = new URL(route.request().url());
        const rel = u.pathname.replace('/card-collection', '') || '/';
        if (/\/media\/t2?\//.test(rel)) { r.thumbReqs++; r.thumbBytes += sizeOf(rel); }
        else if (/\/media\/[^/]+\.(png|jpg|jpeg|webp|mp3)$/i.test(rel)) { r.masterReqs++; r.masterBytes += sizeOf(rel); }
        route.fulfill({ status: 302, headers: { location: 'http://127.0.0.1:' + PORT + rel + u.search } });
    });
    // облако и метрики глушим — стенд должен быть детерминированным
    for (const pat of ['https://textdb.dev/**', 'https://api.ipify.org/**', 'https://api64.ipify.org/**',
                       'https://fonts.googleapis.com/**', 'https://fonts.gstatic.com/**']) {
        await ctx.route(pat, route => route.fulfill({ status: 200, contentType: 'application/json', body: 'null' }));
    }

    const page = await ctx.newPage();
    page.on('console', m => { if (m.type() === 'error') r.consoleErrors.push(m.text().slice(0, 200)); });
    page.on('pageerror', e => r.pageErrors.push(String(e.message).slice(0, 200)));
    page.on('requestfailed', q => r.failedReqs.push(q.url().slice(0, 130) + ' :: ' + ((q.failure() || {}).errorText)));
    page.on('crash', () => { r.crashed = true; });

    const shot = async tag => { await page.screenshot({ path: path.join(OUT, NAME + '-' + tag + '.png') }).catch(() => {}); };
    const step = async (tag, fn, wait) => {
        if (r.crashed) return;
        try { await fn(); } catch (e) { r.pageErrors.push(tag + ': ' + String(e.message).slice(0, 140)); }
        await page.waitForTimeout(wait === undefined ? 2500 : wait);
        try { r.snap[tag] = await page.evaluate(SNAP); } catch (e) { r.crashed = true; }
        await shot(tag);
    };

    try {
        const t0 = Date.now();
        await page.goto(PAGE_URL, { waitUntil: 'load', timeout: 90000 });
        r.t.load = Date.now() - t0;
        await page.waitForTimeout(2500);
        await page.evaluate(() => { try { window.jpSyncNow = () => {}; window.jpSyncSoon = () => {}; } catch (e) {} });
        // стартовые модалки (ежедневная награда и т.п.) закрываем — иначе на
        // скриншотах вместо альбома затемнённое стекло
        await page.evaluate(() => {
            try {
                ['modal-daily', 'modal-name', 'modal-reset', 'modal-export'].forEach(id => {
                    const m = document.getElementById(id); if (m) m.classList.add('hidden');
                });
            } catch (e) {}
        });

        await step('01-store', () => {}, 1500);
        await step('02-albums-hub', () => page.evaluate(() => switchTab('albums')), 2000);
        // вид по умолчанию — «Сетка» (grid), именно он и был сломан
        await step('03-album-grid', () => page.evaluate(() => openAlbum('pack-b377')), 3500);
        await step('04-album-scroll', async () => {
            for (let i = 0; i < 8 && !r.crashed; i++) {
                await page.evaluate(() => window.scrollBy(0, 800)).catch(() => {});
                await page.waitForTimeout(600);
            }
        }, 3000);

        r.view = await page.evaluate(() => {
            try { return JSON.parse(localStorage.getItem('ui_prefs_v1') || '{}').albums || null; } catch (e) { return null; }
        }).catch(() => null);
        r.cardView = await page.evaluate(() => { try { return albumsUiState().cardView; } catch (e) { return '?'; } }).catch(() => '?');
        r.longTasks = await page.evaluate(() => window.__lt).catch(() => null);
        r.winErrs = await page.evaluate(() => (window.__errs || []).slice(0, 8)).catch(() => null);
        if (process.env.TRACE) {
            r.masterCalls = await page.evaluate(() => (window.__masterCalls || []).slice(0, 80)).catch(() => null);
        }
        r.ok = !r.crashed;
    } catch (e) {
        r.fatal = String(e.message).slice(0, 300);
    }
    await browser.close().catch(() => {});
    fs.writeFileSync(path.join(OUT, NAME + '.json'), JSON.stringify(r, null, 2));

    const last = r.snap[Object.keys(r.snap).pop()] || {};
    const MB = b => (b / 1048576).toFixed(1);
    console.log('\n===== ' + NAME + ' ===== ' + (r.ok ? 'вкладка выжила' : '*** ВКЛАДКА УПАЛА (crash) ***'));
    console.log('карт в альбоме        : ' + r.cards + '  (вид: ' + r.cardView + ')');
    console.log('миниатюры media/t*    : ' + r.thumbReqs + ' запросов, ' + MB(r.thumbBytes) + ' МБ');
    console.log('мастера media/        : ' + r.masterReqs + ' запросов, ' + MB(r.masterBytes) + ' МБ');
    console.log('ВСЕГО скачано артов   : ' + MB(r.thumbBytes + r.masterBytes) + ' МБ');
    if (r.snap['04-album-scroll'] || last) {
        const s = r.snap['04-album-scroll'] || last;
        console.log('картинок в DOM        : ' + s.imgsLoaded + '/' + s.imgsTotal + ' доехало, битых ' + s.imgsBroken);
        console.log('тяжёлых (>2 МБ) картинок: ' + s.bigImgs + ' на ' + s.bigImgMB + ' МБ битмапов');
        console.log('распакованные битмапы : ' + s.decodedImgMB + ' МБ   heap ' + s.heapMB + ' МБ   DOM ' + s.domNodes);
        if (s.worst) console.log('крупнейшая картинка   : ' + s.worst.nat + ' -> ' + s.worst.css + ' css = ' + (s.worst.bytes / 1048576).toFixed(2) + ' МБ  …' + s.worst.src);
    }
    console.log('длинные задачи        : ' + JSON.stringify(r.longTasks));
    console.log('ошибки                : pageErrors ' + r.pageErrors.length + ', console.error ' + r.consoleErrors.length + ', failedReq ' + r.failedReqs.length);
    [...new Set(r.pageErrors)].slice(0, 5).forEach(e => console.log('   ! pageError: ' + e));
    [...new Set(r.consoleErrors)].slice(0, 5).forEach(e => console.log('   ! console  : ' + e));
    [...new Set(r.failedReqs)].slice(0, 5).forEach(e => console.log('   ! reqFail  : ' + e));
    process.exit(r.ok ? 0 : 1);
})().catch(e => { console.error('FATAL', e); process.exit(2); });
