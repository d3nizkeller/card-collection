// b491: рулетка — баланс двигается на глазах и привязан к общему джекпоту.
// Жалоба владельца: «чего с баланса не отнимается и не прибавляется и привяжи к джекпоту».
// Проверки:
//  1) исходники: кошелёк стола (nxCoinsExact/rlSync/rlFlash/rouletteSpend/rouletteRefund),
//     рулетка — пятая игра джекпота (JPC_GAMES + Roulette 2.7 %), золотое зеро;
//  2) разметка/CSS: .rl-wallet, #rl-balance, #rl-delta, jp-banner с roulette-*;
//  3) поведение: фишка списывается СРАЗУ, «×2» докупает, «Сброс» возвращает,
//     недостача — отказ; выигрыш и проигрыш меняют баланс и шапку буквами (b494);
//  4) джекпот: ставка кормит банк, проигрыш докидывает, золотое зеро срывает банк
//     (jackpotWin), гарантия по спинам работает, ползунок «Рулетка» есть в Студии;
//  5) сквозной тег: nxmob235 в sw.js, 8 раз в index.html, BUILD_TAG в tools/build.py.
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.resolve(__dirname, '..');
let fails = 0, checks = 0;
function ok(cond, name) {
    checks++;
    if (!cond) { fails++; console.log('  FAIL:', name); }
}
function eq(a, b, name) { ok(a === b, name + ' (факт ' + JSON.stringify(a) + ', ждём ' + JSON.stringify(b) + ')'); }
const sleep = ms => new Promise(r => setTimeout(r, ms));

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
    return w;
}

(async function main() {
    console.log('A. Исходники');
    {
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        ['function rlSync(',
            'function rlFlash(', 'function rouletteSpend(', 'function rouletteRefund(',
            'function rouletteJpArmed(', 'function rouletteJpRoll(', 'let rouletteGoldZero = false;'].forEach(s =>
            ok(app.includes(s), 'app.js: ' + s));
        ok(app.includes("const JPC_GAMES = ['Slots', 'Grid', 'Lines', 'Wheel', 'Roulette'];"), 'app.js: рулетка — пятая игра джекпота');
        ok(app.includes("Roulette: 'Рулетка'") && app.includes("Roulette: 'золотое зеро'"), 'app.js: подпись игры в Студии');
        ok(/JPC_DEFAULT_P = \{[^}]*Roulette: 2\.7 \}/.test(app), 'app.js: заводской шанс золотого зеро 2.7 % (1 из 37)');
        ok(/pRoulette: JPC_DEFAULT_P\.Roulette/.test(app) && /pityRoulette: 0/.test(app), 'app.js: pRoulette/pityRoulette в JPC_DEFAULTS');
        ok(app.includes("case 'odds-roulette':"), 'app.js: фраза шанса золотого зеро');
        ok(app.includes("'odds-roulette']") || app.includes('"odds-roulette"]'), 'app.js: ключ odds-roulette в JPC_LABEL_KEYS');
        ok(/jackpotFeed\(total\);/.test(app), 'app.js: спин кормит банк джекпота');
        ok(/jackpotOnLoss\(total - pay\);/.test(app), 'app.js: чистый проигрыш докидывает банк');
        ok(/jpcPityNote\('Roulette', jpHit\);/.test(app), 'app.js: гарантия по спинам рулетки');
        ok(/const jpHit = rouletteJpRoll\(\);\s*\n\s*const win = jpHit \? 0 : Math\.floor\(Math\.random\(\) \* 37\);/.test(app), 'app.js: золотое зеро = выигрышное число 0');
        ok(/prize = jackpotWin\(\)/.test(app), 'app.js: срыв банка через jackpotWin()');
        ok(app.includes("if (!rouletteSpend(rouletteChip, 'фишка ' + rouletteChip)) return;"), 'app.js: фишка покупается в момент клика');
        ok(app.includes('if (!rouletteSpend(total, \'удвоение ставок\')) return;'), 'app.js: удвоение докупается из кошелька');
        ok(/rouletteRefund\(total\);/.test(app), 'app.js: «Сброс» возвращает фишки в баланс');
        ok(app.includes("document.getElementById('roulette-jackpot')"), 'app.js: jackpotRender обновляет банк в лобби рулетки');
        ok(!app.includes("state.coins -= total;\n            updateCoinDisplay();"), 'app.js: спин больше не списывает второй раз');
        ok(!app.includes("showToast('Не хватает монет: ставок на '"), 'app.js: старой проверки «не хватает на спин» нет');
        ok(!app.includes('function nxCoinsExact(') && !app.includes('function rlExactHdr(') && !app.includes('function rlLobbyOpen('), 'app.js: определений точного формата b491 не осталось (b494)');
        ok(app.includes("const t = fmtCoins(state.coins); if (bal.textContent !== t) bal.textContent = t;"), 'app.js: кошелёк стола пишет баланс буквами (b494)');

        const idx = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        ['class="rl-wallet"', 'id="rl-balance"', 'id="rl-delta"', 'id="rl-table-sum"', 'id="rl-spins"',
            'id="rl-wins"', 'id="rl-jp-odds"', 'id="roulette-jackpot"', 'id="roulette-jackpot-note"',
            'id="roulette-jp-winner"', 'id="roulette-jp-top-list"', 'data-jpc="odds-roulette"',
            'сразу списываются с баланса', 'Рулетка (золотое зеро) 1 из 37'].forEach(s => ok(idx.includes(s), 'index.html: ' + s));

        const css = fs.readFileSync(path.join(ROOT, 'assets', 'app.css'), 'utf8');
        ['.rl-wallet{', '.rl-w-cap{', '.rl-w-bal{', '.rl-w-rows{', '.rl-w-jp{', '.rl-delta{', '.rl-d-up{',
            '.rl-d-down{', '@keyframes rlDelta', '.nx-bump{', '@keyframes nxBump', '.rl-jp-note{'].forEach(s =>
            ok(css.includes(s), 'app.css: ' + s));
        ok(/@media \(max-width:640px\)\{\s*\.rl-wallet\{/.test(css), 'app.css: кошелёк-строка подстраивается на телефоне');
    }

    const w = boot();
    const ev = s => w.eval('(function(){ ' + s + ' })()');
    ev('try { minerStart = function(){}; } catch(e){}; try { clearInterval(minerTickT); } catch(e){}; try { state.achievements.rich = 1; } catch(e){}');
    ev('window.__toasts = []; var __st = showToast; showToast = function(t, k){ window.__toasts.push(String(t) + "|" + (k || "")); return __st.apply(null, arguments); };');
    ev('switchTab("battle"); setBattleMode("roulette");');
    ev('window.__nxRouletteMs = 20;');

    console.log('\nB. Кошелёк стола: фишка списывается сразу');
    ev('jpcSet({ pRoulette: 0 }); state.coins = 1000; rouletteBets = {}; updateCoinDisplay(); renderRoulette();');
    eq(ev('return document.getElementById("rl-balance").textContent;'), '1k', 'баланс в кошельке стола буквами (b494)');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '1k', 'шапка в лобби рулетки тоже буквами (b494)');
    ev('rouletteChip = 25; rouletteBet("red");');
    eq(ev('return state.coins;'), 975, 'клик по клетке списал 25 с баланса');
    eq(ev('return rouletteTotal();'), 25, 'на столе 25');
    eq(ev('return document.getElementById("rl-balance").textContent;'), '975', 'кошелёк стола показал 975');
    eq(ev('return document.getElementById("rl-table-sum").textContent;'), '25', 'сумма на столе в кошельке');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '975', 'шапка обновилась сразу');
    ok(/−25/.test(ev('return document.getElementById("rl-delta").textContent;')), 'живой минус −25 рядом с балансом');
    ok(ev('return document.getElementById("rl-delta").className;').includes('rl-d-down'), 'минус окрашен как расход');
    ev('rouletteBet("black"); rouletteBet("n7");');
    eq(ev('return state.coins;'), 925, 'ещё две фишки по 25 списаны');
    eq(ev('return rouletteTotal();'), 75, 'на столе 75');
    ev('rouletteDouble();');
    eq(ev('return state.coins;'), 850, '«×2» докупил удвоение из кошелька');
    eq(ev('return rouletteTotal();'), 150, 'на столе стало 150');
    ev('rouletteClear();');
    eq(ev('return state.coins;'), 1000, '«Сброс» вернул 150 в баланс');
    eq(ev('return rouletteTotal();'), 0, 'стол пуст');
    ok(/возвращены в баланс/.test(ev('return window.__toasts.join("\\n");')), 'тост о возврате фишек');

    console.log('\nC. Недостача монет');
    ev('window.__toasts = []; state.coins = 10; rouletteChip = 25; rouletteBet("red");');
    eq(ev('return state.coins;'), 10, 'без денег фишка не ставится');
    eq(ev('return rouletteTotal();'), 0, 'стол пуст');
    ok(/Не хватает монет/.test(ev('return window.__toasts.join("\\n");')), 'тост о нехватке монет');
    ev('state.coins = 100; rouletteChip = 100; rouletteBet("red"); rouletteDouble();');
    eq(ev('return state.coins;'), 0, 'после фишки 100 кошелёк пуст');
    eq(ev('return rouletteTotal();'), 100, 'удвоение не прошло — на столе только 100');
    ok(/удвоение/.test(ev('return window.__toasts.join("\\n");')), 'тост про нехватку на удвоение');

    console.log('\nD. Выигрыш и проигрыш двигают баланс');
    ev('state.coins = 5000; rouletteBets = {}; updateCoinDisplay();');
    ev('jpcSet({ pRoulette: 0, feedBet: 0, feedLoss: 0 });'); // isolate balance checks
    ev('rouletteChip = 25; rouletteBet("red");');
    const c0 = ev('return state.coins;');
    ev('Math.random = function(){ return (5 + 0.5) / 37; }; rouletteSpin();');
    await sleep(200);
    eq(ev('return state.coins;'), c0 + 50, 'красное ×2: выигрыш 50 упал в баланс');
    eq(ev('return document.getElementById("rl-balance").textContent;'), ev('return fmtCoins(' + (c0 + 50) + ')'), 'кошелёк стола показал новый баланс буквами (b494)');
    ok(/\+50/.test(ev('return document.getElementById("rl-delta").textContent;')), 'живой плюс +50');
    ok(ev('return document.getElementById("rl-delta").className;').includes('rl-d-up'), 'плюс окрашен как приход');
    eq(ev('return rouletteTotal();'), 0, 'после спина стол пуст');
    ok(/выигрыш \+50 монет/.test(ev('return window.__toasts.join("\\n");')), 'тост о выигрыше точной суммой');
    ev('window.__toasts = []; rouletteChip = 100; rouletteBet("n7");');
    const c1 = ev('return state.coins;');
    ev('Math.random = function(){ return (5 + 0.5) / 37; }; rouletteSpin();');
    await sleep(200);
    eq(ev('return state.coins;'), c1, 'проигрыш: ставка сгорела, баланс не вырос');
    ok(/ставки сгорели \(−100\)/.test(ev('return window.__toasts.join("\\n");')), 'тост о проигрыше');
    eq(ev('return state.stats.rouletteSpins;') >= 2, true, 'счётчик спинов растёт');
    eq(ev('return state.stats.rouletteWins;') >= 1, true, 'счётчик побед растёт');

    console.log('\nE. Привязка к общему джекпоту');
    ev('jpcSet({ feedBet: 100, feedLoss: 100, pRoulette: 0, payout: 100, cap: 0, on: 1 });');
    ev('state.coins = 100000; rouletteBets = {};');
    const pool0 = ev('return jackpotPool();');
    ev('rouletteChip = 100; rouletteBet("red"); Math.random = function(){ return (5 + 0.5) / 37; }; rouletteSpin();');
    await sleep(200);
    const pool1 = ev('return jackpotPool();');
    eq(pool1 - pool0, 100, 'выигрышный спин: 100 % ставки ушли в банк');
    ev('rouletteChip = 100; rouletteBet("n7"); Math.random = function(){ return (5 + 0.5) / 37; }; rouletteSpin();');
    await sleep(200);
    const pool2 = ev('return jackpotPool();');
    eq(pool2 - pool1, 200, 'проигрыш: ставка 100 + 100 % проигрыша = 200 в банк');
    ok(ev('return !!document.getElementById("roulette-jackpot");'), 'банк джекпота виден в лобби рулетки');
    ok(ev('return document.getElementById("roulette-jackpot").textContent.length;') > 0, 'сумма банка в лобби непустая');
    ok(/общий банк сайта/.test(ev('return document.getElementById("roulette-jackpot-note").textContent;')), 'подпись банка в лобби');
    ok(/золотое зеро/.test(ev('return document.getElementById("rl-jp-odds").textContent;')), 'шанс золотого зеро в кошельке стола');
    ok(/Золотое зеро срывает общий джекпот/.test(ev('return document.getElementById("roulette-table").innerHTML;')), 'подсказка про джекпот под столом');

    console.log('\nF. Золотое зеро срывает банк');
    ev('jpcSet({ pRoulette: 100 }); state.coins = 5000; rouletteBets = {};');
    const poolB = ev('return jackpotPool();');
    const coinsB = ev('return state.coins;');
    const jpB = ev('return state.stats.jackpots || 0;');
    ev('window.__toasts = []; rouletteChip = 10; rouletteBet("red"); rouletteSpin();');
    await sleep(250);
    eq(ev('return rouletteState().hist.slice(-1)[0];'), 0, 'золотое зеро: выпало 0');
    eq(ev('return rouletteGoldZero;'), true, 'зеро осталось золотым на колесе');
    eq(ev('return state.stats.jackpots || 0;') - jpB, 1, 'срыв записан в статистику джекпотов');
    ok(ev('return state.coins;') > coinsB + poolB - 10, 'банк сайта упал в баланс');
    ok(ev('return jackpotPool();') < poolB, 'банк сайта уменьшился после срыва');
    ok(/JACKPOT/.test(ev('return window.__toasts.join("\\n");')), 'тост JACKPOT');
    ok(/ЗОЛОТОЕ ЗЕРО/.test(ev('return window.__toasts.join("\\n");')), 'тост рулетки про золотое зеро');
    ok(ev('return (jackpot.hall || []).length;') >= 1, 'срыв попал в зал славы');

    console.log('\nG. Гарантия (pity) и настройки Студии');
    ev('jpcSet({ pRoulette: 0, pityRoulette: 2 }); jpcPity.Roulette = 0; jpcPitySave();');
    eq(ev('return jpcPityForce("Roulette");'), false, 'гарантия молчит на первомспине');
    ev('jpcPity.Roulette = 2; jpcPitySave();');
    eq(ev('return jpcPityForce("Roulette");'), true, 'после 2 спинов без джекпота он гарантирован');
    eq(ev('return jpcSpinPct("Roulette");'), 100, 'шанс по гарантии = 100 %');
    ev('jpcSet({ pityRoulette: 0, pRoulette: 2.7 });');
    const rows = ev('return jpcProbRows();');
    ok(/Рулетка/.test(rows) && /золотое зеро/.test(rows), 'в Студии появился ползунок «Рулетка»');
    ok(/id="jpc-pRoulette"/.test(rows) && /id="jpc-pityRoulette"/.test(rows), 'ползунок шанса и поле гарантии рулетки');
    eq(ev('return jpcOdds(2.7);'), '1 из 37', '2.7 % читаются как «1 из 37»');
    ev('jpcSet({ pRoulette: 0, feedBet: 100, feedLoss: 100 });');

    console.log('\nH. Баланс буквами везде (b494)');
    ev('state.coins = 1234567; updateCoinDisplay();');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '1.2m', 'большие суммы в шапке по-прежнему буквами');
    eq(ev('return document.getElementById("rl-balance").textContent;'), '1.2m', 'кошелёк стола тоже буквами (b494)');
    ev('state.coins = 999999; updateCoinDisplay();');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '999k', 'до миллиона шапка тоже буквами (b494)');
    ev('document.getElementById("lobby-roulette").classList.add("hidden"); state.coins = 5000; updateCoinDisplay();');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '5k', 'вне лобби рулетки шапка как раньше');
    ev('document.getElementById("lobby-roulette").classList.remove("hidden"); updateCoinDisplay();');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '5k', 'вернулись в рулетку — те же буквы (b494)');

    console.log('\nI. Сквозной тег');
    {
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const idx = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const bld = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');
        const tag = (sw.match(/const VERSION = '(nxmob\d+)';/) || [])[1];
        ok(!!tag, 'sw.js: боевой тег присутствует');
        ok(Number(tag && tag.replace('nxmob', '')) >= 235, 'sw.js: тег не ниже nxmob235 (факт ' + tag + ')');
        eq((idx.match(new RegExp(tag, 'g')) || []).length, 8, 'index.html: тег во всех 8 ссылках');
        ok(bld.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG совпадает с тегом sw.js');
        ok(idx.includes('assets/app.js?v=' + tag), 'index.html тянет app.js с тегом');
    }

    console.log(fails ? '\nb491: FAIL (' + fails + '/' + checks + ')' : '\nb491: OK (' + checks + ' проверок)');
    process.exit(fails ? 1 : 0);
})().catch(e => { console.log('b491: CRASH', e.message, e.stack); process.exit(1); });

