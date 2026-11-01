/* b535: «Тут не должно быть пустое место» — блок «Шансы редкостей» не растягивался
   на обе колонки редактора: sm:col-span-2 ВЫРЕЗАН из прекомпелированного
   tailwind.css (проверено: col-span-2 в CSS нет вообще), ячейка падала в левую
   колонку, справа зияла дыра (скрин владельца с крестом).
   Как в b480: инлайн grid-column:1 / -1 — на десктопе_span обеих колонок,
   на мобильной одноколоночной сетке просто первая колонка (безопасно).

   Проверки: инлайн-стиль стоит на обёртке весов прямо над #pack-odds-grid;
   парсер jsdom читает grid-column из атрибута; правило .odds-grid (b534) на
   месте; col-span-2 по-прежнему отсутствует в CSS (значит инлайн необходим);
   единый тег сборки.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom node tools/test-b535.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');
const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };

(async () => {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const tw = fs.readFileSync(path.join(ROOT, 'assets', 'tailwind.css'), 'utf8');
    const ap = fs.readFileSync(path.join(ROOT, 'assets', 'app.css'), 'utf8');
    const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
    const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');

    console.log('A. Разметка');
    const i = html.indexOf('id="pack-odds-grid"');
    const wrap = html.lastIndexOf('<div class="flex flex-col min-w-0 sm:col-span-2" style="grid-column:1 / -1">', i);
    ok(wrap > 0 && i - wrap < 700, 'обёртка весов с инлайн grid-column:1 / -1 прямо над сеткой весов');
    ok(html.indexOf('.odds-grid{') > 0, 'правило .odds-grid (b534, резина на всю ширину ячейки) на месте');
    ok(tw.indexOf('col-span-2') < 0 && ap.indexOf('col-span-2') < 0, 'col-span-2 нет в собранном CSS — инлайн-фолбэк необходим');

    console.log('B. Инлайн-стиль парсится браузером');
    {
        const dom = new JSDOM('<!doctype html><html><body></body></html>');
        const el = dom.window.document.createElement('div');
        el.setAttribute('style', 'grid-column:1 / -1');
        dom.window.document.body.appendChild(el);
        ok(el.style.gridColumn === '1 / -1', 'grid-column из атрибута читается: ' + el.style.gridColumn);
        dom.window.close();
    }

    console.log('C. Тег');
    const tag = (bp.match(/BUILD_TAG = '(nxmob\d+)'/) || [])[1];
    ok(!!tag && html.indexOf(tag) > 0 && new RegExp("const VERSION = '" + tag + "';").test(sw), 'тег единый: ' + tag);

    console.log(fails ? ('\n❌ b535: провалов ' + fails + ' из ' + checks) : ('\n✅ b535: все ' + checks + ' проверок зелёные'));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('crash:', e); process.exit(1); });
