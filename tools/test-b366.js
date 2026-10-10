/* b366: один QR = прогресс + код профиля.
   Устройство A показывает QR переноса (кнопка QR в навбаре), устройство B
   сканирует его: получает прогресс И привязывается к профилю.
   Запуск: node tools/test-b366.js [url] */
const PW = process.env.PW_PATH || '/tmp/pw/node_modules/playwright-core';
const { chromium } = require(PW);
const URL = process.argv[2] || 'http://127.0.0.1:8123/index.html';
const CHROME = process.env.CHROME_PATH || '/tmp/.cache/ms-playwright/chromium-1134/chrome-linux/chrome';

const STORE = new Map(); // мок textdb: профили + relay-ключи

async function newDevice(browser, label) {
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 800 } });
  await ctx.addInitScript(() => { try { localStorage.setItem('nx_weak_gpu', '1'); } catch (e) {} });
  await ctx.route('https://textdb.dev/**', async route => {
    const u = route.request().url();
    const key = u.replace(/https:\/\/textdb\.dev\/api\/data\//, '').replace(/[?].*$/, '');
    if (route.request().method() === 'POST') { STORE.set(key, route.request().postData()); await route.fulfill({ status: 200, body: 'ok' }); return; }
    await route.fulfill({ status: 200, contentType: 'application/json', body: STORE.has(key) ? STORE.get(key) : 'null' });
  });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(label + ': ' + e.message));
  await page.goto(URL, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(3200);
  await page.evaluate(() => { window.jpSyncNow = () => {}; window.jpSyncSoon = () => {}; try { miner.lvl = 0; minerSave(); } catch (e) {} });
  return { ctx, page, errs, label };
}

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
  const A = await newDevice(browser, 'A');

  // A: прогресс + QR из модалки переноса (кнопка QR в навбаре)
  const a = await A.page.evaluate(async () => {
    try { document.getElementById('modal-daily').classList.add('hidden'); } catch (e) {}
    state.coins = 4321;
    state.cards = [{ id: 'cardA', title: 'Карта A', packId: 'p1', rarity: 'rare' }];
    saveState();
    openQrModal();                       // та самая модалка из навбара
    let cv = null;
    for (let i = 0; i < 40; i++) {        // ждём, пока QR нарисуется и пройдёт самопроверку
      await new Promise(r => setTimeout(r, 300));
      const w = document.getElementById('qr-canvas-wrap');
      cv = document.getElementById('qr-canvas');
      if (w && !w.classList.contains('hidden') && cv && cv.width > 0) break;
    }
    const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height);
    const res = jsQR(d.data, cv.width, cv.height);
    return {
      code: res ? res.data : '',
      qrText: res ? res.data : 'НЕ ЧИТАЕТСЯ',
      qrKind: res ? (res.data.indexOf('NXR1.') === 0 ? 'relay(короткий)' : 'direct') : '?',
      status: (document.getElementById('qr-show-status') || {}).textContent || '',
      prof: profCode(),
    };
  });
  console.log('A: код переноса', a.code.slice(0, 12) + '… (' + a.code.length + ' симв.) | тип:', a.qrKind);
  console.log('A: QR декодируется своим же jsQR:', a.qrText === a.code);
  console.log('A: статус модалки:', a.status.trim().slice(0, 140));
  console.log('A: код профиля:', a.prof);

  // B: сканирует этот код
  const B = await newDevice(browser, 'B');
  const b = await B.page.evaluate(async (code) => {
    const L = [];
    const S = tag => L.push(tag + ': coins=' + state.coins + ' lastBal=' + LS.getItem('nx_prof_lastbal') + ' prof=' + profCode());
    state.coins = 7; state.cards = [{ id: 'cardB', title: 'Карта B', packId: 'p1', rarity: 'common' }]; saveState();
    S('до скана');
    await qrxHandleCode(code);                       // как после скана камерой
    S('после скана');
    const confVisible = !document.getElementById('qr-view-conf').classList.contains('hidden');
    const chips = (document.getElementById('qr-conf-chips') || {}).textContent || '';
    return { confVisible, chips: chips.replace(/\s+/g, ' ').trim().slice(0, 90), profAfterScan: profCode(), log: L };
  }, a.qrText);
  console.log('   ' + (b.log || []).join('\n   '));
  console.log('\nB: экран подтверждения переноса виден:', b.confVisible, '| чипы:', b.chips);
  console.log('B: привязался к профилю после скана:', b.profAfterScan, '(ожидаем', a.prof + ')');

  const b2 = await B.page.evaluate(async () => {
    const L = [];
    const S = tag => L.push(tag + ': coins=' + state.coins + ' lastBal=' + LS.getItem('nx_prof_lastbal'));
    qrxAccept();                                     // принял прогресс
    S('после accept');
    await new Promise(r => setTimeout(r, 300));
    S('после 300мс');
    const got = { coins: state.coins, cards: state.cards.map(c => c.id).sort() };
    for (let i = 0; i < 20; i++) { const r = await profSyncOnce(true); S('sync#' + i + ' -> ' + r); if (r) break; await new Promise(r2 => setTimeout(r2, 300)); }
    got.log = L;
    return got;
  });
  console.log('   ' + (b2.log || []).join('\n   '));
  console.log('B: после «Принять»: баланс =', b2.coins, '(ожидаем 4321) | карты:', b2.cards.join(','), '(перенос ЗАМЕНЯет сохранение снимком: cardA)');

  // A подтягивает cardB через профиль (баланс общий)
  await A.page.evaluate(async () => { for (let i = 0; i < 20; i++) { if (await profSyncOnce(false)) break; await new Promise(r => setTimeout(r, 300)); } });
  const a2 = await A.page.evaluate(() => ({ coins: state.coins, cards: state.cards.map(c => c.id).sort() }));
  console.log('A: после профиль-синка: баланс =', a2.coins, '| карты:', a2.cards.join(','));

  // обратная совместимость: код БЕЗ профиля не привязывает ничего
  const b3 = await B.page.evaluate(async () => {
    const before = profCode();
    const json = JSON.stringify({ v: 1, col: {}, coins: 5, packs: [], cards: [], stats: {} });
    await qrxHandleCode(json);
    return { before, after: profCode(), conf: !document.getElementById('qr-view-conf').classList.contains('hidden') };
  });
  console.log('\nСовместимость: код без профиля → подтверждение видно:', b3.conf, '| код профиля не изменился:', b3.before === b3.after);

  const a2Preview = a2.coins;
  const profDocs = Array.from(STORE.keys()).filter(k => k.indexOf('nexus-tcg-prof-') === 0);
  console.log('профильные документы в облаке:', profDocs.join(',') || 'нет');
  const errs = [...A.errs, ...B.errs];
  console.log('ошибки страниц:', errs.length ? errs.slice(0, 5) : 'нет');
  const ok = a.qrText === a.code && /профил/i.test(a.status) && b.confVisible && b.profAfterScan === a.prof && b2.coins >= 4321 && b2.coins === a2Preview && a2.cards.join(',') === 'cardA,cardB' && profDocs.length >= 1 && b3.conf && b3.before === b3.after && errs.length === 0;
  console.log(ok ? '\n✓ b366 РАБОТАЕТ: один QR несёт и прогресс, и профиль' : '\n✗ расхождение с ожиданиями');
  await A.ctx.close(); await B.ctx.close();
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
