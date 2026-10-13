#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b425 — значки альбомов: ПЕРЕД «Достижениями» и красивая сетка на мобильных.

Просьба владельца (скриншот десктопа: редкий ряд кружков слева и пустое поле
справа): «…перед достижениями сделай, чтоб смотрелось красиво на мобильных
устройствах».

Стало:

* карточка «Значки альбомов» переехала НАД блоком «Достижения» — ачивки за
  альбомы теперь первое, что видишь в наградах после заданий дня;
* контейнер — адаптивная сетка вместо flex-ряда: 3 колонки на телефоне,
  4 на планшете, 6–8 на десктопе, `justify-items-center` — кружки ровно
  заполняют ширину карточки без пустого поля справа;
* кружки крупнее на широких экранах (w-20 h-20 → sm:w-24 sm:h-24), ячейка
  тянется на всю колонку (w-full min-w-0), названия центрированы;
* логика значков (обложка, янтарное кольцо, галочка, grayscale, дробь)
  не изменилась.

Запуск:  python3 tools/_b425_patch.py            — применить
         python3 tools/_b425_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob86'
NEW_V = 'nxmob87'

OLD_BLOCK = """            <!-- b424: круглые значки за собранные альбомы — с обложками -->
            <div class="bg-slate-900/80 p-4 sm:p-6 rounded-2xl border border-slate-800 space-y-4">
                <div class="flex flex-wrap justify-between items-center gap-2">
                    <h3 class="text-lg font-bold text-white flex items-center space-x-2">
                        <i class="fa-solid fa-medal text-amber-400"></i>
                        <span>Значки альбомов</span>
                    </h3>
                    <span class="text-xs text-slate-400" id="album-badges-counter"></span>
                </div>
                <p class="text-[11px] text-slate-500 leading-snug">Круглый значок с обложкой загорается янтарём, когда альбом собран полностью: обложка, кольцо и галочка. Несобранные альбомы — серые, с прогрессом «собрано/всего» прямо на обложке.</p>
                <div id="rewards-album-badges" class="flex flex-wrap gap-3 sm:gap-4"></div>
            </div>
"""

NEW_BLOCK = """            <!-- b424/b425: круглые значки за собранные альбомы — с обложками;
                 b425: стоят ПЕРЕД «Достижениями» и свёрстаны адаптивной сеткой -->
            <div class="bg-slate-900/80 p-4 sm:p-6 rounded-2xl border border-slate-800 space-y-4">
                <div class="flex flex-wrap justify-between items-center gap-2">
                    <h3 class="text-lg font-bold text-white flex items-center space-x-2">
                        <i class="fa-solid fa-medal text-amber-400"></i>
                        <span>Значки альбомов</span>
                    </h3>
                    <span class="text-xs text-slate-400" id="album-badges-counter"></span>
                </div>
                <p class="text-[11px] text-slate-500 leading-snug">Круглый значок с обложкой загорается янтарём, когда альбом собран полностью. Несобранные — серые, с прогрессом на обложке.</p>
                <div id="rewards-album-badges" class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3 sm:gap-5 justify-items-center"></div>
            </div>

"""

OLD_ACH_COMMENT = "            <!-- Achievements -->\n"
NEW_ACH_COMMENT = NEW_BLOCK + "            <!-- Achievements -->\n"

OLD_ITEM = """                return '<div class="flex flex-col items-center gap-1.5" style="width:5.5rem">' +
                    '<div class="relative w-20 h-20 rounded-full overflow-hidden border-2 shrink-0 ' +
"""
NEW_ITEM = """                return '<div class="w-full min-w-0 flex flex-col items-center gap-1.5">' + // b425: ячейка сетки на всю колонку
                    '<div class="relative w-20 h-20 sm:w-24 sm:h-24 rounded-full overflow-hidden border-2 shrink-0 ' + // b425: крупнее на широких экранах
"""

JS_PATCHES = [
    ('ячейка значка под сетку', OLD_ITEM, NEW_ITEM),
]

HTML_PATCHES = [
    ('убрать старый блок значков', OLD_BLOCK, ''),
    ('вставить значки перед достижениями', OLD_ACH_COMMENT, NEW_ACH_COMMENT),
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
            n = s.count(old); bad += (n != 1); print('  %s %-36s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        h = open(html, encoding='utf-8').read()
        for label, old, _n in HTML_PATCHES:
            n = h.count(old); bad += (n != 1); print('  %s %-36s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        return 1 if bad else 0

    s = open(js, encoding='utf-8').read()
    for label, old, new in JS_PATCHES:
        s = patch_once(s, old, new, label); print('  · %-36s ok' % label)
    open(js, 'w', encoding='utf-8', newline='').write(s)

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
