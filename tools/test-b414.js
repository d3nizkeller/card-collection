/* b414: «Джекпот» в Студии — управление общим банком сайта.

   Проверяем в jsdom (без браузера, без сети, без WebGL).

   A. Вкладка существует: STUDIO_SECS содержит 'jackpot', кнопка #studio-nav-jackpot
      есть, showStudioSec('jackpot') показывает секцию и подсвечивает свою кнопку.
   B. Заводские настройки = прежнее поведение игры (5.66 / 3.85 / 4 / 6.25 %,
      100 % ставки в банк, 100 % банка победителю, несгораемый остаток 1000).
   C. Вероятности честно отрабатывают на больших прогонах:
      slotsWeightedRand(p), linesRand(), wheelPickIdx() дают p ± допуск.
   D. Проценты банка: feedBet / feedLoss / payout / cap / floor.
   E. Ручное управление банком: jpcSetPool, jpcNudgePool, сброс до минимума.
   F. Выдача джекпота игроку: фиксированная сумма, «весь банк» (a=0),
      однократность (ack), отмена (a=-1), '*' = всем.
   G. Гарантия (pity): после N спинов без джекпота шанс становится 100 %.
   H. Мастер-выключатель on=0: символ JACKPOT не выпадает нигде.
   I. Настройки уезжают в облако: jpDoc().jpc есть, слияние по at работает.
   J. Симулятор и рендер панели не падают.

   ВАЖНО: внутренние переменные игры объявлены через let/const на верхнем уровне,
   поэтому они НЕ свойства window — читаем их через window.eval().

   Запуск:  node tools/test-b414.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const near = (a, b, eps, m) => ok(typeof a === 'number' && isFinite(a) && Math.abs(a - b) <= eps,
    m + '  → ' + a + ' (ждём ' + b + ' ±' + eps + ')');
function freq(fn, n) { let h = 0; for (let i = 0; i < n; i++) if (fn()) h++; return h / n; }

(async () => {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    // runScripts: 'dangerously' — код игры грузим настоящим <script>, иначе
    // let/const верхнего уровня останутся внутри eval и глобально не видны.
    // Внешние ресурсы (three.min.js, tailwind.css, шрифты) jsdom не качает.
    const dom = new JSDOM(html, {
        runScripts: 'dangerously',
        pretendToBeVisual: true,
        url: 'https://d3nizkeller.github.io/card-collection/',
    });
    const w = dom.window;
    const ev = s => w.eval(s);                 // доступ к let/const-связкам игры
    const doc = w.document;

    // ---- заглушки: canvas 2D, WebGL, сеть, звук, наблюдатели ----
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

    // ---- грузим код игры настоящим тегом <script> ----
    const js = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
    let loadErr = '';
    w.addEventListener('error', e => { try { if (e && e.error) loadErr = loadErr || String(e.error.message || e.error); } catch (x) {} });
    try {
        const sc = w.document.createElement('script');
        sc.textContent = js;
        w.document.body.appendChild(sc);
    } catch (e) { loadErr = e.message; }
    ok(!loadErr, 'app.js загрузился без фатальных ошибок' + (loadErr ? ' → ' + loadErr : ''));
    if (loadErr) { console.log('\n💥 дальше проверять нечего'); process.exit(2); }

    // ================= A. вкладка «Джекпот» =================
    console.log('\nA. Вкладка Студии «Джекпот»');
    ok(ev('STUDIO_SECS').indexOf('jackpot') >= 0, "STUDIO_SECS содержит 'jackpot' (всего " + ev('STUDIO_SECS').length + ' вкладок)');
    const navBtn = doc.getElementById('studio-nav-jackpot');
    ok(!!navBtn, 'есть кнопка #studio-nav-jackpot');
    const sec = doc.querySelector('.studio-sec[data-sec="jackpot"]');
    ok(!!sec, 'есть секция .studio-sec[data-sec="jackpot"]');
    ok(['jpc-sum', 'jpc-prob', 'jpc-users', 'jpc-pool-set', 'jpc-grant-amt', 'jpc-sim-out', 'jpc-on']
        .every(id => !!doc.getElementById(id)), 'в секции есть все ключевые узлы');
    const navCls = doc.getElementById('studio-nav').firstElementChild.className;
    ok(navCls.indexOf('grid-cols-4') >= 0 && navCls.indexOf('sm:grid-cols-8') >= 0,
        'сетка вкладок Студии адаптивная: grid-cols-4 на телефоне, sm:grid-cols-8 на широких');
    if (sec) sec.hidden = true;
    let secErr = '';
    try { w.showStudioSec('jackpot'); } catch (e) { secErr = e.message; }
    ok(!secErr && sec && !sec.hidden, 'showStudioSec("jackpot") показывает секцию' + (secErr ? ' → ' + secErr : ''));
    ok(navBtn && /bg-violet-600/.test(navBtn.className), 'кнопка «Джекпот» подсвечена как активная');

    // ================= B. заводские настройки =================
    console.log('\nB. Заводские настройки = прежнее поведение (b220)');
    const d = ev('jpcGet()');
    near(d.pSlots, 5.66, 0.001, 'Слоты: 5.66 % на барабан (было SLOTS_JP_W=3 из 53)');
    near(d.pGrid, 3.85, 0.001, 'Сетка: 3.85 % на ячейку (было GRID_JP_W=2 из 52)');
    near(d.pLines, 4, 0.001, 'Линии: 4 % на ячейку (было LINES_JP_W=1 из 25)');
    near(d.pWheel, 6.25, 0.001, 'Колесо: 6.25 % на сектор (было 1 из 16)');
    near(d.feedBet, 100, 0, 'взнос ставки в банк: 100 %');
    near(d.feedLoss, 100, 0, 'взнос проигрыша в банк: 100 %');
    near(d.payout, 100, 0, 'выплата победителю: 100 % банка');
    near(d.floor, 1000, 0, 'несгораемый остаток: 1000 (= JACKPOT_SEED)');
    near(d.cap, 0, 0, 'потолок выплаты: 0 (без потолка)');
    near(d.on, 1, 0, 'джекпот включён');

    if (!ev('slots.symbols.length')) ev('slots.symbols = slotsSymbols()');
    const syms = ev('slots.symbols');
    const jpIdx = syms.findIndex(s => s.jackpot);
    ok(jpIdx >= 0, 'в наборе символов есть JACKPOT (всего символов: ' + syms.length + ')');
    const jpSector = ev('WHEEL_SECTORS').findIndex(s => s.t === 'jackpot');
    ok(jpSector >= 0, 'в колесе есть золотой сектор (индекс ' + jpSector + ')');

    // ================= C. вероятности на прогонах =================
    console.log('\nC. Вероятности отрабатывают честно');
    const N = 200000;
    near(freq(() => ev('slotsWeightedRand(5.66)') === jpIdx, N) * 100, 5.66, 0.25,
        'slotsWeightedRand(5.66) → 5.66 % JACKPOT на барабан (' + N.toLocaleString('ru-RU') + ' прогонов)');
    near(freq(() => ev('slotsWeightedRand(20)') === jpIdx, N) * 100, 20, 0.4,
        'slotsWeightedRand(20) → 20 %');
    near(freq(() => ev('linesRand()') === 3, N) * 100, 4, 0.2, 'linesRand() → 4 % (заводские)');
    ev('jpcSet({pLines:12})');
    near(freq(() => ev('linesRand()') === 3, N) * 100, 12, 0.3, 'linesRand() после pLines=12 → 12 %');
    ev('jpcSet({pLines:4})');
    near(freq(() => ev('wheelPickIdx()') === jpSector, N) * 100, 6.25, 0.25, 'wheelPickIdx() → 6.25 % золотого сектора');
    ev('jpcSet({pWheel:25})');
    near(freq(() => ev('wheelPickIdx()') === jpSector, N) * 100, 25, 0.4, 'wheelPickIdx() после pWheel=25 → 25 %');
    ev('jpcSet({pWheel:6.25})');
    ok(freq(() => { const i = ev('wheelPickIdx()'); return i >= 0 && i < ev('WHEEL_SECTORS').length; }, 5000) === 1,
        'wheelPickIdx() всегда возвращает валидный индекс сектора');
    // три барабана подряд — заводская частота джекпота Слотов ≈ 1 из 5 500
    const p3 = Math.pow(0.0566, 3);
    const threeJp = () => ev('[0,1,2].map(function(){return slotsWeightedRand(jpcSpinPct("Slots"))}).join(",")')
        === (jpIdx + ',' + jpIdx + ',' + jpIdx);
    near(freq(threeJp, 400000), p3, 0.00012, 'Слоты: три JACKPOT подряд ≈ 1 из 5 500 (как до b414)');

    // ================= D. проценты банка =================
    console.log('\nD. Проценты: взносы и выплата');
    const cid = ev('JACKPOT_CID');
    const resetBank = () => ev('jackpot.led={};jackpot.won={};jackpot.wins={};jackpot.hall=[];jackpotSave()');
    resetBank();
    near(ev('jackpotPool()'), 1000, 0, 'пустой банк = несгораемый остаток 1000');
    ev('jackpotFeed(10000)');
    near(ev('jackpotPool()'), 11000, 0, 'feedBet=100 %: ставка 10k добавила 10k');
    ev('jpcSet({feedBet:10})'); resetBank(); ev('jackpotFeed(10000)');
    near(ev('jackpotPool()'), 2000, 0, 'feedBet=10 %: ставка 10k добавила только 1k');
    ev('jpcSet({feedBet:0})'); resetBank(); ev('jackpotFeed(10000)');
    near(ev('jackpotPool()'), 1000, 0, 'feedBet=0 %: ставка банк не кормит');
    ev('jpcSet({feedBet:100,feedLoss:25})'); resetBank();
    near(ev('jackpotOnLoss(8000)'), 2000, 0, 'feedLoss=25 %: проигрыш 8k вернул в банк 2k');
    ev('jpcSet({feedLoss:100})');

    resetBank(); ev('jackpotFeed(99000)');
    near(ev('jackpotPool()'), 100000, 0, 'банк для теста выплаты = 100k');
    ev('jpcSet({payout:50})');
    const c0 = ev('state.coins');
    ev('jackpotWin()');
    near(ev('state.coins') - c0, 50000, 0, 'payout=50 %: победитель получил 50k из 100k');
    near(ev('jackpotPool()'), 50000, 0, 'payout=50 %: в банке осталось 50k (не обнулился)');
    ev('jpcSet({payout:100,cap:7000})');
    const c1 = ev('state.coins');
    ev('jackpotWin()');
    near(ev('state.coins') - c1, 7000, 0, 'cap=7000: выплата обрезана потолком');
    ev('jpcSet({cap:0,floor:25000})'); resetBank();
    near(ev('jackpotPool()'), 25000, 0, 'floor=25000: пустой банк показывает 25k');
    ev('jpcSet({floor:1000})');

    // ================= E. банк вручную =================
    console.log('\nE. Ручное управление банком');
    resetBank();
    ev('jpcSetPool(500000)');
    near(ev('jackpotPool()'), 500000, 0, 'jpcSetPool(500000) → банк 500k');
    ev('jpcNudgePool(10000)');
    near(ev('jackpotPool()'), 510000, 0, 'jpcNudgePool(+10000) → 510k');
    ev('jpcNudgePool(-100000)');
    near(ev('jackpotPool()'), 410000, 0, 'jpcNudgePool(−100000) → 410k');
    ev('jpcResetPoolFloor()');
    near(ev('jackpotPool()'), 1000, 0, 'сброс до минимума → 1000');
    ev('jpcSetPool(10)');
    near(ev('jackpotPool()'), 1000, 0, 'банк не опускается ниже несгораемого остатка');
    resetBank();

    // ================= F. выдача джекпота игроку =================
    console.log('\nF. Выдача джекпота игроку');
    try { w.localStorage.removeItem('nexus_jp_grant_ack'); } catch (e) {}
    const g0 = ev('state.coins');
    ev('jpc.grant["' + cid + '"]={a:12345,t:Date.now()}');
    ev('jpcApplyGrants()');
    near(ev('state.coins') - g0, 12345, 0, 'фиксированная сумма 12345 дошла до баланса');
    const g1 = ev('state.coins');
    ev('jpcApplyGrants()');
    near(ev('state.coins') - g1, 0, 0, 'та же выдача второй раз НЕ срабатывает (ack)');
    resetBank(); ev('jpcSetPool(80000)');
    const g2 = ev('state.coins');
    ev('jpc.grant["' + cid + '"]={a:0,t:Date.now()+1}');
    ev('jpcApplyGrants()');
    near(ev('state.coins') - g2, 80000, 0, 'a=0 → выплачен весь банк (80k) через jackpotWin()');
    near(ev('(jackpot.wins["' + cid + '"]|0)'), 1, 0, 'выплата «весь банк» записана в зал славы (wins=1)');
    const g3 = ev('state.coins');
    ev('jpc.grant["' + cid + '"]={a:-1,t:Date.now()+2}');
    ev('jpcApplyGrants()');
    near(ev('state.coins') - g3, 0, 0, 'a=−1 (отмена выдачи) ничего не начисляет');
    const g4 = ev('state.coins');
    ev('jpc.grant["*"]={a:500,t:Date.now()+3}');
    ev('jpcApplyGrants()');
    near(ev('state.coins') - g4, 500, 0, "grant['*'] — выдача сразу всем игрокам сайта");
    ev('delete jpc.grant["*"]; delete jpc.grant["' + cid + '"]');

    // ================= G. гарантия (pity) =================
    console.log('\nG. Гарантия: джекпот не реже чем раз в N спинов');
    try { w.localStorage.removeItem('nexus_jp_pity'); } catch (e) {}
    ev('jpcPity.Slots=0; jpcSet({pitySlots:3})');
    near(ev('jpcPityN("Slots")'), 3, 0, 'pitySlots=3 принят');
    near(ev('jpcSpinPct("Slots")'), 5.66, 0.001, 'счётчик пустой → обычная вероятность 5.66 %');
    ev('jpcPityNote("Slots",false); jpcPityNote("Slots",false)');
    near(ev('jpcSpinPct("Slots")'), 5.66, 0.001, '2 промаха из 3 → ещё обычная вероятность');
    ev('jpcPityNote("Slots",false)');
    near(ev('jpcSpinPct("Slots")'), 100, 0, '3 промаха подряд → следующий спин 100 %');
    near(freq(() => ev('slotsWeightedRand(jpcSpinPct("Slots"))') === jpIdx, 200), 1, 0, 'при 100 % JACKPOT выпадает каждый раз');
    ev('jpcPityNote("Slots",true)');
    near(ev('jpcSpinPct("Slots")'), 5.66, 0.001, 'после срыва счётчик обнулён → снова 5.66 %');
    ev('jpcSet({pitySlots:0})');
    ok(ev('jpcPityN("Slots")') === 0 && ev('jpcPityForce("Slots")') === false, 'pity=0 → гарантия выключена');

    // ================= H. мастер-выключатель =================
    console.log('\nH. on=0 — джекпот выключен везде');
    ev('jpcSet({on:0})');
    ok(ev('jpcOff()') === true, 'jpcOff() = true');
    ['Slots', 'Grid', 'Lines', 'Wheel'].forEach(gm =>
        near(ev('jpcSpinPct("' + gm + '")'), 0, 0, gm + ': вероятность 0'));
    near(freq(() => ev('slotsWeightedRand(jpcSpinPct("Slots"))') === jpIdx, 50000), 0, 0,
        'символ JACKPOT не выпал ни разу из 50 000');
    near(freq(() => ev('wheelPickIdx()') === jpSector, 50000), 0, 0, 'золотой сектор не выпал ни разу из 50 000');
    near(freq(() => ev('linesRand()') === 3, 20000), 0, 0, 'в Линиях JACKPOT не выпадает');
    resetBank(); ev('jackpotFeed(5000)');
    near(ev('jackpotPool()'), 6000, 0, 'выключенный джекпот всё равно кормит банк');
    ev('jpcSet({on:1})'); resetBank();

    // ================= I. синхронизация настроек =================
    console.log('\nI. Настройки уезжают в облако вместе с банком');
    const jdoc = ev('jpDoc()');
    ok(!!jdoc.jpc && typeof jdoc.jpc === 'object', 'jpDoc().jpc присутствует');
    ok(!!jdoc.jp && !!jdoc.st && !!jdoc.updatedAt, 'остальные поля документа (jp / st / updatedAt) на месте');
    near(jdoc.jpc.payout, ev('jpcGet().payout'), 0, 'в документе — актуальный payout');
    ev('jpcSet({payout:42,pSlots:9}); jpcPublish(true)');
    ok(ev('jpcGet().at') > 0, 'jpcPublish() проставил метку редакции at');
    ev('window.__b414r = JSON.parse(JSON.stringify(jpcGet())); window.__b414r.payout=77; window.__b414r.pSlots=3; window.__b414r.at=Date.now()+5000');
    ev('jpcMerge(window.__b414r)');
    near(ev('jpcGet().payout'), 77, 0, 'свежая чужая редакция принята (payout=77)');
    ev('window.__b414s = JSON.parse(JSON.stringify(window.__b414r)); window.__b414s.payout=5; window.__b414s.at=1');
    ev('jpcMerge(window.__b414s)');
    near(ev('jpcGet().payout'), 77, 0, 'устаревшая редакция (at=1) проигнорирована');
    ev('jpcMerge({at:Date.now()+9000, grant:{pXXX:{a:111,t:Date.now()+9000}}})');
    ok(!!ev('jpcGet().grant.pXXX'), 'чужая выдача игроку принята в grant');
    ev('jpcSet({payout:100,pSlots:5.66,on:1,feedBet:100,feedLoss:100,cap:0,floor:1000,pitySlots:0}); delete jpcGet().grant.pXXX');

    // ================= J. рендер и симулятор =================
    console.log('\nJ. Рендер панели и симулятор');
    let e1 = ''; try { ev('jpcAdminRender()'); } catch (e) { e1 = e.message; }
    ok(!e1, 'jpcAdminRender() не упал' + (e1 ? ' → ' + e1 : ''));
    ok(ev('jpcSumChips()').indexOf('Банк сейчас') >= 0, 'чипы сводки содержат «Банк сейчас»');
    const probHtml = doc.getElementById('jpc-prob').innerHTML;
    ok(['jpc-pSlots', 'jpc-pGrid', 'jpc-pLines', 'jpc-pWheel', 'jpc-pitySlots', 'jpc-pityWheel']
        .every(id => probHtml.indexOf(id) >= 0), 'в #jpc-prob отрисованы ползунки и поля гарантии для всех четырёх игр');
    ok(probHtml.indexOf('Слоты') >= 0 && probHtml.indexOf('Колесо') >= 0, 'подписи игр на русском');
    let e2 = ''; try { ev('jpcSim()'); } catch (e) { e2 = e.message; }
    ok(!e2, 'jpcSim() не упал' + (e2 ? ' → ' + e2 : ''));
    const simOut = doc.getElementById('jpc-sim-out').innerHTML;
    ok(simOut.indexOf('Слоты') >= 0 && simOut.indexOf('Колесо') >= 0 && simOut.indexOf('%') >= 0,
        'симулятор выдал таблицу частот');
    try {
        ev('siteStats.p["pTEST01"]={cid:"pTEST01",n:"Тестовый игрок",bal:4242,jp:2,at:Date.now()}');
        ev('jpcAdminUsers()');
        const uh = doc.getElementById('jpc-users').innerHTML;
        ok(uh.indexOf('Тестовый игрок') >= 0 && uh.indexOf('pTEST01') >= 0, 'игрок из реестра показан в списке выдачи');
        ok(uh.indexOf('jpcGrant(') >= 0 && uh.indexOf('Выдать банк') >= 0 && uh.indexOf('Выдать сумму') >= 0,
            'у игрока есть кнопки «Выдать банк» и «Выдать сумму»');
        ok(uh.indexOf('4.2k') >= 0 || uh.indexOf('4242') >= 0, 'баланс игрока подписан');
    } catch (e) { ok(false, 'список игроков: ' + e.message); }
    ok(ev('jpcOdds(0)') === 'не выпадет', "jpcOdds(0) = 'не выпадет'");
    ok(ev('jpcOdds(100)') === 'каждый спин', "jpcOdds(100) = 'каждый спин'");
    ok(String(ev('jpcOdds(6.25)')).indexOf('1 из 16') === 0, 'jpcOdds(6.25) = «1 из 16»');
    near(ev('jpcWeight(50,5)'), 50, 0.001, 'jpcWeight(50 %, 5 символов) = 50 → шанс ровно половина');
    near(ev('jpcWeight(0,5)'), 0, 0, 'jpcWeight(0 %) = 0');

    // ================= K. живые надписи (b415) =================
    console.log('\nK. Надписи о процентах следуют за настройками (b415)');
    const lbl = key => Array.from(doc.querySelectorAll('[data-jpc="' + key + '"]')).map(e => e.textContent);
    ok(lbl('feed').length >= 10, 'разметка data-jpc="feed" есть во всех играх (' + lbl('feed').length + ' мест)');
    ok(lbl('loss').length >= 10, 'разметка data-jpc="loss" есть во всех играх (' + lbl('loss').length + ' мест)');
    ok(lbl('feed').every(t => t === '100%'), 'заводские: все надписи взноса = «100%»');
    ok(lbl('loss').every(t => t === '100%'), 'заводские: все надписи проигрыша = «100%»');
    ok(lbl('pay').every(t => t === 'весь банк ваш'), 'заводские: «весь банк ваш»');
    ok(lbl('odds-wheel').every(t => t === '1 из 16 спинов'), 'заводские: колесо «1 из 16 спинов»');
    ev('jpcSet({feedBet:25,feedLoss:50})');
    ev('jackpotRender()');
    ok(lbl('feed').every(t => t === '25%'), 'feedBet=25 → все надписи взноса стали «25%» (' + lbl('feed').length + ')');
    ok(lbl('loss').every(t => t === '50%'), 'feedLoss=50 → все надписи проигрыша стали «50%» (' + lbl('loss').length + ')');
    ok(doc.getElementById('jpc-ex-add').textContent === '2.5k', 'живой пример в Студии: 10k × 25% = 2.5k');
    ev('jpcSet({payout:40})');
    ev('jackpotRender()');
    ok(lbl('pay').every(t => t === 'вам 40% банка'), 'payout=40 → «вам 40% банка» во всех трёх баннерах');
    ok(lbl('pay2').every(t => t === '40% общего банка сайта'), 'payout=40 → «40% общего банка сайта» (колесо)');
    ok(lbl('pay2v').every(t => t === 'вам 40% общего банка сайта'), 'payout=40 → «вам 40% общего банка сайта» (линии)');
    ok(lbl('pay3').every(t => t === '40% банка джекпота'), 'payout=40 → «40% банка джекпота» (строка выплат)');
    ok(lbl('paynum').every(t => t === '40%'), 'payout=40 → «40%» в живом примере');
    const poolNow = ev('jackpotPool()');
    ok(doc.getElementById('jpc-ex-win').textContent === ev('fmtCoins(' + Math.round(poolNow * 0.4) + ')'),
        'живой пример: выплата = 40% текущего банка (' + doc.getElementById('jpc-ex-win').textContent + ')');
    ok(ev('jpcPhrase("pay2v")') === 'вам 40% общего банка сайта', 'jpcPhrase("pay2v") для динамического результата колеса');
    ev('jpcSet({pWheel:25})');
    ev('jackpotRender()');
    ok(lbl('odds-wheel').every(t => t === '1 из 4 спинов'), 'pWheel=25 → колесо «1 из 4 спинов»');
    ev('jpcSet({pWheel:0.5})');
    ev('jackpotRender()');
    ok(lbl('odds-wheel').every(t => t === '1 из 200 спинов'), 'pWheel=0.5 → колесо «1 из 200 спинов»');
    ev('jpcSet({on:0})');
    ev('jackpotRender()');
    ok(lbl('odds-wheel').every(t => t === 'не выпадает'), 'on=0 → колесо «не выпадает»');
    ev('jpcSet({on:1,feedBet:100,feedLoss:100,payout:100,pWheel:6.25})');
    ev('jackpotRender()');
    ok(lbl('feed').every(t => t === '100%') && lbl('pay').every(t => t === 'весь банк ваш')
        && lbl('odds-wheel').every(t => t === '1 из 16 спинов'), 'возврат к заводским: надписи снова прежние');
    // чужая редакция настроек тоже обновляет надписи
    ev('window.__b414m = JSON.parse(JSON.stringify(jpcGet())); window.__b414m.feedBet=7; window.__b414m.at=Date.now()+600000;');
    ev('jpcMerge(window.__b414m)');
    ok(lbl('feed').every(t => t === '7%'), 'чужая редакция из облака (feedBet=7) обновила надписи без ручного вызова');
    ev('jpcSet({feedBet:100})');

    console.log('\n' + '─'.repeat(58));
    if (fails) { console.log('❌ ' + fails + ' из ' + checks + ' проверок НЕ пройдено'); process.exit(1); }
    console.log('✅ ALL PASS — ' + checks + ' проверок, ошибок 0');
    process.exit(0);
})().catch(e => { console.error('💥 тест упал:', e); process.exit(2); });
