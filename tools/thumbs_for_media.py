#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Догенерация миниатюр для артов, которые появились в media/ ПОСЛЕ сборки.

Зачем: автоотправка b343/b341 коммитит в media/ только мастера (1.6-4.3 МБ).
Без миниатюр новая карта в любой сетке грузилась мастером — см. FIXES.md, b377.
Раньше это лечилось только ручным запуском build.py у владельца.

Теперь: GitHub Action на каждый пуш, затрагивающий media/** (кроме самих
media/t и media/t2), догоняет недостающие миниатюры и коммитит их обратно.
Параметры (THUMB_W/Q, MID_W/Q, MID_MIN_SRC) — один в один с tools/build.py,
чтобы картинки, собранные экшеном, не отличались от собранных локально.

Запуск локально:  python3 tools/thumbs_for_media.py [--force]
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(ROOT, 'media')
THUMBS = os.path.join(MEDIA, 't')
MIDS = os.path.join(MEDIA, 't2')

THUMB_W, THUMB_Q = 256, 72        # как в tools/build.py
MID_W, MID_Q = 512, 78            # как в tools/build.py
MID_MIN_SRC = 640                 # как в tools/build.py

EXT = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')


def masters():
    out = []
    for f in sorted(os.listdir(MEDIA)):
        p = os.path.join(MEDIA, f)
        if os.path.isfile(p) and f.lower().endswith(EXT):
            out.append(f)
    return out


def encode(im, w, q, dst, force):
    if os.path.exists(dst) and not force:
        return False
    ww, hh = im.size
    tw = w if ww > w else ww
    th = max(1, round(hh * tw / ww))
    im.resize((tw, th), Image.LANCZOS).save(dst, 'WEBP', quality=q, method=6)
    return True


def main():
    force = '--force' in sys.argv
    os.makedirs(THUMBS, exist_ok=True)
    os.makedirs(MIDS, exist_ok=True)
    made_t = made_m = skipped = 0
    for f in masters():
        base = os.path.splitext(f)[0]
        src = os.path.join(MEDIA, f)
        dt = os.path.join(THUMBS, base + '.webp')
        dm = os.path.join(MIDS, base + '.webp')
        try:
            w = Image.open(src).size[0]
        except Exception as e:
            print('  ! не читается %s: %s' % (f, e))
            continue
        need_t = force or not os.path.exists(dt)
        need_m = w > MID_MIN_SRC and (force or not os.path.exists(dm))
        if not need_t and not need_m:
            skipped += 1
            continue
        try:
            im = Image.open(src)
            im.load()
        except Exception as e:
            print('  ! не читается %s: %s' % (f, e))
            continue
        if im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGB')
        if encode(im, THUMB_W, THUMB_Q, dt, force):
            made_t += 1
        if w > MID_MIN_SRC and encode(im, MID_W, MID_Q, dm, force):
            made_m += 1
        im.close()
    print('миниатюры: новых мелких %d, новых средних %d, уже были %d'
          % (made_t, made_m, skipped))
    return 0


if __name__ == '__main__':
    sys.exit(main())
