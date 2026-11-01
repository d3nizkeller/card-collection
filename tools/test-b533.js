/* b533: «стрелочки верх-вниз выглядят некрасиво и где жидкое стекло» —
   строка «Открыть сразу» (1/5/10/20/40/MAX + инпут) переведена на жидкое
   стекло, нативные спиннеры number-инпутов скрыты сайтом целиком.

   Проверки: CSS-правила существуют и ПАРСЯТСЯ браузером (jsdom CSSOM):
   скрытие спиннеров (webkit + moz), .nx-glass-row с backdrop-filter и бликом
   ::before, стеклянные чипы/инпут; шаблон строки в assets/app.js использует
   новые классы вместо плоских bg-slate-800/70; единый тег сборки.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom node tools/test-b533.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };

(async () => {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
    const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
    const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');

    console.log('A. Исходники: стекло в CSS, стекло в шаблоне');
    ok(html.indexOf('input[type="number"]::-webkit-inner-spin-button') > 0 && html.indexOf('-moz-appearance:textfield') > 0,
        'нативные спиннеры number-инпутов скрыты (webkit + firefox)');
    ok(html.indexOf('.nx-glass-row{') > 0 && html.indexOf('backdrop-filter:blur(14px) saturate(1.5)') > 0,
        'панель: жидкое стекло (полупрозрачный градиент + blur)');
    ok(html.indexOf('.nx-glass-row::before') > 0, 'панель: верхний блик стекла (::before)');
    ok(html.indexOf('.nx-glass-chip-on{') > 0 && html.indexOf('.nx-glass-chip-max{') > 0 && html.indexOf('.nx-glass-input{') > 0,
        'стеклянные чипы, активный чип, MAX и инпут');
    ok(app.indexOf('nx-glass-row" id="nx-qty-row"') > 0, 'шаблон строки: контейнер nx-glass-row');
    ok(app.indexOf('class="shrink-0 nx-glass-chip ' + "' + (nxPackQty === v ? 'nx-glass-chip-on' : '') + '") > 0, 'шаблон: пресеты — стеклянные чипы с активным состоянием');
    ok(app.indexOf('nx-glass-chip nx-glass-chip-max') > 0, 'шаблон: MAX — стеклянный янтарный чип');
    ok(app.indexOf('class="shrink-0 nx-glass-input"') > 0 && app.indexOf('w-12 px-1 py-1 rounded-lg bg-slate-800/80') < 0,
        'шаблон: инпут без плоских классов и без старых спинок');
    const tag = (bp.match(/BUILD_TAG = '(nxmob\d+)'/) || [])[1];
    ok(!!tag && html.indexOf(tag) > 0 && new RegExp("const VERSION = '" + tag + "';").test(sw), 'тег единый: ' + tag);

    console.log('B. CSS парсится браузером (jsdom CSSOM)');
    {
        const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>');
        const st = dom.window.document.createElement('style');
        const i = html.indexOf('/* ===== b533:');
        const j = html.indexOf('</style>', i);
        st.textContent = html.slice(i, j);
        dom.window.document.head.appendChild(st);
        const rules = [...dom.window.document.styleSheets[0].cssRules].map(r => r.selectorText || '');
        ok(rules.some(s => s && s.indexOf('input[type="number"]::-webkit-inner-spin-button') >= 0), 'правило скрытия спиннеров дошло до CSSOM');
        ok(rules.includes('.nx-glass-row'), '.nx-glass-row в CSSOM');
        ok(rules.includes('.nx-glass-row::before'), 'блик .nx-glass-row::before в CSSOM');
        ok(rules.includes('.nx-glass-chip') && rules.includes('.nx-glass-chip-on') && rules.includes('.nx-glass-input'), 'чипы и инпут в CSSOM');
        const row = [...dom.window.document.styleSheets[0].cssRules].find(r => r.selectorText === '.nx-glass-row');
        ok(row && /blur\(14px\)/.test(row.style.backdropFilter || row.style.getPropertyValue('backdrop-filter') || ''), 'backdrop-filter панели не отброшен парсером');
        dom.window.close();
    }

    console.log(fails ? ('\n❌ b533: провалов ' + fails + ' из ' + checks) : ('\n✅ b533: все ' + checks + ' проверок зелёные'));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('crash:', e); process.exit(1); });
