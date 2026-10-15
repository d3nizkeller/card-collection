/* b440: раскрытое описание в просмотре карты показывается ЦЕЛИКОМ.

   Заявка владельца: «при раскрытом опесани должен быть виден весь текст».
   Лицо карты (#inspect-card-render) имеет aspect-ratio 9/16 + overflow:hidden
   и как flex-потомок с невидимым overflow не растёт по содержимому — раскрытый
   текст обрезался краем карты. Теперь полный текст живёт в панели
   #inspect-desc-full под картой.

   A. Свёрнуто: панель скрыта и пуста, текст описания на карте на месте.
   B. Клик «Показать полностью»: панель видна, в ней ВЕСЬ текст (символ в символ,
      без обрезки/многоточия), кнопка «Свернуть», aria-expanded=true.
   C. Очень длинное описание (2000 симв.) — тоже целиком, без ограничения длины.
   D. «Свернуть»: панель снова скрыта и очищена.
   E. Листание карт (inspectStep) при раскрытом описании: панель показывает
      текст новой карты; на карте с коротким описанием панель прячется.
   F. closeInspectModal прячет и чистит панель; новое открытие — свёрнуто.
   G. Разметка/CSS: панель под картой, .nx-desc-open прячет текст на карте,
      модалка центрируется auto-полями (высокий контент прокручивается сначала),
      мобильная ширина панели = ширине карты.
   H. Свайп по панели не листает карты, свайп по карте — листает.
   I. Экранирование: HTML в чужом описании не становится разметкой.
   J. Теги сборки едины (боевой тег из sw.js), исторический nxmob24 не тронут.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b440.js
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
        state.cards[3].description = ${JSON.stringify(EVIL)};
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

    console.log('\nA. Свёрнуто: панель скрыта, текст на карте');
    insp(0);
    ok(!!panel(), 'панель #inspect-desc-full есть в разметке');
    ok(!!panelTxt(), 'контейнер текста #inspect-desc-full-text есть');
    ok(!shown(), 'по умолчанию панель скрыта (hidden)');
    eq(panelTxt().textContent, '', 'по умолчанию панель пуста');
    const follows = doc.getElementById('inspect-card-render').compareDocumentPosition(panel()) & w.Node.DOCUMENT_POSITION_FOLLOWING;
    ok(!!follows, 'панель стоит ПОСЛЕ лица карты (вне его overflow:hidden)');
    ok(!doc.getElementById('inspect-card-render').contains(panel()), 'панель НЕ внутри лица карты (не обрежется)');
    {
        const t = doc.querySelector('#inspect-card-render .nx-desc-text');
        ok(!!t, 'текст описания на карте на месте');
        eq(t && t.textContent, LONG, 'на карте — полный текст (обрезку делает CSS)');
        ok(!doc.querySelector('#inspect-card-render .nx-desc-wrap').classList.contains('nx-desc-open'), 'свёрнуто (нет nx-desc-open)');
    }

    console.log('\nB. Клик «Показать полностью» — виден ВЕСЬ текст');
    clickBtn();
    ok(shown(), 'панель раскрыта (hidden снят)');
    eq(panelTxt().textContent, LONG, 'в панели — весь текст описания, символ в символ');
    eq(panelTxt().textContent.length, LONG.length, 'длина текста не урезана');
    ok(!/…|\.\.\.$/.test(panelTxt().textContent), 'никаких многоточий/обрезки');
    ok(panelTxt().textContent.startsWith(LONG.slice(0, 40)), 'начало текста на месте');
    ok(panelTxt().textContent.endsWith(LONG.slice(-40)), 'конец текста на месте');
    ok(doc.querySelector('#inspect-card-render .nx-desc-wrap').classList.contains('nx-desc-open'), 'обёртка на карте получила nx-desc-open');
    ok(/Свернуть/.test(doc.querySelector('#inspect-card-render .nx-desc-btn').textContent), 'кнопка стала «Свернуть»');
    eq(doc.querySelector('#inspect-card-render .nx-desc-btn').getAttribute('aria-expanded'), 'true', 'aria-expanded=true');
    eq(ev('nxDescOpen'), true, 'флаг nxDescOpen=true');
    ok(!!doc.querySelector('#inspect-card-render .nx-desc-text'), 'текст на карте остался в DOM (прячет CSS, не JS)');
    ok(/Описание целиком/.test(panel().textContent), 'у панели есть заголовок «Описание целиком»');

    console.log('\nC. Очень длинное описание (2000 симв.) — тоже целиком');
    insp(1);
    ok(shown(), 'раскрытие помнится при переходе на другую карту');
    eq(panelTxt().textContent.length, VERYLONG.length, '2000 символов дошли до панели полностью');
    eq(panelTxt().textContent, VERYLONG, 'текст совпадает с описанием карты');

    console.log('\nD. «Свернуть» — панель скрыта и очищена');
    clickBtn();
    ok(!shown(), 'после сворачивания панель скрыта');
    eq(panelTxt().textContent, '', 'текст из панели вычищен');
    eq(ev('nxDescOpen'), false, 'nxDescOpen=false');
    ok(/Показать полностью/.test(doc.querySelector('#inspect-card-render .nx-desc-btn').textContent), 'кнопка снова «Показать полностью»');

    console.log('\nE. Листание карт: панель за текущей картой, короткое описание — без панели');
    insp(0);
    clickBtn();
    ev('inspectStep(1)');
    eq(ev('inspectIdx'), 1, 'inspectStep сдвинул индекс');
    eq(panelTxt().textContent, VERYLONG, 'панель показала текст НОВОЙ карты');
    ok(shown(), 'панель осталась открытой');
    ev('inspectStep(1)'); // карта 2 — короткое описание
    ok(!shown(), 'на карте с коротким описанием панель скрыта');
    eq(panelTxt().textContent, '', 'панель очищена (нет текста прошлой карты)');
    eq(doc.querySelector('#inspect-card-render .nx-desc-btn'), null, 'у короткого описания кнопки нет');
    ev('inspectStep(1)'); // карта 3 — зловредное описание (короткое)
    ok(!shown(), 'короткое «зловредное» описание панель не открывает');
    ev('inspectStep(-1)'); ev('inspectStep(-1)'); // обратно на карту 1 (VERYLONG)
    eq(ev('inspectIdx'), 1, 'вернулись на карту с длинным описанием');
    ok(shown(), 'панель снова показывает длинное описание');
    eq(panelTxt().textContent, VERYLONG, 'и показывает его целиком');

    console.log('\nF. Закрытие модалки прячет панель');
    ev('closeInspectModal()');
    ok(!shown(), 'closeInspectModal: панель скрыта');
    eq(panelTxt().textContent, '', 'closeInspectModal: панель очищена');
    eq(ev('nxDescOpen'), false, 'closeInspectModal: nxDescOpen сброшен');
    ok(doc.getElementById('modal-inspect').classList.contains('hidden'), 'модалка закрыта');
    insp(0);
    ok(!shown(), 'новое открытие — описание свёрнуто, панель скрыта');
    ok(/Показать полностью/.test(doc.querySelector('#inspect-card-render .nx-desc-btn').textContent), 'кнопка «Показать полностью»');

    console.log('\nG. Разметка и CSS в index.html');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        ok(html.includes('id="inspect-desc-full"'), 'панель #inspect-desc-full в разметке');
        ok(html.includes('id="inspect-desc-full-text"'), 'контейнер текста панели в разметке');
        ok(html.includes('.nx-desc-wrap.nx-desc-open .nx-desc-text{ display:none; }'), 'CSS: в раскрытом виде текст на карте скрыт');
        ok(html.includes('#modal-inspect{ justify-content:flex-start; }'), 'CSS: модалка больше не центрирует через justify-center');
        ok(html.includes('#modal-inspect > div{ margin-top:auto; margin-bottom:auto; }'), 'CSS: центрирование auto-полями (контент выше экрана прокручивается с начала)');
        ok(html.includes('#inspect-desc-full-text{ white-space:pre-wrap'), 'CSS: переносы строк описания сохраняются');
        ok(/#inspect-desc-full\{ max-width: min\(24rem, calc\(58vh \* 0\.5625\)\); \}/.test(html), 'CSS: на телефоне панель по ширине карты');
        ok(html.includes('.nx-desc-wrap .nx-desc-text{ display:-webkit-box'), 'CSS: кламп свёрнутого состояния (b439) на месте');
        ok(html.includes('-webkit-line-clamp:3'), 'CSS: свёрнуто до 3 строк (b439)');
        const iPanel = html.indexOf('id="inspect-desc-full"'), iCounter = html.indexOf('id="inspect-counter"');
        ok(iPanel > 0 && iCounter > 0 && iPanel < iCounter, 'панель стоит между картой и счётчиком листания');
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        ok(app.includes('function nxDescPanelSync('), 'хелпер nxDescPanelSync на месте');
        ok(app.includes('nxDescPanelSync(false); // b440'), 'inspectCard синхронизирует панель');
        ok(app.includes('try { nxDescPanelSync(false); } catch (e) {} // b440'), 'closeInspectModal синхронизирует панель');
        ok(app.includes('nxDescPanelSync(true); // b440'), 'nxDescToggle синхронизирует панель');
    }

    console.log('\nH. Свайп по панели — скролл текста, а не листание карт');
    insp(0);
    clickBtn();
    ok(shown(), 'панель открыта перед свайпом');
    {
        const before = ev('inspectIdx');
        ev(`(function(){
            const t = new Event('touchstart', { bubbles: true }); t.touches = [{ clientX: 320 }];
            document.getElementById('inspect-desc-full-text').dispatchEvent(t);
            const e2 = new Event('touchend', { bubbles: true }); e2.changedTouches = [{ clientX: 60 }];
            document.dispatchEvent(e2);
        })()`);
        eq(ev('inspectIdx'), before, 'свайп по панели карту не переключил');
        eq(panelTxt().textContent, LONG, 'текст панели не сбился');
        ev(`(function(){
            const t = new Event('touchstart', { bubbles: true }); t.touches = [{ clientX: 320 }];
            document.getElementById('inspect-card-render').dispatchEvent(t);
            const e2 = new Event('touchend', { bubbles: true }); e2.changedTouches = [{ clientX: 60 }];
            document.dispatchEvent(e2);
        })()`);
        eq(ev('inspectIdx'), before + 1, 'свайп по карте по-прежнему листает');
    }

    console.log('\nI. Чужой HTML в описании не становится разметкой');
    ev('closeInspectModal()');
    insp(3);
    {
        const cardTxt = doc.querySelector('#inspect-card-render .nx-desc-text');
        ok(!cardTxt, 'короткое описание — без обёртки клампа (как раньше)');
        const ps = [...doc.querySelectorAll('#inspect-card-render p')];
        const p = ps.find(x => x.textContent.indexOf('жирный') >= 0);
        ok(!!p, 'описание отрендерено');
        eq(p && p.textContent, EVIL, 'текст описания показан как есть');
        eq(p && p.querySelectorAll('img,b').length, 0, 'в лице карты нет чужих элементов (img/b не созданы)');
        eq(ev('window.__pwned === true'), false, 'onerror из чужого описания не выполнился');
        // длинное «зловредное» описание → панель
        ev(`state.cards[3].description = ${JSON.stringify(EVIL + ' ' + LONG)}`);
        insp(3);
        clickBtn();
        ok(shown(), 'панель открыта для длинного описания с HTML');
        eq(panelTxt().querySelectorAll('img,b').length, 0, 'в панели нет чужих элементов (текст через textContent)');
        eq(panelTxt().textContent, EVIL + ' ' + LONG, 'в панели весь текст, включая спецсимволы');
        eq(ev('window.__pwned === true'), false, 'инъекция не сработала и в панели');
    }

    console.log('\nJ. Теги сборки едины (боевой тег берём из sw.js)');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bld = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');
        const tagM = sw.match(/const VERSION = '(nxmob\d+)';/);
        ok(!!tagM, 'sw.js: боевой тег VERSION парсится');
        const TAG = tagM ? tagM[1] : 'nxmob0';
        ok(TAG >= 'nxmob162', 'боевой тег не старше nxmob162 (сборка b440)  → ' + TAG);
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
