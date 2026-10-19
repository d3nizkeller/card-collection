#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b471: цены обмена «🏛 Дом коллекционера» настраиваются в Студии.

Просьба владельца: «сделай в студии чтоб можно было менять цены в обмене
🏛 Дом коллекционера». Уточнено: все три таблицы цен + переопределение на
отдельную карту.

Как было
--------
Цены обмена были зашиты константами в assets/app.js, в трёх разных местах:

  MARKET_HOUSE_PRICE  {common 1b, rare 4b, epic 10b, legendary 35b}  (b435)
        — ценник витрины Дома и сумма, которую игрок платит (marketBuySys)
  MARKET_SYS_PRICE    {common 100, rare 400, epic 1000, legendary 3500}  (b142)
        — сколько игрок получает, когда Дом автовыкупает залежавшийся лот
  база внутри marketRecommendPrice()  {100 / 400 / 1000 / 3500}  (b139)
        — рекомендованная цена при выставлении дубликата

Чтобы поменять любую из них, нужно было править app.js и поднимать тег сборки —
то есть перезагружать всех игроков (см. b470, к чему это приводило).

Как стало
---------
1. Все три таблицы + личные цены на карты хранятся в jpc.mkt — общем конфиге
   сайта. Отдельный документ и отдельный мердж не понадобились: у jpc уже есть
   канал «владелец опубликовал -> jpcMerge() у каждого клиента за 15 секунд»
   (jpPullLight тянет jpc каждые 15 с), защита от правки участником комнаты
   (jpcAdminGuard) и нормализация (jpcNorm).
2. jpcMktNorm() приводит конфиг к безопасному виду: каждое число в
   [0, MKT_PRICE_MAX=1e15], отсутствующее или мусорное -> заводское; личных цен
   на карты не больше MKT_CARD_OVER_MAX=400, id обрезан до 64 символов,
   h<=0 отбрасывается. Нормализация обязательна: jpc приходит из общего
   документа textdb, куда пишет кто угодно.
3. mktPriceOf(kind, card) — единая точка чтения: личная цена карты ->
   таблица редкости -> заводское значение. Через неё ходят marketHousePrice(),
   marketSysPrice() и marketRecommendPrice(), поэтому без опубликованного
   конфига (участник комнаты, старый jpc без mkt) цены совпадают с прежними
   байт в байт.
4. Константы MARKET_HOUSE_PRICE и MARKET_SYS_PRICE оставлены как ссылки на
   MKT_DEFAULTS — их упоминают комментарии b413/b435/b142.
5. Объявлено ДО `let jpc = jpcLoad()`: jpcLoad() вызывает jpcNorm() ->
   jpcMktNorm() при загрузке страницы, а const, объявленный ниже, в этот момент
   ещё в temporal dead zone — был бы ReferenceError на старте.

Панель в Студии (вкладка «Джекпот», рядом с остальными настройками сайта)
-------------------------------------------------------------------------
* таблица 4 редкости x 3 цены, 12 полей;
* ввод числом или с суффиксом k/m/b/t/q (mktParseNum): 35b = 35 000 000 000,
  4.5m = 4 500 000, пробелы и запятая-разделитель допустимы; непонятное значение
  не публикуется молча — показывается тост с перечислением полей;
* «Опубликовать цены» и «Сбросить к заводским»;
* «Личная цена на карту»: поиск по названию или id (до 20 строк), цена,
  «Задать» / «Снять», отдельный список уже заданных переопределений.
  Переопределение действует ТОЛЬКО на витрину Дома — выкуп и рекомендованная
  цена остаются по редкости, иначе автовыкуп превратился бы в выдачу денег;
* mktPricesRender() не трогает поле, в котором стоит курсор
  (document.activeElement), — панель перерисовывается каждые 15 с вместе с
  jpcMerge и иначе вырывала бы ввод;
* публикация — та же, что у настроек джекпота: jpc.at = Date.now(), jpcSave(),
  jpSyncNow(). Список карт для поиска берётся по индексу (mktCardList /
  mktOverList), а не подстановкой id в onclick — id карт бывают с кавычками.

Что ещё пришлось починить по пути
---------------------------------
Сигнатура биржи __nxMktSig учитывала только ЧИСЛО виртуальных лотов Дома
('|S' + marketSystemLots().length), но не их цены: после смены ценника список
не перерисовывался бы, пока не изменится что-то ещё. Добавлен компонент
'|H' + mktSig(). Туда же в jpcMerge() добавлен renderMarketIfVisible(), чтобы
новая цена прилетала на биржу в тот же тик, что и остальной конфиг.

app.js и index.html менялись — тег сборки nxmob214 -> nxmob215.

Проверка/применение:
    python3 tools/_b471_patch.py --check
    python3 tools/_b471_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob214'
TAG_NEW = 'nxmob215'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('assets/app.js', 1,
              '''        const JPC_DEFAULTS = {''',
              '''        // ============ b471: ЦЕНЫ ОБМЕНА «🏛 ДОМ КОЛЛЕКЦИОНЕРА» ============
        // Три таблицы по редкости + личная цена на отдельную карту. Раньше все три
        // были зашиты константами (MARKET_HOUSE_PRICE, MARKET_SYS_PRICE и база
        // внутри marketRecommendPrice): чтобы поменять ценник, приходилось править
        // app.js и поднимать тег сборки — то есть перезагружать всех игроков.
        //
        // Хранятся ВНУТРИ jpc — общего конфига сайта. Там уже есть готовый канал
        // «владелец опубликовал → jpcMerge() у каждого клиента за 15 секунд»,
        // защита от правки участником комнаты (jpcAdminGuard) и нормализация
        // (jpcNorm). Отдельный документ и отдельный мердж не понадобились.
        //
        // Объявлено ДО `let jpc = jpcLoad()` намеренно: jpcLoad() вызывает
        // jpcNorm() → jpcMktNorm() при загрузке страницы, а const, объявленный
        // ниже, в этот момент ещё в temporal dead zone — был бы ReferenceError.
        const MKT_RARITIES = ['common', 'rare', 'epic', 'legendary'];
        const MKT_KINDS = [
            { k: 'house',   ru: 'Витрина Дома',   col: 'Витрина' },
            { k: 'buy',     ru: 'Выкуп лота',     col: 'Выкуп' },
            { k: 'suggest', ru: 'Рекомендованная', col: 'Рекоменд.' }
        ];
        const MKT_DEFAULTS = {
            // b435: ценники витрины «от миллиарда» — ровно те, что были в MARKET_HOUSE_PRICE
            house:   { common: 1000000000, rare: 4000000000, epic: 10000000000, legendary: 35000000000 },
            // b142: низкая фикс-цена автовыкупа защищает от мани-абуза — нельзя
            // выставить свою карту за миллион и получить его от Дома
            buy:     { common: 100, rare: 400, epic: 1000, legendary: 3500 },
            // b139: рекомендованная цена дубликата (выше автовыкупа)
            suggest: { common: 100, rare: 400, epic: 1000, legendary: 3500 }
        };
        const MKT_PRICE_MAX = 1e15;      // тот же потолок, что у jpc.floor
        const MKT_CARD_OVER_MAX = 400;   // сколько личных цен на карты держим в конфиге
        function jpcMktNorm(raw) {
            raw = (raw && typeof raw === 'object') ? raw : {};
            const out = {};
            MKT_KINDS.forEach(kind => {
                const src = (raw[kind.k] && typeof raw[kind.k] === 'object') ? raw[kind.k] : {};
                const t = {};
                MKT_RARITIES.forEach(r => {
                    let v = Number(src[r]);
                    if (!isFinite(v) || v < 0) v = MKT_DEFAULTS[kind.k][r];   // чужое/старое значение → заводское
                    t[r] = Math.round(Math.min(MKT_PRICE_MAX, v));
                });
                out[kind.k] = t;
            });
            // личные цены: { cardId: { h: цена, t: метка } }; 0/мусор = переопределения нет
            out.card = {};
            const srcCard = (raw.card && typeof raw.card === 'object') ? raw.card : {};
            Object.keys(srcCard).slice(0, MKT_CARD_OVER_MAX).forEach(id => {
                const e = srcCard[id];
                if (!e || typeof e !== 'object') return;
                const h = Number(e.h);
                if (!isFinite(h) || h <= 0) return;
                out.card[String(id).slice(0, 64)] = { h: Math.round(Math.min(MKT_PRICE_MAX, h)), t: Number(e.t) || 0 };
            });
            return out;
        }
        // единая точка чтения цены: личная цена карты → таблица редкости → заводская.
        // Через неё ходят все три прежние функции, поэтому поведение без конфига
        // (старый jpc без mkt, участник без публикации) совпадает с прежним байт в байт.
        function mktPriceOf(kind, card) {
            const rar = MKT_RARITIES.indexOf((card || {}).rarity) >= 0 ? card.rarity : 'common';
            try {
                const m = (jpc && jpc.mkt) ? jpc.mkt : null;
                if (m) {
                    if (kind === 'house' && card && card.id && m.card && m.card[card.id]) {
                        const h = Number(m.card[card.id].h);
                        if (isFinite(h) && h > 0) return Math.round(h);
                    }
                    const t = m[kind] ? m[kind][rar] : undefined;
                    if (t !== undefined && t !== null && isFinite(Number(t))) return Math.max(0, Math.round(Number(t)));
                }
            } catch (e) { /* конфиг ещё не инициализирован — заводские значения */ }
            return MKT_DEFAULTS[kind][rar];
        }
        // отпечаток цен: биржа не должна залипать на старых ценниках (__nxMktSig)
        function mktSig() {
            try {
                const m = (jpc && jpc.mkt) || {};
                let s = '';
                MKT_KINDS.forEach(k => MKT_RARITIES.forEach(r => { s += ((m[k.k] || {})[r] !== undefined ? m[k.k][r] : MKT_DEFAULTS[k.k][r]) + '.'; }));
                const c = m.card || {};
                return s + Object.keys(c).map(id => id + ':' + c[id].h).join(',');
            } catch (e) { return ''; }
        }
        // ввод «35b» / «4.5m» / «1 000» / «1000» → число. Пробелы и запятая допустимы
        function mktParseNum(v) {
            const s = String(v == null ? '' : v).trim().toLowerCase().replace(/[\s\u00a0]/g, '').replace(',', '.');
            if (!s) return NaN;
            const m = s.match(/^(\d+(?:\.\d+)?)(k|m|b|t|q)?$/);
            if (!m) return NaN;
            const mult = { k: 1e3, m: 1e6, b: 1e9, t: 1e12, q: 1e15 }[m[2] || ''] || 1;
            const n = Number(m[1]) * mult;
            return isFinite(n) ? Math.round(Math.min(MKT_PRICE_MAX, Math.max(0, n))) : NaN;
        }
        const JPC_DEFAULTS = {'''))

PAIRS.append(('assets/app.js', 1,
              '''            n.grant = {};
            if (o.grant && typeof o.grant === 'object') {''',
              '''            n.mkt = jpcMktNorm(o.mkt);   // b471: цены обмена «Дом коллекционера»
            n.grant = {};
            if (o.grant && typeof o.grant === 'object') {'''))

PAIRS.append(('assets/app.js', 1,
              '''        const MARKET_SYS_PRICE = { common: 100, rare: 400, epic: 1000, legendary: 3500 };''',
              '''        const MARKET_SYS_PRICE = MKT_DEFAULTS.buy;   // b471: заводские значения; рабочие — в jpc.mkt (Студия → Джекпот)'''))

PAIRS.append(('assets/app.js', 1,
              '''        const MARKET_HOUSE_PRICE = { common: 1000000000, rare: 4000000000, epic: 10000000000, legendary: 35000000000 };
        function marketHousePrice(card) { return MARKET_HOUSE_PRICE[(card || {}).rarity] || 1000000000; }''',
              '''        const MARKET_HOUSE_PRICE = MKT_DEFAULTS.house;   // b471: заводские значения; рабочие — в jpc.mkt
        // b471: цену берём из конфига Студии — личная цена карты, иначе таблица редкости
        function marketHousePrice(card) { return mktPriceOf('house', card); }'''))

PAIRS.append(('assets/app.js', 1,
              '''        function marketSysPrice(card) { return MARKET_SYS_PRICE[(card || {}).rarity] || 100; }''',
              '''        function marketSysPrice(card) { return mktPriceOf('buy', card); }   // b471'''))

PAIRS.append(('assets/app.js', 1,
              '''        function marketRecommendPrice(card) {
            const base = { common: 100, rare: 400, epic: 1000, legendary: 3500 };
            return base[(card && card.rarity) || 'common'] || 100;
        }''',
              '''        function marketRecommendPrice(card) { return mktPriceOf('suggest', card); }   // b471: из конфига Студии'''))

PAIRS.append(('assets/app.js', 1,
              '''            if (ch) {
                jpcSave();
                try { jackpotRender(); } catch (e) {}
                try { if (jpcVisible()) jpcAdminRender(); else jpcAdminPreview(); } catch (e) {}
            }''',
              '''            if (ch) {
                jpcSave();
                try { jackpotRender(); } catch (e) {}
                try { if (jpcVisible()) jpcAdminRender(); else jpcAdminPreview(); } catch (e) {}
                // b471: цены обмена приехали в составе конфига — биржу и панель перерисовываем
                try { renderMarketIfVisible(); } catch (e) {}
            }'''))

PAIRS.append(('assets/app.js', 1,
              '''                    state.cards.filter(c => cardCopies(c.id) > 0).map(c => c.id + cardCopies(c.id)).join(',') + '|S' + marketSystemLots().length + '|C' + marketShownCap;''',
              '''                    state.cards.filter(c => cardCopies(c.id) > 0).map(c => c.id + cardCopies(c.id)).join(',') + '|S' + marketSystemLots().length + '|C' + marketShownCap + '|H' + mktSig();   // b471: '|H' — цены Дома, иначе витрина залипла бы на старых ценниках'''))

PAIRS.append(('assets/app.js', 1,
              '''        function jpcVisible() {''',
              '''        // ============ b471: ПАНЕЛЬ ЦЕН ОБМЕНА В СТУДИИ ============
        // Всё читается/пишется через jpc.mkt, публикация — та же, что у настроек
        // джекпота (jpc.at + jpcSave + jpSyncNow), доступ — тот же jpcAdminGuard.
        function mktPricesRender() {
            const m = (jpc && jpc.mkt) ? jpc.mkt : jpcMktNorm(null);
            MKT_KINDS.forEach(kind => MKT_RARITIES.forEach(r => {
                const el = document.getElementById('mkt-' + kind.k + '-' + r);
                if (el && document.activeElement !== el) el.value = String(m[kind.k][r]);   // не вырываем ввод из-под курсора
            }));
            const note = document.getElementById('mkt-price-note');
            if (note) {
                const n = Object.keys(m.card || {}).length;
                note.textContent = 'Цены применяются к витрине биржи у всех игроков сайта после публикации'
                    + (jpc && jpc.at ? ' (конфиг опубликован ' + new Date(jpc.at).toLocaleString('ru-RU') + ')' : '')
                    + '. Личных цен на карты задано: ' + n + '.';
            }
            mktCardOverRender();
            mktCardSearch();
        }
        function mktPricesRead() {
            const cfg = { house: {}, buy: {}, suggest: {} };
            const bad = [];
            MKT_KINDS.forEach(kind => MKT_RARITIES.forEach(r => {
                const el = document.getElementById('mkt-' + kind.k + '-' + r);
                const v = mktParseNum(el ? el.value : '');
                if (isFinite(v)) cfg[kind.k][r] = v;
                else { bad.push(kind.ru + ' / ' + (RARITY_LABELS_RU[r] || r)); cfg[kind.k][r] = MKT_DEFAULTS[kind.k][r]; }
            }));
            return { cfg: cfg, bad: bad };
        }
        function mktPublish(msg) {
            jpc.at = Date.now(); jpc.by = JACKPOT_CID;
            jpcSave();
            try { jpSyncNow(); } catch (e) {}
            try { mktPricesRender(); renderMarketIfVisible(); } catch (e) {}
            if (msg) showToast(msg, 'success');
        }
        function mktPricesPublish() {
            if (jpcAdminGuard()) return;
            const r = mktPricesRead();
            if (r.bad.length) {
                showToast('Не понял значения: ' + r.bad.join(', ') + '. Введите число или значение с суффиксом: 35b = 35 000 000 000, 4.5m = 4 500 000', 'error');
                return;
            }
            jpc.mkt = jpcMktNorm({ house: r.cfg.house, buy: r.cfg.buy, suggest: r.cfg.suggest, card: (jpc.mkt && jpc.mkt.card) || {} });
            mktPublish('🏛 Цены обмена опубликованы для всех игроков сайта');
        }
        function mktPricesReset() {
            if (jpcAdminGuard()) return;
            jpc.mkt = jpcMktNorm(null);   // заводские таблицы; личные цены карт снимаются тоже
            mktPublish('Цены обмена возвращены к заводским и опубликованы');
        }
        // --- личная цена на отдельную карту ---
        let mktCardList = [], mktOverList = [];
        function mktCardFind() {
            const q = String((document.getElementById('mkt-card-q') || {}).value || '').trim().toLowerCase();
            const all = (state.cards || []).filter(c => c && c.id);
            const hit = q
                ? all.filter(c => String(c.name || '').toLowerCase().indexOf(q) >= 0 || String(c.id).toLowerCase().indexOf(q) >= 0)
                : all;
            return hit.slice(0, 20);
        }
        function mktCardSearch() {
            const box = document.getElementById('mkt-card-list');
            if (!box) return;
            mktCardList = mktCardFind();
            if (!mktCardList.length) { nxSetHtml(box, '<p class="text-[11px] text-slate-500">Ничего не найдено</p>'); return; }
            const card = (jpc.mkt && jpc.mkt.card) ? jpc.mkt.card : {};
            nxSetHtml(box, mktCardList.map((c, i) => {
                const over = card[c.id] ? Number(card[c.id].h) : 0;
                const inp = '<input id="mkt-cp-' + i + '" type="text" inputmode="decimal" value="' + (over || '') +
                    '" placeholder="цена" class="w-20 shrink-0 bg-slate-900 border border-slate-700 rounded px-2 py-1 text-[11px] font-bold text-white">';
                return '<div class="flex items-center gap-1.5 bg-slate-950/60 border border-slate-800 rounded-lg px-2 py-1.5">' +
                    '<span class="flex-1 min-w-0 truncate text-[11px] font-bold text-slate-200">' + jpcEsc(c.name || 'Без имени') +
                    ' <span class="text-slate-500 font-normal">' + jpcEsc(RARITY_LABELS_RU[c.rarity] || c.rarity || '') + '</span></span>' +
                    '<span class="text-[9px] text-slate-500 whitespace-nowrap">' + (over ? 'лично' : 'сейчас') + ' ' + fmtCoins(over || marketHousePrice(c)) + '</span>' +
                    inp +
                    '<button type="button" onclick="mktCardSet(' + i + ')" class="shrink-0 px-2 py-1 bg-violet-600 hover:bg-violet-500 rounded text-[10px] font-bold text-white">Задать</button>' +
                    (over ? '<button type="button" onclick="mktCardClearIdx(' + i + ')" class="shrink-0 px-2 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded text-[10px] font-bold text-slate-300">Снять</button>' : '') +
                    '</div>';
            }).join(''));
        }
        function mktCardSet(i) {
            if (jpcAdminGuard()) return;
            const c = mktCardList[i];
            if (!c || !c.id) return;
            const el = document.getElementById('mkt-cp-' + i);
            const v = mktParseNum(el ? el.value : '');
            if (!isFinite(v) || v <= 0) {
                showToast('Введите цену числом или с суффиксом (35b, 4.5m). Ноль задать нельзя — чтобы вернуть цену по редкости, нажмите «Снять»', 'error');
                return;
            }
            if (!jpc.mkt) jpc.mkt = jpcMktNorm(null);
            if (!jpc.mkt.card) jpc.mkt.card = {};
            jpc.mkt.card[c.id] = { h: v, t: Date.now() };
            mktPublish('🏛 Личная цена «' + (c.name || c.id) + '» = ' + fmtCoins(v) + ' — опубликовано');
        }
        function mktCardDrop(id) {
            if (jpcAdminGuard()) return;
            if (!jpc.mkt || !jpc.mkt.card || !jpc.mkt.card[id]) return;
            delete jpc.mkt.card[id];
            const c = (state.cards || []).find(x => x && x.id === id);
            mktPublish('Личная цена снята — «' + ((c && c.name) || id) + '» снова по редкости');
        }
        function mktCardClearIdx(i) { const c = mktCardList[i]; if (c && c.id) mktCardDrop(c.id); }
        function mktCardClearId(i) { const id = mktOverList[i]; if (id) mktCardDrop(id); }
        function mktCardOverRender() {
            const box = document.getElementById('mkt-card-over');
            if (!box) return;
            const card = (jpc.mkt && jpc.mkt.card) ? jpc.mkt.card : {};
            mktOverList = Object.keys(card);
            if (!mktOverList.length) { nxSetHtml(box, ''); return; }
            const byId = {};
            (state.cards || []).forEach(c => { if (c && c.id) byId[c.id] = c; });
            nxSetHtml(box, '<p class="text-[10px] font-bold text-slate-400">Заданные личные цены (' + mktOverList.length + '):</p>' +
                mktOverList.map((id, i) => {
                    const c = byId[id] || {};
                    return '<div class="flex items-center gap-2 text-[11px]">' +
                        '<span class="flex-1 min-w-0 truncate text-slate-300">' + jpcEsc(c.name || id) + '</span>' +
                        '<span class="text-amber-300 font-bold whitespace-nowrap">' + fmtCoins(Number(card[id].h) || 0) + '</span>' +
                        '<button type="button" onclick="mktCardClearId(' + i + ')" class="shrink-0 px-2 py-0.5 bg-slate-800 hover:bg-rose-950/70 border border-slate-700 rounded text-[10px] font-bold text-slate-300">Снять</button>' +
                        '</div>';
                }).join(''));
        }
        function jpcVisible() {'''))

PAIRS.append(('assets/app.js', 1,
              '''            jpcAdminPreview();
            jpcAdminUsers();''',
              '''            jpcAdminPreview();
            jpcAdminUsers();
            try { mktPricesRender(); } catch (e) {}   // b471: цены обмена — в той же панели'''))

PAIRS.append(('index.html', 1,
              '''                <div id="jpc-sim-out" class="text-[11px] text-slate-300"></div>
            </div>
            </div><!-- /studio-sec jackpot -->''',
              '''                <div id="jpc-sim-out" class="text-[11px] text-slate-300"></div>
            </div>

            <!-- b471: цены обмена «🏛 Дом коллекционера». Раньше все три таблицы
                 были зашиты константами в assets/app.js; теперь это настройки
                 владельца, лежат в jpc.mkt и уезжают всем игрокам вместе с
                 конфигом джекпота. -->
            <div class="bg-slate-900/80 p-3 sm:p-4 rounded-2xl border border-slate-800 space-y-3">
                <h3 class="text-sm font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-landmark text-amber-400"></i>
                    <span>Дом коллекционера: цены обмена</span>
                </h3>
                <p class="text-[11px] text-slate-400 leading-snug">
                    <b class="text-slate-200">Витрина Дома</b> — сколько игрок платит Дому за карту.
                    <b class="text-slate-200">Выкуп лота</b> — сколько игрок получает, когда Дом забирает залежавшийся лот
                    (специально низкая: защищает от накрутки).
                    <b class="text-slate-200">Рекоменд.</b> — что подставляется, когда игрок сам выставляет дубликат.
                    Вводить можно числом или с суффиксом: <span class="font-mono text-slate-200">35b</span> = 35 000 000 000,
                    <span class="font-mono text-slate-200">4.5m</span> = 4 500 000, <span class="font-mono text-slate-200">900k</span> = 900 000.
                </p>
                <div class="overflow-x-auto">
                    <table class="w-full text-[11px] border-separate" style="border-spacing:0 4px">
                        <thead>
                            <tr class="text-slate-500">
                                <th class="font-bold pr-2 text-left">Редкость</th>
                                <th class="font-bold px-1 text-left">Витрина Дома</th>
                                <th class="font-bold px-1 text-left">Выкуп лота</th>
                                <th class="font-bold px-1 text-left">Рекоменд.</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td class="pr-2 font-bold text-slate-300 whitespace-nowrap">Обычная</td>
                                <td class="px-1"><input id="mkt-house-common" type="text" inputmode="decimal" class="w-full min-w-[5.5rem] bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] font-bold text-white"></td>
                                <td class="px-1"><input id="mkt-buy-common" type="text" inputmode="decimal" class="w-full min-w-[5.5rem] bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] font-bold text-white"></td>
                                <td class="px-1"><input id="mkt-suggest-common" type="text" inputmode="decimal" class="w-full min-w-[5.5rem] bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] font-bold text-white"></td>
                            </tr>
                            <tr>
                                <td class="pr-2 font-bold text-slate-300 whitespace-nowrap">Редкая</td>
                                <td class="px-1"><input id="mkt-house-rare" type="text" inputmode="decimal" class="w-full min-w-[5.5rem] bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] font-bold text-white"></td>
                                <td class="px-1"><input id="mkt-buy-rare" type="text" inputmode="decimal" class="w-full min-w-[5.5rem] bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] font-bold text-white"></td>
                                <td class="px-1"><input id="mkt-suggest-rare" type="text" inputmode="decimal" class="w-full min-w-[5.5rem] bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] font-bold text-white"></td>
                            </tr>
                            <tr>
                                <td class="pr-2 font-bold text-slate-300 whitespace-nowrap">Эпическая</td>
                                <td class="px-1"><input id="mkt-house-epic" type="text" inputmode="decimal" class="w-full min-w-[5.5rem] bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] font-bold text-white"></td>
                                <td class="px-1"><input id="mkt-buy-epic" type="text" inputmode="decimal" class="w-full min-w-[5.5rem] bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] font-bold text-white"></td>
                                <td class="px-1"><input id="mkt-suggest-epic" type="text" inputmode="decimal" class="w-full min-w-[5.5rem] bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] font-bold text-white"></td>
                            </tr>
                            <tr>
                                <td class="pr-2 font-bold text-slate-300 whitespace-nowrap">Легендарная</td>
                                <td class="px-1"><input id="mkt-house-legendary" type="text" inputmode="decimal" class="w-full min-w-[5.5rem] bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] font-bold text-white"></td>
                                <td class="px-1"><input id="mkt-buy-legendary" type="text" inputmode="decimal" class="w-full min-w-[5.5rem] bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] font-bold text-white"></td>
                                <td class="px-1"><input id="mkt-suggest-legendary" type="text" inputmode="decimal" class="w-full min-w-[5.5rem] bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] font-bold text-white"></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div class="flex flex-wrap gap-2">
                    <button type="button" onclick="mktPricesPublish()" class="px-3 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-[11px] font-bold text-white transition"><i class="fa-solid fa-bullhorn mr-1"></i>Опубликовать цены</button>
                    <button type="button" onclick="mktPricesReset()" class="px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-[11px] font-bold text-slate-300 transition"><i class="fa-solid fa-rotate-left mr-1"></i>Сбросить к заводским</button>
                </div>
                <p id="mkt-price-note" class="text-[10px] text-slate-500"></p>
                <div class="border-t border-slate-800 pt-3 space-y-2">
                    <p class="text-[11px] font-bold text-slate-300">Личная цена на карту</p>
                    <p class="text-[10px] text-slate-500 leading-snug">Переопределяет цену <b>витрины Дома</b> для одной карты, независимо от редкости. На выкуп и рекомендованную цену не влияет. Ноль задать нельзя — чтобы вернуть цену по редкости, нажмите «Снять».</p>
                    <input id="mkt-card-q" type="search" oninput="mktCardSearch()" placeholder="Название или id карты…" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-[11px] font-bold text-white placeholder-slate-600">
                    <div id="mkt-card-list" class="space-y-1 max-h-56 overflow-y-auto pr-1"></div>
                    <div id="mkt-card-over" class="space-y-1"></div>
                </div>
            </div>
            </div><!-- /studio-sec jackpot -->'''))


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
        txt = files.get(rel)
        if txt is None:
            txt = read(rel)
        if txt.count(old) != cnt:
            problems.append('%s: якорь встретился %d раз вместо %d: %s...' % (rel, txt.count(old), cnt, old[:60]))
            continue
        files[rel] = txt.replace(old, new)
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
        print('b471: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b471: цены обмена «Дом коллекционера» настраиваются в Студии; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
