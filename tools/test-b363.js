/* b363: группировка «один IP = один пользователь» + определение устройств.
   Сеем фейковые записи реестра и смотрим, что рисует панель.
   Запуск: node tools/test-b363.js [url] (нужен python3 -m http.server в корне) */
const PW = process.env.PW_PATH || '/tmp/pw/node_modules/playwright-core';
const { chromium } = require(PW);
const URL = process.argv[2] || 'http://127.0.0.1:8123/index.html';
const CHROME = process.env.CHROME_PATH || '/tmp/.cache/ms-playwright/chromium-1134/chrome-linux/chrome';

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  const errs = [];
  page.on('pageerror', e => errs.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 140)); });
  await page.goto(URL, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(4000);

  const seed = await page.evaluate(() => {
    window.cloudGuest = () => false; // локально мы «создатель»: нужны рабочие кнопки
    window.jpSyncNow = () => {};     // глушим мердж продакшн-реестра: снимаем чистый пример
    window.jpSyncSoon = () => {};
    const now = Date.now();
    const rec = (cid, n, bal, ip, dev, did, ago, extra) => Object.assign({
      cid, n, bal, op: 12, jp: 1, fed: 500, won: 0, at: now - ago, pk: {}, alb: {}, ip, dev, did,
    }, extra || {});
    siteStats.p = {};
    siteStats.p['pHONE1aaa'] = rec('pHONE1aaa', 'Денис Keller', 43588, '95.214.22.7', 'Android 14 · Chrome · телефон · 393×851@2.75x · 8 яд., 4 ГБ', 'dvphone1', 60000);
    siteStats.p['pTAB2bbb'] = rec('pTAB2bbb', 'Денис Keller', 810, '95.214.22.7', 'iPadOS 17.5 · Safari · планшет · 820×1180@2x · 8 яд., 4 ГБ', 'dvtab2', 300000);
    siteStats.p['pPC3ccc'] = rec('pPC3ccc', 'Денис Keller', 692, '77.88.99.1', 'Windows 10/11 · Chrome · ПК · 1920×1080@1x · 16 яд., 16 ГБ', 'dvpc3', 90000);
    siteStats.p['pOLD4ddd'] = rec('pOLD4ddd', 'An', 304, '', '', '', 86400000); // старый клиент: ни IP, ни устройства
    siteStats.b = {}; siteStats.z = {};
    window.__nxStatsSig = '';
    statsRender();
    return {
      groupBtn: (document.getElementById('nx-groupip-btn') || {}).innerHTML || 'НЕТ КНОПКИ',
      usersChip: Array.from(document.querySelectorAll('#stats-summary p')).map(p => p.textContent).filter(t => t.indexOf('Пользователей') >= 0)[0] || '?',
      cards: Array.from(document.querySelectorAll('#stats-users > div')).map(d => {
        const head = d.querySelector('div > span');
        return {
          head: (head ? head.textContent : '').trim(),
          badges: Array.from(d.querySelectorAll('span.inline-flex')).slice(0, 12).map(b => b.textContent.trim()),
          details: !!d.querySelector('details'),
          memberRows: d.querySelectorAll('details > div').length,
        };
      }),
    };
  });

  console.log('кнопка группировки:', seed.groupBtn.replace(/<[^>]+>/g, ''));
  console.log('чип сводки        :', seed.usersChip);
  console.log('карточек в панели :', seed.cards.length);
  seed.cards.forEach((c, i) => {
    console.log(`  [${i + 1}] ${c.head}`);
    console.log('      бейджи:', c.badges.join(' | '));
    console.log('      устройств внутри:', c.memberRows, '| раскрывающийся список:', c.details);
  });

  // раскрываем первую группу и смотрим устройства
  const members = await page.evaluate(() => {
    const d = document.querySelector('#stats-users details');
    if (!d) return null;
    d.open = true;
    return Array.from(d.querySelectorAll('div.rounded-lg')).map(r => r.textContent.replace(/\s+/g, ' ').trim().slice(0, 160));
  });
  console.log('\nустройства внутри группы №1:');
  (members || []).forEach(m => console.log('   •', m));

  // групповое обнуление: два клика по кнопке «Обнулить все» (подтверждение)
  const zero = await page.evaluate(async () => {
    const btn = Array.from(document.querySelectorAll('#stats-users button')).find(b => (b.getAttribute('onclick') || '').indexOf('statsZeroGroup') >= 0);
    if (!btn) return 'нет кнопки statsZeroGroup';
    btn.click(); btn.click();
    await new Promise(r => setTimeout(r, 300));
    return { z: Object.keys(siteStats.z).sort(), balances: Object.keys(siteStats.p).map(k => k + ':' + siteStats.p[k].bal) };
  });
  console.log('\nпосле «Обнулить все» по группе с одним IP:', JSON.stringify(zero));

  // toggle выключает группировку
  const off = await page.evaluate(() => {
    nxToggleGroupIp();
    return {
      btn: (document.getElementById('nx-groupip-btn') || {}).textContent,
      cards: document.querySelectorAll('#stats-users > div').length,
    };
  });
  console.log('после выключения группировки:', off.btn, '| карточек:', off.cards);
  await page.evaluate(() => nxToggleGroupIp());

  // своя запись: устройство и ID опубликованы?
  const self = await page.evaluate(async () => {
    siteStatsSelfUpdate();
    await new Promise(r => setTimeout(r, 2500)); // даём фону дотянуть IP
    siteStatsSelfUpdate();
    const e = siteStats.p[JACKPOT_CID];
    return { dev: e.dev, did: e.did, ip: e.ip || '(ещё не пришёл)' };
  });
  console.log('\nсвоя запись в реестре:', JSON.stringify(self, null, 1));

  console.log('\nошибки страницы:', errs.length ? errs.slice(0, 5) : 'нет');
  await page.evaluate(() => {
    try { document.getElementById('modal-daily').classList.add('hidden'); } catch (e) {}
    try { document.querySelectorAll('.fixed.inset-0').forEach(el => el.classList.add('hidden')); } catch (e) {}
    try { // показываем саму секцию статистики в Студии (без паролей комнаты)
      const tab = document.getElementById('tab-studio');
      if (tab) tab.classList.remove('hidden');
      document.querySelectorAll('#tab-studio .studio-sec').forEach(x => { x.hidden = true; x.classList.add('hidden'); });
      const sec = document.querySelector('#tab-studio .studio-sec[data-sec="stats"]') || document.querySelector('.studio-sec[data-sec="stats"]');
      if (sec) { sec.hidden = false; sec.classList.remove('hidden'); }
    } catch (e) {}
    window.__nxStatsSig = ''; statsRender();
    try { document.querySelectorAll('#stats-users details').forEach(d => { d.open = true; }); } catch (e) {}
  });
  await page.waitForTimeout(600);
  await page.waitForTimeout(400);
  const wrap = await page.evaluateHandle(() => document.getElementById('stats-users'));
  await wrap.asElement().screenshot({ path: 'tools/shots/b363-users-panel.png' });
  await browser.close();
})();
