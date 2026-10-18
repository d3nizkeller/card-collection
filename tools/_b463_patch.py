#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b463: админка, пароль Студии и вся экономика перенесены на сервер.

Жалоба владельца: «админка, пароль Студии и баланс лежат в публичном
клиентском коде — любой игрок может подменить баланс или объявить себя
победителем джекпота». Так и было: пароль комнаты хэшировался и сравнивался
в браузере, админ-действия (обнулить/заблокировать/поставить банк/выдать всем)
писали прямо в общий облачный документ, а баланс вообще жил в localStorage
и лишь зеркалился в облако.

ЭТАП 1 — админка и пароль уехали на сервер
──────────────────────────────────────────
УДАЛЕНО из клиента:
  • cloudHashPass() и cloudHashWeak() — хэширование пароля Студии в браузере
    и все сравнения с хэшем из общего документа;
  • локальный обход входа в Студию (`if (!ref) studioUnlocked = true`);
  • client-side права администратора: jpcAdminGuard()/statsAdminGuard() больше
    не смотрят на cloudRole (его можно было выставить в консоли) — нужен
    серверный админ-токен.
ДОБАВЛЕНО на сервере (server/worker/src/):
  • crypto.js  — PBKDF2-SHA256 (150 000 итераций) для пароля Студии, HMAC-токен
    устройства и админ-токен, постоянный сравнение, крипто-RNG;
  • admin.js   — /api/studio/login, /api/studio/setup и все действия админки
    (zero/block/unblock/delete/grant/poolSet/cfg/hallReset/catalog) с журналом;
  • перенос старого пароля: сервер понимает прежний клиентский хэш
    (legacyHashPass) только чтобы один раз принять старый пароль и сразу
    переложить его в PBKDF2 — владельцу ничего менять не нужно.

ЭТАП 2 — баланс и джекпот защищены от подмены
────────────────────────────────────────────
На сервер перенесены: списание ставки, генерация случайных чисел, результат
спина, выплата, розыгрыш и изменение банка, вскрытие паков, биржа, мины,
шахта и награды. Клиент отправляет только «крутить со ставкой N».
  • api.js      — /api/boot, /api/spin (Слоты/Сетка/Линии/Колесо), /api/mines;
  • economy.js  — /api/pack, /api/miner, /api/reward, /api/market/*;
  • store.js    — деньги в BigInt, любая запись через версию записи
    (оптимистичная блокировка): гонка не удваивает выплату и не гасит срыв;
  • assets/nx-rules.js — ОДИН файл правил на браузер и сервер (таблицы выплат,
    веса, множители, каскады Сетки). Разъехаться нечему.
Прямая запись баланса и банка из клиента закрыта:
  • в серверном режиме клиент не пишет ни баланс, ни банк в общий документ
    (jpSyncNow/jpSyncSoon/siteStatsSelfUpdate), а читает их с сервера;
  • сторож баланса каждые 4 с возвращает серверное значение, если число
    подменили в консоли или в localStorage;
  • для комнат на Firebase добавлены правила server/firebase/database.rules.json
    (запись банка и баланса — только с сервера);
  • purchases/exchange: цену пака сервер сверяет со своим каталогом, владение
    картой и эскроу биржи ведёт сервер.

Дизайн и визуальная часть НЕ изменены: анимации, разметка, тексты и звуки
те же — серверные числа просто подставляются в прежние функции (очереди
nxTakeForced в slotsWeightedRand/gridRandSym/linesRand/wheelPickIdx).

Данные игроков сохраняются: server/migrate.mjs переносит банк, balances,
зал славы, блокировки, лоты и каталог из текущего общего документа
(textdb.dev или Firebase-комната) в базу сервера.

Новые файлы:
  assets/nx-rules.js, assets/nx-cloud.js,
  server/worker/{src/*,schema.sql,wrangler.toml,package.json},
  server/dev/serve.mjs, server/test/economy.test.mjs,
  server/firebase/database.rules.json, server/migrate.mjs, server/README.md,
  tools/gen_nx_rules_tables.py, SECURITY-MIGRATION.md

app.js и index.html менялись — тег сборки nxmob185 -> nxmob186 (index.html,
sw.js, tools/build.py).

Проверка/применение:
    python3 tools/_b463_patch.py --check
    python3 tools/_b463_patch.py
Тесты серверной экономики (83 проверки, локально, без деплоя):
    node server/test/economy.test.mjs
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob185'
TAG_NEW = 'nxmob186'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('''assets/app.js''', '''        function slotsWeightedRand(pct) {
            const syms = slots.symbols;''',
              '''        function slotsWeightedRand(pct) {
            // b463: в серверном режиме символ приходит с сервера — локальный
            // Math.random в расчёте денег больше не участвует
            const nxForcedSym = nxTakeForced('slots');
            if (nxForcedSym !== null) return nxForcedSym;
            const syms = slots.symbols;'''))

PAIRS.append(('''assets/app.js''', '''        function gridRandSym() {
            if (!slots.symbols.length) slots.symbols = slotsSymbols();''',
              '''        function gridRandSym() {
            // b463: ячейку выбрал сервер — берём из его очереди
            const nxForcedSym = nxTakeForced('grid');
            if (nxForcedSym !== null && slots.symbols[nxForcedSym]) return slots.symbols[nxForcedSym];
            if (!slots.symbols.length) slots.symbols = slotsSymbols();'''))

PAIRS.append(('''assets/app.js''', '''        function linesRand() {
            // b414: шанс JACKPOT на ячейку берётся из настроек Студии (проценты)''',
              '''        function linesRand() {
            const nxForcedSym = nxTakeForced('lines'); // b463: ячейку выбрал сервер
            if (nxForcedSym !== null) return nxForcedSym;
            // b414: шанс JACKPOT на ячейку берётся из настроек Студии (проценты)'''))

PAIRS.append(('''assets/app.js''', '''        function linesMakePool() {
            if (!slots.symbols.length) slots.symbols = slotsSymbols();''',
              '''        function linesMakePool() {
            // b463: пул уже собран и отправлен на сервер — перемешивать заново
            // нельзя, иначе индексы ячеек на клиенте и сервере разъедутся
            if (nxPoolLock) return;
            if (!slots.symbols.length) slots.symbols = slotsSymbols();'''))

PAIRS.append(('''assets/app.js''', '''        function wheelPickIdx() {
            const n = WHEEL_SECTORS.length;''',
              '''        function wheelPickIdx() {
            const nxForcedIdx = nxTakeForced('wheel'); // b463: сектор выбрал сервер
            if (nxForcedIdx !== null) return nxForcedIdx;
            const n = WHEEL_SECTORS.length;'''))

PAIRS.append(('''assets/app.js''', '''            if (statsBlockGuard('слоты')) return; // b277
            const bet = slots.bet;''',
              '''            if (statsBlockGuard('слоты')) return; // b277
            // b463: серверный режим — ставку списывает сервер, он же крутит
            // барабаны своим генератором и считает выплату. Клиент отправляет
            // только «крутить со ставкой N» и проигрывает присланный результат.
            if (nxSrvSpin('slots', slotsSpin)) return;
            const bet = slots.bet;'''))

PAIRS.append(('''assets/app.js''', '''            if (statsBlockGuard('ставки в сетке')) return; // b277
            const bet = grid.bet;''',
              '''            if (statsBlockGuard('ставки в сетке')) return; // b277
            if (nxSrvSpin('grid', gridSpin)) return; // b463: спин проводит сервер
            const bet = grid.bet;'''))

PAIRS.append(('''assets/app.js''', '''            if (statsBlockGuard('линии')) return; // b277
            const bet = lines.bet;''',
              '''            if (statsBlockGuard('линии')) return; // b277
            if (nxSrvSpin('lines', linesSpin)) return; // b463: спин проводит сервер
            const bet = lines.bet;'''))

PAIRS.append(('''assets/app.js''', '''            if (statsBlockGuard('колесо')) return; // b277
            const bet = wheel.bet;''',
              '''            if (statsBlockGuard('колесо')) return; // b277
            if (nxSrvSpin('wheel', wheelSpin)) return; // b463: спин проводит сервер
            const bet = wheel.bet;'''))

PAIRS.append(('''assets/app.js''', '''                        idxSet.forEach(i => { grid.cells[i] = gridRandSym(); });
                        grid3dApplyCells(idxSet);''',
              '''                        nxGridRefill(idxSet); // b463: досыпка по возрастанию индекса — как на сервере
                        grid3dApplyCells(idxSet);'''))

PAIRS.append(('''assets/app.js''', '''                        idxSet.forEach(i => { grid.cells[i] = gridRandSym(); });
                        gridRenderCells(idxSet, 'drop');''',
              '''                        nxGridRefill(idxSet); // b463: тот же порядок досыпки, что на сервере
                        gridRenderCells(idxSet, 'drop');'''))

PAIRS.append(('''assets/app.js''', '''            if (statsBlockGuard('мины')) return; // b277
            const bet = mines.bet;''',
              '''            if (statsBlockGuard('мины')) return; // b277
            // b463: серверный режим — раскладка мин остаётся на сервере,
            // клиент про каждую плитку спрашивает его
            if (nxSrvMinesStart(minesStart)) return;
            const bet = mines.bet;'''))

PAIRS.append(('''assets/app.js''', '''        function minesPick(i) {
            if (!mines.active || mines.picked.indexOf(i) >= 0) return;
            mines.picked.push(i);''',
              '''        function minesPick(i) {
            if (!mines.active || mines.picked.indexOf(i) >= 0) return;
            // b463: где мины — знает только сервер
            if (nxServerMode() && mines.srvId) { nxSrvMinesPick(i, minesPick); return; }
            mines.picked.push(i);'''))

PAIRS.append(('''assets/app.js''', '''        function minesCashout() {
            if (!mines.active || !mines.picked.length) return;
            minesEnd(true);
        }''',
              '''        function minesCashout() {
            if (!mines.active || !mines.picked.length) return;
            if (nxServerMode() && mines.srvId) { nxSrvMinesCashout(); return; } // b463: выплату считает сервер
            minesEnd(true);
        }'''))

PAIRS.append(('''assets/app.js''', '''            mines.active = false;
            saveState(); updateCoinDisplay();
            checkAchievements();''',
              '''            mines.active = false;
            nxSrvSyncCoins(); // b463: баланс — серверный
            saveState(); updateCoinDisplay();
            checkAchievements();'''))

PAIRS.append(('''assets/app.js''', '''        function jackpotWin() {
            // b414: победителю уходит payout % банка (было всегда 100 %), остаток копится''',
              '''        function jackpotWin() {
            // b463: банк и выплату считает сервер; клиент показывает витрину
            // и возвращает сумму, которую прислал сервер
            if (nxServerMode()) return nxSrvJackpotWin();
            // b414: победителю уходит payout % банка (было всегда 100 %), остаток копится'''))

PAIRS.append(('''assets/app.js''', '''        function jackpotFeed(bet) {
            // b414: процент взноса ставки в банк настраивается в Студии (было всегда 100 %)''',
              '''        function jackpotFeed(bet) {
            // b463: банк кормит сервер (он же знает feedBet из настроек Студии)
            if (nxServerMode()) { nxSrvApplyBank(); return; }
            // b414: процент взноса ставки в банк настраивается в Студии (было всегда 100 %)'''))

PAIRS.append(('''assets/app.js''', '''        function jackpotOnLoss(loss) {
            // b414: процент проигрыша, уходящий в банк, настраивается в Студии (было всегда 100 %)''',
              '''        function jackpotOnLoss(loss) {
            // b463: взнос проигрыша в банк делает сервер
            if (nxServerMode()) { nxSrvApplyBank(); return 0; }
            // b414: процент проигрыша, уходящий в банк, настраивается в Студии (было всегда 100 %)'''))

PAIRS.append(('''assets/app.js''', '''        function jackpotPool() {
            // b414: несгораемый остаток банка задаётся в Студии (заводской = прежний сид)''',
              '''        function jackpotPool() {
            // b463: число «банк сайта» берём с сервера — локальный реестр его
            // больше не определяет (иначе подделка витрины возвращала бы и деньги)
            if (nxServerMode()) { const nxPot = nxSrvPot(); if (nxPot !== null && isFinite(nxPot)) return nxPot; }
            // b414: несгораемый остаток банка задаётся в Студии (заводской = прежний сид)'''))

PAIRS.append(('''assets/app.js''', '''        function jpSyncNow() {
            // b183: раньше пуш во время занятого канала молча отбрасывался — так терялись победы''',
              '''        function jpSyncNow() {
            // b463: общий документ больше не источник денег. Банк, зал славы и
            // реестр игроков берём с сервера и ничего туда не пишем.
            if (nxServerMode()) { try { nxSrvPullPublic(); } catch (e) {} return; }
            // b183: раньше пуш во время занятого канала молча отбрасывался — так терялись победы'''))

PAIRS.append(('''assets/app.js''', '''        function jpSyncSoon() { clearTimeout(jpT); jpT = setTimeout(jpSyncNow, 2500); }''',
              '''        // b463: в серверном режиме пушить общий документ нечего — только тянем витрину
        function jpSyncSoon() { if (nxServerMode()) { try { nxSrvPullPublic(); } catch (e) {} return; } clearTimeout(jpT); jpT = setTimeout(jpSyncNow, 2500); }'''))

PAIRS.append(('''assets/app.js''', '''        function siteStatsSelfUpdate() {
            try {
                const e = siteStatsNorm(JACKPOT_CID, siteStats.p[JACKPOT_CID] || {});''',
              '''        function siteStatsSelfUpdate() {
            // b463: в серверном режиме реестр игроков ведёт сервер — локальная
            // копия баланса в общий документ больше не публикуется
            if (nxServerMode()) return;
            try {
                const e = siteStatsNorm(JACKPOT_CID, siteStats.p[JACKPOT_CID] || {});'''))

PAIRS.append(('''assets/app.js''', '''            if (statsBlockGuard('покупка паков')) return; // b277
            const pack = state.packs.find(p => p.id === packId);''',
              '''            if (statsBlockGuard('покупка паков')) return; // b277
            // b463: серверный режим — цену проверяет сервер по своему каталогу,
            // монеты списывает он же, карты разыгрывает своим генератором
            if (nxSrvPack(packId, qty, buyPack)) return;
            const pack = state.packs.find(p => p.id === packId);'''))

PAIRS.append(('''assets/app.js''', '''        function buyPackBatch(pack, qty) {
            const price = packSalePrice(pack);
            const cards = [];
            let opened = 0;
            window.__nxBatchRoll = 1; // b404: 99 saveState подряд вешали телефон
            for (let i = 0; i < qty; i++) {
                const r = rollPackCards(pack);
                if (!r) { state.coins += price * (qty - i); updateCoinDisplay(); saveState(); break; }
                opened++;
                for (let k = 0; k < r.length; k++) cards.push(r[k]);
            }
            window.__nxBatchRoll = 0; // b404''',
              '''        function buyPackBatch(pack, qty, preRolled) {
            const price = packSalePrice(pack);
            const cards = [];
            let opened = 0;
            // b463: preRolled — карты, которые разыграл СЕРВЕР. Локальный ролл
            // и локальные возвраты монет в этом случае не выполняются.
            if (Array.isArray(preRolled)) {
                for (let i = 0; i < preRolled.length; i++) cards.push(preRolled[i]);
                opened = qty;
            } else {
            window.__nxBatchRoll = 1; // b404: 99 saveState подряд вешали телефон
            for (let i = 0; i < qty; i++) {
                const r = rollPackCards(pack);
                if (!r) { state.coins += price * (qty - i); updateCoinDisplay(); saveState(); break; }
                opened++;
                for (let k = 0; k < r.length; k++) cards.push(r[k]);
            }
            window.__nxBatchRoll = 0; // b404
            }'''))

PAIRS.append(('''assets/app.js''', '''                state.collection[card.id] = cardCopies(card.id) + 1;
                state.coins += refund;''',
              '''                state.collection[card.id] = cardCopies(card.id) + 1;
                // b463: дубликат уже оплатил сервер — второй раз не начисляем
                if (!nxUnboxServer) state.coins += refund; else nxSrvSyncCoins();'''))

PAIRS.append(('''assets/app.js''', '''                state.collection[card.id] = cardCopies(card.id) + 1; // b18: считаем повторы
                state.coins += refund;''',
              '''                state.collection[card.id] = cardCopies(card.id) + 1; // b18: считаем повторы
                // b463: дубликат уже оплатил сервер — второй раз не начисляем
                if (!nxUnboxServer) state.coins += refund; else nxSrvSyncCoins();'''))

PAIRS.append(('''assets/app.js''', '''        function marketApplyBuy(lot, receipt) {
            if (!lot || !lot.card) return;
            if (state.coins < lot.price) { showToast('Не хватает монет: нужно ' + fmtCoins(lot.price), 'error'); renderMarket(); return; }
            state.coins -= lot.price;''',
              '''        function marketApplyBuy(lot, receipt) {
            if (!lot || !lot.card) return;
            // b463: в серверном режиме деньги уже списал сервер (он же проверил
            // баланс, владение картой и перевёл монеты продавцу) — локально не
            // списываем второй раз
            if (!nxServerMode()) {
                if (state.coins < lot.price) { showToast('Не хватает монет: нужно ' + fmtCoins(lot.price), 'error'); renderMarket(); return; }
                state.coins -= lot.price;
            } else { try { nxSrvSyncCoins(); } catch (e) {} }'''))

PAIRS.append(('''assets/app.js''', '''        function marketCreditNow() {
            const led = Array.isArray(CLOUD.ledger) ? CLOUD.ledger : [];
            if (!led.length) return;''',
              '''        function marketCreditNow() {
            // b463: в серверном режиме продавец получает монеты сразу на сервере,
            // локальные квитанции не оплачиваются (иначе деньги задвоятся)
            if (nxServerMode()) { try { nxSrvSyncCoins(); } catch (e) {} return; }
            const led = Array.isArray(CLOUD.ledger) ? CLOUD.ledger : [];
            if (!led.length) return;'''))

PAIRS.append(('''assets/app.js''', '''            if (sec > 5) {
                const gain = sec * minerRate();
                state.coins += gain; miner.mined += gain;''',
              '''            if (sec > 5) {
                // b463: офлайн-добычу начисляет сервер по своему времени и своему
                // уровню кирки (потолок 2 часа у него тот же)
                if (nxServerMode()) { try { nxSrvMinerClaim(true); } catch (e) {} return { sec: sec, gain: 0 }; }
                const gain = sec * minerRate();
                state.coins += gain; miner.mined += gain;'''))

PAIRS.append(('''assets/app.js''', '''        function minerTick() {
            const r = minerRate();
            state.coins += r; miner.mined += r;''',
              '''        function minerTick() {
            // b463: в серверном режиме монеты локально не печатаем — раз в минуту
            // забираем добычу с сервера (время и уровень кирки знает он)
            if (nxServerMode()) { nxSrvMinerClaim(); return; }
            const r = minerRate();
            state.coins += r; miner.mined += r;'''))

PAIRS.append(('''assets/app.js''', '''        function minerUpgrade() {
            const c = minerCost();''',
              '''        function minerUpgrade() {
            if (nxSrvMinerUpgrade(minerUpgrade)) return; // b463: цену и уровень ведёт сервер
            const c = minerCost();'''))

PAIRS.append(('''assets/app.js''', '''        function claimDailyReward() {
            if (!canClaimDaily()) {''',
              '''        function claimDailyReward() {
            // b463: серию дней и сумму награды ведёт сервер
            if (nxServerMode()) {
                nxSrvReward('daily', {}, r => {
                    try {
                        state.daily.streak = Number(r.streak) || state.daily.streak;
                        state.daily.lastClaimDate = todayStr();
                        if (state.daily.streak > state.stats.bestStreak) state.stats.bestStreak = state.daily.streak;
                        saveState(); updateCoinDisplay(); updateDailyDot();
                        try { SoundFX.play('achievement'); } catch (e) {}
                        showToast('🎁 Награда дня ' + state.daily.streak + ': +' + fmtCoins(Number(r.amount) || 0) + ' монет!', 'success');
                        try { checkAchievements(); } catch (e) {}
                        try { renderDailyModal(); } catch (e) {}
                    } catch (e) {}
                });
                return;
            }
            if (!canClaimDaily()) {'''))

PAIRS.append(('''assets/app.js''', '''        function claimMission(idx) {
            const m = state.missions.list[idx];
            if (!m || m.claimed || m.progress < m.target) return;
            m.claimed = true;
            state.coins += m.reward;''',
              '''        function claimMission(idx) {
            const m = state.missions.list[idx];
            if (!m || m.claimed || m.progress < m.target) return;
            m.claimed = true;
            // b463: сумму и прогресс задания проверяет сервер — он сам считает
            // спины, вскрытия и продажи, поэтому награду начисляет он же
            if (nxServerMode()) {
                nxSrvReward('mission', { type: m.type, target: m.target }, r => {
                    try { saveState(); updateCoinDisplay(); SoundFX.play('coin'); } catch (e) {}
                    showToast('Награда за задание: +' + fmtCoins(Number(r.amount) || m.reward) + ' монет!', 'success');
                    try { checkAchievements(); renderRewards(); } catch (e) {}
                });
                saveState(); updateCoinDisplay();
                try { renderRewards(); } catch (e) {}
                return;
            }
            state.coins += m.reward;'''))

PAIRS.append(('''assets/app.js''', '''                        if (ok) {
                            state.achievements[a.id] = Date.now();
                            state.coins += a.reward;''',
              '''                        if (ok) {
                            state.achievements[a.id] = Date.now();
                            // b463: награду за достижение начисляет сервер — он
                            // проверяет условие по своим счётчикам и платит один раз
                            if (nxServerMode()) nxSrvReward('achievement', { id: a.id });
                            else state.coins += a.reward;'''))

PAIRS.append(('''assets/app.js''', '''        function statsAdminGuard() {
            if (typeof cloudGuest === 'function' && cloudGuest()) { showToast('Режим участника: управлять пользователями может только создатель комнаты', 'error'); return true; }
            return false;
        }''',
              '''        function statsAdminGuard() {
            // b463: прав в клиентском коде больше нет — есть серверный админ-токен.
            // Раньше здесь была проверка cloudGuest(), которую обходили одной
            // строчкой в консоли (cloudRole='owner'); теперь без токена действие
            // не выполнится ни здесь, ни на сервере.
            if (!nxAdminHasToken()) {
                showToast('⛔ Управление пользователями доступно после входа в Студию по паролю (пароль проверяет сервер)', 'error');
                try { nxOpenStudioPassFromAdmin(); } catch (e) {}
                return true;
            }
            return false;
        }'''))

PAIRS.append(('''assets/app.js''', '''        function jpcAdminGuard() {
            if (typeof cloudGuest === 'function' && cloudGuest()) {
                showToast('Режим участника: управлять джекпотом может только создатель комнаты', 'error');
                return true;
            }
            return false;
        }''',
              '''        function jpcAdminGuard() {
            // b463: управлять джекпотом может только тот, кому сервер выдал
            // админ-токен (вход по паролю Студии). Локальная роль больше не право.
            if (!nxAdminHasToken()) {
                showToast('⛔ Управлять банком и настройками джекпота можно только после входа в Студию по паролю', 'error');
                try { nxOpenStudioPassFromAdmin(); } catch (e) {}
                return true;
            }
            return false;
        }'''))

PAIRS.append(('''assets/app.js''', '''                cid = String(cid);
                const t = Date.now();
                siteStats.z[cid] = t; siteStatsSave();
                if (cid === JACKPOT_CID) { try { LS.setItem('nexus_stats_zero_ack', String(t)); } catch (e) {} state.coins = 0; saveState(); updateCoinDisplay(); }
                try { jpSyncNow(); } catch (e) {}
                statsRender();
                showToast('💸 Баланс обнулён — после синхронизации у игрока будет 0 монет', 'success');''',
              '''                cid = String(cid);
                // b463: баланс хранит и обнуляет СЕРВЕР (запись в общий документ
                // из браузера больше ничего не решает)
                nxAdminAct('zero', { cid: cid }, '💸 Баланс обнулён — у игрока 0 монет', r => {
                    nxApplyAdminUser(r, cid);
                    try { statsRender(); } catch (e) {}
                });'''))

PAIRS.append(('''assets/app.js''', '''                cid = String(cid);
                siteStats.b[cid] = { on: on ? 1 : 0, at: Date.now() };
                if (on) siteStats.z[cid] = Date.now(); // b334: блокировка обнуляет баланс
                siteStatsSave();
                try { jpSyncNow(); } catch (e) {}
                statsRender();
                showToast(on ? '🚫 Пользователь заблокирован — после синхронизации у него отключатся покупки и ставки' : '✅ Пользователь разблокирован', on ? 'info' : 'success');''',
              '''                cid = String(cid);
                // b463: блокировку ставит сервер — у заблокированного не проходят
                // ни спины, ни покупки (он проверяет флаг на каждом запросе)
                nxAdminAct(on ? 'block' : 'unblock', { cid: cid },
                    on ? '🚫 Пользователь заблокирован — покупки и ставки отключены' : '✅ Пользователь разблокирован', r => {
                        nxApplyAdminUser(r, cid);
                        try { statsRender(); } catch (e) {}
                    });'''))

PAIRS.append(('''assets/app.js''', '''                cid = String(cid);
                siteStats.b[cid] = { on: 1, del: 1, at: Date.now() };
                siteStats.z[cid] = Date.now();
                delete siteStats.p[cid];
                siteStatsSave();
                try { jpSyncNow(); } catch (e) {}
                statsRender();
                showToast('🗑 Игрок удалён: баланс обнулён, доступ отключён, из списка исчез', 'info');''',
              '''                cid = String(cid);
                // b463: удаление — на сервере (блокировка + обнуление + флаг del)
                nxAdminAct('delete', { cid: cid }, '🗑 Игрок удалён: баланс обнулён, доступ отключён', r => {
                    nxApplyAdminUser(r, cid);
                    try { delete siteStats.p[cid]; siteStatsSave(); statsRender(); } catch (e) {}
                });'''))

PAIRS.append(('''assets/app.js''', '''                const t = Date.now();
                list.forEach(cid => {
                    siteStats.z[cid] = t; siteStatsSave();
                    if (cid === JACKPOT_CID) { try { LS.setItem('nexus_stats_zero_ack', String(t)); } catch (e) {} state.coins = 0; saveState(); updateCoinDisplay(); }
                });
                try { jpSyncNow(); } catch (e) {}
                statsRender();
                showToast('💸 Обнулено устройств: ' + list.length + ' — после синхронизации у игроков будет 0', 'success');''',
              '''                // b463: обнуляет сервер одним запросом на все устройства
                nxAdminAct('zero', { cids: list }, '💸 Обнулено устройств: ' + list.length, r => {
                    nxApplyAdminUsers(r);
                    try { statsRender(); } catch (e) {}
                });'''))

PAIRS.append(('''assets/app.js''', '''                list.forEach(cid => {
                    siteStats.b[cid] = { on: on ? 1 : 0, at: Date.now() };
                    if (on) siteStats.z[cid] = Date.now(); // блокировка обнуляет баланс
                });
                siteStatsSave();
                try { jpSyncNow(); } catch (e) {}
                statsRender();
                showToast(on ? '🚫 Заблокировано устройств: ' + list.length : '✅ Разблокировано устройств: ' + list.length, on ? 'info' : 'success');''',
              '''                // b463: блокирует/разблокирует сервер
                nxAdminAct(on ? 'block' : 'unblock', { cids: list },
                    on ? '🚫 Заблокировано устройств: ' + list.length : '✅ Разблокировано устройств: ' + list.length, r => {
                        nxApplyAdminUsers(r);
                        try { statsRender(); } catch (e) {}
                    });'''))

PAIRS.append(('''assets/app.js''', '''                list.forEach(cid => {
                    siteStats.b[cid] = { on: 1, del: 1, at: Date.now() };
                    siteStats.z[cid] = Date.now();
                    delete siteStats.p[cid];
                });
                siteStatsSave();
                try { jpSyncNow(); } catch (e) {}
                statsRender();
                showToast('🗑 Удалено устройств: ' + list.length + ' — балансы обнулены, доступ отключён', 'info');''',
              '''                // b463: удаление устройств — на сервере
                nxAdminAct('delete', { cids: list }, '🗑 Удалено устройств: ' + list.length + ' — балансы обнулены, доступ отключён', r => {
                    nxApplyAdminUsers(r);
                    try { statsRender(); } catch (e) {}
                });'''))

PAIRS.append(('''assets/app.js''', '''        function jpcSetPool(target) {
            if (jpcAdminGuard()) return;
            target = Math.max(0, Math.round(Number(target) || 0));''',
              '''        function jpcSetPool(target) {
            if (jpcAdminGuard()) return;
            target = Math.max(0, Math.round(Number(target) || 0));
            // b463: банк хранится на сервере — «Поставить банк» выполняет он.
            // Локальная запись дельты в реестр led/won больше ничего не решает:
            // витрину и деньги определяет сервер.
            if (nxServerMode() || nxAdminHasToken()) {
                nxAdminAct('poolSet', { value: target }, null, r => {
                    try {
                        if (r && r.bank) { window.__nxSrvBank = r.bank; }
                        jackpotRender(); jpcAdminPreview();
                        const got = jackpotPool();
                        showToast(got === target
                            ? ((target > 0 ? '📈 Банк поднят до ' : '📉 Банк снижен до ') + fmtCoins(got))
                            : ('Банк не встал ровно: сейчас ' + fmtCoins(got)), got === target ? 'success' : 'info');
                    } catch (e) {}
                });
                return;
            }'''))

PAIRS.append(('''assets/app.js''', '''        function jpcGrant(cid, amount) {
            if (jpcAdminGuard()) return;
            cid = String(cid || '').slice(0, 40);
            if (!cid) return;''',
              '''        function jpcGrant(cid, amount) {
            if (jpcAdminGuard()) return;
            cid = String(cid || '').slice(0, 40);
            if (!cid) return;
            // b463: выдачу джекпота проводит сервер (amount=0 — весь банк по
            // payout %, с записью в зал славы). Отложенных назначений больше нет.
            if (nxServerMode() || nxAdminHasToken()) {
                const a = Math.max(0, Math.round(Number(amount) || 0));
                const who = cid === '*' ? 'ВСЕМ игрокам сайта' : (jpcNameOf(cid) || cid.slice(0, 10));
                nxAdminAct('grant', { cid: cid, amount: a },
                    '👑 Джекпот выдан: ' + who + ' — ' + (a > 0 ? fmtCoins(a) + ' монет' : 'весь банк (' + jpc.payout + ' %)'), r => {
                        try { jpcAdminRender(); } catch (e) {}
                        try { nxSrvApplyBank(); } catch (e) {}
                        if (cid === JACKPOT_CID || cid === '*') {
                            setTimeout(() => { try { nxSrvSyncCoins(); saveState(); updateCoinDisplay(); } catch (e) {} }, 300);
                        }
                    });
                return;
            }'''))

PAIRS.append(('''assets/app.js''', '''        function jpcGrantCancel(cid) {
            if (jpcAdminGuard()) return;
            cid = String(cid || '');
            if (!cid || !jpc.grant[cid]) return;''',
              '''        function jpcGrantCancel(cid) {
            if (jpcAdminGuard()) return;
            cid = String(cid || '');
            // b463: выдача на сервере происходит СРАЗУ — отложенных назначений нет
            if (nxServerMode() || nxAdminHasToken()) {
                if (jpc.grant[cid]) { jpc.grant[cid] = { a: -1, t: Date.now() }; jpcSave(); try { jpcAdminRender(); } catch (e) {} }
                showToast('Выдача происходит сразу на сервере — отменять нечего', 'info');
                return;
            }
            if (!cid || !jpc.grant[cid]) return;'''))

PAIRS.append(('''assets/app.js''', '''        function jpcPublish(silent) {
            if (jpcAdminGuard()) return;
            jpc.at = Date.now(); jpc.by = JACKPOT_CID;
            jpcSave();''',
              '''        function jpcPublish(silent) {
            if (jpcAdminGuard()) return;
            jpc.at = Date.now(); jpc.by = JACKPOT_CID;
            jpcSave();
            // b463: настройки джекпота хранит сервер. Публиковать их из браузера
            // в общий документ больше нельзя — их подменил бы любой игрок
            // (проценты банка, вероятность JACKPOT, «гарантия»).
            if (nxServerMode() || nxAdminHasToken()) {
                nxAdminAct('cfg', { cfg: jpc }, silent ? null : '👑 Настройки джекпота опубликованы для всех игроков сайта', r => {
                    try { if (r && r.cfg) { jpcMerge(r.cfg); jpcSave(); jpcAdminRender(); jackpotRender(); } } catch (e) {}
                });
                return;
            }'''))

PAIRS.append(('''assets/app.js''', '''        function jpcResetHall() {
            if (jpcAdminGuard()) return;
            jackpot.hall = [];''',
              '''        function jpcResetHall() {
            if (jpcAdminGuard()) return;
            // b463: зал славы хранится на сервере
            if (nxServerMode() || nxAdminHasToken()) {
                nxAdminAct('hallReset', {}, '🏆 Топ джекпотов сайта сброшен — банк и настройки не тронуты', () => {
                    try { jackpot.hall = []; jackpotSave(); jackpotRender(); jpcAdminPreview(); } catch (e) {}
                });
                return;
            }
            jackpot.hall = [];'''))

PAIRS.append(('''assets/app.js''', '''        function jpRepairNow() {
            // кнопка «Починить банк» в Студии: то же самое, что автоматика, но сразу
            // с публикацией — владелец может починить банк для всех игроков сайта
            if (jpcAdminGuard()) return;''',
              '''        function jpRepairNow() {
            // кнопка «Починить банк» в Студии: то же самое, что автоматика, но сразу
            if (jpcAdminGuard()) return;
            // b463: реестр банка (разряды led/won) ведёт сервер — чинить локальные
            // счётчики больше не нужно, достаточно перечитать банк с сервера
            if (nxServerMode() || nxAdminHasToken()) {
                nxSrvPullPublic().then(() => {
                    try { jackpotRender(); jpcAdminPreview(); } catch (e) {}
                    showToast('🧰 Банк перечитан с сервера: сейчас ' + fmtCoins(jackpotPool()), 'success');
                });
                return;
            }'''))

PAIRS.append(('''assets/app.js''', '''        function jpcRefresh() {
            try { jpSyncNow(); } catch (e) {}''',
              '''        function jpcRefresh() {
            // b463: данные игроков и банка тянем с сервера
            try { if (nxServerMode() || nxAdminHasToken()) nxSrvPullUsers(); } catch (e) {}
            try { jpSyncNow(); } catch (e) {}'''))

PAIRS.append(('''assets/app.js''', '''        async function submitStudioPass() {
            const i = document.getElementById('studio-pass-input');
            const e = document.getElementById('studio-pass-err');
            const showErr = t => { if (e) { e.textContent = t; e.classList.remove('hidden'); } };
            const pass = String((i && i.value) || '');
            const ref = CLOUD.remoteAuth || cloudLocalAuth();
            if (!ref) { studioUnlocked = true; closeStudioPassModal(); switchTab('studio'); return; }
            if (!pass) { showErr('Введите пароль комнаты'); return; }
            try {
                const h = await cloudHashPass(pass, ref.salt);
                if (String(h) === String(ref.hash)) {
                    studioUnlocked = true;
                    // b133: знаешь пароль комнаты = создатель: сохраняем права и на это устройство
                    try { cloudSaveLocalAuth({ login: ref.login, hash: ref.hash, salt: ref.salt, at: Date.now() }); } catch (e) {}
                    cloudRole = 'owner';
                    closeStudioPassModal();
                    switchTab('studio');
                    showToast('🔓 Студия открыта до конца сессии', 'success');
                } else {
                    showErr('Неверный пароль комнаты');
                }
            } catch (err) { showErr('Не удалось проверить пароль'); }
        }''',
              '''        async function submitStudioPass() {
            const i = document.getElementById('studio-pass-input');
            const e = document.getElementById('studio-pass-err');
            const showErr = t => { if (e) { e.textContent = t; e.classList.remove('hidden'); } };
            const pass = String((i && i.value) || '');
            if (!pass) { showErr('Введите пароль комнаты'); return; }
            // ============ b463: ПРОВЕРКА ПАРОЛЯ ПЕРЕНЕСЕНА НА СЕРВЕР ============
            // БЫЛО: клиент сам считал хэш пароля (cloudHashPass) и сравнивал его
            // с хэшем из общего облачного документа. Хэш и соль лежали там же,
            // где весь каталог, а сравнение было в публичном коде — то есть
            // любой игрок мог написать в консоли studioUnlocked=true (или
            // cloudRole='owner') и получить всю админку: обнуление балансов,
            // блокировки, «Поставить банк», «Выдать ВСЕМ».
            // СТАЛО: пароля и его хэша в клиентском коде нет вовсе. Пароль
            // уходит на сервер (/api/studio/login), сервер сверяет его со своим
            // PBKDF2-хэшем (150 000 итераций) и выдаёт админ-токен на 12 часов.
            // Каждое действие админки принимается только с этим токеном.
            const ref = CLOUD.remoteAuth || cloudLocalAuth();
            if (!nxApiConfigured()) {
                showErr('Сервер не подключён: укажите адрес API в разделе «Облако» — вход в Студию проверяет сервер');
                return;
            }
            try {
                const okPass = await nxStudioVerify(pass);
                if (!okPass) { showErr('Неверный пароль комнаты'); return; }
                studioUnlocked = true;
                // b133 с поправкой b463: права создателя подтверждает серверный
                // токен; в комнате и на устройстве остаётся только метка-маркер,
                // которая с паролем не связана и сама по себе прав не даёт
                const marker = cloudAuthMarker((ref && ref.login) || nxStudioLogin());
                try { cloudSaveLocalAuth(marker); } catch (e2) {}
                try { CLOUD.remoteAuth = marker; } catch (e2) {}
                cloudRole = 'owner';
                closeStudioPassModal();
                switchTab('studio');
                showToast('🔓 Студия открыта до конца сессии (права выдал сервер)', 'success');
                // реестр игроков, банк и каталог — с сервера
                try { nxSrvPullUsers(() => { try { statsRenderIfVisible(); } catch (e3) {} }); } catch (e2) {}
                try { nxSrvPublishCatalog(true); } catch (e2) {}
            } catch (err) { showErr('Не удалось проверить пароль'); }
        }'''))

PAIRS.append(('''assets/app.js''', '''        // Запасной хэш на случай, если браузер не дал crypto.subtle (страница открыта не по https / file://)
        function cloudHashWeak(str) {
            let h1 = 0x811c9dc5, h2 = 0x9e3779b9;
            for (let r = 0; r < 256; r++) {
                for (let i = 0; i < str.length; i++) {
                    const c = (str.charCodeAt(i) + r) & 0xffff;
                    h1 = (h1 ^ c) >>> 0; h1 = (h1 * 0x01000193) >>> 0;
                    h2 = (h2 + c + (h1 >>> 13)) >>> 0; h2 = ((h2 << 7) | (h2 >>> 25)) >>> 0;
                    h1 = (h1 ^ h2) >>> 0;
                }
            }
            return 'w1:' + h1.toString(16).padStart(8, '0') + h2.toString(16).padStart(8, '0');
        }
        // Хэш пароля: SHA-256 + соль, 512 раундов. В облако уходит только он.
        function cloudHashPass(pass, salt) {
            const s = String(salt == null ? '' : salt);
            if (typeof crypto !== 'undefined' && crypto && crypto.subtle && typeof TextEncoder !== 'undefined') {
                const hex = buf => Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
                const one = str => crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
                let p = one(s + ':' + String(pass));
                for (let i = 0; i < 511; i++) p = p.then(h => one(hex(h) + s));
                return p.then(h => 'sha256:' + hex(h));
            }
            return Promise.resolve(cloudHashWeak(s + ':' + String(pass)));
        }''',
              '''        // ============ b463: ХЭШИРОВАНИЕ ПАРОЛЯ УБРАНО ИЗ КЛИЕНТА ============
        // Здесь были cloudHashWeak() (слабый FNV-подобный хэш на случай, если
        // браузер не дал crypto.subtle) и cloudHashPass() (SHA-256 + соль,
        // 512 раундов), а также сравнение результата с хэшем из общего облачного
        // документа. Всё это переехало на сервер: server/worker/src/crypto.js
        // проверяет пароль по PBKDF2-SHA256 (150 000 итераций), а прежний
        // клиентский алгоритм сервер знает только для переноса уже заданного
        // пароля (admin.js: legacyHashPass / legacyWeakHash).
        //
        // В комнате и на устройстве остаётся МЕТКА-МАРКЕР: случайная строка,
        // которая показывает «комната защищена, создатель такой-то». С паролем
        // она не связана и никаких прав сама по себе не даёт — права выдаёт
        // серверный админ-токен.
        function cloudAuthMarker(login) {
            let rnd = '';
            try {
                const b = new Uint8Array(16);
                if (typeof crypto !== 'undefined' && crypto.getRandomValues) crypto.getRandomValues(b);
                else for (let i = 0; i < b.length; i++) b[i] = Math.floor(Math.random() * 256);
                for (let i = 0; i < b.length; i++) rnd += b[i].toString(16).padStart(2, '0');
            } catch (e) { rnd = String(Date.now()) + Math.random().toString(16).slice(2); }
            return { login: cloudAuthNorm(login), hash: 'srv:' + rnd, salt: '', srv: 1, at: Date.now() };
        }'''))

PAIRS.append(('''assets/app.js''', '''        function cloudAuthMake(login, pass) {
            const salt = cloudSalt();
            return cloudHashPass(pass, salt).then(hash => ({ login: cloudAuthNorm(login), hash: hash, salt: salt, at: Date.now() }));
        }''',
              '''        // b463: пароль создаёт/меняет СЕРВЕР (client-side хэширования больше нет).
        // Функция осталась на прежнем месте, чтобы не трогать вызывающий код:
        // она просит сервер сохранить пароль и возвращает метку-маркер для комнаты.
        function cloudAuthMake(login, pass) {
            return nxStudioSetup(login, pass, '').then(r => {
                if (!r || !r.ok) throw new Error((r && r.error) || 'Сервер не принял пароль');
                return cloudAuthMarker(r.login || login);
            });
        }'''))

PAIRS.append(('''assets/app.js''', '''                if (mode === 'login') {
                    if (!rAuth) throw new Error('В этой комнате пароль ещё не задан');
                    return cloudHashPass(pass, rAuth.salt || '').then(h => {
                        if (cloudAuthNorm(login) !== cloudAuthNorm(rAuth.login) || h !== String(rAuth.hash)) throw new Error('Неверный логин или пароль комнаты');
                        return { login: cloudAuthNorm(rAuth.login), hash: String(rAuth.hash), salt: rAuth.salt || '', at: Date.now() };
                    });
                }
                if (mode === 'set' && rAuth) throw new Error('Пароль в этой комнате уже задан — войдите по нему');
                const known = rAuth || cloudLocalAuth();
                const checkCur = (mode === 'change' && known)
                    ? cloudHashPass(cur, known.salt || '').then(h => { if (h !== String(known.hash)) throw new Error('Текущий пароль указан неверно'); return true; })
                    : Promise.resolve(true);
                return checkCur.then(() => cloudAuthMake(login, pass));''',
              '''                // ============ b463: логин/пароль комнаты проверяет СЕРВЕР ======
                // Клиент больше не считает хэш и не сравнивает его с хэшем из
                // общего документа: и вход, и создание пароля, и смену пароля
                // (включая проверку текущего) делает сервер.
                const adm = nxAdm();
                if (!adm) throw new Error('Сервер не подключён: укажите адрес API в разделе «Облако»');
                if (mode === 'login') {
                    return adm.login(login || (rAuth && rAuth.login) || '', pass).then(r => {
                        if (!r || !r.ok) throw new Error((r && r.error) || 'Неверный логин или пароль комнаты');
                        return cloudAuthMarker(r.login || login);
                    });
                }
                if (mode === 'set' && rAuth && !rAuth.srv) throw new Error('Пароль в этой комнате уже задан — войдите по нему');
                // set / change: пароль сохраняет сервер, при смене он же сверяет текущий
                return adm.setup(login, pass, mode === 'change' ? cur : '', '').then(r => {
                    if (!r || !r.ok) throw new Error((r && r.error) || 'Сервер не принял пароль');
                    return cloudAuthMarker(r.login || login);
                });'''))

PAIRS.append(('''assets/app.js''', '''            if (cloudGuest()) { if (!quiet) showToast('⛔ Публиковать может только создатель комнаты', 'error'); return; }''',
              '''            if (cloudGuest()) { if (!quiet) showToast('⛔ Публиковать может только создатель комнаты', 'error'); return; }
            // b463: вместе с каталогом комнаты публикуем его и на сервере —
            // серверу нужны паки и редкости карт, чтобы честно вскрывать паки
            // и не верить словам клиента про «у меня легендарка»
            try { if (nxServerMode() && nxAdminHasToken()) nxSrvPublishCatalog(true); } catch (e) {}'''))

PAIRS.append(('''index.html''', '''    <!-- Код игры. Внешний файл: кешируется отдельно от разметки. -->
    <script src="assets/app.js?v=nxmob185"></script>''',
              '''    <!-- Код игры. Внешний файл: кешируется отдельно от разметки. -->
    <!-- b463: правила игры (ОДИН файл на браузер и сервер) и клиент серверной
         экономики. Грузятся ДО app.js: игра берёт из них константы выплат и
         доступ к API (NXS/NXJ/NXM/NXA). -->
    <script src="assets/nx-rules.js?v=nxmob185"></script>
    <script src="assets/nx-cloud.js?v=nxmob185"></script>
    <script src="assets/app.js?v=nxmob185"></script>'''))

PAIRS.append(('''assets/app.js''', '''          } catch (e) {
            try { console.error('window.onload', e); } catch (e2) {}
            try { nxErrorToast(String((e && e.message) || e) + ' (при запуске)'); } catch (e2) {}
          }
        };''',
              '''          } catch (e) {
            try { console.error('window.onload', e); } catch (e2) {}
            try { nxErrorToast(String((e && e.message) || e) + ' (при запуске)'); } catch (e2) {}
          }
        };
        // ---------------- права администратора (b463) ----------------
        /** Есть ли серверный админ-токен. Только он даёт права: локальной роли нет. */
        function nxAdminHasToken() { try { const a = nxAdm(); return !!(a && a.hasToken && a.hasToken()); } catch (e) { return false; } }

        /** Перелить ответ сервера про одного игрока в локальный реестр (для той же таблицы). */
        function nxApplyAdminUser(r, cid) {
            try {
                const list = (r && r.results) || [];
                for (let i = 0; i < list.length; i++) {
                    const x = list[i];
                    if (!x || !x.cid) continue;
                    if (x.blocked) siteStats.b[x.cid] = { on: 1, at: Date.now(), del: x.del ? 1 : 0 };
                    else siteStats.b[x.cid] = { on: 0, at: Date.now() };
                    if (x.zeroAt) siteStats.z[x.cid] = x.zeroAt;
                    if (siteStats.p[x.cid]) siteStats.p[x.cid].bal = Math.floor(Number(x.bal && x.bal.s) || 0);
                    if (x.cid === JACKPOT_CID) {
                        try { LS.setItem('nexus_stats_zero_ack', String(x.zeroAt || Date.now())); } catch (e) {}
                        nxSrvSyncCoins();
                        try { saveState(); updateCoinDisplay(); } catch (e) {}
                    }
                }
                siteStatsSave();
            } catch (e) {}
        }
        function nxApplyAdminUsers(r) { nxApplyAdminUser(r, ''); }

        // =====================================================================
        // ============ b463: СЕРВЕРНАЯ ЭКОНОМИКА (клиентская часть) ===========
        // =====================================================================
        // Что изменилось для игрока: НИЧЕГО. Дизайн, анимации, тексты, звуки и
        // выплаты — прежние. Изменилось то, КТО считает деньги.
        //
        // Раньше: ставка, случайные числа, выплата, банк джекпота, баланс,
        //         покупки и обмен считались в браузере и писались в общий
        //         облачный документ напрямую. Любой мог подменить баланс в
        //         консоли или объявить себя победителем джекпота.
        // Теперь: клиент отправляет «крутить со ставкой N», а сервер
        //         (server/worker) списывает ставку, крутит СВОИМ криптогенератором,
        //         считает выплату по общим правилам (assets/nx-rules.js — тот же
        //         файл, что грузит браузер), двигает банк и возвращает результат.
        //         Клиент лишь проигрывает анимацию по присланным числам.
        //
        // Запасной путь: если сервер не настроен или сеть пропала, available()
        // остаётся false и игра работает ровно как раньше — на локальной логике.
        // Ничего не ломается и не тормозит (тот же принцип, что заложен в
        // b443/b444 для биржи и атомарного банка).
        // =====================================================================

        function nxApi() { try { return (typeof window !== 'undefined' && window.NXS) ? window.NXS : null; } catch (e) { return null; } }
        function nxAdm() { try { return (typeof window !== 'undefined' && window.NXA) ? window.NXA : null; } catch (e) { return null; } }
        /** true, только если адрес API задан И сервер уже ответил успешно. */
        function nxServerMode() { try { const a = nxApi(); return !!(a && a.available && a.available()); } catch (e) { return false; } }
        function nxApiConfigured() { try { const a = nxApi(); return !!(a && a.configured && a.configured()); } catch (e) { return false; } }

        let nxLocalPass = false;      // идём локальным запасным путём — серверные охраны пропускаем
        let nxUnboxServer = false;    // текущее вскрытие пака разыграл сервер (дубликаты оплатил он)
        let nxForcedQ = {};           // очереди серверных случайных чисел по играм
        let nxSpinBusy = {};          // защита от двойного клика в серверном режиме
        let nxLastSpin = {};          // последний ответ сервера по играм
        let nxLastJp = null;          // последний срыв джекпота (пришёл с сервера)
        let nxPoolLock = false;       // пул карт для «Линий» уже отправлен на сервер — не перемешивать

        function nxOid(kind) {
            return kind + '-' + JACKPOT_CID + '-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
        }

        // ---------------- серверные случайные числа ----------------
        // Единственная точка, откуда игры берут «случайность» в серверном режиме.
        // Очередь заполняется ответом сервера; когда она пуста — возвращаем null,
        // и функция работает по-старому (локально), так что игра не встаёт.
        function nxTakeForced(game) {
            const q = nxForcedQ[game];
            if (!q || !q.length) return null;
            return q.shift();
        }
        function nxSetForced(game, arr) { nxForcedQ[game] = Array.isArray(arr) ? arr.slice() : []; }

        /**
         * Досыпка поля «Сетки» после взрыва выигрышных ячеек.
         * Порядок ОБЯЗАН совпадать с серверным: по возрастанию индекса ячейки.
         * Раньше здесь был Set.forEach (порядок вставки), поэтому на каскадах
         * клиент и сервер могли разойтись — теперь сортируем явно.
         */
        function nxGridRefill(idxSet) {
            const idxs = [];
            try { idxSet.forEach(i => idxs.push(i)); } catch (e) {}
            idxs.sort((a, b) => a - b);
            for (let k = 0; k < idxs.length; k++) {
                const f = nxTakeForced('grid');
                grid.cells[idxs[k]] = (f !== null && slots.symbols[f]) ? slots.symbols[f] : gridRandSym();
            }
        }

        // ---------------- баланс и банк: источник истины — сервер ----------------
        function nxSrvPot() {
            try { const a = nxApi(); const b = a && a.bank && a.bank(); return b ? Math.round(Number(b.pot)) : null; } catch (e) { return null; }
        }
        function nxSrvApplyBank() {
            try {
                const a = nxApi(); if (!a) return;
                const b = a.bank(); if (!b) return;
                // витрина банка берётся с сервера: локальный реестр больше не
                // источник числа «банк сайта»
                window.__nxSrvBank = b;
                try { jackpotRender(); } catch (e) {}
                try { jpcLabelsRender(); } catch (e) {}
            } catch (e) {}
        }
        /**
         * Вернуть балансу серверное значение. Вызывается после каждого действия,
         * где деньги двигает сервер: локальные прибавки (которые сервер уже учёл)
         * не накапливаются, а подмена числа в консоли живёт лишь до следующей
         * синхронизации (сторож баланса — каждые 4 секунды).
         */
        function nxSrvSyncCoins() {
            try {
                if (!nxServerMode()) return;
                const a = nxApi(); const v = Math.floor(Number(a && a.balNum()) || 0);
                if (!isFinite(v)) return;
                if ((state.coins || 0) !== v) { state.coins = v; try { updateCoinDisplay(); } catch (e) {} }
            } catch (e) {}
        }

        // ---------------- спины: клиент отправляет только ставку ----------------
        function nxSrvCards(game) {
            try {
                if (game === 'lines') {
                    return (lines.pool || []).filter(s => s && !s.jackpot).map(s => s.id).slice(0, 3);
                }
                if (!slots.symbols || !slots.symbols.length) slots.symbols = slotsSymbols();
                return slots.symbols.filter(s => s && !s.jackpot).map(s => s.id).slice(0, 5);
            } catch (e) { return []; }
        }

        function nxSrvBet(game) {
            try {
                if (game === 'slots') return slots.bet;
                if (game === 'grid') return grid.bet;
                if (game === 'lines') return lines.bet;
                if (game === 'wheel') return wheel.bet;
            } catch (e) {}
            return 0;
        }

        /** Заполнить очереди случайных чисел из ответа сервера. */
        function nxSrvFillForced(game, r) {
            if (game === 'slots') nxSetForced('slots', r.res || []);
            else if (game === 'lines') nxSetForced('lines', r.res || []);
            else if (game === 'wheel') nxSetForced('wheel', (r.res === undefined || r.res === null) ? [] : [r.res]);
            else if (game === 'grid') {
                const q = [];
                const cells = (r.res && r.res.cells) || [];
                for (let i = 0; i < cells.length; i++) q.push(cells[i]);
                const steps = (r.res && r.res.steps) || [];
                for (let s = 0; s < steps.length; s++) {
                    const ref = steps[s].refill || {};
                    const keys = Object.keys(ref).map(Number).sort((a, b) => a - b); // тот же порядок, что в nxGridRefill
                    for (let k = 0; k < keys.length; k++) q.push(ref[keys[k]]);
                }
                nxSetForced('grid', q);
            }
        }

        /**
         * Серверный спин. Возвращает true, если спин проводит сервер — тогда
         * локальный код функции не выполняется вовсе: ни списания монет,
         * ни Math.random, ни локального пересчёта выплаты.
         */
        function nxSrvSpin(game, localFn) {
            try {
                if (nxLocalPass || !nxServerMode()) return false;
                if (nxSpinBusy[game]) return true;
                const bet = Math.floor(Number(nxSrvBet(game)) || 0);
                if (bet < 1) return false;
                // «Линии»: пул карт собирается ДО запроса и уходит на сервер тем же
                // порядком — иначе клиент и сервер говорили бы о разных картах
                if (game === 'lines') { try { linesEnsure(); nxPoolLock = false; linesMakePool(); nxPoolLock = true; } catch (e) {} }
                const cards = nxSrvCards(game);
                nxSpinBusy[game] = true;
                const oid = nxOid(game);
                nxApi().guard(() => nxApi().spin(game, bet, cards, oid)).then(r => {
                    nxSpinBusy[game] = false;
                    if (!r) { nxLocalPass = true; try { localFn(); } finally { nxLocalPass = false; } return; }
                    if (r.error === 'blocked' || r.error === 'deleted') {
                        showToast('🚫 Вы заблокированы администратором — ставки недоступны', 'error');
                        try { nxLockModal('Вы заблокированы администратором'); } catch (e) {}
                        return;
                    }
                    if (r.error === 'not_enough') {
                        nxSrvSyncCoins();
                        showToast('Недостаточно монет для ставки ' + fmtCoins(bet) + '.' + nxLackNote(bet), 'error');
                        return;
                    }
                    if (r.fallback || r.error === 'no_catalog') {
                        // сервер есть, но каталог комнаты на него ещё не опубликован —
                        // играем по-старому, ничего не ломая
                        nxLocalPass = true; try { localFn(); } finally { nxLocalPass = false; }
                        return;
                    }
                    if (!r.ok) { nxSrvSyncCoins(); if (r.error) showToast('⚠️ ' + r.error, 'error'); return; }

                    nxLastSpin[game] = r;
                    nxLastJp = r.jpHit ? (r.jp || {}) : null;
                    // баланс в ответе уже содержит и списанную ставку, и выигрыш
                    nxSrvSyncCoins();
                    nxSrvFillForced(game, r);
                    // проигрываем ПРЕЖНЮЮ анимацию, но по серверным числам
                    nxLocalPass = true;
                    try { localFn(); } finally { nxLocalPass = false; }
                    // после анимации — контрольная сверка баланса и витрины банка
                    setTimeout(() => { try { nxSrvSyncCoins(); nxSrvApplyBank(); saveState(); } catch (e) {} }, 3200);
                }).catch(() => {
                    nxSpinBusy[game] = false;
                    nxLocalPass = true; try { localFn(); } finally { nxLocalPass = false; }
                });
                return true;
            } catch (e) {
                nxSpinBusy[game] = false;
                return false;
            }
        }

        /**
         * Срыв джекпота в серверном режиме: деньги уже начислил сервер,
         * поэтому здесь — только витрина, зал славы, звук и конфетти.
         * Возвращает сумму выплаты (её ждут slotsFinish/gridStep/linesFinish).
         */
        function nxSrvJackpotWin() {
            let prize = 0;
            try {
                const jp = nxLastJp || {};
                prize = Math.max(0, Math.round(Number(jp.prizeN !== undefined ? jp.prizeN : jp.prize) || 0));
                const nm = getPlayerName() || ('Игрок-' + JACKPOT_CID.slice(1, 5));
                jackpot.wins[JACKPOT_CID] = (jackpot.wins[JACKPOT_CID] || 0) + 1;
                jackpot.names[JACKPOT_CID] = nm;
                jackpot.hall = jackpot.hall || [];
                jackpot.hall.unshift({ n: nm, a: prize, t: Date.now(), c: JACKPOT_CID, nm: getPlayerName() ? 1 : 0 });
                jackpot.hall = jackpot.hall.slice(0, 40);
                state.stats.jackpots = (state.stats.jackpots || 0) + 1;
                try { slots.winFlash = performance.now(); } catch (e) {}
                try { grid.winFlashT = performance.now(); } catch (e) {}
                try { SoundFX.play('legendary'); } catch (e) {}
                try { launchConfetti(220); } catch (e) {}
                showToast('👑 JACKPOT! +' + fmtCoins(prize) + ' монет — весь банк сайта ваш', 'success');
                nxSrvSyncCoins();
                nxSrvApplyBank();
                try { saveState(); updateCoinDisplay(); } catch (e) {}
                try { LS.setItem('nexus_jp_seen', String(Date.now())); } catch (e) {}
            } catch (e) {}
            return prize;
        }

        // ---------------- мины: раскладка хранится на сервере ----------------
        function nxSrvMinesStart(localFn) {
            try {
                if (nxLocalPass || !nxServerMode()) return false;
                if (nxSpinBusy.mines) return true;
                const bet = Math.floor(Number(mines.bet) || 0);
                if (bet < 1) return false;
                nxSpinBusy.mines = true;
                nxApi().guard(() => nxApi().mines('start', { bet: bet, m: mines.m })).then(r => {
                    nxSpinBusy.mines = false;
                    if (!r || !r.ok) {
                        nxSrvSyncCoins();
                        if (r && r.error === 'not_enough') showToast('Недостаточно монет!' + nxLackNote(bet), 'error');
                        else if (r && r.error === 'blocked') showToast('🚫 Вы заблокированы администратором', 'error');
                        else { nxLocalPass = true; try { localFn(); } finally { nxLocalPass = false; } }
                        return;
                    }
                    nxSrvSyncCoins();
                    mines.srvId = r.id;
                    mines.mines = [];        // раскладка мин клиенту неизвестна
                    mines.picked = [];
                    mines.active = true;
                    mines.tilePack = [];
                    for (let i = 0; i < MINES_TILES; i++) mines.tilePack[i] = null;
                    try { nxMinesFillPacks(); } catch (e) {}
                    try { updateCoinDisplay(); renderMinesUI(); } catch (e) {}
                    try { SoundFX.play('click'); } catch (e) {}
                }).catch(() => { nxSpinBusy.mines = false; nxLocalPass = true; try { localFn(); } finally { nxLocalPass = false; } });
                return true;
            } catch (e) { nxSpinBusy.mines = false; return false; }
        }
        // плитки мин показывают паки игрока — заполняем как в minesStart
        function nxMinesFillPacks() {
            const own = (state.packs || []).filter(p => p && p.id);
            for (let i = 0; i < MINES_TILES; i++) mines.tilePack[i] = own.length ? own[i % own.length] : null;
        }
        function nxSrvMinesPick(i, localFn) {
            try {
                if (!nxServerMode() || !mines.srvId) { localFn(i); return; }
                nxApi().mines('pick', { id: mines.srvId, i: i }).then(r => {
                    if (!r || !r.ok) { if (r && r.error) showToast('⚠️ ' + r.error, 'error'); return; }
                    mines.picked.push(i);
                    if (r.mine) {
                        // мины становятся видны только после взрыва — как и раньше
                        mines.mines = Array.isArray(r.mines) ? r.mines : [i];
                        nxSrvSyncCoins();
                        try { nxSrvApplyBank(); } catch (e) {}
                        minesEnd(false);
                        return;
                    }
                    try { updateMissions('mines_open', 1); } catch (e) {}
                    try { SoundFX.play('reveal'); } catch (e) {}
                    if (mines.picked.length >= MINES_TILES - mines.m) { nxSrvMinesCashout(); return; }
                    try { renderMinesUI(); } catch (e) {}
                }).catch(() => { showToast('Нет связи с сервером — попробуйте ещё раз', 'error'); });
            } catch (e) { localFn(i); }
        }
        function nxSrvMinesCashout() {
            try {
                if (!nxServerMode() || !mines.srvId) { minesEnd(true); return; }
                nxApi().mines('cashout', { id: mines.srvId }).then(r => {
                    if (!r || !r.ok) { if (r && r.error) showToast('⚠️ ' + r.error, 'error'); return; }
                    nxSrvSyncCoins();
                    try { nxSrvApplyBank(); } catch (e) {}
                    minesEnd(true);
                }).catch(() => { showToast('Нет связи с сервером — выигрыш не забран, попробуйте ещё раз', 'error'); });
            } catch (e) { minesEnd(true); }
        }

        // ---------------- паки: цену и карты проверяет сервер ----------------
        function nxSrvPack(packId, qty, localFn) {
            try {
                if (nxLocalPass || !nxServerMode()) return false;
                if (nxSpinBusy.pack) return true;
                const pack = state.packs.find(p => p.id === packId);
                if (!pack) return false;
                const q = Math.max(1, Math.min(99, Math.floor(qty) || 1));
                let price = 0;
                try { price = packSalePrice(pack); } catch (e) { price = Math.floor(Number(pack.price) || 0); }
                nxSpinBusy.pack = true;
                nxApi().guard(() => nxApi().pack(packId, q, price)).then(r => {
                    nxSpinBusy.pack = false;
                    if (!r) { nxLocalPass = true; try { localFn(packId, qty); } finally { nxLocalPass = false; } return; }
                    if (r.fallback || r.error === 'no_catalog') {
                        nxLocalPass = true; try { localFn(packId, qty); } finally { nxLocalPass = false; }
                        return;
                    }
                    if (!r.ok) {
                        nxSrvSyncCoins();
                        if (r.error === 'not_enough') showToast('Недостаточно монет! Нужно ' + fmtCoins(Math.floor(Number(r.need || price) || price)), 'error');
                        else if (r.error === 'pack_retired') showToast('🚫 Пак снят с продажи — купить его больше нельзя', 'error');
                        else if (r.error === 'pack_premiere') showToast('🎬 Премьера пака ещё не состоялась', 'info');
                        else if (r.error === 'price_out_of_range') showToast('⚠️ Цена пака не совпала с каталогом — обновите страницу', 'error');
                        else if (r.error === 'blocked') showToast('🚫 Вы заблокированы администратором — покупки недоступны', 'error');
                        else showToast('⚠️ ' + (r.error || 'Не удалось купить пак'), 'error');
                        return;
                    }
                    nxSrvApplyPackResult(pack, q, r);
                }).catch(() => { nxSpinBusy.pack = false; nxLocalPass = true; try { localFn(packId, qty); } finally { nxLocalPass = false; } });
                return true;
            } catch (e) { nxSpinBusy.pack = false; return false; }
        }

        /** Карты разыграл сервер — показываем то же вскрытие, что и раньше. */
        function nxSrvApplyPackResult(pack, q, r) {
            try {
                const byId = {};
                (state.cards || []).forEach(c => { if (c && c.id) byId[c.id] = c; });
                const cards = (r.cards || []).map(c => {
                    const d = byId[c.id] || { id: c.id, name: c.name, rarity: c.rarity, image: c.image, packId: pack.id };
                    const o = Object.assign({}, d);
                    o.rarity = c.rarity || d.rarity || 'common';
                    o.unboxedId = Math.random();
                    return o;
                });
                // статистика и гарант — из ответа сервера
                state.stats.packsOpened = (state.stats.packsOpened || 0) + q;
                if (r.pity !== undefined) state.pity.packsSinceEpic = Math.max(0, Math.floor(Number(r.pity) || 0));
                try {
                    const ps = state.packStats || (state.packStats = {});
                    const en = ps[pack.id] || (ps[pack.id] = { opens: 0, revenue: 0, days: {} });
                    en.opens += q; en.revenue += Math.floor(Number(r.total) || 0);
                    const dk = new Date().toISOString().slice(0, 10);
                    en.days[dk] = (en.days[dk] || 0) + q;
                } catch (e) {}
                try { updatePityIndicator(); } catch (e) {}
                try { SoundFX.play('coin'); } catch (e) {}
                nxSrvSyncCoins();
                saveState(); updateCoinDisplay();

                nxUnboxServer = true;   // дубликаты уже оплатил сервер — локально не начисляем
                if (q > 1) {
                    try { buyPackBatch(pack, q, cards); } finally { nxUnboxServer = false; }
                    return;
                }
                currentUnboxingPack = pack;
                try { PackMusic.startFor(pack); } catch (e) {}
                if (typeof THREE !== 'undefined' && webglAvailable()) {
                    try { openPack3D(pack, cards); return; }
                    catch (e) {
                        try {
                            if (pack3d) finishPack3D();
                            else { const m = document.getElementById('modal-pack3d'); if (m) m.classList.add('hidden'); showUnboxingUI(pack, cards); }
                        } catch (e2) { try { showUnboxingUI(pack, cards); } catch (e3) {} }
                    }
                } else {
                    try { showUnboxingUI(pack, cards); } catch (e) {}
                }
            } catch (e) {
                nxUnboxServer = false;
                try { nxCrashLog('nxSrvApplyPackResult: ' + ((e && e.message) || e)); } catch (e2) {}
                showToast('Пак куплен, но не удалось показать вскрытие — обновите страницу', 'error');
            }
        }

        // ---------------- шахта: добыча по времени сервера ----------------
        let nxMinerSrvLast = 0;
        function nxSrvMinerClaim(force) {
            try {
                if (!nxServerMode()) return Promise.resolve(null);
                const t = Date.now();
                if (!force && t - nxMinerSrvLast < 30000) return Promise.resolve(null); // не чаще раза в 30 c
                nxMinerSrvLast = t;
                return nxApi().miner('claim').then(r => {
                    if (r && r.ok) { nxSrvSyncCoins(); try { miner.lvl = Number(r.lvl) || miner.lvl; } catch (e) {} }
                    return r;
                });
            } catch (e) { return Promise.resolve(null); }
        }
        function nxSrvMinerUpgrade(localFn) {
            try {
                if (nxLocalPass || !nxServerMode()) return false;
                nxApi().miner('upgrade').then(r => {
                    if (!r) return;
                    if (!r.ok) {
                        nxSrvSyncCoins();
                        showToast(r.error === 'not_enough' ? ('Не хватает монет: улучшение стоит ' + fmtCoins(Number(r.cost) || 0)) : ('⚠️ ' + (r.error || '')), 'error');
                        return;
                    }
                    miner.lvl = Number(r.lvl) || miner.lvl;
                    state.stats.minerLvl = miner.lvl;
                    try { miner.last = Date.now(); minerSave(); } catch (e) {}
                    nxSrvSyncCoins();
                    try { SoundFX.play('coin'); } catch (e) {}
                    try { updateMissions('miner_upgrade', 1); } catch (e) {}
                    try { renderMiner(); } catch (e) {}
                    showToast('⛏ Кирка ' + miner.lvl + ' уровня: теперь ' + fmtCoins(minerRate()) + ' монет/сек', 'success');
                    try { minerCatCelebrate(miner.lvl); } catch (e) {}
                    try { checkAchievements(); } catch (e) {}
                }).catch(() => { nxLocalPass = true; try { localFn(); } finally { nxLocalPass = false; } });
                return true;
            } catch (e) { return false; }
        }

        // ---------------- награды: суммы и прогресс на сервере ----------------
        function nxSrvReward(kind, params, onOk) {
            try {
                if (!nxServerMode()) return false;
                nxApi().reward(kind, params || {}).then(r => {
                    if (r && r.ok) {
                        nxSrvSyncCoins();
                        if (typeof onOk === 'function') onOk(r);
                    } else if (r && r.error && r.error !== 'already_claimed' && r.error !== 'not_completed') {
                        showToast('⚠️ ' + r.error, 'error');
                    }
                }).catch(() => {});
                return true;
            } catch (e) { return false; }
        }

        // ---------------- админка: всё через серверный токен ----------------
        /**
         * Общий вызов действия админки. Клиентских прав больше нет: сервер
         * проверяет админ-токен и сам меняет данные. Без токена действие не
         * выполняется вовсе (раньше хватало cloudRole = 'owner' в консоли).
         */
        function nxAdminAct(act, params, okMsg, after) {
            try {
                const a = nxAdm();
                if (!a || !a.hasToken || !a.hasToken()) {
                    showToast('⚠️ Действие доступно только после входа в Студию по паролю (пароль проверяет сервер)', 'error');
                    nxOpenStudioPassFromAdmin();
                    return Promise.resolve({ ok: false, error: 'admin_required' });
                }
                return a.act(act, params || {}).then(r => {
                    if (r && r.ok) {
                        if (okMsg) showToast(okMsg, 'success');
                        try { nxSrvApplyBank(); } catch (e) {}
                        if (typeof after === 'function') after(r);
                    } else {
                        const noRights = r && (r.error === 'admin_required' || r.status === 403);
                        showToast(noRights ? '⛔ Нет прав администратора — войдите в Студию по паролю' : ('⚠️ ' + ((r && r.error) || 'Сервер отклонил действие')), 'error');
                        if (noRights) nxOpenStudioPassFromAdmin();
                    }
                    return r;
                });
            } catch (e) { return Promise.resolve({ ok: false, error: String(e) }); }
        }
        function nxOpenStudioPassFromAdmin() {
            try {
                studioUnlocked = false;
                if (typeof openStudioPassModal === 'function') openStudioPassModal();
            } catch (e) {}
        }

        /** Таблица «Пользователи» в Студии: данные берём с сервера. */
        function nxSrvPullUsers(then) {
            try {
                const a = nxAdm();
                if (!a || !a.hasToken || !a.hasToken()) { if (then) then(null); return Promise.resolve(null); }
                return a.users().then(r => {
                    if (r && r.ok && Array.isArray(r.players)) {
                        // переливаем в ТЕ ЖЕ структуры, которые рисует Студия, —
                        // разметка и внешний вид панели не меняются
                        const p = {}, b = {}, z = {};
                        r.players.forEach(e => {
                            p[e.cid] = {
                                cid: e.cid, n: e.n, bal: Math.floor(Number(e.bal) || 0), op: e.op || 0, jp: e.jp || 0,
                                fed: Number(e.fed) || 0, won: Number(e.won) || 0, at: e.at || 0,
                                ip: e.ip || '', dev: e.dev || '', did: e.did || '', prof: e.prof || '',
                                pk: e.pk || {}, alb: e.alb || {}
                            };
                            if (e.blocked) b[e.cid] = { on: 1, at: e.at || Date.now(), del: e.del ? 1 : 0 };
                            if (e.zeroAt) z[e.cid] = e.zeroAt;
                        });
                        siteStats.p = p; siteStats.b = b; siteStats.z = z;
                        try { siteStatsSave(); } catch (e2) {}
                        if (r.bank) window.__nxSrvBank = r.bank;
                        if (r.cfg) { try { jpcMerge(r.cfg); jpcSave(); } catch (e3) {} }
                    }
                    if (then) then(r);
                    return r;
                });
            } catch (e) { if (then) then(null); return Promise.resolve(null); }
        }

        /** Витрина банка и зала славы — с сервера (вместо общего документа). */
        function nxSrvPullPublic() {
            try {
                const a = nxApi(); if (!a) return Promise.resolve(null);
                return a.publicState().then(r => {
                    if (r && r.ok) {
                        window.__nxSrvBank = r.bank;
                        if (r.cfg) { try { jpcMerge(r.cfg); } catch (e) {} }
                        if (Array.isArray(r.hall)) {
                            jackpot.hall = r.hall.map(h => ({ n: h.n, a: Math.floor(Number(h.a) || 0), t: h.t, c: h.c, nm: h.nm ? 1 : 0 }));
                        }
                        try { jackpotRender(); } catch (e) {}
                        try { jpcLabelsRender(); } catch (e) {}
                        try { statsRenderIfVisible(); } catch (e) {}
                    }
                    return r;
                });
            } catch (e) { return Promise.resolve(null); }
        }

        // ---------------- вход в Студию: пароль проверяет сервер ----------------
        /**
         * Логин комнаты. В клиентском коде больше НЕ хранится ни пароль, ни его
         * хэш: логин берётся из открытой части комнаты (он и раньше был виден),
         * а сверяет пароль сервер. Если логин неизвестен — сервер проверит
         * единственную учётку сам.
         */
        function nxStudioLogin() {
            try {
                const ref = (typeof CLOUD !== 'undefined' && CLOUD.remoteAuth) ? CLOUD.remoteAuth : null;
                if (ref && ref.login) return String(ref.login);
            } catch (e) {}
            try { const l = cloudLocalAuth(); if (l && l.login) return String(l.login); } catch (e) {}
            return '';
        }

        /**
         * Проверка пароля Студии НА СЕРВЕРЕ. Возвращает Promise<boolean>.
         * Никаких сравнений хэшей в браузере: клиент отправляет пароль, сервер
         * сверяет его со своим PBKDF2-хэшем и выдаёт админ-токен на 12 часов.
         */
        function nxStudioVerify(pass) {
            const a = nxAdm();
            if (!a || !nxApiConfigured()) return Promise.resolve(false);
            return a.login(nxStudioLogin(), pass).then(r => !!(r && r.ok && r.adminToken)).catch(() => false);
        }

        /** Задать/сменить пароль Студии — тоже на сервере. */
        function nxStudioSetup(login, pass, currentPass) {
            const a = nxAdm();
            if (!a) return Promise.resolve({ ok: false, error: 'Сервер не подключён' });
            if (!nxApiConfigured()) return Promise.resolve({ ok: false, error: 'API не настроен: укажите адрес сервера в разделе «Облако»' });
            return a.setup(login, pass, currentPass || '', '').catch(() => ({ ok: false, error: 'Сервер недоступен' }));
        }

        // ---------------- запуск ----------------
        /** Публикуем каталог комнаты на сервере: без него сервер не знает редкости карт. */
        function nxSrvPublishCatalog(silent) {
            try {
                const a = nxAdm();
                if (!a || !a.hasToken || !a.hasToken()) return Promise.resolve(null);
                const packs = (state.packs || []).map(p => ({
                    id: p.id, title: p.title, price: Math.floor(Number(p.price) || 0),
                    retired: !!p.retired, saleUntil: p.saleUntil || undefined,
                    premiereAt: p.premiereAt || undefined, schedule: p.schedule || undefined
                })).filter(p => p.id);
                const cards = (state.cards || []).map(c => ({
                    id: c.id, packId: c.packId, rarity: c.rarity, name: c.name,
                    image: (typeof c.image === 'string' && c.image.indexOf('data:') === 0) ? '' : (c.image || '')
                })).filter(c => c.id);
                if (!packs.length || !cards.length) return Promise.resolve(null);
                return a.publishCatalog(packs, cards).then(r => {
                    if (r && r.ok && !silent) showToast('📦 Каталог комнаты опубликован на сервере: паков ' + r.packs + ', карт ' + r.cards, 'success');
                    return r;
                });
            } catch (e) { return Promise.resolve(null); }
        }

        function nxSrvBoot() {
            try {
                const a = nxApi();
                if (!a || !nxApiConfigured()) return;
                a.setRoom((typeof CLOUD !== 'undefined' && CLOUD.room) ? CLOUD.room : 'site');
                a.on('balance', () => { try { nxSrvSyncCoins(); } catch (e) {} });
                a.on('bank', () => { try { nxSrvApplyBank(); } catch (e) {} });
                a.on('blocked', d => {
                    try {
                        if (d && (d.blocked || d.deleted)) {
                            state.coins = 0; saveState(); updateCoinDisplay();
                            nxLockModal(d.deleted ? 'Учётка удалена администратором' : 'Вы заблокированы администратором');
                        } else nxHideLockModal();
                    } catch (e) {}
                });
                a.on('tamper', d => { try { nxCrashLog('balance tamper: local=' + d.local + ' server=' + d.server); } catch (e) {} });
                a.boot({
                    cid: JACKPOT_CID,
                    name: getPlayerName() || '',
                    dev: (typeof nxDeviceLabel === 'function') ? nxDeviceLabel() : '',
                    did: (typeof nxDeviceId === 'function') ? nxDeviceId() : '',
                    prof: (typeof profCode === 'function' && profCode()) ? ('код ' + profCode()) : ''
                }).then(r => {
                    if (!r || !r.ok) return;
                    // баланс прислал сервер — он и есть истина
                    nxSrvSyncCoins(); saveState(); updateCoinDisplay();
                    nxSrvApplyBank();
                    if (r.cfg) { try { jpcMerge(r.cfg); jpcSave(); } catch (e) {} }
                    if (Array.isArray(r.hall)) {
                        jackpot.hall = r.hall.map(h => ({ n: h.n, a: Math.floor(Number(h.a) || 0), t: h.t, c: h.c, nm: h.nm ? 1 : 0 }));
                        try { jackpotRender(); } catch (e) {}
                    }
                    // сторож баланса: возвращает серверное значение, если число подменили
                    a.startWatchdog(() => state.coins, v => { state.coins = v; try { saveState(); updateCoinDisplay(); } catch (e) {} }, 4000);
                    // шахта в серверном режиме: локально не капаем, забираем с сервера
                    try {
                        if (nxServerMode()) {
                            clearInterval(window.__nxSrvMinerT);
                            window.__nxSrvMinerT = setInterval(() => { if (!document.hidden) nxSrvMinerClaim(); }, 60000);
                            nxSrvMinerClaim(true);
                        }
                    } catch (e) {}
                    try { nxSrvPullPublic(); } catch (e) {}
                    try { renderSlotsUI(); renderGridUI(); renderLinesUI(); renderWheelUI(); renderMinesUI(); renderMiner(); } catch (e) {}
                }).catch(() => {});
            } catch (e) {
                try { nxCrashLog('nxSrvBoot: ' + ((e && e.message) || e)); } catch (e2) {}
            }
        }

        // после загрузки страницы — поднимаем сессию и витрину банка с сервера
        try {
            if (document.readyState === 'complete' || document.readyState === 'interactive') setTimeout(nxSrvBoot, 600);
            else document.addEventListener('DOMContentLoaded', () => setTimeout(nxSrvBoot, 600));
            window.addEventListener('load', () => setTimeout(nxSrvBoot, 1200));
            setInterval(() => { try { if (nxServerMode() && !document.hidden) nxSrvPullPublic(); } catch (e) {} }, 30000);
        } catch (e) {}
'''))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, old, new in PAIRS:
        txt = files.get(rel) if rel in files else read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        c = txt.count(o)
        if c != 1:
            problems.append('%s: якорь встретился %d раз: %s...' % (rel, c, o[:70].replace('\n', '⏎')))
            continue
        files[rel] = txt.replace(o, n, 1)
    for rel in TAG_FILES:
        txt = files.get(rel) if rel in files else read(rel)
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
        print('b463: все %d якорей найдены ровно по разу, тег %s на месте — можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b463: экономика и админка перенесены на сервер; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    print('      правок в файлах: %d' % len(PAIRS))
    return 0


if __name__ == '__main__':
    sys.exit(main())
