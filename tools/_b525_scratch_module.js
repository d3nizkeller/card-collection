        // ============ b519: СКРЕТЧ-ЛОТО — стирай фольгу как в настоящей моментальной лотерее ============
        // b525: до 4 билетов за покупку (каждый стоит ставку), билеты лежат сеткой 2×2,
        // каждый билет разыгрывается и рассчитывается независимо.
        // Билет: 4 «выигрышных числа» и 12 «ваших чисел» под серебряной фольгой.
        // Фольга стирается пальцем/мышью (canvas, destination-out); стёрто >55% — клетка вскрывается.
        // Совпало число — приз множитель ставки; золотая клетка JKP (1 из 300 билетов) срывает джекпот сайта.
        const SC_P_CELL = 0.04;   // шанс выигрышной клетки
        const SC_JP_P = 1 / 300;  // шанс золотой клетки джекпота на билет
        const SC_MAX_TICKETS = 4; // b525: максимум билетов в покупке
        const SC_PRIZES = [[1, 50], [2, 30], [5, 14], [25, 5], [100, 1]]; // [множитель, вес]
        const SC_SYMS = ['fa-trophy', 'fa-star', 'fa-crown', 'fa-sack-dollar'];
        const scratch = { bet: 1000, count: 1, tickets: [], scratching: -1 };
        try { scratch.count = Math.max(1, Math.min(SC_MAX_TICKETS, parseInt(LS.getItem('nx_sc_count'), 10) || 1)); } catch (e) {}
        function scMultPick() {
            let sum = 0;
            for (let i = 0; i < SC_PRIZES.length; i++) sum += SC_PRIZES[i][1];
            let r = Math.random() * sum;
            for (let i = 0; i < SC_PRIZES.length; i++) { r -= SC_PRIZES[i][1]; if (r <= 0) return SC_PRIZES[i][0]; }
            return 1;
        }
        function scMakeTicket() {
            const pool = [];
            for (let v = 1; v <= 30; v++) pool.push(v);
            for (let i = pool.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); const t = pool[i]; pool[i] = pool[j]; pool[j] = t; }
            const winNums = pool.slice(0, 4);
            const rest = pool.slice(4);
            const cells = [];
            for (let c = 0; c < 12; c++) {
                const isWin = Math.random() < SC_P_CELL;
                if (isWin) {
                    cells.push({ num: winNums[Math.floor(Math.random() * 4)], mult: scMultPick(), sym: SC_SYMS[Math.floor(Math.random() * SC_SYMS.length)], jkp: false });
                } else {
                    cells.push({ num: rest[Math.floor(Math.random() * rest.length)], mult: 0, sym: SC_SYMS[Math.floor(Math.random() * SC_SYMS.length)], jkp: false });
                }
            }
            if (Math.random() < SC_JP_P) { // золотая клетка джекпота
                const k = Math.floor(Math.random() * 12);
                cells[k] = { num: winNums[0], mult: 0, sym: 'fa-crown', jkp: true };
            }
            return { winNums: winNums, cells: cells, serial: 'NX-' + (100000 + Math.floor(Math.random() * 900000)), revealed: new Array(16).fill(false), done: false, win: 0 };
        }
        function scratchSetBet(b) {
            scratch.bet = normBet(b);
            renderScratchUI();
        }
        function scSetCount(n) { // b525: сколько билетов купить
            if (scActive()) return;
            scratch.count = Math.max(1, Math.min(SC_MAX_TICKETS, Math.floor(Number(n) || 1)));
            try { LS.setItem('nx_sc_count', String(scratch.count)); } catch (e) {}
            renderScratchUI();
        }
        function scActive() {
            return scratch.tickets.some(function (t) { return !t.done; });
        }
        function scratchBuy() {
            if (scActive()) return;
            const bet = normBet(scratch.bet);
            scratch.bet = bet;
            const cost = bet * scratch.count; // b525: каждый билет стоит ставку
            if (state.coins < cost) {
                try { showToast('Скретч: не хватает ' + fmtCoins(cost - state.coins) + ' монет на ' + scratch.count + ' билет(ов)', 'error'); } catch (e) {}
                renderScratchUI();
                return;
            }
            state.coins -= cost;
            try { jackpotFeed(cost); } catch (e) {}
            scratch.tickets = [];
            for (let k = 0; k < scratch.count; k++) scratch.tickets.push(scMakeTicket());
            saveState(); updateCoinDisplay();
            renderScratchUI();
        }
        function scCellPrize(cell) {
            if (cell.jkp) return 0;
            return cell.mult > 0 ? Math.floor(scratch.bet * cell.mult) : 0;
        }
        function scReveal(t, i) {
            const T = scratch.tickets[t];
            if (!T || T.revealed[i]) return;
            T.revealed[i] = true;
            const cv = document.getElementById('sc-foil-' + t + '-' + i);
            if (cv) cv.style.display = 'none';
            const host = document.getElementById('sc-slot-' + t + '-' + i);
            if (host) {
                host.classList.add('rev');
                if (i >= 4) { // b520: подсветка призовых клеток после вскрытия
                    const cell = T.cells[i - 4];
                    if (cell.jkp) host.classList.add('jp');
                    else if (scCellPrize(cell) > 0) host.classList.add('win');
                }
            }
            if (T.revealed.every(Boolean)) scSettleTicket(t);
        }
        function scSettleTicket(t) { // b525: каждый билет рассчитывается независимо
            const T = scratch.tickets[t];
            if (!T || T.done) return;
            T.done = true;
            let win = 0, hits = 0, jp = 0;
            for (let c = 0; c < 12; c++) {
                const cell = T.cells[c];
                if (cell.jkp) {
                    try { if (!(typeof jpcOff === 'function' && jpcOff())) jp = jackpotWin() || 0; } catch (e) {}
                    try { jpcPityNote('Scratch', jp > 0); } catch (e) {}
                    continue;
                }
                if (cell.mult > 0 && T.winNums.indexOf(cell.num) >= 0) { win += scCellPrize(cell); hits++; }
            }
            T.win = win + jp;
            if (jp > 0) {
                try { launchConfetti(220); SoundFX.play('legendary'); } catch (e) {}
                try { showToast('👑 Скретч, билет ' + (t + 1) + ': золотая клетка! Джекпот +' + fmtCoins(jp), 'success'); } catch (e) {}
            }
            if (win > 0) {
                state.coins += win;
                try { launchConfetti(win >= scratch.bet * 25 ? 140 : 60); SoundFX.play('coin'); } catch (e) {}
                try { showToast('🎫 Билет ' + (t + 1) + ': совпадений ' + hits + ', выигрыш +' + fmtCoins(win), 'success'); } catch (e) {}
            } else if (jp <= 0) {
                try { showToast('🎫 Билет ' + (t + 1) + ' пустой. Повезёт в следующий раз!', 'refund'); } catch (e) {}
            }
            const net = T.win - scratch.bet;
            if (net < 0) {
                try {
                    const add = jackpotOnLoss(-net);
                    if (add && t === 0) showToast('Банк джекпота вырос на +' + fmtCoins(add), 'refund');
                } catch (e) {}
            } else if (T.win > 0) {
                state.stats.scratchWins = (state.stats.scratchWins || 0) + 1;
            }
            saveState(); updateCoinDisplay();
            renderScratchUI();
        }
        function scEraseAll() {
            if (!scratch.tickets.length) return;
            for (let t = 0; t < scratch.tickets.length; t++) {
                for (let i = 0; i < 16; i++) scReveal(t, i);
            }
        }
        // ---- фольга: canvas-стирание ----
        function scFoilPaint(cv) {
            try {
                const ctx = cv.getContext('2d');
                const w = cv.width, h = cv.height;
                ctx.globalCompositeOperation = 'source-over';
                // b522: гладкий металл без полос: мягкие вертикальные переходы + центральный блик
                const g = ctx.createLinearGradient(0, 0, 0, h);
                g.addColorStop(0, '#e3e7ed'); g.addColorStop(.18, '#c2c8d2'); g.addColorStop(.38, '#eef1f5');
                g.addColorStop(.55, '#b7bdc9'); g.addColorStop(.75, '#e2e6ec'); g.addColorStop(1, '#aab0bc');
                ctx.fillStyle = g;
                ctx.fillRect(0, 0, w, h);
                const rg = ctx.createRadialGradient(w * .32, h * .26, 4, w * .5, h * .5, w * .85);
                rg.addColorStop(0, 'rgba(255,255,255,.6)'); rg.addColorStop(1, 'rgba(255,255,255,0)');
                ctx.fillStyle = rg;
                ctx.fillRect(0, 0, w, h);
                ctx.fillStyle = 'rgba(255,255,255,.55)'; // тонкая светлая кромка
                ctx.fillRect(0, 0, w, 1.5); ctx.fillRect(0, 0, 1.5, h);
                ctx.fillStyle = 'rgba(90,96,110,.35)';
                ctx.fillRect(0, h - 1.5, w, 1.5); ctx.fillRect(w - 1.5, 0, 1.5, h);
                for (let i = 0; i < 60; i++) { // мелкое зерно металла
                    ctx.fillStyle = i % 2 ? 'rgba(255,255,255,.12)' : 'rgba(70,76,90,.12)';
                    ctx.fillRect(Math.random() * w, Math.random() * h, 1, 1);
                }
                // тиснение «СТЕРЕТЬ»: светлый слой выше, тёмный ниже
                try { ctx.letterSpacing = '3px'; } catch (e) {}
                ctx.font = 'bold 10px system-ui, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillStyle = 'rgba(255,255,255,.8)';
                ctx.fillText('СТЕРЕТЬ', w / 2, h / 2 + 2);
                ctx.fillStyle = 'rgba(70,76,90,.75)';
                ctx.fillText('СТЕРЕТЬ', w / 2, h / 2 + 3.5);
            } catch (e) {}
        }
        function scErase(ev, idx) {
            const t = Math.floor(idx / 16), i = idx % 16;
            const cv = document.getElementById('sc-foil-' + t + '-' + i);
            if (!cv || !cv.getContext) return;
            try {
                const rect = cv.getBoundingClientRect();
                if (!rect.width) return;
                const x = (ev.clientX - rect.left) * cv.width / rect.width;
                const y = (ev.clientY - rect.top) * cv.height / rect.height;
                const ctx = cv.getContext('2d');
                ctx.globalCompositeOperation = 'destination-out';
                ctx.beginPath();
                ctx.arc(x, y, 13, 0, Math.PI * 2);
                ctx.fill();
                cv._mv = (cv._mv || 0) + 1;
                if (cv._mv % 6 === 0) {
                    const d = ctx.getImageData(0, 0, cv.width, cv.height).data;
                    let clear = 0, tot = 0;
                    for (let p = 3; p < d.length; p += 16) { tot++; if (d[p] < 40) clear++; }
                    if (tot && clear / tot > 0.55) scReveal(t, i);
                }
            } catch (e) {}
        }
        function scDown(ev, idx) {
            const t = Math.floor(idx / 16), i = idx % 16;
            const T = scratch.tickets[t];
            if (!T || T.done || T.revealed[i]) return;
            try { ev.preventDefault(); } catch (e) {}
            scratch.scratching = idx;
            scErase(ev, idx);
        }
        function scMove(ev) {
            if (scratch.scratching < 0) return;
            scErase(ev, scratch.scratching);
        }
        function scUp() { scratch.scratching = -1; }
        try {
            window.addEventListener('pointermove', scMove);
            window.addEventListener('pointerup', scUp);
            window.addEventListener('pointercancel', scUp);
        } catch (e) {}
        // ---- рендер ----
        function scSlotHtml(t, i, inner, cls) {
            const idx = t * 16 + i;
            return '<div class="' + cls + '" id="sc-slot-' + t + '-' + i + '"><div class="sc-face">' + inner + '</div>' +
                '<canvas class="sc-foil" id="sc-foil-' + t + '-' + i + '" width="96" height="96" onpointerdown="scDown(event,' + idx + ')"></canvas></div>';
        }
        function scTicketHtml(t) {
            const T = scratch.tickets[t];
            let html = '<div class="sc-ticket">';
            html += '<div class="sc-notch l"></div><div class="sc-notch r"></div>';
            html += '<div class="sc-head"><span class="sc-brand"><i class="fa-solid fa-crown sc-brand-i"></i>СКРЕТЧ-ЛОТО · ' + (t + 1) + '</span><span class="sc-price">' + fmtCoins(scratch.bet) + '</span></div>';
            html += '<div class="sc-super">СУПЕРПРИЗ</div><div class="sc-super-val sc-jp-val"' + (t === 0 ? ' id="sc-jp"' : '') + '>0</div>';
            html += '<div class="sc-cap">ВЫИГРЫШНЫЕ ЧИСЛА</div><div class="sc-winrow">';
            for (let i = 0; i < 4; i++) html += scSlotHtml(t, i, '<span class="sc-ball-n">' + T.winNums[i] + '</span>', 'sc-wslot');
            html += '</div><div class="sc-cap">ВАШИ ЧИСЛА</div><div class="sc-grid">';
            for (let c = 0; c < 12; c++) {
                const cell = T.cells[c];
                const prize = scCellPrize(cell);
                const inner = cell.jkp
                    ? '<i class="fa-solid fa-crown sc-sym gold"></i><span class="sc-num">JKP</span><span class="sc-prize gold">ДЖЕКПОТ</span>'
                    : '<i class="fa-solid ' + cell.sym + ' sc-sym"></i><span class="sc-num">' + cell.num + '</span><span class="sc-prize' + (prize > 0 ? ' win' : '') + '">' + (prize > 0 ? '+' + fmtCoins(prize) : '—') + '</span>';
                html += scSlotHtml(t, 4 + c, inner, 'sc-cell' + (cell.jkp ? ' jkp' : ''));
            }
            html += '</div>';
            html += '<div class="sc-foot"><span class="sc-barcode" aria-hidden="true"></span><span class="sc-serial">' + (T.serial || '') + '</span></div>';
            html += '</div>';
            return html;
        }
        function renderScratchUI() {
            try { syncBetInput('scratch'); } catch (e) {}
            // b525: выбор числа билетов
            const cnt = document.getElementById('sc-count');
            if (cnt) cnt.innerHTML = [1, 2, 3, 4].map(function (v) {
                return '<button type="button" onclick="scSetCount(' + v + ')" title="Билетов в покупке: ' + v + ' (каждый стоит ставку)" class="px-3 py-1.5 rounded-full text-[11px] font-bold border transition shrink-0 whitespace-nowrap ' + (scratch.count === v ? 'bg-violet-500 border-violet-400 text-white' : 'bg-slate-800/80 border-slate-700 text-slate-300 hover:bg-slate-700') + '" ' + (scActive() ? 'disabled' : '') + '>' + v + '</button>';
            }).join('');
            const cost = scratch.bet * scratch.count;
            const buy = document.getElementById('sc-buy');
            if (buy) {
                buy.classList.toggle('hidden', scActive());
                buy.innerHTML = '<i class="fa-solid fa-ticket mr-1"></i>Купить билеты: ' + scratch.count + ' — ' + fmtCoins(cost) + (state.coins < cost ? ' · мало ' + fmtCoins(cost - state.coins) : '');
                buy.classList.toggle('opacity-40', state.coins < cost);
            }
            const erase = document.getElementById('sc-erase');
            if (erase) erase.classList.toggle('hidden', !scActive());
            const res = document.getElementById('sc-result');
            if (res) {
                if (!scratch.tickets.length) {
                    res.innerHTML = 'Купите от 1 до 4 билетов и стирайте фольгу пальцем или мышью: совпало число — приз множителем к ставке, золотая клетка — джекпот сайта.';
                } else if (scActive()) {
                    res.innerHTML = 'Стирайте фольгу! Билетов в тираже: <b class="text-slate-200">' + scratch.tickets.length + '</b>, ставка каждого: <b class="text-slate-200">' + fmtCoins(scratch.bet) + '</b>.';
                } else {
                    const total = scratch.tickets.reduce(function (a, T) { return a + T.win; }, 0);
                    res.innerHTML = 'Все билеты разыграны: выигрыш <b class="text-amber-300">' + fmtCoins(total) + '</b> при затраченных ' + fmtCoins(cost) + '. Купить ещё?';
                }
            }
            const wrap = document.getElementById('sc-tickets');
            if (!wrap) return;
            if (!scratch.tickets.length) {
                wrap.innerHTML = '<div class="sc-ticket"><div class="sc-empty">Билеты появятся после покупки</div></div>';
                return;
            }
            let html = '';
            for (let t = 0; t < scratch.tickets.length; t++) html += scTicketHtml(t);
            wrap.innerHTML = html;
            for (let t = 0; t < scratch.tickets.length; t++) {
                const T = scratch.tickets[t];
                for (let i = 0; i < 16; i++) {
                    const cv = document.getElementById('sc-foil-' + t + '-' + i);
                    if (cv && !T.revealed[i]) scFoilPaint(cv);
                    if (cv && T.revealed[i]) cv.style.display = 'none';
                    if (T.revealed[i]) {
                        const host = document.getElementById('sc-slot-' + t + '-' + i);
                        if (host) {
                            host.classList.add('rev');
                            if (i >= 4) {
                                const cell = T.cells[i - 4];
                                if (cell.jkp) host.classList.add('jp');
                                else if (scCellPrize(cell) > 0) host.classList.add('win');
                            }
                        }
                    }
                }
            }
            try {
                const vals = document.querySelectorAll('.sc-jp-val');
                for (let k = 0; k < vals.length; k++) vals[k].textContent = fmtCoins(jackpotPool());
            } catch (e) {}
        }
        function renderScratch() { renderScratchUI(); }
        // ============ /b519 ============
