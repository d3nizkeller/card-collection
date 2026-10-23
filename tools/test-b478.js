/* b478: размер чипов боевых статов — мелкий (как раньше), средний и крупный.

   Заявка владельца к b477: «а размер сейчас маленький, нужно сделать средний
   и большой».

   A. Разметка/CSS/теги: селект «Размер статов» (card-stats-size: sm/md/lg) в
      форме Студии рядом с местом/расположением/формой; в app.css масштаб идёт
      одним коэффициентом --k на обёртке .nx-st-wrap (паддинги чипов, кант,
      подложка, зазор и кегль текста — через calc), все шесть форм b477
      масштабируются одинаково; тег сборки единый nxmob222.
   B. Исходники app.js: cardLayoutOf нормирует statsSize; cardStatsHtml без
      третьего аргумента (кегль больше не задаёт рендер), обёртка получает
      nx-st-md/nx-st-lg; readCardLayoutForm и editCard работают с размером.
   C. Поведение (jsdom): md/lg добавляют свои классы обёртке в просмотре,
      сетке альбома и предпросмотре; sm = прежний вид; формы/места/скрытие из
      b475–b477 не сломаны; сохранение и восстановление размера в форме.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b478.js
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
    dom.virtualConsole.on('jsdomError', () => {});
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

const NAME = 'ТЕСТОВОЕ_ИМЯ_XYZ';

(async () => {
    console.log('A. Разметка формы, CSS-масштаб и теги сборки');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const css = fs.readFileSync(path.join(ROOT, 'assets', 'app.css'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');

        const sel = (html.match(/<select id="card-stats-size"[\s\S]*?<\/select>/) || [''])[0];
        ok(sel.length > 0, 'селект «Размер статов» (card-stats-size) в форме Студии');
        ok(/<option value="sm">/.test(sel) && /<option value="md">/.test(sel) && /<option value="lg">/.test(sel), 'три размера: мелкий / средний / крупный');
        ok(/onchange="renderCardPreviewSoon\(\)"/.test(sel), 'размер перерисовывает предпросмотр');

        ok(/\.nx-st-wrap\{--k:1;/.test(css), 'app.css: обёртка .nx-st-wrap задаёт коэффициент --k');
        ok(/\.nx-st-wrap\.nx-st-md\{--k:1\.3\}/.test(css), 'app.css: средний размер — --k 1.3');
        ok(/\.nx-st-wrap\.nx-st-lg\{--k:1\.65\}/.test(css), 'app.css: крупный размер — --k 1.65');
        ok(/\.nx-st\{[^}]*padding:calc\(3px \* var\(--k\)\)/.test(css), 'app.css: паддинги чипа растут с --k');
        ok(/\.nx-st-tx\{[^}]*font-size:calc\(10px \* var\(--k\)\)/.test(css), 'app.css: кегль текста растёт с --k');
        ok(/\.nx-st-diamond\{padding:calc\(8px \* var\(--k\)\)/.test(css), 'app.css: паддинги форм (ромб) тоже растут с --k');
        ok(/\.nx-st-star\{padding:calc\(9px \* var\(--k\)\)/.test(css), 'app.css: паддинги форм (звезда) тоже растут с --k');

        eq((html.match(/nxmob222/g) || []).length, 8, 'index.html: тег nxmob222 во всех 8 ссылках на assets');
        ok(!html.includes('nxmob221'), 'index.html: старого тега nxmob221 не осталось');
        ok(sw.includes("const VERSION = 'nxmob222';"), 'sw.js: VERSION = nxmob222');
        ok(bp.includes("BUILD_TAG = 'nxmob222'"), 'tools/build.py: BUILD_TAG = nxmob222');
    }

    console.log('\nB. Исходники assets/app.js');
    {
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        ok(app.includes("statsSize: (L.statsSize === 'md' || L.statsSize === 'lg') ? L.statsSize : 'sm'"), 'cardLayoutOf: нормализация statsSize');
        ok(app.includes('function cardStatsHtml(card, L) {'), 'cardStatsHtml: без третьего аргумента (кегль не задаёт рендер)');
        ok(app.includes("const sz = L.statsSize === 'lg' ? ' nx-st-lg' : (L.statsSize === 'md' ? ' nx-st-md' : '');"), 'классы размера nx-st-md/nx-st-lg на обёртке');
        eq((app.match(/nx-st-wrap\$\{sz\}/g) || []).length, 2, 'обёртка nx-st-wrap в обоих вариантах контейнера (зоны и кромка)');
        ok(app.includes("statsSize: g('card-stats-size')"), 'readCardLayoutForm читает размер');
        ok(/statsSizeEl\.value = L0\.statsSize;/.test(app), 'editCard восстанавливает размер');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;

    console.log('\nC. Нормализация и чипы');
    eq(ev(`cardLayoutOf({}).statsSize`), 'sm', 'пустой layout → мелкий (как раньше)');
    eq(ev(`cardLayoutOf({ layout: { statsSize: 'XL' } }).statsSize`), 'sm', 'мусор в statsSize → мелкий');
    eq(ev(`cardLayoutOf({ layout: { statsSize: 'lg' } }).statsSize`), 'lg', 'крупный проходит');
    {
        const mk = layout => ev(`cardStatsHtml({ atk: 7, hp: 9, layout: ${JSON.stringify(layout)} }, cardLayoutOf({ layout: ${JSON.stringify(layout)} }))`);
        ok(!mk({}).includes('nx-st-md') && !mk({}).includes('nx-st-lg'), 'мелкий: без классов размера (прежний вид)');
        ok(mk({ statsSize: 'md' }).includes('nx-st-wrap nx-st-md'), 'средний: обёртка nx-st-md');
        ok(mk({ statsSize: 'lg' }).includes('nx-st-wrap nx-st-lg'), 'крупный: обёртка nx-st-lg');
        ok(mk({ statsSize: 'lg', statsPos: 'left' }).includes('nx-st-wrap nx-st-lg absolute z-20'), 'крупный работает и на кромке (слева)');
        ok(mk({ statsSize: 'md', statsShape: 'diamond' }).includes('nx-st nx-st-diamond'), 'размер сочетается с формой «ромбик»');
        eq(mk({ statsSize: 'lg', statsPos: 'hide' }), '', 'скрытие статов важнее размера');
    }

    console.log('\nD. Рендеры лица и форма');
    const id = JSON.parse(ev(`(function(){
        try { SoundFX.play = function(){}; } catch (e) {}
        try { imgPump = function(){}; imgQueue.length = 0; } catch (e) {}
        state.cards = STANDARD_CARDS.map(c => Object.assign({}, c));
        state.collection = state.collection || {};
        const a = state.cards[0];
        a.name = ${JSON.stringify(NAME)}; a.atk = 7; a.hp = 9;
        a.layout = Object.assign({}, a.layout, { statsPos: 'bottom', statsDir: 'row', statsShape: 'diamond', statsSize: 'lg' });
        state.collection[a.id] = 1;
        return JSON.stringify(a.id);
    })()`));
    {
        ev(`inspectCard(${JSON.stringify(id)}, [${JSON.stringify(id)}])`);
        const h = doc.getElementById('inspect-card-render').innerHTML;
        ok(h.includes('nx-st-wrap nx-st-lg'), 'просмотр карты: крупный размер применён');
        ok(h.includes('nx-st-diamond'), 'просмотр карты: форма «ромбик» не потерялась');
        ev('closeInspectModal()');
        const grid = ev(`albumCardHTML(state.cards.find(c => c.id === ${JSON.stringify(id)}), { art: 'mid' })`);
        ok(grid.includes('nx-st-wrap nx-st-lg'), 'сетка альбома: крупный размер применён');
    }
    {
        const setForm = size => ev(`(function(){
            document.getElementById('card-name').value = ${JSON.stringify(NAME)};
            document.getElementById('card-atk').value = '7';
            document.getElementById('card-hp').value = '9';
            document.getElementById('card-image').value = 'https://example.com/a.png';
            document.getElementById('card-stats-size').value = ${JSON.stringify(size)};
            renderCardPreview();
            return document.getElementById('card-preview').innerHTML;
        })()`);
        ok(!setForm('sm').includes('nx-st-md') && !setForm('sm').includes('nx-st-lg'), 'предпросмотр: мелкий без классов размера');
        ok(setForm('md').includes('nx-st-md'), 'предпросмотр: средний применяется сразу');
        ok(setForm('lg').includes('nx-st-lg'), 'предпросмотр: крупный применяется сразу');
        ev(`(function(){
            document.getElementById('edit-card-id').value = ${JSON.stringify(id)};
            document.getElementById('card-pack-id').value = state.cards.find(c => c.id === ${JSON.stringify(id)}).packId;
            document.getElementById('card-image').value = 'https://example.com/a.png';
            document.getElementById('card-stats-size').value = 'md';
            handleSaveCard(new Event('submit'));
        })()`);
        const card = JSON.parse(ev(`JSON.stringify(state.cards.find(c => c.id === ${JSON.stringify(id)}))`));
        eq(card.layout.statsSize, 'md', 'handleSaveCard: размер сохранён в layout');
        ev(`editCard(${JSON.stringify(id)})`);
        eq(doc.getElementById('card-stats-size').value, 'md', 'editCard: размер восстановлен в форме');
    }

    console.log('\nE. Регрессии b475–b477');
    {
        eq(ev(`cardLayoutOf({ layout: { statsPos: 'hide' } }).statsPos`), 'hide', 'скрытие статов работает');
        eq(ev(`cardLayoutOf({ layout: { namePos: 'hide' } }).namePos`), 'hide', 'скрытие имени работает');
        eq(ev(`cardLayoutOf({ layout: { statsShape: 'star' } }).statsShape`), 'star', 'формы b477 работают');
        const st = JSON.parse(ev(`JSON.stringify(getCardStats(state.cards.find(c => c.id === ${JSON.stringify(id)})))`));
        ok(st.atk === 7 && st.hp === 9, 'getCardStats: значения не тронуты (' + st.atk + '/' + st.hp + ')');
        const row = ev(`albumRowHTML(state.cards.find(c => c.id === ${JSON.stringify(id)}))`);
        ok(row.includes('⚔') && row.includes('❤'), '«Строки» альбома: эмодзи-статы как раньше');
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
