#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b439: просмотр карты — кнопка скрытия/раскрытия длинного описания.

Заявка владельца: «Сделай в просмотре карт описание кнопа скрытие и
раскрытее длинные описание».

Диагноз: в просмотре карты (inspectCard) описание рендерится на лицe карты
без какого-либо ограничения (в альбоме — line-clamp-2, а тут полный <p>).
Длинный текст (карты из конструктора, лор-описания паков) переполняет зону
текста, налезает на арт/статы и на телефоне вылезает за карточку.

Лечение:
  1. описание длиннее NX_DESC_CLAMP_LEN (150) символов по умолчанию
     свёрнуто до 3 строк (CSS .nx-desc-wrap .nx-desc-text — -webkit-line-clamp);
  2. под описанием — кнопка «Показать полностью / Свернуть» (nxDescToggle);
  3. выбор запоминается при листании карт (inspectStep) и сбрасывается
     при закрытии модалки (closeInspectModal);
  4. короткие описания рендерятся как раньше — без кнопки;
  5. тег сборки nxmob160 -> nxmob161 (index.html ?v= x8, sw.js VERSION,
     tools/build.py BUILD_TAG).

Проверка/применение:
    python3 tools/_b439_patch.py --check   # только проверить, что всё легло
    python3 tools/_b439_patch.py           # применить (идемпотентно)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = []

# 1. app.js: хелперы сворачивания перед inspectCard --------------------------
PAIRS.append(('app.js: хелперы b439 перед inspectCard', """
        try { cardMusicSeekInit(); } catch (e) {}
        function inspectCard(cardId, list) {
""", """
        try { cardMusicSeekInit(); } catch (e) {}
        // b439: сворачивание длинного описания в просмотре карты. Полное
        // описание переполняло лицо карты; теперь текст длиннее порога
        // показывается в 3 строки (CSS .nx-desc-wrap .nx-desc-text), а кнопка
        // «Показать полностью / Свернуть» раскрывает его. Выбор живёт до
        // закрытия модалки: свайп на соседнюю карту не сбрасывает раскрытие.
        const NX_DESC_CLAMP_LEN = 150;
        let nxDescOpen = false;
        function nxDescBtnHtml(open) {
            return open
                ? '<i class="fa-solid fa-chevron-up mr-1"></i>Свернуть'
                : '<i class="fa-solid fa-chevron-down mr-1"></i>Показать полностью';
        }
        function nxDescToggle(btn) {
            try {
                const wrap = btn && btn.closest ? btn.closest('.nx-desc-wrap') : null;
                if (!wrap) return;
                nxDescOpen = !wrap.classList.contains('nx-desc-open');
                wrap.classList.toggle('nx-desc-open', nxDescOpen);
                const b = wrap.querySelector('.nx-desc-btn');
                if (b) {
                    b.innerHTML = nxDescBtnHtml(nxDescOpen);
                    b.setAttribute('aria-expanded', nxDescOpen ? 'true' : 'false');
                }
            } catch (e) {}
        }
        function inspectCard(cardId, list) {
"""))

# 2. app.js: descHtml в inspectCard -------------------------------------------
PAIRS.append(('app.js: descHtml c клампом и кнопкой', """
            const descHtml = `<p class="w-full text-xs text-slate-300 drop-shadow ${L.text}">${card.description || 'Коллекционная карта «Коллекционер карт»'}</p>`;
""", """
            // b439: длинное описание — в 3 строки и кнопка раскрытия;
            // короткое рендерится как раньше (без обёртки и кнопки)
            const descTxt = card.description || 'Коллекционная карта «Коллекционер карт»';
            const descHtml = String(descTxt).length > NX_DESC_CLAMP_LEN
                ? `<div class="w-full nx-desc-wrap ${L.text}${nxDescOpen ? ' nx-desc-open' : ''}">
                        <p class="w-full text-xs text-slate-300 drop-shadow nx-desc-text">${descTxt}</p>
                        <button type="button" onclick="nxDescToggle(this)" aria-expanded="${nxDescOpen ? 'true' : 'false'}" class="nx-desc-btn mt-1 px-2 py-0.5 rounded-lg text-[10px] font-bold bg-slate-950/80 border border-slate-700 text-slate-300 backdrop-blur-sm transition active:scale-95">${nxDescBtnHtml(nxDescOpen)}</button>
                    </div>`
                : `<p class="w-full text-xs text-slate-300 drop-shadow ${L.text}">${descTxt}</p>`;
"""))

# 3. app.js: сброс при закрытии модалки ---------------------------------------
PAIRS.append(('app.js: closeInspectModal сбрасывает nxDescOpen', """
        function closeInspectModal() {
            CardMusic.stop();
            try { document.body.classList.remove('nx-inspect-open'); } catch (e) {} // b429
""", """
        function closeInspectModal() {
            CardMusic.stop();
            nxDescOpen = false; // b439: следующее открытие — описание снова свёрнуто
            try { document.body.classList.remove('nx-inspect-open'); } catch (e) {} // b429
"""))

# 4. index.html: CSS ----------------------------------------------------------
PAIRS.append(('index.html: CSS .nx-desc-wrap', """
    #modal-inspect{ touch-action: pan-y; overscroll-behavior: contain; }
    body.nx-inspect-open{ overflow: hidden; }
""", """
    #modal-inspect{ touch-action: pan-y; overscroll-behavior: contain; }
    body.nx-inspect-open{ overflow: hidden; }
    /* b439: длинное описание в просмотре карты по умолчанию свёрнуто в 3 строки,
       кнопка «Показать полностью» раскрывает (выбор помнится при свайпе карт) */
    .nx-desc-wrap .nx-desc-text{ display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:3; overflow:hidden; }
    .nx-desc-wrap.nx-desc-open .nx-desc-text{ display:block; overflow:visible; }
    .nx-desc-btn{ cursor:pointer; -webkit-tap-highlight-color:transparent; }
"""))

TAG_OLD = 'nxmob160'
TAG_NEW = 'nxmob161'
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
        assert old.strip() in txt, 'b439: не найден якорь: %s' % label
        assert txt.count(old.strip()) == 1, 'b439: якорь не уникален: %s (%d)' % (label, txt.count(old.strip()))
        files[rel] = txt.replace(old.strip(), new.strip(), 1)
    for rel, txt in files.items():
        write(rel, txt)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b439: не найден тег %s в %s' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b439: применено')


def check():
    problems = []
    for label, old, new in PAIRS:
        rel = 'index.html' if label.startswith('index.html') else 'assets/app.js'
        txt = read(rel)
        if new.strip() not in txt:
            problems.append('%s: нет нового блока: %s' % (rel, label))
    app = read('assets/app.js')
    for extra in ('function nxDescToggle(', 'function nxDescBtnHtml(',
                  'const NX_DESC_CLAMP_LEN = 150;', 'nxDescOpen = false; // b439'):
        if extra not in app:
            problems.append('app.js: нет %r' % extra)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не %s' % (rel, TAG_NEW))
    if problems:
        print('b439 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b439 --check: всё на месте (кламп описания, кнопка, CSS, тег %s)' % TAG_NEW)


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
