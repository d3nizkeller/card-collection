/* b488: рулетка 2D во вкладке «Игры» — ставки фишками, колесо, выплаты.

   Владелец (референс-скриншот стола): «добавь в игры игру рулетка в 2д».

   A. Разметка/CSS/теги: десятая плитка «Рулетка» (fa-circle-dot), лобби
      #lobby-roulette с canvas-колесом и столом #roulette-table; контейнер
      переключателей на .nx-modes (5 колонок на телефоне, 10 от sm); плитка в
      четырёх id-списках стекла + своё правило lq-on; тег nxmob232 единый.
   B. Исходники: все функции рулетки объявлены один раз; выплаты 36/3/2;
      порядок колеса европейский; red/black-множество стандартное.
   C. Поведение (jsdom,Math.random и длительность спина под контролем):
      цвета номеров; ставки копятся кликами и видны бейджем; не хватает
      монет — ставка не ставится; ×2 удваивает или отказывает; сброс чистит;
      спин списывает сумму, крутит колесо (rAF), по итогу платит ×2/×3/×36,
      пишет номер в историю, чистит ставки и рапортует тостом; зеро обесценивает
      равные шансы; режим открывается через setBattleMode.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b488.js
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
    w.HTMLCanvasElement.prototype.getContext = () => null; // колесо в jsdom не рисуется — логика не должна падать
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

const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
    console.log('A. Разметка, CSS, теги');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const css = fs.readFileSync(path.join(ROOT, 'assets', 'app.css'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');

        const tiles = (html.match(/id="mode-[a-z]+-btn"/g) || []).length;
        eq(tiles, 10, 'плиток режимов в «Играх» — десять');
        ok(html.includes('id="mode-roulette-btn"') && html.includes('fa-circle-dot'), 'плитка «Рулетка» с иконкой fa-circle-dot');
        ok(html.includes('class="grid nx-modes gap-1 sm:gap-2 w-full py-0.5"'), 'контейнер переключателей на .nx-modes');
        ok(/\.nx-modes\{grid-template-columns:repeat\(5,minmax\(0,1fr\)\)\}/.test(css) && /@media \(min-width:640px\)\{\.nx-modes\{grid-template-columns:repeat\(10,minmax\(0,1fr\)\)\}\}/.test(css), '.nx-modes: 5 колонок на телефоне, 10 от sm');
        ok(html.includes('id="lobby-roulette"') && html.includes('id="roulette-wheel"') && html.includes('id="roulette-table"'), 'лобби рулетки: колесо-canvas и стол');
        ['#mode-grid-btn, #mode-wheel-btn, #mode-mines-btn, #mode-lines-btn, #mode-tama-btn, #mode-roulette-btn, #miner-btn{',
         '#mode-roulette-btn::before', '#mode-roulette-btn:hover', '#mode-roulette-btn:active', '#mode-roulette-btn.lq-on{'].forEach(s =>
            ok(html.includes(s), 'плитка рулетки в списках стекла/подсветки: ' + s.slice(0, 40) + '…'));

        const tag = (sw.match(/const VERSION = '(nxmob\d+)';/) || [])[1];
        // b489: номер тега не прибиваем к b488 — единство и не ниже nxmob232
        eq((html.match(new RegExp(tag, 'g')) || []).length, 8, 'index.html: тег из sw.js во всех 8 ссылках на assets');
        ok(bp.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG равен тегу из sw.js');
        ok(Number((tag || '0').replace('nxmob', '')) >= 232, 'тег не ниже nxmob232 (' + tag + ')');
    }

    console.log('\nB. Исходники app.js');
    {
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        const count = re => (app.match(re) || []).length;
        ['rouletteColor', 'rouletteState', 'rouletteSpotDefs', 'rouletteTotal', 'rouletteSetChip', 'rouletteBet', 'rouletteDouble', 'rouletteClear', 'rouletteSpin', 'rouletteAnimate', 'rouletteDraw', 'renderRoulette'].forEach(fn =>
            eq(count(new RegExp('function ' + fn + '\\(', 'g')), 1, fn + '() объявлена один раз'));
        ok(app.includes('pay: 36') && app.includes('pay: 3') && app.includes('pay: 2'), 'выплаты: число ×36, дюжина ×3, равные ×2');
        ok(app.includes('const ROULETTE_ORDER = [0, 32, 15, 19, 4, 21, 2, 25,'), 'порядок колеса — европейский');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;
    // пассивный тик «Шахты» капает монеты сам — глушим, чтобы считать только рулетку
    ev(`try { minerStart = function () {}; if (minerTickT) { clearInterval(minerTickT); minerTickT = null; } } catch (e) {}`);
    const coins = () => ev('state.coins');
    const total = () => ev('rouletteTotal()');
    const table = () => doc.getElementById('roulette-table').innerHTML;
    const toasts = () => doc.getElementById('toast-container').innerHTML;
    const clearToasts = () => { doc.getElementById('toast-container').innerHTML = ''; };

    console.log('\nC. Цвета и ставки');
    eq(ev(`rouletteColor(0)`), 'green', 'зеро зелёное');
    eq(ev(`rouletteColor(7)`), 'red', '7 — красное');
    eq(ev(`rouletteColor(8)`), 'black', '8 — чёрное');
    {
        ev(`state.coins = 1000; renderRoulette();`);
        ev(`rouletteSetChip(25); rouletteBet('n7'); rouletteBet('n7');`);
        eq(total(), 50, 'две фишки по 25 на число = 50 на столе');
        ok(table().includes('>50<'), 'бейдж ставки 50 виден на клетке');
        // b491: фишка покупается из кошелька В МОМЕНТ КЛИКА, поэтому проверяем
        // недостачу на реально пустом балансе (10 монет при фишке 25)
        ev(`state.coins = 10;`);
        clearToasts();
        ev(`rouletteBet('red')`);
        eq(total(), 50, 'ставка сверх баланса не встала');
        eq(coins(), 10, 'b491: без денег баланс не тронут');
        ok(toasts().includes('Не хватает монет'), 'тост о нехватке монет на ставку');
        ev(`state.coins = 1000; rouletteDouble();`);
        eq(total(), 100, '×2 удвоил стол');
        eq(coins(), 950, 'b491: удвоение докуплено из кошелька (1000 − 50)');
        ev(`rouletteClear();`);
        eq(total(), 0, 'сброс чистит стол');
        eq(coins(), 1050, 'b491: «Сброс» вернул 100 со стола в баланс');
    }

    console.log('\nD. Спины и выплаты (рандом и тайминг под контролем)');
    {
        ev(`window.__nxRouletteMs = 20; rouletteClear(); state.coins = 1000; updateCoinDisplay();`);
        // b491: золотое зеро (шанс срыва общего джекпота) выключаем, чтобы
        // детерминированные проверки выплат не зависели от банка сайта
        ev(`jpcSet({ pRoulette: 0 });`);
        ev(`Math.random = function () { return 0.2; };`); // win = floor(0.2*37) = 7 (красное)
        ev(`rouletteSetChip(5); rouletteBet('red'); rouletteBet('red');`); // 10 на красное
        clearToasts();
        ev(`rouletteSpin()`);
        eq(coins(), 990, 'b491: ставки списаны ещё при постановке фишек');
        await sleep(400);
        eq(coins(), 1010, 'красное ×2: вернулось 20 (990+20)');
        ok(toasts().includes('Выпало 7 (красное): выигрыш +20'), 'тост с номером, цветом и суммой');
        eq(ev(`rouletteState().hist.slice(-1)[0]`), 7, 'номер 7 ушёл в историю');
        eq(total(), 0, 'после спина стол чист');
    }
    {
        ev(`rouletteClear(); rouletteSetChip(5); rouletteBet('n3');`); // 5 на число 3
        clearToasts();
        ev(`rouletteSpin()`); // снова выпадет 7
        await sleep(400);
        eq(coins(), 1005, 'промах по числу: −5 ставок');
        ok(toasts().includes('ставки сгорели'), 'тост про сгоревшие ставки');
    }
    {
        const c2 = coins();
        ev(`rouletteClear(); rouletteSetChip(5); rouletteBet('n7');`); // 5 на число 7
        clearToasts();
        ev(`rouletteSpin()`);
        await sleep(400);
        eq(coins(), c2 - 5 + 180, 'число ×36: 5 монет превратились в 180');
    }
    {
        ev(`Math.random = function () { return 0.0; };`); // win = 0
        ev(`rouletteClear(); rouletteSetChip(5); rouletteBet('even'); rouletteBet('red');`);
        clearToasts();
        const c0 = coins(); // b491: 10 монет уже ушли из кошелька на стол
        ev(`rouletteSpin()`);
        await sleep(400);
        eq(coins(), c0, 'зеро: равные шансы сгорели (списаны заранее)');
        eq(ev(`rouletteState().hist.slice(-1)[0]`), 0, 'зеро в истории');
        ev(`Math.random = Math.__origRandom || Math.random;`);
    }
    {
        ev(`rouletteClear(); rouletteSetChip(5); rouletteBet('n1');`);
        clearToasts();
        ev(`rouletteSpin()`);
        ok(ev(`rouletteSpinning`) === true || ev(`rouletteSpinning`) === false, 'флаг спина существует');
        await sleep(400);
    }

    console.log('\nE. Режим в навигации и регрессии');
    {
        ev(`setBattleMode('roulette')`);
        eq(doc.getElementById('lobby-roulette').classList.contains('hidden'), false, 'лобби рулетки открылось');
        ok(table().includes('Крутить'), 'стол отрисован с кнопкой «Крутить»');
        ok(doc.getElementById('mode-roulette-btn').className.includes('lq-on'), 'плитка «Рулетка» подсвечена');
        ev(`setBattleMode('tama')`);
        eq(doc.getElementById('lobby-roulette').classList.contains('hidden'), true, 'уход в другой режим прячет лобби рулетки');
        ok(doc.getElementById('tama-panel').innerHTML.length > 50, 'тамагочи не задет');
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
