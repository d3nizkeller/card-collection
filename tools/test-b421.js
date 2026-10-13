/* b421: синхронизация переехала на документ v3.

   A. jpPath() указывает на nexus-tcg-jackpot-v3 (и в textdb, и в комнате firebase).
   B. Эпохи b420 продолжают работать на новом пути (регрессия).
   C. Пустой v3 (новая комната): первый клиент запушит свой реестр, банк продолжится.

   Запуск:  node tools/test-b421.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + a + (a === b ? '' : ' (ждём ' + b + ')'));

function boot() {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const dom = new JSDOM(html, {
        runScripts: 'dangerously',
        pretendToBeVisual: true,
        url: 'https://d3nizkeller.github.io/card-collection/',
    });
    const w = dom.window;
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
        value: () => Promise.resolve({ ok: false, status: 0, text: () => Promise.resolve(''), json: () => Promise.resolve(null) }),
        configurable: true,
    });
    w.navigator.sendBeacon = () => true;
    w.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} };
    w.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
    w.matchMedia = w.matchMedia || (q => ({ matches: false, media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }));
    w.THREE = new Proxy({}, { get: () => function () { return {}; } });
    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
    w.document.body.appendChild(sc);
    return { w, ev: s => w.eval(s) };
}

(async () => {
    console.log('\nA. Путь синхронизации');
    const A = boot();
    ok(A.ev('jpPath()').indexOf('nexus-tcg-jackpot-v3') >= 0, 'textdb: ' + A.ev('jpPath()'));
    ok(A.ev('jpPath()').indexOf('-v2') < 0, 'v2 больше не используется');
    A.ev('CLOUD.db = "https://room.example/db"');
    ok(A.ev('jpPath()').indexOf('/nexus-jackpot-v3.json') >= 0, 'комната firebase: ' + A.ev('jpPath()'));

    console.log('\nB. Эпохи на новом пути (регрессия b420)');
    const B = boot();
    B.ev('jackpot.led = {me: 1}; jackpotMerge({ep: 7, led: {x: 2}, won: {}, wins: {}})');
    eq(B.ev('jackpot.ep'), 7, 'ep принят');
    eq(B.ev('jackpot.led["me"]'), undefined, 'реестр принят целиком');
    B.ev('jackpotMerge({led: {legacy: 5}})');
    eq(B.ev('jackpot.led["legacy"]'), undefined, 'без ep при нашей эпохе реестр не принимается');

    console.log('\nC. Пустой документ (новая комната): банк продолжается локальным пушем');
    const C = boot();
    C.ev('jackpot.led = {mine: 42000}; jackpot.won = {};');
    const doc = C.ev('jpDoc()');
    eq(doc.jp.led.mine, 42000, 'jpDoc() несёт локальный реестр в пустое облако');
    eq(typeof doc.jp.ep, 'number', 'и эпоху тоже');

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
