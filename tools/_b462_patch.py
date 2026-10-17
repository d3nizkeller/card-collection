#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b462: широкую (и высокую) картину можно двигать даже при масштабе 100%.

Жалоба владельца: «почему широкую картинку не могу двигать» — слайдер
«Сдвиг по горизонтали» = 20, картина стоит. Причина: object-cover у
широкого арта срезает бока ВНУТРИ рамки уже при масштабе 100%, а
трансформ translate() двигал только избыток самого зума ±(S−1)*50% —
при S=1 он нулевой, и сдвигDegenerate в ноль; боковой срез object-cover
оставался недосягаем.

Лечение:
  1. cardArtStyle() добавляет в style объект-position: ox% oy%
     (ox = 50 + artPosX/2, oy = 50 + artPosY/2) — это панорама окном
     кадрирования object-cover: широкая картина ездит влево-вправо,
     высокая — вверх-вниз при ЛЮБОМ масштабе, без оголения краёв;
     translate() поверх по-прежнему панорамирует избыток зума;
  2. драг мышью/пальцем получил ёмкость по осям: cap = (S−1)*50 +
     полуширина среза object-cover (считается по naturalWidth/Height
     превью-картинки и пропорциям панели) — тянуть широкую картину
     можно и при 100%, со скоростью 1:1 к пикселям курсора; ось без
     среза и зума остаётся неподвижной (двигать нечего).
Слайдеры, сохранение в layout (artZoom/artPosY/artPosX) и облачная
синхронизация не менялись.

app.js менялся — тег сборки nxmob184 -> nxmob185 (index.html, sw.js,
tools/build.py).

Проверка/применение:
    python3 tools/_b462_patch.py --check
    python3 tools/_b462_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob184'
TAG_NEW = 'nxmob185'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('assets/app.js', '''            const s = L.artZoom / 100;
            const max = (s - 1) * 50;
            const y = (L.artPosY / 100) * max;
            const x = (L.artPosX / 100) * max;
            return ' style="transform:translate(' + x.toFixed(2) + '%, ' + y.toFixed(2) + '%) scale(' + s.toFixed(2) + ')"';''',
              '''            const s = L.artZoom / 100;
            const max = (s - 1) * 50;
            const y = (L.artPosY / 100) * max;
            const x = (L.artPosX / 100) * max;
            // b462: object-position панорамирует окно кадрирования object-cover —
            // широкая/высокая картина ездит даже при масштабе 100%, где translate
            // ограничен нулевым избытком зума. Крайние значения 0%/100% не оголяют
            // рамку: object-position не выходит за срез cover.
            const ox = 50 + L.artPosX / 2;
            const oy = 50 + L.artPosY / 2;
            return ' style="object-position:' + ox.toFixed(1) + '% ' + oy.toFixed(1) + '%;transform:translate(' + x.toFixed(2) + '%, ' + y.toFixed(2) + '%) scale(' + s.toFixed(2) + ')"';'''))

PAIRS.append(('assets/app.js', '''            wrap.addEventListener('pointermove', function (e) {
                if (!drag) return;
                const maxY = (drag.s - 1) * 50;
                if (maxY <= 0) return; // масштаб 100%: панорамить нечего
                const Y = document.getElementById('card-arty');
                const X = document.getElementById('card-artx');
                if (!Y || !X) return;
                const dyPct = (e.clientY - drag.y) / drag.h * 100;
                const dxPct = (e.clientX - drag.x) / drag.w * 100;
                let uy = drag.sy + (dyPct / maxY) * 100;
                let ux = drag.sx + (dxPct / maxY) * 100;''',
              '''            wrap.addEventListener('pointermove', function (e) {
                if (!drag) return;
                const Y = document.getElementById('card-arty');
                const X = document.getElementById('card-artx');
                if (!Y || !X) return;
                // b462: ёмкость панорамы по осям = избыток зума + половина среза
                // object-cover (широкая картина движется и при масштабе 100%)
                let capX = (drag.s - 1) * 50, capY = (drag.s - 1) * 50;
                const art = document.querySelector('#card-preview img');
                if (art && art.naturalWidth > 0 && art.naturalHeight > 0) {
                    const arI = art.naturalWidth / art.naturalHeight;
                    const arB = (drag.w / drag.h) || arI;
                    if (arI > arB) capX += (arI / arB - 1) * 50;
                    else if (arI < arB) capY += (arB / arI - 1) * 50;
                }
                const dyPct = (e.clientY - drag.y) / drag.h * 100;
                const dxPct = (e.clientX - drag.x) / drag.w * 100;
                let uy = drag.sy + (capY > 0 ? (dyPct / capY) * 100 : 0);
                let ux = drag.sx + (capX > 0 ? (dxPct / capX) * 100 : 0);'''))


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
        print('b462: якоря и тег %s на месте, можно применять' % TAG_OLD)
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b462: широкая картина двигается (object-position + ёмкость драга); тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
