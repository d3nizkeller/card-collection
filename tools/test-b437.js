/* b437: строка количества паков «Открыть сразу: 1 5 10 20 40 | MAX | [40] | итого»
   — ВСЕГДА в одну строку (на телефоне переносилась на две).

   A. Раскладка #nx-qty-row: flex-nowrap + overflow-x-auto + no-scrollbar,
      без flex-wrap; все 9 элементов — прямые дети одной строки; у всех shrink-0.
   B. Компактность на узких экранах: надпись «Открыть сразу:» скрыта до md
      (иконка остаётся, смысл — в title/aria-label), кнопки px-1.5, поле w-12,
      «итого» не переносится (whitespace-nowrap).
   C. Поведение не сломано: пресеты 1/5/10/20/40, MAX = floor(монеты/цена),
      ввод с клавиатуры, клампы 1..99, перерисовка «итого», LS-память.

   Запуск:  node tools/test-b437.js
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

(async () => {
    const G = boot();
    const ev = G.ev, doc = G.doc;

    // рендерим панель пака (облако в тесте недоступно — берём локальный список)
    ev(`
        try { SoundFX.play = function(){}; } catch (e) {}
        SHOP_LIST = shopPacks();
        if (!SHOP_LIST.length) SHOP_LIST = [{ id: 'tp1', title: 'Тестовый пак', price: 1000000, color: 'silver', shimmer: 'holo', image: '', description: 'тест' }];
        packCarousel.idx = 0;
        carouselUpdateDetail();
    `);
    const row = doc.getElementById('nx-qty-row');
    ok(!!row, '#nx-qty-row отрисован');
    if (!row) { console.log('\n' + (fails ? 'ПРОВАЛ' : 'OK') + ': ' + (checks - fails) + '/' + checks); process.exit(fails ? 1 : 0); }

    console.log('\nA. Одна строка: раскладка контейнера');
    ok(row.classList.contains('flex'), 'контейнер — flex');
    ok(row.classList.contains('flex-nowrap'), 'flex-nowrap: переноса на вторую строку нет');
    ok(!row.classList.contains('flex-wrap'), 'старый flex-wrap убран');
    ok(row.classList.contains('overflow-x-auto'), 'overflow-x-auto: крайний случай — прокрутка, а не перенос');
    ok(row.classList.contains('no-scrollbar'), 'no-scrollbar: прокрутка без видимого скроллбара');
    const kids = Array.from(row.children);
    eq(kids.length, 9, 'все 9 элементов — прямые дети ОДНОЙ строки (лейбл + 5 пресетов + MAX + ввод + итого)');
    ok(kids.every(k => !['DIV', 'P', 'BR'].includes(k.tagName)), 'внутри нет блочных переносов (div/p/br)');
    ok(kids.every(k => k.classList.contains('shrink-0')), 'у всех детей shrink-0 — никто не сжимается');

    console.log('\nB. Компактность на узких экранах');
    const label = kids[0];
    eq(label.tagName, 'SPAN', 'первый элемент — лейбл');
    eq(label.getAttribute('title'), 'Открыть сразу', 'смысл лейбла сохранён в title');
    eq(label.getAttribute('aria-label'), 'Открыть сразу', '…и в aria-label');
    ok(!!label.querySelector('i.fa-layer-group'), 'иконка лейбла на месте (видна всегда)');
    const labelText = label.querySelector('span');
    ok(!!labelText && labelText.classList.contains('hidden') && labelText.classList.contains('md:inline'),
        'надпись «Открыть сразу:» скрыта на узких (<md) — экономит ~85px');
    const presets = kids.slice(1, 6);
    eq(presets.map(b => b.textContent.trim()).join(','), '1,5,10,20,40', 'пресеты 1/5/10/20/40 на месте');
    ok(presets.every(b => b.classList.contains('px-1.5')), 'кнопки компактнее: px-1.5 (было px-2)');
    const maxBtn = kids[6];
    eq(maxBtn.textContent.trim(), 'MAX', 'кнопка MAX на месте');
    ok(maxBtn.classList.contains('px-1.5'), 'MAX тоже px-1.5');
    const input = kids[7];
    eq(input.id, 'nx-qty-input', 'поле ввода на месте');
    eq(input.type, 'number', 'поле — number');
    ok(input.classList.contains('w-12'), 'поле компактнее: w-12 (было w-14)');
    const total = kids[8];
    ok(total.textContent.includes('итого'), '«итого» на месте');
    ok(total.classList.contains('whitespace-nowrap'), '«итого» не переносится (whitespace-nowrap)');

    console.log('\nC. Поведение не сломано');
    const price = ev('packSalePrice(SHOP_LIST[packCarousel.idx])');
    ok(price > 0, 'цена пака известна: ' + price);
    ev('nxSetPackQty(20)');
    eq(ev('nxPackQty'), 20, 'клик пресета 20 → nxPackQty=20');
    eq(doc.getElementById('nx-qty-input').value, '20', 'поле ввода перерисовано: 20');
    const sel = Array.from(doc.getElementById('nx-qty-row').children).slice(1, 6).filter(b => b.classList.contains('bg-sky-500/20'));
    eq(sel.length, 1, 'подсвечен ровно один пресет');
    eq(sel[0] && sel[0].textContent.trim(), '20', 'подсвечен пресет 20');
    ok(doc.getElementById('nx-qty-row').children[8].textContent.includes(ev('fmtCoins(' + price + ' * 20)')), '«итого» = цена × 20');
    eq(ev('LS.getItem("nx_pack_qty")'), '20', 'выбор запомнен в LS');
    // MAX = floor(монеты / цена)
    ev('state.coins = ' + price + ' * 7 + 13;');
    doc.querySelector('#nx-qty-row button[title*="максимум"]').click();
    eq(ev('nxPackQty'), 7, 'MAX: 7×цена+13 монет → 7 паков');
    eq(doc.getElementById('nx-qty-input').value, '7', 'поле ввода после MAX: 7');
    // ввод с клавиатуры + клампы
    ev('nxSetPackQty(0)');
    eq(ev('nxPackQty'), 1, 'кламп снизу: 0 → 1');
    ev('nxSetPackQty(500)');
    eq(ev('nxPackQty'), 99, 'кламп сверху: 500 → 99');
    ev('nxSetPackQty(5)');
    eq(doc.getElementById('nx-qty-row').children.length, 9, 'после перерисовок строка та же: 9 элементов в одну линию');

    console.log('\n' + (fails ? 'ПРОВАЛ: ' + fails + ' из ' : 'OK: ') + checks + (fails ? ' (' + fails + ' ❌)' : ' ✅'));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('CRASH', e); process.exit(2); });
