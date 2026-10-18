#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_nx_rules_tables.py — таблицы наград для assets/nx-rules.js (b463)

Зачем
─────
С переносом экономики на сервер деньги за задания и достижения начисляет
ВОRKER. Чтобы сервер не мог заплатить больше, чем задумано игрой, ему нужны
те же таблицы наград, что и клиенту. Держать их в двух файлах — значит
рано или поздно получить расхождение, поэтому таблицы ВЫЧИТЫВАЮТСЯ из
assets/app.js (MISSION_POOL, ACHIEVEMENTS, DAILY_REWARDS) и вставляются в
assets/nx-rules.js между маркерами NXR_TABLES_START/END.

Файл nx-rules.js грузит и браузер, и воркер — значит и клиент, и сервер
работают по одним числам, а обновляются они одной командой.

Что ещё здесь
─────────────
Для каждого достижения прописано, по какому серверному счётчику его проверять
(ACH_RULES). Счётчики сервер ведёт сам, потому что сам же и проводит все
спины, вскрытия паков и продажи. Достижения, которые сервер проверить не может
(арена/дурак — они пока считаются на клиенте, и «альбомы» — нужна коллекция),
помечены None: такая награда выдаётся ОДИН раз на id и в размере из таблицы,
то есть завысить её нельзя даже при желании.

Запуск
──────
    python3 tools/gen_nx_rules_tables.py            # обновить nx-rules.js
    python3 tools/gen_nx_rules_tables.py --check    # только сравнить, не писать
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'assets', 'app.js')
RULES = os.path.join(ROOT, 'assets', 'nx-rules.js')

START = '/*NXR_TABLES_START*/'
END = '/*NXR_TABLES_END*/'

# тип задания -> счётчик сервера (поле p.st). Сервер увеличивает их сам,
# когда проводит соответствующее действие.
MISSION_COUNTER = {
    'open_pack': 'packsOpened',
    'collect_new': 'newCards',
    'find_rare_plus': 'rarePlusFound',
    'find_epic_plus': 'epicPlusFound',
    'sell_dupe': 'dupesSold',
    'earn_dupe_coins': 'dupeCoins',
    'open_album': 'albumOpens',
    'spin_slots': 'slotsSpins',
    'win_slots': 'slotsWins',
    'slots_coins': 'slotsCoins',
    'spin_grid': 'gridSpins',
    'win_grid': 'gridWins',
    'grid_coins': 'gridCoins',
    'spin_lines': 'linesSpins',
    'win_lines': 'linesWins',
    'lines_coins': 'linesCoins',
    'wheel_spin': 'wheelSpins',
    'wheel_coins': 'wheelCoins',
    'mines_open': 'minesOpen',
    'mines_win': 'minesWins',
    'mines_coins': 'minesCoins',
    'mine_ore': 'mineOre',
    'miner_upgrade': 'minerUpgrades',
}

# достижение -> (счётчик сервера, порог). None = сервер проверить не может,
# награда выдаётся один раз на id в размере из таблицы.
ACH_RULES = {
    'first_card': ('collected', 1),
    'collector_10': ('collected', 10),
    'collector_25': ('collected', 25),
    'collector_50': ('collected', 50),
    'rare_find': ('rarePlusFound', 1),
    'epic_find': ('epicPlusFound', 1),
    'legendary_find': ('legendariesFound', 1),
    'packs_5': ('packsOpened', 5),
    'packs_20': ('packsOpened', 20),
    'packs_50': ('packsOpened', 50),
    'dupes_10': ('dupesSold', 10),
    'dupes_50': ('dupesSold', 50),
    'album_complete': None,
    'albums_3': None,
    'albums_5': None,
    'albums_10': None,
    'rich': ('balance', 2000),
    'streak_7': ('bestStreak', 7),
    'all_missions': None,
    'first_win': None,
    'wins_10': None,
    'wins_25': None,
    'flawless': None,
    'battle_streak3': None,
    'champion_down': None,
    'durak_win': None,
    'durak_streak3': None,
    'slots_win_1': ('slotsWins', 1),
    'slots_win_10': ('slotsWins', 10),
    'slots_jackpot': ('jackpots', 1),
    'grid_win_1': ('gridWins', 1),
    'grid_win_10': ('gridWins', 10),
    'grid_chain3': ('bestGridChain', 3),
    'miner_lvl5': ('minerLvl', 5),
    'miner_lvl10': ('minerLvl', 10),
    'lines_win_10': ('linesWins', 10),
    'wheel_spin_10': ('wheelSpins', 10),
    'mines_win_10': ('minesWins', 10),
}


def block(src, marker):
    i = src.index(marker)
    j = src.index('\n        ];', i)
    return src[i:j]


def js_obj(d, indent='        '):
    parts = []
    for k in d:
        v = d[k]
        if isinstance(v, list):
            parts.append("%s'%s': %s" % (indent, k, json_arr(v)))
        elif v is None:
            parts.append("%s'%s': null" % (indent, k))
        elif isinstance(v, tuple):
            parts.append("%s'%s': { k: '%s', n: %d }" % (indent, k, v[0], v[1]))
        elif isinstance(v, str):
            parts.append("%s'%s': '%s'" % (indent, k, v))
        else:
            parts.append("%s'%s': %s" % (indent, k, v))
    return ',\n'.join(parts)


def json_arr(v):
    return '[' + ', '.join('[' + ', '.join(str(x) for x in item) + ']' for item in v) + ']'


def main():
    src = io.open(APP, encoding='utf-8').read()

    # ---- задания ----
    missions = {}
    mblock = block(src, 'const MISSION_POOL = [')
    for m in re.finditer(r"type:\s*'([^']+)'(.*?)(?=\n\s*\{\s*type:|\Z)", mblock, re.S):
        t, rest = m.group(1), m.group(2)
        v = re.search(r"variants:\s*(\[\[.*?\]\])", rest, re.S)
        if not v:
            continue
        pairs = re.findall(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]", v.group(1))
        missions[t] = [[int(a), int(b)] for a, b in pairs]

    # ---- достижения ----
    ach = {}
    ablock = block(src, 'const ACHIEVEMENTS = [')
    for m in re.finditer(r"\{\s*id:\s*'([^']+)'(.*?)\}\s*,?\s*$", ablock, re.S | re.M):
        aid, rest = m.group(1), m.group(2)
        rw = re.search(r"reward:\s*(\d+)", rest)
        if rw:
            ach[aid] = int(rw.group(1))

    daily = re.search(r"const DAILY_REWARDS = \[([\d,\s]+)\]", src)
    daily_list = [int(x) for x in daily.group(1).split(',')] if daily else []

    missing_m = [t for t in missions if t not in MISSION_COUNTER]
    missing_a = [a for a in ach if a not in ACH_RULES]
    if missing_m:
        print('ВНИМАНИЕ: нет счётчика сервера для заданий:', ', '.join(missing_m))
    if missing_a:
        print('ВНИМАНИЕ: нет правила проверки для достижений:', ', '.join(missing_a))

    tables = '\n'.join([
        START,
        '    // Таблицы наград ниже СГЕНЕРИРОВАНЫ из assets/app.js скриптом',
        '    // tools/gen_nx_rules_tables.py. Руками их не править: после любой',
        '    // смены наград в игре скрипт запускается заново и обновляет этот блок.',
        '    var DAILY_REWARDS = [' + ', '.join(str(x) for x in daily_list) + '];',
        '',
        '    // задания дня: тип -> варианты [цель, награда]',
        '    var MISSION_VARIANTS = {',
        js_obj(missions),
        '    };',
        '',
        '    // тип задания -> счётчик сервера (поле st игрока)',
        '    var MISSION_COUNTER = {',
        js_obj(MISSION_COUNTER),
        '    };',
        '',
        '    // достижения: награда и правило проверки (null = выдаётся один раз на id)',
        '    var ACHIEVEMENT_REWARDS = {',
        js_obj(ach),
        '    };',
        '    var ACHIEVEMENT_RULES = {',
        js_obj(ACH_RULES),
        '    };',
        END,
    ])

    rules = io.open(RULES, encoding='utf-8').read()
    if START not in rules or END not in rules:
        print('ОШИБКА: в assets/nx-rules.js нет маркеров %s/%s' % (START, END))
        return 1
    new = re.sub(re.escape(START) + r'.*?' + re.escape(END), tables.replace('\\', '\\\\'), rules, flags=re.S)
    # добавляем таблицы в экспортируемый объект NXR (один раз)
    if 'MISSION_VARIANTS: MISSION_VARIANTS' not in new:
        new = new.replace(
            "        BET_MAX: BET_MAX, normBet: normBet",
            "        BET_MAX: BET_MAX, normBet: normBet,\n"
            "        DAILY_REWARDS: DAILY_REWARDS, MISSION_VARIANTS: MISSION_VARIANTS,\n"
            "        MISSION_COUNTER: MISSION_COUNTER, ACHIEVEMENT_REWARDS: ACHIEVEMENT_REWARDS,\n"
            "        ACHIEVEMENT_RULES: ACHIEVEMENT_RULES")
    if '--check' in sys.argv:
        print('Таблицы: заданий %d, достижений %d, дневных наград %d' % (len(missions), len(ach), len(daily_list)))
        print('ПРОБЛЕМА: файл отличается от сгенерированного' if new != rules else 'nx-rules.js актуален')
        return 0 if new == rules else 2
    io.open(RULES, 'w', encoding='utf-8').write(new)
    print('nx-rules.js: таблицы наград обновлены (заданий %d, достижений %d)' % (len(missions), len(ach)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
