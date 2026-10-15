/* b422: общий банк — общий и в реальном времени.

   A. jpPullLight: лёгкий pull сливает облако без лишнего пуша (15-секундный
      ритм вместо 60-секундного): чужой взнос виден сразу.
   B. jpPullLight: если наш реестр впереди облака — запускает догоняющий пуш.
   C. b436: вкладка на старой сборке замечает новую тихо — без баннера и
      кнопки: регистрирует авто-обновление (window.__nxAutoUpd), активную
      видимую вкладку не перезагружает.
   D. Регрессии: эпохи b420/b421, разряды b419, prune rm b420.

   Запуск:  node tools/test-b422.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + a + (a === b ? '' : ' (ждём ' + b + ')'));

function boot(fetchHandler, ownTag) {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const dom = new JSDOM(html, {
        runScripts: 'dangerously',
        pretendToBeVisual: true,
        url: 'https://d3nizkeller.github.io/card-collection/',
    });
    const w = dom.window;
    const calls = [];
    const ctx2d = () => new Proxy({}, {
        get(t, k) {
            if (k === 'canvas') return { width: 256, height: 256, style: {} };
            if (k === 'measureText') return () => ({ width: 10 });
            if (k === 'getImageData') return () => ({ data: new Uint8ClampedArray(4) });
            if (k === 'createLinearGradient' || k === 'createRadialGradient') return () => ({ addColorStop() {} });
            if (k === 'createPattern') return () => null;
            return t[k] !== undefined ? t[k] : (() => {});
        },
        set(t, k, v) { t[k] = v; return true; },
    });
    w.HTMLCanvasElement.prototype.getContext = kind => (kind === '2d' ? ctx2d() : null);
    w.HTMLCanvasElement.prototype.toDataURL = () => 'data:image/png;base64,';
    w.HTMLMediaElement.prototype.play = function () { return Promise.resolve(); };
    w.HTMLMediaElement.prototype.pause = function () {};
    w.HTMLMediaElement.prototype.load = function () {};
    Object.defineProperty(w, 'fetch', {
        value: (url, opt) => {
            calls.push({ url: String(url), method: (opt && opt.method) || 'GET' });
            return fetchHandler ? fetchHandler(String(url), opt, calls) : Promise.resolve({ ok: false, status: 0, text: () => Promise.resolve(''), json: () => Promise.resolve(null) });
        },
        configurable: true,
    });
    w.navigator.sendBeacon = () => true;
    w.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} };
    w.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
    w.matchMedia = w.matchMedia || (q => ({ matches: false, media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }));
    w.THREE = new Proxy({}, { get: () => function () { return {}; } });
    if (ownTag) {
        // отдельный МАРКЕРНЫЙ тег: jsdom не грузит внешние src, но document.scripts
        // его видит — nxOwnTag() читает тег сборки именно оттуда
        const mk = w.document.createElement('script');
        mk.src = 'https://d3nizkeller.github.io/card-collection/assets/app.js?v=' + ownTag;
        w.document.head.appendChild(mk);
    }
    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
    w.document.body.appendChild(sc);
    return { w, ev: s => w.eval(s), doc: w.document, calls };
}

const resp = obj => Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve(JSON.stringify(obj)), json: () => Promise.resolve(obj) });

(async () => {
    // ===== A. pull сливает чужое без лишнего пуша =====
    console.log('\nA. jpPullLight: чужой взнос виден сразу');
    const remoteDoc = { jp: { led: { pother: 500000 }, won: {}, wins: {}, names: {}, hall: [], ep: 0 }, jpc: null, mk: null, st: null, updatedAt: '1-x' };
    const A = boot((url, opt) => resp(remoteDoc));
    const av = A.ev;
    av('jackpot.led = {}; jackpot.won = {};');
    const p0 = av('jackpotPool()');
    const pushes0 = A.calls.filter(c => c.method !== 'GET').length;
    await av('jpPullLight(), new Promise(r => setTimeout(r, 300))');
    eq(av('jackpotPool()') - p0, 500000, 'чужой взнос 500k доехал без событий и таймера минуты');
    eq(A.calls.filter(c => c.method !== 'GET').length, pushes0, 'лишнего пуша не было (мы не впереди облака)');

    // ===== B. мы впереди — догоняющий пуш =====
    console.log('\nB. jpPullLight: свой взнос пушится догоняющим циклом');
    const B = boot((url, opt) => resp({ jp: { led: {}, won: {}, wins: {}, hall: [], ep: 0 }, updatedAt: '1-x' }));
    const bv = B.ev;
    bv('jackpot.led = {}; jackpot.won = {};');
    bv('jackpotFeed(777000)');
    const before = B.calls.filter(c => c.method !== 'GET').length;
    await bv('jpPullLight(), new Promise(r => setTimeout(r, 600))');
    ok(B.calls.filter(c => c.method !== 'GET').length > before, 'обнаружив себя впереди, клиент запушил реестр');

    // ===== C. проверка версии (b436: тихо, без баннера) =====
    console.log('\nC. nxVersionNudge → b436: старая вкладка узнаёт о новой сборке тихо');
    const C = boot((url) => {
        if (String(url).indexOf('index.html') === 0 || String(url).indexOf('index.html?nc') >= 0)
            return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve('<script src="assets/app.js?v=nxmob99"></script>'), json: () => Promise.resolve(null) });
        if (String(url).indexOf('assets/app.js') >= 0)
            return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve('/* new build */ nexus-tcg-jackpot-v3 nexus-jackpot-v3.json'), json: () => Promise.resolve(null) });
        return resp({ jp: { led: {}, won: {}, wins: {}, hall: [], ep: 0 }, updatedAt: '1-x' });
    }, 'nxmob83');
    const cv = C.ev;
    eq(cv('nxOwnTag()'), 'nxmob83', 'свой тег читается из src скрипта');
    await cv('nxVersionNudge(), new Promise(r => setTimeout(r, 300))');
    ok(!C.doc.getElementById('nx-ver-toast'), 'b436: баннера «Обновить» больше нет');
    eq((C.doc.getElementById('toast-container') || { childElementCount: 0 }).childElementCount, 0, 'и вообще никаких тостов о версии');
    eq(cv('(window.__nxAutoUpd || {}).tag'), 'nxmob99', 'но авто-обновление зарегистрировало новый тег');
    eq(cv('(window.__nxAutoUpd || {}).swapped || ""'), '', 'документ тот же v3 — hot-swap не нужен');
    eq(cv('window.__reloads || 0'), 0, 'видимая активная вкладка не перезагружается');
    // свой тег совпадает — авто-обновление не стартует
    const D = boot((url) => {
        if (String(url).indexOf('index.html') >= 0)
            return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve('<script src="assets/app.js?v=nxmob84"></script>'), json: () => Promise.resolve(null) });
        return resp({ jp: { led: {}, won: {}, wins: {}, hall: [], ep: 0 }, updatedAt: '1-x' });
    }, 'nxmob84');
    await D.ev('nxVersionNudge(), new Promise(r => setTimeout(r, 300))');
    ok(!D.doc.getElementById('nx-ver-toast'), 'на актуальной сборке баннера нет');
    ok(!D.ev('(window.__nxAutoUpd || {}).tag'), 'и авто-обновление не регистрируется');

    // ===== D2. самовосстановление после загрязнения (b423) =====
    console.log('\nD2. b423: загрязнённый реестр чинит себя сам');
    const G = boot((url, opt) => resp({ jp: { led: { clean: 1000 }, won: {}, wins: {}, hall: [], ep: 5 }, updatedAt: '1-x' }));
    const gv = G.ev;
    gv('cloudGuest = () => false');
    gv('jackpot.ep = 5; jackpot.led = {}; jackpot.won = {}; for (let i = 0; i < 900; i++) { jackpot.led["junk#" + i] = 1e12; }');
    const pushesG = G.calls.filter(c => c.method !== 'GET').length;
    await gv('jpPullLight(), new Promise(r => setTimeout(r, 800))');
    ok(gv('Object.keys(jackpot.led).length') <= 6, '900 ключей схлопнулись в каскад: ' + gv('Object.keys(jackpot.led).length'));
    eq(gv('jackpot.ep'), 6, 'эпоха увеличена — остальные примут реестр целиком');
    ok(G.calls.filter(c => c.method !== 'GET').length > pushesG, 'уплотнённый реестр сразу опубликован');

    // ===== E. регрессии =====
    console.log('\nE. Регрессии b419–b421');
    const E = boot();
    const evv = E.ev;
    eq(evv('jpLedAdd("led", "pr", 1e30)'), 1e30, 'b419: 1e30 ложится целиком');
    evv('jackpot.led = {me: 1}; jackpotMerge({ep: 9, led: {x: 2}, won: {}, wins: {}})');
    eq(evv('jackpot.ep'), 9, 'b420/b421: эпоха принимается');
    eq(evv('jpPath()').indexOf('nexus-tcg-jackpot-v3') >= 0, true, 'b421: путь v3');
    evv('marketRemovedAddMany(Array.from({length: 400}, (_, i) => "old_" + i))');
    ok(Object.keys(evv('marketRemoved()')).length <= 300, 'b420: rm обрезается');

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
