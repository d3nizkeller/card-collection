#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b461: карточка создаётся с одной картиной — имя и описание необязательны.

Просьба владельца: «создавать карточки можно и без имени и описания,
просто с картинкой». Раньше input'ы card-name/card-desc имели required —
форма не отправлялась без текста.

Лечение:
  1. required снят с обоих полей, у подписей появилось «(необязательно)»;
  2. хелпер cardDisplayName(card): пустое имя рендерится как «Без имени»
     ТОЛЬКО в отображении (лицо карты, список альбома, карусель пака,
     большой просмотр, сторис-канвас, тосты и шапка лота на рынке);
     в карте хранится пустая строка — редактор не подставляет лишнего;
  3. пустое описание больше не рисует пустую строку на лице карты:
     descHtml становится '' (зона пропускается); в большом просмотре
     по-прежнему работает запасной лор из nxDescTextOf;
  4. живой предпросмотр совпадает с сохранённой картой: имя-плейсхолдер
     «Без имени», пустое описание скрывается (ранее превью показывало
     «Имя персонажа»/«Описание карты», которых на карте потом не было).
pack-id и ссылка на картинку остаются обязательными: карта должна жить
в альбоме и иметь арт.

app.js менялся — тег сборки nxmob183 -> nxmob184 (index.html, sw.js,
tools/build.py).

Проверка/применение:
    python3 tools/_b461_patch.py --check
    python3 tools/_b461_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob183'
TAG_NEW = 'nxmob184'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('index.html', '''                            <label class="block text-[11px] font-medium text-slate-400 mb-1">Имя персонажа</label>
                            <input type="text" id="card-name" required oninput="renderCardPreview()" placeholder="Например: Cyber Paladin" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">''',
              '''                            <label class="block text-[11px] font-medium text-slate-400 mb-1">Имя персонажа <span class="text-slate-600">(необязательно)</span></label>
                            <!-- b461: карта живёт с одной картиной — required снят -->
                            <input type="text" id="card-name" oninput="renderCardPreview()" placeholder="Например: Cyber Paladin" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">'''))

PAIRS.append(('index.html', '''                            <label class="block text-[11px] font-medium text-slate-400 mb-1">Описание карты</label>
                            <input type="text" id="card-desc" required oninput="renderCardPreview()" placeholder="Специальные способности и лор" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">''',
              '''                            <label class="block text-[11px] font-medium text-slate-400 mb-1">Описание карты <span class="text-slate-600">(необязательно)</span></label>
                            <input type="text" id="card-desc" oninput="renderCardPreview()" placeholder="Специальные способности и лор" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-violet-500">'''))

PAIRS.append(('assets/app.js', '''        // b456+b457: inline-transform арта в рамке карты: масштаб + сдвиги по''',
              '''        // b461: карта валидна с одной картиной: пустое имя подставляется
        // только в отображении, храним пустую строку.
        function cardDisplayName(card) {
            const n = String((card && card.name) || '').trim();
            return n || 'Без имени';
        }
        // b456+b457: inline-transform арта в рамке карты: масштаб + сдвиги по'''))

PAIRS.append(('assets/app.js', 'const nameHtml = `<h4 class="w-full font-bold text-white text-base truncate drop-shadow-md ${L.text}">${card.name}</h4>`;',
              'const nameHtml = `<h4 class="w-full font-bold text-white text-base truncate drop-shadow-md ${L.text}">${cardDisplayName(card)}</h4>`; // b461'))

PAIRS.append(('assets/app.js', '<h4 class="relative z-10 w-full font-bold text-white text-[10px] truncate drop-shadow-md ${L.text}">${card.name}</h4>',
              '<h4 class="relative z-10 w-full font-bold text-white text-[10px] truncate drop-shadow-md ${L.text}">${cardDisplayName(card)}</h4>'))

PAIRS.append(('assets/app.js', 'const nameHtml = `<h4 class="w-full font-bold text-white text-sm sm:text-base truncate drop-shadow-md ${L.text}">${card.name}</h4>`;',
              'const nameHtml = `<h4 class="w-full font-bold text-white text-sm sm:text-base truncate drop-shadow-md ${L.text}">${cardDisplayName(card)}</h4>`; // b461'))

PAIRS.append(('assets/app.js', '<h4 class="font-bold text-sm text-white truncate group-hover:text-violet-300 transition-colors">${card.name}</h4>',
              '<h4 class="font-bold text-sm text-white truncate group-hover:text-violet-300 transition-colors">${cardDisplayName(card)}</h4>'))

PAIRS.append(('assets/app.js', 'const nameHtml = `<h4 class="w-full font-bold text-white text-lg drop-shadow-md break-words ${L.text}">${card.name}</h4>`;',
              'const nameHtml = `<h4 class="w-full font-bold text-white text-lg drop-shadow-md break-words ${L.text}">${cardDisplayName(card)}</h4>`; // b461'))

PAIRS.append(('assets/app.js', "const descHtml = `<p class=\"w-full text-xs text-slate-300 line-clamp-2 drop-shadow ${L.text}\">${card.description || ''}</p>`;",
              "const descHtml = String(card.description || '').trim() ? `<p class=\"w-full text-xs text-slate-300 line-clamp-2 drop-shadow ${L.text}\">${card.description}</p>` : ''; // b461: нет описания — нет пустой строки"))

PAIRS.append(('assets/app.js', "const descHtml = `<p class=\"w-full text-[11px] sm:text-xs text-slate-300 line-clamp-2 drop-shadow ${L.text}\">${card.description || ''}</p>`;",
              "const descHtml = String(card.description || '').trim() ? `<p class=\"w-full text-[11px] sm:text-xs text-slate-300 line-clamp-2 drop-shadow ${L.text}\">${card.description}</p>` : ''; // b461"))

PAIRS.append(('assets/app.js', "showToast('🏷 Лот выставлен: ' + card.name + ' за ' + fmtCoins(price), 'success');",
              "showToast('🏷 Лот выставлен: ' + cardDisplayName(card) + ' за ' + fmtCoins(price), 'success'); // b461"))

PAIRS.append(('assets/app.js', "if (nm) nm.innerHTML = 'Карта: <b class=\"text-slate-200\">' + cloudEsc(card.name) + '</b> • копий у вас: <b class=\"text-slate-200\">' + cardCopies(id) + '</b>';",
              "if (nm) nm.innerHTML = 'Карта: <b class=\"text-slate-200\">' + cloudEsc(cardDisplayName(card)) + '</b> • копий у вас: <b class=\"text-slate-200\">' + cardCopies(id) + '</b>'; // b461"))

PAIRS.append(('assets/app.js', "showToast('🎡 Приз: карта «' + card.name + '»! ('",
              "showToast('🎡 Приз: карта «' + cardDisplayName(card) + '»! ('"))

PAIRS.append(('assets/app.js', 'showToast(`Повторная карта ${card.name} продана за ${refund} монет!`, \'refund\');',
              'showToast(`Повторная карта ${cardDisplayName(card)} продана за ${refund} монет!`, \'refund\');'))

PAIRS.append(('assets/app.js', 'showToast(`Новая карта получена: ${card.name}!`, \'success\');',
              'showToast(`Новая карта получена: ${cardDisplayName(card)}!`, \'success\');'))

PAIRS.append(('assets/app.js', 'wrapCanvasText(g, card.name, W / 2, 292, W - 80, 28);',
              'wrapCanvasText(g, cardDisplayName(card), W / 2, 292, W - 80, 28); // b461'))

PAIRS.append(('assets/app.js', '''            const name = String(gv('card-name') || '').trim() || 'Имя персонажа';
            const desc = String(gv('card-desc') || '').trim() || 'Описание карты';''',
              '''            const name = String(gv('card-name') || '').trim() || 'Без имени'; // b461: превью совпадает с сохранённой картой
            const desc = String(gv('card-desc') || '').trim(); // b461: нет описания — зона скрыта'''))

PAIRS.append(('assets/app.js', 'const descHtml = `<p class="w-full text-[10px] text-slate-300 line-clamp-2 drop-shadow ${L.text}">${esc(desc)}</p>`;',
              'const descHtml = desc ? `<p class="w-full text-[10px] text-slate-300 line-clamp-2 drop-shadow ${L.text}">${esc(desc)}</p>` : \'\'; // b461'))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, old, new in PAIRS:
        txt = files.get(rel) or read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        if txt.count(o) != 1:
            problems.append('%s: якорь встретился %d раз: %s...' % (rel, txt.count(o), o[:60]))
            continue
        files[rel] = txt.replace(o, n, 1)
    for rel in TAG_FILES:
        txt = files.get(rel) or read(rel)
        if TAG_NEW in txt:
            problems.append('%s: тег уже %s' % (rel, TAG_NEW))
            continue
        if TAG_OLD not in txt:
            problems.append('%s: нет тега %s' % (rel, TAG_OLD))
            continue
        files[rel] = txt.replace(TAG_OLD, TAG_NEW)
    if problems:
        for p in problems:
            print('ПРОБЛЕМА:', p)
        return 1
    if '--check' in sys.argv:
        print('b461: якоря и тег %s на месте, можно применять' % TAG_OLD)
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b461: имя/описание необязательны; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
