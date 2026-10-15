#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b438: картинки карточек плохо грузятся — третий уровень артов media/t3/.

Заявка владельца: «КАРТИНКИ КАТОЧЕК ПЛОХО ГРУЗЯТСЯ ИЛИ НЕ ПРОГРУЖАЮТСЯ».

Диагноз: просмотр карты (inspectCard) и вид «галерея» в альбоме грузят
МАСТЕРА напрямую. Пак «Гарри Поттер» — это 4K PNG (2160x3840) по 10–16 МБ
на карту: на телефоне такая картинка грузится десятки секунд или не грузится
вовсе, а файл >8 МБ даже не сохраняется в постоянный кэш (IMG_CACHE_MAX_BLOB)
— каждое открытие заново качает 15 МБ. Галерея из 52 карт — это ~600 МБ.

Лечение — третий уровень артов:
  media/t3/<имя>.webp — длинная сторона ≤1440px, quality 80 (~0.1–0.3 МБ).
Карта на экране крупнее 1440px не показывается никогда, поэтому визуально
ничего не меняется, а грузится в ~50 раз быстрее и влезает в постоянный кэш.

Что делает патч (assets/app.js):
  1. NX_EMBED_BIG — карта «мастер -> media/t3/» (заполняет sync_thumb_maps.py,
     в CI — после tools/thumbs_for_media.py, который теперь строит t3);
  2. mediaBig()/nxBigFor(): t3 из карты; ключа нет (лёгкий мастер или арт
     новее сборки) — мастер, как раньше; подтверждённый 404 тизерится
     общей мемоизацией NX_THUMB_404;
  3. inspectCard: src=mediaBig + data-nx-full=мастер (последний резерв);
     прогрев «больших» артов соседей ±2 — свайп по списку мгновенный;
  4. галерея альбома (artTier 'full'): mediaUrl -> mediaBig;
  5. nxProgressiveAttach: для src из media/t3/ мгновенно показывает 512px
     миниатюру (nxDownTierUrl), затем тихо подменяет на t3 — картинка в
     просмотре появляется сразу;
  6. imgErrorChain: регулятор производных /media\\/t2?\\// -> /media\\/t[23]?\\//
     (t3 не прогрузился — откат на data-nx-full, как у t/t2);
  7. preloadImages: новый tier='big' (прогрев mediaBig).
  8. Тег сборки nxmob157 -> nxmob158 (index.html ?v= x8, sw.js VERSION,
     tools/build.py BUILD_TAG).

Проверка/применение:
    python3 tools/_b438_patch.py --check   # только проверить, что всё легло
    python3 tools/_b438_patch.py           # применить (идемпотентно)
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = []

# 1. комментарий про уровни артов -------------------------------------------
PAIRS.append(('app.js: комментарий про уровни', """
        //   media/t/  256px — списки, строки, компактные сетки  (~0.47 МБ в памяти)
        //   media/t2/ 512px — обычные сетки, вскрытие пака       (~1.9 МБ в памяти)
        //   мастер        — просмотр карты и вид «галерея» (1:1, как было)
        // Полноразмерные арты не пережаты и не изменены: там, где карта
        // показывается крупной, картинка осталась ровно той же.
""".lstrip('\n'), """
        //   media/t/  256px — списки, строки, компактные сетки  (~0.47 МБ в памяти)
        //   media/t2/ 512px — обычные сетки, вскрытие пака       (~1.9 МБ в памяти)
        //   media/t3/ 1440px — просмотр карты, «галерея» (b438: ~0.1–0.3 МБ вместо мастера 10–16 МБ)
        //   мастер        — последний резерв, если t3 ещё не построен (1:1, как было)
        // Полноразмерные арты не пережаты и не изменены: мастер на диске
        // остаётся ровно тем же, просто для показа на телефоне он больше не качается.
""".lstrip('\n')))

# 2. декларация NX_EMBED_BIG (заполняет sync_thumb_maps.py) ------------------
PAIRS.append(('app.js: декларация NX_EMBED_BIG', """
        /*NX_EMBED_THUMB_END*/
""".lstrip('\n'), """
        const NX_EMBED_BIG = {};
        /*NX_EMBED_THUMB_END*/
""".lstrip('\n')))

# 3. mediaBig/nxBigFor/nxDownTierUrl после mediaThumbMid ---------------------
PAIRS.append(('app.js: mediaBig + nxDownTierUrl', """
        function mediaThumbMid(u) {                    // 512px, иначе мелкая, иначе мастер
            const a = nxThumbFor(u, 'mid');
            if (a && !nxThumb404Hit(a)) return a;
            const b = nxThumbFor(u, 'small');
            if (b && !nxThumb404Hit(b)) return b;
            return mediaUrl(u);
        }
""".lstrip('\n'), """
        function mediaThumbMid(u) {                    // 512px, иначе мелкая, иначе мастер
            const a = nxThumbFor(u, 'mid');
            if (a && !nxThumb404Hit(a)) return a;
            const b = nxThumbFor(u, 'small');
            if (b && !nxThumb404Hit(b)) return b;
            return mediaUrl(u);
        }
        // b438: третий уровень — «большой» webp media/t3/ (длинная сторона ≤1440px,
        // ~0.1–0.3 МБ). Просмотр карты и «галерея» раньше грузили мастер: «Гарри
        // Поттер» — 4K PNG по 10–16 МБ на карту. На телефоне это десятки секунд
        // (часто вовсе не прогружается), а файл >8 МБ не влезает в постоянный кэш
        // (IMG_CACHE_MAX_BLOB) — каждое открытие качает его заново. t3 на экране
        // неотличим (крупнее 1440px карта не показывается), грузится в ~50 раз
        // быстрее и кэшируется навсегда.
        // Ключа нет в NX_EMBED_BIG (лёгкий мастер, или арт новее сборки) — мастер,
        // как раньше: цепочка data-nx-full/ретраи не изменилась.
        function nxBigFor(u) {
            try {
                const s = String(u == null ? '' : u);
                if (!s) return '';
                const full = mediaUrl(s);              // уже с учётом зеркала и NX_EMBED_MEDIA
                if (!full) return '';
                const key = nxMediaKey(full) || nxMediaKey(s);
                const rel = NX_EMBED_BIG[key];
                if (!rel) return '';
                if (full.indexOf('http') !== 0) return rel;   // локальный арт — путь относительный
                const i = full.lastIndexOf('/media/');        // облачная/зеркальная ссылка: t3 лежит рядом с мастером
                if (i < 0) return rel;
                return full.slice(0, i + 7) + rel.slice(6);
            } catch (e) { return ''; }
        }
        function mediaBig(u) {                         // 1440px, иначе мастер
            const t = nxBigFor(u);
            return (t && !nxThumb404Hit(t)) ? t : mediaUrl(u);
        }
        function nxDownTierUrl(url) {                  // b438: t3 -> t2 (мгновенный показ, пока «большой» грузится)
            try {
                const s = String(url || '');
                if (s.indexOf('/media/t3/') >= 0) return s.replace('/media/t3/', '/media/t2/');
                return '';
            } catch (e) { return ''; }
        }
""".lstrip('\n')))

# 4. imgErrorChain: t3 входит в цепочку откатов ------------------------------
PAIRS.append(('app.js: imgErrorChain t3', """
                                // миниатюра не отдалась (папки media/t/ или media/t2/ ещё не
                // задеплоены, файл битый, арт добавили после сборки) — показываем
                // полный арт: карта не должна оставаться заглушкой
                if (!el.__nxThumbTried && /\\/media\\/t2?\\//.test(u)) {
""".lstrip('\n'), """
                                // производная не отдалась (папки media/t/, media/t2/ или media/t3/
                // ещё не задеплоены, файл битый, арт добавили после сборки) —
                // показываем полный арт (data-nx-full): карта не должна оставаться
                // заглушкой. b438: t3 тоже в цепочке — с «большого» откат на мастер
                if (!el.__nxThumbTried && /\\/media\\/t[23]?\\//.test(u)) {
""".lstrip('\n')))

# 5. nxProgressiveAttach: t3 -> мгновенная 512px миниатюра -------------------
PAIRS.append(('app.js: progressive для t3', """
                const thumb = nxThumbUrl(url);
                if (!thumb) return;
""".lstrip('\n'), """
                // b438: src — «большой» арт media/t3/ (просмотр карты, галерея):
                // сперва показываем 512px миниатюру — она почти всегда уже в кэше,
                // картинка появляется мгновенно, — затем тихо подменяем на t3.
                const thumb = nxThumbUrl(url) || nxDownTierUrl(url);
                if (!thumb) return;
""".lstrip('\n')))

# 6. inspectCard: src=mediaBig, data-nx-full=мастер ---------------------------
PAIRS.append(('app.js: inspectCard src', """
                <img src="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);" class="absolute inset-0 w-full h-full object-cover z-0" loading="lazy" decoding="async">
""".lstrip('\n'), """
                <img src="${mediaBig(card.image)}" data-nx-full="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);" class="absolute inset-0 w-full h-full object-cover z-0" loading="lazy" decoding="async">
""".lstrip('\n')))

# 7. прогрев соседей в просмотре карты ---------------------------------------
PAIRS.append(('app.js: прогрев соседей inspect', """
            applyCardAura(document.getElementById('inspect-aura'), card, 'aura-inspect');
""".lstrip('\n'), """
            applyCardAura(document.getElementById('inspect-aura'), card, 'aura-inspect');
            // b438: греем «большие» арты соседей по списку — свайп на следующую
            // карту показывает её сразу (t3 весит ~0.1–0.3 МБ, два соседа с каждой
            // стороны — копейки, очередь предзагрузки ограничена b404)
            try {
                const nN = (inspectList || []).length;
                if (nN > 1) {
                    const near = [];
                    for (let d = 1; d <= 2 && d < nN; d++) {
                        for (let sgn = 1; sgn >= -1; sgn -= 2) {
                            const k = ((inspectIdx + sgn * d) % nN + nN) % nN;
                            const c2 = state.cards.find(c => c.id === inspectList[k]);
                            if (c2 && c2.image) near.push(c2.image);
                        }
                    }
                    if (near.length) preloadImages(near, 'big');
                }
            } catch (e) {}
""".lstrip('\n')))

# 8. галерея альбома: 'full' -> mediaBig --------------------------------------
PAIRS.append(('app.js: галерея mediaBig', """
            const artFn = artTier === 'full' ? mediaUrl : (artTier === 'mid' ? mediaThumbMid : mediaThumb);
""".lstrip('\n'), """
            const artFn = artTier === 'full' ? mediaBig : (artTier === 'mid' ? mediaThumbMid : mediaThumb); // b438: галерея — 1440px webp (media/t3), а не мастера по 10–16 МБ
""".lstrip('\n')))

# 9. preloadImages: tier='big' -------------------------------------------------
PAIRS.append(('app.js: preloadImages big', """
                // tier='full' — греть полный арт (нужно только для просмотра карты).
                // По умолчанию греем миниатюру 256px: полный арт облачного каталога
                // весит 2-4 МБ и показывается в списках размером 30-180 px.
                let u = mediaUrl(raw);
                if (tier !== 'full') { const t = mediaThumb(raw); if (t) u = t; }
""".lstrip('\n'), """
                // tier='full' — греть мастер (нужно только авто-вшиванию владельца).
                // tier='big' — греть «большой» арт media/t3 (b438: просмотр карты).
                // По умолчанию греем миниатюру 256px: полный арт облачного каталога
                // весит 2-4 МБ и показывается в списках размером 30-180 px.
                let u = mediaUrl(raw);
                if (tier === 'big') { u = mediaBig(raw); }
                else if (tier !== 'full') { const t = mediaThumb(raw); if (t) u = t; }
""".lstrip('\n')))

TAG_OLD = 'nxmob24'
TAG_NEW = 'nxmob25'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, text):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
        f.write(text)


def apply():
    app = read('assets/app.js')
    for label, old, new in PAIRS:
        if label.endswith('декларация NX_EMBED_BIG'):
            # карту заполняет tools/sync_thumb_maps.py: {} -> {...json...};
            import re
            if re.search(r'const NX_EMBED_BIG = \{.*?\};', app):
                continue  # декларация уже есть (возможно, с заполненной картой)
        elif new in app:
            continue  # уже применено (у части пар old входит в new — проверяем только new)
        assert old in app, 'b438: не найден якорь: %s' % label
        assert app.count(old) == 1, 'b438: якорь не уникален: %s (%d)' % (label, app.count(old))
        app = app.replace(old, new, 1)
    write('assets/app.js', app)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b438: не найден тег %s в %s' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b438: применено')


def check():
    app = read('assets/app.js')
    problems = []
    for label, old, new in PAIRS:
        if label.endswith('декларация NX_EMBED_BIG'):
            # карту заполняет tools/sync_thumb_maps.py: {} -> {...json...};
            import re
            if not re.search(r'const NX_EMBED_BIG = \{.*?\};', app):
                problems.append('app.js: нет декларации NX_EMBED_BIG = {...};')
            continue
        if new not in app:
            problems.append('app.js: нет нового блока: %s' % label)
        if old not in new and old in app:
            problems.append('app.js: остался старый блок: %s' % label)
    for extra in ('function nxBigFor(', 'function mediaBig(', 'function nxDownTierUrl(',
                  'const NX_EMBED_BIG = ', "preloadImages(near, 'big')",
                  '/media\\/t[23]?\\//'):
        if extra not in app:
            problems.append('app.js: нет %r' % extra)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не nxmob154' % rel)
    if problems:
        print('b438 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b438 --check: всё на месте (media/t3, mediaBig, progressive, тег nxmob158)')


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
