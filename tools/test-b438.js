/* b438: картинки карточек плохо грузятся — третий уровень артов media/t3/.

   Просмотр карты и «галерея» раньше грузили мастеров (4K PNG по 10–16 МБ):
   на телефоне десятки секунд или вечная заглушка, а файл >8 МБ не влезает в
   постоянный кэш. Теперь для тяжёлых мастеров строится media/t3/<имя>.webp
   (длинная сторона ≤1440px, ~0.1–0.3 МБ) и используется везде, где раньше
   был мастер; мастер остаётся последним резервом (data-nx-full).

   A. Карта NX_EMBED_BIG: существует, валидна, синхронна с media/t3 на диске.
   B. mediaBig(): t3 для тяжёлых, мастер для лёгких/неизвестных, облачные
      URL, мемоизация 404 (NX_THUMB_404).
   C. nxDownTierUrl(): t3 -> t2, дальше не понижает.
   D. imgErrorChain: ошибка t3 откатывается на data-nx-full (мастер);
      старая цепочка t/t2 не сломана.
   E. nxProgressiveAttach: src из t3 мгновенно показывает t2 и греет t3 фоном.
   F. inspectCard: src=mediaBig + data-nx-full=мастер + прогрев соседей ±2.
   G. Галерея/preload: artFn 'full' -> mediaBig; preloadImages tier 'big'.
   H. Тег nxmob160 (index.html x8, sw.js, build.py), инструменты и CI.

   Запуск:  node tools/test-b438.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; }
const eq = (a, b, m) => ok(a === b, m + '  → ' + JSON.stringify(a) + (a === b ? '' : ' (ждём ' + JSON.stringify(b) + ')'));

const APP = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');

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
    sc.textContent = APP;
    w.document.body.appendChild(sc);
    return { w, ev: s => w.eval(s), doc: w.document };
}

(async () => {
    console.log('A. Карта NX_EMBED_BIG и файлы media/t3');
    const mLine = APP.split('\n').find(l => l.trim().startsWith('const NX_EMBED_BIG = '));
    ok(!!mLine, 'в app.js есть декларация NX_EMBED_BIG');
    let BIG = {};
    try { BIG = JSON.parse(mLine.trim().slice('const NX_EMBED_BIG = '.length).replace(/;$/, '')); } catch (e) {}
    const keys = Object.keys(BIG);
    ok(keys.length >= 150, 'в карте >=150 записей (факт на диске: ' + fs.readdirSync(path.join(ROOT, 'media', 't3')).length + ')  → ' + keys.length);
    ok(keys.every(k => /^media\/t3\/.+\.webp$/.test(BIG[k])), 'все значения — media/t3/*.webp');
    ok(keys.every(k => fs.existsSync(path.join(ROOT, 'media', k.replace(/^media\//, '')))), 'все мастера из карты существуют в media/');
    ok(keys.every(k => fs.existsSync(path.join(ROOT, BIG[k]))), 'все t3-файлы из карты существуют на диске');
    const disk = fs.readdirSync(path.join(ROOT, 'media', 't3'));
    eq(new Set(keys.map(k => BIG[k].split('/').pop())).size, disk.length, 'карта покрывает все файлы media/t3 (без сирот)');
    const oversize = disk.filter(f => fs.statSync(path.join(ROOT, 'media', 't3', f)).size > 8 * 1024 * 1024);
    eq(oversize.length, 0, 'все t3 < 8 МБ (влезут в постоянный кэш IMG_CACHE_MAX_BLOB)');
    const hp = 'card_mv9i1vnd_30.png';
    if (fs.existsSync(path.join(ROOT, 'media', hp))) {
        const mSz = fs.statSync(path.join(ROOT, 'media', hp)).size;
        const bSz = fs.statSync(path.join(ROOT, 'media', 't3', 'card_mv9i1vnd_30.webp')).size;
        ok(mSz > 10 * 1024 * 1024 && bSz < mSz / 20, '4K-мастер «Гарри Поттера» ' + (mSz / 1048576).toFixed(1) + ' МБ -> t3 ' + (bSz / 1024).toFixed(0) + ' КБ (>20x легче)');
    }

    const G = boot();
    const ev = G.ev, doc = G.doc;

    console.log('\nB. mediaBig()');
    eq(ev("typeof mediaBig"), 'function', 'mediaBig — функция');
    eq(ev("typeof nxBigFor"), 'function', 'nxBigFor — функция');
    eq(ev("mediaBig('media/card_mv9byrso_1.png')"), 'media/t3/card_mv9byrso_1.webp', 'тяжёлый мастер -> t3');
    eq(ev("mediaBig('media/skubi17.jpg')"), 'media/skubi17.jpg', 'лёгкий мастер (нет в карте) -> сам мастер');
    eq(ev("mediaBig('media/unknown_art_xyz.png')"), 'media/unknown_art_xyz.png', 'неизвестный арт -> мастер (без 404-дыры)');
    eq(ev("mediaBig('')"), '', 'пустая строка -> пустая');
    eq(ev("mediaBig('https://room.example.com/files/media/card_mv9c5cgp_2.png')"),
       'https://room.example.com/files/media/t3/card_mv9c5cgp_2.webp', 'облачный URL: хост сохранён, каталог media/ -> media/t3/');
    eq(ev("(function(){ NX_THUMB_404.set('media/t3/card_mv9byrso_1.webp', Date.now()); const r = mediaBig('media/card_mv9byrso_1.png'); NX_THUMB_404.delete('media/t3/card_mv9byrso_1.webp'); return r; })()"),
       'media/card_mv9byrso_1.png', 'подтверждённый 404 (NX_THUMB_404) -> временно мастер');
    eq(ev("mediaBig('media/card_mv9byrso_1.png')"), 'media/t3/card_mv9byrso_1.webp', 'после истечения мемо — снова t3');

    console.log('\nC. nxDownTierUrl()');
    eq(ev("nxDownTierUrl('https://d3nizkeller.github.io/card-collection/media/t3/x.webp')"),
       'https://d3nizkeller.github.io/card-collection/media/t2/x.webp', 't3 -> t2');
    eq(ev("nxDownTierUrl('https://x/media/t2/x.webp')"), '', 't2 дальше не понижается (сетки не мигают)');
    eq(ev("nxDownTierUrl('https://x/media/x.png')"), '', 'мастер не трогается');
    eq(ev("nxDownTierUrl('')"), '', 'пусто -> пусто');

    console.log('\nD. imgErrorChain: откат t3 -> мастер');
    {
        const r = ev(`(function(){
            const img = document.createElement('img');
            img.setAttribute('src', 'https://d3nizkeller.github.io/card-collection/media/t3/card_mv9byrso_1.webp');
            img.setAttribute('data-nx-full', 'https://d3nizkeller.github.io/card-collection/media/card_mv9byrso_1.png');
            document.body.appendChild(img);
            const res = imgErrorChain(img);
            const out = { res: res, src: img.src, tried: img.__nxThumbTried };
            img.remove();
            return JSON.stringify(out);
        })()`);
        const d = JSON.parse(r);
        eq(d.res, true, 'цепочка вернула true (лечим, не заглушка)');
        ok(d.src.endsWith('/media/card_mv9byrso_1.png'), 'src откатился на мастер из data-nx-full  → ' + d.src);
        eq(d.tried, 1, '__nxThumbTried выставлен (повторных ретраев t3 нет)');
        const r2 = ev(`(function(){
            const img = document.createElement('img');
            img.setAttribute('src', 'https://d3nizkeller.github.io/card-collection/media/t/a.webp');
            img.setAttribute('data-nx-full', 'https://d3nizkeller.github.io/card-collection/media/a.png');
            document.body.appendChild(img);
            imgErrorChain(img);
            const s = img.src; img.remove(); return s;
        })()`);
        ok(r2.endsWith('/media/a.png'), 'старая цепочка t -> data-nx-full не сломана');
    }

    console.log('\nE. nxProgressiveAttach: t3 показывает t2 мгновенно');
    {
        const r = ev(`(function(){
            const img = document.createElement('img');
            img.setAttribute('src', 'media/t3/card_mv9dr7d2_7.webp');
            document.body.appendChild(img);
            nxProgressiveAttach(img);
            const out = { src: img.getAttribute('src'), thumb: img.__nxThumb,
                          loading: NX_FULL_LOADING.has('https://d3nizkeller.github.io/card-collection/media/t3/card_mv9dr7d2_7.webp') };
            img.remove();
            return JSON.stringify(out);
        })()`);
        const d = JSON.parse(r);
        ok(d.src.endsWith('/media/t2/card_mv9dr7d2_7.webp'), 'на карту сразу встала 512px миниатюра  → ' + d.src);
        eq(d.thumb, 1, '__nxThumb=1: после загрузки t3 миниатюра сменится «большим» артом');
        eq(d.loading, true, 't3 поставлен в фоновую очередь NX_FULL_LOADING');
    }

    console.log('\nF. inspectCard: mediaBig + прогрев соседей');
    const insp = ev(`(function(){
        try { SoundFX.play = function(){}; } catch (e) {}
        state.cards = STANDARD_CARDS.map(c => Object.assign({}, c));
        state.collection = state.collection || {};
        const heavy = ['card_mv9byrso_1.png','card_mv9c5cgp_2.png','card_mv9cb6km_3.png','card_mv9cg7nw_4.png','card_mv9dfsrk_5.png'];
        heavy.forEach((h, i) => { if (state.cards[i]) { state.cards[i].image = 'media/' + h; state.collection[state.cards[i].id] = 1; } });
        window.__oldPump = imgPump; imgPump = function(){}; imgQueue.length = 0;
        const ids = state.cards.slice(0, 5).map(c => c.id);
        inspectCard(ids[0], ids);
        const img = document.querySelector('#inspect-card-render img');
        const r = { src: img && img.getAttribute('src'), full: img && img.getAttribute('data-nx-full'), queue: imgQueue.slice() };
        imgPump = window.__oldPump;
        return JSON.stringify(r);
    })()`);
    {
        const r = JSON.parse(insp);
        eq(r.src, 'media/t3/card_mv9byrso_1.webp', 'просмотр карты: src — «большой» t3 (не мастер 10+ МБ)');
        eq(r.full, 'media/card_mv9byrso_1.png', 'data-nx-full — мастер (последний резерв цепочки)');
        const q = r.queue;
        ok(q.length >= 4, 'очередь прогрева соседей не пуста  → ' + q.length);
        ok(q.filter(u => u.indexOf('media/t3/') === 0).length >= 4, 'соседи ±2 греются «большими» артами t3');
        ['card_mv9c5cgp_2', 'card_mv9cb6km_3', 'card_mv9cg7nw_4', 'card_mv9dfsrk_5'].forEach(nm => {
            ok(q.indexOf('media/t3/' + nm + '.webp') >= 0, 'прогрет сосед ' + nm);
        });
    }

    console.log('\nG. Галерея и preloadImages');
    ok(/artTier === 'full' \? mediaBig/.test(APP), "галерея альбома (artTier 'full') использует mediaBig");
    ok(!/artTier === 'full' \? mediaUrl/.test(APP), 'мастер в галерее больше не грузится напрямую');
    eq(ev(`(function(){ imgPump = function(){}; imgQueue.length = 0; IMG_PRELOADED.clear();
        preloadImages(['media/card_mv9dvf6f_8.png'], 'big');
        return imgQueue[0]; })()`), 'media/t3/card_mv9dvf6f_8.webp', "preloadImages tier='big' греет t3");
    eq(ev(`(function(){ imgQueue.length = 0; IMG_PRELOADED.clear();
        preloadImages(['media/card_mv9dki7z_6.png'], 'full');
        return imgQueue[0]; })()`), 'media/card_mv9dki7z_6.png', "tier='full' по-прежнему греет мастер (авто-вшивание владельца)");
    eq(ev(`(function(){ imgQueue.length = 0; IMG_PRELOADED.clear();
        preloadImages(['media/card_mv9dr7d2_7.png']);
        return imgQueue[0]; })()`), 'media/t/card_mv9dr7d2_7.webp', 'по умолчанию греется мелкая миниатюра (сетки не изменились)');

    console.log('\nH. Тег сборки и инструменты');
    const idx = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
    const bld = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');
    eq((idx.match(/\?v=nxmob160/g) || []).length, 8, 'index.html: ?v=nxmob160 x8');
    ok(sw.includes("const VERSION = 'nxmob160';"), 'sw.js: VERSION nxmob160');
    ok(bld.includes("BUILD_TAG = 'nxmob160'"), 'build.py: BUILD_TAG nxmob160');
    ok(!idx.includes('?v=nxmob159') && !sw.includes("'nxmob159'") && !bld.includes("BUILD_TAG = 'nxmob159'"), 'предыдущий тег nxmob159 вычищен из ?v=/VERSION/BUILD_TAG');
    const tfm = fs.readFileSync(path.join(ROOT, 'tools', 'thumbs_for_media.py'), 'utf8');
    ok(tfm.includes("BIGS = os.path.join(MEDIA, 't3')") && tfm.includes('BIG_W, BIG_Q = 1440, 80'), 'thumbs_for_media.py строит t3 (CI догонит новые арты)');
    const stm = fs.readFileSync(path.join(ROOT, 'tools', 'sync_thumb_maps.py'), 'utf8');
    ok(stm.includes("BIG_DECL = 'const NX_EMBED_BIG = '"), 'sync_thumb_maps.py синхронизирует NX_EMBED_BIG');
    const wf = fs.readFileSync(path.join(ROOT, '.github', 'workflows', 'media-thumbs.yml'), 'utf8');
    ok(wf.includes('git add media/t media/t2 media/t3'), 'workflow коммитит media/t3');
    ok(bld.includes("BIGS = os.path.join(MEDIA, 't3')") && bld.includes('__BIG_MAP__'), 'build.py: локальная сборка parity (t3 + __BIG_MAP__)');

    console.log('\n' + (fails ? 'ПРОВАЛ' : 'OK') + ': ' + (checks - fails) + '/' + checks);
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
