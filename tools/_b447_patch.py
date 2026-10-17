#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b447: переключатель «Вид паков» виден сразу в разделе Студии «Паки».

Жалоба владельца: «не вижу». Разбор показал: ряды «Форма упаковки» и
«Форма по умолчанию» из b446 лежат ВНУТРИ формы создания/правки пака, а форма —
внутри секции Студии <div class="studio-sec" data-sec="packs">. Секции Студии
переключаются подразделами, и пока открыт не «Паки», формы (и новых рядов)
не видно вовсе; даже в «Паках» до них нужно доехать глазами сквозь цену,
премьеру и музыку.

Лечение: компактный ряд «Вид паков:» в самом верху секции «Паки» — пять кнопок
общей формы, видны сразу при открытии подраздела, без входа в редактор.
Кнопки вызывают ту же nxSetPackSkinDefault() из b446. Ряды внутри редактора
(своя форма пака) остаются как были.

Тег сборки nxmob176 -> nxmob177.

Проверка/применение:
    python3 tools/_b447_patch.py --check
    python3 tools/_b447_patch.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = []

PAIRS.append(('index.html: ряд «Вид паков» вверху секции Паки', """
            <div class="studio-sec space-y-3" data-sec="packs">
""", """
            <div class="studio-sec space-y-3" data-sec="packs">
            <!-- b447: переключатель формы паков виден СРАЗУ при открытии подраздела
                 «Паки», без входа в редактор пака. Кнопки — те же, что в ряду
                 «Форма по умолчанию» (nxSetPackSkinDefault из b446). -->
            <div class="bg-slate-900/60 border border-slate-800 rounded-xl px-3 py-2 flex flex-wrap items-center gap-2">
                <span class="text-[10px] font-bold uppercase tracking-wide text-slate-500"><i class="fa-solid fa-box-open text-violet-400 mr-1"></i>Вид паков:</span>
                <div id="pack-skin-quick" class="flex flex-wrap gap-1"><!-- кнопки форм --></div>
                <span class="text-[10px] text-slate-600">форма по умолчанию для всех паков; у отдельного пака своя форма задаётся в редакторе ниже</span>
            </div>
"""))

PAIRS.append(('app.js: быстрый ряд заполняется вместе с пикерами', """
            const dp = document.getElementById('pack-skin-default');
            if (dp) {
                const cur = nxPackSkinDefault();
                dp.innerHTML = Object.keys(PACK_SKINS).map(k => {
                    const on = k === cur;
                    return `<button type="button" onclick="nxSetPackSkinDefault('${k}')" title="${PACK_SKINS[k].hint}" class="rounded-lg border px-1.5 py-1 text-[9px] font-semibold transition ${on ? 'border-emerald-400 text-emerald-300 bg-emerald-500/10' : 'border-slate-700 text-slate-400 bg-slate-950 hover:border-slate-500'}">${PACK_SKINS[k].name}</button>`;
                }).join('');
            }
""", """
            // b447: один и тот же ряд кнопок рисуется и внутри редактора
            // (pack-skin-default), и в шапке подраздела «Паки» (pack-skin-quick),
            // чтобы переключатель находился без прокручивания формы.
            const skinBtns = () => {
                const cur = nxPackSkinDefault();
                return Object.keys(PACK_SKINS).map(k => {
                    const on = k === cur;
                    return `<button type="button" onclick="nxSetPackSkinDefault('${k}')" title="${PACK_SKINS[k].hint}" class="rounded-lg border px-1.5 py-1 text-[9px] font-semibold transition ${on ? 'border-emerald-400 text-emerald-300 bg-emerald-500/10' : 'border-slate-700 text-slate-400 bg-slate-950 hover:border-slate-500'}">${PACK_SKINS[k].name}</button>`;
                }).join('');
            };
            const dp = document.getElementById('pack-skin-default');
            if (dp) dp.innerHTML = skinBtns();
            const qp = document.getElementById('pack-skin-quick');
            if (qp) qp.innerHTML = skinBtns();
"""))

TAG_OLD = 'nxmob176'
TAG_NEW = 'nxmob177'
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
        assert old.strip() in txt, 'b447: не найден якорь: %s' % label
        assert txt.count(old.strip()) == 1, 'b447: якорь не уникален: %s (%d)' % (label, txt.count(old.strip()))
        files[rel] = txt.replace(old.strip(), new.strip(), 1)
    for rel, txt in files.items():
        write(rel, txt)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b447: не найден тег %s в %s (сначала _b442.._b446)' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b447: применено')


def check():
    problems = []
    for label, old, new in PAIRS:
        rel = 'index.html' if label.startswith('index.html') else 'assets/app.js'
        txt = read(rel)
        if new.strip() not in txt:
            problems.append('%s: нет нового блока: %s' % (rel, label))
    html = read('index.html')
    for extra in ('id="pack-skin-quick"', 'Вид паков:'):
        if extra not in html:
            problems.append('index.html: нет %r' % extra)
    app = read('assets/app.js')
    for extra in ('const skinBtns = () =>', "getElementById('pack-skin-quick')"):
        if extra not in app:
            problems.append('app.js: нет %r' % extra)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не %s' % (rel, TAG_NEW))
    if problems:
        print('b447 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b447 --check: всё на месте (ряд «Вид паков» в шапке секции, тег %s)' % TAG_NEW)


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
