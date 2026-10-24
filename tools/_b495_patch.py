#!/usr/bin/env python3
# b495: рулетка — подписи зеро и колонок 2:1 БЕЗ поворота (горизонтально).
# Жалоба владельца (скрин): «Эти копки чего-то крутятся исправить что не
# крутились» — вертикальная плашка «0» и три коробки «2:1» рисовались с
# writing-mode:vertical-rl + transform:rotate(180deg), текст шёл сверху вниз.
#  1) .rl-zero-v: убраны writing-mode/rotate — «0» стоит горизонтально по
#     центру высокой плашки (flex-центровка .rl-cell уже есть);
#  2) .rl-colbet: убраны writing-mode/rotate — «2:1» читается как обычно;
#     ширины колонки хватает (40px десктоп / 22px телефон, «2:1» ≈ 17px);
#  3) test-b489: новые проверки — vertical-rl и rotate() в css стола нет.
# Якоря применяются один раз; повторный запуск отклоняется (--check для проверки).
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EDITS = [
    # ---------------- assets/app.css: зеро без вертикального текста ----------------
    ('assets/app.css',
     ".rl-zero-v{grid-column:1;grid-row:1 / span 3;writing-mode:vertical-rl;transform:rotate(180deg);font-size:14px;letter-spacing:.1em}",
     "/* b495: просьба владельца (скрин «кнопки крутятся») — подписи зеро и колонок\n   горизонтальные: vertical-rl и rotate(180deg) убраны, «0» центрирует flex */\n.rl-zero-v{grid-column:1;grid-row:1 / span 3;font-size:14px;letter-spacing:.1em}"),
    # ---------------- assets/app.css: колонки 2:1 без вертикального текста ----------------
    ('assets/app.css',
     ".rl-colbet{writing-mode:vertical-rl;transform:rotate(180deg);font-size:10px}",
     ".rl-colbet{font-size:10px}"),
    # ---------------- tools/test-b489.js: css-проверки b495 ----------------
    ('tools/test-b489.js',
     "        ok(/@media \\(max-width:640px\\)\\{\\s*\\.rl-grid\\{grid-template-columns:26px/.test(css), 'мобильный стол ужимается под 390px');",
     "        ok(/@media \\(max-width:640px\\)\\{\\s*\\.rl-grid\\{grid-template-columns:26px/.test(css), 'мобильный стол ужимается под 390px');\n        ok(!css.includes('writing-mode:vertical-rl'), 'b495: зеро и колонки 2:1 без вертикального текста');\n        ok(!/\\.rl-(zero-v|colbet)\\{[^}]*rotate\\(/.test(css), 'b495: rotate() у зеро и колонок нет');"),
    # ---------------- tools/test-b489.js: имя проверки разметки ----------------
    ('tools/test-b489.js',
     "        ok(t.includes('rl-zero-v'), 'зеро — вертикальная плашка слева');",
     "        ok(t.includes('rl-zero-v'), 'зеро — плашка слева, подпись без поворота (b495)');"),
]

TAG_OLD, TAG_NEW = 'nxmob238', 'nxmob239'


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
