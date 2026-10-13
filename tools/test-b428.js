/* b428: просмотр карточек альбома под телефоны.

   A. Media-query для #inspect-float присутствует в разметке (карта ужимается по высоте).
   B. Стрелки листания на телефоне компактнее (w-9/left-1), на десктопе прежние.
   C. Подсказка на телефоне — про свайп, на десконе — про стрелки/Esc.
   D. Просмотр карты из альбома по-прежнему открывается и листается.

   Запуск:  node tools/test-b428.js
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

    console.log('\nA. Media-query высоты карты на телефоне');
    let rule = '';
    for (const sh of doc.styleSheets) {
        try {
            const walk = rs => { for (const r of rs) { if (r.cssRules) { walk(r.cssRules); continue; } if ((r.selectorText || '').indexOf('#inspect-float') >= 0) rule += r.cssText + ' | '; } };
            walk(sh.cssRules || []);
        } catch (e) {}
    }
    ok((rule.indexOf('max-width') >= 0 && rule.indexOf('58vh') >= 0) || (G.html.indexOf('#inspect-float{ max-width: min(24rem, calc(58vh * 0.5625))') >= 0),
        'правило для #inspect-float ограничивает карту по высоте экрана');
    ok(G.html.indexOf('@media (max-width:640px)') >= 0, 'правило обёрнуто в @media (max-width:640px) — десктоп не тронут');

    console.log('\nB. Стрелки компактные на телефоне');
    const prev = doc.getElementById('inspect-prev');
    const next = doc.getElementById('inspect-next');
    ok(prev.className.indexOf('w-9 h-9') >= 0 && prev.className.indexOf('sm:w-11 sm:h-11') >= 0, 'prev: w-9 на телефоне, w-11 на десктопе');
    ok(prev.className.indexOf('left-1 ') >= 0 && next.className.indexOf('right-1 ') >= 0, 'прижаты к краям на телефоне (left-1/right-1)');

    console.log('\nC. Подсказка про свайп');
    const hint = doc.querySelector('#modal-inspect p.mt-1');
    ok(hint && hint.querySelector('.sm\\:hidden') && /Свайп/.test(hint.textContent), 'на телефоне: «Свайп влево/вправо — листать, ✕ — закрыть»');
    ok(hint && hint.querySelector('.hidden.sm\\:inline') && /Esc/.test(hint.textContent), 'на десктопе: прежняя подсказка со стрелками и Esc');

    console.log('\nD. Просмотр из альбома работает');
    ev('state.cards = STANDARD_CARDS.map(c => Object.assign({}, c)); state.collection = state.collection || {}; state.cards.forEach(c => state.collection[c.id] = 1);');
    ev('openAlbum("pack-1790762837197")');
    ev('renderAlbumGrid()');
    const first = ev('albumViewIds[0]');
    ok(!!first, 'альбом открыт, список листания собран: ' + first);
    ev('inspectCard(albumViewIds[0], albumViewIds)');
    eq(doc.getElementById('modal-inspect').classList.contains('hidden'), false, 'просмотр карты открыт');
    ev('inspectStep(1)');
    ok(ev('inspectIdx') === 1, 'листание работает');
    ev('closeInspectModal()');
    eq(doc.getElementById('modal-inspect').classList.contains('hidden'), true, 'закрытие работает');

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
