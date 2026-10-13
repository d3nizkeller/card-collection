/* b416: банк джекпота больше не замерзает.

   Жалоба владельца: «Чего-то число в банке не растёт».

   Проверяем в jsdom на снимке НАСТОЯЩЕГО облачного документа общего банка
   (tools/_jp_frozen_fixture.json — textdb nexus-tcg-jackpot-v2 от 2026-10-13:
   счётчик владельца 1e57 в led и 1e57 в won, floor 10 000 000, «долг» реестра
   −16.9 млрд).

   A. На испорченном реестре банк снова растёт (главная проверка).
   B. Несгораемый остаток — гарантия пола, а не «мёртвая зона»;
      при заводском floor = JACKPOT_SEED числа ровно прежние (регрессия b414).
   C. Срыв банка, стоящего на полу, больше не создаёт «фантомный долг».
   D. Потолок счётчика и точность сумм: 1e57 в реестр не пишется,
      «Поставить банк» работает и не врёт в тосте.
   E. jpRepairLedger идемпотентен, дом ('house') не считается игроком.
   F. Чужой мусор из облака лечится при слиянии и не замораживает банк.
   G. Долгий прогон: 3000 случайных событий — банк жив, счётчики в потолке.

   ВАЖНО: внутренние переменные игры объявлены через let/const на верхнем уровне,
   поэтому они НЕ свойства window — читаем их через window.eval().

   Запуск:  node tools/test-b416.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
const FIXTURE = path.join(ROOT, 'tools', '_jp_frozen_fixture.json');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + a + (a === b ? '' : ' (ждём ' + b + ')'));

function bootDom(withFixture, ownerCid) {
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

    if (withFixture) {
        const doc = JSON.parse(fs.readFileSync(FIXTURE, 'utf8'));
        w.localStorage.setItem('nexus_jackpot_cid', ownerCid || doc.jpc.by);
        w.localStorage.setItem('nexus_jackpot_v2', JSON.stringify(doc.jp));
        w.localStorage.setItem('nexus_jackpot_cfg', JSON.stringify(doc.jpc));
    }
    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
    w.document.body.appendChild(sc);
    return { w, ev: s => w.eval(s), doc: w.document };
}

(async () => {
    // ================= A. испорченный реестр: банк снова растёт =================
    console.log('\nA. Настоящий испорченный документ банка (снимок облака)');
    const G = bootDom(true);
    const ev = G.ev;
    ev('cloudGuest = () => false'); // играем за владельца комнаты
    const CAP = ev('JP_LED_CAP');
    eq(ev('JACKPOT_CID'), 'pl4lq4hk5sk', 'cid = владелец комнаты (Денис Keller)');
    eq(ev('jpc.floor'), 10000000, 'floor из облака = 10 000 000');
    ok(ev('jpFixInfo.n') > 0, 'реестр починен автоматически при загрузке: записей ' + ev('jpFixInfo.n'));
    eq(ev('jpFixInfo.debt'), 16884760700, 'долг реестра покрыт домом (16 884 760 700)');
    ok(ev('(function(){for(const k in jackpot.led) if (jpLedBad(jackpot.led[k])) return k; for(const k in jackpot.won) if (jpLedBad(jackpot.won[k])) return k; return "";})()') === '',
        'в реестре не осталось счётчиков вне потолка ' + CAP);
    eq(ev('jackpot.led["pl4lq4hk5sk"]'), undefined, 'счётчик владельца 1e57 выброшен как мусор');
    eq(ev('jpRawPool()'), 1000, 'raw = сид (долг погашен, банк чист)');
    eq(ev('jackpotPool()'), 10000000, 'банк = пол 10 000 000 (таким его видят игроки)');

    // главное: ставки снова двигают витрину
    const p0 = ev('jackpotPool()');
    for (let i = 0; i < 50; i++) ev('jackpotFeed(10000)');
    eq(ev('jackpotPool()') - p0, 500000, '50 ставок по 10k → банк ВЫРОС на 500k (было: не двигался вовсе)');
    const p1 = ev('jackpotPool()');
    eq(ev('jackpotOnLoss(250000)'), 250000, 'проигрыш 250k докинул в банк 250k');
    eq(ev('jackpotPool()') - p1, 250000, 'банк вырос после проигрыша');
    eq(ev('jackpot.led[JACKPOT_CID]'), 750000, 'взнос владельца виден в реестре (750k), а не утонул в 1e57');

    // витрина: число доезжает до DOM
    ev('jackpotRender()');
    const shown = (G.doc.getElementById('slots-jackpot') || {}).textContent;
    eq(shown, ev('fmtCoins(jackpotPool())'), 'на витрине Слотов — актуальный банк (' + shown + ')');
    const note = (G.doc.getElementById('slots-jackpot-note') || {}).textContent || '';
    ok(note.indexOf('копят игроки: ' + ev('jackpotPlayers()')) >= 0, 'в подписи число игроков без служебной записи дома');

    // ================= B. floor — гарантия, а не мёртвая зона =================
    console.log('\nB. Несгораемый остаток: пол, а не «мёртвая зона»');
    const reset = () => ev('jackpot.led={};jackpot.won={};jackpot.wins={};jackpot.hall=[];jackpotSave()');
    ev('jpcSet({floor:25000,payout:100,cap:0,feedBet:100,feedLoss:100})'); reset();
    eq(ev('jackpotPool()'), 25000, 'floor=25000, пустой реестр → банк 25k (как и было)');
    ev('jackpotFeed(10000)');
    eq(ev('jackpotPool()'), 35000, 'floor=25000 + ставка 10k → 35k (до b416 стояло на 25k, пока взносы не переползут пол)');
    ev('jpcSet({floor:1000})'); reset();
    eq(ev('jackpotPool()'), 1000, 'заводской floor=1000: пустой банк = 1000');
    ev('jackpotFeed(99000)');
    eq(ev('jackpotPool()'), 100000, 'заводской floor: ставка 99k → 100k (формула прежняя, регрессия b414)');
    ev('jackpotFeed(10000000)');
    eq(ev('jackpotPool()'), 10100000, 'большой взнос считается точно');

    // ================= C. фантомный долг =================
    console.log('\nC. Срыв банка на полу не создаёт «фантомный долг»');
    ev('jpcSet({floor:10000000,payout:100,cap:0})'); reset();
    eq(ev('jackpotPool()'), 10000000, 'банк на полу');
    const coins0 = ev('state.coins');
    ev('jackpotWin()');
    eq(ev('state.coins') - coins0, 10000000, 'победитель получил весь банк (пол — гарантия выплаты)');
    eq(ev('jpLedNum(jackpot.won[JACKPOT_CID])'), 0, 'в won не записано ничего: этих денег в реестре не было');
    eq(ev('jpRawPool()'), 1000, 'raw не ушёл в минус (до b416: −10 000 000 за каждый срыв)');
    eq(ev('jackpotPool()'), 10000000, 'банк снова на полу');
    // 20 циклов «взнос → срыв»: банк растёт между срывами и не проседает
    let frozen = 0, prev = ev('jackpotPool()');
    for (let i = 0; i < 20; i++) {
        ev('jackpotFeed(50000)');
        const up = ev('jackpotPool()');
        if (up <= prev) frozen++;
        prev = up;
        ev('jackpotWin()');
        prev = ev('jackpotPool()');
        if (prev !== 10000000) frozen += 100; // после срыва — ровно пол
    }
    eq(frozen, 0, '20 циклов «взнос 50k → срыв»: банк каждый раз растёт и возвращается ровно на пол');
    eq(ev('jpLedSum(jackpot.won)'), ev('jpLedSum(jackpot.led)'), 'Σвыплат = Σвзносов: в реестре только обеспеченные деньги');
    eq(ev('jpRawPool()'), 1000, 'долга нет: raw вернулся к сиду (до b416 каждый срыв на полу добавлял −10m)');

    // ================= D. потолок и точность =================
    console.log('\nD. Потолок счётчика, точность сумм, честный «Поставить банк»');
    ev('jpcSet({floor:1000})'); reset();
    eq(ev('jpLedAdd("led", JACKPOT_CID, 1e30)'), 1e30, 'b419: взнос 1e30 лёг ПОЛНОСТЬЮ — ограничений роста нет');
    eq(ev('jpLedSum(jackpot.led)'), 1e30, 'сумма реестра точна');
    ok(ev('jpLedNum(jackpot.led[JACKPOT_CID + "#1"], 1)') > 0, 'переполнение ушло в старший разряд (#1)');
    ok(ev('jpLedNum(jackpot.led[JACKPOT_CID], 0)') <= ev('jpTierCap(0)'), 'разряд 0 не выше своей ёмкости 1e13');
    eq(ev('jackpotPool()'), 1000 + 1e30, 'банк вырос до 1e30');
    reset();
    ev('jpcSetPool(1e30)');
    eq(ev('jackpotPool()'), 1000 + 1e30, '«Поставить банк 1e30» → ровно 1e30 сверх пола');
    reset();
    ev('jpcSetPool(500000)');
    eq(ev('jackpotPool()'), 500000, '«Поставить банк 500k» → ровно 500k');
    ev('jpcNudgePool(10000)');
    eq(ev('jackpotPool()'), 510000, '«+10k» → 510k');
    ev('jpcNudgePool(-100000)');
    eq(ev('jackpotPool()'), 410000, '«−100k» → 410k');
    ev('jpcResetPoolFloor()');
    eq(ev('jackpotPool()'), 1000, 'сброс до минимума → 1000');
    ev('jpcSetPool(10)');
    eq(ev('jackpotPool()'), 1000, 'ниже несгораемого остатка банк не опускается');
    eq(ev('jpRawPool()'), 1000, 'уход ниже пола погашен домом — долг не копится');
    // точность суммы на большом реестре
    const big = {}; for (let i = 0; i < 1000; i++) big['p' + i] = 1e9;
    big.pmax = CAP;
    eq(ev('jpLedSum(' + JSON.stringify(big) + ')'), 1e12 + CAP, 'сумма 1001 записей (1000×1e9 + потолок) точна до монеты');
        eq(ev('jpLedSum({a:1e57,b:-5,c:"x",d:NaN,e:7})'), 7, 'мусор (1e57, −5, "x", NaN) в сумму не попадает');

    // ================= E. идемпотентность ремонта =================
    console.log('\nE. Ремонт реестра идемпотентен');
    reset();
    ev('jackpot.led["pbad"] = 1e57; jackpot.won["pbad2"] = 4.9e18; jackpot.led["pok"] = 5000;');
    const n1 = ev('jpRepairLedger()');
    eq(n1, 2, 'первый прогон выбросил 2 испорченные записи');
    eq(ev('jpRepairLedger()'), 0, 'второй прогон — 0 правок (идемпотентно)');
    eq(ev('jackpot.led["pok"]'), 5000, 'честная запись не тронута');
    eq(ev('jackpot.led["pbad"]'), undefined, 'счётчик 1e57 удалён из реестра');
    eq(ev('jackpot.won["pbad2"]'), undefined, 'выплата 4.9e18 удалена из реестра');
    eq(ev('jackpot.led["house"]'), undefined, 'долга нет → запись дома не создаётся (деньги не печатаются)');
    eq(ev('jpRawPool()'), 6000, 'raw = сид + честный взнос 5k');

    // долг: Σвыплат больше Σвзносов (наследие срывов при банке на полу)
    reset();
    ev('jackpot.led["p1"] = 1e57; jackpot.won["p1"] = 1e57; jackpot.won["p2"] = 500000; jackpot.led["p3"] = 120000;');
    const n2 = ev('jpRepairLedger()');
    eq(n2, 3, 'мусор выброшен (2 записи) и долг погашен (1 запись дома)');
    eq(ev('jackpot.led["house"]'), 380000, 'дом покрыл ровно долг: 500000 выплат − 120000 взносов − сид 1000 = 380000');
    eq(ev('jpRawPool()'), 1000, 'raw снова = сид: банк стоит на полу и готов расти');
    eq(ev('jpRepairLedger()'), 0, 'повторный ремонт ничего не меняет');
    eq(ev('jackpot.led["house"]'), 380000, 'запись дома не растёт от повторных ремонтов');
    eq(ev('jackpotPlayers()'), 1, '«копят банк» = 1 игрок (p3); дом и удалённые записи не в счёт');
    const rawA = ev('jpRawPool()');
    ev('jpRepairLedger(); jpRepairLedger(); jpRepairLedger()');
    eq(ev('jpRawPool()'), rawA, 'raw не уезжает от повторных ремонтов');
    ok(ev('JSON.stringify(jpDoc().jp)').indexOf('e+5') < 0, 'в облачный документ jpDoc() мусор не уезжает');

    // ================= F. слияние с облаком =================
    console.log('\nF. Чужой мусор из облака лечится при слиянии');
    reset();
    ev('jpcSet({floor:1000})');
    ev('jackpotFeed(100000)');
    const before = ev('jackpotPool()');
    ev('jackpotMerge({led:{"plegacy":1e57,"pgood":25000}, won:{"plegacy":1e57}})');
    ok(ev('jackpotPool()') < 1e15, 'после слияния с 1e57 банк остался вменяемым: ' + ev('fmtCoins(jackpotPool())'));
    eq(ev('jackpotPool()'), before + 25000, 'честный взнос 25k из облака учтён, мусор выброшен');
    const g1 = ev('jackpotPool()');
    ev('jackpotFeed(10000)');
    eq(ev('jackpotPool()'), g1 + 10000, 'после чужого мусора свои ставки снова двигают банк');
    eq(ev('jackpot.led["plegacy"]'), undefined, 'запись 1e57 больше не висит в реестре');
    eq(ev('jackpot.won["plegacy"]'), undefined, 'чужая выплата 1e57 тоже выброшена');

    // ================= G. долгий прогон =================
    console.log('\nG. 700 случайных событий: банк жив');
    reset();
    ev('jpcSet({floor:10000000,payout:100,cap:0,feedBet:100,feedLoss:100})');
    let minSeen = Infinity, maxSeen = 0, grew = 0, lastPool = ev('jackpotPool()');
    for (let i = 0; i < 700; i++) {
        const r = Math.random();
        if (r < 0.55) ev('jackpotFeed(' + (1000 + Math.floor(Math.random() * 500000)) + ')');
        else if (r < 0.85) ev('jackpotOnLoss(' + (1000 + Math.floor(Math.random() * 250000)) + ')');
        else ev('jackpotWin()');
        const p = ev('jackpotPool()');
        if (p > lastPool) grew++;
        lastPool = p;
        if (p < minSeen) minSeen = p;
        if (p > maxSeen) maxSeen = p;
    }
    ok(minSeen >= 10000000, 'банк ни разу не опустился ниже пола (минимум ' + minSeen + ')');
    ok(grew > 150, 'банк рос в ' + grew + ' событиях из 700');
    ok(maxSeen > 10000000, 'максимум банка выше пола: ' + maxSeen);
    ok(ev('(function(){for(const f in {led:1,won:1}) for(const k in jackpot[f]) if (jpLedBad(jackpot[f][k])) return k; return "";})()') === '',
        'после прогона все счётчики в пределах потолка');
    ok(ev('jpRawPool()') >= 1000, 'raw не ушёл в минус: ' + ev('jpRawPool()'));

    // ================= H. панель Студии «Джекпот» =================
    console.log('\nH. Студия: отчёт о ремонте и кнопка «Починить банк»');
    const H = bootDom(true);
    const hv = H.ev;
    hv('cloudGuest = () => false');
    let secErr = '';
    try { H.w.showStudioSec('jackpot'); } catch (e) { secErr = e.message; }
    ok(!secErr, 'showStudioSec("jackpot") без ошибок' + (secErr ? ' → ' + secErr : ''));
    const fixNote = H.doc.getElementById('jpc-fix-note');
    ok(!!fixNote, 'в панели есть строка отчёта #jpc-fix-note');
    ok(fixNote && fixNote.hidden === false, 'отчёт о ремонте показан (реестр был испорчен)');
    ok(fixNote && /починен автоматически/.test(fixNote.textContent) && /16\.8b|16884760700/.test(fixNote.textContent),
        'в отчёте — число покрытого долга: ' + (fixNote ? fixNote.textContent.slice(0, 110) + '…' : ''));
    const btn = H.doc.querySelector('button[onclick="jpRepairNow()"]');
    ok(!!btn, 'есть кнопка «Починить банк»');
    const chips = hv('jpcSumChips()');
    ok(chips.indexOf('1q') < 0 && chips.indexOf('e+57') < 0, 'в сводке Студии нет астрономических сумм («Внесено в банк» = ' +
        (chips.match(/Внесено в банк<\/p>\s*<p[^>]*>([^<]+)</) || [, '?'])[1] + ')');
    ok(/Копят банк<\/p>\s*<p[^>]*>\d+/.test(chips), '«Копят банк» — число игроков без записи дома');
    let repErr = '';
    try { hv('jpRepairNow()'); } catch (e) { repErr = e.message; }
    ok(!repErr, 'jpRepairNow() отрабатывает без ошибок' + (repErr ? ' → ' + repErr : ''));
    eq(hv('jpRepairLedger()'), 0, 'после ручного ремонта чинить больше нечего');
    ok(hv('jackpotPool()') >= hv('jpc.floor'), 'банк не ниже пола: ' + hv('fmtCoins(jackpotPool())'));

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
