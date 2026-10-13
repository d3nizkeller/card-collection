#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b422 — общий банк реально общий и обновляется в реальном времени.

Жалоба владельца: «у пользователей чегото разные даные джекпода а долженбыть
обший и должео обновлятся вряльном времини» + два скриншота: 38q и 24q.

Две причины:

1. РАСХОЖДЕНИЕ ДОКУМЕНТОВ. После переезда на v3 (b421) вкладки на сборках
   ≤ nxmob82 продолжают синхронизироваться через v2 — со своим банком.
   38q (v3) и 24q (v2) — это два разных документа, а не «глюк»: пока вкладка
   не перезагрузится, она живёт в старой вселенной. Кодом это лечится только
   одним способом: старая вкладка должна узнать, что она старая. Теперь игра
   раз в 3 минуты сверяет тег сборки с сервером и, если он новее своего,
   показывает неснимаемый тост «Версия игры обновилась… Обновите», — открытый
   таб переезжает на v3 за минуты, а не когда вспомнит пользователь.
2. НЕ РЕАЛЬНОЕ ВРЕМЯ. Фоновая синхронизация шла раз в 60 секунд
   (setInterval jpSyncNow, b404) плюс по событиям: чужой срыв банка доходил
   до_IDLE_ вкладки с задержкой до минуты. Теперь каждые 15 секунд идёт
   лёгкий pull (jpPullLight: fetch → merge → push только если мы впереди),
   а полный цикл остаётся для событий. Документ после b420/b421 лёгкий
   (~60 КБ), так что 15-секундный ритм бесплатен.

Запуск:  python3 tools/_b422_patch.py            — применить
         python3 tools/_b422_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob83'
NEW_V = 'nxmob84'

# --------------------------------------------------------------------------- #
# app.js
# --------------------------------------------------------------------------- #

OLD_INTERVAL = "                jpSyncNow(); setInterval(() => { if (!document.hidden) jpSyncNow(); }, 60000); // b404: в фоне сеть не дёргаем\n"
NEW_INTERVAL = ("                jpSyncNow(); setInterval(() => { if (!document.hidden) jpPullLight(); }, 15000); // b422: реальное время — лёгкий pull каждые 15 с (в фоне сеть не дёргаем)\n"
                "                setInterval(() => { try { if (!document.hidden) nxVersionNudge(); } catch (e) {} }, 180000); // b422: старая вкладка узнаёт, что она старая\n")

OLD_SOON = "        function jpSyncSoon() { clearTimeout(jpT); jpT = setTimeout(jpSyncNow, 2500); }\n"
NEW_SOON = """        function jpSyncSoon() { clearTimeout(jpT); jpT = setTimeout(jpSyncNow, 2500); }
        // b422: реальное время. Лёгкий pull раз в 15 секунд: fetch → merge всех
        // четырёх разделов → push ТОЛЬКО если наш реестр впереди облака. Полный
        // цикл jpSyncNow (с повторным чтением после записи) остаётся для событий.
        function jpPullLight() {
            if (jpBusy) return;
            jpBusy = true; window.__nxJpAt = Date.now(); // b404: отметка для watchdog
            jpFetch().then(remote => {
                const rj = remote && remote.jp ? remote.jp : remote;
                jackpotMerge(rj);
                jpcMerge(remote && remote.jpc); // b414
                marketMerge(remote && remote.mk); // b136
                siteStatsMerge(remote && remote.st); // b277
                try { jpcApplyGrants(); } catch (e) {} // b414
                if (jpAheadOf(rj)) { jpBusy = false; jpSyncNow(); return; } // мы впереди — догоняющий пуш
                try { marketCreditLedger(); } catch (e) {}
                try { statsRenderIfVisible(); } catch (e) {}
                try { renderMarketIfVisible(); } catch (e) {}
            }).catch(() => { /* офлайн — дождёмся следующего тика */ })
              .then(() => { jpBusy = false; jpLastAt = Date.now(); });
        }
        // b422: открытый таб на старой сборке после b421 синхронизируется через
        // брошенный документ v2 и видит СВОЙ банк (те самые «38q против 24q»).
        // Сверяем тег сборки с сервером и просим обновить вкладку: только так
        // старая вселенная схлопывается в общую.
        function nxOwnTag() {
            try {
                const list = document.scripts || [];
                for (let i = 0; i < list.length; i++) {
                    const src = String(list[i].src || '');
                    if (src.indexOf('assets/app.js') < 0) continue;
                    const m = src.match(/v=(nxmob\\d+)/);
                    if (m) return m[1];
                }
            } catch (e) {}
            return '';
        }
        function nxVersionNudge() {
            try {
                const own = nxOwnTag();
                if (!own || document.getElementById('nx-ver-toast')) return;
                fetch('index.html?nc=' + Date.now(), { cache: 'no-store' }).then(r => (r && r.ok) ? r.text() : '').then(t => {
                    const m = String(t || '').match(/assets\\/app\\.js\\?v=(nxmob\\d+)/);
                    if (!m || m[1] === own) return;
                    if (document.getElementById('nx-ver-toast')) return;
                    const c = document.getElementById('toast-container');
                    if (!c) return;
                    positionToastContainer();
                    const el = document.createElement('div');
                    el.id = 'nx-ver-toast';
                    el.className = 'pointer-events-auto w-full px-3.5 py-3 flex items-center gap-2.5 rounded-xl border border-amber-500/40 bg-amber-950/95 text-amber-100 text-[11px] font-bold leading-snug shadow-lg';
                    el.innerHTML = '<i class="fa-solid fa-rotate text-amber-300"></i><span>Версия игры обновилась (' + m[1] + '). Эта вкладка синхронизируется по старому документу и видит свой банк — обновите, чтобы играть со всеми.</span>' +
                        '<button type="button" onclick="location.reload()" class="px-2.5 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-[11px] font-black shrink-0 transition">Обновить</button>';
                    c.appendChild(el);
                }).catch(() => {});
            } catch (e) {}
        }
"""

JS_PATCHES = [
    ('jpPullLight + nxVersionNudge', OLD_SOON, NEW_SOON),
    ('ритм синхронизации 15 с', OLD_INTERVAL, NEW_INTERVAL),
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
    html = os.path.join(ROOT, 'index.html')

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
