#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b420 — «не синхронизируется с пользователями»: облачный документ похудел с 922 КБ до ~100 КБ.

Жалоба владельца: «чего не синхронизируется с пользователями». Замеры живого
документа nexus-tcg-jackpot-v2:

    чтение 919 КБ (2.6 c)   запись 922 КБ (3.5 c)   updatedAt свежий (4 c)
    jp  134 КБ   jpc 0 КБ   mk 752 КБ   st 31 КБ
    mk.rm = 16 918 записей = 728 КБ;  led/won: 4200 ключей, 4107 из них «#»-разряды

То есть textdb пишет и читает нормально (с десктопа), но КАЖДЫЙ синхронный
цикл игры (jpFetch → merge → jpPush, таймауты 15 c из b404) таскает 922 КБ.
На телефоне в LTE такая полезная нагрузка регулярно не долетает в таймаут,
catch глотает ошибку («банк дождётся следующей синхронизации») — и игрок
тихо выпадает из синхронизации. Владелец на десктопе sync видит, остальные — нет.

Откуда 922 КБ:

1. mk.rm — tombstone снятых лотов (b336). marketRemovedAdd() дома обрезал его
   до 300 ключей, НО marketMerge() сливал чужой rm БЕЗ обрезки: union по всем
   клиентам за всю историю = 16 918 записей. И marketDoc() пушил их все.
   Tombstone нужен лишь пока жив кэш виденных лотов (10 минут, b336).
2. jp: 4107 «#»-ключей — наследие вёдер b418 с устройства владельца: 134 КБ.

Стало:

* marketRemovedPrune(): rm живёт 2 часа (MK_RM_TTL) и не больше 300 записей
  (MK_RM_MAX); вызывается в marketMerge, marketDoc, marketRemovedAdd/Many —
  728 КБ → единицы КБ;
* уплотнение реестра банка jpCompact(): все разряды игрока сводятся в
  минимальный каскад, эпоха jp.ep увеличивается; клиенты b420+ при ep > своей
  принимают реестр ЦЕЛИКОМ (иначе старые ключи возвращались бы max-слиянием);
  134 КБ → единицы КБ;
* автоуплотнение: после успешного цикла синхронизации, если jpDoc() > 600 КБ и
  прошло > 5 минут (и мы не гость) — jpCompact(true) без тоста;
* кнопка Студии «Уплотнить реестр» рядом с «Починить банк».

Запуск:  python3 tools/_b420_patch.py            — применить
         python3 tools/_b420_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob81'
NEW_V = 'nxmob82'

# --------------------------------------------------------------------------- #
# app.js
# --------------------------------------------------------------------------- #

OLD_RM_ADD = """        function marketRemovedAdd(id) {
            try { const o = marketRemoved(); o[id] = Date.now(); const ks = Object.keys(o); if (ks.length > 300) delete o[ks[0]]; LS.setItem('nexus_market_removed', JSON.stringify(o)); } catch (e) {}
        }
"""

NEW_RM_ADD = """        // b420: tombstone снятых лотов раньше сливался без обрезки (union по всем
        // клиентам за историю = 16 918 записей = 728 КБ в каждом пуше) — мобильные
        // клиенты не долетали в 15-секундный таймаут и выпадали из синхронизации.
        // Tombstone нужен лишь пока жив кэш виденных лотов (10 минут, b336):
        // держим 2 часа и не больше 300 записей.
        const MK_RM_TTL = 2 * 60 * 60 * 1000;
        const MK_RM_MAX = 300;
        function marketRemovedPrune(o) {
            try {
                const cut = Date.now() - MK_RM_TTL;
                let ks = Object.keys(o || {});
                for (let i = 0; i < ks.length; i++) if ((o[ks[i]] || 0) < cut) delete o[ks[i]];
                ks = Object.keys(o || {}).sort((a, b) => (o[a] || 0) - (o[b] || 0));
                if (ks.length > MK_RM_MAX) ks.slice(0, ks.length - MK_RM_MAX).forEach(k => delete o[k]);
            } catch (e) {}
            return o;
        }
        function marketRemovedAdd(id) {
            try { const o = marketRemoved(); o[id] = Date.now(); marketRemovedPrune(o); LS.setItem('nexus_market_removed', JSON.stringify(o)); } catch (e) {} // b420: prune
        }
"""

OLD_RM_MANY = """                const o = marketRemoved();
                const now = Date.now();
                for (let i = 0; i < ids.length; i++) o[ids[i]] = now;
                const ks = Object.keys(o);
                if (ks.length > 300) { ks.slice(0, ks.length - 300).forEach(k => delete o[k]); }
                LS.setItem('nexus_market_removed', JSON.stringify(o));
"""
NEW_RM_MANY = """                const o = marketRemoved();
                const now = Date.now();
                for (let i = 0; i < ids.length; i++) o[ids[i]] = now;
                marketRemovedPrune(o); // b420: возраст + количество, а не «первые 300»
                LS.setItem('nexus_market_removed', JSON.stringify(o));
"""

OLD_MERGE_RM = """                    const o = JSON.parse(LS.getItem('nexus_market_removed') || '{}');
                    let ch2 = false;
                    for (const k in rrm) { if (rrm[k] && (!o[k] || rrm[k] > o[k])) { o[k] = rrm[k]; ch2 = true; } }
                    if (ch2) LS.setItem('nexus_market_removed', JSON.stringify(o));
"""
NEW_MERGE_RM = """                    const o = JSON.parse(LS.getItem('nexus_market_removed') || '{}');
                    let ch2 = false;
                    for (const k in rrm) { if (rrm[k] && (!o[k] || rrm[k] > o[k])) { o[k] = rrm[k]; ch2 = true; } }
                    marketRemovedPrune(o); // b420: чужой rm больше не раздувает наш документ
                    if (ch2) LS.setItem('nexus_market_removed', JSON.stringify(o));
"""

OLD_MDOC = "            return { lots: marketLots().slice(-80), ledger: (Array.isArray(CLOUD.ledger) ? CLOUD.ledger : []).slice(-60), rm: marketRemoved() }; // b336: rm — снятые лоты\n"
NEW_MDOC = "            return { lots: marketLots().slice(-80), ledger: (Array.isArray(CLOUD.ledger) ? CLOUD.ledger : []).slice(-60), rm: marketRemovedPrune(marketRemoved()) }; // b336: rm — снятые лоты; b420: обрезанные по возрасту/количеству\n"

OLD_LOAD_EP = "                if (j && j.led) return { led: j.led || {}, won: j.won || {}, wins: j.wins || {}, names: j.names || {}, hall: jpHallFiltered(j.hall, j.hallCut), hallCut: Math.floor(j.hallCut) || 0 }; // b418: tombstone зала славы\n"
NEW_LOAD_EP = "                if (j && j.led) return { led: j.led || {}, won: j.won || {}, wins: j.wins || {}, names: j.names || {}, hall: jpHallFiltered(j.hall, j.hallCut), hallCut: Math.floor(j.hallCut) || 0, ep: Math.floor(j.ep) || 0 }; // b418: tombstone зала славы; b420: эпоха реестра\n"

OLD_MERGE_HEAD = """            pick(jackpot.led, remote.led); pick(jackpot.won, remote.won); pick(jackpot.wins, remote.wins);
            if (jpRepairLedger()) ch = true; // b416: облако (или старый клиент) могло притащить счётчики-гиганты
"""
NEW_MERGE_HEAD = """            // b420: эпоха реестра. После уплотнения (jpCompact) реестр принимается
            // ЦЕЛИКОМ: max-слияние вернуло бы старые ключи-разряды и документ снова
            // раздулся бы; имена/зал славы ниже сливаются как обычно
            const rep = Math.floor(remote.ep) || 0;
            const myEp = Math.floor(jackpot.ep) || 0;
            if (rep > myEp) {
                jackpot.led = (remote.led && typeof remote.led === 'object') ? remote.led : {};
                jackpot.won = (remote.won && typeof remote.won === 'object') ? remote.won : {};
                jackpot.wins = (remote.wins && typeof remote.wins === 'object') ? remote.wins : {};
                jackpot.ep = rep;
            } else if (rep === myEp) {
                pick(jackpot.led, remote.led); pick(jackpot.won, remote.won); pick(jackpot.wins, remote.wins);
            }
            // b420: rep < myEp — реестр собеседника старше нашего уплотнения
            // (или вообще без эпохи): его ключи легли бы ПОВЕРХ уплотнённых и
            // удвоили бы банк, поэтому реестр от него не принимается (имена и
            // зал славы ниже сливаются как обычно). Он догонит после обновления.
            if (jpRepairLedger()) ch = true; // b416: облако (или старый клиент) могло притащить счётчики-гиганты
"""

OLD_DOC_EP = "                jp: { led: jackpot.led, won: jackpot.won, wins: jackpot.wins, names: jackpot.names, hall: jackpot.hall, hallCut: jackpot.hallCut || 0 }, // b418: tombstone зала славы едет со всеми\n"
NEW_DOC_EP = "                jp: { led: jackpot.led, won: jackpot.won, wins: jackpot.wins, names: jackpot.names, hall: jackpot.hall, hallCut: jackpot.hallCut || 0, ep: Math.floor(jackpot.ep) || 0 }, // b418: tombstone; b420: эпоха реестра\n"

OLD_COMPACT_ANCHOR = """        function jpRepairNow() {
"""
NEW_COMPACT = """        // b420: уплотнение реестра: все разряды игрока сводятся в минимальный
        // каскад (1–10 ключей вместо тысяч), эпоха ep увеличивается — клиенты b420+
        // примут реестр целиком, старые ключи уйдут из облака и из localStorage.
        // Суммы (Σled − Σwon) сохраняются, значит банк не меняется.
        function jpCompact(silent) {
            if (jpcAdminGuard()) return false;
            // b420: клиент ДО эпох (nxmob81 и старше) не знает ep и при max-слиянии
            // вернёт старые ключи-разряды поверх уплотнённых — банк удвоится.
            // Поэтому уплотняем только когда старых клиентов не было видно 10 минут
            if ((window.__nxJpLegacyAt || 0) > Date.now() - 600000) {
                if (!silent) showToast('⏳ Сейчас активен клиент старой версии — уплотнение удвоит его витрину. Обновите все вкладки игры и повторите', 'error');
                return false;
            }
            const rebuild = f => {
                const src = jackpot[f] || {};
                const totals = {};
                for (const k in src) {
                    const h = k.indexOf('#');
                    const base = h > 0 ? k.slice(0, h) : k;
                    totals[base] = (totals[base] || 0) + jpLedNum(src[k], jpTierOfKey(k));
                }
                const out = {};
                for (const base in totals) {
                    let left = Math.floor(totals[base] || 0);
                    for (let i = 0; left > 0 && i < JP_TIERS; i++) {
                        const put = Math.min(left, jpTierCap(i));
                        if (put > 0) out[jpBucketKey(base, i)] = put;
                        left -= put;
                    }
                }
                return out;
            };
            jackpot.led = rebuild('led');
            jackpot.won = rebuild('won');
            jackpot.ep = (Math.floor(jackpot.ep) || 0) + 1;
            jackpotSave(); jackpotRender();
            try { jpcAdminPreview(); } catch (e) {}
            try { jpSyncNow(); } catch (e) {}
            if (!silent) showToast('📦 Реестр банка уплотнён до ' + (Object.keys(jackpot.led).length + Object.keys(jackpot.won).length) + ' ключей и опубликован (эпоха ' + jackpot.ep + ')', 'success');
            return true;
        }
        function jpDocBytes() { try { return JSON.stringify(jpDoc()).length; } catch (e) { return 0; } }
        function jpRepairNow() {
"""

OLD_SYNC_TAIL = """                    jpcApplyGrants();           // b414: назначенный мне джекпот — сразу на баланс
                    statsRenderIfVisible();     // b277
                    renderMarketIfVisible();
"""
NEW_SYNC_TAIL = """                    jpcApplyGrants();           // b414: назначенный мне джекпот — сразу на баланс
                    statsRenderIfVisible();     // b277
                    renderMarketIfVisible();
                    // b420: документ распух → уплотняем реестр (владелец комнаты),
                    // иначе мобильные клиенты не долетают в 15-секундный таймаут
                    try {
                        if (!cloudGuest() && jpDocBytes() > 600000 && Date.now() - (window.__nxJpCompactAt || 0) > 300000) {
                            window.__nxJpCompactAt = Date.now();
                            jpCompact(true);
                        }
                    } catch (e) {}
"""

JS_PATCHES = [
    ('rm: prune + константы (b420)', OLD_RM_ADD, NEW_RM_ADD),
    ('rm: пакетный prune', OLD_RM_MANY, NEW_RM_MANY),
    ('rm: prune при слиянии', OLD_MERGE_RM, NEW_MERGE_RM),
    ('marketDoc: prune rm', OLD_MDOC, NEW_MDOC),
    ('jackpotLoad: ep', OLD_LOAD_EP, NEW_LOAD_EP),
    ('jackpotMerge: эпоха реестра', OLD_MERGE_HEAD, NEW_MERGE_HEAD),
    ('jpDoc: ep', OLD_DOC_EP, NEW_DOC_EP),
    ('jpCompact + jpDocBytes', OLD_COMPACT_ANCHOR, NEW_COMPACT),
    ('автоуплотнение после синка', OLD_SYNC_TAIL, NEW_SYNC_TAIL),
]

HTML_PATCHES = [
    ('кнопка «Уплотнить реестр»',
     '<button type="button" onclick="jpRepairNow()" title="Выбросить испорченные счётчики реестра и погасить долг банка" class="px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-slate-950 rounded-lg text-[11px] font-black transition"><i class="fa-solid fa-screwdriver-wrench mr-1"></i>Починить банк</button>',
     '<button type="button" onclick="jpRepairNow()" title="Выбросить испорченные счётчики реестра и погасить долг банка" class="px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-slate-950 rounded-lg text-[11px] font-black transition"><i class="fa-solid fa-screwdriver-wrench mr-1"></i>Починить банк</button>\n'
     '                    <button type="button" onclick="jpCompact()" title="Свести тысячи ключей-разрядов в минимальный каскад и опубликовать (эпоха +1): облачный документ станет легче, синхронизация — быстрее" class="px-2.5 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-[11px] font-black transition"><i class="fa-solid fa-boxes-stacked mr-1"></i>Уплотнить реестр</button>'),
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
            n = s.count(old); bad += (n != 1); print('  %s %-36s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        h = open(html, encoding='utf-8').read()
        for label, old, _n in HTML_PATCHES:
            n = h.count(old); bad += (n != 1); print('  %s %-36s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        return 1 if bad else 0

    s = open(js, encoding='utf-8').read()
    for label, old, new in JS_PATCHES:
        s = patch_once(s, old, new, label); print('  · %-36s ok' % label)
    open(js, 'w', encoding='utf-8', newline='').write(s)

    h = open(html, encoding='utf-8').read()
    for label, old, new in HTML_PATCHES:
        h = patch_once(h, old, new, label); print('  · %-36s ok' % label)
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
