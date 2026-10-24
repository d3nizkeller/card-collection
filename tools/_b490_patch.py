#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b490: колесо рулетки — номера в своих секторах, шарик точно под указателем.

Жалоба владельца (два скриншота): «зачем в колесе пустые сектора и история
работает не правильно».

Разбор (пиксельная диагностика tools/shots/_dbg-wheel0.png: зондом по всем
37 направлениям белые цифры нашлись только у 28 секторов)
--------------------------------------------------------------------------
1. «Пустые сектора». Номер рисовался так: g.rotate(i*sector) и fillText в
   точке (0, -RS*0.85) — то есть на 90° ПРОТИВ часовой от центра собственного
   сектора (точка (0,-r) в повёрнутом кадре = направление i*sector - 90°).
   Номер поэтому садился на сектор (i-9 mod 37): для i >= 9 этот сектор к
   моменту рисования уже был залит — номер виден; для i = 0..8 его сектор-
   подложка (i+28 mod 37) рисовался ПОЗЖЕ и закрашивал номер напрочь.
   Отсюда дуга «пустых» секторов ровно в 9 штук.
2. «История неправильная». Формула остановки колеса целилась в
   (360 - (idx*sector + sector/2)) - 90: центр клина сидит на i*sector без
   половинки, а -90 уже учтён направлением указателя — итог: колесо
   останавливалось на пол-сектора мимо, шарик (который садится на экранный
   угол -90) вставал на ГРАНИЦУ двух секторов, и номер под указателем не
   совпадал ни с шариком, ни с историей.

Лечение
-------
1. Номер рисуется в центре своего клина: rotate(i*sector) → translate
   (RS*0.85, 0) → rotate(90°) → fillText(0,0): цифра стоит на радиусе,
   «головой» к ободу, и больше ничем не перекрывается.
2. Остановка: желаемый угол колеса desired = ((-90 - idx*sector) mod 360),
   target = from + 5 оборотов + доворот до desired — клин выигрышного номера
   встает ровно под указатель и шарик.
3. Пиксель-регессия: после спина экранный угол центра выигрышного клина
   равен -90° (проверка в jsdom по rouletteAngle).

Менялся только assets/app.js — тег сборки nxmob233 -> nxmob234.

Проверка/применение:
    python3 tools/_b490_patch.py --check
    python3 tools/_b490_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob233'
TAG_NEW = 'nxmob234'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('assets/app.js', 1,
              r'''                g.save();
                g.rotate(i * sector);
                g.fillStyle = '#f8fafc';
                g.font = '700 ' + Math.round(R / 15) + 'px Inter, sans-serif';
                g.textAlign = 'center';
                g.textBaseline = 'middle';
                g.fillText(String(n), 0, -RS * 0.85);
                g.restore();''',
              r'''                g.save();
                // b490: номер СТРОГО в своём секторе: поворот на центр клина,
                // вынос на радиус и доворот на 90°, чтобы цифра стояла вдоль
                // радиуса «головой» к ободу. В b489 номер уезжал на 90° мимо
                // своего клина и у первых девяти секторов закрашивался соседями
                // (те самые «пустые сектора» со скриншота владельца).
                g.rotate(i * sector);
                g.translate(RS * 0.85, 0);
                g.rotate(Math.PI / 2);
                g.fillStyle = '#f8fafc';
                g.font = '700 ' + Math.round(R / 15) + 'px Inter, sans-serif';
                g.textAlign = 'center';
                g.textBaseline = 'middle';
                g.fillText(String(n), 0, 0);
                g.restore();'''))

PAIRS.append(('assets/app.js', 1,
              r'''            // сектор win должен встать под указатель сверху (угол -90°)
            const target = 360 * 5 + (360 - (idx * sector + sector / 2)) - 90;
            const from = rouletteAngle % 360;''',
              r'''            // b490: центр клина win в координатах колеса = idx*sector, указатель
            // сверху = экранный угол -90°, значит колесо должно встать на
            // desired = -90 - idx*sector. В b488/b489 формула давала пол-сектора
            // мимо: шарик вставал на границу двух секторов и «история не
            // совпадала с колесом».
            const from = rouletteAngle % 360;
            const desired = ((-90 - idx * sector) % 360 + 360) % 360;
            const target = from + 360 * 5 + ((desired - from) % 360 + 360) % 360;'''))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8', newline='') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, cnt, old, new in PAIRS:
        txt = files.get(rel) or read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        if n in txt:
            problems.append('%s: правка уже применена: %s...' % (rel, o[:60]))
            continue
        if txt.count(o) != cnt:
            problems.append('%s: якорь встретился %d раз вместо %d: %s...' % (rel, txt.count(o), cnt, o[:60]))
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
        print('b490: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b490: номера в своих секторах, шарик точно под указателем; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
