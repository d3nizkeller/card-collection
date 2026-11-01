/* b534: «Шансы редкостей (веса)» — во всю ширину, без пустого места справа.
   Владелец (скрин): четыре инпута весов занимали ~2/3 ячейки редактора.
   Сетка весов получила id pack-odds-grid + класс .odds-grid: отдельное
   CSS-правило повторяет резиновые колонки repeat(4, minmax(0,1fr)) и w-full,
   не полагаясь на хвост-классы и старый кэш; инпуты внутри — width:100%.

   Проверки: разметка (id/класс/w-full), CSS-правило и его разбор в CSSOM,
   единый тег сборки.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom node tools/test-b534.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');
const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };

(async () => {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
    const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');

    console.log('A. Разметка и CSS');
    const i = html.indexOf('id="pack-odds-grid"');
    ok(i > 0 && html.slice(i, i + 420).indexOf("pack-odds-common") > 0, 'сетка весов с id pack-odds-grid прямо над инпутами');
    ok(html.slice(i, i + 160).indexOf('odds-grid grid grid-cols-4 gap-2 w-full') > 0, 'класс .odds-grid + w-full на сетке');
    ok(html.indexOf('.odds-grid{') > 0 && html.indexOf('grid-template-columns:repeat(4, minmax(0, 1fr))') > 0, 'CSS: резиновые 4 колонки на всю ширину');
    ok(html.indexOf('.odds-grid input{ width:100%; min-width:0; }') > 0, 'CSS: инпуты растянуты (width:100%, min-width:0)');
    const tag = (bp.match(/BUILD_TAG = '(nxmob\d+)'/) || [])[1];
    ok(!!tag && html.indexOf(tag) > 0 && new RegExp("const VERSION = '" + tag + "';").test(sw), 'тег единый: ' + tag);

    console.log('B. CSSOM');
    {
        const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>');
        const st = dom.window.document.createElement('style');
        const a = html.indexOf('/* ===== b534:');
        const b = html.indexOf('</style>', a);
        st.textContent = html.slice(a, b);
        dom.window.document.head.appendChild(st);
        const rules = [...dom.window.document.styleSheets[0].cssRules];
        const g = rules.find(r => r.selectorText === '.odds-grid');
        ok(!!g, '.odds-grid дошло до CSSOM');
        ok(g && /repeat\(4, minmax\(0, 1fr\)|repeat\(4,minmax\(0,1fr\)/.test(g.style.gridTemplateColumns), 'колонки не отброшены парсером: ' + (g ? g.style.gridTemplateColumns : '-'));
        ok(!!rules.find(r => r.selectorText === '.odds-grid input'), '.odds-grid input в CSSOM');
        dom.window.close();
    }

    console.log(fails ? ('\n❌ b534: провалов ' + fails + ' из ' + checks) : ('\n✅ b534: все ' + checks + ' проверок зелёные'));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('crash:', e); process.exit(1); });
