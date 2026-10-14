#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b432 — в топ джекпота попадают только игроки С ИМЕНЕМ.

Просьба владельца: «чего игроки без имени в топ попадают — только кто с
именем, кто из пользователей ввёл имя для джекпота». Скриншот: в топе
«Игрок-5r6s», «Игрок-cxaa» — это авто-заглушки ('Игрок-' + cid), которые
ставились, когда имя не введено.

Стало:

* запись зала славы получает флаг `nm: 1`, если игрок ввёл имя
  (getPlayerName()), и `nm: 0`, если нет;
* топ-3 («Последние срывы джекпота»), строка «Последний джекпот» и тултип
  со списком строятся ТОЛЬКО из записей с именем: jpHallNamed(h) = флаг nm
  или (для записей до b432) имя без префикса «Игрок-»;
* если срывы были, но все без имён — в топе честная плашка: «Все срывы пока
  без имени — введите имя, чтобы попасть в топ»;
* безымянный победитель через секунду получает подсказку-тост: «Введите имя
  игрока — и ваши срывы джекпота попадут в топ сайта»;
* старый зал (без флага nm) фильтруется тем же префиксом, миграция не нужна.

Запуск:  python3 tools/_b432_patch.py            — применить
         python3 tools/_b432_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob95'
NEW_V = 'nxmob96'

# --------------------------------------------------------------------------- #
# app.js
# --------------------------------------------------------------------------- #

OLD_HELPER = """        function jpFloor() { const fl = Number(jpc.floor); return (isFinite(fl) && fl >= 0) ? Math.round(fl) : JACKPOT_SEED; }
"""
NEW_HELPER = """        // b432: в топ сайта попадают только игроки, которые ВВЕЛИ имя: запись с
        // флагом nm (после b432) или, для старого зала, с именем без префикса «Игрок-»
        function jpHallNamed(h) {
            if (!h) return false;
            if (h.nm !== undefined) return !!h.nm;
            const n = String(h.n || '');
            return !!n && n.indexOf('Игрок-') !== 0;
        }
        function jpFloor() { const fl = Number(jpc.floor); return (isFinite(fl) && fl >= 0) ? Math.round(fl) : JACKPOT_SEED; }
"""

OLD_WIN = """            // b91: фиксируем победителя по имени — зал славы увидят все игроки сайта
            const wname = getPlayerName() || ('Игрок-' + JACKPOT_CID.slice(1, 5));
            jackpot.names[JACKPOT_CID] = wname;
            jackpot.hall = jackpot.hall || [];
            jackpot.hall.unshift({ n: wname, a: prize, t: Date.now(), c: JACKPOT_CID });
"""
NEW_WIN = """            // b91: фиксируем победителя по имени — зал славы увидят все игроки сайта
            // b432: флаг nm — попал ли срыв в топ сайта (только игроки с именем)
            const realName = getPlayerName();
            const wname = realName || ('Игрок-' + JACKPOT_CID.slice(1, 5));
            jackpot.names[JACKPOT_CID] = wname;
            jackpot.hall = jackpot.hall || [];
            jackpot.hall.unshift({ n: wname, a: prize, t: Date.now(), c: JACKPOT_CID, nm: realName ? 1 : 0 });
"""

OLD_TOAST = """            showToast('👑 JACKPOT! +' + fmtCoins(prize) + ' монет' + (pct < 100 ? ' (' + pct + '% банка)' : ' — весь банк сайта ваш'), 'success');
"""
NEW_TOAST = OLD_TOAST + """            // b432: безымянный победитель узнаёт, как попасть в топ сайта
            if (!realName) setTimeout(() => { try { showToast('🖊 Введите имя игрока — и ваши срывы джекпота попадут в топ сайта', 'info'); } catch (e) {} }, 1200);
"""

OLD_RENDER = """            // b418: зал славы читаем через tombstone hallCut (после сброса топ пуст)
            const hall = jpHallFiltered(jackpot.hall, jackpot.hallCut);
            const top = hall[0];
"""
NEW_RENDER = """            // b418: зал славы читаем через tombstone hallCut (после сброса топ пуст)
            // b432: топ и «последний срыв» — только игроки С ИМЕНЕМ
            const hall = jpHallFiltered(jackpot.hall, jackpot.hallCut).filter(jpHallNamed);
            const top = hall[0];
"""

OLD_EMPTY = """                : '<li class="jp-empty">Джекпот ещё не срывали — станьте первым в топе!</li>';
"""
NEW_EMPTY = """                : (jackpot.hall || []).length
                    ? '<li class="jp-empty">Все срывы пока без имени — введите имя, чтобы попасть в топ</li>'
                    : '<li class="jp-empty">Джекпот ещё не срывали — станьте первым в топе!</li>'; // b432
"""

OLD_SEEN = """                    const top = (jackpot.hall || [])[0];
                    const seen = parseInt(LS.getItem('nexus_jp_seen') || '0', 10) || 0;"""
NEW_SEEN = """                    const top = (jackpot.hall || []).filter(jpHallNamed)[0]; // b432: анонс только именным
                    const seen = parseInt(LS.getItem('nexus_jp_seen') || '0', 10) || 0;"""

JS_PATCHES = [
    ('jpHallNamed', OLD_HELPER, NEW_HELPER),
    ('анонс чужой победы только именной', OLD_SEEN, NEW_SEEN),
    ('флаг nm в записи зала', OLD_WIN, NEW_WIN),
    ('подсказка безымянному победителю', OLD_TOAST, NEW_TOAST),
    ('топ только с именами', OLD_RENDER, NEW_RENDER),
    ('плашка «все без имени»', OLD_EMPTY, NEW_EMPTY),
]

HTML_PATCHES = []


# --------------------------------------------------------------------------- #
def patch_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise AssertionError('якорь «%s» встретился %d раз (нужно 1)' % (label, n))
    return text.replace(old, new, 1)


def main():
    check = '--check' in sys.argv
    js = os.path.join(ROOT, 'assets', 'app.js')

    if check:
        bad = 0
        s = open(js, encoding='utf-8').read()
        for label, old, _n in JS_PATCHES:
            n = s.count(old); bad += (n != 1); print('  %s %-36s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        return 1 if bad else 0

    s = open(js, encoding='utf-8').read()
    for label, old, new in JS_PATCHES:
        s = patch_once(s, old, new, label); print('  · %-36s ok' % label)
    open(js, 'w', encoding='utf-8', newline='').write(s)

    html = os.path.join(ROOT, 'index.html')
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
