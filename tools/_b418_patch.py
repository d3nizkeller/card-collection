#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b418 — банк снова растёт: счётчики-«вёдра», сброс настроек и сброс топа джекпотов.

Жалобы владельца (скриншоты Студии и тоста):
  1) «джекпот не усиливается от проигрышей пользователей», тост:
     «Мимо — банк джекпота вырос на +0 и теперь 1k»;
  2) «в студии кнопки: стандартные настройки и сброс топ джекпотов сайта».

Диагноз (1): потолок b416 (JP_LED_CAP = 1e13 на один счётчик) спас банк от
1e57, но сам стал новым потолком: владелец кормил банк ставками до 100b и
ручными «Поставить банк», его led дошёл ровно до 1e13 («Внесено в банк: 10t»),
и дальше jpLedAdd() возвращал 0 — взносы и проигрыши снова исчезали
(«вырос на +0»). Одномерный счётчик с потолком всегда можно упереть в потолок.

Решение: счётчик стал многомерным — «вёдра» по JP_BUCKET = 1e12. Запись
переполнилась → остаток дописывается в следующую (`cid#1`, `cid#2`, …).
Правило слияния то же (max на ключ), суммы точные (каждое слагаемое ≤ 1e12,
складываем по возрастанию), потолок jpLedBad по-прежнему режет только мусор
(> 1e13), а живой банк не упирается ни во что: 4096 вёдер × 1e12 = 4e15
на игрока, суммарно до Number.MAX_SAFE_INTEGER включительно.

Диагноз (2): в топе-3 висел мусор эпохи 1e57 («+1e+42q») — зал славы (hall)
сливается объединением, поэтому простое «очистить» откатилось бы первым же
слиянием со старым клиентом. Добавлен tombstone `hallCut`: записи с t ≤ hallCut
игнорируются везде (загрузка, слияние, рендер), кнопка «Сбросить топ джекпотов
сайта» ставит hallCut = сейчас и очищает hall. Рядом кнопка «Стандартные
настройки» — возвращает заводские проценты (b414) и публикует их всем.

Запуск:  python3 tools/_b418_patch.py            — применить
         python3 tools/_b418_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob79'
NEW_V = 'nxmob80'

# --------------------------------------------------------------------------- #
# app.js
# --------------------------------------------------------------------------- #

OLD_ADD = """        function jpLedAdd(field, cid, x) {
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
"""

NEW_ADD = """        // b418: счётчик-«вёдра». Одномерный счётчик с потолком можно упереть в
        // потолок (владелец докормил led до 1e13 — и взносы снова стали исчезать,
        // «банк вырос на +0»). Теперь переполнение дописывается в следующее ведро
        // (cid#1, cid#2, …): слияние то же (max на ключ), суммы точные (слагаемые
        // ≤ 1e12), а живой банк не упирается ни во что: 4096 вёдер × 1e12 = 4e15
        // на игрока. Мусор (> JP_LED_CAP в одном ключе) по-прежнему режется.
        const JP_BUCKET = 1e12;
        const JP_MAX_BUCKETS = 4096;
        function jpBucketKey(cid, i) { return i ? cid + '#' + i : cid; }
        function jpLedAdd(field, cid, x) {
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
        function jpLedOf(field, cid) {
            // b418: суммарный счётчик игрока по всем его вёдрам
            const m = jackpot[field] || {};
            let s = 0;
            for (const k in m) if (k === cid || k.indexOf(cid + '#') === 0) s += jpLedNum(m[k]);
            return s;
        }
        function jpHallFiltered(hall, cut) {
            // b418: записи зала славы старше tombstone hallCut не показываются нигде
            const c = Math.floor(Number(cut) || 0);
            return (Array.isArray(hall) ? hall : []).filter(h => h && h.t > c);
        }
"""

OLD_PLAYERS = """        // b416: служебная запись дома и испорченные счётчики игроками не считаются
        function jackpotPlayers() { let n = 0; for (const k in jackpot.led) if (k !== JP_HOUSE && !jpLedBad(jackpot.led[k])) n++; return n; }
"""

NEW_PLAYERS = """        // b416: служебная запись дома и испорченные счётчики игроками не считаются
        // b418: вёдра cid#N одного игрока считаем за ОДНОГО игрока
        function jackpotPlayers() {
            const seen = {};
            for (const k in jackpot.led) {
                if (jpLedBad(jackpot.led[k])) continue;
                const h = k.indexOf('#');
                const base = h > 0 ? k.slice(0, h) : k;
                if (base === JP_HOUSE) continue;
                seen[base] = 1;
            }
            return Object.keys(seen).length;
        }
"""

OLD_LOAD = "                if (j && j.led) return { led: j.led || {}, won: j.won || {}, wins: j.wins || {}, names: j.names || {}, hall: j.hall || [] };\n"
NEW_LOAD = "                if (j && j.led) return { led: j.led || {}, won: j.won || {}, wins: j.wins || {}, names: j.names || {}, hall: jpHallFiltered(j.hall, j.hallCut), hallCut: Math.floor(j.hallCut) || 0 }; // b418: tombstone зала славы\n"

OLD_MERGE_HALL = """            // зал славы победителей: объединяем по метке времени, держим 6 последних
            if (Array.isArray(remote.hall) && remote.hall.length) {
                const map = {};
                (jackpot.hall || []).forEach(h => { if (h && h.t) map[h.t] = h; });
                remote.hall.forEach(h => { if (h && h.t && !map[h.t]) { map[h.t] = h; ch = true; } });
                jackpot.hall = Object.keys(map).map(k => map[k]).sort((a, b) => b.t - a.t).slice(0, 20);
            }
"""

NEW_MERGE_HALL = """            // зал славы победителей: объединяем по метке времени, держим 6 последних
            // b418: сброс зала славы — tombstone hallCut: записи с t ≤ hallCut не
            // воскресают ни из облака, ни из localStorage старых клиентов
            const cut = Math.max(Math.floor(jackpot.hallCut) || 0, Math.floor(remote.hallCut) || 0);
            if (cut > (Math.floor(jackpot.hallCut) || 0)) { jackpot.hallCut = cut; ch = true; }
            if (Array.isArray(remote.hall) && remote.hall.length) {
                const map = {};
                (jackpot.hall || []).forEach(h => { if (h && h.t && h.t > cut) map[h.t] = h; });
                remote.hall.forEach(h => { if (h && h.t && h.t > cut && !map[h.t]) { map[h.t] = h; ch = true; } });
                jackpot.hall = Object.keys(map).map(k => map[k]).sort((a, b) => b.t - a.t).slice(0, 20);
            } else if ((jackpot.hall || []).some(h => h && h.t <= cut)) {
                jackpot.hall = (jackpot.hall || []).filter(h => h && h.t > cut);
                ch = true;
            }
"""

OLD_DOC = "                jp: { led: jackpot.led, won: jackpot.won, wins: jackpot.wins, names: jackpot.names, hall: jackpot.hall },\n"
NEW_DOC = "                jp: { led: jackpot.led, won: jackpot.won, wins: jackpot.wins, names: jackpot.names, hall: jackpot.hall, hallCut: jackpot.hallCut || 0 }, // b418: tombstone зала славы едет со всеми\n"

OLD_RENDER_REAL = """            // b91: кто последним сорвал джекпот — видно всем
            const top = (jackpot.hall || [])[0];
            const wtxt = top
                ? '👑 Последний джекпот: ' + (top.n || 'игрок') + ' — +' + fmtCoins(top.a || 0) + ' (' + new Date(top.t).toLocaleDateString() + ')'
                : '👑 Джекпот сайта ещё не срывали — станьте первым!';
            const wtitle = (jackpot.hall || []).map(h => (h.n || 'игрок') + ': +' + fmtCoins(h.a || 0) + ' (' + new Date(h.t).toLocaleDateString() + ')').join('\\n');"""

NEW_RENDER = """            // b91: кто последним сорвал джекпот — видно всем
            // b418: зал славы читаем через tombstone hallCut (после сброса топ пуст)
            const hall = jpHallFiltered(jackpot.hall, jackpot.hallCut);
            const top = hall[0];
            const wtxt = top
                ? '👑 Последний джекпот: ' + (top.n || 'игрок') + ' — +' + fmtCoins(top.a || 0) + ' (' + new Date(top.t).toLocaleDateString() + ')'
                : '👑 Джекпот сайта ещё не срывали — станьте первым!';
            const wtitle = hall.map(h => (h.n || 'игрок') + ': +' + fmtCoins(h.a || 0) + ' (' + new Date(h.t).toLocaleDateString() + ')').join('\\n');"""

OLD_TOPWINS = "            const topWins = (jackpot.hall || []).slice().sort((a, b) => (b.a || 0) - (a.a || 0)).slice(0, 3); // b101: топ-3\n"
NEW_TOPWINS = "            const topWins = hall.slice().sort((a, b) => (b.a || 0) - (a.a || 0)).slice(0, 3); // b101: топ-3; b418: после сброса — пуст\n"

OLD_SELF = """                e.fed = jpLedNum(jackpot.led[JACKPOT_CID]); // b416: в реестр сайта не утекает 1e57
                e.won = jpLedNum(jackpot.won[JACKPOT_CID]);
"""
NEW_SELF = """                e.fed = jpLedOf('led', JACKPOT_CID); // b416: в реестр сайта не утекает 1e57; b418: сумма по всем вёдрам
                e.won = jpLedOf('won', JACKPOT_CID);
"""

OLD_FLOOR_BTN = "        function jpcResetPoolFloor() { jpcSetPool(Math.max(0, Math.round(jpc.floor || 0))); }\n"
NEW_FLOOR_BTN = """        function jpcResetPoolFloor() { jpcSetPool(Math.max(0, Math.round(jpc.floor || 0))); }
        // b418: кнопка «Стандартные настройки» в Студии — заводские проценты b414
        // (100/100/100, пол 1000, без потолка, заводские вероятности и гарантии)
        // с публикацией всем игрокам сайта; назначенные выдачи (grant) сохраняем
        function jpcResetDefaults() {
            if (jpcAdminGuard()) return;
            const kept = jpc.grant;
            jpc = jpcNorm(JPC_DEFAULTS);
            jpc.grant = kept;
            jpcSave();
            jpcPublish(true); // b414: at/by + пуш в облако, тост свой не нужен
            try { jackpotRender(); } catch (e) {}
            try { if (jpcVisible()) jpcAdminRender(); else jpcAdminPreview(); } catch (e) {}
            showToast('♻️ Настройки джекпота сброшены к стандартным и опубликованы для всех', 'success');
        }
        // b418: кнопка «Сбросить топ джекпотов сайта» — очищает зал славы и топ-3
        // на ВСЕХ клиентах: tombstone hallCut не даст старым записям (включая мусор
        // эпохи 1e57) воскреснуть при слиянии; банк и настройки не трогает
        function jpcResetHall() {
            if (jpcAdminGuard()) return;
            jackpot.hall = [];
            jackpot.hallCut = Date.now();
            jackpotSave(); jackpotRender();
            try { jpcAdminPreview(); } catch (e) {}
            try { jpSyncNow(); } catch (e) {}
            showToast('🏆 Топ джекпотов сайта сброшен — банк и настройки не тронуты', 'success');
        }
"""

JS_PATCHES = [
    ('вёдра вместо одного счётчика (b418)', OLD_ADD, NEW_ADD),
    ('jackpotPlayers: вёдра = один игрок', OLD_PLAYERS, NEW_PLAYERS),
    ('jackpotLoad: hallCut', OLD_LOAD, NEW_LOAD),
    ('слияние зала славы с tombstone', OLD_MERGE_HALL, NEW_MERGE_HALL),
    ('jpDoc: hallCut едет в облако', OLD_DOC, NEW_DOC),
    ('рендер зала славы через hallCut', OLD_RENDER_REAL, NEW_RENDER),
    ('топ-3 из отфильтрованного зала', OLD_TOPWINS, NEW_TOPWINS),
    ('siteStats: fed/won по вёдрам', OLD_SELF, NEW_SELF),
    ('кнопки Студии: сброс настроек и топа', OLD_FLOOR_BTN, NEW_FLOOR_BTN),
]

# --------------------------------------------------------------------------- #
# index.html: две кнопки в блоке «Проценты»
# --------------------------------------------------------------------------- #
HTML_PATCHES = [
    ('кнопки «Стандартные настройки» и «Сбросить топ»',
     '<p class="text-[10px] text-slate-500 leading-snug">Живой пример по текущим настройкам: ставка <b class="text-slate-300">10k</b> кормит банк на <b data-jpc="feed">100%</b> — это <b class="text-slate-300"><span id="jpc-ex-add">10k</span></b>; победитель забирает <b data-jpc="paynum">100%</b> банка — сейчас это <b class="text-slate-300"><span id="jpc-ex-win">—</span></b>, остальное копится дальше и не обнуляет витрину.</p>',
     '<p class="text-[10px] text-slate-500 leading-snug">Живой пример по текущим настройкам: ставка <b class="text-slate-300">10k</b> кормит банк на <b data-jpc="feed">100%</b> — это <b class="text-slate-300"><span id="jpc-ex-add">10k</span></b>; победитель забирает <b data-jpc="paynum">100%</b> банка — сейчас это <b class="text-slate-300"><span id="jpc-ex-win">—</span></b>, остальное копится дальше и не обнуляет витрину.</p>\n'
     '                <div class="flex flex-wrap items-center gap-1.5">\n'
     '                    <button type="button" onclick="jpcResetDefaults()" title="Вернуть заводские проценты: 100/100/100, пол 1000, без потолка, заводские вероятности и гарантии" class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-[11px] font-bold text-slate-200 transition"><i class="fa-solid fa-rotate-left mr-1"></i>Стандартные настройки</button>\n'
     '                    <button type="button" onclick="jpcResetHall()" title="Очистить топ-3 и зал славы на всех клиентах; банк и настройки не трогает" class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-[11px] font-bold text-slate-200 transition"><i class="fa-solid fa-trophy mr-1"></i>Сбросить топ джекпотов сайта</button>\n'
     '                </div>'),
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
        h = open(html, encoding='utf-8').read()
        for label, old, _n in HTML_PATCHES:
            n = h.count(old); bad += (n != 1); print('  %s %-44s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        return 1 if bad else 0

    s = open(js, encoding='utf-8').read()
    for label, old, new in JS_PATCHES:
        s = patch_once(s, old, new, label); print('  · %-44s ok' % label)
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
