#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b476: блок «Боевые статы» в форме карточки — во всю ширину, подсказка убрана.

Уточнение владельца к b475 (со скриншотом формы): «сделай во всю ширину и убери
подсказку».

Разбор
------
В b475 поля значений боевых статов (⚡ Атака / ❤ Здоровье) остались одной
ячейкой сетки «Композиция и эффект карты» (grid grid-cols-2) — то есть занимали
половину ширины формы, в то время как строки «Имя персонажа / Описание карты»
тянутся на всю ширину. Под блоком жила подсказка про «Скрыть» — владелец
попросил её убрать: смысл селекторов виден из их названий.

Лечение
-------
1. Блок значений статов ВЫНЕСЕН из сетки композиции и встал отдельной строкой
   левой колонки формы (space-y-3) — теперь оба поля тянутся на всю ширину, как
   строка имени/описания. Обёртка и id полей (card-atk/card-hp) не менялись:
   readCardLayoutForm/handleSaveCard/editCard и предпросмотр работают как прежде.
   Класс col-span-2 не используем: его нет в прекомпилированном tailwind.css, а
   перенос блока обходится без новых утилит вовсе.
2. Подсказка ««Скрыть» убирает блок с лица карты…» удалена вместе с комментарием.
3. Селекторы видимости b475 («Имя персонажа» → «Скрыть», «Боевые статы на карте»)
   не тронуты.

Менялся только index.html — тег сборки nxmob219 -> nxmob220.

Проверка/применение:
    python3 tools/_b476_patch.py --check
    python3 tools/_b476_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob219'
TAG_NEW = 'nxmob220'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('index.html', 1,
              '''                        <div>
                            <label class="block text-[11px] font-medium text-slate-400 mb-1">Боевые статы <span class="text-slate-600">(необязательно — иначе по редкости)</span></label>
                            <div class="grid grid-cols-2 gap-2">
                                <div class="relative">
                                    <span class="absolute left-3 top-1/2 -translate-y-1/2 text-amber-400 text-xs"><i class="fa-solid fa-bolt"></i></span>
                                    <input type="number" id="card-atk" min="1" max="30" oninput="renderCardPreviewSoon()" placeholder="Атака" class="w-full bg-slate-950 border border-slate-700 rounded-lg pl-8 pr-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">
                                </div>
                                <div class="relative">
                                    <span class="absolute left-3 top-1/2 -translate-y-1/2 text-rose-400 text-xs"><i class="fa-solid fa-heart"></i></span>
                                    <input type="number" id="card-hp" min="1" max="50" oninput="renderCardPreviewSoon()" placeholder="Здоровье" class="w-full bg-slate-950 border border-slate-700 rounded-lg pl-8 pr-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">
                                </div>
                            </div>
                        </div>
                            </div>
                            <!-- b475: что значит «Скрыть» у имени/описания/статов -->
                            <p class="text-[10px] text-slate-600 mt-2 leading-snug"><i class="fa-solid fa-eye-slash mr-1"></i>«Скрыть» убирает блок с лица карты: имени и/или чисел ⚔ ❤ не видно в просмотре карты, в сетке альбома и во вскрытии пака — остаётся только арт. Значения не удаляются: в бою, в «Строках» альбома и в списках Студии всё работает как раньше.</p>''',
              '''                            </div>
                        <!-- b476: значения боевых статов — отдельной строкой во всю
                             ширину формы (в b475 жили одной ячейкой сетки композиции).
                             Подсказка b475 под блоком убрана по просьбе владельца:
                             смысл селекторов виден из их названий. -->
                        <div>
                            <label class="block text-[11px] font-medium text-slate-400 mb-1">Боевые статы <span class="text-slate-600">(необязательно — иначе по редкости)</span></label>
                            <div class="grid grid-cols-2 gap-2">
                                <div class="relative">
                                    <span class="absolute left-3 top-1/2 -translate-y-1/2 text-amber-400 text-xs"><i class="fa-solid fa-bolt"></i></span>
                                    <input type="number" id="card-atk" min="1" max="30" oninput="renderCardPreviewSoon()" placeholder="Атака" class="w-full bg-slate-950 border border-slate-700 rounded-lg pl-8 pr-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">
                                </div>
                                <div class="relative">
                                    <span class="absolute left-3 top-1/2 -translate-y-1/2 text-rose-400 text-xs"><i class="fa-solid fa-heart"></i></span>
                                    <input type="number" id="card-hp" min="1" max="50" oninput="renderCardPreviewSoon()" placeholder="Здоровье" class="w-full bg-slate-950 border border-slate-700 rounded-lg pl-8 pr-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">
                                </div>
                            </div>
                        </div>'''))


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
        print('b476: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b476: статы во всю ширину, подсказка убрана; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
