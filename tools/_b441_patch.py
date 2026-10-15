#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b441: раскрытое описание можно ПРОЛИСТЫВАТЬ верх-вниз.

Заявка владельца: «Сделай открытие описание можно пролистывать верх вниз,
чтоб читать длинное описание карточки».

Диагноз: в b440 полный текст раскрытого описания переехал в панель
#inspect-desc-full под картой, но панель растёт на всю длину текста, а
скроллится вся модалка #modal-inspect. На очень длинном лоре, чтобы читать,
приходится тянуть всю модалку (карта, счётчик и кнопки уезжают за экран),
на телефоне это неудобно. Описание должно листаться верх-вниз само, внутри
панели.

Лечение:
  1. текст панели #inspect-desc-full-text получает max-height:32vh +
     overflow-y:auto + -webkit-overflow-scrolling:touch + touch-action:pan-y +
     overscroll-behavior:contain — вертикальный жест пальцем/колесо крутят
     САМ текст, цепочка скролла не уходит в модалку; тонкий тёмный скроллбар;
  2. подсказка «низу ещё текст»: nxDescScrollHint() вешает на панель класс
     nx-desc-scrollable (внизу градиентный фейд ::after, pointer-events:none),
     а при докрутке до конца — nx-desc-end (фейд гаснет); пересчёт на смену
     текста (nxDescPanelSync), на scroll панели и на resize окна (32vh);
  3. при листании карт scrollTop панели сбрасывается — лор новой карты
     показывается с первой строки;
  4. клавиатура: у текста tabindex="0" + role="region" — фокус Tab, скролл
     стрелками/PgUp/PgDn, :focus-visible рисует ненавязчивый аутлайн;
  5. защита b440 на месте: свайп по панели не листает карты (touchstart-гард),
     текст вставляется через textContent (XSS);
  6. тег сборки nxmob162 -> nxmob163 (index.html ?v= x8, sw.js VERSION,
     tools/build.py BUILD_TAG).

Проверка/применение:
    python3 tools/_b441_patch.py --check   # только проверить, что всё легло
    python3 tools/_b441_patch.py           # применить (идемпотентно)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = []

# 1. app.js: nxDescPanelSync — сброс scrollTop + подсказка; функция nxDescScrollHint
PAIRS.append(('app.js: nxDescPanelSync + nxDescScrollHint', """
            const t = document.getElementById('inspect-desc-full-text');
            if (t) t.textContent = show ? txt : '';
            p.classList.toggle('hidden', !show);
            if (show && scrollTo) {
                try { p.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); } catch (e) {
                    try { p.scrollIntoView(); } catch (e2) {}
                }
            }
        }
""", """
            const t = document.getElementById('inspect-desc-full-text');
            if (t) t.textContent = show ? txt : '';
            p.classList.toggle('hidden', !show);
            if (t) { try { t.scrollTop = 0; } catch (e) {} } // b441: при листании карт текст начинается сначала
            nxDescScrollHint(); // b441: панель прокручивается — подсказка «низу ещё текст»
            if (show && scrollTo) {
                try { p.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); } catch (e) {
                    try { p.scrollIntoView(); } catch (e2) {}
                }
            }
        }
        // b441: «открытие описание можно пролистывать верх вниз, чтоб читать
        // длинное описание». Текст панели (#inspect-desc-full-text) ограничен
        // по высоте ~32vh и крутится внутри пальцем/колесом (CSS), а здесь
        // живёт подсказка, что снизу ещё текст: nx-desc-scrollable включает
        // фейд внизу панели, nx-desc-end гасит его, когда докрутили до конца.
        function nxDescScrollHint() {
            const p = document.getElementById('inspect-desc-full');
            const t = document.getElementById('inspect-desc-full-text');
            if (!p || !t) return;
            const upd = () => {
                try {
                    if (p.classList.contains('hidden')) {
                        p.classList.remove('nx-desc-scrollable', 'nx-desc-end');
                        return;
                    }
                    const scrollable = t.scrollHeight > t.clientHeight + 4;
                    p.classList.toggle('nx-desc-scrollable', scrollable);
                    p.classList.toggle('nx-desc-end', scrollable && (t.scrollTop + t.clientHeight >= t.scrollHeight - 4));
                } catch (e) {}
            };
            upd();
            try { requestAnimationFrame(upd); } catch (e) {}
        }
"""))

# 2. app.js: слушатели scroll/resize панели полного описания
PAIRS.append(('app.js: слушатели scroll/resize панели', """
        document.addEventListener('touchend', (e) => {
            const m = document.getElementById('modal-inspect');
            if (!m || m.classList.contains('hidden') || inspectTouchX === null) return;
            const x = (e.changedTouches && e.changedTouches[0]) ? e.changedTouches[0].clientX : null;
            if (x !== null && Math.abs(x - inspectTouchX) > 40) inspectStep(x < inspectTouchX ? 1 : -1);
            inspectTouchX = null;
        }, { passive: true });
""", """
        document.addEventListener('touchend', (e) => {
            const m = document.getElementById('modal-inspect');
            if (!m || m.classList.contains('hidden') || inspectTouchX === null) return;
            const x = (e.changedTouches && e.changedTouches[0]) ? e.changedTouches[0].clientX : null;
            if (x !== null && Math.abs(x - inspectTouchX) > 40) inspectStep(x < inspectTouchX ? 1 : -1);
            inspectTouchX = null;
        }, { passive: true });
        // b441: собственный скролл панели описания — обновляем подсказку
        // «долистали до конца»; при resize окна меняется и лимит 32vh
        (function () {
            const nxDescTxt = document.getElementById('inspect-desc-full-text');
            if (nxDescTxt) nxDescTxt.addEventListener('scroll', () => { try { nxDescScrollHint(); } catch (e) {} }, { passive: true });
            window.addEventListener('resize', () => { try { nxDescScrollHint(); } catch (e) {} });
        })();
"""))

# 3. index.html: CSS — скролл текста панели, скроллбар, фейд «низу ещё текст»
PAIRS.append(('index.html: CSS скролла панели описания', """
    #inspect-desc-full-text{ white-space:pre-wrap; overflow-wrap:anywhere; word-break:break-word; }
""", """
    #inspect-desc-full-text{ white-space:pre-wrap; overflow-wrap:anywhere; word-break:break-word; }
    /* b441: раскрытое описание пролистывается верх-вниз САМО: текст панели
       ограничен ~32vh и крутится внутри (палец/колесо), цепочка скролла не
       уходит в модалку (overscroll-behavior:contain), вертикальный жест
       принадлежит панели (touch-action:pan-y), на iOS — инерция */
    #inspect-desc-full-text{
      max-height:32vh; overflow-y:auto; -webkit-overflow-scrolling:touch;
      overscroll-behavior:contain; touch-action:pan-y;
      scrollbar-width:thin; scrollbar-color:#475569 transparent;
    }
    #inspect-desc-full-text::-webkit-scrollbar{ width:6px; }
    #inspect-desc-full-text::-webkit-scrollbar-thumb{ background:#475569; border-radius:3px; }
    #inspect-desc-full-text::-webkit-scrollbar-track{ background:transparent; }
    #inspect-desc-full-text:focus-visible{ outline:2px solid #475569; outline-offset:2px; border-radius:6px; }
    /* подсказка «низу ещё текст»: градиентный фейд, гаснет при докрутке до конца */
    #inspect-desc-full{ position:relative; }
    #inspect-desc-full.nx-desc-scrollable #inspect-desc-full-text{ padding-right:4px; }
    #inspect-desc-full.nx-desc-scrollable::after{
      content:''; position:absolute; left:10px; right:10px; bottom:8px; height:28px;
      pointer-events:none; border-radius:0 0 10px 10px; transition:opacity .2s;
      background:linear-gradient(180deg, rgba(15,23,42,0), rgba(15,23,42,.9));
    }
    #inspect-desc-full.nx-desc-scrollable.nx-desc-end::after{ opacity:0; }
"""))

# 4. index.html: tabindex/role — скролл с клавиатуры
PAIRS.append(('index.html: tabindex/role текста панели', """
                <div id="inspect-desc-full-text" class="text-xs leading-relaxed text-slate-200 whitespace-pre-wrap break-words"></div>
""", """
                <div id="inspect-desc-full-text" tabindex="0" role="region" aria-label="Описание целиком, прокручивается" class="text-xs leading-relaxed text-slate-200 whitespace-pre-wrap break-words"></div>
"""))

TAG_OLD = 'nxmob162'
TAG_NEW = 'nxmob163'
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
        assert old.strip() in txt, 'b441: не найден якорь: %s' % label
        assert txt.count(old.strip()) == 1, 'b441: якорь не уникален: %s (%d)' % (label, txt.count(old.strip()))
        files[rel] = txt.replace(old.strip(), new.strip(), 1)
    for rel, txt in files.items():
        write(rel, txt)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b441: не найден тег %s в %s' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b441: применено')


def check():
    problems = []
    for label, old, new in PAIRS:
        rel = 'index.html' if label.startswith('index.html') else 'assets/app.js'
        txt = read(rel)
        if new.strip() not in txt:
            problems.append('%s: нет нового блока: %s' % (rel, label))
    app = read('assets/app.js')
    for extra in ('function nxDescScrollHint(', 'nxDescScrollHint(); // b441',
                  't.scrollTop = 0; } catch (e) {} } // b441',
                  "nxDescTxt.addEventListener('scroll'",
                  "e.target.closest('#inspect-desc-full')"):
        if extra not in app:
            problems.append('app.js: нет %r' % extra)
    html = read('index.html')
    for extra in ('max-height:32vh; overflow-y:auto;', 'overscroll-behavior:contain; touch-action:pan-y;',
                  '#inspect-desc-full.nx-desc-scrollable::after',
                  '#inspect-desc-full.nx-desc-scrollable.nx-desc-end::after{ opacity:0; }',
                  'id="inspect-desc-full-text" tabindex="0" role="region"'):
        if extra not in html:
            problems.append('index.html: нет %r' % extra)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не %s' % (rel, TAG_NEW))
    if problems:
        print('b441 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b441 --check: всё на месте (скролл панели 32vh, фейд-подсказка, сброс scrollTop, tabindex, тег %s)' % TAG_NEW)


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
