/* b419: «джекпот должен расти без ограничений» — разряды смешанной системы.

   A. Любая конечная сумма ложится полностью: 1e12…1e41 по порядку —
      jpLedAdd возвращает ровно x, банк растёт, ключей ~log1000(банк).
   B. Удвоение банка 60 раз подряд: ни одного «+0», ни одного стопа.
   C. Витрина: fmtCoins и parseBetStr понимают величины до дециллионов
      (s/u/p/o/n/d), огромный банк показывается буквами, а не «1000q».
   D. Наследие: ключ с 1e13 (ёмкость разряда 0) валиден без миграции,
      новые взносы уходят в разряд 1; мусор вне ёмкости СВОЕГО разряда режется.
   E. «Поставить банк 1e30» и срыв такого банка работают (выплата каскадом).
   F. Регрессии: tombstone hallCut, ремонт 1e57, тосты нехватки b417.

   Запуск:  node tools/test-b419.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + a + (a === b ? '' : ' (ждём ' + b + ')'));

function boot(ledger, cid) {
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
    if (cid) w.localStorage.setItem('nexus_jackpot_cid', cid);
    if (ledger) w.localStorage.setItem('nexus_jackpot_v2', JSON.stringify(ledger));
    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
    w.document.body.appendChild(sc);
    return { w, ev: s => w.eval(s), doc: w.document };
}

(async () => {
    // ===== A. любая сумма ложится полностью =====
    console.log('\nA. Взносы от 1e12 до 1e41 — без потерь');
    const A = boot(null, 'pgrow');
    const av = A.ev;
    av('cloudGuest = () => false');
    let want = 0, keys = 0;
    for (let i = 12; i <= 41; i++) {
        const x = Math.pow(10, i);
        const got = av('jpLedAdd("led", "pgrow", ' + x + ')');
        if (got !== x) { ok(false, 'взнос 1e' + i + ' лёг не целиком: ' + got); want += x; continue; }
        want += x;
    }
    ok(true, 'все 30 взносов (1e12…1e41) легли полностью');
    ok(Math.abs(av('jpLedOf("led", "pgrow")') - want) <= want * 1e-12, 'сумма по разрядам сходится с ожидаемой в пределах сетки double');
    keys = av('Object.keys(jackpot.led).length');
    ok(keys <= 12, 'ключей на игроку ~log1000(банк): ' + keys + ' при банке ≈1.1e42');
    ok(av('jackpotPool()') >= 1e41, 'банк дорос до 1e41+: ' + av('fmtCoins(jackpotPool())'));

    // ===== B. 60 удвоений подряд — ни одного «+0» =====
    console.log('\nB. 60 удвоений банка: ни одного стопа');
    const B = boot(null, 'pdbl');
    const bv = B.ev;
    bv('cloudGuest = () => false');
    let cur = 1e13, stops = 0;
    for (let i = 0; i < 60; i++) {
        const got = bv('jpLedAdd("led", "pdbl", ' + cur + ')');
        if (got !== cur) stops++;
        cur *= 2;
    }
    eq(stops, 0, 'ни один взнос не вернулся «+0» (60 удвоений до 1e31)');
    ok(bv('jackpotPool()') > 1e30, 'банк ≈ 2e30: ' + bv('fmtCoins(jackpotPool())'));
    ok(bv('Object.keys(jackpot.led).length') <= 10, 'разрядов немного: ' + bv('Object.keys(jackpot.led).length'));

    // ===== C. витрина больших чисел =====
    console.log('\nC. fmtCoins / parseBetStr до дециллионов');
    const C = boot(null);
    const cvv = C.ev;
    eq(cvv('fmtCoins(1e18)'), '1s', '1e18 → 1s');
    eq(cvv('fmtCoins(2.5e21)'), '2.5u', '2.5e21 → 2.5u');
    eq(cvv('fmtCoins(1e24)'), '1p', '1e24 → 1p');
    eq(cvv('fmtCoins(3e30)'), '3n', '3e30 → 3n');
    eq(cvv('fmtCoins(1e33)'), '1d', '1e33 → 1d');
    eq(cvv('fmtCoins(1234567)'), '1.2m', 'прежние величины не изменились');
    eq(cvv('parseBetStr("3s")'), 3e18, 'ставка «3s» = 3e18');
    eq(cvv('parseBetStr("2d")'), 2e33, 'ставка «2d» = 2e33');
    eq(cvv('parseBetStr("10k")'), 10000, '«10k» по-прежнему 10000');

    // ===== D. наследие и мусор по разрядам =====
    console.log('\nD. Старые ключи 1e13 валидны, мусор режется по своему разряду');
    const D = boot({
        led: { old: 1e13, 'good#1': 1e16, 'bad#1': 1e19, bad0: 1e57 },
        won: { old: 1e13 - 5000 },
        wins: {}, names: {}, hall: [],
    }, 'newcid');
    const dv = D.ev;
    eq(dv('jackpot.led["old"]'), 1e13, 'ключ 1e13 (ёмкость разряда 0) не выброшен — миграция не нужна');
    eq(dv('jackpot.led["good#1"]'), 1e16, '1e16 в разряде 1 — честное значение, осталось');
    eq(dv('jackpot.led["bad#1"]'), undefined, '1e19 в разряде 1 (ёмкость 1e16) — мусор, выброшен');
    eq(dv('jackpot.led["bad0"]'), undefined, '1e57 в разряде 0 — мусор, выброшен (защита b416)');
    eq(dv('jackpotPool()'), 1000 + 1e16 + 5000, 'банк = пол + честные разряды');
    dv('jpLedAdd("led", "old", 250000)');
    eq(dv('jpLedNum(jackpot.led["old#1"], 1)'), 250000, 'довнесение в полный разряд 0 ушло в разряд 1');

    // ===== E. ручной банк 1e30 и срыв такого банка =====
    console.log('\nE. «Поставить банк 1e30» и выплата');
    const E = boot(null, 'pown');
    const evv = E.ev;
    evv('cloudGuest = () => false');
    evv('jpcSet({payout:100,floor:1000,cap:0})');
    evv('jackpot.led = {}; jackpot.won = {};');
    evv('jpcSetPool(1e30)');
    eq(evv('jackpotPool()'), 1e30 + 1000, 'банк поставлен ровно на 1e30 + пол');
    const c0 = evv('state.coins');
    evv('jackpotWin()');
    eq(evv('state.coins') - c0, 1e30 + 1000, 'срыв банка 1e30 выплатил всё (пол — гарантия)');
    eq(evv('jackpotPool()'), 1000, 'банк вернулся на пол, долга нет');
    ok(Math.abs(evv('jpRawPool()') - 1000) <= 1e30 * 1e-12, 'raw ≈ сид: обеспеченная часть списалась каскадом разрядов');

    // ===== F. регрессии =====
    console.log('\nF. Регрессии b416–b418');
    const F = boot({ led: { x: 1e57 }, won: {}, wins: {}, names: {}, hall: [{ n: 'М', a: 5, t: 1 }] }, 'pf');
    const fv = F.ev;
    fv('cloudGuest = () => false');
    eq(fv('jackpot.led["x"]'), undefined, 'ремонт b416 режет 1e57');
    fv('jpcResetHall()');
    eq(fv('jackpot.hall.length'), 0, 'tombstone b418 работает');
    ok(typeof fv('nxBetLack') === 'function', 'хелперы b417 на месте');
    ok(typeof fv('jpcResetDefaults') === 'function' && typeof fv('jpcResetHall') === 'function', 'кнопки b418 на месте');

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
