/* b429: в просмотре карты страница не ездит по горизонтали на телефонах.

   A. CSS: touch-action pan-y + overscroll contain на модалке, overflow hidden на теле.
   B. Открытие просмотра блокирует скролл тела, закрытие — возвращает.
   C. Tilt карты выключен на тач-устройствах (nxIsTouchDevice), на десктопе жив.
   D. Свайп-листание (touchstart/touchend) по-прежнему работает.

   Запуск:  node tools/test-b429.js
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
    return { w, ev: s => w.eval(s), doc: w.document, html };
}

(async () => {
    const G = boot();
    const ev = G.ev, doc = G.doc;

    console.log('\nA. CSS-защита от горизонтального пана');
    ok(/#modal-inspect\{\s*touch-action:\s*pan-y;\s*overscroll-behavior:\s*contain;\s*\}/.test(G.html), 'модалка: touch-action pan-y + overscroll-behavior contain');
    ok(/body\.nx-inspect-open\{\s*overflow:\s*hidden;\s*\}/.test(G.html), 'тело с классом nx-inspect-open: overflow hidden');

    console.log('\nB. Блокировка скролла тела на время просмотра');
    ev('state.cards = STANDARD_CARDS.map(c => Object.assign({}, c)); state.collection = state.collection || {}; state.cards.forEach(c => state.collection[c.id] = 1);');
    ev('inspectCard(state.cards[0].id)');
    eq(doc.body.classList.contains('nx-inspect-open'), true, 'просмотр открыт → скролл тела заблокирован');
    ev('closeInspectModal()');
    eq(doc.body.classList.contains('nx-inspect-open'), false, 'закрыли → скролл возвращён');

    console.log('\nC. Tilt только для нетач-устройств');
    eq(ev('nxIsTouchDevice()'), false, 'без тача nxIsTouchDevice() = false');
    ev('inspectCard(state.cards[0].id)');
    ev('document.dispatchEvent(new MouseEvent("mousemove", { clientX: 300, clientY: 300, bubbles: true }))');
    ok(ev('document.getElementById("inspect-card-render").style.transform').indexOf('rotate') === 0, 'на десктопе tilt работает: ' + ev('document.getElementById("inspect-card-render").style.transform'));
    ev('closeInspectModal()');
    eq(ev('document.getElementById("inspect-card-render").style.transform'), '', 'при закрытии tilt сброшен');
    ev('Object.defineProperty(navigator, "maxTouchPoints", { value: 5, configurable: true })');
    eq(ev('nxIsTouchDevice()'), true, 'с maxTouchPoints nxIsTouchDevice() = true');
    ev('inspectCard(state.cards[0].id)');
    ev('document.getElementById("inspect-card-render").style.transform = ""');
    ev('document.dispatchEvent(new MouseEvent("mousemove", { clientX: 300, clientY: 300, bubbles: true }))');
    eq(ev('document.getElementById("inspect-card-render").style.transform'), '', 'на тач-устройстве tilt не применяется');
    ev('closeInspectModal()');

    console.log('\nD. Свайп-листание работает');
    ev('inspectCard(state.cards[0].id, state.cards.map(c => c.id))');
    const i0 = ev('inspectIdx');
    ev('(function(){ const t = new Event("touchstart"); t.touches = [{ clientX: 300 }]; document.dispatchEvent(t); const e2 = new Event("touchend"); e2.changedTouches = [{ clientX: 180 }]; document.dispatchEvent(e2); })()');
    eq(ev('inspectIdx'), i0 + 1, 'свайп влево листает вперёд');

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
