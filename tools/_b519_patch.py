#!/usr/bin/env python3
# b519: новая игра во вкладке «Игры» — «Скретч-лото»: моментальная лотерея со
# стиранием фольги (canvas, pointer-events), как билеты Stoloto с референса.
# 4 выигрышных числа + 12 ваших под фольгой; множители ×1…×100; золотая клетка
# JKP (1 из 300) срывает общий джекпот сайта; билет кормит банк (feed/loss).
# Правки: index.html (плитка, стекло, лобби, CSS), assets/app.js (setBattleMode,
# степперы ставки, jackpotRender, модуль b519). Версия nxmob252->nxmob253.
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


BTN = ('<button onclick="setBattleMode(\'scratch\')" id="mode-scratch-btn" class="w-full flex flex-col items-center justify-center gap-1 px-1 py-2 rounded-xl text-[13px] sm:text-[15px] lg:text-[13px] font-bold transition whitespace-nowrap overflow-hidden min-w-0 lg:flex-row lg:gap-1.5 lg:px-2 bg-slate-800 text-slate-300 border border-slate-700" title="Скретч-лото: стирайте фольгу, совпадайте с выигрышными числами, золотая клетка JKP срывает джекпот сайта"><i class="fa-solid fa-eraser mr-0 lg:mr-1.5"></i><span class="block lg:inline w-full lg:w-auto text-center lg:text-left text-[8px] sm:text-[9px] lg:text-xs font-bold leading-none truncate">Скретч</span></button>')

LOBBY = '''                <!-- b519: лобби режима «Скретч»: моментальная лотерея со стиранием фольги -->
                <div id="lobby-scratch" class="space-y-6 hidden">
                    <div class="bg-gradient-to-r from-slate-900 to-slate-900/60 p-4 sm:p-6 rounded-2xl border border-slate-800">
                        <div class="flex flex-wrap items-start justify-between gap-3">
                            <div class="min-w-0">
                                <h2 class="text-2xl font-black text-white tracking-tight"><i class="fa-solid fa-eraser text-slate-300 mr-2"></i>Скретч-лото</h2>
                                <p class="text-sm text-slate-400 mt-1">Моментальная лотерея как в киоске: купите билет и <b class="text-slate-200">стирайте серебряную фольгу</b> пальцем или мышью. 4 выигрышных числа и 12 ваших: совпало число — приз множителем к ставке (до ×100), золотая клетка <b class="text-amber-300">JKP</b> (1 из 300 билетов) срывает весь джекпот сайта.</p>
                            </div>
                        </div>
                        <div class="flex flex-wrap justify-center gap-x-5 gap-y-3 sm:gap-x-10 mt-4">
                            <div class="flex flex-col items-center gap-1 shrink-0"><span class="text-[9px] sm:text-[10px] uppercase tracking-[.18em] font-black text-slate-500 leading-none">Ставка</span><div class="flex items-center gap-1"><button type="button" onclick="stepBet('scratch',-1)" title="Уменьшить ставку" class="step-btn w-8 h-8 sm:w-9 sm:h-9 flex items-center justify-center shrink-0 text-[11px] font-black"><i class="fa-solid fa-minus"></i></button><input id="scratch-bet-input" inputmode="numeric" maxlength="16" placeholder="Своя ставка" title="Впишите свою сумму ставки и нажмите Enter (примеры: 250, 5k, 1.2m, 3b, 2t, 4q)" class="px-2 py-1.5 rounded-full text-[11px] font-bold text-center bg-slate-800/80 border border-slate-700 text-amber-200 placeholder-slate-500 w-24 sm:w-28 shrink-0 focus:border-amber-400/70 focus:outline-none transition" onkeydown="if(event.key==='Enter')this.blur()" onchange="applyCustomBet('scratch', this.value)"><button type="button" onclick="stepBet('scratch',1)" title="Увеличить ставку" class="step-btn w-8 h-8 sm:w-9 sm:h-9 flex items-center justify-center shrink-0 text-[11px] font-black"><i class="fa-solid fa-plus"></i></button></div></div>
                        </div>
                        <div class="flex flex-wrap items-center justify-center gap-2 mt-4">
                            <button id="sc-buy" onclick="scratchBuy()" class="px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-sm font-black transition shadow-lg shadow-amber-950/40"><i class="fa-solid fa-ticket mr-1"></i>Купить билет</button>
                            <button id="sc-erase" onclick="scEraseAll()" class="hidden px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-bold border border-slate-700 transition"><i class="fa-solid fa-eraser mr-1"></i>Стереть всё</button>
                        </div>
                        <div id="sc-ticket" class="sc-ticket mt-4"></div>
                        <p id="sc-result" class="text-xs text-slate-400 mt-3 text-center"></p>
                        <div class="rules-card">
                            <p class="rules-title"><i class="fa-solid fa-book-open mr-1"></i>Как играть</p>
                            <ol class="rules-list">
                                <li>Выберите ставку и нажмите <b>«Купить билет»</b> — ставка списывается, билет приходит закрытый серебряной фольгой.</li>
                                <li><b>Стирайте фольгу</b> пальцем или мышью (или «Стереть всё»): стёрли больше половины клетки — она вскрывается сама.</li>
                                <li>Ваше число совпало с выигрышным — приз множителем к ставке (×1…×100); золотая клетка <b>JKP</b> срывает весь джекпот сайта.</li>
                                <li>Билет кормит общий банк: взнос со ставки и <b>100%</b> чистого проигрыша; суперприз билета — это и есть джекпот сайта.</li>
                            </ol>
                        </div>
                    </div>
                </div>
'''

CSS = '''
    /* ===== b519: Скретч-лото — оранжевый билет и серебряная фольга ===== */
    #mode-scratch-btn.lq-on{ --lq-tint: rgba(148,163,184,.30); --lq-text:#e2e8f0; border-color: rgba(203,213,225,.5); }
    .sc-ticket{
        max-width:420px; margin:0 auto; border-radius:18px; padding:14px 14px 16px;
        background:linear-gradient(180deg,#ff8a00 0%,#f45800 55%,#e34c00 100%);
        box-shadow:0 14px 34px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.35);
        color:#fff;
    }
    .sc-empty{ padding:40px 10px; text-align:center; font-weight:800; color:rgba(255,255,255,.75); border:2px dashed rgba(255,255,255,.4); border-radius:14px; }
    .sc-head{ display:flex; justify-content:space-between; align-items:center; gap:8px; }
    .sc-brand{ font-weight:900; letter-spacing:.12em; font-size:13px; }
    .sc-price{ background:#fff; color:#e34c00; font-weight:900; font-size:12px; padding:3px 10px; border-radius:8px; }
    .sc-super{ margin-top:10px; text-align:center; font-weight:900; letter-spacing:.2em; font-size:11px; color:#ffe8d1; }
    .sc-super-val{ text-align:center; font-size:26px; font-weight:900; text-shadow:0 2px 0 rgba(0,0,0,.25); }
    .sc-cap{ margin:12px 0 6px; text-align:center; font-size:10px; font-weight:900; letter-spacing:.18em; color:#ffe8d1; }
    .sc-winrow{ display:flex; justify-content:center; gap:8px; }
    .sc-wslot{ position:relative; width:52px; height:52px; }
    .sc-wslot .sc-face{
        position:absolute; inset:0; border-radius:50%;
        background:radial-gradient(circle at 35% 30%, #ffffff, #d9d9de 70%, #b9b9bf);
        color:#20242c; display:flex; align-items:center; justify-content:center;
    }
    .sc-ball-n{ font-weight:900; font-size:18px; }
    .sc-grid{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; }
    .sc-cell{ position:relative; aspect-ratio:1; border-radius:12px; }
    .sc-cell .sc-face{
        position:absolute; inset:0; border-radius:12px;
        background:linear-gradient(180deg,#2b2417,#171208);
        border:1px solid rgba(255,214,150,.35);
        display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px;
    }
    .sc-cell.jkp .sc-face{ background:linear-gradient(180deg,#4a3208,#241a04); border-color:#fcd34d; box-shadow:0 0 14px rgba(252,211,77,.5); }
    .sc-sym{ font-size:18px; color:#fcd34d; }
    .sc-sym.gold{ color:#fde68a; filter:drop-shadow(0 0 6px rgba(253,224,71,.8)); }
    .sc-num{ font-weight:900; font-size:15px; color:#fff; }
    .sc-prize{ font-size:10px; font-weight:800; color:#9ca3af; }
    .sc-prize.win{ color:#4ade80; }
    .sc-prize.gold{ color:#fde68a; }
    .sc-foil{ position:absolute; inset:0; width:100%; height:100%; border-radius:inherit; cursor:pointer; touch-action:none; }
    .sc-wslot .sc-foil{ border-radius:50%; }
    @keyframes sc-pop{ 0%{ transform:scale(.7); } 70%{ transform:scale(1.08); } 100%{ transform:scale(1); } }
    .sc-wslot.rev .sc-face, .sc-cell.rev .sc-face{ animation:sc-pop .3s ease; }
    @media (max-width:480px){
        .sc-ticket{ padding:10px 10px 12px; }
        .sc-wslot{ width:44px; height:44px; }
        .sc-ball-n{ font-size:15px; }
        .sc-sym{ font-size:15px; }
        .sc-num{ font-size:13px; }
        .sc-prize{ font-size:9px; }
    }
    @media (prefers-reduced-motion:reduce){
        .sc-wslot.rev .sc-face, .sc-cell.rev .sc-face{ animation:none; }
    }
'''

EDITS = [
    # ---------------- index.html: плитка режима ----------------
    ('index.html', 'truncate">Лото</span></button>', 'truncate">Лото</span></button>\n                ' + BTN),
    # ---------------- index.html: стекло (4 списка) ----------------
    ('index.html', '#mode-roulette-btn, #mode-loto-btn, #miner-btn{', '#mode-roulette-btn, #mode-loto-btn, #mode-scratch-btn, #miner-btn{'),
    ('index.html', '#mode-roulette-btn::before, #mode-loto-btn::before, #miner-btn::before{', '#mode-roulette-btn::before, #mode-loto-btn::before, #mode-scratch-btn::before, #miner-btn::before{'),
    ('index.html', '#mode-roulette-btn:hover, #mode-loto-btn:hover, #miner-btn:hover{', '#mode-roulette-btn:hover, #mode-loto-btn:hover, #mode-scratch-btn:hover, #miner-btn:hover{'),
    ('index.html', '#mode-roulette-btn:active, #mode-loto-btn:active, #miner-btn:active{', '#mode-roulette-btn:active, #mode-loto-btn:active, #mode-scratch-btn:active, #miner-btn:active{'),
    # ---------------- index.html: 12 плиток в ряд от sm ----------------
    ('assets/app.css', '@media (min-width:640px){.nx-modes{grid-template-columns:repeat(11,minmax(0,1fr))}}', '@media (min-width:640px){.nx-modes{grid-template-columns:repeat(12,minmax(0,1fr))}}'),
    # ---------------- index.html: лобби перед лобби лото ----------------
    ('index.html', '                <!-- b500: лобби режима «Лото»', LOBBY + '                <!-- b500: лобби режима «Лото»'),
    # ---------------- index.html: CSS перед закрытием style ----------------
    ('index.html', '    .loto-bcell.n90.on{ background:linear-gradient(180deg,#fde68a,#f59e0b); color:#78350f; box-shadow:0 0 12px rgba(253,224,71,.8); }\n',
     '    .loto-bcell.n90.on{ background:linear-gradient(180deg,#fde68a,#f59e0b); color:#78350f; box-shadow:0 0 12px rgba(253,224,71,.8); }\n' + CSS),
    # ---------------- assets/app.js: setBattleMode ----------------
    ('assets/app.js',
     "            const llto = document.getElementById('lobby-loto'); // b500\n            if (llto) llto.classList.toggle('hidden', m !== 'loto');",
     "            const llto = document.getElementById('lobby-loto'); // b500\n            if (llto) llto.classList.toggle('hidden', m !== 'loto');\n            const lsc = document.getElementById('lobby-scratch'); // b519\n            if (lsc) lsc.classList.toggle('hidden', m !== 'scratch');"),
    ('assets/app.js',
     "            setModeBtn('mode-loto-btn', m === 'loto', 'lq-on'); // b500",
     "            setModeBtn('mode-loto-btn', m === 'loto', 'lq-on'); // b500\n            setModeBtn('mode-scratch-btn', m === 'scratch', 'lq-on'); // b519"),
    ('assets/app.js',
     "            if (m === 'loto') { renderLoto(); try { jackpotRender(); } catch (e) {} } // b500/b517",
     "            if (m === 'loto') { renderLoto(); try { jackpotRender(); } catch (e) {} } // b500/b517\n            if (m === 'scratch') { renderScratch(); try { jackpotRender(); } catch (e) {} } // b519"),
    # ---------------- assets/app.js: ставка скретча в степперах (по 2 места) ----------------
    ('assets/app.js',
     "const cur = game === 'slots' ? slots.bet : game === 'grid' ? grid.bet : game === 'lines' ? lines.bet : game === 'wheel' ? wheel.bet : game === 'durak' ? durakBet : game === 'loto' ? loto.bet : mines.bet; // b500",
     "const cur = game === 'slots' ? slots.bet : game === 'grid' ? grid.bet : game === 'lines' ? lines.bet : game === 'wheel' ? wheel.bet : game === 'durak' ? durakBet : game === 'loto' ? loto.bet : game === 'scratch' ? scratch.bet : mines.bet; // b500/b519",
     2),
    ('assets/app.js',
     "            else if (game === 'loto') lotoSetBet(b); // b500",
     "            else if (game === 'loto') lotoSetBet(b); // b500\n            else if (game === 'scratch') scratchSetBet(b); // b519",
     2),
    # ---------------- assets/app.js: суперприз билета = банк сайта ----------------
    ('assets/app.js',
     "            nxSetHtml(document.getElementById('loto-jp-top-list'), html);",
     "            nxSetHtml(document.getElementById('loto-jp-top-list'), html);\n            const sjv = document.getElementById('sc-jp'); // b519: суперприз скретча = общий банк\n            if (sjv) sjv.textContent = fmtCoins(pool);"),
    # ---------------- assets/app.js: модуль игры ----------------
    ('assets/app.js', '        window.onload = function() {', rd('_b519_scratch_module.js') + '        window.onload = function() {'),
]

TAG_OLD, TAG_NEW = 'nxmob252', 'nxmob253'


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
            problems.append('%s: якорь встречается %d раз (ждём %d)' % (p, s.count(old), want))
        if new and new.strip() and new in s:
            problems.append('%s: патч УЖЕ применён: %s…' % (p, new[:60]))
    idx = read('index.html')
    if idx.count(TAG_OLD) != 9:
        problems.append('index.html: тега %s найдено %d (ждём 9)' % (TAG_OLD, idx.count(TAG_OLD)))
    if problems:
        for x in problems:
            print('PROBLEM:', x)
        return 1
    if check:
        print('OK: все якоря на месте, патч b519 применим')
        return 0
    for ed in EDITS:
        p, old, new = ed[0], ed[1], ed[2]
        want = ed[3] if len(ed) > 3 else 1
        s = read(p)
        s = s.replace(old, new) if want != 1 else s.replace(old, new, 1)
        write(p, s)
    for p in ('index.html', 'sw.js', 'tools/build.py'):
        s = read(p)
        s = s.replace(TAG_OLD, TAG_NEW)
        write(p, s)
    print('b519: применено правок:', len(EDITS), '+ версия', TAG_NEW)
    return 0


if __name__ == '__main__':
    sys.exit(main())
