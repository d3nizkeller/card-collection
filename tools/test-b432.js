/* b432: в топ джекпота попадают только игроки С ИМЕНЕМ.

   A. jpHallNamed: флаг nm и старый зал без флага (префикс «Игрок-»).
   B. Топ-3 и «последний срыв» — только именные; безымянные не видны.
   C. Все срывы без имён — честная плашка вместо пустого топа.
   D. jackpotWin: флаг nm по факту имени + подсказка безымянному победителю.
   E. Регрессия b431: среди именных — сортировка по свежести.

   Запуск:  node tools/test-b432.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + a + (a === b ? '' : ' (ждём ' + b + ')'));
const sleep = ms => new Promise(r => setTimeout(r, ms));

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
    console.log('\nA. jpHallNamed');
    const A = boot();
    const av = A.ev;
    eq(av('jpHallNamed({ nm: 1, n: "Игрок-1234" })'), true, 'nm=1 — именной, даже если имя похоже на заглушку');
    eq(av('jpHallNamed({ nm: 0, n: "Денис" })'), false, 'nm=0 — безымянный, даже если имя красивое');
    eq(av('jpHallNamed({ n: "Денис Keller" })'), true, 'старая запись с именем — именная');
    eq(av('jpHallNamed({ n: "Игрок-5r6s" })'), false, 'старая запись-заглушка — безымянная');
    eq(av('jpHallNamed(null)'), false, 'null безопасен');

    console.log('\nB. Топ и «последний срыв» — только именные');
    const B = boot();
    const bv = B.ev;
    const t1 = 1791990000000, t2 = t1 + 60000;
    bv('jackpot.hall = [' +
       '{ n: "Игрок-aaaa", a: 22000000000000, t: ' + t2 + ', nm: 0 },' +
       '{ n: "Денис Keller", a: 5000, t: ' + t1 + ', nm: 1 }]; jackpotRender()');
    const list = B.doc.getElementById('slots-jp-top-list').innerHTML;
    ok(list.indexOf('Игрок-aaaa') < 0, 'безымянный срыв +22q в топ НЕ попал');
    ok(list.indexOf('Денис Keller') >= 0, 'именной срыв в топе');
    const wtxt = B.doc.getElementById('slots-jp-winner').textContent;
    ok(wtxt.indexOf('Денис Keller') >= 0 && wtxt.indexOf('Игрок-aaaa') < 0, '«Последний джекпот» — тоже только именной: ' + wtxt.slice(0, 46) + '…');

    console.log('\nC. Все срывы без имён — плашка-подсказка');
    const C = boot();
    C.ev('jackpot.hall = [{ n: "Игрок-bbbb", a: 1000, t: 1, nm: 0 }]; jackpotRender()');
    const empty = C.doc.getElementById('slots-jp-top-list').innerHTML;
    ok(/Все срывы пока без имени/.test(empty), 'плашка: ' + (empty.match(/>[^<]*без имени[^<]*</) || ['?'])[0]);
    C.ev('jackpot.hall = []; jackpotRender()');
    ok(/ещё не срывали/.test(C.doc.getElementById('slots-jp-top-list').innerHTML), 'пустой зал — прежняя плашка');

    console.log('\nD. jackpotWin ставит флаг и подсказывает');
    const D = boot();
    const dv = D.ev;
    dv('jackpot.led = {}; jackpot.won = {}; jackpot.hall = [];');
    dv('jackpotWin()');
    eq(dv('jackpot.hall[0].nm'), 0, 'без имени запись получила nm=0');
    await sleep(1600);
    ok(/Введите имя игрока/.test(toasts(D.doc)), 'безымянный победитель получил подсказку про имя');
    const E = boot();
    const ev2 = E.ev;
    ev2('setPlayerName("Денис Keller")');
    ev2('jackpot.led = {}; jackpot.won = {}; jackpot.hall = [];');
    ev2('jackpotWin()');
    eq(ev2('jackpot.hall[0].nm'), 1, 'с именем запись получила nm=1');

    console.log('\nE. Регрессии b431/b433: среди именных топ по сумме, строка последнего — по свежести');
    const F = boot();
    F.ev('jackpot.hall = [' +
       '{ n: "Ранний", a: 999000, t: ' + t1 + ', nm: 1 },' +
       '{ n: "Свежий", a: 1000, t: ' + t2 + ', nm: 1 }]; jackpotRender()');
    const l2 = F.doc.getElementById('grid-jp-top-list').innerHTML;
    ok(l2.indexOf('Ранний') < l2.indexOf('Свежий'), 'b433: топ по сумме — крупнее выше');
    ok(F.doc.getElementById('grid-jp-winner').textContent.indexOf('Свежий') >= 0, 'b431: «последний срыв» — свежайший именной');

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
