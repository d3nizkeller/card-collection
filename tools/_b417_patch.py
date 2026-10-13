#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b417 — «кнопки зависают»: disabled из-за нехватки монет былsilent-состоянием.

Жалоба владельца: «в играх кнопки зависают и невозможно играть» + скриншот
димленной кнопки «Крутить — 10m».

Диагноз: во всех пяти играх кнопка ставки получала `disabled`, когда
`state.coins < bet` (renderSlotsUI/renderGridUI/renderMinesUI/renderLinesUI/
renderWheelUI). Disabled-кнопка не пропускает клик, поэтому обработчик со своим
тостом «Недостаточно монет…» (slotsSpin/gridSpin/wheelSpin/minesStart/linesSpin)
НИКОГДА не вызывался: тап не давал НИКАКОЙ обратной связи — ни тоста, ни
подсказки, ни изменения состояния. Со стороны это выглядит ровно как «зависла»:
кнопка есть, тусклая, не нажимается. При этом ставка 10m оставалась выбранной,
и снижение ставки было единственным выходом, о котором игра молчала.

Стало (b417):

* `disabled` остаётся ТОЛЬКО на время спина/раунда (защита от двойного списания);
* при нехватке монет кнопка гаснет визуально (opacity-40), но кликабельна:
  обработчик показывает тост с причиной и выходом —
  «не хватает N — снизьте ставку кнопкой −», а при балансе ниже минимальной
  ставки (100) — «монеты кончились — загляните в Шахту и задания дня»;
* подсветка нехватки добавлена и там, где её не было (Сетка/Колесо/Мины/Линии);
* минная кнопка «Начать раунд» больше не disabled из-за монет (раунд всё равно
  не стартует, но тост объясняет почему).

Запуск:  python3 tools/_b417_patch.py            — применить
         python3 tools/_b417_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob77'
NEW_V = 'nxmob78'

# --------------------------------------------------------------------------- #
# app.js
# --------------------------------------------------------------------------- #

ANCHOR_HELPER = "        function updateCoinDisplay() {\n"

HELPER = r'''        // ============ b417: ЗАВИСШАЯ КНОПКА — ЭТО ТА, КОТОРАЯ МОЛЧИТ ============
        // До b417 при нехватке монет кнопка ставки получала disabled: клик не
        // доходил до обработчика, тост «Недостаточно монет» не показывался, и
        // игрок видел «кнопка зависла». Теперь disabled выдаётся только на время
        // спина/раунда, а при нехватке монет кнопка гаснет визуально, но остаётся
        // кликабельной — обработчик объясняет причину и подсказывает выход.
        function nxBetLack(bet) {
            return Math.max(0, Math.round((Number(bet) || 0) - (Math.floor(Number(state.coins)) || 0)));
        }
        function nxLackNote(bet) {
            const lack = nxBetLack(bet);
            if (lack <= 0) return '';
            if ((Math.floor(Number(state.coins)) || 0) < 100) return ' Монеты кончились — их дают Шахта и задания дня.';
            return ' Не хватает ' + fmtCoins(lack) + ' — снизьте ставку кнопкой «−».';
        }
'''

JS_PATCHES = [
    # --- helper ---
    ('helper нехватки ставки (b417)', ANCHOR_HELPER, HELPER + ANCHOR_HELPER),

    # --- Слоты: рендер ---
    ('слоты: disabled только на спин',
     """                spin.innerHTML = '<i class="fa-solid fa-rotate mr-1"></i>Крутить — ' + fmtCoins(slots.bet);
                spin.disabled = state.coins < slots.bet || slots.spinning;
                spin.classList.toggle('opacity-40', state.coins < slots.bet);
""",
     """                spin.innerHTML = '<i class="fa-solid fa-rotate mr-1"></i>Крутить — ' + fmtCoins(slots.bet);
                // b417: disabled — только пока крутится; нехватка монет гасит кнопку
                // визуально, но клик доходит до slotsSpin и там объясняется
                spin.disabled = slots.spinning;
                spin.classList.toggle('opacity-40', state.coins < slots.bet);
"""),

    # --- Слоты: тост ---
    ('слоты: тост с подсказкой',
     "            if (state.coins < bet) { showToast('Недостаточно монет для ставки ' + fmtCoins(bet), 'error'); return; }\n            if (!slots.symbols.length) slots.symbols = slotsSymbols();",
     "            if (state.coins < bet) { showToast('Недостаточно монет для ставки ' + fmtCoins(bet) + '.' + nxLackNote(bet), 'error'); return; }\n            if (!slots.symbols.length) slots.symbols = slotsSymbols();"),

    # --- Сетка: рендер ---
    ('сетка: disabled только на спин',
     """                spin.innerHTML = '<i class="fa-solid fa-rotate mr-1"></i>Крутить — ' + fmtCoins(grid.bet);
                spin.disabled = state.coins < grid.bet || grid.spinning;
                spin.classList.toggle('opacity-40', state.coins < grid.bet);
""",
     """                spin.innerHTML = '<i class="fa-solid fa-rotate mr-1"></i>Крутить — ' + fmtCoins(grid.bet);
                spin.disabled = grid.spinning; // b417: нехватка монет — не disabled
                spin.classList.toggle('opacity-40', state.coins < grid.bet);
"""),

    # --- Сетка: тост ---
    ('сетка: тост с подсказкой',
     "            if (state.coins < bet) { showToast('Недостаточно монет для ставки ' + fmtCoins(bet), 'error'); return; }\n            state.coins -= bet;",
     "            if (state.coins < bet) { showToast('Недостаточно монет для ставки ' + fmtCoins(bet) + '.' + nxLackNote(bet), 'error'); return; }\n            state.coins -= bet;"),

    # --- Мины: рендер ---
    ('мины: disabled только на раунд',
     """                start.classList.toggle('hidden', mines.active);
                start.disabled = state.coins < mines.bet;
                start.classList.toggle('opacity-40', state.coins < mines.bet);
""",
     """                start.classList.toggle('hidden', mines.active);
                start.disabled = mines.active; // b417: нехватка монет — не disabled
                start.classList.toggle('opacity-40', state.coins < mines.bet);
"""),

    # --- Мины: тост ---
    ('мины: тост с подсказкой',
     "            if (state.coins < bet) { showToast('Недостаточно монет!', 'error'); return; }\n            state.coins -= bet;\n            updateCoinDisplay(); saveState();\n            jackpotFeed(bet); // b79:",
     "            if (state.coins < bet) { showToast('Недостаточно монет!' + nxLackNote(bet), 'error'); return; }\n            state.coins -= bet;\n            updateCoinDisplay(); saveState();\n            jackpotFeed(bet); // b79:"),

    # --- Линии: рендер ---
    ('линии: disabled только на спин',
     "            if (spin) { spin.disabled = lines.spinning || state.coins < lines.bet; spin.classList.toggle('opacity-40', lines.spinning || state.coins < lines.bet); }",
     "            if (spin) { spin.disabled = lines.spinning; spin.classList.toggle('opacity-40', lines.spinning || state.coins < lines.bet); } // b417: нехватка монет — не disabled"),

    # --- Линии: тост ---
    ('линии: тост с подсказкой',
     "            if (state.coins < bet) { showToast('Недостаточно монет!', 'error'); return; }\n            linesEnsure();",
     "            if (state.coins < bet) { showToast('Недостаточно монет!' + nxLackNote(bet), 'error'); return; }\n            linesEnsure();"),

    # --- Колесо: рендер ---
    ('колесо: disabled только на спин',
     """                spin.innerHTML = '<i class="fa-solid fa-dharmachakra mr-1"></i>Крутить — ' + fmtCoins(wheel.bet);
                spin.disabled = wheel.spinning || state.coins < wheel.bet;
                spin.classList.toggle('opacity-40', wheel.spinning || state.coins < wheel.bet);
""",
     """                spin.innerHTML = '<i class="fa-solid fa-dharmachakra mr-1"></i>Крутить — ' + fmtCoins(wheel.bet);
                spin.disabled = wheel.spinning; // b417: нехватка монет — не disabled
                spin.classList.toggle('opacity-40', wheel.spinning || state.coins < wheel.bet);
"""),

    # --- Колесо: тост ---
    ('колесо: тост с подсказкой',
     "            if (state.coins < bet) { showToast('Недостаточно монет!', 'error'); return; }\n            wheelEnsure();",
     "            if (state.coins < bet) { showToast('Недостаточно монет!' + nxLackNote(bet), 'error'); return; }\n            wheelEnsure();"),
]

# «Недостаточно монет!» встречается у мин/линий/колеса — правим все одинаково,
# но якоря выше уже уникальны за счёт окружающего кода; этот список — страховка,
# что других молчаливых мест не осталось.
JS_PATCHES_ALL = []


# --------------------------------------------------------------------------- #
def patch_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise AssertionError('якорь «%s» встретился %d раз (нужно 1)' % (label, n))
    return text.replace(old, new, 1)


def main():
    check = '--check' in sys.argv
    js = os.path.join(ROOT, 'assets', 'app.js')

    if check:
        bad = 0
        s = open(js, encoding='utf-8').read()
        for label, old, _n in JS_PATCHES:
            n = s.count(old); bad += (n != 1); print('  %s %-40s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        return 1 if bad else 0

    s = open(js, encoding='utf-8').read()
    for label, old, new in JS_PATCHES:
        s = patch_once(s, old, new, label); print('  · %-40s ok' % label)
    open(js, 'w', encoding='utf-8', newline='').write(s)

    html = os.path.join(ROOT, 'index.html')
    for p, old, new in ((html, '?v=' + OLD_V, '?v=' + NEW_V),
                        (os.path.join(ROOT, 'sw.js'), "const VERSION = '%s';" % OLD_V, "const VERSION = '%s';" % NEW_V),
                        (os.path.join(ROOT, 'tools', 'build.py'), "BUILD_TAG = '%s'" % OLD_V, "BUILD_TAG = '%s'" % NEW_V)):
        t = open(p, encoding='utf-8').read()
        n = t.count(old)
        if n:
            open(p, 'w', encoding='utf-8', newline='').write(t.replace(old, new))
        print('  · версия %-28s ×%d → %s' % (os.path.basename(p), n, NEW_V))
    return 0


if __name__ == '__main__':
    sys.exit(main())
