#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b450: убрать светлую полосу-ребро над паками (откат побочки b449).

Жалоба владельца: «ещё хуже стало, убери вообще эту полосу» + скриншот, где над
верхней кромкой КАЖДОГО пака торчит тонкий светлый шпиль, а у зубчатой формы он
ещё и светит сквозь центральный вырез.

Настоящий виновник — не клип и не задняя грань, а .pack3d-rim (строки 12910–12911
шаблона карусели): две «реберные» плоскости-позвоночника (.rim-y вертикальная,
.rim-x горизонтальная), закрашенные светлым металлом var(--pk-rim). Дальше сложилось:

  · до b449 ребро было вровень с гранями и светило только сквозь прозрачные
    вырезы зубцов (тот самый шпиль на первом скриншоте);
  · b449 сделал грани на 2% ниже (inset:2% 0), а ребро осталось полной высоты —
    и его верхний край стал торчать НАД паком уже у всех форм сразу.
    Стало заметнее, а не меньше. Отсюда «ещё хуже».

Лечение по желанию владельца — полосы больше нет вовсе:
  1. оба <div class="pack3d-rim …"> удалены из шаблона карусели;
  2. в CSS добавлено .pack3d-rim{display:none} — страховка на случай любого
     другого места, где ребро могло создаваться (и на уже открытые вкладки);
  3. укорочение граней из b449 откатывается: .pack3d-face возвращает inset:0
     (силуэт пака снова во всю высоту слота), превью в Студии тоже inset:0;
  4. против просвета в вырезах зубцов остаётся точечная мера: короче делается
     ТОЛЬКО задняя грань (.pack3d-back{inset:2% 0}) — её зубцы не дотягиваются
     до вырезов передней, а силуэт пака при этом не меняется.

Боковых «торцов» ребро никогда не закрывало (оно одно и по центру), поэтому
после удаления ничего не зияет: на yaw ±12° между гранями остаётся та же
невидимая глубина, что и задумана translateZ.

Тег сборки nxmob179 -> nxmob180.

Проверка/применение:
    python3 tools/_b450_patch.py --check
    python3 tools/_b450_patch.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = []

PAIRS.append(('app.js: реберные плоскости удалены из карусели', """
                            <div class="pack3d-rim rim-y"></div>
                            <div class="pack3d-rim rim-x"></div>
""", """
                            <!-- b450: реберные плоскости (.pack3d-rim rim-y/rim-x) удалены:
                                 светлый металл var(--pk-rim) торчал над кромкой пака и светил
                                 сквозь вырезы зубцов. Боковых торцов они не закрывали. -->
"""))

PAIRS.append(('index.html: ребро скрыто везде + откат укорочения граней', """
    .pack3d-face{ inset:2% 0; }
""", """
    /* b450: полосы-ребра больше нет нигде. display:none — страховка и для уже
       отрисованных вкладок, и на случай, если ребро когда-нибудь вернётся в
       разметку: светлый металл var(--pk-rim) торчал над кромкой пака и светил
       сквозь вырезы зубцов. */
    .pack3d-rim{ display:none; }
    /* b449 откатывается: грани снова во всю высоту слота. Против просвета в
       вырезах зубцов работает только укорочение ЗАДНЕЙ грани ниже. */
    .pack3d-back{ inset:2% 0; }
"""))

PAIRS.append(('app.js: превью Студии снова во всю высоту', """
                <div class="pack3d-face pack3d-front booster ${pkSkinCls(p)}" style="position:absolute;inset:2% 0;${packCssVars(p)}">
""", """
                <div class="pack3d-face pack3d-front booster ${pkSkinCls(p)}" style="position:absolute;inset:0;${packCssVars(p)}">
"""))

TAG_OLD = 'nxmob179'
TAG_NEW = 'nxmob180'
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
            continue
        assert old.strip() in txt, 'b450: не найден якорь: %s' % label
        assert txt.count(old.strip()) == 1, 'b450: якорь не уникален: %s (%d)' % (label, txt.count(old.strip()))
        files[rel] = txt.replace(old.strip(), new.strip(), 1)
    for rel, txt in files.items():
        write(rel, txt)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b450: не найден тег %s в %s (сначала _b442.._b449)' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b450: применено')


def check():
    problems = []
    for label, old, new in PAIRS:
        rel = 'index.html' if label.startswith('index.html') else 'assets/app.js'
        txt = read(rel)
        if new.strip() not in txt:
            problems.append('%s: нет нового блока: %s' % (rel, label))
    app = read('assets/app.js')
    if 'class="pack3d-rim' in app:
        problems.append('app.js: в разметке осталось class="pack3d-rim')
    html = read('index.html')
    if '.pack3d-rim{ display:none; }' not in html:
        problems.append('index.html: нет .pack3d-rim{ display:none; }')
    if '.pack3d-back{ inset:2% 0; }' not in html:
        problems.append('index.html: нет .pack3d-back{ inset:2% 0; }')
    if '.pack3d-face{ inset:2% 0; }' in html:
        problems.append('index.html: не откатилось укорочение .pack3d-face из b449')
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не %s' % (rel, TAG_NEW))
    if problems:
        print('b450 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b450 --check: всё на месте (ребро удалено и скрыто, грани во всю высоту, тег %s)' % TAG_NEW)


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
