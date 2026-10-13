/* b418: банк снова растёт (счётчики-«вёдра»), сброс настроек и сброс топа.

   Жалоба владельца: «джекпот не усиливается от проигрышей пользователей»,
   тост «Мимо — банк джекпота вырос на +0 и теперь 1k» + просьба добавить
   в Студию кнопки «Стандартные настройки» и «Сбросить топ джекпотов сайта».

   Причина «+0»: потолок b416 (JP_LED_CAP = 1e13 на один счётчик) сам стал
   потолком — владелец докормил led до ровно 1e13, и jpLedAdd() возвращал 0.
   Теперь счётчик многомерный: переполнение дописывается в вёдра cid#N.

   A. Регрессия жалобы: led упёрт в потолок — проигрыши и ставки снова растут.
   B. Вёдра: переполнение, точность суммы, «копят банк» считает игрока один раз.
   C. Зал славы: сброс топа tombstone'ом hallCut — мусор не воскресает слиянием.
   D. «Стандартные настройки»: заводские проценты возвращаются и публикуются.
   E. Кнопки есть в разметке Студии.
   F. Регрессии b416/b417: ремонт мусора, рост банка, тосты нехватки.

   Запуск:  node tools/test-b418.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + a + (a === b ? '' : ' (ждём ' + b + ')'));

function boot(ledger, cid) {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const dom = new JSDOM(html, {
        runScripts: 'dangerously',
        pretendToBeVisual: true,
        url: 'https://d3nizkeller.github.io/card-collection/',
    });
    const w = dom.window;
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
        value: () => Promise.resolve({ ok: false, status: 0, text: () => Promise.resolve(''), json: () => Promise.resolve(null) }),
        configurable: true,
    });
    w.navigator.sendBeacon = () => true;
    w.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} };
    w.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
    w.matchMedia = w.matchMedia || (q => ({ matches: false, media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }));
    w.THREE = new Proxy({}, { get: () => function () { return {}; } });
    if (cid) w.localStorage.setItem('nexus_jackpot_cid', cid);
    if (ledger) w.localStorage.setItem('nexus_jackpot_v2', JSON.stringify(ledger));
    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
    w.document.body.appendChild(sc);
    return { w, ev: s => w.eval(s), doc: w.document };
}

(async () => {
    const CAP = 1e13, BUCKET = 1e12;

    // ===== A. регрессия жалобы: счётчик упёрт в потолок =====
    console.log('\nA. Счётчик владельца упёрт в потолок 1e13 (состояние с сайта)');
    const A = boot({
        led: { pl4lq4hk5sk: CAP },
        won: { pl4lq4hk5sk: CAP - 3100 },
        wins: { pl4lq4hk5sk: 282 }, names: { pl4lq4hk5sk: 'Денис Keller' }, hall: [],
    }, 'pl4lq4hk5sk');
    const av = A.ev;
    av('cloudGuest = () => false');
    eq(av('JACKPOT_CID'), 'pl4lq4hk5sk', 'cid владельца');
    eq(av('jpLedNum(jackpot.led[JACKPOT_CID])'), CAP, 'основной счётчик полон (1e13) — как на сайте');
    eq(av('jackpotPool()'), 4100, 'банк = пол 1000 + избыток 3100 (как на скриншоте 4.1k)');
    const p0 = av('jackpotPool()');
    const got = av('jackpotOnLoss(250000)');
    eq(got, 250000, 'проигрыш 250k ДОШЁЛ в банк (было: +0)');
    eq(av('jackpotPool()') - p0, 250000, 'банк вырос на 250k');
    eq(av('jpLedNum(jackpot.led[JACKPOT_CID + "#1"])'), 250000, 'переполнение ушло в ведро cid#1');
    const p1 = av('jackpotPool()');
    av('jackpotFeed(10000)');
    eq(av('jackpotPool()') - p1, 10000, 'ставка 10k тоже растит банк');
    ok(av('jpLedSum(jackpot.led)') <= 9e15, 'сумма реестра в пределах точности double');

    // ===== B. вёдра =====
    console.log('\nB. Вёдра: переполнение, точность, «копят банк»');
    const B = boot(null);
    const bv = B.ev;
    bv('jackpot.led = {}; jackpot.won = {};');
    eq(bv('jpLedAdd("led", "px", 2.5e12)'), 2.5e12, 'взнос 2.5t лёг целиком');
    eq(bv('jpLedNum(jackpot.led["px"])'), BUCKET, 'ведро 0 = 1e12');
    eq(bv('jpLedNum(jackpot.led["px#1"])'), BUCKET, 'ведро 1 = 1e12');
    eq(bv('jpLedNum(jackpot.led["px#2"])'), 0.5e12, 'ведро 2 = 0.5t');
    eq(bv('jpLedOf("led", "px")'), 2.5e12, 'jpLedOf суммирует все вёдра игрока');
    eq(bv('jpLedSum(jackpot.led)'), 2.5e12, 'jpLedSum видит вёдра');
    eq(bv('jackpotPlayers()'), 1, '«копят банк»: три вёдра = один игрок');
    eq(bv('jpLedAdd("led", "px", 1e18)'), 4096 * BUCKET - 2.5e12, 'взнос 1e18 обрезан суммарной ёмкостью вёдер (4096 × 1e12)');
    ok(bv('jpLedOf("led", "px")') <= 4096 * BUCKET, 'суммарный счётчик не выше 4096 × 1e12 = 4e15');
    // siteStats видит сумму по вёдрам
    bv('siteStatsSelfUpdate()');
    eq(bv('siteStats.p[JACKPOT_CID].fed'), bv('jpLedOf("led", JACKPOT_CID)'), 'в реестр сайта fed ушёл суммой по вёдрам');

    // ===== C. зал славы и tombstone =====
    console.log('\nC. Сброс топа джекпотов: мусор не воскресает');
    const now = Date.now();
    const C = boot({
        led: { p1: 1000 }, won: {}, wins: {}, names: {},
        hall: [
            { n: 'Денис Keller', a: 1e57, t: 1791887502300, c: 'pl4lq4hk5sk' }, // мусор эпохи 1e57
            { n: 'Леха', a: 59e15, t: 1791887502400, c: 'pxxx' },
        ],
    });
    const cv = C.ev;
    cv('cloudGuest = () => false');
    ok(cv('jackpot.hall.length') === 2, 'до сброса в зале 2 записи (в т.ч. «+1e+42q»)');
    cv('jackpotRender()');
    ok(/1e\+42q/.test((C.doc.getElementById('slots-jp-top-list') || {}).innerHTML || ''), 'мусор виден в топе-3 до сброса (как на скриншоте)');
    cv('jpcResetHall()');
    eq(cv('jackpot.hall.length'), 0, 'зал славы очищен');
    ok(cv('jackpot.hallCut') > 1791887502400, 'tombstone hallCut поставлен');
    cv('jackpotRender()');
    ok(/ещё не срывали/.test((C.doc.getElementById('slots-jp-top-list') || {}).innerHTML || ''), 'топ-3 показывает «ещё не срывали»');
    // слияние со старым клиентом: мусор не воскресает
    cv('jackpotMerge({hall:[{n:"Денис Keller",a:1e57,t:1791887502300,c:"pl4lq4hk5sk"},{n:"Леха",a:59e15,t:1791887502400,c:"pxxx"}]})');
    eq(cv('jackpot.hall.length'), 0, 'старые записи НЕ воскресли после слияния');
    // свежая победа видна
    const t2 = cv('jackpot.hallCut') + 5000;
    cv('jackpotMerge({hall:[{n:"Нина",a:777,t:' + t2 + ',c:"pnina"}]})');
    eq(cv('jackpot.hall.length'), 1, 'победа свежее tombstone видна');
    eq(cv('jackpot.hall[0].n'), 'Нина', 'в топе новая запись');
    ok(cv('JSON.stringify(jpDoc().jp)').indexOf('hallCut') > 0, 'jpDoc везёт hallCut в облако');

    // ===== D. стандартные настройки =====
    console.log('\nD. «Стандартные настройки»');
    const D = boot(null);
    const dv = D.ev;
    dv('cloudGuest = () => false');
    dv('jpcSet({feedBet:25,feedLoss:50,payout:40,floor:10000000,cap:777,pSlots:1.5,pitySlots:9})');
    eq(dv('jpcGet().feedBet'), 25, 'до сброса: feedBet 25');
    dv('jpc.grant["pz"] = {a: 5, t: 123}');
    dv('jpcResetDefaults()');
    const g = dv('jpcGet()');
    ok(g.feedBet === 100 && g.feedLoss === 100 && g.payout === 100 && g.floor === 1000 && g.cap === 0,
        'заводские проценты вернулись: ' + g.feedBet + '/' + g.feedLoss + '/' + g.payout + ', пол ' + g.floor + ', потолок ' + g.cap);
    ok(g.pSlots === 5.66 && g.pitySlots === 0, 'заводские вероятность и гарантия');
    ok(g.grant && g.grant.pz && g.grant.pz.a === 5, 'назначенные выдачи не потеряны');
    ok(g.at > 0 && g.by === dv('JACKPOT_CID'), 'сброс опубликован (at/by проставлены)');

    // ===== E. кнопки в Студии =====
    console.log('\nE. Кнопки в разметке Студии');
    const E = boot(null);
    ok(!!E.doc.querySelector('button[onclick="jpcResetDefaults()"]'), 'есть кнопка «Стандартные настройки»');
    ok(!!E.doc.querySelector('button[onclick="jpcResetHall()"]'), 'есть кнопка «Сбросить топ джекпотов сайта»');
    let err = '';
    try { E.w.showStudioSec('jackpot'); E.ev('jpcAdminRender()'); } catch (e) { err = e.message; }
    ok(!err, 'панель «Джекпот» рендерится с новыми кнопками' + (err ? ' → ' + err : ''));

    // ===== F. регрессии =====
    console.log('\nF. Регрессии b416/b417');
    const F = boot({ led: { pbad: 1e57 }, won: { pbad2: 4.9e18 }, wins: {}, names: {}, hall: [] });
    const fv = F.ev;
    eq(fv('jackpot.led["pbad"]'), undefined, 'ремонт b416 по-прежнему режет 1e57');
    fv('jackpot.led = {}; jackpot.won = {};');
    const f0 = fv('jackpotPool()');
    for (let i = 0; i < 20; i++) fv('jackpotFeed(10000)');
    eq(fv('jackpotPool()') - f0, 200000, 'банк растёт от ставок');
    ok(fv('JP_BUCKET') === 1e12 && fv('JP_LED_CAP') === 1e13, 'константы вёдер и потолка на месте');
    ok(typeof fv('nxBetLack') === 'function' && typeof fv('nxLackNote') === 'function', 'хелперы b417 на месте');

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
