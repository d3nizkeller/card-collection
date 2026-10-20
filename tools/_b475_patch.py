#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b475: имя и боевые статы можно СКРЫТЬ с лица карты — настройка в Студии.

Запрос владельца: «сделай на карточках, чтоб в Студии можно скрывать имя и
характеристики (боевые статы) на самой карте, чтоб их не было видно в просмотре
карты — нужно сделать, чтоб их можно было скрывать в настройках карты».

Разбор
------
У лица карты уже была композиция (card.layout): имя — «Внизу/Вверху», описание —
«Внизу/Вверху/Скрыть», выравнивание, эффект, аура, кадрирование арта. Не хватало
двух вещей:

* у имени не было варианта «Скрыть» (cardLayoutOf нормировал namePos только в
  'top'/'bottom', а cardTextZones клал имя в зону всегда);
* у боевых статов (⚔ atk / ❤ hp) настройки видимости не было вовсе — чипы
  рисовались в нижней зоне во всех четырёх рендерах лица карты.

Лечение
-------
1. card.layout получает namePos:'hide' и новое поле statsPos:'hide'; оба
   нормируются в cardLayoutOf (мусор и отсутствие поля = прежнее поведение).
2. Форма Студии («Композиция и эффект карты»): у «Имя персонажа» добавлен
   вариант «Скрыть (имя не показывать)», рядом появился селект «Боевые статы на
   карте» (id card-stats-pos) с вариантами «Внизу (классика)» / «Скрыть (чисел
   не видно)». readCardLayoutForm пишет statsPos, editCard его восстанавливает.
3. Лицо карты рисуется одним cardTextZones во всех рендерах, поэтому скрытие
   действует сразу везде: просмотр карты (inspectCard), сетка альбома
   (albumCardHTML, оба варианта — обычный и компактный), вскрытие пака
   (showUnboxingUI) и живой предпросмотр Студии (renderCardPreview).
   Блок статов при statsPos:'hide' передаётся в зону пустой строкой.
4. Значения НЕ удаляются: card.atk/card.hp остаются в каталоге, getCardStats
   продолжает считать их для боя, силы колоды, списков альбома («Строки») и
   списков Студии. Скрывается только отрисовка на лице карты.
5. layout уже входит в STD_CARD_FIELDS и в карточку облака комнаты — настройка
   уезжает всем игрокам сама, отдельная синхронизация не нужна.

app.js и index.html менялись — тег сборки nxmob218 -> nxmob219.

Проверка/применение:
    python3 tools/_b475_patch.py --check
    python3 tools/_b475_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob218'
TAG_NEW = 'nxmob219'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

# --------------------------------------------------------------------------- #
# assets/app.js — нормализация layout + помощники видимости
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''                namePos: L.namePos === 'top' ? 'top' : 'bottom',
                descPos: (L.descPos === 'top' || L.descPos === 'hide') ? L.descPos : 'bottom',''',
              r'''                namePos: (L.namePos === 'top' || L.namePos === 'hide') ? L.namePos : 'bottom', // b475: имя можно скрыть с лица карты
                descPos: (L.descPos === 'top' || L.descPos === 'hide') ? L.descPos : 'bottom',
                statsPos: L.statsPos === 'hide' ? 'hide' : 'bottom', // b475: боевые статы (⚔/❤) на карте можно скрыть'''))

PAIRS.append(('assets/app.js', 1,
              r'''        // b461: карта валидна с одной картиной: пустое имя подставляется
        // только в отображении, храним пустую строку.
        function cardDisplayName(card) {''',
              r'''        // b475: ВИДИМОСТЬ ИМЕНИ И БОЕВЫХ СТАТОВ НА ЛИЦЕ КАРТЫ — настройка карты
        // из Студии («Композиция и эффект карты» → «Скрыть»). Живёт в card.layout
        // (namePos:'hide' / statsPos:'hide'), поэтому уезжает в облако комнаты тем
        // же полем 'layout' (STD_CARD_FIELDS) и действует у всех игроков: лицо
        // карты собирают одним cardTextZones и просмотр карты, и сетка альбома,
        // и вскрытие пака, и предпросмотр Студии.
        // Значения при этом НЕ удаляются: card.atk/card.hp остаются в каталоге,
        // getCardStats считает их для боя, силы колоды, строк альбома и списков
        // Студии — скрывается только отрисовка на самой карте.
        function cardNameShown(L) { return !L || L.namePos !== 'hide'; }
        function cardStatsShown(L) { return !L || L.statsPos !== 'hide'; }
        // b461: карта валидна с одной картиной: пустое имя подставляется
        // только в отображении, храним пустую строку.
        function cardDisplayName(card) {'''))

# --------------------------------------------------------------------------- #
# assets/app.js — общая сборка текстовых зон лица карты
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            if (L.namePos === 'top') top.push(nameHtml); else bottom.push(nameHtml);''',
              r'''            if (L.namePos === 'top') top.push(nameHtml);
            else if (L.namePos !== 'hide') bottom.push(nameHtml); // b475: имя скрыто настройкой карты — в зонах его нет'''))

# --------------------------------------------------------------------------- #
# assets/app.js — сетка альбома: компактная карточка (только имя) и обычная
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''                        <h4 class="relative z-10 w-full font-bold text-white text-[10px] truncate drop-shadow-md ${L.text}">${cardDisplayName(card)}</h4>''',
              r'''                        ${cardNameShown(L) ? `<h4 class="relative z-10 w-full font-bold text-white text-[10px] truncate drop-shadow-md ${L.text}">${cardDisplayName(card)}</h4>` : ''}'''))

PAIRS.append(('assets/app.js', 1,
              r'''            const statsHtml = `<div class="flex items-center space-x-1.5 pt-0.5 w-full ${L.justify}">
                            <span class="text-[10px] font-bold text-amber-300 bg-slate-950/80 px-1.5 py-0.5 rounded">⚔ ${getCardStats(card).atk}</span>
                            <span class="text-[10px] font-bold text-rose-300 bg-slate-950/80 px-1.5 py-0.5 rounded">❤ ${getCardStats(card).hp}</span>
                        </div>`;''',
              r'''            const statsHtml = cardStatsShown(L) ? `<div class="flex items-center space-x-1.5 pt-0.5 w-full ${L.justify}">
                            <span class="text-[10px] font-bold text-amber-300 bg-slate-950/80 px-1.5 py-0.5 rounded">⚔ ${getCardStats(card).atk}</span>
                            <span class="text-[10px] font-bold text-rose-300 bg-slate-950/80 px-1.5 py-0.5 rounded">❤ ${getCardStats(card).hp}</span>
                        </div>` : ''; // b475: статы скрыты настройкой карты'''))

# --------------------------------------------------------------------------- #
# assets/app.js — просмотр карты (inspectCard)
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            const statsHtml = `<div class="flex items-center space-x-2 pt-1.5 w-full ${L.justify}">
                    <span class="inline-flex items-center space-x-1 text-[11px] font-bold text-amber-300 bg-slate-950/80 border border-amber-500/30 px-2 py-0.5 rounded-lg backdrop-blur-sm"><i class="fa-solid fa-bolt"></i><span>${st.atk}</span></span>
                    <span class="inline-flex items-center space-x-1 text-[11px] font-bold text-rose-300 bg-slate-950/80 border border-rose-500/30 px-2 py-0.5 rounded-lg backdrop-blur-sm"><i class="fa-solid fa-heart"></i><span>${st.hp}</span></span>
                </div>`;''',
              r'''            const statsHtml = cardStatsShown(L) ? `<div class="flex items-center space-x-2 pt-1.5 w-full ${L.justify}">
                    <span class="inline-flex items-center space-x-1 text-[11px] font-bold text-amber-300 bg-slate-950/80 border border-amber-500/30 px-2 py-0.5 rounded-lg backdrop-blur-sm"><i class="fa-solid fa-bolt"></i><span>${st.atk}</span></span>
                    <span class="inline-flex items-center space-x-1 text-[11px] font-bold text-rose-300 bg-slate-950/80 border border-rose-500/30 px-2 py-0.5 rounded-lg backdrop-blur-sm"><i class="fa-solid fa-heart"></i><span>${st.hp}</span></span>
                </div>` : ''; // b475: статы скрыты настройкой карты'''))

# --------------------------------------------------------------------------- #
# assets/app.js — живой предпросмотр карты в форме Студии
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            const statsHtml = `<div class="flex items-center space-x-1.5 pt-0.5 w-full ${L.justify}">
                    <span class="text-[9px] font-bold text-amber-300 bg-slate-950/80 px-1.5 py-0.5 rounded">⚔ ${st.atk}</span>
                    <span class="text-[9px] font-bold text-rose-300 bg-slate-950/80 px-1.5 py-0.5 rounded">❤ ${st.hp}</span>
                </div>`;''',
              r'''            const statsHtml = cardStatsShown(L) ? `<div class="flex items-center space-x-1.5 pt-0.5 w-full ${L.justify}">
                    <span class="text-[9px] font-bold text-amber-300 bg-slate-950/80 px-1.5 py-0.5 rounded">⚔ ${st.atk}</span>
                    <span class="text-[9px] font-bold text-rose-300 bg-slate-950/80 px-1.5 py-0.5 rounded">❤ ${st.hp}</span>
                </div>` : ''; // b475: предпросмотр показывает ровно то, что увидит игрок'''))

# --------------------------------------------------------------------------- #
# assets/app.js — форма Студии: чтение и восстановление настройки
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            return { namePos: g('card-name-pos'), descPos: g('card-desc-pos'), align: g('card-align'), shine: g('card-shine'), artZoom: g('card-artzoom'), artPosY: g('card-arty'), artPosX: g('card-artx') }; // b456: + масштаб/сдвиг арта; b457: + сдвиг по горизонтали''',
              r'''            return { namePos: g('card-name-pos'), descPos: g('card-desc-pos'), statsPos: g('card-stats-pos'), align: g('card-align'), shine: g('card-shine'), artZoom: g('card-artzoom'), artPosY: g('card-arty'), artPosX: g('card-artx') }; // b456: + масштаб/сдвиг арта; b457: + сдвиг по горизонтали; b475: + видимость боевых статов'''))

PAIRS.append(('assets/app.js', 1,
              r'''            document.getElementById('card-name-pos').value = L0.namePos;
            document.getElementById('card-desc-pos').value = L0.descPos;''',
              r'''            document.getElementById('card-name-pos').value = L0.namePos;
            document.getElementById('card-desc-pos').value = L0.descPos;
            const statsPosEl = document.getElementById('card-stats-pos'); // b475: видимость боевых статов
            if (statsPosEl) statsPosEl.value = L0.statsPos;'''))

# --------------------------------------------------------------------------- #
# index.html — форма карточки в Студии
# --------------------------------------------------------------------------- #
PAIRS.append(('index.html', 1,
              r'''                                    <select id="card-name-pos" onchange="renderCardPreviewSoon()" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-2 text-[11px] focus:outline-none focus:border-fuchsia-500">
                                        <option value="bottom">Внизу (классика)</option>
                                        <option value="top">Вверху</option>
                                    </select>''',
              r'''                                    <select id="card-name-pos" onchange="renderCardPreviewSoon()" title="«Скрыть» — имени не видно на карте (в просмотре, в альбоме, во вскрытии). Само имя остаётся в каталоге и в списках" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-2 text-[11px] focus:outline-none focus:border-fuchsia-500">
                                        <option value="bottom">Внизу (классика)</option>
                                        <option value="top">Вверху</option>
                                        <!-- b475: имя можно убрать с лица карты -->
                                        <option value="hide">Скрыть (имя не показывать)</option>
                                    </select>'''))

PAIRS.append(('index.html', 1,
              r'''                                    <select id="card-desc-pos" onchange="renderCardPreviewSoon()" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-2 text-[11px] focus:outline-none focus:border-fuchsia-500">
                                        <option value="bottom">Внизу</option>
                                        <option value="top">Вверху</option>
                                        <option value="hide">Скрыть</option>
                                    </select>
                                </div>''',
              r'''                                    <select id="card-desc-pos" onchange="renderCardPreviewSoon()" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-2 text-[11px] focus:outline-none focus:border-fuchsia-500">
                                        <option value="bottom">Внизу</option>
                                        <option value="top">Вверху</option>
                                        <option value="hide">Скрыть</option>
                                    </select>
                                </div>
                                <!-- b475: видимость боевых статов (⚔/❤) на лице карты -->
                                <div>
                                    <span class="block text-[10px] text-slate-500 mb-1">Боевые статы на карте</span>
                                    <select id="card-stats-pos" onchange="renderCardPreviewSoon()" title="«Скрыть» — чисел ⚔ и ❤ не видно на карте (в просмотре, в альбоме, во вскрытии). Значения остаются и работают в бою" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-2 text-[11px] focus:outline-none focus:border-fuchsia-500">
                                        <option value="bottom">Внизу (классика)</option>
                                        <option value="hide">Скрыть (чисел не видно)</option>
                                    </select>
                                </div>'''))

PAIRS.append(('index.html', 1,
              r'''                                    <input type="number" id="card-hp" min="1" max="50" oninput="renderCardPreviewSoon()" placeholder="Здоровье" class="w-full bg-slate-950 border border-slate-700 rounded-lg pl-8 pr-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">
                                </div>
                            </div>
                        </div>
                            </div>''',
              r'''                                    <input type="number" id="card-hp" min="1" max="50" oninput="renderCardPreviewSoon()" placeholder="Здоровье" class="w-full bg-slate-950 border border-slate-700 rounded-lg pl-8 pr-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">
                                </div>
                            </div>
                        </div>
                            </div>
                            <!-- b475: что значит «Скрыть» у имени/описания/статов -->
                            <p class="text-[10px] text-slate-600 mt-2 leading-snug"><i class="fa-solid fa-eye-slash mr-1"></i>«Скрыть» убирает блок с лица карты: имени и/или чисел ⚔ ❤ не видно в просмотре карты, в сетке альбома и во вскрытии пака — остаётся только арт. Значения не удаляются: в бою, в «Строках» альбома и в списках Студии всё работает как раньше.</p>'''))


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
        print('b475: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b475: имя и боевые статы скрываются в настройках карты; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
