/* b477: боевые статы на карте — выбор МЕСТА, РАСПОЛОЖЕНИЯ и ФОРМЫ чипов.

   Заявка владельца: «значения боевых статов нужно сделать выбор, куда ставить
   на карту: справа, слева, сверху; и вертикально или горизонтально; и фон
   статов — пример: в бриллианте, или в квадратике, или в звёздочке, и так
   далее».

   A. Разметка/CSS/теги: у «Боевые статы на карте» варианты Сверху/Слева/Справа
      плюс «Скрыть»; новые селекты «Расположение статов» (card-stats-dir:
      row/col) и «Форма статов» (card-stats-shape: rect/circle/diamond/star/
      hex/shield); в app.css — чипы .nx-st с фоновым слоем .nx-st-bg и силуэтами
      clip-path; тег сборки единый nxmob221.
   B. Исходники app.js: cardLayoutOf нормирует statsPos (bottom/top/left/right/
      hide), statsDir (row/col), statsShape (6 форм); единый рендерер
      cardStatsHtml; cardTextZones принимает статы шестым аргументом и отдаёт
      left/right отдельным слоем side; все четыре рендера лица вставляют side.
   C. Поведение (jsdom): чипы рисуются выбранной формой и выбранным местом
      (внизу/сверху в потоке, слева/справа абсолютным слоем по центру кромки),
      столбиком или рядом; «Скрыть» по-прежнему глушит статы; вскрытие пака не
      теряет слой статуса; списки (строки альбома, Студия) с эмодзи-статами не
      тронуты; getCardStats и бой не задеты; форма сохраняет и восстанавливает
      все три настройки.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b477.js
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
let __probe = null;
const visibleText = (doc, html) => {
    if (!__probe) __probe = doc.createElement('div');
    __probe.innerHTML = html;
    return __probe.textContent || '';
};

(async () => {
    console.log('A. Разметка формы, CSS форм и теги сборки');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const css = fs.readFileSync(path.join(ROOT, 'assets', 'app.css'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');

        const posSel = (html.match(/<select id="card-stats-pos"[\s\S]*?<\/select>/) || [''])[0];
        ['bottom', 'top', 'left', 'right', 'hide'].forEach(v =>
            ok(new RegExp('<option value="' + v + '">').test(posSel), 'место статов: вариант «' + v + '» в селекторе'));
        const dirSel = (html.match(/<select id="card-stats-dir"[\s\S]*?<\/select>/) || [''])[0];
        ok(/<option value="row">/.test(dirSel) && /<option value="col">/.test(dirSel), 'расположение статов: «По горизонтали» и «Вертикально»');
        ok(/onchange="renderCardPreviewSoon\(\)"/.test(dirSel), 'расположение перерисовывает предпросмотр');
        const shSel = (html.match(/<select id="card-stats-shape"[\s\S]*?<\/select>/) || [''])[0];
        ['rect', 'circle', 'diamond', 'star', 'hex', 'shield'].forEach(v =>
            ok(new RegExp('<option value="' + v + '">').test(shSel), 'форма статов: вариант «' + v + '» в селекторе'));
        ok(/onchange="renderCardPreviewSoon\(\)"/.test(shSel), 'форма перерисовывает предпросмотр');

        ok(css.includes('.nx-st{'), 'app.css: базовый чип .nx-st');
        ok(/\.nx-st-bg\{[^}]*position:absolute/.test(css), 'app.css: фоновый слой .nx-st-bg под текстом');
        ok(/\.nx-st-diamond[^{]*\{[^}]*clip-path:polygon\(50% 0,100% 50%,50% 100%,0 50%\)/.test(css), 'app.css: «бриллиант» — clip-path ромба (кант и подложка)');
        ok(/\.nx-st-star[^{]*\{[^}]*clip-path:polygon\(/.test(css), 'app.css: звёздочка — clip-path звезды');
        ok(/\.nx-st-hex[^{]*\{[^}]*clip-path:polygon\(/.test(css), 'app.css: шестиугольник — clip-path');
        ok(/\.nx-st-shield[^{]*\{[^}]*clip-path:polygon\(/.test(css), 'app.css: щит — clip-path');
        ok(/\.nx-st-circle[^{]*\{[^}]*border-radius:9999px/.test(css), 'app.css: кружок — скругление');
        ok(/\.nx-st-tx\{[^}]*position:relative/.test(css), 'app.css: текст чипа НАД фоном (клип его не режет)');
        ok(/\.nx-st::before\{[^}]*background:currentColor/.test(css), 'app.css: цветной кант силуэта — currentColor стата');
        ok(/\.nx-st-bg\{[^}]*inset:calc\(2px/.test(css), 'app.css: тёмная подложка со сдвигом 2px внутри канта (b478: масштабируется через --k)');

        // b478: номер тега не прибиваем к b477 — проверяем единство: боевой тег из
        // sw.js повторён во всех 8 ссылках index.html и равен BUILD_TAG, не ниже nxmob221
        const tag = (sw.match(/const VERSION = '(nxmob\d+)';/) || [])[1];
        ok(!!tag, 'sw.js: боевой тег на месте (' + tag + ')');
        eq((html.match(new RegExp(tag, 'g')) || []).length, 8, 'index.html: тег из sw.js во всех 8 ссылках на assets');
        ok(bp.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG равен тегу из sw.js');
        ok(Number((tag || '0').replace('nxmob', '')) >= 221, 'тег не ниже nxmob221');
    }

    console.log('\nB. Исходники assets/app.js');
    {
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        const count = re => (app.match(re) || []).length;
        ok(app.includes("const CARD_STATS_SHAPES = ['rect', 'circle', 'diamond', 'star', 'hex', 'shield'];"), 'список форм чипов — 6 силуэтов');
        ok(app.includes("statsDir: L.statsDir === 'col' ? 'col' : 'row'"), 'cardLayoutOf: нормализация statsDir');
        ok(app.includes("statsShape: CARD_STATS_SHAPES.indexOf(L.statsShape) >= 0 ? L.statsShape : 'rect'"), 'cardLayoutOf: нормализация statsShape');
        ok(/statsPos: \(L\.statsPos === 'hide' \|\| L\.statsPos === 'top' \|\| L\.statsPos === 'left' \|\| L\.statsPos === 'right'\)/.test(app), 'cardLayoutOf: statsPos пропускает верх/лево/право/скрыть');
        eq(count(/function cardStatsHtml\(/g), 1, 'cardStatsHtml() объявлена один раз');
        eq(count(/= cardStatsHtml\((card|fake), L\);/g), 3, 'единый рендерер вызывается в трёх рендерах лица');
        ok(app.includes('function cardTextZones(L, badgeHtml, nameHtml, descHtml, extraHtml, statsHtml)'), 'cardTextZones: статы — шестой аргумент');
        eq(count(/\$\{Z\.side\}|\$\{z\.side\}/g), 4, 'боковой слой side вставляется во всех четырёх рендерах лица');
        ok(/const side = \(statsHtml && L\.statsPos !== 'hide' && \(L\.statsPos === 'left' \|\| L\.statsPos === 'right'\)\) \? statsHtml : '';/.test(app), 'side отдаётся только для лево/право и только когда статы не скрыты');
        ok(app.includes("statsDir: g('card-stats-dir'), statsShape: g('card-stats-shape')"), 'readCardLayoutForm читает расположение и форму');
        ok(/statsDirEl\.value = L0\.statsDir;/.test(app) && /statsShapeEl\.value = L0\.statsShape;/.test(app), 'editCard восстанавливает расположение и форму');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;

    console.log('\nC. Нормализация layout');
    eq(ev(`JSON.stringify([cardLayoutOf({}).statsPos, cardLayoutOf({}).statsDir, cardLayoutOf({}).statsShape])`), '["bottom","row","rect"]', 'пустой layout = как до b477');
    eq(ev(`cardLayoutOf({ layout: { statsDir: 'COL' } }).statsDir`), 'row', 'мусор в statsDir → «row»');
    eq(ev(`cardLayoutOf({ layout: { statsShape: 'triangle' } }).statsShape`), 'rect', 'неизвестная форма → «rect»');
    eq(ev(`JSON.stringify([cardLayoutOf({ layout: { statsPos: 'left', statsDir: 'col', statsShape: 'star' } }).statsPos, cardLayoutOf({ layout: { statsPos: 'left', statsDir: 'col', statsShape: 'star' } }).statsDir, cardLayoutOf({ layout: { statsPos: 'left', statsDir: 'col', statsShape: 'star' } }).statsShape])`), '["left","col","star"]', 'left/col/star проходят без изменений');
    eq(ev(`cardLayoutOf({ layout: { statsPos: 'hide' } }).statsPos`), 'hide', '«Скрыть» из b475 не сломано');

    console.log('\nD. cardStatsHtml: место, расположение, форма');
    {
        const mk = layout => ev(`cardStatsHtml({ atk: 7, hp: 9, layout: ${JSON.stringify(layout)} }, cardLayoutOf({ layout: ${JSON.stringify(layout)} }), { txt: 'text-[10px]' })`);
        eq(mk({ statsPos: 'hide' }), '', 'скрытые статы — пустая строка');
        const b = mk({});
        ok(/flex w-full flex-row/.test(b) && /nx-st-rect/.test(b), 'классика: внизу, рядом, квадратик');
        ok(/fa-bolt/.test(b) && /fa-heart/.test(b) && b.includes('>7<') && b.includes('>9<'), 'чипы несут иконки и числа 7/9');
        const col = mk({ statsDir: 'col', align: 'center' });
        ok(/flex-col items-center/.test(col), 'столбик по центру при выравнивании по центру');
        const l = mk({ statsPos: 'left', statsDir: 'col' });
        ok(/absolute z-20 top-1\/2 -translate-y-1\/2 left-1\.5/.test(l) && /flex-col/.test(l), 'слева: абсолютный слой по центру кромки, столбиком');
        const r = mk({ statsPos: 'right' });
        ok(/right-1\.5 items-end/.test(r), 'справа: слой у правой кромки');
        ok(mk({ statsShape: 'diamond' }).includes('nx-st-diamond'), 'форма «ромбик» доезжает до чипов');
        ok(mk({ statsShape: 'star' }).includes('nx-st-star'), 'форма «звёздочка» доезжает до чипов');
        ok(mk({ statsShape: 'shield' }).includes('nx-st-shield'), 'форма «щит» доезжает до чипов');
        ok(/<i class="nx-st-bg"><\/i>/.test(b), 'фон чипа — отдельным слоем под текстом');
        ok(/nx-st nx-st-rect text-amber-300/.test(b), 'цвет стата на самом чипе (им тонируется кант силуэта)');
    }

    console.log('\nE. cardTextZones: статы по местам + статус вскрытия');
    {
        const z = (layout, stats) => ev(`(function(){
            const L = cardLayoutOf({ layout: ${JSON.stringify(layout)} });
            const Z = cardTextZones(L, '<b>BADGE</b>', '<h4>NAMEZONE</h4>', '<p>DESCZONE</p>', '<i>STATUSZONE</i>', ${stats ? "'<s>STATSZONE</s>'" : "''"});
            return JSON.stringify({ top: Z.top, bottom: Z.bottom, side: Z.side });
        })()`);
        const dn = JSON.parse(z({}, true));
        ok(dn.bottom.includes('STATSZONE') && !dn.top.includes('STATSZONE') && dn.side === '', 'по умолчанию статы внизу, side пуст');
        const tp = JSON.parse(z({ statsPos: 'top' }, true));
        ok(tp.top.includes('STATSZONE') && !tp.bottom.includes('STATSZONE'), 'statsPos:"top" — статы в верхней зоне');
        const lf = JSON.parse(z({ statsPos: 'left' }, true));
        ok(lf.side.includes('STATSZONE') && !lf.top.includes('STATSZONE') && !lf.bottom.includes('STATSZONE'), 'statsPos:"left" — статы в боковом слое');
        ok(lf.bottom.includes('STATUSZONE'), 'слой статуса вскрытия остаётся внизу даже при статах слева');
        const no = JSON.parse(z({ statsPos: 'left' }, false));
        ok(no.side === '' && no.bottom.includes('STATUSZONE'), 'без статов (вскрытие пака) side пуст, статус на месте');
        const hd = JSON.parse(z({ statsPos: 'hide' }, true));
        ok(!hd.top.includes('STATSZONE') && !hd.bottom.includes('STATSZONE') && hd.side === '', 'statsPos:"hide" — статов нет нигде');
    }

    console.log('\nF. Рендеры лица карты');
    const ids = JSON.parse(ev(`(function(){
        try { SoundFX.play = function(){}; } catch (e) {}
        try { imgPump = function(){}; imgQueue.length = 0; } catch (e) {}
        state.cards = STANDARD_CARDS.map(c => Object.assign({}, c));
        state.collection = state.collection || {};
        const a = state.cards[0];
        a.name = ${JSON.stringify(NAME)}; a.atk = 7; a.hp = 9; a.description = 'видимое';
        a.layout = Object.assign({}, a.layout, { namePos: 'bottom', descPos: 'bottom', statsPos: 'left', statsDir: 'col', statsShape: 'star' });
        state.collection[a.id] = 1;
        const b = state.cards[1];
        b.name = ${JSON.stringify(NAME)}; b.atk = 7; b.hp = 9; b.description = 'скрытое';
        b.layout = Object.assign({}, b.layout, { statsPos: 'hide', statsShape: 'diamond' });
        state.collection[b.id] = 1;
        return JSON.stringify([a.id, b.id]);
    })()`));
    eq(ids.length, 2, 'подготовлены карты: статы слева-столбиком-звёздочки и скрытые');
    {
        ev(`inspectCard(${JSON.stringify(ids[0])}, ${JSON.stringify(ids)})`);
        const h = doc.getElementById('inspect-card-render').innerHTML;
        ok(h.includes('nx-st-star'), 'просмотр: чипы-звёздочки');
        ok(/absolute z-20 top-1\/2[^>]*left-1\.5/.test(h), 'просмотр: статы слоем у левой кромки');
        ok(/fa-bolt/.test(h) && h.includes('>7<'), 'просмотр: числа на месте');
        ev('closeInspectModal()');
        const grid = ev(`albumCardHTML(state.cards.find(c => c.id === ${JSON.stringify(ids[0])}), { art: 'mid' })`);
        ok(grid.includes('nx-st-star') && grid.includes('left-1.5'), 'сетка альбома: те же звёздочки слева');
        const hid = ev(`albumCardHTML(state.cards.find(c => c.id === ${JSON.stringify(ids[1])}), { art: 'mid' })`);
        ok(!hid.includes('nx-st-') && !hid.includes('fa-bolt'), 'скрытые статы не рисуются ни в одной форме');
    }
    {
        const setForm = (pos, dir, shape) => ev(`(function(){
            document.getElementById('card-name').value = ${JSON.stringify(NAME)};
            document.getElementById('card-atk').value = '7';
            document.getElementById('card-hp').value = '9';
            document.getElementById('card-image').value = 'https://example.com/a.png';
            document.getElementById('card-stats-pos').value = ${JSON.stringify(pos)};
            document.getElementById('card-stats-dir').value = ${JSON.stringify(dir)};
            document.getElementById('card-stats-shape').value = ${JSON.stringify(shape)};
            renderCardPreview();
            return document.getElementById('card-preview').innerHTML;
        })()`);
        const p1 = setForm('right', 'col', 'diamond');
        ok(p1.includes('nx-st-diamond') && p1.includes('right-1.5') && /flex-col/.test(p1), 'предпросмотр: ромбики столбиком у правой кромки');
        const p2 = setForm('top', 'row', 'shield');
        ok(p2.includes('nx-st-shield') && !/absolute z-20 top-1\/2/.test(p2), 'предпросмотр: щиты рядом в верхней зоне');
        const p3 = setForm('hide', 'row', 'rect');
        ok(!p3.includes('nx-st-'), 'предпросмотр: «Скрыть» глушит чипы');
    }
    {
        ev(`(function(){
            document.getElementById('edit-card-id').value = ${JSON.stringify(ids[0])};
            document.getElementById('card-pack-id').value = state.cards.find(c => c.id === ${JSON.stringify(ids[0])}).packId;
            document.getElementById('card-image').value = 'https://example.com/a.png';
            document.getElementById('card-stats-pos').value = 'right';
            document.getElementById('card-stats-dir').value = 'col';
            document.getElementById('card-stats-shape').value = 'hex';
            handleSaveCard(new Event('submit'));
        })()`);
        const card = JSON.parse(ev(`JSON.stringify(state.cards.find(c => c.id === ${JSON.stringify(ids[0])}))`));
        eq(card.layout.statsPos, 'right', 'сохранено: место справа');
        eq(card.layout.statsDir, 'col', 'сохранено: столбиком');
        eq(card.layout.statsShape, 'hex', 'сохранено: шестиугольник');
        ev(`editCard(${JSON.stringify(ids[0])})`);
        eq(doc.getElementById('card-stats-pos').value, 'right', 'editCard: место восстановлено');
        eq(doc.getElementById('card-stats-dir').value, 'col', 'editCard: расположение восстановлено');
        eq(doc.getElementById('card-stats-shape').value, 'hex', 'editCard: форма восстановлена');
    }

    console.log('\nG. Регрессии');
    {
        const st = JSON.parse(ev(`JSON.stringify(getCardStats(state.cards.find(c => c.id === ${JSON.stringify(ids[0])})))`));
        ok(st.atk === 7 && st.hp === 9, 'getCardStats: значения не тронуты (' + st.atk + '/' + st.hp + ')');
        const row = ev(`albumRowHTML(state.cards.find(c => c.id === ${JSON.stringify(ids[0])}))`);
        ok(row.includes('⚔') && row.includes('❤'), '«Строки» альбома: эмодзи-статы как раньше');
        const srow = ev(`studioCardRowHTML(state.cards.find(c => c.id === ${JSON.stringify(ids[0])}), 1, 1)`);
        ok(srow.includes('⚔'), 'список Студии: статы видны владельцу');
        const unbox = ev(`(function(){
            const c = state.cards.find(x => x.id === ${JSON.stringify(ids[0])});
            showUnboxingUI({ id: 'pack-test', title: 'Тест', price: 1 }, [Object.assign({}, c, { unboxedId: 1 })]);
            return document.getElementById('unboxing-cards-container').innerHTML;
        })()`);
        ok(/id="status-0"/.test(unbox), 'вскрытие пака: слой статуса на месте');
        ok(!unbox.includes('nx-st-star'), 'вскрытие пака: статы не рисуются (как до b477)');
        ev(`document.getElementById('modal-unboxing').classList.add('hidden')`);
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
