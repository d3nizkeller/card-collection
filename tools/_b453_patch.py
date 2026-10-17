#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b453: «Перелив фольги» — внутрь колонки полей, лента без пустой полосы.

После b452 колонки внешнего грида тянутся до общей высоты (stretch).
Колонка полей короче колонки превью+подсказки, поэтому ПОСЛЕ карточек
«форма|зубчики» и до полноширинного ряда «Перелив фольги» (который стоял
ВНЕ внешнего грида) оставалась пустая полоса в высоту растяжки.

Лечение: ряд «Перелив фольги» перенесён ВНУТРЬ колонки полей последним
блоком (сразу после карточек свотчей). Тогда высота колонки полей
включает перелив, растяжка достаётся карточке «Подсказки» (flex-1), и
лента формы идёт сплошняком: строки → карточки → перелив → кнопка.
На <lg ничего не меняется: колонка полей и так во всю ширину.
Ширина ряда перелива на lg = ширина колонки полей (15 колонок свотчей).

Проверка/применение:
    python3 tools/_b453_patch.py --check
    python3 tools/_b453_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'index.html')

SHIMMER_BLOCK = '''                        <!-- b265: «Перелив фольги» — полноширинная строка над кнопками
                             «Создать Бустер Пак»: 25 режимов ложатся рядами по всей
                             ширине формы, без дыр и узких колонок -->
                        <div>
                            <label class="block text-[11px] font-medium text-slate-400 mb-1.5">Перелив фольги</label>
                            <div id="pack-shimmer-picker" class="grid grid-cols-5 sm:grid-cols-9 lg:grid-cols-[repeat(15,minmax(0,1fr))] gap-1"><!-- b272: компакт — 15 колонок на десктопе --><!-- режимы перелива --></div>
                        </div>
'''

SHIMMER_BLOCK_NEW = '''                        <!-- b453: «Перелив фольги» — последний блок колонки полей:
                             лента формы идёт сплошняком, пустой полосы между
                             карточками и переливом больше нет -->
                        <div>
                            <label class="block text-[11px] font-medium text-slate-400 mb-1.5">Перелив фольги</label>
                            <div id="pack-shimmer-picker" class="grid grid-cols-5 sm:grid-cols-9 lg:grid-cols-[repeat(15,minmax(0,1fr))] gap-1"><!-- b272: компакт — 15 колонок на десктопе --><!-- режимы перелива --></div>
                        </div>
'''

# 1) убрать перелив с прежнего места (после закрывающего </div> внешнего грида)
OLD_REMOVE = '                        </div>\n' + SHIMMER_BLOCK
NEW_REMOVE = '                        </div>\n'

# 2) вставить последним блоком колонки полей (перед её закрывающим </div>)
OLD_INSERT = '''                        </div>
                        </div>
                        <!-- b452: колонка превью на всю высоту формы: превью + подсказки -->'''
NEW_INSERT = '''                        </div>
''' + SHIMMER_BLOCK_NEW + '''                        </div>
                        <!-- b452: колонка превью на всю высоту формы: превью + подсказки -->'''


def read():
    with io.open(HTML, encoding='utf-8') as f:
        return f.read()


def main():
    html = read()
    done = ('b453: «Перелив фольги» — последний блок колонки полей' in html)
    if done and '--check' in sys.argv:
        print('b453: уже применён')
        return 0
    if done:
        print('b453: уже применён')
        return 1
    if html.count(OLD_REMOVE) != 1:
        print('ПРОБЛЕМА: якорь удаления перелива не уникален/не найден (%d)'
              % html.count(OLD_REMOVE))
        return 1
    if html.count(OLD_INSERT) != 1:
        print('ПРОБЛЕМА: якорь вставки не уникален/не найден (%d)'
              % html.count(OLD_INSERT))
        return 1
    new = html.replace(OLD_REMOVE, NEW_REMOVE, 1).replace(OLD_INSERT, NEW_INSERT, 1)
    d_old = html.count('<div') - html.count('</div>')
    d_new = new.count('<div') - new.count('</div>')
    if d_old != d_new:
        print('ПРОБЛЕМА: баланс <div> изменился: %d -> %d' % (d_old, d_new))
        return 1
    if new.count('id="pack-shimmer-picker"') != 1:
        print('ПРОБЛЕМА: pack-shimmer-picker задвоен/потерян')
        return 1
    if '--check' in sys.argv:
        print('b453: якоря найдены, можно применять')
        return 0
    with io.open(HTML, 'w', encoding='utf-8') as f:
        f.write(new)
    print('b453: перелив перенесён в колонку полей (%d -> %d байт)'
          % (len(html), len(new)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
