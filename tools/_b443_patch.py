#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b443: биржа переезжает на свой API — покупка атомарная, выплаты не теряются.

Ставится ПОСЛЕ b442 (тег nxmob172 -> nxmob173). Требует задеплоенного воркера
NX-CLOUD и подключённого assets/nx-cloud.js с блоком NXM. Если API недоступен —
игра работает ровно как раньше, без задержек: NXM.available() возвращает true
только после успешного ответа сервера.

Диагноз (продолжение DIAGNOSTIKA-propadayut-karty.md, причины 3 и 4):

  · Лоты живут внутри общего документа банка (150 КБ, textdb, без атомарности).
    marketBuy() фильтрует лот локально и пушит весь документ: при гонке два
    покупателя получали одну карту, а монеты списывались у обоих.
  · Квитанция продавца добавлялась в CLOUD.ledger, который режется до 60 записей
    НА ВЕСЬ САЙТ. При 40 лотах и автовыкупе каждые 6 ч (~160 выкупов в сутки)
    чья-то квитанция гарантированно выталкивалась до того, как продавец её
    увидит: карта уходила, деньги не приходили.
  · Витрина упиралась в 80 лотов (marketDoc: lots.slice(-80)) и в
    marketSellRoom() = 80 - lots. В живом документе ровно 40 лотов при
    MARKET_HARD_TRIM = 40, то есть биржа ПОСТОЯННО в состоянии «забита»:
    full = true, срок жизни лота падает с 24 ч до 6 ч, и дом выкупает всё
    подряд по {common 20, rare 50, epic 120, legendary 300}. Легендарка,
    выставленная за миллион, исчезала через 6 часов за 300 монет.

Лечение:
  1. покупка — через POST /api/market/buy: UPDATE … WHERE status='open',
     монеты списываются ТОЛЬКО после подтверждения сервера, второй покупатель
     получает «лот уже куплен»;
  2. квитанцию создаёт СЕРВЕР и сразу с sid = продавец; продавец забирает свои
     выплаты отдельным запросом GET /api/market/ledger?cid=… — окно в 60
     записей больше не съедает деньги;
  3. выставление/снятие лота дублируется на сервер пакетом; при офлайне лот
     уходит в очередь IndexedDB (эскроу уже снят с коллекции — терять нельзя);
  4. витрина добирает лоты с сервера (лимит 400 вместо 80), раз в 30 с;
  5. лимиты поднимаются ТОЛЬКО когда API жив: soft 60→400, hard 40→300,
     sellRoom 80→400, лотов на карту 4→8, «забита» больше не укорачивает
     срок жизни лота до 6 ч. Без API все прежние значения сохраняются.

Проверка/применение:
    python3 tools/_b443_patch.py --check
    python3 tools/_b443_patch.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = []

# ── 1. Помощники: лимиты зависят от того, жив ли свой API ────────────────────
PAIRS.append(('app.js: помощники биржи b443', """
        const MARKET_HARD_TRIM = 40;
""", """
        const MARKET_HARD_TRIM = 40;
        // ============ b443: БИРЖА НА СВОЁМ API ============
        // window.NXM даёт assets/nx-cloud.js. available() становится true только
        // ПОСЛЕ успешного ответа сервера, поэтому без задеплоенного воркера все
        // лимиты и пути остаются прежними — ничего не ломается и не тормозит.
        function nxMkt() {
            try { const m = window.NXM; return (m && m.available && m.available()) ? m : null; } catch (e) { return null; }
        }
        function nxMarketApiOn() { return !!nxMkt(); }
        function marketCapSoft() { return nxMarketApiOn() ? 400 : MARKET_SOFT_CAP; }
        function marketCapHard() { return nxMarketApiOn() ? 300 : MARKET_HARD_TRIM; }
        function marketCapRoom() { return nxMarketApiOn() ? 400 : 80; }
        function marketMaxPerCard() { return nxMarketApiOn() ? 8 : MARKET_MAX_PER_CARD; }
        // «Забита» больше не укорачивает жизнь лота до 6 часов, если есть свой API:
        // лоты хранятся строками в базе, а не в общем документе на 150 КБ.
        function marketTtlNow(full) { return (full && !nxMarketApiOn()) ? MARKET_TTL_FULL : MARKET_LOT_TTL; }
        // Витрина добирает открытые лоты с сервера (не чаще раза в 30 с).
        let nxMktTopAt = 0;
        function nxMktTopUp() {
            try {
                const nxm = nxMkt();
                if (!nxm) return;
                const t = Date.now();
                if (t - nxMktTopAt < 30000) return;
                nxMktTopAt = t;
                nxm.lots('', 400).then(res => {
                    if (!res || !res.ok || !Array.isArray(res.lots)) return;
                    const removed = marketRemoved();
                    const cur = {};
                    marketLots().forEach(l => { if (l && l.id) cur[l.id] = l; });
                    let added = 0;
                    res.lots.forEach(l => { if (l && l.id && !cur[l.id] && !removed[l.id]) { cur[l.id] = l; added++; } });
                    if (added) {
                        CLOUD.market = Object.values(cur);
                        window.__nxMktSig = '';
                        try { renderMarketIfVisible(); } catch (e) {}
                        try { console.log('market: с сервера добавлено лотов — ' + added); } catch (e) {}
                    }
                }).catch(() => {});
            } catch (e) {}
        }
"""))

# ── 2. Свободное место на бирже ─────────────────────────────────────────────
PAIRS.append(('app.js: marketSellRoom от своего API', """
        function marketSellRoom() { return Math.max(0, 80 - marketLots().length); }
""", """
        function marketSellRoom() { return Math.max(0, marketCapRoom() - marketLots().length); } // b443: 80 → 400, если свой API жив
"""))

PAIRS.append(('app.js: marketListMany — комната и лимит на карту', """
            const room = Math.max(0, 80 - marketLots().length);
""", """
            const room = marketSellRoom(); // b443
"""))

PAIRS.append(('app.js: marketListMany — MARKET_MAX_PER_CARD динамический', """
                if (pc >= MARKET_MAX_PER_CARD) { skipped++; continue; }
""", """
                if (pc >= marketMaxPerCard()) { skipped++; continue; } // b443
"""))

PAIRS.append(('app.js: лимит лотов на карту в marketListCardFor', """
            if (marketLotsFor(cardId) >= MARKET_MAX_PER_CARD) {
""", """
            if (marketLotsFor(cardId) >= marketMaxPerCard()) { // b443
"""))

PAIRS.append(('app.js: текст тоста про лимит лотов', """
                    showToast('♻ На бирже уже ' + MARKET_MAX_PER_CARD + ' лота этой карты — копия продана автоматически за ' + fmtCoins(r.sum), 'success');
""", """
                    showToast('♻ На бирже уже ' + marketMaxPerCard() + ' лота этой карты — копия продана автоматически за ' + fmtCoins(r.sum), 'success'); // b443
"""))

PAIRS.append(('app.js: сколько ещё можно выставить (listable)', """
            return Math.max(0, MARKET_MAX_PER_CARD - exist);
""", """
            return Math.max(0, marketMaxPerCard() - exist); // b443
"""))

PAIRS.append(('app.js: marketSellDupesSmart — лимит на карту', """
            listed = Math.min(dupes, Math.max(0, MARKET_MAX_PER_CARD - marketLotsFor(card.id)));
""", """
            listed = Math.min(dupes, Math.max(0, marketMaxPerCard() - marketLotsFor(card.id))); // b443
"""))

PAIRS.append(('app.js: nxAutoSellDupes — лимит на карту', """
            const listable = Math.max(0, MARKET_MAX_PER_CARD - marketLotsFor(en.id));
""", """
            const listable = Math.max(0, marketMaxPerCard() - marketLotsFor(en.id)); // b443
"""))

# ── 3. Автовыкуп: лимиты + квитанция на сервере ─────────────────────────────
PAIRS.append(('app.js: marketEnforceLimit — пороги от своего API', """
            const full = marketLots().length >= MARKET_SOFT_CAP; // b411
            const ttl = full ? MARKET_TTL_FULL : MARKET_LOT_TTL; // b411: забита — просрочка 6 ч
""", """
            const full = marketLots().length >= marketCapSoft(); // b411; b443: 60 → 400 со своим API
            const ttl = marketTtlNow(full); // b411; b443: со своим API агрессивный выкуп через 6 ч не нужен
"""))

PAIRS.append(('app.js: marketEnforceLimit — срез переполнения', """
            let over = left.length + bought.length - (full ? MARKET_HARD_TRIM : MARKET_SOFT_CAP);
""", """
            let over = left.length + bought.length - (full ? marketCapHard() : marketCapSoft()); // b443
"""))

PAIRS.append(('app.js: marketEnforceLimit — excess на карту', """
                let excess = arr.length - MARKET_MAX_PER_CARD;
""", """
                let excess = arr.length - marketMaxPerCard(); // b443
"""))

PAIRS.append(('app.js: marketEnforceLimit — квитанции выкупа дублируются на сервер', """
            marketRemovedAddMany(rmIds); // b405: одна запись localStorage на всю партию
            CLOUD.market = marketLots().filter(l => !gone[l.id]);
            CLOUD.ledger = (Array.isArray(CLOUD.ledger) ? CLOUD.ledger : []).concat(receipts).slice(-60);
""", """
            marketRemovedAddMany(rmIds); // b405: одна запись localStorage на всю партию
            CLOUD.market = marketLots().filter(l => !gone[l.id]);
            CLOUD.ledger = (Array.isArray(CLOUD.ledger) ? CLOUD.ledger : []).concat(receipts).slice(-60);
            // b443: квитанция в общем документе живёт ровно до тех пор, пока её не
            // вытолкнут следующие 60 записей. Дублируем на сервер — там она лежит
            // строкой с PRIMARY KEY и продавец заберёт её отдельным запросом.
            try {
                const nxm = nxMkt();
                if (nxm && nxm.refund) {
                    receipts.forEach(rc => {
                        try { nxm.refund(String(rc.id).replace(/^sys-/, ''), rc.sid, rc.amount, ''); } catch (e) {}
                    });
                }
            } catch (e) {}
"""))

# ── 4. Выставление и снятие лота ────────────────────────────────────────────
PAIRS.append(('app.js: marketCommitLots — лоты фиксируются на сервере', """
        function marketCommitLots(lots) {
            if (!lots || !lots.length) return 0;
            CLOUD.market = marketLots().concat(lots);
            saveState(); jpSyncNow(); jpSyncSoon(); renderMarket(); // ОДИН пуш на партию
""", """
        function marketCommitLots(lots) {
            if (!lots || !lots.length) return 0;
            CLOUD.market = marketLots().concat(lots);
            // b443: копия УЖЕ снята с коллекции (эскроу), поэтому лот обязан дойти
            // до базы. Пакетом, одним запросом; при офлайне NXM кладёт его в
            // очередь IndexedDB и отправляет, как только связь вернётся.
            try { const nxm = window.NXM; if (nxm && nxm.list) nxm.list(lots); } catch (e) {}
            saveState(); jpSyncNow(); jpSyncSoon(); renderMarket(); // ОДИН пуш на партию
"""))

PAIRS.append(('app.js: marketListCardFor — одиночный лот на сервер', """
            CLOUD.market = marketLots().concat([lot]);
            saveState(); jpSyncNow(); jpSyncSoon(); renderMarket(); // b336: мгновенный пуш лота
""", """
            CLOUD.market = marketLots().concat([lot]);
            try { const nxm = window.NXM; if (nxm && nxm.list) nxm.list([lot]); } catch (e) {} // b443: эскроу фиксируется на сервере
            saveState(); jpSyncNow(); jpSyncSoon(); renderMarket(); // b336: мгновенный пуш лота
"""))

PAIRS.append(('app.js: marketCancel — снятие фиксируется на сервере', """
        function marketCancel(lotId) {
            const lot = marketLots().find(l => l.id === lotId);
            if (!lot || !marketIsMine(lot)) return;
            marketRemovedAdd(lotId);
""", """
        function marketCancel(lotId) {
            const lot = marketLots().find(l => l.id === lotId);
            if (!lot || !marketIsMine(lot)) return;
            // b443: снятие фиксируем и на сервере. Иначе лот воскреснет из чужой
            // копии документа, а копия карты уже вернулась в коллекцию — дубль.
            try { const nxm = window.NXM; if (nxm && nxm.cancel) nxm.cancel(lotId, cloudDeviceId()); } catch (e) {}
            marketRemovedAdd(lotId);
"""))

PAIRS.append(('app.js: marketMerge добирает лоты с сервера', """
            CLOUD.ledger = arr;
        }
""", """
            CLOUD.ledger = arr;
            try { nxMktTopUp(); } catch (e) {} // b443: витрина шире, чем 80 лотов документа
        }
"""))

# ── 5. Покупка: атомарно, монеты только после подтверждения ──────────────────
PAIRS.append(('app.js: marketBuy — атомарная покупка', """
        function marketBuy(lotId) {
            if (statsBlockGuard('биржа')) return; // b277
            if (String(lotId).indexOf('syslot:') === 0) return marketBuySys(String(lotId).slice(7)); // b413: витрина Дома
            if (!CLOUD.connected()) { showToast('Биржа работает при подключённом облаке комнаты', 'error'); return; }
            const lot = marketLots().find(l => l.id === lotId);
            if (!lot) { showToast('Лот уже куплен или снят', 'error'); renderMarket(); return; }
            if (marketIsMine(lot)) { showToast('Это ваш собственный лот', 'error'); return; }
            if (state.coins < lot.price) { showToast('Не хватает монет: нужно ' + fmtCoins(lot.price), 'error'); return; }
            state.coins -= lot.price;
            marketRemovedAdd(lotId);
            CLOUD.market = marketLots().filter(l => l.id !== lotId);
            CLOUD.ledger = (Array.isArray(CLOUD.ledger) ? CLOUD.ledger : []).concat([{
                id: 'sale-' + lot.id, sid: lot.sid, amount: lot.price, at: Date.now(),
                bname: getPlayerName() || ('Игрок-' + cloudDeviceId().slice(-4))
            }]).slice(-60);
            const isNewDef = !state.cards.some(c => c.id === lot.card.id);
            if (isNewDef && lot.card) { state.cards.push(Object.assign({}, lot.card)); try { cardsSortNorm(); } catch (e) {} } // b375: купленная карта встаёт по нумерации создателя
            marketSetCollection(lot.card.id, cardCopies(lot.card.id) + 1);
            saveState(); updateCoinDisplay(); checkAchievements();
            if (isNewDef) updateMissions('collect_new', 1);
            jpSyncNow(); jpSyncSoon(); renderMarket(); // b336: мгновенный пуш покупки
            try { preloadImages([lot.card.image]); } catch (e) {}
            try { SoundFX.play('coin'); } catch (e) {}
            showToast('🎉 Куплено: «' + (lot.card.name || 'карта') + '» в коллекции!', 'success');
        }
""", """
        function marketBuy(lotId) {
            if (statsBlockGuard('биржа')) return; // b277
            if (String(lotId).indexOf('syslot:') === 0) return marketBuySys(String(lotId).slice(7)); // b413: витрина Дома
            if (!CLOUD.connected()) { showToast('Биржа работает при подключённом облаке комнаты', 'error'); return; }
            const lot = marketLots().find(l => l.id === lotId);
            if (!lot) { showToast('Лот уже куплен или снят', 'error'); renderMarket(); return; }
            if (marketIsMine(lot)) { showToast('Это ваш собственный лот', 'error'); return; }
            if (state.coins < lot.price) { showToast('Не хватает монет: нужно ' + fmtCoins(lot.price), 'error'); return; }
            // b443: АТОМАРНАЯ ПОКУПКА. Решение принимает база:
            //     UPDATE mk_lots SET status='sold' WHERE id=? AND status='open'
            // Второй покупатель получит «лот уже куплен», а монеты списываются
            // ТОЛЬКО после подтверждения — раньше каждый фильтровал лот у себя и
            // пушил весь документ, поэтому при гонке карту получали оба.
            const nxm = nxMkt();
            if (nxm && nxm.buy) {
                nxm.buy(lotId, cloudDeviceId(), getPlayerName() || ('Игрок-' + cloudDeviceId().slice(-4))).then(res => {
                    if (res && res.ok) { marketApplyBuy(lot, res.receipt); return; }
                    if (res && res.offline) { marketLegacyBuy(lot); return; } // сеть пропала — запасной путь
                    try { marketRemovedAdd(lotId); } catch (e) {}
                    try { CLOUD.market = marketLots().filter(l => l.id !== lotId); } catch (e) {}
                    showToast(res && res.error ? '⚠️ ' + res.error : 'Лот уже куплен или снят', 'error');
                    renderMarket();
                }).catch(() => { marketLegacyBuy(lot); });
                return;
            }
            marketLegacyBuy(lot);
        }
        // b443: общий хвост покупки — вызывается ТОЛЬКО после того, как сервер
        // подтвердил, что лот достался нам (или когда сервера нет вовсе).
        function marketApplyBuy(lot, receipt) {
            if (!lot || !lot.card) return;
            if (state.coins < lot.price) { showToast('Не хватает монет: нужно ' + fmtCoins(lot.price), 'error'); renderMarket(); return; }
            state.coins -= lot.price;
            marketRemovedAdd(lot.id);
            CLOUD.market = marketLots().filter(l => l.id !== lot.id);
            // квитанцию создал сервер (id = 'sale-'+лот, sid = ПРОДАВЕЦ). Кладём её
            // и локально: если продавец на этом же устройстве — выплата видна сразу.
            if (receipt && receipt.id) {
                CLOUD.ledger = (Array.isArray(CLOUD.ledger) ? CLOUD.ledger : []).concat([receipt]).slice(-60);
            }
            const isNewDef = !state.cards.some(c => c.id === lot.card.id);
            if (isNewDef && lot.card) { state.cards.push(Object.assign({}, lot.card)); try { cardsSortNorm(); } catch (e) {} } // b375
            marketSetCollection(lot.card.id, cardCopies(lot.card.id) + 1);
            saveState(); updateCoinDisplay(); checkAchievements();
            if (isNewDef) updateMissions('collect_new', 1);
            jpSyncNow(); jpSyncSoon(); renderMarket();
            try { preloadImages([lot.card.image]); } catch (e) {}
            try { SoundFX.play('coin'); } catch (e) {}
            showToast('🎉 Куплено: «' + (lot.card.name || 'карта') + '» в коллекции!', 'success');
        }
        // Прежний путь (фильтр у себя + пуш всего документа). Остаётся запасным на
        // случай, когда свой API недоступен: лучше редкая гонка, чем мёртвая кнопка.
        function marketLegacyBuy(lot) {
            if (!lot || !lot.card) return;
            if (state.coins < lot.price) { showToast('Не хватает монет: нужно ' + fmtCoins(lot.price), 'error'); return; }
            state.coins -= lot.price;
            marketRemovedAdd(lot.id);
            CLOUD.market = marketLots().filter(l => l.id !== lot.id);
            CLOUD.ledger = (Array.isArray(CLOUD.ledger) ? CLOUD.ledger : []).concat([{
                id: 'sale-' + lot.id, sid: lot.sid, amount: lot.price, at: Date.now(),
                bname: getPlayerName() || ('Игрок-' + cloudDeviceId().slice(-4))
            }]).slice(-60);
            const isNewDef = !state.cards.some(c => c.id === lot.card.id);
            if (isNewDef && lot.card) { state.cards.push(Object.assign({}, lot.card)); try { cardsSortNorm(); } catch (e) {} } // b375: купленная карта встаёт по нумерации создателя
            marketSetCollection(lot.card.id, cardCopies(lot.card.id) + 1);
            saveState(); updateCoinDisplay(); checkAchievements();
            if (isNewDef) updateMissions('collect_new', 1);
            jpSyncNow(); jpSyncSoon(); renderMarket(); // b336: мгновенный пуш покупки
            try { preloadImages([lot.card.image]); } catch (e) {}
            try { SoundFX.play('coin'); } catch (e) {}
            showToast('🎉 Куплено: «' + (lot.card.name || 'карта') + '» в коллекции!', 'success');
        }
"""))

# ── 6. Выплаты продавцу: забираем свои квитанции с сервера ───────────────────
PAIRS.append(('app.js: marketCreditLedger тянет свои квитанции с сервера', """
        function marketCreditLedger() {
            const led = Array.isArray(CLOUD.ledger) ? CLOUD.ledger : [];
""", """
        function marketCreditLedger() {
            // b443: свои квитанции забираем с сервера (GET /api/market/ledger?cid=…).
            // В общем документе ledger держит только 60 последних записей на ВЕСЬ
            // сайт: при 40 лотах и автовыкупе каждые 6 ч (~160 выкупов в сутки)
            // чья-то квитанция гарантированно выталкивалась раньше, чем продавец
            // успевал её увидеть — карта уходила, деньги не приходили.
            try {
                const nxm = nxMkt();
                if (nxm && nxm.ledger) {
                    const t = Date.now();
                    const lastPoll = Number(LS.getItem('nx_mkt_ledger_poll') || 0);
                    if (t - lastPoll > 20000) {
                        LS.setItem('nx_mkt_ledger_poll', String(t));
                        const after = Number(LS.getItem('nx_mkt_ledger_at') || 0);
                        nxm.ledger(cloudDeviceId(), after).then(res => {
                            if (!res || !res.ok || !Array.isArray(res.ledger) || !res.ledger.length) return;
                            const have = {};
                            (Array.isArray(CLOUD.ledger) ? CLOUD.ledger : []).forEach(x => { if (x && x.id) have[x.id] = 1; });
                            const add = [];
                            let maxAt = after;
                            res.ledger.forEach(x => {
                                if (!x || !x.id || have[x.id]) return;
                                add.push(x);
                                if (Number(x.at) > maxAt) maxAt = Number(x.at);
                            });
                            if (!add.length) return;
                            CLOUD.ledger = (Array.isArray(CLOUD.ledger) ? CLOUD.ledger : []).concat(add).slice(-60);
                            try { LS.setItem('nx_mkt_ledger_at', String(maxAt)); } catch (e) {}
                            marketCreditNow(); // начислить сразу, не дожидаясь следующего синка
                        }).catch(() => {});
                    }
                }
            } catch (e) {}
            marketCreditNow();
        }
        function marketCreditNow() {
            const led = Array.isArray(CLOUD.ledger) ? CLOUD.ledger : [];
"""))

TAG_OLD = 'nxmob172'
TAG_NEW = 'nxmob173'
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
        assert old.strip() in txt, 'b443: не найден якорь: %s' % label
        assert txt.count(old.strip()) == 1, 'b443: якорь не уникален: %s (%d)' % (label, txt.count(old.strip()))
        files[rel] = txt.replace(old.strip(), new.strip(), 1)
    for rel, txt in files.items():
        write(rel, txt)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b443: не найден тег %s в %s (сначала примените _b442_patch.py)' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b443: применено')


def check():
    problems = []
    for label, old, new in PAIRS:
        rel = 'index.html' if label.startswith('index.html') else 'assets/app.js'
        txt = read(rel)
        if new.strip() not in txt:
            problems.append('%s: нет нового блока: %s' % (rel, label))
    app = read('assets/app.js')
    for extra in ('function nxMkt(', 'function marketCapSoft(', 'function nxMktTopUp(',
                  'function marketApplyBuy(', 'function marketLegacyBuy(', 'function marketCreditNow(',
                  'nxm.buy(lotId, cloudDeviceId()', 'nxm.ledger(cloudDeviceId(), after)',
                  'if (nxm && nxm.list) nxm.list(lots);', 'if (nxm && nxm.cancel) nxm.cancel(lotId, cloudDeviceId());',
                  'nxm.refund(String(rc.id).replace(/^sys-/, \'\')'):
        if extra not in app:
            problems.append('app.js: нет %r' % extra)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не %s' % (rel, TAG_NEW))
    if problems:
        print('b443 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b443 --check: всё на месте (атомарная покупка, серверные квитанции, витрина 400, '
          'лимиты от API, тег %s)' % TAG_NEW)


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
