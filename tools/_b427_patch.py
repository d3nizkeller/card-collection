#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b427 — музыка карты: без названия трека на кнопке + промотка трека.

Просьба владельца: «не нужно показывать название трека, сделай промотку трека».

Стало:

* кнопка в просмотре карты больше не показывает имя файла: играя — просто
  «⏹ Стоп», в ожидании — «▶ Включить трек карты»;
* под кнопкой — мини-плеер промотки: полоса прогресса с бегунком, клик и
  перетаскивание перематывают трек (cardMusicSeekTo), по краям — текущее
  время и длительность (0:42 / 1:30);
* полоса видна только пока трек карты играет; обновление — тиком 500 мс;
* перемотка защищена от NaN-длительности (метаданные ещё не доехали).

Запуск:  python3 tools/_b427_patch.py            — применить
         python3 tools/_b427_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob89'
NEW_V = 'nxmob90'

# --------------------------------------------------------------------------- #
# app.js
# --------------------------------------------------------------------------- #

OLD_LABEL = """            b.innerHTML = playing
                ? '<i class="fa-solid fa-stop mr-1.5"></i>Стоп · ' + jpcEsc(PackMusic.nameOf(url))
                : '<i class="fa-solid fa-play mr-1.5"></i>Включить трек карты';
"""
NEW_LABEL = """            b.innerHTML = playing
                ? '<i class="fa-solid fa-stop mr-1.5"></i>Стоп' // b427: название трека не показываем
                : '<i class="fa-solid fa-play mr-1.5"></i>Включить трек карты';
"""

OLD_TITLE_LINE = """            b.title = playing ? 'Выключить трек этой карты' : 'Включить трек этой карты';
        }
"""
NEW_TITLE_LINE = """            b.title = playing ? 'Выключить трек этой карты' : 'Включить трек этой карты';
            try { cardMusicSeekRender(); } catch (e) {} // b427: полоса промотки следует за состоянием
        }
"""

OLD_TOGGLE = """        function cardMusicToggle() {
            const card = inspectCardRef;
            if (!card || !card.musicUrl) return;
            const url = mediaUrl(card.musicUrl);
            if (CardMusic.url === url && CardMusic.audio) CardMusic.stop();
            else CardMusic.play(card.musicUrl);
            inspectRenderMusicBtn(card);
        }
"""

NEW_TOGGLE = OLD_TOGGLE + """
        // ============ b427: ПРОМОТКА ТРЕКА КАРТЫ ============
        // Мини-плеер под кнопкой: полоса прогресса с бегунком, клик/перетаскивание
        // перематывают, по краям — текущее время и длительность. Видна только пока
        // трек карты играет.
        function nxTimeFmt(sec) {
            sec = Math.max(0, Math.floor(Number(sec) || 0));
            const m = Math.floor(sec / 60), s = sec % 60;
            return m + ':' + (s < 10 ? '0' : '') + s;
        }
        function cardMusicSeekRender() {
            const wrap = document.getElementById('inspect-music-seek');
            if (!wrap) return;
            const a = CardMusic.audio;
            const playing = !!a && !!CardMusic.url;
            if (!playing) { wrap.classList.add('hidden'); return; }
            wrap.classList.remove('hidden');
            let cur = 0, dur = 0;
            try { cur = Number(a.currentTime) || 0; dur = Number(a.duration) || 0; } catch (e) {}
            const pct = (isFinite(dur) && dur > 0) ? Math.min(100, Math.max(0, cur / dur * 100)) : 0;
            const fill = document.getElementById('inspect-music-fill');
            const knob = document.getElementById('inspect-music-knob');
            if (fill) fill.style.width = pct + '%';
            if (knob) knob.style.left = 'calc(' + pct + '% - 6px)';
            const tc = document.getElementById('inspect-music-cur');
            const td = document.getElementById('inspect-music-dur');
            if (tc) tc.textContent = nxTimeFmt(cur);
            if (td) td.textContent = (isFinite(dur) && dur > 0) ? nxTimeFmt(dur) : '—:—';
        }
        function cardMusicSeekTo(frac) {
            const a = CardMusic.audio;
            if (!a) return;
            let dur = 0;
            try { dur = Number(a.duration) || 0; } catch (e) {}
            if (!isFinite(dur) || dur <= 0) return; // метаданные ещё не доехали — промотка недоступна
            try { a.currentTime = Math.max(0, Math.min(1, frac)) * dur; } catch (e) {}
            cardMusicSeekRender();
        }
        function cardMusicSeekInit() {
            if (window.__nxCardMusicSeekBound) return;
            const bar = document.getElementById('inspect-music-bar');
            if (!bar) return;
            window.__nxCardMusicSeekBound = 1;
            let drag = false;
            const fracOf = ev => {
                const r = bar.getBoundingClientRect();
                if (!r || !r.width) return 0;
                return Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width));
            };
            bar.addEventListener('pointerdown', ev => { drag = true; try { bar.setPointerCapture(ev.pointerId); } catch (e) {} cardMusicSeekTo(fracOf(ev)); });
            bar.addEventListener('pointermove', ev => { if (drag) cardMusicSeekTo(fracOf(ev)); });
            bar.addEventListener('pointerup', () => { drag = false; });
            bar.addEventListener('pointercancel', () => { drag = false; });
            // тик прогресса: дёшево, только когда есть играющий трек карты
            setInterval(() => { try { if (CardMusic.url) cardMusicSeekRender(); } catch (e) {} }, 500);
        }
        try { cardMusicSeekInit(); } catch (e) {}
"""

JS_PATCHES = [
    ('кнопка без названия трека', OLD_LABEL, NEW_LABEL),
    ('seek-рендер из кнопки', OLD_TITLE_LINE, NEW_TITLE_LINE),
    ('промотка трека карты', OLD_TOGGLE, NEW_TOGGLE),
]

HTML_PATCHES = [
    ('полоса промотки под кнопкой',
     '            <button id="inspect-music-btn" onclick="cardMusicToggle()" class="hidden mt-3 px-4 py-2 rounded-xl text-xs font-bold transition"></button>\n',
     '            <button id="inspect-music-btn" onclick="cardMusicToggle()" class="hidden mt-3 px-4 py-2 rounded-xl text-xs font-bold transition"></button>\n'
     '            <!-- b427: промотка трека карты -->\n'
     '            <div id="inspect-music-seek" class="hidden w-full max-w-sm mt-2 px-2">\n'
     '                <div id="inspect-music-bar" class="relative h-2 bg-slate-800 rounded-full cursor-pointer touch-none select-none">\n'
     '                    <div id="inspect-music-fill" class="absolute inset-y-0 left-0 bg-fuchsia-500 rounded-full" style="width:0%"></div>\n'
     '                    <div id="inspect-music-knob" class="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow" style="left:-6px"></div>\n'
     '                </div>\n'
     '                <div class="flex justify-between text-[10px] font-mono text-slate-400 mt-1"><span id="inspect-music-cur">0:00</span><span id="inspect-music-dur">—:—</span></div>\n'
     '            </div>\n'),
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
