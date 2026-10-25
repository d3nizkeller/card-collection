#!/usr/bin/env python3
# b501: редизайн внешнего вида «Русского лота».
# Владелец: «переработай внешний вид лото». Новый образ — как на референс-фото:
# деревянный стол-комната, красное сукно стола с золотой строчкой, бочонки
# торцом к игроку (деревянный цилиндр + номерное кольцо), куча бочонков внахлёст,
# белая бумажная карточка с печатной пунктирной рамкой (закрытые числа накрыты
# бочонками-фишками), табло — бумажный тиражный лист, кнопка розыгрыша — сукно мешка.
# Правки только в index.html (CSS-блок b500 заменяется на b501 + 2 класса разметки).
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))


def read(p):
    with io.open(os.path.join(ROOT, p), 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write(p, s):
    with io.open(os.path.join(ROOT, p), 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def main():
    check = '--check' in sys.argv
    s = read('index.html')
    problems = []

    css_old_start = s.find('    /* ===== b500: Русское лото')
    css_end = s.find('    </style>', css_old_start)
    if css_old_start < 0 or css_end < 0:
        problems.append('index.html: CSS-блок b500 не найден')
    new_css = io.open(os.path.join(HERE, '_b501_loto_css.txt'), encoding='utf-8', newline='').read()

    panel_old = '<div id="lobby-loto" class="space-y-6 hidden">\n                    <div class="bg-gradient-to-r from-slate-900 to-slate-900/60 p-4 sm:p-6 rounded-2xl border border-slate-800">'
    panel_new = '<div id="lobby-loto" class="space-y-6 hidden">\n                    <div class="loto-room p-4 sm:p-6 rounded-2xl border border-amber-900/40">'
    if s.count(panel_old) != 1:
        problems.append('index.html: якорь панели лобби Лото найден %d раз' % s.count(panel_old))

    draw_old = 'id="loto-draw" onclick="lotoDraw()" class="hidden px-5 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-sm font-black transition shadow-lg shadow-emerald-950/40"'
    draw_new = 'id="loto-draw" onclick="lotoDraw()" class="hidden px-5 py-2.5 rounded-xl loto-draw-btn text-amber-100 text-sm font-black transition shadow-lg shadow-red-950/50 border border-amber-400/60"'
    if s.count(draw_old) != 1:
        problems.append('index.html: якорь кнопки розыгрыша найден %d раз' % s.count(draw_old))

    if '/* ===== b501:' in s:
        problems.append('index.html: патч b501 уже применён')
    if problems:
        for x in problems:
            print('PROBLEM:', x)
        return 1
    if check:
        print('OK: патч b501 применим')
        return 0

    s = s[:css_old_start] + new_css + s[css_end:]
    s = s.replace(panel_old, panel_new, 1)
    s = s.replace(draw_old, draw_new, 1)
    write('index.html', s)
    print('b501: внешний вид лото переработан')
    return 0


if __name__ == '__main__':
    sys.exit(main())
