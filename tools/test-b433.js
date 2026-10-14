/* b433: топ-3 по СУММЕ среди срывов за 24 часа — и обновляется в реальном времени.

   A. Суммы в топе убывают (759q выше 18q), порядок не зависит от свежести.
   B. Срыв старше 24 часов в топ не попадает (окно суток).
   C. Новый крупный срыв сразу встаёт первым (реальное время).
   D. Все срывы старше окна — топ не пустой (фолбэк на весь зал).
   E. Безымянные по-прежнему не попадают (b432).

   Запуск:  node tools/test-b433.js
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
    w.HTMLCanvasElement.prototype.getContext = () => null;
    w.HTMLMediaElement.prototype.play = function () { return Promise.resolve(); };
    w.HTMLMediaElement.prototype.pause = function () {};
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
    return { w, ev: s => w.eval(s), doc: w.document };
}
const names = doc => Array.from(doc.getElementById('slots-jp-top-list').querySelectorAll('.jp-name')).map(e => e.textContent);

(async () => {
    const NOW = Date.now();
    const H = 3600000;

    console.log('\nA. Топ-3 по сумме, порядок не зависит от свежести');
    const A = boot();
    A.ev('jackpot.hall = [' +
        '{ n: "Утренний", a: 18000000000000000, t: ' + (NOW - 2 * H) + ', nm: 1 },' +   // 18q, раньше
        '{ n: "Дневной",  a: 759000000000000000000, t: ' + (NOW - 5 * H) + ', nm: 1 },' + // 759q, ещё раньше
        '{ n: "Мелкий",   a: 1000000000000000, t: ' + (NOW - 60000) + ', nm: 1 }' +       // 1q, свежий
        ']; jackpotRender()');
    eq(JSON.stringify(names(A.doc)), JSON.stringify(['Дневной', 'Утренний', 'Мелкий']), 'суммы убывают: 759q → 18q → 1q, несмотря на время');

    console.log('\nB. Окно 24 часа');
    const B = boot();
    B.ev('jackpot.hall = [' +
        '{ n: "Древний рекорд", a: 999000000000000000000, t: ' + (NOW - 25 * H) + ', nm: 1 },' +
        '{ n: "Сегодняшний", a: 5000, t: ' + (NOW - 60000) + ', nm: 1 }' +
        ']; jackpotRender()');
    eq(JSON.stringify(names(B.doc)), JSON.stringify(['Сегодняшний']), 'срыв старше 24 ч в топ не попал');

    console.log('\nC. Новый крупный срыв сразу первый (реальное время)');
    const C = boot();
    C.ev('jackpot.hall = [{ n: "Денис Keller", a: 18000000000000000, t: ' + (NOW - 60000) + ', nm: 1 }]; jackpotRender()');
    eq(names(C.doc)[0], 'Денис Keller', 'до нового срыва первый — Денис');
    C.ev('jackpot.hall.unshift({ n: "An", a: 759000000000000000000, t: ' + NOW + ', nm: 1 }); jackpotRender()');
    eq(names(C.doc)[0], 'An', 'новый срыв 759q мгновенно встал первым');

    console.log('\nD. Все срывы старше окна — фолбэк на весь зал');
    const D = boot();
    D.ev('jackpot.hall = [{ n: "Древний", a: 7000, t: ' + (NOW - 48 * H) + ', nm: 1 }, { n: "Древнее", a: 9000, t: ' + (NOW - 49 * H) + ', nm: 1 }]; jackpotRender()');
    eq(JSON.stringify(names(D.doc)), JSON.stringify(['Древнее', 'Древний']), 'топ не пустой: фолбэк на весь зал');

    console.log('\nE. Безымянные по-прежнему вне топа (b432)');
    const E = boot();
    E.ev('jackpot.hall = [{ n: "Игрок-zzzz", a: 999000000000000000000, t: ' + NOW + ', nm: 0 }, { n: "Именной", a: 1000, t: ' + (NOW - 1000) + ', nm: 1 }]; jackpotRender()');
    eq(JSON.stringify(names(E.doc)), JSON.stringify(['Именной']), 'безымянный рекорд суток в топ не попал');

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
