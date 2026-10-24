#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b487: мобильная красота панели тамагочи (владелец: «на мобильных выглядит некрасиво»).

Заявка владельца (скриншот панели на телефоне): кнопки действий стояли
«лесенкой» (flex-wrap: 2+2+1 разной ширины), а питомец с именем занимал
пол-экрана по центру, отъедая место у характеристик.

Лечение
-------
1. Кнопки действий — ровная сетка .tama-actions (assets/app.css): 2 колонки на
   телефоне, причём пятая кнопка («Лечить») растягивается на всю строку
   (grid-column:1/-1 до 640px) — никаких лесенок и огрызков; 3 колонки от sm;
   5 колонок от lg (одна строка, как задумывалось). Все кнопки одинаковой
   ширины и высоты в своих ячейках.
2. Шапка питомца на мобильном — компактной строкой: морда со сценой слева,
   имя/уровень/опыт справа (flex items-center gap-3), с lg — как раньше
   столбиком (lg:block). Подпись обёрнута в min-w-0, у полоски опыта убран
   mx-auto (в строке центрировать нечего).
3. Итог: панель на телефоне стала короче примерно на треть, кнопки читаются
   витриной 2×2+1, питомец не доминирует.

Менялись assets/app.css и assets/app.js — тег сборки nxmob230 -> nxmob231.

Проверка/применение:
    python3 tools/_b487_patch.py --check
    python3 tools/_b487_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob230'
TAG_NEW = 'nxmob231'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('assets/app.css', 1,
              r'''.tama-btn:active{transform:scale(.94)}''',
              r'''.tama-btn:active{transform:scale(.94)}

/* b487: ровная сетка кнопок действий тамагочи: 2 колонки на телефоне (пятая
   кнопка тянется на всю строку — никакой лесенки из flex-wrap), 3 от sm,
   5 от lg. Ячейки одинаковой ширины, кнопки в них растягиваются. */
.tama-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
@media (min-width:640px){.tama-actions{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (min-width:1024px){.tama-actions{grid-template-columns:repeat(5,minmax(0,1fr))}}
@media (max-width:639px){.tama-actions > :last-child{grid-column:1/-1}}'''))

PAIRS.append(('assets/app.js', 1,
              r'''                <div class="text-center lg:text-left shrink-0">''',
              r'''                <div class="flex items-center gap-3 shrink-0 lg:block"><!-- b487: на телефоне питомец рядом с подписью, а не во всю ширину -->'''))

PAIRS.append(('assets/app.js', 1,
              r'''                    <p class="mt-2 text-sm font-black text-white">${t.name || 'Тоша'}${t.sick ? ' <span class="text-rose-300">· болен</span>' : ''}</p>
                    <p class="text-[10px] text-slate-400">уровень <b class="text-violet-300">${t.level}</b> · рост ${Math.round(t.xp || 0)}/${need}</p>
                    <div class="mt-1 h-2 w-32 mx-auto lg:mx-0 rounded-full bg-slate-800 overflow-hidden"><div class="tama-xp-fill h-full bg-violet-500 rounded-full" style="width:${Math.min(100, Math.round((t.xp || 0) / need * 100))}%"></div></div>''',
              r'''                    <div class="min-w-0"><!-- b487: подпись сбоку от морды на мобильном -->
                        <p class="text-sm font-black text-white">${t.name || 'Тоша'}${t.sick ? ' <span class="text-rose-300">· болен</span>' : ''}</p>
                        <p class="text-[10px] text-slate-400">уровень <b class="text-violet-300">${t.level}</b> · рост ${Math.round(t.xp || 0)}/${need}</p>
                        <div class="mt-1 h-2 w-32 rounded-full bg-slate-800 overflow-hidden"><div class="tama-xp-fill h-full bg-violet-500 rounded-full" style="width:${Math.min(100, Math.round((t.xp || 0) / need * 100))}%"></div></div>
                    </div>'''))

PAIRS.append(('assets/app.js', 1,
              r'''                    <div class="flex flex-wrap gap-2 pt-1">${btns}</div>''',
              r'''                    <div class="tama-actions pt-1">${btns}</div><!-- b487: ровная сетка кнопок вместо лесенки flex-wrap -->'''))


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
        print('b487: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b487: мобильная раскладка тамагочи — ровная сетка кнопок и компактная шапка; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
