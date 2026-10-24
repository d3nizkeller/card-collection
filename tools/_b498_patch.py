#!/usr/bin/env python3
# b498: заголовок сеточного раздела 5×5 — «Сетка» (а не «Слоты»).
# Владелец со скрином заголовка «Слоты» (фиолетовая иконка fa-border-all):
# «тут сетка должна быть написано». В b496 раздел получил имя «Слоты», но
# владельцу нужно имя вкладки — «Сетка»; заодно уходит коллизия с заголовком
# барабанного автомата «Игровые автоматы: Слоты».
#  1) h2 сеточного раздела: «Слоты» -> «Сетка» (иконка и id не тронуты);
#  2) тесты строку не проверяют — правок тестов не нужно.
# Якоря применяются один раз; повторный запуск отклоняется (--check для проверки).
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EDITS = [
    # ---------------- index.html: заголовок сеточного раздела 5×5 ----------------
    ('index.html',
     '<i class="fa-solid fa-border-all text-violet-400 mr-2"></i>Слоты</h2>',
     '<i class="fa-solid fa-border-all text-violet-400 mr-2"></i>Сетка</h2>'),
]

TAG_OLD, TAG_NEW = 'nxmob241', 'nxmob242'


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
