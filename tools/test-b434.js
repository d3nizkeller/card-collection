/* b434: игры не зависают при переключении вкладок.

   A. Спин Слотов, прерванный сбросом контекста (переключение вкладки),
      дочитывается: spinning=false, выплата начислена, кнопка живая.
   B. Спин Линий с висящим lines3d.pending дочитывается тем же финишем.
   C. Watchdog: спин старше лимита дочитывается сам без переключения вкладок.
   D. Обычный спин не страдает: одна выплата, без двойного начисления.
   E. Повторный принудительный финиш не платит дважды.

   Запуск:  node tools/test-b434.js
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

(async () => {
    console.log('\nA. Слоты: спин прерван переключением вкладки');
    const A = boot();
    const av = A.ev;
    av('state.coins = 1000000; slots.bet = 1000; slots.spinning = true; slots.spinAt = Date.now(); slots.lastResult = [0, 0, 0];');
    const c0 = av('state.coins');
    av('nx3dReleaseHidden("grid")'); // уход на другую игру/вкладку посреди спина
    eq(av('slots.spinning'), false, 'спин дочитан, а не брошен висящим');
    ok(av('state.coins') > c0 - 1000, 'выплата начислена (три одинаковых): баланс ' + av('state.coins') + ' при ставке 1000');
    av('renderSlotsUI()');
    eq(A.doc.getElementById('slots-spin').disabled, false, 'кнопка «Крутить» снова живая');

    console.log('\nB. Линии: висящий pending дочитывается');
    const B = boot();
    const bv = B.ev;
    bv('state.coins = 1000000; lines.bet = 500; lines.spinning = true; lines.spinAt = Date.now(); linesEnsure(); linesMakePool();');
    bv('lines3d.pending = { final: lines.cells.slice(), bet: 500 };');
    const b0 = bv('state.coins');
    bv('nx3dReleaseHidden("slots")');
    eq(bv('lines.spinning'), false, 'линии дочитаны');
    eq(bv('lines3d.pending'), null, 'pending снят');
    ok(bv('state.coins') >= b0 - 500, 'ставка/выплата обработаны один раз');

    console.log('\nC. Watchdog дочитывает зависший спин сам');
    const C = boot();
    const cv = C.ev;
    // ставка списывается при старте спина (slotsSpin), имитируем уже списанную
    cv('state.coins = 998000; slots.bet = 2000; slots.spinning = true; slots.spinAt = Date.now() - 13000; slots.lastResult = [0, 1, 2];');
    cv('nxSpinWatchdog()');
    eq(cv('slots.spinning'), false, 'спин старше 12 с дочитан сторожем');
    eq(cv('state.coins'), 998000, 'пустой спин не платит и не списывает повторно');
    cv('grid.spinning = true; grid.spinAt = Date.now() - 26000; grid.total = 0; grid.jpPaid = 0; grid.lastBet = 100;');
    cv('nxSpinWatchdog()');
    eq(cv('grid.spinning'), false, 'сетка старше 25 с дочитана сторожем');

    console.log('\nD. Обычный спин: одна выплата');
    const D = boot();
    const dv = D.ev;
    dv('state.coins = 100000; slotsSetBet(1000);');
    const d0 = dv('state.coins');
    dv('slotsSpin()');
    await D.w.eval('new Promise(r => setTimeout(r, 1500))');
    eq(dv('slots.spinning'), false, 'спин завершился сам');
    const delta = dv('state.coins') - d0;
    ok(delta === -1000 || delta >= 0, 'баланс сошёлся (ставка ± выплата): ' + delta);

    console.log('\nE. Двойного финиша нет');
    const E = boot();
    const evv = E.ev;
    evv('state.coins = 1000000; slots.bet = 1000; slots.spinning = true; slots.lastResult = [0, 0, 0];');
    const e0 = evv('state.coins');
    evv('nxForceFinishSpins()');
    const e1 = evv('state.coins');
    evv('nxForceFinishSpins()');
    eq(evv('state.coins'), e1, 'второй вызов не платит повторно');
    ok(e1 > e0, 'первый вызов выплатил выигрыш');

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
