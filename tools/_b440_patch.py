#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b440: раскрытое описание в просмотре карты показывается ЦЕЛИКОМ.

Заявка владельца: «при раскрытом опесани должен быть виден весь текст».

Диагноз: b439 снимал с текста кламп (.nx-desc-open -> display:block), но текст
живёт на лице карты #inspect-card-render, а у него aspect-ratio 9/16 и
overflow:hidden. Такой элемент — flex-потомок с НЕвидимым overflow, значит его
автоматический минимальный размер равен 0 и коробка не растёт по содержимому:
раскрытое описание упиралось в край карты и обрезалось (на телефоне — тем
сильнее, чем длиннее лор; у карт из конструктора maxlength нет).
Плюс модалка #modal-inspect центрирует контент через justify-center: когда
содержимое выше экрана, его начало уезжает вверх и не достаётся скроллом.

Лечение:
  1. полный текст раскрытого описания показывается в панели #inspect-desc-full
     ПОД картой (вне обрезанного лица карты), в скроллящейся модалке — виден
     весь текст любой длины; на лице карты остаётся кнопка «Свернуть»;
  2. панель синхронизирована с состоянием: nxDescToggle, листание карт
     (inspectStep) и закрытие модалки (closeInspectModal);
  3. центрирование модалки переведено на auto-поля (justify-content:flex-start
     + margin:auto у потомка) — высокий контент прокручивается с самого начала;
  4. свайп по панели описания больше не листает карты (это скролл текста);
  5. описание экранируется (nxDescEsc) — карточки приходят из общих облачных
     комнат, чужой HTML не должен попадать в разметку;
  6. тег сборки nxmob161 -> nxmob162 (index.html ?v= x8, sw.js VERSION,
     tools/build.py BUILD_TAG).

Проверка/применение:
    python3 tools/_b440_patch.py --check   # только проверить, что всё легло
    python3 tools/_b440_patch.py           # применить (идемпотентно)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = []

# 1. app.js: nxDescToggle тянет панель + хелперы b440 -------------------------
PAIRS.append(('app.js: nxDescToggle + панель полного описания', """
                }
            } catch (e) {}
        }
        function inspectCard(cardId, list) {
""", """
                }
                nxDescPanelSync(true); // b440: полный текст — в панель под картой
            } catch (e) {}
        }
        // b440: «при раскрытом описании должен быть виден весь текст». Лицо
        // карты (#inspect-card-render) имеет aspect-ratio 9/16 и overflow:hidden,
        // а как flex-потомок с невидимым overflow оно не растёт по содержимому —
        // раскрытый длинный текст обрезался краем карты. Поэтому полный текст
        // показывается в панели #inspect-desc-full под картой (модалка
        // #modal-inspect скроллится), а на лице карты остаётся кнопка «Свернуть».
        function nxDescEsc(t) {
            return String(t == null ? '' : t)
                .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        }
        function nxDescTextOf(card) {
            return String((card && card.description) || 'Коллекционная карта «Коллекционер карт»');
        }
        function nxDescPanelSync(scrollTo) {
            const p = document.getElementById('inspect-desc-full');
            if (!p) return;
            let show = false, txt = '';
            try {
                const id = (inspectList || [])[inspectIdx];
                const card = state.cards.find(c => c.id === id);
                if (nxDescOpen && card) {
                    txt = nxDescTextOf(card);
                    show = txt.length > NX_DESC_CLAMP_LEN;
                }
            } catch (e) {}
            const t = document.getElementById('inspect-desc-full-text');
            if (t) t.textContent = show ? txt : '';
            p.classList.toggle('hidden', !show);
            if (show && scrollTo) {
                try { p.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); } catch (e) {
                    try { p.scrollIntoView(); } catch (e2) {}
                }
            }
        }
        function inspectCard(cardId, list) {
"""))

# 2. app.js: descHtml — общий источник текста и экранирование -----------------
PAIRS.append(('app.js: descTxt через nxDescTextOf + nxDescEsc', """
            const descTxt = card.description || 'Коллекционная карта «Коллекционер карт»';
            const descHtml = String(descTxt).length > NX_DESC_CLAMP_LEN
                ? `<div class="w-full nx-desc-wrap ${L.text}${nxDescOpen ? ' nx-desc-open' : ''}">
                        <p class="w-full text-xs text-slate-300 drop-shadow nx-desc-text">${descTxt}</p>""",
"""
            // b440: текст берём из nxDescTextOf (тот же источник, что и у панели
            // полного описания) и экранируем — описания приходят из общих
            // облачных комнат, чужой HTML не должен попадать в разметку
            const descTxt = nxDescTextOf(card);
            const descHtml = String(descTxt).length > NX_DESC_CLAMP_LEN
                ? `<div class="w-full nx-desc-wrap ${L.text}${nxDescOpen ? ' nx-desc-open' : ''}">
                        <p class="w-full text-xs text-slate-300 drop-shadow nx-desc-text">${nxDescEsc(descTxt)}</p>"""))

PAIRS.append(('app.js: короткая ветка descHtml тоже экранируется', """
                : `<p class="w-full text-xs text-slate-300 drop-shadow ${L.text}">${descTxt}</p>`;
""", """
                : `<p class="w-full text-xs text-slate-300 drop-shadow ${L.text}">${nxDescEsc(descTxt)}</p>`;
"""))

# 3. app.js: панель синхронизируется при каждом рендере карты -----------------
PAIRS.append(('app.js: inspectCard синхронизирует панель', """
            updateInspectNav();
            updateInspectSlotsBtn();
            updateInspectMarketBtn();
""", """
            updateInspectNav();
            updateInspectSlotsBtn();
            updateInspectMarketBtn();
            nxDescPanelSync(false); // b440: панель полного описания — за текущей картой
"""))

# 4. app.js: закрытие модалки прячет панель -----------------------------------
PAIRS.append(('app.js: closeInspectModal прячет панель', """
            nxDescOpen = false; // b439: следующее открытие — описание снова свёрнуто
""", """
            nxDescOpen = false; // b439: следующее открытие — описание снова свёрнуто
            try { nxDescPanelSync(false); } catch (e) {} // b440: панель полного описания прячем и чистим
"""))

# 5. app.js: свайп по панели — это скролл текста, а не листание карт ----------
PAIRS.append(('app.js: свайп по панели не листает карты', """
            if (!m || m.classList.contains('hidden')) { inspectTouchX = null; return; }
            inspectTouchX = (e.touches && e.touches[0]) ? e.touches[0].clientX : null;
""", """
            if (!m || m.classList.contains('hidden')) { inspectTouchX = null; return; }
            // b440: свайп по панели полного описания — это скролл текста, не листание карт
            try {
                if (e.target && e.target.closest && e.target.closest('#inspect-desc-full')) { inspectTouchX = null; return; }
            } catch (err) {}
            inspectTouchX = (e.touches && e.touches[0]) ? e.touches[0].clientX : null;
"""))

# 6. index.html: панель полного описания под картой ---------------------------
PAIRS.append(('index.html: панель #inspect-desc-full', """
            </div>
            <!-- b18: счётчик / листание альбома -->
""", """
            </div>
            <!-- b440: раскрытое описание целиком. Лицо карты (aspect-ratio 9/16
                 + overflow:hidden) обрезало длинный текст, поэтому полный текст
                 живёт здесь — под картой, в скроллящейся модалке просмотра -->
            <div id="inspect-desc-full" class="hidden w-full mt-3 px-3 py-2.5 rounded-xl border border-slate-700 bg-slate-900/85 backdrop-blur-sm">
                <div class="flex items-center gap-1.5 mb-1 text-[10px] font-black uppercase tracking-wider text-slate-400"><i class="fa-solid fa-scroll"></i><span>Описание целиком</span></div>
                <div id="inspect-desc-full-text" class="text-xs leading-relaxed text-slate-200 whitespace-pre-wrap break-words"></div>
            </div>
            <!-- b18: счётчик / листание альбома -->
"""))

# 7. index.html: CSS ----------------------------------------------------------
PAIRS.append(('index.html: CSS раскрытого описания и центрирования модалки', """
    .nx-desc-wrap.nx-desc-open .nx-desc-text{ display:block; overflow:visible; }
    .nx-desc-btn{ cursor:pointer; -webkit-tap-highlight-color:transparent; }
""", """
    /* b440: в раскрытом состоянии текст на лице карты скрывается — весь текст
       показывается в панели #inspect-desc-full под картой (иначе aspect-ratio
       9/16 + overflow:hidden обрезали бы его краем карты) */
    .nx-desc-wrap.nx-desc-open .nx-desc-text{ display:none; }
    .nx-desc-btn{ cursor:pointer; -webkit-tap-highlight-color:transparent; }
    #inspect-desc-full-text{ white-space:pre-wrap; overflow-wrap:anywhere; word-break:break-word; }
    /* b440: модалка просмотра центрируется auto-полями, а не justify-center —
       иначе высокий контент (раскрытое описание) обрезался бы сверху и не
       прокручивался до самого начала */
    #modal-inspect{ justify-content:flex-start; }
    #modal-inspect > div{ margin-top:auto; margin-bottom:auto; }
    @media (max-width:640px){
        #inspect-desc-full{ max-width: min(24rem, calc(58vh * 0.5625)); }
    }
"""))

TAG_OLD = 'nxmob161'
TAG_NEW = 'nxmob162'
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
        assert old.strip() in txt, 'b440: не найден якорь: %s' % label
        assert txt.count(old.strip()) == 1, 'b440: якорь не уникален: %s (%d)' % (label, txt.count(old.strip()))
        files[rel] = txt.replace(old.strip(), new.strip(), 1)
    for rel, txt in files.items():
        write(rel, txt)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b440: не найден тег %s в %s' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b440: применено')


def check():
    problems = []
    for label, old, new in PAIRS:
        rel = 'index.html' if label.startswith('index.html') else 'assets/app.js'
        txt = read(rel)
        if new.strip() not in txt:
            problems.append('%s: нет нового блока: %s' % (rel, label))
    app = read('assets/app.js')
    for extra in ('function nxDescPanelSync(', 'function nxDescTextOf(', 'function nxDescEsc(',
                  'nxDescPanelSync(true); // b440', 'nxDescPanelSync(false); // b440',
                  "e.target.closest('#inspect-desc-full')"):
        if extra not in app:
            problems.append('app.js: нет %r' % extra)
    html = read('index.html')
    for extra in ('id="inspect-desc-full"', 'id="inspect-desc-full-text"',
                  '.nx-desc-wrap.nx-desc-open .nx-desc-text{ display:none; }',
                  '#modal-inspect{ justify-content:flex-start; }'):
        if extra not in html:
            problems.append('index.html: нет %r' % extra)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не %s' % (rel, TAG_NEW))
    if problems:
        print('b440 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b440 --check: всё на месте (панель полного описания, CSS, скролл модалки, тег %s)' % TAG_NEW)


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
