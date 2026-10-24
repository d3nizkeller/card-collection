// b490: номера рулетки в своих секторах + остановка колеса точно под указателем.
// Жалоба владельца: «зачем в колесе пустые сектора и история работает не правильно».
// Проверки:
//  1) исходники: номер рисуется в центре клина (translate RS*0.85 + rotate 90°),
//     старого смещения «-RS * 0.85» больше нет;
//  2) после спина экранный угол центра выигрышного клина = -90° (под указателем),
//     шарик и первыйchip истории указывают на тот же номер;
//  3) история красится по цвету числа (красные/чёрные/зеро);
//  4) регресс b488/b489: споты, фетр, фишки на месте;
//  5) сквозной тег: nxmob234 в sw.js, 8 раз в index.html, BUILD_TAG в tools/build.py.
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.resolve(__dirname, '..');
let fails = 0, checks = 0;
function ok(cond, name) {
    checks++;
    if (!cond) { fails++; console.log('  FAIL:', name); }
}
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
    const appSrc = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');

    // 1) исходники: новая геометрия номера
    ok(appSrc.indexOf('g.translate(RS * 0.85, 0);') !== -1, 'номер выносится на радиус клина');
    ok(/g\.rotate\(i \* sector\);\s*g\.translate\(RS \* 0\.85, 0\);\s*g\.rotate\(Math\.PI \/ 2\);/.test(appSrc), 'номер доворачивается вдоль радиуса');
    ok(appSrc.indexOf('-RS * 0.85') === -1, 'старого смещения номера на 90° больше нет');
    ok(appSrc.indexOf('const desired = ((-90 - idx * sector) % 360 + 360) % 360;') !== -1, 'новая формула остановки под указатель');
    ok(appSrc.indexOf('(360 - (idx * sector + sector / 2)) - 90') === -1, 'старой формулы с пол-сектора мимо больше нет');

    const w = boot();
    const ev = s => w.eval('(function(){ ' + s + ' })()');
    ev('try { minerStart = function(){}; } catch(e){}; try { clearInterval(minerTickT); } catch(e){}; try { state.achievements.rich = 1; } catch(e){}');
    ev('switchTab("battle"); setBattleMode("roulette");');
    ev('try { window.__nxRouletteMs = 20; } catch(e){}');

    // 2) остановка точно под указателем для набора чисел
    const wins = [0, 5, 17, 32, 34, 21, 8, 11, 33];
    for (const win of wins) {
        ev('Math.random = function(){ return (' + win + ' + 0.5) / 37; }; state.coins = 100000; rouletteBets = {}; rouletteBets[' + win + '] = 10; rouletteSpinning = false; rouletteSpin();');
        await sleep(150);
        const r = ev('return { ang: rouletteAngle, hist: rouletteState().hist.slice(-1), idx: ROULETTE_ORDER.indexOf(' + win + ') };');
        const sector = 360 / 37;
        const desired = ((-90 - r.idx * sector) % 360 + 360) % 360;
        const ang = ((r.ang % 360) + 360) % 360;
        ok(Math.abs(ang - desired) < 0.01, 'win ' + win + ': колесо встало на ' + desired.toFixed(1) + '° (факт ' + ang.toFixed(2) + '°)');
        const screen = ((r.ang + r.idx * sector) % 360 + 360) % 360;
        ok(Math.abs(screen - 270) < 0.01, 'win ' + win + ': центр клина под указателем (-90°)');
        ok(r.hist[0] === win, 'win ' + win + ': история начинается с выпавшего числа');
    }

    // 3) цвета истории: скриншот владельца 33/8/11/5
    ev('rouletteState().hist = [33, 8, 11, 5]; renderRoulette();');
    const histHtml = ev('return document.getElementById("lobby-roulette").innerHTML;');
    ok(/rl-histn rl-hist-black">33</.test(histHtml), '33 в истории — чёрный чип');
    ok(/rl-histn rl-hist-black">8</.test(histHtml), '8 в истории — чёрный чип');
    ok(/rl-histn rl-hist-black">11</.test(histHtml), '11 в истории — чёрный чип');
    ok(/rl-histn rl-hist-red">5</.test(histHtml), '5 в истории — красный чип');
    ev('rouletteState().hist = [0]; renderRoulette();');
    ok(/rl-histn rl-hist-zero">0</.test(ev('return document.getElementById("lobby-roulette").innerHTML;')), '0 в истории — зеро-чип');

    // 4) регресс b488/b489
    ok(ev('return rouletteSpotDefs().length;') >= 49, 'споты на месте (b488/b489)');
    ev('renderRoulette();');
    ok(ev('return !!document.querySelector(".rl-felt");'), 'казино-фетр на месте (b489)');
    ok(ev('return !!document.querySelector(".rl-chip.rl-chip-25");'), 'фишки казино на месте (b489)');

    // 5) сквозной тег
    const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
    const idx = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const bld = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');
    const m = sw.match(/VERSION\s*=\s*'([^']+)'/);
    const tag = m && m[1];
    ok(tag === 'nxmob234', 'sw.js VERSION = nxmob234');
    ok((idx.match(/nxmob234/g) || []).length === 8, 'index.html: тег 8 раз');
    ok(/BUILD_TAG\s*=\s*'nxmob234'/.test(bld), 'tools/build.py BUILD_TAG = nxmob234');
    ok(tag && idx.indexOf('assets/app.js?v=' + tag) !== -1, 'index.html тянет app.js с тегом');

    console.log(fails ? 'b490: FAIL (' + fails + '/' + checks + ')' : 'b490: OK (' + checks + ' проверок)');
    process.exit(fails ? 1 : 0);
})().catch(e => { console.log('b490: CRASH', e.message); process.exit(1); });
