        // ============ b500: РУССКОЕ ЛОТО — мешок бочонков, карточки, голосовая озвучка ============
        // b505: игрок сам выбирает, сколько карточек купить на тираж (1–4): каждая карточка
        // стоит ставку, каждая играет независимо (линия ×3, ЛОТО ×25 за карточку).
        // Механика: ставка списывается за каждую карточку; тираж = 60 бочонков из мешка 1–90.
        // Каждый бочонок показывается деревянным цилиндром с красным номером и
        // ОЗВУЧИВАЕТСЯ (Web Speech API, ru-RU): «сорок пять», «восемьдесят девять»…
        // Чистый проигрыш раунда кормит общий джекпот сайта, как в других играх.
        const LOTO_DRAWS = 60;      // бочонков за тираж (из 90)
        const LOTO_PAY_ROW = 3;     // линия закрыта — ставка ×3
        const LOTO_PAY_FULL = 25;   // «ЛОТО!» (все 15) — ставка ×25
        const LOTO_MAX_TICKETS = 4; // b505: максимум карточек в тираже
        const loto = { bet: 1000, tickets: 1, voice: true, active: false, bag: [], drawn: [], cards: [], auto: 0, last: [], win: 0 };
        try { if (LS.getItem('nx_loto_voice') === '0') loto.voice = false; } catch (e) {}
        try { loto.tickets = Math.max(1, Math.min(LOTO_MAX_TICKETS, parseInt(LS.getItem('nx_loto_tickets'), 10) || 1)); } catch (e) {}
        const LOTO_ONES = ['', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять'];
        const LOTO_TEENS = ['десять', 'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать', 'пятнадцать', 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать'];
        const LOTO_TENS = ['', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят', 'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто'];
        function lotoWords(n) {
            n = Math.floor(Number(n));
            if (!isFinite(n) || n < 1 || n > 99) return String(n);
            if (n < 10) return LOTO_ONES[n];
            if (n < 20) return LOTO_TEENS[n - 10];
            const t = Math.floor(n / 10), o = n % 10;
            return o ? LOTO_TENS[t] + ' ' + LOTO_ONES[o] : LOTO_TENS[t];
        }
        function lotoSpeak(text, cancel) {
            if (!loto.voice || !text) return;
            try {
                if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
                const u = new SpeechSynthesisUtterance(text);
                u.lang = 'ru-RU'; u.rate = 1.05; u.pitch = 1.08; u.volume = 1;
                const vs = window.speechSynthesis.getVoices ? (window.speechSynthesis.getVoices() || []) : [];
                for (let i = 0; i < vs.length; i++) { if (vs[i] && /^ru/i.test(vs[i].lang || '')) { u.voice = vs[i]; break; } }
                if (cancel !== false) window.speechSynthesis.cancel();
                window.speechSynthesis.speak(u);
            } catch (e) {}
        }
        function lotoSetBet(b) {
            loto.bet = normBet(b);
            renderLotoUI();
        }
        function lotoSetTickets(n) { // b505: выбор числа карточек на тираж
            if (loto.active) return;
            loto.tickets = Math.max(1, Math.min(LOTO_MAX_TICKETS, Math.floor(Number(n) || 1)));
            try { LS.setItem('nx_loto_tickets', String(loto.tickets)); } catch (e) {}
            renderLotoUI();
        }
        function lotoToggleVoice() {
            loto.voice = !loto.voice;
            try { LS.setItem('nx_loto_voice', loto.voice ? '1' : '0'); } catch (e) {}
            if (!loto.voice) { try { window.speechSynthesis.cancel(); } catch (e) {} }
            else lotoSpeak('Озвучка включена');
            renderLotoUI();
        }
        // Классическая карточка 3×9: в каждой строке 5 чисел, колонка c — диапазон
        // 1–9, 10–19, …, 80–90; числа в колонке растут сверху вниз.
        function lotoMakeCard() {
            const pat = [[0, 1], [0, 1], [0, 2], [0, 2], [1, 2], [1, 2], [0], [1], [2]];
            for (let i = pat.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); const t = pat[i]; pat[i] = pat[j]; pat[j] = t; }
            const grid = [[0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0]];
            for (let c = 0; c < 9; c++) {
                const lo = c === 0 ? 1 : c * 10, hi = c === 8 ? 90 : c * 10 + 9;
                const pool = [];
                for (let v = lo; v <= hi; v++) pool.push(v);
                for (let i = pool.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); const t = pool[i]; pool[i] = pool[j]; pool[j] = t; }
                const rows = pat[c].slice().sort();
                const pick = pool.slice(0, rows.length).sort(function (x, y) { return x - y; });
                for (let k = 0; k < rows.length; k++) grid[rows[k]][c] = pick[k];
            }
            return grid;
        }
        function lotoMakeTicket() { // b505: одна карточка игрока со своим состоянием
            return {
                grid: lotoMakeCard(),
                marked: [[false, false, false, false, false, false, false, false, false], [false, false, false, false, false, false, false, false, false], [false, false, false, false, false, false, false, false, false]],
                rowDone: [false, false, false],
                rowPaid: [false, false, false],
                fullPaid: false
            };
        }
        function lotoStart() {
            if (loto.active) return;
            const bet = normBet(loto.bet);
            loto.bet = bet;
            const cost = bet * loto.tickets; // b505: каждая карточка стоит ставку
            if (state.coins < cost) {
                try { showToast('Лото: не хватает ' + fmtCoins(cost - state.coins) + ' монет на ' + loto.tickets + ' карточ.', 'error'); } catch (e) {}
                renderLotoUI();
                return;
            }
            state.coins -= cost;
            try { jackpotFeed(cost); } catch (e) {} // b71: старт раунда кормит общий банк, как в других играх
            const bag = [];
            for (let v = 1; v <= 90; v++) bag.push(v);
            for (let i = bag.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); const t = bag[i]; bag[i] = bag[j]; bag[j] = t; }
            loto.bag = bag;
            loto.drawn = []; loto.last = []; loto.win = 0;
            loto.cards = [];
            for (let k = 0; k < loto.tickets; k++) loto.cards.push(lotoMakeTicket());
            loto.active = true;
            lotoStopAuto(false);
            saveState(); updateCoinDisplay();
            lotoSpeak('Новая игра! Куплено карточек: ' + loto.tickets + '. Тяните бочонки.');
            lotoRenderStage(null, 'Мешок перемешан: 90 бочонков, карточек в тираже: ' + loto.tickets + '. Тяните первый!');
            renderLotoUI();
        }
        function lotoRowComplete(card, r) {
            for (let c = 0; c < 9; c++) { if (card.grid[r][c] && !card.marked[r][c]) return false; }
            return true;
        }
        function lotoDraw() {
            if (!loto.active) return;
            const n = loto.bag.length ? loto.bag.pop() : null;
            if (n == null) { lotoFinish(false); return; }
            loto.drawn.push(n);
            loto.last.push(n);
            if (loto.last.length > 12) loto.last.shift();
            let hit = false;
            for (let k = 0; k < loto.cards.length; k++) {
                const card = loto.cards[k];
                for (let r = 0; r < 3; r++) for (let c = 0; c < 9; c++) {
                    if (card.grid[r][c] === n) { card.marked[r][c] = true; hit = true; }
                }
            }
            // b500: озвучка выпавшего номера — главное требование игры
            lotoSpeak(lotoWords(n) + (hit ? '! Есть на карточке.' : '.'));
            let lines = 0, fulls = 0, msg = '';
            for (let k = 0; k < loto.cards.length; k++) {
                const card = loto.cards[k];
                for (let r = 0; r < 3; r++) {
                    if (!card.rowDone[r] && lotoRowComplete(card, r)) {
                        card.rowDone[r] = true;
                        if (!card.rowPaid[r]) {
                            card.rowPaid[r] = true;
                            lines++;
                            const pay = Math.floor(loto.bet * LOTO_PAY_ROW);
                            state.coins += pay; loto.win += pay;
                            msg = 'Билет ' + (k + 1) + ': линия ' + (r + 1) + ' закрыта! +' + fmtCoins(pay);
                        }
                    }
                }
                if (!card.fullPaid && card.rowDone[0] && card.rowDone[1] && card.rowDone[2]) {
                    card.fullPaid = true;
                    fulls++;
                    const pay = Math.floor(loto.bet * LOTO_PAY_FULL);
                    state.coins += pay; loto.win += pay;
                    msg = 'Билет ' + (k + 1) + ': ЛОТО! Все 15 чисел! +' + fmtCoins(pay);
                }
            }
            if (lines || fulls) {
                try { showToast(fulls ? '🎉 ЛОТО на билете! +' + fmtCoins(loto.win) : '🪵 Линия закрыта! Раунд: +' + fmtCoins(loto.win), 'success'); } catch (e) {}
                try { launchConfetti(fulls ? 160 : 60); SoundFX.play(fulls ? 'legendary' : 'coin'); } catch (e) {}
                lotoSpeak(fulls ? 'Лото! Все пятнадцать чисел закрыты!' : 'Линия закрыта!', false);
            }
            const allFull = loto.cards.length > 0 && loto.cards.every(function (cd) { return cd.fullPaid; });
            if (allFull) {
                loto.active = false;
                msg = (msg ? msg + ' • ' : '') + 'Все карточки закрыты — тираж окончен!';
            } else if (loto.drawn.length >= LOTO_DRAWS) {
                loto.active = false;
                msg = (msg ? msg + ' • ' : '') + 'Тираж окончен: 60 бочонков разыграны.';
                lotoSpeak('Тираж окончен', false);
            }
            if (!loto.active) lotoSettle();
            lotoRenderStage(n, msg || (hit ? 'Бочонок ' + n + ' — есть на карточке!' : 'Бочонок ' + n + ' — мимо карточек.'));
            saveState(); updateCoinDisplay();
            renderLotoUI();
        }
        function lotoSettle() {
            lotoStopAuto(false);
            const cost = loto.bet * loto.cards.length;
            const net = loto.win - cost;
            if (net < 0) {
                try {
                    const add = jackpotOnLoss(-net); // b71: проигрыш кормит общий джекпот сайта
                    if (add) showToast('Банк джекпота вырос на +' + fmtCoins(add) + ' и теперь ' + fmtCoins(jackpotPool()), 'refund');
                } catch (e) {}
            } else if (loto.win > 0) {
                state.stats.lotoWins = (state.stats.lotoWins || 0) + 1;
            }
            saveState(); updateCoinDisplay();
        }
        function lotoFinish(manual) {
            if (!loto.active) return;
            loto.active = false;
            lotoSettle();
            const done = loto.drawn.length;
            lotoRenderStage(null, manual ? 'Тираж остановлен на ' + done + ' бочонках. Выигрыш раунда: ' + fmtCoins(loto.win) + '.' : 'Тираж окончен. Выигрыш раунда: ' + fmtCoins(loto.win) + '.');
            if (manual) lotoSpeak('Тираж остановлен', false);
            renderLotoUI();
        }
        function lotoToggleAuto() {
            if (!loto.active) return;
            if (loto.auto) { lotoStopAuto(true); return; }
            loto.auto = setInterval(function () {
                try { if (loto.active) lotoDraw(); else lotoStopAuto(true); } catch (e) { lotoStopAuto(false); }
            }, 3400);
            renderLotoUI();
        }
        function lotoStopAuto(ui) {
            if (loto.auto) { try { clearInterval(loto.auto); } catch (e) {} loto.auto = 0; }
            if (ui) renderLotoUI();
        }
        function lotoBarrelHtml(n, mini) {
            return '<div class="loto-barrel' + (mini ? ' mini' : '') + '"><div class="lb-body"></div><div class="lb-cap">' + n + '</div></div>';
        }
        function lotoRenderStage(n, phrase) {
            const cur = document.getElementById('loto-current');
            if (cur) cur.innerHTML = n == null ? '<div class="loto-barrel ghost"><div class="lb-body"></div><div class="lb-cap">?</div></div>' : lotoBarrelHtml(n, false).replace('loto-barrel', 'loto-barrel loto-drop');
            const ph = document.getElementById('loto-phrase');
            if (ph) ph.textContent = phrase || '';
            const bl = document.getElementById('loto-bag-left');
            if (bl) bl.textContent = loto.active ? loto.bag.length : 90;
            const last = document.getElementById('loto-last');
            if (last) last.innerHTML = loto.last.slice().reverse().map(function (v) { return lotoBarrelHtml(v, true); }).join('');
        }
        function renderLotoUI() {
            try { syncBetInput('loto'); } catch (e) {}
            // b505: выбор числа карточек на тираж
            const tk = document.getElementById('loto-tickets');
            if (tk) tk.innerHTML = [1, 2, 3, 4].map(function (v) {
                return '<button type="button" onclick="lotoSetTickets(' + v + ')" title="Карточек в тираже: ' + v + ' (каждая стоит ставку)" class="px-3 py-1.5 rounded-full text-[11px] font-bold border transition shrink-0 whitespace-nowrap ' + (loto.tickets === v ? 'bg-amber-500 border-amber-400 text-slate-950' : 'bg-slate-800/80 border-slate-700 text-slate-300 hover:bg-slate-700') + '" ' + (loto.active ? 'disabled' : '') + '>' + v + '</button>';
            }).join('');
            const cost = loto.bet * loto.tickets;
            const start = document.getElementById('loto-start');
            if (start) {
                start.classList.toggle('hidden', loto.active);
                start.innerHTML = '<i class="fa-solid fa-play mr-1"></i>Новая игра — ' + fmtCoins(cost) + (state.coins < cost ? ' · мало ' + fmtCoins(cost - state.coins) : '');
                start.classList.toggle('opacity-40', state.coins < cost);
            }
            const draw = document.getElementById('loto-draw');
            if (draw) {
                draw.classList.toggle('hidden', !loto.active);
                draw.innerHTML = '<i class="fa-solid fa-hand-pointer mr-1"></i>Достать бочонок (' + Math.max(0, LOTO_DRAWS - loto.drawn.length) + ')';
            }
            const auto = document.getElementById('loto-auto');
            if (auto) {
                auto.classList.toggle('hidden', !loto.active);
                auto.innerHTML = loto.auto ? '<i class="fa-solid fa-pause mr-1"></i>Авто: ВКЛ' : '<i class="fa-solid fa-play mr-1"></i>Авто: выкл';
                auto.classList.toggle('bg-amber-500', !!loto.auto);
                auto.classList.toggle('text-slate-950', !!loto.auto);
                auto.classList.toggle('border-amber-400', !!loto.auto);
            }
            const voice = document.getElementById('loto-voice');
            if (voice) voice.innerHTML = loto.voice ? '<i class="fa-solid fa-volume-up mr-1"></i>Озвучка: вкл' : '<i class="fa-solid fa-volume-xmark mr-1"></i>Озвучка: выкл';
            const stop = document.getElementById('loto-stop');
            if (stop) stop.classList.toggle('hidden', !loto.active);
            let markedCount = 0, totalCells = 0;
            for (let k = 0; k < loto.cards.length; k++) for (let r = 0; r < 3; r++) for (let c = 0; c < 9; c++) {
                if (loto.cards[k].grid[r][c]) { totalCells++; if (loto.cards[k].marked[r][c]) markedCount++; }
            }
            const res = document.getElementById('loto-result');
            if (res) res.innerHTML = loto.active
                ? 'Тираж: <b class="text-slate-200">' + loto.drawn.length + '/' + LOTO_DRAWS + '</b> • карточек: <b class="text-slate-200">' + loto.cards.length + '</b> • закрыто <b class="text-slate-200">' + markedCount + '/' + totalCells + '</b> • выигрыш раунда: <b class="text-amber-300">' + fmtCoins(loto.win) + '</b>'
                : 'Выберите ставку и число карточек (1–4, каждая стоит ставку) и жмите «Новая игра» — голос озвучит каждый бочонок. Линия ×' + LOTO_PAY_ROW + ', все 15 чисел ×' + LOTO_PAY_FULL + '.';
            // карточки игрока
            const wrap = document.getElementById('loto-cards');
            if (wrap) {
                if (!loto.cards.length) {
                    wrap.innerHTML = '<p class="text-xs text-slate-500 text-center">Карточки появятся после «Новой игры».</p>';
                } else {
                    let html = '';
                    for (let k = 0; k < loto.cards.length; k++) {
                        const card = loto.cards[k];
                        const doneRows = card.rowDone.filter(Boolean).length;
                        html += '<div class="loto-ticket">';
                        html += '<div class="loto-ticket-head"><span><i class="fa-solid fa-ticket mr-1"></i>Билет ' + (k + 1) + '</span><span>' + (card.fullPaid ? '<b class="loto-stamp-full">ЛОТО ×' + LOTO_PAY_FULL + '</b>' : doneRows ? '<b class="loto-stamp-row">линий: ' + doneRows + ' ×' + LOTO_PAY_ROW + '</b>' : '<span class="text-slate-500">в игре</span>') + '</span></div>';
                        html += '<div class="loto-card">';
                        for (let r = 0; r < 3; r++) {
                            html += '<div class="loto-card-row' + (card.rowDone[r] ? ' row-done' : '') + '">';
                            for (let c = 0; c < 9; c++) {
                                const v = card.grid[r][c];
                                if (!v) html += '<div class="loto-cell empty"></div>';
                                else html += '<div class="loto-cell' + (card.marked[r][c] ? ' marked' : '') + '">' + v + '</div>';
                            }
                            html += '</div>';
                        }
                        html += '</div></div>';
                    }
                    wrap.innerHTML = html;
                }
            }
            // табло 1–90
            const board = document.getElementById('loto-board');
            if (board) {
                let html = '';
                const cur = loto.drawn.length ? loto.drawn[loto.drawn.length - 1] : 0;
                for (let v = 1; v <= 90; v++) {
                    const on = loto.drawn.indexOf(v) >= 0;
                    html += '<div class="loto-bcell' + (on ? ' on' : '') + (v === cur ? ' cur' : '') + '">' + v + '</div>';
                }
                board.innerHTML = html;
            }
        }
        function renderLoto() { renderLotoUI(); lotoRenderStage(loto.drawn.length ? loto.drawn[loto.drawn.length - 1] : null, loto.active ? 'Тираж идёт: достаньте бочонок.' : 'Нажмите «Новая игра», чтобы купить карточки.'); }
        // ============ /b500 ============
