/* b431: топ джекпота обновляется в реальном времени.

   A. Топ-3 = три последних срыва (по t), а не три крупнейших: новый срыв
      виден сразу, даже если он меньше старых; в строке — дата И время.
   B. jpPullLight перерисовывает витрину каждый pull, даже без изменений.
   C. Сторож синхронизации: 60 с тишины при видимой вкладке → jpSyncNow.
   D. Окно зала славы 40 записей.
   E. Заголовок блока — «Последние срывы джекпота» с live-точкой (3 баннера).

   Запуск:  node tools/test-b431.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + a + (a === b ? '' : ' (ждём ' + b + ')'));
const sleep = ms => new Promise(r => setTimeout(r, ms));

function boot(fetchHandler) {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const dom = new JSDOM(html, {
        runScripts: 'dangerously',
        pretendToBeVisual: true,
        url: 'https://d3nizkeller.github.io/card-collection/',
    });
    const w = dom.window;
    const calls = [];
    w.HTMLCanvasElement.prototype.getContext = () => null;
    w.HTMLMediaElement.prototype.play = function () { return Promise.resolve(); };
    w.HTMLMediaElement.prototype.pause = function () {};
    Object.defineProperty(w, 'fetch', {
        value: (url, opt) => {
            calls.push({ url: String(url), method: (opt && opt.method) || 'GET' });
            if (fetchHandler) return fetchHandler(String(url), opt);
            return Promise.resolve({ ok: false, status: 0, text: () => Promise.resolve(''), json: () => Promise.resolve(null) });
        },
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
    return { w, ev: s => w.eval(s), doc: w.document, calls };
}
const resp = obj => Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve(JSON.stringify(obj)), json: () => Promise.resolve(obj) });

(async () => {
    console.log('\nA. Топ-3 — последние срывы, с датой и временем');
    const A = boot();
    const av = A.ev;
    const tOld = 1791980000000, tNew = tOld + 60000;
    av('jackpot.hall = [' +
       '{ n: "Старый гигант", a: 900000000000, t: ' + tOld + ' },' +
       '{ n: "Свежий срыв", a: 5000, t: ' + tNew + ' }]; jackpotRender()');
    const list = A.doc.getElementById('slots-jp-top-list').innerHTML;
    ok(list.indexOf('Свежий срыв') < list.indexOf('Старый гигант'), 'свежий срыв стоит ПЕРВЫМ, хотя он меньше');
    ok(/🥇/.test(list.slice(0, list.indexOf('Свежий срыв') + 20)), 'свежий срыв с медалью первого места');
    const d = new Date(tNew);
    const expect = d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' }) + ' ' + d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    ok(list.indexOf(expect) >= 0, 'в строке топа дата и время: ' + expect);

    console.log('\nB. jpPullLight перерисовывает витрину каждый pull');
    const remote = { jp: { led: { q: 1000 }, won: {}, wins: {}, names: {}, hall: [{ n: 'Облачный', a: 777, t: tNew + 5 }], ep: 0 }, updatedAt: '1-x' };
    const B = boot(() => resp(remote));
    const bv = B.ev;
    await bv('jpPullLight(), new Promise(r => setTimeout(r, 300))');
    const filled = B.doc.getElementById('slots-jp-top-list').innerHTML;
    ok(filled.indexOf('Облачный') >= 0, 'после pull топ показывает запись из облака');
    B.doc.getElementById('slots-jp-top-list').innerHTML = ''; // имитируем «залипший» DOM
    await bv('jpPullLight(), new Promise(r => setTimeout(r, 300))');
    ok(B.doc.getElementById('slots-jp-top-list').innerHTML.indexOf('Облачный') >= 0, 'pull без изменений слияния всё равно перерисовал витрину');

    console.log('\nC. Сторож синхронизации');
    const C = boot(() => resp({ jp: { led: {}, won: {}, wins: {}, hall: [], ep: 0 }, updatedAt: '1-x' }));
    const cv = C.ev;
    cv('jpLastAt = Date.now() - 70000');
    const n0 = C.calls.length;
    cv('nxSyncWatchdog()');
    await sleep(400);
    ok(C.calls.length > n0, '60 с тишины → сторож дёрнул синхронизацию');
    cv('jpLastAt = Date.now()');
    const n1 = C.calls.length;
    cv('nxSyncWatchdog()');
    await sleep(200);
    eq(C.calls.length, n1, 'свежая синхронизация → сторож молчит');

    console.log('\nD. Окно зала славы 40');
    const D = boot();
    const dv = D.ev;
    const many = [];
    for (let i = 0; i < 60; i++) many.push({ n: 'w' + i, a: i, t: 1791900000000 + i * 1000 });
    dv('jackpotMerge({ hall: ' + JSON.stringify(many) + ' })');
    eq(dv('jackpot.hall.length'), 40, 'зал держит 40 записей (было 20)');

    console.log('\nE. Заголовок блока');
    const E = boot();
    const heads = E.doc.querySelectorAll('.jp-top-title');
    eq(heads.length, 3, 'три баннера (Слоты/Сетка/Линии)');
    ok(Array.from(heads).every(h => /Последние срывы джекпота/.test(h.textContent)), 'заголовок: «Последние срывы джекпота»');
    ok(Array.from(heads).every(h => h.querySelector('.animate-pulse')), 'live-точка пульсирует');

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
