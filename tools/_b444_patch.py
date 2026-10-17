#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b444: банк на атомарных вызовах + кнопка «Вернуть карты» в Студии.

Ставится ПОСЛЕ b442 и b443 (тег nxmob173 -> nxmob174). Требует задеплоенного
воркера NX-CLOUD и assets/nx-cloud.js с блоками NXM/NXJ. Если API не отвечает —
всё идёт прежним путём (документ целиком), без задержек на таймауты:
NXJ.available() становится true только после успешного ответа сервера.

────────────────────────────────────────────────────────────────────────────
 ЧАСТЬ 1. Банк: 118 КБ на спин -> ~200 байт
────────────────────────────────────────────────────────────────────────────
Было: каждый спин и каждый проигрыш вызывали jpSyncSoon(), который скачивал
общий документ (118 КБ, 1.8 с на textdb), менял его в памяти и заливал обратно.
Два одновременных срыва банка гасили друг друга, а «банк замерзает» лечилось
вручную через tools/repair_cloud_bank.py.

Стало: jackpotFeed/jackpotOnLoss/jackpotWin дополнительно шлют
POST /api/jp/feed и /api/jp/win, где банк меняется одним выражением
    UPDATE jp_state SET pot = MAX(floor, pot + ?) WHERE id = 1
внутри транзакции. Тест: 50 одновременных взносов = ровно +50; 20 отправок
с одним oid = ровно одно начисление.

Двойная запись (клиент в свой локальный реестр + сервер в свой) БЕЗОПАСНА:
absorbJp на сервере сливает реестры через MAX на ключ, поэтому оба значения
сходятся к одному. Ни пуш документа, ни повторная доставка запроса (oid)
взнос не удваивают — проверено тестами [6] и [8] в jp-atomic-test.mjs.

Две тонкости, из-за которых атомарный путь включается не всегда:
  · amount передаётся УЖЕ ПОСЧИТАННЫЙ клиентом (с его jpc.feedBet/feedLoss),
    иначе сервер прибавил бы другую сумму и MAX-слияние медленно разъезжалось;
  · на счётчиках больше 1e12 атомарный путь отключается: сервер пишет в ключ
    разряда 0 (JACKPOT_CID), а клиент следующий взнос положит уже в
    JACKPOT_CID#1 — MAX по двум разным ключам задвоил бы сумму.

────────────────────────────────────────────────────────────────────────────
 ЧАСТЬ 2. Кнопка «Вернуть карты»
────────────────────────────────────────────────────────────────────────────
b442 добавил nxRescueCollection()/nxRestoreArchive(), но вызывать их можно было
только из консоли. Теперь в Студии рядом с «Починить банк» стоит кнопка, которая
показывает, сколько найдено, спрашивает подтверждение и возвращает:
  · число копий — по теневому снимку коллекции (nx_col_shadow);
  · определения карт и паков — из архива зеркала комнаты (nexus_guest_archive).
Кнопка доступна всем игрокам (без jpcAdminGuard) — спасают они свои карты.

────────────────────────────────────────────────────────────────────────────
 ВАЖНО ПРО СБОРЩИК
────────────────────────────────────────────────────────────────────────────
tools/source-index.html в репозитории остановился на b397, а assets/app.js — на
b441. Запуск `python3 tools/build.py` сейчас ОТКАТИЛ БЫ игру на 44 правки назад
(пропали бы jpLedAdd/jpRepairLedger/MARKET_HARD_TRIM/nxDescScrollHint — все
фиксы целостности банка и биржи). Поэтому этот патч, как и b441/b442/b443,
правит СОБРАННЫЕ файлы (assets/app.js и index.html) и build.py запускать НЕ НАДО.

Проверка/применение:
    python3 tools/_b444_patch.py --check
    python3 tools/_b444_patch.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = []

PAIRS.append(('app.js: помощники атомарного банка + nxRescueCards (b444)', """
        function jpRepairNow() {
            // кнопка «Починить банк» в Студии: то же самое, что автоматика, но сразу
""", """
        // ============ b444: АТОМАРНЫЙ БАНК ============
        // window.NXJ даёт assets/nx-cloud.js. available() — тот же флаг, что у
        // биржи: true только после успешного ответа сервера, поэтому без
        // задеплоенного воркера всё идёт прежним путём и ничего не тормозит.
        function nxJp() {
            try { const j = window.NXJ; return (j && j.available && j.available()) ? j : null; } catch (e) { return null; }
        }
        // Ключ операции: сервер гасит повторную доставку того же запроса
        // (INSERT OR IGNORE в jp_ops), поэтому взнос не начислится дважды.
        function nxJpOid(kind) {
            return kind + '-' + JACKPOT_CID + '-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
        }
        function nxJpCanAtomic(add) {
            const j = nxJp();
            if (!j) return null;
            try {
                // Атомарный эндпоинт пишет в ключ разряда 0 (JACKPOT_CID). Когда
                // счётчик подходит к ёмкости разряда (1e13), клиент следующий взнос
                // положит уже в JACKPOT_CID#1 — а MAX-слияние двух РАЗНЫХ ключей
                // задвоило бы сумму. Поэтому на больших величинах остаётся документ.
                if (jpLedNum(jackpot.led[JACKPOT_CID], 0) + (Number(add) || 0) > 1e12) return null;
                if (jpLedNum(jackpot.won[JACKPOT_CID], 0) > 1e12) return null;
            } catch (e) { return null; }
            return j;
        }
        // b444: кнопка «Вернуть карты» в Студии. Доступна ВСЕМ игрокам (без
        // jpcAdminGuard) — спасают они свою коллекцию, а не банк сайта.
        function nxRescueCards() {
            try {
                const rep = nxRescueReport();
                const arc = cloudGuestArchive();
                const arcC = ((arc && arc.cards) || []).length;
                const arcP = ((arc && arc.packs) || []).length;
                if (!rep.lost && !arcC && !arcP) {
                    showToast('Терять нечего: коллекция цела, архив зеркала пуст', 'info');
                    return 0;
                }
                const parts = [];
                if (rep.lost) parts.push(rep.lost + ' ' + pluralRu(rep.lost, 'копия', 'копии', 'копий') + ' карт');
                if (arcC || arcP) parts.push((arcC + arcP) + ' ' + pluralRu(arcC + arcP, 'определение', 'определения', 'определений') + ' в архиве зеркала');
                const msg = 'Вернуть пропавшие карты?\\n\\nНайдено: ' + parts.join(', ') + '.\\n\\n' +
                    'Число копий восстановится по теневому снимку коллекции, определения карт и паков — ' +
                    'из архива, куда их складывало «зеркало комнаты».\\n\\n' +
                    'Честно проданные копии не воскреснут, если после продажи прошло больше 10 минут.';
                if (typeof confirm === 'function' && !confirm(msg)) return 0;
                const defs = nxRestoreArchive();
                const back = nxRescueCollection(true);
                try { saveState(); } catch (e) {}
                try { refreshVisibleTabs(); } catch (e) {}
                try { profSyncSoon(); } catch (e) {}
                try { cloudPublishSoon(); } catch (e) {}
                try { nxCrashLog('nxRescueCards: +' + back + ' копий, +' + defs + ' определений'); } catch (e) {}
                showToast('🛟 Возвращено: ' + back + ' ' + pluralRu(back, 'копия', 'копии', 'копий') +
                    (defs ? ', определений карт и паков: ' + defs : ''), back || defs ? 'success' : 'info');
                return back;
            } catch (e) {
                try { nxCrashLog('nxRescueCards: ' + ((e && e.message) || e)); } catch (e2) {}
                showToast('Не удалось вернуть карты: ' + ((e && e.message) || e), 'error');
                return 0;
            }
        }
        function jpRepairNow() {
            // кнопка «Починить банк» в Студии: то же самое, что автоматика, но сразу
"""))

# ── 2. Взнос со ставки ───────────────────────────────────────────────────────
PAIRS.append(('app.js: jackpotFeed шлёт взнос атомарно', """
            jpLedAdd('led', JACKPOT_CID, x); // b416: запись через потолок — счётчик больше не улетает в 1e57
            jackpotSave(); jackpotRender(); jpSyncSoon();
""", """
            jpLedAdd('led', JACKPOT_CID, x); // b416: запись через потолок — счётчик больше не улетает в 1e57
            // b444: взнос уходит и на сервер — pot = pot + x одним выражением.
            // amount передаём УЖЕ ПОСЧИТАННЫЙ (по своим jpc.feedBet), чтобы сервер
            // прибавил ровно столько же: иначе MAX-слияние реестров разъезжается.
            try {
                const nxj = nxJpCanAtomic(x);
                if (nxj) nxj.feed({ cid: JACKPOT_CID, name: getPlayerName() || '', amount: x, oid: nxJpOid('f') });
            } catch (e) {}
            jackpotSave(); jackpotRender(); jpSyncSoon();
"""))

# ── 3. Взнос с проигрыша ─────────────────────────────────────────────────────
PAIRS.append(('app.js: jackpotOnLoss шлёт взнос атомарно', """
            const got = jpLedAdd('led', JACKPOT_CID, add); // b416: через потолок; возвращаем, сколько реально легло в банк
            jackpotSave(); jackpotRender(); jpSyncSoon();
            return got;
""", """
            const got = jpLedAdd('led', JACKPOT_CID, add); // b416: через потолок; возвращаем, сколько реально легло в банк
            // b444: на сервер уходит ровно то, что легло в реестр (got), а не add:
            // при переполнении разряда часть взноса уходит в старший разряд.
            try {
                const nxj = nxJpCanAtomic(got);
                if (nxj && got > 0) nxj.feed({ cid: JACKPOT_CID, name: getPlayerName() || '', amount: got, oid: nxJpOid('f') });
            } catch (e) {}
            jackpotSave(); jackpotRender(); jpSyncSoon();
            return got;
"""))

# ── 4. Срыв банка ────────────────────────────────────────────────────────────
PAIRS.append(('app.js: jackpotWin — атомарный срыв и общее время для зала славы', """
            jpLedAdd('won', JACKPOT_CID, Math.min(prize, jpExcess()));
            jackpot.wins[JACKPOT_CID] = (jackpot.wins[JACKPOT_CID] || 0) + 1;
            // b91: фиксируем победителя по имени — зал славы увидят все игроки сайта
            // b432: флаг nm — попал ли срыв в топ сайта (только игроки с именем)
            const realName = getPlayerName();
            const wname = realName || ('Игрок-' + JACKPOT_CID.slice(1, 5));
            jackpot.names[JACKPOT_CID] = wname;
            jackpot.hall = jackpot.hall || [];
            jackpot.hall.unshift({ n: wname, a: prize, t: Date.now(), c: JACKPOT_CID, nm: realName ? 1 : 0 });
""", """
            // b416: в реестр выплат пишем только обеспеченную часть
            const secured = Math.min(prize, jpExcess());
            jpLedAdd('won', JACKPOT_CID, secured);
            jackpot.wins[JACKPOT_CID] = (jackpot.wins[JACKPOT_CID] || 0) + 1;
            // b91: фиксируем победителя по имени — зал славы увидят все игроки сайта
            // b432: флаг nm — попал ли срыв в топ сайта (только игроки с именем)
            const realName = getPlayerName();
            const wname = realName || ('Игрок-' + JACKPOT_CID.slice(1, 5));
            jackpot.names[JACKPOT_CID] = wname;
            // b444: время срыва фиксируем ОДИН раз и отдаём то же значение серверу.
            // Зал славы дедуплицируется по (cid, ts, amount): расхождение в
            // миллисекунду между локальной записью и серверной дало бы ДВЕ записи.
            const wonAt = Date.now();
            jackpot.hall = jackpot.hall || [];
            jackpot.hall.unshift({ n: wname, a: prize, t: wonAt, c: JACKPOT_CID, nm: realName ? 1 : 0 });
            // b444: срыв атомарно — pot = MAX(floor, pot - prize) в транзакции.
            // Два одновременных срыва больше не гасят друг друга, а 118 КБ
            // документ летит только потом, обычным jpSyncNow().
            try {
                const nxj = nxJpCanAtomic();
                if (nxj) nxj.win({ cid: JACKPOT_CID, name: wname, amount: prize, secured: secured, at: wonAt, oid: nxJpOid('w') });
            } catch (e) {}
"""))

# b442 добавил nxRescueCollection() со своим тостом — учим её молчать по запросу,
# иначе кнопка покажет два тоста подряд.
PAIRS.append(('app.js: nxRescueCollection(silent)', """
        function nxRescueCollection() {
            const sh = nxColShadow();
""", """
        function nxRescueCollection(silent) { // b444: silent — тост покажет вызывающий
            const sh = nxColShadow();
"""))

PAIRS.append(('app.js: тост nxRescueCollection учитывает silent', """
                try { showToast('🛟 Возвращено: ' + back + ' ' + (back === 1 ? 'копия' : 'копий') + (defs ? ', определений карт: ' + defs : ''), 'success'); } catch (e) {}
""", """
                try { if (!silent) showToast('🛟 Возвращено: ' + back + ' ' + (back === 1 ? 'копия' : 'копий') + (defs ? ', определений карт: ' + defs : ''), 'success'); } catch (e) {}
"""))

# ── 6. Сама кнопка в разметке Студии ────────────────────────────────────────
PAIRS.append(('index.html: кнопка «Вернуть карты» рядом с «Починить банк»', """
                    <button type="button" onclick="jpRepairNow()" title="Выбросить испорченные счётчики реестра и погасить долг банка" class="px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-slate-950 rounded-lg text-[11px] font-black transition"><i class="fa-solid fa-screwdriver-wrench mr-1"></i>Починить банк</button>
""", """
                    <button type="button" onclick="nxRescueCards()" title="Вернуть копии карт по теневому снимку и определения из архива зеркала комнаты" class="px-2.5 py-1.5 bg-sky-600 hover:bg-sky-500 text-slate-950 rounded-lg text-[11px] font-black transition"><i class="fa-solid fa-life-ring mr-1"></i>Вернуть карты</button>
                    <button type="button" onclick="jpRepairNow()" title="Выбросить испорченные счётчики реестра и погасить долг банка" class="px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-slate-950 rounded-lg text-[11px] font-black transition"><i class="fa-solid fa-screwdriver-wrench mr-1"></i>Починить банк</button>
"""))

TAG_OLD = 'nxmob173'
TAG_NEW = 'nxmob174'
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
        assert old.strip() in txt, 'b444: не найден якорь: %s' % label
        assert txt.count(old.strip()) == 1, 'b444: якорь не уникален: %s (%d)' % (label, txt.count(old.strip()))
        files[rel] = txt.replace(old.strip(), new.strip(), 1)
    for rel, txt in files.items():
        write(rel, txt)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b444: не найден тег %s в %s (сначала _b442 и _b443)' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b444: применено')


def check():
    problems = []
    for label, old, new in PAIRS:
        rel = 'index.html' if label.startswith('index.html') else 'assets/app.js'
        txt = read(rel)
        if new.strip() not in txt:
            problems.append('%s: нет нового блока: %s' % (rel, label))
    app = read('assets/app.js')
    for extra in ('function nxJp(', 'function nxJpOid(', 'function nxJpCanAtomic(', 'function nxRescueCards(',
                  'nxj.feed({ cid: JACKPOT_CID, name: getPlayerName()',
                  'nxj.win({ cid: JACKPOT_CID, name: wname, amount: prize, secured: secured, at: wonAt',
                  'const wonAt = Date.now();', 'function nxRescueCollection(silent)',
                  'nxRescueCollection(true)'):
        if extra not in app:
            problems.append('app.js: нет %r' % extra)
    html = read('index.html')
    for extra in ('onclick="nxRescueCards()"', 'Вернуть карты', 'fa-life-ring'):
        if extra not in html:
            problems.append('index.html: нет %r' % extra)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не %s' % (rel, TAG_NEW))
    if problems:
        print('b444 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b444 --check: всё на месте (атомарные feed/win с oid и secured, общее время зала славы, '
          'кнопка «Вернуть карты», тег %s)' % TAG_NEW)


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
