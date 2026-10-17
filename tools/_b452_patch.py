#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b452: колонка превью пака — на всю высоту формы, без дыры под превью.

Жалоба владельца (скриншот с крестами): после b451 поля стоят ровными
строками, но СПРАВА под карточкой живого превью остаётся пустой столбец
до низа формы (внешний грид был items-start — колонки не растягивались).

Лечение:
  1. у внешнего грида формы убран items-start — колонки тянутся до общей
     высоты (grid stretch);
  2. колонка превью стала flex-колонкой (min-w-0 flex flex-col gap-3,
     sticky убран: форма теперь короткая, липкость не нужна);
  3. под превью добавлена карточка «Подсказки» (арт 9:16, премьера,
     mp3-превью, форма/зубчики/цвет/перелив) с flex-1 — она растягивается
     ровно до высоты колонки полей: пустого столбца не остаётся ни на
     одной ширине ≥lg; до lg обе карточки превью стоят стопкой по центру
     (max-w-md mx-auto).
Тексты подсказок собраны из уже имеющихся в форме подписей — новой
сущности не появилось. JS не тронут; классы и иконки — только из
собранного assets/tailwind.css и fa.css.

Проверка/применение:
    python3 tools/_b452_patch.py --check
    python3 tools/_b452_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'index.html')

PAIRS = []

PAIRS.append(('внешний грид формы пака без items-start', """
                        <div class="grid lg:grid-cols-[minmax(0,1fr)_250px] gap-4 items-start">
                                                <div class="space-y-3 min-w-0">
                        <!-- b451: форма без «дыр»: строки равной высоты
""", """
                        <!-- b452: stretch по умолчанию — колонка превью тянется
                             до высоты полей, дыра под превью исчезает -->
                        <div class="grid lg:grid-cols-[minmax(0,1fr)_250px] gap-4">
                                                <div class="space-y-3 min-w-0">
                        <!-- b451: форма без «дыр»: строки равной высоты
"""))

PAIRS.append(('колонка превью — flex-колонка', """
                        <div class="min-w-0 lg:sticky lg:top-20">
                            <!-- b451: до lg превью — узкая центрированная карточка, а не полоса во всю ширину -->
""", """
                        <!-- b452: колонка превью на всю высоту формы: превью + подсказки -->
                        <div class="min-w-0 flex flex-col gap-3">
                            <!-- b451: до lg превью — узкая центрированная карточка, а не полоса во всю ширину -->
"""))

PAIRS.append(('карточка «Подсказки» с flex-1 под превью', """
                                <p class="text-[10px] text-slate-500 mt-1 text-center">Цвет и перелив применяются к паку в магазине и при вскрытии.</p>
                            </div>
                        </div>
""", """
                                <p class="text-[10px] text-slate-500 mt-1 text-center">Цвет и перелив применяются к паку в магазине и при вскрытии.</p>
                            </div>
                            <!-- b452: «Подсказки» — полезный заполнитель колонки превью;
                                 flex-1 растягивает карточку ровно до высоты колонки полей -->
                            <div class="flex-1 flex flex-col gap-1.5 bg-slate-950/70 border border-slate-800 rounded-xl p-3 max-w-md mx-auto">
                                <div class="text-[10px] font-bold uppercase tracking-wide text-slate-500"><i class="fa-solid fa-circle-info text-sky-400 mr-1"></i>Подсказки</div>
                                <p class="text-[10px] text-slate-400 leading-relaxed"><i class="fa-solid fa-image text-violet-400 mr-1"></i>Обложка 9:16 — ссылкой или «Загрузить с устройства»: сайт сам зальёт файл в media/ и подставит ссылку.</p>
                                <p class="text-[10px] text-slate-400 leading-relaxed"><i class="fa-solid fa-clapperboard text-amber-400 mr-1"></i>До премьеры пак виден как «Скоро» с отсчётом — купить нельзя.</p>
                                <p class="text-[10px] text-slate-400 leading-relaxed"><i class="fa-solid fa-music text-fuchsia-400 mr-1"></i>mp3 вскрытия — превью 8 секунд; с чекбоксом трек играет при вскрытии пака.</p>
                                <p class="text-[10px] text-slate-400 leading-relaxed"><i class="fa-solid fa-box text-emerald-400 mr-1"></i>Форма и зубчики — силуэт пака, цвет и перелив — фольга. «По умолчанию» — для паков без своих.</p>
                            </div>
                        </div>
"""))


def read():
    with io.open(HTML, encoding='utf-8') as f:
        return f.read()


def main():
    html = read()
    applied = sum(1 for _, _, new in PAIRS if new.strip() in html)
    if applied == len(PAIRS):
        if '--check' in sys.argv:
            print('b452: всё на месте (stretch, flex-колонка превью, подсказки)')
            return 0
        print('b452: уже применён')
        return 1
    if applied:
        print('ПРОБЛЕМА: b452 применён частично (%d/%d)' % (applied, len(PAIRS)))
        return 1
    new = html
    for label, old, rep in PAIRS:
        o, r = old.strip('\n'), rep.strip('\n')
        if new.count(o) != 1:
            print('ПРОБЛЕМА: якорь не уникален/не найден (%d): %s' % (new.count(o), label))
            return 1
        new = new.replace(o, r, 1)
    d_old = html.count('<div') - html.count('</div>')
    d_new = new.count('<div') - new.count('</div>')
    if d_old != d_new:
        print('ПРОБЛЕМА: баланс <div> изменился: %d -> %d' % (d_old, d_new))
        return 1
    if '--check' in sys.argv:
        print('b452: якоря найдены, можно применять')
        return 0
    with io.open(HTML, 'w', encoding='utf-8') as f:
        f.write(new)
    print('b452: колонка превью на всю высоту формы (%d -> %d байт)'
          % (len(html), len(new)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
