/* b378: скриншот модалки QR — проверка, что блок профиля-синхронизации убран.
   Запуск: python3 -m http.server 8123 &  node tools/shot-qr.js [out.png] */
const PW = process.env.PW_PATH || '/tmp/pw/node_modules/playwright-core';
const { chromium, devices } = require(PW);
const OUT = process.argv[2] || '/tmp/shots-b377/qr.png';

(async () => {
    const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
    const ctx = await browser.newContext({ ...devices['iPhone 12'], deviceScaleFactor: 2 });
    await ctx.route('https://textdb.dev/**', r => r.fulfill({ status: 200, contentType: 'application/json', body: 'null' }));
    await ctx.route('https://api.ipify.org/**', r => r.fulfill({ status: 200, contentType: 'application/json', body: '{"ip":"9.9.9.9"}' }));
    await ctx.route('https://api64.ipify.org/**', r => r.fulfill({ status: 200, contentType: 'application/json', body: '{"ip":"9.9.9.9"}' }));
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', e => errs.push(String(e.message).slice(0, 160)));
    await page.goto('http://127.0.0.1:8123/index.html', { waitUntil: 'load', timeout: 60000 });
    await page.waitForTimeout(2500);
    await page.evaluate(() => {
        ['modal-daily', 'modal-name'].forEach(id => { const m = document.getElementById(id); if (m) m.classList.add('hidden'); });
        try { openQrModal(); } catch (e) {}
    });
    await page.waitForTimeout(1800);
    const info = await page.evaluate(() => {
        const m = document.getElementById('modal-qr');
        const gone = ['qr-prof-row'].map(id => !!document.getElementById(id));
        const btns = Array.from(m.querySelectorAll('button')).map(b => (b.textContent || '').trim()).filter(Boolean);
        return { open: m && !m.classList.contains('hidden'), profRowExists: gone[0], buttons: btns };
    });
    await page.screenshot({ path: OUT });
    console.log('модалка открыта:', info.open);
    console.log('#qr-prof-row существует:', info.profRowExists, '(должно быть false)');
    console.log('кнопки модалки:', JSON.stringify(info.buttons));
    console.log('pageErrors:', errs.length, errs.slice(0, 3));
    await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(2); });
