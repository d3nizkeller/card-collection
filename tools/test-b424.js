/* b424: значки альбомов в «Наградах» — кружочки с обложками.

   A. На каждый альбом (pack) есть круглый значок с обложкой.
   B. Собранный альбом: янтарное кольцо + галочка, обложка цветная.
   C. Несобранный: grayscale + дробь «собрано/всего» поверх обложки.
   D. Счётчик «Собрано: N из M» и обновление после досбора альбома.
   E. Старые блоки вкладки (ежедневная награда, задания, достижения) на месте.

   Запуск:  node tools/test-b424.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + a + (a === b ? '' : ' (ждём ' + b + ')'));

function boot() {
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
    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
    w.document.body.appendChild(sc);
    return { w, ev: s => w.eval(s), doc: w.document };
}

(async () => {
    const G = boot();
    const ev = G.ev;
    const doc = G.doc;

    console.log('\nA. Значки есть на каждый альбом');
    const packsN = ev('(state.packs || []).length');
    ok(packsN >= 4, 'альбомов в игре: ' + packsN);
    // в jsdom облачный каталог не приходит — синтезируем карты двух альбомов
    ev('(function(){ const ps = state.packs; state.cards = (state.cards || []).slice(); ' +
       'for (let i = 0; i < 5; i++) state.cards.push({ id: "tA" + i, packId: ps[0].id, name: "A" + i, rarity: "common", image: "media/g0.jpg" }); ' +
       'for (let i = 0; i < 4; i++) state.cards.push({ id: "tB" + i, packId: ps[1].id, name: "B" + i, rarity: "common", image: "media/s0.jpg" }); })()');
    // собираем первый альбом полностью, второй — наполовину
    ev('(function(){ const ps = state.packs; state.collection = state.collection || {}; ' +
       'const c0 = state.cards.filter(c => c.packId === ps[0].id); c0.forEach(c => state.collection[c.id] = 1); ' +
       'const c1 = state.cards.filter(c => c.packId === ps[1].id); c1.slice(0, Math.max(1, Math.floor(c1.length/2))).forEach(c => state.collection[c.id] = 1); })()');
    ev('renderRewards()');
    const box = doc.getElementById('rewards-album-badges');
    ok(!!box, 'контейнер #rewards-album-badges существует');
    const badges = box ? Array.from(box.children) : [];
    eq(badges.length, packsN, 'по значку на каждый альбом');
    ok(badges.every(b => b.querySelector('img')), 'у каждого значка есть обложка <img>');
    ok(badges.every(b => (b.querySelector('img') || {}).src), 'обложки имеют src (mediaThumb/mediaUrl)');
    ok(badges.every(b => b.querySelector('.rounded-full')), 'значки круглые (rounded-full)');

    console.log('\nB. Собранный альбом — янтарный значок с галочкой');
    const b0 = badges[0];
    ok(b0.innerHTML.indexOf('border-amber-400') >= 0, 'янтарное кольцо');
    ok(b0.innerHTML.indexOf('fa-check') >= 0, 'галочка поверх обложки');
    ok(b0.querySelector('img').className.indexOf('grayscale') < 0, 'обложка цветная');

    console.log('\nC. Несобранный — серый с прогрессом');
    const b1 = badges[1];
    ok(b1.querySelector('img').className.indexOf('grayscale') >= 0, 'обложка серая');
    const half = ev('albumPackProgress(state.packs[1])');
    ok(b1.textContent.indexOf(half[0] + '/' + half[1]) >= 0, 'дробь прогресса ' + half[0] + '/' + half[1] + ' поверх обложки');
    ok(b1.innerHTML.indexOf('fa-check') < 0, 'без галочки');

    console.log('\nD. Счётчик и обновление после досбора');
    const cnt = doc.getElementById('album-badges-counter');
    ok(cnt && cnt.textContent.indexOf('Собрано: 1 из ' + packsN) >= 0, 'счётчик: ' + (cnt ? cnt.textContent : 'нет'));
    ev('(function(){ const ps = state.packs; state.cards.filter(c => c.packId === ps[1].id).forEach(c => state.collection[c.id] = 1); })()');
    ev('renderRewards()');
    const cnt2 = doc.getElementById('album-badges-counter');
    ok(cnt2 && cnt2.textContent.indexOf('Собрано: 2 из ' + packsN) >= 0, 'после досбора счётчик: ' + (cnt2 ? cnt2.textContent : 'нет'));
    const b1b = Array.from(doc.getElementById('rewards-album-badges').children)[1];
    ok(b1b.innerHTML.indexOf('border-amber-400') >= 0, 'второй значок стал янтарным');
    ok(ev('completedAlbums(state)') >= 2, 'completedAlbums согласован со значками');

    console.log('\nD2. b425: значки ПЕРЕД достижениями, адаптивная сетка');
    const sec = doc.getElementById('tab-rewards');
    const badgesCard = box.closest('.rounded-2xl');
    const achCard = doc.getElementById('rewards-achievements-grid').closest('.rounded-2xl');
    const kids = Array.from(sec.children);
    ok(kids.indexOf(badgesCard) < kids.indexOf(achCard), 'карточка значков стоит РАНЬШЕ карточки достижений');
    ok(box.className.indexOf('grid grid-cols-3') === 0 || box.className.indexOf('grid ') >= 0, 'контейнер — сетка: ' + box.className.slice(0, 60) + '…');
    ok(box.className.indexOf('sm:grid-cols-4') >= 0 && box.className.indexOf('md:grid-cols-6') >= 0 && box.className.indexOf('lg:grid-cols-8') >= 0, 'колонки 3/4/6/8 по ширине экрана');
    ok(box.className.indexOf('justify-items-center') >= 0, 'кружки центрированы в колонках');
    ok(badges.every(b => { const c = b.firstElementChild; return c.className.indexOf('sm:w-24') >= 0; }), 'кружки крупнее на широких экранах (sm:w-24)');
    ok(badges.every(b => b.className.indexOf('w-full') >= 0), 'ячейка тянется на колонку сетки');

    console.log('\nE. Остальная вкладка наград на месте');
    ok(!!doc.getElementById('rewards-daily-strip'), 'ежедневная награда');
    ok(!!doc.getElementById('rewards-missions-list'), 'задания дня');
    ok((doc.getElementById('rewards-achievements-grid') || {}).children > 0 || doc.getElementById('rewards-achievements-grid').innerHTML.length > 100, 'достижения отрисованы');
    ok(ev('ACHIEVEMENTS.length') >= 30, 'прежние достижения не тронуты: ' + ev('ACHIEVEMENTS.length'));

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
