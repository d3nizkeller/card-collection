#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guard_monolith.py — не даёт tools/build.py откатить игру.

Проблема
────────
build.py собирает index.html и assets/* из монолита tools/source-index.html,
применяя к нему свой список правок (patch_once). Но с b414 правки вносились
НАПРЯМУЮ в собранные файлы (tools/_bNNN_patch.py), и монолит перестал
обновляться. Фактическое состояние репозитория:

    tools/source-index.html   b397   (устарел, к тому же в LF вместо CRLF)
    tools/build.py            знает правки до b413
    assets/app.js             b441   (реальный прод)
    index.html                старше build.py по разметке (b383 и др.)

Запуск build.py на таком монолите либо падает (LF: read_lines() режет по CRLF,
получается «источник: 1 строк» → IndexError), либо — если переводы строк
починить — молча собирает игру уровня b413 и стирает 28 правок, включая всю
защиту целостности банка (jpLedAdd/jpRepairLedger/JP_TIER_MUL) и лимиты биржи
(MARKET_HARD_TRIM).

Что делает страж
────────────────
Сравнивает монолит и собранные файлы по трём признакам и не пускает сборку,
если монолит позади:

  1. переводы строк: монолит обязан быть CRLF, иначе build.py прочитает его
     как одну строку;
  2. максимальный номер правки bNNN в монолите против assets/app.js;
  3. наличие в assets/app.js ключевых маркеров, которых нет в монолите
     (список задан ниже и проверяется явно, чтобы не полагаться только на номера).

Запуск
──────
    python3 tools/guard_monolith.py            # проверка (код возврата 1 = нельзя собирать)
    python3 tools/guard_monolith.py --install  # встроить проверку в начало build.py
    python3 tools/guard_monolith.py --force    # проверить и вернуть 0 в любом случае

Лечится это одним способом: пересобрать монолит из текущих assets/*
(tools/rebuild_monolith.py) и пересчитать границы блоков. Пока монолит не
соответствует прод-файлам, собирать из него НЕЛЬЗЯ.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'tools', 'source-index.html')
APP = os.path.join(ROOT, 'assets', 'app.js')
BLD = os.path.join(ROOT, 'tools', 'build.py')

# Маркеры, которые обязаны быть и в монолите, и в собранных файлах.
# Если в app.js они есть, а в монолите нет — монолит отстал, и сборка
# их сотрёт. Каждый маркер привязан к конкретной правке.
MARKERS = [
    ('jpLedBad', 'b416: защита реестра банка от счётчиков 1e57'),
    ('JP_TIER_MUL', 'b419: разряды реестра 1e13 → 1e16 → 1e19'),
    ('jackpot.ep', 'b420: эпоха реестра (уплотнение не воскрешает мусор)'),
    ('jpAutoCompactIfNeeded', 'b423: автоуплотнение реестра'),
    ('MARKET_HARD_TRIM', 'b411: автовыкуп при переполнении биржи'),
    ('jpc.feedBet', 'b414: настраиваемый процент взноса в банк'),
    ('nxDescScrollHint', 'b441: прокрутка описания карты'),
    ('jpRepairNow', 'кнопка «Починить банк» в Студии'),
    ('profMergeState', 'b370: леджер коллекции в профиль-синхронизации'),
]

GUARD_MARK = '# --- GUARD_MONOLITH (tools/guard_monolith.py) ---'


def nums(text):
    return [int(m.group(1)) for m in re.finditer(r'\bb(3[5-9]\d|4\d\d)\b', text)]


def check(quiet=False):
    problems = []
    if not os.path.isfile(SRC):
        return ['нет %s' % SRC]
    if not os.path.isfile(APP):
        return ['нет %s' % APP]
    raw = io.open(SRC, 'rb').read()
    if raw.count(b'\r\n') == 0:
        problems.append('монолит в LF, а read_lines() режет по CRLF — сборщик прочитает '
                        'его как одну строку и упадёт (IndexError в inner())')
    mon = raw.decode('utf-8', 'replace')
    built = io.open(APP, encoding='utf-8').read()
    mmax, bmax = max(nums(mon) or [0]), max(nums(built) or [0])
    if bmax > mmax:
        problems.append('монолит на b%d, а assets/app.js на b%d — сборка откатит игру на %d правок'
                        % (mmax, bmax, bmax - mmax))
    lost = [(m, d) for m, d in MARKERS if m in built and m not in mon]
    if lost:
        problems.append('в монолите нет %d маркеров, которые есть в assets/app.js' % len(lost))
    if not quiet:
        print('guard_monolith: монолит b%d, assets/app.js b%d' % (mmax, bmax))
        for m, d in lost:
            print('  · отсутствует %-22s %s' % (m, d))
        if not problems:
            print('  ✓ монолит соответствует прод-файлам, собирать можно')
        else:
            print('')
            print('  ⛔ СБОРКУ ЗАПУСКАТЬ НЕЛЬЗЯ:')
            for p in problems:
                print('     - ' + p)
    return problems


def install():
    bld = io.open(BLD, encoding='utf-8').read()
    if GUARD_MARK in bld:
        print('страж уже встроен в build.py')
        return 0
    anchor = 'def main():'
    if anchor not in bld:
        print('в build.py не найден def main() — страж не встроен')
        return 1
    # вставляем вызов стража в самое начало main()
    code = (GUARD_MARK + '\n'
            + 'def _nx_guard():\n'
            + '    import subprocess\n'
            + '    g = os.path.join(ROOT, "tools", "guard_monolith.py")\n'
            + '    if not os.path.isfile(g) or os.environ.get("NX_SKIP_MONOLITH_GUARD") == "1":\n'
            + '        return\n'
            + '    r = subprocess.run([sys.executable, g], cwd=ROOT)\n'
            + '    if r.returncode != 0:\n'
            + '        raise SystemExit(r.returncode)\n'
            + '# --- /GUARD_MONOLITH ---\n\n\n')
    bld = bld.replace(anchor, code + anchor + '\n    _nx_guard()', 1)
    io.open(BLD + '.bak-guard', 'w', encoding='utf-8').write(
        io.open(BLD, encoding='utf-8').read())
    io.open(BLD, 'w', encoding='utf-8').write(bld)
    print('build.py: страж встроен (копия: build.py.bak-guard)')
    return 0


def main():
    if '--install' in sys.argv:
        rc = install()
        problems = check()
        return rc or (1 if problems else 0)
    problems = check()
    if '--force' in sys.argv:
        return 0
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
