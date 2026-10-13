/* b420: синхронизация чинится — облачный документ похудел (rm prune + эпoha реестра).

   Жалоба владельца: «чего не синхронизируется с пользователями». Замеры:
   документ 922 КБ (mk.rm 728 КБ = 16 918 tombstone, jp 134 КБ = 4107 ключей),
   каждый синхронный цикл таскает его целиком с таймаутом 15 c — мобильные
   клиенты не долетали и тихо выпадали из синхронизации.

   A. mk.rm: prune по возрасту (2 ч) и количеству (300) — при записи,
      слиянии и пакетном снятии.
   B. Эпоха реестра: ep > своей принимается целиком; без ep / со старым ep —
      прежний max-merge.
   C. jpCompact(): тысячи ключей → минимальный каскад, суммы и банк не меняются,
      ep растёт; охрана от старых клиентов (10 минут тишины).
   D. Кнопка «Уплотнить реестр» в Студии; jpDocBytes существует.
   E. Регрессии: разряды b419, tombstone b418, тосты b417.

   Запуск:  node tools/test-b420.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + a + (a === b ? '' : ' (ждём ' + b + ')'));

function boot(pre) {
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
    if (pre) pre(w);
    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
    w.document.body.appendChild(sc);
    return { w, ev: s => w.eval(s), doc: w.document };
}

(async () => {
    // ===== A. prune mk.rm =====
    console.log('\nA. Tombstone биржи режутся по возрасту и количеству');
    const now = Date.now();
    const A = boot(w => {
        const old = {};
        for (let i = 0; i < 400; i++) old['lot_old_' + i] = now - 3 * 60 * 60 * 1000 - i; // старше 2 ч
        for (let i = 0; i < 5; i++) old['lot_new_' + i] = now - 1000;
        w.localStorage.setItem('nexus_market_removed', JSON.stringify(old));
    });
    const av = A.ev;
    av('cloudGuest = () => false');
    const d0 = av('marketDoc()');
    ok(Object.keys(d0.rm).length <= 300, 'marketDoc(): rm обрезан до 300 (было 405): ' + Object.keys(d0.rm).length);
    ok(Object.keys(d0.rm).every(k => k.indexOf('lot_new_') === 0), 'старые tombstone (＞2 ч) в документ не попадают');
    const remote = { rm: {} };
    for (let i = 0; i < 600; i++) remote.rm['r_old_' + i] = now - 5 * 60 * 60 * 1000;
    for (let i = 0; i < 10; i++) remote.rm['r_new_' + i] = now - 500;
    av('marketMerge(' + JSON.stringify(remote) + ')');
    const after = av('marketRemoved()');
    ok(Object.keys(after).length <= 300, 'после слияния 610 чужих tombstone локально ≤300: ' + Object.keys(after).length);
    ok(Object.keys(after).every(k => (after[k] || 0) > now - 2 * 60 * 60 * 1000 - 5000), 'в локальном rm остались только свежие');
    av('marketRemovedAddMany(Array.from({length: 500}, (_, i) => "bulk_" + i))');
    ok(Object.keys(av('marketRemoved()')).length <= 300, 'пакетное снятие 500 лотов тоже обрезается');

    // ===== B. эпоха реестра =====
    console.log('\nB. ep: уплотнённый реестр принимается целиком');
    const B = boot();
    const bv = B.ev;
    bv('jackpot.led = {me: 5000}; jackpot.won = {}; jackpot.wins = {};');
    bv('jackpotMerge({ep: 3, led: {other: 777}, won: {other: 7}, wins: {other: 1}})');
    eq(bv('jackpot.led["me"]'), undefined, 'свой ключ уступил место уплотнённому реестру (ep=3)');
    eq(bv('jackpot.led["other"]'), 777, 'принят чужой уплотнённый реестр');
    eq(bv('jackpot.ep'), 3, 'эпоха запомнена');
    bv('jackpotMerge({led: {old: 1e13}})'); // без ep при нашей ep=3 — реестр не принимается
    eq(bv('jackpot.led["old"]'), undefined, 'без ep при нашей эпохе реестр собеседника не принимается (иначе удвоение)');
    eq(bv('jackpot.led["other"]'), 777, 'и ничего не потерялось');
    bv('jackpotMerge({ep: 2, led: {ancient: 1}})');
    eq(bv('jackpot.led["ancient"]'), undefined, 'старая эпоха (2 < 3) не затирает новый реестр');
    bv('jackpotMerge({ep: 3, led: {peer: 42}})');
    eq(bv('jackpot.led["peer"]'), 42, 'та же эпоха (3 = 3) — прежний max-merge');
    const Z = boot();
    Z.ev('jackpotMerge({led: {fresh: 5}})');
    eq(Z.ev('jackpot.led["fresh"]'), 5, 'пока эпохи ни у кого нет (0 = 0) — прежний max-merge');

    // ===== C. jpCompact =====
    console.log('\nC. Уплотнение: тысячи ключей → каскад, банк не меняется');
    const C = boot();
    const cv = C.ev;
    cv('cloudGuest = () => false');
    cv('window.__nxJpLegacyAt = 0');
    cv('(function(){ jackpot.led = {}; jackpot.won = {}; var tot = 0; for (var i = 0; i < 400; i++) { jackpot.led["pc#" + i] = 1e12; tot += 1e12; } jackpot.led["pc"] = 5e11; tot += 5e11; jackpot.__tot = tot; })()');
    const raw0 = cv('jpRawPool()');
    const keys0 = cv('Object.keys(jackpot.led).length');
    ok(keys0 >= 400, 'до уплотнения ключей много: ' + keys0);
    cv('jpCompact()');
    const keys1 = cv('Object.keys(jackpot.led).length');
    ok(keys1 <= 6, 'после уплотнения ключей ≤6: ' + keys1);
    eq(cv('jpRawPool()'), raw0, 'raw банка не изменился');
    eq(cv('jpLedOf("led", "pc")'), cv('jackpot.__tot'), 'сумма игрока сохранилась до монеты');
    eq(cv('jackpot.ep'), 1, 'эпоха увеличена');
    cv('jpCompact()');
    eq(cv('Object.keys(jackpot.led).length'), keys1, 'повторное уплотнение стабильно');
    // охрана от старых клиентов
    cv('window.__nxJpLegacyAt = Date.now()');
    eq(cv('jpCompact()'), false, 'при активном старом клиенте уплотнение отклонено');
    ok(cv('document.getElementById("toast-container").textContent').indexOf('старой версии') >= 0, 'и объяснено почему');
    eq(cv('jpDocBytes()') > 0, true, 'jpDocBytes() считает размер документа');

    // ===== D. кнопка в Студии =====
    console.log('\nD. Студия');
    const D = boot();
    ok(!!D.doc.querySelector('button[onclick="jpCompact()"]'), 'есть кнопка «Уплотнить реестр»');
    ok(!!D.doc.querySelector('button[onclick="jpcResetDefaults()"]') && !!D.doc.querySelector('button[onclick="jpcResetHall()"]'), 'кнопки b418 на месте');

    // ===== E. регрессии =====
    console.log('\nE. Регрессии b416–b419');
    const E = boot();
    const evv = E.ev;
    evv('jackpot.led = {}; jackpot.won = {};');
    eq(evv('jpLedAdd("led", "pr", 1e30)'), 1e30, 'b419: взнос 1e30 ложится целиком');
    eq(evv('fmtCoins(1e18)'), '1s', 'b419: витрина 1e18 → 1s');
    evv('jackpot.led = {x: 1e57}; jpRepairLedger()');
    eq(evv('jackpot.led["x"]'), undefined, 'b416: 1e57 режется');
    ok(typeof evv('nxBetLack') === 'function', 'b417: хелперы на месте');
    evv('jpcResetHall()');
    eq(evv('jackpot.hall.length'), 0, 'b418: tombstone зала славы работает');

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
