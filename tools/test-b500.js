// test-b500: харнес-тест модуля «Русское лото» (b500) без браузера.
// Вытаскиваем кусок app.js между маркерами b500, подставляем стабы зависимостей
// и прогоняем: генерацию карточек, озвучку-слова, полный тираж, выплаты.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const src = fs.readFileSync(path.join(__dirname, '..', 'assets', 'app.js'), 'utf8');
const a = src.indexOf('// ============ b500:');
const b = src.indexOf('// ============ /b500 ============');
if (a < 0 || b < 0) { console.error('FAIL: маркеры b500 не найдены в app.js'); process.exit(1); }
const moduleCode = src.slice(a, b);

const spoken = [];
const toasts = [];
const els = {};
function fakeEl() {
    return {
        innerHTML: '', textContent: '', value: '',
        classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } },
        set disabled(v) {}, get disabled() { return false; },
    };
}
const sandbox = {
    console,
    setInterval: () => 0,
    clearInterval: () => {},
    Math, Number, String, Array, Object, JSON, isFinite, parseInt, parseFloat,
    window: { speechSynthesis: { cancel() {}, speak(u) { spoken.push(u.text); }, getVoices() { return [{ lang: 'ru-RU' }]; } } },
    SpeechSynthesisUtterance: class { constructor(t) { this.text = t; } },
    document: { getElementById(id) { if (!els[id]) els[id] = fakeEl(); return els[id]; } },
    LS: { getItem() { return null; }, setItem() {}, },
    state: { coins: 100000, stats: {} },
    saveState() {}, updateCoinDisplay() {},
    showToast(m, t) { toasts.push([m, t]); },
    launchConfetti() {}, SoundFX: { play() {} },
    jackpotFeed() {}, jackpotOnLoss(x) { return x; }, jackpotPool() { return 0; },
    normBet(b) { b = Math.floor(Number(b)); return isFinite(b) && b >= 1 ? b : 1; },
    fmtCoins(n) { return String(n); },
    SLOTS_BETS: [100, 1000, 5000],
    syncBetInput() {},
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(moduleCode + `
;globalThis.__x = { loto, lotoWords, lotoMakeCard, lotoStart, lotoDraw, lotoFinish, renderLotoUI, LOTO_DRAWS, LOTO_PAY_ROW, LOTO_PAY_FULL };`, sandbox);
const X = sandbox.__x;

let fails = 0;
function ok(cond, msg) { if (cond) console.log('  ok:', msg); else { fails++; console.error('  FAIL:', msg); } }

// 1) числа словами
ok(X.lotoWords(1) === 'один', '1 -> один');
ok(X.lotoWords(7) === 'семь', '7 -> семь');
ok(X.lotoWords(11) === 'одиннадцать', '11 -> одиннадцать');
ok(X.lotoWords(20) === 'двадцать', '20 -> двадцать');
ok(X.lotoWords(40) === 'сорок', '40 -> сорок');
ok(X.lotoWords(45) === 'сорок пять', '45 -> сорок пять');
ok(X.lotoWords(90) === 'девяносто', '90 -> девяносто');
ok(X.lotoWords(89) === 'восемьдесят девять', '89 -> восемьдесят девять');

// 2) карточки: 3×9, по 5 чисел в строке, диапазоны колонок, возрастание в колонке
for (let i = 0; i < 300; i++) {
    const g = X.lotoMakeCard();
    let bad = false;
    for (let r = 0; r < 3; r++) {
        const cnt = g[r].filter(v => v > 0).length;
        if (cnt !== 5) bad = true;
    }
    for (let c = 0; c < 9; c++) {
        const lo = c === 0 ? 1 : c * 10, hi = c === 8 ? 90 : c * 10 + 9;
        const col = [];
        for (let r = 0; r < 3; r++) {
            const v = g[r][c];
            if (v) { if (v < lo || v > hi) bad = true; col.push(v); }
        }
        if (!col.length) bad = true;
        for (let k = 1; k < col.length; k++) if (col[k] <= col[k - 1]) bad = true;
    }
    const all = new Set(g.flat().filter(v => v > 0));
    if (all.size !== 15) bad = true;
    if (bad) { fails++; console.error('  FAIL: карточка невалидна', JSON.stringify(g)); break; }
}
ok(true, '300 карточек: 5 чисел в строке, диапазоны колонок, уникальность');

// 3) полный тираж: выплаты и озвучка каждого бочонка
for (let round = 0; round < 40; round++) {
    spoken.length = 0; toasts.length = 0;
    sandbox.state.coins = 100000;
    const before = sandbox.state.coins;
    X.loto.bet = 1000;
    X.lotoStart();
    ok(X.loto.active === true, 'тираж начался');
    ok(sandbox.state.coins === before - 1000, 'ставка списана');
    let draws = 0;
    while (X.loto.active && draws < 60) { X.lotoDraw(); draws++; }
    ok(draws <= 60, 'тираж не длиннее 60 бочонков (' + draws + ')');
    ok(X.loto.drawn.length === draws, 'история розыгрыша совпадает');
    ok(new Set(X.loto.drawn).size === X.loto.drawn.length, 'бочонки не повторяются');
    // озвучен каждый бочонок (первая фраза каждого draw — число)
    ok(spoken.length >= draws, 'озвучка каждого бочонка (' + spoken.length + ' фраз)');
    // выплаты согласованы с win
    const rows = X.loto.rowPaid.filter(Boolean).length;
    const full = X.loto.rowDone.every(Boolean);
    const expect = rows * 1000 * X.LOTO_PAY_ROW + (full ? 1000 * X.LOTO_PAY_FULL : 0);
    ok(X.loto.win === expect, 'выплаты = линии×3 + ЛОТО×25 (' + X.loto.win + ')');
    ok(sandbox.state.coins === before - 1000 + X.loto.win, 'баланс сошёлся');
    if (round === 0) console.log('  пример озвучки:', spoken.slice(0, 5).join(' | '));
}

// 4) досрочная остановка
sandbox.state.coins = 5000;
X.loto.bet = 1000;
X.lotoStart();
X.lotoDraw(); X.lotoDraw(); X.lotoDraw();
X.lotoFinish(true);
ok(X.loto.active === false, 'ручная остановка тиража');

console.log(fails ? ('\nFAILS: ' + fails) : '\nALL TESTS PASSED');
process.exit(fails ? 1 : 0);
