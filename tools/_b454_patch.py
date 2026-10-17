#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b454: карточка живого превью тянется по высоте колонки, пак по центру.

После b452–b453 колонка превью точно равна колонке полей, но лишнюю
высоту забирала карточка «Подсказки» — внутри неё снизу оставалось
пустое место. Красивее отдать растяжку карточке превью: flex-1 +
justify-center — пак стоит по центру «витрины», а подсказки идут
своей естественной высотой ниже.

Проверка/применение:
    python3 tools/_b454_patch.py --check
    python3 tools/_b454_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'index.html')

OLD = '<div class="flex flex-col items-center gap-2 bg-slate-950/70 border border-slate-800 rounded-xl p-3 max-w-md mx-auto">\n                                <div id="pack-style-preview"'
NEW = '<div class="flex-1 justify-center flex flex-col items-center gap-2 bg-slate-950/70 border border-slate-800 rounded-xl p-3 max-w-md mx-auto">\n                                <div id="pack-style-preview"'


def read():
    with io.open(HTML, encoding='utf-8') as f:
        return f.read()


def main():
    html = read()
    done = 'flex-1 justify-center flex flex-col items-center gap-2 bg-slate-950/70' in html
    if done and '--check' in sys.argv:
        print('b454: уже применён')
        return 0
    if done:
        print('b454: уже применён')
        return 1
    if html.count(OLD) != 1:
        print('ПРОБЛЕМА: якорь превью-карточки не уникален/не найден (%d)' % html.count(OLD))
        return 1
    if '--check' in sys.argv:
        print('b454: якорь найден, можно применять')
        return 0
    new = html.replace(OLD, NEW, 1)
    with io.open(HTML, 'w', encoding='utf-8') as f:
        f.write(new)
    print('b454: превью-карточка тянется по высоте, пак по центру')
    return 0


if __name__ == '__main__':
    sys.exit(main())
