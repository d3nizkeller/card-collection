/* b479: кнопка «Скачать готовую карточку» — PNG со всем лицом карты.

   Заявка владельца: «добавь кнопку скачать готовую карточку с нумерацией и
   всем остальным».

   A. Разметка/теги: кнопка под живым предпросмотром в форме Студии
      (downloadCardPngOfForm), глиф fa-download есть в сабсете fa.css, тег
      сборки единый nxmob223.
   B. Исходники app.js: экспортный блок объявлен (nxCardFaceCanvas,
      downloadCardPng, downloadCardPngOfForm, nxCardExportName, nxArtBlobUrl,
      чипы/иконки/полигоны); уважает настройки b475–b478 (скрытие имени/
      описания/статов, место/расположение/форма/размер); кнопка скачивания в
      строке карточки Студии только владельцу (у гостей плашка «просмотр»).
   C. Поведение (jsdom): имя файла санитизируется и несёт номер #N; без арта/
      без CORS скачивание не роняет игру, а даёт понятный тост; кнопка формы
      без сохранённой карты подсказывает создать карту; строка Студии содержит
      кнопку скачивания. Настоящая отрисовка canvas проверяется браузером
      (скриншот-экспорт tools/shots/b479-export-sample.png).

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b479.js
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
    w.HTMLCanvasElement.prototype.getContext = () => null; // в jsdom нет canvas: экспорт идёт в ветку тоста
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

(async () => {
    console.log('A. Разметка и теги сборки');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const fa = fs.readFileSync(path.join(ROOT, 'assets', 'fa.css'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');

        const btn = (html.match(/<button type="button" id="card-download-btn"[\s\S]*?<\/button>/) || [''])[0];
        ok(btn.length > 0, 'в форме Студии есть кнопка скачивания (card-download-btn)');
        ok(/onclick="downloadCardPngOfForm\(\)"/.test(btn), 'кнопка вызывает downloadCardPngOfForm()');
        ok(/fa-download/.test(btn) && /Скачать готовую карточку/.test(btn), 'кнопка с иконкой и подписью «Скачать готовую карточку»');
        ok(/title="[^"]*номер #N/.test(btn), 'в title кнопки перечислено, что попадёт в файл');
        ok(fa.includes('fa-download'), 'глиф fa-download есть в сабсете fa.css');

        // b480: номер тега не прибиваем к b479 — проверяем единство: боевой тег из
        // sw.js повторён во всех 8 ссылках index.html и равен BUILD_TAG, не ниже nxmob223
        const tag = (sw.match(/const VERSION = '(nxmob\d+)';/) || [])[1];
        ok(!!tag, 'sw.js: боевой тег на месте (' + tag + ')');
        eq((html.match(new RegExp(tag, 'g')) || []).length, 8, 'index.html: тег из sw.js во всех 8 ссылках на assets');
        ok(bp.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG равен тегу из sw.js');
        ok(Number((tag || '0').replace('nxmob', '')) >= 223, 'тег не ниже nxmob223');
    }

    console.log('\nB. Исходники assets/app.js');
    {
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        const count = re => (app.match(re) || []).length;
        ['nxCardFaceCanvas', 'downloadCardPng', 'downloadCardPngOfForm', 'nxCardExportName', 'nxArtBlobUrl', 'nxDrawChip', 'nxDrawBolt', 'nxDrawHeart', 'nxPolyPath'].forEach(fn =>
            eq(count(new RegExp('function ' + fn + '\\(', 'g')), 1, fn + '() объявлена один раз'));
        ok(/const NX_STAT_POLYS = \{[\s\S]*?diamond:[\s\S]*?star:[\s\S]*?hex:[\s\S]*?shield:/.test(app), 'полигоны форм b477 для canvas: ромб, звезда, шестиугольник, щит');
        ok(/const nameBlock = cardNameShown\(L\)/.test(app), 'экспорт уважает скрытие имени (b475)');
        ok(/L\.descPos !== 'hide'/.test(app), 'экспорт уважает скрытие описания (b261/b475)');
        ok(/cardStatsShown\(L\) && L\.statsPos !== 'left' && L\.statsPos !== 'right'/.test(app), 'экспорт: статы в зонах только когда не скрыты и не на кромке');
        ok(/cardStatsShown\(L\) && \(L\.statsPos === 'left' \|\| L\.statsPos === 'right'\)/.test(app), 'экспорт: статы у кромки рисуются отдельно');
        ok(/L\.statsSize === 'lg' \? 1\.65 : \(L\.statsSize === 'md' \? 1\.3 : 1\)/.test(app), 'экспорт: тот же коэффициент размера b478 (1 / 1.3 / 1.65)');
        ok(/L\.statsShape/.test(app) && /NX_STAT_POLYS\[shape\]/.test(app), 'экспорт: форма чипов b477 берётся из layout');
        ok(/getCardLocalNumber\(card\)/.test(app), 'экспорт: номер #N из getCardLocalNumber');
        ok(/RAR_COLORS\[card\.rarity\]/.test(app), 'экспорт: рамка и бейдж редкости цветами RAR_COLORS');
        ok(/fetch\(url, \{ mode: 'cors' \}\)/.test(app), 'арт тянется fetch→blob (canvas не tainted)');
        ok(/showToast\('Не удалось скачать карточку: /.test(app), 'ошибка экспорта — понятный тост с советом про CORS');
        ok(app.includes('onclick="downloadCardPng(') && app.includes('fa-download text-xs'), 'кнопка скачивания в строке карточки Студии');
        ok(/cloudGuest\(\) \? `<span class=\\"h-7 px-1\.5 rounded-lg bg-amber-500\/10/.test(app) || app.includes('cloudGuest() ? `<span class="h-7 px-1.5 rounded-lg bg-amber-500/10'), 'у гостей в строке по-прежнему плашка «просмотр», не кнопка');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;

    console.log('\nC. Поведение (jsdom)');
    const id = JSON.parse(ev(`(function(){
        try { SoundFX.play = function(){}; } catch (e) {}
        state.cards = STANDARD_CARDS.map(c => Object.assign({}, c));
        state.collection = state.collection || {};
        const a = state.cards[0];
        a.name = 'Тест/карта: №1!';
        a.atk = 7; a.hp = 9;
        state.collection[a.id] = 2;
        return JSON.stringify(a.id);
    })()`));
    {
        const nm = ev(`nxCardExportName(state.cards.find(c => c.id === ${JSON.stringify(id)}))`);
        ok(/^card_001_[A-Za-zА-Яа-яё0-9_\-]+\.png$/.test(nm), 'имя файла: номер + санитизированное имя (' + nm + ')');
        ok(!/[\/:!]/.test(nm), 'в имени файла нет slashed/двоеточий/восклицаний');
    }
    {
        await ev(`downloadCardPng(${JSON.stringify(id)})`);
        const toast = doc.getElementById('toast-container').innerHTML;
        ok(toast.includes('Не удалось скачать карточку'), 'без арта/CORS — тост об ошибке, а не падение');
        ok(toast.includes('Загрузить с устройства'), 'в тосте подсказка залить арт на GitHub');
    }
    {
        doc.getElementById('toast-container').innerHTML = '';
        ev('downloadCardPngOfForm()');
        ok(doc.getElementById('toast-container').innerHTML.includes('Сначала создайте карточку'), 'кнопка формы без сохранённой карты подсказывает создать её');
    }
    {
        ev(`try { CLOUD.connected = function () { return false; }; } catch (e) {}`); // jsdom: без комнаты владелец, не гость
        const row = ev(`studioCardRowHTML(state.cards.find(c => c.id === ${JSON.stringify(id)}), 1, 1)`);
        ok(row.includes('downloadCardPng(') && row.includes('fa-download'), 'строка карточки в Студии: кнопка скачивания PNG');
        ok(row.includes('editCard(') && row.includes('fa-pen'), 'строка карточки: кнопка редактирования на месте');
        ok(doc.getElementById('card-download-btn') !== null, 'кнопка скачивания есть в DOM формы Студии');
    }
    {
        // регрессии: лицо карты и списки не задеты
        eq(ev(`cardLayoutOf({ layout: { statsSize: 'lg' } }).statsSize`), 'lg', 'размер b478 работает');
        eq(ev(`cardLayoutOf({ layout: { statsShape: 'star' } }).statsShape`), 'star', 'форма b477 работает');
        eq(ev(`cardLayoutOf({ layout: { statsPos: 'hide' } }).statsPos`), 'hide', 'скрытие b475 работает');
        const grid = ev(`albumCardHTML(state.cards.find(c => c.id === ${JSON.stringify(id)}), { art: 'mid' })`);
        ok(grid.includes('nx-st-wrap') && grid.includes('fa-bolt'), 'лицо карты в альбоме по-прежнему рисует чипы');
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
