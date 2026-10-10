/* b375: порядок карт — порядок владельца.
   1) profMergeState: порядок out.cards определяется нумерацией ord, а не объединением ключей;
      ord берётся у стороны, которая последней меняла порядок (ordAt, LWW).
   2) миграция при загрузке: перемешанный state.cards восстанавливается по времени создания id.
   3) E2E: устройство B после связки кодом получает порядок владельца A (не порядок документа).
   4) bulkCreateCards: порядок строк = порядок карт, номера ord растут; Студия показывает №1..№N
      и кнопки перемещения; moveCardInPack меняет порядок и БЕЗ force доезжает до B (sig-ворота пуша).
   Запуск: node tools/test-b375.js [url] */
const PW = process.env.PW_PATH || '/tmp/pw/node_modules/playwright-core';
const { chromium } = require(PW);
const URL = process.argv[2] || 'http://127.0.0.1:8123/index.html';
const CHROME = process.env.CHROME_PATH || '/tmp/.cache/ms-playwright/chromium-1134/chrome-linux/chrome';
const PACK = 'p-b375';

const STORE = new Map();
let fails = 0;
const ok = (cond, msg) => { console.log((cond ? '  ✅ ' : '  ❌ ') + msg); if (!cond) fails++; };

async function newDevice(browser, label) {
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 850 } });
  await ctx.addInitScript(() => { try { localStorage.setItem('nx_weak_gpu', '1'); localStorage.setItem('ui_prefs_v1', JSON.stringify({ section: 1 })); } catch (e) {} }); // без WebGL + открытая Студия (скрытая вкладка)
  await ctx.route('https://textdb.dev/**', async route => {
    const u = route.request().url();
    const key = u.replace(/https:\/\/textdb\.dev\/api\/data\//, '').replace(/[?].*$/, '');
    if (route.request().method() === 'POST') {
      STORE.set(key, route.request().postData());
      await route.fulfill({ status: 200, contentType: 'text/plain', body: 'ok' });
      return;
    }
    const body = STORE.has(key) ? STORE.get(key) : 'null';
    await route.fulfill({ status: 200, contentType: 'application/json', body });
  });
  await ctx.route('https://api.ipify.org/**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ip: '9.9.9.9' }) }));
  await ctx.route('https://api64.ipify.org/**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ip: '9.9.9.9' }) }));
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(label + ' pageerror: ' + e.message));
  await page.goto(URL, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(3000);
  await page.evaluate(() => { window.jpSyncNow = () => {}; window.jpSyncSoon = () => {}; });
  return { ctx, page, errs, label };
}
const syncLoop = (page, force) => page.evaluate(async f => {
  for (let i = 0; i < 15; i++) { const r = await profSyncOnce(f); if (r) return true; await new Promise(res => setTimeout(res, 400)); }
  return false;
}, force);

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
  const A = await newDevice(browser, 'A');
  const B = await newDevice(browser, 'B');

  console.log('=== 1) profMergeState: порядок по нумерации, а не по объединению ключей ===');
  const unit = await A.page.evaluate(() => {
    const mk = (id, ord, ordAt) => ({ id, packId: 'p1', name: id, rarity: 'common', image: '', ord, ordAt });
    const L = {
      coins: 0, packs: [], deck: [], stats: {}, achievements: {}, pity: {}, albumBonus: {}, packStats: {}, windowBuys: {},
      collection: { 'card-100': 1, 'card-200': 1, 'card-300': 1 },
      cards: [mk('card-300', 30, 9), mk('card-100', 10, 9), mk('card-200', 20, 9)]
    };
    const R = { cards: [mk('card-200'), mk('card-300'), mk('card-100')], packs: [], deck: [], collection: {} }; // документ в другом порядке, без номеров
    const out1 = profMergeState(JSON.parse(JSON.stringify(L)), R, null, 'devX');
    // LWW: облако ПОСЛЕДНИМ поменяло порядок card-100 (ordAt 99) — его номер побеждает
    const R2 = { cards: [Object.assign(mk('card-100', 999, 99)), mk('card-200'), mk('card-300')], packs: [], deck: [], collection: {} };
    const out2 = profMergeState(JSON.parse(JSON.stringify(L)), R2, null, 'devX');
    return {
      ids1: out1.cards.map(c => c.id),
      ids2: out2.cards.map(c => c.id),
      ord100: (out2.cards.find(c => c.id === 'card-100') || {}).ord
    };
  });
  ok(JSON.stringify(unit.ids1) === JSON.stringify(['card-100', 'card-200', 'card-300']), 'L [300,100,200] + документ [200,300,100] → порядок по ord: ' + unit.ids1.join(','));
  ok(JSON.stringify(unit.ids2) === JSON.stringify(['card-200', 'card-300', 'card-100']) && unit.ord100 === 999, 'LWW: свежий ordAt облака побеждает → ' + unit.ids2.join(',') + ' (ord card-100 = ' + unit.ord100 + ')');

  console.log('=== 2) миграция при загрузке: перемешанные карты возвращаются в порядок загрузки ===');
  const T0 = Date.now();
  await A.page.evaluate(([t0, PACK]) => {
    state.cards = [
      { id: 'card-' + (t0 + 2), packId: PACK, name: 'Третья', rarity: 'common', image: '' },
      { id: 'card-' + t0, packId: PACK, name: 'Первая', rarity: 'common', image: '' },
      { id: 'card-' + (t0 + 1), packId: PACK, name: 'Вторая', rarity: 'common', image: '' }
    ];
    state.packs = [{ id: PACK, title: 'Тест b375', price: 100, color: 'silver', shimmer: 'holo', image: '' }];
    state.collection = {};
    saveState();
  }, [T0, PACK]);
  await A.page.reload({ waitUntil: 'load', timeout: 60000 });
  await A.page.waitForTimeout(3000);
  await A.page.evaluate(() => { window.jpSyncNow = () => {}; window.jpSyncSoon = () => {}; });
  const mig = await A.page.evaluate(PACK => ({
    names: state.cards.filter(c => c.packId === PACK).map(c => c.name),
    ords: state.cards.filter(c => c.packId === PACK).map(c => c.ord > 0),
    persisted: (JSON.parse(LS.getItem('nexus_cards')).filter(c => c.packId === PACK)).every(c => c.ord > 0)
  }), PACK);
  ok(JSON.stringify(mig.names) === JSON.stringify(['Первая', 'Вторая', 'Третья']), 'после reload порядок восстановлен по времени загрузки: ' + mig.names.join(' → '));
  ok(mig.ords.every(Boolean) && mig.persisted, 'каждой карте проставлен явный номер ord (и сохранён в LS)');

  console.log('=== 3) E2E: владелец переставил карты — устройство B получает ТОТ ЖЕ порядок ===');
  const owner = await A.page.evaluate(async PACK => {
    const cs = state.cards.filter(c => c.packId === PACK); // Первая, Вторая, Третья
    const t = Date.now();
    cs[0].ord = 20; cs[0].ordAt = t; // Первая
    cs[1].ord = 30; cs[1].ordAt = t; // Вторая
    cs[2].ord = 10; cs[2].ordAt = t; // Третья — теперь первая
    cardsSortNorm();
    state.collection = {}; cs.forEach(c => state.collection[c.id] = 1);
    state.coins = 700;
    saveState();
    profSetCode('TEST75', true);
    for (let i = 0; i < 15; i++) { if (await profSyncOnce(true)) break; await new Promise(r => setTimeout(r, 400)); }
    return state.cards.filter(c => c.packId === PACK).map(c => c.name);
  }, PACK);
  ok(JSON.stringify(owner) === JSON.stringify(['Третья', 'Первая', 'Вторая']), 'порядок владельца на A: ' + owner.join(' → '));
  const bOrder = await B.page.evaluate(async PACK => {
    profSetCode('TEST75', true);
    for (let i = 0; i < 15; i++) { if (await profSyncOnce(true)) break; await new Promise(r => setTimeout(r, 400)); }
    return state.cards.filter(c => c.packId === PACK).map(c => c.name);
  }, PACK);
  ok(JSON.stringify(bOrder) === JSON.stringify(['Третья', 'Первая', 'Вторая']), 'B после связки видит ТОТ ЖЕ порядок: ' + bOrder.join(' → '));
  const doc = JSON.parse(STORE.get('nexus-tcg-prof-c-test75') || '{}');
  const docOrds = ((doc.state || {}).cards || []).filter(c => c.packId === PACK).map(c => c.ord);
  ok(docOrds.length === 3 && docOrds.every(o => o > 0), 'в документе профиля у карт есть номера ord: ' + docOrds.join(','));

  console.log('=== 4) массовая загрузка: порядок строк = порядок карт + нумерация в Студии ===');
  const bulk = await A.page.evaluate(async PACK => {
    renderStudio();
    const sel = document.getElementById('bulk-pack-id'); if (sel) sel.value = PACK;
    const ta = document.getElementById('bulk-card-urls');
    ta.value = 'https://x.dev/a.png|Альфа\nhttps://x.dev/b.png|Бета\nhttps://x.dev/c.png|Гамма';
    await bulkCreateCards();
    state.cards.filter(c => c.packId === PACK).forEach(c => { state.collection[c.id] = 1; }); // владелец держит свои карты
    saveState();
    const mine = state.cards.filter(c => c.packId === PACK);
    return {
      ordGrow: mine.every((c, i) => i === 0 || c.ord > mine[i - 1].ord),
      last3: mine.slice(-3).map(c => c.name)
    };
  }, PACK);
  ok(JSON.stringify(bulk.last3) === JSON.stringify(['Альфа', 'Бета', 'Гамма']), 'порядок строк загрузки сохранён: ' + bulk.last3.join(' → '));
  ok(bulk.ordGrow, 'номера ord растут вдоль списка (порядок закреплён номерами)');

  const ui = await A.page.evaluate(PACK => {
    renderStudio();
    const box = document.getElementById('pack-cards-' + PACK);
    const html = box ? box.innerHTML : '';
    return {
      badges: ['№1', '№2', '№3', '№4', '№5', '№6'].filter(b => html.includes(b)).length,
      moveBtns: (html.match(/moveCardInPack\(/g) || []).length
    };
  }, PACK);
  ok(ui.badges >= 6 && ui.moveBtns >= 12, 'в Студии номера №1…№' + ui.badges + ' и кнопки перемещения (' + ui.moveBtns + ' шт.)');

  console.log('=== 4b) moveCardInPack + авто-пуш БЕЗ force: перестановка доезжает до B ===');
  const moved = await A.page.evaluate(async PACK => {
    const beta = state.cards.find(c => c.name === 'Бета');
    moveCardInPack(beta.id, -1); // Бета вверх
    const names = state.cards.filter(c => c.packId === PACK).slice(-3).map(c => c.name);
    let pushed = false;
    for (let i = 0; i < 15; i++) { if (await profSyncOnce(false)) { pushed = true; break; } await new Promise(r => setTimeout(r, 400)); } // НЕ force — только sig-ворота
    return { names, ordAt: beta.ordAt > 0, saved: (JSON.parse(LS.getItem('nexus_cards')).find(c => c.id === beta.id) || {}).ordAt > 0, pushed };
  }, PACK);
  ok(JSON.stringify(moved.names) === JSON.stringify(['Бета', 'Альфа', 'Гамма']), 'Бета поднялась наверх: ' + moved.names.join(' → '));
  ok(moved.ordAt && moved.saved, 'перемещение помечено ordAt и сохранено в LS');
  const docAfter = JSON.parse(STORE.get('nexus-tcg-prof-c-test75') || '{}');
  const docNames = ((docAfter.state || {}).cards || []).filter(c => c.packId === PACK).map(c => c.name);
  ok(moved.pushed && JSON.stringify(docNames) === JSON.stringify(['Третья', 'Первая', 'Вторая', 'Бета', 'Альфа', 'Гамма']), 'авто-пуш без force опубликовал новый порядок: ' + docNames.join(' → '));

  const bMoved = await B.page.evaluate(async PACK => {
    for (let i = 0; i < 15; i++) { if (await profSyncOnce(false)) break; await new Promise(r => setTimeout(r, 400)); }
    return state.cards.filter(c => c.packId === PACK).map(c => c.name);
  }, PACK);
  ok(JSON.stringify(bMoved) === JSON.stringify(['Третья', 'Первая', 'Вторая', 'Бета', 'Альфа', 'Гамма']), 'B подтянул перестановку владельца: ' + bMoved.join(' → '));

  console.log('=== 5) скриншот Студии с нумерацией ===');
  await A.page.evaluate(PACK => {
    try { closeDailyModal(); } catch (e) {}
    try { studioUnlocked = true; } catch (e) {} // b133: гейт пароля комнаты — в тесте открываем напрямую
    switchTab('studio');
    showStudioSec('catalog'); // список паков с их карточками — в секции «Каталог»
    if (!studioOpenPacks.has(PACK)) toggleStudioPackCards(PACK);
    const box = document.getElementById('pack-cards-' + PACK);
    if (box && box.scrollIntoView) box.scrollIntoView({ block: 'center' });
  }, PACK);
  await A.page.waitForTimeout(800);
  await A.page.evaluate(PACK => {
    const t = document.getElementById('toast-container'); if (t) t.innerHTML = ''; // чистый кадр без тостов
    const box = document.getElementById('pack-cards-' + PACK);
    if (box && box.scrollIntoView) box.scrollIntoView({ block: 'center' }); // после перерисовки скролл сбрасывается — крутим ещё раз
  }, PACK);
  await A.page.waitForTimeout(300);
  await A.page.screenshot({ path: 'tools/shots/b375-card-numbers.png' });
  console.log('  снимок: tools/shots/b375-card-numbers.png');

  const allErrs = A.errs.concat(B.errs);
  ok(allErrs.length === 0, 'без ошибок страницы' + (allErrs.length ? ': ' + allErrs.slice(0, 3).join(' | ') : ''));

  await A.ctx.close(); await B.ctx.close(); await browser.close();
  console.log(fails === 0 ? '\n=== b375: ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ ===' : '\n=== b375: ПРОВАЛОВ: ' + fails + ' ===');
  process.exit(fails === 0 ? 0 : 1);
})().catch(e => { console.error('FATAL', e); process.exit(2); });
