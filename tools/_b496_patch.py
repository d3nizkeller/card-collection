#!/usr/bin/env python3
# b496: короткие названия разделов по просьбе владельца (скрины трёх заголовков):
# «Рулетка 2D» -> «Рулетка», «Сеточный слот: Линии» -> «Сеточные Линии»,
# «Сеточный слот: Коллекция карт» -> «Слоты».
#  1) три <h2> в index.html переименованы (иконки и id не тронуты);
#  2) тултип кнопки режима рулетки согласован: «Рулетка: ставки фишками…»;
#  3) тесты эти строки не asserting — правок тестов не нужно.
# Якоря применяются один раз; повторный запуск отклоняется (--check для проверки).
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EDITS = [
    # ---------------- index.html: заголовок рулетки ----------------
    ('index.html',
     '<i class="fa-solid fa-circle-dot text-rose-400 mr-2"></i>Рулетка 2D</h2>',
     '<i class="fa-solid fa-circle-dot text-rose-400 mr-2"></i>Рулетка</h2>'),
    # ---------------- index.html: заголовок сеточного слота (коллекция) ----------------
    ('index.html',
     '<i class="fa-solid fa-border-all text-violet-400 mr-2"></i>Сеточный слот: Коллекция карт</h2>',
     '<i class="fa-solid fa-border-all text-violet-400 mr-2"></i>Слоты</h2>'),
    # ---------------- index.html: заголовок сеточного слота (линии) ----------------
    ('index.html',
     '<i class="fa-solid fa-table-cells text-sky-300 mr-2"></i>Сеточный слот: Линии</h2>',
     '<i class="fa-solid fa-table-cells text-sky-300 mr-2"></i>Сеточные Линии</h2>'),
    # ---------------- index.html: тултип кнопки режима рулетки ----------------
    ('index.html',
     'title="Рулетка 2D: ставки фишками из баланса, число ×36, дюжина ×3, равные шансы ×2"',
     'title="Рулетка: ставки фишками из баланса, число ×36, дюжина ×3, равные шансы ×2"'),
]

TAG_OLD, TAG_NEW = 'nxmob239', 'nxmob240'


def read(p):
    with io.open(os.path.join(ROOT, p), 'r', encoding='utf-8') as f:
        return f.read()


def write(p, s):
    with io.open(os.path.join(ROOT, p), 'w', encoding='utf-8') as f:
        f.write(s)


def main():
    check = '--check' in sys.argv
    problems = []
    for p, old, new in EDITS:
        s = read(p)
        if old not in s:
            problems.append('%s: якорь не найден: %s…' % (p, old[:60]))
        elif s.count(old) != 1:
            problems.append('%s: якорь встречается %d раз: %s…' % (p, s.count(old), old[:60]))
        if new and new.strip() and new in s:
            problems.append('%s: похоже, патч УЖЕ применён: %s…' % (p, new[:60]))
    idx = read('index.html')
    if idx.count(TAG_OLD) != 8:
        problems.append('index.html: тега %s найдено %d (ждём 8)' % (TAG_OLD, idx.count(TAG_OLD)))
    sw = read('sw.js')
    if ("VERSION = '%s';" % TAG_OLD) not in sw:
        problems.append('sw.js: строки VERSION=%s нет' % TAG_OLD)
    bp = read('tools/build.py')
    if ("BUILD_TAG = '%s'" % TAG_OLD) not in bp:
        problems.append('tools/build.py: BUILD_TAG=%s нет' % TAG_OLD)
    if problems:
        for x in problems:
            print('PROBLEM:', x)
        sys.exit(1)
    if check:
        print('check ok: %d якорей + тег %s -> %s' % (len(EDITS), TAG_OLD, TAG_NEW))
        sys.exit(0)
    for p, old, new in EDITS:
        s = read(p)
        write(p, s.replace(old, new, 1))
    write('index.html', read('index.html').replace(TAG_OLD, TAG_NEW))
    write('sw.js', read('sw.js').replace("VERSION = '%s';" % TAG_OLD, "VERSION = '%s';" % TAG_NEW))
    write('tools/build.py', read('tools/build.py').replace("BUILD_TAG = '%s'" % TAG_OLD, "BUILD_TAG = '%s'" % TAG_NEW))
    print('applied: %d якорей, тег %s -> %s' % (len(EDITS), TAG_OLD, TAG_NEW))


if __name__ == '__main__':
    main()
