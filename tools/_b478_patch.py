#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b478: размер чипов боевых статов — мелкий (как раньше), средний и крупный.

Заявка владельца к b477: «а размер сейчас маленький, нужно сделать средний и
большой».

Разбор
------
Чипы статов рисовались одним размером (текст 9–11px в зависимости от рендера),
управления размером не было. На карте с крупным артом мелкие чипы теряются.

Лечение: card.layout.statsSize = 'sm' (по умолчанию, как раньше) / 'md' / 'lg'
+ селект «Размер статов» в Студии. Масштаб делается одним CSS-коэффициентом
--k на обёртке .nx-st-wrap: от него через calc() растут паддинги чипов,
толщина канта, сдвиг подложки, зазор и кегль текста — поэтому все шесть форм
(b477) масштабируются одинаково и не разъезжаются.

1. cardLayoutOf нормирует statsSize ('md'/'lg', остальное → 'sm').
2. cardStatsHtml: обёртка получает класс nx-st-md/nx-st-lg (и nx-st-wrap для
   --k и зазора); кегль текста больше не задаётся вариантом рендера
   (o.txt убран вместе с третьим аргументом) — единый базовый кегль 10px * --k
   делает чипы одинаковыми в альбоме, просмотре и предпросмотре, а размер
   выбирает владелец.
3. assets/app.css: блок b477 переписан на calc(...*var(--k)); добавлены
   .nx-st-wrap, .nx-st-md (--k:1.3), .nx-st-lg (--k:1.65).
4. Форма Студии: селект «Размер статов» (card-stats-size) рядом с местом,
   расположением и формой; readCardLayoutForm и editCard его читают/
   восстанавливают. layout синхронизируется в комнату как обычно.

Менялись app.js, app.css, index.html — тег сборки nxmob221 -> nxmob222.

Проверка/применение:
    python3 tools/_b478_patch.py --check
    python3 tools/_b478_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob221'
TAG_NEW = 'nxmob222'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

# --------------------------------------------------------------------------- #
# assets/app.js — нормализация statsSize
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''                statsShape: CARD_STATS_SHAPES.indexOf(L.statsShape) >= 0 ? L.statsShape : 'rect', // b477: форма чипов''',
              r'''                statsShape: CARD_STATS_SHAPES.indexOf(L.statsShape) >= 0 ? L.statsShape : 'rect', // b477: форма чипов
                statsSize: (L.statsSize === 'md' || L.statsSize === 'lg') ? L.statsSize : 'sm', // b478: размер чипов (мелкий/средний/крупный)'''))

# --------------------------------------------------------------------------- #
# assets/app.js — cardStatsHtml: масштаб через --k обёртки
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''        function cardStatsHtml(card, L, o) {
            if (!cardStatsShown(L)) return '';
            const st = getCardStats(card);
            const opt = o || {};
            const shape = 'nx-st-' + L.statsShape;
            const chip = (color, icon, val) =>
                `<span class="nx-st ${shape} ${color}"><i class="nx-st-bg"></i><span class="nx-st-tx ${opt.txt || 'text-[10px]'}">${icon}<span>${val}</span></span></span>`; // b477: цвет на самом чипе — силуэт подложки тонируется им через currentColor
            const chips = chip('text-amber-300', '<i class="fa-solid fa-bolt"></i>', st.atk) +
                chip('text-rose-300', '<i class="fa-solid fa-heart"></i>', st.hp);
            const gap = opt.gap || 'gap-1';
            if (L.statsPos === 'left' || L.statsPos === 'right') {
                const edge = L.statsPos === 'left' ? 'left-1.5 items-start' : 'right-1.5 items-end';
                const dir = L.statsDir === 'col' ? 'flex-col' : 'flex-row';
                return `<div class="absolute z-20 top-1/2 -translate-y-1/2 ${edge} flex ${dir} ${gap} pointer-events-none">${chips}</div>`;
            }
            const dir = L.statsDir === 'col'
                ? `flex-col ${L.align === 'center' ? 'items-center' : (L.align === 'right' ? 'items-end' : 'items-start')}`
                : `flex-row ${L.justify}`;
            return `<div class="flex w-full ${dir} ${gap} pt-0.5">${chips}</div>`;
        }''',
              r'''        function cardStatsHtml(card, L) {
            if (!cardStatsShown(L)) return '';
            const st = getCardStats(card);
            const shape = 'nx-st-' + L.statsShape;
            const chip = (color, icon, val) =>
                `<span class="nx-st ${shape} ${color}"><i class="nx-st-bg"></i><span class="nx-st-tx">${icon}<span>${val}</span></span></span>`; // b477: цвет на самом чипе; b478: кегль и паддинги растут через --k обёртки
            const chips = chip('text-amber-300', '<i class="fa-solid fa-bolt"></i>', st.atk) +
                chip('text-rose-300', '<i class="fa-solid fa-heart"></i>', st.hp);
            const sz = L.statsSize === 'lg' ? ' nx-st-lg' : (L.statsSize === 'md' ? ' nx-st-md' : ''); // b478: средний/крупный размер
            if (L.statsPos === 'left' || L.statsPos === 'right') {
                const edge = L.statsPos === 'left' ? 'left-1.5 items-start' : 'right-1.5 items-end';
                const dir = L.statsDir === 'col' ? 'flex-col' : 'flex-row';
                return `<div class="nx-st-wrap${sz} absolute z-20 top-1/2 -translate-y-1/2 ${edge} flex ${dir} pointer-events-none">${chips}</div>`;
            }
            const dir = L.statsDir === 'col'
                ? `flex-col ${L.align === 'center' ? 'items-center' : (L.align === 'right' ? 'items-end' : 'items-start')}`
                : `flex-row ${L.justify}`;
            return `<div class="nx-st-wrap${sz} flex w-full ${dir} pt-0.5">${chips}</div>`;
        }'''))

# --------------------------------------------------------------------------- #
# assets/app.js — вызовы рендеров без третьего аргумента
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            const statsHtml = cardStatsHtml(card, L, { txt: 'text-[10px]' }); // b477: место/расположение/форма из настроек карты''',
              r'''            const statsHtml = cardStatsHtml(card, L); // b477+b478: сетка альбома — место/расположение/форма/размер из настроек карты'''))

PAIRS.append(('assets/app.js', 1,
              r'''            const statsHtml = cardStatsHtml(card, L, { txt: 'text-[11px]', gap: 'gap-1.5' }); // b477: место/расположение/форма из настроек карты''',
              r'''            const statsHtml = cardStatsHtml(card, L); // b477+b478: просмотр карты — место/расположение/форма/размер из настроек карты'''))

PAIRS.append(('assets/app.js', 1,
              r'''            const statsHtml = cardStatsHtml(fake, L, { txt: 'text-[9px]' }); // b477: предпросмотр показывает ровно то, что увидит игрок''',
              r'''            const statsHtml = cardStatsHtml(fake, L); // b477+b478: предпросмотр Студии показывает ровно то, что увидит игрок'''))

# --------------------------------------------------------------------------- #
# assets/app.js — форма Студии: чтение и восстановление размера
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''statsDir: g('card-stats-dir'), statsShape: g('card-stats-shape'), align:''',
              r'''statsDir: g('card-stats-dir'), statsShape: g('card-stats-shape'), statsSize: g('card-stats-size'), align:'''))

PAIRS.append(('assets/app.js', 1,
              r'''            const statsShapeEl = document.getElementById('card-stats-shape'); // b477: форма чипов статов
            if (statsShapeEl) statsShapeEl.value = L0.statsShape;''',
              r'''            const statsShapeEl = document.getElementById('card-stats-shape'); // b477: форма чипов статов
            if (statsShapeEl) statsShapeEl.value = L0.statsShape;
            const statsSizeEl = document.getElementById('card-stats-size'); // b478: размер чипов статов
            if (statsSizeEl) statsSizeEl.value = L0.statsSize;'''))

# --------------------------------------------------------------------------- #
# assets/app.css — масштаб чипов через --k
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.css', 1,
              r'''.nx-st{position:relative;display:inline-flex;align-items:center;justify-content:center;padding:3px 8px;line-height:1.1;flex:none}
.nx-st::before{content:'';position:absolute;inset:0;background:currentColor;opacity:.45;border-radius:7px;pointer-events:none}
.nx-st-bg{position:absolute;inset:2px;background:rgba(2,6,23,.9);border-radius:5px;pointer-events:none;backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px)}
.nx-st-tx{position:relative;display:inline-flex;align-items:center;gap:4px;font-weight:700;white-space:nowrap}
.nx-st-circle{padding:4px 11px}
.nx-st-circle::before{border-radius:9999px}
.nx-st-circle .nx-st-bg{border-radius:9999px}
.nx-st-diamond{padding:8px 17px}
.nx-st-diamond::before,.nx-st-diamond .nx-st-bg{border-radius:0;clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%)}
.nx-st-star{padding:9px 16px}
.nx-st-star::before,.nx-st-star .nx-st-bg{border-radius:0;clip-path:polygon(50% 0%,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)}
.nx-st-hex{padding:5px 13px}
.nx-st-hex::before,.nx-st-hex .nx-st-bg{border-radius:0;clip-path:polygon(25% 0,75% 0,100% 50%,75% 100%,25% 100%,0 50%)}
.nx-st-shield{padding:5px 12px 8px}
.nx-st-shield::before,.nx-st-shield .nx-st-bg{border-radius:0;clip-path:polygon(0 0,100% 0,100% 68%,50% 100%,0 68%)}''',
              r'''.nx-st-wrap{--k:1;gap:calc(4px * var(--k))}          /* b478: мелкий (как в b477) */
.nx-st-wrap.nx-st-md{--k:1.3}                       /* b478: средний */
.nx-st-wrap.nx-st-lg{--k:1.65}                      /* b478: крупный */
.nx-st{position:relative;display:inline-flex;align-items:center;justify-content:center;padding:calc(3px * var(--k)) calc(8px * var(--k));line-height:1.1;flex:none}
.nx-st::before{content:'';position:absolute;inset:0;background:currentColor;opacity:.45;border-radius:calc(7px * var(--k));pointer-events:none}
.nx-st-bg{position:absolute;inset:calc(2px * var(--k));background:rgba(2,6,23,.9);border-radius:calc(5px * var(--k));pointer-events:none;backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px)}
.nx-st-tx{position:relative;display:inline-flex;align-items:center;gap:calc(4px * var(--k));font-weight:700;white-space:nowrap;font-size:calc(10px * var(--k))}
.nx-st-circle{padding:calc(4px * var(--k)) calc(11px * var(--k))}
.nx-st-circle::before{border-radius:9999px}
.nx-st-circle .nx-st-bg{border-radius:9999px}
.nx-st-diamond{padding:calc(8px * var(--k)) calc(17px * var(--k))}
.nx-st-diamond::before,.nx-st-diamond .nx-st-bg{border-radius:0;clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%)}
.nx-st-star{padding:calc(9px * var(--k)) calc(16px * var(--k))}
.nx-st-star::before,.nx-st-star .nx-st-bg{border-radius:0;clip-path:polygon(50% 0%,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)}
.nx-st-hex{padding:calc(5px * var(--k)) calc(13px * var(--k))}
.nx-st-hex::before,.nx-st-hex .nx-st-bg{border-radius:0;clip-path:polygon(25% 0,75% 0,100% 50%,75% 100%,25% 100%,0 50%)}
.nx-st-shield{padding:calc(5px * var(--k)) calc(12px * var(--k)) calc(8px * var(--k))}
.nx-st-shield::before,.nx-st-shield .nx-st-bg{border-radius:0;clip-path:polygon(0 0,100% 0,100% 68%,50% 100%,0 68%)}'''))

# --------------------------------------------------------------------------- #
# index.html — селект размера статов
# --------------------------------------------------------------------------- #
PAIRS.append(('index.html', 1,
              r'''                                        <option value="shield">Щит</option>
                                    </select>
                                </div>''',
              r'''                                        <option value="shield">Щит</option>
                                    </select>
                                </div>
                                <!-- b478: размер чипов статов на карте -->
                                <div>
                                    <span class="block text-[10px] text-slate-500 mb-1">Размер статов</span>
                                    <select id="card-stats-size" onchange="renderCardPreviewSoon()" title="Размер чипов ⚔ и ❤ на карте: мелкий как раньше, средний или крупный" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-2 text-[11px] focus:outline-none focus:border-fuchsia-500">
                                        <option value="sm">Мелкий (классика)</option>
                                        <option value="md">Средний</option>
                                        <option value="lg">Крупный</option>
                                    </select>
                                </div>'''))


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
        print('b478: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b478: размер статов (мелкий/средний/крупный) настраивается в Студии; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
