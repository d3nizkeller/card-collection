#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b474: процентность пака генерирует игра сама, владелец ничего не выставляет.

Уточнение владельца к b473: «Не я должен выставлять — игра автоматически
рандомно». То есть ручные веса в форме остались полезными, но по умолчанию
ничего вводить не нужно: у каждого пака своя процентность появляется сама.

Как сделано
-----------
1. packAutoOdds(packId) выводит веса детерминированно из id пака тем же
   FNV-хэшем schedHash (b161), который уже используется для флеш-сейлов и
   «одинаков у всех игроков». Значит:
     * каждый пак получает СВОЮ процентность без участия владельца;
     * все клиенты считают её одинаково — ничего не надо публиковать и
       синхронизировать, старые паки получают свои шансы сразу;
     * процентность стабильна во времени: не пляшет между вскрытиями и не
       меняется после перезахода.
   Диапазоны держат экономику в разумных рамках: легендарная 1-8, эпическая
   6-18, редкая 15-35, обычная — остаток до 100 (39-78). Сумма всегда 100.
2. packOddsOf() (3076): ручные веса pack.odds важнее; нет их — packAutoOdds
   по id пака; нет и id (битые данные) — заводская таблица RARITY_WEIGHTS.
   Крутка (rollCardFromPack) и показ (getPackOdds, чипы b472) читают только
   packOddsOf, поэтому авто-процентность автоматически видна и в крутке, и на
   чипах в магазине.
3. Форма пака: пустые поля теперь означают «процентность от игры», а не
   «заводские 60/25/12/3» (packOddsFill очищает поля). Превью под полями
   (packOddsPreview) при пустых полях показывает АВТО-значения редактируемого
   пака с пометкой «сгенерированы игрой», а для нового пака объясняет, что
   процентность появится при создании. Кнопка «Сгенерировать»
   (packOddsReroll) кладёт в поля новый случайный набор из тех же диапазонов —
   он закрепится как ручной после сохранения.
4. Ручные веса, ноль-запрет редкости, защита от мусора и STD_PACK_FIELDS —
   без изменений (b473).

app.js и index.html менялись — тег сборки nxmob217 -> nxmob218.

Проверка/применение:
    python3 tools/_b474_patch.py --check
    python3 tools/_b474_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob217'
TAG_NEW = 'nxmob218'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('assets/app.js', 1,
              '''        function packOddsOf(pack) {''',
              '''        // b474: СВОИ ШАНСЫ У ПАКА ПОЯВЛЯЮТСЯ САМИ — владелец ничего не выставляет.
        // Веса выводятся детерминированно из id пака тем же FNV-хэшем schedHash,
        // что у флеш-сейлов (b161, «одинаково у всех игроков»): каждый пак получает
        // свою процентность, все клиенты считают её одинаково, публиковать и
        // синхронизировать нечего. Диапазоны держат экономику в разумных рамках:
        // легендарная 1-8 %, эпическая 6-18 %, редкая 15-35 %, обычная — остаток
        // (39-78 %). Сумма всегда 100, поэтому «на одну карту» читается напрямую.
        // Ручные веса из формы (pack.odds) по-прежнему важнее авто-значений.
        const MKT_AUTO_ODDS = { legendary: [1, 8], epic: [6, 18], rare: [15, 35] };
        function packAutoOdds(packId) {
            const id = String(packId || '');
            const take = (salt, lo, hi) => lo + (schedHash(id + '|' + salt) % (hi - lo + 1));
            const legendary = take('leg', MKT_AUTO_ODDS.legendary[0], MKT_AUTO_ODDS.legendary[1]);
            const epic = take('epic', MKT_AUTO_ODDS.epic[0], MKT_AUTO_ODDS.epic[1]);
            const rare = take('rare', MKT_AUTO_ODDS.rare[0], MKT_AUTO_ODDS.rare[1]);
            return { common: 100 - legendary - epic - rare, rare: rare, epic: epic, legendary: legendary };
        }
        function packOddsOf(pack) {'''))

PAIRS.append(('assets/app.js', 1,
              '''                if (sum > 0) return n;
            }
            return RARITY_WEIGHTS;
        }''',
              '''                if (sum > 0) return n;
            }
            if (pack && pack.id) return packAutoOdds(pack.id);   // b474: своих весов нет — процентность пака от игры
            return RARITY_WEIGHTS;
        }'''))

PAIRS.append(('assets/app.js', 1,
              '''        function packOddsFill(odds) {
            RARITY_ORDER.forEach(r => {
                const el = document.getElementById('pack-odds-' + r);
                if (el) el.value = String(odds ? (odds[r] === undefined ? 0 : odds[r]) : RARITY_WEIGHTS[r]);
            });
            packOddsPreview();
        }''',
              '''        function packOddsFill(odds) {
            // b474: пустые поля = процентность сгенерировала игра (у каждого пака
            // своя), а не «заводские 60/25/12/3». Заводские теперь частный случай
            // ручных весов: впишите их и сохраните.
            RARITY_ORDER.forEach(r => {
                const el = document.getElementById('pack-odds-' + r);
                if (el) el.value = odds ? String(odds[r] === undefined ? 0 : odds[r]) : '';
            });
            packOddsPreview();
        }'''))

PAIRS.append(('assets/app.js', 1,
              '''        function packOddsPreview() {
            const el = document.getElementById('pack-odds-preview');
            if (!el) return;
            const els = packOddsInputs();
            const o = {};
            let any = false, ok = true;
            RARITY_ORDER.forEach((r, i) => {
                const v = String(els[i] ? els[i].value : '').trim();
                if (v === '') { o[r] = 0; return; }
                const n = Number(v);
                if (!isFinite(n) || n < 0) { ok = false; o[r] = 0; return; }
                o[r] = n;
                if (n > 0) any = true;
            });
            if (!ok || !any) { el.textContent = ''; return; }
            const W = packOddsSameAsDefault(o) ? RARITY_WEIGHTS : o;
            const present = RARITY_ORDER.filter(r => (Number(W[r]) || 0) > 0);
            const total = present.reduce((s, r) => s + Number(W[r]), 0);
            el.textContent = present.map(r => {
                const p = Number(W[r]) / total;
                return RARITY_LABELS_RU[r] + ' ' + Math.round(p * 100) + '% на карту / ' +
                    Math.round((1 - Math.pow(1 - p, PACK_CARDS)) * 100) + '% в паке';
            }).join(' • ');
        }''',
              '''        function packOddsPreview() {
            const el = document.getElementById('pack-odds-preview');
            if (!el) return;
            const els = packOddsInputs();
            const typed = {};
            let any = false, ok = true;
            RARITY_ORDER.forEach((r, i) => {
                const v = String(els[i] ? els[i].value : '').trim();
                if (v === '') { typed[r] = 0; return; }
                const n = Number(v);
                if (!isFinite(n) || n < 0) { ok = false; typed[r] = 0; return; }
                typed[r] = n;
                if (n > 0) any = true;
            });
            if (!ok || (any && RARITY_ORDER.every(r => typed[r] === 0))) { el.textContent = ''; return; }
            const editId = String((document.getElementById('edit-pack-id') || {}).value || '');
            let W = null, src = '';
            if (any) { W = typed; src = 'Ваши веса: '; }
            else if (editId) { W = packAutoOdds(editId); src = 'Шансы пака (сгенерированы игрой): '; }
            if (!W) {
                el.textContent = 'У нового пака процентность появится сама при создании — своя у каждого пака.';
                return;
            }
            const present = RARITY_ORDER.filter(r => (Number(W[r]) || 0) > 0);
            const total = present.reduce((s, r) => s + Number(W[r]), 0);
            el.textContent = src + present.map(r => {
                const p = Number(W[r]) / total;
                return RARITY_LABELS_RU[r] + ' ' + Math.round(p * 100) + '% на карту / ' +
                    Math.round((1 - Math.pow(1 - p, PACK_CARDS)) * 100) + '% в паке';
            }).join(' • ');
        }
        // b474: «Сгенерировать» — новый случайный набор в поля (закрепится как
        // ручной после сохранения). Авто-значения пака при этом не меняются,
        // пока поля не сохранены: перегенерировать их «на месте» нельзя и не
        // нужно — иначе процентность пака плясала бы между клиентами.
        function packOddsReroll() {
            const rnd = (lo, hi) => lo + Math.floor(Math.random() * (hi - lo + 1));
            const legendary = rnd(MKT_AUTO_ODDS.legendary[0], MKT_AUTO_ODDS.legendary[1]);
            const epic = rnd(MKT_AUTO_ODDS.epic[0], MKT_AUTO_ODDS.epic[1]);
            const rare = rnd(MKT_AUTO_ODDS.rare[0], MKT_AUTO_ODDS.rare[1]);
            packOddsFill({ common: 100 - legendary - epic - rare, rare: rare, epic: epic, legendary: legendary });
        }'''))

PAIRS.append(('index.html', 1,
              '''                            <label class="block text-[11px] font-medium text-slate-400 mb-1">Шансы редкостей (веса)</label>''',
              '''                            <label class="block text-[11px] font-medium text-slate-400 mb-1 flex items-center gap-2">Шансы редкостей (веса)
                                <button type="button" onclick="packOddsReroll()" title="Предложить новый случайный набор и закрепить его в паке" class="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[10px] font-bold text-slate-300 transition"><i class="fa-solid fa-dice mr-1"></i>Сгенерировать</button>
                            </label>'''))

PAIRS.append(('index.html', 1,
              '''                            <p class="text-[10px] text-slate-600 mt-0.5">Веса, а не проценты: 60/25/12/3 — заводские. Ноль = редкости в паке не бывает. Оставьте все четыре поля пустыми — вернутся заводские. Чипы шансов на паке в магазине пересчитаются сами.</p>''',
              '''                            <p class="text-[10px] text-slate-600 mt-0.5">Выставлять ничего не нужно: поля пустые = процентность сгенерировала игра, у каждого пака своя и одинаковая у всех игроков (строка под полями показывает её). Захотели свою — впишите веса или нажмите «Сгенерировать». Ноль = редкости в паке не бывает. Чипы шансов на паке в магазине пересчитываются сами.</p>'''))


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
        print('b474: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b474: процентность пака генерирует игра сама; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
