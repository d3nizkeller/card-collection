#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b448: выбор зубчиков (формы кромки запайки) — независимо от формы и цвета пака.

Заявка владельца: «а выбор зубчиков».

Раньше кромка была одна: 15 острых зубцов, зашитых в clip-path у .pack3d-face
(assets/app.css) и дублирующихся в PACK_CLIP_POLY для мини-паков (переменная
--packclip). Теперь кромка — четвёртое измерение внешности пака:

    zip    «Зубчики»  15 острых зубцов, глубина 5.2%   (текущий вид, по умолчанию)
    coarse «Крупные»   8 зубцов, глубина 7.5%
    fine   «Мелкие»   26 зубцов, глубина 3.4%
    trap   «Трапеция» 10 трапециевидных зубцов (площадка вместо острия)
    flat   «Прямые»   ровный край без зубцов

Цепочка выбора, как у форм b446: pack.crimp → localStorage nx_pack_crimp → 'zip'.
Полигон считается в JS (packCrimpPoly) и приходит на грань пака переменной
--pk-clip через packCssVars(); в CSS: .pack3d-face{clip-path:var(--pk-clip, <полигон
по умолчанию>)}, поэтому без настройки всё выглядит ровно как раньше. Полигон по
умолчанию также уходит в --packclip на <html> — мини-паки в Минах следуют за
общим выбором.

Выбор в трёх местах:
    · ряд «Зубчики» в шапке подраздела Студии «Паки» (рядом с «Вид паков», b447);
    · ряд «Зубчики упаковки» в редакторе пака (пишется в pack.crimp и уезжает
      игрокам с каталогом комнаты);
    · ряд «Зубчики по умолчанию» там же (localStorage, для паков без своего crimp).

Формы box/ticket/neon/retro из b446 кромку не показывают (у них свой силуэт) —
зубчики имеют смысл только для «Фольги», что и отражено в подсказках.

Тег сборки nxmob177 -> nxmob178.

Проверка/применение:
    python3 tools/_b448_patch.py --check
    python3 tools/_b448_patch.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Полигон кромки по умолчанию — побайтово тот же, что в assets/app.css
# у .pack3d-face (15 зубцов, глубина 5.2%). Лежит константой, чтобы патч
# оставался самодостаточным одним файлом.
POLY_DEFAULT = 'polygon(0.00% 5.2%, 3.57% 0.0%, 7.14% 5.2%, 10.71% 0.0%, 14.29% 5.2%, 17.86% 0.0%, 21.43% 5.2%, 25.00% 0.0%, 28.57% 5.2%, 32.14% 0.0%, 35.71% 5.2%, 39.29% 0.0%, 42.86% 5.2%, 46.43% 0.0%, 50.00% 5.2%, 53.57% 0.0%, 57.14% 5.2%, 60.71% 0.0%, 64.29% 5.2%, 67.86% 0.0%, 71.43% 5.2%, 75.00% 0.0%, 78.57% 5.2%, 82.14% 0.0%, 85.71% 5.2%, 89.29% 0.0%, 92.86% 5.2%, 96.43% 0.0%, 100.00% 5.2%, 100.00% 94.8%, 96.43% 100.0%, 92.86% 94.8%, 89.29% 100.0%, 85.71% 94.8%, 82.14% 100.0%, 78.57% 94.8%, 75.00% 100.0%, 71.43% 94.8%, 67.86% 100.0%, 64.29% 94.8%, 60.71% 100.0%, 57.14% 94.8%, 53.57% 100.0%, 50.00% 94.8%, 46.43% 100.0%, 42.86% 94.8%, 39.29% 100.0%, 35.71% 94.8%, 32.14% 100.0%, 28.57% 94.8%, 25.00% 100.0%, 21.43% 94.8%, 17.86% 100.0%, 14.29% 94.8%, 10.71% 100.0%, 7.14% 94.8%, 3.57% 100.0%, 0.00% 94.8%)'

PAIRS = []

# ── 1. Справочник кромок и генератор полигона ───────────────────────────────
PAIRS.append(('app.js: PACK_CRIMPS и генератор полигона', """
        // b80: силуэт зигзаг-пака доступен в CSS (мини-паки в Минах)
        try { document.documentElement.style.setProperty('--packclip', PACK_CLIP_POLY); } catch (e) {}
""", """
        // b80: силуэт зигзаг-пака доступен в CSS (мини-паки в Минах)
        // ===== b448: ФОРМА КРОМКИ (зубчики запайки) =====
        // teeth — число зубцов на кромку, depth — глубина в % высоты, trap —
        // площадка вместо острия (трапеция). flat = teeth 0.
        const PACK_CRIMPS = {
            zip: { name: 'Зубчики', teeth: 15, depth: 5.2, hint: 'Классическая запайка: 15 острых зубцов сверху и снизу' },
            coarse: { name: 'Крупные', teeth: 8, depth: 7.5, hint: 'Крупный редкий зуб — брутальная запайка' },
            fine: { name: 'Мелкие', teeth: 26, depth: 3.4, hint: 'Мелкая частая пила, как у фольги шоколадки' },
            trap: { name: 'Трапеция', teeth: 10, depth: 6.0, trap: true, hint: 'Трапециевидные зубцы с площадкой вместо острия' },
            flat: { name: 'Прямые', teeth: 0, depth: 0, hint: 'Ровный край без зубцов' }
        };
        function packCrimpPoly(teeth, depth, trap) {
            const t = Math.max(0, Math.floor(Number(teeth) || 0));
            const d = Math.min(12, Math.max(0, Number(depth) || 0));
            if (!t || !d) return 'polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)';
            const pts = [];
            const step = 100 / t;
            const put = (x, y) => pts.push(Math.max(0, Math.min(100, x)).toFixed(2) + '% ' + Math.max(0, Math.min(100, y)).toFixed(2) + '%');
            for (let i = 0; i < t; i++) {
                if (trap) { put(i * step, d); put(i * step + step * 0.3, 0); put(i * step + step * 0.7, 0); }
                else { put(i * step, d); put(i * step + step / 2, 0); }
            }
            put(100, d);
            put(100, 100 - d);
            for (let i = t - 1; i >= 0; i--) {
                if (trap) { put(i * step + step * 0.7, 100); put(i * step + step * 0.3, 100); put(i * step, 100 - d); }
                else { put(i * step + step / 2, 100); put(i * step, 100 - d); }
            }
            put(0, 100 - d);
            return 'polygon(' + pts.join(',') + ')';
        }
        function nxCrimpDefault() {
            try { const v = LS.getItem('nx_pack_crimp') || ''; return PACK_CRIMPS[v] ? v : 'zip'; } catch (e) { return 'zip'; }
        }
        function packCrimpId(p) {
            if (p && PACK_CRIMPS[p.crimp]) return p.crimp;
            return nxCrimpDefault();
        }
        function packCrimpPolyFor(p) {
            const c = PACK_CRIMPS[packCrimpId(p)] || PACK_CRIMPS.zip;
            return packCrimpPoly(c.teeth, c.depth, c.trap);
        }
        function nxCrimpApplyRoot() {
            // мини-паки (Мины) берут силуэт из --packclip на <html>.
            // При zip оставляем прежний PACK_CLIP_POLY — мини-паки не меняются.
            try {
                document.documentElement.style.setProperty('--packclip',
                    nxCrimpDefault() === 'zip' ? PACK_CLIP_POLY : packCrimpPolyFor(null));
            } catch (e) {}
        }
        function pickPackCrimp(k) {           // своя кромка редактируемого пака
            if (!PACK_CRIMPS[k]) return;
            packFormCrimp = k;
            try { renderPackFormPickers(); } catch (e) {}
            try { renderPackStylePreview(); } catch (e) {}
        }
        function nxSetCrimpDefault(k) {       // общая кромка для паков без своей
            if (!PACK_CRIMPS[k]) return;
            try { LS.setItem('nx_pack_crimp', k); } catch (e) {}
            nxCrimpApplyRoot();
            try { refreshVisibleTabs(); } catch (e) {}
            try { renderPackStylePreview(); } catch (e) {}
            try { showToast('Зубчики по умолчанию: ' + PACK_CRIMPS[k].name, 'success'); } catch (e) {}
        }
        try { window.pickPackCrimp = pickPackCrimp; window.nxSetCrimpDefault = nxSetCrimpDefault; } catch (e) {}
        nxCrimpApplyRoot(); // b448: мини-паки следуют за общим выбором сразу
"""))

# ── 2. --pk-clip в packCssVars ──────────────────────────────────────────────
PAIRS.append(('app.js: полигон кромки уходит в --pk-clip', """
                '--pk-spark:' + spark + ';--pk-spark-op:' + sparkOp + ';';
""", """
                '--pk-spark:' + spark + ';--pk-spark-op:' + sparkOp + ';' +
                // b448: силуэт кромки приезжает на грань переменной --pk-clip.
                // Для «Зубчиков» (zip) переменной НЕТ вовсе: грань остаётся с
                // родным clip-path из assets/app.css — побайтово как раньше.
                // (В app.css у грани 14 зубцов, а у PACK_CLIP_POLY для мини-паков
                // 15 — историческая рассинхронизация, трогать её не будем.)
                (packCrimpId(pack) === 'zip' ? '' : '--pk-clip:' + packCrimpPolyFor(pack) + ';');
"""))

# ── 3. CSS: грань берёт клип из переменной ───────────────────────────────────
PAIRS.append(('index.html: clip-path грани из --pk-clip', """
    /* ===== b446: ФОРМЫ УПАКОВКИ =====""", """
    /* ===== b448: КРОМКА (зубчики) =====
       Полигон приходит переменной --pk-clip из packCssVars(); без неё — прежние
       15 зубцов, побайтово как в assets/app.css. Правило стоит ДО форм b446,
       поэтому .pk-box/.pk-ticket/.pk-neon/.pk-retro со своим clip-path
       перебивают его при равной специфичности (ниже по каскаду). */
    .pack3d-face{ clip-path: var(--pk-clip, POLY_DEFAULT); }
    /* мини-превьюшки кромок в пикерах Студии */
    .pk-mini-crimp{ border:1px solid rgba(255,255,255,.25);
        background:linear-gradient(135deg,#eef1f7 0%,#9aa2b1 55%,#c7ccd8 100%); }
    .pk-mini-crimp-zip{ clip-path:polygon(0 14%,12% 0,25% 14%,37% 0,50% 14%,63% 0,75% 14%,88% 0,100% 14%,100% 86%,88% 100%,75% 86%,63% 100%,50% 86%,37% 100%,25% 86%,12% 100%,0 86%); }
    .pk-mini-crimp-coarse{ clip-path:polygon(0 22%,25% 0,50% 22%,75% 0,100% 22%,100% 78%,75% 100%,50% 78%,25% 100%,0 78%); }
    .pk-mini-crimp-fine{ clip-path:polygon(0 10%,8% 0,16% 10%,25% 0,33% 10%,41% 0,50% 10%,58% 0,66% 10%,75% 0,83% 10%,91% 0,100% 10%,100% 90%,91% 100%,83% 90%,75% 100%,66% 90%,58% 100%,50% 90%,41% 100%,33% 90%,25% 100%,16% 90%,8% 100%,0 90%); }
    .pk-mini-crimp-trap{ clip-path:polygon(0 18%,10% 0,20% 0,30% 18%,40% 0,50% 0,60% 18%,70% 0,80% 0,90% 18%,100% 0,100% 100%,0 100%); }
    .pk-mini-crimp-flat{ clip-path:none; border-radius:2px; }

    /* ===== b446: ФОРМЫ УПАКОВКИ =====""".replace('POLY_DEFAULT', POLY_DEFAULT)))

# ── 4. Студия: переменная формы кромки и пикеры ──────────────────────────────
PAIRS.append(('app.js: packFormCrimp', """
        let packFormSkin = 'foil'; // b446: форма упаковки редактируемого пака
""", """
        let packFormSkin = 'foil'; // b446: форма упаковки редактируемого пака
        let packFormCrimp = 'zip'; // b448: кромка (зубчики) редактируемого пака
"""))

PAIRS.append(('app.js: пикеры кромок в редакторе и в шапке секции', """
            const kp = document.getElementById('pack-skin-picker');
""", """
            // b448: зубчики — свой ряд в редакторе и быстрый ряд в шапке секции
            const crimpBtns = (fn) => {
                const cur = fn === 'pack' ? packFormCrimp : nxCrimpDefault();
                return Object.keys(PACK_CRIMPS).map(k => {
                    const c = PACK_CRIMPS[k];
                    const on = k === cur;
                    const click = fn === 'pack' ? ('pickPackCrimp(\\'' + k + '\\')') : ('nxSetCrimpDefault(\\'' + k + '\\')');
                    const hi = fn === 'pack' ? 'border-violet-400 bg-violet-500/10' : 'border-emerald-400 text-emerald-300 bg-emerald-500/10';
                    return `<button type="button" onclick="${click}" title="${c.hint}" class="rounded-lg border p-1 transition text-center ${on ? hi : 'border-slate-700 bg-slate-950 hover:border-slate-500'}">
                        <span class="block h-5 pk-mini-crimp pk-mini-crimp-${k}"></span>
                        <span class="block text-[9px] leading-tight mt-0.5 font-semibold truncate ${on ? (fn === 'pack' ? 'text-violet-300' : 'text-emerald-300') : 'text-slate-400'}">${c.name}</span>
                    </button>`;
                }).join('');
            };
            const crp = document.getElementById('pack-crimp-picker');
            if (crp) crp.innerHTML = crimpBtns('pack');
            const crd = document.getElementById('pack-crimp-default');
            if (crd) crd.innerHTML = crimpBtns('default');
            const crq = document.getElementById('pack-crimp-quick');
            if (crq) crq.innerHTML = crimpBtns('default');
            const kp = document.getElementById('pack-skin-picker');
"""))

PAIRS.append(('app.js: превью и подпись учитывают кромку', """
            const p = { color: packFormColor, shimmer: packFormShimmer, skin: packFormSkin }; // b446
""", """
            const p = { color: packFormColor, shimmer: packFormShimmer, skin: packFormSkin, crimp: packFormCrimp }; // b446+b448
"""))

PAIRS.append(('app.js: подпись стиля показывает и зубчики', """
            if (nm) nm.innerText = `${PACK_COLORS[packFormColor].name} • ${PACK_SHIMMERS[packFormShimmer].name} • ${PACK_SKINS[packFormSkin].name}`; // b446
""", """
            if (nm) nm.innerText = `${PACK_COLORS[packFormColor].name} • ${PACK_SHIMMERS[packFormShimmer].name} • ${PACK_SKINS[packFormSkin].name} • ${PACK_CRIMPS[packFormCrimp].name}`; // b446+b448
"""))

# ── 5. Сохранение и подстановка ─────────────────────────────────────────────
PAIRS.append(('app.js: crimp из формы при сохранении', """
            const skin = PACK_SKINS[packFormSkin] ? packFormSkin : 'foil'; // b446
""", """
            const skin = PACK_SKINS[packFormSkin] ? packFormSkin : 'foil'; // b446
            const crimp = PACK_CRIMPS[packFormCrimp] ? packFormCrimp : 'zip'; // b448
"""))

PAIRS.append(('app.js: crimp в редактируемый пак', """
                    pack.skin = skin; // b446: форма упаковки (уезжает в каталог комнаты)
""", """
                    pack.skin = skin; // b446: форма упаковки (уезжает в каталог комнаты)
                    pack.crimp = crimp; // b448: кромка (зубчики) — тоже в каталог
"""))

PAIRS.append(('app.js: crimp в новый пак', """
                    skin,              // b446: форма упаковки
""", """
                    skin,              // b446: форма упаковки
                    crimp,             // b448: кромка (зубчики)
"""))

PAIRS.append(('app.js: кромка пака подставляется в редактор', """
            packFormSkin = PACK_SKINS[pack.skin] ? pack.skin : nxPackSkinDefault(); // b446
""", """
            packFormSkin = PACK_SKINS[pack.skin] ? pack.skin : nxPackSkinDefault(); // b446
            packFormCrimp = PACK_CRIMPS[pack.crimp] ? pack.crimp : nxCrimpDefault(); // b448
"""))

# ── 6. index.html: контейнеры ───────────────────────────────────────────────
PAIRS.append(('index.html: ряд «Зубчики» в шапке секции Паки', """
                <div id="pack-skin-quick" class="flex flex-wrap gap-1"><!-- кнопки форм --></div>
""", """
                <div id="pack-skin-quick" class="flex flex-wrap gap-1"><!-- кнопки форм --></div>
                <span class="text-[10px] font-bold uppercase tracking-wide text-slate-500 ml-2"><i class="fa-solid fa-scissors text-sky-400 mr-1"></i>Зубчики:</span>
                <div id="pack-crimp-quick" class="flex flex-wrap gap-1"><!-- кнопки кромок --></div>
"""))

PAIRS.append(('index.html: ряды кромок в редакторе пака', """
                        <div id="pack-skin-default" class="flex flex-wrap gap-1"><!-- кнопки общей формы --></div>
""", """
                        <div id="pack-skin-default" class="flex flex-wrap gap-1"><!-- кнопки общей формы --></div>
                        <!-- b448: кромка запайки -->
                        <div class="mt-2 text-[10px] font-bold uppercase tracking-wide text-slate-500">Зубчики упаковки</div>
                        <div id="pack-crimp-picker" class="grid grid-cols-5 gap-1 max-w-sm"><!-- свотчи кромок --></div>
                        <div class="mt-2 text-[10px] font-bold uppercase tracking-wide text-slate-500">Зубчики по умолчанию <span class="normal-case font-normal text-slate-600">(для паков без своей кромки; видны на «Фольге»)</span></div>
                        <div id="pack-crimp-default" class="grid grid-cols-5 gap-1 max-w-sm"><!-- кнопки общей кромки --></div>
"""))

TAG_OLD = 'nxmob177'
TAG_NEW = 'nxmob178'
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
            continue
        assert old.strip() in txt, 'b448: не найден якорь: %s' % label
        assert txt.count(old.strip()) == 1, 'b448: якорь не уникален: %s (%d)' % (label, txt.count(old.strip()))
        files[rel] = txt.replace(old.strip(), new.strip(), 1)
    for rel, txt in files.items():
        write(rel, txt)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b448: не найден тег %s в %s (сначала _b442.._b447)' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b448: применено')


def check():
    problems = []
    for label, old, new in PAIRS:
        rel = 'index.html' if label.startswith('index.html') else 'assets/app.js'
        txt = read(rel)
        if new.strip() not in txt:
            problems.append('%s: нет нового блока: %s' % (rel, label))
    app = read('assets/app.js')
    for extra in ('const PACK_CRIMPS = {', 'function packCrimpPoly(', 'function packCrimpId(',
                  'function nxCrimpDefault(', 'function nxCrimpApplyRoot(', 'function pickPackCrimp(',
                  'function nxSetCrimpDefault(', "(packCrimpId(pack) === 'zip' ? '' : '--pk-clip:' + packCrimpPolyFor(pack) + ';')",
                  'let packFormCrimp', 'const crimp = PACK_CRIMPS[packFormCrimp]',
                  'pack.crimp = crimp;', 'crimp,             // b448',
                  'packFormCrimp = PACK_CRIMPS[pack.crimp]', "getElementById('pack-crimp-quick')"):
        if extra not in app:
            problems.append('app.js: нет %r' % extra)
    html = read('index.html')
    for extra in ('id="pack-crimp-quick"', 'id="pack-crimp-picker"', 'id="pack-crimp-default"',
                  '.pack3d-face{ clip-path: var(--pk-clip,', '.pk-mini-crimp-zip{', 'Зубчики:'):
        if extra not in html:
            problems.append('index.html: нет %r' % extra)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не %s' % (rel, TAG_NEW))
    if problems:
        print('b448 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b448 --check: всё на месте (5 кромок, --pk-clip, три ряда кнопок, тег %s)' % TAG_NEW)


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
