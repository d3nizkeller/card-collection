/* b365: QR-код профиля синхронизации.
   Проверяем цикл целиком: нарисовали QR -> декодировали jsQR -> содержимое =
   ссылка ?prof=КОД -> «скан» этой ссылки (qrxHandleCode) -> код применён.
   Запуск: node tools/test-b365.js [url] */
const PW = process.env.PW_PATH || '/tmp/pw/node_modules/playwright-core';
const { chromium } = require(PW);
const URL = process.argv[2] || 'http://127.0.0.1:8123/index.html';
const CHROME = process.env.CHROME_PATH || '/tmp/.cache/ms-playwright/chromium-1134/chrome-linux/chrome';

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 800 } });
  await ctx.addInitScript(() => { try { localStorage.setItem('nx_weak_gpu', '1'); } catch (e) {} });
  // профильные документы textdb мокаем — привязка кода запускает синхронизацию
  const STORE = new Map();
  await ctx.route('https://textdb.dev/api/data/nexus-tcg-prof-*', async route => {
    const u = route.request().url();
    const key = u.replace(/https:\/\/textdb\.dev\/api\/data\//, '').replace(/[?].*$/, '');
    if (route.request().method() === 'POST') { STORE.set(key, route.request().postData()); await route.fulfill({ status: 200, body: 'ok' }); return; }
    await route.fulfill({ status: 200, contentType: 'application/json', body: STORE.has(key) ? STORE.get(key) : 'null' });
  });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push('pageerror: ' + e.message));
  await page.goto(URL, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(3500);

  const r = await page.evaluate(async () => {
    const out = {};
    try { document.getElementById('modal-daily').classList.add('hidden'); } catch (e) {}
    // 1) показ QR: кода ещё нет — должен создаться
    profQrShow();
    const cv = document.getElementById('nx-prof-qr-canvas');
    const modal = document.getElementById('nx-prof-qr-modal');
    out.modalVisible = !!modal && !modal.classList.contains('hidden');
    out.code = profCode();
    out.codeShown = (document.getElementById('nx-prof-qr-code') || {}).textContent || '';
    // canvas непустой?
    let dark = 0;
    const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
    for (let i = 0; i < d.length; i += 4) if (d[i] < 128) dark++;
    out.darkPixels = dark;
    // 2) декодируем нарисованный QR тем же jsQR, которым сканирует сайт
    const res = jsQR(d, cv.width, cv.height);
    out.qrText = res ? res.data : 'НЕ ЧИТАЕТСЯ';
    out.qrIsProfLink = /[?&]prof=[A-Z0-9]{6}/.test(out.qrText || '');
    out.linkMatches = profQrFromText(out.qrText) === profCode();
    // 3) распознавание «голым» кодом
    out.bareCode = profQrFromText('NXPROF:AB12CD') === 'AB12CD';
    out.looksLike = qrxLooksLikeCode(out.qrText) === true;
    // 4) имитация скана чужой ссылки: устройство привязывается к профилю QR77XK
    await qrxHandleCode('https://d3nizkeller.github.io/card-collection/?prof=QR77XK');
    out.appliedCode = profCode();
    // синхронизация создала документ нового профиля?
    for (let i = 0; i < 25; i++) { if (await profSyncOnce(true)) break; await new Promise(r2 => setTimeout(r2, 300)); }
    out.docCreated = 'ok';
    profQrClose();
    out.modalHidden = modal.classList.contains('hidden');
    return out;
  });

  console.log('модалка QR видна          :', r.modalVisible);
  console.log('код профиля создан        :', r.code, '| подпись:', r.codeShown);
  console.log('тёмных пикселей на canvas :', r.darkPixels, '(0 = пусто)');
  console.log('QR декодируется jsQR      :', r.qrText);
  console.log('это ссылка ?prof=КОД      :', r.qrIsProfLink, '| код совпадает:', r.linkMatches);
  console.log('голый NXPROF: распознаётся:', r.bareCode, '| qrxLooksLikeCode:', r.looksLike);
  console.log('«скан» чужой ссылки       : применён код', r.appliedCode, '(ожидаем QR77XK)');
  console.log('док-профиль создан        :', Array.from(STORE.keys()).join(',') || 'нет');
  console.log('модалка закрывается       :', r.modalHidden);
  console.log('ошибки страницы           :', errs.length ? errs.slice(0, 5) : 'нет');
  const ok = r.modalVisible && /^[A-Z0-9]{6}$/.test(r.code) && r.darkPixels > 1000 && r.qrIsProfLink && r.linkMatches && r.bareCode && r.looksLike && r.appliedCode === 'QR77XK' && STORE.has('nexus-tcg-prof-c-qr77xk') && r.modalHidden && errs.length === 0;
  console.log(ok ? '\n✓ b365 РАБОТАЕТ: QR рисуется, читается своим же сканером, привязывает профиль' : '\n✗ есть расхождение');
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
