/* b365/b372: QR-привязка профиля живёт в модалке QR из навбара (доступна всем),
   в Студии блока синхронизации больше нет.
   Запуск: node tools/test-b365.js [url] */
const PW = process.env.PW_PATH || '/tmp/pw/node_modules/playwright-core';
const { chromium } = require(PW);
const URL = process.argv[2] || 'http://127.0.0.1:8123/index.html';
const CHROME = process.env.CHROME_PATH || '/tmp/.cache/ms-playwright/chromium-1134/chrome-linux/chrome';

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 560, height: 900 }, deviceScaleFactor: 2 });
  await ctx.addInitScript(() => { try { localStorage.setItem('nx_weak_gpu', '1'); } catch (e) {} });
  const STORE = new Map();
  await ctx.route('https://textdb.dev/**', async route => {
    const u = route.request().url();
    const key = u.replace(/https:\/\/textdb\.dev\/api\/data\//, '').replace(/[?].*$/, '');
    if (route.request().method() === 'POST') { STORE.set(key, route.request().postData()); await route.fulfill({ status: 200, body: 'ok' }); return; }
    await route.fulfill({ status: 200, contentType: 'application/json', body: STORE.has(key) ? STORE.get(key) : 'null' });
  });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(e.message));
  await page.goto(URL, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(3200);

  const r = await page.evaluate(async () => {
    const out = {};
    try { document.getElementById('modal-daily').classList.add('hidden'); } catch (e) {}
    // в Студии больше нет блока синхронизации
    out.studioBlockGone = !Array.from(document.querySelectorAll('.studio-sec h3 span')).some(sp => sp.textContent.indexOf('Синхронизация между устройствами') >= 0);
    out.profQrModalGone = typeof profQrShow === 'undefined';
    // модалка QR из навбара: QR + строка профиля + кнопки управления
    openQrModal();
    for (let i = 0; i < 40; i++) {
      await new Promise(r2 => setTimeout(r2, 300));
      const w = document.getElementById('qr-canvas-wrap');
      if (w && !w.classList.contains('hidden') && document.getElementById('qr-canvas').width > 0) break;
    }
    const cv = document.getElementById('qr-canvas');
    const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height);
    const res = jsQR(d.data, cv.width, cv.height);
    out.qrText = res ? res.data : 'НЕ ЧИТАЕТСЯ';
    out.qrHasProf = await (async () => {
      const t = out.qrText;
      if (t.indexOf('NXQ1.') === 0) { // прямой код: профиль лежит внутри сжатого снимка
        try { const j = JSON.parse(await qrxInflate(qrxB64d(t.slice(5)))); return !!(j && j.prof); } catch (e) { return false; }
      }
      if (t.indexOf('NXR1.') === 0) return true; // облачный ключ: снимок с профилем лежит в облаке
      return /[?&]prof=[A-Z0-9]{4,12}/.test(t);
    })();
    out.profRow = (document.getElementById('qr-prof-row') || {}).textContent || '';
    out.buttons = ['profEnterCode', 'profCopyLink', 'profSyncNowBtn', 'profUnlink'].map(fn => fn + '=' + (typeof window[fn] === 'function'));
    out.code = profCode();
    return out;
  });
  console.log('блок синхронизации удалён из Студии :', r.studioBlockGone);
  console.log('мёртвая проф-QR-модалка удалена      :', r.profQrModalGone);
  console.log('QR из навбара содержит ?prof=        :', r.qrHasProf, '|', r.qrText.slice(0, 64));
  console.log('строка профиля в модалке             :', r.profRow.replace(/\s+/g, ' ').trim());
  console.log('кнопки управления                    :', r.buttons.join(' '));
  console.log('код профиля                          :', r.code);
  await page.evaluate(() => { const m = document.getElementById('modal-qr'); const card = m.querySelector('.relative') || m.firstElementChild; window.__shot = card; });
  const card = await page.evaluateHandle(() => window.__shot);
  await card.asElement().screenshot({ path: 'tools/shots/b372-qr-modal-profile.png' });
  console.log('ошибки страницы:', errs.length ? errs.slice(0, 4) : 'нет');
  const ok = r.studioBlockGone && r.profQrModalGone && r.qrHasProf && /код/.test(r.profRow) && r.buttons.every(b => b.endsWith('true')) && errs.length === 0;
  console.log(ok ? '\n✓ b372: управление профилем живёт в модалке QR, Студия чистая' : '\n✗ расхождение');
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
