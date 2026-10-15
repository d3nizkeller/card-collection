/* b441: раскрытое описание пролистывается верх-вниз само (панель под картой).

   Заявка владельца: «Сделай открытие описание можно пролистывать верх вниз,
   чтоб читать длинное описание карточки».
   В b440 полный текст переехал в панель #inspect-desc-full, но панель росла
   на всю длину текста и скроллилась вся модалка. Теперь текст панели
   ограничен ~32vh и крутится внутри: палец/колесо, инерция iOS, цепочка
   скролла не уходит в модалку, фейд-подсказка «низу ещё текст».

   A. CSS/разметка: max-height:32vh + overflow-y:auto + pan-y + contain,
      инерция, тонкий скроллбар, фейд ::after и его погасание (nx-desc-end),
      tabindex/role для клавиатуры.
   B. Исходники app.js: nxDescScrollHint, сброс scrollTop в nxDescPanelSync,
      слушатели scroll/resize, гард b440 (свайп по панели не листает).
   C. Поведение (jsdom): открытие длинного описания → панель с ВЕСЬ текстом;
      класс nx-desc-scrollable когда текст не помещается; nx-desc-end при
      докрутке до конца и его снятие при открутке назад; скролл-событие
      панели пересчитывает подсказку; при свайпе карты scrollTop сбрасывается;
      короткое описание/«Свернуть» — панель скрыта и классы сняты; resize не
      роняет подсказку.
   D. Регрессии b439/b440: свайп по панели не листает карты, свайп по карте
      листает, чужой HTML экранируется (textContent), модалка закрывается.
   E. Теги сборки едины (боевой тег из sw.js, ≥ nxmob163), nxmob24 не тронут.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b441.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + (typeof a === 'string' && a.length > 60 ? a.slice(0, 60) + '…(' + a.length + ')' : a) + (a === b ? '' : ' (ждём ' + (typeof b === 'string' && b.length > 60 ? b.slice(0, 60) + '…(' + b.length + ')' : b) + ')'));

function boot() {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const dom = new JSDOM(html, {
        runScripts: 'dangerously',
        pretendToBeVisual: true,
        url: 'https://d3nizkeller.github.io/card-collection/',
    });
    const w = dom.window;
    const vc = dom.virtualConsole;
    vc.on('jsdomError', () => {}); // scrollIntoView/navigation в jsdom не реализованы
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

const LONG = 'Древний хранитель башни, знающий все тайны коллекционеров карт и их судьбы. '.repeat(4); // ~300 симв.
const VERYLONG = 'Легенда о карте, которую искали поколения коллекционеров: '.repeat(34); // ~2000 симв.
const SHORT = 'Короткое описание карты.';
const EVIL = '<img src=x onerror="window.__pwned=1"> & <b>жирный</b> "кавычки" \'апостроф\'';

(async () => {
    console.log('A. CSS/разметка панели (index.html)');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        ok(/#inspect-desc-full-text\{[^}]*max-height:32vh;\s*overflow-y:auto;/.test(html), 'текст панели: max-height:32vh + overflow-y:auto');
        ok(/#inspect-desc-full-text\{[^}]*-webkit-overflow-scrolling:touch;/.test(html), 'инерционный скролл iOS (-webkit-overflow-scrolling:touch)');
        ok(/#inspect-desc-full-text\{[^}]*overscroll-behavior:contain;\s*touch-action:pan-y;/.test(html), 'цепочка скролла заперта в панели (contain), жест вертикальный (pan-y)');
        ok(html.includes('#inspect-desc-full-text::-webkit-scrollbar{ width:6px; }'), 'тонкий скроллбар webkit (6px)');
        ok(html.includes('scrollbar-width:thin; scrollbar-color:#475569 transparent;'), 'тонкий скроллбар Firefox');
        ok(html.includes('#inspect-desc-full{ position:relative; }'), 'панель — контекст позиционирования для фейда');
        ok(/#inspect-desc-full\.nx-desc-scrollable::after\{[^}]*pointer-events:none/.test(html), 'фейд «низу ещё текст» ::after не перехватывает клики');
        ok(/#inspect-desc-full\.nx-desc-scrollable::after\{[^}]*linear-gradient/.test(html), 'фейд — градиент к фону панели');
        ok(html.includes('#inspect-desc-full.nx-desc-scrollable.nx-desc-end::after{ opacity:0; }'), 'на конце текста фейд гаснет (nx-desc-end)');
        ok(/<div id="inspect-desc-full-text" tabindex="0" role="region"/.test(html), 'текст панели доступен с клавиатуры (tabindex=0, role=region)');
        ok(html.includes('#inspect-desc-full-text:focus-visible{'), ':focus-visible — видимый, но ненавязчивый аутлайн');
    }

    console.log('\nB. Исходники app.js');
    {
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        ok(app.includes('function nxDescScrollHint('), 'функция nxDescScrollHint() на месте');
        ok(/nxDescPanelSync\(scrollTo\) \{[\s\S]{0,900}?t\.scrollTop = 0;/.test(app), 'nxDescPanelSync сбрасывает scrollTop текста');
        ok(/nxDescPanelSync\(scrollTo\) \{[\s\S]{0,900}?nxDescScrollHint\(\);/.test(app), 'nxDescPanelSync пересчитывает подсказку');
        ok(/scrollHeight > t\.clientHeight \+ 4/.test(app), 'прокручиваемость определяется по scrollHeight > clientHeight');
        ok(/'nx-desc-end', scrollable && \(t\.scrollTop \+ t\.clientHeight >= t\.scrollHeight - 4\)/.test(app), 'nx-desc-end — только когда докрутили до конца');
        ok(/nxDescTxt\.addEventListener\('scroll'/.test(app), 'слушатель scroll на тексте панели');
        ok(/window\.addEventListener\('resize', \(\) => \{ try \{ nxDescScrollHint\(\); \}/.test(app), 'слушатель resize пересчитывает подсказку');
        ok(app.includes("e.target.closest('#inspect-desc-full')"), 'гард b440: свайп по панели не листает карты');
        ok(/if \(p\.classList\.contains\('hidden'\)\) \{\s*p\.classList\.remove\('nx-desc-scrollable', 'nx-desc-end'\);/.test(app), 'скрытая панель теряет классы подсказки');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;

    const ids = JSON.parse(ev(`(function(){
        try { SoundFX.play = function(){}; } catch (e) {}
        window.__oldPump = imgPump; imgPump = function(){}; imgQueue.length = 0;
        state.cards = STANDARD_CARDS.map(c => Object.assign({}, c));
        state.collection = state.collection || {};
        state.cards[0].description = ${JSON.stringify(LONG)};
        state.cards[1].description = ${JSON.stringify(VERYLONG)};
        state.cards[2].description = ${JSON.stringify(SHORT)};
        state.cards[3].description = ${JSON.stringify(EVIL + ' ' + LONG)};
        state.cards.slice(0, 4).forEach(c => { state.collection[c.id] = 1; });
        return JSON.stringify(state.cards.slice(0, 4).map(c => c.id));
    })()`));
    eq(ids.length, 4, 'подготовлено 4 тестовых карты');
    const insp = (i) => ev(`inspectCard(${JSON.stringify(ids[i])}, ${JSON.stringify(ids)})`);
    const panel = () => doc.getElementById('inspect-desc-full');
    const panelTxt = () => doc.getElementById('inspect-desc-full-text');
    const shown = () => !!panel() && !panel().classList.contains('hidden');
    const clickBtn = () => doc.querySelector('#inspect-card-render .nx-desc-btn')
        .dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    const swipe = (from, to, target) => ev(`(function(){
        const t = new Event('touchstart', { bubbles: true }); t.touches = [{ clientX: ${from} }];
        document.getElementById(${JSON.stringify(target)}).dispatchEvent(t);
        const e2 = new Event('touchend', { bubbles: true }); e2.changedTouches = [{ clientX: ${to} }];
        document.dispatchEvent(e2);
    })()`);
    const scrollEv = () => panelTxt().dispatchEvent(new w.Event('scroll'));
    const cls = (c) => panel().classList.contains(c);

    // jsdom не считает раскладку: изображаем «текст 900px в окне 200px»
    let fakeScrollTop = 0;
    Object.defineProperty(panelTxt(), 'scrollHeight', { value: 900, configurable: true });
    Object.defineProperty(panelTxt(), 'clientHeight', { value: 200, configurable: true });
    Object.defineProperty(panelTxt(), 'scrollTop', {
        get: () => fakeScrollTop, set: v => { fakeScrollTop = v | 0; }, configurable: true,
    });

    console.log('\nC. Поведение: панель пролистывается верх-вниз');
    insp(0);
    ok(!shown(), 'до раскрытия панель скрыта');
    clickBtn();
    ok(shown(), '«Показать полностью» — панель видна');
    eq(panelTxt().textContent, LONG, 'в панели весь текст длинного описания');
    ok(cls('nx-desc-scrollable'), 'текст не помещается (900>200) — панель помечена прокручиваемой (фейд включён)');
    ok(!cls('nx-desc-end'), 'мы наверху — nx-desc-end нет (фейд виден)');
    eq(fakeScrollTop, 0, 'открытие — текст с первой строки (scrollTop=0)');

    fakeScrollTop = 350; scrollEv();
    ok(!cls('nx-desc-end'), 'середина текста (350+200<896) — до конца ещё далеко');
    fakeScrollTop = 700; scrollEv();
    ok(cls('nx-desc-end'), 'докрутили до конца (700+200>=896) — фейд погас (nx-desc-end)');
    fakeScrollTop = 120; scrollEv();
    ok(!cls('nx-desc-end'), 'открутили назад — фейд снова виден');
    ok(cls('nx-desc-scrollable'), 'панель по-прежнему прокручиваемая');

    console.log('\nC2. Листание карт при раскрытом описании');
    fakeScrollTop = 350;
    const idx0 = ev('inspectIdx');
    swipe(320, 60, 'inspect-card-render');
    eq(ev('inspectIdx'), idx0 + 1, 'свайп по карте перелистнул');
    eq(panelTxt().textContent, VERYLONG, 'панель показывает текст новой карты целиком (~2000 симв.)');
    eq(fakeScrollTop, 0, 'b441: после свайпа scrollTop сброшен — лор новой карты с первой строки');
    ok(cls('nx-desc-scrollable') && !cls('nx-desc-end'), 'подсказка пересчитана: прокручиваема, мы наверху');

    swipe(320, 60, 'inspect-card-render');
    eq(panelTxt().textContent, '', 'короткое описание — панель пуста');
    ok(!shown(), 'короткое описание — панель скрыта');
    ok(!cls('nx-desc-scrollable') && !cls('nx-desc-end'), 'скрытая панель потеряла классы подсказки');

    fakeScrollTop = 500;
    swipe(60, 320, 'inspect-card-render');
    eq(ev('inspectIdx'), idx0 + 1, 'свайп назад вернулся к предыдущей карте (очень длинный лор)');
    ok(shown() && panelTxt().textContent === VERYLONG, 'выбор «раскрыто» помнится (b439), текст снова в панели');
    eq(fakeScrollTop, 0, 'и снова с первой строки (scrollTop сброшен при свайпе назад)');

    console.log('\nC3. «Свернуть» и resize');
    clickBtn();
    ok(!shown(), '«Свернуть» — панель скрыта');
    eq(panelTxt().textContent, '', 'текст панели очищен');
    ok(!cls('nx-desc-scrollable') && !cls('nx-desc-end'), 'классы подсказки сняты');
    clickBtn();
    ok(shown() && cls('nx-desc-scrollable'), 'повторное раскрытие — панель и подсказка вернулись');
    ev(`window.dispatchEvent(new Event('resize'))`);
    ok(cls('nx-desc-scrollable'), 'resize пересчитал подсказку без ошибок');
    ev('closeInspectModal()');
    ok(!shown(), 'закрытие модалки прячет панель (b440)');

    console.log('\nD. Регрессии: свайпы и экранирование');
    insp(0); clickBtn();
    {
        const before = ev('inspectIdx');
        swipe(320, 60, 'inspect-desc-full-text');
        eq(ev('inspectIdx'), before, 'свайп по тексту панели карту не переключил (это скролл)');
        swipe(320, 60, 'inspect-card-render');
        eq(ev('inspectIdx'), before + 1, 'свайп по карте по-прежнему листает');
    }
    ev('closeInspectModal()');
    insp(3);
    clickBtn();
    ok(shown(), 'карта с HTML в описании — панель открыта');
    eq(panelTxt().querySelectorAll('img,b').length, 0, 'чужие элементы не созданы (текст через textContent)');
    eq(panelTxt().textContent, EVIL + ' ' + LONG, 'спецсимволы показаны как есть');
    eq(ev('window.__pwned === true'), false, 'инъекция onerror не сработала');

    console.log('\nE. Теги сборки едины (боевой тег берём из sw.js)');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bld = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');
        const tagM = sw.match(/const VERSION = '(nxmob\d+)';/);
        ok(!!tagM, 'sw.js: боевой тег VERSION парсится');
        const TAG = tagM ? tagM[1] : 'nxmob0';
        ok(TAG >= 'nxmob163', 'боевой тег не старше nxmob163 (сборка b441)  → ' + TAG);
        const vTags = html.match(/\?v=nxmob\d+/g) || [];
        eq(vTags.filter(s => s === '?v=' + TAG).length, 8, 'index.html: ?v=' + TAG + ' × 8');
        ok(!vTags.some(s => s !== '?v=' + TAG), 'index.html: чужих/устаревших тегов в ?v= нет');
        ok(bld.includes("BUILD_TAG = '" + TAG + "'"), 'build.py: BUILD_TAG ' + TAG);
        ok(/nxmob24/.test(html.split('\n')[23]), 'index.html: исторический комментарий nxmob24 не тронут');
        ok(/nxmob24/.test(sw.split('\n')[0]), 'sw.js: исторический комментарий nxmob24 не тронут');
    }

    console.log('\n' + (fails ? 'ПРОВАЛ: ' + fails + ' из ' : 'OK: ') + checks + (fails ? ' (' + fails + ' ❌)' : ' ✅'));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('CRASH', e); process.exit(2); });
