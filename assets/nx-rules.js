/* ============================================================================
 * assets/nx-rules.js — ЕДИНЫЙ ИСТОЧНИК ИГРОВЫХ ПРАВИЛ (b463)
 * ----------------------------------------------------------------------------
 * Зачем этот файл
 * ---------------
 * Раньше таблица выплат, веса символов и формулы множились в двух местах:
 * в браузере (assets/app.js) и — после переноса экономики на сервер — ещё и
 * в воркере. Две копии правил обязательно разъехались бы: сервер платил бы
 * не столько, сколько показывает анимация.
 *
 * Поэтому чистая математика игры (без DOM, без localStorage, без состояния)
 * вынесена сюда ОДИН раз. Файл грузится:
 *   • браузером — обычным <script> ДО assets/app.js, правила попадают в
 *     window.NXR, и app.js берёт константы/формулы оттуда;
 *   • сервером  — воркер импортирует этот же файл (import '../../../assets/
 *     nx-rules.js') и читает globalThis.NXR.
 *
 * Все функции ЧИСТЫЕ: случайность приходит извне аргументом `rng` — функцией,
 * возвращающей число в [0, 1). В браузере это Math.random, на сервере —
 * криптографический генератор. Благодаря этому клиент и сервер считают
 * выплаты по одним и тем же формулам, а случайные числа решает только сервер.
 *
 * Значения перенесены из assets/app.js БЕЗ ИЗМЕНЕНИЙ (b56/b92/b105/b220/b414):
 *   SLOTS_MULT, GRID_CHAIN, gridPay, LINES_PATHS, LINES_PAY, WHEEL_SECTORS,
 *   MINES_TILES, MINES_EDGE, minesMult, RARITY_WEIGHTS, jpcWeight, JPC_*.
 * ========================================================================== */
(function (root) {
    'use strict';

    // ---------------- редкости и веса выпадения карт в паке ----------------
    var RARITY_ORDER = ['common', 'rare', 'epic', 'legendary'];
    var RARITY_WEIGHTS = { common: 60, rare: 25, epic: 12, legendary: 3 };
    var RARITY_MULT = { common: 1, rare: 1.5, epic: 2, legendary: 3 };
    // возврат монет за дубликат (app.js: nxGrantCard)
    var DUPE_REFUND = { common: 20, rare: 50, epic: 120, legendary: 300 };
    var PITY_LIMIT = 10;          // каждый 10-й пак без epic+ гарантирует epic+
    var PACK_CARDS = 4;           // карт в одном вскрытии пака

    // ---------------- настройки джекпота (b414) ----------------
    var JPC_GAMES = ['Slots', 'Grid', 'Lines', 'Wheel'];
    var JPC_DEFAULT_P = { Slots: 5.66, Grid: 3.85, Lines: 4, Wheel: 6.25 };
    var JPC_DEFAULTS = {
        on: 1, feedBet: 100, feedLoss: 100, payout: 100, floor: 1000, cap: 0,
        pSlots: JPC_DEFAULT_P.Slots, pGrid: JPC_DEFAULT_P.Grid,
        pLines: JPC_DEFAULT_P.Lines, pWheel: JPC_DEFAULT_P.Wheel,
        pitySlots: 0, pityGrid: 0, pityLines: 0, pityWheel: 0,
        grant: {}, at: 0, by: ''
    };

    function jpcNorm(o) {
        o = (o && typeof o === 'object') ? o : {};
        var n = {};
        function num(k, min, max, dflt) {
            var v = Number(o[k]);
            if (!isFinite(v)) v = dflt;
            return Math.min(max, Math.max(min, v));
        }
        n.on = (Number(o.on) === 0) ? 0 : 1;
        n.feedBet = num('feedBet', 0, 1000, JPC_DEFAULTS.feedBet);
        n.feedLoss = num('feedLoss', 0, 1000, JPC_DEFAULTS.feedLoss);
        n.payout = num('payout', 0, 100, JPC_DEFAULTS.payout);
        n.floor = Math.round(num('floor', 0, 1e15, JPC_DEFAULTS.floor));
        n.cap = Math.round(num('cap', 0, 1e15, 0));
        for (var i = 0; i < JPC_GAMES.length; i++) {
            var g = JPC_GAMES[i];
            n['p' + g] = num('p' + g, 0, 100, JPC_DEFAULT_P[g]);
            n['pity' + g] = Math.round(num('pity' + g, 0, 1000000, 0));
        }
        n.grant = {};
        if (o.grant && typeof o.grant === 'object') {
            for (var k in o.grant) {
                var gr = o.grant[k];
                if (!gr || typeof gr !== 'object') continue;
                var t = Math.floor(gr.t) || 0;
                if (!t) continue;
                n.grant[String(k).slice(0, 40)] = { a: Math.max(-1, Math.floor(gr.a) || 0), t: t };
            }
        }
        n.at = Math.floor(o.at) || 0;
        n.by = String(o.by || '').slice(0, 40);
        return n;
    }
    function jpcOff(cfg) { return !(cfg.on | 0); }
    function jpcP(cfg, g) { var v = Number(cfg['p' + g]); return (isFinite(v) && v > 0) ? v : 0; }
    function jpcPityN(cfg, g) { var n = Math.floor(cfg['pity' + g]) || 0; return n > 0 ? n : 0; }
    // вес символа JACKPOT при нужной вероятности p (app.js: jpcWeight)
    function jpcWeight(pct, others) {
        var p = Math.min(99.999, Math.max(0, Number(pct) || 0)) / 100;
        if (p <= 0) return 0;
        return (others * 10) * p / (1 - p);
    }
    // вероятность JACKPOT в конкретном спине: база из настроек или 100 % по гарантии
    function jpcSpinPct(cfg, g, pityCounter) {
        if (jpcOff(cfg)) return 0;
        var n = jpcPityN(cfg, g);
        if (n && Math.floor(pityCounter || 0) >= n) return 100;
        return jpcP(cfg, g);
    }
    function jpcPityNext(cfg, g, pityCounter, hit) {
        if (!jpcPityN(cfg, g)) return Math.floor(pityCounter || 0);
        return hit ? 0 : (Math.floor(pityCounter || 0) + 1);
    }

    // ---------------- СЛОТЫ (b49/b56) ----------------
    var SLOTS_REELS = 3;
    var SLOTS_MULT = { common: 8, rare: 12, epic: 18, legendary: 30 };

    // Набор символов: до 5 карт игрока + обязательный JACKPOT последним.
    // cards — [{id, rarity}] в порядке выбора; совпадает со slotsSymbols().
    function buildSymbols(cards) {
        var syms = [];
        var src = Array.isArray(cards) ? cards.slice(0, 5) : [];
        for (var i = 0; i < src.length; i++) {
            var c = src[i] || {};
            syms.push({
                id: String(c.id || ('sym-' + i)),
                rarity: RARITY_WEIGHTS[c.rarity] ? c.rarity : 'common',
                name: String(c.name || c.id || 'Карта'),
                image: String(c.image || '')
            });
        }
        while (syms.length < 3) syms.push({ id: 'sym-' + syms.length, name: 'Джокер', rarity: 'legendary', image: '' });
        syms.push({ id: 'sym-jackpot', name: 'JACKPOT', rarity: 'legendary', image: '', jackpot: true });
        return syms;
    }

    // Выбор символа с весами: обычная карта = 10, JACKPOT = jpcWeight(pct, others)
    function pickSymbol(rng, syms, pct) {
        if (!syms || !syms.length) return 0;
        var others = 0, hasJp = false;
        for (var i = 0; i < syms.length; i++) { if (syms[i].jackpot) hasJp = true; else others++; }
        var p = Number(pct) || 0;
        var wJp = (hasJp && p > 0) ? jpcWeight(p, others) : 0;
        var tot = others * 10 + wJp;
        if (tot <= 0) return 0;
        var r = rng() * tot;
        for (var j = 0; j < syms.length; j++) {
            var w = syms[j].jackpot ? wJp : 10;
            if (w <= 0) continue;
            r -= w;
            if (r <= 0) return j;
        }
        return syms.length - 1;
    }

    // Выплата слотов: три одинаковых = ×8…×30, три JACKPOT = банк, две = ×2
    function slotsPayout(res, syms, bet) {
        var out = { win: 0, mult: 0, kind: '', jpHit: false };
        var a = syms[res[0]], b = syms[res[1]], c = syms[res[2]];
        if (res[0] === res[1] && res[1] === res[2]) {
            if (a && a.jackpot) { out.jpHit = true; return out; }
            out.mult = SLOTS_MULT[(a && a.rarity) || 'common'] || 8;
            out.kind = 'джекпот';
        } else if (res[0] === res[1] || res[1] === res[2] || res[0] === res[2]) {
            out.mult = 2; out.kind = 'пара';
        }
        out.win = Math.round(bet * out.mult);
        return out;
    }

    // ---------------- СЕТКА 5×4 (b53/b54) ----------------
    var GRID_COLS = 5, GRID_ROWS = 4, GRID_CELLS = 20;
    var GRID_CHAIN = [1, 1.5, 2, 3, 5, 8];
    function gridPay(count, rarity) {
        if (count < 8) return 0;
        var base = count >= 12 ? 15 : (count >= 10 ? 5 : 2);
        return Math.round(base * (RARITY_MULT[rarity] || 1));
    }
    function gridGroups(cells, syms) {
        var m = {}, order = [];
        for (var i = 0; i < cells.length; i++) {
            var s = syms[cells[i]];
            if (!s) continue;
            if (!m[s.id]) { m[s.id] = { id: s.id, rarity: s.rarity, jackpot: !!s.jackpot, idxs: [] }; order.push(s.id); }
            m[s.id].idxs.push(i);
        }
        return order.map(function (k) {
            return { id: m[k].id, rarity: m[k].rarity, jackpot: m[k].jackpot, count: m[k].idxs.length, idxs: m[k].idxs };
        });
    }
    // Полный просчёт спина сетки: начальное поле + все каскады.
    // Возвращает {cells, steps:[{win:[…], add, chain, refill:{i:symIdx}}], total, jpHit}
    function gridSimulate(rng, syms, bet, pct, pityCounter, cfg) {
        var cells = [];
        for (var i = 0; i < GRID_CELLS; i++) cells.push(pickSymbol(rng, syms, pct));
        var steps = [], total = 0, chain = 0, jpHit = false;
        var pityHit = false;
        for (var guard = 0; guard < GRID_CHAIN.length + 2; guard++) {
            var groups = gridGroups(cells, syms);
            var jg = null;
            for (var q = 0; q < groups.length; q++) if (groups[q].jackpot && groups[q].count >= 3) { jg = groups[q]; break; }
            if (jg) { jpHit = true; pityHit = true; steps.push({ jp: 1, win: jg.idxs.slice(), chain: Math.max(chain, 1) }); break; }
            var wins = [];
            for (var w = 0; w < groups.length; w++) {
                if (!groups[w].jackpot && gridPay(groups[w].count, groups[w].rarity) > 0) wins.push(groups[w]);
            }
            if (!wins.length || chain >= GRID_CHAIN.length) break;
            var cm = GRID_CHAIN[chain];
            var add = 0, idxSet = {};
            for (var k = 0; k < wins.length; k++) {
                add += bet * gridPay(wins[k].count, wins[k].rarity) * cm;
                for (var z = 0; z < wins[k].idxs.length; z++) idxSet[wins[k].idxs[z]] = 1;
            }
            add = Math.round(add);
            total += add;
            chain++;
            var refill = {};
            for (var key in idxSet) {
                var ns = pickSymbol(rng, syms, pct);
                cells[+key] = ns;
                refill[key] = ns;
            }
            steps.push({ win: Object.keys(idxSet).map(Number), add: add, chain: chain, refill: refill });
        }
        return {
            cells: cells, steps: steps, total: total, chain: chain, jpHit: jpHit,
            pity: jpcPityNext(cfg || {}, 'Grid', pityCounter, pityHit)
        };
    }

    // ---------------- ЛИНИИ 5×3 (b105/b107/b220) ----------------
    var LINES_COLS = 5, LINES_ROWS = 3, LINES_CELLS = 15;
    var LINES_PATHS = [
        [1, 1, 1, 1, 1], [0, 0, 0, 0, 0], [2, 2, 2, 2, 2],
        [0, 1, 1, 1, 0], [2, 1, 1, 1, 2],
        [0, 0, 1, 2, 2], [2, 2, 1, 0, 0],
        [1, 0, 1, 2, 1], [1, 2, 1, 0, 1], [0, 1, 2, 1, 0]
    ];
    var LINES_PAY = { common: [0.5, 2, 10], rare: [1, 5, 25], epic: [2, 10, 50], legendary: [5, 25, 100] };
    // Пул линий: 3 карты + JACKPOT под индексом 3 (app.js: linesMakePool/linesRand)
    function linesPayout(final, pool, bet) {
        var total = 0, jpHit = false, winCells = {}, winLines = [];
        for (var li = 0; li < LINES_PATHS.length; li++) {
            var path = LINES_PATHS[li];
            var first = pool ? pool[final[path[0] * LINES_COLS + 0]] : null;
            if (!first) continue;
            var count = 1;
            for (var c = 1; c < LINES_COLS; c++) {
                var sy = pool ? pool[final[path[c] * LINES_COLS + c]] : null;
                if (!sy || sy.id !== first.id) break;
                count++;
            }
            if (count < 3) continue;
            for (var m = 0; m < count; m++) winCells[path[m] * LINES_COLS + m] = 1;
            if (first.jackpot) { jpHit = true; winLines.push({ li: li, count: count }); continue; }
            total += Math.round(bet * ((LINES_PAY[first.rarity] || LINES_PAY.common)[count - 3]));
            winLines.push({ li: li, count: count });
        }
        return { total: total, jpHit: jpHit, winCells: winCells, winLines: winLines };
    }

    // ---------------- КОЛЕСО (b74/b220) ----------------
    var WHEEL_SECTORS = [
        { t: 'mult', m: 0, label: '0' },
        { t: 'mult', m: 1, label: '×1' },
        { t: 'mult', m: 0.5, label: '×0.5' },
        { t: 'mult', m: 0, label: '0' },
        { t: 'mult', m: 2, label: '×2' },
        { t: 'mult', m: 1, label: '×1' },
        { t: 'mult', m: 0.5, label: '×0.5' },
        { t: 'card', label: 'КАРТА' },
        { t: 'jackpot', label: 'JACKPOT' },
        { t: 'mult', m: 1.5, label: '×1.5' },
        { t: 'mult', m: 1, label: '×1' },
        { t: 'mine', label: 'КИРКА' },
        { t: 'mult', m: 0, label: '0' },
        { t: 'mult', m: 3, label: '×3' },
        { t: 'mult', m: 0.5, label: '×0.5' },
        { t: 'mult', m: 5, label: '×5' }
    ];
    function wheelPickIdx(rng, pct) {
        var n = WHEEL_SECTORS.length, gold = [], rest = [];
        for (var i = 0; i < n; i++) (WHEEL_SECTORS[i].t === 'jackpot' ? gold : rest).push(i);
        var p = Number(pct) || 0;
        if (gold.length && p > 0 && rng() * 100 < p) return gold[Math.floor(rng() * gold.length)];
        if (rest.length) return rest[Math.floor(rng() * rest.length)];
        return Math.floor(rng() * n);
    }

    // ---------------- МИНЫ (b79) ----------------
    var MINES_TILES = 25;
    var MINES_EDGE = 0.97;
    var MINES_COUNTS = [3, 5, 10];
    function minesMult(k, m) {
        if (k <= 0) return 1;
        var p = 1;
        for (var i = 0; i < k; i++) p *= (MINES_TILES - i) / (MINES_TILES - m - i);
        return Math.floor(p * MINES_EDGE * 100) / 100;
    }
    // Раскладка мин: перемешивание Фишера–Йетса, как в minesStart()
    function minesLayout(rng, m) {
        var idx = [];
        for (var i = 0; i < MINES_TILES; i++) idx.push(i);
        for (var j = idx.length - 1; j > 0; j--) {
            var k = Math.floor(rng() * (j + 1));
            var t = idx[j]; idx[j] = idx[k]; idx[k] = t;
        }
        return idx.slice(0, Math.max(1, Math.min(MINES_TILES - 1, m | 0)));
    }

    // ---------------- ПАКИ / КАРТЫ ----------------
    function pickWeightedRarity(rng, rarities) {
        var total = 0;
        for (var i = 0; i < rarities.length; i++) total += (RARITY_WEIGHTS[rarities[i]] || 1);
        var roll = rng() * total;
        for (var j = 0; j < rarities.length; j++) {
            roll -= (RARITY_WEIGHTS[rarities[j]] || 1);
            if (roll <= 0) return rarities[j];
        }
        return rarities[rarities.length - 1];
    }
    function rollCardFromPack(rng, packCards, forceEpicPlus) {
        var pool = packCards;
        if (forceEpicPlus) {
            var ep = [];
            for (var i = 0; i < packCards.length; i++) {
                var r = packCards[i].rarity;
                if (r === 'epic' || r === 'legendary') ep.push(packCards[i]);
            }
            if (ep.length) pool = ep;
        }
        var present = [];
        for (var o = 0; o < RARITY_ORDER.length; o++) {
            var rr = RARITY_ORDER[o], has = false;
            for (var k = 0; k < pool.length; k++) if (pool[k].rarity === rr) { has = true; break; }
            if (has) present.push(rr);
        }
        if (!present.length) return null;
        var rarity = pickWeightedRarity(rng, present);
        var ofRarity = [];
        for (var z = 0; z < pool.length; z++) if (pool[z].rarity === rarity) ofRarity.push(pool[z]);
        return ofRarity[Math.floor(rng() * ofRarity.length)] || null;
    }
    // Вскрытие одного пака: 4 карты + гарант каждый PITY_LIMIT-й пак.
    // pityIn — счётчик паков без epic+ ДО вскрытия. Возвращает карты и новый счётчик.
    function rollPack(rng, packCards, pityIn) {
        var rolled = [];
        for (var i = 0; i < PACK_CARDS; i++) {
            var c = rollCardFromPack(rng, packCards, false);
            if (c) rolled.push(c);
        }
        if (!rolled.length) return { cards: [], pity: pityIn };
        var hasEp = false, gotEp = false;
        for (var a = 0; a < packCards.length; a++) if (packCards[a].rarity === 'epic' || packCards[a].rarity === 'legendary') hasEp = true;
        for (var b = 0; b < rolled.length; b++) if (rolled[b].rarity === 'epic' || rolled[b].rarity === 'legendary') gotEp = true;
        if (Math.floor(pityIn || 0) >= PITY_LIMIT - 1 && hasEp && !gotEp) {
            var forced = rollCardFromPack(rng, packCards, true);
            if (forced) { rolled[rolled.length - 1] = forced; gotEp = (forced.rarity === 'epic' || forced.rarity === 'legendary'); }
        }
        return { cards: rolled, pity: gotEp ? 0 : (Math.floor(pityIn || 0) + 1) };
    }

/*NXR_TABLES_START*/
    // Таблицы наград ниже СГЕНЕРИРОВАНЫ из assets/app.js скриптом
    // tools/gen_nx_rules_tables.py. Руками их не править: после любой
    // смены наград в игре скрипт запускается заново и обновляет этот блок.
    var DAILY_REWARDS = [100, 200, 350, 500, 750, 1000, 2000];

    // задания дня: тип -> варианты [цель, награда]
    var MISSION_VARIANTS = {
        'open_pack': [[1, 80], [2, 150], [3, 250]],
        'collect_new': [[3, 140], [5, 220]],
        'find_rare_plus': [[1, 120], [2, 200]],
        'find_epic_plus': [[1, 200]],
        'sell_dupe': [[2, 100], [4, 180]],
        'earn_dupe_coins': [[100, 120], [250, 200]],
        'open_album': [[1, 50], [2, 90]],
        'spin_slots': [[3, 100], [10, 220]],
        'win_slots': [[1, 150], [3, 320]],
        'slots_coins': [[500, 140], [1500, 260]],
        'spin_grid': [[3, 100], [8, 200]],
        'win_grid': [[1, 150], [3, 320]],
        'grid_coins': [[500, 140], [2000, 280]],
        'spin_lines': [[3, 100], [8, 200]],
        'win_lines': [[1, 150], [3, 320]],
        'lines_coins': [[500, 150], [2500, 320]],
        'wheel_spin': [[3, 120], [8, 240]],
        'wheel_coins': [[300, 130], [1500, 260]],
        'mines_open': [[5, 120], [12, 260]],
        'mines_win': [[1, 180], [3, 400]],
        'mines_coins': [[500, 150], [2500, 320]],
        'mine_ore': [[2000, 120], [10000, 250]],
        'miner_upgrade': [[1, 150], [2, 320]]
    };

    // тип задания -> счётчик сервера (поле st игрока)
    var MISSION_COUNTER = {
        'open_pack': 'packsOpened',
        'collect_new': 'newCards',
        'find_rare_plus': 'rarePlusFound',
        'find_epic_plus': 'epicPlusFound',
        'sell_dupe': 'dupesSold',
        'earn_dupe_coins': 'dupeCoins',
        'open_album': 'albumOpens',
        'spin_slots': 'slotsSpins',
        'win_slots': 'slotsWins',
        'slots_coins': 'slotsCoins',
        'spin_grid': 'gridSpins',
        'win_grid': 'gridWins',
        'grid_coins': 'gridCoins',
        'spin_lines': 'linesSpins',
        'win_lines': 'linesWins',
        'lines_coins': 'linesCoins',
        'wheel_spin': 'wheelSpins',
        'wheel_coins': 'wheelCoins',
        'mines_open': 'minesOpen',
        'mines_win': 'minesWins',
        'mines_coins': 'minesCoins',
        'mine_ore': 'mineOre',
        'miner_upgrade': 'minerUpgrades'
    };

    // достижения: награда и правило проверки (null = выдаётся один раз на id)
    var ACHIEVEMENT_REWARDS = {
        'first_card': 50,
        'collector_10': 100,
        'collector_25': 250,
        'collector_50': 600,
        'rare_find': 75,
        'epic_find': 150,
        'legendary_find': 500,
        'packs_5': 100,
        'packs_20': 300,
        'packs_50': 800,
        'dupes_10': 150,
        'dupes_50': 400,
        'album_complete': 750,
        'albums_3': 1200,
        'albums_5': 2500,
        'albums_10': 5000,
        'rich': 200,
        'streak_7': 600,
        'all_missions': 150,
        'first_win': 100,
        'wins_10': 300,
        'wins_25': 600,
        'flawless': 250,
        'battle_streak3': 250,
        'champion_down': 800,
        'durak_win': 150,
        'durak_streak3': 200,
        'slots_win_1': 100,
        'slots_win_10': 300,
        'slots_jackpot': 1000,
        'grid_win_1': 100,
        'grid_win_10': 300,
        'grid_chain3': 500,
        'miner_lvl5': 400,
        'miner_lvl10': 800,
        'lines_win_10': 300,
        'wheel_spin_10': 250,
        'mines_win_10': 400
    };
    var ACHIEVEMENT_RULES = {
        'first_card': { k: 'collected', n: 1 },
        'collector_10': { k: 'collected', n: 10 },
        'collector_25': { k: 'collected', n: 25 },
        'collector_50': { k: 'collected', n: 50 },
        'rare_find': { k: 'rarePlusFound', n: 1 },
        'epic_find': { k: 'epicPlusFound', n: 1 },
        'legendary_find': { k: 'legendariesFound', n: 1 },
        'packs_5': { k: 'packsOpened', n: 5 },
        'packs_20': { k: 'packsOpened', n: 20 },
        'packs_50': { k: 'packsOpened', n: 50 },
        'dupes_10': { k: 'dupesSold', n: 10 },
        'dupes_50': { k: 'dupesSold', n: 50 },
        'album_complete': null,
        'albums_3': null,
        'albums_5': null,
        'albums_10': null,
        'rich': { k: 'balance', n: 2000 },
        'streak_7': { k: 'bestStreak', n: 7 },
        'all_missions': null,
        'first_win': null,
        'wins_10': null,
        'wins_25': null,
        'flawless': null,
        'battle_streak3': null,
        'champion_down': null,
        'durak_win': null,
        'durak_streak3': null,
        'slots_win_1': { k: 'slotsWins', n: 1 },
        'slots_win_10': { k: 'slotsWins', n: 10 },
        'slots_jackpot': { k: 'jackpots', n: 1 },
        'grid_win_1': { k: 'gridWins', n: 1 },
        'grid_win_10': { k: 'gridWins', n: 10 },
        'grid_chain3': { k: 'bestGridChain', n: 3 },
        'miner_lvl5': { k: 'minerLvl', n: 5 },
        'miner_lvl10': { k: 'minerLvl', n: 10 },
        'lines_win_10': { k: 'linesWins', n: 10 },
        'wheel_spin_10': { k: 'wheelSpins', n: 10 },
        'mines_win_10': { k: 'minesWins', n: 10 }
    };
/*NXR_TABLES_END*/

    // ---------------- общий банк джекпота ----------------
    // Банк = floor + (Σвзносов − Σвыплат), но не ниже floor (app.js: jpFloor/jpExcess)
    function bankPool(b) {
        var floor = Math.max(0, Math.round(Number(b.floor) || 0));
        var excess = Math.max(0, Math.round(Number(b.fed) || 0) - Math.round(Number(b.won) || 0));
        return Math.round(floor + excess);
    }
    // Взнос в банк: процент ставки (feedBet) или процент проигрыша (feedLoss)
    function bankFeed(cfg, amount, kind) {
        var pct = Number(kind === 'loss' ? cfg.feedLoss : cfg.feedBet);
        if (!isFinite(pct)) pct = 100;
        pct = Math.max(0, pct);
        if (pct <= 0) return 0;
        return Math.max(1, Math.round((Number(amount) || 0) * pct / 100));
    }
    // Выплата победителю: payout % банка, не больше cap (0 = без потолка)
    function bankPrize(cfg, pool) {
        var pct = Math.min(100, Math.max(0, Number(cfg.payout)));
        if (!isFinite(pct)) pct = 100;
        var prize = Math.round(pool * pct / 100);
        var cap = Math.round(Number(cfg.cap) || 0);
        if (cap > 0 && prize > cap) prize = cap;
        return Math.max(0, prize);
    }

    // ---------------- ставки ----------------
    // Потолок ставки — буква q (1e15), как в normBet() клиента
    var BET_MAX = 1e15;
    function normBet(b) {
        b = Math.floor(Number(b));
        if (!isFinite(b) || b < 1) return 1;
        if (b > BET_MAX) return BET_MAX;
        return b;
    }

    root.NXR = {
        VERSION: 'b463',
        RARITY_ORDER: RARITY_ORDER, RARITY_WEIGHTS: RARITY_WEIGHTS, RARITY_MULT: RARITY_MULT,
        DUPE_REFUND: DUPE_REFUND, PITY_LIMIT: PITY_LIMIT, PACK_CARDS: PACK_CARDS,
        JPC_GAMES: JPC_GAMES, JPC_DEFAULT_P: JPC_DEFAULT_P, JPC_DEFAULTS: JPC_DEFAULTS,
        jpcNorm: jpcNorm, jpcOff: jpcOff, jpcP: jpcP, jpcWeight: jpcWeight,
        jpcSpinPct: jpcSpinPct, jpcPityNext: jpcPityNext, jpcPityN: jpcPityN,
        SLOTS_REELS: SLOTS_REELS, SLOTS_MULT: SLOTS_MULT,
        buildSymbols: buildSymbols, pickSymbol: pickSymbol, slotsPayout: slotsPayout,
        GRID_COLS: GRID_COLS, GRID_ROWS: GRID_ROWS, GRID_CELLS: GRID_CELLS, GRID_CHAIN: GRID_CHAIN,
        gridPay: gridPay, gridGroups: gridGroups, gridSimulate: gridSimulate,
        LINES_COLS: LINES_COLS, LINES_ROWS: LINES_ROWS, LINES_CELLS: LINES_CELLS,
        LINES_PATHS: LINES_PATHS, LINES_PAY: LINES_PAY, linesPayout: linesPayout,
        WHEEL_SECTORS: WHEEL_SECTORS, wheelPickIdx: wheelPickIdx,
        MINES_TILES: MINES_TILES, MINES_EDGE: MINES_EDGE, MINES_COUNTS: MINES_COUNTS,
        minesMult: minesMult, minesLayout: minesLayout,
        pickWeightedRarity: pickWeightedRarity, rollCardFromPack: rollCardFromPack, rollPack: rollPack,
        bankPool: bankPool, bankFeed: bankFeed, bankPrize: bankPrize,
        BET_MAX: BET_MAX, normBet: normBet,
        DAILY_REWARDS: DAILY_REWARDS, MISSION_VARIANTS: MISSION_VARIANTS,
        MISSION_COUNTER: MISSION_COUNTER, ACHIEVEMENT_REWARDS: ACHIEVEMENT_REWARDS,
        ACHIEVEMENT_RULES: ACHIEVEMENT_RULES
    };
})(typeof globalThis !== 'undefined' ? globalThis : (typeof window !== 'undefined' ? window : this));
