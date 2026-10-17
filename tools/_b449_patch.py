#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b449: из вырезов зубчиков больше ничего не торчит.

Жалоба владельца: скриншот кромки пака — в вырезе между зубцами виден светлый
тонкий шпиль «на заднем плане».

Причина (геометрия 3D-пака, а не клип и не кэш):
  · у пака две грани, .pack3d-front и .pack3d-back, разнесённые по Z
    (translateZ(9px) у каждой → 18px между плоскостями);
  · обе гранит имеют ОДИНАКОВЫЙ зубчатый clip-path, но контейнер
    .pack3d-tilt слегка повёрнут (наклон витрины + packTilt при движении мыши),
    поэтому проекция ДАЛЬНЕЙ плоскости сдвигается на 1–2px относительно ближней;
  · вырез зубца у ближней грани — это прозрачное окно клипа: сквозь него виден
    любой пиксель дальней грани, попавший в эту область. Светлая фольга дальней
    грани и даёт тот самый шпиль в вырезе.

Лечение: обе грани получают небольшой вертикальный отступ
    .pack3d-face{ inset:2% 0; }
Теперь зубцы каждой грани начинаются на 2% высоты (~5px при 262px) ниже кромки
слота, и проекционный сдвиг в 1–2px полностью поглощается этим запасом:
дальняя грань физически не дотягивается до вырезов ближней. Пак становится на
4% ниже — при высоте слота 220–260px это 5–10px, глазом не ловится, тени и
подписи позиционируются от слота, а не от грани.

Дополнительно: у превью пака в Студии inline-стиль inset:0 заменяется на
inset:2% 0, чтобы превью и витрина были одного силуэта (inline-стиль иначе
перебил бы новое CSS-правило).

Формы из b446 (box/ticket/neon/retro) не страдают: у них clip-path без вырезов
или без зубцов, и правило им не мешает (их собственные clip-path ниже по
каскаду и перебивают только форму, не inset).

Тег сборки nxmob178 -> nxmob179.

Проверка/применение:
    python3 tools/_b449_patch.py --check
    python3 tools/_b449_patch.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = []

PAIRS.append(('index.html: грани пака с вертикальным отступом', """
    /* ===== b448: КРОМКА (зубчики) =====""", """
    /* ===== b449: ИЗ ВЫРЕЗОВ ЗУБЧИКОВ НИЧЕГО НЕ ТОРЧИТ =====
       Две грани 3D-пака разнесены по Z на 18px; при лёгком наклоне витрины
       проекция дальней плоскости сдвигается на 1–2px, и её светлая фольга
       проступала в прозрачных вырезах зубцов ближней грани (тонкий шпиль на
       скриншоте владельца). Отступ 2% сверху и снизу даёт запас ~5px, который
       полностью поглощает проекционный сдвиг: дальняя грань не дотягивается до
       вырезов ближней. Правило стоит ПОСЛЕ app.css и до форм b446, специфичность
       равна .pack3d-face, поэтому выигрывает порядком. */
    .pack3d-face{ inset:2% 0; }

    /* ===== b448: КРОМКА (зубчики) ====="""))

PAIRS.append(('app.js: превью в Студии того же силуэта', """
                <div class="pack3d-face pack3d-front booster ${pkSkinCls(p)}" style="position:absolute;inset:0;${packCssVars(p)}">
""", """
                <div class="pack3d-face pack3d-front booster ${pkSkinCls(p)}" style="position:absolute;inset:2% 0;${packCssVars(p)}">
"""))

TAG_OLD = 'nxmob178'
TAG_NEW = 'nxmob179'
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
        assert old.strip() in txt, 'b449: не найден якорь: %s' % label
        assert txt.count(old.strip()) == 1, 'b449: якорь не уникален: %s (%d)' % (label, txt.count(old.strip()))
        files[rel] = txt.replace(old.strip(), new.strip(), 1)
    for rel, txt in files.items():
        write(rel, txt)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b449: не найден тег %s в %s (сначала _b442.._b448)' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b449: применено')


def check():
    problems = []
    for label, old, new in PAIRS:
        rel = 'index.html' if label.startswith('index.html') else 'assets/app.js'
        txt = read(rel)
        if new.strip() not in txt:
            problems.append('%s: нет нового блока: %s' % (rel, label))
    html = read('index.html')
    if '.pack3d-face{ inset:2% 0; }' not in html:
        problems.append('index.html: нет правила .pack3d-face{ inset:2% 0; }')
    # порядок каскада: правило должно идти ПОСЛЕ ссылки на app.css (иначе базу
    # не перебить) и ДО форм b446 (иначе их clip-path не перебьёт клип b448).
    # Между собой правила b448 (clip-path) и b449 (inset) не конкурируют —
    # свойства разные, поэтому их взаимный порядок не важен.
    i_link = html.find('assets/app.css')
    i_face = html.find('.pack3d-face{ inset:2% 0; }')
    i_skins = html.find('/* ===== b446: ФОРМЫ УПАКОВКИ =====')
    if not (0 <= i_link < i_face < i_skins):
        problems.append('index.html: нарушен порядок каскада (app.css → inset b449 → формы b446)')
    app = read('assets/app.js')
    if 'style="position:absolute;inset:2% 0;${packCssVars(p)}"' not in app:
        problems.append('app.js: превью Студии без inset:2% 0')
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не %s' % (rel, TAG_NEW))
    if problems:
        print('b449 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b449 --check: всё на месте (inset 2%% у граней, превью в том же силуэте, тег %s)' % TAG_NEW)


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
