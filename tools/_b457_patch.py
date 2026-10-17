#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b457: слайдеры арта ЗАРАБОТАЛИ на сайте (тег сборки) + сдвиг по горизонтали.

(1) «Не работает» из отзыва владельца: b456 изменил assets/app.js, но тег
сборки не поднялся. Service worker держит app.js cache-first в кэше
`nx-assets-<ТЕГ>` (сверка раз в 7 дней) — браузер продолжал крутить
СТАРЫЙ app.js без cardArtStyle(): слайдеры в разметке есть, а эффекта
нет. Лечение по конвенции b450: тег nxmob180 -> nxmob181 в index.html,
sw.js и tools/build.py — ключ кэша меняется, клиенты сразу читают новый
app.js.

(2) Просьба владельца: «и по горизонтали надо». Третий слайдер
«Сдвиг по горизонтали» −100…100 (шаг 5, id card-artx): значение живёт в
layout.artPosX, нормализуется в cardLayoutOf(), в cardArtStyle() даёт
translate(X%, Y%) scale(S); предел по X тот же ±(S−1)*50% — края картины
не оголяются. Подпись значения #card-artx-val обновляется в
renderCardPreview(), editCard() подставляет сохранённое, сброс формы
возвращает 0 (value-атрибут). Сетка слайдеров 2 -> 3 колонки
(grid-cols-3 есть в собранном tailwind.css), иконка fa-exchange-alt —
из собранного fa.css.

Проверка/применение:
    python3 tools/_b457_patch.py --check
    python3 tools/_b457_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob180'
TAG_NEW = 'nxmob181'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('index.html', '''                            <div class="grid grid-cols-2 gap-3 mt-2">
                                <div class="flex flex-col">
                                    <label class="block text-[11px] font-medium text-slate-400 mb-1"><i class="fa-solid fa-search text-violet-400 mr-1"></i>Масштаб арта <span id="card-artzoom-val" class="text-slate-300 font-bold">100%</span></label>
                                    <input type="range" id="card-artzoom" min="100" max="220" step="5" value="100" oninput="renderCardPreview()" class="w-full accent-violet-500">
                                </div>
                                <div class="flex flex-col">
                                    <label class="block text-[11px] font-medium text-slate-400 mb-1"><i class="fa-solid fa-image text-sky-400 mr-1"></i>Сдвиг по вертикали <span id="card-arty-val" class="text-slate-300 font-bold">0</span></label>
                                    <input type="range" id="card-arty" min="-100" max="100" step="5" value="0" oninput="renderCardPreview()" class="w-full accent-violet-500">
                                </div>
                            </div>''',
              '''                            <div class="grid grid-cols-3 gap-3 mt-2">
                                <div class="flex flex-col">
                                    <label class="block text-[11px] font-medium text-slate-400 mb-1"><i class="fa-solid fa-search text-violet-400 mr-1"></i>Масштаб арта <span id="card-artzoom-val" class="text-slate-300 font-bold">100%</span></label>
                                    <input type="range" id="card-artzoom" min="100" max="220" step="5" value="100" oninput="renderCardPreview()" class="w-full accent-violet-500">
                                </div>
                                <div class="flex flex-col">
                                    <label class="block text-[11px] font-medium text-slate-400 mb-1"><i class="fa-solid fa-image text-sky-400 mr-1"></i>Сдвиг по вертикали <span id="card-arty-val" class="text-slate-300 font-bold">0</span></label>
                                    <input type="range" id="card-arty" min="-100" max="100" step="5" value="0" oninput="renderCardPreview()" class="w-full accent-violet-500">
                                </div>
                                <!-- b457: сдвиг по горизонтали — третий слайдер кадрирования -->
                                <div class="flex flex-col">
                                    <label class="block text-[11px] font-medium text-slate-400 mb-1"><i class="fa-solid fa-exchange-alt text-emerald-400 mr-1"></i>Сдвиг по горизонтали <span id="card-artx-val" class="text-slate-300 font-bold">0</span></label>
                                    <input type="range" id="card-artx" min="-100" max="100" step="5" value="0" oninput="renderCardPreview()" class="w-full accent-violet-500">
                                </div>
                            </div>'''))

PAIRS.append(('assets/app.js', '''artZoom: g('card-artzoom'), artPosY: g('card-arty') }; // b456: + масштаб/сдвиг арта''',
              '''artZoom: g('card-artzoom'), artPosY: g('card-arty'), artPosX: g('card-artx') }; // b456: + масштаб/сдвиг арта; b457: + сдвиг по горизонтали'''))

PAIRS.append(('assets/app.js', '''                artPosY: Math.max(-100, Math.min(100, Number(L.artPosY) || 0)),''',
              '''                artPosY: Math.max(-100, Math.min(100, Number(L.artPosY) || 0)),
                artPosX: Math.max(-100, Math.min(100, Number(L.artPosX) || 0)), // b457'''))

PAIRS.append(('assets/app.js', '''        // b456: inline-transform арта в рамке карты: масштаб + вертикальный сдвиг,
        // ограниченный ±(S−1)*50% — края картины не оголяются ни при каком зуме.
        // При дефолте (100/0) возвращает пустую строку: hover-зум group-hover:scale-105
        // на обычных картах не глушится inline-стилем.
        function cardArtStyle(card) {
            const L = cardLayoutOf(card);
            if (L.artZoom === 100 && L.artPosY === 0) return '';
            const s = L.artZoom / 100;
            const maxY = (s - 1) * 50;
            const y = (L.artPosY / 100) * maxY;
            return ' style="transform:translateY(' + y.toFixed(2) + '%) scale(' + s.toFixed(2) + ')"';
        }''',
              '''        // b456+b457: inline-transform арта в рамке карты: масштаб + сдвиги по
        // вертикали и горизонтали, каждый ограниченный ±(S−1)*50% — края картины
        // не оголяются ни при каком зуме. При дефолте (100/0/0) возвращает пустую
        // строку: hover-зум group-hover:scale-105 на обычных картах не глушится.
        function cardArtStyle(card) {
            const L = cardLayoutOf(card);
            if (L.artZoom === 100 && L.artPosY === 0 && L.artPosX === 0) return '';
            const s = L.artZoom / 100;
            const max = (s - 1) * 50;
            const y = (L.artPosY / 100) * max;
            const x = (L.artPosX / 100) * max;
            return ' style="transform:translate(' + x.toFixed(2) + '%, ' + y.toFixed(2) + '%) scale(' + s.toFixed(2) + ')"';
        }'''))

PAIRS.append(('assets/app.js', '''            const ayv = document.getElementById('card-arty-val');
            if (ayv) ayv.textContent = String(Number(gv('card-arty')) || 0);''',
              '''            const ayv = document.getElementById('card-arty-val');
            if (ayv) ayv.textContent = String(Number(gv('card-arty')) || 0);
            const axv = document.getElementById('card-artx-val'); // b457
            if (axv) axv.textContent = String(Number(gv('card-artx')) || 0);'''))

PAIRS.append(('assets/app.js', '''            const ayEl = document.getElementById('card-arty');
            if (ayEl) ayEl.value = L0.artPosY;''',
              '''            const ayEl = document.getElementById('card-arty');
            if (ayEl) ayEl.value = L0.artPosY;
            const axEl = document.getElementById('card-artx'); // b457
            if (axEl) axEl.value = L0.artPosX;'''))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, old, new in PAIRS:
        txt = files.get(rel) or read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        if txt.count(o) != 1:
            problems.append('%s: якорь встретился %d раз: %s...' % (rel, txt.count(o), o[:60]))
            continue
        files[rel] = txt.replace(o, n, 1)
    for rel in TAG_FILES:
        txt = files.get(rel) or read(rel)
        if TAG_NEW in txt:
            problems.append('%s: тег уже %s' % (rel, TAG_NEW))
            continue
        if TAG_OLD not in txt:
            problems.append('%s: нет тега %s' % (rel, TAG_OLD))
            continue
        files[rel] = txt.replace(TAG_OLD, TAG_NEW)
    if problems:
        for p in problems:
            print('ПРОБЛЕМА:', p)
        return 1
    if '--check' in sys.argv:
        print('b457: якоря и тег %s на месте, можно применять' % TAG_OLD)
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b457: горизонтальный сдвиг арта + тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
