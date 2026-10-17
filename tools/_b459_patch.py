#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b459: внешняя ссылка на арт снова видна в превью + слайдеры в одну линию.

(1) «Вставляю ссылку на изображение, а картинка не появляется в
просмотре». Диагноз (puppeteer, dbg3): для внешней ссылки без «/media/»
в URL (unsplash и т.п.) nxThumbFor() достраивал «по соглашению»
ЛОЖНЫЙ локальный путь миниатюры media/t2/<имя>.webp: сервер отвечает
404, цепочка ошибок до мастера доходит не сразу (или не доходит на
битом кэше) — превью стоит пустое. Лечение: если ссылка внешняя
(http…) и каталога /media/ в ней нет — миниатюры у нас для неё нет и
быть не может: возвращаем пустую строку, и mediaThumbMid()/
mediaThumbFor() сразу откатываются на мастер-URL (mediaUrl) — картинка
рисуетcя мгновенно, без круговорота 404.

(2) «Кнопки не ровные»: подпись «Сдвиг по горизонтали» переносится на
две строки и уводит свой ползунок ниже остальных. Лечение: строка
слайдеров получает items-end — все три ползунка выровнены по нижней
линии независимо от высоты подписей; на узких экранах
grid-cols-1 sm:grid-cols-3 — слайдеры встают в столбик во всю ширину.

(3) app.js менялся — поднят тег сборки nxmob181 -> nxmob182 (index.html,
sw.js, tools/build.py): кэш nx-assets у клиентов перечитается сразу,
без ожидания фоновой сверки (урок b457).

Проверка/применение:
    python3 tools/_b459_patch.py --check
    python3 tools/_b459_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob181'
TAG_NEW = 'nxmob182'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('assets/app.js', '''                if (full.indexOf('http') !== 0) return conv;
                const j = full.lastIndexOf('/media/');
                if (j < 0) return conv;''',
              '''                if (full.indexOf('http') !== 0) return conv;
                const j = full.lastIndexOf('/media/');
                // b459: у внешней ссылки (unsplash и т.п.) без каталога /media/
                // миниатюры на нашем сервере нет и быть не может: достроенный
                // «по соглашению» путь media/t2/<имя>.webp давал 404, и живой
                // предпросмотр стоял пустым. Возвращаем пустоту — mediaThumbMid()/
                // mediaThumbFor() сразу откатятся на мастер-URL (mediaUrl).
                if (j < 0) return '';'''))

PAIRS.append(('index.html', '''                        <div class="grid grid-cols-3 gap-3">''',
              '''                        <!-- b459: ползунки выровнены по нижней линии (items-end) —
                             подпись «Сдвиг по горизонтали» может переноситься, кнопки
                             остаются в одну линию; на узких экранах — столбиком -->
                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">'''))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, old, new in PAIRS:
        txt = files.get(rel) or read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        if txt.count(o) != 1:
            problems.append('%s: якорь встретился %d раз: %s...' % (rel, txt.count(o), o[:60]))
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
        print('b459: якоря и тег %s на месте, можно применять' % TAG_OLD)
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b459: внешние ссылки в превью + ровные слайдеры; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
