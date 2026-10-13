#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b416 — банк джекпота больше не замерзает: потолок счётчиков, честный пол,
       автоматический ремонт реестра.

Жалоба владельца: «Чего-то число в банке не растёт».

Диагноз (воспроизведён в tools/repro-jp-frozen.js на снимке настоящего облачного
документа textdb nexus-tcg-jackpot-v2):

1. Реестр банка — CRDT «max на игрока»: счётчики led (взносы) и won (выплаты)
   могут только расти. Ручные правки банка в Студии и срывы джекпота при банке,
   прижатом к несгораемому остатку, раздули счётчик владельца до 1e57.
2. У double на величине 1e57 шаг (ulp) ≈ 8.7e40, поэтому
       jackpot.led[cid] += 10000   →   1e57 + 1e4 === 1e57,
   то есть взнос просто исчезает. Σled и Σwon дают ровно 1e57 − 1e57 = 0,
   а честные взносы остальных 96 игроков тонут в погрешности сложения.
3. Банк = max(floor, 1000 + 0) = 10 000 000 и не двигается ни от ставок,
   ни от проигрышей, ни от «Поставить банк» (дельта тоже тонет в ulp).
4. Вторая, независимая ловушка: floor работал как «мёртвая зона» — пока сумма
   взносов не переползёт несгораемый остаток (10m при ставках 10k = 1000 спинов),
   витрина стоит на месте. Плюс каждый срыв банка на полу писал в won всю
   выплату, хотя в реестре этих денег не было, — «фантомный долг» навсегда
   прижимал банк к полу.

Что стало:

* JP_LED_CAP = 1e13 — потолок одного счётчика; все записи в реестр идут только
  через jpLedAdd(), все суммы — через jpLedSum() (мусор не учитывается, слагаемые
  складываются по возрастанию, поэтому сумма остаётся точной: 9000 игроков ×
  1e13 = 9e15 ≈ Number.MAX_SAFE_INTEGER, шаг сложения 1 монета).
* jackpotPool() = floor + max(0, raw − SEED): несгораемый остаток — гарантия
  пола, а не мёртвая зона. При заводском floor (= JACKPOT_SEED = 1000) формула
  даёт ровно прежние числа, при floor = 10m банк растёт с первой же ставки.
* jackpotWin() пишет в won только обеспеченную часть выплаты
  (min(prize, excess)) — срыв банка, стоящего на полу, больше не создаёт долг.
* jpRepairLedger() — автоматический ремонт: выбрасывает испорченные счётчики
  и гасит образовавшийся долг одной служебной записью 'house' (общая для всех
  клиентов, сливается тем же max-правилом → ремонт идемпотентен и не
  размножается). Вызывается при загрузке и после каждого слияния с облаком,
  поэтому банк лечится сам, даже если старые клиенты продолжают пушить мусор.
* Студия: кнопка «Починить банк» (jpRepairNow) и строка-отчёт о ремонте;
  «Поставить банк» больше не врёт — если сумма не встала ровно, так и пишет.

Запуск:  python3 tools/_b416_patch.py            — применить
         python3 tools/_b416_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob75'
NEW_V = 'nxmob76'

# --------------------------------------------------------------------------- #
# app.js
# --------------------------------------------------------------------------- #

# --- 1. новый модуль целостности реестра: вставляется сразу за константами ---
ANCHOR_MODULE = "        const JACKPOT_FEED = 1; // b96: базовый множитель взноса; сам процент ставки задаётся в Студии (b414/b415)\n"

MODULE = r'''
        // ============ b416: ЦЕЛОСТНОСТЬ РЕЕСТРА БАНКА (банк больше не замерзает) ============
        // Диагноз жалобы «число в банке не растёт» (воспроизведение — tools/repro-jp-frozen.js):
        // реестр банка это CRDT «max на игрока», счётчики led/won в нём только растут.
        // Ручные правки банка и срывы джекпота при банке, прижатом к полу, раздули
        // счётчик владельца до 1e57, а у double на такой величине шаг (ulp) ≈ 8.7e40:
        //     jackpot.led[cid] += 10000  →  1e57 + 1e4 === 1e57   (взнос исчезал),
        //     Σled − Σwon = 1e57 − 1e57 = 0, честные взносы остальных 96 игроков
        //     тонули в погрешности, и банк стоял на floor = 10 000 000 намертво —
        //     его не двигали ни ставки, ни проигрыши, ни «Поставить банк» в Студии.
        // Поэтому: (1) у каждого счётчика есть потолок, (2) суммы считаются через
        // jpLedSum() — мусор в них не попадает, (3) испорченный реестр лечится сам.
        const JP_LED_CAP = 1e13;   // 10 триллионов на один счётчик: недостижимо честной игрой, но 9000 таких записей = 9e15 ≈ Number.MAX_SAFE_INTEGER, то есть сумма остаётся точной до монеты
        const JP_HOUSE = 'house';  // служебная запись реестра: дом гасит долг испорченного банка (в «копят банк» не считается)
        let jpFixInfo = { n: 0, debt: 0, at: 0 }; // что починил jpRepairLedger — видно в Студии
        // запись пригодна для счёта, если это целое в пределах [0, JP_LED_CAP]
        function jpLedBad(v) { const n = Number(v); return !(isFinite(n) && n >= 0 && n <= JP_LED_CAP && n === Math.floor(n)); }
        function jpLedNum(v) { return jpLedBad(v) ? 0 : Math.floor(Number(v)); }
        function jpLedSum(m) {
            // b416: испорченные счётчики в сумму не идут вовсе, остальные складываем
            // по возрастанию — слагаемые целые и ≤ 1e13, значит сумма точная
            const a = [];
            for (const k in m) { const v = jpLedNum(m[k]); if (v > 0) a.push(v); }
            a.sort((x, y) => x - y);
            let s = 0;
            for (let i = 0; i < a.length; i++) s += a[i];
            return s;
        }
        function jpLedAdd(field, cid, x) {
            // b416: единственный способ писать в реестр банка — со срезом мусора и
            // потолком. Возвращает, сколько РЕАЛЬНО легло в счётчик (0 = не влезло).
            x = Math.floor(Number(x) || 0);
            if (!(x > 0)) return 0;
            const m = jackpot[field] || (jackpot[field] = {});
            const cur = jpLedNum(m[cid]);
            const add = Math.min(x, JP_LED_CAP - cur);
            if (!(add > 0)) return 0;
            m[cid] = cur + add;
            return add;
        }
        function jpFloor() { const fl = Number(jpc.floor); return (isFinite(fl) && fl >= 0) ? Math.round(fl) : JACKPOT_SEED; }
        function jpRawPool() { return Math.round(JACKPOT_SEED + jpLedSum(jackpot.led) - jpLedSum(jackpot.won)); }
        function jpExcess() { return Math.max(0, jpRawPool() - JACKPOT_SEED); } // накоплено сверх сида
        function jpRepairLedger() {
            // b416: (1) выбрасываем счётчики, улетевшие за потолок, — это не честный
            // вклад, а мусор, который обнуляет банк; (2) образовавшийся «долг»
            // (Σвыплат > Σвзносов — наследие срывов при банке на полу и прежней
            // записи всей выплаты в won) гасит дом ОДНОЙ служебной записью: она
            // общая для всех клиентов и сливается тем же правилом max, поэтому
            // ремонт идемпотентен — повторный прогон ничего не меняет и не плодит деньги.
            let n = 0;
            ['led', 'won'].forEach(f => {
                const m = jackpot[f] || (jackpot[f] = {});
                for (const k in m) if (jpLedBad(m[k])) { delete m[k]; n++; }
            });
            const debt = JACKPOT_SEED - jpRawPool();
            if (debt > 0) { if (jpLedAdd('led', JP_HOUSE, debt)) n++; }
            if (n) jpFixInfo = { n: (jpFixInfo.n || 0) + n, debt: (jpFixInfo.debt || 0) + (debt > 0 ? debt : 0), at: Date.now() };
            return n;
        }
        function jpRepairNow() {
            // кнопка «Починить банк» в Студии: то же самое, что автоматика, но сразу
            // с публикацией — владелец может починить банк для всех игроков сайта
            if (jpcAdminGuard()) return;
            const n = jpRepairLedger();
            jackpotSave(); jackpotRender();
            try { jpcAdminPreview(); } catch (e) {}
            try { jpSyncNow(); } catch (e) {}
            showToast(n
                ? '🧰 Банк починен: записей с мусором/долгом — ' + n + ', банк сейчас ' + fmtCoins(jackpotPool())
                : 'Банк в порядке — реестр чистый, банк ' + fmtCoins(jackpotPool()), n ? 'success' : 'info');
        }
'''

# --- 2. jackpotPool / jackpotPlayers ---
OLD_POOL = """        function jackpotPool() {
            let c = 0, w = 0;
            for (const k in jackpot.led) c += jackpot.led[k] || 0;
            for (const k in jackpot.won) w += jackpot.won[k] || 0;
            // b414: несгораемый остаток банка задаётся в Студии (заводской = прежний сид)
            const fl = Number(jpc.floor);
            const floor = (isFinite(fl) && fl >= 0) ? Math.round(fl) : JACKPOT_SEED;
            return Math.max(floor, Math.round(JACKPOT_SEED + c - w));
        }
        function jackpotPlayers() { return Object.keys(jackpot.led).length; }
"""

NEW_POOL = """        function jackpotPool() {
            // b414: несгораемый остаток банка задаётся в Студии (заводской = прежний сид)
            // b416: floor — это ГАРАНТИЯ ПОЛА, а не «мёртвая зона». Раньше было
            // max(floor, SEED + Σвзносов − Σвыплат), и при floor = 10 000 000 витрина
            // стояла на месте, пока взносы не переползут 10m (при ставке 10k — тысяча
            // спинов). Теперь банк = floor + всё, что накоплено сверх сида: с первой
            // же ставки число растёт, а ниже floor не опускается. При заводском
            // floor = JACKPOT_SEED формула даёт ровно прежние числа.
            return Math.round(jpFloor() + jpExcess());
        }
        // b416: служебная запись дома и испорченные счётчики игроками не считаются
        function jackpotPlayers() { let n = 0; for (const k in jackpot.led) if (k !== JP_HOUSE && !jpLedBad(jackpot.led[k])) n++; return n; }
"""

# --- 3. загрузка реестра: лечим то, что досталось от старых версий ---
OLD_LOAD = "        let jackpot = jackpotLoad();\n"
NEW_LOAD = ("        let jackpot = jackpotLoad();\n"
            "        // b416: реестр, доставшийся от прежних версий/чужих пушей, может содержать\n"
            "        // счётчики за пределами double-точности (1e57) — с ними банк замерзает.\n"
            "        // Чиним сразу, до первого рендера и до первой синхронизации.\n"
            "        if (jpRepairLedger()) { try { jackpotSave(); } catch (e) {} }\n")

# --- 4. слияние с облаком: чужой мусор не должен замораживать банк ---
OLD_MERGE = "            pick(jackpot.led, remote.led); pick(jackpot.won, remote.won); pick(jackpot.wins, remote.wins);\n"
NEW_MERGE = ("            pick(jackpot.led, remote.led); pick(jackpot.won, remote.won); pick(jackpot.wins, remote.wins);\n"
             "            if (jpRepairLedger()) ch = true; // b416: облако (или старый клиент) могло притащить счётчики-гиганты\n")

# --- 5. взнос ставки ---
OLD_FEED = """            const x = pct > 0 ? Math.max(1, Math.round((bet || 0) * JACKPOT_FEED * pct / 100)) : 0;
            if (x <= 0) return;
            jackpot.led[JACKPOT_CID] = (jackpot.led[JACKPOT_CID] || 0) + x;
            jackpotSave(); jackpotRender(); jpSyncSoon();
"""
NEW_FEED = """            const x = pct > 0 ? Math.max(1, Math.round((bet || 0) * JACKPOT_FEED * pct / 100)) : 0;
            if (x <= 0) return;
            jpLedAdd('led', JACKPOT_CID, x); // b416: запись через потолок — счётчик больше не улетает в 1e57
            jackpotSave(); jackpotRender(); jpSyncSoon();
"""

# --- 6. взнос проигрыша ---
OLD_LOSS = """            const add = pct > 0 ? Math.max(1, Math.round((loss || 0) * pct / 100)) : 0;
            if (add <= 0) return 0;
            jackpot.led[JACKPOT_CID] = (jackpot.led[JACKPOT_CID] || 0) + add;
            jackpotSave(); jackpotRender(); jpSyncSoon();
            return add;
"""
NEW_LOSS = """            const add = pct > 0 ? Math.max(1, Math.round((loss || 0) * pct / 100)) : 0;
            if (add <= 0) return 0;
            const got = jpLedAdd('led', JACKPOT_CID, add); // b416: через потолок; возвращаем, сколько реально легло в банк
            jackpotSave(); jackpotRender(); jpSyncSoon();
            return got;
"""

# --- 7. срыв джекпота: никакого «фантомного долга» ---
OLD_WIN = """            jackpot.won[JACKPOT_CID] = (jackpot.won[JACKPOT_CID] || 0) + prize;
"""
NEW_WIN = """            // b416: в реестр выплат пишем только обеспеченную часть — ту, что реально
            // накоплена сверх несгораемого остатка. Раньше сюда падал весь prize, и срыв
            // банка, стоящего на полу, создавал «фантомный долг»: Σвыплат уезжала выше
            // Σвзносов, банк навсегда прижимался к floor и переставал расти.
            jpLedAdd('won', JACKPOT_CID, Math.min(prize, jpExcess()));
"""

# --- 8. ручная правка банка ---
OLD_SET = """            if (d > 0) jackpot.led[JACKPOT_CID] = (jackpot.led[JACKPOT_CID] || 0) + d;
            else jackpot.won[JACKPOT_CID] = (jackpot.won[JACKPOT_CID] || 0) + (-d);
            jackpotSave(); jackpotRender();
            try { jpcAdminPreview(); } catch (e) {}
            try { jpSyncNow(); } catch (e) {}
            showToast((d > 0 ? '📈 Банк поднят до ' : '📉 Банк снижен до ') + fmtCoins(jackpotPool()), 'success');
"""
NEW_SET = """            // b416: пишем через jpLedAdd (потолок + срез мусора). Дельта больше не
            // тонет в погрешности double, поэтому «Поставить банк» снова работает и
            // на огромных числах, и после испорченного реестра.
            if (d > 0) jpLedAdd('led', JACKPOT_CID, d);
            else jpLedAdd('won', JACKPOT_CID, -d);
            jpRepairLedger(); // уход ниже пола гасится домом сразу — долг не копится
            jackpotSave(); jackpotRender();
            try { jpcAdminPreview(); } catch (e) {}
            try { jpSyncNow(); } catch (e) {}
            const got = jackpotPool();
            if (got === target) showToast((d > 0 ? '📈 Банк поднят до ' : '📉 Банк снижен до ') + fmtCoins(got), 'success');
            // b416: честная подпись — раньше тост рапортовал успех, даже если сумма не встала
            else showToast('Банк не встал ровно: сейчас ' + fmtCoins(got) + ' (потолок одного счётчика ' + fmtCoins(JP_LED_CAP) + ')', 'info');
"""

# --- 9. суммы в панели Студии (два одинаковых места) ---
OLD_SUMS = """            for (const k in jackpot.led) fed += jackpot.led[k] || 0;
            for (const k in jackpot.won) won += jackpot.won[k] || 0;
"""
NEW_SUMS = """            fed = jpLedSum(jackpot.led); won = jpLedSum(jackpot.won); // b416: суммы без мусора и без потери точности
"""

# --- 10. своя статистика сайта ---
OLD_SELF = """                e.fed = Math.floor(jackpot.led[JACKPOT_CID]) || 0;
                e.won = Math.floor(jackpot.won[JACKPOT_CID]) || 0;
"""
NEW_SELF = """                e.fed = jpLedNum(jackpot.led[JACKPOT_CID]); // b416: в реестр сайта не утекает 1e57
                e.won = jpLedNum(jackpot.won[JACKPOT_CID]);
"""

# --- 11. отчёт о ремонте в панели «Джекпот» ---
OLD_PREVIEW = """            const pn = document.getElementById('jpc-pool-now');
            if (pn) pn.textContent = fmtCoins(jackpotPool());
"""
NEW_PREVIEW = """            const pn = document.getElementById('jpc-pool-now');
            if (pn) pn.textContent = fmtCoins(jackpotPool());
            // b416: что именно починила автоматика — владелец должен видеть причину
            const fn = document.getElementById('jpc-fix-note');
            if (fn) {
                if (jpFixInfo.n > 0) {
                    fn.hidden = false;
                    fn.innerHTML = '<i class="fa-solid fa-screwdriver-wrench text-emerald-400 mr-1"></i>Реестр банка починен автоматически: испорченных записей <b class="text-slate-300">' + jpFixInfo.n + '</b>' +
                        (jpFixInfo.debt > 0 ? ', долг <b class="text-slate-300">' + fmtCoins(jpFixInfo.debt) + '</b> покрыт домом' : '') +
                        '. Счётчики выше <b class="text-slate-300">' + fmtCoins(JP_LED_CAP) + '</b> банк не учитывает — на таких величинах у double шаг ≈ 1e40, и взносы игроков исчезали, поэтому банк стоял на месте.';
                } else fn.hidden = true;
            }
"""

# --- 12. реестр сайта: fed/won — копии счётчиков банка, режем тем же потолком ---
OLD_NORM = """                jp: Math.max(0, Math.floor(e.jp) || 0),
                fed: Math.max(0, Math.floor(e.fed) || 0),
                won: Math.max(0, Math.floor(e.won) || 0),
"""
NEW_NORM = """                jp: Math.max(0, Math.floor(e.jp) || 0),
                // b416: fed/won — это копии счётчиков реестра банка; режем их тем же
                // потолком, иначе старый клиент с 1e57 в localStorage снова тащит
                // астрономию в таблицу Студии (записи сливаются по «at», поэтому
                // своя свежая публикация их и так перетирает — это страховка)
                fed: jpLedNum(e.fed),
                won: jpLedNum(e.won),
"""

JS_PATCHES = [
    ('модуль целостности реестра (b416)', ANCHOR_MODULE, ANCHOR_MODULE + MODULE),
    ('siteStatsNorm: fed/won в потолке', OLD_NORM, NEW_NORM),
    ('jackpotPool + jackpotPlayers', OLD_POOL, NEW_POOL),
    ('ремонт реестра при загрузке', OLD_LOAD, NEW_LOAD),
    ('ремонт реестра после слияния', OLD_MERGE, NEW_MERGE),
    ('jackpotFeed: запись через потолок', OLD_FEED, NEW_FEED),
    ('jackpotOnLoss: запись через потолок', OLD_LOSS, NEW_LOSS),
    ('jackpotWin: без фантомного долга', OLD_WIN, NEW_WIN),
    ('jpcSetPool: честная правка банка', OLD_SET, NEW_SET),
    ('siteStatsSelfUpdate: fed/won без мусора', OLD_SELF, NEW_SELF),
    ('jpcAdminPreview: отчёт о ремонте', OLD_PREVIEW, NEW_PREVIEW),
]

JS_PATCHES_ALL = [
    (OLD_SUMS, NEW_SUMS),
]

# --------------------------------------------------------------------------- #
# index.html: вкладка Студии «Джекпот»
# --------------------------------------------------------------------------- #
HTML_PATCHES = [
    ('подпись несгораемого остатка',
     '<span class="block text-[9px] text-slate-600 mt-1 leading-tight">Банк никогда не опускается ниже этого значения</span>',
     '<span class="block text-[9px] text-slate-600 mt-1 leading-tight">Пол банка: ниже него банк не опускается, а взносы игроков растут <b>сверх</b> него (b416 — раньше при большом поле банк стоял на месте)</span>'),

    ('кнопка «Починить банк»',
     '<button type="button" onclick="jpcResetPoolFloor()" class="px-2.5 py-1.5 bg-slate-900 hover:bg-rose-950/60 border border-slate-800 rounded-lg text-[11px] font-bold text-slate-400 transition">Сбросить до минимума</button>',
     '<button type="button" onclick="jpcResetPoolFloor()" class="px-2.5 py-1.5 bg-slate-900 hover:bg-rose-950/60 border border-slate-800 rounded-lg text-[11px] font-bold text-slate-400 transition">Сбросить до минимума</button>\n'
     '                    <button type="button" onclick="jpRepairNow()" title="Выбросить испорченные счётчики реестра и погасить долг банка" class="px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-slate-950 rounded-lg text-[11px] font-black transition"><i class="fa-solid fa-screwdriver-wrench mr-1"></i>Починить банк</button>'),

    ('пояснение про реестр банка',
     '<p class="text-[10px] text-slate-500 leading-snug">Сумма понимает буквы: <b class="text-slate-300">10k</b>, <b class="text-slate-300">5m</b>, <b class="text-slate-300">1b</b>. Банк общий на весь сайт — правка видна всем игрокам после синхронизации. «Сбросить до минимума» оставляет в банке только несгораемый остаток.</p>',
     '<p class="text-[10px] text-slate-500 leading-snug">Сумма понимает буквы: <b class="text-slate-300">10k</b>, <b class="text-slate-300">5m</b>, <b class="text-slate-300">1b</b>. Банк общий на весь сайт — правка видна всем игрокам после синхронизации. «Сбросить до минимума» оставляет в банке только несгораемый остаток.</p>\n'
     '                <p id="jpc-fix-note" hidden class="text-[10px] text-emerald-300 leading-snug"></p>\n'
     '                <p class="text-[10px] text-slate-500 leading-snug"><i class="fa-solid fa-circle-info text-sky-400 mr-1"></i>Банк копится реестром счётчиков (взносы минус выплаты). b416: у одного счётчика есть потолок <b class="text-slate-300">10t</b>, всё выше — мусор, который банк не учитывает; «Починить банк» выбрасывает такие записи и гасит долг, из-за которого банк стоял на полу. То же самое игра делает сама при загрузке и после каждой синхронизации.</p>'),
]


# --------------------------------------------------------------------------- #
def patch_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise AssertionError('якорь «%s» встретился %d раз (нужно 1)' % (label, n))
    return text.replace(old, new, 1)


def main():
    check = '--check' in sys.argv
    js = os.path.join(ROOT, 'assets', 'app.js')
    html = os.path.join(ROOT, 'index.html')

    if check:
        bad = 0
        s = open(js, encoding='utf-8').read()
        for label, old, _n in JS_PATCHES:
            n = s.count(old); bad += (n != 1); print('  %s %-44s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        for old, _n in JS_PATCHES_ALL:
            n = s.count(old); bad += (n < 1); print('  %s %-44s %d (все)' % ('OK ' if n >= 1 else 'BAD', old[:40].replace('\n', '\\n'), n))
        h = open(html, encoding='utf-8').read()
        for label, old, _n in HTML_PATCHES:
            n = h.count(old); bad += (n != 1); print('  %s %-44s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        return 1 if bad else 0

    s = open(js, encoding='utf-8').read()
    for label, old, new in JS_PATCHES:
        s = patch_once(s, old, new, label); print('  · %-44s ok' % label)
    for old, new in JS_PATCHES_ALL:
        n = s.count(old)
        if n:
            s = s.replace(old, new); print('  · %-44s ok ×%d' % (old[:40].replace('\n', '\\n'), n))
    open(js, 'w', encoding='utf-8', newline='').write(s)

    h = open(html, encoding='utf-8').read()
    for label, old, new in HTML_PATCHES:
        h = patch_once(h, old, new, label); print('  · %-44s ok' % label)
    open(html, 'w', encoding='utf-8', newline='').write(h)

    for p, old, new in ((html, '?v=' + OLD_V, '?v=' + NEW_V),
                        (os.path.join(ROOT, 'sw.js'), "const VERSION = '%s';" % OLD_V, "const VERSION = '%s';" % NEW_V),
                        (os.path.join(ROOT, 'tools', 'build.py'), "BUILD_TAG = '%s'" % OLD_V, "BUILD_TAG = '%s'" % NEW_V)):
        t = open(p, encoding='utf-8').read()
        n = t.count(old)
        if n:
            open(p, 'w', encoding='utf-8', newline='').write(t.replace(old, new))
        print('  · версия %-28s ×%d → %s' % (os.path.basename(p), n, NEW_V))
    return 0


if __name__ == '__main__':
    sys.exit(main())
