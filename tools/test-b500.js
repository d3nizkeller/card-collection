// test-b500: харнес-тест модуля «Русское лото» (b500/b505) без браузера.
// Вытаскиваем кусок app.js между маркерами b500, подставляем стабы зависимостей
// и прогоняем: генерацию карточек, озвучку-слова, выбор 1–4 билетов, полный тираж, выплаты.
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
        querySelectorAll() { return []; },
        set disabled(v) {}, get disabled() { return false; },
    };
}
const sandbox = {
    console,
    setInterval: () => 0,
    clearInterval: () => {},
    Math, Number, String, Array, Object, JSON, isFinite, parseInt, parseFloat,
    window: { speechSynthesis: { cancel() {}, resume() {}, speak(u) { spoken.push(u.text); this.speaking = true; if (u.onend) u.onend(); }, getVoices() { return [{ lang: 'ru-RU' }]; }, speaking: false, pending: false } },
    setTimeout(fn, ms) { if (ms >= 1000) return 0; fn(); return 0; },
    SpeechSynthesisUtterance: class { constructor(t) { this.text = t; } },
    document: { getElementById(id) { if (!els[id]) els[id] = fakeEl(); return els[id]; } },
    LS: { getItem() { return null; }, setItem() {}, },
    state: { coins: 100000000, stats: {} },
    saveState() {}, updateCoinDisplay() {},
    showToast(m, t) { toasts.push([m, t]); },
    launchConfetti() {}, SoundFX: { play() {} },
    jackpotFeed() {}, jackpotOnLoss(x) { return x; }, jackpotPool() { return 0; },
    jackpotWin() { const p = sandbox.__jp || 0; sandbox.state.coins += p; return p; },
    jpcOff() { return false; },
    jpcSpinPct(g) { return sandbox.__jpPct || 0; },
    jpcPityNote() {},
    normBet(b) { b = Math.floor(Number(b)); return isFinite(b) && b >= 1 ? b : 1; },
    fmtCoins(n) { return String(n); },
    SLOTS_BETS: [100, 1000, 5000],
    syncBetInput() {},
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(moduleCode + `
;globalThis.__x = { loto, lotoWords, lotoMakeCard, lotoStart, lotoDraw, lotoFinish, lotoSetTickets, renderLotoUI, lotoSummary, lotoSummaryData, lotoCheerPhrase, LOTO_DRAWS, LOTO_PAY_ROW, LOTO_PAY_FULL, LOTO_MAX_TICKETS };`, sandbox);
const X = sandbox.__x;

let fails = 0;
function ok(cond, msg) { if (cond) console.log('  ok:', msg); else { fails++; console.error('  FAIL:', msg); } }

// 1) числа словами
ok(X.lotoWords(1) === 'один', '1 -> один');
ok(X.lotoWords(11) === 'одиннадцать', '11 -> одиннадцать');
ok(X.lotoWords(40) === 'сорок', '40 -> сорок');
ok(X.lotoWords(45) === 'сорок пять', '45 -> сорок пять');
ok(X.lotoWords(90) === 'девяносто', '90 -> девяносто');
ok(X.lotoWords(89) === 'восемьдесят девять', '89 -> восемьдесят девять');

// 2) карточки: 3×9, по 5 чисел в строке, диапазоны колонок, возрастание в колонке
for (let i = 0; i < 300; i++) {
    const g = X.lotoMakeCard();
    let bad = false;
    for (let r = 0; r < 3; r++) if (g[r].filter(v => v > 0).length !== 5) bad = true;
    for (let c = 0; c < 9; c++) {
        const lo = c === 0 ? 1 : c * 10, hi = c === 8 ? 90 : c * 10 + 9;
        const col = [];
        for (let r = 0; r < 3; r++) { const v = g[r][c]; if (v) { if (v < lo || v > hi) bad = true; col.push(v); } }
        if (!col.length) bad = true;
        for (let k = 1; k < col.length; k++) if (col[k] <= col[k - 1]) bad = true;
    }
    if (new Set(g.flat().filter(v => v > 0)).size !== 15) bad = true;
    if (bad) { fails++; console.error('  FAIL: карточка невалидна', JSON.stringify(g)); break; }
}
ok(true, '300 карточек: 5 чисел в строке, диапазоны колонок, уникальность');

// 3) b505: выбор числа билетов +_CLAMP_
X.lotoSetTickets(3); ok(X.loto.tickets === 3, 'выбор 3 карточек');
X.lotoSetTickets(9); ok(X.loto.tickets === X.LOTO_MAX_TICKETS, 'зажим сверху до 6');
X.lotoSetTickets(0); ok(X.loto.tickets === 1, 'зажим снизу до 1');

// 4) полный тираж с N билетами: стоимость, выплаты по каждому билету, озвучка
for (const T of [1, 2, 6]) {
    for (let round = 0; round < 15; round++) {
        spoken.length = 0; toasts.length = 0;
        sandbox.state.coins = 100000000;
        const before = sandbox.state.coins;
        X.lotoSetTickets(T);
        X.loto.bet = 1000;
        X.lotoStart();
        ok(X.loto.active === true && X.loto.cards.length === T, 'тираж начался, билетов: ' + T);
        ok(sandbox.state.coins === before - 1000 * T, 'списано ставка×' + T);
        let draws = 0;
        while (X.loto.active && draws < 60) { X.lotoDraw(); draws++; }
        ok(draws <= 60, 'тираж <= 60 бочонков');
        ok(new Set(X.loto.drawn).size === X.loto.drawn.length, 'бочонки без повторов');
        ok(spoken.length >= draws, 'озвучка каждого бочонка');
        let expect = 0;
        for (const cd of X.loto.cards) {
            expect += cd.rowPaid.filter(Boolean).length * 1000 * X.LOTO_PAY_ROW;
            if (cd.fullPaid) expect += 1000 * X.LOTO_PAY_FULL;
        }
        ok(X.loto.win === expect, 'выплаты = сумма по билетам (' + X.loto.win + ')');
        ok(sandbox.state.coins === before - 1000 * T + X.loto.win, 'баланс сошёлся');
        if (round === 0 && T === 2) console.log('  пример озвучки:', spoken.slice(0, 4).join(' | '));
    }
}

// 5) блокировка смены билетов во время тиража и ручная остановка
sandbox.state.coins = 50000;
X.lotoSetTickets(2);
X.loto.bet = 1000;
X.lotoStart();
X.lotoSetTickets(4);
ok(X.loto.tickets === 2 && X.loto.cards.length === 2, 'смена билетов во время тиража заблокирована');
X.lotoDraw(); X.lotoDraw(); X.lotoDraw();
X.lotoFinish(true);
ok(X.loto.active === false, 'ручная остановка тиража');

// 6) b509: панель итогов после тиража
sandbox.state.coins = 100000000;
X.lotoSetTickets(2);
X.loto.bet = 1000;
X.lotoStart();
let dd = 0;
while (X.loto.active && dd < 60) { X.lotoDraw(); dd++; }
const sumHtml = els['loto-summary'].innerHTML;
ok(sumHtml.indexOf('Итоги тиража') >= 0, 'панель итогов отображается после тиража');
ok(sumHtml.indexOf('Сыграли билетов') >= 0, 'в итогах есть счётчик сыгравших билетов');
const sd = X.lotoSummaryData();
ok(sd.tickets.length === 2 && sd.won.length === sd.tickets.filter(t => t.win > 0).length, 'lotoSummaryData согласована');

// 7) b509: все билеты проигрышные — слова поддержки
X.loto.active = false;
X.loto.cards = [X.loto.cards[0]];
X.loto.cards[0].rowPaid = [false, false, false];
X.loto.cards[0].fullPaid = false;
X.loto.win = 0;
X.loto.cheer = X.lotoCheerPhrase();
const cheerHtml = X.lotoSummary();
ok(cheerHtml.indexOf('0 из 1') >= 0, 'итоги: 0 из 1 сыгравших');
ok(cheerHtml.indexOf(X.loto.cheer) >= 0, 'баннер со словами поддержки в итогах');
ok(X.lotoCheerPhrase().length > 10, 'слова поддержки непустые');

// 8) b517/b518: золотой бочонок 90 первым в тираже срывает джекпот (шанс из Студии)
sandbox.__jp = 777;
sandbox.__jpPct = 100; // гарантия/100% — срыв разыгрывается на старте
sandbox.state.coins = 100000000;
X.lotoSetTickets(1);
X.loto.bet = 1000;
X.lotoStart();
X.lotoDraw();
ok(X.loto.drawn[0] === 90, 'первым выпал золотой бочонок 90');
ok(X.loto.win >= 777, 'джекпот-приз учтён в выигрыше раунда (' + X.loto.win + ')');
ok(els['loto-current'].innerHTML.indexOf('gold') >= 0, 'золотой бочонок рисуется золотым');
ok(els['loto-phrase'].textContent.indexOf('Джекпот сайта +777') >= 0, 'фраза о срыве джекпота');
// не первым — без джекпота
X.lotoFinish(true);
sandbox.__jp = 0;
sandbox.__jpPct = 0; // срыва нет — золотой первым выйти не должен
X.loto.bet = 1000;
X.lotoStart();
X.lotoDraw();
ok(X.loto.drawn[0] !== 90, 'без срыва 90 первым не выходит (не дразнит)');
ok(X.loto.win === 0, 'без срыва джекпота нет');
X.lotoFinish(true);

console.log(fails ? ('\nFAILS: ' + fails) : '\nALL TESTS PASSED');
process.exit(fails ? 1 : 0);
