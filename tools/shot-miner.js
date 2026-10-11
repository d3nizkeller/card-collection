/* b380: скриншот панели «Котик-шахтёр» на заданном уровне кирки и балансе.
   Запуск: python3 -m http.server 8123 &
           node tools/shot-miner.js <lvl> <coins> <out.png> */
const PW = process.env.PW_PATH || '/tmp/pw/node_modules/playwright-core';
const { chromium, devices } = require(PW);

const LVL = Number(process.argv[2] || 1);
const COINS = Number(process.argv[3] || 0);
const OUT = process.argv[4] || '/tmp/shots-b380/miner.png';

(async () => {
    const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
    const ctx = await browser.newContext({ ...devices['iPhone 12'], deviceScaleFactor: 2 });
    await ctx.addInitScript(([lvl, coins]) => {
        try {
            localStorage.setItem('nexus_miner', JSON.stringify({ lvl: lvl, mined: 0, last: Date.now() }));
            localStorage.setItem('nexus_coins', String(coins));
            localStorage.setItem('ui_prefs_v1', JSON.stringify({ section: 1 }));
        } catch (e) {}
    }, [LVL, COINS]);
    for (const p of ['https://textdb.dev/**', 'https://api.ipify.org/**', 'https://api64.ipify.org/**'])
        await ctx.route(p, r => r.fulfill({ status: 200, contentType: 'application/json', body: 'null' }));
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', e => errs.push(String(e.message).slice(0, 160)));
    await page.goto('http://127.0.0.1:8123/index.html', { waitUntil: 'load', timeout: 60000 });
    await page.waitForTimeout(2500);
    await page.evaluate(() => {
        ['modal-daily', 'modal-name'].forEach(id => { const m = document.getElementById(id); if (m) m.classList.add('hidden'); });
        try { const t = document.getElementById('name-remind-toast'); if (t) t.remove(); } catch (e) {}
        try { switchTab('battle'); } catch (e) {}
        try { setBattleMode('miner'); } catch (e) {}
    });
    await page.waitForTimeout(1200);
    await page.evaluate(() => {
        const b = document.getElementById('miner-cat-box');
        if (b) b.scrollIntoView({ block: 'center' });
    });
    await page.waitForTimeout(2500);
    const info = await page.evaluate(() => {
        const st = document.getElementById('miner-cat-stage');
        const vis = id => { const e = document.getElementById(id); return !!e && e.style.display !== 'none' && getComputedStyle(e).display !== 'none'; };
        return {
            cls: st ? st.className : '',
            tier: st ? st.getAttribute('data-tier') : null,
            rock: [0, 1, 2, 3].filter(i => vis('kc-rock-' + i)),
            den: [0, 1, 2, 3].filter(i => vis('kc-den-' + i)),
            pick: vis('kc-pick'), chips: vis('kc-chips'),
            badge: (document.getElementById('miner-cat-state') || {}).textContent,
            bubble: (document.getElementById('kc-bubble') || {}).textContent,
        };
    });
    await page.evaluate(() => { try { window.nameRemindToast = () => {}; } catch (e) {}
        const t = document.getElementById('name-remind-toast'); if (t) t.remove(); });
    await page.waitForTimeout(300);
    const box = await page.$('#miner-cat-box');
    if (box) await box.screenshot({ path: OUT });
    console.log('lvl', LVL, 'coins', COINS);
    console.log('класс сцены:', info.cls, '| tier:', info.tier);
    console.log('видимы rock:', info.rock, 'den:', info.den, '| кирка:', info.pick, 'щепа:', info.chips);
    console.log('бейдж:', info.badge, '| реплика:', info.bubble);
    console.log('pageErrors:', errs.length, errs.slice(0, 3));
    await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(2); });
