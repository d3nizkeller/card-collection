#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b486: уведомления облака комнаты («Опубликовано в комнату…») — только в Студии.

Заявка владельца (скриншот тоста посреди игры): «эти уведомление видны должны
только в студии».

Разбор
------
Успешная публикация каталога в комнату комнаты рапортовала тостом
«Опубликовано в комнату 7j8uytui: 2 паков, 384 карт» через обычный showToast —
всплывающим посреди партии, хотя владельцу это интересно только когда он
смотрит в Студию. В проекте с b369 уже есть механизм для таких случаев:
nxOwnerToast (qr-transfer.js) показывает тост, ТОЛЬКО если открыта вкладка
«Студия» (nxInStudio), иначе молча проглатывает.

Лечение: на nxOwnerToast переведены три информационных тоста облака:
1. успех публикации каталога («Опубликовано в комнату … паков, … карт»,
   включая тихий авто-режим с префиксом ☁️);
2. «Возвращено в стандартный набор и опубликовано в комнату» (действие
   владельца из Студии — там тост и останется);
3. «Автопубликация выключена — нажмите „Опубликовать“…» (подсказка у кнопки
   публикации, тоже живёт в Студии).
Ошибки публикации («Сначала введите код комнаты…», «Публиковать может только
создатель…») тронуты НЕ были: они и так показываются только при ручном
действии (!quiet) или владельцу при облачном гейте — молча оставлять ошибку
нельзя, иначе непонятно, почему не сохранилось.

Менялся только assets/app.js — тег сборки nxmob229 -> nxmob230.

Проверка/применение:
    python3 tools/_b486_patch.py --check
    python3 tools/_b486_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob229'
TAG_NEW = 'nxmob230'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('assets/app.js', 1,
              r'''                        showToast((quiet ? '☁️ ' : '') + 'Опубликовано в комнату ' + CLOUD.room + ': ' +
                            fit.cat.packs.length + ' паков, ' + fit.cat.cards.length + ' карт', 'success');''',
              r'''                        nxOwnerToast((quiet ? '☁️ ' : '') + 'Опубликовано в комнату ' + CLOUD.room + ': ' +
                            fit.cat.packs.length + ' паков, ' + fit.cat.cards.length + ' карт', 'success'); // b486: рапорт о публикации — только в Студии, не посреди партии'''))

PAIRS.append(('assets/app.js', 1,
              r'''            showToast('Возвращено в стандартный набор и опубликовано в комнату', 'success');''',
              r'''            nxOwnerToast('Возвращено в стандартный набор и опубликовано в комнату', 'success'); // b486: только в Студии'''))

PAIRS.append(('assets/app.js', 1,
              r'''            if (!cloudAuto()) { showToast('⚠️ Автопубликация выключена — нажмите «Опубликовать», чтобы отправить изменения в комнату', 'refund'); return; }''',
              r'''            if (!cloudAuto()) { nxOwnerToast('⚠️ Автопубликация выключена — нажмите «Опубликовать», чтобы отправить изменения в комнату', 'refund'); return; } // b486: подсказка у кнопки публикации — только в Студии'''))


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
        print('b486: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b486: рапорты облака комнаты — только в Студии; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
