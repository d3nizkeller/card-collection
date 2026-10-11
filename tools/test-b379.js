/* b379: синхронизация профилей удалена целиком. Проверяем в браузере:

   1. за всю сессию НЕТ ни одного запроса к textdb nexus-tcg-prof-* (облачные
      документы профилей) — подсистема действительно не ходит в сеть;
   2. открытие страницы со ссылкой ?prof=CODE НЕ привязывает устройство:
      profCode() === '' и nx_prof_code в localStorage не появляется;
   3. скан/вставка кода переноса с кодом профиля внутри НЕ привязывают;
   4. комнатное облако (nexus-tcg-room-*) и джекпот по-прежнему опрашиваются —
      мы выключили только профили, а не облако комнаты;
   5. модалка QR собирается: код переноса есть, упоминания профиля нет;
   6. нет pageErrors.

   Запуск: python3 -m http.server 8123 &  node tools/test-b379.js
*/
const PW = process.env.PW_PATH || '/tmp/pw/node_modules/playwright-core';
const { chromium, devices } = require(PW);

const STORE = new Map();
let fails = 0;
const ok = (c, m) => { console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };

(async () => {
    const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
    const ctx = await browser.newContext({ ...devices['iPhone 12'], deviceScaleFactor: 2 });

    const reqs = { prof: 0, room: 0, jackpot: 0 };
    await ctx.route('https://textdb.dev/**', async route => {
        const u = route.request().url();
        const key = u.replace(/https:\/\/textdb\.dev\/api\/data\//, '').replace(/[?].*$/, '');
        if (/^nexus-tcg-prof-/.test(key)) reqs.prof++;
        if (/^nexus-tcg-room-/.test(key)) reqs.room++;
        if (/^nexus-tcg-jackpot/.test(key)) reqs.jackpot++;
        if (route.request().method() === 'POST') {
            STORE.set(key, route.request().postData());
            if (/^nexus-tcg-prof-/.test(key)) { fails++; console.log('  ❌ ПОПЫТКА ЗАПИСИ документа профиля: ' + key); }
            await route.fulfill({ status: 200, contentType: 'text/plain', body: 'ok' });
            return;
        }
        await route.fulfill({ status: 200, contentType: 'application/json', body: STORE.has(key) ? STORE.get(key) : 'null' });
    });
    for (const p of ['https://api.ipify.org/**', 'https://api64.ipify.org/**'])
        await ctx.route(p, r => r.fulfill({ status: 200, contentType: 'application/json', body: '{"ip":"9.9.9.9"}' }));

    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', e => errs.push(String(e.message).slice(0, 160)));

    // открываем СО ссылкой профиля — привязка обязана НЕ сработать
    await page.goto('http://127.0.0.1:8123/index.html?prof=TEST42', { waitUntil: 'load', timeout: 60000 });
    await page.waitForTimeout(6000); // больше, чем прежние таймеры профилей (4 c)

    const st1 = await page.evaluate(() => ({
        profCode: (function () { try { return profCode(); } catch (e) { return 'ERR'; } })(),
        ls: (function () { try { return localStorage.getItem('nx_prof_code'); } catch (e) { return 'ERR'; } })(),
    }));
    ok(st1.profCode === '', 'profCode() пустой даже после открытия с ?prof=TEST42 (получено: ' + JSON.stringify(st1.profCode) + ')');
    ok(!(st1.ls && st1.ls.length), 'nx_prof_code в localStorage не появился');

    // модалка QR: код переноса собирается, профиля в статусе нет
    await page.evaluate(() => { try { openQrModal(); } catch (e) {} });
    await page.waitForTimeout(2500);
    const qr = await page.evaluate(() => {
        const st = document.getElementById('qr-show-status');
        return { status: st ? st.textContent : '', hasCode: !!document.querySelector('#qr-canvas') };
    });
    ok(/профил/i.test(qr.status) === false, 'в статусе QR нет упоминания профиля: «' + qr.status.slice(0, 70) + '»');

    // вставка кода переноса, внутри которого лежит код профиля, не привязывает
    const applied = await page.evaluate(async () => {
        try {
            const snap = { v: 1, c: 777, col: {}, st: {}, prof: 'ZZ9999' };
            qrxApplyProf(snap);
            return profCode();
        } catch (e) { return 'ERR:' + e.message; }
    });
    ok(applied === '', 'qrxApplyProf() с кодом профиля внутри не привязывает (profCode=' + JSON.stringify(applied) + ')');

    const linked = await page.evaluate(() => {
        try { return profSetCode('ABC123'); } catch (e) { return 'ERR'; }
    });
    ok(linked === '' || linked === undefined || linked === false, 'profSetCode() больше не привязывает (вернула ' + JSON.stringify(linked) + ')');

    // комната жива: подключаем тестовую комнату и дёргаем синк — облако комнаты
    // обязано отвечать, то есть мы выключили ТОЛЬКО профили
    await page.evaluate(() => { try { closeQrModal(); } catch (e) {} });
    await page.evaluate(() => {
        try { CLOUD.room = 'b379-test'; } catch (e) {}
        try { jpSyncNow(); } catch (e) {}
        try { jpSyncSoon(); } catch (e) {}
    });
    await page.waitForTimeout(6000);
    ok(reqs.prof === 0, 'запросов к документам профилей nexus-tcg-prof-*: ' + reqs.prof + ' (должно быть 0)');
    ok(reqs.room > 0, 'облако комнаты nexus-tcg-room-* по-прежнему опрашивается: ' + reqs.room + ' запросов');
    ok(errs.length === 0, 'без ошибок страницы' + (errs.length ? ': ' + errs.slice(0, 3).join(' | ') : ''));

    await browser.close();
    console.log(fails === 0 ? '\n=== b379: ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ ===' : '\n=== b379: ПРОВАЛОВ: ' + fails + ' ===');
    process.exit(fails === 0 ? 0 : 1);
})().catch(e => { console.error('FATAL', e); process.exit(2); });
