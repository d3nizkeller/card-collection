/* b436: тихое фоновое авто-обновление — игра сама обновляется и не отвлекает игроков.

   A. Старая вкладка замечает новую сборку БЕЗ баннера: тост «Обновить» удалён,
      регистрируется window.__nxAutoUpd, активная видимая вкладка не перезагружается.
   B. Hot-swap: новая сборка перенесла общий документ банка (v3 → v9) — jpPath
      переключается на лету, свой банк пушится уже в новый документ.
   C. Документ не менялся — hot-swap не происходит.
   D. Вкладку скрыли — тихая перезагрузка случается сама (фон = незаметно),
      банк перед уходом отправлен (jpFlush/sendBeacon), тег помечен в sessionStorage.
   E. Видимая вкладка: перезагрузка только после 2 минут простоя.
   F. Спин крутится — перезагрузки нет, даже если простой есть.
   G. Играет трек карты — перезагрузки нет, даже в фоне.
   H. Открыто модальное окно (просмотр карты) — перезагрузки нет.
   I. Защита от цикла: в тег уже заходили после перезагрузки — второй раз не грузим.
   J. Санити: в обычном состоянии модалок не видно, видимая активная вкладка «не безопасна».

   Запуск:  node tools/test-b436.js
*/
const fs = require('fs');
const path = require('path');
const jsdomPkg = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');
const { JSDOM, VirtualConsole } = jsdomPkg;

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + a + (a === b ? '' : ' (ждём ' + b + ')'));

function boot(fetchHandler, ownTag) {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    // jsdom не даёт подменить location.reload (own non-configurable): настоящая
    // перезагрузка в jsdom — это «Not implemented: navigation», глушим её тут,
    // а факт перезагрузки видим по window.__nxAutoUpd.reloads и sessionStorage
    const vc = new VirtualConsole();
    vc.on('jsdomError', () => {});
    vc.on('error', () => {});
    const dom = new JSDOM(html, {
        runScripts: 'dangerously',
        pretendToBeVisual: true,
        virtualConsole: vc,
        url: 'https://d3nizkeller.github.io/card-collection/',
    });
    const w = dom.window;
    const calls = [];
    const ctx2d = () => new Proxy({}, {
        get(t, k) {
            if (k === 'canvas') return { width: 256, height: 256, style: {} };
            if (k === 'measureText') return () => ({ width: 10 });
            if (k === 'getImageData') return () => ({ data: new Uint8ClampedArray(4) });
            if (k === 'createLinearGradient' || k === 'createRadialGradient') return () => ({ addColorStop() {} });
            if (k === 'createPattern') return () => null;
            return t[k] !== undefined ? t[k] : (() => {});
        },
        set(t, k, v) { t[k] = v; return true; },
    });
    w.HTMLCanvasElement.prototype.getContext = kind => (kind === '2d' ? ctx2d() : null);
    w.HTMLCanvasElement.prototype.toDataURL = () => 'data:image/png;base64,';
    w.HTMLMediaElement.prototype.play = function () { return Promise.resolve(); };
    w.HTMLMediaElement.prototype.pause = function () {};
    w.HTMLMediaElement.prototype.load = function () {};
    Object.defineProperty(w, 'fetch', {
        value: (url, opt) => {
            calls.push({ url: String(url), method: (opt && opt.method) || 'GET' });
            return fetchHandler ? fetchHandler(String(url), opt, calls) : Promise.resolve({ ok: false, status: 0, text: () => Promise.resolve(''), json: () => Promise.resolve(null) });
        },
        configurable: true,
    });
    w.navigator.sendBeacon = () => { w.__beacons = (w.__beacons || 0) + 1; return true; };
    w.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} };
    w.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
    w.matchMedia = w.matchMedia || (q => ({ matches: false, media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }));
    w.THREE = new Proxy({}, { get: () => function () { return {}; } });
    if (ownTag) {
        const mk = w.document.createElement('script');
        mk.src = 'https://d3nizkeller.github.io/card-collection/assets/app.js?v=' + ownTag;
        w.document.head.appendChild(mk);
    }
    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
    w.document.body.appendChild(sc);
    return { w, ev: s => w.eval(s), doc: w.document, calls };
}

const resp = obj => Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve(JSON.stringify(obj)), json: () => Promise.resolve(obj) });
const sleep = ms => new Promise(r => setTimeout(r, ms));
// сервер отдаёт сборку serverTag; app.js текст — appJsText (для hot-swap пробы)
const server = (serverTag, appJsText) => (url) => {
    if (String(url).indexOf('index.html') >= 0)
        return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve('<script src="assets/app.js?v=' + serverTag + '"></script>'), json: () => Promise.resolve(null) });
    if (String(url).indexOf('assets/app.js') >= 0)
        return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve(appJsText || ''), json: () => Promise.resolve(null) });
    return resp({ jp: { led: {}, won: {}, wins: {}, names: {}, hall: [], ep: 0 }, jpc: null, mk: null, st: null, updatedAt: '1-x' });
};

(async () => {
    // ===== A. детект без баннера =====
    console.log('\nA. b436: баннера нет — авто-обновление работает тихо');
    const A = boot(server('nxmob99', 'nexus-tcg-jackpot-v3 nexus-jackpot-v3.json'), 'nxmob83');
    const av = A.ev;
    await av('nxAutoUpdCheck(), new Promise(r => setTimeout(r, 400))');
    ok(!A.doc.getElementById('nx-ver-toast'), 'баннер «Версия игры обновилась… Обновить» не появляется');
    eq((A.doc.getElementById('toast-container') || { childElementCount: 0 }).childElementCount, 0, 'в контейнере тостов пусто');
    eq(av('(window.__nxAutoUpd || {}).tag'), 'nxmob99', 'новый тег зарегистрирован в window.__nxAutoUpd');
    eq(av('(window.__nxAutoUpd || {}).plan'), 'nxmob99', 'перезагрузка запланирована на тихий момент');
    eq(av('(window.__nxAutoUpd || {}).reloads || 0'), 0, 'видимая активная вкладка НЕ перезагружена');

    // ===== B. hot-swap документа банка =====
    console.log('\nB. b436: hot-swap — банк переехал на v9, вкладка перешла без перезагрузки');
    const B = boot(server('nxmob99', '/* nxmob99 */ nexus-tcg-jackpot-v9 и комната nexus-jackpot-v9.json'), 'nxmob83');
    const bv = B.ev;
    await bv('nxAutoUpdCheck(), new Promise(r => setTimeout(r, 400))');
    eq(bv('(window.__nxJpSwap || {}).doc'), 'nexus-tcg-jackpot-v9', 'jpSwap выставлен на новый документ');
    ok(String(bv('jpPath()')).indexOf('nexus-tcg-jackpot-v9') >= 0, 'jpPath() теперь смотрит на v9: ' + bv('jpPath()'));
    eq(bv('(window.__nxAutoUpd || {}).swapped'), '9', 'в диагностике отмечен hot-swap');
    await bv('jpSyncNow(), new Promise(r => setTimeout(r, 700))');
    ok(B.calls.some(c => c.method !== 'GET' && String(c.url).indexOf('v9') >= 0), 'свой банк опубликован в новый общий документ');

    // ===== C. документ тот же — swap не нужен =====
    console.log('\nC. b436: документ не менялся — hot-swap не происходит');
    const Cc = boot(server('nxmob99', 'nexus-tcg-jackpot-v3 nexus-jackpot-v3.json'), 'nxmob83');
    await Cc.ev('nxAutoUpdCheck(), new Promise(r => setTimeout(r, 400))');
    eq(Cc.ev('window.__nxJpSwap === undefined'), true, '__nxJpSwap не выставлен');
    eq(Cc.ev('(window.__nxAutoUpd || {}).swapped || ""'), '', 'swapped пустой');

    // ===== D. скрытая вкладка обновляется сама =====
    console.log('\nD. b436: вкладку скрыли — тихая перезагрузка в фоне');
    const D = boot(server('nxmob99', 'nexus-tcg-jackpot-v3 nexus-jackpot-v3.json'), 'nxmob83');
    const dv = D.ev;
    await sleep(300); // даём init-слушателям visibilitychange встать
    Object.defineProperty(D.doc, 'hidden', { value: true, configurable: true });
    D.doc.dispatchEvent(new D.w.Event('visibilitychange')); // b436: скрытие запускает проверку
    await sleep(600);
    ok((dv('(window.__nxAutoUpd || {}).reloads || 0')) >= 1, 'фоновая вкладка перезагрузилась сама: ' + dv('(window.__nxAutoUpd || {}).reloads || 0'));
    ok((D.w.__beacons || 0) >= 1, 'банк отправлен перед перезагрузкой (jpFlush/sendBeacon)');
    ok(String(dv('sessionStorage.getItem("nxAutoUpdTried") || ""')).indexOf('nxmob99') >= 0, 'тег помечен как посещённый (защита от цикла)');

    // ===== E. видимая: только после простоя =====
    console.log('\nE. b436: видимая вкладка — перезагрузка лишь после 2 минут простоя');
    const E = boot(null, 'nxmob83');
    const evv = E.ev;
    evv('nxSilentReloadPlan("nxmob777")'); // ставит интервал-пробу и сразу пробует
    eq(evv('(window.__nxAutoUpd || {}).reloads || 0'), 0, 'игрок активен (касания свежие) — перезагрузки нет');
    eq(evv('nxAutoUpdTimer') > 0, true, 'план стоит и ждёт тихий момент');
    evv('window.__nxLastInputAt = Date.now() - 130000');
    evv('nxSilentReloadTry("nxmob777")');
    eq(evv('(window.__nxAutoUpd || {}).reloads || 0'), 1, 'простой 2+ минуты — перезагрузка случилась сама');
    eq(evv('nxAutoUpdTimer') > 0, true, 'интервал-проба продолжает работать');

    // ===== F. спин важнее обновления =====
    console.log('\nF. b436: спин не рвём');
    const F = boot(null, 'nxmob83');
    const fv = F.ev;
    fv('window.__nxLastInputAt = Date.now() - 130000; slots.spinning = true;');
    fv('nxSilentReloadTry("nxmob777")');
    eq(fv('(window.__nxAutoUpd || {}).reloads || 0'), 0, 'slots.spinning — перезагрузки нет');
    fv('slots.spinning = false; grid.spinning = true; nxSilentReloadTry("nxmob777")');
    eq(fv('(window.__nxAutoUpd || {}).reloads || 0'), 0, 'grid.spinning — перезагрузки нет');
    fv('grid.spinning = false; lines.spinning = true; nxSilentReloadTry("nxmob777")');
    eq(fv('(window.__nxAutoUpd || {}).reloads || 0'), 0, 'lines.spinning — перезагрузки нет');

    // ===== G. музыка важнее обновления =====
    console.log('\nG. b436: трек карты не обрываем');
    const G = boot(null, 'nxmob83');
    const gv = G.ev;
    Object.defineProperty(G.doc, 'hidden', { value: true, configurable: true });
    gv('CardMusic.audio = { paused: false };');
    gv('nxSilentReloadTry("nxmob777")');
    eq(gv('(window.__nxAutoUpd || {}).reloads || 0'), 0, 'CardMusic играет даже в фоне — перезагрузки нет');
    gv('CardMusic.audio = { paused: true }; nxSilentReloadTry("nxmob777")');
    eq(gv('(window.__nxAutoUpd || {}).reloads || 0'), 1, 'трек остановлен — фоновая перезагрузка разрешена');

    // ===== H. открытая модалка важнее обновления =====
    console.log('\nH. b436: модальные окна не сносим перезагрузкой');
    const H = boot(null, 'nxmob83');
    const hv = H.ev;
    hv('window.__nxLastInputAt = Date.now() - 130000;');
    hv('document.getElementById("modal-inspect").classList.remove("hidden")');
    hv('nxSilentReloadTry("nxmob777")');
    eq(hv('(window.__nxAutoUpd || {}).reloads || 0'), 0, 'открыт просмотр карты — перезагрузки нет');
    hv('document.getElementById("modal-inspect").classList.add("hidden"); document.getElementById("modal-unboxing").classList.remove("hidden"); nxSilentReloadTry("nxmob777")');
    eq(hv('(window.__nxAutoUpd || {}).reloads || 0'), 0, 'идёт вскрытие пака — перезагрузки нет');

    // ===== I. защита от цикла =====
    console.log('\nI. b436: нет цикла перезагрузок');
    const I = boot(null, 'nxmob83');
    const iv = I.ev;
    iv('sessionStorage.setItem("nxAutoUpdTried", "nxmob777")');
    iv('window.__nxLastInputAt = Date.now() - 130000');
    iv('nxSilentReloadPlan("nxmob777")');
    await sleep(50);
    eq(iv('(window.__nxAutoUpd || {}).reloads || 0'), 0, 'в этот тег уже заходили — вторую перезагрузку не делаем');
    eq(iv('nxAutoUpdTimer'), 0, 'план остановлен (интервал снят)');

    // ===== J. санити =====
    console.log('\nJ. b436: санити проверок безопасности');
    const J = boot(null, 'nxmob83');
    const jv = J.ev;
    eq(jv('nxModalOpen()'), false, 'в обычном состоянии модалок не видно');
    eq(jv('nxReloadSafe()'), false, 'видимая активная вкладка не «безопасна» для перезагрузки');
    eq(jv('nxAudioPlaying()'), false, 'музыка по умолчанию не играет');

    console.log('\n' + (fails ? '❌ ПРОВАЛ: ' + fails + ' из ' + checks : '✅ b436: все ' + checks + ' проверок зелёные'));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
