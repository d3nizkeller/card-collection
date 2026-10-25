#!/usr/bin/env python3
# b505: лото — выбор числа карточек на тираж (1–4, каждая стоит ставку) + новый
# тканевый мешок с узором и бочонками из горловины (вместо «луковицы»).
# Правки: assets/app.js (модуль b500 целиком заменён на v2), index.html (мешок,
# селектор карточек, тексты), CSS-добавления. Версия nxmob244->nxmob245.
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


NEW_BAG = '''<svg viewBox="0 0 140 150" fill="none">
                                    <defs>
                                        <radialGradient id="loto-sack-g" cx="38%" cy="28%" r="85%">
                                            <stop offset="0" stop-color="#fb7185"/><stop offset=".45" stop-color="#e11d48"/><stop offset="1" stop-color="#7f1d1d"/>
                                        </radialGradient>
                                        <pattern id="loto-sack-p" width="16" height="16" patternUnits="userSpaceOnUse">
                                            <circle cx="3" cy="3" r="1.4" fill="#fcd34d" opacity=".5"/>
                                            <circle cx="11" cy="10" r="1.1" fill="#ffe4e6" opacity=".45"/>
                                            <path d="M8 5l.8 1.6 1.7.3-1.2 1.2.3 1.7-1.6-.8-1.6.8.3-1.7-1.2-1.2 1.7-.3z" fill="#fda4af" opacity=".35"/>
                                        </pattern>
                                    </defs>
                                    <ellipse cx="70" cy="141" rx="44" ry="7" fill="#000" opacity=".35"/>
                                    <path d="M46 46c-19 14-32 35-32 56 0 25 25 37 56 37s56-12 56-37c0-21-13-42-32-56z" fill="url(#loto-sack-g)"/>
                                    <path d="M46 46c-19 14-32 35-32 56 0 25 25 37 56 37s56-12 56-37c0-21-13-42-32-56z" fill="url(#loto-sack-p)"/>
                                    <path d="M38 66c-7 13-10 27-9 40M102 66c7 13 10 27 9 40" stroke="#7f1d1d" stroke-width="2.5" opacity=".4" fill="none"/>
                                    <path d="M54 58c-4 16-5 38-1 58M86 58c4 16 5 38 1 58" stroke="#fff" stroke-width="2" opacity=".16" fill="none"/>
                                    <path d="M48 46c4-9 10-13 22-13s18 4 22 13c-6 5-14 7-22 7s-16-2-22-7z" fill="#be123c"/>
                                    <path d="M54 36l-3 12M63 33l-2 14M77 33l2 14M86 36l3 12" stroke="#7f1d1d" stroke-width="2" opacity=".5"/>
                                    <ellipse cx="70" cy="33" rx="19" ry="7.5" fill="#450a0a"/>
                                    <circle cx="62" cy="30" r="7.5" fill="#f4e3c1" stroke="#8a5a33" stroke-width="1.5"/>
                                    <circle cx="62" cy="30" r="3.4" fill="none" stroke="#d64541" stroke-width="1.6"/>
                                    <circle cx="77" cy="29" r="6" fill="#efd9ae" stroke="#8a5a33" stroke-width="1.4"/>
                                    <circle cx="77" cy="29" r="2.7" fill="none" stroke="#d64541" stroke-width="1.4"/>
                                    <rect x="45" y="42" width="50" height="8" rx="4" fill="#fbbf24"/>
                                    <path d="M70 46c-7-8-18-8-20 0 7 6 14 6 20 0zM70 46c7-8 18-8 20 0-7 6-14 6-20 0z" fill="#f59e0b"/>
                                    <circle cx="70" cy="46" r="4" fill="#fde68a"/>
                                </svg>'''

TICKET_COL = '''                            <div class="flex flex-col items-center gap-1 shrink-0"><span class="text-[9px] sm:text-[10px] uppercase tracking-[.18em] font-black text-slate-500 leading-none">Карточки</span><div id="loto-tickets" class="flex items-center gap-1.5"></div></div>
'''

B505_CSS = '''
    /* ===== b505: выбор числа карточек (1–4) и новый тканевый мешок ===== */
    .loto-bag{ width:118px; height:128px; }
    .loto-bag-left{
        position:absolute; left:50%; top:64%; transform:translate(-50%,-50%) rotate(-8deg);
        width:40px; height:40px; border-radius:50%;
        display:flex; align-items:center; justify-content:center;
        background:radial-gradient(circle at 35% 30%, #fde68a, #f59e0b 62%, #b45309);
        color:#451a03; font-size:16px; font-weight:900; text-shadow:none;
        box-shadow:0 3px 10px rgba(0,0,0,.55), inset 0 0 0 2px rgba(255,255,255,.35);
    }
    .loto-ticket{ max-width:560px; margin:0 auto; }
    .loto-ticket + .loto-ticket{ margin-top:12px; }
    .loto-ticket-head{ display:flex; justify-content:space-between; align-items:center; gap:8px; font-size:12px; font-weight:800; color:#fde68a; margin:0 2px 4px; }
    .loto-stamp-row{ color:#6ee7b7; }
    .loto-stamp-full{ color:#fcd34d; text-shadow:0 0 10px rgba(252,211,77,.55); }
    @media (max-width:480px){
        .loto-bag{ width:96px; height:104px; }
        .loto-bag-left{ width:34px; height:34px; font-size:14px; }
    }
'''

EDITS = [
    # ---------------- index.html: новый мешок ----------------
    ('index.html', None, None),  # мешок меняется отдельной процедурой ниже
    # ---------------- index.html: селектор числа карточек после степпера ставки ----------------
    ('index.html',
     '<i class="fa-solid fa-plus"></i></button></div></div>\n                        </div>',
     '<i class="fa-solid fa-plus"></i></button></div></div>\n' + TICKET_COL + '                        </div>'),
    # ---------------- index.html: описание ----------------
    ('index.html',
     'все 15 чисел («ЛОТО!») — <b class="text-amber-300">×25</b>. Тираж — 60 бочонков.</p>',
     'все 15 чисел («ЛОТО!») — <b class="text-amber-300">×25</b>. Карточек покупаете, сколько хотите: <b class="text-amber-300">1–4 билета</b> на тираж (каждая стоит ставку), каждый играет сам за себя. Тираж — 60 бочонков.</p>'),
    # ---------------- index.html: правила ----------------
    ('index.html',
     '<li>Выберите ставку и нажмите <b>«Новая игра»</b> — получите карточку 3×9, а мешок из 90 бочонков перемешается.</li>',
     '<li>Выберите ставку и число карточек (<b>1–4</b>, каждая стоит ставку) и нажмите <b>«Новая игра»</b> — получите билеты 3×9, а мешок из 90 бочонков перемешается.</li>'),
    ('index.html',
     '<li>Числа на карточке закрываются сами: закрытая линия — <b>×3</b> к ставке, все 15 чисел («ЛОТО!») — <b>×25</b>.</li>',
     '<li>Числа на билетах закрываются сами: линия билета — <b>×3</b> к ставке, все 15 чисел билета («ЛОТО!») — <b>×25</b>; каждый билет играет сам за себя.</li>'),
    # ---------------- index.html: CSS b505 перед закрытием style ----------------
    ('index.html',
     '        .loto-drop{ animation:none; }\n    }\n    </style>',
     '        .loto-drop{ animation:none; }\n    }\n' + B505_CSS + '    </style>'),
]

TAG_OLD, TAG_NEW = 'nxmob244', 'nxmob245'


def swap_module(app_js, new_module):
    a = app_js.index('// ============ b500:')
    b = app_js.index('// ============ /b500 ============')
    b = app_js.index('\n', b) + 1
    return app_js[:a] + new_module.rstrip('\n') + '\n' + app_js[b:]


def swap_bag(html):
    a = html.index('<svg viewBox="0 0 120 130" fill="none">')
    b = html.index('</svg>', a) + len('</svg>')
    return html[:a] + NEW_BAG + html[b:]


def main():
    check = '--check' in sys.argv
    problems = []
    for ed in EDITS:
        if ed[1] is None:
            continue
        p, old, new = ed
        s = read(p)
        if old not in s:
            problems.append('%s: якорь не найден: %s…' % (p, old[:60]))
        elif s.count(old) != 1:
            problems.append('%s: якорь встречается %d раз: %s…' % (p, s.count(old), old[:60]))
        if new in s:
            problems.append('%s: патч УЖЕ применён: %s…' % (p, new[:60]))
    idx = read('index.html')
    if '<svg viewBox="0 0 120 130" fill="none">' not in idx:
        problems.append('index.html: старый мешок не найден')
    if idx.count(TAG_OLD) != 8:
        problems.append('index.html: тега %s найдено %d (ждём 8)' % (TAG_OLD, idx.count(TAG_OLD)))
    if problems:
        for x in problems:
            print('PROBLEM:', x)
        return 1
    if check:
        print('OK: все якоря на месте, патч b505 применим')
        return 0
    for ed in EDITS:
        if ed[1] is None:
            continue
        p, old, new = ed
        s = read(p)
        s = s.replace(old, new, 1)
        write(p, s)
    write('index.html', swap_bag(read('index.html')))
    write('assets/app.js', swap_module(read('assets/app.js'), rd('_b505_loto_module.js')))
    for p in ('index.html', 'sw.js', 'tools/build.py'):
        s = read(p)
        s = s.replace(TAG_OLD, TAG_NEW)
        write(p, s)
    print('b505: применено правок:', len([e for e in EDITS if e[1]]) , '+ мешок + модуль v2 + версия', TAG_NEW)
    return 0


if __name__ == '__main__':
    sys.exit(main())
