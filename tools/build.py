#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборка мобильно-оптимизированной версии «Коллекционер карт».

Было: один index.html на 3.2 МБ, внутри — JIT-компилятор Tailwind (пересобирает
CSS прямо в браузере при каждой мутации DOM), Font Awesome целиком (шрифт трижды),
three.js, и весь код игры. На телефоне это = долгий парсинг + постоянные
пересборки CSS в главном потоке + ~91 МБ распакованных картинок.

Стало: тонкий index.html (~0.25 МБ разметки) + отдельные кешируемые файлы.

Вход :  tools/source-index.html   — исходный монолит (копия текущего index.html)
Выход:  index.html, assets/*, media/t/*.webp

Запуск:  python3 tools/build.py            (пересобрать всё)
         python3 tools/build.py --no-media (не перегенерировать миниатюры)

Скрипт идемпотентен: его можно запускать после каждой правки игры.
Если вы правите сам index.html напрямую — сначала верните его в
tools/source-index.html, потом запускайте сборку.
"""

import base64
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'tools', 'source-index.html')
ASSETS = os.path.join(ROOT, 'assets')
MEDIA = os.path.join(ROOT, 'media')
THUMBS = os.path.join(MEDIA, 't')
MIDS = os.path.join(MEDIA, 't2')

BUILD_TAG = 'nxmob5'          # меняется при изменении структуры — сбрасывает кэш SW
THUMB_W = 256                 # мелкая миниатюра (списки, компактные сетки), px
THUMB_Q = 72
MID_W = 512                   # средняя (обычные сетки, вскрытие пака), px
MID_Q = 78
MID_MIN_SRC = 640             # средняя миниатюра нужна только если мастер шире этого
# ВАЖНО: миниатюры строятся для ВСЕХ файлов media/, а не только для упомянутых
# в index.html. Каталог карт приходит из облака комнаты (textdb.dev) и ссылается
# на media/card_*.png напрямую — в HTML этих имён нет, но файлы рабочие.

log = []


def say(msg):
    print(msg)
    log.append(msg)


# --------------------------------------------------------------------------- #
# 0. читаем исходник (CRLF сохраняем как есть)
# --------------------------------------------------------------------------- #
def read_lines(path):
    with open(path, 'rb') as f:
        data = f.read().decode('utf-8')
    return data.split('\r\n')


def write_crlf(path, text):
    with open(path, 'wb') as f:
        f.write(text.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))


def write_lf(path, text):
    with open(path, 'wb') as f:
        f.write(text.replace('\r\n', '\n').encode('utf-8'))


# --------------------------------------------------------------------------- #
# 1. границы блоков в исходном монолите (1-based, включительно)
#    проверяем содержимое — если источник изменился, сборка упадёт громко,
#    а не молча соберёт кашу
# --------------------------------------------------------------------------- #
BLOCKS = {
    'tw_cdn':    (19, 105,    'script', 'Tailwind Play CDN'),
    'tw_config': (106, 122,   'script', 'tailwind.config'),
    'three':     (123, 132,   'script', 'three.js r128'),
    'fa':        (133, 144,   'style',  'Font Awesome 6.4.0'),
    'app_css':   (146, 1087,  'style',  'основной CSS игры'),
    'app_js':    (3612, 17951, 'script', 'код игры'),
    'stories':   (17952, 18693, 'script', 'нарезчик сторис 9:16'),
    'qrcode':    (18694, 18698, 'script', 'qrcode.js'),
    'qr_xfer':   (18699, 20241, 'script', 'перенос прогресса по QR'),
}

HEAD_END = 1088       # </head>
GOOGLE_FONTS = 145    # <link href="https://fonts.googleapis.com/...">
BODY_OPEN = 1089
BODY_CLOSE = 20242


def inner(lines, key):
    """содержимое блока без обрамляющих тегов <script>/<style>"""
    a, b, kind, _ = BLOCKS[key]
    first = lines[a - 1]
    last = lines[b - 1]
    assert first.strip().startswith('<' + kind), f'{key}: строка {a} — не <{kind}>, а {first[:60]!r}'
    assert last.strip() == '</%s>' % kind, f'{key}: строка {b} — не </{kind}>, а {last[:60]!r}'
    body = list(lines[a:b - 1])
    # у первого блока-opening тега может быть хвост после <script>
    body[0] = re.sub(r'^\s*<%s[^>]*>' % kind, '', body[0])
    return '\n'.join(body)


# --------------------------------------------------------------------------- #
# 2. Font Awesome: вырезаем подмножество
# --------------------------------------------------------------------------- #
FA_FIXES = {
    # этих иконок нет в Font Awesome 6 Free (только в Pro) — сейчас они
    # рисуются пустым квадратом. Меняем на ближайшие бесплатные аналоги.
    'fa-sack-coins': 'fa-sack-dollar',
    'fa-sparkles': 'fa-wand-magic-sparkles',
}
FA_NOISE = {
    'solid', 'regular', 'brands', 'classic', 'sharp', 'light', 'thin', 'duotone',
    '2xs', 'xs', 'sm', 'lg', 'xl', '2xl', 'fw', 'spin', 'pulse', 'shake', 'beat',
    'fade', 'beat-fade', 'bounce', 'flip', 'rotate', 'border', 'pull-left',
    'pull-right', 'stack', 'stack-1x', 'stack-2x', 'inverse', 'sr-only', 'ul',
    'li', 'fixed-width', 'swap-opacity', 'layers', 'sr-only-focusable',
}


def fa_used_icons(text_without_fa_css):
    names = set(re.findall(r'\bfa-([a-z0-9]+(?:-[a-z0-9]+)*)\b', text_without_fa_css))
    return {n for n in names if n not in FA_NOISE and not n[0].isdigit()}


def fa_codepoints(fa_css):
    """имя иконки -> codepoint; устойчиво к сгруппированным селекторам
       вида .fa-a:before,.fa-b:before{content:"\\f000"}"""
    cp = {}
    rx = re.compile(r'\{content:"\\([0-9a-fA-F]{2,6})"\}')
    for m in rx.finditer(fa_css):
        code = m.group(1).zfill(4)
        start = max(fa_css.rfind('}', 0, m.start()), fa_css.rfind('{', 0, m.start() - 1))
        sel = fa_css[start + 1:m.start()]
        for part in sel.split(','):
            part = part.strip()
            if part.endswith(':before') and part.startswith('.fa-'):
                cp.setdefault(part[4:-7], code)
    return cp


def build_fontawesome(fa_css, used):
    keep = {}
    cp = fa_codepoints(fa_css)
    for name in sorted(used):
        if name in cp:
            keep[name] = cp[name]
    unresolved = sorted(n for n in used if n not in cp)

    # шрифт: в исходнике один и тот же woff2 лежит base64 ТРИ раза
    b64 = re.search(r'url\(data:font/woff2;charset=utf-8;base64,([A-Za-z0-9+/=]+)\)', fa_css)
    assert b64, 'не найден встроенный woff2 Font Awesome'
    full = os.path.join(ROOT, 'tools', '_fa_solid_full.woff2')
    with open(full, 'wb') as f:
        f.write(base64.b64decode(b64.group(1)))

    subset = os.path.join(ASSETS, 'fa-solid-900.woff2')
    unicodes = ','.join('U+' + v for v in set(keep.values())) + ',U+0020'
    try:
        subprocess.run(
            [sys.executable, '-m', 'fontTools.subset', full,
             '--unicodes=' + unicodes, '--flavor=woff2',
             '--output-file=' + subset, '--layout-features=*',
             '--no-hinting', '--desubroutinize'],
            check=True, capture_output=True)
        font_note = 'собран из %d глифов' % len(set(keep.values()))
    except Exception as e:
        # нет fontTools — кладём полный шрифт, иконки всё равно будут работать
        shutil.copy(full, subset)
        font_note = 'fontTools недоступен (%s) — взят полный шрифт' % e
    os.remove(full)

    # CSS: выбрасываем все @font-face (сделаем один свой) и неиспользуемые иконки
    css = re.sub(r'@font-face\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', '', fa_css)
    rx = re.compile(r'\{content:"\\([0-9a-fA-F]{2,6})"\}')
    out, pos, dropped = [], 0, 0
    for m in rx.finditer(css):
        start = max(css.rfind('}', 0, m.start()), css.rfind('{', 0, m.start() - 1)) + 1
        sel = css[start:m.start()]
        names = [p.strip()[4:-7] for p in sel.split(',')
                 if p.strip().endswith(':before') and p.strip().startswith('.fa-')]
        if names and not any(n in keep for n in names):
            out.append(css[pos:start])
            pos = m.end()          # m.end() уже стоит ПОСЛЕ закрывающей скобки
            dropped += 1
    out.append(css[pos:])
    css = ''.join(out)
    css = css.replace('<style>', '').replace('</style>', '').strip()

    header = (
        '/* Font Awesome Free 6.4.0 (CC BY 4.0) — ПОДМНОЖЕСТВО: %d иконок из ~2000.\n'
        '   Собрано tools/build.py. Шрифт — один файл fa-solid-900.woff2 (%s),\n'
        '   вместо трёх одинаковых base64-копий по 150 КБ внутри CSS. */\n'
        '@font-face{font-family:"Font Awesome 6 Free";font-style:normal;font-weight:900;'
        'font-display:block;src:url(fa-solid-900.woff2) format("woff2")}\n'
        % (len(keep), font_note))
    return header + css + '\n', keep, unresolved, dropped


# --------------------------------------------------------------------------- #
# 3. миниатюры артов
# --------------------------------------------------------------------------- #
def used_media(src_text):
    files = [f for f in sorted(os.listdir(MEDIA))
             if os.path.isfile(os.path.join(MEDIA, f))]
    return [f for f in files if ('media/' + f) in src_text]


def all_media_images():
    """ВСЕ картинки media/ (облачный каталог ссылается на них напрямую)"""
    out = []
    for f in sorted(os.listdir(MEDIA)):
        p = os.path.join(MEDIA, f)
        if os.path.isfile(p) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            out.append(f)
    return out


def build_thumbs(files, force=False):
    """Два уровня: media/t/ (256px) для списков и media/t2/ (512px) для сеток.
       Полноразмерные мастера не трогаем — просмотр карты остаётся 1:1."""
    from PIL import Image
    os.makedirs(THUMBS, exist_ok=True)
    os.makedirs(MIDS, exist_ok=True)
    small, mid = {}, {}
    made = skipped = 0
    src_bytes = th_bytes = mid_bytes = 0
    src_px = th_px = mid_px = 0

    def encode(im, w, q, dst, mtime_ref):
        if os.path.exists(dst) and not force and os.path.getmtime(dst) > mtime_ref:
            return False, Image.open(dst).size
        ww, hh = im.size
        tw = w if ww > w else ww
        th = max(1, round(hh * tw / ww))
        im.resize((tw, th), Image.LANCZOS).save(dst, 'WEBP', quality=q, method=6)
        return True, (tw, th)

    for f in files:
        src = os.path.join(MEDIA, f)
        base = os.path.splitext(f)[0]
        s1 = os.path.getsize(src)
        src_bytes += s1
        try:
            im = Image.open(src)
            im.load()
        except Exception as e:
            say('  ! не читается %s: %s' % (f, e))
            continue
        if im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGB')
        w, h = im.size
        src_px += w * h * 4

        d1 = os.path.join(THUMBS, base + '.webp')
        ch, sz = encode(im, THUMB_W, THUMB_Q, d1, os.path.getmtime(src))
        made += ch
        skipped += (not ch)
        small[f] = 'media/t/' + base + '.webp'
        th_bytes += os.path.getsize(d1)
        th_px += sz[0] * sz[1] * 4

        if w > MID_MIN_SRC:
            d2 = os.path.join(MIDS, base + '.webp')
            ch2, sz2 = encode(im, MID_W, MID_Q, d2, os.path.getmtime(src))
            mid[f] = 'media/t2/' + base + '.webp'
            mid_bytes += os.path.getsize(d2)
            mid_px += sz2[0] * sz2[1] * 4
        im.close()

    say('миниатюры: создано %d, уже были %d' % (made, skipped))
    say('  мастера : %6.1f МБ на диске, %5.0f МБ распакованных битмапов' %
        (src_bytes / 1048576, src_px / 1048576))
    say('  t/ 256px: %6.1f МБ на диске, %5.0f МБ распакованных битмапов (%d шт.)' %
        (th_bytes / 1048576, th_px / 1048576, len(small)))
    say('  t2/512px: %6.1f МБ на диске, %5.0f МБ распакованных битмапов (%d шт.)' %
        (mid_bytes / 1048576, mid_px / 1048576, len(mid)))
    return small, mid


# --------------------------------------------------------------------------- #
# 4. правки кода игры
# --------------------------------------------------------------------------- #
def patch_once(text, old, new, label, required=True):
    n = text.count(old)
    if n == 0:
        if required:
            raise AssertionError('патч не найден: ' + label)
        say('  · %s — не найдено (пропущено)' % label)
        return text, 0
    text = text.replace(old, new, 1)
    say('  · %s (%d вхожд.)' % (label, n))
    return text, n


def patch_all(text, old, new, label):
    n = text.count(old)
    if n:
        text = text.replace(old, new)
    say('  · %s: %d' % (label, n))
    return text, n


def add_img_attrs(html):
    """loading=lazy + decoding=async каждому <img src=...> — без этого браузер
       декодирует все картинки списка сразу: ~1.3 МБ битмапы на карту."""
    added_l = added_d = 0

    def fix(m):
        nonlocal added_l, added_d
        tag = m.group(0)
        if 'src=' not in tag:
            return tag
        if 'loading=' not in tag:
            tag = tag[:-1].rstrip() + ' loading="lazy">'
            added_l += 1
        if 'decoding=' not in tag:
            tag = tag[:-1].rstrip() + ' decoding="async">'
            added_d += 1
        return tag

    return re.sub(r'<img\b[^>]*>', fix, html), added_l, added_d


# места, где карта показывается МЕЛКО (<= ~180 css px) — там достаточно миниатюры
THUMB_SITES = [
    ('биржа, вид списком (40-48px)',
     '''<img src="${mediaUrl(c.image)}" alt="${cloudEsc(c.name || '')}" loading="lazy" onerror="this.onerror=null;imgErrorChain(this);" class="w-full h-full object-cover">''',
     '''<img src="${mediaThumb(c.image)}" data-nx-full="${mediaUrl(c.image)}" alt="${cloudEsc(c.name || '')}" loading="lazy" onerror="this.onerror=null;imgErrorChain(this);" class="w-full h-full object-cover">'''),
    ('колода, список бойцов (88px)',
     '''<img src="${mediaUrl(c.image)}" alt="${c.name}" class="w-full h-20 object-cover rounded-lg" onerror="imgErrorChain(this);" data-card-id="${c.id}">''',
     '''<img src="${mediaThumb(c.image)}" data-nx-full="${mediaUrl(c.image)}" alt="${c.name}" class="w-full h-20 object-cover rounded-lg" onerror="imgErrorChain(this);" data-card-id="${c.id}">'''),
    ('колода, выбор карты (56px)',
     '''<img src="${mediaUrl(c.image)}" alt="${c.name}" class="w-full h-14 object-cover rounded" onerror="imgErrorChain(this);" data-card-id="${c.id}">''',
     '''<img src="${mediaThumb(c.image)}" data-nx-full="${mediaUrl(c.image)}" alt="${c.name}" class="w-full h-14 object-cover rounded" onerror="imgErrorChain(this);" data-card-id="${c.id}">'''),
    ('арена, выбор замены (96px)',
     '''<img src="${mediaUrl(x.f.image)}" class="w-full h-16 object-cover rounded-lg" onerror="imgErrorChain(this);" data-card-id="${x.f.cardId || ''}">''',
     '''<img src="${mediaThumb(x.f.image)}" data-nx-full="${mediaUrl(x.f.image)}" class="w-full h-16 object-cover rounded-lg" onerror="imgErrorChain(this);" data-card-id="${x.f.cardId || ''}">'''),
    ('арена, карточка бойца (80x112)',
     '''<img src="${mediaUrl(f.image)}" alt="${f.name}" class="w-20 h-28 object-cover rounded-xl shadow-lg shrink-0" onerror="imgErrorChain(this);" data-card-id="${f.cardId || ''}">''',
     '''<img src="${mediaThumb(f.image)}" data-nx-full="${mediaUrl(f.image)}" alt="${f.name}" class="w-20 h-28 object-cover rounded-xl shadow-lg shrink-0" onerror="imgErrorChain(this);" data-card-id="${f.cardId || ''}">'''),
    ('альбом, вид «строки» (36-44px)',
     '''<img src="${mediaUrl(card.image)}" alt="${card.name}" onerror="imgErrorChain(this);" class="absolute inset-0 w-full h-full object-cover">''',
     '''<img src="${mediaThumb(card.image)}" data-nx-full="${mediaUrl(card.image)}" alt="${card.name}" onerror="imgErrorChain(this);" class="absolute inset-0 w-full h-full object-cover">'''),
    ('студия, список паков (28x40)',
     '''<img src="${mediaUrl(p.image)}" class="w-7 h-10 object-cover rounded shrink-0" onerror="this.onerror=null;imgErrorChain(this);">''',
     '''<img src="${mediaThumb(p.image)}" data-nx-full="${mediaUrl(p.image)}" class="w-7 h-10 object-cover rounded shrink-0" onerror="this.onerror=null;imgErrorChain(this);">'''),
    ('студия, список карт (28x40)',
     '''<img src="${mediaUrl(c.image)}" class="w-7 h-10 object-cover rounded" onerror="imgErrorChain(this);" data-card-id="${c.id}">''',
     '''<img src="${mediaThumb(c.image)}" data-nx-full="${mediaUrl(c.image)}" class="w-7 h-10 object-cover rounded" onerror="imgErrorChain(this);" data-card-id="${c.id}">'''),
]

# крупные сетки, где карт может быть 100+ — добавляем класс отложенной отрисовки
CV_SITES = [
    ('альбом: карточка (обычная)',
     '''<div onclick="inspectCard('${card.id}')" class="relative w-full card-aspect rounded-2xl border-2 ${getRarityClass(card.rarity)} ${cardHoloClass(card)} p-3 sm:p-4''',
     '''<div onclick="inspectCard('${card.id}')" class="nx-cv relative w-full card-aspect rounded-2xl border-2 ${getRarityClass(card.rarity)} ${cardHoloClass(card)} p-3 sm:p-4'''),
    ('альбом: карточка (компакт)',
     '''<div onclick="inspectCard('${card.id}')" class="relative w-full card-aspect rounded-xl border-2 ${getRarityClass(card.rarity)} ${cardHoloClass(card)} p-1.5 sm:p-2''',
     '''<div onclick="inspectCard('${card.id}')" class="nx-cv relative w-full card-aspect rounded-xl border-2 ${getRarityClass(card.rarity)} ${cardHoloClass(card)} p-1.5 sm:p-2'''),
    ('альбом: строка',
     '''<div onclick="inspectCard('${card.id}')" class="group flex items-center gap-2.5 sm:gap-3 rounded-xl border border-slate-800/80 bg-slate-900/60 p-2''',
     '''<div onclick="inspectCard('${card.id}')" class="nx-cv group flex items-center gap-2.5 sm:gap-3 rounded-xl border border-slate-800/80 bg-slate-900/60 p-2'''),
    ('биржа: строка лота',
     '''<div class="group flex items-center gap-2.5 rounded-xl border p-1.5 sm:p-2 transition-all duration-200 ${mine''',
     '''<div class="nx-cv group flex items-center gap-2.5 rounded-xl border p-1.5 sm:p-2 transition-all duration-200 ${mine'''),
    ('биржа: плитка лота',
     '''<div class="group relative rounded-xl border p-1.5 transition-all duration-200 flex flex-col gap-1.5 ${mine''',
     '''<div class="nx-cv group relative rounded-xl border p-1.5 transition-all duration-200 flex flex-col gap-1.5 ${mine'''),
]

# Альбом: уровень арта выбирается по виду сетки. «Галерея» (1 колонка на
# телефоне, карта ~358 css px) и просмотр карты остаются на полном арте —
# там качество видно. Остальные виды (2-8 колонок, ~120-180 css px) берут
# среднюю миниатюру 512px: на экране разница неотличима, а памяти в 4 раза меньше.
ALBUM_SITES = [
    ('albumCardHTML: выбор уровня арта',
     '            const compact = !!(opts && opts.compact);',
     '''            const compact = !!(opts && opts.compact);
            // 'full' — полный арт, 'mid' — 512px, 'thumb' — 256px (по умолчанию)
            const artTier = (opts && opts.art) || (compact ? 'thumb' : 'mid');
            const artFn = artTier === 'full' ? mediaUrl : (artTier === 'mid' ? mediaThumbMid : mediaThumb);'''),
    ('albumCardHTML: <img> обеих веток (компакт + обычная)',
     '''<img src="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);" loading="lazy" decoding="async" class="absolute inset-0 w-full h-full object-cover z-0 group-hover:scale-105 transition duration-500">''',
     '''<img src="${artFn(card.image)}" data-nx-full="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);" loading="lazy" decoding="async" class="absolute inset-0 w-full h-full object-cover z-0 group-hover:scale-105 transition duration-500">'''),
    ('renderAlbumGrid: вид «альбом» (страницы по 9)',
     "pg.map(c => albumCardHTML(c)).join('')",
     "pg.map(c => albumCardHTML(c, { art: 'mid' })).join('')"),
    ('renderAlbumGrid: сетка/галерея/компакт',
     "visible.map(c => albumCardHTML(c, { compact: cv === 'compact' })).join('')",
     "visible.map(c => albumCardHTML(c, { compact: cv === 'compact', art: cv === 'gallery' ? 'full' : (cv === 'compact' ? 'thumb' : 'mid') })).join('')"),
    # вскрытие пака: карта ~176 css px, но её рассматривают — берём 512px.
    # Отличается от просмотра карты отступом в 24 пробела (у просмотра — 16),
    # поэтому полный арт в модалке inspectCard остаётся нетронутым.
    ('вскрытие пака: карта на столе',
     '''                        <img src="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);" class="absolute inset-0 w-full h-full object-cover z-0">''',
     '''                        <img src="${mediaThumbMid(card.image)}" data-nx-full="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);" class="absolute inset-0 w-full h-full object-cover z-0">'''),
]

# Витрина магазина и 3D-карусель паков. Именно они давали ~63 МБ распакованных
# битмапов ещё на СТАРТОВОМ экране: обложка пака показывается размером 176x235
# css-пикселей, а грузится арт 1152x2048 (9.0 МБ в памяти) или 1080x1920 (7.9 МБ).
# Пять плиток + пять «окон» бустера + панель выбранного пака = весь бюджет памяти
# WebView Telegram. На телефонах это и есть «игра вылетает / закрывается браузер».
PACK_SITES = [
    ('витрина: плитка пака (176x235 css)',
     '''<img src="${mediaUrl(pack.image)}" alt="${pack.title}" loading="lazy" onerror="this.onerror=null;imgErrorChain(this);">''',
     '''<img src="${mediaThumbMid(pack.image)}" data-nx-full="${mediaUrl(pack.image)}" alt="${pack.title}" loading="lazy" decoding="async" onerror="this.onerror=null;imgErrorChain(this);">''',
     1),
    ('карусель: «окно» бустера + панель выбранного пака (77-142 css)',
     '''<img src="${mediaUrl(pack.image)}" alt="${pack.title}" class="w-full h-full object-cover" onerror="this.onerror=null;imgErrorChain(this);">''',
     '''<img src="${mediaThumbMid(pack.image)}" data-nx-full="${mediaUrl(pack.image)}" alt="${pack.title}" class="w-full h-full object-cover" loading="lazy" decoding="async" onerror="this.onerror=null;imgErrorChain(this);">''',
     2),
    ('альбомы: обложка пака в сетке',
     '''<img src="${mediaUrl(pack.image)}" alt="${pack.title}" class="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-[1.07]" onerror="this.onerror=null;imgErrorChain(this);">''',
     '''<img src="${mediaThumbMid(pack.image)}" data-nx-full="${mediaUrl(pack.image)}" alt="${pack.title}" class="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-[1.07]" loading="lazy" decoding="async" onerror="this.onerror=null;imgErrorChain(this);">''',
     1),
    ('альбомы: обложка пака в списке (56-64 css)',
     '''<img src="${mediaUrl(pack.image)}" alt="${pack.title}" class="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.06]" onerror="this.onerror=null;imgErrorChain(this);">''',
     '''<img src="${mediaThumb(pack.image)}" data-nx-full="${mediaUrl(pack.image)}" alt="${pack.title}" class="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.06]" loading="lazy" decoding="async" onerror="this.onerror=null;imgErrorChain(this);">''',
     1),
    ('альбом: обложка в шапке (56-80 css)',
     '''<img src="${mediaUrl(pack.image)}" alt="" class="absolute inset-0 w-full h-full object-cover" onerror="this.onerror=null;imgErrorChain(this);">''',
     '''<img src="${mediaThumb(pack.image)}" data-nx-full="${mediaUrl(pack.image)}" alt="" class="absolute inset-0 w-full h-full object-cover" loading="lazy" decoding="async" onerror="this.onerror=null;imgErrorChain(this);">''',
     1),
    ('мокап бустера (вскрытие/превью)',
     '''<img src="${mediaUrl(image)}" alt="" class="w-full h-full object-cover" onerror="this.onerror=null;imgErrorChain(this);">''',
     '''<img src="${mediaThumbMid(image)}" data-nx-full="${mediaUrl(image)}" alt="" class="w-full h-full object-cover" loading="lazy" decoding="async" onerror="this.onerror=null;imgErrorChain(this);">''',
     1),
]

# Предзагрузка каталога. Раньше preloadAllGameImages() ставила в очередь ПОЛНЫЕ
# арты всех карт и паков. Для облачной комнаты это 156 файлов, из них 82 —
# PNG 1080x1920/1152x2048 по 2-4 МБ: ~157 МБ фонового трафика на старте,
# параллельно с витриной. На мобильной сети это минуты загрузки, забитый канал
# (картинки витрины не успевали) и непрерывная запись в IndexedDB.
# Теперь греются миниатюры: ~3 МБ вместо ~157 МБ.
PRELOAD_PATCHES = [
    ('preloadImages: греем миниатюры вместо полных артов',
     '''        function preloadImages(urls) {
            (urls || []).forEach(raw => {
                if (!raw || typeof raw !== 'string') return;
                const u = mediaUrl(raw);
                if (!u || u.indexOf('http') !== 0 || IMG_PRELOADED.has(u) || imgQueue.indexOf(u) >= 0) return;
                imgQueue.push(u);
            });
            imgPump();
        }''',
     '''        function preloadImages(urls, tier) {
            (urls || []).forEach(raw => {
                if (!raw || typeof raw !== 'string') return;
                // tier='full' — греть полный арт (нужно только для просмотра карты).
                // По умолчанию греем миниатюру 256px: полный арт облачного каталога
                // весит 2-4 МБ и показывается в списках размером 30-180 px.
                let u = mediaUrl(raw);
                if (tier !== 'full') { const t = mediaThumb(raw); if (t) u = t; }
                if (!u || u.indexOf('http') !== 0 || IMG_PRELOADED.has(u) || imgQueue.indexOf(u) >= 0) return;
                imgQueue.push(u);
            });
            imgPump();
        }'''),
    ('injectPosterPreloads: <link rel=preload> на среднюю миниатюру',
     '''                    const u = mediaUrl(p.image);
                    if (IMG_OBJ.has(u)) return; // b180: постер уже в постоянном кэше — preload не нужен''',
     '''                    const u = mediaThumbMid(p.image) || mediaUrl(p.image);
                    if (IMG_OBJ.has(u)) return; // b180: постер уже в постоянном кэше — preload не нужен'''),
]

# loadImgSafe грузит арт для холста/WebGL-текстуры. Все её потребители рисуют
# на холст не крупнее 512x768 (текстура пака для three.js — 512x768, символы
# слотов — 224x512, «линии» — 256x368, карта в арене), но грузился ПОЛНЫЙ мастер:
# 1152x2048 = 9.0 МБ распакованной битмапы и 2-4 МБ трафика на каждый пак.
# Карусель магазина строит 5+ таких текстур на старте — отсюда десятки
# мегабайт и сотни мегабайт трафика ещё до первого клика.
LOADIMG_PATCH = (
    'loadImgSafe: текстуры из миниатюры 512px вместо мастера 1152x2048',
    '''            const first = mediaUrl(src);
            const cands = [first];
            if (first !== src) cands.push(src);''',
    '''            const first = mediaUrl(src);
            // Все потребители loadImgSafe рисуют арт на холст не крупнее 512x768,
            // поэтому сначала пробуем среднюю миниатюру 512px (1.8 МБ в памяти
            // вместо 9.0 МБ, ~60 КБ трафика вместо 2-4 МБ). Мастер — запасной
            // вариант: если миниатюры для файла нет, nxThumbFor вернёт пустоту.
            const mid = mediaThumbMid(src);
            const cands = [];
            if (mid && mid !== first) cands.push(mid);
            cands.push(first);
            if (first !== src) cands.push(src);''')

THUMB_HELPERS = '''
        // ===== УРОВНИ АРТОВ (tools/build.py) =====
        // Почему это главное исправление вылетов на телефоне:
        // каталог карт приходит из облака комнаты и ссылается на media/card_*.png
        // размером 1080x1920 и 1152x2048. Распакованная битмапа такого арта —
        // 7.9 и 9.0 МБ СООТВЕТСТВЕННО, а показывается он в списке размером
        // 76-176 css-пикселей. Стартовый экран держал ~63 МБ битмапов на 12
        // картинках; полный альбом — сотни мегабайт. iOS/Android убивают WebView.
        //
        // Теперь три уровня:
        //   media/t/  256px — списки, строки, компактные сетки  (~0.47 МБ в памяти)
        //   media/t2/ 512px — обычные сетки, вскрытие пака       (~1.9 МБ в памяти)
        //   мастер        — просмотр карты и вид «галерея» (1:1, как было)
        // Полноразмерные арты не пережаты и не изменены: там, где карта
        // показывается крупной, картинка осталась ровно той же.
        /*NX_EMBED_THUMB_START*/
        const NX_EMBED_THUMB = __THUMB_MAP__;
        const NX_EMBED_THUMB_MID = __THUMB_MID_MAP__;
        /*NX_EMBED_THUMB_END*/
        function nxThumbFor(u, tier) {
            try {
                const s = String(u == null ? '' : u);
                if (!s) return '';
                const full = mediaUrl(s);              // уже с учётом зеркала и NX_EMBED_MEDIA
                if (!full) return '';
                const map = (tier === 'mid') ? NX_EMBED_THUMB_MID : NX_EMBED_THUMB;
                const rel = map[nxMediaKey(full)] || map[nxMediaKey(s)];
                if (!rel) return '';                   // для этого файла миниатюры нет
                if (full.indexOf('http') !== 0) return rel;   // локальный арт — путь относительный
                // облачная/зеркальная ссылка: миниатюра лежит рядом с мастером,
                // подменяем только каталог media/ -> media/t/ (или media/t2/)
                const i = full.lastIndexOf('/media/');
                if (i < 0) return rel;
                return full.slice(0, i + 7) + rel.slice(6);
            } catch (e) { return ''; }
        }
        function mediaThumb(u) {                       // 256px
            return nxThumbFor(u, 'small') || mediaUrl(u);
        }
        function mediaThumbMid(u) {                    // 512px, иначе мелкая, иначе мастер
            return nxThumbFor(u, 'mid') || nxThumbFor(u, 'small') || mediaUrl(u);
        }
'''

THUMB_ERROR_FALLBACK = '''                // миниатюра не отдалась (папки media/t/ или media/t2/ ещё не
                // задеплоены, файл битый, арт добавили после сборки) — показываем
                // полный арт: карта не должна оставаться заглушкой
                if (!el.__nxThumbTried && /\\/media\\/t2?\\//.test(u)) {
                    el.__nxThumbTried = 1;
                    const full = el.getAttribute && el.getAttribute('data-nx-full');
                    if (full && full !== u) { el.onerror = null; el.style.display = ''; el.src = full; return true; }
                }
'''

MEMGUARD_OLD = "        if (mb < 350) return; // b318: пороги ниже — WebView Telegram живёт в меньшем лимите"
MEMGUARD_NEW = """        // Порог не абсолютный: на слабых Android jsHeapSizeLimit бывает ~256 МБ,
        // и фиксированные 350 МБ не достигались НИКОГДА — сторож просто не работал.
        let lim = 350;
        try { if (pm.jsHeapSizeLimit > 0) lim = Math.min(350, Math.floor(pm.jsHeapSizeLimit / 1048576 * 0.55)); } catch (e) {}
        if (lim < 120) lim = 120;
        if (mb < lim) return; // b318: WebView Telegram живёт в меньшем лимите"""

PIXELRATIO_OLD = """        function nxPixelRatio() { // b308: слабый GPU держит контекст живее без ретины 2x
            try {
                const d = window.devicePixelRatio || 1;
                const mob = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
                return Math.min(d, mob ? 1.5 : 2);
            } catch (e) { return 1; }
        }"""
PIXELRATIO_NEW = """        function nxLowRam() { // устройство с малой памятью / слабым CPU
            try {
                const dm = navigator.deviceMemory;               // Chrome/Android
                if (typeof dm === 'number' && dm > 0 && dm <= 3) return true;
                const hc = navigator.hardwareConcurrency;
                if (typeof hc === 'number' && hc > 0 && hc <= 3) return true;
            } catch (e) {}
            return false;
        }
        function nxPixelRatio() { // b308: слабый GPU держит контекст живее без ретины 2x
            try {
                const d = window.devicePixelRatio || 1;
                const mob = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
                // 1080x1920 канвас с DPR 3 = 3240x5760 = 74 МБ видеопамяти на ОДИН
                // рендерер. На устройствах с малой памятью режем до 1.0.
                return Math.min(d, mob ? (nxLowRam() ? 1 : 1.5) : 2);
            } catch (e) { return 1; }
        }"""

TAILWIND_GUARD_OLD = """            if (typeof window.tailwind === 'undefined') {
                setTimeout(() => showToast('⚠️ Нет доступа к CDN: стили/3D не загрузились. Откройте файл в браузере с интернетом', 'error'), 300);
            }"""
TAILWIND_GUARD_NEW = """            // Tailwind прекомпилирован в assets/tailwind.css — window.tailwind
            // больше не существует, и это нормально. Проверяем саму таблицу стилей.
            if (!document.getElementById('nx-tw-css')) {
                setTimeout(() => showToast('⚠️ Не загрузились стили (assets/tailwind.css). Проверьте подключение и обновите страницу', 'error'), 300);
            }"""

WATCHDOG_OLD = """        setInterval(() => {
            try {
                const imgs = document.images;
                for (let i = 0; i < imgs.length; i++) {
                    const el = imgs[i];
                    if (el.__nxPh || el.__nxWatch) continue;"""
WATCHDOG_NEW = """        setInterval(() => {
            try {
                if (document.hidden) return; // в фоне не сканируем: WebView и так под нагрузкой
                const imgs = document.images;
                for (let i = 0; i < imgs.length; i++) {
                    const el = imgs[i];
                    if (el.__nxPh || el.__nxWatch) continue;"""

TG_HARDENING = '''
// ===== Telegram Mini App / мобильная стабилизация (tools/build.py) =====
(function () {
    'use strict';
    function tg() {
        try { return (window.Telegram && window.Telegram.WebApp) || null; } catch (e) { return null; }
    }
    function harden() {
        var w = tg();
        if (!w) return;
        // Развернуть на весь экран: без этого мини-апп остаётся в маленьком окне,
        // а игра верстается под 100vh и получает обрезанный низ.
        try { w.expand(); } catch (e) {}
        // iOS: свайп сверху вниз закрывает мини-апп. Во время анимации вскрытия
        // пака или прокрутки альбома это срабатывает случайно — «игра сама закрылась».
        // Кнопка «Закрыть» при этом продолжает работать.
        try { if (w.disableVerticalSwipes) w.disableVerticalSwipes(); } catch (e) {}
        try { if (w.enableClosingConfirmation) w.enableClosingConfirmation(); } catch (e) {}
        // Клавиатура в WebView не двигает viewport — ловим сами, чтобы поле ввода
        // не уезжало под клавиатуру.
        try {
            if (w.onEvent) w.onEvent('viewportChanged', function () {
                try { window.dispatchEvent(new Event('resize')); } catch (e) {}
            });
        } catch (e) {}
    }
    if (tg()) harden();
    else {
        // telegram-web-app.js подгружается асинхронно — дожидаемся
        var tries = 0;
        var t = setInterval(function () {
            if (tg() || ++tries > 40) { clearInterval(t); harden(); }
        }, 100);
    }
    // WebView Telegram замораживают, а не закрывают: pagehide может не прийти.
    // Сохраняемся на всех сигналах, иначе прогресс теряется при убийстве процесса.
    ['pagehide', 'freeze', 'visibilitychange'].forEach(function (ev) {
        window.addEventListener(ev, function () {
            try {
                if (ev === 'visibilitychange' && !document.hidden) return;
                if (typeof saveState === 'function') saveState();
            } catch (e) {}
        }, { passive: true });
    });
    // iOS Safari не даёт performance.memory — сторож памяти там молчал.
    // Дублируем его грубой, но работающей везде оценкой: сколько распакованных
    // битмапов держат <img> на странице.
    setInterval(function () {
        try {
            if (document.hidden) return;
            var imgs = document.images, bytes = 0, heavy = 0;
            for (var i = 0; i < imgs.length; i++) {
                var el = imgs[i];
                if (!el.complete || !el.naturalWidth) continue;
                if (!el.getBoundingClientRect) continue;
                var r = el.getBoundingClientRect();
                // за экраном битмап браузеру не нужна — не считаем
                if (r.bottom < -200 || r.top > (window.innerHeight || 800) + 200) continue;
                var b = el.naturalWidth * el.naturalHeight * 4;
                bytes += b;
                if (b > 2 * 1024 * 1024) heavy++;
            }
            var mb = bytes / 1048576;
            if (mb > 160 || heavy > 24) {
                // снимаем src у крупных картинок ЗА экраном — WebKit освободит битмапы
                var freed = 0;
                for (var j = 0; j < imgs.length; j++) {
                    var im = imgs[j];
                    if (!im.complete || !im.naturalWidth || im.__nxUnloaded) continue;
                    if (im.naturalWidth * im.naturalHeight * 4 < 400000) continue;
                    var rr = im.getBoundingClientRect();
                    if (rr.bottom < -600 || rr.top > (window.innerHeight || 800) + 600) {
                        im.__nxUnloaded = im.src;
                        im.removeAttribute('src');
                        freed++;
                    }
                }
                if (freed) {
                    try { nxCrashLog('imgguard: на экране ~' + Math.round(mb) + ' МБ битмапов, выгружено ' + freed); } catch (e) {}
                }
            }
        } catch (e) {}
    }, 8000);
})();
'''

APP_CSS_EXTRA = '''

/* ============================================================
   Дополнения мобильной сборки (tools/build.py)
   ============================================================ */

/* Отложенная отрисовка длинных списков. content-visibility:auto велит браузеру
   не считать layout и не рисовать то, что за пределами экрана; contain-intrinsic-size
   reserves место, чтобы полоса прокрутки не прыгала. В альбоме/на бирже бывает
   100-300 карточек — это главный источник подвисаний при прокрутке на телефоне.
   Браузеры без поддержки просто игнорируют правило. */
@supports (content-visibility: auto) {
    .nx-cv {
        content-visibility: auto;
        contain-intrinsic-size: auto 300px;
    }
}

/* iPhone: вырез/чёлка и нижняя полоса не должны перекрывать интерфейс */
@supports (padding: env(safe-area-inset-top)) {
    body {
        padding-top: env(safe-area-inset-top);
        padding-bottom: env(safe-area-inset-bottom);
        padding-left: env(safe-area-inset-left);
        padding-right: env(safe-area-inset-right);
    }
}

/* Меньше «резиновых» перерисовок при прокрутке на слабых GPU */
@media (max-width: 1023px) {
    .nx-cv { will-change: auto; }
}
'''

SW_JS = '''/* nx-media-sw v2 (%s): cache-first для media/ и assets/, network-first для HTML.
   Арты и скрипты скачиваются с сервера ОДИН раз на браузер; дальше отдаются из
   кэша мгновенно — в Telegram Mini App повторное открытие становится мгновенным
   и работает без сети. Тихая сверка с сервером — не чаще раза в 7 дней на файл. */
const VERSION = '%s';
const CACHE_MEDIA = 'nx-media-v2';
const CACHE_ASSETS = 'nx-assets-' + VERSION;
const CACHE_PAGES = 'nx-pages-' + VERSION;
const MAX_ENTRIES = 500;
const REVALIDATE_MS = 7 * 24 * 60 * 60 * 1000;

self.addEventListener('install', e => {
    self.skipWaiting();
});
self.addEventListener('activate', e => {
    e.waitUntil((async () => {
        // старые версии кэшей не копятся: на слабом телефоне место на вес золота
        const keep = [CACHE_MEDIA, CACHE_ASSETS, CACHE_PAGES];
        for (const k of await caches.keys()) if (keep.indexOf(k) < 0) await caches.delete(k);
        await self.clients.claim();
    })());
});

self.addEventListener('message', e => {
    if (e && e.data === 'nx-skip-waiting') self.skipWaiting();
});

self.addEventListener('fetch', e => {
    const req = e.request;
    if (req.method !== 'GET') return;
    const url = new URL(req.url);
    if (url.origin !== self.location.origin) return;

    const p = url.pathname;
    if (p.indexOf('/media/') >= 0) { e.respondWith(mediaFirst(e, url, CACHE_MEDIA)); return; }
    if (p.indexOf('/assets/') >= 0) { e.respondWith(mediaFirst(e, url, CACHE_ASSETS)); return; }
    if (req.mode === 'navigate' || /\\.html?$/.test(p) || p.endsWith('/')) {
        e.respondWith(pageFirst(e, req));
    }
});

/* вечный cache-first: файл неизменяем, сверяемся редко и только в фоне */
async function mediaFirst(e, url, cacheName) {
    const bypass = url.searchParams.has('nxcb');
    const cache = await caches.open(cacheName);
    if (!bypass) {
        const hit = await cache.match(e.request.url, { ignoreSearch: true });
        if (hit) {
            const ts = Number(hit.headers.get('x-nx-ts') || 0);
            if (Date.now() - ts > REVALIDATE_MS) e.waitUntil(refresh(cache, e.request));
            return hit;
        }
    }
    try {
        const resp = await fetch(e.request);
        if (resp.ok && !bypass) e.waitUntil(store(cache, e.request, resp.clone()));
        return resp;
    } catch (err) {
        const stale = await cache.match(e.request.url, { ignoreSearch: true });
        if (stale) return stale;
        throw err;
    }
}

/* HTML: сначала сеть (иначе игрок застрянет на старой версии), кэш — запасной выход */
async function pageFirst(e, req) {
    const cache = await caches.open(CACHE_PAGES);
    try {
        const resp = await fetch(req);
        if (resp.ok) e.waitUntil(cache.put(req, resp.clone()));
        return resp;
    } catch (err) {
        const stale = await cache.match(req) || await cache.match('./');
        if (stale) return stale;
        throw err;
    }
}

async function store(cache, req, resp) {
    try {
        const headers = new Headers(resp.headers);
        headers.set('x-nx-ts', String(Date.now()));
        const body = await resp.blob();
        await cache.put(req, new Response(body, { status: resp.status, statusText: resp.statusText, headers: headers }));
        await trim(cache);
    } catch (e) {}
}

async function refresh(cache, req) {
    try {
        const resp = await fetch(req, { cache: 'no-store' });
        if (resp.ok) await store(cache, req, resp.clone());
    } catch (e) {}
}

async function trim(cache) {
    try {
        const keys = await cache.keys();
        if (keys.length <= MAX_ENTRIES) return;
        const stamped = [];
        for (const k of keys) {
            const r = await cache.match(k);
            stamped.push([Number((r && r.headers.get('x-nx-ts')) || 0), k]);
        }
        stamped.sort((a, b) => a[0] - b[0]);
        const drop = keys.length - MAX_ENTRIES;
        for (let i = 0; i < drop; i++) await cache.delete(stamped[i][1]);
    } catch (e) {}
}
'''


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    argv = sys.argv[1:]
    no_media = '--no-media' in argv

    if not os.path.exists(SRC):
        print('нет tools/source-index.html — положите туда текущий index.html')
        return 1
    os.makedirs(ASSETS, exist_ok=True)

    lines = read_lines(SRC)
    src_text = '\r\n'.join(lines)
    say('источник: %d строк, %.2f МБ' % (len(lines), len(src_text.encode()) / 1048576))

    # --- извлекаем блоки ------------------------------------------------- #
    three_js = inner(lines, 'three')
    app_js = inner(lines, 'app_js')
    stories_js = inner(lines, 'stories')
    qrcode_js = inner(lines, 'qrcode')
    qrxfer_js = inner(lines, 'qr_xfer')
    app_css = inner(lines, 'app_css')
    fa_css = inner(lines, 'fa')

    # --- миниатюры -------------------------------------------------------- #
    # Для ВСЕХ файлов media/: облачный каталог комнаты ссылается на card_*.png
    # напрямую, в HTML этих имён нет, но без миниатюр именно они роняют телефон.
    all_imgs = all_media_images()
    say('артов в media/: %d (в HTML упомянуто %d, остальные приходят из облака)'
        % (len(all_imgs), len(used_media(src_text))))
    thumb_map, mid_map = {}, {}
    if not no_media:
        thumb_map, mid_map = build_thumbs(all_imgs, force='--force-media' in argv)
    else:
        for f in all_imgs:
            b = os.path.splitext(f)[0]
            if os.path.exists(os.path.join(THUMBS, b + '.webp')):
                thumb_map[f] = 'media/t/' + b + '.webp'
            if os.path.exists(os.path.join(MIDS, b + '.webp')):
                mid_map[f] = 'media/t2/' + b + '.webp'
        say('миниатюры: пропущено (--no-media), найдено %d мелких / %d средних'
            % (len(thumb_map), len(mid_map)))

    # --- Font Awesome ----------------------------------------------------- #
    fa_scan = '\r\n'.join(lines[:BLOCKS['fa'][0] - 1] + lines[BLOCKS['fa'][1]:])
    used_icons = fa_used_icons(fa_scan)
    for bad, good in FA_FIXES.items():
        used_icons.discard(bad[3:])
        used_icons.add(good[3:])
    fa_out, keep, unresolved, dropped = build_fontawesome(fa_css, used_icons)
    say('Font Awesome: иконок %d (правлено битых имён: %d), CSS %d -> %d Б, правил удалено %d'
        % (len(keep), len(FA_FIXES), len(fa_css), len(fa_out), dropped))
    if unresolved:
        say('  ! не найдено в Font Awesome 6 Free: %s' % ', '.join(unresolved))
    write_lf(os.path.join(ASSETS, 'fa.css'), fa_out)
    say('  шрифт fa-solid-900.woff2: %d Б' % os.path.getsize(os.path.join(ASSETS, 'fa-solid-900.woff2')))

    # --- Tailwind --------------------------------------------------------- #
    tw_path = os.path.join(ASSETS, 'tailwind.css')
    if '--tw' in argv or not os.path.exists(tw_path):
        say('Tailwind: прекомпиляция через node ...')
        shutil.copy(SRC, os.path.join(ROOT, 'tools', '_tw_src.html'))
        r = subprocess.run(['node', os.path.join(ROOT, 'tools', 'twbuild.js')],
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode != 0:
            print(r.stdout, r.stderr)
            raise SystemExit('не удалось прекомпилировать Tailwind (нужен node + tailwindcss)')
        say('  ' + r.stdout.strip())
    say('Tailwind CSS: %d Б' % os.path.getsize(tw_path))

    # --- пишем ассеты ----------------------------------------------------- #
    def w(name, text):
        p = os.path.join(ASSETS, name)
        write_lf(p, text)
        say('assets/%-18s %8.1f КБ' % (name, os.path.getsize(p) / 1024))

    # сторож памяти живёт в блоке qr-transfer, а не в основном коде игры
    qrxfer_js, _n = patch_once(qrxfer_js, MEMGUARD_OLD, MEMGUARD_NEW,
                               'сторож памяти: относительный порог heap')

    w('three.min.js', three_js)
    w('qrcode.min.js', qrcode_js)
    w('stories.js', stories_js)
    w('qr-transfer.js', qrxfer_js)
    w('app.css', app_css + APP_CSS_EXTRA)

    # --- правим код игры -------------------------------------------------- #
    say('правки кода:')
    js = app_js

    js, _ = patch_all(js, 'fa-solid fa-sack-coins', 'fa-solid fa-sack-dollar',
                      'иконка fa-sack-coins (нет в FA Free) -> fa-sack-dollar')
    js, _ = patch_all(js, 'fa-solid fa-sparkles', 'fa-solid fa-wand-magic-sparkles',
                      'иконка fa-sparkles (нет в FA Free) -> fa-wand-magic-sparkles')

    anchor = '/*NX_EMBED_MEDIA_END*/'
    assert anchor in js, 'не найден маркер NX_EMBED_MEDIA_END'
    js = js.replace(anchor, anchor + THUMB_HELPERS
                    .replace('__THUMB_MAP__', json.dumps(thumb_map, ensure_ascii=False, sort_keys=True))
                    .replace('__THUMB_MID_MAP__', json.dumps(mid_map, ensure_ascii=False, sort_keys=True)), 1)
    say('  · добавлены mediaThumb()/mediaThumbMid(): %d мелких + %d средних миниатюр'
        % (len(thumb_map), len(mid_map)))

    for label, old, new in ALBUM_SITES:
        js, _ = patch_once(js, old, new, 'уровни артов: ' + label, required=False)
    for label, old, new, want in PACK_SITES:
        n = js.count(old)
        if n != want:
            say('  ! витрина/карусель «%s»: ожидалось %d вхождений, найдено %d' % (label, want, n))
        js = js.replace(old, new)
        say('  · %s (заменено %d)' % (label, n))
    for label, old, new in THUMB_SITES:
        js, _ = patch_once(js, old, new, 'миниатюры: ' + label, required=False)
    for label, old, new in PRELOAD_PATCHES:
        js, _ = patch_once(js, old, new, label)
    js, _ = patch_once(js, LOADIMG_PATCH[1], LOADIMG_PATCH[2], LOADIMG_PATCH[0])
    for label, old, new in CV_SITES:
        js, _ = patch_once(js, old, new, 'content-visibility: ' + label, required=False)

    js, _ = patch_once(js,
                       'const raw = el.__nxOrig || u;',
                       THUMB_ERROR_FALLBACK + '                const raw = el.__nxOrig || u;',
                       'фолбэк миниатюра -> полный арт в imgErrorChain')
    js, _ = patch_once(js, PIXELRATIO_OLD, PIXELRATIO_NEW, 'nxPixelRatio: учёт deviceMemory')
    js, _ = patch_once(js, TAILWIND_GUARD_OLD, TAILWIND_GUARD_NEW, 'убран ложный тост «нет CDN»')
    js, _ = patch_once(js, WATCHDOG_OLD, WATCHDOG_NEW, 'watchdog картинок: не работаем в фоне')

    js, n_l, n_d = add_img_attrs(js)
    say('  · <img>: добавлено loading="lazy" %d, decoding="async" %d' % (n_l, n_d))

    w('app.js', js)

    # --- собираем index.html --------------------------------------------- #
    say('сборка index.html:')
    v = BUILD_TAG
    head_new = [
        '    <!-- Мобильная сборка %s: тяжёлые библиотеки вынесены в assets/ и кешируются -->' % v,
        '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '    <!-- three.js нужен только в 3D-режимах и только по клику: defer не блокирует парсинг -->',
        '    <script src="assets/three.min.js?v=%s" defer></script>' % v,
        '    <link rel="stylesheet" href="assets/fa.css?v=%s">' % v,
        '    <!-- Inter грузится НЕ блокируя отрисовку: fonts.googleapis.com может быть',
        '         недоступен, и раньше страница висела до таймаута сети -->',
        '    <link rel="stylesheet" media="print" onload="this.media=\'all\'"',
        '          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap">',
        '    <noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"></noscript>',
        '    <link rel="stylesheet" href="assets/app.css?v=%s">' % v,
        '    <!-- ПРЕДКОМПИЛИРОВАННЫЙ Tailwind. Раньше здесь работал Tailwind Play CDN:',
        '         JIT-компилятор + PostCSS выполнялись В БРАУЗЕРЕ и пересобирали весь CSS',
        '         при каждой мутации DOM (~550 мс холодного прогона). На телефоне это',
        '         блокировало главный поток во время анимаций — отсюда подвисания и',
        '         закрытие WebView. Теперь CSS статический, а JS-компилятора нет вовсе. -->',
        '    <link id="nx-tw-css" rel="stylesheet" href="assets/tailwind.css?v=%s">' % v,
    ]

    # разметка тела: между <body> и первым скриптом игры (строки 1090..3611).
    # Скрипты 3612..20241 ушли в assets/ и подключаются отдельными тегами ниже.
    body = list(lines[BODY_OPEN:BLOCKS['app_js'][0] - 1])
    body_text = '\r\n'.join(body)
    for bad, good in FA_FIXES.items():
        c = body_text.count(bad)
        if c:
            body_text = body_text.replace(bad, good)
            say('  · разметка: %s -> %s (%d)' % (bad, good, c))
    body_text, bl, bd = add_img_attrs(body_text)
    say('  · разметка: <img> добавлено loading="lazy" %d, decoding="async" %d' % (bl, bd))

    out = []
    out.extend(lines[0:12])                            # 1..12: doctype … <meta charset>
    assert '<title>' in lines[16], 'строка 17 — не <title>: %r' % lines[16][:60]
    assert 'rel="icon"' in lines[17], 'строка 18 — не favicon: %r' % lines[17][:60]
    out.append(lines[16])                              # 17: <title>
    # пропускаем 3 no-cache мета-тега и старый viewport, ставим свой
    out.append('    <!-- Убраны <meta http-equiv="Cache-Control/Pragma/Expires" no-cache>:')
    out.append('         часть WebView честно их выполняла и каждый раз качала 3.2 МБ заново.')
    out.append('         Кешированием теперь занимается sw.js + версионирование ?v= -->')
    out.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">')
    out.append('    <meta name="theme-color" content="#020617">')
    out.append('    <meta name="mobile-web-app-capable" content="yes">')
    out.append('    <meta name="apple-mobile-web-app-capable" content="yes">')
    out.append('    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">')
    out.append('    <meta name="format-detection" content="telephone=no">')
    out.append(lines[17])                              # favicon
    out.extend(head_new)
    out.append('</head>')
    out.append(lines[BODY_OPEN - 1])                   # <body …>
    out.append(body_text)
    # скрипты в конце body — порядок как в оригинале
    out.append('    <!-- Код игры. Внешний файл: кешируется отдельно от разметки. -->')
    out.append('    <script src="assets/app.js?v=%s"></script>' % v)
    out.append('    <script src="assets/stories.js?v=%s"></script>' % v)
    out.append('    <script src="assets/qrcode.min.js?v=%s"></script>' % v)
    out.append('    <script src="assets/qr-transfer.js?v=%s"></script>' % v)
    out.append('    <script>%s</script>' % TG_HARDENING)
    out.append('</body>')
    out.append('</html>')

    html = '\r\n'.join(out)
    write_crlf(os.path.join(ROOT, 'index.html'), html)
    say('index.html: %.2f МБ -> %.2f МБ' % (len(src_text.encode()) / 1048576,
                                            len(html.encode()) / 1048576))

    # --- service worker --------------------------------------------------- #
    write_lf(os.path.join(ROOT, 'sw.js'), SW_JS % (v, v))
    say('sw.js: v2 (media/ + assets/ cache-first, HTML network-first)')

    # --- отчёт ------------------------------------------------------------ #
    total = sum(os.path.getsize(os.path.join(ASSETS, f))
                for f in os.listdir(ASSETS))
    say('assets/ всего: %.2f МБ' % (total / 1048576))
    say('')
    say('Первый визит качает: index.html + app.js + tailwind.css + fa.css + app.css + three.js')
    say('Повторный визит: всё из кэша SW, сеть не трогается.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
