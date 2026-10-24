#!/usr/bin/env python3
# b493: кошелёк стола рулетки — в одну строку на всю ширину лобби.
# Жалоба владельца (скрин): «Сделай в одну линию и ширину» — кошелёк висел
# узкой карточкой справа от заголовка, строки стояли столбиком, слева пустота.
#  1) кошелёк вынут из flex-строки заголовка и стал отдельной панелью .rl-wallet
#     на всю ширину: подпись, точный баланс, «На столе», «Спинов / побед» и
#     «золотое зеро» — в ОДНУ строку (display:flex, width:100%);
#  2) зеркало золотого зеро прижато к правому краю за пунктирным разделителем;
#  3) на телефоне (<640px) строка аккуратно переносится, разделитель скрыт;
#  4) все id сохранены — поведение b491/b492 (точный баланс, буквы, живой +/−)
#     не меняется; assertions test-b491 обновлены под новую разметку.
# Якоря применяются один раз; повторный запуск отклоняется (--check для проверки).
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EDITS = [
    # ---------------- index.html ----------------
    ('index.html',
     """                            <!-- b491: кошелёк стола — баланс точно до монеты, сумма на столе, живой плюс/минус -->
                            <div class="rl-wallet shrink-0">
                                <p class="rl-w-cap"><i class="fa-solid fa-wallet"></i>Кошелёк стола</p>
                                <p class="rl-w-bal"><span id="rl-balance">0</span><i id="rl-delta" class="rl-delta"></i></p>
                                <p class="rl-w-rows"><span>На столе</span><b id="rl-table-sum">0</b></p>
                                <p class="rl-w-rows"><span>Спинов / побед</span><b><span id="rl-spins">0</span> / <span id="rl-wins">0</span></b></p>
                                <p class="rl-w-jp"><i class="fa-solid fa-crown"></i><span id="rl-jp-odds">золотое зеро: —</span></p>
                            </div>
                        </div>""",
     """                        </div>
                        <!-- b493: кошелёк стола — ОДНА строка на всю ширину лобби (b491/b492):
                             подпись, точный баланс, «На столе», «Спинов / побед», золотое зеро -->
                        <div class="rl-wallet">
                            <span class="rl-w-cap"><i class="fa-solid fa-wallet"></i>Кошелёк стола</span>
                            <span class="rl-w-bal"><span id="rl-balance">0</span><i id="rl-delta" class="rl-delta"></i></span>
                            <span class="rl-w-rows"><span>На столе</span><b id="rl-table-sum">0</b></span>
                            <span class="rl-w-rows"><span>Спинов / побед</span><b><span id="rl-spins">0</span> / <span id="rl-wins">0</span></b></span>
                            <span class="rl-w-jp"><i class="fa-solid fa-crown"></i><span id="rl-jp-odds">золотое зеро: —</span></span>
                        </div>"""),
    # ---------------- assets/app.css ----------------
    ('assets/app.css',
     """.rl-wallet{flex:0 1 250px;min-width:196px;margin-left:auto;border-radius:14px;border:1px solid rgba(251,191,36,.35);background:linear-gradient(160deg,rgba(2,6,23,.88),rgba(15,23,42,.62));padding:9px 11px;box-shadow:inset 0 0 22px rgba(251,191,36,.07)}
.rl-w-cap{font-size:9px;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:rgba(252,211,77,.92)}
.rl-w-cap i{margin-right:5px}
.rl-w-bal{display:flex;align-items:baseline;gap:8px;margin-top:4px;font-family:ui-monospace,SFMono-Regular,monospace;font-size:25px;line-height:1;font-weight:900;color:#fde68a;text-shadow:0 0 18px rgba(251,191,36,.28)}
.rl-w-rows{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-top:6px;font-size:10px;font-weight:700;color:#94a3b8}
.rl-w-rows b{font-family:ui-monospace,SFMono-Regular,monospace;font-size:12px;font-weight:900;color:#e2e8f0}
.rl-w-jp{margin-top:7px;padding-top:6px;border-top:1px dashed rgba(251,191,36,.25);font-size:10px;font-weight:800;color:#fcd34d}
.rl-w-jp i{margin-right:5px}""",
     """/* b493: кошелёк стола — одна строка на всю ширину лобби: подпись, точный
   баланс, «На столе», «Спинов / побед» и золотое зеро стоят в ряд, зеркало
   зеро прижато к правому краю за пунктирным разделителем. */
.rl-wallet{display:flex;align-items:center;flex-wrap:wrap;gap:6px 20px;width:100%;margin-top:12px;padding:8px 16px;border-radius:14px;border:1px solid rgba(251,191,36,.35);background:linear-gradient(90deg,rgba(2,6,23,.9),rgba(15,23,42,.55));box-shadow:inset 0 0 22px rgba(251,191,36,.07)}
.rl-w-cap{display:flex;align-items:center;font-size:9px;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:rgba(252,211,77,.92);white-space:nowrap}
.rl-w-cap i{margin-right:5px}
.rl-w-bal{display:flex;align-items:baseline;gap:8px;font-family:ui-monospace,SFMono-Regular,monospace;font-size:21px;line-height:1;font-weight:900;color:#fde68a;text-shadow:0 0 18px rgba(251,191,36,.28);white-space:nowrap}
.rl-w-rows{display:flex;align-items:baseline;gap:6px;font-size:10px;font-weight:700;color:#94a3b8;white-space:nowrap}
.rl-w-rows b{font-family:ui-monospace,SFMono-Regular,monospace;font-size:12px;font-weight:900;color:#e2e8f0}
.rl-w-jp{display:flex;align-items:baseline;margin-left:auto;padding-left:20px;border-left:1px dashed rgba(251,191,36,.25);font-size:10px;font-weight:800;color:#fcd34d;white-space:nowrap}
.rl-w-jp i{margin-right:5px}"""),
    ('assets/app.css',
     """@media (max-width:640px){
    .rl-wallet{flex:1 1 100%;min-width:0}
    .rl-w-bal{font-size:21px}
    .rl-delta{font-size:12px}
}""",
     """@media (max-width:640px){
    .rl-wallet{gap:5px 12px;padding:8px 12px}
    .rl-w-bal{font-size:19px}
    .rl-delta{font-size:12px}
    .rl-w-jp{margin-left:0;padding-left:0;border-left:0}
}"""),
    # ---------------- tools/test-b491.js (разметка кошелька изменилась) ----------------
    ('tools/test-b491.js',
     """        ['class="rl-wallet shrink-0"', 'id="rl-balance"', 'id="rl-delta"', 'id="rl-table-sum"', 'id="rl-spins"',""",
     """        ['class="rl-wallet"', 'id="rl-balance"', 'id="rl-delta"', 'id="rl-table-sum"', 'id="rl-spins"',"""),
    ('tools/test-b491.js',
     """    ok(/@media \\(max-width:640px\\)\\{\\s*\\.rl-wallet\\{flex:1 1 100%/.test(css), 'app.css: кошелёк на всю ширину на телефоне');""",
     """    ok(/@media \\(max-width:640px\\)\\{\\s*\\.rl-wallet\\{/.test(css), 'app.css: кошелёк-строка подстраивается на телефоне');"""),
]

TAG_OLD, TAG_NEW = 'nxmob236', 'nxmob237'


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
