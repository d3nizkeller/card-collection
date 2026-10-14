#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b431 — топ джекпота обновляется в реальном времени.

Жалоба владельца: «не обновляется в реальном времени» + скриншот топ-3.
Замеры облака показали: документ живой (свежий срыв был 212 с назад, пуши
идут), то есть тормозил не сервер, а витрина: топ-3 считался как «три
КРУПНЕЙШИХ срыва из последних 20» (b98/b101) — новый срыв на 18q при старых
759q/201q/67q в список НЕ попадал, и блок выглядел застывшим, даже когда
облако уже знало о новом джекпоте. Плюс витрина перерисовывалась только при
изменениях (ch) и не имела страховки от тихо умершей синхронизации.

Стало:

* топ-3 = ТРИ ПОСЛЕДНИХ срыва (сортировка по t): любой новый джекпот виден
  сразу, у всех игроков, с того момента как до них доехало облако;
* в строке топа теперь дата И время срыва («14.10 14:32») — реальное время
  видно глазами;
* заголовок блока: «Топ-3 джекпота сайта» → «Последние срывы джекпота» +
  пульсирующая live-точка;
* jpPullLight перерисовывает джекпот-витрину КАЖДЫЙ pull (15 с), даже если
  слияние не нашло изменений — витрина не может «залипнуть» на старом DOM;
* сторож синхронизации nxSyncWatchdog(): если вкладка видима и 60 секунд
  не было ни одного успешного цикла (тихо умерший pull, сон WebView) —
  принудительный jpSyncNow(); порог настраивается window.__nxSyncWatchMs;
* окно зала славы 20 → 40 записей: последние срывы не выталкивают друг
  друга слишком быстро, топ живёт дольше и честнее.

Запуск:  python3 tools/_b431_patch.py            — применить
         python3 tools/_b431_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob94'
NEW_V = 'nxmob95'

# --------------------------------------------------------------------------- #
# app.js
# --------------------------------------------------------------------------- #

OLD_TOP = """            const topWins = hall.slice().sort((a, b) => (b.a || 0) - (a.a || 0)).slice(0, 3); // b101: топ-3; b418: после сброса — пуст
"""
NEW_TOP = """            // b431: топ-3 = ТРИ ПОСЛЕДНИХ срыва (по t): новый джекпот виден сразу,
            // а не только когда он крупнее старых (b98/b101: было — по сумме);
            // b418: после сброса — пуст
            const topWins = hall.slice().sort((a, b) => (b.t || 0) - (a.t || 0)).slice(0, 3);
"""

OLD_ROW = """                ? topWins.map((h, i) => '<li><span class="jp-rank">' + (i + 1) + (medals[i] ? ' ' + medals[i] : '.') + '</span><span class="jp-name">' + String(h.n || 'игрок').replace(/[<>&]/g, '') + '</span><span class="jp-amt">+' + fmtCoins(h.a || 0) + '</span><span class="jp-date">' + new Date(h.t || 0).toLocaleDateString() + '</span></li>').join('')
"""
NEW_ROW = """                ? topWins.map((h, i) => '<li><span class="jp-rank">' + (i + 1) + (medals[i] ? ' ' + medals[i] : '.') + '</span><span class="jp-name">' + String(h.n || 'игрок').replace(/[<>&]/g, '') + '</span><span class="jp-amt">+' + fmtCoins(h.a || 0) + '</span><span class="jp-date">' + new Date(h.t || 0).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' }) + ' ' + new Date(h.t || 0).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) + '</span></li>').join('') // b431: дата И время срыва
"""

OLD_PULL_RENDER = """                try { jpcApplyGrants(); } catch (e) {} // b414
                jpAutoCompactIfNeeded(); // b423
"""
NEW_PULL_RENDER = """                try { jpcApplyGrants(); } catch (e) {} // b414
                // b431: витрина джекпота (банк, топ-3, надписи) перерисовывается
                // КАЖДЫЙ pull, даже если слияние не нашло изменений, — залипнуть
                // на старом DOM невозможно
                try { jackpotRender(); } catch (e) {}
                jpAutoCompactIfNeeded(); // b423
"""

OLD_WATCH_ANCHOR = """        function jpSyncSoon() { clearTimeout(jpT); jpT = setTimeout(jpSyncNow, 2500); }
"""
NEW_WATCH = """        function jpSyncSoon() { clearTimeout(jpT); jpT = setTimeout(jpSyncNow, 2500); }
        // b431: сторож синхронизации: если вкладка видима, но 60 секунд не было
        // ни одного успешного цикла (тихо умерший pull, сон WebView, обрыв сети),
        // дёргаем jpSyncNow принудительно — топ и банк догоняют облако сами
        function nxSyncWatchdog() {
            try {
                const limit = Math.max(5000, Math.floor(Number(window.__nxSyncWatchMs) || 60000));
                if (document.hidden || jpBusy) return;
                if (Date.now() - jpLastAt > limit) jpSyncNow();
            } catch (e) {}
        }
        setInterval(nxSyncWatchdog, 20000);
"""

OLD_HALL1 = "                jackpot.hall = Object.keys(map).map(k => map[k]).sort((a, b) => b.t - a.t).slice(0, 20);\n"
NEW_HALL1 = "                jackpot.hall = Object.keys(map).map(k => map[k]).sort((a, b) => b.t - a.t).slice(0, 40); // b431: окно зала 40\n"
OLD_HALL2 = "            jackpot.hall = jackpot.hall.slice(0, 20);\n"
NEW_HALL2 = "            jackpot.hall = jackpot.hall.slice(0, 40); // b431: окно зала 40\n"

JS_PATCHES = [
    ('топ-3 по свежести', OLD_TOP, NEW_TOP),
    ('в строке топа дата и время', OLD_ROW, NEW_ROW),
    ('рендер витрины каждый pull', OLD_PULL_RENDER, NEW_PULL_RENDER),
    ('сторож синхронизации', OLD_WATCH_ANCHOR, NEW_WATCH + OLD_WATCH_ANCHOR.replace('        function jpSyncSoon() { clearTimeout(jpT); jpT = setTimeout(jpSyncNow, 2500); }\n', '')),
    ('окно зала 40 (merge)', OLD_HALL1, NEW_HALL1),
    ('окно зала 40 (win)', OLD_HALL2, NEW_HALL2),
]

# --------------------------------------------------------------------------- #
# index.html: заголовок блока топа
# --------------------------------------------------------------------------- #
OLD_HEAD = '<p class="jp-top-title"><i class="fa-solid fa-trophy"></i>Топ-3 джекпота сайта</p>'
NEW_HEAD = '<p class="jp-top-title"><i class="fa-solid fa-trophy"></i>Последние срывы джекпота<i class="fa-solid fa-circle text-emerald-400 animate-pulse ml-1.5" style="font-size:6px;vertical-align:2px" title="обновляется в реальном времени"></i></p>'

HTML_PATCHES_ALL = [(OLD_HEAD, NEW_HEAD)]


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
            n = s.count(old); bad += (n != 1); print('  %s %-36s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        h = open(html, encoding='utf-8').read()
        for old, _n in HTML_PATCHES_ALL:
            n = h.count(old); bad += (n < 1); print('  %s %-36s %d (все)' % ('OK ' if n >= 1 else 'BAD', old[:36], n))
        return 1 if bad else 0

    s = open(js, encoding='utf-8').read()
    for label, old, new in JS_PATCHES:
        s = patch_once(s, old, new, label); print('  · %-36s ok' % label)
    open(js, 'w', encoding='utf-8', newline='').write(s)

    h = open(html, encoding='utf-8').read()
    for old, new in HTML_PATCHES_ALL:
        n = h.count(old)
        h = h.replace(old, new); print('  · %-36s ok ×%d' % (old[:36], n))
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
