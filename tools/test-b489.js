/* b489: редизайн рулетки — казино-сукно, классический стол, живое колесо.

   Владелец: «выглядит не красиво и дизайн не красивый».

   A. CSS: сукно .rl-felt, сетка стола .rl-grid (зеро слева на 3 ряда, 12
      колонок чисел, колонка 2:1 справа), клетки rl-red/rl-black/rl-zero/
      rl-out, мини-фишка ставки rl-chipmini, казино-фишки rl-chip-* с
      коническими полосами и золотым кольцом активной, история rl-histn,
      мобильный ужимальщик сетки; дом колеса .rl-wheelhouse с тенью.
   B. app.js: ставки на колонки 2:1 (c1/c2/c3, pay 3) в rouletteSpotDefs;
      шарик ROULETTE_BALL крутится против колеса и садится в карман
      выигрышного сектора; rouletteDraw рисует обод/пины/конус/спицы/ступицу/
      шарик/ромб-указатель; renderRoulette собирает классический стол.
   C. Поведение (jsdom): стол содержит зеро-плашку, 36 чисел, три 2:1, три
      дюжины и шесть равных шансов; ставка на колонку платит ×3; бейдж ставки
      виден мини-фишкой; активная фишка подсвечена; шарик после спина сидит
      под указателем (угол -90); регрессии выплат b488.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b489.js
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
    return { w, ev: s => w.eval(s), doc: w.document };
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
    console.log('A. CSS казино и теги');
    {
        const css = fs.readFileSync(path.join(ROOT, 'assets', 'app.css'), 'utf8');
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');
        ['.rl-felt{', '.rl-grid{display:grid;grid-template-columns:44px repeat(12,minmax(0,1fr)) 40px', '.rl-cell{', '.rl-red{', '.rl-black{', '.rl-zero{', '.rl-zero-v{', '.rl-out{', '.rl-chipmini{', '.rl-chip{', '.rl-chip-5{', '.rl-chip-on{', '.rl-histn{', '.rl-wheelhouse{'].forEach(s =>
            ok(css.includes(s), 'css: ' + s.slice(0, 40)));
        ok(/@media \(max-width:640px\)\{\s*\.rl-grid\{grid-template-columns:26px/.test(css), 'мобильный стол ужимается под 390px');
        ok(/\.rl-chip-100\{[^}]*conic-gradient\(#b45309/.test(css), 'фишка 100 — янтарные конические полосы');
        const tag = (sw.match(/const VERSION = '(nxmob\d+)';/) || [])[1];
        // сквозная проверка тега: единый тег из sw.js повторяется 8 раз в index.html,
        // совпадает с BUILD_TAG и не ниже тега своего батча (nxmob233 для b489)
        ok(!!tag, 'sw.js: боевой тег присутствует');
        ok(Number(tag && tag.replace('nxmob', '')) >= 233, 'sw.js: тег не ниже nxmob233 (факт ' + tag + ')');
        eq((html.match(new RegExp(tag, 'g')) || []).length, 8, 'index.html: тег во всех 8 ссылках');
        ok(bp.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG совпадает с тегом sw.js');
        ok(html.includes('rl-wheelhouse') && html.includes('width="420"'), 'canvas колеса 420px в доме с тенью');
    }

    console.log('\nB. Исходники app.js');
    {
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        ok(app.includes("defs.push({ id: 'c3', label: '2:1', kind: 'col', pay: 3"), 'ставки на колонку 2:1 в defs (c3)');
        ok(app.includes("defs.push({ id: 'c1', label: '2:1', kind: 'col', pay: 3"), 'ставки на колонку 2:1 в defs (c1)');
        ok(app.includes('const ROULETTE_BALL = {'), 'состояние шарика');
        ok(/ROULETTE_BALL\.angle = -90 - \(1 - e\) \* ROULETTE_BALL\.spin;/.test(app), 'шарик крутится против колеса и сходится к указателю');
        ok(app.includes('ROULETTE_BALL.r = 0.94 - 0.16 * e;'), 'шарик по спирали сходит с обода в карман');
        ok(app.includes('createRadialGradient(cx, cy, R * 0.8, cx, cy, R)'), 'обод колеса — радиальный градиент дерева');
        ok(app.includes('hub.addColorStop(0, \'#fde68a\')'), 'золотая ступица');
        ok(/g\.fillStyle = '#fbbf24'; g\.fill\(\);\s*g\.strokeStyle = 'rgba\(2,6,23,\.6\)';/.test(app), 'ромб-указатель с обводкой');
        ok(app.includes('rl-chipmini'), 'ставки на столе — мини-фишки');
        ok(app.includes('class="rl-felt"'), 'стол лежит на сукне');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;
    // пассивная «Шахта» капает монеты сама — глушим, чтобы считать только рулетку
    ev(`try { minerStart = function () {}; if (minerTickT) { clearInterval(minerTickT); minerTickT = null; } } catch (e) {}`);
    // достижение «Богач» (2000+ монет) дарит +200 сами — помечаем собранным,
    // чтобы в тестах монеты двигала только рулетка
    ev(`state.achievements = state.achievements || {}; state.achievements.rich = 1;`);
    const table = () => doc.getElementById('roulette-table').innerHTML;

    console.log('\nC. Классический стол в DOM');
    {
        ev(`state.coins = 5000; renderRoulette();`);
        const t = table();
        ok(t.includes('rl-zero-v'), 'зеро — вертикальная плашка слева');
        eq((t.match(/rl-cell rl-red|rl-cell rl-black/g) || []).length, 36, '36 чисел красными/чёрными клетками');
        eq((t.match(/2:1/g) || []).length, 3, 'три коробки 2:1 справа');
        ok(t.includes('1–12') && t.includes('13–24') && t.includes('25–36'), 'дюжины под числами');
        ok(t.includes('КРАСНОЕ') && t.includes('ЧЁРНОЕ') && t.includes('ЧЁТ') && t.includes('НЕЧЕТ') && t.includes('1–18') && t.includes('19–36'), 'шесть равных шансов');
        ok(t.includes('rl-chip rl-chip-5 rl-chip-on'), 'фишка 5 активна по умолчанию и подсвечена');
        ok(t.includes('rl-chip-100'), 'фишка 100 янтарная');
    }
    {
        ev(`jpcSet({ pRoulette: 0 });`); // b491: золотое зеро не мешает детерминированным выплатам
        ev(`rouletteSetChip(25); rouletteBet('c2'); rouletteBet('c2');`);
        ok(table().includes('>50<'), 'бейдж ставки на колонку — мини-фишка 50');
        ev(`window.__nxRouletteMs = 20; Math.random = function () { return 0.14; };`); // win = floor(0.14*37) = 5 → 5%3==2 → бьёт ставка на колонку c2
        const c0 = ev('state.coins');
        ev(`rouletteSpin()`);
        await sleep(400);
        eq(ev('state.coins'), c0 + 150, 'колонка 2:1 платит ×3 по числу 5 (b491: 50 уже списаны при постановке)');
        eq(ev(`rouletteState().hist.slice(-1)[0]`), 5, 'число 5 в истории');
        ok(ev(`ROULETTE_BALL.on`) === true && ev(`ROULETTE_BALL.angle`) === -90, 'шарик после спина сидит под указателем');
    }

    console.log('\nD. Регрессии b488');
    {
        ev(`Math.random = function () { return 0.2; };`); // win 7 red
        ev(`rouletteClear(); rouletteSetChip(5); rouletteBet('red'); rouletteBet('red');`);
        const c1 = ev('state.coins');
        ev(`rouletteSpin()`);
        await sleep(400);
        eq(ev('state.coins'), c1 + 20, 'красное ×2 работает после редизайна (b491: 10 уже списаны при постановке)');
        ok(table().includes('Крутить'), 'кнопка «Крутить» на месте');
        ok(doc.getElementById('roulette-table').querySelectorAll('.rl-histn').length >= 2, 'история кругляшами rl-histn');
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
