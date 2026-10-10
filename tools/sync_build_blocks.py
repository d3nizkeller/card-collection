#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пересчёт границ блоков в tools/build.py после правок tools/source-index.html.

build.py режет монолит по АБСОЛЮТНЫМ номерам строк (BLOCKS, BODY_CLOSE). Любая
вставка строк в блоки app_js / qr_xfer сдвигает всё, что ниже, и сборка начинает
резать не те куски. Скрипт находит фактические границы <script>/</script> и
обновляет build.py. Запуск:  python3 tools/sync_build_blocks.py
"""
import io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'tools', 'source-index.html')
BLD = os.path.join(ROOT, 'tools', 'build.py')

BLOCK_KEYS = ['app_css', 'app_js', 'stories', 'qrcode', 'qr_xfer']


def find_pairs(lines):
    """Список (строка_откр_тега, строка_закрыв_тега) для всех <script>/<style>."""
    pairs, opened = [], None
    for i, l in enumerate(lines, 1):
        st = l.strip()
        if st.startswith('<script') or st.startswith('<style'):
            opened = (i, 'style' if st.startswith('<style') else 'script')
        elif st in ('</script>', '</style>'):
            if opened:
                pairs.append((opened[0], i, opened[1]))
                opened = None
    return pairs


def main():
    lines = io.open(SRC, encoding='utf-8').read().split('\n')
    pairs = find_pairs(lines)
    scripts = [(a, b) for a, b, k in pairs if k == 'script']
    styles = [(a, b) for a, b, k in pairs if k == 'style']
    if not scripts or not styles:
        print('в монолите не нашлось блоков <script>/<style>')
        return 1

    # app_css — самый крупный <style>
    app_css = max(styles, key=lambda p: p[1] - p[0])
    # app_js — самый крупный <script> после app_css
    after_css = [p for p in scripts if p[0] > app_css[1]]
    if len(after_css) < 4:
        print('после app_css ожидалось >=4 блоков <script> (three/fa/app_js/stories/qrcode/qr_xfer), найдено %d' % len(after_css))
        return 1
    app_js = max(after_css, key=lambda p: p[1] - p[0])
    # за app_js подряд идут stories, qrcode, qr_xfer
    tail = sorted([p for p in after_css if p[0] > app_js[1]])
    if len(tail) < 3:
        print('после app_js ожидалось 3 блока (stories, qrcode, qr_xfer), найдено %d' % len(tail))
        return 1
    stories, qrcode, qr_xfer = tail[0], tail[1], tail[2]

    body_close = qr_xfer[1] + 1
    if lines[body_close - 1].strip() != '</body>':
        print('строка %d — не </body> (а %r): монолит разошёлся с ожиданиями build.py'
              % (body_close, lines[body_close - 1][:50]))
        return 1

    found = {'app_css': app_css, 'app_js': app_js, 'stories': stories,
             'qrcode': qrcode, 'qr_xfer': qr_xfer}
    s = io.open(BLD, encoding='utf-8').read()
    for key in BLOCK_KEYS:
        a, b = found[key]
        pat = re.compile(r"(^\s*'%s':\s*\()\s*\d+\s*,\s*\d+(\s*,)" % re.escape(key), re.M)
        s, n = pat.subn(lambda m: '%s%d, %d%s' % (m.group(1), a, b, m.group(2)), s, count=1)
        if n != 1:
            print('в build.py не нашлась строка блока %r' % key)
            return 1
    s, n = re.subn(r'^BODY_CLOSE = \d+', 'BODY_CLOSE = %d' % body_close, s, count=1, flags=re.M)
    if n != 1:
        print('в build.py не нашлась строка BODY_CLOSE')
        return 1
    io.open(BLD, 'w', encoding='utf-8', newline='').write(s)
    print('границы блоков обновлены: ' + ', '.join('%s %d-%d' % (k, found[k][0], found[k][1]) for k in BLOCK_KEYS)
          + ', BODY_CLOSE %d' % body_close)
    return 0


if __name__ == '__main__':
    sys.exit(main())
