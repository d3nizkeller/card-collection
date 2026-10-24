// b492: суммы рулетки буквами («1k», «9.8m») + читаемое лицо фишки.
// Жалоба владельца: «сделай суммы 1k и все остальные буквы, и в фишках не видно
// сумму, потому что сумма написана белым на белом».
// Проверки:
//  1) исходники: бейджи/«На столе»/«Крутить»/#rl-table-sum/rlFlash через fmtCoins,
//     лицо фишки — span.rl-chip-val, баланс ПО-ПРЕЖНЕМУ точный (nxCoinsExact);
//  2) CSS: таблетка .rl-chip-val сплошным цветом фишки + мобильный размер;
//  3) поведение: ставки и удвоения дают «1.6k» на столе и в бейдже, сырое число
//     со стола исчезает, «Сброс» мигает «+1.6k», спин рапортует буквами,
//     мелкие суммы (25) остаются без букв, баланс точный с тонкими пробелами;
//  4) сквозной тег: nxmob236 в sw.js, 8 раз в index.html, BUILD_TAG в tools/build.py.
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
const TS = '\u2009'; // тонкий пробел nxCoinsExact

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
    console.log('A. Исходники: суммы буквами, лицо фишки — таблетка');
    {
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        ['class="rl-chipmini">${fmtCoins(bet)}</i>',
            'class="rl-chipmini">${fmtCoins(rouletteBets[id])}</i>',
            'title="Фишка ${fmtCoins(c)} монет"><span class="rl-chip-val">${fmtCoins(c)}</span></button>',
            'На столе: <b class="text-amber-300">${fmtCoins(total)}</b>',
            'Крутить · ${total ? fmtCoins(total) : \'—\'}',
            "t = fmtCoins(rouletteTotal());",
            "(d > 0 ? '+' : '−') + fmtCoins(Math.abs(d));"].forEach(s =>
            ok(app.includes(s), 'app.js: ' + s.slice(0, 64)));
        ok(/\/\/ b492: суммы НА СТОЛЕ/.test(app), 'app.js: комментарий b492 у кошелька стола');
        // b491 не сломан: баланс точный
        ok(app.includes("const t = nxCoinsExact(state.coins); if (bal.textContent !== t) bal.textContent = t;"), 'app.js: баланс стола по-прежнему точный (b491)');
        ok(/if \(rlExactHdr\(\)\) s = nxCoinsExact\(state\.coins\);/.test(app), 'app.js: шапка по-прежнему точная в лобби (b491)');
        ok(!/>`\$\{bet\}</.test(app) && !app.includes('rl-chipmini">${bet}</i>'), 'app.js: сырой суммы в бейдже не осталось');

        const css = fs.readFileSync(path.join(ROOT, 'assets', 'app.css'), 'utf8');
        ['.rl-chip-val{', '.rl-chip-1 .rl-chip-val{background:#475569}', '.rl-chip-5 .rl-chip-val{background:#b91c1c}',
            '.rl-chip-25 .rl-chip-val{background:#047857}', '.rl-chip-100 .rl-chip-val{background:#b45309}'].forEach(s =>
            ok(css.includes(s), 'app.css: ' + s));
        ok(/\.rl-chip-val\{[^}]*color:#f8fafc/.test(css), 'app.css: текст таблетки светлый на сплошном фоне');
        ok(/@media \(max-width:640px\)\{[\s\S]*?\.rl-chip-val\{width:24px;height:24px;font-size:10px\}/.test(css), 'app.css: мобильная таблетка 24px');
    }

    const w = boot();
    const ev = s => w.eval('(function(){ ' + s + ' })()');
    ev('try { minerStart = function(){}; } catch(e){}; try { clearInterval(minerTickT); } catch(e){}; try { state.achievements.rich = 1; } catch(e){}');
    ev('window.__toasts = []; var __st = showToast; showToast = function(t, k){ window.__toasts.push(String(t) + "|" + (k || "")); return __st.apply(null, arguments); };');
    ev('switchTab("battle"); setBattleMode("roulette");');
    ev('window.__nxRouletteMs = 20;');

    console.log('\nB. fmtCoins: буквы k/m/b/t');
    eq(ev('return fmtCoins(999);'), '999', 'до тысячи — без букв');
    eq(ev('return fmtCoins(1000);'), '1k', '1000 -> 1k');
    eq(ev('return fmtCoins(409600);'), '409k', '409600 -> 409k (сайтовый формат: >=100 без десятых)');
    eq(ev('return fmtCoins(9834496);'), '9.8m', '9834496 -> 9.8m');
    eq(ev('return fmtCoins(1234567890);'), '1.2b', '1234567890 -> 1.2b');

    console.log('\nC. Стол: крупные суммы буквами, баланс точный');
    ev('jpcSet({ pRoulette: 0 }); state.coins = 10000000; rouletteBets = {}; updateCoinDisplay(); renderRoulette();');
    ev('rouletteSetChip(100); rouletteBet("n12"); rouletteDouble(); rouletteDouble(); rouletteDouble(); rouletteDouble();');
    // 100 -> 200 -> 400 -> 800 -> 1600
    eq(ev('return rouletteTotal();'), 1600, 'стол на 1600 после четырёх удвоений');
    eq(ev('return document.querySelector("#roulette-table .rl-chipmini").textContent;'), '1.6k', 'бейдж на клетке — буквами');
    ok(ev('return document.getElementById("roulette-table").innerHTML.includes(">1600<");') === false, 'сырого 1600 в разметке стола нет');
    eq(ev('return document.querySelector("#roulette-table .text-amber-300").textContent;'), '1.6k', '«На столе:» — буквами');
    ok(/Крутить · 1\.6k/.test(ev('return document.querySelector("#roulette-table button.bg-rose-600").textContent;')), 'кнопка «Крутить · 1.6k»');
    eq(ev('return document.getElementById("rl-table-sum").textContent;'), '1.6k', 'кошелёк стола: сумма буквами');
    eq(ev('return document.getElementById("rl-balance").textContent;'), '9' + TS + '998' + TS + '400', 'баланс стола ТОЧНЫЙ (b491 жив)');
    eq(ev('return document.querySelector(".rl-chip-100 .rl-chip-val").textContent;'), '100', 'лицо фишки 100 — в таблетке');
    eq(ev('return document.querySelectorAll("#roulette-table .rl-chip .rl-chip-val").length;'), 4, 'таблетка у каждой из четырёх фишек');
    eq(ev('return document.querySelector(".rl-chip-5").title;'), 'Фишка 5 монет', 'title фишки 5 без букв');

    console.log('\nD. «Сброс» мигает буквами, мелкие суммы без букв');
    ev('rouletteClear();');
    ok(/\+1\.6k/.test(ev('return document.getElementById("rl-delta").textContent;')), 'живой плюс «+1.6k» после возврата');
    eq(ev('return document.getElementById("rl-table-sum").textContent;'), '0', 'стол пустой');
    ev('rouletteSetChip(25); rouletteBet("red");');
    eq(ev('return document.querySelector("#roulette-table .rl-chipmini").textContent;'), '25', 'мелкая ставка 25 — без букв');
    eq(ev('return document.querySelector("#roulette-table .text-amber-300").textContent;'), '25', '«На столе: 25» без букв');

    console.log('\nE. Спин рапортует буквами');
    ev('rouletteClear(); rouletteSetChip(100); rouletteBet("n7"); rouletteDouble(); rouletteDouble(); rouletteDouble(); rouletteDouble();');
    ev('rouletteSpin();');
    await sleep(400);
    {
        const toasts = ev('return window.__toasts.join("\\n");');
        ok(/[0-9](\.[0-9])?[kmbt]\b/.test(toasts), 'тост спина с буквой разряда: ' + toasts.split('\n').pop());
        ok(!/−1600|\+1600|1600 монет/.test(toasts), 'сырого 1600 в тосте нет');
    }
    ok(ev('return document.getElementById("rl-balance").textContent;').length > 0, 'баланс после спина непустой');

    console.log('\nF. Сквозной тег nxmob236');
    {
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const tag = (sw.match(/VERSION = '(nxmob\d+)';/) || [])[1];
        ok(!!tag, 'sw.js: боевой тег присутствует');
        ok(Number(tag && tag.replace('nxmob', '')) >= 236, 'sw.js: тег не ниже nxmob236 (факт ' + tag + ')');
        const idx = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        eq(idx.split(tag).length - 1, 8, 'index.html: тег в 8 ссылках на ассеты');
        const bld = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');
        ok(bld.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG совпадает с тегом sw.js');
    }

    console.log('\n' + (fails ? 'FAIL: ' + fails + ' из ' + checks : 'OK: ' + checks + ' проверок b492'));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.log('CRASH:', e && e.message); process.exit(1); });
