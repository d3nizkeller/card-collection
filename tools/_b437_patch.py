#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b437: строка «Открыть сразу: 1 5 10 20 40 | MAX | [40] | итого» — в одну строку.

Заявка владельца: на телефоне панель количества паков переносилась на две
строки (1-я: «Открыть сразу: 1 5 10 20 40», 2-я: «MAX 40 итого 40m»).
Нужно, чтобы всё было в одну строку.

Что делает патч (assets/app.js, carouselUpdateDetail, #nx-qty-row):
  1. контейнер: flex-wrap -> flex-nowrap + overflow-x-auto + no-scrollbar
     (тот же приём, что у полос ставок bets-strip): переноса нет НИКОГДА,
     в крайнем случае строка прокручивается по горизонтали без скроллбара;
  2. надпись «Открыть сразу:» на узких экранах (<md) сворачивается в иконку
     (title/aria-label сохраняют смысл), на md+ — как раньше;
  3. kompakтнее: gap-1 (md:gap-1.5), кнопки px-1.5, поле ввода w-12,
     у всех детей shrink-0 + whitespace-nowrap у «итого» — ничего не сжимается
     и не переносится.
  4. Тег сборки nxmob152 -> nxmob153 (index.html ?v= x8, sw.js VERSION,
     tools/build.py BUILD_TAG).

Проверка/применение:
    python3 tools/_b437_patch.py --check   # только проверить, что всё легло
    python3 tools/_b437_patch.py           # применить (идемпотентно)
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OLD_ROW = """<div class="mt-3 flex flex-wrap items-center gap-1.5" id="nx-qty-row">
                            <span class="text-[10px] font-bold text-slate-400 mr-0.5"><i class="fa-solid fa-layer-group mr-1 text-sky-300"></i>Открыть сразу:</span>
                            ${NX_QTY_PRESETS.map(v => '<button onclick="nxSetPackQty(' + v + ')" class="px-2 py-1 rounded-lg text-[10px] font-black border ' + (nxPackQty === v ? 'bg-sky-500/20 border-sky-400/60 text-sky-200' : 'bg-slate-800/70 border-slate-700 text-slate-300 hover:bg-slate-700') + '">' + v + '</button>').join('')}
                            <button onclick="nxSetPackQty(Math.floor(state.coins / ${salePrice}))" class="px-2 py-1 rounded-lg text-[10px] font-black border bg-slate-800/70 border-slate-700 text-amber-300 hover:bg-slate-700" title="Открыть максимум паков на текущий баланс">MAX</button>
                            <input id="nx-qty-input" type="number" min="1" max="99" value="${nxPackQty}" onchange="nxSetPackQty(this.value)" class="w-14 px-1.5 py-1 rounded-lg bg-slate-800/80 border border-slate-700 text-[11px] font-black text-center text-slate-100" aria-label="Количество паков">
                            <span class="text-[10px] font-bold text-amber-300">итого ${fmtCoins(salePrice * nxPackQty)}</span>"""

NEW_ROW = """<!-- b437: строка количества паков — всегда в одну строку: без переноса (flex-nowrap), на узких экранах компактнее, а в крайнем случае прокручивается по горизонтали без видимого скроллбара (no-scrollbar) --><div class="mt-3 flex flex-nowrap items-center gap-1 md:gap-1.5 overflow-x-auto no-scrollbar" id="nx-qty-row">
                            <span class="shrink-0 text-[10px] font-bold text-slate-400 mr-0.5" title="Открыть сразу" aria-label="Открыть сразу"><i class="fa-solid fa-layer-group mr-0 md:mr-1 text-sky-300"></i><span class="hidden md:inline">Открыть сразу:</span></span>
                            ${NX_QTY_PRESETS.map(v => '<button onclick="nxSetPackQty(' + v + ')" class="shrink-0 px-1.5 py-1 rounded-lg text-[10px] font-black border ' + (nxPackQty === v ? 'bg-sky-500/20 border-sky-400/60 text-sky-200' : 'bg-slate-800/70 border-slate-700 text-slate-300 hover:bg-slate-700') + '">' + v + '</button>').join('')}
                            <button onclick="nxSetPackQty(Math.floor(state.coins / ${salePrice}))" class="shrink-0 px-1.5 py-1 rounded-lg text-[10px] font-black border bg-slate-800/70 border-slate-700 text-amber-300 hover:bg-slate-700" title="Открыть максимум паков на текущий баланс">MAX</button>
                            <input id="nx-qty-input" type="number" min="1" max="99" value="${nxPackQty}" onchange="nxSetPackQty(this.value)" class="shrink-0 w-12 px-1 py-1 rounded-lg bg-slate-800/80 border border-slate-700 text-[11px] font-black text-center text-slate-100" aria-label="Количество паков">
                            <span class="shrink-0 whitespace-nowrap text-[10px] font-bold text-amber-300">итого ${fmtCoins(salePrice * nxPackQty)}</span>"""

TAG_OLD = 'nxmob152'
TAG_NEW = 'nxmob153'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, text):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
        f.write(text)


def apply():
    app = read('assets/app.js')
    if NEW_ROW not in app:
        assert OLD_ROW in app, 'b437: не найден старый блок #nx-qty-row'
        assert app.count(OLD_ROW) == 1, 'b437: старый блок #nx-qty-row не уникален'
        app = app.replace(OLD_ROW, NEW_ROW, 1)
        write('assets/app.js', app)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b437: не найден тег %s в %s' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b437: применено')


def check():
    app = read('assets/app.js')
    problems = []
    if NEW_ROW not in app:
        problems.append('app.js: нет нового блока #nx-qty-row (flex-nowrap/no-scrollbar)')
    if OLD_ROW in app:
        problems.append('app.js: остался старый блок #nx-qty-row (flex-wrap)')
    if app.count('id="nx-qty-row"') != 1:
        problems.append('app.js: #nx-qty-row встречается %d раз(а), ждём 1' % app.count('id="nx-qty-row"'))
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не nxmob153' % rel)
    if problems:
        print('b437 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b437 --check: всё на месте (одна строка #nx-qty-row, тег nxmob153)')


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
