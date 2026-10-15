/* b439: просмотр карты — кнопка скрытия/раскрытия длинного описания.

   A. Длинное описание (>150 симв.): обёртка .nx-desc-wrap, текст .nx-desc-text,
      кнопка .nx-desc-btn; по умолчанию свёрнуто («Показать полностью», aria=false).
   B. Клик по кнопке раскрывает (nx-desc-open, «Свернуть», aria=true), повторный — сворачивает.
   C. Короткое описание (≤150) и пустое (фолбэк) — рендерятся как раньше, без кнопки.
   D. Граница порога: 150 символов — без кнопки, 151 — с кнопкой.
   E. Свайп на соседнюю карту (inspectStep) сохраняет раскрытие; closeInspectModal сбрасывает.
   F. CSS в index.html: line-clamp 3 строки + правило раскрытия (с b440 раскрытый
      текст показывается в панели под картой, а на лице карты скрывается).
   G. Теги nxmob161 (index ?v= x8, sw.js, build.py), исторический nxmob24 не тронут.
   H. Альбом не задет: line-clamp-2 у описаний карточек альбома на месте.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b439.js
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

const LONG = 'Древний хранитель башни, знающий все тайны коллекционеров карт и их судьбы. '.repeat(4); // ~300 симв.
const SHORT = 'Короткое описание карты.';

(async () => {
    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;

    // готовим карты: 0 и 1 — длинные описания, 2 — короткое, 3 — пустое,
    // 4 — ровно 150 символов, 5 — 151 символ
    const ids = JSON.parse(ev(`(function(){
        try { SoundFX.play = function(){}; } catch (e) {}
        window.__oldPump = imgPump; imgPump = function(){}; imgQueue.length = 0;
        state.cards = STANDARD_CARDS.map(c => Object.assign({}, c));
        state.collection = state.collection || {};
        state.cards[0].description = ${JSON.stringify(LONG)};
        state.cards[1].description = ${JSON.stringify(LONG)};
        state.cards[2].description = ${JSON.stringify(SHORT)};
        state.cards[3].description = '';
        state.cards[4].description = 'а'.repeat(150);
        state.cards[5].description = 'а'.repeat(151);
        state.cards.slice(0, 6).forEach(c => { state.collection[c.id] = 1; });
        return JSON.stringify(state.cards.slice(0, 6).map(c => c.id));
    })()`));
    eq(ids.length, 6, 'подготовлено 6 тестовых карт');
    const insp = (i, list) => ev(`inspectCard(${JSON.stringify(ids[i])}, ${list ? JSON.stringify(ids) : 'null'})`);

    console.log('\nA. Длинное описание: кламп + кнопка, по умолчанию свёрнуто');
    insp(0, true);
    {
        const wrap = doc.querySelector('#inspect-card-render .nx-desc-wrap');
        const txt = doc.querySelector('#inspect-card-render .nx-desc-text');
        const btn = doc.querySelector('#inspect-card-render .nx-desc-btn');
        ok(!!wrap, 'обёртка .nx-desc-wrap на месте');
        ok(!!txt, 'текст описания .nx-desc-text на месте');
        ok(!!btn, 'кнопка .nx-desc-btn на месте');
        ok(txt && txt.textContent === LONG, 'внутри полный текст описания (обрежет CSS, не JS)');
        ok(wrap && !wrap.classList.contains('nx-desc-open'), 'по умолчанию свёрнуто (нет nx-desc-open)');
        ok(btn && /Показать полностью/.test(btn.textContent), 'кнопка: «Показать полностью»');
        eq(btn && btn.getAttribute('aria-expanded'), 'false', 'aria-expanded=false');
        ok(btn && /nxDescToggle\(this\)/.test(btn.getAttribute('onclick') || ''), 'onclick ведёт на nxDescToggle');
        eq(ev('nxDescOpen'), false, 'внутренний флаг nxDescOpen=false');
        ok(doc.getElementById('modal-inspect').classList.contains('hidden') === false, 'модалка просмотра открыта');
    }

    console.log('\nB. Клик: раскрытие и повторное сворачивание');
    {
        const btn = doc.querySelector('#inspect-card-render .nx-desc-btn');
        btn.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
        const wrap = doc.querySelector('#inspect-card-render .nx-desc-wrap');
        ok(wrap.classList.contains('nx-desc-open'), 'клик: обёртка получила nx-desc-open');
        ok(/Свернуть/.test(btn.textContent), 'клик: кнопка теперь «Свернуть»');
        eq(btn.getAttribute('aria-expanded'), 'true', 'клик: aria-expanded=true');
        eq(ev('nxDescOpen'), true, 'клик: nxDescOpen=true');
        ok(/fa-chevron-up/.test(btn.innerHTML), 'клик: иконка — шеврон вверх');
        btn.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
        ok(!wrap.classList.contains('nx-desc-open'), 'повторный клик: снова свёрнуто');
        ok(/Показать полностью/.test(btn.textContent), 'повторный клик: кнопка «Показать полностью»');
        eq(btn.getAttribute('aria-expanded'), 'false', 'повторный клик: aria-expanded=false');
        eq(ev('nxDescOpen'), false, 'повторный клик: nxDescOpen=false');
    }

    console.log('\nC. Короткое и пустое описание — без кнопки (как раньше)');
    insp(2, true);
    {
        const p = doc.querySelector('#inspect-card-render .nx-desc-wrap');
        eq(p, null, 'короткое описание: обёртки .nx-desc-wrap нет');
        eq(doc.querySelector('#inspect-card-render .nx-desc-btn'), null, 'короткое описание: кнопки нет');
        const ps = [...doc.querySelectorAll('#inspect-card-render p')];
        ok(ps.some(x => x.textContent === SHORT), 'короткое описание отрендерено обычным <p>');
    }
    insp(3, true);
    {
        eq(doc.querySelector('#inspect-card-render .nx-desc-wrap'), null, 'пустое описание (фолбэк): обёртки нет');
        eq(doc.querySelector('#inspect-card-render .nx-desc-btn'), null, 'пустое описание (фолбэк): кнопки нет');
        const ps = [...doc.querySelectorAll('#inspect-card-render p')];
        ok(ps.some(x => /Коллекционная карта/.test(x.textContent)), 'фолбэк-текст «Коллекционная карта…» на месте');
    }

    console.log('\nD. Граница порога NX_DESC_CLAMP_LEN=150');
    eq(ev('NX_DESC_CLAMP_LEN'), 150, 'порог «длинного» описания — 150 символов');
    insp(4, true);
    eq(doc.querySelector('#inspect-card-render .nx-desc-btn'), null, 'ровно 150 символов — кнопка НЕ нужна');
    insp(5, true);
    ok(!!doc.querySelector('#inspect-card-render .nx-desc-btn'), '151 символ — кнопка есть');

    console.log('\nE. Свайп сохраняет раскрытие, закрытие модалки сбрасывает');
    insp(0, true);
    doc.querySelector('#inspect-card-render .nx-desc-btn').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    ev('inspectStep(1)'); // переход на соседнюю карту с длинным описанием
    {
        const wrap = doc.querySelector('#inspect-card-render .nx-desc-wrap');
        const btn = doc.querySelector('#inspect-card-render .nx-desc-btn');
        ok(wrap && wrap.classList.contains('nx-desc-open'), 'соседняя карта открыта уже раскрытой');
        ok(btn && /Свернуть/.test(btn.textContent), 'на соседней кнопка сразу «Свернуть»');
        eq(ev('inspectIdx'), 1, 'inspectStep сдвинул индекс на 1');
    }
    ev('closeInspectModal()');
    eq(ev('nxDescOpen'), false, 'closeInspectModal сбросил nxDescOpen');
    ok(doc.getElementById('modal-inspect').classList.contains('hidden'), 'модалка закрыта');
    insp(1, true);
    {
        const wrap = doc.querySelector('#inspect-card-render .nx-desc-wrap');
        ok(wrap && !wrap.classList.contains('nx-desc-open'), 'после закрытия новое открытие — свёрнуто');
        ok(/Показать полностью/.test(doc.querySelector('#inspect-card-render .nx-desc-btn').textContent), 'кнопка снова «Показать полностью»');
    }

    console.log('\nF. CSS в index.html');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        ok(html.includes('.nx-desc-wrap .nx-desc-text{ display:-webkit-box'), 'CSS: кламп через -webkit-box');
        ok(html.includes('-webkit-line-clamp:3'), 'CSS: свёрнуто до 3 строк');
        // b440: раскрытый текст уехал в панель #inspect-desc-full под картой —
        // на лице карты он в раскрытом состоянии скрывается (иначе длинный текст
        // обрезался бы краем карты: aspect-ratio 9/16 + overflow:hidden)
        ok(html.includes('.nx-desc-wrap.nx-desc-open .nx-desc-text{ display:none; }'), 'CSS: раскрытие прячет текст на лице карты (b440: весь текст — в панели под картой)');
        ok(html.includes('.nx-desc-btn{ cursor:pointer'), 'CSS: курсор-указатель на кнопке');
    }

    console.log('\nG. Теги сборки едины (боевой тег берём из sw.js)');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bld = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');
        const tagM = sw.match(/const VERSION = '(nxmob\d+)';/);
        ok(!!tagM, 'sw.js: боевой тег VERSION парсится');
        const TAG = tagM ? tagM[1] : 'nxmob0';
        ok(TAG >= 'nxmob161', 'боевой тег не старше nxmob161 (сборка b439)  → ' + TAG);
        const vTags = html.match(/\?v=nxmob\d+/g) || [];
        eq(vTags.filter(s => s === '?v=' + TAG).length, 8, 'index.html: ?v=' + TAG + ' × 8');
        ok(!vTags.some(s => s !== '?v=' + TAG), 'index.html: чужих/устаревших тегов в ?v= нет');
        ok(bld.includes("BUILD_TAG = '" + TAG + "'"), 'build.py: BUILD_TAG ' + TAG);
        ok(/nxmob24/.test(html.split('\n')[23]), 'index.html: исторический комментарий nxmob24 не тронут');
    }

    console.log('\nH. Альбом не задет, старый inspect-рендер заменён');
    {
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        ok((app.match(/line-clamp-2 drop-shadow/g) || []).length >= 2, 'альбом/строки: line-clamp-2 описания на месте');
        // в альбоме (13619/14120) описания остались с line-clamp-2 — их не трогаем;
        // проверяем, что бесклампного descHtml больше нет именно в inspectCard
        ok(!/^\s*const descHtml = `<p class="w-full text-xs text-slate-300 drop-shadow \$\{L\.text\}">/m.test(app),
            'старый бесклампный descHtml в inspectCard заменён');
        const fn = app.slice(app.indexOf('function inspectCard(cardId, list)'));
        ok(fn.indexOf('NX_DESC_CLAMP_LEN') > 0 && fn.indexOf('NX_DESC_CLAMP_LEN') < 4000, 'inspectCard ветвится по NX_DESC_CLAMP_LEN');
        ok(app.includes('function nxDescToggle(') && app.includes('function nxDescBtnHtml('), 'хелперы b439 на месте');
        ok(app.includes('nxDescOpen = false; // b439'), 'сброс в closeInspectModal на месте');
    }

    console.log('\n' + (fails ? 'ПРОВАЛ: ' + fails + ' из ' : 'OK: ') + checks + (fails ? ' (' + fails + ' ❌)' : ' ✅'));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('CRASH', e); process.exit(2); });
