#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b434 — игры больше не зависают при переключении вкладок.

Жалоба владельца: «игры зависают если переключаешь вкладки».

Диагноз: nx3dReleaseHidden() при уходе с экрана (переключение игровой
вкладки/режима, уход из «Игр») гасит rAF-цикл и СБРАСЫВАЕТ WebGL-контекст.
Если в этот момент шёл спин, цикл не доходил до финиша:
`slots.spinning` / `lines.spinning` оставались true НАВСЕГДА, кнопка
«Крутить» — disabled (renderSlotsUI: spin.disabled = slots.spinning),
игра выглядела мёртвой. То же для Линий: `lines3d.pending` обнулялся
вместе с контекстом, и linesFinish не вызывался никогда. Колесо и Сетка
доезжают на setTimeout-цепочках, но WebView/потеря контекста могли
оставить и их.

Стало:

* nxForceFinishSpins() — перед любым сбросом контекста висящий спин
  дочитывается тем же финишем, который вызвал бы цикл:
  slots → slotsFinish(lastResult, bet), lines → linesFinish(pending),
  grid → gridEnd(); выплата/статистика/джекпот начисляются как обычно;
* метки времени спина (slots.spinAt / grid.spinAt / lines.spinAt) и
  watchdog nxSpinWatchdog() каждые 5 с: спин дольше своего нормального
  времени (12 с Слоты/Линии, 25 с Сетка) дочитывается принудительно —
  страховка от потери контекста, сна WebView и любых будущих путей,
  где цикл мог умереть тихо;
* Колесо не трогаем: оно всегда доезжает setTimeout-ом (b310, 2D).

Запуск:  python3 tools/_b434_patch.py            — применить
         python3 tools/_b434_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob97'
NEW_V = 'nxmob98'

OLD_RELEASE = """        function nx3dReleaseHidden(m) {
            // скрытая игра не держит WebGL-контекст: мобильный Chrome держит ~8-16
"""
NEW_RELEASE = """        // b434: переключение вкладок больше не замораживает игры: висящий спин
        // дочитывается тем же финишем, который вызвал бы убитый цикл
        function nxForceFinishSpins() {
            try { if (slots.spinning) { slots.spinning = false; slotsFinish(slots.lastResult, slots.bet); } } catch (e) {}
            try { if (lines.spinning) { const p = lines3d.pending; lines3d.pending = null; linesFinish(p ? p.final : lines.cells.slice(), p ? p.bet : lines.bet); } } catch (e) {}
            try { if (grid.spinning) gridEnd(); } catch (e) {}
        }
        // b434: сторож «висящих» спинов: потеря контекста, сон WebView, тихая
        // смерть цикла — спин дольше нормального времени дочитывается сам
        function nxSpinWatchdog() {
            try {
                const now = Date.now();
                if (slots.spinning && now - (slots.spinAt || now) > 12000) { slots.spinning = false; slotsFinish(slots.lastResult, slots.bet); }
                if (lines.spinning && now - (lines.spinAt || now) > 12000) { const p = lines3d.pending; lines3d.pending = null; linesFinish(p ? p.final : lines.cells.slice(), p ? p.bet : lines.bet); }
                if (grid.spinning && now - (grid.spinAt || now) > 25000) gridEnd();
            } catch (e) {}
        }
        setInterval(nxSpinWatchdog, 5000);
        function nx3dReleaseHidden(m) {
            nxForceFinishSpins(); // b434: сначала дочитать спины, потом гасить контексты
            // скрытая игра не держит WebGL-контекст: мобильный Chrome держит ~8-16
"""

OLD_SLOTS_SPIN = """            slots.spinning = true;
            slots.reels.forEach((grp, i) => {
"""
NEW_SLOTS_SPIN = """            slots.spinning = true;
            slots.spinAt = Date.now(); // b434: метка для сторожа висящих спинов
            slots.reels.forEach((grp, i) => {
"""

OLD_GRID_SPIN = "            grid.spinning = true; grid.chain = 0; grid.total = 0; grid.jpPaid = 0; grid.lastBet = bet; // b57 / b183\n"
NEW_GRID_SPIN = "            grid.spinning = true; grid.chain = 0; grid.total = 0; grid.jpPaid = 0; grid.lastBet = bet; grid.spinAt = Date.now(); // b57 / b183 / b434\n"

OLD_LINES_SPIN = """            lines.spinning = true;
"""
NEW_LINES_SPIN = """            lines.spinning = true;
            lines.spinAt = Date.now(); // b434: метка для сторожа висящих спинов
"""

JS_PATCHES = [
    ('принудительный финиш + сторож', OLD_RELEASE, NEW_RELEASE),
    ('метка спина слотов', OLD_SLOTS_SPIN, NEW_SLOTS_SPIN),
    ('метка спина сетки', OLD_GRID_SPIN, NEW_GRID_SPIN),
    ('метка спина линий', OLD_LINES_SPIN, NEW_LINES_SPIN),
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
