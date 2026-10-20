#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генератор tools/_b473_patch.py: свои шансы редкостей у каждого пака."""
import io, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = io.open(os.path.join(ROOT, 'assets/app.js'), encoding='utf-8').read()
IDX = io.open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
PAIRS = []

# ── 1. чтение весов пака + нормализация ─────────────────────────────────────
a = "        const RARITY_WEIGHTS = { common: 60, rare: 25, epic: 12, legendary: 3 };"
assert APP.count(a) == 1
PAIRS.append(('assets/app.js', 1, a, a + '''
        // b473: СВОИ ШАНСЫ РЕДКОСТЕЙ У КАЖДОГО ПАКА. pack.odds — необязательное
        // поле {common,rare,epic,legendary} с ВЕСАМИ (не процентами): крутка
        // (rollCardFromPack) и показ (getPackOdds) читают его через packOddsOf(),
        // а нет поля — работает общая таблица RARITY_WEIGHTS.
        // Поле приходит из общего документа комнаты, куда пишет кто угодно,
        // поэтому нормализуем здесь: целые числа >= 0, потолок MKT_ODDS_MAX,
        // и хотя бы один вес > 0 — иначе молча возвращаемся к заводским.
        const MKT_ODDS_MAX = 1000000;
        function packOddsOf(pack) {
            const o = pack && pack.odds;
            if (o && typeof o === 'object') {
                const n = {};
                let sum = 0;
                for (let i = 0; i < RARITY_ORDER.length; i++) {
                    const r = RARITY_ORDER[i];
                    let v = Number(o[r]);
                    if (!isFinite(v) || v < 0) v = 0;
                    v = Math.min(MKT_ODDS_MAX, Math.round(v));
                    n[r] = v;
                    sum += v;
                }
                if (sum > 0) return n;
            }
            return RARITY_WEIGHTS;
        }
        function packOddsSameAsDefault(o) {
            for (let i = 0; i < RARITY_ORDER.length; i++) {
                if (Number(o[RARITY_ORDER[i]]) !== RARITY_WEIGHTS[RARITY_ORDER[i]]) return false;
            }
            return true;
        }'''))

# ── 2. стандартные паки: odds едет в комнату через stdMod-патч ──────────────
a = "        const STD_PACK_FIELDS = ['title', 'description', 'image', 'price', 'color', 'shimmer', 'musicUrl', 'musicOff', 'saleUntil', 'premiereAt', 'schedule', 'retired'];"
assert APP.count(a) == 1
PAIRS.append(('assets/app.js', 1, a,
              "        const STD_PACK_FIELDS = ['title', 'description', 'image', 'price', 'color', 'shimmer', 'musicUrl', 'musicOff', 'saleUntil', 'premiereAt', 'schedule', 'retired', 'odds']; // b473: свои шансы редкостей стандартного пака уезжают в комнату тем же patch-механизмом"))

# ── 3. крутка с учётом весов пака и нулевых весов ───────────────────────────
a = '''        function pickWeightedRarity(rarities) {
            const total = rarities.reduce((s, r) => s + (RARITY_WEIGHTS[r] || 1), 0);
            let roll = Math.random() * total;
            for (const r of rarities) {
                roll -= (RARITY_WEIGHTS[r] || 1);
                if (roll <= 0) return r;
            }
            return rarities[rarities.length - 1];
        }'''
assert APP.count(a) == 1
PAIRS.append(('assets/app.js', 1, a, '''        // b473: веса приезжают аргументом (веса конкретного пака). НУЛЕВОЙ вес
        // значит «редкости в паке не бывает» — раньше «|| 1» превращал ноль в
        // единицу и запрет молча не работал. Если нули стоят везде (битый
        // конфиг), крутим равномерно, чтобы пак не перестал открываться.
        function pickWeightedRarity(rarities, weights) {
            const W = weights || RARITY_WEIGHTS;
            let list = rarities.filter(r => (Number(W[r]) || 0) > 0);
            let uniform = false;
            if (!list.length) { list = rarities; uniform = true; }
            const w = r => (uniform ? 1 : (Number(W[r]) || 0));
            const total = list.reduce((s, r) => s + w(r), 0);
            let roll = Math.random() * total;
            for (const r of list) {
                roll -= w(r);
                if (roll <= 0) return r;
            }
            return list[list.length - 1];
        }'''))

a = '''        function rollCardFromPack(packCards, forceEpicPlus = false) {
            let pool = packCards;
            if (forceEpicPlus) {
                const ep = packCards.filter(c => c.rarity === 'epic' || c.rarity === 'legendary');
                if (ep.length) pool = ep;
            }
            const availRarities = RARITY_ORDER.filter(r => pool.some(c => c.rarity === r));
            const rarity = pickWeightedRarity(availRarities);
            const ofRarity = pool.filter(c => c.rarity === rarity);
            return ofRarity[Math.floor(Math.random() * ofRarity.length)];
        }'''
assert APP.count(a) == 1
PAIRS.append(('assets/app.js', 1, a, '''        function rollCardFromPack(packCards, forceEpicPlus = false, pack) {
            let pool = packCards;
            if (forceEpicPlus) {
                const ep = packCards.filter(c => c.rarity === 'epic' || c.rarity === 'legendary');
                if (ep.length) pool = ep;
            }
            // b473: свои веса пака. Пак мог не доехать третьим аргументом (колесо,
            // старые вызовы) — находим его по packId первой карты.
            const pk = pack || ((state.packs || []).find(p => p && p.id === ((packCards[0] || {}).packId)) || null);
            const W = packOddsOf(pk);
            let availRarities = RARITY_ORDER.filter(r => pool.some(c => c.rarity === r) && (Number(W[r]) || 0) > 0);
            if (!availRarities.length) availRarities = RARITY_ORDER.filter(r => pool.some(c => c.rarity === r)); // гарант epic+ при нулевых весах всё равно даёт epic+
            const rarity = pickWeightedRarity(availRarities, W);
            const ofRarity = pool.filter(c => c.rarity === rarity);
            return ofRarity[Math.floor(Math.random() * ofRarity.length)];
        }'''))

# ── 4. показ шансов — из весов пака ─────────────────────────────────────────
a = '''        function getPackOdds(pack) {
            const cards = state.cards.filter(c => c.packId === pack.id);
            const present = RARITY_ORDER.filter(r => cards.some(c => c.rarity === r));
            const total = present.reduce((s, r) => s + RARITY_WEIGHTS[r], 0);
            return present.map(r => {
                const p = RARITY_WEIGHTS[r] / total;
                return { r, pct: Math.round((1 - Math.pow(1 - p, PACK_CARDS)) * 100), one: Math.round(p * 100) };
            });
        }'''
assert APP.count(a) == 1
PAIRS.append(('assets/app.js', 1, a, '''        function getPackOdds(pack) {
            const cards = state.cards.filter(c => c.packId === pack.id);
            const W = packOddsOf(pack);   // b473: свои веса пака, иначе заводские
            // редкости с нулевым весом не показываем: их в паке не бывает
            let present = RARITY_ORDER.filter(r => cards.some(c => c.rarity === r) && (Number(W[r]) || 0) > 0);
            if (!present.length) present = RARITY_ORDER.filter(r => cards.some(c => c.rarity === r));
            const total = present.reduce((s, r) => s + (Number(W[r]) || 1), 0);
            return present.map(r => {
                const p = (Number(W[r]) || 1) / total;
                return { r, pct: Math.round((1 - Math.pow(1 - p, PACK_CARDS)) * 100), one: Math.round(p * 100) };
            });
        }'''))

# ── 5. вызовы крутки передают пак ───────────────────────────────────────────
a = "            const card = rollCardFromPack(packCards);"
assert APP.count(a) == 1
PAIRS.append(('assets/app.js', 1, a, "            const card = rollCardFromPack(packCards, false, pack);   // b473: веса этого пака"))
a = "            for (let i = 0; i < PACK_CARDS; i++) rolled.push(rollCardFromPack(packCards));   // b472"
assert APP.count(a) == 1
PAIRS.append(('assets/app.js', 1, a, "            for (let i = 0; i < PACK_CARDS; i++) rolled.push(rollCardFromPack(packCards, false, pack));   // b472+b473"))
a = "                rolled[PACK_CARDS - 1] = rollCardFromPack(packCards, true);   // b472"
assert APP.count(a) == 1
PAIRS.append(('assets/app.js', 1, a, "                rolled[PACK_CARDS - 1] = rollCardFromPack(packCards, true, pack);   // b472+b473"))

# ── 6. форма пака: чтение/запись/превью весов ───────────────────────────────
UI = '''        // ============ b473: СВОИ ШАНСЫ РЕДКОСТЕЙ У ПАКА (форма Студии) ============
        function packOddsInputs() {
            return RARITY_ORDER.map(r => document.getElementById('pack-odds-' + r));
        }
        // null  — все поля пустые или значения совпадают с заводскими (поле не создаём)
        // undefined — ввод испорчен, тост уже показан, сохранение отменяется
        function packOddsReadForm() {
            const els = packOddsInputs();
            const vals = els.map(el => String(el ? el.value : '').trim());
            if (vals.every(v => v === '')) return null;
            const out = {};
            let any = false;
            for (let i = 0; i < RARITY_ORDER.length; i++) {
                const raw = vals[i];
                const v = raw === '' ? 0 : Number(raw);
                if (!isFinite(v) || v < 0 || v > MKT_ODDS_MAX) {
                    showToast('Шансы редкостей: нужно целое число от 0 до ' + MKT_ODDS_MAX + ' (или оставьте поле пустым)', 'error');
                    return undefined;
                }
                out[RARITY_ORDER[i]] = Math.round(v);
                if (out[RARITY_ORDER[i]] > 0) any = true;
            }
            if (!any) {
                showToast('Шансы редкостей: хотя бы один вес должен быть больше нуля — иначе пак не сможет крутиться. Или оставьте все четыре поля пустыми', 'error');
                return undefined;
            }
            return packOddsSameAsDefault(out) ? null : out;
        }
        function packOddsFill(odds) {
            RARITY_ORDER.forEach(r => {
                const el = document.getElementById('pack-odds-' + r);
                if (el) el.value = String(odds ? (odds[r] === undefined ? 0 : odds[r]) : RARITY_WEIGHTS[r]);
            });
            packOddsPreview();
        }
        function packOddsPreview() {
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
        }
        function resetPackForm() {'''
a = "        function resetPackForm() {"
assert APP.count(a) == 1
PAIRS.append(('assets/app.js', 1, a, UI))

a = '''            updatePackMusicHint(); // b20
            renderPackFormPickers();
        }'''
assert APP.count(a) == 1
PAIRS.append(('assets/app.js', 1, a, '''            updatePackMusicHint(); // b20
            renderPackFormPickers();
            packOddsFill(null);   // b473: веса возвращаются к заводским вместе с остальной формой
        }'''))

# ── 7. handleSavePack: читаем и пишем odds ──────────────────────────────────
a = '''            const crimp = PACK_CRIMPS[packFormCrimp] ? packFormCrimp : 'zip'; // b448
            // b19: музыка вскрытия — своя ссылка на mp3 + флаг «играть»'''
assert APP.count(a) == 1
PAIRS.append(('assets/app.js', 1, a, '''            const crimp = PACK_CRIMPS[packFormCrimp] ? packFormCrimp : 'zip'; // b448
            // b473: свои веса редкостей. null = заводские (поле не создаём),
            // undefined = ввод испорчен и сохранение отменяется
            const oddsRaw = packOddsReadForm();
            if (oddsRaw === undefined) return;
            // b19: музыка вскрытия — своя ссылка на mp3 + флаг «играть»'''))

a = '''                    pack.crimp = crimp; // b448: кромка (зубчики) — тоже в каталог'''
assert APP.count(a) == 1
PAIRS.append(('assets/app.js', 1, a, '''                    pack.crimp = crimp; // b448: кромка (зубчики) — тоже в каталог
                    if (oddsRaw) pack.odds = oddsRaw; else delete pack.odds; // b473'''))

a = '''                if (premTs) newPack.premiereAt = premTs; // b165: до премьеры пак виден как «Скоро»'''
assert APP.count(a) == 1
PAIRS.append(('assets/app.js', 1, a, '''                if (premTs) newPack.premiereAt = premTs; // b165: до премьеры пак виден как «Скоро»
                if (oddsRaw) newPack.odds = oddsRaw;     // b473: свои шансы редкостей'''))

# ── 8. editPack: заполняем поля весов ───────────────────────────────────────
a = '''            document.getElementById('pack-price').value = pack.price;'''
assert APP.count(a) == 1
PAIRS.append(('assets/app.js', 1, a, '''            document.getElementById('pack-price').value = pack.price;
            packOddsFill(pack.odds || null); // b473: свои шансы редкостей пака'''))

# ── 9. разметка формы: четыре поля весов ────────────────────────────────────
INP = 'min="0" max="1000000" step="1" oninput="packOddsPreview()" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2 py-2 text-[12px] font-bold focus:outline-none focus:border-violet-500"'
PANEL = '''                        <!-- b473: свои шансы редкостей у пака. Это ВЕСА, а не
                             проценты: крутка нормирует их сама, как и показ. -->
                        <div class="flex flex-col min-w-0 sm:col-span-2">
                            <label class="block text-[11px] font-medium text-slate-400 mb-1">Шансы редкостей (веса)</label>
                            <div class="grid grid-cols-4 gap-2">
                                <input type="number" id="pack-odds-common" value="60" ''' + INP + ''' placeholder="60" title="Обычная">
                                <input type="number" id="pack-odds-rare" value="25" ''' + INP + ''' placeholder="25" title="Редкая">
                                <input type="number" id="pack-odds-epic" value="12" ''' + INP + ''' placeholder="12" title="Эпическая">
                                <input type="number" id="pack-odds-legendary" value="3" ''' + INP + ''' placeholder="3" title="Легендарная">
                            </div>
                            <p id="pack-odds-preview" class="text-[10px] text-slate-500 mt-1"></p>
                            <p class="text-[10px] text-slate-600 mt-0.5">Веса, а не проценты: 60/25/12/3 — заводские. Ноль = редкости в паке не бывает. Оставьте все четыре поля пустыми — вернутся заводские. Чипы шансов на паке в магазине пересчитаются сами.</p>
                        </div>
'''
a = '''                            <div id="pack-color-picker" class="grid grid-cols-4 gap-1 max-w-sm"><!-- b272: компакт --><!-- свотчи цветов --></div>
                        </div>
                        </div>'''
assert IDX.count(a) == 1
PAIRS.append(('index.html', 1, a, '''                            <div id="pack-color-picker" class="grid grid-cols-4 gap-1 max-w-sm"><!-- b272: компакт --><!-- свотчи цветов --></div>
                        </div>
''' + PANEL + '''                        </div>'''))

# ── контроль и сборка файла патча ───────────────────────────────────────────
docs = {'assets/app.js': APP, 'index.html': IDX}
for rel, cnt, old, new in PAIRS:
    txt = docs[rel]
    if txt.count(old) != cnt:
        raise SystemExit('ЯКОРЬ %s: ждал %d, нашёл %d → %r' % (rel, cnt, txt.count(old), old[:70]))
    docs[rel] = txt.replace(old, new, 1)
print('все %d якорей сошлись' % len(PAIRS))


def q(s):
    assert "'''" not in s and not s.rstrip('\n').endswith('\\'), 'небезопасная строка'
    return "'''" + s + "'''"


body = '\n\n'.join('PAIRS.append((%s, %d,\n              %s,\n              %s))' % (repr(r), c, q(o), q(n)) for r, c, o, n in PAIRS)

script = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b473: у каждого пака свои шансы редкостей (веса в форме пака).

Просьба владельца: «у каждаго пака свая процентность должна быть». До b473 все
паки крутились по одной таблице RARITY_WEIGHTS {common 60, rare 25, epic 12,
legendary 3}, а чипы на паке (b472) показывали её же, пересчитанную «в пак».

Как стало
---------
1. У пака появилось необязательное поле odds = {common,rare,epic,legendary} —
   ВЕСА, не проценты. Крутка и показ читают его через packOddsOf() (3068):
   целые >= 0, потолок MKT_ODDS_MAX=1e6, сумма > 0; нет поля или мусор —
   заводская таблица. Нормализация обязательна: поле приходит из общего
   документа комнаты, куда пишет кто угодно.
2. pickWeightedRarity(rarities, weights) принимает веса аргументом. НУЛЕВОЙ вес
   теперь действительно запрещает редкость: раньше «RARITY_WEIGHTS[r] || 1»
   превращало 0 в 1 и запрет молча не работал. Если нули стоят везде (битый
   конфиг), крутка равномерно выбирает из присутствующих редкостей — пак не
   перестаёт открываться.
3. rollCardFromPack(packCards, forceEpicPlus, pack) принимает пак третьим
   аргументом; если он не доехал (колесо, внешние вызовы) — ищется по packId
   первой карты. Вызовы в rollPackCards (цикл и гарант epic+) и в
   wheelGrantCard пак передают. Гарант epic+ при нулевых весах epic/legendary
   всё равно даёт epic+: пул принудительного ролла не фильтруется по весам.
4. getPackOdds() (показ чипов, b472) считает из весов пака; редкости с нулевым
   весом не показываются вовсе — их в паке не бывает.
5. Форма пака в Студии: четыре поля «Шансы редкостей (веса)» с живым превью
   «N% на карту / M% в паке» под ними (packOddsPreview). Все четыре пустые =
   заводские; значения, совпавшие с заводскими, в каталог не пишутся (поле не
   создаётся). Ноль во всех четырёх или мусор — сохранение отменяется с тостом,
   молча пак не портится. editPack() заполняет поля из pack.odds,
   resetPackForm() возвращает заводские.
6. Стандартные (вшитые) паки: 'odds' добавлен в STD_PACK_FIELDS, поэтому правка
   весов стандартного пака уезжает в комнату тем же patch-механизмом
   (cloudStdDiff/cloudStdTouch/applyStdPatchTo), что и цена с расписанием, и
   так же откатывается к базе, когда правку снимают (b173).

app.js и index.html менялись — тег сборки nxmob216 -> nxmob217.

Проверка/применение:
    python3 tools/_b473_patch.py --check
    python3 tools/_b473_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob216'
TAG_NEW = 'nxmob217'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

''' + body + '''


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
        o, n = old.strip('\\n'), new.strip('\\n')
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
        print('b473: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b473: у каждого пака свои шансы редкостей; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
'''

dst = os.path.join(ROOT, 'tools/_b473_patch.py')
io.open(dst, 'w', encoding='utf-8', newline='').write(script)
print('записан tools/_b473_patch.py,', len(script.splitlines()), 'строк')
