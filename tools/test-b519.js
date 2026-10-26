// test-b519: харнес-тест модуля «Скретч-лото» (b519/b525, мультибилетный) без браузера.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const src = fs.readFileSync(path.join(__dirname, '..', 'assets', 'app.js'), 'utf8');
const a = src.indexOf('// ============ b519:');
const b = src.indexOf('// ============ /b519 ============');
if (a < 0 || b < 0) { console.error('FAIL: маркеры b519 не найдены в app.js'); process.exit(1); }
const moduleCode = src.slice(a, b);

const toasts = [];
const els = {};
function fakeCtx() {
    return {
        globalCompositeOperation: '', fillStyle: '', font: '', textAlign: '', letterSpacing: '',
        createLinearGradient() { return { addColorStop() {} }; },
        createRadialGradient() { return { addColorStop() {} }; },
        fillRect() {}, beginPath() {}, arc() {}, fill() {}, fillText() {}, closePath() {}, moveTo() {}, lineTo() {},
        getImageData(x, y, w, h) { return { data: new Uint8ClampedArray(w * h * 4) }; },
    };
}
function fakeEl() {
    return {
        innerHTML: '', textContent: '', value: '', style: {},
        classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } },
        set disabled(v) {}, get disabled() { return false; },
        getContext() { return fakeCtx(); },
        getBoundingClientRect() { return { width: 96, height: 96, left: 0, top: 0 }; },
        width: 96, height: 96,
    };
}
const sandbox = {
    console, Uint8ClampedArray, Math, Number, String, Array, Object, JSON, isFinite, parseInt, parseFloat,
    setInterval: () => 0, clearInterval: () => {},
    window: { addEventListener() {}, speechSynthesis: { cancel() {}, speak() {}, getVoices() { return []; } } },
    SpeechSynthesisUtterance: class { constructor(t) { this.text = t; } },
    document: {
        getElementById(id) { if (!els[id]) els[id] = fakeEl(); return els[id]; },
        querySelectorAll() { return []; },
    },
    LS: { getItem() { return null; }, setItem() {} },
    state: { coins: 100000000, stats: {} },
    saveState() {}, updateCoinDisplay() {},
    showToast(m, t) { toasts.push([m, t]); },
    launchConfetti() {}, SoundFX: { play() {} },
    jackpotFeed() {}, jackpotOnLoss(x) { return x; }, jackpotPool() { return 12345; },
    jackpotWin() { const p = sandbox.__jp || 0; sandbox.state.coins += p; return p; },
    jpcOff() { return false; }, jpcPityNote() {},
    normBet(b) { b = Math.floor(Number(b)); return isFinite(b) && b >= 1 ? b : 1; },
    fmtCoins(n) { return String(n); },
    syncBetInput() {},
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(moduleCode + `
;globalThis.__x = { scratch, scratchBuy, scratchSetBet, scSetCount, scEraseAll, scReveal, scMakeTicket, scActive, renderScratchUI, SC_MAX_TICKETS };`, sandbox);
const X = sandbox.__x;

let fails = 0;
function ok(cond, msg) { if (cond) console.log('  ok:', msg); else { fails++; console.error('  FAIL:', msg); } }

// 1) структура билета
for (let i = 0; i < 200; i++) {
    const t = X.scMakeTicket();
    let bad = false;
    if (new Set(t.winNums).size !== 4) bad = true;
    if (t.cells.length !== 12 || t.revealed.length !== 16) bad = true;
    t.cells.forEach(c => {
        if (c.jkp) { if (t.winNums.indexOf(c.num) < 0) bad = true; }
        else if (c.mult > 0) { if (t.winNums.indexOf(c.num) < 0) bad = true; }
        else if (t.winNums.indexOf(c.num) >= 0) bad = true;
    });
    if (bad) { fails++; console.error('  FAIL: билет невалиден', JSON.stringify(t)); break; }
}
ok(true, '200 билетов: 4 выигрышных числа, совпадения только у призовых/JKP');

// 2) b525: выбор числа билетов и зажимы
X.scSetCount(4); ok(X.scratch.count === 4, 'выбор 4 билетов');
X.scSetCount(9); ok(X.scratch.count === X.SC_MAX_TICKETS, 'зажим сверху до 4');
X.scSetCount(0); ok(X.scratch.count === 1, 'зажим снизу до 1');

// 3) покупка 2 билетов: списание двойной ставки
X.scSetCount(2);
X.scratchSetBet(2000);
sandbox.state.coins = 100000000;
const before = sandbox.state.coins;
X.scratchBuy();
ok(scratch_tickets_len() === 2, 'куплено 2 билета');
ok(sandbox.state.coins === before - 4000, 'списано ставка×2');
ok(X.scActive() === true, 'пока есть невскрытые — покупка заблокирована');
X.scSetCount(4);
ok(X.scratch.count === 2, 'смена числа билетов во время игры заблокирована');

// 4) полное вскрытие: независимый расчёт каждого билета
let expect = 0;
X.scratch.tickets.forEach(T => T.cells.forEach(c => { if (!c.jkp && c.mult > 0) expect += Math.floor(2000 * c.mult); }));
X.scEraseAll();
ok(X.scratch.tickets.every(T => T.done), 'оба билета разыграны');
const totalWin = X.scratch.tickets.reduce((s, T) => s + T.win, 0);
ok(totalWin === expect, 'выигрыш = сумма по билетам (' + totalWin + ')');
ok(sandbox.state.coins === before - 4000 + expect, 'баланс сошёлся');
ok(X.scActive() === false, 'после розыгрыша можно покупать снова');

// 5) JKP-клетка срывает джекпот
sandbox.__jp = 5000;
sandbox.state.coins = 100000000;
const b2 = sandbox.state.coins;
X.scSetCount(1);
X.scratchSetBet(1000);
X.scratchBuy();
const T0 = X.scratch.tickets[0];
T0.cells.forEach((c, idx) => { if (idx !== 3) c.jkp = false; });
T0.cells[3] = { num: T0.winNums[0], mult: 0, sym: 'fa-crown', jkp: true };
X.scEraseAll();
ok(T0.win >= 5000, 'JKP-клетка принесла джекпот (' + T0.win + ')');
ok(sandbox.state.coins === b2 - 1000 + T0.win, 'баланс с джекпотом сошёлся');
sandbox.__jp = 0;

// 6) вскрытие одной клетки через scReveal(t,i)
X.scratchBuy();
X.scReveal(0, 0);
ok(X.scratch.tickets[0].revealed[0] === true, 'scReveal(0,0) вскрыл клетку');
ok(X.scratch.tickets[0].done === false, 'билет ещё не разыгран');

// 7) b526: расшифровка совпадений и поясняющий блок
sandbox.state.coins = 100000000;
X.scSetCount(1);
X.scratchSetBet(1000);
X.scratchBuy();
const TW = X.scratch.tickets[0];
TW.cells[0] = { num: TW.winNums[0], mult: 2, sym: 'fa-star', jkp: false };
X.scEraseAll();
ok(typeof TW.explain === 'string' && TW.explain.indexOf('число ' + TW.winNums[0]) >= 0, 'расшифровка: «число N → +X» (' + TW.explain + ')');
ok(els['sc-legend'].innerHTML.indexOf('Как читать') >= 0, 'поясняющий блок показан при выигрыше');
ok(els['sc-result'].innerHTML.indexOf('Билет 1:') >= 0, 'в итоге есть расшифровка по билетам');

// 8) b529: золотая клетка управляется из Студии (scJpRoll)
X.scEraseAll(); // дорозыгрыш активного билета из предыдущего теста
sandbox.__jpPct = 100;
sandbox.state.coins = 100000000;
X.scSetCount(2);
X.scratchSetBet(100);
X.scratchBuy();
ok(X.scratch.tickets.every(T => T.cells.some(c => c.jkp)), 'шанс 100%: золотая клетка в каждом билете');
sandbox.__jpPct = 0;
X.scratchBuy();
ok(X.scratch.tickets.every(T => !T.cells.some(c => c.jkp)), 'шанс 0%: золотых клеток нет');
sandbox.__jpPct = 0;

function scratch_tickets_len() { return X.scratch.tickets.length; }

console.log(fails ? ('\nFAILS: ' + fails) : '\nALL TESTS PASSED');
process.exit(fails ? 1 : 0);
