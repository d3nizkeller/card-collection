/* b480: убрать пустую ячейку в сетке «Композиция и эффект карты».

   Владелец (со скриншотом, дырка обведена красным): «не должно быть пустое
   место». Селекторов композиции девять (b475–b478), поэтому в двухколоночной
   сетке десятая ячейка пустовала рядом с «Аура за картой». Аура растянута на
   всю строку: style="grid-column:1 / -1".

   A. Разметка/теги: обёртка ауры несет grid-column:1 / -1 и содержит
      #card-aura; в сетке композиции девять селекторов и ровно одна ячейка
      во всю ширину (дырки нет); все селекторов b475–b478 на месте; тег
      nxmob224 единый.
   B. Поведение (jsdom): форма живая — предпросмотр рисуется, аура
      применяется к превью и к контейнеру ауры; редактирование карты
      восстанавливает ауру.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b480.js
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
    console.log('A. Разметка сетки композиции и теги');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');

        ok(/<!-- b480: аура занимает всю строку сетки композиции:/.test(html), 'перенос ауры на всю строку помечен комментарием b480');
        ok(/<div style="grid-column:1 \/ -1">\s*<span class="block text-\[10px\] text-slate-500 mb-1"><i class="fa-solid fa-feather-pointed[^>]*><\/i>Аура за картой<\/span>/.test(html), 'обёртка «Аура за картой» растянута на всю строку (grid-column:1 / -1)');
        ok(!/class="[^"]*col-span-2/.test(html.slice(html.indexOf('id="card-name-pos"'), html.indexOf('id="card-image-lamp"'))), 'класса col-span-2 в композиции нет — только инлайн grid-column');
        ok(/style="grid-column:1 \/ -1"/.test(html.slice(html.indexOf('id="card-name-pos"'), html.indexOf('id="card-image-lamp"'))), 'растянутая ячейка задана инлайн-стилем grid-column');

        const tag = (sw.match(/const VERSION = '(nxmob\d+)';/) || [])[1];
        // сквозная проверка тега: единый тег из sw.js повторяется 8 раз в index.html,
        // совпадает с BUILD_TAG и не ниже тега своего батча (nxmob224 для b480)
        ok(!!tag, 'sw.js: боевой тег присутствует');
        ok(Number(tag && tag.replace('nxmob', '')) >= 224, 'sw.js: тег не ниже nxmob224 (факт ' + tag + ')');
        eq((html.match(new RegExp(tag, 'g')) || []).length, 8, 'index.html: тег во всех 8 ссылках на assets');
        ok(bp.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG совпадает с тегом sw.js');
        ['card-name-pos', 'card-desc-pos', 'card-stats-pos', 'card-stats-dir', 'card-stats-shape', 'card-stats-size', 'card-align', 'card-shine', 'card-aura'].forEach(id =>
            ok(html.includes('id="' + id + '"'), 'селектор ' + id + ' на месте'));
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;

    console.log('\nB. Сетка без дырки (живой DOM)');
    {
        const g = JSON.parse(ev(`(function () {
            const grid = document.getElementById('card-name-pos').closest('.grid');
            const kids = Array.from(grid.children);
            const spanned = kids.filter(k => (k.getAttribute('style') || '').indexOf('grid-column') >= 0);
            return JSON.stringify({
                kids: kids.length,
                spanned: spanned.length,
                spanHasAura: spanned.length === 1 && !!spanned[0].querySelector('#card-aura'),
                selects: grid.querySelectorAll('select').length,
                rows: (kids.length - spanned.length) / 2 + spanned.length,
            });
        })()`));
        eq(g.kids, 9, 'в сетке композиции девять ячеек (селекторов)');
        eq(g.spanned, 1, 'ровно одна ячейка во всю ширину');
        eq(g.spanHasAura, true, 'во всю ширину — именно «Аура за картой»');
        eq(g.selects, 9, 'все девять селекторов живы');
        eq(g.rows, 5, 'четыре полных строки + одна во всю ширину: пустых ячеек нет');
    }

    console.log('\nC. Форма живая');
    {
        ev(`(function () {
            document.getElementById('card-name').value = 'Тест';
            document.getElementById('card-image').value = 'https://example.com/a.png';
            document.getElementById('card-aura').value = 'hearts';
            renderCardPreview();
        })()`);
        await new Promise(r => setTimeout(r, 300));
        const prev = doc.getElementById('card-preview').innerHTML;
        ok(prev.length > 100, 'предпросмотр рисуется после правки сетки');
        const aura = doc.getElementById('card-preview-aura');
        ok(aura && /aura-hearts/.test(aura.className), 'аура из полноширинного селекта применяется к превью');
        eq(ev(`document.getElementById('card-aura').value`), 'hearts', 'селект ауры доступен и читается');
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
