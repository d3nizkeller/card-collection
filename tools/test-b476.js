/* b476: блок «Боевые статы» в форме карточки — во всю ширину, подсказка убрана.

   Уточнение владельца к b475: «сделай во всю ширину и убери подсказку».

   A. Разметка/теги: подсказки b475 под формой нет; блок значений статов
      (card-atk/card-hp) вынесен из сетки «Композиция и эффект карты» и стоит
      отдельной строкой левой колонки (то есть тянется на всю ширину формы, как
      строка имени/описания); селекторы видимости b475 на месте; тег сборки
      единый nxmob220 (index.html ×8, sw.js, build.py).
   B. Поведение (jsdom): скрытие имени/статов b475 не сломано (просмотр карты,
      сетка альбома, предпросмотр Студии); форма по-прежнему сохраняет atk/hp и
      layout.statsPos, editCard восстанавливает и селекторы, и числа;
      getCardStats не тронут.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b476.js
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
    console.log('A. Разметка формы и теги сборки');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');

        ok(!html.includes('«Скрыть» убирает блок с лица карты'), 'подсказка b475 под формой удалена');
        ok(!/<i class="fa-solid fa-eye-slash mr-1"><\/i>«Скрыть»/.test(html), 'строки подсказки с иконкой fa-eye-slash больше нет');

        // блок статов стоит ПОСЛЕ закрытия сетки композиции, отдельной строкой колонки
        const iSelClose = html.indexOf('</select>', html.indexOf('id="card-stats-pos"'));
        const iGridClose = html.indexOf('</div>', html.indexOf('id="card-aura"'));
        const iStats = html.indexOf('id="card-atk"');
        ok(iSelClose > 0 && iStats > iSelClose, 'порядок в разметке сохранён: статы-селектор, затем поля значений');
        ok(html.indexOf('<!-- b476:') > 0 && html.indexOf('<!-- b476:') < iStats, 'перенос блока помечен комментарием b476');
        ok(!/col-span-2[^\n]*card-atk|card-atk[^\n]*col-span-2/.test(html), 'блок статов не relies на col-span-2 (класса нет в прекомпилированном tailwind.css)');

        const atkBlock = (html.match(/<label[^>]*>Боевые статы <span[\s\S]{0,1400}?<\/div>\s*<\/div>/) || [''])[0];
        ok(atkBlock.includes('id="card-atk"') && atkBlock.includes('id="card-hp"'), 'оба поля значений остались в одном блоке');
        ok(/id="card-atk"[^>]*oninput="renderCardPreviewSoon\(\)"/.test(html), 'Атака по-прежнему перерисовывает предпросмотр');
        ok(/id="card-hp"[^>]*oninput="renderCardPreviewSoon\(\)"/.test(html), 'Здоровье по-прежнему перерисовывает предпросмотр');
        ok(/<select id="card-stats-pos"/.test(html), 'селектор «Боевые статы на карте» (b475) на месте');
        ok(/<select id="card-name-pos"[^>]*>[\s\S]{0,400}?<option value="hide">/.test(html), '«Скрыть» у имени (b475) на месте');

        // b477: номер тега не прибиваем к b476 — проверяем единство: боевой тег из
        // sw.js повторён во всех 8 ссылках index.html и равен BUILD_TAG, не ниже nxmob220
        const tag = (sw.match(/const VERSION = '(nxmob\d+)';/) || [])[1];
        ok(!!tag, 'sw.js: боевой тег на месте (' + tag + ')');
        eq((html.match(new RegExp(tag, 'g')) || []).length, 8, 'index.html: тег из sw.js во всех 8 ссылках на assets');
        ok(bp.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG равен тегу из sw.js');
        ok(Number((tag || '0').replace('nxmob', '')) >= 220, 'тег не ниже nxmob220');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;

    console.log('\nB. Структура формы в живом DOM');
    {
        const st = JSON.parse(ev(`(function () {
            const atk = document.getElementById('card-atk');
            const compGrid = document.getElementById('card-name-pos').closest('.grid');
            const inner = atk.closest('.grid');          // внутренняя сетка Атака/Здоровье
            const block = inner.parentElement;           // обёртка блока статов
            const row = block.parentElement;             // строка формы
            return JSON.stringify({
                inCompGrid: compGrid.contains(atk),
                rowNotGrid: !row.classList.contains('grid'),
                rowInColumn: row.parentElement.classList.contains('space-y-3'),
                fullRowWithComposition: row.contains(document.getElementById('card-name-pos')),
                innerTwoCols: inner.classList.contains('grid-cols-2'),
            });
        })()`));
        eq(st.inCompGrid, false, 'поля статов больше НЕ внутри двухколоночной сетки композиции');
        eq(st.rowNotGrid, true, 'строка блока статов — не сетка: блок тянется на всю ширину');
        eq(st.rowInColumn, true, 'блок статов — в левой колонке формы, как остальные строки');
        eq(st.fullRowWithComposition, true, 'ширина блока статов = ширине блока «Композиция и эффект карты»');
        eq(st.innerTwoCols, true, 'внутри блока — две половины на всю ширину (Атака / Здоровье)');
    }

    console.log('\nC. Регрессии b475: скрытие имени и статов работает');
    const ids = JSON.parse(ev(`(function(){
        try { SoundFX.play = function(){}; } catch (e) {}
        try { imgPump = function(){}; imgQueue.length = 0; } catch (e) {}
        state.cards = STANDARD_CARDS.map(c => Object.assign({}, c));
        state.collection = state.collection || {};
        const a = state.cards[0], b = state.cards[1];
        a.name = ${JSON.stringify(NAME)}; a.atk = 7; a.hp = 9; a.description = 'видимое';
        a.layout = Object.assign({}, a.layout, { namePos: 'bottom', descPos: 'bottom', statsPos: 'bottom' });
        b.name = ${JSON.stringify(NAME)}; b.atk = 7; b.hp = 9; b.description = 'скрытое';
        b.layout = Object.assign({}, b.layout, { namePos: 'hide', descPos: 'hide', statsPos: 'hide' });
        state.collection[a.id] = 1; state.collection[b.id] = 1;
        return JSON.stringify([a.id, b.id]);
    })()`));
    eq(ids.length, 2, 'подготовлены 2 карты: видимая и скрытая');
    {
        const face = (id) => { ev(`inspectCard(${JSON.stringify(id)}, ${JSON.stringify(ids)})`); return doc.getElementById('inspect-card-render').innerHTML; };
        const h1 = face(ids[0]);
        ok(visibleText(doc, h1).includes(NAME) && /fa-bolt/.test(h1), 'просмотр: обычная карта с именем и статами');
        const h2 = face(ids[1]);
        ok(!visibleText(doc, h2).includes(NAME) && !/fa-bolt|fa-heart/.test(h2), 'просмотр: скрытая карта без имени и статов');
        ev('closeInspectModal()');
        const grid = ev(`albumCardHTML(state.cards.find(c => c.id === ${JSON.stringify(ids[1])}), { art: 'mid' })`);
        ok(!visibleText(doc, grid).includes(NAME) && !grid.includes('fa-bolt'), 'сетка альбома: скрытая карта без имени и статов');
    }
    {
        const setForm = (namePos, statsPos) => ev(`(function(){
            document.getElementById('card-name').value = ${JSON.stringify(NAME)};
            document.getElementById('card-atk').value = '7';
            document.getElementById('card-hp').value = '9';
            document.getElementById('card-image').value = 'https://example.com/a.png';
            document.getElementById('card-name-pos').value = ${JSON.stringify(namePos)};
            document.getElementById('card-stats-pos').value = ${JSON.stringify(statsPos)};
            renderCardPreview();
            return document.getElementById('card-preview').innerHTML;
        })()`);
        ok(!visibleText(doc, setForm('hide', 'hide')).includes(NAME), 'предпросмотр: имя скрыто');
        ok(!setForm('hide', 'hide').includes('fa-bolt'), 'предпросмотр: статы скрыты');
        ok(visibleText(doc, setForm('bottom', 'bottom')).includes(NAME), 'предпросмотр: имя видно при «Внизу»');
    }
    {
        ev(`(function(){
            document.getElementById('edit-card-id').value = ${JSON.stringify(ids[0])};
            document.getElementById('card-pack-id').value = state.cards.find(c => c.id === ${JSON.stringify(ids[0])}).packId;
            document.getElementById('card-image').value = 'https://example.com/a.png';
            document.getElementById('card-atk').value = '11';
            document.getElementById('card-hp').value = '22';
            document.getElementById('card-name-pos').value = 'hide';
            document.getElementById('card-stats-pos').value = 'hide';
            handleSaveCard(new Event('submit'));
        })()`);
        const card = JSON.parse(ev(`JSON.stringify(state.cards.find(c => c.id === ${JSON.stringify(ids[0])}))`));
        eq(card.atk, 11, 'handleSaveCard: Атака сохраняется из полноширинного блока');
        eq(card.hp, 22, 'handleSaveCard: Здоровье сохраняется');
        eq(card.layout.statsPos, 'hide', 'handleSaveCard: statsPos сохраняется');
        ev(`editCard(${JSON.stringify(ids[0])})`);
        eq(doc.getElementById('card-atk').value, '11', 'editCard: Атака возвращается в поле');
        eq(doc.getElementById('card-hp').value, '22', 'editCard: Здоровье возвращается в поле');
        eq(doc.getElementById('card-stats-pos').value, 'hide', 'editCard: селектор статов возвращается');
        const st = JSON.parse(ev(`JSON.stringify(getCardStats(state.cards.find(c => c.id === ${JSON.stringify(ids[0])})))`));
        ok(st.atk === 11 && st.hp === 22, 'getCardStats: значения не потеряны (' + st.atk + '/' + st.hp + ')');
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
