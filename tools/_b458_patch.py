#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b458: форма карточки — предпросмотр живой сразу + дыра под музыкой убрана.

Отзыв владельца (скриншот с крестами по форме «Новая Карточка»):
  1. панель «Живой предпросмотр карты и ауры за ней» ПУСТАЯ при открытии
     формы — renderCardPreview() вызывался только на input/change полей,
     первая отрисовка случалась после первого же нажатия клавиши;
  2. слева под кнопкой «Загрузить с устройства» — пустое место: слайдеры
     кадрирования (b456/b457) сидели ВНУТРИ ячейки картинки и делали её
     выше ячейки музыки; справа под музыкой зияла дыра.

Лечение:
  1. showStudioSec('cards') сразу дёргает renderCardPreview() — превью
     рисуется дефолтной картой ещё до ввода (try/catch: на битых
     состояниях раздел не падает);
  2. кнопка загрузки встала В ОДНУ СТРОКУ с полем ссылки на картинку
     (flex-wrap, как в форме пака b451), под полем — строка-подсказка
     «Арт 9:16; рамка подрезает края…», выравнивающая ячейку с музыкой;
  3. слайдеры «Масштаб / Сдвиг по вертикали / Сдвиг по горизонтали»
     вынесены из ячейки картинки в отдельную полноширинную строку
     (grid-cols-3, mt-2 убран — space-y-3 колонки даёт ритм) — под
     музыкой больше нет пустой колонки.
id/oninput/onclick сохранены; JS-логика кадрирования не менялась.

Проверка/применение:
    python3 tools/_b458_patch.py --check
    python3 tools/_b458_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'index.html')
APPJS = os.path.join(ROOT, 'assets', 'app.js')

# --- app.js: предпросмотр при открытии раздела «Карточки» ---
JS_OLD = "            if (name === 'story' && window.s9OnShow) window.s9OnShow(); // b254: relayout встроенного резчика"
JS_NEW = ("            if (name === 'cards') { try { renderCardPreview(); } catch (e) {} } // b458: предпросмотр рисуется сразу, а не только после первого ввода\n"
          "            if (name === 'story' && window.s9OnShow) window.s9OnShow(); // b254: relayout встроенного резчика")


def read(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def write(p, s):
    with io.open(p, 'w', encoding='utf-8') as f:
        f.write(s)


def find(lines, needle, start=0):
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i
    return -1


def patch_html(lines):
    """Возвращает новые строки или None+ошибка."""
    out = list(lines)

    # 1) поле ссылки + кнопка загрузки в одну строку, подсказка снизу
    i_in = find(out, 'id="card-image" required')
    i_up = find(out, "nxPickFileFor('card-image')")
    if i_in < 0 or i_up != i_in + 1:
        return None, 'не найдены соседние строки card-image/кнопка загрузки'
    new_cell = [
        '                            <div class="flex flex-wrap items-center gap-2">',
        '                                <input type="url" id="card-image" required oninput="renderCardPreview();nxEmbedLampRefresh(\'card-image\')" placeholder="https://images.unsplash.com/..." class="flex-1 min-w-0 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">',
        '                                <button type="button" onclick="nxPickFileFor(\'card-image\')" class="px-2.5 py-1.5 bg-emerald-700/70 hover:bg-emerald-600 border border-emerald-500/40 rounded-lg text-[11px] font-semibold text-white transition shrink-0" title="Выберите файл картинки на устройстве — сайт сам зальёт его в папку media/ репозитория GitHub и подставит готовую ссылку в поле"><i class="fa-solid fa-upload mr-1"></i>Загрузить с устройства &rarr; GitHub</button>',
        '                                <span id="card-image-upl" class="text-[10px] text-slate-500"></span>',
        '                            </div>',
        '                            <p class="text-[10px] text-slate-500 mt-1">Арт 9:16; рамка подрезает края — кадрирование правьте слайдерами ниже.</p>',
    ]
    out[i_in:i_up + 1] = new_cell

    # 2) вырезать блок слайдеров из ячейки картинки
    i_c = find(out, '<!-- b456: масштаб арта')
    if i_c < 0:
        return None, 'не найден комментарий b456'
    depth = 0
    i_end = -1
    for j in range(i_c + 1, len(out)):
        depth += out[j].count('<div') - out[j].count('</div>')
        if depth <= 0 and '</div>' in out[j]:
            i_end = j
            break
    if i_end < 0:
        return None, 'не найден конец блока слайдеров'
    slider = out[i_c:i_end + 1]
    del out[i_c:i_end + 1]
    # правки внутри вырезанного блока: комментарий + убрать mt-2
    slider[0] = '                        <!-- b456/b458: слайдеры кадрирования арта — отдельная полноширинная\n                             строка: значения сохраняются в layout карты (artZoom/artPosY/artPosX)\n                             и видны во всех рендерах -->'
    del slider[1:3]  # хвост старого трёхстрочного комментария b456
    slider = [l.replace('grid grid-cols-3 gap-3 mt-2', 'grid grid-cols-3 gap-3') for l in slider]
    # дедент на 4 пробела (из ячейки 28sp на уровень колонки 24sp)
    slider = [(l[4:] if l.startswith('    ') else l) for l in slider]

    # 3) вставить после закрывающего </div> грида [картинка|музыка]
    i_note = find(out, 'Трек играет, пока карта открыта')
    if i_note < 0:
        return None, 'не найдена подпись музыки'
    i_music_close = i_note + 1   # </div> ячейки музыки
    i_grid_close = i_note + 2    # </div> грида
    if '</div>' not in out[i_music_close] or '</div>' not in out[i_grid_close]:
        return None, 'не совпали закрывающие </div> после подписи музыки'
    out[i_grid_close + 1:i_grid_close + 1] = slider

    return out, None


def main():
    html = read(HTML)
    js = read(APPJS)
    done_html = 'b458: слайдеры кадрирования арта' in html
    done_js = "if (name === 'cards') { try { renderCardPreview();" in js
    if done_html and done_js:
        print('b458: уже применён' if '--check' not in sys.argv else 'b458: всё на месте')
        return 0
    if done_html or done_js:
        print('ПРОБЛЕМА: b458 применён частично (html=%s js=%s)' % (done_html, done_js))
        return 1
    if js.count(JS_OLD) != 1:
        print('ПРОБЛЕМА: якорь showStudioSec в app.js не уникален (%d)' % js.count(JS_OLD))
        return 1
    lines = html.split('\n')
    new_lines, err = patch_html(lines)
    if err:
        print('ПРОБЛЕМА:', err)
        return 1
    new_html = '\n'.join(new_lines)
    d_old = html.count('<div') - html.count('</div>')
    d_new = new_html.count('<div') - new_html.count('</div>')
    if d_old != d_new:
        print('ПРОБЛЕМА: баланс <div> изменился: %d -> %d' % (d_old, d_new))
        return 1
    for needle in ('id="card-artzoom"', 'id="card-arty"', 'id="card-artx"', 'id="card-image-upl"'):
        if new_html.count(needle) != 1:
            print('ПРОБЛЕМА: id потерян/задвоен:', needle)
            return 1
    if '--check' in sys.argv:
        print('b458: якоря на месте, можно применять')
        return 0
    write(HTML, new_html)
    write(APPJS, js.replace(JS_OLD, JS_NEW, 1))
    print('b458: предпросмотр рисуется сразу; слайдеры — отдельная строка; дыра под музыкой убрана')
    return 0


if __name__ == '__main__':
    sys.exit(main())
