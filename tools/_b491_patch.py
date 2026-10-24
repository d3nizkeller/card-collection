#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b491: рулетка — баланс двигается на глазах и привязан к общему джекпоту.

Жалоба владельца: «чего с баланса не отнимается и не прибавляется и привяжи к
джекпоту».

Разбор
------
1. «Не отнимается». Фишки только ЛОЖИЛИСЬ на сукно: rouletteBet() проверял
   хватает ли монет, но ничего не списывал — деньги уходили из кошелька лишь в
   момент «Крутить». Плюс шапка сайта показывает баланс буквами (fmtCoins:
   1000 -> «1k», 1 234 567 -> «1.2m»), поэтому ставка 25 и выигрыш 900 не
   меняли картинку вообще: было «1k» и осталось «1k».
2. «Не прибавляется». Выигрыш начислялся (state.coins += pay), но по той же
   причине в шапке это было не видно, а точной цифры на столе не было нигде.
3. «Привяжи к джекпоту». Рулетка была единственной игрой вкладки «Игры»,
   которая не кормила общий банк сайта: jackpotFeed/jackpotOnLoss не
   вызывались, своего шанса на срыв банка у неё не было, а JPC_GAMES не знал
   про рулетку — в Студии не было её ползунка.

Лечение
-------
1. Фишка покупается из кошелька СРАЗУ (rouletteSpend): клик по клетке списывает
   достоинство фишки, «×2» докупает удвоение, «Сброс» возвращает всю сумму со
   стола обратно в баланс. Заблокированным игрокам ставки запрещены
   (statsBlockGuard), как в остальных играх.
2. Кошелёк стола: в лобби рулетки появилась панель .rl-wallet — баланс ТОЧНО до
   монеты (#rl-balance, nxCoinsExact с тонкими пробелами), сумма на столе,
   счётчики спинов/побед и шанс золотого зеро. Каждое движение денег
   показывает живой плюс/минус (#rl-delta, .rl-d-up/.rl-d-down) и «бамп» шапки
   (.nx-bump). Пока открыто лобби рулетки и баланс < 1 000 000, шапка сайта
   тоже показывает точную сумму вместо «1k» (updateCoinDisplay -> rlExactHdr).
3. Джекпот: JPC_GAMES += 'Roulette' (заводской шанс 2.7 % = 1 из 37, «золотое
   зеро»), в Студии появился ползунок и гарантия по спинам. Спин кормит банк
   jackpotFeed(стол), чистый проигрыш докидывает jackpotOnLoss(стол - выплата),
   а при срыве зеро становится золотым, колесо останавливается на нём и
   jackpotWin() выдаёт банк (тост, салют, зал славы, топ сайта — как везде).
   Банк джекпота теперь виден и в лобби рулетки (jp-banner с roulette-*).

Теги: nxmob234 -> nxmob235.

Проверка/применение:
    python3 tools/_b491_patch.py --check
    python3 tools/_b491_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob234'
TAG_NEW = 'nxmob235'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

# ---------------------------------------------------------------- app.js
# 1) шапка модуля рулетки
PAIRS.append(('assets/app.js', 1,
r'''        // ============ b488: РУЛЕТКА 2D (европейская, 0–36) ============
        // Ставки копятся кликами по клеткам стола (фишка = выбранное
        // достоинство), «Крутить» списывает сумму ставок с общего баланса,
        // колесо крутится и останавливает выигрышный сектор под указателем.
        // Выплаты: число ×36, дюжина ×3, равные шансы ×2.''',
r'''        // ============ b488: РУЛЕТКА 2D (европейская, 0–36) ============
        // Фишка покупается из кошелька СРАЗУ (b491): клик по клетке списывает
        // достоинство фишки с общего баланса, «×2» докупает удвоение, «Сброс»
        // возвращает всё со стола обратно. «Крутить» только кормит общий банк
        // джекпота и крутит колесо до выигрышного сектора под указателем.
        // Выплаты: число ×36, колонка/дюжина ×3, равные шансы ×2.
        // b491: рулетка привязана к общему джекпоту сайта — % ставки и % чистого
        // проигрыша кормят банк (jackpotFeed/jackpotOnLoss), а «золотое зеро»
        // (шанс и гарантия настраиваются в Студии, JPC_GAMES → 'Roulette')
        // срывает весь банк через jackpotWin().'''))

# 2) состояние
PAIRS.append(('assets/app.js', 1,
r'''        let rouletteBets = {};      // spotId -> сумма (живёт до перезагрузки: стол, не кошелёк)
        let rouletteChip = 5;
        let rouletteSpinning = false;
        let rouletteAngle = 0;      // текущий поворот колеса, градусы''',
r'''        let rouletteBets = {};      // spotId -> сумма; с b491 эти деньги УЖЕ списаны с баланса
        let rouletteChip = 5;
        let rouletteSpinning = false;
        let rouletteAngle = 0;      // текущий поворот колеса, градусы
        let rouletteGoldZero = false; // b491: зеро золотое — этот спин сорвал общий джекпот'''))

# 3) кошелёк стола: точные цифры, живой плюс/минус, покупка/возврат фишек
PAIRS.append(('assets/app.js', 1,
r'''        function rouletteSetChip(v) { rouletteChip = v; renderRoulette(); }
        function rouletteBet(spotId) {
            if (rouletteSpinning) return;
            const total = rouletteTotal();
            if (total + rouletteChip > state.coins) { showToast('Не хватает монет на ставку: нужно ' + (total + rouletteChip) + ', у вас ' + state.coins, 'error'); return; }
            rouletteBets[spotId] = (rouletteBets[spotId] || 0) + rouletteChip;
            renderRoulette();
        }
        function rouletteDouble() {
            if (rouletteSpinning) return;
            const total = rouletteTotal();
            if (!total) { showToast('Сначала поставьте фишки на стол', 'error'); return; }
            if (total * 2 > state.coins) { showToast('Не хватает монет на удвоение: нужно ' + (total * 2) + ', у вас ' + state.coins, 'error'); return; }
            for (const k in rouletteBets) rouletteBets[k] *= 2;
            renderRoulette();
        }
        function rouletteClear() {
            if (rouletteSpinning) return;
            rouletteBets = {};
            renderRoulette();
        }''',
r'''        function rouletteSetChip(v) { rouletteChip = v; renderRoulette(); }
        // ---- b491: кошелёк стола ----
        // fmtCoins() в шапке сайта округляет до букв (1000 -> «1k», 1234567 ->
        // «1.2m»), поэтому ставка 25 и выигрыш 900 выглядели как «баланс не
        // двигается». Здесь баланс показывается ТОЧНО, до монеты.
        function nxCoinsExact(n) {
            n = Math.floor(Number(n) || 0);
            const s = String(Math.abs(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '\u2009');
            return (n < 0 ? '−' : '') + s;
        }
        function rlLobbyOpen() {
            try {
                const lr = document.getElementById('lobby-roulette');
                const tb = document.getElementById('tab-battle');
                return !!(lr && tb && !lr.classList.contains('hidden') && !tb.classList.contains('hidden'));
            } catch (e) { return false; }
        }
        // в лобби рулетки шапка показывает точную сумму (пока она влезает в пилюлю)
        function rlExactHdr() { return rlLobbyOpen() && (Math.floor(Number(state.coins) || 0) < 1000000); }
        function rlSync() {
            const bal = document.getElementById('rl-balance');
            if (bal) { const t = nxCoinsExact(state.coins); if (bal.textContent !== t) bal.textContent = t; }
            const ts = document.getElementById('rl-table-sum');
            if (ts) { let t = '0'; try { t = nxCoinsExact(rouletteTotal()); } catch (e) {} if (ts.textContent !== t) ts.textContent = t; }
            const sp = document.getElementById('rl-spins');
            if (sp) { const t = String((state.stats && state.stats.rouletteSpins) || 0); if (sp.textContent !== t) sp.textContent = t; }
            const wn = document.getElementById('rl-wins');
            if (wn) { const t = String((state.stats && state.stats.rouletteWins) || 0); if (wn.textContent !== t) wn.textContent = t; }
            const jp = document.getElementById('rl-jp-odds');
            if (jp) {
                let t = 'золотое зеро: —';
                try { t = jpcOff() ? 'джекпот выключен в Студии' : ('золотое зеро: ' + jpcPhrase('odds-roulette')); } catch (e) {}
                if (jp.textContent !== t) jp.textContent = t;
            }
        }
        let rlFlashT = null;
        // живой «+900» / «−25» рядом с балансом и толчок пилюли в шапке
        function rlFlash(delta) {
            try { rlSync(); } catch (e) {}
            const d = Math.round(Number(delta) || 0);
            const el = document.getElementById('rl-delta');
            if (el && d) {
                el.textContent = (d > 0 ? '+' : '−') + nxCoinsExact(Math.abs(d));
                el.classList.remove('rl-d-go');
                void el.offsetWidth; // перезапуск анимации
                el.className = 'rl-delta ' + (d > 0 ? 'rl-d-up' : 'rl-d-down') + ' rl-d-go';
                clearTimeout(rlFlashT);
                rlFlashT = setTimeout(() => { try { el.classList.remove('rl-d-go'); } catch (e) {} }, 1500);
            }
            try {
                const cb = document.getElementById('coin-balance');
                const pill = cb && cb.parentElement;
                if (pill && d) {
                    pill.classList.remove('nx-bump');
                    void pill.offsetWidth;
                    pill.classList.add('nx-bump');
                    setTimeout(() => { try { pill.classList.remove('nx-bump'); } catch (e) {} }, 600);
                }
            } catch (e) {}
        }
        // покупка фишки из кошелька: деньги уходят СРАЗУ, как на настоящем столе
        function rouletteSpend(n, what) {
            n = Math.round(Number(n) || 0);
            if (n <= 0) return false;
            if ((Math.floor(Number(state.coins) || 0)) < n) {
                showToast('Не хватает монет: ' + what + ' — ' + fmtCoins(n) + ', у вас ' + fmtCoins(state.coins) + nxLackNote(n), 'error');
                return false;
            }
            state.coins -= n;
            saveState(); updateCoinDisplay();
            rlFlash(-n);
            try { SoundFX.play('coin'); } catch (e) {}
            return true;
        }
        // возврат фишек со стола в кошелёк («Сброс»)
        function rouletteRefund(n) {
            n = Math.round(Number(n) || 0);
            if (n <= 0) return;
            state.coins += n;
            saveState(); updateCoinDisplay();
            rlFlash(n);
        }
        function rouletteBet(spotId) {
            if (rouletteSpinning) return;
            if (statsBlockGuard('ставки в рулетке')) return; // b277: заблокированным ставки запрещены
            // b491: фишка списывается с баланса в момент клика по клетке
            if (!rouletteSpend(rouletteChip, 'фишка ' + rouletteChip)) return;
            rouletteBets[spotId] = (rouletteBets[spotId] || 0) + rouletteChip;
            renderRoulette();
        }
        function rouletteDouble() {
            if (rouletteSpinning) return;
            const total = rouletteTotal();
            if (!total) { showToast('Сначала поставьте фишки на стол', 'error'); return; }
            // b491: удвоение докупается из кошелька — на столе становится вдвое больше
            if (!rouletteSpend(total, 'удвоение ставок')) return;
            for (const k in rouletteBets) rouletteBets[k] *= 2;
            renderRoulette();
        }
        function rouletteClear() {
            if (rouletteSpinning) return;
            const total = rouletteTotal();
            rouletteBets = {};
            // b491: всё, что лежало на сукне, возвращается в баланс
            if (total > 0) {
                rouletteRefund(total);
                showToast('↩ Фишки со стола возвращены в баланс: +' + fmtCoins(total), 'info');
            }
            renderRoulette();
        }
        // ---- b491: золотое зеро = срыв общего джекпота сайта ----
        function rouletteJpArmed() {
            try { return !jpcOff() && jpcSpinPct('Roulette') > 0; } catch (e) { return false; }
        }
        function rouletteJpRoll() {
            try {
                if (jpcOff()) return false;
                const p = jpcSpinPct('Roulette');   // базовый шанс из Студии или 100 % по гарантии
                return p > 0 && Math.random() * 100 < p;
            } catch (e) { return false; }
        }'''))

# 4) спин: деньги уже списаны, банк кормится, золотое зеро срывает джекпот
PAIRS.append(('assets/app.js', 1,
r'''        function rouletteSpin() {
            if (rouletteSpinning) return;
            const total = rouletteTotal();
            if (!total) { showToast('Сначала поставьте фишки на стол', 'error'); return; }
            if (total > state.coins) { showToast('Не хватает монет: ставок на ' + total + ', у вас ' + state.coins, 'error'); return; }
            rouletteSpinning = true;
            state.coins -= total;
            updateCoinDisplay();
            saveState();
            const win = Math.floor(Math.random() * 37);
            const defs = rouletteSpotDefs();
            let pay = 0;
            defs.forEach(d => { if (rouletteBets[d.id] && d.hit(win)) pay += rouletteBets[d.id] * d.pay; });
            rouletteAnimate(win, () => {
                rouletteSpinning = false;
                if (pay > 0) {
                    state.coins += pay;
                    updateCoinDisplay();
                }
                const rs = rouletteState();
                rs.hist = (rs.hist || []).concat([win]).slice(-12);
                rouletteBets = {};
                saveState();
                renderRoulette();
                const col = rouletteColor(win);
                const colRu = col === 'red' ? 'красное' : (col === 'black' ? 'чёрное' : 'зеро');
                if (pay > 0) showToast('🎯 Выпало ' + win + ' (' + colRu + '): выигрыш +' + pay + ' монет', 'success');
                else showToast('🎯 Выпало ' + win + ' (' + colRu + '): ставки сгорели (−' + total + ')', 'error');
                if (pay >= total * 10) { try { launchConfetti(80); } catch (e) {} }
            });
        }''',
r'''        function rouletteSpin() {
            if (rouletteSpinning) return;
            const total = rouletteTotal();
            if (!total) { showToast('Сначала поставьте фишки на стол', 'error'); return; }
            if (statsBlockGuard('рулетка')) return; // b277
            rouletteSpinning = true;
            // b491: монеты УЖЕ списаны при постановке фишек — здесь только банк игры
            try { jackpotFeed(total); } catch (e) {} // % ставки кормит общий джекпот сайта
            state.stats.rouletteSpins = (state.stats.rouletteSpins || 0) + 1;
            saveState();
            // b491: золотое зеро — шанс сорвать общий банк (настройки в Студии)
            const jpHit = rouletteJpRoll();
            const win = jpHit ? 0 : Math.floor(Math.random() * 37);
            const defs = rouletteSpotDefs();
            let pay = 0;
            defs.forEach(d => { if (rouletteBets[d.id] && d.hit(win)) pay += rouletteBets[d.id] * d.pay; });
            try { SoundFX.play('whoosh'); } catch (e) {}
            rouletteAnimate(win, () => {
                rouletteSpinning = false;
                rouletteGoldZero = jpHit; // b491: зеро золотое — видно на колесе после остановки
                if (pay > 0) {
                    state.coins += pay;
                    rlFlash(pay);
                    updateCoinDisplay();
                }
                let prize = 0;
                try { jpcPityNote('Roulette', jpHit); } catch (e) {} // b414: счётчик гарантии
                if (jpHit) {
                    // jackpotWin() сама начисляет монеты, пишет зал славы и показывает тост
                    try { prize = jackpotWin() || 0; } catch (e) {}
                } else if (pay < total) {
                    try { jackpotOnLoss(total - pay); } catch (e) {} // чистый проигрыш докидывает банк
                }
                const got = pay + prize;
                if (got > 0) {
                    state.stats.rouletteWins = (state.stats.rouletteWins || 0) + 1;
                    if (got > (state.stats.rouletteBest || 0)) state.stats.rouletteBest = got;
                }
                const rs = rouletteState();
                rs.hist = (rs.hist || []).concat([win]).slice(-12);
                rouletteBets = {};
                saveState();
                renderRoulette();
                updateCoinDisplay();
                try { rouletteDraw(); } catch (e) {} // b491: зеро красится золотом (или гаснет)
                const col = rouletteColor(win);
                const colRu = col === 'red' ? 'красное' : (col === 'black' ? 'чёрное' : 'зеро');
                if (jpHit) showToast('🎯 Выпало ' + win + ' (' + colRu + ') — ЗОЛОТОЕ ЗЕРО: банк сайта ваш' + (pay > 0 ? ', плюс +' + fmtCoins(pay) + ' со стола' : ''), 'success');
                else if (pay > 0) showToast('🎯 Выпало ' + win + ' (' + colRu + '): выигрыш +' + fmtCoins(pay) + ' монет', 'success');
                else showToast('🎯 Выпало ' + win + ' (' + colRu + '): ставки сгорели (−' + fmtCoins(total) + '), банк джекпота стал больше', 'error');
                if (!jpHit && pay >= total * 10) { try { launchConfetti(80); } catch (e) {} }
            });
        }'''))

# 5) колесо: золотое зеро
PAIRS.append(('assets/app.js', 1,
r'''            const sector = Math.PI * 2 / 37;
            for (let i = 0; i < 37; i++) {
                const n = ROULETTE_ORDER[i];''',
r'''            const sector = Math.PI * 2 / 37;
            const jpArm = rouletteJpArmed(); // b491: пока джекпот включён, зеро обведено золотом
            for (let i = 0; i < 37; i++) {
                const n = ROULETTE_ORDER[i];'''))

PAIRS.append(('assets/app.js', 1,
r'''                g.fillStyle = n === 0 ? '#059669' : (ROULETTE_REDS.indexOf(n) >= 0 ? '#c81e3f' : '#111827');
                g.fill();
                g.strokeStyle = 'rgba(251,191,36,.35)';
                g.lineWidth = 0.8;
                g.stroke();''',
r'''                // b491: золотое зеро — этот спин срывает общий джекпот сайта
                if (n === 0 && rouletteGoldZero) {
                    const gz = g.createRadialGradient(0, 0, RS * 0.15, 0, 0, RS);
                    gz.addColorStop(0, '#fef3c7'); gz.addColorStop(0.55, '#f59e0b'); gz.addColorStop(1, '#92400e');
                    g.fillStyle = gz;
                } else {
                    g.fillStyle = n === 0 ? '#059669' : (ROULETTE_REDS.indexOf(n) >= 0 ? '#c81e3f' : '#111827');
                }
                g.fill();
                g.strokeStyle = (n === 0 && jpArm) ? 'rgba(253,224,71,.95)' : 'rgba(251,191,36,.35)';
                g.lineWidth = (n === 0 && jpArm) ? 1.8 : 0.8;
                g.stroke();'''))

# 6) панель стола: точная сумма, подсказка про джекпот, синхронизация кошелька
PAIRS.append(('assets/app.js', 1,
r'''                    <span class="ml-auto text-[11px] text-slate-300">На столе: <b class="text-amber-300">${total}</b></span>''',
r'''                    <span class="ml-auto text-[11px] text-slate-300">На столе: <b class="text-amber-300">${nxCoinsExact(total)}</b></span>'''))

PAIRS.append(('assets/app.js', 1,
r'''                    ${hist.length ? hist.map(n => `<span class="rl-histn ${n === 0 ? 'rl-hist-zero' : (ROULETTE_REDS.indexOf(n) >= 0 ? 'rl-hist-red' : 'rl-hist-black')}">${n}</span>`).join('') : '<span class="text-[10px] text-slate-600">пока пусто</span>'}
                </div>`;
        }
        // ============ /b488 рулетка ============''',
r'''                    ${hist.length ? hist.map(n => `<span class="rl-histn ${n === 0 ? 'rl-hist-zero' : (ROULETTE_REDS.indexOf(n) >= 0 ? 'rl-hist-red' : 'rl-hist-black')}">${n}</span>`).join('') : '<span class="text-[10px] text-slate-600">пока пусто</span>'}
                </div>
                <p class="rl-jp-note"><i class="fa-solid fa-crown"></i>Фишки списываются с баланса сразу, «Сброс» возвращает их обратно. Золотое зеро срывает общий джекпот сайта — <b data-jpc="odds-roulette">шанс из Студии</b>; <b data-jpc="feed">100%</b> ставки и <b data-jpc="loss">100%</b> проигрыша кормят банк.</p>`;
            rlSync();                              // b491: кошелёк стола живёт вне этой разметки
            try { jpcLabelsRender(); } catch (e) {} // b491: проценты и шанс — из настроек Студии
        }
        // ============ /b488 рулетка ============'''))

# 7) шапка сайта: точный баланс, пока открыта рулетка
PAIRS.append(('assets/app.js', 1,
r'''        function updateCoinDisplay() {
            // b373: счётчик монет перезаписывался каждую секунду даже без изменений
            const s = fmtCoins(state.coins);
            const cb = document.getElementById('coin-balance');
            if (cb && cb.innerText !== s) cb.innerText = s;
            const sc = document.getElementById('store-stat-coins');
            if (sc && sc.textContent !== s) sc.textContent = s;
            renderMiner(); // b47: баланс виден и в шахте
        }''',
r'''        function updateCoinDisplay() {
            // b373: счётчик монет перезаписывался каждую секунду даже без изменений
            // b491: в лобби рулетки шапка показывает баланс ТОЧНО (до монеты):
            // fmtCoins() округляет до букв, и ставка 25 / выигрыш 900 не меняли
            // «1k» — владелец видел это как «баланс не двигается».
            let s = fmtCoins(state.coins);
            try { if (rlExactHdr()) s = nxCoinsExact(state.coins); } catch (e) {}
            const cb = document.getElementById('coin-balance');
            if (cb && cb.innerText !== s) cb.innerText = s;
            const sc = document.getElementById('store-stat-coins');
            if (sc && sc.textContent !== s) sc.textContent = s;
            try { rlSync(); } catch (e) {} // b491: кошелёк стола рулетки
            renderMiner(); // b47: баланс виден и в шахте
        }'''))

# 8) настройки джекпота: рулетка — пятая игра
PAIRS.append(('assets/app.js', 1,
r'''        const JPC_GAMES = ['Slots', 'Grid', 'Lines', 'Wheel'];
        const JPC_GAME_RU = { Slots: 'Слоты', Grid: 'Сетка', Lines: 'Линии', Wheel: 'Колесо' };
        const JPC_GAME_UNIT = { Slots: 'на барабан', Grid: 'на ячейку', Lines: 'на ячейку', Wheel: 'на сектор' };''',
r'''        const JPC_GAMES = ['Slots', 'Grid', 'Lines', 'Wheel', 'Roulette']; // b491: рулетка тоже кормит банк
        const JPC_GAME_RU = { Slots: 'Слоты', Grid: 'Сетка', Lines: 'Линии', Wheel: 'Колесо', Roulette: 'Рулетка' };
        const JPC_GAME_UNIT = { Slots: 'на барабан', Grid: 'на ячейку', Lines: 'на ячейку', Wheel: 'на сектор', Roulette: 'золотое зеро' };'''))

PAIRS.append(('assets/app.js', 1,
r'''        //   Линии  1 / 25        = 4.00 %   Колесо 1 / 16        = 6.25 %
        const JPC_DEFAULT_P = { Slots: 5.66, Grid: 3.85, Lines: 4, Wheel: 6.25 };''',
r'''        //   Линии  1 / 25        = 4.00 %   Колесо 1 / 16        = 6.25 %
        // b491: Рулетка 1 / 37     = 2.70 %  — золотое зеро (ровно шанс зеро на столе)
        const JPC_DEFAULT_P = { Slots: 5.66, Grid: 3.85, Lines: 4, Wheel: 6.25, Roulette: 2.7 };'''))

PAIRS.append(('assets/app.js', 1,
r'''            pSlots: JPC_DEFAULT_P.Slots, pGrid: JPC_DEFAULT_P.Grid,
            pLines: JPC_DEFAULT_P.Lines, pWheel: JPC_DEFAULT_P.Wheel,
            pitySlots: 0, pityGrid: 0, pityLines: 0, pityWheel: 0, // гарантия: 0 = выкл''',
r'''            pSlots: JPC_DEFAULT_P.Slots, pGrid: JPC_DEFAULT_P.Grid,
            pLines: JPC_DEFAULT_P.Lines, pWheel: JPC_DEFAULT_P.Wheel,
            pRoulette: JPC_DEFAULT_P.Roulette, // b491
            pitySlots: 0, pityGrid: 0, pityLines: 0, pityWheel: 0, pityRoulette: 0, // гарантия: 0 = выкл'''))

# 9) фраза про шанс золотого зеро
PAIRS.append(('assets/app.js', 1,
r'''                case 'odds-wheel': {
                    if (jpcOff()) return 'не выпадает';
                    const pp = jpcP('Wheel');
                    if (pp >= 100) return 'каждый спин';
                    if (pp <= 0) return 'не выпадает';
                    const n = 100 / pp;
                    return '1 из ' + (n >= 100 ? Math.round(n).toLocaleString('ru-RU') : (Math.round(n * 10) / 10)) + ' спинов';
                }
            }
            return '';
        }
        const JPC_LABEL_KEYS = ['feed', 'loss', 'pay', 'pay2', 'pay2v', 'pay3', 'paynum', 'odds-wheel'];''',
r'''                case 'odds-wheel': {
                    if (jpcOff()) return 'не выпадает';
                    const pp = jpcP('Wheel');
                    if (pp >= 100) return 'каждый спин';
                    if (pp <= 0) return 'не выпадает';
                    const n = 100 / pp;
                    return '1 из ' + (n >= 100 ? Math.round(n).toLocaleString('ru-RU') : (Math.round(n * 10) / 10)) + ' спинов';
                }
                // b491: шанс золотого зеро в рулетке
                case 'odds-roulette': {
                    if (jpcOff()) return 'не выпадает';
                    const pr = jpcP('Roulette');
                    if (pr >= 100) return 'каждый спин';
                    if (pr <= 0) return 'не выпадает';
                    const nr = 100 / pr;
                    return '1 из ' + (nr >= 100 ? Math.round(nr).toLocaleString('ru-RU') : (Math.round(nr * 10) / 10)) + ' спинов';
                }
            }
            return '';
        }
        const JPC_LABEL_KEYS = ['feed', 'loss', 'pay', 'pay2', 'pay2v', 'pay3', 'paynum', 'odds-wheel', 'odds-roulette'];'''))

# 10) банк джекпота в лобби рулетки
PAIRS.append(('assets/app.js', 1,
r'''            const lv = document.getElementById('lines-jp-top-list');
            nxSetHtml(lv, html);   // b468
            try { jpcLabelsRender(); } catch (e) {} // b415: надписи о процентах — вслед за настройками''',
r'''            const lv = document.getElementById('lines-jp-top-list');
            nxSetHtml(lv, html);   // b468
            // b491: тот же банк виден в лобби рулетки (золотое зеро срывает его)
            const rv = document.getElementById('roulette-jackpot');
            if (rv) rv.textContent = fmtCoins(pool);
            const rn = document.getElementById('roulette-jackpot-note');
            if (rn) rn.textContent = note;
            const rw = document.getElementById('roulette-jp-winner');
            if (rw) { rw.textContent = wtxt; rw.title = wtitle; }
            nxSetHtml(document.getElementById('roulette-jp-top-list'), html); // b468
            try { rlSync(); } catch (e) {} // b491: шанс золотого зеро — из настроек
            try { jpcLabelsRender(); } catch (e) {} // b415: надписи о процентах — вслед за настройками'''))

# 11) вход в режим: банк и кошелёк сразу живые
PAIRS.append(('assets/app.js', 1,
r'''            if (m === 'roulette') { renderRoulette(); rouletteDraw(); } // b488''',
r'''            if (m === 'roulette') { renderRoulette(); rouletteDraw(); try { jackpotRender(); } catch (e) {} updateCoinDisplay(); } // b488; b491: банк джекпота и точный баланс сразу'''))

# 12) статистика рулетки
PAIRS.append(('assets/app.js', 1,
r'''            durakWins: 0, durakLosses: 0, durakStreak: 0, bestDurakStreak: 0
        };''',
r'''            durakWins: 0, durakLosses: 0, durakStreak: 0, bestDurakStreak: 0,
            rouletteSpins: 0, rouletteWins: 0, rouletteBest: 0 // b491: статистика рулетки
        };'''))

# ---------------------------------------------------------------- index.html
PAIRS.append(('index.html', 1,
r'''                                <p class="text-sm text-slate-400 mt-1">Европейская (0–36): выберите фишку, кликните по клеткам стола и крутите. Число ×36, дюжина ×3, равные шансы ×2. Ставки списываются с баланса.</p>
                            </div>
                        </div>
                        <div class="flex flex-col lg:flex-row gap-4 items-start mt-4">
                            <div class="relative shrink-0 mx-auto rl-wheelhouse"><!-- b489: дом колеса с тенью-свечением -->
                                <canvas id="roulette-wheel" width="420" height="420" class="block max-w-full"></canvas>
                            </div>
                            <div id="roulette-table" class="min-w-0 w-full"></div>
                        </div>
                    </div>''',
r'''                                <p class="text-sm text-slate-400 mt-1">Европейская (0–36): выберите фишку и кликните по клеткам стола — фишки <b class="text-amber-200">сразу списываются с баланса</b>, «Сброс» возвращает их обратно. Число ×36, колонка и дюжина ×3, равные шансы ×2. Золотое зеро срывает общий джекпот сайта.</p>
                            </div>
                            <!-- b491: кошелёк стола — баланс точно до монеты, сумма на столе, живой плюс/минус -->
                            <div class="rl-wallet shrink-0">
                                <p class="rl-w-cap"><i class="fa-solid fa-wallet"></i>Кошелёк стола</p>
                                <p class="rl-w-bal"><span id="rl-balance">0</span><i id="rl-delta" class="rl-delta"></i></p>
                                <p class="rl-w-rows"><span>На столе</span><b id="rl-table-sum">0</b></p>
                                <p class="rl-w-rows"><span>Спинов / побед</span><b><span id="rl-spins">0</span> / <span id="rl-wins">0</span></b></p>
                                <p class="rl-w-jp"><i class="fa-solid fa-crown"></i><span id="rl-jp-odds">золотое зеро: —</span></p>
                            </div>
                        </div>
                        <div class="flex flex-col lg:flex-row gap-4 items-start mt-4">
                            <div class="relative shrink-0 mx-auto rl-wheelhouse"><!-- b489: дом колеса с тенью-свечением -->
                                <canvas id="roulette-wheel" width="420" height="420" class="block max-w-full"></canvas>
                            </div>
                            <div id="roulette-table" class="min-w-0 w-full"></div>
                        </div>
                        <!-- b491: банк джекпота в лобби рулетки -->
                        <div class="jp-banner mt-4">
                            <div class="jp-shine" aria-hidden="true"></div>
                            <div class="jp-flex">
                            <div class="jp-main">
                            <div class="jp-head">
                                <span class="jp-label"><i class="fa-solid fa-crown"></i>Джекпот сайта</span>
                                <span id="roulette-jackpot" class="jp-value">0</span>
                            </div>
                            <p class="jp-desc">золотое зеро (0) срывает <b data-jpc="pay">весь банк ваш</b>; банк кормят <b data-jpc="feed">100%</b> каждой ставки на столе и <b data-jpc="loss">100%</b> чистого проигрыша — шанс: <b data-jpc="odds-roulette">1 из 37 спинов</b></p>
                            <p id="roulette-jackpot-note" class="jp-note"></p>
                            <p id="roulette-jp-winner" class="jp-winner"></p>
                            </div>
                            <div id="roulette-jp-top" class="jp-top">
                                <p class="jp-top-title"><i class="fa-solid fa-trophy"></i>Топ-3 джекпота сайта · 24 ч<i class="fa-solid fa-circle text-emerald-400 animate-pulse ml-1.5" style="font-size:6px;vertical-align:2px" title="крупнейшие срывы за сутки, обновляется в реальном времени"></i></p>
                                <ol id="roulette-jp-top-list" class="jp-top-list"></ol>
                            </div>
                            </div>
                        </div>
                    </div>'''))

# ---------------------------------------------------------------- assets/app.css
# 13) подпись в Студии: заводской шанс рулетки среди прочих игр
PAIRS.append(('index.html', 1,
r'''Колесо 1 из 16.</p>''',
r'''Колесо 1 из 16, Рулетка (золотое зеро) 1 из 37.</p>'''))

PAIRS.append(('assets/app.css', 1,
r'''    .rl-chip{width:38px;height:38px;font-size:11px}
}''',
r'''    .rl-chip{width:38px;height:38px;font-size:11px}
}

/* b491: кошелёк стола рулетки — баланс точно до монеты, живой плюс/минус,
   подсказка про общий джекпот. fmtCoins() в шапке округляет до букв, поэтому
   ставка 25 и выигрыш 900 выглядели как «баланс не двигается». */
.rl-wallet{flex:0 1 250px;min-width:196px;margin-left:auto;border-radius:14px;border:1px solid rgba(251,191,36,.35);background:linear-gradient(160deg,rgba(2,6,23,.88),rgba(15,23,42,.62));padding:9px 11px;box-shadow:inset 0 0 22px rgba(251,191,36,.07)}
.rl-w-cap{font-size:9px;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:rgba(252,211,77,.92)}
.rl-w-cap i{margin-right:5px}
.rl-w-bal{display:flex;align-items:baseline;gap:8px;margin-top:4px;font-family:ui-monospace,SFMono-Regular,monospace;font-size:25px;line-height:1;font-weight:900;color:#fde68a;text-shadow:0 0 18px rgba(251,191,36,.28)}
.rl-w-rows{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-top:6px;font-size:10px;font-weight:700;color:#94a3b8}
.rl-w-rows b{font-family:ui-monospace,SFMono-Regular,monospace;font-size:12px;font-weight:900;color:#e2e8f0}
.rl-w-jp{margin-top:7px;padding-top:6px;border-top:1px dashed rgba(251,191,36,.25);font-size:10px;font-weight:800;color:#fcd34d}
.rl-w-jp i{margin-right:5px}
.rl-delta{font-style:normal;font-family:ui-monospace,SFMono-Regular,monospace;font-size:14px;font-weight:900;opacity:0;transform:translateY(5px);white-space:nowrap}
.rl-delta.rl-d-go{animation:rlDelta 1.5s ease-out forwards}
.rl-d-up{color:#34d399}
.rl-d-down{color:#fb7185}
@keyframes rlDelta{0%{opacity:0;transform:translateY(7px)}16%{opacity:1;transform:translateY(0)}72%{opacity:1;transform:translateY(0)}100%{opacity:0;transform:translateY(-7px)}}
.nx-bump{animation:nxBump .55s ease-out}
@keyframes nxBump{0%{transform:scale(1)}32%{transform:scale(1.08);box-shadow:0 0 0 2px rgba(251,191,36,.55)}100%{transform:scale(1)}}
.rl-jp-note{margin-top:9px;padding:7px 10px;border-radius:10px;border:1px solid rgba(251,191,36,.22);background:rgba(251,191,36,.06);font-size:10px;line-height:1.5;font-weight:700;color:#cbd5e1}
.rl-jp-note i{color:#fbbf24;margin-right:5px}
.rl-jp-note b{color:#fcd34d}
@media (max-width:640px){
    .rl-wallet{flex:1 1 100%;min-width:0}
    .rl-w-bal{font-size:21px}
    .rl-delta{font-size:12px}
}'''))


def read(rel):
    with io.open(os.path.join(ROOT, rel), 'r', encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8', newline='') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, cnt, old, new in PAIRS:
        txt = files.get(rel) or read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        if n in txt:
            problems.append('%s: правка уже применена: %s...' % (rel, o[:60]))
            continue
        if txt.count(o) != cnt:
            problems.append('%s: якорь встретился %d раз вместо %d: %s...' % (rel, txt.count(o), cnt, o[:60]))
            continue
        files[rel] = txt.replace(o, n, 1)
    for rel in TAG_FILES:
        txt = files.get(rel) or read(rel)
        if TAG_NEW in txt:
            problems.append('%s: тег уже %s' % (rel, TAG_NEW))
            continue
        if TAG_OLD not in txt:
            problems.append('%s: нет тега %s' % (rel, TAG_OLD))
            continue
        files[rel] = txt.replace(TAG_OLD, TAG_NEW)
    if problems:
        for p in problems:
            print('ПРОБЛЕМА:', p)
        return 1
    if '--check' in sys.argv:
        print('b491: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b491: баланс рулетки двигается на глазах, золотое зеро срывает общий джекпот; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
