#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b375: порядок карт — порядок владельца (нумерация ord + детерминированная сортировка).

Применяет одинаковые old->new правки к assets/app.js (LF) и tools/source-index.html (CRLF).
Каждый old обязан встретиться ровно один раз, иначе скрипт ничего не пишет.
После: python3 tools/sync_build_blocks.py && python3 tools/build.py --no-media
"""
import io, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EDITS = []          # общие для assets/app.js и монолита
EDITS_APP = []      # только assets/app.js (после медиа-трансформаций build.py)
EDITS_MONO = []     # только tools/source-index.html (до медиа-трансформаций)

# 1) помощники порядка — сразу после lightPack
EDITS.append((
'''        function lightPack(p) {
            return (p.image && SCOOBY_PACK_REF[p.id] && SCOOBY_PACK_REF[p.id] === p.image) ? Object.assign({}, p, { image: 'ref:' + p.id }) : p; // b323
        }
''',
'''        function lightPack(p) {
            return (p.image && SCOOBY_PACK_REF[p.id] && SCOOBY_PACK_REF[p.id] === p.image) ? Object.assign({}, p, { image: 'ref:' + p.id }) : p; // b323
        }

        // b375: порядок карт принадлежит владельцу: карты всегда стоят в порядке
        // создания/загрузки. Каждой карте проставляется явный номер `ord` (ключ
        // сортировки в шкале времени создания). Раньше слияние синхронизации
        // пересобирало state.cards из объединения ключей «облако-first» — порядок
        // загрузки перемешивался («я загружал по-своему, а их перемешали»).
        function cardSortKey(c) {
            if (!c) return Infinity;
            if (c.ord > 0) return c.ord;
            const m = /^card-(\\d+)(?:-(\\d+))?/.exec(String(c.id || ''));
            if (m) return Number(m[1]) + Number(m[2] || 0) / 1000; // время создания + индекс в партии загрузки
            return Infinity; // непарсящиеся — в конец (сортировка устойчивая)
        }
        function cardSortCmp(a, b) {
            const ka = cardSortKey(a), kb = cardSortKey(b);
            if (ka !== kb) return ka < kb ? -1 : 1;
            const ia = String((a && a.id) || ''), ib = String((b && b.id) || '');
            return ia < ib ? -1 : (ia > ib ? 1 : 0); // детерминированный тай-брейк: порядок одинаков везде
        }
        function nextCardOrd() { // следующий номер — всегда в конец текущего порядка
            let mx = 0;
            (state.cards || []).forEach(c => { const k = cardSortKey(c); if (isFinite(k) && k > mx) mx = k; });
            return (mx || Date.now()) + 10;
        }
        function cardsSortNorm() { // сортировка + явный номер каждой карте (порядок больше не зависит от парсинга id); возвращает true, если проставляла номера
            if (!Array.isArray(state.cards)) return false;
            let touched = false;
            state.cards.sort(cardSortCmp);
            let last = 0;
            state.cards.forEach(c => {
                if (!c || typeof c !== 'object') return;
                if (!(c.ord > 0)) {
                    let v = cardSortKey(c);
                    if (!isFinite(v)) v = (last || Date.now()) + 10;
                    c.ord = v;
                    touched = true;
                }
                last = c.ord;
            });
            return touched;
        }
        function packSortKey(p) {
            if (!p) return Infinity;
            const m = /^pack-(\\d+)/.exec(String(p.id || ''));
            return m ? Number(m[1]) : Infinity;
        }
        function packSortCmp(a, b) {
            const ka = packSortKey(a), kb = packSortKey(b);
            if (ka !== kb) return ka < kb ? -1 : 1;
            const ia = String((a && a.id) || ''), ib = String((b && b.id) || '');
            return ia < ib ? -1 : (ia > ib ? 1 : 0);
        }
        function packsSortNorm() { // b375: порядок паков — тоже порядок создания, а не union синхронизации
            if (Array.isArray(state.packs)) state.packs.sort(packSortCmp);
        }
'''))

# 2) разовая миграция при загрузке — восстановить порядок и проставить номера
EDITS.append((
'''        resolveMediaRefs();

        function saveState() {
''',
'''        resolveMediaRefs();
        // b375: разовая миграция — восстанавливаем порядок создания/загрузки из id
        // карт (card-<время>[-<индекс в партии>]) и проставляем явные номера ord.
        // Дальше порядок хранится в номерах и синхронизацией не перемешивается.
        (function migrateCardOrderB375() {
            try {
                const touched = cardsSortNorm(); packsSortNorm();
                if (touched || LS.getItem('nx_ordmig') !== '1') { LS.setItem('nx_ordmig', '1'); saveState(); }
            } catch (e) {}
        })();

        function saveState() {
'''))

# 3) ord уезжает в комнату вместе с правками стандарта
EDITS.append((
"        const STD_CARD_FIELDS = ['name', 'description', 'rarity', 'image', 'layout', 'aura', 'atk', 'hp', 'musicUrl'];",
"        const STD_CARD_FIELDS = ['name', 'description', 'rarity', 'image', 'layout', 'aura', 'atk', 'hp', 'musicUrl', 'ord', 'ordAt']; // b375: нумерация владельца доезжает до комнаты"))

# 4) массовое создание: порядок загрузки сразу фиксируется номерами
EDITS.append((
'''            const now = Date.now();
            items.forEach((it, i) => {
                state.cards.push({
                    id: 'card-' + now + '-' + i + '-' + Math.floor(Math.random() * 1e4),
                    packId,
''',
'''            const now = Date.now();
            const ordBase = nextCardOrd(); // b375: порядок загрузки сразу фиксируется номерами
            items.forEach((it, i) => {
                state.cards.push({
                    id: 'card-' + now + '-' + i + '-' + Math.floor(Math.random() * 1e4),
                    ord: ordBase + i * 10,
                    packId,
'''))
EDITS.append((
"showToast('✅ Создано карточек: ' + items.length, 'success');",
"showToast('✅ Создано карточек: ' + items.length + ' — порядок загрузки сохранён и закреплён номерами', 'success'); // b375"))

# 5) одиночное создание: следующий номер
EDITS.append((
'''                const newCard = {
                    id: 'card-' + Date.now(),
                    packId,
''',
'''                const newCard = {
                    id: 'card-' + Date.now(),
                    ord: nextCardOrd(), // b375: карта получает следующий номер — порядок не боится синхронизации
                    packId,
'''))

# 6) слияние профиля: порядок определяет нумерация, а не объединение ключей
EDITS.append((
'''            const cm = {};
            ((R && R.cards) || []).forEach(c => { if (c && c.id) cm[c.id] = c; });
            (L.cards || []).forEach(c => { if (c && c.id) cm[c.id] = c; });
            out.packs = Object.keys(pm).map(k => pm[k]);
            out.cards = Object.keys(cm).filter(id => mergedCol[id] > 0).map(id => cm[id]);
''',
'''            const cm = {};
            ((R && R.cards) || []).forEach(c => { if (c && c.id) cm[c.id] = c; });
            (L.cards || []).forEach(c => {
                if (!c || !c.id) return;
                const rc = cm[c.id];
                if (rc && rc.ord > 0) { // b375: номер берётся у стороны, которая ПОСЛЕДНИЙ раз меняла порядок
                    if ((rc.ordAt || 0) > (c.ordAt || 0) || !(c.ord > 0)) { c.ord = rc.ord; c.ordAt = rc.ordAt || c.ordAt || 0; }
                }
                cm[c.id] = c;
            });
            // b375: порядок карт и паков больше не зависит от порядка объединения
            // ключей (раньше облачный порядок перекрывал порядок загрузки владельца)
            out.packs = Object.keys(pm).map(k => pm[k]).sort(packSortCmp);
            out.cards = Object.keys(cm).filter(id => mergedCol[id] > 0).map(id => cm[id]).sort(cardSortCmp);
'''))

# 7) порядок колоды — детерминированный
EDITS.append((
"            out.deck = Object.keys(dk).filter(id => cm[id] && mergedCol[id] > 0);",
"            out.deck = Object.keys(dk).filter(id => cm[id] && mergedCol[id] > 0).sort((x, y) => cardSortCmp(cm[x], cm[y])); // b375"))

# 8) применение слитого состояния
EDITS.append((
'''            if (Array.isArray(s.packs)) state.packs = s.packs;
            if (Array.isArray(s.cards)) state.cards = s.cards;
''',
'''            if (Array.isArray(s.packs)) state.packs = s.packs;
            if (Array.isArray(s.cards)) state.cards = s.cards;
            try { cardsSortNorm(); packsSortNorm(); } catch (e) {} // b375: порядок после слияния — порядок владельца
'''))

# 9) импорт сохранения
EDITS.append((
'''            state.packs = imported.packs;
            state.cards = imported.cards;
''',
'''            state.packs = imported.packs;
            state.cards = imported.cards;
            try { cardsSortNorm(); packsSortNorm(); } catch (e) {} // b375
'''))

# 10) полный сброс
EDITS.append((
'''            state.packs = defaultPacks.map(p => Object.assign({}, p));
            state.cards = defaultCards.map(c => Object.assign({}, c));
''',
'''            state.packs = defaultPacks.map(p => Object.assign({}, p));
            state.cards = defaultCards.map(c => Object.assign({}, c));
            try { cardsSortNorm(); packsSortNorm(); } catch (e) {} // b375
'''))

# 11) комнатная синхронизация
EDITS.append((
'''            return changed ? sum : null;
        }
        function refreshVisibleTabs() {
''',
'''            if (changed) { try { cardsSortNorm(); packsSortNorm(); } catch (e) {} } // b375: досев/удаления не ломают порядок
            return changed ? sum : null;
        }
        function refreshVisibleTabs() {
'''))

# 12) досев стандарта
EDITS.append((
'''            STANDARD_CARDS.forEach(c => {
                if (off[c.id] || off[c.packId]) return;
                if (!state.cards.some(x => x.id === c.id)) { state.cards.push(cloudStdCardClone(c)); added = true; }
            });
            return added;
''',
'''            STANDARD_CARDS.forEach(c => {
                if (off[c.id] || off[c.packId]) return;
                if (!state.cards.some(x => x.id === c.id)) { state.cards.push(cloudStdCardClone(c)); added = true; }
            });
            if (added) { try { cardsSortNorm(); packsSortNorm(); } catch (e) {} } // b375
            return added;
'''))

# 13) покупка на бирже
EDITS.append((
"            if (isNewDef && lot.card) state.cards.push(Object.assign({}, lot.card));",
"            if (isNewDef && lot.card) { state.cards.push(Object.assign({}, lot.card)); try { cardsSortNorm(); } catch (e) {} } // b375: купленная карта встаёт по нумерации создателя"))

# 14) Студия: список карт пака с номерами
EDITS.append((
"pCards.map(studioCardRowHTML).join('')",
"pCards.map((c, ci) => studioCardRowHTML(c, ci + 1, pCards.length)).join('')"))
EDITS.append((
"orphanCards.map(studioCardRowHTML).join('')",
"orphanCards.map((c, ci) => studioCardRowHTML(c, ci + 1, orphanCards.length)).join('')"))

# 15) строка карточки: бейдж номера + кнопки перемещения
EDITS.append((
'''        function studioCardRowHTML(c) {
            const st = getCardStats(c);
            const rarLabel = (typeof RARITY_LABELS_RU !== 'undefined' && RARITY_LABELS_RU[c.rarity]) || c.rarity;
            return `
''',
'''        function studioCardRowHTML(c, pos, total) { // b375: pos — номер карточки в списке (порядок загрузки владельца)
            const st = getCardStats(c);
            const rarLabel = (typeof RARITY_LABELS_RU !== 'undefined' && RARITY_LABELS_RU[c.rarity]) || c.rarity;
            const numBadge = pos ? `<span class="shrink-0 w-7 h-7 rounded-lg bg-violet-500/10 border border-violet-500/30 text-violet-300 text-[10px] font-black flex items-center justify-center" title="Номер карточки: порядок задаётся при создании/загрузке и не перемешивается синхронизацией">№${pos}</span>` : '';
            const moveBtns = (pos && !cloudGuest()) ? `<button onclick="moveCardInPack('${c.id}', -1)" class="w-7 h-7 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 flex items-center justify-center transition${pos <= 1 ? ' opacity-30 pointer-events-none' : ''}" title="Переместить выше"><i class="fa-solid fa-arrow-up text-xs"></i></button>
                        <button onclick="moveCardInPack('${c.id}', 1)" class="w-7 h-7 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 flex items-center justify-center transition${pos >= total ? ' opacity-30 pointer-events-none' : ''}" title="Переместить ниже"><i class="fa-solid fa-arrow-down text-xs"></i></button>` : '';
            return `
'''))
# img-строка в studioCardRowHTML различается: в монолите она до медиа-трансформаций
# build.py (mediaUrl, без data-nx-full/lazy/decoding), в app.js — после.
EDITS_APP.append((
'''                    <div class="flex items-center gap-2.5 min-w-0 truncate">
                        <img src="${mediaThumb(c.image)}" data-nx-full="${mediaUrl(c.image)}" class="w-7 h-10 object-cover rounded" onerror="imgErrorChain(this);" data-card-id="${c.id}" loading="lazy" decoding="async">
''',
'''                    <div class="flex items-center gap-2.5 min-w-0 truncate">
                        ${numBadge}
                        <img src="${mediaThumb(c.image)}" data-nx-full="${mediaUrl(c.image)}" class="w-7 h-10 object-cover rounded" onerror="imgErrorChain(this);" data-card-id="${c.id}" loading="lazy" decoding="async">
'''))
EDITS_MONO.append((
'''                    <div class="flex items-center gap-2.5 min-w-0 truncate">
                        <img src="${mediaUrl(c.image)}" class="w-7 h-10 object-cover rounded" onerror="imgErrorChain(this);" data-card-id="${c.id}">
''',
'''                    <div class="flex items-center gap-2.5 min-w-0 truncate">
                        ${numBadge}
                        <img src="${mediaUrl(c.image)}" class="w-7 h-10 object-cover rounded" onerror="imgErrorChain(this);" data-card-id="${c.id}">
'''))
EDITS.append((
'''                    <div class="flex items-center gap-1.5 flex-wrap justify-end">
                        ${cloudGuest() ? `<span class="h-7 px-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[9px] font-bold flex items-center gap-1" title="Карточка создателя комнаты — только просмотр">''',
'''                    <div class="flex items-center gap-1.5 flex-wrap justify-end">
                        ${moveBtns}
                        ${cloudGuest() ? `<span class="h-7 px-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[9px] font-bold flex items-center gap-1" title="Карточка создателя комнаты — только просмотр">'''))

# 16) ручное перемещение карточки
EDITS.append((
'''        function toggleStudioPackCards(packId) {
''',
'''        // b375: ручное перемещение карточки внутри пака — обмен номерами с соседом.
        // Порядок владельца — закон: он переживает синхронизацию, импорт и комнаты.
        function moveCardInPack(cardId, dir) {
            if (cloudGuard()) return;
            try {
                cardsSortNorm();
                const c = state.cards.find(x => x.id === cardId);
                if (!c) return;
                const list = state.cards.filter(x => x.packId === c.packId);
                const i = list.findIndex(x => x.id === cardId);
                const j = i + (dir > 0 ? 1 : -1);
                if (i < 0 || j < 0 || j >= list.length) return;
                const a = list[i], b = list[j];
                if ((a.ord || 0) === (b.ord || 0)) b.ord = (a.ord || Date.now()) + (dir > 0 ? -1 : 1);
                else { const t = a.ord; a.ord = b.ord; b.ord = t; }
                a.ordAt = b.ordAt = Date.now(); // b375: метка «кто последний менял порядок» — для слияния устройств
                cardsSortNorm();
                saveState();
                cloudStdTouch(a); cloudStdTouch(b); // стандартные карты: порядок доезжает до комнаты
                cloudPublishSoon();
                profSyncSoon(); // b375: перестановка сразу уезжает на другие устройства профиля
                renderStudio();
            } catch (e) {}
        }

        function toggleStudioPackCards(packId) {
'''))


# 17) отпечаток состояния: порядок карт теперь значим (перестановка владельца должна
#     уезжать в облако и перерисовывать вкладки)
EDITS.append((
"                    (state.cards || []).map(c => c && c.id).slice().sort().join('.'),",
"                    (state.cards || []).map(c => c && c.id).join('.'), // b375: порядок карт важен — перестановка владельца должна уезжать в облако"))

# 18) снимок «до слияния» для решения о пуше
EDITS.append((
'''            const myDelta0 = myCoins0 - lastBal;
            return profFetch(key).then(remote => {''',
'''            const myDelta0 = myCoins0 - lastBal;
            const sigMine = profSig(); // b375: состояние ДО слияния: если отличается от последнего опубликованного (например, владелец переставил карты) — надо пушить
            return profFetch(key).then(remote => {'''))

# 19) needPush: смена порядка/состава — повод опубликовать
EDITS.append((
"                const needPush = !!force || !remote || myDelta !== 0 || unionGrew || bookStale || movLost || !pub.myDeltaEmpty; // b370: + дельты коллекции/паков",
"                const needPush = !!force || !remote || myDelta !== 0 || unionGrew || bookStale || movLost || !pub.myDeltaEmpty || sigMine !== (LS.getItem('nx_prof_pushsig') || ''); // b370: + дельты коллекции/паков; b375: + смена порядка карт"))

# 20) запоминаем опубликованный отпечаток после успешного пуша
EDITS.append((
'''                return profPushDoc(key, doc).then(() => {
                    // b367: база = ПРИМЕНЁННЫЙ баланс: всё, что устройство держит''',
'''                return profPushDoc(key, doc).then(() => {
                    try { LS.setItem('nx_prof_pushsig', profSig()); } catch (e) {} // b375: опубликованное состояние (включая порядок карт)
                    // b367: база = ПРИМЕНЁННЫЙ баланс: всё, что устройство держит'''))

# 21) то же после анти-клоббер пуша doc2
EDITS.append((
'''                            return profPushDoc(key, doc2).then(() => {
                                try {''',
'''                            return profPushDoc(key, doc2).then(() => {
                                try {
                                    LS.setItem('nx_prof_pushsig', profSig()); // b375'''))


def apply(text, edits, log):
    for i, (old, new) in enumerate(edits):
        c = text.count(old)
        if c == 1:
            text = text.replace(old, new, 1)
            log.append('  · edit %02d: применено' % (i + 1))
        elif c == 0 and new in text:
            log.append('  · edit %02d: уже применено' % (i + 1))
        else:
            log.append('  · edit %02d: ПРОМАХ (вхождений: %d)' % (i + 1, c))
            return text, False
    return text, True


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'check'
    log = []

    app_path = os.path.join(ROOT, 'assets', 'app.js')
    with io.open(app_path, 'r', encoding='utf-8', newline='') as f:
        app = f.read()
    app2, ok1 = apply(app, EDITS + EDITS_APP, log)
    print('assets/app.js:'); print('\n'.join(log))

    log2 = []
    mono_path = os.path.join(ROOT, 'tools', 'source-index.html')
    with io.open(mono_path, 'r', encoding='utf-8', newline='') as f:
        mono_raw = f.read()
    had_crlf = '\r\n' in mono_raw
    mono = mono_raw.replace('\r\n', '\n') if had_crlf else mono_raw
    mono2, ok2 = apply(mono, EDITS + EDITS_MONO, log2)
    print('tools/source-index.html:'); print('\n'.join(log2))

    if mode == 'check':
        print('check: app=%s mono=%s' % ('OK' if ok1 else 'FAIL', 'OK' if ok2 else 'FAIL'))
        return 0 if (ok1 and ok2) else 1
    if not (ok1 and ok2):
        print('НЕ ПИШУ: есть промахи')
        return 1

    with io.open(app_path, 'w', encoding='utf-8', newline='') as f:
        f.write(app2)
    out = mono2.replace('\n', '\r\n') if had_crlf else mono2
    with io.open(mono_path, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    raw = open(mono_path, 'rb').read()
    assert b'\r\r\n' not in raw, 'CRLF повреждён: \\r\\r\\n'
    assert raw.replace(b'\r\n', b'').count(b'\r') == 0, 'CRLF повреждён: одиночные \\r'
    print('записано: assets/app.js + tools/source-index.html (CRLF цел)')
    return 0


if __name__ == '__main__':
    sys.exit(main())


def apply(text, edits, log):
    for i, (old, new) in enumerate(edits):
        c = text.count(old)
        if c == 1:
            text = text.replace(old, new, 1)
            log.append('  · edit %02d: применено' % (i + 1))
        elif c == 0 and new in text:
            log.append('  · edit %02d: уже применено' % (i + 1))
        else:
            log.append('  · edit %02d: ПРОМАХ (вхождений: %d)' % (i + 1, c))
            return text, False
    return text, True


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'check'
    log = []

    app_path = os.path.join(ROOT, 'assets', 'app.js')
    with io.open(app_path, 'r', encoding='utf-8', newline='') as f:
        app = f.read()
    app2, ok1 = apply(app, EDITS + EDITS_APP, log)
    print('assets/app.js:'); print('\n'.join(log))

    log2 = []
    mono_path = os.path.join(ROOT, 'tools', 'source-index.html')
    with io.open(mono_path, 'r', encoding='utf-8', newline='') as f:
        mono_raw = f.read()
    had_crlf = '\r\n' in mono_raw
    mono = mono_raw.replace('\r\n', '\n') if had_crlf else mono_raw
    mono2, ok2 = apply(mono, EDITS + EDITS_MONO, log2)
    print('tools/source-index.html:'); print('\n'.join(log2))

    if mode == 'check':
        print('check: app=%s mono=%s' % ('OK' if ok1 else 'FAIL', 'OK' if ok2 else 'FAIL'))
        return 0 if (ok1 and ok2) else 1
    if not (ok1 and ok2):
        print('НЕ ПИШУ: есть промахи')
        return 1

    with io.open(app_path, 'w', encoding='utf-8', newline='') as f:
        f.write(app2)
    out = mono2.replace('\n', '\r\n') if had_crlf else mono2
    with io.open(mono_path, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    raw = open(mono_path, 'rb').read()
    assert b'\r\r\n' not in raw, 'CRLF повреждён: \\r\\r\\n'
    assert raw.replace(b'\r\n', b'').count(b'\r') == 0, 'CRLF повреждён: одиночные \\r'
    print('записано: assets/app.js + tools/source-index.html (CRLF цел)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
