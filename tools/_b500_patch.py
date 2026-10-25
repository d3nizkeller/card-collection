#!/usr/bin/env python3
# b500: новая игра во вкладке «Игры» — «Русское лото».
# Мешок из 90 деревянных бочонков, карточка 3×9, табло 1–90 и голосовая озвучка
# каждого выпавшего номера (Web Speech API, ru-RU). Правки: index.html (плитка
# режима, лобби, CSS), assets/app.css (сетка плиток 6/11), assets/app.js
# (setBattleMode, степперы ставки, игровой модуль b500). Версия nxmob242->243.
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))


def read(p):
    with io.open(os.path.join(ROOT, p), 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write(p, s):
    with io.open(os.path.join(ROOT, p), 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def rd(p):
    with io.open(os.path.join(HERE, p), 'r', encoding='utf-8', newline='') as f:
        return f.read()


LOTO_BTN = ('<button onclick="setBattleMode(\'loto\')" id="mode-loto-btn" class="w-full flex flex-col items-center justify-center gap-1 px-1 py-2 rounded-xl text-[13px] sm:text-[15px] lg:text-[13px] font-bold transition whitespace-nowrap overflow-hidden min-w-0 lg:flex-row lg:gap-1.5 lg:px-2 bg-slate-800 text-slate-300 border border-slate-700" title="Русское лото: мешок бочонков, карточка 3×9 и голосовая озвучка каждого номера"><svg class="w-[15px] h-[15px] mb-0.5 lg:mb-0 lg:mr-1.5 shrink-0" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 8.2c0-2 2.2-3.2 5-3.2s5 1.2 5 3.2v8.6c0 2-2.2 3.2-5 3.2s-5-1.2-5-3.2z" fill="#c89b62" stroke="#7c4a24" stroke-width="1.4"/><ellipse cx="12" cy="8.2" rx="5" ry="3" fill="#f1dcb4" stroke="#7c4a24" stroke-width="1.4"/><circle cx="12" cy="8.2" r="1.9" fill="#fff8e6" stroke="#d64541" stroke-width="1.1"/><path d="M7 12.5h10M7 15.5h10" stroke="#7c4a24" stroke-width=".9" opacity=".55"/></svg><span class="block lg:inline w-full lg:w-auto text-center lg:text-left text-[8px] sm:text-[9px] lg:text-xs font-bold leading-none truncate">Лото</span></button>')

EDITS = [
    # ---------------- index.html: плитка режима «Лото» в nx-modes ----------------
    ('index.html',
     'truncate">Рулетка</span></button>',
     'truncate">Рулетка</span></button>\n                ' + LOTO_BTN),
    # ---------------- index.html: :active для новой плитки ----------------
    ('index.html',
     '#mode-tama-btn:active, #mode-roulette-btn:active, #miner-btn:active{ transform: scale(.97); }',
     '#mode-tama-btn:active, #mode-roulette-btn:active, #mode-loto-btn:active, #miner-btn:active{ transform: scale(.97); }'),
    # ---------------- index.html: CSS игры перед закрытием <style> ----------------
    ('index.html',
     '        #player-name-box.name-flash{ animation:none; }\n    }\n    </style>',
     '        #player-name-box.name-flash{ animation:none; }\n    }\n' + rd('_b500_loto_css.txt') + '    </style>'),
    # ---------------- index.html: лобби «Лото» перед лобби Тамагочи ----------------
    ('index.html',
     '                <!-- b483: лобби режима «Тамагочи» — содержимое рисует renderTamagotchi() -->',
     rd('_b500_loto_html.txt') + '                <!-- b483: лобби режима «Тамагочи» — содержимое рисует renderTamagotchi() -->'),
    # ---------------- assets/app.css: 11 плиток режимов (6 на телефоне) ----------------
    ('assets/app.css',
     '.nx-modes{grid-template-columns:repeat(5,minmax(0,1fr))}',
     '.nx-modes{grid-template-columns:repeat(6,minmax(0,1fr))}'),
    ('assets/app.css',
     '@media (min-width:640px){.nx-modes{grid-template-columns:repeat(10,minmax(0,1fr))}}',
     '@media (min-width:640px){.nx-modes{grid-template-columns:repeat(11,minmax(0,1fr))}}'),
    # ---------------- assets/app.js: setBattleMode — лобби и плитка ----------------
    ('assets/app.js',
     "            const lr = document.getElementById('lobby-roulette'); // b488\n            if (lr) lr.classList.toggle('hidden', m !== 'roulette');",
     "            const lr = document.getElementById('lobby-roulette'); // b488\n            if (lr) lr.classList.toggle('hidden', m !== 'roulette');\n            const llto = document.getElementById('lobby-loto'); // b500\n            if (llto) llto.classList.toggle('hidden', m !== 'loto');"),
    ('assets/app.js',
     "            setModeBtn('mode-roulette-btn', m === 'roulette', 'lq-on'); // b488",
     "            setModeBtn('mode-roulette-btn', m === 'roulette', 'lq-on'); // b488\n            setModeBtn('mode-loto-btn', m === 'loto', 'lq-on'); // b500"),
    # ---------------- assets/app.js: смена режима гасит авто-тираж лото ----------------
    ('assets/app.js',
     "            if (m !== 'wheel' && wheel.auto) { wheel.auto = false; try { wheelAutoUI(); } catch (e) {} } // b314",
     "            if (m !== 'wheel' && wheel.auto) { wheel.auto = false; try { wheelAutoUI(); } catch (e) {} } // b314\n            if (m !== 'loto' && loto.auto) lotoStopAuto(false); // b500"),
    ('assets/app.js',
     "            if (m === 'mines') { renderMinesUI(); } // b79",
     "            if (m === 'mines') { renderMinesUI(); } // b79\n            if (m === 'loto') { renderLoto(); } // b500"),
    # ---------------- assets/app.js: ставка лото в степперах (2 места) ----------------
    ('assets/app.js',
     "            else if (game === 'durak') durakSetBet(b);",
     "            else if (game === 'durak') durakSetBet(b);\n            else if (game === 'loto') lotoSetBet(b); // b500",
     2),
    ('assets/app.js',
     "const cur = game === 'slots' ? slots.bet : game === 'grid' ? grid.bet : game === 'lines' ? lines.bet : game === 'wheel' ? wheel.bet : game === 'durak' ? durakBet : mines.bet;",
     "const cur = game === 'slots' ? slots.bet : game === 'grid' ? grid.bet : game === 'lines' ? lines.bet : game === 'wheel' ? wheel.bet : game === 'durak' ? durakBet : game === 'loto' ? loto.bet : mines.bet; // b500",
     2),
    # ---------------- assets/app.js: модуль игры перед window.onload ----------------
    ('assets/app.js',
     '        window.onload = function() {',
     rd('_b500_loto_module.js') + '        window.onload = function() {'),
]

TAG_OLD, TAG_NEW = 'nxmob242', 'nxmob243'


def main():
    check = '--check' in sys.argv
    problems = []
    for ed in EDITS:
        p, old, new = ed[0], ed[1], ed[2]
        want = ed[3] if len(ed) > 3 else 1
        s = read(p)
        if old not in s:
            problems.append('%s: якорь не найден: %s…' % (p, old[:60]))
        elif s.count(old) != want:
            problems.append('%s: якорь встречается %d раз (ждём %d): %s…' % (p, s.count(old), want, old[:60]))
        if new and new.strip() and new in s:
            problems.append('%s: похоже, патч УЖЕ применён: %s…' % (p, new[:60]))
    idx = read('index.html')
    if idx.count(TAG_OLD) != 8:
        problems.append('index.html: тега %s найдено %d (ждём 8)' % (TAG_OLD, idx.count(TAG_OLD)))
    sw = read('sw.js')
    if ("VERSION = '%s';" % TAG_OLD) not in sw:
        problems.append('sw.js: строки VERSION=%s нет' % TAG_OLD)
    bp = read('tools/build.py')
    if ("BUILD_TAG = '%s'" % TAG_OLD) not in bp:
        problems.append('tools/build.py: BUILD_TAG=%s нет' % TAG_OLD)
    if problems:
        for x in problems:
            print('PROBLEM:', x)
        return 1
    if check:
        print('OK: все якоря на месте, патч применим')
        return 0
    for ed in EDITS:
        p, old, new = ed[0], ed[1], ed[2]
        want = ed[3] if len(ed) > 3 else 1
        s = read(p)
        if want == 1:
            s = s.replace(old, new, 1)
        else:
            s = s.replace(old, new)
        write(p, s)
    for p in ('index.html', 'sw.js', 'tools/build.py'):
        s = read(p)
        s = s.replace(TAG_OLD, TAG_NEW)
        write(p, s)
    print('b500: применено правок:', len(EDITS), '+ версия', TAG_NEW)
    return 0


if __name__ == '__main__':
    sys.exit(main())
