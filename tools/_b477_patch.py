#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b477: боевые статы на карте — выбор МЕСТА, РАСПОЛОЖЕНИЯ и ФОРМЫ чипов.

Запрос владельца: «значения боевых статов нужно сделать выбор, куда ставить на
карту: справа, слева, сверху; и вертикально или горизонтально; и фон статов —
пример: в бриллианте, или в квадратике, или в звёздочке, и так далее».

Разбор
------
В b475/b476 у статов было только «Внизу (классика)» / «Скрыть», чипы рисовались
внизу лица карты одним рядом в тёмных скруглённых плашках. Владелец хочет
компоновать статы как часть дизайна карты.

Лечение: три настройки в card.layout (все необязательные — старые карты не
меняются) и один общий рендерер чипов.

1. card.layout.statsPos — место: 'bottom' (как раньше) / 'top' / 'left' /
   'right' / 'hide'. Верх и низ идут в текстовые зоны cardTextZones, лево и
   право — отдельным абсолютным слоем по центру кромки (поле side у
   cardTextZones), чтобы числа не смешивались с потоком имени/описания и не
   ломали flex-раскладку лица.
2. card.layout.statsDir — расположение пары: 'row' (по горизонтали, как
   раньше) / 'col' (столбиком). В зонах столбик выравнивается по общему
   выравниванию текста карты (L.align), на кромках — к своей кромке.
3. card.layout.statsShape — форма подложки чипа: 'rect' (квадратик, как
   раньше) / 'circle' / 'diamond' (тот самый «бриллиант») / 'star' / 'hex' /
   'shield'. Формы — clip-path на фоновом слое .nx-st-bg в assets/app.css:
   силуэт вырезается, а цифра с иконкой остаётся НАД ним читаемой (текст не
   режется клипом, в отличие от clip-path на самом чипе).
4. Единый рендерер cardStatsHtml(card, L, o) вместо трёх копий чипов: обзор
   карты, сетка альбома и предпросмотр Студии рисуют одни и те же чипы
   (иконки fa-bolt/fa-heart, цвета янтарь/роза), размер текста задаёт вариант.
   Вскрытие пака статы не рисовало и не рисует (там слой статуса).
5. Форма Студии: у «Боевые статы на карте» добавились варианты Сверху/Слева/
   Справа, рядом новые селекты «Расположение статов» (card-stats-dir) и
   «Форма статов» (card-stats-shape); readCardLayoutForm и editCard их
   читают/восстанавливают. layout уже синхронизируется в комнату
   (STD_CARD_FIELDS), поэтому композиция статов доезжает до игроков сама.

app.js, index.html и app.css менялись — тег сборки nxmob220 -> nxmob221.

Проверка/применение:
    python3 tools/_b477_patch.py --check
    python3 tools/_b477_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob220'
TAG_NEW = 'nxmob221'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

# --------------------------------------------------------------------------- #
# assets/app.js — нормализация layout
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''        function cardLayoutOf(card) {
            const L = (card && card.layout) || {};''',
              r'''        // b477: настройки боевых статов на лице карты: место (statsPos:
        // bottom/top/left/right/hide), расположение пары (statsDir: row/col) и
        // форма чипов (statsShape). Все поля необязательные: без них карта
        // выглядит ровно как до b477.
        const CARD_STATS_SHAPES = ['rect', 'circle', 'diamond', 'star', 'hex', 'shield'];
        function cardLayoutOf(card) {
            const L = (card && card.layout) || {};'''))

PAIRS.append(('assets/app.js', 1,
              r'''                statsPos: L.statsPos === 'hide' ? 'hide' : 'bottom', // b475: боевые статы (⚔/❤) на карте можно скрыть''',
              r'''                statsPos: (L.statsPos === 'hide' || L.statsPos === 'top' || L.statsPos === 'left' || L.statsPos === 'right') ? L.statsPos : 'bottom', // b477: место статов: низ/верх/лево/право/скрыть
                statsDir: L.statsDir === 'col' ? 'col' : 'row', // b477: горизонтально или столбиком
                statsShape: CARD_STATS_SHAPES.indexOf(L.statsShape) >= 0 ? L.statsShape : 'rect', // b477: форма чипов'''))

# --------------------------------------------------------------------------- #
# assets/app.js — единый рендерер чипов статов
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''        function cardNameShown(L) { return !L || L.namePos !== 'hide'; }
        function cardStatsShown(L) { return !L || L.statsPos !== 'hide'; }''',
              r'''        function cardNameShown(L) { return !L || L.namePos !== 'hide'; }
        function cardStatsShown(L) { return !L || L.statsPos !== 'hide'; }
        // b477: единый блок боевых статов лица карты (просмотр, сетка альбома,
        // предпросмотр Студии). Чип = фоновая подложка выбранной формы
        // (.nx-st-* в assets/app.css, clip-path режет только фон) + поверх неё
        // иконка с числом: текст клипом не режется и читается на любой форме.
        // Место — по statsPos: bottom/top отдаются в текстовые зоны через
        // cardTextZones, left/right возвращаются абсолютным слоем у кромки
        // (вертикально по центру), чтобы числа не лезли в поток имени/описания.
        function cardStatsHtml(card, L, o) {
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
        }'''))

# --------------------------------------------------------------------------- #
# assets/app.js — cardTextZones: статы по месту + боковой слой
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''        function cardTextZones(L, badgeHtml, nameHtml, descHtml, extraHtml) {
            const top = [badgeHtml];
            const bottom = [];
            if (L.namePos === 'top') top.push(nameHtml);
            else if (L.namePos !== 'hide') bottom.push(nameHtml); // b475: имя скрыто настройкой карты — в зонах его нет
            if (L.descPos === 'top') top.push(descHtml);
            else if (L.descPos === 'bottom') bottom.push(descHtml);
            bottom.push(extraHtml);
            return {
                top: `<div class="relative z-20 flex flex-col space-y-1 w-full">${top.join('')}</div>`,
                bottom: `<div class="relative z-20 flex flex-col space-y-1 w-full">${bottom.join('')}</div>`
            };
        }''',
              r'''        function cardTextZones(L, badgeHtml, nameHtml, descHtml, extraHtml, statsHtml) {
            const top = [badgeHtml];
            const bottom = [];
            if (L.namePos === 'top') top.push(nameHtml);
            else if (L.namePos !== 'hide') bottom.push(nameHtml); // b475: имя скрыто настройкой карты — в зонах его нет
            if (L.descPos === 'top') top.push(descHtml);
            else if (L.descPos === 'bottom') bottom.push(descHtml);
            bottom.push(extraHtml);
            // b477: статы по настройке карты: top/bottom — в текстовые зоны,
            // left/right — отдельным слоем (side), вне потока имени/описания.
            // Пустой statsHtml (вскрытие пака: там слой статуса в extraHtml)
            // ничего не добавляет — статус вскрытия остаётся внизу, как был.
            if (statsHtml && L.statsPos !== 'hide') {
                if (L.statsPos === 'top') top.push(statsHtml);
                else if (L.statsPos !== 'left' && L.statsPos !== 'right') bottom.push(statsHtml);
            }
            const side = (statsHtml && L.statsPos !== 'hide' && (L.statsPos === 'left' || L.statsPos === 'right')) ? statsHtml : '';
            return {
                top: `<div class="relative z-20 flex flex-col space-y-1 w-full">${top.join('')}</div>`,
                bottom: `<div class="relative z-20 flex flex-col space-y-1 w-full">${bottom.join('')}</div>`,
                side: side
            };
        }'''))

# --------------------------------------------------------------------------- #
# assets/app.js — сетка альбома
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            const statsHtml = cardStatsShown(L) ? `<div class="flex items-center space-x-1.5 pt-0.5 w-full ${L.justify}">
                            <span class="text-[10px] font-bold text-amber-300 bg-slate-950/80 px-1.5 py-0.5 rounded">⚔ ${getCardStats(card).atk}</span>
                            <span class="text-[10px] font-bold text-rose-300 bg-slate-950/80 px-1.5 py-0.5 rounded">❤ ${getCardStats(card).hp}</span>
                        </div>` : ''; // b475: статы скрыты настройкой карты
            const Z = cardTextZones(L, badgeHtml, nameHtml, descHtml, statsHtml);''',
              r'''            const statsHtml = cardStatsHtml(card, L, { txt: 'text-[10px]' }); // b477: место/расположение/форма из настроек карты
            const Z = cardTextZones(L, badgeHtml, nameHtml, descHtml, '', statsHtml);'''))

PAIRS.append(('assets/app.js', 1,
              r'''                    ${Z.top}

                    ${Z.bottom}
                    ${cardShineOverlay(card)}''',
              r'''                    ${Z.top}

                    ${Z.bottom}
                    ${Z.side}
                    ${cardShineOverlay(card)}'''))

# --------------------------------------------------------------------------- #
# assets/app.js — просмотр карты
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            const statsHtml = cardStatsShown(L) ? `<div class="flex items-center space-x-2 pt-1.5 w-full ${L.justify}">
                    <span class="inline-flex items-center space-x-1 text-[11px] font-bold text-amber-300 bg-slate-950/80 border border-amber-500/30 px-2 py-0.5 rounded-lg backdrop-blur-sm"><i class="fa-solid fa-bolt"></i><span>${st.atk}</span></span>
                    <span class="inline-flex items-center space-x-1 text-[11px] font-bold text-rose-300 bg-slate-950/80 border border-rose-500/30 px-2 py-0.5 rounded-lg backdrop-blur-sm"><i class="fa-solid fa-heart"></i><span>${st.hp}</span></span>
                </div>` : ''; // b475: статы скрыты настройкой карты
            const Z = cardTextZones(L, badgeHtml, nameHtml, descHtml, statsHtml);''',
              r'''            const statsHtml = cardStatsHtml(card, L, { txt: 'text-[11px]', gap: 'gap-1.5' }); // b477: место/расположение/форма из настроек карты
            const Z = cardTextZones(L, badgeHtml, nameHtml, descHtml, '', statsHtml);'''))

PAIRS.append(('assets/app.js', 1,
              r'''                ${Z.top}
                ${Z.bottom}
                ${cardShineOverlay(card)}
            `;''',
              r'''                ${Z.top}
                ${Z.bottom}
                ${Z.side}
                ${cardShineOverlay(card)}
            `;'''))

# --------------------------------------------------------------------------- #
# assets/app.js — вскрытие пака: боковой слой для единообразия (пустой)
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''                        ${Z.top}
                        ${Z.bottom}
                        ${cardShineOverlay(card, 25)}''',
              r'''                        ${Z.top}
                        ${Z.bottom}
                        ${Z.side}
                        ${cardShineOverlay(card, 25)}'''))

# --------------------------------------------------------------------------- #
# assets/app.js — предпросмотр Студии
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            const statsHtml = cardStatsShown(L) ? `<div class="flex items-center space-x-1.5 pt-0.5 w-full ${L.justify}">
                    <span class="text-[9px] font-bold text-amber-300 bg-slate-950/80 px-1.5 py-0.5 rounded">⚔ ${st.atk}</span>
                    <span class="text-[9px] font-bold text-rose-300 bg-slate-950/80 px-1.5 py-0.5 rounded">❤ ${st.hp}</span>
                </div>` : ''; // b475: предпросмотр показывает ровно то, что увидит игрок
            const z = cardTextZones(L, badge, nameHtml, descHtml, statsHtml);''',
              r'''            const statsHtml = cardStatsHtml(fake, L, { txt: 'text-[9px]' }); // b477: предпросмотр показывает ровно то, что увидит игрок
            const z = cardTextZones(L, badge, nameHtml, descHtml, '', statsHtml);'''))

PAIRS.append(('assets/app.js', 1,
              r'''                ${z.top}${z.bottom}${cardShineOverlay(fake, 25)}`);''',
              r'''                ${z.top}${z.bottom}${z.side}${cardShineOverlay(fake, 25)}`);'''))

# --------------------------------------------------------------------------- #
# assets/app.js — форма Студии: чтение и восстановление новых настроек
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            return { namePos: g('card-name-pos'), descPos: g('card-desc-pos'), statsPos: g('card-stats-pos'), align: g('card-align'), shine: g('card-shine'), artZoom: g('card-artzoom'), artPosY: g('card-arty'), artPosX: g('card-artx') }; // b456: + масштаб/сдвиг арта; b457: + сдвиг по горизонтали; b475: + видимость боевых статов''',
              r'''            return { namePos: g('card-name-pos'), descPos: g('card-desc-pos'), statsPos: g('card-stats-pos'), statsDir: g('card-stats-dir'), statsShape: g('card-stats-shape'), align: g('card-align'), shine: g('card-shine'), artZoom: g('card-artzoom'), artPosY: g('card-arty'), artPosX: g('card-artx') }; // b456: + масштаб/сдвиг арта; b457: + сдвиг по горизонтали; b475: + видимость боевых статов; b477: + место/расположение/форма статов'''))

PAIRS.append(('assets/app.js', 1,
              r'''            const statsPosEl = document.getElementById('card-stats-pos'); // b475: видимость боевых статов
            if (statsPosEl) statsPosEl.value = L0.statsPos;''',
              r'''            const statsPosEl = document.getElementById('card-stats-pos'); // b475: видимость боевых статов
            if (statsPosEl) statsPosEl.value = L0.statsPos;
            const statsDirEl = document.getElementById('card-stats-dir'); // b477: расположение статов
            if (statsDirEl) statsDirEl.value = L0.statsDir;
            const statsShapeEl = document.getElementById('card-stats-shape'); // b477: форма чипов статов
            if (statsShapeEl) statsShapeEl.value = L0.statsShape;'''))

# --------------------------------------------------------------------------- #
# assets/app.css — формы чипов статов
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.css', 1,
              r'''/* b412: плашка «Продано» под раскрытой повторкой — кнопка больше не остаётся живой */
.nx-dupesold{background:rgba(6,78,59,.5);color:#6ee7b7;border-color:rgba(16,185,129,.45)}''',
              r'''/* b412: плашка «Продано» под раскрытой повторкой — кнопка больше не остаётся живой */
.nx-dupesold{background:rgba(6,78,59,.5);color:#6ee7b7;border-color:rgba(16,185,129,.45)}

/* b477: чипы боевых статов на лице карты — место, расположение и форма задаются
   в Студии (card.layout: statsPos/statsDir/statsShape). Силуэт формы рисуется
   ДВУМЯ слоями: цветной кант .nx-st::before (currentColor стата: янтарь у
   атаки, роза у здоровья) поверх него тёмная подложка .nx-st-bg со сдвигом
   2px — так «бриллиант»/звезда/щит читаются и на светлом, и на тёмном арте,
   а иконка с числом (.nx-st-tx) лежит над фоном и клипом не режется. */
.nx-st{position:relative;display:inline-flex;align-items:center;justify-content:center;padding:3px 8px;line-height:1.1;flex:none}
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
.nx-st-shield::before,.nx-st-shield .nx-st-bg{border-radius:0;clip-path:polygon(0 0,100% 0,100% 68%,50% 100%,0 68%)}'''))

# --------------------------------------------------------------------------- #
# index.html — форма Студии: место / расположение / форма статов
# --------------------------------------------------------------------------- #
PAIRS.append(('index.html', 1,
              r'''                                    <select id="card-stats-pos" onchange="renderCardPreviewSoon()" title="«Скрыть» — чисел ⚔ и ❤ не видно на карте (в просмотре, в альбоме, во вскрытии). Значения остаются и работают в бою" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-2 text-[11px] focus:outline-none focus:border-fuchsia-500">
                                        <option value="bottom">Внизу (классика)</option>
                                        <option value="hide">Скрыть (чисел не видно)</option>
                                    </select>
                                </div>''',
              r'''                                    <select id="card-stats-pos" onchange="renderCardPreviewSoon()" title="Куда поставить числа ⚔ и ❤ на карте: внизу или сверху в потоке текста, у левой/правой кромки — или скрыть совсем" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-2 text-[11px] focus:outline-none focus:border-fuchsia-500">
                                        <option value="bottom">Внизу (классика)</option>
                                        <option value="top">Сверху</option>
                                        <option value="left">Слева</option>
                                        <option value="right">Справа</option>
                                        <option value="hide">Скрыть (чисел не видно)</option>
                                    </select>
                                </div>
                                <!-- b477: расположение пары статов на карте -->
                                <div>
                                    <span class="block text-[10px] text-slate-500 mb-1">Расположение статов</span>
                                    <select id="card-stats-dir" onchange="renderCardPreviewSoon()" title="Как разместить два стата: рядом по горизонтали или столбиком" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-2 text-[11px] focus:outline-none focus:border-fuchsia-500">
                                        <option value="row">По горизонтали</option>
                                        <option value="col">Вертикально (столбиком)</option>
                                    </select>
                                </div>
                                <!-- b477: форма подложки чипов статов -->
                                <div>
                                    <span class="block text-[10px] text-slate-500 mb-1">Форма статов</span>
                                    <select id="card-stats-shape" onchange="renderCardPreviewSoon()" title="Форма подложки чипов ⚔ и ❤ на карте: квадратик, кружок, ромб-«бриллиант», звёздочка и другие" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-2 text-[11px] focus:outline-none focus:border-fuchsia-500">
                                        <option value="rect">Квадратик (классика)</option>
                                        <option value="circle">Кружок</option>
                                        <option value="diamond">Ромбик («бриллиант»)</option>
                                        <option value="star">Звёздочка</option>
                                        <option value="hex">Шестиугольник</option>
                                        <option value="shield">Щит</option>
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
        print('b477: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b477: место/расположение/форма статов настраиваются в Студии; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
