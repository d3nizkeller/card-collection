#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b419 — «джекпот должен расти без ограничений»: разряды вместо вёдер с ёмкостью.

Жалоба владельца: «джектод должен расти без ограничений».

b418 ввёл вёдра по 1e12 с лимитом 4096 штук = 4.096e15 на игрока: это уже не
«+0», но всё ещё потолок — а владелец уже упирался в потолок 1e13 за час игры,
значит и 4e15 когда-нибудь станет «не растёт». Жёстких пределов не должно быть
вовсе.

Стало: вёдра превратились в РАЗРЯДЫ смешанной системы с основанием 1000:
разряд i вмещает JP_TIER0 * 1000^i (1e13, 1e16, 1e19, 1e22, … до 1e82).
Переполнение разряда уходит в старший, поэтому:

  * любой взнос любой величины ложится ПОЛНОСТЬЮ (jpLedAdd возвращает x);
  * ключей на игроку нужно ~log1000(банк): при банке 1e40 их десять,
    облачный документ не раздувается;
  * слияние то же (max на ключ), суммы — по возрастанию разрядов;
  * «мусор» теперь = запись ВНЕ ёмкости СВОЕГО разряда (битая или чужая),
    защита b416 от 1e57 на месте: 1e57 в разряде 0 режется, 1e16 в разряде 1 —
    честное значение;
  * старые ключи с 1e13 (ровно ёмкость разряда 0) остаются валидными,
    миграция данных не нужна.

Плюс витрина: fmtCoins/parseBetStr получили буквы до дециллионов
(s 1e18, u 1e21, p 1e24, o 1e27, n 1e30, d 1e33), чтобы огромный банк
показывался буквами, а не «1000q» и не «1e+42q».

Честное примечание про точность: double даёт ~15–16 значащих цифр, это
свойство JS/JSON, а не ограничение игры: при банке 1e22 взнос 100 монет
округлится (шаг сетки double ≈ 2e6), но любой взнос от тысяч монет виден,
и жёсткого «стопа» нет ни на одной величине.

Запуск:  python3 tools/_b419_patch.py            — применить
         python3 tools/_b419_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob80'
NEW_V = 'nxmob81'

# --------------------------------------------------------------------------- #
# app.js
# --------------------------------------------------------------------------- #

OLD_TIERS = """        // b418: счётчик-«вёдра». Одномерный счётчик с потолком можно упереть в
        // потолок (владелец докормил led до 1e13 — и взносы снова стали исчезать,
        // «банк вырос на +0»). Теперь переполнение дописывается в следующее ведро
        // (cid#1, cid#2, …): слияние то же (max на ключ), суммы точные (слагаемые
        // ≤ 1e12), а живой банк не упирается ни во что: 4096 вёдер × 1e12 = 4e15
        // на игрока. Мусор (> JP_LED_CAP в одном ключе) по-прежнему режется.
        const JP_BUCKET = 1e12;
        const JP_MAX_BUCKETS = 4096;
        function jpBucketKey(cid, i) { return i ? cid + '#' + i : cid; }
"""

NEW_TIERS = """        // b418: счётчик-«вёдра». Одномерный счётчик с потолком можно упереть в
        // потолок (владелец докормил led до 1e13 — и взносы снова стали исчезать,
        // «банк вырос на +0»).
        // b419: «джекпот должен расти без ограничений» — вёдра стали РАЗРЯДАМИ
        // смешанной системы с основанием 1000: разряд i вмещает JP_TIER0*1000^i
        // (1e13, 1e16, 1e19, … до 1e82). Переполнение разряда уходит в старший,
        // любой взнос любой величины ложится полностью, ключей на игроку нужно
        // ~log1000(банк) (при банке 1e40 — десять), слияние то же (max на ключ).
        // Жёстких потолков роста больше нет; «мусор» = запись вне ёмкости СВОЕГО
        // разряда, так что защита b416 от 1e57 на месте, а старые ключи с 1e13
        // (ровно ёмкость разряда 0) остаются валидными без миграции.
        const JP_TIER0 = 1e13;
        const JP_TIER_MUL = 1000;
        const JP_TIERS = 24; // до 1e13*1000^23 ≈ 1e82 — дальше только экспоненциальная запись
        function jpTierCap(i) { return JP_TIER0 * Math.pow(JP_TIER_MUL, i | 0); }
        function jpTierOfKey(k) { const h = String(k).indexOf('#'); return h > 0 ? (Math.abs(parseInt(String(k).slice(h + 1), 10)) || 0) : 0; }
        function jpBucketKey(cid, i) { return i ? cid + '#' + i : cid; }
"""

OLD_BAD = """        // запись пригодна для счёта, если это целое в пределах [0, JP_LED_CAP]
        function jpLedBad(v) { const n = Number(v); return !(isFinite(n) && n >= 0 && n <= JP_LED_CAP && n === Math.floor(n)); }
        function jpLedNum(v) { return jpLedBad(v) ? 0 : Math.floor(Number(v)); }
"""

NEW_BAD = """        // b416/b419: запись пригодна для счёта, только если это целое в пределах
        // ёмкости СВОЕГО разряда (tier по суффиксу ключа; без аргумента — разряд 0)
        function jpLedBad(v, tier) { const n = Number(v); return !(isFinite(n) && n >= 0 && n <= jpTierCap(tier || 0) && n === Math.floor(n)); }
        function jpLedNum(v, tier) { return jpLedBad(v, tier) ? 0 : Math.floor(Number(v)); }
"""

OLD_SUM = """            const a = [];
            for (const k in m) { const v = jpLedNum(m[k]); if (v > 0) a.push(v); }
"""
NEW_SUM = """            const a = [];
            for (const k in m) { const v = jpLedNum(m[k], jpTierOfKey(k)); if (v > 0) a.push(v); } // b419: разряды
"""

OLD_ADD = """        function jpLedAdd(field, cid, x) {
            // возвращает, сколько РЕАЛЬНО легло в реестр (0 = не влезло ни в одно ведро)
            x = Math.floor(Number(x) || 0);
            if (!(x > 0)) return 0;
            const m = jackpot[field] || (jackpot[field] = {});
            let left = x, added = 0;
            for (let i = 0; left > 0 && i < JP_MAX_BUCKETS; i++) {
                const k = jpBucketKey(cid, i);
                const cur = jpLedNum(m[k]);
                const put = Math.min(left, JP_BUCKET - cur);
                if (put > 0) { m[k] = cur + put; added += put; left -= put; }
            }
            return added;
        }
"""

NEW_ADD = """        function jpLedAdd(field, cid, x) {
            // b419: каскад по разрядам; возвращает, сколько легло (для любой
            // конечной суммы вплоть до 1e82 — ровно x, пределов роста нет)
            x = Math.floor(Number(x) || 0);
            if (!(x > 0)) return 0;
            const m = jackpot[field] || (jackpot[field] = {});
            let left = x, added = 0;
            for (let i = 0; left > 0 && i < JP_TIERS; i++) {
                const k = jpBucketKey(cid, i);
                const cur = jpLedNum(m[k], i);
                const put = Math.min(left, jpTierCap(i) - cur);
                if (put > 0) { m[k] = cur + put; added += put; left -= put; }
            }
            return added;
        }
"""

OLD_OF = """            for (const k in m) if (k === cid || k.indexOf(cid + '#') === 0) s += jpLedNum(m[k]);
"""
NEW_OF = """            for (const k in m) if (k === cid || k.indexOf(cid + '#') === 0) s += jpLedNum(m[k], jpTierOfKey(k)); // b419: разряды
"""

OLD_PLAYERS_BAD = """                if (jpLedBad(jackpot.led[k])) continue;
"""
NEW_PLAYERS_BAD = """                if (jpLedBad(jackpot.led[k], jpTierOfKey(k))) continue; // b419
"""

OLD_REPAIR_BAD = """                for (const k in m) if (jpLedBad(m[k])) { delete m[k]; n++; }
"""
NEW_REPAIR_BAD = """                for (const k in m) if (jpLedBad(m[k], jpTierOfKey(k))) { delete m[k]; n++; } // b419: вне ёмкости своего разряда
"""

OLD_FMT = """            const units = [[1e15, 'q'], [1e12, 't'], [1e9, 'b'], [1e6, 'm'], [1e3, 'k']]; // b222: буквы до квадриллионов
"""
NEW_FMT = """            // b222: буквы до квадриллионов; b419: и дальше — до дециллионов, чтобы
            // неограниченно растущий банк показывался буквами, а не «1000q»/«1e+42q»
            const units = [[1e33, 'd'], [1e30, 'n'], [1e27, 'o'], [1e24, 'p'], [1e21, 'u'], [1e18, 's'], [1e15, 'q'], [1e12, 't'], [1e9, 'b'], [1e6, 'm'], [1e3, 'k']];
"""

OLD_PARSE = """            else if (last === 'q') { mult = 1e15; t = t.slice(0, -1); } // b222: квадриллионы
"""
NEW_PARSE = """            else if (last === 'q') { mult = 1e15; t = t.slice(0, -1); } // b222: квадриллионы
            // b419: те же буквы, что и в fmtCoins, — ставку и банк можно писать до дециллионов
            else if (last === 's') { mult = 1e18; t = t.slice(0, -1); }
            else if (last === 'u') { mult = 1e21; t = t.slice(0, -1); }
            else if (last === 'p') { mult = 1e24; t = t.slice(0, -1); }
            else if (last === 'o') { mult = 1e27; t = t.slice(0, -1); }
            else if (last === 'n') { mult = 1e30; t = t.slice(0, -1); }
            else if (last === 'd') { mult = 1e33; t = t.slice(0, -1); }
"""

OLD_SET_TOAST = """            else showToast('Банк не встал ровно: сейчас ' + fmtCoins(got) + ' (потолок одного счётчика ' + fmtCoins(JP_LED_CAP) + ')', 'info');
"""
NEW_SET_TOAST = """            else showToast('Банк не встал ровно: сейчас ' + fmtCoins(got) + ' (так бывает только с нечисловой суммой)', 'info'); // b419: потолков больше нет
"""

OLD_FIXNOTE = """                        '. Счётчики выше <b class="text-slate-300">' + fmtCoins(JP_LED_CAP) + '</b> банк не учитывает — на таких величинах у double шаг ≈ 1e40, и взносы игроков исчезали, поэтому банк стоял на месте.';
"""
NEW_FIXNOTE = """                        '. Битые записи реестра банк не учитывает — раньше они уводили счётчики в 1e57, где у double шаг ≈ 1e40 и взносы игроков исчезали, поэтому банк стоял на месте. С b419 банк растёт без ограничений: реестр ведётся разрядами 1e13 → 1e16 → 1e19…';
"""

JS_PATCHES = [
    ('разряды вместо вёдер (b419)', OLD_TIERS, NEW_TIERS),
    ('jpLedBad/jpLedNum по разряду', OLD_BAD, NEW_BAD),
    ('jpLedSum по разрядам', OLD_SUM, NEW_SUM),
    ('jpLedAdd: каскад разрядов', OLD_ADD, NEW_ADD),
    ('jpLedOf по разрядам', OLD_OF, NEW_OF),
    ('jackpotPlayers: разряды', OLD_PLAYERS_BAD, NEW_PLAYERS_BAD),
    ('ремонт: разряды', OLD_REPAIR_BAD, NEW_REPAIR_BAD),
    ('fmtCoins: буквы до дециллионов', OLD_FMT, NEW_FMT),
    ('parseBetStr: буквы до дециллионов', OLD_PARSE, NEW_PARSE),
    ('тост jpcSetPool без потолка', OLD_SET_TOAST, NEW_SET_TOAST),
    ('fmtCoins: эпсилон-дозводка',
     "                    const t = x >= 100 ? Math.floor(x) : Math.floor(x * 10) / 10;",
     "                    // b419: эпсилон-дозводка: 3e30/1e30 в double = 2.9999999999999996,\n"
     "                    // без неё витрина показала бы «2.9n» вместо «3n»\n"
     "                    const t = x >= 100 ? Math.floor(x + 1e-9) : Math.floor(x * 10 + 1e-6) / 10;"),
    ('отчёт о ремонте: новая формулировка', OLD_FIXNOTE, NEW_FIXNOTE),
]

HTML_PATCHES = [
    ('пояснение про реестр в Студии',
     '<p class="text-[10px] text-slate-500 leading-snug"><i class="fa-solid fa-circle-info text-sky-400 mr-1"></i>Банк копится реестром счётчиков (взносы минус выплаты). b416: у одного счётчика есть потолок <b class="text-slate-300">10t</b>, всё выше — мусор, который банк не учитывает; «Починить банк» выбрасывает такие записи и гасит долг, из-за которого банк стоял на полу. То же самое игра делает сама при загрузке и после каждой синхронизации.</p>',
     '<p class="text-[10px] text-slate-500 leading-snug"><i class="fa-solid fa-circle-info text-sky-400 mr-1"></i>Банк копится реестром счётчиков (взносы минус выплаты) и с b419 растёт <b class="text-slate-300">без ограничений</b>: реестр ведётся разрядами 1e13 → 1e16 → 1e19 → …, переполнение разряда уходит в старший. «Починить банк» выбрасывает битые записи (вне ёмкости своего разряда — как прежние 1e57, из-за которых банк стоял на полу) и гасит долг; то же самое игра делает сама при загрузке и после каждой синхронизации.</p>'),
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
            n = s.count(old); bad += (n != 1); print('  %s %-40s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        h = open(html, encoding='utf-8').read()
        for label, old, _n in HTML_PATCHES:
            n = h.count(old); bad += (n != 1); print('  %s %-40s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        return 1 if bad else 0

    s = open(js, encoding='utf-8').read()
    for label, old, new in JS_PATCHES:
        s = patch_once(s, old, new, label); print('  · %-40s ok' % label)
    open(js, 'w', encoding='utf-8', newline='').write(s)

    h = open(html, encoding='utf-8').read()
    for label, old, new in HTML_PATCHES:
        h = patch_once(h, old, new, label); print('  · %-40s ok' % label)
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
