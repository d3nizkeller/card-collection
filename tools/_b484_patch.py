#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b484: починить переключатель режимов «Игры» после добавления Тамагочи.

Жалоба владельца (скриншот): «что случилось с кнопками» — плитки режимов
встали столбиком во всю ширину, а активная «Тамагочи» потеряла подсветку и
фон, превратившись в голую надпись.

Разбор
------
Три ошибки b483, все из-за невнимательности к тому, что стили в проекте
прекомпилированы и перечисляют id кнопок явно:

1. Контейнер переключателей получил класс grid-cols-9, которого НЕТ в
   assets/tailwind.css (без брейкпоинта есть только до grid-cols-8; девятая
   колонка существует лишь как sm:grid-cols-9). Без grid-template-columns
   сетка выродилась в одну колонку — плитки растянулись полосами.
2. Для активной плитки каждого режима в <style> index.html живёт правило
   «#mode-…-btn.lq-on { --lq-tint … }» (цвет стекла подсветки). Для
   #mode-tama-btn.lq-on правила не было — переменная оставалась пустой.
3. Базовое «стекло» плиток (b232) настроено правилами со СПИСКАМИ id
   (база, ::before, :hover, :active) — #mode-tama-btn не был в этих списках,
   поэтому плитка оставалась без фонового стекла даже неактивной.

Лечение
-------
1. Контейнер: grid-cols-5 sm:grid-cols-9 — на телефоне плитки ложатся в два
   ряда (5+4), от sm и выше — в одну строку из девяти. Обе утилиты есть в
   прекомпилированном tailwind.css, новые классы не нужны.
2. В <style> добавлено правило #mode-tama-btn.lq-on (изумрудное стекло под
   стать питомцу).
3. #mode-tama-btn добавлен во все четыре списка id (база, ::before, :hover,
   :active) — плитка выглядит и ведёт себя как соседи.

Менялся только index.html — тег сборки nxmob227 -> nxmob228.

Проверка/применение:
    python3 tools/_b484_patch.py --check
    python3 tools/_b484_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob227'
TAG_NEW = 'nxmob228'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('index.html', 1,
              r'''                <div class="grid grid-cols-9 gap-1 sm:gap-2 w-full py-0.5"><!-- b483: девятая плитка — Тамагочи -->''',
              r'''                <div class="grid grid-cols-5 sm:grid-cols-9 gap-1 sm:gap-2 w-full py-0.5"><!-- b484: девять плиток: на телефоне 5+4, от sm — одна строка из девяти (голый grid-cols-9 в tailwind.css отсутствует — из-за него сетка в b483 свалилась в столбик) -->'''))

PAIRS.append(('index.html', 1,
              r'''    #mode-lines-btn.lq-on{ --lq-tint: rgba(14,165,233,.28); --lq-text:#bae6fd; border-color: rgba(125,211,252,.5); }''',
              r'''    #mode-lines-btn.lq-on{ --lq-tint: rgba(14,165,233,.28); --lq-text:#bae6fd; border-color: rgba(125,211,252,.5); }
    /* b484: стекло активной плитки «Тамагочи» (в b483 правило забыли —
       переменная --lq-tint оставалась пустой и подсветка исчезала) */
    #mode-tama-btn.lq-on{ --lq-tint: rgba(52,211,153,.26); --lq-text:#a7f3d0; border-color: rgba(110,231,183,.5); }'''))

PAIRS.append(('index.html', 1,
              r'''    #mode-grid-btn, #mode-wheel-btn, #mode-mines-btn, #mode-lines-btn, #miner-btn{''',
              r'''    #mode-grid-btn, #mode-wheel-btn, #mode-mines-btn, #mode-lines-btn, #mode-tama-btn, #miner-btn{'''))

PAIRS.append(('index.html', 1,
              r'''    #mode-grid-btn::before, #mode-wheel-btn::before, #mode-miner-btn::before, #mode-lines-btn::before, #miner-btn::before{''',
              r'''    #mode-grid-btn::before, #mode-wheel-btn::before, #mode-miner-btn::before, #mode-lines-btn::before, #mode-tama-btn::before, #miner-btn::before{'''))

PAIRS.append(('index.html', 1,
              r'''    #mode-grid-btn:hover, #mode-wheel-btn:hover, #mode-miner-btn:hover, #mode-lines-btn:hover, #miner-btn:hover{''',
              r'''    #mode-grid-btn:hover, #mode-wheel-btn:hover, #mode-miner-btn:hover, #mode-lines-btn:hover, #mode-tama-btn:hover, #miner-btn:hover{'''))

PAIRS.append(('index.html', 1,
              r'''    #mode-grid-btn:active, #mode-wheel-btn:active, #mode-miner-btn:active, #mode-lines-btn:active, #miner-btn:active{ transform: scale(.97); }''',
              r'''    #mode-grid-btn:active, #mode-wheel-btn:active, #mode-miner-btn:active, #mode-lines-btn:active, #mode-tama-btn:active, #miner-btn:active{ transform: scale(.97); }'''))


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
        print('b484: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b484: переключатель режимов снова в строку, плитка «Тамагочи» со стеклом и подсветкой; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
