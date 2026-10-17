#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b445: чипсы шансов редкости («Обычная 60% … Легендарная 3%») — в одну строку.

Заявка владельца: скриншот, где ряд чипсов переносится на вторую строку
(«Легендарная 3%» уезжает вниз).

Диагноз: renderPackOdds() (assets/app.js) рисует ряд как
    <div class="flex flex-wrap gap-1 mt-2">
flex-wrap и переносит четвёртый чипс, как только ряд не влезает в карточку пака
(на телефоне карточка ~320px, четыре чипса в 10px с паддингом 6px не влезают).

Лечение:
  1. контейнер: flex-nowrap + items-center + overflow-x-auto (на очень узком
     экране ряд прокручивается пальцем вместо переноса), класс .nx-odds;
  2. чипсы: whitespace-nowrap shrink-0 — текст не рвётся и чипс не сжимается
     в кашу; на мобильных шрифт 9px и паддинг 4px (с sm: обратно 10px/6px) —
     четыре чипса влезают в 320px с запасом;
  3. CSS в index.html: .nx-odds прячет скроллбар (scrollbar-width:none для
     Firefox, ::-webkit-scrollbar для Chrome/Safari), иначе под рядом
     появлялась бы серая полоса.

Тег сборки nxmob174 -> nxmob175 (index.html ?v=, sw.js VERSION, build.py BUILD_TAG),
иначе sw.js с cache-first для /assets/ отдаст игрокам старый app.js.

Проверка/применение:
    python3 tools/_b445_patch.py --check
    python3 tools/_b445_patch.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = []

PAIRS.append(('app.js: ряд чипсов редкости в одну строку', """
            return `<div class="flex flex-wrap gap-1 mt-2">${odds.map(o => `<span class="text-[10px] font-semibold px-1.5 py-0.5 rounded border ${cls[o.r] || cls.common}">${RARITY_LABELS_RU[o.r]} ${o.pct}%</span>`).join('')}</div>`;
""", """
            // b445: строго одна строка. flex-wrap переносил четвёртый чипс,
            // как только ряд не влезал в карточку пака на телефоне. Теперь ряд
            // не переносится: чипсы не рвутся (whitespace-nowrap) и не сжимаются
            // (shrink-0), на мобильных чуть мельче шрифт и паддинг, а если экран
            // совсем узкий — ряд прокручивается пальцем (overflow-x-auto).
            return `<div class="nx-odds flex flex-nowrap items-center gap-0.5 sm:gap-1 mt-2 overflow-x-auto">${odds.map(o => `<span class="text-[9px] sm:text-[10px] font-semibold px-1 sm:px-1.5 py-0.5 rounded border whitespace-nowrap shrink-0 ${cls[o.r] || cls.common}">${RARITY_LABELS_RU[o.r]} ${o.pct}%</span>`).join('')}</div>`;
"""))

PAIRS.append(('index.html: CSS — прячем скроллбар у ряда чипсов', """
    #inspect-desc-full.nx-desc-scrollable.nx-desc-end::after{ opacity:0; }
""", """
    #inspect-desc-full.nx-desc-scrollable.nx-desc-end::after{ opacity:0; }
    /* b445: чипсы шансов редкости — одна строка без серой полосы скроллбара */
    .nx-odds{ scrollbar-width:none; -ms-overflow-style:none; }
    .nx-odds::-webkit-scrollbar{ display:none; }
"""))

TAG_OLD = 'nxmob174'
TAG_NEW = 'nxmob175'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']


def read(rel):
    with open(os.path.join(ROOT, rel), 'r', encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
        f.write(txt)


def apply():
    files = {}
    for label, old, new in PAIRS:
        rel = 'index.html' if label.startswith('index.html') else 'assets/app.js'
        if rel not in files:
            files[rel] = read(rel)
        txt = files[rel]
        if new.strip() in txt:
            continue  # уже применено
        assert old.strip() in txt, 'b445: не найден якорь: %s' % label
        assert txt.count(old.strip()) == 1, 'b445: якорь не уникален: %s (%d)' % (label, txt.count(old.strip()))
        files[rel] = txt.replace(old.strip(), new.strip(), 1)
    for rel, txt in files.items():
        write(rel, txt)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b445: не найден тег %s в %s (сначала _b442.._b444)' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b445: применено')


def check():
    problems = []
    for label, old, new in PAIRS:
        rel = 'index.html' if label.startswith('index.html') else 'assets/app.js'
        txt = read(rel)
        if new.strip() not in txt:
            problems.append('%s: нет нового блока: %s' % (rel, label))
    app = read('assets/app.js')
    for extra in ('class="nx-odds flex flex-nowrap items-center', 'whitespace-nowrap shrink-0',
                  'text-[9px] sm:text-[10px] font-semibold px-1 sm:px-1.5'):
        if extra not in app:
            problems.append('app.js: нет %r' % extra)
    if 'flex flex-wrap gap-1 mt-2">${odds.map' in app:
        problems.append('app.js: остался старый flex-wrap у чипсов')
    html = read('index.html')
    for extra in ('.nx-odds{ scrollbar-width:none;', '.nx-odds::-webkit-scrollbar{ display:none; }'):
        if extra not in html:
            problems.append('index.html: нет %r' % extra)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не %s' % (rel, TAG_NEW))
    if problems:
        print('b445 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b445 --check: всё на месте (ряд чипсов flex-nowrap, скроллбар скрыт, тег %s)' % TAG_NEW)


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
