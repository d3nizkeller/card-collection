/* b487: мобильная красота панели тамагочи.

   Владелец (скриншот с телефона): «на мобильных выглядит некрасиво» — кнопки
   лесенкой (flex-wrap 2+2+1), питомец во всю ширину.

   A. CSS: .tama-actions — сетка 2/3/5 колонок по брейкпоинтам, до 640px
      пятая кнопка тянется на всю строку; в app.js шапка питомца на мобильном
      строкой (морда слева, подпись справа), с lg — столбиком; у полоски опыта
      нет mx-auto; кнопки в ровных ячейках.
   B. Поведение (jsdom): панель содержит tama-actions и 5 кнопок в ней;
      шапка = flex items-center gap-3 shrink-0 lg:block; подпись в min-w-0;
      регрессии: цены действий, частицы и реакции b485 на месте.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b487.js
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
    const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'https://d3nizkeller.github.io/card-collection/' });
    const w = dom.window;
    dom.virtualConsole.on('jsdomError', () => {});
    w.HTMLCanvasElement.prototype.getContext = () => null;
    w.HTMLMediaElement.prototype.play = function () { return Promise.resolve(); };
    w.HTMLMediaElement.prototype.pause = function () {};
    Object.defineProperty(w, 'fetch', { value: () => Promise.resolve({ ok: false, status: 0, text: () => Promise.resolve(''), json: () => Promise.resolve(null) }), configurable: true });
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

(async () => {
    console.log('A. CSS и исходники');
    {
        const css = fs.readFileSync(path.join(ROOT, 'assets', 'app.css'), 'utf8');
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');

        ok(/\.tama-actions\{display:grid;grid-template-columns:repeat\(2,minmax\(0,1fr\)\);gap:8px\}/.test(css), 'кнопки: сетка 2 колонки на мобильном');
        ok(/@media \(min-width:640px\)\{\.tama-actions\{grid-template-columns:repeat\(3,minmax\(0,1fr\)\)\}\}/.test(css), 'от sm — 3 колонки');
        ok(/@media \(min-width:1024px\)\{\.tama-actions\{grid-template-columns:repeat\(5,minmax\(0,1fr\)\)\}\}/.test(css), 'от lg — 5 колонок в одну строку');
        ok(/@media \(max-width:639px\)\{\.tama-actions > :last-child\{grid-column:1\/-1\}\}/.test(css), 'пятая кнопка на мобильном тянется на всю строку');
        ok(app.includes('<div class="flex items-center gap-3 shrink-0 lg:block">'), 'шапка питомца: строкой на мобильном, столбиком от lg');
        ok(app.includes('<div class="min-w-0"><!-- b487: подпись сбоку от морды на мобильном -->'), 'подпись обёрнута в min-w-0');
        ok(!/h-2 w-32 mx-auto lg:mx-0 rounded-full/.test(app), 'у полоски опыта нет mx-auto (в строке он не нужен)');
        ok(app.includes('<div class="tama-actions pt-1">${btns}</div>'), 'контейнер кнопок — tama-actions, не flex-wrap');
        ok(!app.includes('flex flex-wrap gap-2 pt-1'), 'лесенки flex-wrap у кнопок не осталось');

        const tag = (sw.match(/const VERSION = '(nxmob\d+)';/) || [])[1];
        // b488: номер тега не прибиваем к b487 — единство и не ниже nxmob231
        eq((html.match(new RegExp(tag, 'g')) || []).length, 8, 'index.html: тег из sw.js во всех 8 ссылках на assets');
        ok(bp.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG равен тегу из sw.js');
        ok(Number((tag || '0').replace('nxmob', '')) >= 231, 'тег не ниже nxmob231 (' + tag + ')');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;

    console.log('\nB. Панель в живом DOM');
    ev(`state.coins = 2000; state.cards = STANDARD_CARDS.map(c => Object.assign({}, c)); state.collection = state.collection || {}; state.cards.slice(0, 6).forEach(c => state.collection[c.id] = 1); tamaAdopt();`);
    {
        const acts = doc.querySelector('#tama-panel .tama-actions');
        ok(!!acts, 'контейнер кнопок .tama-actions в панели');
        eq(acts ? acts.children.length : 0, 5, 'в сетке пять кнопок действий');
        ok(acts && Array.from(acts.children).every(b => b.className.includes('tama-btn')), 'все кнопки с tama-btn (hover/active)');
        const head = doc.querySelector('#tama-panel .flex.items-center.gap-3.shrink-0');
        ok(!!head, 'шапка питомца — строка на мобильном');
        ok(head && head.querySelector('.tama-stage') && head.querySelector('.min-w-0'), 'в шапке: сцена слева, подпись справа');
        ok(head && head.className.includes('lg:block'), 'с lg шапка возвращается в столбик');
        const xp = doc.querySelector('#tama-panel .tama-xp-fill');
        ok(xp && !xp.className.includes('mx-auto'), 'полоска опыта без центрирующих марджинов');
    }

    console.log('\nC. Регрессии b483/b485');
    {
        const c0 = ev('state.coins');
        ev(`tamaAct('feed')`);
        eq(c0 - ev('state.coins'), 15, 'корм стоит 15 монет');
        ok(doc.getElementById('tama-pet').className.includes('tama-act-feed'), 'реакция морды на корм на месте');
        ok(doc.getElementById('tama-fx').children.length >= 7, 'частицы сыплются');
        ok(doc.getElementById('tama-panel').innerHTML.includes('tama-bar-fill'), 'полоски с бликом на месте');
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
