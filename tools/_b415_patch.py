#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b415 — надписи о процентах джекпота следуют за настройками Студии.

До b415 в разметке были зашиты «100% каждой ставки», «100% каждого проигрыша»,
«весь банк ваш», «1 из 16 спинов» — после изменения процентов в Студии тексты
врали. Теперь каждое такое место размечено атрибутом data-jpc="…", а один
рендер jpcLabelsRender() подставляет актуальные значения:

  data-jpc="feed"       % ставки в банк            (jpc.feedBet)
  data-jpc="loss"       % проигрыша в банк         (jpc.feedLoss)
  data-jpc="pay"        «весь банк ваш» / «вам N% банка»
  data-jpc="pay2"       «весь общий банк сайта» / «N% общего банка сайта»
  data-jpc="pay2v"      «весь общий банк сайта ваш» / «вам N% общего банка сайта»
  data-jpc="pay3"       «весь банк джекпота» / «N% банка джекпота»
  data-jpc="paynum"     просто «N%» выплаты
  data-jpc="odds-wheel" «1 из 16 спинов» по jpc.pWheel («не выпадает» при on=0)

Рендер вызывается из jackpotRender(), поэтому надписи обновляются и после
своих правок в Студии, и когда прилетает чужая редакция настроек. Плюс два
динамических текста в app.js («Линий нет — N% ставки ушли…» и результат колеса
«— весь общий банк сайта ваш!») и живой пример в панели «Джекпот».

Запуск:  python3 tools/_b415_patch.py            — применить
         python3 tools/_b415_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob74'
NEW_V = 'nxmob75'

# --------------------------------------------------------------------------- #
# app.js: модуль живых надписей + точки вызова
# --------------------------------------------------------------------------- #
LABEL_ANCHOR = "        // ---- симулятор: как часто джекпот будет выпадать с текущими процентами ----\n"

LABEL_MODULE = r'''        // ============ b415: НАДПИСИ О ПРОЦЕНТАХ СЛЕДУЮТ ЗА НАСТРОЙКАМИ ============
        // Все пользовательские тексты про «100 % ставки», «весь банк ваш» и
        // «1 из 16 спинов» размечены в index.html атрибутами data-jpc="…".
        // Один рендер подставляет в них актуальные значения; вызывается из
        // jackpotRender(), поэтому надписи обновляются и после своих правок в
        // Студии, и когда прилетает чужая редакция настроек из облака.
        function jpcPctTxt(v) {
            const x = Math.round((Number(v) || 0) * 10) / 10;
            return String(x) + '%';
        }
        function jpcPhrase(key) {
            const p = Math.round(Number(jpc.payout) || 0);
            switch (key) {
                case 'feed': return jpcPctTxt(jpc.feedBet);
                case 'loss': return jpcPctTxt(jpc.feedLoss);
                case 'paynum': return jpcPctTxt(p);
                case 'pay': return p >= 100 ? 'весь банк ваш' : ('вам ' + p + '% банка');
                case 'pay2': return p >= 100 ? 'весь общий банк сайта' : (p + '% общего банка сайта');
                case 'pay2v': return p >= 100 ? 'весь общий банк сайта ваш' : ('вам ' + p + '% общего банка сайта');
                case 'pay3': return p >= 100 ? 'весь банк джекпота' : (p + '% банка джекпота');
                case 'odds-wheel': {
                    if (jpcOff()) return 'не выпадает';
                    const pp = jpcP('Wheel');
                    if (pp >= 100) return 'каждый спин';
                    if (pp <= 0) return 'не выпадает';
                    const n = 100 / pp;
                    return '1 из ' + (n >= 100 ? Math.round(n).toLocaleString('ru-RU') : (Math.round(n * 10) / 10)) + ' спинов';
                }
            }
            return '';
        }
        const JPC_LABEL_KEYS = ['feed', 'loss', 'pay', 'pay2', 'pay2v', 'pay3', 'paynum', 'odds-wheel'];
        function jpcLabelsRender() {
            for (let i = 0; i < JPC_LABEL_KEYS.length; i++) {
                const key = JPC_LABEL_KEYS[i];
                const txt = jpcPhrase(key);
                const nodes = document.querySelectorAll('[data-jpc="' + key + '"]');
                for (let k = 0; k < nodes.length; k++) {
                    if (nodes[k].textContent !== txt) nodes[k].textContent = txt;
                }
            }
            // живой пример в панели «Джекпот»: ставка 10k и текущая выплата
            const ea = document.getElementById('jpc-ex-add');
            if (ea) ea.textContent = fmtCoins(Math.max(0, Math.round(10000 * (Number(jpc.feedBet) || 0) / 100)));
            const ew = document.getElementById('jpc-ex-win');
            if (ew) { try { ew.textContent = fmtCoins(Math.round(jackpotPool() * (Number(jpc.payout) || 0) / 100)); } catch (e) {} }
        }
        try { jpcLabelsRender(); } catch (e) {} // разметка уже в DOM: скрипт в конце body

'''

JS_PATCHES = [
    ('модуль живых надписей b415',
     LABEL_ANCHOR,
     LABEL_MODULE + LABEL_ANCHOR),

    ('jackpotRender обновляет надписи',
     """            const lv = document.getElementById('lines-jp-top-list');
            if (lv) lv.innerHTML = html;
        }""",
     """            const lv = document.getElementById('lines-jp-top-list');
            if (lv) lv.innerHTML = html;
            try { jpcLabelsRender(); } catch (e) {} // b415: надписи о процентах — вслед за настройками
        }"""),

    ('сообщение «Линий нет» с живым процентом',
     """res.innerHTML = 'Линий нет — 100% ставки ушли в общий джекпот';""",
     """res.innerHTML = 'Линий нет — ' + jpcPctTxt(jpc.feedBet) + ' ставки ушли в общий джекпот';"""),

    ('результат колеса с живой фразой выплаты',
     """(sec.t === 'jackpot' ? ' — весь общий банк сайта ваш!' : (win > 0 ? ' — +' + fmtCoins(win) + ' монет' : ''));""",
     """(sec.t === 'jackpot' ? ' — ' + jpcPhrase('pay2v') + '!' : (win > 0 ? ' — +' + fmtCoins(win) + ' монет' : ''));"""),

    ('комментарий JACKPOT_FEED',
     """        const JACKPOT_FEED = 1; // b96: 100% каждой ставки идёт в общий банк сайта""",
     """        const JACKPOT_FEED = 1; // b96: базовый множитель взноса; сам процент ставки задаётся в Студии (b414/b415)"""),

    ('комментарий jackpotOnLoss',
     """        // b92: каждый проигрыш пополняет общий банк на 100% потерянной суммы —
        // джекпот собирает все проигрыши пользователей целиком (раньше было 25%)""",
     """        // b92: каждый проигрыш пополняет общий банк на процент потерянной суммы —
        // джекпот собирает проигрыши пользователей целиком (раньше было 25%).
        // b415: процент (заводской 100) настраивается в Студии → feedLoss."""),

    ('комментарий мины',
     """        // Забрать выигрыш можно в любой момент; мина сжигает ставку (в джекпот уходит 100% проигрыша),
        // старт раунда кормит общий джекпот сайта 100% ставки.""",
     """        // Забрать выигрыш можно в любой момент; мина сжигает ставку (в джекпот уходит
        // feedLoss% проигрыша), старт раунда кормит общий джекпот сайта feedBet% ставки (b415)."""),
]

# комментарии-примечания у вызовов: меняем все вхождения
JS_PATCHES_ALL = [
    ('// b96: 100% ставки в банк',
     '// b96; b415: % ставки в банк — из настроек Студии'),
    ('// b105: 100% ставки кормят общий банк',
     '// b105; b415: % ставки в банк — из настроек Студии'),
    ('// b105: проигрыш отдаёт банку 100% ставки',
     '// b105; b415: % проигрыша в банк — из настроек Студии'),
    ('// b238: Дурак кормит общий джекпот — 100% ставки в банк',
     '// b238; b415: Дурак кормит джекпот — % ставки из настроек Студии'),
    ('// b238: проигрыш кормит банк на 100%',
     '// b238; b415: проигрыш кормит банк на % из настроек Студии'),
    ('// b94: джекпот растёт на 100% проигрыша',
     '// b94; b415: джекпот растёт на % проигрыша из настроек Студии'),
    ('// b94: +100% проигрыша в банк',
     '// b94; b415: +% проигрыша в банк из настроек Студии'),
    ('// b92: в банк идёт 100% чистого проигрыша (пусто — вся ставка, ×0.5 — половина)',
     '// b92; b415: в банк идёт feedLoss% чистого проигрыша (пусто — вся ставка, ×0.5 — половина)'),
]

# --------------------------------------------------------------------------- #
# index.html: разметка data-jpc
# --------------------------------------------------------------------------- #
HTML_PATCHES = [
    ('Слоты: jp-desc',
     '<p class="jp-desc">три символа JACKPOT подряд на барабанах — весь банк ваш; банк кормят 100% каждой ставки и 100% каждого проигрыша</p>',
     '<p class="jp-desc">три символа JACKPOT подряд на барабанах — <b data-jpc="pay">весь банк ваш</b>; банк кормят <b data-jpc="feed">100%</b> каждой ставки и <b data-jpc="loss">100%</b> каждого проигрыша</p>'),

    ('Сетка: jp-desc',
     '<p class="jp-desc">3+ карт JACKPOT где угодно на поле — весь банк ваш; банк кормят 100% каждой ставки и 100% каждого проигрыша</p>',
     '<p class="jp-desc">3+ карт JACKPOT где угодно на поле — <b data-jpc="pay">весь банк ваш</b>; банк кормят <b data-jpc="feed">100%</b> каждой ставки и <b data-jpc="loss">100%</b> каждого проигрыша</p>'),

    ('Линии: jp-desc',
     '<p class="jp-desc">линия JACKPOT слева направо — весь банк ваш; банк кормят 100% каждой ставки и 100% каждого проигрыша</p>',
     '<p class="jp-desc">линия JACKPOT слева направо — <b data-jpc="pay">весь банк ваш</b>; банк кормят <b data-jpc="feed">100%</b> каждой ставки и <b data-jpc="loss">100%</b> каждого проигрыша</p>'),

    ('Слоты: пункт правил',
     '<li>100% каждой ставки кормят общий джекпот сайта, проигрышный спин отдаёт банку ещё 100% ставки. Выигрыш сразу падает в баланс.</li>',
     '<li><b data-jpc="feed">100%</b> каждой ставки кормят общий джекпот сайта, проигрышный спин отдаёт банку ещё <b data-jpc="loss">100%</b> ставки. Выигрыш сразу падает в баланс.</li>'),

    ('Сетка: пункт правил',
     '<li>100% ставки кормят общий джекпот; проигрышный спин отдаёт в банк ещё 100% проигрыша.</li>',
     '<li><b data-jpc="feed">100%</b> ставки кормят общий джекпот; проигрышный спин отдаёт в банк ещё <b data-jpc="loss">100%</b> проигрыша.</li>'),

    ('Колесо: вводный абзац',
     'золотой сектор JACKPOT (1 из 16 спинов) — срывает весь общий банк сайта! Каждая ставка кормит банк на 100%, а проигрыш отдаёт банку ещё 100% потерянной суммы.',
     'золотой сектор JACKPOT (<b data-jpc="odds-wheel">1 из 16 спинов</b>) — срывает <b data-jpc="pay2">весь общий банк сайта</b>! Каждая ставка кормит банк на <b data-jpc="feed">100%</b>, а проигрыш отдаёт банку ещё <b data-jpc="loss">100%</b> потерянной суммы.'),

    ('Колесо: пункт правил 2',
     'или золотой сектор <b>JACKPOT</b> (один — 1 из 16 спинов) — весь общий банк сайта.</li>',
     'или золотой сектор <b>JACKPOT</b> (один — <b data-jpc="odds-wheel">1 из 16 спинов</b>) — <b data-jpc="pay2">весь общий банк сайта</b>.</li>'),

    ('Колесо: пункт правил 3',
     '<li>Пустой сектор: ставка сгорает и уходит в общий джекпот на <b>100%</b>; 100% каждой ставки капают в банк всегда, а проигрыш докидывает ещё 100% потерянной суммы.</li>',
     '<li>Пустой сектор: ставка сгорает и уходит в общий джекпот на <b data-jpc="loss">100%</b>; <b data-jpc="feed">100%</b> каждой ставки капают в банк всегда, а проигрыш докидывает ещё <b data-jpc="loss">100%</b> потерянной суммы.</li>'),

    ('Мины: вводный абзац',
     'Мина сжигает ставку и кормит общий джекпот сайта (100% ставки при старте + 100% проигрыша при мине).',
     'Мина сжигает ставку и кормит общий джекпот сайта (<b data-jpc="feed">100%</b> ставки при старте + <b data-jpc="loss">100%</b> проигрыша при мине).'),

    ('Мины: пункт правил 4',
     '<li>Мина: ставка сгорает и уходит в общий джекпот сайта на <b>100%</b>; старт раунда кормит банк 100% ставки.</li>',
     '<li>Мина: ставка сгорает и уходит в общий джекпот сайта на <b data-jpc="loss">100%</b>; старт раунда кормит банк <b data-jpc="feed">100%</b> ставки.</li>'),

    ('Линии: пункт правил 3',
     '<li>Три символа <b>JACKPOT</b> слева на линии — весь общий банк сайта ваш; 100% ставки кормят банк каждый спин, проигрыш докидывает 100% ставки.</li>',
     '<li>Три символа <b>JACKPOT</b> слева на линии — <b data-jpc="pay2v">весь общий банк сайта ваш</b>; <b data-jpc="feed">100%</b> ставки кормят банк каждый спин, проигрыш докидывает <b data-jpc="loss">100%</b> ставки.</li>'),

    ('Линии: вводный абзац',
     'Линия из JACKPOT — весь общий банк сайта ваш!</p>',
     'Линия из JACKPOT — <b data-jpc="pay2v">весь общий банк сайта ваш</b>!</p>'),

    ('Слоты: строка выплат',
     'Три символа JACKPOT подряд — весь банк джекпота.</p>',
     'Три символа JACKPOT подряд — <b data-jpc="pay3">весь банк джекпота</b>.</p>'),

    ('Студия: живой пример вместо статичного',
     '<p class="text-[10px] text-slate-500 leading-snug">Пример: ставка 10k при «100% ставки в банк» добавляет в банк 10k монет; при выплате 100% победитель забирает не весь банк, а только его часть — остаток копится дальше и не обнуляет витрину.</p>',
     '<p class="text-[10px] text-slate-500 leading-snug">Живой пример по текущим настройкам: ставка <b class="text-slate-300">10k</b> кормит банк на <b data-jpc="feed">100%</b> — это <b class="text-slate-300"><span id="jpc-ex-add">10k</span></b>; победитель забирает <b data-jpc="paynum">100%</b> банка — сейчас это <b class="text-slate-300"><span id="jpc-ex-win">—</span></b>, остальное копится дальше и не обнуляет витрину.</p>'),
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
            n = s.count(old); bad += (n != 1); print('  %s %-44s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        for old, _n in JS_PATCHES_ALL:
            n = s.count(old); bad += (n < 1); print('  %s %-44s %d (все)' % ('OK ' if n >= 1 else 'BAD', old[:40], n))
        h = open(html, encoding='utf-8').read()
        for label, old, _n in HTML_PATCHES:
            n = h.count(old); bad += (n != 1); print('  %s %-44s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        return 1 if bad else 0

    s = open(js, encoding='utf-8').read()
    for label, old, new in JS_PATCHES:
        s = patch_once(s, old, new, label); print('  · %-44s ok' % label)
    for old, new in JS_PATCHES_ALL:
        n = s.count(old)
        if n:
            s = s.replace(old, new); print('  · %-44s ok ×%d' % (old[:40], n))
    open(js, 'w', encoding='utf-8', newline='').write(s)

    h = open(html, encoding='utf-8').read()
    for label, old, new in HTML_PATCHES:
        h = patch_once(h, old, new, label); print('  · %-44s ok' % label)
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
