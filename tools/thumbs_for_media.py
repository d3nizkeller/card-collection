#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Догенерация миниатюр для артов, которые появились в media/ ПОСЛЕ сборки.

Зачем: автоотправка b343/b341 коммитит в media/ только мастера (1.6-4.3 МБ,
а «Гарри Поттер» — вообще 4K PNG по 10-16 МБ). Без миниатюр новая карта в
любой сетке грузилась мастером — см. FIXES.md, b377. Раньше это лечилось
только ручным запуском build.py у владельца.

Теперь: GitHub Action на каждый пуш, затрагивающий media/** (кроме самих
media/t, media/t2 и media/t3), догоняет недостающие миниатюры и коммитит их
обратно. Параметры (THUMB_W/Q, MID_W/Q, MID_MIN_SRC, BIG_W/Q) — один в один
с tools/build.py, чтобы картинки, собранные экшеном, не отличались от
собранных локально.

b438: добавлен третий уровень media/t3/ («большой» webp, длинная сторона
≤1440px) — его грузят просмотр карты и вид «галерея» вместо мастеров
10-16 МБ, которые на телефоне не прогружаются и не влезают в постоянный
кэш (IMG_CACHE_MAX_BLOB = 8 МБ). t3 строится только для тяжёлых мастеров
(длинная сторона > 1440 px ИЛИ файл > 700 КБ): лёгкий мастер и так грузится
мгновенно, плодить дубликат незачем. Если пережатый webp оказался почти
таким же тяжёлым, как мастер (≥90%), файл удаляется — карта останется на
мастере, как раньше.

Запуск локально:  python3 tools/thumbs_for_media.py [--force]
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(ROOT, 'media')
THUMBS = os.path.join(MEDIA, 't')
MIDS = os.path.join(MEDIA, 't2')
BIGS = os.path.join(MEDIA, 't3')

THUMB_W, THUMB_Q = 256, 72        # как в tools/build.py
MID_W, MID_Q = 512, 78            # как в tools/build.py
MID_MIN_SRC = 640                 # как в tools/build.py
BIG_W, BIG_Q = 1440, 80           # b438: как в tools/build.py
BIG_MIN_BYTES = 700 * 1024        # b438: мастер легче — t3 не нужен
BIG_METHOD = 4                    # b438: 4K-мастеров много, method=6 в CI медленный

EXT = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp',
     '.jfif', '.tif', '.tiff')   # b382: единый список с build.py/sync_thumb_maps.py


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


def encode_big(im, dst, src_bytes, force):
    """b438: «большой» уровень — вписываем ДЛИННУЮ сторону в BIG_W (не увеличивая).

    Возвращает True, если файл создан/пересоздан и оставлен.
    """
    if os.path.exists(dst) and not force:
        return False
    ww, hh = im.size
    long_side = max(ww, hh)
    if long_side > BIG_W:
        scale = BIG_W / float(long_side)
        tw, th = max(1, round(ww * scale)), max(1, round(hh * scale))
        out = im.resize((tw, th), Image.LANCZOS)
    else:
        out = im
    out.save(dst, 'WEBP', quality=BIG_Q, method=BIG_METHOD)
    # пережатие почти ничего не сэкономило (мастер сам по себе лёгкий webp/jpg) —
    # дубликат не держим: карта останется на мастере
    try:
        if os.path.getsize(dst) >= src_bytes * 0.9:
            os.remove(dst)
            return False
    except OSError:
        pass
    return True


def main():
    force = '--force' in sys.argv
    os.makedirs(THUMBS, exist_ok=True)
    os.makedirs(MIDS, exist_ok=True)
    os.makedirs(BIGS, exist_ok=True)
    made_t = made_m = made_b = skipped = 0
    for f in masters():
        base = os.path.splitext(f)[0]
        src = os.path.join(MEDIA, f)
        dt = os.path.join(THUMBS, base + '.webp')
        dm = os.path.join(MIDS, base + '.webp')
        db = os.path.join(BIGS, base + '.webp')
        try:
            size = Image.open(src).size
            w = size[0]
        except Exception as e:
            print('  ! не читается %s: %s' % (f, e))
            continue
        src_bytes = os.path.getsize(src)
        heavy = max(size) > BIG_W or src_bytes > BIG_MIN_BYTES
        need_t = force or not os.path.exists(dt)
        need_m = w > MID_MIN_SRC and (force or not os.path.exists(dm))
        need_b = heavy and (force or not os.path.exists(db))
        if not need_t and not need_m and not need_b:
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
        if need_b:
            try:
                if encode_big(im, db, src_bytes, force):
                    made_b += 1
            except Exception as e:
                print('  ! t3 не собрался %s: %s' % (f, e))
        im.close()
    print('миниатюры: новых мелких %d, новых средних %d, новых больших(t3) %d, уже были %d'
          % (made_t, made_m, made_b, skipped))
    return 0


if __name__ == '__main__':
    sys.exit(main())
