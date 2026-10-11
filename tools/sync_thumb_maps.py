#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Синхронизация встроенных карт миниатюр в assets/app.js с содержимым media/.

Зачем это нужно
---------------
``nxThumbFor()`` ищет миниатюру сперва в ``NX_EMBED_THUMB`` / ``NX_EMBED_THUMB_MID``.
Если имени файла там нет, путь достраивается «по соглашению» —
``media/t/<имя>.webp`` или ``media/t2/<имя>.webp``. Когда такого файла на
сервере нет, браузер получает 404, ``imgErrorChain`` откатывается на
``data-nx-full`` (мастер 1.6–4.3 МБ), и карта в сетке грузится мастером.
На телефоне это и есть «картинки не загружаются»: 59 таких карт — около
125 МБ трафика и ~460 МБ распакованных битмапов, WebView умирает.

``tools/build.py`` пересобирает карты при ручном запуске у владельца, но
автоотправка артов (b343) коммитит в ``media/`` только мастера. Этот скрипт
обновляет карты прямо в уже собранном ``assets/app.js``, поэтому его можно
вызывать из CI сразу после ``tools/thumbs_for_media.py``.

Правила построения карт — ровно как в ``tools/build.py``:
  * ключ   — имя файла мастера в ``media/``;
  * значение — относительный путь миниатюры;
  * ``NX_EMBED_THUMB``     — только те мастера, для которых РЕАЛЬНО существует
    ``media/t/<имя>.webp``;
  * ``NX_EMBED_THUMB_MID`` — только те, для которых РЕАЛЬНО существует
    ``media/t2/<имя>.webp`` (build.py строит среднюю лишь при ширине мастера
    больше ``MID_MIN_SRC`` = 640 px).

Карта строится по факту наличия файла на диске, а не по ширине мастера:
``nxThumbFor()`` не должен указывать на то, чего нет на сервере.

Запуск
------
    python3 tools/sync_thumb_maps.py            # переписать assets/app.js
    python3 tools/sync_thumb_maps.py --check    # не писать; код 1, если разошлось
    python3 tools/sync_thumb_maps.py --report   # read-only: warning-аннотации для
                                                # мастеров, оставшихся БЕЗ
                                                # миниатюры (битый/нечитаемый
                                                # файл): карта молча ушла бы
                                                # на мастер 1.6-4.3 МБ
    python3 tools/sync_thumb_maps.py --bump-version  # дополнительно поднять
                                                # ?v=nxmobNN в index.html,
                                                # VERSION в sw.js и BUILD_TAG
                                                # в tools/build.py
"""
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(ROOT, 'media')
THUMBS = os.path.join(MEDIA, 't')
MIDS = os.path.join(MEDIA, 't2')
APP_JS = os.path.join(ROOT, 'assets', 'app.js')
INDEX_HTML = os.path.join(ROOT, 'index.html')
SW_JS = os.path.join(ROOT, 'sw.js')
BUILD_PY = os.path.join(ROOT, 'tools', 'build.py')

EXT = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp',
     '.jfif', '.tif', '.tiff')  # b382: единый список с build.py/thumbs_for_media.py

SMALL_DECL = 'const NX_EMBED_THUMB = '
MID_DECL = 'const NX_EMBED_THUMB_MID = '


def masters():
    """Имена файлов-мастеров в media/ (без подкаталогов)."""
    if not os.path.isdir(MEDIA):
        return []
    out = []
    for f in sorted(os.listdir(MEDIA)):
        p = os.path.join(MEDIA, f)
        if os.path.isfile(p) and f.lower().endswith(EXT):
            out.append(f)
    return out


def names_in(d):
    if not os.path.isdir(d):
        return set()
    return set(os.listdir(d))


def build_maps():
    ms = masters()
    have_t = names_in(THUMBS)
    have_t2 = names_in(MIDS)
    small, mid = {}, {}
    for f in ms:
        base = os.path.splitext(f)[0]
        if base + '.webp' in have_t:
            small[f] = 'media/t/' + base + '.webp'
        if base + '.webp' in have_t2:
            mid[f] = 'media/t2/' + base + '.webp'
    return small, mid


def dumps(m):
    """Тот же формат, что в tools/build.py."""
    return json.dumps(m, ensure_ascii=False, sort_keys=True)


def replace_decl(text, decl, payload):
    """Заменяет однострочное объявление ``decl`` + JSON + ``;``.

    build.py пишет карты одной строкой, поэтому замена построчная: никаких
    рисков с подсчётом скобок внутри имён файлов.
    """
    lines = text.split('\n')
    hits = 0
    for i, ln in enumerate(lines):
        st = ln.lstrip()
        if not st.startswith(decl):
            continue
        indent = ln[:len(ln) - len(st)]
        rest = st[len(decl):]
        if not (rest.startswith('{') and rest.rstrip().endswith('};')):
            raise SystemExit('ожидалось однострочное объявление %r (строка %d)'
                             % (decl, i + 1))
        lines[i] = indent + decl + payload + ';'
        hits += 1
    if hits != 1:
        raise SystemExit('%r найдено %d раз, ожидалось ровно 1' % (decl, hits))
    return '\n'.join(lines)


def bump_version(text_index, text_sw, text_build):
    """nxmobNN -> nxmob(NN+1) в index.html (?v=), sw.js (VERSION), build.py (BUILD_TAG)."""
    m = re.search(r"BUILD_TAG = '(nxmob)(\d+)'", text_build)
    if not m:
        raise SystemExit('в tools/build.py не найден BUILD_TAG = nxmobNN')
    old = m.group(0)[len("BUILD_TAG = '"):-1]
    new = '%s%d' % (m.group(1), int(m.group(2)) + 1)

    n_idx = text_index.count('?v=' + old)
    if n_idx == 0:
        raise SystemExit('в index.html нет ?v=%s' % old)
    text_index = text_index.replace('?v=' + old, '?v=' + new)

    n_sw = text_sw.count("const VERSION = '%s';" % old)
    if n_sw:
        text_sw = text_sw.replace("const VERSION = '%s';" % old,
                                  "const VERSION = '%s';" % new)

    text_build = text_build.replace("BUILD_TAG = '%s'" % old,
                                    "BUILD_TAG = '%s'" % new, 1)
    return text_index, text_sw, text_build, old, new, n_idx


def read(p):
    with io.open(p, 'rb') as fh:
        return fh.read()


def write(p, data):
    with io.open(p, 'wb') as fh:
        fh.write(data)


def report_missing(small, mid):
    """Warning-аннотации для мастеров, у которых нет миниатюры вовсе.

    Такой мастер не попадает ни в одну карту, nxThumbFor() достроит путь
    «по соглашению», сервер ответит 404, и карта молча уйдёт на мастер
    1.6-4.3 МБ — тот самый рецидив «картинки не загружаются». В CI это
    должно быть видно, а не тихо.
    """
    ms = masters()
    bad = [f for f in ms if f not in small]
    for f in bad:
        print('::warning file=media/%s,title=мастер без миниатюры::'
              'media/t/%s.webp не создана (файл не читается PIL?). Карта будет '
              'грузиться мастером.' % (f, os.path.splitext(f)[0]))
    no_mid = [f for f in ms if f in small and f not in mid]
    print('мастеров: %d | без мелкой миниатюры: %d | без средней: %d'
          % (len(ms), len(bad), len(no_mid)))
    return bad


def main(argv):
    check = '--check' in argv
    bump = '--bump-version' in argv
    report = '--report' in argv

    if not os.path.isfile(APP_JS):
        print('нет assets/app.js — нечего синхронизировать')
        return 0

    small, mid = build_maps()
    if report:
        report_missing(small, mid)
        # голый --report — только диагностика, ничего не пишем
        if not check and not bump:
            return 0
    raw = read(APP_JS)
    text = raw.decode('utf-8')
    for marker in ('/*NX_EMBED_THUMB_START*/', '/*NX_EMBED_THUMB_END*/'):
        if marker not in text:
            print('в assets/app.js нет маркера %s — файл собран не build.py?' % marker)
            return 0

    new_text = replace_decl(text, SMALL_DECL, dumps(small))
    new_text = replace_decl(new_text, MID_DECL, dumps(mid))

    print('карты миниатюр: мелких %d, средних %d (мастеров в media/: %d)'
          % (len(small), len(mid), len(masters())))

    changed = new_text.encode('utf-8') != raw
    if bump:
        idx_raw = read(INDEX_HTML)
        sw_raw = read(SW_JS) if os.path.isfile(SW_JS) else None
        bld_raw = read(BUILD_PY)
        idx, sw, bld, old, new, n_idx = bump_version(
            idx_raw.decode('utf-8'),
            sw_raw.decode('utf-8') if sw_raw else '',
            bld_raw.decode('utf-8'))
        print('версия кэша: %s -> %s (?v= в index.html: %d)' % (old, new, n_idx))
        idx_changed = idx.encode('utf-8') != idx_raw
        sw_changed = sw_raw is not None and sw.encode('utf-8') != sw_raw
        bld_changed = bld.encode('utf-8') != bld_raw
    else:
        idx = sw = bld = None
        idx_changed = sw_changed = bld_changed = False

    if check:
        if changed or idx_changed or sw_changed or bld_changed:
            print('РАЗОШЛОСЬ: запустите python3 tools/sync_thumb_maps.py')
            return 1
        print('assets/app.js в синхроне с media/')
        return 0

    if changed:
        write(APP_JS, new_text.encode('utf-8'))
        print('assets/app.js обновлён (%d -> %d байт)' % (len(raw), len(new_text.encode('utf-8'))))
    else:
        print('assets/app.js уже в синхроне')
    if bump:
        if idx_changed:
            write(INDEX_HTML, idx.encode('utf-8'))
            print('index.html обновлён')
        if sw_changed:
            write(SW_JS, sw.encode('utf-8'))
            print('sw.js обновлён')
        if bld_changed:
            write(BUILD_PY, bld.encode('utf-8'))
            print('tools/build.py обновлён')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
