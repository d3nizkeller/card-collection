// test-b519: харнес-тест модуля «Скретч-лото» (b519) без браузера.
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
        globalCompositeOperation: '', fillStyle: '', font: '', textAlign: '',
        createLinearGradient() { return { addColorStop() {} }; },
        fillRect() {}, beginPath() {}, arc() {}, fill() {}, fillText() {},
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
    document: { getElementById(id) { if (!els[id]) els[id] = fakeEl(); return els[id]; } },
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
;globalThis.__x = { scratch, scratchBuy, scratchSetBet, scEraseAll, scReveal, scMakeTicket, renderScratchUI, SC_P_CELL, SC_JP_P };`, sandbox);
const X = sandbox.__x;

let fails = 0;
function ok(cond, msg) { if (cond) console.log('  ok:', msg); else { fails++; console.error('  FAIL:', msg); } }

// 1) структура билета
for (let i = 0; i < 200; i++) {
    const t = X.scMakeTicket();
    let bad = false;
    if (new Set(t.winNums).size !== 4) bad = true;
    t.winNums.forEach(v => { if (v < 1 || v > 30) bad = true; });
    if (t.cells.length !== 12) bad = true;
    t.cells.forEach(c => {
        if (c.jkp) { if (t.winNums.indexOf(c.num) < 0) bad = true; }
        else if (c.mult > 0) { if (t.winNums.indexOf(c.num) < 0) bad = true; }
        else if (t.winNums.indexOf(c.num) >= 0) bad = true; // пустышка не должна совпадать
        if (c.num < 1 || c.num > 30) bad = true;
    });
    if (bad) { fails++; console.error('  FAIL: билет невалиден', JSON.stringify(t)); break; }
}
ok(true, '200 билетов: 4 выигрышных числа, совпадения только у призовых/JKP');

// 2) покупка: списание ставки и состояние
sandbox.state.coins = 100000000;
X.scratchSetBet(2000);
const before = sandbox.state.coins;
X.scratchBuy();
ok(sandbox.state.coins === before - 2000, 'ставка списана при покупке');
ok(!!X.scratch.ticket && X.scratch.revealed.length === 16, 'билет и 16 закрытых клеток');
ok(X.scratch.done === false, 'билет не разыгран');

// 3) вскрытие всех клеток: выплата по множителям
let expect = 0;
X.scratch.ticket.cells.forEach(c => { if (!c.jkp && c.mult > 0) expect += Math.floor(2000 * c.mult); });
X.scEraseAll();
ok(X.scratch.revealed.every(Boolean), 'все клетки вскрыты «Стереть всё»');
ok(X.scratch.done === true, 'билет разыгран после полного вскрытия');
ok(X.scratch.win === expect, 'выигрыш = сумма множителей (' + X.scratch.win + ' / ' + expect + ')');
ok(sandbox.state.coins === before - 2000 + expect, 'баланс сошёлся');

// 4) золотая клетка JKP срывает джекпот
sandbox.__jp = 5000;
sandbox.state.coins = 100000000;
const b2 = sandbox.state.coins;
X.scratchSetBet(1000);
X.scratchBuy();
X.scratch.ticket.cells.forEach((c, idx) => { if (idx !== 3) c.jkp = false; });
X.scratch.ticket.cells[3] = { num: X.scratch.ticket.winNums[0], mult: 0, sym: 'fa-crown', jkp: true };
X.scEraseAll();
ok(X.scratch.win >= 5000, 'JKP-клетка принесла джекпот (' + X.scratch.win + ')');
ok(sandbox.state.coins === b2 - 1000 + X.scratch.win, 'баланс с джекпотом сошёлся');
sandbox.__jp = 0;

// 5) повторная покупка после розыгрыша
X.scratchBuy();
ok(X.scratch.done === false && !!X.scratch.ticket, 'после розыгрыша можно купить новый билет');

console.log(fails ? ('\nFAILS: ' + fails) : '\nALL TESTS PASSED');
process.exit(fails ? 1 : 0);
