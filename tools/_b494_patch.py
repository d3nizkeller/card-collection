#!/usr/bin/env python3
# b494: кошелёк стола и шапка — баланс буквами («1k», «110k»), как весь сайт.
# Просьба владельца со скрином пилюли «Кошелёк стола» (точный баланс 110 307):
# «Сделай suma должна быть 1k в таком формате» — выбран вариант «буквами»:
#  1) #rl-balance в rlSync() пишется через fmtCoins вместо nxCoinsExact:
#     1000 -> «1k», 110307 -> «110k»; до 1000 монет — как есть;
#  2) точная надбавка шапки в лобби рулетки убрана: updateCoinDisplay() всегда
#     пишет fmtCoins — шапка и кошелёк показывают одну сумму в одном формате;
#  3) мёртвый код удалён: nxCoinsExact(), rlExactHdr(), rlLobbyOpen();
#  4) движение баланса по-прежнему видно: живой «+900 / −25» (rlFlash) и толчок
#     пилюли; assertions test-b491/b492/b493 переведены на буквы.
# Якоря применяются один раз; повторный запуск отклоняется (--check для проверки).
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EDITS = [
    # ---------------- assets/app.js: кошелёк стола пишется буквами ----------------
    ('assets/app.js',
     r"""        // ---- b491: кошелёк стола ----
        // fmtCoins() в шапке сайта округляет до букв (1000 -> «1k», 1234567 ->
        // «1.2m»), поэтому ставка 25 и выигрыш 900 выглядели как «баланс не
        // двигается». Здесь баланс показывается ТОЧНО, до монеты.
        function nxCoinsExact(n) {
            n = Math.floor(Number(n) || 0);
            const s = String(Math.abs(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '\u2009');
            return (n < 0 ? '−' : '') + s;
        }
        function rlLobbyOpen() {
            try {
                const lr = document.getElementById('lobby-roulette');
                const tb = document.getElementById('tab-battle');
                return !!(lr && tb && !lr.classList.contains('hidden') && !tb.classList.contains('hidden'));
            } catch (e) { return false; }
        }
        // b492: суммы НА СТОЛЕ (бейджи на клетках, «На столе», «Крутить», кошелёк
        // стола, живой +/−) показываются буквами — fmtCoins: 1000 -> «1k»,
        // 9834496 -> «9.8m». Сырые числа вроде 3690496 не влезали в мини-фишку
        // и читались как каша. Баланс остаётся точным до монеты (b491).
        // в лобби рулетки шапка показывает точную сумму (пока она влезает в пилюлю)
        function rlExactHdr() { return rlLobbyOpen() && (Math.floor(Number(state.coins) || 0) < 1000000); }
        function rlSync() {
            const bal = document.getElementById('rl-balance');
            if (bal) { const t = nxCoinsExact(state.coins); if (bal.textContent !== t) bal.textContent = t; }""",
     r"""        // ---- b491: кошелёк стола ----
        // b494: просьба владельца со скрином пилюли («сумма должна быть 1k»):
        // баланс кошелька стола показывается БУКВАМИ, как все остальные суммы
        // сайта — fmtCoins: 1000 -> «1k», 110307 -> «110k». До 1000 монет сумма
        // пишется как есть, а движение баланса по-прежнему видно по живому
        // «+900 / −25» (rlFlash) и толчку пилюли. Точный формат с пробелами
        // (nxCoinsExact) и точная надбавка шапки (rlExactHdr) убраны.
        // b492: суммы НА СТОЛЕ (бейджи на клетках, «На столе», «Крутить», кошелёк
        // стола, живой +/−) показываются буквами — fmtCoins: 1000 -> «1k»,
        // 9834496 -> «9.8m». Сырые числа вроде 3690496 не влезали в мини-фишку
        // и читались как каша.
        function rlSync() {
            const bal = document.getElementById('rl-balance');
            if (bal) { const t = fmtCoins(state.coins); if (bal.textContent !== t) bal.textContent = t; } // b494: кошелёк буквами"""),
    # ---------------- assets/app.js: шапка всегда буквами ----------------
    ('assets/app.js',
     r"""            // b491: в лобби рулетки шапка показывает баланс ТОЧНО (до монеты):
            // fmtCoins() округляет до букв, и ставка 25 / выигрыш 900 не меняли
            // «1k» — владелец видел это как «баланс не двигается».
            let s = fmtCoins(state.coins);
            try { if (rlExactHdr()) s = nxCoinsExact(state.coins); } catch (e) {}""",
     r"""            // b494: баланс буквами ВЕЗДЕ, включая лобби рулетки (просьба
            // владельца: «сумма должна быть 1k»); кошелёк стола и шапка
            // показывают одну и ту же сумму в одном формате.
            let s = fmtCoins(state.coins);"""),
    # ---------------- tools/test-b491.js: комментарий шапки ----------------
    ('tools/test-b491.js',
     r"""//     недостача — отказ; выигрыш и проигрыш меняют баланс и шапку точно;""",
     r"""//     недостача — отказ; выигрыш и проигрыш меняют баланс и шапку буквами (b494);"""),
    # ---------------- tools/test-b491.js: TS больше не нужен ----------------
    ('tools/test-b491.js',
     r"""const TS = '\u2009'; // тонкий пробел nxCoinsExact
""",
     r""""""),
    # ---------------- tools/test-b491.js: список функций без удалённых ----------------
    ('tools/test-b491.js',
     r"""        ['function nxCoinsExact(', 'function rlLobbyOpen(', 'function rlExactHdr(', 'function rlSync(',""",
     r"""        ['function rlSync(',"""),
    # ---------------- tools/test-b491.js: проверка формата кошелька ----------------
    ('tools/test-b491.js',
     r"""        ok(/if \(rlExactHdr\(\)\) s = nxCoinsExact\(state\.coins\);/.test(app), 'app.js: шапка показывает точный баланс в рулетке');""",
     r"""        ok(!app.includes('function nxCoinsExact(') && !app.includes('function rlExactHdr(') && !app.includes('function rlLobbyOpen('), 'app.js: определений точного формата b491 не осталось (b494)');
        ok(app.includes("const t = fmtCoins(state.coins); if (bal.textContent !== t) bal.textContent = t;"), 'app.js: кошелёк стола пишет баланс буквами (b494)');"""),
    # ---------------- tools/test-b491.js: баланс 1000 -> «1k» ----------------
    ('tools/test-b491.js',
     r"""    eq(ev('return document.getElementById("rl-balance").textContent;'), '1' + TS + '000', 'баланс в кошельке стола точный');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '1' + TS + '000', 'шапка в лобби рулетки тоже точная (не «1k»)');""",
     r"""    eq(ev('return document.getElementById("rl-balance").textContent;'), '1k', 'баланс в кошельке стола буквами (b494)');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '1k', 'шапка в лобби рулетки тоже буквами (b494)');"""),
    # ---------------- tools/test-b491.js: новый баланс после выигрыша ----------------
    ('tools/test-b491.js',
     r"""    eq(ev('return document.getElementById("rl-balance").textContent;'), nx(c0 + 50), 'кошелёк стола показал новый баланс');""",
     r"""    eq(ev('return document.getElementById("rl-balance").textContent;'), ev('return fmtCoins(' + (c0 + 50) + ')'), 'кошелёк стола показал новый баланс буквами (b494)');"""),
    # ---------------- tools/test-b491.js: секция H — буквы везде ----------------
    ('tools/test-b491.js',
     r"""    console.log('\nH. Точный баланс в шапке только в рулетке');
    ev('state.coins = 1234567; updateCoinDisplay();');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '1.2m', 'большие суммы в шапке по-прежнему буквами');
    eq(ev('return document.getElementById("rl-balance").textContent;'), '1' + TS + '234' + TS + '567', 'кошелёк стола точный всегда');
    ev('state.coins = 999999; updateCoinDisplay();');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '999' + TS + '999', 'до миллиона шапка точная');
    ev('document.getElementById("lobby-roulette").classList.add("hidden"); state.coins = 5000; updateCoinDisplay();');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '5k', 'вне лобби рулетки шапка как раньше');
    ev('document.getElementById("lobby-roulette").classList.remove("hidden"); updateCoinDisplay();');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '5' + TS + '000', 'вернулись в рулетку — снова точно');""",
     r"""    console.log('\nH. Баланс буквами везде (b494)');
    ev('state.coins = 1234567; updateCoinDisplay();');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '1.2m', 'большие суммы в шапке по-прежнему буквами');
    eq(ev('return document.getElementById("rl-balance").textContent;'), '1.2m', 'кошелёк стола тоже буквами (b494)');
    ev('state.coins = 999999; updateCoinDisplay();');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '999k', 'до миллиона шапка тоже буквами (b494)');
    ev('document.getElementById("lobby-roulette").classList.add("hidden"); state.coins = 5000; updateCoinDisplay();');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '5k', 'вне лобби рулетки шапка как раньше');
    ev('document.getElementById("lobby-roulette").classList.remove("hidden"); updateCoinDisplay();');
    eq(ev('return document.getElementById("coin-balance").innerText;'), '5k', 'вернулись в рулетку — те же буквы (b494)');"""),
    # ---------------- tools/test-b491.js: хелпер nx больше не нужен ----------------
    ('tools/test-b491.js',
     r"""
function nx(n) {
    n = Math.floor(Number(n) || 0);
    return (n < 0 ? '−' : '') + String(Math.abs(n)).replace(/\B(?=(\d{3})+(?!\d))/g, TS);
}
""",
     r"""
"""),
    # ---------------- tools/test-b492.js: комментарий шапки ----------------
    ('tools/test-b492.js',
     r"""//     лицо фишки — span.rl-chip-val, баланс ПО-ПРЕЖНЕМУ точный (nxCoinsExact);""",
     r"""//     лицо фишки — span.rl-chip-val; b494: баланс буквами, как весь сайт;"""),
    # ---------------- tools/test-b492.js: TS больше не нужен ----------------
    ('tools/test-b492.js',
     r"""const TS = '\u2009'; // тонкий пробел nxCoinsExact
""",
     r""""""),
    # ---------------- tools/test-b492.js: исходники — кошелек буквами ----------------
    ('tools/test-b492.js',
     r"""        // b491 не сломан: баланс точный
        ok(app.includes("const t = nxCoinsExact(state.coins); if (bal.textContent !== t) bal.textContent = t;"), 'app.js: баланс стола по-прежнему точный (b491)');
        ok(/if \(rlExactHdr\(\)\) s = nxCoinsExact\(state\.coins\);/.test(app), 'app.js: шапка по-прежнему точная в лобби (b491)');""",
     r"""        // b494: баланс буквами везде
        ok(app.includes("const t = fmtCoins(state.coins); if (bal.textContent !== t) bal.textContent = t;"), 'app.js: кошелёк стола буквами (b494)');
        ok(!app.includes('function rlExactHdr('), 'app.js: определения точной надбавки шапки b491 не осталось (b494)');"""),
    # ---------------- tools/test-b492.js: баланс 9998400 -> «9.9m» ----------------
    ('tools/test-b492.js',
     r"""    eq(ev('return document.getElementById("rl-balance").textContent;'), '9' + TS + '998' + TS + '400', 'баланс стола ТОЧНЫЙ (b491 жив)');""",
     r"""    eq(ev('return document.getElementById("rl-balance").textContent;'), '9.9m', 'баланс стола буквами (b494)');"""),
    # ---------------- tools/test-b493.js: TS больше не нужен ----------------
    ('tools/test-b493.js',
     r"""const TS = '\u2009'; // тонкий пробел nxCoinsExact
""",
     r""""""),
    # ---------------- tools/test-b493.js: баланс полосы буквами ----------------
    ('tools/test-b493.js',
     r"""    eq(ev('return document.getElementById("rl-balance").textContent;'), '1' + TS + '000', 'точный баланс в строке полосы');""",
     r"""    eq(ev('return document.getElementById("rl-balance").textContent;'), '1k', 'баланс в строке полосы буквами (b494)');"""),
    ('tools/test-b493.js',
     r"""    eq(ev('return document.getElementById("rl-balance").textContent;'), '1' + TS + '000', '«Сброс» вернул баланс в строке');""",
     r"""    eq(ev('return document.getElementById("rl-balance").textContent;'), '1k', '«Сброс» вернул баланс в строке буквами (b494)');"""),
]

TAG_OLD, TAG_NEW = 'nxmob237', 'nxmob238'


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
