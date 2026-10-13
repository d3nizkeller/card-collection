#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b414 — «Джекпот» в Студии: управление общим банком сайта.

Что добавляет:
  · новая 8-я вкладка Студии «Джекпот» (кнопка в #studio-nav);
  · проценты банка: % ставки в банк, % проигрыша в банк, % банка победителю,
    несгораемый остаток, потолок одной выплаты;
  · вероятность JACKPOT в процентах отдельно для Слотов / Сетки / Линий / Колеса
    (вместо зашитых констант SLOTS_JP_W=3, GRID_JP_W=2, LINES_JP_W=1, 1 из 16);
  · «гарантия» (pity): если джекпот не выпадал N спинов — на следующем 100 %;
  · выдача джекпота конкретному игроку (или сразу всем) — суммой или всем банком;
  · ручное управление банком: поставить банк = X, +1k/+10k/+100k, сброс;
  · симулятор частоты по текущим процентам.

Настройки живут в том же облачном документе, что и сам банк (jpDoc → поле jpc),
поэтому действуют для ВСЕХ игроков сайта.

Правятся боевые артефакты (index.html, assets/app.js, sw.js) — так же, как это
делали b405…b413: tools/source-index.html и BLOCKS в tools/build.py рассинхронизированы
ещё до b412 (в монолите нет ни b412, ни b413, ни nxmob-тегов), сборка из него
сейчас не воспроизводит боевой app.js.

Запуск:  python3 tools/_b414_patch.py            — применить
         python3 tools/_b414_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OLD_V = 'nxmob73'
NEW_V = 'nxmob74'


# --------------------------------------------------------------------------- #
# JS: модуль настроек джекпота — вставляется сразу после JACKPOT_FEED
# --------------------------------------------------------------------------- #
JPC_ANCHOR = "        const JACKPOT_FEED = 1; // b96: 100% каждой ставки идёт в общий банк сайта\n"

JPC_MODULE = r'''
        // ============ b414: НАСТРОЙКИ ДЖЕКПОТА ИЗ СТУДИИ (вкладка «Джекпот») ============
        // Всё, что раньше было зашито константами (100 % ставки в банк, 100 % банка
        // победителю, вес символа JACKPOT 3/2/1, золотой сектор колеса 1 из 16), теперь
        // задаётся владельцем комнаты в Студии и уезжает в ТОМ ЖЕ облачном документе,
        // что и сам банк (jpDoc → поле jpc) — настройки видят все игроки сайта.
        // Слияние: у настроек побеждает самая свежая редакция (поле at), у выдач
        // (grant) — своя метка t на каждого игрока, как у счётчиков led/won.
        const JPC_KEY = 'nexus_jackpot_cfg';
        const JPC_PITY_KEY = 'nexus_jp_pity';
        const JPC_GAMES = ['Slots', 'Grid', 'Lines', 'Wheel'];
        const JPC_GAME_RU = { Slots: 'Слоты', Grid: 'Сетка', Lines: 'Линии', Wheel: 'Колесо' };
        const JPC_GAME_UNIT = { Slots: 'на барабан', Grid: 'на ячейку', Lines: 'на ячейку', Wheel: 'на сектор' };
        // Заводские вероятности = ровно прежние константы b220:
        //   Слоты  3 / (5*10 + 3) = 5.66 %   Сетка 2 / (5*10 + 2) = 3.85 %
        //   Линии  1 / 25        = 4.00 %   Колесо 1 / 16        = 6.25 %
        const JPC_DEFAULT_P = { Slots: 5.66, Grid: 3.85, Lines: 4, Wheel: 6.25 };
        const JPC_DEFAULTS = {
            on: 1,          // 0 — джекпот выключен: символ JACKPOT не выпадает нигде
            feedBet: 100,   // % ставки уходит в общий банк
            feedLoss: 100,  // % проигрыша докидывается в банк
            payout: 100,    // % банка получает победитель (остальное копится дальше)
            floor: 1000,    // несгораемый остаток банка (был JACKPOT_SEED)
            cap: 0,         // потолок одной выплаты, 0 — без потолка
            pSlots: JPC_DEFAULT_P.Slots, pGrid: JPC_DEFAULT_P.Grid,
            pLines: JPC_DEFAULT_P.Lines, pWheel: JPC_DEFAULT_P.Wheel,
            pitySlots: 0, pityGrid: 0, pityLines: 0, pityWheel: 0, // гарантия: 0 = выкл
            grant: {},      // { cid: { a: сумма (0 = весь банк, -1 = отменено), t: метка } }
            at: 0, by: ''
        };
        function jpcNorm(o) {
            o = (o && typeof o === 'object') ? o : {};
            const n = {};
            const num = (k, min, max, dflt) => {
                let v = Number(o[k]);
                if (!isFinite(v)) v = dflt;
                return Math.min(max, Math.max(min, v));
            };
            n.on = (Number(o.on) === 0) ? 0 : 1;
            n.feedBet = num('feedBet', 0, 1000, JPC_DEFAULTS.feedBet);
            n.feedLoss = num('feedLoss', 0, 1000, JPC_DEFAULTS.feedLoss);
            n.payout = num('payout', 0, 100, JPC_DEFAULTS.payout);
            n.floor = Math.round(num('floor', 0, 1e15, JPC_DEFAULTS.floor));
            n.cap = Math.round(num('cap', 0, 1e15, 0));
            JPC_GAMES.forEach(g => {
                n['p' + g] = num('p' + g, 0, 100, JPC_DEFAULT_P[g]);
                n['pity' + g] = Math.round(num('pity' + g, 0, 1000000, 0));
            });
            n.grant = {};
            if (o.grant && typeof o.grant === 'object') {
                for (const k in o.grant) {
                    const g = o.grant[k];
                    if (!g || typeof g !== 'object') continue;
                    const t = Math.floor(g.t) || 0;
                    if (!t) continue;
                    n.grant[String(k).slice(0, 40)] = { a: Math.max(-1, Math.floor(g.a) || 0), t: t };
                }
            }
            n.at = Math.floor(o.at) || 0;
            n.by = String(o.by || '').slice(0, 40);
            return n;
        }
        function jpcLoad() {
            try { return jpcNorm(JSON.parse(LS.getItem(JPC_KEY) || 'null')); } catch (e) { return jpcNorm(null); }
        }
        let jpc = jpcLoad();
        function jpcSave() { try { LS.setItem(JPC_KEY, JSON.stringify(jpc)); } catch (e) {} }
        function jpcGet() { return jpc; }
        function jpcOff() { return !(jpc.on | 0); }
        function jpcP(g) { const v = Number(jpc['p' + g]); return (isFinite(v) && v > 0) ? v : 0; }
        // «1 из N» — человекочитаемая частота для панели
        function jpcOdds(p) {
            p = Number(p) || 0;
            if (p <= 0) return 'не выпадет';
            if (p >= 100) return 'каждый спин';
            const n = 100 / p;
            return '1 из ' + (n >= 100 ? Math.round(n).toLocaleString('ru-RU') : (Math.round(n * 10) / 10));
        }
        function jpcMerge(remote) {
            if (!remote || typeof remote !== 'object' || !remote.at) return false;
            const inc = jpcNorm(remote);
            let ch = false;
            // выдачи сливаем по каждому игроку: побеждает свежая метка
            for (const k in inc.grant) {
                const a = inc.grant[k], b = jpc.grant[k];
                if (!b || (a.t || 0) > (b.t || 0)) { jpc.grant[k] = a; ch = true; }
            }
            // настройки: побеждает последняя редакция владельца комнаты
            if ((inc.at || 0) > (jpc.at || 0)) {
                const kept = jpc.grant;
                for (const k in kept) {
                    if (!inc.grant[k] || (kept[k].t || 0) > (inc.grant[k].t || 0)) inc.grant[k] = kept[k];
                }
                jpc = inc; ch = true;
            }
            if (ch) {
                jpcSave();
                try { jackpotRender(); } catch (e) {}
                try { if (jpcVisible()) jpcAdminRender(); else jpcAdminPreview(); } catch (e) {}
            }
            return ch;
        }
        function jpcDoc() {
            // копия: cloud-документ не должен меняться от последующих правок панели
            try { return JSON.parse(JSON.stringify(jpc)); } catch (e) { return jpcNorm(jpc); }
        }
        // вес символа JACKPOT из процента: p = w / (w + others*10)
        function jpcWeight(pct, others) {
            const p = Math.min(99.999, Math.max(0, Number(pct) || 0)) / 100;
            if (p <= 0) return 0;
            return (others * 10) * p / (1 - p);
        }
        // ---- гарантия («pity»): джекпот не реже чем раз в N спинов ----
        function jpcPityLoad() { try { const o = JSON.parse(LS.getItem(JPC_PITY_KEY) || 'null'); return (o && typeof o === 'object') ? o : {}; } catch (e) { return {}; } }
        let jpcPity = jpcPityLoad();
        function jpcPitySave() { try { LS.setItem(JPC_PITY_KEY, JSON.stringify(jpcPity)); } catch (e) {} }
        function jpcPityN(g) { const n = Math.floor(jpc['pity' + g]) || 0; return n > 0 ? n : 0; }
        function jpcPityForce(g) { const n = jpcPityN(g); return !!(n && !jpcOff() && (Math.floor(jpcPity[g]) || 0) >= n); }
        function jpcPityNote(g, hit) { if (!jpcPityN(g)) return; jpcPity[g] = hit ? 0 : (Math.floor(jpcPity[g]) || 0) + 1; jpcPitySave(); }
        // вероятность конкретного спина: базовая из настроек или 100 % по гарантии
        function jpcSpinPct(g) { return jpcOff() ? 0 : (jpcPityForce(g) ? 100 : jpcP(g)); }
        // ---- принудительная выдача джекпота игроку (cid; '*' = всем сразу) ----
        function jpcApplyGrants() {
            try {
                const g = jpc.grant || {};
                let best = null;
                [g[JACKPOT_CID], g['*']].forEach(x => { if (x && x.t && (!best || x.t > best.t)) best = x; });
                if (!best) return;
                let ack = 0;
                try { ack = parseInt(LS.getItem('nexus_jp_grant_ack') || '0', 10) || 0; } catch (e) {}
                if (best.t <= ack) return;
                try { LS.setItem('nexus_jp_grant_ack', String(best.t)); } catch (e) {}
                const amount = Math.floor(best.a) || 0;
                if (amount < 0) return; // владелец отменил выдачу
                if (amount > 0) {
                    state.coins += amount;
                    saveState(); updateCoinDisplay();
                    try { launchConfetti(180); } catch (e) {}
                    try { SoundFX.play('legendary'); } catch (e) {}
                    showToast('👑 Джекпот выдан администратором: +' + fmtCoins(amount) + ' монет', 'success');
                } else {
                    jackpotWin(); // 0 = весь банк по текущему payout %
                }
                try { if (jpcVisible()) jpcAdminRender(); } catch (e) {}
            } catch (e) {}
        }
        // ---- правки из панели: локально сразу, в облако — кнопкой «Опубликовать» ----
        function jpcSet(patch) {
            if (!patch || typeof patch !== 'object') return;
            for (const k in patch) {
                if (k === 'grant' || k === 'at' || k === 'by') continue;
                jpc[k] = patch[k];
            }
            const keep = jpc.grant;
            jpc = jpcNorm(jpc);
            jpc.grant = keep;
            jpcSave();
            try { jackpotRender(); } catch (e) {}
            try { jpcAdminPreview(); } catch (e) {}
        }
        function jpcAdminGuard() {
            if (typeof cloudGuest === 'function' && cloudGuest()) {
                showToast('Режим участника: управлять джекпотом может только создатель комнаты', 'error');
                return true;
            }
            return false;
        }
        function jpcPublish(silent) {
            if (jpcAdminGuard()) return;
            jpc.at = Date.now(); jpc.by = JACKPOT_CID;
            jpcSave();
            try { jpSyncNow(); } catch (e) {}
            if (!silent) showToast('👑 Настройки джекпота опубликованы для всех игроков сайта', 'success');
        }
        // ---- ручное управление банком ----
        // Счётчики led/won растут только вверх (CRDT max-слияние), поэтому «поставить
        // банк = X» делаем дельтой: не хватает — докидываем себе во взносы, лишнее —
        // записываем себе в выплаты. Оба счётчика уже синхронизируются со всеми.
        function jpcSetPool(target) {
            if (jpcAdminGuard()) return;
            target = Math.max(0, Math.round(Number(target) || 0));
            const now = jackpotPool();
            const d = target - now;
            if (!d) { showToast('Банк уже равен ' + fmtCoins(target), 'info'); return; }
            if (d > 0) jackpot.led[JACKPOT_CID] = (jackpot.led[JACKPOT_CID] || 0) + d;
            else jackpot.won[JACKPOT_CID] = (jackpot.won[JACKPOT_CID] || 0) + (-d);
            jackpotSave(); jackpotRender();
            try { jpcAdminPreview(); } catch (e) {}
            try { jpSyncNow(); } catch (e) {}
            showToast((d > 0 ? '📈 Банк поднят до ' : '📉 Банк снижен до ') + fmtCoins(jackpotPool()), 'success');
        }
        function jpcNudgePool(delta) { jpcSetPool(jackpotPool() + Math.round(Number(delta) || 0)); }
        function jpcResetPoolFloor() { jpcSetPool(Math.max(0, Math.round(jpc.floor || 0))); }
        function jpcParseAmount(raw, what) {
            raw = String(raw == null ? '' : raw).trim();
            if (!raw) { showToast('Введите ' + what + ' — например 100k', 'error'); return null; }
            let v = Number(raw.replace(/\s|_/g, ''));
            if (!isFinite(v)) { try { v = parseBetStr(raw); } catch (e) {} }
            if (!isFinite(v) || v < 0) { showToast('Не понял ' + what + ': ' + raw, 'error'); return null; }
            return Math.round(v);
        }
        function jpcSetPoolInput() {
            const el = document.getElementById('jpc-pool-set');
            const v = jpcParseAmount(el && el.value, 'сумму банка');
            if (v === null) return;
            jpcSetPool(v);
            if (el) el.value = '';
        }
        // ---- выдача джекпота игроку ----
        function jpcNameOf(cid) {
            try { if (jackpot.names && jackpot.names[cid]) return jackpot.names[cid]; } catch (e) {}
            try { const p = siteStats.p[cid]; if (p && p.n) return p.n; } catch (e) {}
            return '';
        }
        function jpcGrant(cid, amount) {
            if (jpcAdminGuard()) return;
            cid = String(cid || '').slice(0, 40);
            if (!cid) return;
            const a = Math.max(0, Math.round(Number(amount) || 0)); // 0 = весь банк по payout %
            jpc.grant[cid] = { a: a, t: Date.now() };
            jpc.at = Date.now(); jpc.by = JACKPOT_CID;
            jpcSave();
            try { jpcAdminRender(); } catch (e) {}
            try { jpSyncNow(); } catch (e) {}
            const who = cid === '*' ? 'ВСЕМ игрокам сайта' : (jpcNameOf(cid) || cid.slice(0, 10));
            showToast('👑 Джекпот назначен: ' + who + ' — ' + (a > 0 ? fmtCoins(a) + ' монет' : 'весь банк (' + jpc.payout + ' %)'), 'success');
            if (cid === JACKPOT_CID || cid === '*') setTimeout(() => { try { jpcApplyGrants(); } catch (e) {} }, 60);
        }
        function jpcGrantFromInput(cid) {
            const el = document.getElementById('jpc-grant-amt');
            const v = jpcParseAmount(el && el.value, 'сумму выдачи');
            if (v === null) return;
            if (v <= 0) { showToast('0 = весь банк. Для выдачи всего банка жмите «Выдать банк»', 'info'); return; }
            jpcGrant(cid, v);
        }
        function jpcGrantCancel(cid) {
            if (jpcAdminGuard()) return;
            cid = String(cid || '');
            if (!cid || !jpc.grant[cid]) return;
            jpc.grant[cid] = { a: -1, t: Date.now() }; // отмена доезжает до игрока той же меткой
            jpc.at = Date.now(); jpcSave();
            try { jpSyncNow(); } catch (e) {}
            try { jpcAdminRender(); } catch (e) {}
            showToast('Выдача отменена', 'info');
        }
        function jpcGrantAllFromInput() {
            const el = document.getElementById('jpc-grant-amt');
            const raw = String((el && el.value) || '').trim();
            if (!raw) { jpcGrant('*', 0); return; }
            jpcGrantFromInput('*');
        }
        // ============ b414: ПАНЕЛЬ «ДЖЕКПОТ» В СТУДИИ ============
        function jpcVisible() {
            try {
                const s = document.querySelector('.studio-sec[data-sec="jackpot"]');
                return !!(s && !s.hidden && !s.classList.contains('hidden'));
            } catch (e) { return false; }
        }
        function jpcEsc(s) {
            return String(s == null ? '' : s).replace(/[&<>"'`\\]/g, c => ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;', '`': '&#96;', '\\': '&#92;'
            }[c]));
        }
        function jpcSumChips() {
            let wins = 0, fed = 0, won = 0;
            for (const k in jackpot.wins) wins += jackpot.wins[k] || 0;
            for (const k in jackpot.led) fed += jackpot.led[k] || 0;
            for (const k in jackpot.won) won += jackpot.won[k] || 0;
            const pool = jackpotPool();
            const chip = (ic, col, lab, val) => '<div class="rounded-xl border border-slate-800 bg-slate-950/60 px-2.5 py-2 min-w-0">' +
                '<p class="text-[9px] uppercase tracking-wide text-slate-500 flex items-center gap-1.5 truncate"><i class="fa-solid ' + ic + ' ' + col + '"></i>' + lab + '</p>' +
                '<p class="text-sm sm:text-base font-black text-white truncate mt-0.5">' + val + '</p></div>';
            let pend = 0;
            for (const k in (jpc.grant || {})) if ((jpc.grant[k].a | 0) >= 0) pend++;
            return chip('fa-crown', 'text-amber-400', 'Банк сейчас', fmtCoins(pool)) +
                chip('fa-hand-holding-dollar', 'text-emerald-400', 'Уйдёт победителю', fmtCoins(Math.round(pool * (jpc.payout / 100))) + ' (' + jpc.payout + '%)') +
                chip('fa-trophy', 'text-yellow-300', 'Сорвано джекпотов', String(wins)) +
                chip('fa-users', 'text-sky-400', 'Копят банк', String(jackpotPlayers())) +
                chip('fa-sack-dollar', 'text-slate-300', 'Внесено в банк', fmtCoins(fed)) +
                chip('fa-wallet', 'text-violet-300', 'Выплачено из банка', fmtCoins(won)) +
                chip('fa-gift', 'text-rose-300', 'Назначено выдач', String(pend));
        }
        function jpcAdminPreview() {
            JPC_GAMES.forEach(g => {
                const o = document.getElementById('jpc-o' + g);
                if (o) o.textContent = jpcOff() ? 'выключен' : jpcOdds(jpcP(g));
                const t = document.getElementById('jpc-pt' + g);
                if (t) t.textContent = (Math.round(jpcP(g) * 100) / 100) + '%';
            });
            const sum = document.getElementById('jpc-sum');
            if (sum) sum.innerHTML = jpcSumChips();
            const pn = document.getElementById('jpc-pool-now');
            if (pn) pn.textContent = fmtCoins(jackpotPool());
        }
        function jpcProbRows() {
            return JPC_GAMES.map(g => {
                const p = jpcP(g), pity = Math.floor(jpc['pity' + g]) || 0;
                return '<div class="rounded-xl border border-slate-800 bg-slate-950/60 px-2.5 py-2 space-y-1.5">' +
                    '<div class="flex items-center gap-2">' +
                        '<span class="text-[11px] font-bold text-white shrink-0" style="min-width:5.5rem">' + JPC_GAME_RU[g] +
                            ' <span class="text-[9px] font-semibold text-slate-500">' + JPC_GAME_UNIT[g] + '</span></span>' +
                        '<input id="jpc-p' + g + '" type="range" min="0" max="50" step="0.05" value="' + p + '" ' +
                            'oninput="jpcSet({p' + g + ':Number(this.value)})" class="flex-1 accent-amber-500 min-w-[6rem]">' +
                        '<span id="jpc-pt' + g + '" class="text-[11px] font-mono font-black text-amber-300 text-right shrink-0" style="min-width:3.4rem">' +
                            (Math.round(p * 100) / 100) + '%</span>' +
                        '<span id="jpc-o' + g + '" class="text-[10px] text-slate-400 text-right shrink-0 hidden sm:block" style="min-width:5.5rem">' +
                            (jpcOff() ? 'выключен' : jpcOdds(p)) + '</span>' +
                    '</div>' +
                    '<div class="flex flex-wrap items-center gap-1.5">' +
                        '<span class="text-[9px] text-slate-500 shrink-0" style="min-width:5.5rem">гарантия, спинов</span>' +
                        '<input id="jpc-pity' + g + '" type="number" min="0" max="1000000" step="1" value="' + pity + '" ' +
                            'onchange="jpcSet({pity' + g + ':Math.max(0,Math.round(Number(this.value)||0))})" ' +
                            'class="bg-slate-900 border border-slate-700 rounded-lg px-2 py-0.5 text-[11px] font-bold text-white" style="width:6rem">' +
                        '<span class="text-[9px] text-slate-600">0 = выкл · N = если джекпот не выпадал N спинов подряд, на следующем он гарантирован</span>' +
                    '</div>' +
                '</div>';
            }).join('');
        }
        function jpcUsersHtml() {
            let q = '';
            try { q = String(document.getElementById('jpc-search').value || '').trim().toLowerCase(); } catch (e) {}
            const now = Date.now();
            const list = [];
            const seen = {};
            try {
                for (const k in siteStats.p) {
                    const e = siteStats.p[k];
                    if (!e || !e.cid || seen[e.cid]) continue;
                    seen[e.cid] = 1; list.push(e);
                }
            } catch (e) {}
            try { // игроки из зала славы джекпота — у них может не быть записи в реестре
                for (const cid in jackpot.names) {
                    if (seen[cid]) continue;
                    seen[cid] = 1;
                    list.push({ cid: cid, n: jackpot.names[cid], bal: 0, jp: 0, at: 0 });
                }
            } catch (e) {}
            let vis = q
                ? list.filter(e => String(e.n || '').toLowerCase().indexOf(q) >= 0 || String(e.cid || '').toLowerCase().indexOf(q) >= 0)
                : list;
            vis.sort((a, c) => (c.at || 0) - (a.at || 0));
            const total = vis.length;
            vis = vis.slice(0, 80);
            if (!vis.length) {
                return '<p class="text-[11px] text-slate-500">Никого не нашлось. Нажмите «Обновить» — список игроков приходит из облака сайта (ищите по имени или ID).</p>';
            }
            const btn = 'px-2 py-1 rounded-lg text-[10px] font-black transition shrink-0';
            return '<p class="text-[9px] text-slate-600">Показано ' + vis.length + ' из ' + total + ' · зелёная точка = игрок на сайте сейчас</p>' +
                vis.map(e => {
                    const on = now - (e.at || 0) < 120000;
                    const cid = jpcEsc(e.cid);
                    const pend = jpc.grant[e.cid];
                    const active = pend && (pend.a | 0) >= 0;
                    return '<div class="flex flex-wrap items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-950/50 px-2 py-1.5">' +
                        '<i class="fa-solid fa-circle shrink-0" style="font-size:7px;color:' + (on ? '#34d399' : '#475569') + '"></i>' +
                        '<span class="text-[11px] font-bold text-white truncate" style="max-width:11rem">' + jpcEsc(e.n || 'без имени') + '</span>' +
                        '<span class="text-[9px] font-mono text-slate-500 truncate" style="max-width:8rem">' + cid + '</span>' +
                        '<span class="text-[10px] text-slate-400 ml-auto whitespace-nowrap">' + fmtCoins(e.bal || 0) + ' · 🏆 ' + (e.jp | 0) + '</span>' +
                        (active ? '<span class="text-[9px] font-bold text-amber-300 bg-amber-500/10 border border-amber-500/40 rounded-md px-1.5 py-0.5 whitespace-nowrap">назначено: ' + ((pend.a | 0) > 0 ? fmtCoins(pend.a) : 'весь банк') + '</span>' : '') +
                        '<button type="button" onclick="jpcGrant(\'' + cid + '\',0)" class="' + btn + ' bg-amber-500 hover:bg-amber-400 text-slate-950">Выдать банк</button>' +
                        '<button type="button" onclick="jpcGrantFromInput(\'' + cid + '\')" class="' + btn + ' bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-bold">Выдать сумму</button>' +
                        (active ? '<button type="button" onclick="jpcGrantCancel(\'' + cid + '\')" class="' + btn + ' bg-slate-900 hover:bg-rose-950/60 border border-slate-800 text-slate-400 font-bold">Отменить</button>' : '') +
                    '</div>';
                }).join('');
        }
        function jpcAdminUsers() {
            const box = document.getElementById('jpc-users');
            if (box) box.innerHTML = jpcUsersHtml();
        }
        function jpcAdminRender() {
            const sec = document.querySelector('.studio-sec[data-sec="jackpot"]');
            if (!sec) return;
            const set = (id, v) => { const el = document.getElementById(id); if (el && document.activeElement !== el) el.value = v; };
            set('jpc-feedBet', jpc.feedBet);
            set('jpc-feedLoss', jpc.feedLoss);
            set('jpc-payout', jpc.payout);
            set('jpc-floor', jpc.floor);
            set('jpc-cap', jpc.cap);
            const on = document.getElementById('jpc-on');
            if (on) on.checked = !jpcOff();
            const prob = document.getElementById('jpc-prob');
            if (prob) prob.innerHTML = jpcProbRows();
            jpcAdminPreview();
            jpcAdminUsers();
            const note = document.getElementById('jpc-note');
            if (note) {
                note.textContent = jpc.at
                    ? ('опубликовано ' + new Date(jpc.at).toLocaleString('ru-RU') + (jpc.by === JACKPOT_CID ? ' (вами)' : ''))
                    : 'заводские настройки — не опубликованы';
            }
        }
        function jpcRefresh() {
            try { jpSyncNow(); } catch (e) {}
            try { siteStatsSelfUpdate(); } catch (e) {}
            try { jpcAdminRender(); } catch (e) {}
            try { jpcSim(); } catch (e) {}
            showToast('🔄 Тянем свежие данные банка и игроков…', 'info');
        }
        // ---- симулятор: как часто джекпот будет выпадать с текущими процентами ----
        function jpcSim() {
            const out = document.getElementById('jpc-sim-out');
            if (!out) return;
            const off = jpcOff();
            const ps = off ? 0 : jpcP('Slots') / 100;
            const pg = off ? 0 : jpcP('Grid') / 100;
            const pl = off ? 0 : jpcP('Lines') / 100;
            const pw = off ? 0 : jpcP('Wheel') / 100;
            const slotsHit = ps * ps * ps;                       // три барабана подряд
            const linesHit = 1 - Math.pow(1 - pl * pl * pl, 10);  // 10 линий, 3 слева направо
            // Сетка 5×4: Monte-Carlo, 3+ символов JACKPOT где угодно на поле
            const N = 20000, CELLS = 20;
            let gh = 0;
            if (pg > 0) {
                for (let s = 0; s < N; s++) {
                    let c = 0;
                    for (let i = 0; i < CELLS; i++) if (Math.random() < pg) c++;
                    if (c >= 3) gh++;
                }
            }
            const gridHit = gh / N;
            const row = (name, p, extra) => '<tr class="border-t border-slate-800/70">' +
                '<td class="py-1.5 pr-2 text-slate-300 font-semibold whitespace-nowrap">' + name + '</td>' +
                '<td class="py-1.5 pr-2 text-right font-mono text-white whitespace-nowrap">' + (p > 0 ? (100 * p).toFixed(p < 0.001 ? 5 : 3) + '%' : '0%') + '</td>' +
                '<td class="py-1.5 pr-2 text-right font-mono text-amber-300 whitespace-nowrap">' + (off ? 'выключен' : jpcOdds(100 * p)) + '</td>' +
                '<td class="py-1.5 text-right font-mono text-slate-500 whitespace-nowrap">' + (extra || '') + '</td></tr>';
            const pity = g => { const n = Math.floor(jpc['pity' + g]) || 0; return n > 0 ? ('гарант. ' + n) : ''; };
            out.innerHTML = '<table class="w-full text-[11px]"><tbody>' +
                row('Слоты · 3 барабана', slotsHit, pity('Slots')) +
                row('Сетка · 20 ячеек, 3+', gridHit, pity('Grid')) +
                row('Линии · 10 линий', linesHit, pity('Lines')) +
                row('Колесо · сектор', pw, pity('Wheel')) +
                '</tbody></table>' +
                '<p class="text-[10px] text-slate-500 mt-2 leading-snug">Чистая математика по текущим процентам' +
                (pg > 0 ? ' (сетка — прогон ' + N.toLocaleString('ru-RU') + ' спинов)' : '') +
                '. «Гарантия» здесь не учтена: она поднимает шанс до 100 % на N-м спине без джекпота.</p>';
        }
'''


# --------------------------------------------------------------------------- #
# JS: точечные правки игровых механик
# --------------------------------------------------------------------------- #
JS_PATCHES = [
    ('модуль настроек джекпота',
     JPC_ANCHOR,
     JPC_ANCHOR + JPC_MODULE),

    ('jackpotPool: несгораемый остаток из настроек',
     """        function jackpotPool() {
            let c = 0, w = 0;
            for (const k in jackpot.led) c += jackpot.led[k] || 0;
            for (const k in jackpot.won) w += jackpot.won[k] || 0;
            return Math.max(JACKPOT_SEED, Math.round(JACKPOT_SEED + c - w));
        }""",
     """        function jackpotPool() {
            let c = 0, w = 0;
            for (const k in jackpot.led) c += jackpot.led[k] || 0;
            for (const k in jackpot.won) w += jackpot.won[k] || 0;
            // b414: несгораемый остаток банка задаётся в Студии (заводской = прежний сид)
            const fl = Number(jpc.floor);
            const floor = (isFinite(fl) && fl >= 0) ? Math.round(fl) : JACKPOT_SEED;
            return Math.max(floor, Math.round(JACKPOT_SEED + c - w));
        }"""),

    ('jackpotFeed: процент взноса ставки',
     """        function jackpotFeed(bet) {
            const x = Math.max(1, Math.round((bet || 0) * JACKPOT_FEED));
            jackpot.led[JACKPOT_CID] = (jackpot.led[JACKPOT_CID] || 0) + x;""",
     """        function jackpotFeed(bet) {
            // b414: процент взноса ставки в банк настраивается в Студии (было всегда 100 %)
            const pct = isFinite(+jpc.feedBet) ? Math.max(0, +jpc.feedBet) : 100;
            const x = pct > 0 ? Math.max(1, Math.round((bet || 0) * JACKPOT_FEED * pct / 100)) : 0;
            if (x <= 0) return;
            jackpot.led[JACKPOT_CID] = (jackpot.led[JACKPOT_CID] || 0) + x;"""),

    ('jackpotOnLoss: процент взноса проигрыша',
     """        function jackpotOnLoss(loss) {
            const add = Math.max(1, Math.round((loss || 0) * 1));
            jackpot.led[JACKPOT_CID] = (jackpot.led[JACKPOT_CID] || 0) + add;""",
     """        function jackpotOnLoss(loss) {
            // b414: процент проигрыша, уходящий в банк, настраивается в Студии (было всегда 100 %)
            const pct = isFinite(+jpc.feedLoss) ? Math.max(0, +jpc.feedLoss) : 100;
            const add = pct > 0 ? Math.max(1, Math.round((loss || 0) * pct / 100)) : 0;
            if (add <= 0) return 0;
            jackpot.led[JACKPOT_CID] = (jackpot.led[JACKPOT_CID] || 0) + add;"""),

    ('jackpotWin: выплата payout % банка с потолком',
     """        function jackpotWin() {
            const prize = jackpotPool();
            jackpot.won[JACKPOT_CID] = (jackpot.won[JACKPOT_CID] || 0) + prize;""",
     """        function jackpotWin() {
            // b414: победителю уходит payout % банка (было всегда 100 %), остаток копится
            // дальше; cap — потолок одной выплаты (0 = без потолка).
            const pool = jackpotPool();
            const pct = isFinite(+jpc.payout) ? Math.min(100, Math.max(0, +jpc.payout)) : 100;
            let prize = Math.round(pool * pct / 100);
            const cpm = Math.round(Number(jpc.cap) || 0);
            if (cpm > 0 && prize > cpm) prize = cpm;
            prize = Math.max(0, prize);
            jackpot.won[JACKPOT_CID] = (jackpot.won[JACKPOT_CID] || 0) + prize;"""),

    ('jackpotWin: честный текст тоста при payout < 100',
     """            showToast('👑 JACKPOT! Общий банк сайта ваш: +' + fmtCoins(prize) + ' монет', 'success');""",
     """            showToast('👑 JACKPOT! +' + fmtCoins(prize) + ' монет' + (pct < 100 ? ' (' + pct + '% банка)' : ' — весь банк сайта ваш'), 'success');"""),

    ('slotsWeightedRand: вероятность вместо жёсткого веса',
     """        const SLOTS_JP_W = 3, GRID_JP_W = 2;
        function slotsWeightedRand(jw) {
            const syms = slots.symbols;
            if (!syms.length) return 0;
            const wJp = (Number.isFinite(+jw) && +jw > 0) ? +jw : SLOTS_JP_W;
            let tot = 0;
            for (let i = 0; i < syms.length; i++) tot += syms[i].jackpot ? wJp : 10;
            let r = Math.random() * tot;
            for (let i = 0; i < syms.length; i++) { r -= syms[i].jackpot ? wJp : 10; if (r <= 0) return i; }
            return syms.length - 1;
        }""",
     """        // b414: SLOTS_JP_W/GRID_JP_W оставлены как «заводские» значения; аргумент теперь —
        // ВЕРОЯТНОСТЬ символа JACKPOT в процентах (на барабан / на ячейку), из настроек Студии.
        const SLOTS_JP_W = 3, GRID_JP_W = 2;
        function slotsWeightedRand(pct) {
            const syms = slots.symbols;
            if (!syms.length) return 0;
            let others = 0, hasJp = false;
            for (let i = 0; i < syms.length; i++) { if (syms[i].jackpot) hasJp = true; else others++; }
            const p = (pct === undefined || pct === null) ? jpcP('Slots') : Number(pct);
            const wJp = (hasJp && !jpcOff() && isFinite(p) && p > 0) ? jpcWeight(p, others) : 0;
            const tot = others * 10 + wJp;
            if (tot <= 0) return 0;
            let r = Math.random() * tot;
            for (let i = 0; i < syms.length; i++) {
                const w = syms[i].jackpot ? wJp : 10;
                if (w <= 0) continue;      // JACKPOT выключен — символ просто не выбирается
                r -= w; if (r <= 0) return i;
            }
            return syms.length - 1;
        }"""),

    ('Слоты: вероятность спина + счётчик гарантии',
     """            const res = [0, 1, 2].map(() => slotsWeightedRand()); // b56: JACKPOT редок""",
     """            const res = [0, 1, 2].map(() => slotsWeightedRand(jpcSpinPct('Slots'))); // b56; b414: вероятность из Студии"""),

    ('slotsFinish: отметка гарантии',
     """        function slotsFinish(res, bet) {
            const syms = res.map(i => slots.symbols[i] || { rarity: 'common', name: '?' });""",
     """        function slotsFinish(res, bet) {
            const syms = res.map(i => slots.symbols[i] || { rarity: 'common', name: '?' });
            // b414: счётчик гарантии — сорвали банк в этом спине или нет
            try { jpcPityNote('Slots', !!(res[0] === res[1] && res[1] === res[2] && syms[0] && syms[0].jackpot)); } catch (e) {}"""),

    ('Сетка: своя вероятность из настроек',
     """            return slots.symbols[slotsWeightedRand(GRID_JP_W)]; // b183: свой вес JACKPOT для Сетки""",
     """            return slots.symbols[slotsWeightedRand(jpcSpinPct('Grid'))]; // b183; b414: вероятность из Студии"""),

    ('gridStep: отметка гарантии',
     """            const jg = groups.find(gp => gp.jackpot && gp.count >= 3);
            if (jg) {""",
     """            const jg = groups.find(gp => gp.jackpot && gp.count >= 3);
            try { jpcPityNote('Grid', !!jg); } catch (e) {} // b414: счётчик гарантии
            if (jg) {"""),

    ('Линии: вероятность из настроек',
     """        const LINES_JP_W = 1;
        function linesRand() {
            const r = Math.random() * 25;
            if (r < LINES_JP_W) return 3; // JACKPOT
            return Math.min(2, Math.floor((r - LINES_JP_W) / ((25 - LINES_JP_W) / 3)));
        }""",
     """        const LINES_JP_W = 1; // b414: заводское значение = 1 из 25 (4 %)
        function linesRand() {
            // b414: шанс JACKPOT на ячейку берётся из настроек Студии (проценты)
            const p = jpcSpinPct('Lines');
            if (p > 0 && Math.random() * 100 < p) return 3; // JACKPOT
            return Math.min(2, Math.floor(Math.random() * 3));
        }"""),

    ('Линии: отметка гарантии',
     """            let jpPrize = 0;
            if (jpHit) { jpPrize = jackpotWin(); if (lines.auto) linesToggleAuto(); }""",
     """            let jpPrize = 0;
            try { jpcPityNote('Lines', !!jpHit); } catch (e) {} // b414: счётчик гарантии
            if (jpHit) { jpPrize = jackpotWin(); if (lines.auto) linesToggleAuto(); }"""),

    ('Колесо: выбор сектора по настраиваемой вероятности',
     """        const WHEEL_STEP = Math.PI * 2 / WHEEL_SECTORS.length;""",
     """        const WHEEL_STEP = Math.PI * 2 / WHEEL_SECTORS.length;
        // b414: сектор выбираем по настраиваемой вероятности золотого JACKPOT-сектора.
        // Заводские 1 из 16 = 6.25 %; при 0 % колесо банк не срывает, но продолжает его кормить.
        function wheelPickIdx() {
            const n = WHEEL_SECTORS.length;
            const gold = [], rest = [];
            for (let i = 0; i < n; i++) (WHEEL_SECTORS[i].t === 'jackpot' ? gold : rest).push(i);
            const p = jpcSpinPct('Wheel');
            if (gold.length && p > 0 && Math.random() * 100 < p) return gold[Math.floor(Math.random() * gold.length)];
            if (rest.length) return rest[Math.floor(Math.random() * rest.length)];
            return Math.floor(Math.random() * n);
        }"""),

    ('Колесо: spin использует wheelPickIdx',
     """            const idx = Math.floor(Math.random() * WHEEL_SECTORS.length);
            const jitter = (Math.random() - 0.5) * WHEEL_STEP * 0.6;""",
     """            const idx = wheelPickIdx(); // b414: шанс золотого сектора из настроек Студии
            const jitter = (Math.random() - 0.5) * WHEEL_STEP * 0.6;"""),

    ('wheelAward: отметка гарантии',
     """        function wheelAward(idx) {
            const sec = WHEEL_SECTORS[idx];""",
     """        function wheelAward(idx) {
            const sec = WHEEL_SECTORS[idx];
            try { jpcPityNote('Wheel', !!(sec && sec.t === 'jackpot')); } catch (e) {} // b414: счётчик гарантии"""),

    ('jpDoc: настройки уезжают в облако вместе с банком',
     """                jp: { led: jackpot.led, won: jackpot.won, wins: jackpot.wins, names: jackpot.names, hall: jackpot.hall },""",
     """                jp: { led: jackpot.led, won: jackpot.won, wins: jackpot.wins, names: jackpot.names, hall: jackpot.hall },
                jpc: jpcDoc(), // b414: настройки джекпота и назначенные выдачи — видны всему сайту"""),

    ('jpSyncNow: приём чужих настроек (первое чтение)',
     """            const cycle = depth => jpFetch().then(remote => {
                jackpotMerge(remote && remote.jp ? remote.jp : remote);""",
     """            const cycle = depth => jpFetch().then(remote => {
                jackpotMerge(remote && remote.jp ? remote.jp : remote);
                jpcMerge(remote && remote.jpc); // b414: настройки джекпота от владельца комнаты"""),

    ('jpSyncNow: приём чужих настроек (контрольное чтение)',
     """                    const rj = (chk && chk.jp) ? chk.jp : chk;
                    jackpotMerge(rj);""",
     """                    const rj = (chk && chk.jp) ? chk.jp : chk;
                    jackpotMerge(rj);
                    jpcMerge(chk && chk.jpc); // b414"""),

    ('jpSyncNow: применение выдачи ко мне',
     """                    siteStatsApplyToMe();       // b277: команды админа мне — обнуление баланса / блокировка""",
     """                    siteStatsApplyToMe();       // b277: команды админа мне — обнуление баланса / блокировка
                    jpcApplyGrants();           // b414: назначенный мне джекпот — сразу на баланс"""),

    ('STUDIO_SECS: новая вкладка «Джекпот»',
     """        const STUDIO_SECS = ['cloud', 'packs', 'catalog', 'cards', 'schedule', 'story', 'stats']; // b164: + «Каталог»; b253: + «Нарезка карточек» (сторис 9:16); b277: + «Статистика»""",
     """        const STUDIO_SECS = ['cloud', 'packs', 'catalog', 'cards', 'schedule', 'story', 'stats', 'jackpot']; // b164: + «Каталог»; b253: + «Нарезка карточек» (сторис 9:16); b277: + «Статистика»; b414: + «Джекпот»"""),

    ('showStudioSec: рендер панели джекпота',
     """            if (name === 'stats') { try { statsRender(); jpSyncNow(); } catch (e) {} } // b277: вкладка статистики — сразу тянем свежие данные из облака""",
     """            if (name === 'stats') { try { statsRender(); jpSyncNow(); } catch (e) {} } // b277: вкладка статистики — сразу тянем свежие данные из облака
            if (name === 'jackpot') { try { jpcAdminRender(); jpcSim(); jpSyncNow(); } catch (e) {} } // b414: панель управления джекпотом"""),
]


# --------------------------------------------------------------------------- #
# HTML: кнопка вкладки + сама секция
# --------------------------------------------------------------------------- #
NAV_BTN_CLS = ('w-full min-w-0 px-1 sm:px-2 py-1.5 rounded-lg text-[10px] sm:text-xs font-bold transition '
               'flex items-center justify-center gap-1 sm:gap-1.5 whitespace-nowrap overflow-hidden '
               'bg-slate-800 text-slate-300 border border-slate-700')

STATS_NAV_OLD = ('                    <button id="studio-nav-stats" type="button" onclick="showStudioSec(\'stats\')" '
                 'class="' + NAV_BTN_CLS + '"><i class="fa-solid fa-chart-line"></i>Статистика</button>\n')

JACKPOT_NAV_NEW = ('                    <!-- b414: управление общим джекпотом сайта -->\n'
                   '                    <button id="studio-nav-jackpot" type="button" onclick="showStudioSec(\'jackpot\')" '
                   'class="' + NAV_BTN_CLS + '"><i class="fa-solid fa-crown"></i>Джекпот</button>\n')

NUM_FIELD = '''                    <label class="block rounded-xl border border-slate-800 bg-slate-950/60 px-2.5 py-2 min-w-0">
                        <span class="block text-[9px] uppercase tracking-wide text-slate-500 mb-1 leading-tight">{label}</span>
                        <input id="jpc-{key}" type="number" min="{mn}" max="{mx}" step="{st}" value="{val}"
                               onchange="jpcSet({{{key}:Number(this.value)}})"
                               class="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-sm font-black text-white">
                        <span class="block text-[9px] text-slate-600 mt-1 leading-tight">{hint}</span>
                    </label>'''


def _field(key, label, val, mn, mx, st, hint):
    return NUM_FIELD.format(key=key, label=label, val=val, mx=mx, mn=mn, st=st, hint=hint)


STUDIO_SEC_JACKPOT = '''
            <!-- b414: управление общим джекпотом сайта — проценты, вероятности, выдача игрокам -->
            <div class="studio-sec space-y-3" data-sec="jackpot" hidden>
            <div class="bg-slate-900/80 p-3 sm:p-4 rounded-2xl border border-slate-800 space-y-3">
                <div class="flex flex-wrap items-center justify-between gap-2">
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                        <i class="fa-solid fa-crown text-amber-400"></i>
                        <span>Управление джекпотом сайта</span>
                    </h3>
                    <div class="flex flex-wrap items-center gap-2">
                        <span id="jpc-note" class="text-[10px] text-slate-500"></span>
                        <button type="button" onclick="jpcRefresh()" class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-[11px] font-semibold text-slate-200 transition"><i class="fa-solid fa-arrows-rotate mr-1"></i>Обновить</button>
                        <button type="button" onclick="jpcPublish()" class="px-2.5 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-lg text-[11px] font-black transition"><i class="fa-solid fa-bullhorn mr-1"></i>Опубликовать для всех</button>
                    </div>
                </div>
                <div id="jpc-sum" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-2"></div>
                <label class="flex items-start gap-2 text-[11px] font-bold text-slate-200 cursor-pointer leading-snug">
                    <input id="jpc-on" type="checkbox" onchange="jpcSet({on:this.checked?1:0})" class="w-4 h-4 mt-0.5 shrink-0 accent-amber-500">
                    <span>Джекпот включён. Снимите — символ JACKPOT перестанет выпадать во всех играх, но банк продолжит копиться.</span>
                </label>
                <p class="text-[10px] text-slate-500 leading-snug"><i class="fa-solid fa-circle-info text-amber-400 mr-1"></i>Настройки уезжают в тот же облачный документ, что и общий банк, поэтому действуют <b class="text-slate-300">для всех игроков сайта</b>. Меняются локально сразу, а до остальных доезжают после «Опубликовать для всех» (или при ближайшей синхронизации, около минуты).</p>
            </div>

            <div class="bg-slate-900/80 p-3 sm:p-4 rounded-2xl border border-slate-800 space-y-2.5">
                <h3 class="text-sm font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-percent text-emerald-400"></i>
                    <span>Проценты — как копится банк и сколько уходит победителю</span>
                </h3>
                <div class="grid grid-cols-2 lg:grid-cols-5 gap-2">
{FIELDS}
                </div>
                <p class="text-[10px] text-slate-500 leading-snug">Пример: ставка 10k при «{FB}% ставки в банк» добавляет в банк {EX}; при выплате {PO}% победитель забирает не весь банк, а только его часть — остаток копится дальше и не обнуляет витрину.</p>
            </div>

            <div class="bg-slate-900/80 p-3 sm:p-4 rounded-2xl border border-slate-800 space-y-2.5">
                <h3 class="text-sm font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-vault text-sky-400"></i>
                    <span>Банк вручную</span>
                    <span class="ml-auto text-xs font-black text-amber-300">сейчас: <span id="jpc-pool-now">—</span></span>
                </h3>
                <div class="flex flex-wrap items-center gap-1.5">
                    <input id="jpc-pool-set" type="text" inputmode="numeric" placeholder="Новый банк: 250k"
                           class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-[11px] font-bold text-white" style="width:11rem">
                    <button type="button" onclick="jpcSetPoolInput()" class="px-2.5 py-1.5 bg-sky-500 hover:bg-sky-400 text-slate-950 rounded-lg text-[11px] font-black transition">Поставить банк</button>
                    <button type="button" onclick="jpcNudgePool(1000)" class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-[11px] font-bold text-slate-200 transition">+1k</button>
                    <button type="button" onclick="jpcNudgePool(10000)" class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-[11px] font-bold text-slate-200 transition">+10k</button>
                    <button type="button" onclick="jpcNudgePool(100000)" class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-[11px] font-bold text-slate-200 transition">+100k</button>
                    <button type="button" onclick="jpcNudgePool(-1000)" class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-[11px] font-bold text-slate-200 transition">−1k</button>
                    <button type="button" onclick="jpcNudgePool(-10000)" class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-[11px] font-bold text-slate-200 transition">−10k</button>
                    <button type="button" onclick="jpcResetPoolFloor()" class="px-2.5 py-1.5 bg-slate-900 hover:bg-rose-950/60 border border-slate-800 rounded-lg text-[11px] font-bold text-slate-400 transition">Сбросить до минимума</button>
                </div>
                <p class="text-[10px] text-slate-500 leading-snug">Сумма понимает буквы: <b class="text-slate-300">10k</b>, <b class="text-slate-300">5m</b>, <b class="text-slate-300">1b</b>. Банк общий на весь сайт — правка видна всем игрокам после синхронизации. «Сбросить до минимума» оставляет в банке только несгораемый остаток.</p>
            </div>

            <div class="bg-slate-900/80 p-3 sm:p-4 rounded-2xl border border-slate-800 space-y-2.5">
                <h3 class="text-sm font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-dice text-violet-400"></i>
                    <span>Вероятность JACKPOT и гарантия</span>
                </h3>
                <div id="jpc-prob" class="space-y-2"></div>
                <p class="text-[10px] text-slate-500 leading-snug">Процент — шанс символа JACKPOT на один барабан (Слоты), на одну ячейку поля (Сетка, Линии) или на один сектор (Колесо). Справа — итоговая частота «1 из N». Заводские значения повторяют прежнее поведение игры: Слоты ≈ 1 из 5 500 спинов, Сетка ≈ 1 из 25, Линии ≈ 1 из 1 730, Колесо 1 из 16.</p>
            </div>

            <div class="bg-slate-900/80 p-3 sm:p-4 rounded-2xl border border-slate-800 space-y-2.5">
                <h3 class="text-sm font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-gift text-rose-400"></i>
                    <span>Выдать джекпот игроку</span>
                </h3>
                <div class="flex flex-wrap items-center gap-1.5">
                    <input id="jpc-grant-amt" type="text" inputmode="numeric" placeholder="Сумма: 100k (пусто = весь банк)"
                           class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-[11px] font-bold text-white" style="width:14rem">
                    <input id="jpc-search" type="search" oninput="jpcAdminUsers()" placeholder="Поиск: имя или ID"
                           class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-[11px] font-bold text-white" style="width:12rem">
                    <button type="button" onclick="jpcGrantAllFromInput()" class="px-2.5 py-1.5 bg-rose-500 hover:bg-rose-400 text-slate-950 rounded-lg text-[11px] font-black transition"><i class="fa-solid fa-people-group mr-1"></i>Выдать ВСЕМ</button>
                </div>
                <div id="jpc-users" class="space-y-1.5 max-h-[26rem] overflow-y-auto pr-1"></div>
                <p class="text-[10px] text-slate-500 leading-snug"><b class="text-slate-300">«Выдать банк»</b> — игрок получает payout % общего банка (как при обычном срыве, с записью в зал славы). <b class="text-slate-300">«Выдать сумму»</b> — начисляет ровно вписанную сумму, банк не трогает. Назначение доезжает до игрока при ближайшей синхронизации (около минуты) и срабатывает один раз; «Отменить» отзывает ещё не полученную выдачу.</p>
            </div>

            <div class="bg-slate-900/80 p-3 sm:p-4 rounded-2xl border border-slate-800 space-y-2.5">
                <h3 class="text-sm font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-flask text-sky-400"></i>
                    <span>Симулятор частоты</span>
                    <button type="button" onclick="jpcSim()" class="ml-auto px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-[11px] font-semibold text-slate-200 transition"><i class="fa-solid fa-calculator mr-1"></i>Посчитать</button>
                </h3>
                <div id="jpc-sim-out" class="text-[11px] text-slate-300"></div>
            </div>
            </div><!-- /studio-sec jackpot -->
'''

FIELDS = '\n'.join([
    _field('feedBet', '% ставки в банк', 100, 0, 1000, 1,
           '100 = вся ставка уходит в общий банк (как было)'),
    _field('feedLoss', '% проигрыша в банк', 100, 0, 1000, 1,
           '100 = проигранная сумма докидывается в банк целиком'),
    _field('payout', '% банка победителю', 100, 0, 100, 1,
           '100 = весь банк; 50 = половина, остаток копится дальше'),
    _field('floor', 'Несгораемый остаток', 1000, 0, 1000000000, 1000,
           'Банк никогда не опускается ниже этого значения'),
    _field('cap', 'Потолок одной выплаты', 0, 0, 1000000000000, 10000,
           '0 = без потолка; иначе больше этой суммы не выплачивается'),
])

STATS_SEC_CLOSE = '            </div><!-- /studio-sec stats -->\n'

HTML_PATCHES = [
    ('сетка вкладок Студии: 7 → 8 колонок',
     'grid-cols-7 gap-1 bg-slate-900/95',
     'grid-cols-8 gap-1 bg-slate-900/95'),

    ('кнопка вкладки «Джекпот»',
     STATS_NAV_OLD,
     STATS_NAV_OLD + JACKPOT_NAV_NEW),

    ('секция «Джекпот»',
     STATS_SEC_CLOSE,
     STATS_SEC_CLOSE + STUDIO_SEC_JACKPOT.replace(
         '{FIELDS}', FIELDS).replace('{FB}', '100').replace(
         '{EX}', '10k монет').replace('{PO}', '100') + '\n'),
]


# --------------------------------------------------------------------------- #
def apply(path, patches, allow_multi=()):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    orig = text
    for label, old, new in patches:
        n = text.count(old)
        want = len(old.split('\n')) if old in allow_multi else 1
        if n != 1:
            raise AssertionError('%s: якорь «%s» встретился %d раз (нужно 1)' % (path, label, n))
        text = text.replace(old, new, 1)
        print('  · %-52s ok' % label)
    if text != orig:
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
    return len(orig), len(text)


def bump_version(check_only=False):
    out = []
    # index.html: ?v=nxmobNN в 8 местах
    p = os.path.join(ROOT, 'index.html')
    s = open(p, encoding='utf-8').read()
    n = s.count('?v=' + OLD_V)
    out.append(('index.html ?v=', n))
    if not check_only and n:
        open(p, 'w', encoding='utf-8', newline='').write(s.replace('?v=' + OLD_V, '?v=' + NEW_V))
    # sw.js: VERSION
    p = os.path.join(ROOT, 'sw.js')
    s = open(p, encoding='utf-8').read()
    old = "const VERSION = '%s';" % OLD_V
    n2 = s.count(old)
    out.append(('sw.js VERSION', n2))
    if not check_only and n2:
        open(p, 'w', encoding='utf-8', newline='').write(s.replace(old, "const VERSION = '%s';" % NEW_V, 1))
    # tools/build.py: BUILD_TAG
    p = os.path.join(ROOT, 'tools', 'build.py')
    s = open(p, encoding='utf-8').read()
    old = "BUILD_TAG = '%s'" % OLD_V
    n3 = s.count(old)
    out.append(('build.py BUILD_TAG', n3))
    if not check_only and n3:
        open(p, 'w', encoding='utf-8', newline='').write(s.replace(old, "BUILD_TAG = '%s'" % NEW_V, 1))
    return out


def main():
    check = '--check' in sys.argv
    print('b414: проверяю якоря' if check else 'b414: применяю правки')

    js = os.path.join(ROOT, 'assets', 'app.js')
    html = os.path.join(ROOT, 'index.html')

    if check:
        for path, patches in ((js, JS_PATCHES), (html, HTML_PATCHES)):
            s = open(path, encoding='utf-8').read()
            for label, old, _new in patches:
                n = s.count(old)
                print('  %s %-52s %d' % ('OK ' if n == 1 else 'BAD', label, n))
                if n != 1:
                    return 1
        print('  версии:', bump_version(check_only=True))
        return 0

    a, b = apply(js, JS_PATCHES)
    print('assets/app.js: %d -> %d байт (+%d)' % (a, b, b - a))
    a, b = apply(html, HTML_PATCHES)
    print('index.html:    %d -> %d байт (+%d)' % (a, b, b - a))
    print('  версии:', bump_version())
    return 0


if __name__ == '__main__':
    sys.exit(main())
