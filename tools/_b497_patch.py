#!/usr/bin/env python3
# b497: HTML из сети БЕЗ HTTP-кэша браузера + чистка старого комментария.
# Владелец повторно прислал скрины со старыми заголовками («Рулетка 2D» и т.д.),
# хотя b496 уже на проде: его клиент держал копию index.html из HTTP-кэша —
# pageFirst() в sw.js делал fetch(req) с дефолтным cache-режимом, и браузер
# мог отдать закешированный HTML ещё несколько минут после деплоя.
#  1) pageFirst(): fetch(req, { cache: 'no-store' }) — навигация всегда тянет
#     свежий HTML с сервера; офлайн-фолбэк в кэш CACHE_PAGES сохранён;
#  2) index.html: комментарий b103 с прежним названием раздела приведён к новому.
# Якоря применяются один раз; повторный запуск отклоняется (--check для проверки).
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EDITS = [
    # ---------------- sw.js: навигация мимо HTTP-кэша браузера ----------------
    ('sw.js',
     """/* HTML: сначала сеть (иначе игрок застрянет на старой версии), кэш — запасной выход */
async function pageFirst(e, req) {
    const cache = await caches.open(CACHE_PAGES);
    try {
        const resp = await fetch(req);""",
     """/* HTML: сначала сеть (иначе игрок застрянет на старой версии), кэш — запасной выход.
   b497: cache:'no-store' — HTTP-кэш браузера не подсовывает старый index.html
   сразу после деплоя (владелец видел заголовки до b496). */
async function pageFirst(e, req) {
    const cache = await caches.open(CACHE_PAGES);
    try {
        const resp = await fetch(req, { cache: 'no-store' });"""),
    # ---------------- index.html: комментарий с прежним названием ----------------
    ('index.html',
     '                <!-- b103: Сеточный слот: Линии -->',
     '                <!-- b103/b496: Сеточные Линии -->'),
]

TAG_OLD, TAG_NEW = 'nxmob240', 'nxmob241'


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
