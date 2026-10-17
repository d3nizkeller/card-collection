#!/usr/bin/env python3
# b455: правая колонка формы «Новый Бустер Пак» — финальная полировка.
#
# После b454 (карточка превью flex-1 + justify-center) у карточки «Подсказки»
# оставался flex-1 от b453: лишняя высота колонки делилась пополам, и под
# текстом подсказок оставалось пустое место. Теперь подсказки держат
# естественную высоту, а всю растяжку забирает превью — пак стоит по центру
# «витрины», пустых дыр в колонке нет.
#
# Применение: python3 tools/_b455_patch.py [--check]
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'index.html')

OLD = '<div class="flex-1 flex flex-col gap-1.5 bg-slate-950/70 border border-slate-800 rounded-xl p-3 max-w-md mx-auto">\n                                <div class="text-[10px] font-bold uppercase tracking-wide text-slate-500"><i class="fa-solid fa-circle-info text-sky-400 mr-1"></i>Подсказки</div>'
NEW = ('<!-- b455: подсказки — естественной высоты; всю растяжку\n'
       '                                 колонки забирает карточка превью (flex-1, пак по центру) -->\n'
       '                            <div class="flex flex-col gap-1.5 bg-slate-950/70 border border-slate-800 rounded-xl p-3 max-w-md mx-auto">\n'
       '                                <div class="text-[10px] font-bold uppercase tracking-wide text-slate-500"><i class="fa-solid fa-circle-info text-sky-400 mr-1"></i>Подсказки</div>')


def main():
    s = io.open(HTML, encoding='utf-8').read()
    done = 'b455: подсказки — естественной высоты' in s
    if done and '--check' in sys.argv:
        print('b455: уже применён')
        return 0
    if done:
        print('b455: уже применён')
        return 1
    if s.count(OLD) != 1:
        print('ПРОБЛЕМА: якорь карточки подсказок не уникален/не найден (%d)' % s.count(OLD))
        return 1
    if '--check' in sys.argv:
        print('b455: якорь найден, можно применять')
        return 0
    s = s.replace(OLD, NEW, 1)
    io.open(HTML, 'w', encoding='utf-8').write(s)
    print('b455: подсказки естественной высоты, растяжку берёт превью')
    return 0


if __name__ == '__main__':
    sys.exit(main())
