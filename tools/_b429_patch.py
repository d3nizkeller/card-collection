#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b429 — на телефоне в просмотре карты страница больше не ездит влево-вправо.

Жалоба владельца: «на мобильной версии в просмотре карточки весь сайт
двигается влево и вправо при свайпе пальцем».

Три источника болтанки, лечим все:

1. Горизонтальный пан браузера. Модалка просмотра — fixed-оверлей с
   overflow-y:auto (=> overflow-x:auto), тело страницы под ней живое:
   свайп пальцем браузер трактовал как горизонтальный пан документа/модалки.
   Теперь на модалке `touch-action: pan-y` (горизонтальные жесты отдаются
   нашему свайп-листанию, а не браузеру) + `overscroll-behavior: contain`
   (без цепочки скролла наружу), а тело на время просмотра блокируется
   классом `body.nx-inspect-open { overflow: hidden }`.
2. Tilt-трансформация карты. Документный mousemove-обработчик крутит карту
   (rotateX/rotateY) за курсором; на тач-устройствах браузер шлёт
   совместимые mousemove во время свайпа — карта «плыла» под пальцем,
   а трансформация расширяла溢出-боксы. Теперь на тач-устройствах tilt
   выключен (nxIsTouchDevice), а при закрытии просмотра трансформация
   сбрасывается.
3. Наш свайп-листатель (touchstart/touchend, порог 40 px) остаётся рабочим:
   pan-y не мешает прочитать старт/финиш жеста.

Запуск:  python3 tools/_b429_patch.py            — применить
         python3 tools/_b429_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob92'
NEW_V = 'nxmob93'

OLD_STYLE = """    @media (max-width:640px){
        #inspect-float{ max-width: min(24rem, calc(58vh * 0.5625)); margin: 0 auto; }
    }
"""
NEW_STYLE = OLD_STYLE + """    /* b429: в просмотре карты страница не ездит по горизонтали: горизонтальные
       жесты отдаются свайп-листанию карт, скролл тела блокирован, цепочка
       overscroll не уходит наружу */
    #modal-inspect{ touch-action: pan-y; overscroll-behavior: contain; }
    body.nx-inspect-open{ overflow: hidden; }
"""

OLD_TILT = """        const inspectRender = document.getElementById('inspect-card-render');
        document.addEventListener('mousemove', (e) => {
            if (document.getElementById('modal-inspect').classList.contains('hidden')) return;
            const rect = inspectRender.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;
            inspectRender.style.transform = `rotateY(${x / 12}deg) rotateX(${-y / 12}deg)`;
        });
"""
NEW_TILT = """        const inspectRender = document.getElementById('inspect-card-render');
        // b429: на тач-устройствах совместимые mousemove приходят во время свайпа —
        // tilt крутил карту под пальцем и страница «ездила»; там tilt не нужен
        function nxIsTouchDevice() {
            // b429: одного «ontouchstart in window» мало (он есть и в jsdom, и в
            // десктопном Chrome с тач-эмуляцией) — решаем по фактическим тач-указателям
            try {
                if ((navigator.maxTouchPoints | 0) > 0) return true;
                if (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) return true;
                if (window.matchMedia && window.matchMedia('(hover: none)').matches && ('ontouchstart' in window)) return true;
            } catch (e) {}
            return false;
        }
        document.addEventListener('mousemove', (e) => {
            if (nxIsTouchDevice()) return; // b429
            if (document.getElementById('modal-inspect').classList.contains('hidden')) return;
            const rect = inspectRender.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;
            inspectRender.style.transform = `rotateY(${x / 12}deg) rotateX(${-y / 12}deg)`;
        });
"""

OLD_OPEN = """            updateInspectNav();
            updateInspectSlotsBtn();
            updateInspectMarketBtn();
            document.getElementById('modal-inspect').classList.remove('hidden');
"""
NEW_OPEN = """            updateInspectNav();
            updateInspectSlotsBtn();
            updateInspectMarketBtn();
            // b429: на время просмотра блокируем скролл тела — свайп не панит страницу
            try { document.body.classList.add('nx-inspect-open'); } catch (e) {}
            document.getElementById('modal-inspect').classList.remove('hidden');
"""

OLD_CLOSE = """        function closeInspectModal() {
            CardMusic.stop();
            document.getElementById('modal-inspect').classList.add('hidden');
        }
"""
NEW_CLOSE = """        function closeInspectModal() {
            CardMusic.stop();
            try { document.body.classList.remove('nx-inspect-open'); } catch (e) {} // b429
            try { inspectRender.style.transform = ''; } catch (e) {} // b429: сброс tilt
            document.getElementById('modal-inspect').classList.add('hidden');
        }
"""

JS_PATCHES = [
    ('tilt выключен на тач', OLD_TILT, NEW_TILT),
    ('блокировка тела при открытии', OLD_OPEN, NEW_OPEN),
    ('разблокировка при закрытии', OLD_CLOSE, NEW_CLOSE),
]

HTML_PATCHES = [
    ('touch-action/overscroll/overflow CSS', OLD_STYLE, NEW_STYLE),
]


# --------------------------------------------------------------------------- #
def patch_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise AssertionError('якорь «%s» встретился %d раз (нужно 1)' % (label, n))
    return text.replace(old, new, 1)


def main():
    check = '--check' in sys.argv
    js = os.path.join(ROOT, 'assets', 'app.js')
    html = os.path.join(ROOT, 'index.html')

    if check:
        bad = 0
        s = open(js, encoding='utf-8').read()
        for label, old, _n in JS_PATCHES:
            n = s.count(old); bad += (n != 1); print('  %s %-36s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        h = open(html, encoding='utf-8').read()
        for label, old, _n in HTML_PATCHES:
            n = h.count(old); bad += (n != 1); print('  %s %-36s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        return 1 if bad else 0

    s = open(js, encoding='utf-8').read()
    for label, old, new in JS_PATCHES:
        s = patch_once(s, old, new, label); print('  · %-36s ok' % label)
    open(js, 'w', encoding='utf-8', newline='').write(s)

    h = open(html, encoding='utf-8').read()
    for label, old, new in HTML_PATCHES:
        h = patch_once(h, old, new, label); print('  · %-36s ok' % label)
    open(html, 'w', encoding='utf-8', newline='').write(h)

    for p, old, new in ((html, '?v=' + OLD_V, '?v=' + NEW_V),
                        (os.path.join(ROOT, 'sw.js'), "const VERSION = '%s';" % OLD_V, "const VERSION = '%s';" % NEW_V),
                        (os.path.join(ROOT, 'tools', 'build.py'), "BUILD_TAG = '%s'" % OLD_V, "BUILD_TAG = '%s'" % NEW_V)):
        t = open(p, encoding='utf-8').read()
        n = t.count(old)
        if n:
            open(p, 'w', encoding='utf-8', newline='').write(t.replace(old, new))
        print('  · версия %-28s ×%d → %s' % (os.path.basename(p), n, NEW_V))
    return 0


if __name__ == '__main__':
    sys.exit(main())
