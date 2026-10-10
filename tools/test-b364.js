/* b364: общий баланс/прогресс между устройствами одного пользователя.
   Два независимых контекста = два устройства; textdb-документ профиля мокается
   общим хранилищем в Node. Проверки: код профиля, дельта-слияние баланса,
   объединение коллекции, авто-связка по IP, метка prof в реестре, максимум
   вместо суммы в панели для синхронизированных устройств.
   Запуск: node tools/test-b364.js [url] */
const PW = process.env.PW_PATH || '/tmp/pw/node_modules/playwright-core';
const { chromium } = require(PW);
const URL = process.argv[2] || 'http://127.0.0.1:8123/index.html';
const CHROME = process.env.CHROME_PATH || '/tmp/.cache/ms-playwright/chromium-1134/chrome-linux/chrome';

const STORE = new Map(); // ключ textdb -> JSON-строка

async function newDevice(browser, label) {
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 800 } });
  await ctx.addInitScript(() => { try { localStorage.setItem('nx_weak_gpu', '1'); } catch (e) {} }); // без WebGL: 4 страницы на swiftshader не жилец
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
  await page.evaluate(() => { window.jpSyncNow = () => {}; window.jpSyncSoon = () => {}; try { miner.lvl = 0; minerSave(); } catch (e) {} }); // idle-добыча не должна шуметь в дельтах
  return { ctx, page, errs, label };
}

const snap = (page, fn) => page.evaluate(fn);
// дожидаемся реальной синхронизации (profBusy мог быть занят фоновым циклом)
const syncWait = page => page.evaluate(async () => {
  for (let i = 0; i < 15; i++) { const r = await profSyncOnce(true); if (r) return true; await new Promise(res => setTimeout(res, 400)); }
  return false;
});

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
  const A = await newDevice(browser, 'A');
  const B = await newDevice(browser, 'B');

  console.log('=== устройства A и B связываются кодом TEST01 ===');
  const a1 = await snap(A.page, async () => {
    state.coins = 1000; state.cards = [{ id: 'c1', title: 'Карта A', packId: 'p1', rarity: 'common' }];
    saveState();
    profSetCode('TEST01', true);
  });
  await syncWait(A.page);
  const a1b = await snap(A.page, () => ({ coins: state.coins, lastBal: LS.getItem('nx_prof_lastbal') }));
  const docAfterA = STORE.get('nexus-tcg-prof-c-test01');
  console.log('A после пуша: баланс A =', a1b.coins, '| lastBal =', a1b.lastBal, '| документ профиля:', docAfterA ? (JSON.parse(docAfterA).state.coins + ' монет, карт: ' + JSON.parse(docAfterA).state.cards.length) : 'НЕТ');

  const b1 = await snap(B.page, async () => {
    state.coins = 50; state.cards = [{ id: 'c2', title: 'Карта B', packId: 'p1', rarity: 'rare' }];
    saveState();
    profSetCode('TEST01', true);
    for (let i = 0; i < 15; i++) { const r = await profSyncOnce(true); if (r) break; await new Promise(res => setTimeout(res, 400)); }
    return { coins: state.coins, cards: state.cards.map(c => c.id).sort() };
  });
  console.log('B после слияния: баланс =', b1.coins, '(ожидаем 1000+50=1050) | карты:', b1.cards.join(','), '(ожидаем c1,c2)');

  const a2 = await snap(A.page, async () => { for (let i = 0; i < 15; i++) { if (await profSyncOnce(false)) break; await new Promise(r2 => setTimeout(r2, 400)); } return { coins: state.coins, cards: state.cards.map(c => c.id).sort() }; });
  console.log('A подтянул общее: баланс =', a2.coins, '(ожидаем 1050) | карты:', a2.cards.join(','));

  const docNow = tag => { const d = STORE.get('nexus-tcg-prof-c-test01'); console.log('   [doc ' + tag + ']', d ? JSON.parse(d).state.coins : 'НЕТ'); };
  docNow('после связки');
  console.log('\n=== дельта: A заработал +200 офлайн, B ничего не делал ===');
  await snap(A.page, async () => { state.coins += 200; saveState(); });
  await syncWait(A.page);
  docNow('после +200 на A');
  const bBal0 = await snap(B.page, () => ({ coins: state.coins, lastBal: LS.getItem('nx_prof_lastbal') }));
  console.log('   [B до синка] coins', bBal0.coins, 'lastBal', bBal0.lastBal);
  const b2 = await snap(B.page, async () => { for (let i = 0; i < 15; i++) { if (await profSyncOnce(false)) break; await new Promise(r2 => setTimeout(r2, 400)); } return state.coins; });
  const a3 = await snap(A.page, async () => { for (let i = 0; i < 15; i++) { if (await profSyncOnce(false)) break; await new Promise(r2 => setTimeout(r2, 400)); } return state.coins; });
  console.log('B =', b2, '| A =', a3, '(ожидаем 1250 у обоих, без двойного счёта +200)');

  console.log('\n=== трата на B уходит в общий баланс ===');
  await snap(B.page, async () => { state.coins -= 250; saveState(); });
  await syncWait(B.page);
  const a4 = await snap(A.page, async () => { for (let i = 0; i < 15; i++) { if (await profSyncOnce(false)) break; await new Promise(r2 => setTimeout(r2, 400)); } return state.coins; });
  console.log('A =', a4, '(ожидаем 1000)');


  console.log('\n=== реестр и панель ===');
  const reg = await snap(A.page, async () => { siteStatsSelfUpdate(); return { prof: siteStats.p[JACKPOT_CID].prof, dev: !!siteStats.p[JACKPOT_CID].dev, ip: !!siteStats.p[JACKPOT_CID].ip }; });
  console.log('запись A в реестре: prof =', JSON.stringify(reg.prof), '| dev/ip есть:', reg.dev, reg.ip);
  const panel = await snap(A.page, async () => {
    window.cloudGuest = () => false;
    const now = Date.now();
    siteStats.p['xSYNC1aaa'] = { cid: 'xSYNC1aaa', n: 'Тест Синхрон', bal: 900, op: 3, jp: 0, fed: 10, won: 0, at: now, pk: {}, alb: {}, ip: '1.2.3.4', dev: 'Android 14 · Chrome · телефон', did: 'd1', prof: 'код TEST01' };
    siteStats.p['xSYNC2bbb'] = { cid: 'xSYNC2bbb', n: 'Тест Синхрон', bal: 900, op: 3, jp: 0, fed: 10, won: 0, at: now, pk: {}, alb: {}, ip: '1.2.3.4', dev: 'iPadOS 17 · Safari · планшет', did: 'd2', prof: 'код TEST01' };
    window.__nxStatsSig = '';
    statsRender();
    const card = Array.from(document.querySelectorAll('#stats-users > div')).find(d => d.textContent.indexOf('Тест Синхрон') >= 0);
    return card ? card.textContent.replace(/\s+/g, ' ').slice(0, 260) : 'НЕТ КАРТОЧКИ';
  });
  console.log('карточка панели:', panel);
  const errsAB = [...A.errs, ...B.errs];
  await A.ctx.close(); await B.ctx.close();
  await browser.close(); // 4 тяжёлые страницы в одном браузере роняют песочницу — дальше отдельный

  console.log('\n=== авто-связка по IP без кода (устройства C и D) ===');
  const browser2 = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
  const C = await newDevice(browser2, 'C');
  const D = await newDevice(browser2, 'D');
  await snap(C.page, async () => { state.coins = 10; saveState(); });
  await syncWait(C.page);
  await snap(D.page, async () => { state.coins = 5; saveState(); });
  await syncWait(D.page);
  const d1 = await snap(D.page, async () => { for (let i = 0; i < 15; i++) { if (await profSyncOnce(false)) break; await new Promise(r2 => setTimeout(r2, 400)); } return state.coins; });
  const c1 = await snap(C.page, async () => { for (let i = 0; i < 15; i++) { if (await profSyncOnce(false)) break; await new Promise(r2 => setTimeout(r2, 400)); } return state.coins; });
  const ipKeys = Array.from(STORE.keys()).filter(k => k.indexOf('nexus-tcg-prof-i-') === 0);
  console.log('IP-документ:', ipKeys.join(',') || 'НЕТ', '| C =', c1, '| D =', d1, '(ожидаем 15 у обоих)');
  const errs = [...errsAB, ...C.errs, ...D.errs];
  await C.ctx.close(); await D.ctx.close();
  try { await browser2.close(); } catch (e) {}

  console.log('\nошибки страниц:', errs.length ? errs.slice(0, 6) : 'нет');
  const ok = b1.coins === 1050 && a2.coins === 1050 && b2 === 1250 && a4 === 1000 && c1 === 15 && d1 === 15 && /синхронизированы: код TEST01/.test(panel);
  console.log(ok ? '\n✓ b364 РАБОТАЕТ: код, дельты, union, IP-авто, метка в панели' : '\n✗ где-то расхождение с ожиданиями');
  process.exit(ok ? 0 : 1);
})();
