#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b489: редизайн рулетки — казино-сукно, классический стол, живое колесо.

Заявка владельца (скриншот): «выглядит не красиво и дизайн не красивый».
Стол b488 и правда смотрелся формой из серых кнопок: колесо — тонкие красные
лепестки на темноте (чёрные секторы сливались с фоном), без обода и шарика;
стол — широкие плоские плашки в 3 колонки, вне казино-контекста.

Лечение
-------
1. КОЛЕСО (rouletteDraw): деревянный обод с золотыми кольцами и пинами,
   секторы с золотыми разделителями (чёрные теперь #111827 с обводкой — не
   сливаются), конус с четырьмя спицами и золотой ступицей, НОМера по ободу,
   белый шарик с бликом, который во время спина крутится против колеса по
   спирали (ROULETTE_BALL: угол против хода + радиус сжимается к карману) и
   садится в выигрышный сектор под золотым ромбом-указателем. Canvas 420px,
   вокруг — css-свечение .rl-wheelhouse (drop-shadow).
2. СТОЛ (renderRoulette): классическая европейская раскладка на CSS-grid
   .rl-grid: зеро слева вертикальной плашкой на 3 ряда, 3 ряда × 12 колонок
   чисел, справа три «2:1» (новые ставки на колонку c1/c2/c3, pay 3), ниже
   дюжины (по 4 колонки) и равные шансы (по 2 колонки). Всё лежит на зелёном
   сукне .rl-felt (радиальный градиент + золотая рамка + внутренняя тень):
   красные клетки — градиент #e11d48→#9f1239, чёрные — #1f2937→#0b1220,
   зеро — изумруд, равные шансы — тёмная зелень; золотая обводка клеток,
   hover-подъём с подсветкой.
3. Ставки на клетках — мини-фишка .rl-chipmini (золотой кругляш с белой
   каймой) вместо плоского бейджа; выбор фишки — настоящие казино-фишки
   .rl-chip с коническими полосами своего цвета (1 серая, 5 красная,
   25 зелёная, 100 янтарная), активная приподнята и подсвечена золотом.
4. Мобильная версия: .rl-grid ужимается (28px зеро, 26px 2:1, кегль 9px) —
   стол влезает в 390px без горизонтального скролла.

Менялись assets/app.js и assets/app.css — тег сборки nxmob232 -> nxmob233.

Проверка/применение:
    python3 tools/_b489_patch.py --check
    python3 tools/_b489_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob232'
TAG_NEW = 'nxmob233'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

# --------------------------------------------------------------------------- #
# app.js: ставки на колонки 2:1
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            defs.push({ id: 'd3', label: '25–36', kind: 'dozen', pay: 3, hit: x => x >= 25 && x <= 36 });''',
              r'''            defs.push({ id: 'd3', label: '25–36', kind: 'dozen', pay: 3, hit: x => x >= 25 && x <= 36 });
            // b489: ставки на вертикальную колонку чисел (2:1), как на настоящем столе
            defs.push({ id: 'c3', label: '2:1', kind: 'col', pay: 3, hit: x => x !== 0 && x % 3 === 0 });
            defs.push({ id: 'c2', label: '2:1', kind: 'col', pay: 3, hit: x => x !== 0 && x % 3 === 2 });
            defs.push({ id: 'c1', label: '2:1', kind: 'col', pay: 3, hit: x => x !== 0 && x % 3 === 1 });'''))

# --------------------------------------------------------------------------- #
# app.js: шарик
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''        let rouletteAngle = 0;      // текущий поворот колеса, градусы''',
              r'''        let rouletteAngle = 0;      // текущий поворот колеса, градусы
        const ROULETTE_BALL = { angle: -90, r: 0.94, on: false, spin: 0 }; // b489: шарик: экранный угол, радиус (доля R), видимость'''))

PAIRS.append(('assets/app.js', 1,
              r'''            const from = rouletteAngle % 360;
            const t0 = performance.now();
            const step = now => {
                const p = Math.min(1, (now - t0) / ms);
                const e = 1 - Math.pow(1 - p, 3);
                rouletteAngle = from + (target - from) * e;
                rouletteDraw();
                if (p < 1) requestAnimationFrame(step); else done();
            };
            requestAnimationFrame(step);''',
              r'''            const from = rouletteAngle % 360;
            const t0 = performance.now();
            ROULETTE_BALL.spin = 560 + Math.random() * 240; // b489: сколько градусов шарик пролетит против колеса
            const step = now => {
                const p = Math.min(1, (now - t0) / ms);
                const e = 1 - Math.pow(1 - p, 3);
                rouletteAngle = from + (target - from) * e;
                // b489: шарик крутится против колеса и по спирали садится в карман
                // выигрышного сектора (тот стоит под указателем = экранный угол -90°)
                ROULETTE_BALL.angle = -90 - (1 - e) * ROULETTE_BALL.spin;
                ROULETTE_BALL.r = 0.94 - 0.16 * e;
                ROULETTE_BALL.on = true;
                rouletteDraw();
                if (p < 1) requestAnimationFrame(step);
                else { ROULETTE_BALL.angle = -90; ROULETTE_BALL.r = 0.78; rouletteDraw(); done(); }
            };
            requestAnimationFrame(step);'''))

# --------------------------------------------------------------------------- #
# app.js: новая отрисовка колеса
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''        function rouletteDraw() {
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
        }''',
              r'''        function rouletteDraw() {
            const cv = document.getElementById('roulette-wheel');
            if (!cv) return;
            const g = cv.getContext('2d');
            if (!g) return;
            const W = cv.width, H = cv.height, cx = W / 2, cy = H / 2;
            const R = Math.min(W, H) / 2 - 8;
            g.clearRect(0, 0, W, H);
            // b489: обод — тёмное дерево с золотыми кольцами и пинами
            const rim = g.createRadialGradient(cx, cy, R * 0.8, cx, cy, R);
            rim.addColorStop(0, '#3b2417'); rim.addColorStop(0.55, '#5a3a22'); rim.addColorStop(1, '#241209');
            g.beginPath(); g.arc(cx, cy, R, 0, Math.PI * 2); g.fillStyle = rim; g.fill();
            g.lineWidth = 3; g.strokeStyle = 'rgba(251,191,36,.8)'; g.stroke();
            g.beginPath(); g.arc(cx, cy, R * 0.8, 0, Math.PI * 2); g.strokeStyle = 'rgba(251,191,36,.45)'; g.lineWidth = 1.5; g.stroke();
            for (let i = 0; i < 8; i++) {
                const a = i * Math.PI / 4 + Math.PI / 8;
                g.beginPath(); g.arc(cx + Math.cos(a) * R * 0.9, cy + Math.sin(a) * R * 0.9, Math.max(2, R * 0.018), 0, Math.PI * 2);
                g.fillStyle = '#fcd34d'; g.fill();
            }
            const RS = R * 0.8;
            g.save();
            g.translate(cx, cy);
            g.rotate(rouletteAngle * Math.PI / 180);
            const sector = Math.PI * 2 / 37;
            for (let i = 0; i < 37; i++) {
                const n = ROULETTE_ORDER[i];
                g.beginPath();
                g.moveTo(0, 0);
                g.arc(0, 0, RS, i * sector - sector / 2, i * sector + sector / 2);
                g.closePath();
                g.fillStyle = n === 0 ? '#059669' : (ROULETTE_REDS.indexOf(n) >= 0 ? '#c81e3f' : '#111827');
                g.fill();
                g.strokeStyle = 'rgba(251,191,36,.35)';
                g.lineWidth = 0.8;
                g.stroke();
                g.save();
                g.rotate(i * sector);
                g.fillStyle = '#f8fafc';
                g.font = '700 ' + Math.round(R / 15) + 'px Inter, sans-serif';
                g.textAlign = 'center';
                g.textBaseline = 'middle';
                g.fillText(String(n), 0, -RS * 0.85);
                g.restore();
            }
            // конус со спицами и золотая ступица
            const cone = g.createRadialGradient(0, 0, R * 0.04, 0, 0, R * 0.5);
            cone.addColorStop(0, '#475569'); cone.addColorStop(0.6, '#1e293b'); cone.addColorStop(1, '#0b1220');
            g.beginPath(); g.arc(0, 0, R * 0.5, 0, Math.PI * 2); g.fillStyle = cone; g.fill();
            g.strokeStyle = 'rgba(251,191,36,.5)'; g.lineWidth = 1.5; g.stroke();
            for (let i = 0; i < 4; i++) {
                g.save(); g.rotate(i * Math.PI / 2 + Math.PI / 4);
                g.fillStyle = 'rgba(251,191,36,.55)';
                g.fillRect(-R * 0.02, -R * 0.48, R * 0.04, R * 0.44);
                g.restore();
            }
            g.beginPath(); g.arc(0, 0, R * 0.12, 0, Math.PI * 2);
            const hub = g.createRadialGradient(-R * 0.04, -R * 0.04, R * 0.02, 0, 0, R * 0.12);
            hub.addColorStop(0, '#fde68a'); hub.addColorStop(1, '#b45309');
            g.fillStyle = hub; g.fill();
            g.restore();
            // b489: шарик — белая сфера с бликом, на своей траектории
            if (ROULETTE_BALL.on) {
                const ba = ROULETTE_BALL.angle * Math.PI / 180;
                const br = R * ROULETTE_BALL.r;
                const bx = cx + Math.cos(ba) * br, by = cy + Math.sin(ba) * br;
                g.beginPath(); g.arc(bx + 2, by + 3, R * 0.032, 0, Math.PI * 2);
                g.fillStyle = 'rgba(2,6,23,.45)'; g.fill();
                g.beginPath(); g.arc(bx, by, R * 0.03, 0, Math.PI * 2);
                const bl = g.createRadialGradient(bx - R * 0.012, by - R * 0.012, R * 0.004, bx, by, R * 0.03);
                bl.addColorStop(0, '#ffffff'); bl.addColorStop(1, '#94a3b8');
                g.fillStyle = bl; g.fill();
            }
            // указатель: золотой ромб над ободом
            g.beginPath();
            g.moveTo(cx, cy - R - 6); g.lineTo(cx + 9, cy - R + 12); g.lineTo(cx, cy - R + 20); g.lineTo(cx - 9, cy - R + 12);
            g.closePath();
            g.fillStyle = '#fbbf24'; g.fill();
            g.strokeStyle = 'rgba(2,6,23,.6)'; g.lineWidth = 1; g.stroke();
        }'''))

# --------------------------------------------------------------------------- #
# app.js: новый стол (сукно, классическая раскладка, казино-фишки)
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''        function rouletteSpotBtn(d, cls, style) {''',
              r'''        function rouletteSpotBtn(d, extra, style) {'''))

PAIRS.append(('assets/app.js', 1,
              r'''            const bet = rouletteBets[d.id] || 0;
            const bg = d.kind === 'num'
                ? (d.label === '0' ? 'bg-emerald-600 hover:bg-emerald-500' : (ROULETTE_REDS.indexOf(Number(d.label)) >= 0 ? 'bg-rose-600 hover:bg-rose-500' : 'bg-slate-900 hover:bg-slate-800 border border-slate-700'))
                : 'bg-slate-800 hover:bg-slate-700 border border-slate-700';
            return `<button type="button" onclick="rouletteBet('${d.id}')"${style || ''} class="relative ${cls} ${bg} rounded-lg px-1 py-2 text-[11px] sm:text-[12px] font-bold text-white transition tama-btn">
                ${d.label}${bet ? `<i class="not-italic absolute -top-1.5 -right-1.5 text-[9px] leading-none bg-amber-400 text-slate-900 rounded-full px-1.5 py-1 font-black shadow">${bet}</i>` : ''}
            </button>`;
        }''',
              r'''            const bet = rouletteBets[d.id] || 0;
            // b489: клетки стола — сукно-градиенты по типу ставки
            const col = d.kind === 'num'
                ? (ROULETTE_REDS.indexOf(Number(d.label)) >= 0 ? 'rl-red' : 'rl-black')
                : (d.kind === 'dozen' || d.kind === 'col' ? 'rl-out' : 'rl-out');
            return `<button type="button" onclick="rouletteBet('${d.id}')"${style || ''} class="rl-cell ${col} ${extra || ''}">${d.label}${bet ? `<i class="rl-chipmini">${bet}</i>` : ''}</button>`;
        }'''))

PAIRS.append(('assets/app.js', 1,
              r'''        function renderRoulette() {
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
        }''',
              r'''        function renderRoulette() {
            const box = document.getElementById('roulette-table');
            if (!box) return;
            const defs = rouletteSpotDefs();
            const num = n => defs.find(d => d.id === 'n' + n);
            const total = rouletteTotal();
            const rs = rouletteState();
            const hist = (rs.hist || []).slice().reverse();
            // b489: фишки — казино-кругляши с коническими полосами своего цвета
            const CHIP_CLS = { 1: 'rl-chip-1', 5: 'rl-chip-5', 25: 'rl-chip-25', 100: 'rl-chip-100' };
            const chips = ROULETTE_CHIPS.map(c => `<button type="button" onclick="rouletteSetChip(${c})" class="rl-chip ${CHIP_CLS[c] || ''} ${rouletteChip === c ? 'rl-chip-on' : ''}" title="Фишка ${c} монет">${c}</button>`).join('');
            // b489: классический стол: зеро слева на 3 ряда, 3 ряда × 12 чисел,
            // справа «2:1», ниже дюжины (по 4 колонки) и равные шансы (по 2)
            const betBadge = id => (rouletteBets[id] || 0) ? `<i class="rl-chipmini">${rouletteBets[id]}</i>` : '';
            let cells = `<button type="button" onclick="rouletteBet('n0')" class="rl-cell rl-zero rl-zero-v">0${betBadge('n0')}</button>`;
            const colIds = ['c3', 'c2', 'c1'];
            for (let row = 0; row < 3; row++) {
                for (let col = 1; col <= 12; col++) cells += rouletteSpotBtn(num(col * 3 - row), '');
                cells += `<button type="button" onclick="rouletteBet('${colIds[row]}')" class="rl-cell rl-out rl-colbet">2:1${betBadge(colIds[row])}</button>`;
            }
            const dozens = [['d1', '1–12', 2], ['d2', '13–24', 6], ['d3', '25–36', 10]];
            dozens.forEach(dz => {
                const d = defs.find(x => x.id === dz[0]);
                cells += `<button type="button" onclick="rouletteBet('${dz[0]}')" style="grid-column:${dz[2]} / span 4" class="rl-cell rl-out rl-dz">${d.label}${betBadge(dz[0])}</button>`;
            });
            const outs = [['low', '1–18', 2], ['even', 'ЧЁТ', 4], ['red', 'КРАСНОЕ', 6], ['black', 'ЧЁРНОЕ', 8], ['odd', 'НЕЧЕТ', 10], ['high', '19–36', 12]];
            outs.forEach(oz => {
                cells += `<button type="button" onclick="rouletteBet('${oz[0]}')" style="grid-column:${oz[2]} / span 2" class="rl-cell rl-out rl-ev">${oz[1]}${betBadge(oz[0])}</button>`;
            });
            box.innerHTML = `
                <div class="flex flex-wrap items-center gap-2 mb-2">
                    <span class="text-[10px] text-slate-400 font-bold mr-1">Фишка:</span>${chips}
                    <span class="ml-auto text-[11px] text-slate-300">На столе: <b class="text-amber-300">${total}</b></span>
                </div>
                <div class="rl-felt">
                    <div class="rl-grid">${cells}</div>
                </div>
                <div class="flex flex-wrap items-center gap-2 mt-3">
                    <button type="button" onclick="rouletteDouble()" class="tama-btn px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] font-bold text-slate-200 transition">×2</button>
                    <button type="button" onclick="rouletteClear()" class="tama-btn px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] font-bold text-slate-200 transition">Сброс</button>
                    <button type="button" onclick="rouletteSpin()" class="tama-btn flex-1 min-w-[140px] px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-[12px] font-black transition shadow-lg"><i class="fa-solid fa-circle-dot mr-1.5"></i>Крутить · ${total || '—'}</button>
                </div>
                <div class="flex flex-wrap items-center gap-1 mt-3">
                    <span class="text-[10px] text-slate-500 font-bold mr-1">История:</span>
                    ${hist.length ? hist.map(n => `<span class="rl-histn ${n === 0 ? 'rl-hist-zero' : (ROULETTE_REDS.indexOf(n) >= 0 ? 'rl-hist-red' : 'rl-hist-black')}">${n}</span>`).join('') : '<span class="text-[10px] text-slate-600">пока пусто</span>'}
                </div>`;
        }'''))

# --------------------------------------------------------------------------- #
# app.css: сукно, клетки, фишки, история, дом колеса
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.css', 1,
              r'''@media (min-width:640px){.nx-modes{grid-template-columns:repeat(10,minmax(0,1fr))}}''',
              r'''@media (min-width:640px){.nx-modes{grid-template-columns:repeat(10,minmax(0,1fr))}}

/* b489: рулетка-казино: сукно, клетки стола, казино-фишки, история, дом колеса */
.rl-wheelhouse{filter:drop-shadow(0 12px 34px rgba(2,6,23,.7))}
.rl-felt{background:radial-gradient(120% 90% at 50% 0%,#065f46 0%,#064e3b 45%,#022c22 100%);border:1px solid rgba(251,191,36,.35);border-radius:16px;padding:10px;box-shadow:inset 0 0 46px rgba(2,6,23,.55)}
.rl-grid{display:grid;grid-template-columns:44px repeat(12,minmax(0,1fr)) 40px;gap:4px}
.rl-cell{position:relative;display:flex;align-items:center;justify-content:center;border-radius:6px;border:1px solid rgba(251,191,36,.28);font-weight:800;font-size:12px;color:#fff;padding:8px 2px;cursor:pointer;transition:transform .1s ease,box-shadow .2s ease}
.rl-cell:hover{transform:translateY(-1px);box-shadow:0 0 0 1px rgba(251,191,36,.65),0 4px 12px rgba(2,6,23,.5)}
.rl-red{background:linear-gradient(160deg,#e11d48,#9f1239)}
.rl-black{background:linear-gradient(160deg,#1f2937,#0b1220)}
.rl-zero{background:linear-gradient(160deg,#059669,#065f46)}
.rl-zero-v{grid-column:1;grid-row:1 / span 3;writing-mode:vertical-rl;transform:rotate(180deg);font-size:14px;letter-spacing:.1em}
.rl-out{background:linear-gradient(160deg,rgba(6,78,59,.9),rgba(2,44,34,.95));font-size:10px;letter-spacing:.05em}
.rl-colbet{writing-mode:vertical-rl;transform:rotate(180deg);font-size:10px}
.rl-chipmini{position:absolute;top:-7px;right:-6px;min-width:20px;height:20px;padding:0 4px;border-radius:9999px;background:radial-gradient(circle at 35% 30%,#fde68a,#f59e0b 60%,#b45309);color:#1c1917;font-style:normal;font-size:10px;font-weight:900;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(2,6,23,.6),inset 0 0 0 2px rgba(255,255,255,.55)}
.rl-chip{width:44px;height:44px;border-radius:9999px;font-weight:900;font-size:12px;color:#fff;display:inline-flex;align-items:center;justify-content:center;box-shadow:0 3px 8px rgba(2,6,23,.6),inset 0 0 0 3px rgba(248,250,252,.7);opacity:.72;transition:transform .15s ease,opacity .15s ease,box-shadow .15s ease}
.rl-chip-1{background:radial-gradient(circle at 35% 30%,rgba(255,255,255,.4),rgba(255,255,255,0) 46%),conic-gradient(#475569 0 12.5%,#f8fafc 12.5% 25%,#475569 25% 37.5%,#f8fafc 37.5% 50%,#475569 50% 62.5%,#f8fafc 62.5% 75%,#475569 75% 87.5%,#f8fafc 87.5%)}
.rl-chip-5{background:radial-gradient(circle at 35% 30%,rgba(255,255,255,.4),rgba(255,255,255,0) 46%),conic-gradient(#b91c1c 0 12.5%,#f8fafc 12.5% 25%,#b91c1c 25% 37.5%,#f8fafc 37.5% 50%,#b91c1c 50% 62.5%,#f8fafc 62.5% 75%,#b91c1c 75% 87.5%,#f8fafc 87.5%)}
.rl-chip-25{background:radial-gradient(circle at 35% 30%,rgba(255,255,255,.4),rgba(255,255,255,0) 46%),conic-gradient(#047857 0 12.5%,#f8fafc 12.5% 25%,#047857 25% 37.5%,#f8fafc 37.5% 50%,#047857 50% 62.5%,#f8fafc 62.5% 75%,#047857 75% 87.5%,#f8fafc 87.5%)}
.rl-chip-100{background:radial-gradient(circle at 35% 30%,rgba(255,255,255,.4),rgba(255,255,255,0) 46%),conic-gradient(#b45309 0 12.5%,#f8fafc 12.5% 25%,#b45309 25% 37.5%,#f8fafc 37.5% 50%,#b45309 50% 62.5%,#f8fafc 62.5% 75%,#b45309 75% 87.5%,#f8fafc 87.5%)}
.rl-chip-on{opacity:1;transform:scale(1.12);box-shadow:0 0 0 3px rgba(251,191,36,.85),0 6px 14px rgba(2,6,23,.7),inset 0 0 0 3px rgba(248,250,252,.85)}
.rl-histn{width:26px;height:26px;border-radius:9999px;font-size:10px;font-weight:900;display:inline-flex;align-items:center;justify-content:center;color:#fff;box-shadow:0 2px 6px rgba(2,6,23,.5)}
.rl-hist-zero{background:#059669}
.rl-hist-red{background:#be123c}
.rl-hist-black{background:#1e293b;border:1px solid #475569}
@media (max-width:640px){
    .rl-grid{grid-template-columns:26px repeat(12,minmax(0,1fr)) 22px;gap:2px}
    .rl-cell{font-size:9px;padding:6px 0;border-radius:4px}
    .rl-zero-v{font-size:11px}
    .rl-out{font-size:8px}
    .rl-chip{width:38px;height:38px;font-size:11px}
}'''))

# --------------------------------------------------------------------------- #
# index.html: canvas крупнее + дом колеса
# --------------------------------------------------------------------------- #
PAIRS.append(('index.html', 1,
              r'''                            <div class="relative shrink-0 mx-auto">
                                <canvas id="roulette-wheel" width="340" height="340" class="block max-w-full"></canvas>
                            </div>''',
              r'''                            <div class="relative shrink-0 mx-auto rl-wheelhouse"><!-- b489: дом колеса с тенью-свечением -->
                                <canvas id="roulette-wheel" width="420" height="420" class="block max-w-full"></canvas>
                            </div>'''))


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
        print('b489: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b489: рулетка в казино-стиле: сукно, классический стол, колесо с шариком; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
