/* Стенд сравнения: оригинал vs мобильная сборка.
   Запуск: node tools/compare.js <url-orig> <url-fixed> [outDir] */
const { chromium, devices } = require('/tmp/pw/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const ORIG = process.argv[2];
const FIXED = process.argv[3];
const OUT = process.argv[4] || '/tmp/shots';
fs.mkdirSync(OUT, { recursive: true });

const http = require('http');
const GH = 'https://d3nizkeller.github.io/card-collection/';
// Облачный каталог комнаты ссылается на боевой origin (d3nizkeller.github.io).
// В тесте этого origin нет, а миниатюры media/t|t2 ещё не задеплоены — поэтому
// проксируем боевой origin на локальный сервер: так проверка честно повторяет
// прод, где игра и лежит на d3nizkeller.github.io/card-collection/.
function localFetch(port, path) {
    return new Promise((res) => {
        http.get({ host: '127.0.0.1', port, path }, r => {
            const chunks = [];
            r.on('data', d => chunks.push(d));
            r.on('end', () => res({ status: r.statusCode, headers: r.headers, body: Buffer.concat(chunks) }));
        }).on('error', () => res(null));
    });
}
async function routeGithub(context, port) {
    await context.route(GH + '**', async route => {
        const u = new URL(route.request().url());
        const rel = u.pathname.replace('/card-collection', '') || '/';
        const got = await localFetch(port, rel + u.search);
        if (!got) return route.abort();
        if (got.status === 404) return route.fulfill({ status: 404, contentType: 'text/plain', body: 'not found' });
        const ct = got.headers['content-type'] ||
            (/\.webp$/.test(rel) ? 'image/webp' :
             /\.png$/.test(rel) ? 'image/png' :
             /\.jpe?g$/.test(rel) ? 'image/jpeg' :
             /\.mp3$/.test(rel) ? 'audio/mpeg' : 'application/octet-stream');
        return route.fulfill({ status: got.status, contentType: ct, body: got.body });
    });
}

const INIT = `
window.__lt = { count: 0, total: 0, worst: 0, worstAt: 0 };
window.__ltStart = Date.now();
try {
    const po = new PerformanceObserver(l => {
        for (const e of l.getEntries()) {
            window.__lt.count++;
            window.__lt.total += e.duration;
            if (e.duration > window.__lt.worst) { window.__lt.worst = e.duration; window.__lt.worstAt = e.startTime | 0; }
        }
    });
    po.observe({ entryTypes: ['longtask'] });
} catch (e) { window.__lt.unsupported = true; }
window.__errs = [];
window.addEventListener('error', e => window.__errs.push('error: ' + (e.message || '')));
window.addEventListener('unhandledrejection', e => window.__errs.push('reject: ' + ((e.reason && e.reason.message) || e.reason)));
`;

async function probe(name, url) {
    const browser = await chromium.launch({
        args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader',
               '--disable-dev-shm-usage', '--no-sandbox'],
    });
    const ctx = await browser.newContext({
        ...devices['iPhone 12'],
        // Telegram Mini App ≈ iOS WKWebView: DPR 3 и жёсткий лимит памяти
        deviceScaleFactor: 3,
    });
    await ctx.addInitScript(INIT);
    await routeGithub(ctx, name === 'fixed' ? 8002 : 8001);
    const page = await ctx.newPage();
    const r = { name, url, consoleErrors: [], pageErrors: [], failedReqs: [], t: {}, metrics: {} };

    page.on('console', m => { if (m.type() === 'error') r.consoleErrors.push(m.text().slice(0, 240)); });
    page.on('pageerror', e => r.pageErrors.push(String(e.message).slice(0, 240)));
    page.on('requestfailed', q => {
        const u = q.url();
        if (!/fonts\.g(oogleapis|static)\.com|textdb\.dev|archive\.org|corsproxy|weserv/.test(u))
            r.failedReqs.push(u.slice(0, 150) + ' :: ' + ((q.failure() || {}).errorText));
    });

    const t0 = Date.now();
    await page.goto(url, { waitUntil: 'load', timeout: 120000 });
    r.t.load = Date.now() - t0;
    try { await page.waitForLoadState('networkidle', { timeout: 25000 }); } catch (e) {}
    r.t.networkidle = Date.now() - t0;
    await page.waitForTimeout(4000);
    r.t.settled = Date.now() - t0;

    r.metrics = await page.evaluate(() => {
        const m = {};
        m.domNodes = document.getElementsByTagName('*').length;
        m.imgsTotal = document.images.length;
        let decoded = 0, loaded = 0;
        for (const im of document.images) {
            if (im.complete && im.naturalWidth) { decoded += im.naturalWidth * im.naturalHeight * 4; loaded++; }
        }
        m.imgsLoaded = loaded;
        m.decodedImgMB = +(decoded / 1048576).toFixed(1);
        const pm = performance.memory;
        m.heapMB = pm ? +(pm.usedJSHeapSize / 1048576).toFixed(1) : null;
        m.stylesheets = document.styleSheets.length;
        let rules = 0;
        for (const ss of document.styleSheets) { try { rules += ss.cssRules.length; } catch (e) {} }
        m.cssRules = rules;
        m.tailwindJitPresent = typeof window.tailwind !== 'undefined';
        m.threePresent = typeof window.THREE !== 'undefined';
        const res = performance.getEntriesByType('resource');
        m.reqCount = res.length;
        m.transferMB = +(res.reduce((a, e) => a + (e.transferSize || 0), 0) / 1048576).toFixed(2);
        m.biggest = res.map(e => [e.name.split('/').pop().split('?')[0], Math.round((e.transferSize || 0) / 1024)])
                       .sort((a, b) => b[1] - a[1]).slice(0, 6);
        m.fcp = (performance.getEntriesByName('first-contentful-paint')[0] || {}).startTime | 0;
        return m;
    });

    await page.screenshot({ path: path.join(OUT, name + '-01-start.png') }).catch(() => {});

    const clickText = async (txt) => {
        const el = await page.$(`xpath=//*[self::button or self::a][normalize-space(.)="${txt}" or contains(normalize-space(.), "${txt}")][1]`);
        if (el) { await el.scrollIntoViewIfNeeded().catch(() => {}); await el.click({ timeout: 6000 }).catch(() => {}); return true; }
        return false;
    };
    const nav = async (label, fn) => {
        const a = Date.now();
        try { await fn(); } catch (e) { r.pageErrors.push(label + ': ' + e.message); }
        await page.waitForTimeout(2500);
        r.t[label] = Date.now() - a;
        await page.screenshot({ path: path.join(OUT, name + '-' + label + '.png') }).catch(() => {});
    };

    for (const label of ['Альбомы', 'Магазин', 'Биржа', 'Игры', 'Колода', 'Статистика']) {
        await nav(label, () => clickText(label));
    }
    // самый тяжёлый экран: сетка карточек альбома
    await nav('album-grid', async () => {
        await clickText('Альбомы');
        await page.waitForTimeout(900);
        const clickable = await page.$$('xpath=//*[contains(@onclick,"Album") or contains(@onclick,"album")]');
        if (clickable[1]) await clickable[1].click({ timeout: 4000 }).catch(() => {});
    });
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight)).catch(() => {});
    await page.waitForTimeout(2500);
    await page.screenshot({ path: path.join(OUT, name + '-zz-scrolled.png') }).catch(() => {});

    r.after = await page.evaluate(() => {
        let decoded = 0, n = 0;
        for (const im of document.images) if (im.complete && im.naturalWidth) { decoded += im.naturalWidth * im.naturalHeight * 4; n++; }
        const pm = performance.memory;
        return {
            imgsLoaded: n, imgsTotal: document.images.length,
            decodedImgMB: +(decoded / 1048576).toFixed(1),
            heapMB: pm ? +(pm.usedJSHeapSize / 1048576).toFixed(1) : null,
            domNodes: document.getElementsByTagName('*').length,
            longTasks: window.__lt,
            windowErrors: (window.__errs || []).slice(0, 10),
        };
    });

    await browser.close();
    return r;
}

(async () => {
    const results = [];
    for (const [name, url] of [['orig', ORIG], ['fixed', FIXED]]) {
        console.log('\n================ ' + name + ' ================ ' + url);
        let r;
        try { r = await probe(name, url); }
        catch (e) { console.log('СБОЙ ПРОГОНА: ' + e.message); continue; }
        results.push(r);
        const m = r.metrics;
        console.log(`время: load ${r.t.load}мс | networkidle ${r.t.networkidle}мс | settled ${r.t.settled}мс | FCP ${m.fcp}мс`);
        console.log(`сеть : запросов ${m.reqCount}, ${m.transferMB} МБ | крупнейшие ${JSON.stringify(m.biggest)}`);
        console.log(`DOM  : узлов ${m.domNodes} | <img> ${m.imgsTotal} (загружено ${m.imgsLoaded}) | битмапы ${m.decodedImgMB} МБ | heap ${m.heapMB} МБ`);
        console.log(`CSS  : таблиц ${m.stylesheets}, правил ${m.cssRules} | TailwindJIT в странице: ${m.tailwindJitPresent} | THREE: ${m.threePresent}`);
        console.log(`после обхода разделов: ${JSON.stringify(r.after)}`);
        console.log(`ошибки: pageErrors ${r.pageErrors.length}, console.error ${r.consoleErrors.length}, failedReq ${r.failedReqs.length}`);
        r.pageErrors.slice(0, 10).forEach(e => console.log('   ! pageError: ' + e));
        [...new Set(r.consoleErrors)].slice(0, 10).forEach(e => console.log('   ! console  : ' + e));
        [...new Set(r.failedReqs)].slice(0, 10).forEach(e => console.log('   ! reqFail  : ' + e));
    }
    fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(results, null, 2));
    console.log('\nотчёт: ' + path.join(OUT, 'report.json'));
})();
