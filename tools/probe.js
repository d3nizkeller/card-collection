/* Прогон ОДНОЙ версии игры в мобильной эмуляции.
   Запуск: node tools/probe.js <name> <url> <port> <outJson> [shotsDir]

   port — порт локального сервера, на который перенаправляется боевой origin
   d3nizkeller.github.io/card-collection (облачный каталог комнаты ссылается
   на него напрямую, а в песочнице его нет). */
const { chromium, devices } = require('/tmp/pw/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const [, , NAME, PAGE_URL, PORT, OUTJSON, SHOTS] = process.argv;
const OUT = SHOTS || '/tmp/shots';
fs.mkdirSync(OUT, { recursive: true });
const GH = 'https://d3nizkeller.github.io/card-collection/';

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
`;

const SNAP = () => {
    let decoded = 0, loaded = 0, total = 0, worst = null;
    for (const im of document.images) {
        total++;
        if (!im.complete || !im.naturalWidth) continue;
        const b = im.naturalWidth * im.naturalHeight * 4;
        decoded += b; loaded++;
        if (!worst || b > worst.bytes) {
            const r = im.getBoundingClientRect();
            worst = { bytes: b, nat: im.naturalWidth + 'x' + im.naturalHeight,
                      css: Math.round(r.width) + 'x' + Math.round(r.height),
                      src: (im.currentSrc || im.src || '').slice(-58) };
        }
    }
    const pm = performance.memory;
    return {
        imgsTotal: total, imgsLoaded: loaded,
        decodedImgMB: +(decoded / 1048576).toFixed(1),
        heapMB: pm ? +(pm.usedJSHeapSize / 1048576).toFixed(1) : null,
        domNodes: document.getElementsByTagName('*').length,
        worst,
    };
};

(async () => {
    const r = { name: NAME, url: PAGE_URL, ok: false, crashed: false, t: {},
                consoleErrors: [], pageErrors: [], failedReqs: [], thumbReqs: 0, masterReqs: 0 };
    const browser = await chromium.launch({
        args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox',
               '--disable-dev-shm-usage', '--js-flags=--max-old-space-size=512'],
    });
    const ctx = await browser.newContext({ ...devices['iPhone 12'], deviceScaleFactor: 3 });
    await ctx.addInitScript(INIT);

    // боевой origin -> локальный сервер, через 302 (без буферизации тел в node)
    await ctx.route(GH + '**', route => {
        const u = new URL(route.request().url());
        const rel = u.pathname.replace('/card-collection', '') || '/';
        if (/\/media\/t2?\//.test(rel)) r.thumbReqs++;
        else if (/\/media\//.test(rel)) r.masterReqs++;
        route.fulfill({ status: 302, headers: { location: 'http://127.0.0.1:' + PORT + rel + u.search } });
    });

    const page = await ctx.newPage();
    page.on('console', m => { if (m.type() === 'error') r.consoleErrors.push(m.text().slice(0, 200)); });
    page.on('pageerror', e => r.pageErrors.push(String(e.message).slice(0, 200)));
    page.on('requestfailed', q => {
        const u = q.url();
        if (!/fonts\.g(oogleapis|static)\.com|textdb\.dev|archive\.org|corsproxy|weserv/.test(u))
            r.failedReqs.push(u.slice(0, 130) + ' :: ' + ((q.failure() || {}).errorText));
    });
    page.on('crash', () => { r.crashed = true; });

    const shot = async tag => { await page.screenshot({ path: path.join(OUT, NAME + '-' + tag + '.png') }).catch(() => {}); };
    const step = async (tag, fn, wait) => {
        if (r.crashed) return;
        const a = Date.now();
        try { await fn(); } catch (e) { r.pageErrors.push(tag + ': ' + String(e.message).slice(0, 120)); }
        await page.waitForTimeout(wait === undefined ? 2500 : wait);
        r.t[tag] = Date.now() - a;
        try { r.snap = r.snap || {}; r.snap[tag] = await page.evaluate(SNAP); } catch (e) { r.crashed = true; }
        await shot(tag);
    };

    try {
        const t0 = Date.now();
        await page.goto(PAGE_URL, { waitUntil: 'load', timeout: 90000 });
        r.t.load = Date.now() - t0;
        try { await page.waitForLoadState('networkidle', { timeout: 20000 }); } catch (e) {}
        r.t.networkidle = Date.now() - t0;
        await page.waitForTimeout(4000);
        r.t.settled = Date.now() - t0;

        r.metrics = await page.evaluate(() => {
            const m = {};
            m.stylesheets = document.styleSheets.length;
            let rules = 0;
            for (const ss of document.styleSheets) { try { rules += ss.cssRules.length; } catch (e) {} }
            m.cssRules = rules;
            m.tailwindJit = typeof window.tailwind !== 'undefined';
            m.three = typeof window.THREE !== 'undefined';
            const res = performance.getEntriesByType('resource');
            m.reqCount = res.length;
            m.transferMB = +(res.reduce((a, e) => a + (e.transferSize || 0), 0) / 1048576).toFixed(2);
            m.fcp = (performance.getEntriesByName('first-contentful-paint')[0] || {}).startTime | 0;
            return m;
        });
        await step('01-start', () => {}, 0);

        const clickText = async txt => {
            const el = await page.$(`xpath=//*[self::button or self::a][contains(normalize-space(.), "${txt}")][1]`);
            if (el) { await el.scrollIntoViewIfNeeded().catch(() => {}); await el.click({ timeout: 6000 }).catch(() => {}); return true; }
            return false;
        };
        for (const label of ['Магазин', 'Биржа', 'Колода', 'Игры', 'Статистика']) {
            await step(label, () => clickText(label));
        }
        // самый тяжёлый экран: альбом со всеми картами облачного каталога
        await step('07-albums', () => clickText('Альбомы'));
        await step('08-album-open', async () => {
            const el = await page.$('xpath=//*[contains(@onclick,"openAlbum")][1]');
            if (el) await el.click({ timeout: 5000 }).catch(() => {});
        }, 4000);
        await step('09-album-scroll', async () => {
            for (let i = 0; i < 6 && !r.crashed; i++) {
                await page.evaluate(() => window.scrollBy(0, 900)).catch(() => {});
                await page.waitForTimeout(700);
            }
        }, 1500);

        r.after = await page.evaluate(() => ({
            longTasks: window.__lt,
            windowErrors: (window.__errs || []).slice(0, 8),
        })).catch(() => null);
        r.ok = !r.crashed;
    } catch (e) {
        r.fatal = String(e.message).slice(0, 300);
    }
    await browser.close().catch(() => {});
    fs.writeFileSync(OUTJSON, JSON.stringify(r, null, 2));

    const m = r.metrics || {};
    console.log(`\n===== ${NAME} ===== ${r.ok ? 'ЗАВЕРШИЛОСЬ' : '*** ВКЛАДКА УПАЛА (crash) ***'}`);
    console.log(`время : load ${r.t.load}мс | networkidle ${r.t.networkidle}мс | settled ${r.t.settled}мс | FCP ${m.fcp}мс`);
    console.log(`сеть  : запросов ${m.reqCount}, ${m.transferMB} МБ | миниатюр ${r.thumbReqs}, полных артов ${r.masterReqs}`);
    console.log(`CSS   : таблиц ${m.stylesheets}, правил ${m.cssRules} | TailwindJIT=${m.tailwindJit} THREE=${m.three}`);
    if (r.snap) {
        console.log('битмапы/heap по экранам:');
        for (const k of Object.keys(r.snap)) {
            const s = r.snap[k];
            console.log(`   ${k.padEnd(15)} картинок ${String(s.imgsLoaded).padStart(3)}/${String(s.imgsTotal).padEnd(3)} битмапы ${String(s.decodedImgMB).padStart(7)} МБ  heap ${String(s.heapMB).padStart(6)} МБ  DOM ${s.domNodes}`);
        }
        const last = r.snap[Object.keys(r.snap).pop()];
        if (last && last.worst) console.log(`   крупнейшая картинка: ${last.worst.nat} -> ${last.worst.css} css, ${(last.worst.bytes / 1048576).toFixed(2)} МБ  ${last.worst.src}`);
    }
    if (r.after) console.log(`длинные задачи: ${JSON.stringify(r.after.longTasks)}`);
    console.log(`ошибки: pageErrors ${r.pageErrors.length}, console.error ${r.consoleErrors.length}, failedReq ${r.failedReqs.length}`);
    [...new Set(r.pageErrors)].slice(0, 6).forEach(e => console.log('   ! pageError: ' + e));
    [...new Set(r.consoleErrors)].slice(0, 6).forEach(e => console.log('   ! console  : ' + e));
    [...new Set(r.failedReqs)].slice(0, 6).forEach(e => console.log('   ! reqFail  : ' + e));
})();
