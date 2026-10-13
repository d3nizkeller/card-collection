#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b426 — музыка карты: кнопка «Плей/Стоп» в карте и никаких одновременных треков.

Просьба владельца: «на карты где есть музыка в карту добавь плей и стоп…
чтоб пользователи могли выключать трек карты, просто у пользователей все
треки карт включаются одновременно».

Что было: личная музыка карты стартовала АВТОМАТИЧЕСКИ при открытии карты
(inspectCard → CardMusic.play) и loop'илась, пока карта открыта; параллельно
мог играть трек пака/вскрытия (PackMusic) — получалась каша из нескольких
треков, а выключить трек карты было нечем: только закрыть просмотр.

Стало:

* автозапуска НЕТ: открытие карты останавливает предыдущий трек карты и
  показывает кнопку;
* в просмотре карты — кнопка «▶ Включить трек карты» / «⏹ Стоп · <имя файла>»
  (#inspect-music-btn, onclick cardMusicToggle()): пользователь сам решает,
  слушать трек или нет;
* взаимоисключение по всей игре: CardMusic.play глушит PackMusic, а
  PackMusic.play глушит CardMusic — одновременно всегда не больше ОДНОГО
  трека;
* бейджи «у карты своя музыка» в списках получили честную подсказку:
  трек включается кнопкой в просмотре, а не сам.

Запуск:  python3 tools/_b426_patch.py            — применить
         python3 tools/_b426_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob88'
NEW_V = 'nxmob89'

# --------------------------------------------------------------------------- #
# app.js
# --------------------------------------------------------------------------- #

OLD_CM_PLAY = """            play(url) {
                this.stop();
                url = mediaUrl(url); // b38: трек тоже может лежать на зеркале
"""
NEW_CM_PLAY = """            play(url) {
                this.stop();
                // b426: одновременно не больше одного трека: музыка карты глушит трек пака
                try { if (PackMusic.playing) PackMusic.stop(); } catch (e) {}
                url = mediaUrl(url); // b38: трек тоже может лежать на зеркале
"""

OLD_PM_PLAY = """            play(url) {
                const u = String(mediaUrl(url) || '').trim(); // b38
                if (!u) return false;
"""
NEW_PM_PLAY = """            play(url) {
                const u = String(mediaUrl(url) || '').trim(); // b38
                if (!u) return false;
                // b426: одновременно не больше одного трека: трек пака глушит музыку карты
                try { if (CardMusic.url) { CardMusic.stop(); inspectRenderMusicBtn(inspectCardRef); } } catch (e) {}
"""

OLD_INSPECT_AUTO = """            // личная музыка карты: играет, пока карта открыта
            if (card.musicUrl) CardMusic.play(card.musicUrl); else CardMusic.stop();
"""
NEW_INSPECT_AUTO = """            // b426: личная музыка карты больше не стартует сама (иначе вместе с
            // треком пака играло несколько треков сразу): предыдущий трек глушим,
            // управление — кнопкой «Плей/Стоп» в просмотре карты
            CardMusic.stop();
            inspectRenderMusicBtn(card);
"""

OLD_INSPECT_FN = "        function inspectCard(cardId, list) {\n"
NEW_MODULE = """        // ============ b426: МУЗЫКА КАРТЫ — КНОПКА «ПЛЕЙ/СТОП» В КАРТЕ ============
        // Трек карты больше не включается сам: в просмотре карты появляется кнопка,
        // которой пользователь включает и выключает свою музыку. Одновременно во
        // всей игре играет не больше одного трека (см. CardMusic.play/PackMusic.play).
        let inspectCardRef = null;
        function inspectRenderMusicBtn(card) {
            inspectCardRef = card || null;
            const b = document.getElementById('inspect-music-btn');
            if (!b) return;
            const url = card && card.musicUrl ? String(card.musicUrl) : '';
            if (!url) { b.classList.add('hidden'); b.innerHTML = ''; return; }
            b.classList.remove('hidden');
            const playing = !!CardMusic.audio && CardMusic.url === mediaUrl(url);
            b.className = 'mt-3 px-4 py-2 rounded-xl text-xs font-bold transition ' + (playing
                ? 'bg-fuchsia-600 text-white shadow-lg shadow-fuchsia-950/40 animate-pulse'
                : 'bg-fuchsia-600/15 hover:bg-fuchsia-600/25 border border-fuchsia-500/40 text-fuchsia-200');
            b.innerHTML = playing
                ? '<i class="fa-solid fa-stop mr-1.5"></i>Стоп · ' + jpcEsc(PackMusic.nameOf(url))
                : '<i class="fa-solid fa-play mr-1.5"></i>Включить трек карты';
            b.title = playing ? 'Выключить трек этой карты' : 'Включить трек этой карты';
        }
        function cardMusicToggle() {
            const card = inspectCardRef;
            if (!card || !card.musicUrl) return;
            const url = mediaUrl(card.musicUrl);
            if (CardMusic.url === url && CardMusic.audio) CardMusic.stop();
            else CardMusic.play(card.musicUrl);
            inspectRenderMusicBtn(card);
        }
        function inspectCard(cardId, list) {
"""

OLD_BADGE1 = 'title="У карты своя музыка — трек играет в просмотре"'
NEW_BADGE1 = 'title="У карты своя музыка — включается кнопкой в просмотре"'
OLD_BADGE2 = "title=\"У карты своя музыка\""
NEW_BADGE2 = "title=\"У карты своя музыка — включается кнопкой в просмотре\""

JS_PATCHES = [
    ('CardMusic.play глушит пак', OLD_CM_PLAY, NEW_CM_PLAY),
    ('PackMusic.play глушит карту', OLD_PM_PLAY, NEW_PM_PLAY),
    ('без автозапуска трека карты', OLD_INSPECT_AUTO, NEW_INSPECT_AUTO),
    ('модуль кнопки музыки карты', OLD_INSPECT_FN, NEW_MODULE),
    ('бейдж музыки в списке карт', OLD_BADGE1, NEW_BADGE1),
    ('бейдж музыки в альбомах', OLD_BADGE2, NEW_BADGE2),
]

HTML_PATCHES = [
    ('кнопка музыки в просмотре карты',
     '            <div id="inspect-counter" class="hidden mt-3 text-[11px] font-mono tracking-wide text-slate-400 text-center"></div>\n',
     '            <div id="inspect-counter" class="hidden mt-3 text-[11px] font-mono tracking-wide text-slate-400 text-center"></div>\n'
     '            <!-- b426: плей/стоп личной музыки карты -->\n'
     '            <button id="inspect-music-btn" onclick="cardMusicToggle()" class="hidden mt-3 px-4 py-2 rounded-xl text-xs font-bold transition"></button>\n'),
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
