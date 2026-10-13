/* b417: «кнопки зависают» — disabled из-за нехватки монет больше не молчит.

   До b417 при state.coins < bet кнопка ставки получала disabled: клик не
   доходил до обработчика, тост «Недостаточно монет» не показывался — кнопка
   выгляdead мертвой («зависла»). Проверяем в jsdom:

   A. Нехватка монет: кнопка НЕ disabled, гаснет визуально (opacity-40),
      клик доходит до обработчика и даёт тост с подсказкой;
      баланс и ставка при этом не меняются, спин не стартует.
   B. Баланс ниже минимальной ставки (100): тост отправляет в Шахту/задания.
   C. Хватает монет: клик стартует спин; во время спина кнопка disabled
      (защита от двойного списания).
   D. То же для Сетки, Колеса, Мин и Линий.
   E. Регрессия b416: банк по-прежнему растёт, ремонт идемпотентен.

   Запуск:  node tools/test-b417.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + a + (a === b ? '' : ' (ждём ' + b + ')'));

function boot(coins) {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const dom = new JSDOM(html, {
        runScripts: 'dangerously',
        pretendToBeVisual: true,
        url: 'https://d3nizkeller.github.io/card-collection/',
    });
    const w = dom.window;
    const ctx2d = () => new Proxy({}, {
        get(t, k) {
            if (k === 'canvas') return { width: 256, height: 256, style: {} };
            if (k === 'measureText') return () => ({ width: 10 });
            if (k === 'getImageData') return () => ({ data: new Uint8ClampedArray(4) });
            if (k === 'createLinearGradient' || k === 'createRadialGradient') return () => ({ addColorStop() {} });
            if (k === 'createPattern') return () => null;
            return t[k] !== undefined ? t[k] : (() => {});
        },
        set(t, k, v) { t[k] = v; return true; },
    });
    w.HTMLCanvasElement.prototype.getContext = kind => (kind === '2d' ? ctx2d() : null);
    w.HTMLCanvasElement.prototype.toDataURL = () => 'data:image/png;base64,';
    w.HTMLMediaElement.prototype.play = function () { return Promise.resolve(); };
    w.HTMLMediaElement.prototype.pause = function () {};
    w.HTMLMediaElement.prototype.load = function () {};
    Object.defineProperty(w, 'fetch', {
        value: () => Promise.resolve({ ok: false, status: 0, text: () => Promise.resolve(''), json: () => Promise.resolve(null) }),
        configurable: true,
    });
    w.navigator.sendBeacon = () => true;
    w.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} };
    w.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
    w.matchMedia = w.matchMedia || (q => ({ matches: false, media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }));
    w.THREE = new Proxy({}, { get: () => function () { return {}; } });
    w.localStorage.setItem('nexus_coins', String(coins));
    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
    w.document.body.appendChild(sc);
    return { w, ev: s => w.eval(s), doc: w.document };
}

const toasts = doc => Array.from((doc.getElementById('toast-container') || { children: [] }).children)
    .map(t => t.textContent).join(' | ');

(async () => {
    // ================= A. не хватает монет =================
    console.log('\nA. Баланс 5m, ставка 10m (сценарий со скриншота владельца)');
    const G = boot(5000000);
    const ev = G.ev;
    ev('slotsSetBet(10000000); renderSlotsUI()');
    const btn = G.doc.getElementById('slots-spin');
    eq(btn.disabled, false, 'кнопка «Крутить» НЕ disabled (раньше — disabled и молчала)');
    ok(btn.classList.contains('opacity-40'), 'визуально погашена (opacity-40) — состояние читается');
    const coins0 = ev('state.coins'), spins0 = ev('state.stats.slotsSpins || 0');
    btn.click(); // настоящий клик, как палец игрока
    const t = toasts(G.doc);
    ok(/Недостаточно монет для ставки 10m/.test(t), 'тап дал тост: ' + (t.match(/Недостаточно монет[^|]*/) || ['?'])[0].trim());
    ok(/сни-?зьте ставку|кнопкой «−»/.test(t), 'в тосте есть выход: снизить ставку');
    eq(ev('state.coins'), coins0, 'баланс не тронут');
    eq(ev('state.stats.slotsSpins || 0'), spins0, 'спин не стартовал');
    eq(ev('slots.spinning'), false, 'спин не висит');
    // шаг ставки вниз работает и оживляет кнопку
    ev("stepBet('slots', -1); renderSlotsUI()");
    eq(ev('slots.bet'), 5000000, 'кнопка «−» снизила ставку до 5m');
    eq(G.doc.getElementById('slots-spin').classList.contains('opacity-40'), false, 'кнопка ожила: ставка по балансу');
    ok(!/мало/.test(G.doc.getElementById('slots-spin').textContent), 'подпись «мало» ушла вместе с нехваткой');
    btn.click();
    ok(ev('slots.spinning') === true || ev('state.stats.slotsSpins || 0') > spins0, 'спин по сниженной ставке запускается');

    // ================= B. баланс ниже минимальной ставки =================
    console.log('\nB. Баланс 0: тост отправляет за монетами');
    const Z = boot(0);
    Z.ev('state.coins = 0; updateCoinDisplay();'); // стартовый бонус игры убираем вручную
    Z.ev('slotsSetBet(10000000); renderSlotsUI()');
    Z.doc.getElementById('slots-spin').click();
    const tz = toasts(Z.doc);
    ok(/Монеты кончились/.test(tz) && /Шахта/.test(tz) && /задания дня/.test(tz), 'тост: ' + (tz.match(/Недостаточно[^|]*/) || ['?'])[0].trim());
    ok(Z.doc.getElementById('slots-spin').disabled === false, 'кнопка кликабельна (игрок может узнать причину)');

    // ================= C. хватает монет: спин и disabled во время спина =================
    console.log('\nC. Баланс 24t, ставка 10m');
    const R = boot(24000000000000);
    R.ev('slotsSetBet(10000000); renderSlotsUI()');
    const rb = R.doc.getElementById('slots-spin');
    eq(rb.disabled, false, 'кнопка живая');
    rb.click();
    const busy = R.ev('slots.spinning');
    ok(busy === true || R.ev('state.stats.slotsSpins || 0') > 0, 'спин стартовал');
    if (busy) {
        R.ev('renderSlotsUI()');
        eq(R.doc.getElementById('slots-spin').disabled, true, 'во время спина кнопка disabled (двойное списание невозможно)');
        await R.w.eval('new Promise(r => setTimeout(r, 1500))');
        eq(R.ev('slots.spinning'), false, 'спин завершился, кнопка отпущена');
        eq(R.doc.getElementById('slots-spin').disabled, false, 'после спина кнопка снова живая');
    }

    // ================= D. остальные игры =================
    console.log('\nD. Сетка / Колесо / Мины / Линии при нехватке монет');
    const D = boot(5000000);
    const dv = D.ev;
    const cases = [
        ['grid', 'gridSetBet(10000000); renderGridUI()', 'grid-spin', 'gridSpin()', 'grid.spinning'],
        ['wheel', 'wheelSetBet(10000000); renderWheelUI()', 'wheel-spin', 'wheelSpin()', 'wheel.spinning'],
        ['mines', 'minesSetBet(10000000)', 'mines-start', 'minesStart()', 'mines.active'],
        ['lines', 'linesSetBet(10000000); renderLinesUI()', 'lines-spin', 'linesSpin()', 'lines.spinning'],
    ];
    for (const [name, setup, id, call, busyExpr] of cases) {
        let err = '';
        try { dv(setup); } catch (e) { err = e.message; }
        const b = D.doc.getElementById(id);
        if (!b) { ok(false, name + ': кнопка #' + id + ' не найдена'); continue; }
        ok(!err && b.disabled === false, name + ': кнопка не disabled при нехватке монет' + (err ? ' (' + err + ')' : ''));
        try { dv(call); } catch (e) { err = e.message; }
        const tt = toasts(D.doc);
        ok(/Недостаточно монет/.test(tt), name + ': обработчик объяснил причину');
        ok(/сни-?зьте ставку|Монеты кончились|кнопкой «−»/.test(tt), name + ': в тосте подсказка');
        eq(dv(busyExpr), false, name + ': ничего не зависло в состоянии спина');
    }

    // ================= E. регрессия b416 =================
    console.log('\nE. Регрессия b416: банк растёт, ремонт идемпотентен');
    const B = boot(1000000);
    const bv = B.ev;
    bv('jackpot.led = {}; jackpot.won = {};');
    const p0 = bv('jackpotPool()');
    for (let i = 0; i < 10; i++) bv('jackpotFeed(10000)');
    eq(bv('jackpotPool()') - p0, 100000, '10 ставок по 10k → банк +100k');
    eq(bv('jpRepairLedger()'), 0, 'ремонт реестра: чинить нечего');
    ok(bv('JP_LED_CAP') === 1e13, 'потолок счётчика на месте');

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
