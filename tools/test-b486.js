/* b486: уведомления облака комнаты — только в Студии.

   Владелец (скриншот тоста посреди игры): «эти уведомление видны должны
   только в студии».

   A. Исходники: три информационных тоста облака («Опубликовано в комнату…»,
      «Возвращено в стандартный набор…», «Автопубликация выключена…») идут
      через nxOwnerToast; ошибки публикации (!quiet / гейты) остались
      showToast — молча оставлять ошибку нельзя; тег nxmob230 единый.
   B. Поведение (jsdom): nxOwnerToast молчит при закрытой Студии и показывает
      тост при открытой; обычный showToast работает всегда (регессия).

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b486.js
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
    const sc2 = w.document.createElement('script');
    sc2.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'qr-transfer.js'), 'utf8');
    w.document.body.appendChild(sc2);
    return { w, ev: s => w.eval(s), doc: w.document };
}

(async () => {
    console.log('A. Исходники и теги');
    {
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');

        ok(/nxOwnerToast\(\(quiet \? '☁️ ' : ''\) \+ 'Опубликовано в комнату '/.test(app), 'рапорт публикации — через nxOwnerToast');
        ok(!/showToast\(\(quiet \? '☁️ '/.test(app), 'старого showToast у рапорта публикации нет');
        ok(app.includes("nxOwnerToast('Возвращено в стандартный набор и опубликовано в комнату'"), 'возврат в стандартный набор — через nxOwnerToast');
        ok(app.includes("nxOwnerToast('⚠️ Автопубликация выключена"), 'подсказка про выключенную автопубликацию — через nxOwnerToast');
        ok(/if \(!quiet\) \{ showToast\('⛔ Сначала задайте логин и пароль комнаты/.test(app) || app.includes("if (!quiet) { showToast('⛔ Сначала задайте логин и пароль комнаты"), 'ошибки публикации остались громкими (!quiet)');
        ok(/if \(!quiet\) showToast\('Сначала введите код комнаты/.test(app) || app.includes("if (!quiet) showToast('Сначала введите код комнаты"), 'ошибка «нет комнаты» при ручном действии осталась громкой');

        const tag = (sw.match(/const VERSION = '(nxmob\d+)';/) || [])[1];
        // b487: номер тега не прибиваем к b486 — единство и не ниже nxmob230
        eq((html.match(new RegExp(tag, 'g')) || []).length, 8, 'index.html: тег из sw.js во всех 8 ссылках на assets');
        ok(bp.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG равен тегу из sw.js');
        ok(Number((tag || '0').replace('nxmob', '')) >= 230, 'тег не ниже nxmob230 (' + tag + ')');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;
    const toasts = () => doc.getElementById('toast-container').innerHTML;
    const clear = () => { doc.getElementById('toast-container').innerHTML = ''; };

    console.log('\nB. nxOwnerToast: молчит вне Студии, говорит в Студии');
    {
        // jsdom не считает offsetParent — даём вкладке честный «видимый» офсетParent
        ev(`Object.defineProperty(document.getElementById('tab-studio'), 'offsetParent', { configurable: true, get: function () { return this.classList.contains('hidden') ? null : document.body; } });`);
        clear();
        ev(`nxOwnerToast('проверка вне студии', 'success')`);
        eq(toasts().includes('проверка вне студии'), false, 'Студия закрыта — owner-тост не показан');
        clear();
        ev(`showToast('обычный тост', 'success')`);
        eq(toasts().includes('обычный тост'), true, 'обычный showToast работает всегда (регрессия)');
        clear();
        ev(`try { studioUnlocked = true; unlockHiddenTab(); } catch (e) {} switchTab('studio');`);
        eq(ev(`nxInStudio()`), true, 'Студия открыта — nxInStudio true');
        ev(`nxOwnerToast('рапорт из студии', 'success')`);
        eq(toasts().includes('рапорт из студии'), true, 'Студия открыта — owner-тост показан');
        ev(`switchTab('store');`);
        clear();
        ev(`nxOwnerToast('снова вне студии', 'success')`);
        eq(toasts().includes('снова вне студии'), false, 'ушли из Студии — owner-тост снова молчит');
    }

    console.log('\nC. Регрессии');
    {
        eq(ev(`typeof nxOwnerToast`), 'function', 'nxOwnerToast на месте');
        eq(ev(`typeof nxInStudio`), 'function', 'nxInStudio на месте');
        eq(ev(`typeof cloudPublishSoon`), 'function', 'автопубликация на месте');
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
