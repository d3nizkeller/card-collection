// b493: кошелёк стола рулетки — в одну строку на всю ширину лобби.
// Жалоба владельца: «Сделай в одну линию и ширину» (скрин: узкая карточка
// справа со строками столбиком). Проверки:
//  1) сквозной тег: VERSION в sw.js, 8 раз в index.html, BUILD_TAG в build.py;
//  2) разметка: .rl-wallet без shrink-0, пять детей-SPAN в одну строку, панель
//     НЕ внутри flex-строки заголовка, а отдельная полоса на всю ширину;
//  3) CSS: display:flex + width:100% у .rl-wallet, зеркало зеро справа
//     (margin-left:auto), мобильный перенос в @media (max-width:640px);
//  4) поведение b491/b492 не сломано: точный баланс, буквы на столе, живой +/−,
//     спинов/побед и золотое зеро обновляются в новой полосе.
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

function rule(css, sel) {
    const i = css.indexOf(sel);
    if (i < 0) return '';
    const j = css.indexOf('}', i);
    return css.slice(i, j < 0 ? css.length : j + 1);
}

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
    console.log('A. Сквозной тег и исходники');
    const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
    const m = sw.match(/VERSION = '(nxmob(\d+))'/);
    ok(!!m, 'sw.js: VERSION читается');
    const tag = m ? m[1] : 'nxmob0', num = m ? +m[2] : 0;
    ok(num >= 237, 'тег не младше nxmob237 (факт ' + tag + ')');
    const idx = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    eq(idx.split('?v=' + tag).length - 1, 8, 'index.html: тег в 8 ссылках');
    const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');
    ok(bp.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG совпадает');

    ok(idx.includes('<div class="rl-wallet">'), 'index.html: полоса .rl-wallet без shrink-0');
    ok(!idx.includes('rl-wallet shrink-0'), 'index.html: старой узкой карточки нет');
    ok(idx.includes('<span class="rl-w-cap">') && idx.includes('<span class="rl-w-bal">'), 'index.html: подпись и баланс —SPAN в строке');
    eq(idx.split('<span class="rl-w-rows">').length - 1, 2, 'index.html: две ячейки строк (На столе, Спинов / побед)');
    ok(idx.includes('<span class="rl-w-jp">'), 'index.html: золотое зеро — пятый в строке');
    ok(!idx.includes('<p class="rl-w-'), 'index.html: вертикальных <p class="rl-w-…"> не осталось');
    ['id="rl-balance"', 'id="rl-delta"', 'id="rl-table-sum"', 'id="rl-spins"', 'id="rl-wins"', 'id="rl-jp-odds"'].forEach(s =>
        ok(idx.includes(s), 'index.html: ' + s + ' сохранён'));

    const css = fs.readFileSync(path.join(ROOT, 'assets', 'app.css'), 'utf8');
    const rw = rule(css, '.rl-wallet{');
    ok(rw.includes('display:flex') && rw.includes('width:100%'), 'app.css: .rl-wallet — flex-строка на всю ширину');
    ok(!css.includes('flex:0 1 250px'), 'app.css: старой фикс-ширины 250px нет');
    ok(rule(css, '.rl-w-jp{').includes('margin-left:auto'), 'app.css: золотое зеро прижато вправо');
    ok(rule(css, '.rl-w-jp{').includes('border-left:1px dashed'), 'app.css: пунктирный разделитель перед зеро');
    ok(/@media \(max-width:640px\)\{\s*\.rl-wallet\{/.test(css), 'app.css: мобильная подстройка строки');
    ok(/@media \(max-width:640px\)\{[\s\S]*?\.rl-w-jp\{margin-left:0/.test(css), 'app.css: на телефоне разделитель скрыт');

    console.log('\nB. Разметка полосы в DOM');
    const w = boot();
    const ev = s => w.eval('(function(){ ' + s + ' })()');
    ev('try { minerStart = function(){}; } catch(e){}; try { clearInterval(minerTickT); } catch(e){}; try { state.achievements.rich = 1; } catch(e){}');
    ev('switchTab("battle"); setBattleMode("roulette");');
    const wl = ev('return !!document.querySelector(".rl-wallet");');
    eq(wl, true, 'полоса .rl-wallet есть в DOM');
    eq(ev('return document.querySelectorAll(".rl-wallet").length;'), 1, 'полоса одна');
    eq(ev('return document.querySelector(".rl-wallet").children.length;'), 5, 'в полосе пять детей в одну линию');
    eq(ev('return Array.from(document.querySelector(".rl-wallet").children).every(c => c.tagName === "SPAN");'), true, 'все дети — SPAN (строка, не столбик)');
    eq(ev('return !!document.querySelector(".rl-wallet").closest(".justify-between");'), false, 'полоса НЕ внутри flex-строки заголовка');
    eq(ev('return document.querySelector(".rl-wallet").parentElement.className.includes("bg-gradient-to-r");'), true, 'полоса лежит в карточке лобби на всю ширину');
    eq(ev('const p = document.querySelector(".rl-wallet").previousElementSibling; return p.className.includes("justify-between") && !!p.querySelector("h2");'), true, 'перед полосой — заголовок лобби');

    console.log('\nC. Поведение b491/b492 в новой полосе');
    ev('window.__toasts = []; var __st = showToast; showToast = function(t, k){ window.__toasts.push(String(t) + "|" + (k || "")); return __st.apply(null, arguments); };');
    ev('jpcSet({ pRoulette: 0 }); state.coins = 1000; rouletteBets = {}; updateCoinDisplay(); renderRoulette(); rlSync();');
    eq(ev('return document.getElementById("rl-balance").textContent;'), '1' + TS + '000', 'точный баланс в строке полосы');
    ev('rouletteChip = 25; rouletteBet("red");');
    eq(ev('return document.getElementById("rl-balance").textContent;'), '975', 'баланс строки сразу упал до 975');
    eq(ev('return document.getElementById("rl-table-sum").textContent;'), '25', '«На столе» в строке: 25');
    ok(/−25/.test(ev('return document.getElementById("rl-delta").textContent;')), 'живой минус −25 в строке баланса');
    ev('rouletteClear();');
    eq(ev('return document.getElementById("rl-balance").textContent;'), '1' + TS + '000', '«Сброс» вернул баланс в строке');
    ok(/\+25/.test(ev('return document.getElementById("rl-delta").textContent;')), 'живой плюс +25');
    ev('rouletteBets = { n1: 409600 }; rlSync();');
    eq(ev('return document.getElementById("rl-table-sum").textContent;'), '409k', '«На столе» буквами: 409k');
    ev('rouletteBets = {}; state.coins = 5000; state.stats.rouletteSpins = 6; state.stats.rouletteWins = 1; rlSync();');
    eq(ev('return document.getElementById("rl-spins").textContent + "/" + document.getElementById("rl-wins").textContent;'), '6/1', '«Спинов / побед» 6 / 1 в строке');
    ok(/золотое зеро/.test(ev('return document.getElementById("rl-jp-odds").textContent;')), 'зеркало золотого зеро в строке');
    ev('rouletteChip = 25; rouletteBet("red"); Math.random = function(){ return (5 + 0.5) / 37; }; window.__nxRouletteMs = 20; rouletteSpin();');
    await sleep(300);
    eq(ev('return document.getElementById("rl-spins").textContent;'), '7', 'спин обновил счётчик в полосе');
    ok(/\+50/.test(ev('return document.getElementById("rl-delta").textContent;')), 'выигрыш +50 мигнул в строке');

    console.log('\n' + (fails ? 'FAIL: ' + fails + ' из ' + checks : 'OK: все ' + checks + ' проверок зелёные'));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.log('CRASH:', e && e.message); process.exit(1); });
