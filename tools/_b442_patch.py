#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b442: у пользователей НЕ ПРОПАДАЮТ купленные карточки.

Заявка владельца: «проверь почему у пользователей пропадают купленые каточки».

Диагноз (по коду assets/app.js, все места найдены и проверены):

  1. ЗЕРКАЛО КОМНАТЫ У УЧАСТНИКА (b35, cloudMerge). Участник ничего не
     публикует, поэтому «чего нет в каталоге комнаты — того нет и у него».
     Вместе с определением карты вызывался dropCardRefs(id), который стирал
     state.collection[id]. Купленная на бирже карта (marketBuy добавляет
     определение локально: isNewDef → state.cards.push) или карта, которой нет
     в каталоге комнаты, удалялась у участника на ближайшем cloudPull.
     Архив nexus_guest_archive при этом НИКТО НЕ ЧИТАЕТ: cloudGuestArchive()
     вызывается ровно один раз — внутри того же cloudMerge. Возврата нет.
     cloudRoomTrust() возвращает true для любой комнаты без пароля, то есть
     зеркало работает практически у всех участников.

  2. КВОТА localStorage (saveState). В запасной ветке сохранялись
     coins/cards/packs, а nexus_collection — НЕТ. На переполненной квоте
     (base64-арты в nexus_cards) получалось: монеты списаны и записаны,
     купленная карта — нет.

  3. ЭСКРОУ БИРЖИ (b336). marketListCardFor убирает копию из коллекции в лот.
     Кэш виденных лотов nexus_market_cache жил 10 минут И пересобирался
     исключительно из того, что сейчас в облаке: лот, потерянный при гонке
     записей textdb, выпадал из кэша на той же синхронизации — карта не
     возвращалась никогда, а квитанция могла не дойти (ledger режется до 60).

  4. ВЕЧНЫЕ НАДГРОБИЯ ПАКОВ (b370/b374, profMergeState). myRemoved заносил в
     ptomb любой пак, которого не оказалось в state.packs на момент синка.
     Пак мог пропасть ВРЕМЕННО (квота, зеркало, откат документа, импорт сейва)
     — а надгробие уезжало в облако, и пак с картами исчезал уже на всех
     устройствах навсегда: обратного хода у ptomb нет.

Лечение:
  1. зеркало не трогает карты и паки, которыми игрок ВЛАДЕЕТ (cardCopies > 0
     или карта в колоде); счётчик sum.kept видно в сводке слияния;
  2. nexus_collection пишется ПЕРВЫМ и сохраняется даже в запасной ветке,
     тяжёлые base64-арты в аварийном режиме урезаются; добавлена теневая копия
     коллекции (не чаще раза в 10 минут) и функция возврата nxRescueCollection();
  3. свой эскроу-лот держится в кэше 72 часа и не выпадает из него, даже если
     облако лот потеряло; чужие — как раньше, 10 минут;
  4. пак, из которого у устройства есть купленные карты, в надгробия не уходит;
  5. тег сборки nxmob171 -> nxmob172 (index.html ?v= x8, sw.js VERSION,
     tools/build.py BUILD_TAG) — иначе sw.js отдаст игрокам старую копию.

Откат: git checkout assets/app.js index.html sw.js tools/build.py

Проверка/применение:
    python3 tools/_b442_patch.py --check   # только проверить, что всё легло
    python3 tools/_b442_patch.py           # применить (идемпотентно)

После применения: python3 tools/build.py --no-media   (или пересборка монолита
по вашей обычной схеме) и обязательно коммит — патч правит assets/app.js.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = []

# ── 1. Зеркало комнаты: купленные карты не удаляем ───────────────────────────
PAIRS.append(('app.js: зеркало участника не трогает купленные карты', """
                state.cards.slice().forEach(c => {
                    if (!c || !c.id || STANDARD_IDS[c.id] || inRoomC[c.id]) return;
                    archive.cards.push(c); archived = true;
                    dropCardRefs(c.id);
""", """
                // b442: КУПЛЕННЫЕ КАРТЫ ЗЕРКАЛОМ НЕ УДАЛЯЮТСЯ.
                // Зеркало (b35) придумано против расхождения КАТАЛОГА — «у создателя
                // 1 пак, у игроков 5». Но вместе с определением карты оно вызывало
                // dropCardRefs(id), который стирал state.collection[id]: участник,
                // купивший карту на бирже (marketBuy добавляет определение локально)
                // или вытащивший её из пака, терял карту на ближайшем cloudPull,
                // а архив nexus_guest_archive не читал никто — возврата не было.
                // Карта, которой игрок владеет или которая в его колоде, остаётся.
                const ownedHere = id => {
                    try { return cardCopies(id) > 0 || (state.deck || []).indexOf(id) >= 0; } catch (e) { return false; }
                };
                state.cards.slice().forEach(c => {
                    if (!c || !c.id || STANDARD_IDS[c.id] || inRoomC[c.id]) return;
                    if (ownedHere(c.id)) { sum.kept = (sum.kept || 0) + 1; return; }
                    archive.cards.push(c); archived = true;
                    dropCardRefs(c.id);
"""))

PAIRS.append(('app.js: зеркало не удаляет пак с купленными картами', """
                state.packs.slice().forEach(p => {
                    if (!p || !p.id || STANDARD_IDS[p.id] || inRoomP[p.id]) return;
                    archive.packs.push(p); archived = true;
                    dropPack(p.id); sum.mirror++; changed = true;
                });
""", """
                state.packs.slice().forEach(p => {
                    if (!p || !p.id || STANDARD_IDS[p.id] || inRoomP[p.id]) return;
                    // b442: dropPack() чистит и карты пака, и collection по ним,
                    // поэтому пак, из которого у игрока что-то куплено, не трогаем
                    try {
                        if (state.cards.some(c => c && c.packId === p.id && cardCopies(c.id) > 0)) { sum.kept = (sum.kept || 0) + 1; return; }
                    } catch (e) {}
                    archive.packs.push(p); archived = true;
                    dropPack(p.id); sum.mirror++; changed = true;
                });
"""))

# ── 2. saveState: коллекция первой и всегда ──────────────────────────────────
PAIRS.append(('app.js: saveState — коллекция пишется первой', """
                LS.setItem('nexus_coins', state.coins);
                LS.setItem('nexus_packs', JSON.stringify(state.packs.map(lightPack)));
                LS.setItem('nexus_cards', JSON.stringify(state.cards.map(lightCard)));
                LS.setItem('nexus_collection', JSON.stringify(state.collection));
""", """
                // b442: коллекция — ПЕРВОЙ. Если квота кончится на середине
                // записи, главное («игрок чем-то владеет») уже сохранено.
                LS.setItem('nexus_collection', JSON.stringify(state.collection));
                nxColShadowMaybe(); // b442: теневая копия для возврата потерь
                LS.setItem('nexus_coins', state.coins);
                LS.setItem('nexus_packs', JSON.stringify(state.packs.map(lightPack)));
                LS.setItem('nexus_cards', JSON.stringify(state.cards.map(lightCard)));
"""))

PAIRS.append(('app.js: saveState — запасная ветка больше не теряет коллекцию', """
            } catch (err) {
                // Квота localStorage или private-режим: игра НЕ должна падать
                try {
                    LS.setItem('nexus_coins', state.coins);
                    LS.setItem('nexus_cards', JSON.stringify(state.cards.map(lightCard)));
                    LS.setItem('nexus_packs', JSON.stringify(state.packs.map(lightPack)));
                } catch (err2) { /* работаем без сохранений */ }
            }
""", """
            } catch (err) {
                // Квота localStorage или private-режим: игра НЕ должна падать.
                // b442: раньше здесь сохранялись coins/cards/packs, а
                // nexus_collection — НЕТ. На переполненной квоте (base64-арты в
                // nexus_cards) выходило: монеты списаны и записаны, а купленная
                // карта — нет. После перезагрузки покупки просто не было.
                // Теперь коллекция пишется первой, а тяжёлые арты урезаются.
                try { LS.setItem('nexus_collection', JSON.stringify(state.collection)); } catch (e0) {}
                try {
                    LS.setItem('nexus_coins', state.coins);
                    LS.setItem('nexus_packs', JSON.stringify(state.packs.map(lightPack)));
                    LS.setItem('nexus_cards', JSON.stringify(state.cards.map(c => {
                        const l = lightCard(c);
                        return (l && typeof l.image === 'string' && l.image.indexOf('data:') === 0)
                            ? Object.assign({}, l, { image: '' }) : l;
                    })));
                } catch (err2) {
                    try { LS.setItem('nexus_collection', JSON.stringify(state.collection)); } catch (e3) {}
                    try { LS.setItem('nexus_coins', state.coins); } catch (e4) {}
                    try { nxCrashLog('saveState: квота localStorage, коллекция сохранена отдельно'); } catch (e5) {}
                }
            }
"""))

# ── 3. Теневая копия коллекции и возврат потерянного ─────────────────────────
PAIRS.append(('app.js: теневая копия коллекции + nxRescueCollection', """
        function cloudGuestArchiveSave(a) {
            try { LS.setItem('nexus_guest_archive', JSON.stringify({ packs: (a.packs || []).slice(-100), cards: (a.cards || []).slice(-300) })); } catch (e) {}
        }
""", """
        function cloudGuestArchiveSave(a) {
            try { LS.setItem('nexus_guest_archive', JSON.stringify({ packs: (a.packs || []).slice(-100), cards: (a.cards || []).slice(-300) })); } catch (e) {}
        }
        // ------------------- b442: СПАСЕНИЕ КОЛЛЕКЦИИ -------------------
        // Теневая копия коллекции (не чаще раза в 10 минут) и ручной возврат.
        // Нужна, потому что потери копились месяцами и причинами были разные:
        // зеркало комнаты, квота localStorage, эскроу биржи, вечные надгробия.
        // Возврат ДЕЛАЕТСЯ ВРУЧНУЮ: автоматический MAX-мердж воскресил бы
        // честно проданные карты.
        let nxColShadowAt = 0;
        function nxColShadowMaybe() {
            try {
                const t = Date.now();
                if (t - nxColShadowAt < 600000) return;
                nxColShadowAt = t;
                const cur = state.collection || {};
                const n = Object.keys(cur).length;
                if (!n) return;
                LS.setItem('nx_col_shadow', JSON.stringify({ t: t, n: n, c: cur }));
            } catch (e) {}
        }
        function nxColShadow() {
            try { return JSON.parse(LS.getItem('nx_col_shadow') || 'null'); } catch (e) { return null; }
        }
        /** Сколько карт исчезло относительно теневой копии (диагноз). */
        function nxRescueReport() {
            const sh = nxColShadow();
            const cur = state.collection || {};
            if (!sh || !sh.c) return { shadow: 0, current: Object.keys(cur).length, lost: 0 };
            let lost = 0;
            const lostIds = [];
            for (const id in sh.c) {
                const a = Math.floor(Number(sh.c[id]) || 0), b = Math.floor(Number(cur[id]) || 0);
                if (a > b) { lost += (a - b); lostIds.push(id); }
            }
            return { shadow: Object.keys(sh.c).length, current: Object.keys(cur).length, lost: lost, lostIds: lostIds.slice(0, 40), at: sh.t };
        }
        /**
         * Вернуть потерянные копии из теневой копии (MAX на ключ).
         * Возвращает число восстановленных копий. Вызывать из консоли:
         *     nxRescueReport()      — что пропало
         *     nxRescueCollection()  — вернуть
         */
        function nxRescueCollection() {
            const sh = nxColShadow();
            if (!sh || !sh.c) { try { showToast('Теневая копия пуста — восстанавливать нечего', 'info'); } catch (e) {} return 0; }
            let back = 0;
            for (const id in sh.c) {
                const a = Math.floor(Number(sh.c[id]) || 0);
                const b = Math.floor(Number((state.collection || {})[id]) || 0);
                if (a > b) { state.collection[id] = a; back += (a - b); }
            }
            // возвращённым картам нужны определения: достаём из архива зеркала
            let defs = 0;
            try {
                const arc = cloudGuestArchive();
                const have = {};
                (state.cards || []).forEach(c => { if (c && c.id) have[c.id] = 1; });
                const left = [];
                (arc.cards || []).forEach(c => {
                    if (c && c.id && !have[c.id] && state.collection[c.id]) { state.cards.push(c); have[c.id] = 1; defs++; }
                    else left.push(c);
                });
                if (defs) { arc.cards = left; cloudGuestArchiveSave(arc); }
            } catch (e) {}
            if (back || defs) {
                try { cardsSortNorm(); } catch (e) {}
                saveState();
                try { refreshVisibleTabs(); } catch (e) {}
                try { profSyncSoon(); } catch (e) {}
                try { showToast('🛟 Возвращено: ' + back + ' ' + (back === 1 ? 'копия' : 'копий') + (defs ? ', определений карт: ' + defs : ''), 'success'); } catch (e) {}
            }
            return back;
        }
        /** Вернуть в каталог ВСЁ, что зеркало сложило в архив (определения карт). */
        function nxRestoreArchive() {
            let defs = 0;
            try {
                const arc = cloudGuestArchive();
                const have = {};
                (state.cards || []).forEach(c => { if (c && c.id) have[c.id] = 1; });
                (arc.cards || []).forEach(c => { if (c && c.id && !have[c.id]) { state.cards.push(c); have[c.id] = 1; defs++; } });
                const haveP = {};
                (state.packs || []).forEach(p => { if (p && p.id) haveP[p.id] = 1; });
                (arc.packs || []).forEach(p => { if (p && p.id && !haveP[p.id]) { state.packs.push(p); haveP[p.id] = 1; defs++; } });
                if (defs) { saveState(); try { refreshVisibleTabs(); } catch (e) {} }
            } catch (e) {}
            return defs;
        }
        try {
            window.nxRescueReport = nxRescueReport;
            window.nxRescueCollection = nxRescueCollection;
            window.nxRestoreArchive = nxRestoreArchive;
        } catch (e) {}
"""))

# ── 4. Эскроу биржи: свой лот не теряется ────────────────────────────────────
PAIRS.append(('app.js: кэш лотов — свой эскроу живёт 72 часа', """
                    if (!e || !e.l || nowM - (e.t || 0) > 600000) continue;
""", """
                    if (!e || !e.l) continue;
                    // b442: СВОЙ эскроу-лот ждём 72 часа, чужой — 10 минут, как было.
                    // В эскроу копия уходит из коллекции (marketSetCollection),
                    // поэтому потеря своего лота = потеря карты безвозвратно.
                    if (nowM - (e.t || 0) > ((e.l.sid === cloudDeviceId()) ? 259200000 : 600000)) continue;
"""))

PAIRS.append(('app.js: кэш лотов не пересобирается только из облака', """
                const nc = {};
                CLOUD.market.forEach(l => { if (l && l.id) nc[l.id] = { l: l, t: nowM }; });
                LS.setItem('nexus_market_cache', JSON.stringify(nc));
""", """
                // b442: кэш больше не пересобирается «только из того, что сейчас в
                // облаке». Раньше лот, потерянный при гонке записей textdb, выпадал
                // из кэша на той же синхронизации, и карта, ушедшая в эскроу, не
                // возвращалась никогда (квитанция тоже могла не дойти: ledger
                // режется до 60 записей). Свои лоты держим 72 часа.
                const nc = {};
                const myDeviceId = cloudDeviceId();
                CLOUD.market.forEach(l => { if (l && l.id) nc[l.id] = { l: l, t: nowM }; });
                for (const cid0 in mcache) {
                    const e0 = mcache[cid0];
                    if (!e0 || !e0.l || nc[cid0]) continue;
                    if (removedIds[cid0] || soldIds['sale-' + cid0]) continue;
                    const age = nowM - (e0.t || 0);
                    if (e0.l.sid === myDeviceId ? age <= 259200000 : age <= 600000) nc[cid0] = e0;
                }
                LS.setItem('nexus_market_cache', JSON.stringify(nc));
"""))

# ── 5. Надгробия паков: не вечные для чужих потерь ───────────────────────────
PAIRS.append(('app.js: пак с купленными картами не уходит в надгробия', """
            const myRemoved = packsnap ? packsnap.filter(id => curPackIds.indexOf(id) < 0) : [];
""", """
            // b442: пак, из которого у этого устройства есть КУПЛЕННЫЕ карты, в
            // надгробия не уходит. Раньше любое временное отсутствие пака в
            // state.packs (квота localStorage, зеркало комнаты, откат документа
            // textdb, импорт сейва) навсегда заносило пак в ptomb — а обратного
            // хода у надгробия нет: пак вместе с картами исчезал на всех
            // устройствах профиля.
            const myRemoved = packsnap ? packsnap.filter(id => curPackIds.indexOf(id) < 0
                && !(state.cards || []).some(c => c && c.packId === id && cardCopies(c.id) > 0)) : [];
"""))

TAG_OLD = 'nxmob171'
TAG_NEW = 'nxmob172'
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
        assert old.strip() in txt, 'b442: не найден якорь: %s' % label
        assert txt.count(old.strip()) == 1, 'b442: якорь не уникален: %s (%d)' % (label, txt.count(old.strip()))
        files[rel] = txt.replace(old.strip(), new.strip(), 1)
    for rel, txt in files.items():
        write(rel, txt)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b442: не найден тег %s в %s' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b442: применено')


def check():
    problems = []
    for label, old, new in PAIRS:
        rel = 'index.html' if label.startswith('index.html') else 'assets/app.js'
        txt = read(rel)
        if new.strip() not in txt:
            problems.append('%s: нет нового блока: %s' % (rel, label))
    app = read('assets/app.js')
    for extra in ('const ownedHere = id =>', 'function nxColShadowMaybe(', 'function nxRescueCollection(',
                  'function nxRestoreArchive(', 'nxColShadowMaybe(); // b442',
                  '259200000 : 600000)) continue;', 'const myDeviceId = cloudDeviceId();',
                  "&& !(state.cards || []).some(c => c && c.packId === id && cardCopies(c.id) > 0)) : [];"):
        if extra not in app:
            problems.append('app.js: нет %r' % extra)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не %s' % (rel, TAG_NEW))
    if problems:
        print('b442 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b442 --check: всё на месте (зеркало не трогает купленное, коллекция пишется первой, '
          'теневая копия + nxRescueCollection, эскроу 72 ч, надгробия паков, тег %s)' % TAG_NEW)


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
