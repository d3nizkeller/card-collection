#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b428 — просмотр карточек альбома под телефоны: весь просмотр на одном экране.

Просьба владельца: «просмотр карточек в альбоме нужно адаптировать под
телефоны». Замеры на 390×844: карта в просмотре (max-w-sm = 384 px при
пропорции 9/16) имеет высоту ~683 px, поэтому кнопки под картой (музыка,
промотка, «Подключить к Слотам», «Отправить на продажу») уезжали за пределы
экрана — приходилось скроллить модалку, а стрелки ← → лежали поверх арта.

Стало (только на <sm, десктоп не меняется):

* #inspect-float получает max-width: min(24rem, 58vh * 9/16) — карта ужимается
  по высоте экрана, и карта, и счётчик, и все кнопки видны без скролла;
  по бокам освобождается место, и стрелки листания больше не перекрывают арт;
* стрелки на телефоне компактнее (w-9 h-9, left-1/right-1), на десктопе прежние;
* подсказка под кнопками на телефоне говорит про свайп и касание, а не про
  стрелки клавиатуры и Esc.

Запуск:  python3 tools/_b428_patch.py            — применить
         python3 tools/_b428_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob91'
NEW_V = 'nxmob92'

# --------------------------------------------------------------------------- #
# index.html
# --------------------------------------------------------------------------- #

OLD_ARROWS = """        <button id="inspect-prev" onclick="inspectStep(-1)" title="Предыдущая (←)" style="display:none;" class="hidden fixed left-2 sm:left-6 top-1/2 -translate-y-1/2 z-10 w-11 h-11 rounded-full bg-slate-900/85 border border-slate-700 hover:border-violet-400 hover:text-violet-300 text-slate-200 flex items-center justify-center transition shadow-xl"><i class="fa-solid fa-chevron-left"></i></button>
        <button id="inspect-next" onclick="inspectStep(1)" title="Следующая (→)" style="display:none;" class="hidden fixed right-2 sm:right-6 top-1/2 -translate-y-1/2 z-10 w-11 h-11 rounded-full bg-slate-900/85 border border-slate-700 hover:border-violet-400 hover:text-violet-300 text-slate-200 flex items-center justify-center transition shadow-xl"><i class="fa-solid fa-chevron-right"></i></button>
"""

NEW_ARROWS = """        <button id="inspect-prev" onclick="inspectStep(-1)" title="Предыдущая (←)" style="display:none;" class="hidden fixed left-1 sm:left-6 top-1/2 -translate-y-1/2 z-10 w-9 h-9 sm:w-11 sm:h-11 rounded-full bg-slate-900/85 border border-slate-700 hover:border-violet-400 hover:text-violet-300 text-slate-200 flex items-center justify-center transition shadow-xl"><i class="fa-solid fa-chevron-left text-sm sm:text-base"></i></button>
        <button id="inspect-next" onclick="inspectStep(1)" title="Следующая (→)" style="display:none;" class="hidden fixed right-1 sm:right-6 top-1/2 -translate-y-1/2 z-10 w-9 h-9 sm:w-11 sm:h-11 rounded-full bg-slate-900/85 border border-slate-700 hover:border-violet-400 hover:text-violet-300 text-slate-200 flex items-center justify-center transition shadow-xl"><i class="fa-solid fa-chevron-right text-sm sm:text-base"></i></button>
"""

OLD_HINT = """            <p class="mt-1 text-[10px] text-slate-600 text-center">Листайте стрелками ← → или свайпом, Esc — закрыть</p>
"""
NEW_HINT = """            <p class="mt-1 text-[10px] text-slate-600 text-center"><span class="sm:hidden">Свайп влево/вправо — листать, ✕ — закрыть</span><span class="hidden sm:inline">Листайте стрелками ← → или свайпом, Esc — закрыть</span></p>
"""

OLD_STYLE_ANCHOR = """    <!-- b217: уведомления в стиле Liquid Glass -->
    <style>
"""
NEW_STYLE = """    <!-- b217: уведомления в стиле Liquid Glass -->
    <style>
    /* b428: просмотр карты на телефоне — целиком на одном экране: карта
       ужимается по высоте (58vh при пропорции 9/16), кнопки и стрелки
       остаются видимыми без скролла модалки */
    @media (max-width:640px){
        #inspect-float{ max-width: min(24rem, calc(58vh * 0.5625)); margin: 0 auto; }
    }
"""

HTML_PATCHES = [
    ('компактные стрелки на телефоне', OLD_ARROWS, NEW_ARROWS),
    ('подсказка про свайп на телефоне', OLD_HINT, NEW_HINT),
    ('media-query высоты карты', OLD_STYLE_ANCHOR, NEW_STYLE),
]

JS_PATCHES = []


# --------------------------------------------------------------------------- #
def patch_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise AssertionError('якорь «%s» встретился %d раз (нужно 1)' % (label, n))
    return text.replace(old, new, 1)


def main():
    check = '--check' in sys.argv
    html = os.path.join(ROOT, 'index.html')

    if check:
        bad = 0
        h = open(html, encoding='utf-8').read()
        for label, old, _n in HTML_PATCHES:
            n = h.count(old); bad += (n != 1); print('  %s %-36s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        return 1 if bad else 0

    h = open(html, encoding='utf-8').read()
    for label, old, new in HTML_PATCHES:
        h = patch_once(h, old, new, label); print('  · %-36s ok' % label)
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
