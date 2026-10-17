#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b451: форма «Новый Бустер Пак» — красивое расположение без пустых дыр.

Жалоба владельца: скриншот редактора пака, где левая колонка после поля
«Цена» обрывается и до низа формы зияет пустой прямоугольник, а правая
(премьера + цвет + формы + зубчики) уезжает в длинную «простыню»; живое
превью пака при этом вообще ниже сгиба.

Причина: поле формы было свёрстано как две НЕРАВНОВЕСНЫЕ колонки (b263):
слева обложка+цена (~150px), справа премьера+пять рядов свотчей (~450px).
Разница высот колонок и есть «дыра».

Лечение — перестройка формы в строки равной высоты (проверено скриншотами
tools/shots, puppeteer, ширины 948 и 1280):
  1. строка 1: название | описание (как было);
  2. строка 2: обложка | премьера — кнопка «Загрузить с устройства →
     GitHub» встала В ОДНУ СТРОКУ с полем ссылки (flex-wrap), ячейки
     одинаковой высоты;
  3. строка 3: цена (+подсказка) | цвет упаковки (4 свотча в один ряд) —
     обе ячейки ~72px;
  4. музыка вскрытия — полноширинная строка: заголовок и чекбокс
     «Проигрывать при вскрытии» на одной линии, поле с кнопками ниже,
     статус трека последней строкой;
  5. форма и зубчики упаковки — две равновесные карточки 2×2 половинки
     (свотчи + ряд «по умолчанию» в каждой), с подложкой и рамкой;
  6. «Перелив фольги» (b265) остался полноширинной строкой над кнопкой
     «Создать Бустер Пак» — 25 режимов ложатся рядами без дыр.
Высоких «простыней» и пустых колонок не осталось; форма стала короче, и
живое превью пака на десктопе видно на том же экране, что и поля.
Все id, onclick и oninput сохранены байт в байт — JS не трогаем.
Классы взяты только из собранного assets/tailwind.css (JIT отключён).

Проверка/применение:
    python3 tools/_b451_patch.py --check
    python3 tools/_b451_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'index.html')

START = '<div class="space-y-3 min-w-0">'
END_MARK = '<div class="flex gap-2">\n                            <button type="submit" id="pack-submit-btn"'
RAIL_OPEN = '<div class="min-w-0 lg:sticky lg:top-20">'

NEW_REGION = '''                        <div class="space-y-3 min-w-0">
                        <!-- b451: форма без «дыр»: строки равной высоты
                             (название|описание, обложка|премьера, цена|цвет),
                             музыка и перелив — полноширинные строки, форма и
                             зубчики — две равновесные карточки. Кнопка загрузки
                             стоит в одну строку с полем ссылки, чекбокс музыки —
                             в строке её заголовка. Пустых колонок больше нет. -->
<div class="grid sm:grid-cols-2 gap-3">
                        <div class="flex flex-col">
                            <label class="block text-[11px] font-medium text-slate-400 mb-1">Название пака</label>
                            <input type="text" id="pack-title" required oninput="renderPackStylePreview()" placeholder="Например: Mystery Set" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">
                        </div>
                        <div class="flex flex-col">
                            <label class="block text-[11px] font-medium text-slate-400 mb-1">Описание пака</label>
                            <input type="text" id="pack-desc" required placeholder="Эпичные технологии будущего" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">
                        </div>
                        </div>
<div class="grid sm:grid-cols-2 gap-3">
                        <div class="flex flex-col min-w-0">
                            <label class="block text-[11px] font-medium text-slate-400 mb-1">Ссылка на обложку (9:16)<span id="pack-image-lamp" style="width:10px;height:10px;border-radius:9999px;display:inline-block;vertical-align:middle;margin-left:6px;background:#475569;box-shadow:0 0 8px rgba(71,85,105,.7);" title="Индикатор арта: зелёный — вшит в сборку сайта; жёлтый — скачан авто-кэшем в устройство; красный — не вшит, грузится по ссылке; серый — ссылки нет"></span></label>
                            <div class="flex flex-wrap items-center gap-2">
                                <input type="url" id="pack-image" required oninput="renderPackStylePreview();nxEmbedLampRefresh('pack-image')" placeholder="https://images.unsplash.com/..." class="flex-1 min-w-0 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">
                                <button type="button" onclick="nxPickFileFor('pack-image')" class="px-2.5 py-1.5 bg-emerald-700/70 hover:bg-emerald-600 border border-emerald-500/40 rounded-lg text-[11px] font-semibold text-white transition shrink-0" title="Выберите файл картинки на устройстве — сайт сам зальёт его в папку media/ репозитория GitHub и подставит готовую ссылку в поле"><i class="fa-solid fa-upload mr-1"></i>Загрузить с устройства &rarr; GitHub</button>
                                <span id="pack-image-upl" class="text-[10px] text-slate-500"></span>
                            </div>
                        </div>
                        <!-- b165: премьера пака — до этой даты/времени пак виден как «Скоро» с отсчётом, купить нельзя -->
                        <div class="flex flex-col">
                            <label class="block text-[11px] font-medium text-slate-400 mb-1"><i class="fa-solid fa-clapperboard text-amber-400 mr-1"></i>Премьера — старт продажи (необязательно)</label>
                            <input type="datetime-local" id="pack-premiere" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-amber-500">
                        </div>
                        </div>
<div class="grid sm:grid-cols-2 gap-3">
                        <div class="flex flex-col">
                            <label class="block text-[11px] font-medium text-slate-400 mb-1">Цена (монеты)</label>
                            <input type="number" id="pack-price" required min="10" value="100" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">
                            <p class="text-[10px] text-slate-500 mt-1">Монеты за один пак; минимальная цена — 10.</p>
                        </div>
                        <!-- b451: цвет упаковки встал в пару к цене — обе ячейки одной высоты -->
                        <div class="flex flex-col min-w-0">
                            <label class="block text-[11px] font-medium text-slate-400 mb-1.5">Цвет упаковки</label>
                            <div id="pack-color-picker" class="grid grid-cols-4 gap-1 max-w-sm"><!-- b272: компакт --><!-- свотчи цветов --></div>
                        </div>
                        </div>
                        <!-- b266: музыка вскрытия — полноширинная строка: заголовок и чекбокс на
                             одной линии, поле с кнопками ниже, статус трека последней строкой -->
                        <div class="flex flex-col min-w-0">
                            <div class="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 mb-1">
                                <label class="text-[11px] font-medium text-slate-400"><i class="fa-solid fa-music text-fuchsia-400 mr-1"></i>Музыка вскрытия — ссылка на mp3</label>
                                <label class="flex items-center gap-2 cursor-pointer select-none">
                                    <input type="checkbox" id="pack-music-use" checked onchange="updatePackMusicHint()" class="accent-fuchsia-500 w-3.5 h-3.5">
                                    <span class="text-[10px] text-slate-400">Проигрывать при вскрытии этого пака</span>
                                </label>
                            </div>
                            <div class="flex flex-wrap gap-2">
                                <input type="url" id="pack-music" oninput="updatePackMusicHint()" placeholder="https://.../track.mp3" class="flex-1 min-w-0 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-fuchsia-500">
                                <button type="button" onclick="previewPackMusic()" class="px-2.5 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs font-semibold text-slate-200 transition" title="Прослушать 8 секунд"><i class="fa-solid fa-play"></i></button>
                                <button type="button" onclick="stopPackMusicPreview()" class="px-2.5 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs font-semibold text-slate-200 transition" title="Остановить"><i class="fa-solid fa-stop"></i></button>
                                <button type="button" onclick="clearPackMusicField()" class="px-2.5 py-2 bg-slate-800 hover:bg-red-900/50 border border-slate-700 hover:border-red-700 rounded-lg text-xs font-semibold text-slate-300 transition" title="Стереть ссылку mp3 этого пака"><i class="fa-solid fa-eraser"></i></button>
                                <button type="button" onclick="nxPickFileFor('pack-music','audio')" class="px-2.5 py-2 bg-emerald-700/70 hover:bg-emerald-600 border border-emerald-500/40 rounded-lg text-xs font-semibold text-white transition shrink-0" title="Выберите файл музыки на устройстве — сайт зальёт его в папку media/ репозитория GitHub и подставит ссылку в поле"><i class="fa-solid fa-upload mr-1"></i>На GitHub</button>
                                <span id="pack-music-upl" class="text-[10px] text-slate-500 self-center"></span>
                            </div>
                            <p id="pack-music-state" class="text-[10px] text-fuchsia-300/80 mt-1">трек не задан</p>
                        </div>
                        <!-- b451: форма и зубчики упаковки — две равновесные карточки на половинки:
                             свотчи и ряд «по умолчанию» в каждой; grid растягивает их до одной
                             высоты, остаток растворяется в отступах карточки -->
<div class="grid sm:grid-cols-2 gap-3">
                        <!-- b446: форма упаковки — свой ряд превьюшек и ряд «по умолчанию» -->
                        <div class="flex flex-col gap-2 min-w-0 bg-slate-950/40 border border-slate-800 rounded-xl p-2.5">
                            <div class="text-[10px] font-bold uppercase tracking-wide text-slate-500">Форма упаковки</div>
                            <div id="pack-skin-picker" class="grid grid-cols-5 gap-1 max-w-sm"><!-- свотчи форм --></div>
                            <div class="text-[10px] font-bold uppercase tracking-wide text-slate-500">Форма по умолчанию <span class="normal-case font-normal text-slate-600">(для паков без своей формы)</span></div>
                            <div id="pack-skin-default" class="flex flex-wrap gap-1"><!-- кнопки общей формы --></div>
                        </div>
                        <!-- b448: кромка запайки -->
                        <div class="flex flex-col gap-2 min-w-0 bg-slate-950/40 border border-slate-800 rounded-xl p-2.5">
                            <div class="text-[10px] font-bold uppercase tracking-wide text-slate-500">Зубчики упаковки</div>
                            <div id="pack-crimp-picker" class="grid grid-cols-5 gap-1 max-w-sm"><!-- свотчи кромок --></div>
                            <div class="text-[10px] font-bold uppercase tracking-wide text-slate-500">Зубчики по умолчанию <span class="normal-case font-normal text-slate-600">(для паков без своей кромки; видны на «Фольге»)</span></div>
                            <div id="pack-crimp-default" class="grid grid-cols-5 gap-1 max-w-sm"><!-- кнопки общей кромки --></div>
                        </div>
                        </div>
                        </div>
                        <div class="min-w-0 lg:sticky lg:top-20">
                            <!-- b451: до lg превью — узкая центрированная карточка, а не полоса во всю ширину -->
                            <div class="flex flex-col items-center gap-2 bg-slate-950/70 border border-slate-800 rounded-xl p-3 max-w-md mx-auto">
                                <div id="pack-style-preview" style="position:relative;width:120px;height:220px;flex:none;"></div>
                                <p class="text-[11px] text-slate-500 font-medium mt-1">Живое превью пака</p>
                                <p id="pack-style-name" class="text-xs font-bold text-white truncate mt-0.5 max-w-full"></p>
                                <p class="text-[10px] text-slate-500 mt-1 text-center">Цвет и перелив применяются к паку в магазине и при вскрытии.</p>
                            </div>
                        </div>
                        </div>
                        <!-- b265: «Перелив фольги» — полноширинная строка над кнопками
                             «Создать Бустер Пак»: 25 режимов ложатся рядами по всей
                             ширине формы, без дыр и узких колонок -->
                        <div>
                            <label class="block text-[11px] font-medium text-slate-400 mb-1.5">Перелив фольги</label>
                            <div id="pack-shimmer-picker" class="grid grid-cols-5 sm:grid-cols-9 lg:grid-cols-[repeat(15,minmax(0,1fr))] gap-1"><!-- b272: компакт — 15 колонок на десктопе --><!-- режимы перелива --></div>
                        </div>
'''


def read():
    with io.open(HTML, encoding='utf-8') as f:
        return f.read()


def region_bounds(html):
    """Границы старой разметки: от начала колонки полей до конца блока
    «Перелив фольги» (включительно), прямо перед кнопками submit."""
    i = html.find(START)
    if i < 0:
        return None
    j = html.find(END_MARK, i)
    if j < 0:
        return None
    k = html.rfind('</div>', i, j)
    if k < 0:
        return None
    k += len('</div>')
    return i, k


def check(html):
    problems = []
    if 'b451: форма без «дыр»' in html:
        return ['b451 уже применён']
    b = region_bounds(html)
    if not b:
        return ['не найден старый блок формы пака (b451 не к чему применять)']
    old = html[b[0]:b[1]]
    for needle in ('pack-crimp-default', 'pack-shimmer-picker', RAIL_OPEN):
        if needle not in old:
            problems.append('в старом регионе нет: ' + needle)
    # регион начинается ВНУТРИ внешнего грида и содержит его закрывающий
    # </div>, поэтому закрывающих на один больше
    if old.count('</div>') != old.count('<div') + 1:
        problems.append('старый регион небалансен по <div>: %d/%d'
                        % (old.count('<div'), old.count('</div>')))
    if NEW_REGION.count('</div>') != NEW_REGION.count('<div') + 1:
        problems.append('новый регион небалансен по <div>')
    return problems


def main():
    html = read()
    problems = check(html)
    if problems:
        for p in problems:
            print('ПРОБЛЕМА:', p)
        return 1
    if '--check' in sys.argv:
        print('b451: старый блок формы на месте, можно применять')
        return 0
    i, k = region_bounds(html)
    new = html[:i] + NEW_REGION + html[k:]
    # баланс <div> всего документа не должен измениться
    d_old = html.count('<div') - html.count('</div>')
    d_new = new.count('<div') - new.count('</div>')
    if d_old != d_new:
        print('ПРОБЛЕМА: баланс <div> изменился: %d -> %d' % (d_old, d_new))
        return 1
    for needle in ('id="pack-color-picker"', 'id="pack-shimmer-picker"',
                   'id="pack-skin-picker"', 'id="pack-crimp-picker"',
                   'id="pack-skin-default"', 'id="pack-crimp-default"',
                   'id="pack-music-use"', 'id="pack-music-state"',
                   'id="pack-image-lamp"', 'id="pack-style-preview"'):
        if new.count(needle) != 1:
            print('ПРОБЛЕМА: id потерян/задвоен:', needle)
            return 1
    with io.open(HTML, 'w', encoding='utf-8') as f:
        f.write(new)
    print('b451: форма пака перестроена без пустых дыр (%d -> %d байт)'
          % (len(html), len(new)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
