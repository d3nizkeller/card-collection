/* b435: ценники «Дома коллекционера» на бирже — от 1 миллиарда.

   A. marketHousePrice по редкостям: common 1b … legendary 35b, минимум 1b.
   B. Витрина Дома: у каждого лота ценник ≥ 1b.
   C. Автовыкуп игроков НЕ тронут: MARKET_SYS_PRICE прежний (защита от мани-абаза).
   D. Покупка лота Дома списывает ровно ценник; при нехватке — честный тост.

   Запуск:  node tools/test-b435.js
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
const toasts = doc => Array.from((doc.getElementById('toast-container') || { children: [] }).children).map(t => t.textContent).join(' | ');

(async () => {
    const G = boot();
    const ev = G.ev;

    console.log('\nA. Ценники Дома — от 1 миллиарда');
    eq(ev('marketHousePrice({ rarity: "common" })'), 1000000000, 'common = 1b');
    eq(ev('marketHousePrice({ rarity: "rare" })'), 4000000000, 'rare = 4b');
    eq(ev('marketHousePrice({ rarity: "epic" })'), 10000000000, 'epic = 10b');
    eq(ev('marketHousePrice({ rarity: "legendary" })'), 35000000000, 'legendary = 35b');
    eq(ev('marketHousePrice({})'), 1000000000, 'без редкости — минимум 1b');
    eq(ev('fmtCoins(marketHousePrice({ rarity: "common" }))'), '1b', 'витрина покажет «1b»');

    console.log('\nB. Витрина Дома: все лоты ≥ 1b');
    ev('CLOUD.connected = function () { return true; };');
    ev('state.cards = STANDARD_CARDS.map(c => Object.assign({}, c));');
    const lots = ev('marketSystemLots()');
    ok(Array.isArray(lots) && lots.length > 0, 'лоты витрины построены: ' + (lots || []).length);
    ok(lots.every(l => l.price >= 1000000000), 'у каждого лота ценник ≥ 1b');
    ok(lots.some(l => l.price >= 35000000000), 'легендарные — 35b (скуби-легенды в стандарте)');

    console.log('\nC. Автовыкуп игроков не тронут (защита от мани-абаза)');
    eq(ev('MARKET_SYS_PRICE.common'), 100, 'автовыкуп: common по-прежнему 100');
    eq(ev('MARKET_SYS_PRICE.legendary'), 3500, 'автовыкуп: legendary по-прежнему 3500');
    eq(ev('marketSysPrice({ rarity: "epic" })'), 1000, 'marketSysPrice не изменился');

    console.log('\nD. Покупка лота Дома = ценник');
    ev('state.cards.push({ id: "hc1", packId: state.packs[0].id, name: "Тестовая обычная", rarity: "common", image: "media/g0.jpg" });');
    const cid = 'hc1';
    ev('checkAchievements = function () {};'); // награды достижений не примешиваются к проверке списания
    ev('state.coins = 1000000000; state.collection = state.collection || {};');
    ev('marketBuySys("' + cid + '")');
    eq(ev('state.coins'), 0, 'списан ровно миллиард (ценник common)');
    ok(ev('cardCopies("' + cid + '")') >= 1, 'карта встала в коллекцию');
    ev('state.coins = 500000000;');
    ev('marketBuySys("' + cid + '")');
    ok(/Не хватает монет: нужно 1b/.test(toasts(G.doc)), 'при нехватке — тост с миллиардным ценником: ' + (toasts(G.doc).match(/Не хватает[^|]*/) || ['?'])[0]);

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
