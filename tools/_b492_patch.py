#!/usr/bin/env python3
# b492: суммы рулетки — буквами («1k», «9.8m»), лицо фишки — контрастная таблетка.
# Жалоба владельца: «сделай суммы 1k и все остальные буквы, и в фишках не видно
# сумму, потому что сумма написана белым на белом».
#  1) бейджи ставок на клетках, «На столе», «Крутить ·», кошелёк стола (#rl-table-sum)
#     и живой +/− (rlFlash) — через fmtCoins (буквы k/m/b/t/…);
#  2) лицо фишки: достоинство в сплошной цветной таблетке .rl-chip-val поверх
#     конических полос — раньше белая цифра терялась на белых секторах;
#  3) баланс остаётся ТОЧНЫМ до монеты (b491) — иначе «баланс не двигается».
# Якоря применяются один раз; повторный запуск отклоняется (--check для проверки).
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EDITS = [
    # ---------------- assets/app.js ----------------
    ('assets/app.js',
     """        // в лобби рулетки шапка показывает точную сумму (пока она влезает в пилюлю)""",
     """        // b492: суммы НА СТОЛЕ (бейджи на клетках, «На столе», «Крутить», кошелёк
        // стола, живой +/−) показываются буквами — fmtCoins: 1000 -> «1k»,
        // 9834496 -> «9.8m». Сырые числа вроде 3690496 не влезали в мини-фишку
        // и читались как каша. Баланс остаётся точным до монеты (b491).
        // в лобби рулетки шапка показывает точную сумму (пока она влезает в пилюлю)"""),
    ('assets/app.js',
     """            if (ts) { let t = '0'; try { t = nxCoinsExact(rouletteTotal()); } catch (e) {} if (ts.textContent !== t) ts.textContent = t; }""",
     """            if (ts) { let t = '0'; try { t = fmtCoins(rouletteTotal()); } catch (e) {} if (ts.textContent !== t) ts.textContent = t; } // b492: сумма стола — буквами"""),
    ('assets/app.js',
     """                el.textContent = (d > 0 ? '+' : '−') + nxCoinsExact(Math.abs(d));""",
     """                el.textContent = (d > 0 ? '+' : '−') + fmtCoins(Math.abs(d)); // b492: живой +/− буквами"""),
    ('assets/app.js',
     """class="rl-chipmini">${bet}</i>""",
     """class="rl-chipmini">${fmtCoins(bet)}</i>"""),
    ('assets/app.js',
     """            const betBadge = id => (rouletteBets[id] || 0) ? `<i class="rl-chipmini">${rouletteBets[id]}</i>` : '';""",
     """            const betBadge = id => (rouletteBets[id] || 0) ? `<i class="rl-chipmini">${fmtCoins(rouletteBets[id])}</i>` : ''; // b492: буквами"""),
    ('assets/app.js',
     """title="Фишка ${c} монет">${c}</button>""",
     """title="Фишка ${fmtCoins(c)} монет"><span class="rl-chip-val">${fmtCoins(c)}</span></button>"""),
    ('assets/app.js',
     """На столе: <b class="text-amber-300">${nxCoinsExact(total)}</b>""",
     """На столе: <b class="text-amber-300">${fmtCoins(total)}</b>"""),
    ('assets/app.js',
     """Крутить · ${total || '—'}</button>""",
     """Крутить · ${total ? fmtCoins(total) : '—'}</button>"""),
    # ---------------- assets/app.css ----------------
    ('assets/app.css',
     """.rl-chip-on{opacity:1;transform:scale(1.12);box-shadow:0 0 0 3px rgba(251,191,36,.85),0 6px 14px rgba(2,6,23,.7),inset 0 0 0 3px rgba(248,250,252,.85)}""",
     """.rl-chip-on{opacity:1;transform:scale(1.12);box-shadow:0 0 0 3px rgba(251,191,36,.85),0 6px 14px rgba(2,6,23,.7),inset 0 0 0 3px rgba(248,250,252,.85)}
/* b492: лицо фишки — контрастная сплошная таблетка в центре: белая цифра
   терялась на белых секторах конического градиента (белым по белому, скрин
   владельца). Цвет таблетки = цвет фишки, текст всегда читается. */
.rl-chip-val{width:28px;height:28px;border-radius:9999px;display:flex;align-items:center;justify-content:center;background:#0b1220;color:#f8fafc;font-size:11px;font-weight:900;line-height:1;box-shadow:0 0 0 2px rgba(248,250,252,.8),inset 0 1px 3px rgba(255,255,255,.28);text-shadow:0 1px 2px rgba(0,0,0,.7)}
.rl-chip-1 .rl-chip-val{background:#475569}
.rl-chip-5 .rl-chip-val{background:#b91c1c}
.rl-chip-25 .rl-chip-val{background:#047857}
.rl-chip-100 .rl-chip-val{background:#b45309}"""),
    ('assets/app.css',
     """    .rl-chip{width:38px;height:38px;font-size:11px}""",
     """    .rl-chip{width:38px;height:38px;font-size:11px}
    .rl-chip-val{width:24px;height:24px;font-size:10px}"""),
]

TAG_OLD, TAG_NEW = 'nxmob235', 'nxmob236'


def read(p):
    with io.open(os.path.join(ROOT, p), 'r', encoding='utf-8') as f:
        return f.read()


def write(p, s):
    with io.open(os.path.join(ROOT, p), 'w', encoding='utf-8') as f:
        f.write(s)


def main():
    check = '--check' in sys.argv
    problems = []
    for p, old, new in EDITS:
        s = read(p)
        if old not in s:
            problems.append('%s: якорь не найден: %s…' % (p, old[:60]))
        elif s.count(old) != 1:
            problems.append('%s: якорь встречается %d раз: %s…' % (p, s.count(old), old[:60]))
        if new in s:
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
        sys.exit(1)
    if check:
        print('check ok: %d якорей + тег %s -> %s' % (len(EDITS), TAG_OLD, TAG_NEW))
        sys.exit(0)
    for p, old, new in EDITS:
        s = read(p)
        write(p, s.replace(old, new, 1))
    write('index.html', read('index.html').replace(TAG_OLD, TAG_NEW))
    write('sw.js', read('sw.js').replace("VERSION = '%s';" % TAG_OLD, "VERSION = '%s';" % TAG_NEW))
    write('tools/build.py', read('tools/build.py').replace("BUILD_TAG = '%s'" % TAG_OLD, "BUILD_TAG = '%s'" % TAG_NEW))
    print('applied: %d якорей, тег %s -> %s' % (len(EDITS), TAG_OLD, TAG_NEW))


if __name__ == '__main__':
    main()
