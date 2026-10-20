/* b475: имя и боевые статы можно СКРЫТЬ с лица карты — настройка в Студии.

   Заявка владельца: «сделай на карточках, чтоб в Студии можно скрывать имя и
   характеристики (боевые статы) на самой карте, чтоб их не было видно в
   просмотре карты — нужно сделать, чтоб их можно было скрывать в настройках
   карты».

   A. Разметка/теги: в форме карточки у «Имя персонажа» появился вариант
      «Скрыть», рядом — селект «Боевые статы на карте» (card-stats-pos) с
      вариантами «Внизу (классика)» / «Скрыть», оба перерисовывают предпросмотр;
      подсказка про «Скрыть»; тег сборки единый (index.html ×8, sw.js, build.py).
   B. Исходники app.js: cardLayoutOf нормирует namePos:'hide' и новое statsPos;
      помощники cardNameShown/cardStatsShown; cardTextZones не кладёт скрытое
      имя ни в одну зону; три рендера статов закрыты гардом; форма читает и
      восстанавливает statsPos; 'layout' по-прежнему в STD_CARD_FIELDS.
   C. Поведение (jsdom): просмотр карты, сетка альбома (обычная и компактная),
      вскрытие пака и предпросмотр Студии не рисуют имя/статы при 'hide' и
      рисуют при 'bottom'; арт, номер и редкость остаются; статус вскрытия
      (#status-N) не теряется; форма → card.layout → editCard (round-trip);
      getCardStats, «Строки» альбома и списки Студии продолжают показывать
      значения (скрытие касается только лица карты).

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b475.js
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

const NAME = 'ТЕСТОВОЕ_ИМЯ_XYZ';

// Имя карты остаётся в alt=<img> (доступность, поиск по коллекции), поэтому
// проверяем не подстроку HTML, а ВИДИМЫЙ текст лица карты.
let __probe = null;
const visibleText = (doc, html) => {
    if (!__probe) __probe = doc.createElement('div');
    __probe.innerHTML = html;
    return __probe.textContent || '';
};

(async () => {
    console.log('A. Разметка формы карточки и теги сборки');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');

        ok(/<select id="card-name-pos"[^>]*>[\s\S]{0,600}?<option value="hide">/.test(html),
           '«Имя персонажа»: добавлен вариант «Скрыть»');
        ok(/<select id="card-stats-pos"[^>]*onchange="renderCardPreviewSoon\(\)"/.test(html),
           'появился селект «Боевые статы на карте» (card-stats-pos), перерисовывает предпросмотр');
        const statsSel = (html.match(/<select id="card-stats-pos"[\s\S]*?<\/select>/) || [''])[0];
        ok(/<option value="bottom">/.test(statsSel), 'card-stats-pos: вариант «Внизу (классика)»');
        ok(/<option value="hide">/.test(statsSel), 'card-stats-pos: вариант «Скрыть»');
        ok(!/<option value="top">/.test(statsSel), 'card-stats-pos: лишних вариантов нет (статы живут внизу)');
        ok(/<select id="card-name-pos"[^>]*onchange="renderCardPreviewSoon\(\)"/.test(html),
           '«Имя персонажа» по-прежнему перерисовывает предпросмотр');
        ok(/«Скрыть» убирает блок с лица карты/.test(html), 'под формой — подсказка, что значит «Скрыть»');

        const tags = (html.match(/nxmob219/g) || []).length;
        eq(tags, 8, 'index.html: тег nxmob219 во всех 8 ссылках на assets');
        ok(!html.includes('nxmob218'), 'index.html: старого тега nxmob218 не осталось');
        ok(sw.includes("const VERSION = 'nxmob219';"), 'sw.js: VERSION = nxmob219');
        ok(bp.includes("BUILD_TAG = 'nxmob219'"), 'tools/build.py: BUILD_TAG = nxmob219');
    }

    console.log('\nB. Исходники assets/app.js');
    {
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        const count = (re) => (app.match(re) || []).length;
        ok(app.includes("namePos: (L.namePos === 'top' || L.namePos === 'hide') ? L.namePos : 'bottom'"),
           'cardLayoutOf: namePos пропускает «hide»');
        ok(app.includes("statsPos: L.statsPos === 'hide' ? 'hide' : 'bottom'"),
           'cardLayoutOf: новое поле statsPos (мусор и отсутствие = «bottom»)');
        eq(count(/function cardNameShown\(/g), 1, 'cardNameShown() объявлена один раз');
        eq(count(/function cardStatsShown\(/g), 1, 'cardStatsShown() объявлена один раз');
        ok(/else if \(L\.namePos !== 'hide'\) bottom\.push\(nameHtml\);/.test(app),
           'cardTextZones: скрытое имя не попадает ни в верхнюю, ни в нижнюю зону');
        eq(count(/cardStatsShown\(L\) \? `<div class="flex items-center/g), 3,
           'статы закрыты гардом во всех трёх рендерах (альбом, просмотр, предпросмотр Студии)');
        ok(/\$\{cardNameShown\(L\) \? `<h4 class="relative z-10/.test(app),
           'компактная карточка альбома: имя под гардом');
        ok(app.includes("statsPos: g('card-stats-pos')"), 'readCardLayoutForm() читает statsPos из формы');
        ok(/const statsPosEl = document\.getElementById\('card-stats-pos'\);[\s\S]{0,80}?statsPosEl\.value = L0\.statsPos;/.test(app),
           'editCard() восстанавливает настройку статов в форме');
        ok(/STD_CARD_FIELDS = \[[^\]]*'layout'/.test(app), "'layout' в STD_CARD_FIELDS — настройка уезжает в комнату");
        ok(!/function cardNameShown\([\s\S]{0,4000}?function cardNameShown\(/.test(app), 'дубликатов новых функций нет');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;

    console.log('\nC. Нормализация layout');
    eq(ev(`cardLayoutOf({}).statsPos`), 'bottom', 'пустой layout → статы видны (прежнее поведение)');
    eq(ev(`cardLayoutOf({}).namePos`), 'bottom', 'пустой layout → имя внизу (прежнее поведение)');
    eq(ev(`cardLayoutOf({ layout: { statsPos: 'hide' } }).statsPos`), 'hide', 'statsPos:"hide" проходит');
    eq(ev(`cardLayoutOf({ layout: { statsPos: 'HIDE' } }).statsPos`), 'bottom', 'мусор в statsPos → «bottom»');
    eq(ev(`cardLayoutOf({ layout: { statsPos: 'top' } }).statsPos`), 'bottom', 'неизвестное значение statsPos → «bottom»');
    eq(ev(`cardLayoutOf({ layout: { namePos: 'hide' } }).namePos`), 'hide', 'namePos:"hide" проходит');
    eq(ev(`cardLayoutOf({ layout: { namePos: 'top' } }).namePos`), 'top', 'namePos:"top" не сломан');
    eq(ev(`cardLayoutOf({ layout: { namePos: 'hide', descPos: 'top', align: 'center', shine: 'foil' } }).descPos`), 'top',
       'остальные поля композиции не задеты');
    eq(ev(`cardNameShown(cardLayoutOf({ layout: { namePos: 'hide' } }))`), false, 'cardNameShown: hide → false');
    eq(ev(`cardStatsShown(cardLayoutOf({}))`), true, 'cardStatsShown: по умолчанию → true');

    console.log('\nD. cardTextZones');
    {
        const z = (layout) => ev(`(function(){
            const L = cardLayoutOf({ layout: ${JSON.stringify(layout)} });
            const Z = cardTextZones(L, '<b>BADGE</b>', '<h4>NAMEZONE</h4>', '<p>DESCZONE</p>', '<i>STATSZONES</i>');
            return JSON.stringify({ top: Z.top, bottom: Z.bottom });
        })()`);
        const both = JSON.parse(z({}));
        ok(both.bottom.includes('NAMEZONE') && both.bottom.includes('STATSZONES'), 'по умолчанию имя и статы в нижней зоне');
        const hid = JSON.parse(z({ namePos: 'hide', statsPos: 'hide' }));
        ok(!hid.top.includes('NAMEZONE') && !hid.bottom.includes('NAMEZONE'), 'имя скрыто — зоны без него');
        ok(hid.top.includes('BADGE'), 'бейджи (номер/редкость) остаются');
        // extraHtml — общий слот: в нём статы (альбом/просмотр/превью) И статус
        // вскрытия (#status-N). Поэтому статы гасятся в рендерах (пустая строка),
        // а не внутри cardTextZones — иначе молчал бы и статус вскрытия.
        ok(hid.bottom.includes('STATSZONES'), 'слот extraHtml остался общим (статус вскрытия не теряется)');
        const hid2 = JSON.parse(ev(`(function(){
            const L = cardLayoutOf({ layout: { statsPos: 'hide' } });
            const Z = cardTextZones(L, '<b>BADGE</b>', '<h4>NAMEZONE</h4>', '', cardStatsShown(L) ? '<i>STATSZONES</i>' : '');
            return JSON.stringify({ bottom: Z.bottom });
        })()`));
        ok(!hid2.bottom.includes('STATSZONES'), 'рендеры передают пустой блок статов — в зонах их нет');
        const top = JSON.parse(z({ namePos: 'top', descPos: 'top' }));
        ok(top.top.includes('NAMEZONE') && top.top.includes('DESCZONE'), '«Вверху» у имени и описания не сломано');
        const dHide = JSON.parse(z({ descPos: 'hide' }));
        ok(!dHide.top.includes('DESCZONE') && !dHide.bottom.includes('DESCZONE'), '«Скрыть» у описания (b261) не сломано');
    }

    // тестовые карты: обычная и «скрытая»
    const ids = JSON.parse(ev(`(function(){
        try { SoundFX.play = function(){}; } catch (e) {}
        window.__oldPump = imgPump; imgPump = function(){}; imgQueue.length = 0;
        state.cards = STANDARD_CARDS.map(c => Object.assign({}, c));
        state.collection = state.collection || {};
        const a = state.cards[0], b = state.cards[1];
        a.name = ${JSON.stringify(NAME)}; a.description = 'обычное описание';
        a.atk = 7; a.hp = 9;
        a.layout = Object.assign({}, a.layout, { namePos: 'bottom', descPos: 'bottom', statsPos: 'bottom' });
        b.name = ${JSON.stringify(NAME)}; b.description = 'скрытое описание';
        b.atk = 7; b.hp = 9;
        b.layout = Object.assign({}, b.layout, { namePos: 'hide', descPos: 'hide', statsPos: 'hide' });
        state.collection[a.id] = 2; state.collection[b.id] = 1;
        return JSON.stringify([a.id, b.id]);
    })()`));
    eq(ids.length, 2, 'подготовлены 2 карты: видимая и скрытая');
    const [ID_SHOW, ID_HIDE] = ids;

    console.log('\nE. Просмотр карты (inspectCard)');
    {
        const face = (id) => { ev(`inspectCard(${JSON.stringify(id)}, ${JSON.stringify(ids)})`); return doc.getElementById('inspect-card-render').innerHTML; };
        const h1 = face(ID_SHOW);
        ok(visibleText(doc, h1).includes(NAME), 'обычная карта: имя видно');
        ok(/fa-bolt/.test(h1) && /fa-heart/.test(h1), 'обычная карта: чипы ⚔ и ❤ видны');
        ok(visibleText(doc, h1).includes('7') && visibleText(doc, h1).includes('9'), 'обычная карта: числа статов видны');
        const h2 = face(ID_HIDE);
        ok(!visibleText(doc, h2).includes(NAME), 'скрытая карта: имени на лице НЕТ');
        ok(!/fa-bolt|fa-heart/.test(h2), 'скрытая карта: боевых статов на лице НЕТ');
        ok(!visibleText(doc, h2).includes('скрытое описание'), 'скрытая карта: описания на лице нет (descPos:"hide")');
        ok(/<img /.test(h2), 'арт карты на месте');
        ok(/font-mono/.test(h2), 'бейдж номера карты на месте');
        ok(/backdrop-blur-sm/.test(h2), 'бейдж редкости на месте');
        ok(h2.includes('alt="' + NAME + '"'), 'alt у арта имя сохранил (доступность/поиск — невидимо)');
        ok(!doc.getElementById('modal-inspect').classList.contains('hidden'), 'модалка просмотра открылась');
        ev('closeInspectModal()');
    }

    console.log('\nF. Сетка альбома (albumCardHTML)');
    {
        const full = (id) => ev(`albumCardHTML(state.cards.find(c => c.id === ${JSON.stringify(id)}), { art: 'mid' })`);
        const compact = (id) => ev(`albumCardHTML(state.cards.find(c => c.id === ${JSON.stringify(id)}), { compact: true })`);
        ok(visibleText(doc, full(ID_SHOW)).includes(NAME), 'обычная карточка альбома: имя видно');
        ok(full(ID_SHOW).includes('⚔') && full(ID_SHOW).includes('❤'), 'обычная карточка альбома: статы видны');
        ok(!visibleText(doc, full(ID_HIDE)).includes(NAME), 'скрытая карточка альбома: имени нет');
        ok(!full(ID_HIDE).includes('⚔') && !full(ID_HIDE).includes('❤'), 'скрытая карточка альбома: статов нет');
        ok(/<img /.test(full(ID_HIDE)) && full(ID_HIDE).includes('inspectCard'), 'арт и клик по карточке остались');
        ok(!visibleText(doc, compact(ID_HIDE)).includes(NAME), 'компактная сетка: имени нет');
        ok(visibleText(doc, compact(ID_SHOW)).includes(NAME), 'компактная сетка: обычная карта с именем');
        ok(/<img /.test(compact(ID_HIDE)), 'компактная сетка: арт на месте');
    }

    console.log('\nG. Вскрытие пака (showUnboxingUI)');
    {
        const unbox = (id) => {
            ev(`(function(){
                const c = state.cards.find(x => x.id === ${JSON.stringify(id)});
                showUnboxingUI({ id: 'pack-test', title: 'Тестовый пак', price: 100 }, [Object.assign({}, c, { unboxedId: 1 })]);
            })()`);
            return doc.getElementById('unboxing-cards-container').innerHTML;
        };
        const u1 = unbox(ID_SHOW);
        ok(visibleText(doc, u1).includes(NAME), 'обычная карта во вскрытии: имя видно');
        const u2 = unbox(ID_HIDE);
        ok(!visibleText(doc, u2).includes(NAME), 'скрытая карта во вскрытии: имени нет');
        ok(/id="status-0"/.test(u2), 'слой статуса вскрытия (#status-0) не потерялся');
        ok(/scratch-canvas-0/.test(u2), 'слой стирания на месте');
        ev(`document.getElementById('modal-unboxing').classList.add('hidden')`);
    }

    console.log('\nH. Форма Студии: предпросмотр, сохранение, восстановление');
    {
        const setForm = (namePos, statsPos) => ev(`(function(){
            document.getElementById('card-name').value = ${JSON.stringify(NAME)};
            document.getElementById('card-desc').value = 'описание из формы';
            document.getElementById('card-image').value = 'https://example.com/art.png';
            document.getElementById('card-atk').value = '7';
            document.getElementById('card-hp').value = '9';
            document.getElementById('card-name-pos').value = ${JSON.stringify(namePos)};
            document.getElementById('card-stats-pos').value = ${JSON.stringify(statsPos)};
            renderCardPreview();
            return document.getElementById('card-preview').innerHTML;
        })()`);
        const p1 = setForm('bottom', 'bottom');
        ok(p1.includes(NAME), 'предпросмотр: имя видно при «Внизу»');
        ok(p1.includes('⚔') && p1.includes('❤'), 'предпросмотр: статы видны при «Внизу»');
        const p2 = setForm('hide', 'hide');
        ok(!visibleText(doc, p2).includes(NAME), 'предпросмотр: имени нет при «Скрыть»');
        ok(!p2.includes('⚔') && !p2.includes('❤'), 'предпросмотр: статов нет при «Скрыть»');
        ok(/<img /.test(p2), 'предпросмотр не развалился (арт на месте)');
        ok(/card-aspect/.test(doc.getElementById('card-preview').className), 'рамка предпросмотра (card-aspect) на месте');
        const p3 = setForm('top', 'bottom');
        ok(visibleText(doc, p3).includes(NAME) && p3.includes('⚔'), 'предпросмотр: «Вверху» + статы — всё видно');

        eq(ev(`JSON.stringify(readCardLayoutForm().statsPos)`).replace(/"/g, ''), 'bottom',
           'readCardLayoutForm(): statsPos читается из формы');

        // round-trip: сохранили «скрыто» → editCard вернул настройки в форму
        ev(`(function(){
            document.getElementById('edit-card-id').value = ${JSON.stringify(ID_SHOW)};
            document.getElementById('card-pack-id').value = state.cards.find(c => c.id === ${JSON.stringify(ID_SHOW)}).packId;
            document.getElementById('card-image').value = 'https://example.com/art.png';
            document.getElementById('card-name-pos').value = 'hide';
            document.getElementById('card-stats-pos').value = 'hide';
            handleSaveCard(new Event('submit'));
        })()`);
        const saved = ev(`JSON.stringify(state.cards.find(c => c.id === ${JSON.stringify(ID_SHOW)}).layout)`);
        ok(/"namePos":"hide"/.test(saved), 'handleSaveCard: namePos:"hide" записан в карту');
        ok(/"statsPos":"hide"/.test(saved), 'handleSaveCard: statsPos:"hide" записан в карту');
        const face2 = ev(`(function(){ inspectCard(${JSON.stringify(ID_SHOW)}, ${JSON.stringify(ids)}); return document.getElementById('inspect-card-render').innerHTML; })()`);
        ok(!visibleText(doc, face2).includes(NAME) && !/fa-bolt/.test(face2), 'после сохранения просмотр карты не показывает имя и статы');
        ev('closeInspectModal()');

        ev(`editCard(${JSON.stringify(ID_SHOW)})`);
        eq(doc.getElementById('card-name-pos').value, 'hide', 'editCard: «Имя персонажа» = Скрыть');
        eq(doc.getElementById('card-stats-pos').value, 'hide', 'editCard: «Боевые статы на карте» = Скрыть');
        ev('resetCardForm()');
        eq(doc.getElementById('card-name-pos').value, 'bottom', 'resetCardForm: имя снова «Внизу»');
        eq(doc.getElementById('card-stats-pos').value, 'bottom', 'resetCardForm: статы снова «Внизу»');
    }

    console.log('\nI. Регрессии: значения статов и списки не задеты');
    {
        const st = JSON.parse(ev(`JSON.stringify(getCardStats(state.cards.find(c => c.id === ${JSON.stringify(ID_HIDE)})))`));
        ok(st.atk > 0 && st.hp > 0, 'getCardStats скрытой карты считает atk/hp (' + st.atk + '/' + st.hp + ') — бой не сломан');
        const row = ev(`albumRowHTML(state.cards.find(c => c.id === ${JSON.stringify(ID_HIDE)}))`);
        ok(visibleText(doc, row).includes(NAME), '«Строки» альбома: имя остаётся (это список, а не лицо карты)');
        ok(row.includes('⚔') && row.includes('❤'), '«Строки» альбома: статы остаются');
        const srow = ev(`studioCardRowHTML(state.cards.find(c => c.id === ${JSON.stringify(ID_HIDE)}), 1, 1)`);
        ok(srow.includes('⚔') && srow.includes('❤'), 'список карточек в Студии: статы видны владельцу');
        ok(/editCard\(/.test(srow), 'список карточек в Студии: кнопка правки на месте');
        const bulk = ev(`(function(){ const L = { namePos: 'bottom', descPos: 'hide', align: 'center', shine: 'auto' }; return cardLayoutOf({ layout: L }).statsPos; })()`);
        eq(bulk, 'bottom', 'массовая загрузка (layout без statsPos): статы видны, как раньше');
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
