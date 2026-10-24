#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b488: новая игра во вкладке «Игры» — РУЛЕТКА 2D (европейская, 0–36).

Заявка владельца (референс-скриншот стола): «добавь в игры игру рулетка в 2д».

Что появилось
-------------
Десятый режим «Рулетка» (плитка fa-circle-dot) с лобби #lobby-roulette:
слева 2D-колесо (canvas: 37 секторов с номерами и цветами, крутится с
ease-out и останавливает выигрышный сектор под указателем), справа стол:
зеро, сетка чисел 1–36 (3 колонки), дюжины, половины, чёт/нечет,
красное/чёрное; фишки 1/5/25/100; ставки копятся кликами по клеткам (бейдж
с суммой на клетке), кнопки «×2» и «Сброс», «Крутить» списывает сумму ставок,
выплата по классике: число ×36, дюжина ×3, равные шансы ×2. История последних
12 номеров — цветными чипами, как колонка STATS в референсе. Крупный выигрыш
(×36) празднует конфетти. Баланс — общий (state.coins), ставки сессии не
переживают перезагрузку (осознанно: стол — не кошелёк), история номеров
хранится в state.roulette.hist и в saveState.

Технически
----------
* Модуль в app.js перед тамагочи: ROULETTE_REDS/ROULETTE_ORDER (порядок
  номеров на колесе), rouletteSpotDefs() (все клетки стола с предикатами и
  множителями), rouletteBet/SetChip/Double/Clear/Spin, rouletteDraw()
  (отрисовка колеса) + анимация requestAnimationFrame с кубическим ease-out;
  длительность спинов берётся из window.__nxRouletteMs (тесты ставят 30 мс).
* setBattleMode('roulette'): показывает лобби, подсвечивает плитку, рисует
  стол и колесо; плитка добавлена в четыре id-списка «стекла» и получила
  правило .lq-on, контейнер переключателей переведён на .nx-modes
  (5 колонок на телефоне, 10 от sm — app.css), иначе десятая плитка не
  влезала в старую сетку.
* Инлайн-обработчики (onclick rouletteBet/… ) объявлены глобально —
  проверка «все inline-обработчики объявлены» не ломается.

Менялись app.js, index.html, app.css — тег сборки nxmob231 -> nxmob232.

Проверка/применение:
    python3 tools/_b488_patch.py --check
    python3 tools/_b488_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob231'
TAG_NEW = 'nxmob232'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

# --------------------------------------------------------------------------- #
# assets/app.css: сетка переключателей на 10 режимов
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.css', 1,
              r'''@media (max-width:639px){.tama-actions > :last-child{grid-column:1/-1}}''',
              r'''@media (max-width:639px){.tama-actions > :last-child{grid-column:1/-1}}

/* b488: переключатель режимов «Игры» на десять плиток: на телефоне 5+5,
   от sm — одна строка из десяти (в tailwind.css нет sm:grid-cols-10) */
.nx-modes{grid-template-columns:repeat(5,minmax(0,1fr))}
@media (min-width:640px){.nx-modes{grid-template-columns:repeat(10,minmax(0,1fr))}}'''))

# --------------------------------------------------------------------------- #
# assets/app.js: модуль рулетки (перед тамагочи)
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''        // ============ b483: ТАМАГОЧИ — питомец на балансе игры ============''',
              r'''        // ============ b488: РУЛЕТКА 2D (европейская, 0–36) ============
        // Ставки копятся кликами по клеткам стола (фишка = выбранное
        // достоинство), «Крутить» списывает сумму ставок с общего баланса,
        // колесо крутится и останавливает выигрышный сектор под указателем.
        // Выплаты: число ×36, дюжина ×3, равные шансы ×2.
        const ROULETTE_REDS = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36];
        const ROULETTE_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26];
        const ROULETTE_CHIPS = [1, 5, 25, 100];
        let rouletteBets = {};      // spotId -> сумма (живёт до перезагрузки: стол, не кошелёк)
        let rouletteChip = 5;
        let rouletteSpinning = false;
        let rouletteAngle = 0;      // текущий поворот колеса, градусы
        function rouletteColor(n) { return n === 0 ? 'green' : (ROULETTE_REDS.indexOf(n) >= 0 ? 'red' : 'black'); }
        function rouletteState() { if (!state.roulette) state.roulette = { hist: [] }; return state.roulette; }
        function rouletteSpotDefs() {
            const defs = [];
            for (let n = 0; n <= 36; n++) defs.push({ id: 'n' + n, label: String(n), kind: 'num', pay: 36, hit: x => x === n });
            defs.push({ id: 'd1', label: '1–12', kind: 'dozen', pay: 3, hit: x => x >= 1 && x <= 12 });
            defs.push({ id: 'd2', label: '13–24', kind: 'dozen', pay: 3, hit: x => x >= 13 && x <= 24 });
            defs.push({ id: 'd3', label: '25–36', kind: 'dozen', pay: 3, hit: x => x >= 25 && x <= 36 });
            defs.push({ id: 'low', label: '1–18', kind: 'even', pay: 2, hit: x => x >= 1 && x <= 18 });
            defs.push({ id: 'high', label: '19–36', kind: 'even', pay: 2, hit: x => x >= 19 && x <= 36 });
            defs.push({ id: 'even', label: 'ЧЁТ', kind: 'even', pay: 2, hit: x => x !== 0 && x % 2 === 0 });
            defs.push({ id: 'odd', label: 'НЕЧЕТ', kind: 'even', pay: 2, hit: x => x % 2 === 1 });
            defs.push({ id: 'red', label: 'КРАСНОЕ', kind: 'color', pay: 2, hit: x => rouletteColor(x) === 'red' });
            defs.push({ id: 'black', label: 'ЧЁРНОЕ', kind: 'color', pay: 2, hit: x => rouletteColor(x) === 'black' });
            return defs;
        }
        function rouletteTotal() {
            let s = 0;
            for (const k in rouletteBets) s += rouletteBets[k];
            return s;
        }
        function rouletteSetChip(v) { rouletteChip = v; renderRoulette(); }
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
        }
        function rouletteSpin() {
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
        }
        function rouletteAnimate(win, done) {
            const cv = document.getElementById('roulette-wheel');
            const ms = Number(window.__nxRouletteMs) || 4200;
            if (!cv || !cv.getContext) { setTimeout(done, 0); return; }
            const sector = 360 / 37;
            const idx = ROULETTE_ORDER.indexOf(win);
            // сектор win должен встать под указатель сверху (угол -90°)
            const target = 360 * 5 + (360 - (idx * sector + sector / 2)) - 90;
            const from = rouletteAngle % 360;
            const t0 = performance.now();
            const step = now => {
                const p = Math.min(1, (now - t0) / ms);
                const e = 1 - Math.pow(1 - p, 3);
                rouletteAngle = from + (target - from) * e;
                rouletteDraw();
                if (p < 1) requestAnimationFrame(step); else done();
            };
            requestAnimationFrame(step);
        }
        function rouletteDraw() {
            const cv = document.getElementById('roulette-wheel');
            if (!cv) return;
            const g = cv.getContext('2d');
            if (!g) return;
            const W = cv.width, H = cv.height, R = Math.min(W, H) / 2 - 4, cx = W / 2, cy = H / 2;
            g.clearRect(0, 0, W, H);
            g.save();
            g.translate(cx, cy);
            g.rotate(rouletteAngle * Math.PI / 180);
            const sector = Math.PI * 2 / 37;
            for (let i = 0; i < 37; i++) {
                const n = ROULETTE_ORDER[i];
                g.beginPath();
                g.moveTo(0, 0);
                g.arc(0, 0, R, i * sector - sector / 2, i * sector + sector / 2);
                g.closePath();
                g.fillStyle = n === 0 ? '#059669' : (ROULETTE_REDS.indexOf(n) >= 0 ? '#be123c' : '#0f172a');
                g.fill();
                g.strokeStyle = 'rgba(248,250,252,.25)';
                g.lineWidth = 1;
                g.stroke();
                g.save();
                g.rotate(i * sector);
                g.fillStyle = '#f8fafc';
                g.font = '700 ' + Math.round(R / 16) + 'px Inter, sans-serif';
                g.textAlign = 'center';
                g.textBaseline = 'middle';
                g.fillText(String(n), 0, -R * 0.82);
                g.restore();
            }
            g.beginPath(); g.arc(0, 0, R * 0.34, 0, Math.PI * 2);
            g.fillStyle = '#1e293b'; g.fill();
            g.strokeStyle = 'rgba(248,250,252,.3)'; g.lineWidth = 2; g.stroke();
            g.restore();
            // указатель сверху
            g.beginPath();
            g.moveTo(cx - 8, 2); g.lineTo(cx + 8, 2); g.lineTo(cx, 16);
            g.closePath();
            g.fillStyle = '#fbbf24'; g.fill();
        }
        function rouletteSpotBtn(d, cls, style) {
            const bet = rouletteBets[d.id] || 0;
            const bg = d.kind === 'num'
                ? (d.label === '0' ? 'bg-emerald-600 hover:bg-emerald-500' : (ROULETTE_REDS.indexOf(Number(d.label)) >= 0 ? 'bg-rose-600 hover:bg-rose-500' : 'bg-slate-900 hover:bg-slate-800 border border-slate-700'))
                : 'bg-slate-800 hover:bg-slate-700 border border-slate-700';
            return `<button type="button" onclick="rouletteBet('${d.id}')"${style || ''} class="relative ${cls} ${bg} rounded-lg px-1 py-2 text-[11px] sm:text-[12px] font-bold text-white transition tama-btn">
                ${d.label}${bet ? `<i class="not-italic absolute -top-1.5 -right-1.5 text-[9px] leading-none bg-amber-400 text-slate-900 rounded-full px-1.5 py-1 font-black shadow">${bet}</i>` : ''}
            </button>`;
        }
        function renderRoulette() {
            const box = document.getElementById('roulette-table');
            if (!box) return;
            const defs = rouletteSpotDefs();
            const nums = defs.filter(d => d.kind === 'num');
            const dozens = defs.filter(d => d.kind === 'dozen');
            const evens = defs.filter(d => d.kind === 'even' || d.kind === 'color');
            const total = rouletteTotal();
            const rs = rouletteState();
            const hist = (rs.hist || []).slice().reverse();
            const chips = ROULETTE_CHIPS.map(c => `<button type="button" onclick="rouletteSetChip(${c})" class="tama-btn px-3 py-1.5 rounded-full text-[11px] font-black border-2 ${rouletteChip === c ? 'bg-amber-400 text-slate-900 border-amber-200' : 'bg-slate-800 text-slate-200 border-slate-600'}">${c}</button>`).join('');
            box.innerHTML = `
                <div class="flex flex-wrap items-center gap-2">
                    <span class="text-[10px] text-slate-400 font-bold mr-1">Фишка:</span>${chips}
                    <span class="ml-auto text-[11px] text-slate-300">На столе: <b class="text-amber-300">${total}</b></span>
                </div>
                <div class="grid grid-cols-3 gap-1 mt-2">
                    ${rouletteSpotBtn(nums[0], 'py-2.5', ' style="grid-column:1/-1"')}<!-- b488: зеро во всю ширину стола (col-span-3 в tailwind.css нет) -->
                    ${nums.slice(1).map(d => rouletteSpotBtn(d, '')).join('')}
                </div>
                <div class="grid grid-cols-3 gap-1 mt-1">
                    ${dozens.map(d => rouletteSpotBtn(d, 'py-2')).join('')}
                </div>
                <div class="grid grid-cols-3 gap-1 mt-1">
                    ${evens.map(d => rouletteSpotBtn(d, 'py-2 text-[10px]')).join('')}
                </div>
                <div class="flex flex-wrap items-center gap-2 mt-3">
                    <button type="button" onclick="rouletteDouble()" class="tama-btn px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] font-bold text-slate-200 transition">×2</button>
                    <button type="button" onclick="rouletteClear()" class="tama-btn px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] font-bold text-slate-200 transition">Сброс</button>
                    <button type="button" onclick="rouletteSpin()" class="tama-btn flex-1 min-w-[140px] px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-[12px] font-black transition shadow-lg"><i class="fa-solid fa-circle-dot mr-1.5"></i>Крутить · ${total || '—'}</button>
                </div>
                <div class="flex flex-wrap items-center gap-1 mt-3">
                    <span class="text-[10px] text-slate-500 font-bold mr-1">История:</span>
                    ${hist.length ? hist.map(n => `<span class="w-6 h-6 rounded-full text-[10px] font-black flex items-center justify-center ${n === 0 ? 'bg-emerald-600' : (ROULETTE_REDS.indexOf(n) >= 0 ? 'bg-rose-600' : 'bg-slate-800 border border-slate-600')} text-white">${n}</span>`).join('') : '<span class="text-[10px] text-slate-600">пока пусто</span>'}
                </div>`;
        }
        // ============ /b488 рулетка ============

        // ============ b483: ТАМАГОЧИ — питомец на балансе игры ============'''))

# --------------------------------------------------------------------------- #
# assets/app.js: setBattleMode знает roulette
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            const lt = document.getElementById('lobby-tama'); // b483
            if (lt) lt.classList.toggle('hidden', m !== 'tama');''',
              r'''            const lt = document.getElementById('lobby-tama'); // b483
            if (lt) lt.classList.toggle('hidden', m !== 'tama');
            const lr = document.getElementById('lobby-roulette'); // b488
            if (lr) lr.classList.toggle('hidden', m !== 'roulette');'''))

PAIRS.append(('assets/app.js', 1,
              r'''            setModeBtn('mode-tama-btn', m === 'tama', 'lq-on'); // b483''',
              r'''            setModeBtn('mode-tama-btn', m === 'tama', 'lq-on'); // b483
            setModeBtn('mode-roulette-btn', m === 'roulette', 'lq-on'); // b488'''))

PAIRS.append(('assets/app.js', 1,
              r'''            if (m === 'tama') renderTamagotchi(); // b483''',
              r'''            if (m === 'tama') renderTamagotchi(); // b483
            if (m === 'roulette') { renderRoulette(); rouletteDraw(); } // b488'''))

# --------------------------------------------------------------------------- #
# index.html: контейнер на 10 плиток, плитка и лобби рулетки
# --------------------------------------------------------------------------- #
PAIRS.append(('index.html', 1,
              r'''                <div class="grid grid-cols-5 sm:grid-cols-9 gap-1 sm:gap-2 w-full py-0.5"><!-- b484: девять плиток: на телефоне 5+4, от sm — одна строка из девяти (голый grid-cols-9 в tailwind.css отсутствует — из-за него сетка в b483 свалилась в столбик) -->''',
              r'''                <div class="grid nx-modes gap-1 sm:gap-2 w-full py-0.5"><!-- b488: десять плиток: nx-modes = 5 колонок на телефоне и 10 от sm (sm:grid-cols-10 в tailwind.css нет) -->'''))

PAIRS.append(('index.html', 1,
              r'''<button onclick="setBattleMode('tama')" id="mode-tama-btn" class="w-full flex flex-col items-center justify-center gap-1 px-1 py-2 rounded-xl text-[13px] sm:text-[15px] lg:text-[13px] font-bold transition whitespace-nowrap overflow-hidden min-w-0 lg:flex-row lg:gap-1.5 lg:px-2 bg-slate-800 text-slate-300 border border-slate-700" title="Тамагочи: питомец тратит ваш баланс на еду, игры и уход, а за уровни дарит карты"><i class="fa-solid fa-paw mr-0 lg:mr-1.5"></i><span class="block lg:inline w-full lg:w-auto text-center lg:text-left text-[8px] sm:text-[9px] lg:text-xs font-bold leading-none truncate">Тамагочи</span></button>''',
              r'''<button onclick="setBattleMode('tama')" id="mode-tama-btn" class="w-full flex flex-col items-center justify-center gap-1 px-1 py-2 rounded-xl text-[13px] sm:text-[15px] lg:text-[13px] font-bold transition whitespace-nowrap overflow-hidden min-w-0 lg:flex-row lg:gap-1.5 lg:px-2 bg-slate-800 text-slate-300 border border-slate-700" title="Тамагочи: питомец тратит ваш баланс на еду, игры и уход, а за уровни дарит карты"><i class="fa-solid fa-paw mr-0 lg:mr-1.5"></i><span class="block lg:inline w-full lg:w-auto text-center lg:text-left text-[8px] sm:text-[9px] lg:text-xs font-bold leading-none truncate">Тамагочи</span></button>
                <button onclick="setBattleMode('roulette')" id="mode-roulette-btn" class="w-full flex flex-col items-center justify-center gap-1 px-1 py-2 rounded-xl text-[13px] sm:text-[15px] lg:text-[13px] font-bold transition whitespace-nowrap overflow-hidden min-w-0 lg:flex-row lg:gap-1.5 lg:px-2 bg-slate-800 text-slate-300 border border-slate-700" title="Рулетка 2D: ставки фишками из баланса, число ×36, дюжина ×3, равные шансы ×2"><i class="fa-solid fa-circle-dot mr-0 lg:mr-1.5"></i><span class="block lg:inline w-full lg:w-auto text-center lg:text-left text-[8px] sm:text-[9px] lg:text-xs font-bold leading-none truncate">Рулетка</span></button>'''))

PAIRS.append(('index.html', 1,
              r'''                <!-- b483: лобби режима «Тамагочи» — содержимое рисует renderTamagotchi() -->''',
              r'''                <!-- b488: лобби режима «Рулетка»: колесо canvas слева, стол справа -->
                <div id="lobby-roulette" class="space-y-6 hidden">
                    <div class="bg-gradient-to-r from-slate-900 to-slate-900/60 p-4 sm:p-6 rounded-2xl border border-slate-800">
                        <div class="flex flex-wrap items-start justify-between gap-3">
                            <div class="min-w-0">
                                <h2 class="text-2xl font-black text-white tracking-tight"><i class="fa-solid fa-circle-dot text-rose-400 mr-2"></i>Рулетка 2D</h2>
                                <p class="text-sm text-slate-400 mt-1">Европейская (0–36): выберите фишку, кликните по клеткам стола и крутите. Число ×36, дюжина ×3, равные шансы ×2. Ставки списываются с баланса.</p>
                            </div>
                        </div>
                        <div class="flex flex-col lg:flex-row gap-4 items-start mt-4">
                            <div class="relative shrink-0 mx-auto">
                                <canvas id="roulette-wheel" width="340" height="340" class="block max-w-full"></canvas>
                            </div>
                            <div id="roulette-table" class="min-w-0 w-full"></div>
                        </div>
                    </div>
                </div>
                <!-- b483: лобби режима «Тамагочи» — содержимое рисует renderTamagotchi() -->'''))

# --------------------------------------------------------------------------- #
# index.html: стекло и подсветка плитки рулетки
# --------------------------------------------------------------------------- #
PAIRS.append(('index.html', 1,
              r'''    #mode-grid-btn, #mode-wheel-btn, #mode-mines-btn, #mode-lines-btn, #mode-tama-btn, #miner-btn{''',
              r'''    #mode-grid-btn, #mode-wheel-btn, #mode-mines-btn, #mode-lines-btn, #mode-tama-btn, #mode-roulette-btn, #miner-btn{'''))

PAIRS.append(('index.html', 1,
              r'''    #mode-grid-btn::before, #mode-wheel-btn::before, #mode-mines-btn::before, #mode-lines-btn::before, #mode-tama-btn::before, #miner-btn::before{''',
              r'''    #mode-grid-btn::before, #mode-wheel-btn::before, #mode-mines-btn::before, #mode-lines-btn::before, #mode-tama-btn::before, #mode-roulette-btn::before, #miner-btn::before{'''))

PAIRS.append(('index.html', 1,
              r'''    #mode-grid-btn:hover, #mode-wheel-btn:hover, #mode-mines-btn:hover, #mode-lines-btn:hover, #mode-tama-btn:hover, #miner-btn:hover{''',
              r'''    #mode-grid-btn:hover, #mode-wheel-btn:hover, #mode-mines-btn:hover, #mode-lines-btn:hover, #mode-tama-btn:hover, #mode-roulette-btn:hover, #miner-btn:hover{'''))

PAIRS.append(('index.html', 1,
              r'''    #mode-grid-btn:active, #mode-wheel-btn:active, #mode-mines-btn:active, #mode-lines-btn:active, #mode-tama-btn:active, #miner-btn:active{ transform: scale(.97); }''',
              r'''    #mode-grid-btn:active, #mode-wheel-btn:active, #mode-mines-btn:active, #mode-lines-btn:active, #mode-tama-btn:active, #mode-roulette-btn:active, #miner-btn:active{ transform: scale(.97); }'''))

PAIRS.append(('index.html', 1,
              r'''    #mode-tama-btn.lq-on{ --lq-tint: rgba(52,211,153,.26); --lq-text:#a7f3d0; border-color: rgba(110,231,183,.5); }''',
              r'''    #mode-tama-btn.lq-on{ --lq-tint: rgba(52,211,153,.26); --lq-text:#a7f3d0; border-color: rgba(110,231,183,.5); }
    /* b488: стекло активной плитки «Рулетка» — малиновое, под цвет стола */
    #mode-roulette-btn.lq-on{ --lq-tint: rgba(244,63,94,.30); --lq-text:#fecdd3; border-color: rgba(253,164,175,.5); }'''))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
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
        print('b488: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b488: рулетка 2D в «Играх» — ставки, колесо, выплаты; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
