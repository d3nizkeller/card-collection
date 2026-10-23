#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b480: убрать пустую ячейку в сетке «Композиция и эффект карты».

Заявка владельца (со скриншотом формы, дырка обведена красным): «не должно быть
пустое место».

Разбор
------
Селектов композиции стало девять: имя, описание, статы-место (b475),
статы-расположение и статы-форма (b477), статы-размер (b478), выравнивание,
эффект и аура. Двухколоночная сетка grid grid-cols-2 с девятью ячейками
оставляет десятую пустой — рядом с «Аура за картой» (скриншот владельца).

Лечение
-------
«Аура за картой» растягивается на всю строку сетки: style="grid-column:1 / -1"
(инлайн, потому что утилиты col-span-2 нет в прекомпилированном
assets/tailwind.css — прецедент b376). Девять ячеек = четыре полных строки +
одна во всю ширину: дырки нет, а длинному списку аур полная ширина даже
удобнее. Порядок селекторов не менялся.

Менялся только index.html — тег сборки nxmob223 -> nxmob224.

Проверка/применение:
    python3 tools/_b480_patch.py --check
    python3 tools/_b480_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob223'
TAG_NEW = 'nxmob224'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('index.html', 1,
              r'''                                <div>
                                    <span class="block text-[10px] text-slate-500 mb-1"><i class="fa-solid fa-feather-pointed text-amber-300 mr-1"></i>Аура за картой</span>''',
              r'''                                <!-- b480: аура занимает всю строку сетки композиции:
                                     селекторов стало девять (b475–b478), и десятая ячейка
                                     оставалась пустой дырой рядом с аурой (скриншот владельца).
                                     Инлайн-стиль, потому что col-span-2 нет в прекомпилированном
                                     tailwind.css; длинному списку аур полная ширина удобнее. -->
                                <div style="grid-column:1 / -1">
                                    <span class="block text-[10px] text-slate-500 mb-1"><i class="fa-solid fa-feather-pointed text-amber-300 mr-1"></i>Аура за картой</span>'''))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8', newline='') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, cnt, old, new in PAIRS:
        txt = files.get(rel) or read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        if n in txt:
            problems.append('%s: правка уже применена: %s...' % (rel, o[:60]))
            continue
        if txt.count(o) != cnt:
            problems.append('%s: якорь встретился %d раз вместо %d: %s...' % (rel, txt.count(o), cnt, o[:60]))
            continue
        files[rel] = txt.replace(o, n, 1)
    for rel in TAG_FILES:
        txt = files.get(rel) or read(rel)
        if TAG_NEW in txt:
            problems.append('%s: тег уже %s' % (rel, TAG_NEW))
            continue
        if TAG_OLD not in txt:
            problems.append('%s: нет тега %s' % (rel, TAG_OLD))
            continue
        files[rel] = txt.replace(TAG_OLD, TAG_NEW)
    if problems:
        for p in problems:
            print('ПРОБЛЕМА:', p)
        return 1
    if '--check' in sys.argv:
        print('b480: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b480: аура на всю строку — пустой ячейки в композиции нет; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
