#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b472: чипы редкостей на паке показывают шанс В ПАКЕ, а не на одну карту.

Жалоба владельца со скриншотом: чипы «Обычная 60% · Редкая 25% · Эпическая 12% ·
Легендарная 3%» — «не правильно показывает проценты».

Разбор
------
Цифры на чипах были честными ШАНСАМИ НА ОДНУ КАРТУ: getPackOdds() считал
Math.round(RARITY_WEIGHTS[r] / total * 100), а rollCardFromPack() крутит ровно
по тем же весам. Симуляция 300 000 паков дала 60.0 / 25.0 / 12.0 / 3.0 на карту.

Но игрок открывает не карту, а ПАК, а пак даёт 4 независимые карты
(rollPackCards, было зашито «i < 4»). Поэтому шанс увидеть хотя бы одну
легендарную в паке = 1 - 0.97^4 = 11,5 %, а эпическую и выше = 1 - 0.85^4 =
47,8 %. Симуляция: легендарная хотя бы одна в 11,5 % паков (в 3,8 раза чаще
обещанных трёх процентов), эпическая+ в 47,8 %. Отсюда ощущение, что проценты
врут, — и жалоба.

Гарант epic+ (PITY_LIMIT) на эти цифры практически не влияет: до счётчика 9
доживают ~0,3 % серий паков, симуляция с гарантом и без дала одинаковые 47,8 %.

Лечение (по выбору владельца: показывать шанс хотя бы одной карты в паке)
-------------------------------------------------------------------------
1. getPackOdds() (assets/app.js:4141) считает 1 - (1 - p)^PACK_CARDS, где p —
   вес редкости, нормированный по редкостям, присутствующим в паке (пак без
   легендарных карт по-прежнему пересчитывает веса на оставшиеся). Шанс на одну
   карту возвращается в поле one — он не теряется.
2. Чипы показывают процент «в паке»; в title чипа и в подписи под рядом
   остаются числа «на одну карту», чтобы веса крутки продолжали быть видны.
3. PACK_CARDS = 4 вынесен константой рядом с PITY_LIMIT и подставлен в
   rollPackCards (цикл и замена последней карты при гаранте), чтобы формула
   показа и сама крутка не могли разъехаться.

Ряд чипов по-прежнему строго в одну строку (b445): подпись — отдельная строка
под ним, карточка пака тянется за счёт mt-auto у строки цены.

app.js менялся — тег сборки nxmob215 -> nxmob216.

Проверка/применение:
    python3 tools/_b472_patch.py --check
    python3 tools/_b472_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob215'
TAG_NEW = 'nxmob216'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('assets/app.js', 1,
              '''        const PITY_LIMIT = 10; // каждый 10-й пак без epic+ гарантирует epic+''',
              '''        const PITY_LIMIT = 10; // каждый 10-й пак без epic+ гарантирует epic+
        const PACK_CARDS = 4;  // b472: карт в одном вскрытии (раньше было зашито «i < 4» в rollPackCards)'''))

PAIRS.append(('assets/app.js', 1,
              '''            const rolled = [];
            for (let i = 0; i < 4; i++) rolled.push(rollCardFromPack(packCards));''',
              '''            const rolled = [];
            for (let i = 0; i < PACK_CARDS; i++) rolled.push(rollCardFromPack(packCards));   // b472'''))

PAIRS.append(('assets/app.js', 1,
              '''                rolled[3] = rollCardFromPack(packCards, true);''',
              '''                rolled[PACK_CARDS - 1] = rollCardFromPack(packCards, true);   // b472'''))

PAIRS.append(('assets/app.js', 1,
              '''        function getPackOdds(pack) {
            const cards = state.cards.filter(c => c.packId === pack.id);
            const present = RARITY_ORDER.filter(r => cards.some(c => c.rarity === r));
            const total = present.reduce((s, r) => s + RARITY_WEIGHTS[r], 0);
            return present.map(r => ({ r, pct: Math.round(RARITY_WEIGHTS[r] / total * 100) }));
        }''',
              '''        // b472: процент на чипе — шанс встретить редкость В ПАКЕ (хотя бы одну из
        // PACK_CARDS карт), а не на одну карту. Игрок открывает пак, а не карту:
        // при весах 60/25/12/3 легендарная приходила хотя бы одна в 11,5 % паков,
        // а чип обещал «3 %» — игроки справедливо жаловались, что проценты
        // неправильные. Формула для независимых карт: 1 - (1 - p)^PACK_CARDS.
        // Гарант epic+ на цифру почти не влияет (<0,1 % паков до него доживают),
        // поэтому в формулу он не входит. Шанс на одну карту остаётся в поле one:
        // он показан в title чипа и в подписи под рядом.
        function getPackOdds(pack) {
            const cards = state.cards.filter(c => c.packId === pack.id);
            const present = RARITY_ORDER.filter(r => cards.some(c => c.rarity === r));
            const total = present.reduce((s, r) => s + RARITY_WEIGHTS[r], 0);
            return present.map(r => {
                const p = RARITY_WEIGHTS[r] / total;
                return { r, pct: Math.round((1 - Math.pow(1 - p, PACK_CARDS)) * 100), one: Math.round(p * 100) };
            });
        }'''))

PAIRS.append(('assets/app.js', 1,
              '''            return `<div class="nx-odds flex flex-nowrap items-center gap-0.5 sm:gap-1 mt-2 overflow-x-auto">${odds.map(o => `<span class="text-[9px] sm:text-[10px] font-semibold px-1 sm:px-1.5 py-0.5 rounded border whitespace-nowrap shrink-0 ${cls[o.r] || cls.common}">${RARITY_LABELS_RU[o.r]} ${o.pct}%</span>`).join('')}</div>`;''',
              '''            const chips = odds.map(o => `<span class="text-[9px] sm:text-[10px] font-semibold px-1 sm:px-1.5 py-0.5 rounded border whitespace-nowrap shrink-0 ${cls[o.r] || cls.common}" title="на одну карту: ${o.one}% • в паке из ${PACK_CARDS}: ${o.pct}%">${RARITY_LABELS_RU[o.r]} ${o.pct}%</span>`).join('');
            return `<div class="nx-odds flex flex-nowrap items-center gap-0.5 sm:gap-1 mt-2 overflow-x-auto">${chips}</div>` +
                `<p class="text-[9px] text-slate-600 mt-1 leading-snug">шанс хотя бы одной карты редкости в паке из ${PACK_CARDS} • на одну карту: ${odds.map(o => o.one + '%').join(' / ')}</p>`;'''))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8', newline='') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, cnt, old, new in PAIRS:
        txt = files.get(rel) or read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        if txt.count(o) != cnt:
            problems.append('%s: якорь встретился %d раз вместо %d: %s...' % (rel, txt.count(o), cnt, o[:60]))
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
        print('b472: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b472: чипы редкостей показывают шанс в паке; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
