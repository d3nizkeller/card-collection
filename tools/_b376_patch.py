# -*- coding: utf-8 -*-
"""b376: «кнопки не отрисовались» — стрелки перемещения карт в Студии.

Причина: сабсет assets/fa.css + fa-solid-900.woff2 (18 КБ) собран ДО b375 и НЕ содержит
глифа fa-arrow-down (класс даже не определён в css) → кнопка «ниже» рисовалась пустым
кружком. Заодно disabled-состояние relied on .opacity-30, которого нет в собранном
assets/tailwind.css → неактивная стрелка не отличалась от активной.

Починка: обе стрелки (↑ и ↓) — инлайн-SVG (path из Font Awesome 6 solid, viewBox 384×512),
не зависят от шрифта-сабсета; disabled — инлайн-style opacity:.3;pointer-events:none
(pointer-events-none в tailwind есть, но держим оба свойства вместе и явно).

Правка вносится ОДИНАКОВО в assets/app.js (LF) и tools/source-index.html (CRLF-монолит).
"""
import io, sys

UP_OLD = u"""transition${pos <= 1 ? ' opacity-30 pointer-events-none' : ''}" title="Переместить выше"><i class="fa-solid fa-arrow-up text-xs"></i></button>"""
UP_NEW = u"""transition" style="${pos <= 1 ? 'opacity:.3;pointer-events:none' : ''}" title="Переместить выше"><svg aria-hidden="true" focusable="false" fill="currentColor" viewBox="0 0 384 512" style="width:9px;height:12px"><path d="M214.6 41.4c-12.5-12.5-32.8-12.5-45.3 0l-160 160c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 141.2V448c0 17.7 14.3 32 32 32s32-14.3 32-32V141.2L329.4 246.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3l-160-160z"/></svg></button>"""
DN_OLD = u"""transition${pos >= total ? ' opacity-30 pointer-events-none' : ''}" title="Переместить ниже"><i class="fa-solid fa-arrow-down text-xs"></i></button>"""
DN_NEW = u"""transition" style="${pos >= total ? 'opacity:.3;pointer-events:none' : ''}" title="Переместить ниже"><svg aria-hidden="true" focusable="false" fill="currentColor" viewBox="0 0 384 512" style="width:9px;height:12px"><path d="M169.4 470.6c12.5 12.5 32.8 12.5 45.3 0l160-160c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L224 370.8V64c0-17.7-14.3-32-32-32s-32 14.3-32 32v306.7L54.6 265.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l160 160z"/></svg></button>"""
COMMENT = u"""            // b376: стрелки — инлайн-SVG (в сабсете fa.css/woff2 нет глифа fa-arrow-down — кнопка рисовалась пустой); disabled — инлайн-style (opacity-30 нет в собранном tailwind.css)
"""

def patch(path, crlf):
    with io.open(path, 'r', encoding='utf-8', newline='') as f:
        t = f.read()
    for old, new in ((UP_OLD, UP_NEW), (DN_OLD, DN_NEW)):
        n = t.count(old)
        assert n == 1, (path, old[:40], n)
        t = t.replace(old, new)
    anchor = u"            const moveBtns = (pos && !cloudGuest())"
    assert t.count(anchor) == 1, (path, 'anchor')
    nl = u'\r\n' if crlf else u'\n'
    t = t.replace(anchor, COMMENT.rstrip(u'\n') + nl + anchor, 1)
    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(t)
    raw = io.open(path, 'rb').read()
    assert b'\r\r\n' not in raw, path
    if crlf:
        assert raw.count(b'\r') == raw.count(b'\r\n'), path  # нет одиноких \r
    else:
        assert b'\r' not in raw, path
    print('patched', path)

patch(u'assets/app.js', False)
patch(u'tools/source-index.html', True)
print('b376 patch ok')
