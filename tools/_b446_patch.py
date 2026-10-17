#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b446: несколько ВНЕШНИХ ВИДОВ паков на выбор (форма упаковки).

Заявка владельца: «сделай несколько видов внешних видов паков на выбор,
хочу поменять дизайн паков» + скриншот витрины с фольговыми пакетами.

Что уже было и чего не хватало
──────────────────────────────
Цвет фольги (серебро/золото/бронза/чёрный) и перелив (голо/блёстки/металл/…)
выбираются в Студии давно: PACK_COLORS + PACK_SHIMMERS, хранятся в паке
(pack.color / pack.shimmer). Но СИЛУЭТ упаковки был один-единственный:
зубчатый пакет с швами (clip-path на .pack3d-face + .booster-crimp + засечки).

Что добавляет патч
──────────────────
Пять форм упаковки, ортогональных цвету и переливу (любой цвет работает
с любой формой):

    foil    «Фольга»   текущий вид: зубчатый шов, засечки, линия отрыва
    box     «Бокс»     прямые края, скругление 10px, матовая крышка-полоса
    ticket  «Билет»    скругление 6px, перфорированные швы, пунктир отрыва
    neon    «Неон»     тёмная плита, светящийся контур цветом рамки пака
    retro   «Ретро»    картон: сепия, двойная рамка, угловой штамп ★

Выбор в двух местах Студии:
    · «Форма упаковки»       — для редактируемого пака (хранится в pack.skin
                               и уезжает игрокам вместе с каталогом комнаты,
                               как и цвет);
    · «Форма по умолчанию»   — для всех паков без своего skin (localStorage
                               nx_pack_skin, на этом устройстве).
packSkinId(p) = pack.skin → nx_pack_skin → 'foil', поэтому старые сохранения
и чужие комнаты без поля skin выглядят ровно как раньше.

Реализация — только CSS-класс pk-* на грани пака (.pack3d-face/.booster):
внутренности (foil/wrinkle/crimp/notch/…) те же, скин их переопределяет.
3D-вскрытие не тронуто: там продолжает работать цвет фольги и перелив.

Тег сборки nxmob175 -> nxmob176 (index.html ?v=, sw.js VERSION, build.py
BUILD_TAG) — иначе sw.js с cache-first для /assets/ отдаст старый app.js.

Проверка/применение:
    python3 tools/_b446_patch.py --check
    python3 tools/_b446_patch.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = []

# ── 1. Справочник форм и выбор ───────────────────────────────────────────────
PAIRS.append(('app.js: справочник PACK_SKINS и выбор формы', """
        // ===== b13: внешний вид пака в Студии (цвет фольги + перелив) =====
""", """
        // ===== b446: ФОРМА УПАКОВКИ — отдельно от цвета фольги и перелива =====
        // Любая форма работает с любым цветом: скин меняет только внешность
        // (силуэт, швы, засечки, блеск), палитра ложится поверх.
        const PACK_SKINS = {
            foil: { name: 'Фольга', hint: 'Запаянный пакет: зубчатый шов, боковые засечки, линия отрыва' },
            box: { name: 'Бокс', hint: 'Прямые края и матовая крышка-полоса, как у бустер-бокса' },
            ticket: { name: 'Билет', hint: 'Скруглённый конверт с перфорацией и пунктирной линией отрыва' },
            neon: { name: 'Неон', hint: 'Тёмная плита со светящимся контуром в цвете рамки пака' },
            retro: { name: 'Ретро', hint: 'Картон: приглушённые тона, двойная рамка, угловой штамп' }
        };
        function nxPackSkinDefault() {
            try { const v = LS.getItem('nx_pack_skin') || ''; return PACK_SKINS[v] ? v : 'foil'; } catch (e) { return 'foil'; }
        }
        function packSkinId(p) {
            if (p && PACK_SKINS[p.skin]) return p.skin;   // своя форма пака
            return nxPackSkinDefault();                    // иначе общая
        }
        function pkSkinCls(p) { return 'pk-' + packSkinId(p); }
        // выбор формы для редактируемого пака (кнопки в Студии)
        function pickPackSkin(k) {
            if (!PACK_SKINS[k]) return;
            packFormSkin = k;
            try { renderPackFormPickers(); } catch (e) {}
            try { renderPackPreview(); } catch (e) {}
        }
        // общая форма для всех паков без своего skin
        function nxSetPackSkinDefault(k) {
            if (!PACK_SKINS[k]) return;
            try { LS.setItem('nx_pack_skin', k); } catch (e) {}
            try { refreshVisibleTabs(); } catch (e) {}
            try { renderPackPreview(); } catch (e) {}
            try { showToast('Форма паков по умолчанию: ' + PACK_SKINS[k].name, 'success'); } catch (e) {}
        }
        try { window.pickPackSkin = pickPackSkin; window.nxSetPackSkinDefault = nxSetPackSkinDefault; } catch (e) {}

        // ===== b13: внешний вид пака в Студии (цвет фольги + перелив) =====
"""))

PAIRS.append(('app.js: переменная формы в форме пака', """
        let packFormShimmer = 'holo';
""", """
        let packFormShimmer = 'holo';
        let packFormSkin = 'foil'; // b446: форма упаковки редактируемого пака
"""))

# ── 2. Класс скина на гранях пака ────────────────────────────────────────────
PAIRS.append(('app.js: класс формы на передней грани витрины', """
                            <div class="pack3d-face pack3d-front booster">
""", """
                            <div class="pack3d-face pack3d-front booster ${pkSkinCls(pack)}">
"""))

PAIRS.append(('app.js: класс формы на задней грани', """
                            <div class="pack3d-face pack3d-back">
""", """
                            <div class="pack3d-face pack3d-back ${pkSkinCls(pack)}">
"""))

PAIRS.append(('app.js: превью в Студии учитывает форму', """
            const p = { color: packFormColor, shimmer: packFormShimmer };
""", """
            const p = { color: packFormColor, shimmer: packFormShimmer, skin: packFormSkin }; // b446
"""))

PAIRS.append(('app.js: класс формы на превью в Студии', """
                <div class="pack3d-face pack3d-front booster" style="position:absolute;inset:0;${packCssVars(p)}">
""", """
                <div class="pack3d-face pack3d-front booster ${pkSkinCls(p)}" style="position:absolute;inset:0;${packCssVars(p)}">
"""))

# ── 3. Пикеры в Студии ───────────────────────────────────────────────────────
PAIRS.append(('app.js: пикер форм в renderPackFormPickers', """
            const sp = document.getElementById('pack-shimmer-picker');
""", """
            // b446: форма упаковки — свой ряд кнопок + ряд «по умолчанию»
            const kp = document.getElementById('pack-skin-picker');
            if (kp) {
                kp.innerHTML = Object.keys(PACK_SKINS).map(k => {
                    const sk = PACK_SKINS[k];
                    const on = k === packFormSkin;
                    return `<button type="button" onclick="pickPackSkin('${k}')" title="${sk.hint}" class="rounded-lg border p-1 transition text-center ${on ? 'border-violet-400 bg-violet-500/10' : 'border-slate-700 bg-slate-950 hover:border-slate-500'}">
                        <span class="block h-6 pk-mini pk-mini-${k}"></span>
                        <span class="block text-[9px] leading-tight mt-0.5 font-semibold truncate ${on ? 'text-violet-300' : 'text-slate-400'}">${sk.name}</span>
                    </button>`;
                }).join('');
            }
            const dp = document.getElementById('pack-skin-default');
            if (dp) {
                const cur = nxPackSkinDefault();
                dp.innerHTML = Object.keys(PACK_SKINS).map(k => {
                    const on = k === cur;
                    return `<button type="button" onclick="nxSetPackSkinDefault('${k}')" title="${PACK_SKINS[k].hint}" class="rounded-lg border px-1.5 py-1 text-[9px] font-semibold transition ${on ? 'border-emerald-400 text-emerald-300 bg-emerald-500/10' : 'border-slate-700 text-slate-400 bg-slate-950 hover:border-slate-500'}">${PACK_SKINS[k].name}</button>`;
                }).join('');
            }
            const sp = document.getElementById('pack-shimmer-picker');
"""))

PAIRS.append(('app.js: подпись стиля показывает и форму', """
            if (nm) nm.innerText = `${PACK_COLORS[packFormColor].name} • ${PACK_SHIMMERS[packFormShimmer].name}`;
""", """
            if (nm) nm.innerText = `${PACK_COLORS[packFormColor].name} • ${PACK_SHIMMERS[packFormShimmer].name} • ${PACK_SKINS[packFormSkin].name}`; // b446
"""))

# ── 4. Сохранение ────────────────────────────────────────────────────────────
PAIRS.append(('app.js: skin читается из формы при сохранении', """
            const shimmer = PACK_SHIMMERS[packFormShimmer] ? packFormShimmer : 'holo';
""", """
            const shimmer = PACK_SHIMMERS[packFormShimmer] ? packFormShimmer : 'holo';
            const skin = PACK_SKINS[packFormSkin] ? packFormSkin : 'foil'; // b446
"""))

PAIRS.append(('app.js: skin пишется в редактируемый пак', """
                    pack.color = color;
                    pack.shimmer = shimmer;
""", """
                    pack.color = color;
                    pack.shimmer = shimmer;
                    pack.skin = skin; // b446: форма упаковки (уезжает в каталог комнаты)
"""))

PAIRS.append(('app.js: skin в новый пак', """
                    color,
                    shimmer,
""", """
                    color,
                    shimmer,
                    skin,              // b446: форма упаковки
"""))

PAIRS.append(('app.js: форма пака подставляется в редактор', """
            packFormShimmer = PACK_SHIMMERS[pack.shimmer] ? pack.shimmer : 'holo';
""", """
            packFormShimmer = PACK_SHIMMERS[pack.shimmer] ? pack.shimmer : 'holo';
            packFormSkin = PACK_SKINS[pack.skin] ? pack.skin : nxPackSkinDefault(); // b446
"""))

# ── 5. index.html: контейнеры пикеров ────────────────────────────────────────
PAIRS.append(('index.html: ряды «Форма упаковки» и «по умолчанию»', """
                        <div id="pack-color-picker" class="grid grid-cols-4 gap-1 max-w-sm"><!-- b272: компакт --><!-- свотчи цветов --></div>
""", """
                        <div id="pack-color-picker" class="grid grid-cols-4 gap-1 max-w-sm"><!-- b272: компакт --><!-- свотчи цветов --></div>
                        <!-- b446: форма упаковки — свой ряд превьюшек и ряд «по умолчанию» -->
                        <div class="mt-2 text-[10px] font-bold uppercase tracking-wide text-slate-500">Форма упаковки</div>
                        <div id="pack-skin-picker" class="grid grid-cols-5 gap-1 max-w-sm"><!-- свотчи форм --></div>
                        <div class="mt-2 text-[10px] font-bold uppercase tracking-wide text-slate-500">Форма по умолчанию <span class="normal-case font-normal text-slate-600">(для паков без своей формы)</span></div>
                        <div id="pack-skin-default" class="flex flex-wrap gap-1"><!-- кнопки общей формы --></div>
"""))

# ── 6. CSS пяти форм + мини-превьюшки ────────────────────────────────────────
PAIRS.append(('index.html: CSS форм упаковки', """
    /* b445: чипсы шансов редкости — одна строка без серой полосы скроллбара */
    .nx-odds{ scrollbar-width:none; -ms-overflow-style:none; }
    .nx-odds::-webkit-scrollbar{ display:none; }
""", """
    /* b445: чипсы шансов редкости — одна строка без серой полосы скроллбара */
    .nx-odds{ scrollbar-width:none; -ms-overflow-style:none; }
    .nx-odds::-webkit-scrollbar{ display:none; }

    /* ===== b446: ФОРМЫ УПАКОВКИ =====
       Класс pk-* стоит на грани пака (.pack3d-face/.booster). Меняется только
       внешность: силуэт (clip-path), швы, засечки, блеск. Цвет фольги (--pk-foil)
       и перелив (--pk-holo/--pk-spark) продолжают работать с любой формой.
       specificity .booster.pk-* (0,2,0) выше, чем у .pack3d-face (0,1,0),
       поэтому переопределения выигрывают без !important. */
    .pk-foil{ }

    /* Бокс: прямые края, крышка-полоса вместо зубчатого шва */
    .pk-box{ clip-path:none; border-radius:10px;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,.14), inset 0 12px 26px rgba(255,255,255,.10), inset 0 -16px 28px rgba(0,0,0,.36); }
    .pk-box .booster-crimp{ height:9%; opacity:.92; border:0; box-shadow:none;
        background: linear-gradient(180deg, rgba(0,0,0,.38), rgba(0,0,0,.10) 62%, rgba(255,255,255,.16)); }
    .pk-box .booster-crimp-bottom{ background: linear-gradient(0deg, rgba(0,0,0,.42), rgba(0,0,0,.12) 62%, rgba(255,255,255,.10)); }
    .pk-box .booster-notch, .pk-box .booster-tearline{ display:none; }
    .pk-box .booster-wrinkle{ opacity:.35; }

    /* Билет: скруглённый конверт, перфорация швов, пунктирный отрыв */
    .pk-ticket{ clip-path:none; border-radius:6px; }
    .pk-ticket .booster-crimp{ height:10%; opacity:.55; border:0; box-shadow:none;
        background: repeating-linear-gradient(90deg, rgba(255,255,255,.30) 0 5px, transparent 5px 11px),
                    linear-gradient(180deg, rgba(0,0,0,.30), transparent); }
    .pk-ticket .booster-crimp-bottom{ background:
        repeating-linear-gradient(90deg, rgba(255,255,255,.30) 0 5px, transparent 5px 11px),
        linear-gradient(0deg, rgba(0,0,0,.30), transparent); }
    .pk-ticket .booster-notch{ display:none; }
    .pk-ticket .booster-tearline{ height:0; background:none; top:12%; opacity:.95;
        border-top:2px dashed rgba(255,255,255,.55); box-shadow:none; }
    .pk-ticket .booster-wrinkle{ opacity:.25; }

    /* Неон: тёмная плита, контур и швы светятся цветом рамки пака (--pk-frame) */
    .pk-neon{ clip-path:none; border-radius:12px; background:#05070d;
        box-shadow: inset 0 0 0 2px var(--pk-frame, #22d3ee), inset 0 0 24px rgba(34,211,238,.22), 0 0 18px rgba(34,211,238,.30); }
    .pk-neon .booster-foil{ opacity:.24; filter:saturate(1.25) contrast(1.1); }
    .pk-neon .booster-crimp{ height:3px; opacity:1; border:0;
        background: var(--pk-frame, #22d3ee); box-shadow:0 0 10px var(--pk-frame, #22d3ee); }
    .pk-neon .booster-notch, .pk-neon .booster-tearline, .pk-neon .booster-wrinkle,
    .pk-neon .booster-gloss{ display:none; }
    .pk-neon .booster-holo{ opacity:.55; }

    /* Ретро: картон, сепия, двойная рамка, угловой штамп */
    .pk-retro{ clip-path:none; border-radius:4px; }
    .pk-retro .booster-foil{ filter:sepia(.35) saturate(.72) contrast(.95); }
    .pk-retro::before{ content:''; position:absolute; inset:6px; z-index:12; pointer-events:none;
        border:1px solid rgba(255,255,255,.5); outline:1px solid rgba(0,0,0,.35); border-radius:2px; }
    .pk-retro::after{ content:'\\2605'; position:absolute; top:9px; right:9px; z-index:13;
        width:26px; height:26px; border:2px solid rgba(255,255,255,.55); border-radius:50%;
        color:rgba(255,255,255,.7); display:flex; align-items:center; justify-content:center;
        font-size:13px; transform:rotate(-12deg); }
    .pk-retro .booster-crimp{ height:8%; opacity:.8; border:0; box-shadow:none;
        background: repeating-linear-gradient(90deg, rgba(0,0,0,.26) 0 3px, rgba(255,255,255,.16) 3px 6px); }
    .pk-retro .booster-notch{ display:none; }
    .pk-retro .booster-wrinkle{ opacity:.5; }

    /* мини-превьюшки форм в пикере Студии */
    .pk-mini{ border:1px solid rgba(255,255,255,.25);
        background: linear-gradient(135deg,#eef1f7 0%,#9aa2b1 55%,#c7ccd8 100%); }
    .pk-mini-foil{ clip-path: polygon(0 12%, 12% 0, 25% 12%, 38% 0, 50% 12%, 63% 0, 75% 12%, 88% 0, 100% 12%, 100% 88%, 88% 100%, 75% 88%, 63% 100%, 50% 88%, 38% 100%, 25% 88%, 12% 100%, 0 88%); }
    .pk-mini-box{ border-radius:3px; box-shadow: inset 0 4px 0 rgba(0,0,0,.35), inset 0 0 0 1px rgba(255,255,255,.3); }
    .pk-mini-ticket{ border-radius:2px;
        background: linear-gradient(135deg,#eef1f7 0%,#9aa2b1 55%,#c7ccd8 100%),
                    repeating-linear-gradient(90deg, rgba(0,0,0,.5) 0 2px, transparent 2px 5px);
        background-blend-mode: multiply; border-style:dashed; }
    .pk-mini-neon{ background:#05070d; border-color:#22d3ee; box-shadow:0 0 6px rgba(34,211,238,.8), inset 0 0 4px rgba(34,211,238,.6); border-radius:3px; }
    .pk-mini-retro{ background:linear-gradient(135deg,#d9c39a 0%,#a5825a 55%,#c9ab7d 100%); border-radius:1px;
        box-shadow: inset 0 0 0 2px rgba(255,255,255,.45); }
"""))

TAG_OLD = 'nxmob175'
TAG_NEW = 'nxmob176'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']


def read(rel):
    with open(os.path.join(ROOT, rel), 'r', encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
        f.write(txt)


def apply():
    files = {}
    for label, old, new in PAIRS:
        rel = 'index.html' if label.startswith('index.html') else 'assets/app.js'
        if rel not in files:
            files[rel] = read(rel)
        txt = files[rel]
        if new.strip() in txt:
            continue  # уже применено
        assert old.strip() in txt, 'b446: не найден якорь: %s' % label
        assert txt.count(old.strip()) == 1, 'b446: якорь не уникален: %s (%d)' % (label, txt.count(old.strip()))
        files[rel] = txt.replace(old.strip(), new.strip(), 1)
    for rel, txt in files.items():
        write(rel, txt)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b446: не найден тег %s в %s (сначала _b442.._b445)' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b446: применено')


def check():
    problems = []
    for label, old, new in PAIRS:
        rel = 'index.html' if label.startswith('index.html') else 'assets/app.js'
        txt = read(rel)
        if new.strip() not in txt:
            problems.append('%s: нет нового блока: %s' % (rel, label))
    app = read('assets/app.js')
    for extra in ('const PACK_SKINS = {', 'function packSkinId(p)', 'function pkSkinCls(p)',
                  'function pickPackSkin(k)', 'function nxSetPackSkinDefault(k)',
                  "booster ${pkSkinCls(pack)}", "booster ${pkSkinCls(p)}",
                  'skin: packFormSkin', 'const skin = PACK_SKINS[packFormSkin]',
                  'pack.skin = skin;', 'skin,              // b446',
                  'packFormSkin = PACK_SKINS[pack.skin]', "getElementById('pack-skin-picker')"):
        if extra not in app:
            problems.append('app.js: нет %r' % extra)
    html = read('index.html')
    for extra in ('id="pack-skin-picker"', 'id="pack-skin-default"', '.pk-box{ clip-path:none',
                  '.pk-ticket .booster-tearline', '.pk-neon{ clip-path:none', '.pk-retro::after',
                  '.pk-mini-neon{'):
        if extra not in html:
            problems.append('index.html: нет %r' % extra)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не %s' % (rel, TAG_NEW))
    if problems:
        print('b446 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b446 --check: всё на месте (5 форм упаковки, пикеры в Студии, тег %s)' % TAG_NEW)


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
