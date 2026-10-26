        // ============ b519: СКРЕТЧ-ЛОТО — стирай фольгу как в настоящей моментальной лотерее ============
        // Билет: 4 «выигрышных числа» и 12 «ваших чисел» под серебряной фольгой.
        // Фольга стирается пальцем/мышью (canvas, destination-out); стёрто >55% — клетка вскрывается.
        // Совпало число — приз множитель ставки; золотая клетка JKP (1 из 300 билетов) срывает джекпот сайта.
        const SC_P_CELL = 0.04;   // шанс выигрышной клетки
        const SC_JP_P = 1 / 300;  // шанс золотой клетки джекпота на билет
        const SC_PRIZES = [[1, 50], [2, 30], [5, 14], [25, 5], [100, 1]]; // [множитель, вес]
        const SC_SYMS = ['fa-trophy', 'fa-star', 'fa-crown', 'fa-sack-dollar'];
        const scratch = { bet: 1000, ticket: null, revealed: null, scratching: -1, done: false, win: 0 };
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
            return { winNums: winNums, cells: cells };
        }
        function scratchSetBet(b) {
            scratch.bet = normBet(b);
            renderScratchUI();
        }
        function scratchBuy() {
            if (scratch.ticket && !scratch.done) return;
            const bet = normBet(scratch.bet);
            scratch.bet = bet;
            if (state.coins < bet) {
                try { showToast('Скретч: не хватает ' + fmtCoins(bet - state.coins) + ' монет на билет', 'error'); } catch (e) {}
                renderScratchUI();
                return;
            }
            state.coins -= bet;
            try { jackpotFeed(bet); } catch (e) {}
            scratch.ticket = scMakeTicket();
            scratch.revealed = new Array(16).fill(false);
            scratch.done = false;
            scratch.win = 0;
            saveState(); updateCoinDisplay();
            renderScratchUI();
        }
        function scCellPrize(cell) {
            if (cell.jkp) return 0;
            return cell.mult > 0 ? Math.floor(scratch.bet * cell.mult) : 0;
        }
        function scReveal(i) {
            if (!scratch.ticket || scratch.revealed[i]) return;
            scratch.revealed[i] = true;
            const cv = document.getElementById('sc-foil-' + i);
            if (cv) cv.style.display = 'none';
            const host = document.getElementById('sc-slot-' + i);
            if (host) host.classList.add('rev');
            if (scratch.revealed.every(Boolean)) scSettle();
        }
        function scSettle() {
            if (scratch.done || !scratch.ticket) return;
            scratch.done = true;
            const t = scratch.ticket;
            let win = 0, hits = 0, jp = 0;
            for (let c = 0; c < 12; c++) {
                const cell = t.cells[c];
                if (cell.jkp) {
                    try { if (!(typeof jpcOff === 'function' && jpcOff())) jp = jackpotWin() || 0; } catch (e) {}
                    try { jpcPityNote('Scratch', jp > 0); } catch (e) {}
                    continue;
                }
                if (cell.mult > 0 && t.winNums.indexOf(cell.num) >= 0) { win += scCellPrize(cell); hits++; }
            }
            if (jp > 0) {
                try { launchConfetti(220); SoundFX.play('legendary'); } catch (e) {}
                try { showToast('👑 СКРЕТЧ: золотая клетка! Джекпот сайта +' + fmtCoins(jp), 'success'); } catch (e) {}
            }
            scratch.win = win + jp;
            if (win > 0) {
                state.coins += win;
                try { launchConfetti(win >= scratch.bet * 25 ? 140 : 60); SoundFX.play('coin'); } catch (e) {}
                try { showToast('🎫 Скретч: совпадений ' + hits + ', выигрыш +' + fmtCoins(win), 'success'); } catch (e) {}
            } else if (jp <= 0) {
                try { showToast('🎫 Билет пустой. Повезёт в следующий раз!', 'refund'); } catch (e) {}
            }
            const net = scratch.win - scratch.bet;
            if (net < 0) {
                try {
                    const add = jackpotOnLoss(-net);
                    if (add) showToast('Банк джекпота вырос на +' + fmtCoins(add), 'refund');
                } catch (e) {}
            } else if (scratch.win > 0) {
                state.stats.scratchWins = (state.stats.scratchWins || 0) + 1;
            }
            saveState(); updateCoinDisplay();
            renderScratchUI();
        }
        function scEraseAll() {
            if (!scratch.ticket || scratch.done) return;
            for (let i = 0; i < 16; i++) scReveal(i);
        }
        // ---- фольга: canvas-стирание ----
        function scFoilPaint(cv) {
            try {
                const ctx = cv.getContext('2d');
                const w = cv.width, h = cv.height;
                const g = ctx.createLinearGradient(0, 0, w, h);
                g.addColorStop(0, '#e8e8ec'); g.addColorStop(.35, '#b9bcc4'); g.addColorStop(.55, '#dcdde2'); g.addColorStop(1, '#9aa0aa');
                ctx.globalCompositeOperation = 'source-over';
                ctx.fillStyle = g;
                ctx.fillRect(0, 0, w, h);
                ctx.fillStyle = 'rgba(255,255,255,.35)';
                for (let i = 0; i < 26; i++) ctx.fillRect(Math.random() * w, Math.random() * h, 2 + Math.random() * 5, 1);
                ctx.fillStyle = 'rgba(70,74,84,.35)';
                for (let i = 0; i < 18; i++) ctx.fillRect(Math.random() * w, Math.random() * h, 1 + Math.random() * 4, 1);
                ctx.fillStyle = 'rgba(90,94,104,.55)';
                ctx.font = 'bold 11px system-ui, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('СТЕРЕТЬ', w / 2, h / 2 + 4);
            } catch (e) {}
        }
        function scErase(ev, i) {
            const cv = document.getElementById('sc-foil-' + i);
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
                    if (tot && clear / tot > 0.55) scReveal(i);
                }
            } catch (e) {}
        }
        function scDown(ev, i) {
            if (!scratch.ticket || scratch.done || scratch.revealed[i]) return;
            try { ev.preventDefault(); } catch (e) {}
            scratch.scratching = i;
            scErase(ev, i);
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
        function scSlotHtml(i, inner, cls) {
            return '<div class="' + cls + '" id="sc-slot-' + i + '"><div class="sc-face">' + inner + '</div>' +
                '<canvas class="sc-foil" id="sc-foil-' + i + '" width="96" height="96" onpointerdown="scDown(event,' + i + ')"></canvas></div>';
        }
        function renderScratchUI() {
            try { syncBetInput('scratch'); } catch (e) {}
            const buy = document.getElementById('sc-buy');
            if (buy) {
                const busy = !!(scratch.ticket && !scratch.done);
                buy.classList.toggle('hidden', busy);
                buy.innerHTML = '<i class="fa-solid fa-ticket mr-1"></i>Купить билет — ' + fmtCoins(scratch.bet) + (state.coins < scratch.bet ? ' · мало ' + fmtCoins(scratch.bet - state.coins) : '');
                buy.classList.toggle('opacity-40', state.coins < scratch.bet);
            }
            const erase = document.getElementById('sc-erase');
            if (erase) erase.classList.toggle('hidden', !scratch.ticket || scratch.done);
            const res = document.getElementById('sc-result');
            if (res) res.innerHTML = !scratch.ticket
                ? 'Купите билет и стирайте фольгу пальцем или мышью: совпало число — приз множителем к ставке, золотая клетка — джекпот сайта.'
                : scratch.done
                    ? 'Билет разыгран: выигрыш <b class="text-amber-300">' + fmtCoins(scratch.win) + '</b> при ставке ' + fmtCoins(scratch.bet) + '. Купить новый?'
                    : 'Стирайте фольгу! Совпадение с выигрышными числами приносит множитель к ставке.';
            const wrap = document.getElementById('sc-ticket');
            if (!wrap) return;
            if (!scratch.ticket) {
                wrap.innerHTML = '<div class="sc-empty">Билет появится после покупки</div>';
                return;
            }
            const t = scratch.ticket;
            let html = '<div class="sc-head"><span class="sc-brand">СКРЕТЧ-ЛОТО</span><span class="sc-price">' + fmtCoins(scratch.bet) + '</span></div>';
            html += '<div class="sc-super">СУПЕРПРИЗ</div><div class="sc-super-val" id="sc-jp">0</div>';
            html += '<div class="sc-cap">ВЫИГРЫШНЫЕ ЧИСЛА</div><div class="sc-winrow">';
            for (let i = 0; i < 4; i++) html += scSlotHtml(i, '<span class="sc-ball-n">' + t.winNums[i] + '</span>', 'sc-wslot');
            html += '</div><div class="sc-cap">ВАШИ ЧИСЛА</div><div class="sc-grid">';
            for (let c = 0; c < 12; c++) {
                const cell = t.cells[c];
                const prize = scCellPrize(cell);
                const inner = cell.jkp
                    ? '<i class="fa-solid fa-crown sc-sym gold"></i><span class="sc-num">JKP</span><span class="sc-prize gold">ДЖЕКПОТ</span>'
                    : '<i class="fa-solid ' + cell.sym + ' sc-sym"></i><span class="sc-num">' + cell.num + '</span><span class="sc-prize' + (prize > 0 ? ' win' : '') + '">' + (prize > 0 ? '+' + fmtCoins(prize) : '—') + '</span>';
                html += scSlotHtml(4 + c, inner, 'sc-cell' + (cell.jkp ? ' jkp' : ''));
            }
            html += '</div>';
            wrap.innerHTML = html;
            for (let i = 0; i < 16; i++) {
                const cv = document.getElementById('sc-foil-' + i);
                if (cv) scFoilPaint(cv);
                if (scratch.revealed[i]) { if (cv) cv.style.display = 'none'; const host = document.getElementById('sc-slot-' + i); if (host) host.classList.add('rev'); }
            }
            try {
                const sj = document.getElementById('sc-jp');
                if (sj) sj.textContent = fmtCoins(jackpotPool());
            } catch (e) {}
        }
        function renderScratch() { renderScratchUI(); }
        // ============ /b519 ============
