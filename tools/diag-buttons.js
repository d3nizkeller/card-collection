/* b417: диагностика «кнопки зависают и невозможно играть» в headless Chromium.

   Открываем ЖИВОЙ сайт с контролируемым балансом и проверяем:
     A. баланс огромный (как у владельца в облаке) — кнопка «Крутить» живая?
     B. баланс НИЖЕ ставки (ставка 10m) — что видит игрок: disabled? opacity?
        даёт ли тап по кнопке хоть какую-то обратную связь? работают ли − / + ?
     C. баланс 0 — во всех ли играх кнопки мертвы и есть ли путь назад;
     D. авто-режим: крутит ли спины и останавливается ли корректно;
     E. копим pageerror/console.error на всём пути.

   Запуск:  node tools/diag-buttons.js
*/
const { chromium } = require(process.env.PW_PATH || '/tmp/pw/node_modules/playwright');

const URL = process.env.SITE_URL || 'https://d3nizkeller.github.io/card-collection/';

async function boot(browser, coins, bet) {
    const ctx = await browser.newContext({ viewport: { width: 412, height: 900 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push('pageerror: ' + String(e.message).slice(0, 200)));
    page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + String(m.text()).slice(0, 200)); });
    await page.addInitScript(c => {
        localStorage.setItem('nexus_coins', String(c.coins));
        localStorage.setItem('nexus_jackpot_cid', 'pdiag00000001');
    }, { coins });
    await page.goto(URL, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => typeof window.slotsSpin === 'function', null, { timeout: 30000 });
    await page.waitForTimeout(2500);
    // игра стартует не на вкладке игр — переключаемся на Слоты, иначе кнопка скрыта
    await page.evaluate(() => {
        try { switchTab('battle'); setBattleMode('slots'); } catch (e) {}
        // модалка ежедневного бонуса на первом входе перехватывает клики — закрываем
        try {
            ['modal-daily', 'modal-unboxing', 'modal-qr', 'modal-reset'].forEach(id => {
                const m = document.getElementById(id);
                if (m) m.classList.add('hidden');
            });
        } catch (e) {}
    });
    await page.waitForTimeout(600);
    if (bet) await page.evaluate(b => { slotsSetBet(b); renderSlotsUI(); }, bet);
    await page.waitForTimeout(300);
    return { ctx, page, errors };
}

const snap = page => page.evaluate(() => {
    const g = id => document.getElementById(id);
    const s = g('slots-spin');
    const cs = s ? getComputedStyle(s) : null;
    return {
        coins: state.coins, bet: slots.bet, spinning: slots.spinning,
        disabled: s ? s.disabled : null, opacity: cs ? cs.opacity : null,
        bg: cs ? cs.backgroundColor : null, text: s ? s.textContent.trim() : null,
        toasts: (g('toast-container') ? g('toast-container').children.length : 0),
    };
});

(async () => {
    const browser = await chromium.launch();

    // ---------- A. баланс как у владельца (24 трлн), ставка 10m ----------
    {
        const { ctx, page, errors } = await boot(browser, 24000000000000, 10000000);
        const before = await snap(page);
        await page.click('#slots-spin');
        await page.waitForTimeout(400);
        const during = await snap(page);
        await page.waitForFunction(() => !slots.spinning, null, { timeout: 15000 }).catch(() => {});
        const after = await snap(page);
        console.log('A. баланс 24t, ставка 10m');
        console.log('   до   :', JSON.stringify(before));
        console.log('   тап  : spinning=' + during.spinning + ' спинов=' + await page.evaluate(() => state.stats.slotsSpins || 0));
        console.log('   после:', JSON.stringify(after));
        console.log('   ошибки:', errors.length ? errors : 'нет');
        await page.screenshot({ path: '/tmp/shot-A.png', clip: { x: 0, y: 0, width: 412, height: 900 } });
        await ctx.close();
    }

    // ---------- B. баланс НИЖЕ ставки ----------
    {
        const { ctx, page, errors } = await boot(browser, 5000000, 10000000);
        const s0 = await snap(page);
        // тап по «мёртвой» кнопке: доходит ли хоть что-то до игрока?
        await page.click('#slots-spin', { force: true });
        await page.waitForTimeout(600);
        const s1 = await snap(page);
        // работают ли шаги ставки вниз?
        await page.click('button[onclick="stepBet(\'slots\',-1)"]');
        await page.waitForTimeout(300);
        const s2 = await snap(page);
        await page.click('button[onclick="stepBet(\'slots\',-1)"]');
        await page.waitForTimeout(300);
        const s3 = await snap(page);
        console.log('\nB. баланс 5m, ставка 10m');
        console.log('   старт        :', JSON.stringify(s0));
        console.log('   после тапа   :', JSON.stringify(s1), '← тостов ' + s1.toasts + ' (обратная связь?)');
        console.log('   шаг −        :', s2.bet, 'disabled=' + s2.disabled, 'opacity=' + s2.opacity);
        console.log('   ещё шаг −    :', s3.bet, 'disabled=' + s3.disabled, 'opacity=' + s3.opacity);
        console.log('   ошибки:', errors.length ? errors : 'нет');
        await page.screenshot({ path: '/tmp/shot-B.png', clip: { x: 0, y: 300, width: 412, height: 600 } });
        await ctx.close();
    }

    // ---------- C. баланс 0 ----------
    {
        const { ctx, page, errors } = await boot(browser, 0, null);
        const st = await page.evaluate(() => {
            const ids = ['slots-spin', 'grid-spin', 'wheel-spin', 'mines-start', 'lines-spin'];
            return ids.map(id => { const b = document.getElementById(id); return id + ':' + (b ? (b.disabled ? 'disabled' : 'live') : 'нет'); });
        });
        console.log('\nC. баланс 0 →', st.join('  '));
        const ways = await page.evaluate(() => ({
            miner: typeof window.minerCollect === 'function' || !!document.getElementById('miner-btn'),
            daily: !!document.getElementById('daily-list'),
        }));
        console.log('   пути заработка: ', JSON.stringify(ways));
        console.log('   ошибки:', errors.length ? errors : 'нет');
        await ctx.close();
    }

    // ---------- D. авто-режим ----------
    {
        const { ctx, page, errors } = await boot(browser, 500000000, 10000000);
        await page.evaluate(() => slotsToggleAuto());
        await page.waitForTimeout(6000);
        const spins1 = await page.evaluate(() => state.stats.slotsSpins || 0);
        await page.waitForTimeout(4000);
        const spins2 = await page.evaluate(() => state.stats.slotsSpins || 0);
        await page.evaluate(() => slotsToggleAuto());
        await page.waitForTimeout(2500);
        const spins3 = await page.evaluate(() => state.stats.slotsSpins || 0);
        await page.waitForTimeout(2500);
        const spins4 = await page.evaluate(() => state.stats.slotsSpins || 0);
        const fin = await snap(page);
        console.log('\nD. авто: спинов 6с=' + spins1 + ' 10с=' + spins2 + ' | после стопа: ' + spins3 + ' → ' + spins4 + ' (должно встать)');
        console.log('   итог:', JSON.stringify(fin));
        console.log('   ошибки:', errors.length ? errors : 'нет');
        await ctx.close();
    }

    await browser.close();
})();
