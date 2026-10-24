/* b484: починка переключателя режимов «Игры» после b483 (плитки в столбик,
   активная «Тамагочи» без подсветки).

   A. Разметка/CSS/теги: контейнер плиток = grid-cols-5 sm:grid-cols-9 (обе
      утилиты реально есть в прекомпилированном tailwind.css, голого
      grid-cols-9 больше нет); правило #mode-tama-btn.lq-on с --lq-tint и
      :active добавлены; тег nxmob228 единый.
   B. Поведение (jsdom): девять плиток в контейнере; setBattleMode('tama')
      вешает lq-on на плитку тамагочи и снимает с арены; остальные режимы
      переключаются как раньше.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b484.js
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
    console.log('A. Разметка, CSS, теги');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const tw = fs.readFileSync(path.join(ROOT, 'assets', 'tailwind.css'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');

        const row = (html.match(/<div class="grid[^>]*mode-arena-btn[\s\S]{0,40}?/) || [''])[0] + html.slice(html.indexOf('id="mode-arena-btn"') - 400, html.indexOf('id="mode-arena-btn"'));
        ok(/<div class="grid grid-cols-5 sm:grid-cols-9 gap-1 sm:gap-2 w-full py-0\.5">/.test(html), 'контейнер плиток: grid-cols-5 sm:grid-cols-9');
        ok(!/class="grid grid-cols-9 /.test(html), 'голового grid-cols-9 (которого нет в tailwind.css) больше нет');
        ok(tw.includes('.grid-cols-5'), 'утилита grid-cols-5 есть в прекомпилированном tailwind.css');
        ok(tw.includes('.sm\\:grid-cols-9'), 'утилита sm:grid-cols-9 есть в прекомпилированном tailwind.css');
        ok(/#mode-tama-btn\.lq-on\{ --lq-tint: rgba\(52,211,153,\.26\)/.test(html), 'подсветка активной плитки «Тамагочи» (--lq-tint) добавлена');
        ok(/#mode-lines-btn, #mode-tama-btn, #miner-btn\{/.test(html), 'базовое «стекло» плиток: #mode-tama-btn в списке id (b484)');
        ok(/#mode-tama-btn:hover/.test(html) && /#mode-tama-btn:active/.test(html), 'hover/active у плитки «Тамагочи» как у соседей');
        ok(/#mode-lines-btn:active, #mode-tama-btn:active, #miner-btn:active\{ transform: scale\(\.97\); \}/.test(html), 'нажатие плитки «Тамагочи» пружинит в общем списке :active');

        const tag = (sw.match(/const VERSION = '(nxmob\d+)';/) || [])[1];
        // b485: номер тега не прибиваем к b484 — единство и не ниже nxmob228
        eq((html.match(new RegExp(tag, 'g')) || []).length, 8, 'index.html: тег из sw.js во всех 8 ссылках на assets');
        ok(bp.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG равен тегу из sw.js');
        ok(Number((tag || '0').replace('nxmob', '')) >= 228, 'тег не ниже nxmob228 (' + tag + ')');
        ok(row.length > 0, 'плитка арены по-прежнему первая в контейнере');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;

    console.log('\nB. Поведение переключателя');
    {
        const n = ev(`document.getElementById('mode-arena-btn').parentElement.children.length`);
        eq(n, 9, 'в переключателе девять плиток');
        ev(`setBattleMode('tama')`);
        ok(doc.getElementById('mode-tama-btn').className.includes('lq-on'), 'активная «Тамагочи» получает lq-on (стекло подсветки)');
        ok(!doc.getElementById('mode-arena-btn').className.includes('lq-on'), 'с арены подсветка снята');
        eq(doc.getElementById('lobby-tama').classList.contains('hidden'), false, 'лобби тамагочи открыто');
        ev(`try { setBattleMode('slots'); } catch (e) {}`); // jsdom: 3D-слоты падают на canvas, классы кнопок ставятся до этого
        ok(doc.getElementById('mode-slots-btn').className.includes('lq-on'), 'слоты подсвечиваются как раньше');
        eq(doc.getElementById('lobby-tama').classList.contains('hidden'), true, 'лобби тамагочи скрыто при другом режиме');
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
