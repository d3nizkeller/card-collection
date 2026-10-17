#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make-build-tolerant.py — добавить в tools/build.py режим --tolerant.

Зачем: список правок сборщика знает только про b355…b413, а assets/app.js ушёл
на b441+. Правки b414…b441 применялись напрямую к собранным файлам
(tools/_bNNN_patch.py), поэтому в монолите их нет, и 44 правила сборщика больше
не находят свой OLD-текст. Без --tolerant сборка падает на первом же:

    AssertionError: патч не найден: b379: profCode всегда пустой

С флагом устаревшее правило пропускается с предупреждением. БЕЗ флага поведение
прежнее — строгое: любой разошедшийся патч роняет сборку.

    python3 tools/make-build-tolerant.py            # применить (идемпотентно)
    python3 tools/make-build-tolerant.py --revert   # вернуть из build.py.bak-tol
"""
import io, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLD = os.path.join(ROOT, 'tools', 'build.py')

OLD = '''def patch_once(text, old, new, label, required=True, want=None):'''
NEW = '''# --tolerant: устаревшие правила (их OLD уже переписан более поздними правками,
# которых сборщик не знает) пропускаются с предупреждением вместо падения.
NX_TOLERANT = '--tolerant' in sys.argv


def patch_once(text, old, new, label, required=True, want=None):'''

OLD2 = '''    n = text.count(old)
    if n == 0:
        if required:
            raise AssertionError('патч не найден: ' + label)
        say('  · %s — не найдено (пропущено)' % label)
        return text, 0
    if want is not None and n != want:
        raise AssertionError('патч «%s»: ожидалось %d вхождений, найдено %d '
                             '(источник изменился — обновите патч)' % (label, want, n))'''
NEW2 = '''    n = text.count(old)
    if n == 0:
        if required and not NX_TOLERANT:
            raise AssertionError('патч не найден: ' + label)
        if required:
            say('  · %s — УСТАРЕЛ, пропущено (--tolerant)' % label)
            return text, 0
        say('  · %s — не найдено (пропущено)' % label)
        return text, 0
    if want is not None and n != want:
        if not NX_TOLERANT:
            raise AssertionError('патч «%s»: ожидалось %d вхождений, найдено %d '
                                 '(источник изменился — обновите патч)' % (label, want, n))
        say('  ! %s: ожидалось %d вхождений, найдено %d (--tolerant)' % (label, want, n))'''


# Два места в main() бросают AssertionError напрямую, минуя patch_once:
# «сцена котика» (b380) и «блок профиля QR» (b378). Их якоря тоже переписаны
# более поздними правками, поэтому в режиме --tolerant они предупреждают.
DIRECT = [
    ("""        if _n2 != 1:
            raise AssertionError('сцена котика «%s»: якорь встретился %d раз' % (_lbl, _n2))""",
     """        if _n2 != 1:
            if not NX_TOLERANT:
                raise AssertionError('сцена котика «%s»: якорь встретился %d раз' % (_lbl, _n2))
            say('  ! сцена котика «%s»: якорь %d раз (--tolerant)' % (_lbl, _n2))"""),
    ("""    if _n != 1:
        raise AssertionError('разметка: блок профиля QR встретился %d раза' % _n)""",
     """    if _n != 1:
        if not NX_TOLERANT:
            raise AssertionError('разметка: блок профиля QR встретился %d раза' % _n)
        say('  ! разметка: блок профиля QR встретился %d раза (--tolerant)' % _n)"""),
]


def main():
    s = io.open(BLD, encoding='utf-8').read()
    if '--revert' in sys.argv:
        bak = BLD + '.bak-tol'
        if not os.path.isfile(bak):
            print('нет %s' % bak); return 1
        io.open(BLD, 'w', encoding='utf-8').write(io.open(bak, encoding='utf-8').read())
        print('build.py восстановлен из .bak-tol'); return 0
    if 'NX_TOLERANT' in s:
        print('уже применено'); return 0
    assert OLD in s, 'не найден заголовок patch_once'
    assert OLD2 in s, 'не найден тело patch_once'
    io.open(BLD + '.bak-tol', 'w', encoding='utf-8').write(s)
    s = s.replace(OLD, NEW, 1).replace(OLD2, NEW2, 1)
    n_direct = 0
    for old, new in DIRECT:
        if old in s:
            s = s.replace(old, new, 1)
            n_direct += 1
        else:
            print('  ! не найден якорь прямого raise (пропущено): %s' % old.strip().splitlines()[-1][:60])
    io.open(BLD, 'w', encoding='utf-8').write(s)
    print('build.py: режим --tolerant добавлен, прямых raise защищено %d (копия: build.py.bak-tol)' % n_direct)
    return 0


if __name__ == '__main__':
    sys.exit(main())
