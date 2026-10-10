#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пересобирает tools/apply_fix.py под правку b366: QR переноса прогресса
(кнопка QR в навбаре) теперь содержит ЕЩЁ и код профиля синхронизации —
отсканировавшее устройство и прогресс получает, и к профилю привязывается.
База — HEAD. Одноразовый служебный скрипт."""
import io, os, ast, subprocess

AP = 'tools/apply_fix.py'

qr_head = subprocess.run(['git', 'show', 'HEAD:assets/qr-transfer.js'], capture_output=True, text=True).stdout
assert qr_head, 'HEAD:assets/qr-transfer.js не читается'

QR_EDITS = [
    ('b366-snap-prof',
     "        const snap = qrxSnapshot();\n        const json = JSON.stringify(snap);",
     "        const snap = qrxSnapshot();\n"
     "        // b366: в тот же QR зашиваем код профиля синхронизации: устройство,\n"
     "        // отсканировавшее этот код, не только получит прогресс, но и привяжется\n"
     "        // к профилю — баланс и прогресс станут общими (правила b364).\n"
     "        try { let pc = profCode(); if (!pc) { pc = profGenCode(); profSetCode(pc, true); } snap.prof = pc; } catch (e) {}\n"
     "        const json = JSON.stringify(snap);"),
    ('b366-status',
     "        if (status) status.innerHTML = code.indexOf(QRX_DIRECT) === 0\n"
     "            ? '<i class=\"fa-solid fa-bolt text-amber-300 mr-1\"></i>Прямой код: весь прогресс зашит прямо в QR (' + code.length + ' символов)'\n"
     "            : '<i class=\"fa-solid fa-cloud text-violet-300 mr-1\"></i>Облачный ключ: снимок прогресса в транзитном облаке, в QR только ключ';",
     "        if (status) status.innerHTML = (code.indexOf(QRX_DIRECT) === 0\n"
     "            ? '<i class=\"fa-solid fa-bolt text-amber-300 mr-1\"></i>Прямой код: весь прогресс зашит прямо в QR (' + code.length + ' символов)'\n"
     "            : '<i class=\"fa-solid fa-cloud text-violet-300 mr-1\"></i>Облачный ключ: снимок прогресса в транзитном облаке, в QR только ключ')\n"
     "            + (snap.prof ? ' <span class=\"text-emerald-300\">• в QR также код профиля ' + cloudEsc(snap.prof) + ' — второе устройство сразу привяжется</span>' : '');"),
    ('b366-helper',
     "async function qrxHandleCode(raw) {",
     "function qrxApplyProf(o) { // b366: в коде переноса может лежать код профиля — привязываем устройство сразу\n"
     "    try {\n"
     "        const pc = (o && typeof o.prof === 'string') ? o.prof.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 12) : '';\n"
     "        if (pc && pc !== profCode()) {\n"
     "            profSetCode(pc);\n"
     "            try { showToast('Устройство привязано к профилю ' + pc + ' вместе с переносом — баланс и прогресс станут общими', 'success'); } catch (e) {}\n"
     "        }\n"
     "    } catch (e) {}\n"
     "}\n"
     "async function qrxHandleCode(raw) {"),
    ('b366-relay',
     "            const obj = await qrxRelayFetch(s.slice(QRX_RELAY.length));\n"
     "            if (!obj || !obj.d) throw new Error('облако не вернуло данные');\n"
     "            qrxShowConfirm(obj.d, null);",
     "            const obj = await qrxRelayFetch(s.slice(QRX_RELAY.length));\n"
     "            if (!obj || !obj.d) throw new Error('облако не вернуло данные');\n"
     "            qrxApplyProf(obj.d || obj); // b366: в relay-ветке профиль лежит внутри obj.d\n"
     "            qrxShowConfirm(obj.d, null);"),
    ('b366-direct',
     "            const json = await qrxInflate(qrxB64d(s.slice(QRX_DIRECT.length)));\n"
     "            if (!json) throw new Error('не удалось распаковать код');\n"
     "            qrxShowConfirm(JSON.parse(json), null);",
     "            const json = await qrxInflate(qrxB64d(s.slice(QRX_DIRECT.length)));\n"
     "            if (!json) throw new Error('не удалось распаковать код');\n"
     "            const objD = JSON.parse(json);\n"
     "            qrxApplyProf(objD); // b366\n"
     "            qrxShowConfirm(objD, null);"),
    ('b366-accept-baseline',
     "    qrxApplyProgress(p);\n    closeQrModal();",
     "    try { profHold(2500); } catch (e) {} // b366: фоновый синк не перетирает привезённый сейв\n"
     "    qrxApplyProgress(p);\n"
     "    // b366: база дельт = ПРИВЕЗЁННЫЙ баланс: локальные бонусы после accept\n"
     "    // (достижения и т.п.) уходят в общий профиль обычной дельтой, а сам перенос\n"
     "    // не прибавляется к общему балансу вторым разом\n"
     "    try { LS.setItem('nx_prof_lastbal', String(Math.max(0, Math.round(Number(p && p.c) || 0)))); } catch (e) {}\n"
     "    closeQrModal();"),
    ('b366-json',
     "        if (s.charAt(0) === '{') {\n"
     "            const o = JSON.parse(s);\n"
     "            if (o && o.v === 1 && o.col) { qrxShowConfirm(o, null); return; }",
     "        if (s.charAt(0) === '{') {\n"
     "            const o = JSON.parse(s);\n"
     "            qrxApplyProf(o); // b366\n"
     "            if (o && o.v === 1 && o.col) { qrxShowConfirm(o, null); return; }"),
]

APP_EDITS = [
    ('b367-ipauto-off',
     "        function profIpAuto() { try { return LS.getItem('nx_prof_ipauto') !== '0'; } catch (e) { return true; } }",
     "        function profIpAuto() { try { return LS.getItem('nx_prof_ipauto') === '1'; } catch (e) { return false; } } // b367: ПО УМОЛЧАНИЮ ВЫКЛ: за одним IP провайдера (CGNAT) сидят сотни чужих людей — их балансы смешивались"),
    ('b367-setcode-movc',
     "                try { LS.removeItem('nx_prof_lastbal'); } catch (e) {} // баланс пересчитаем с нуля против нового профиля",
     "                try { LS.removeItem('nx_prof_lastbal'); LS.removeItem('nx_prof_movc'); } catch (e) {} // b367: новый профиль — леджер взносов с нуля"),
    ('b367-unlink-movc',
     "            try { LS.setItem('nx_prof_code', ''); LS.removeItem('nx_prof_lastbal'); } catch (e) {}",
     "            try { LS.setItem('nx_prof_code', ''); LS.removeItem('nx_prof_lastbal'); LS.removeItem('nx_prof_movc'); } catch (e) {}"),
    ('b367-toggle-movc',
     "            try { LS.setItem('nx_prof_ipauto', profIpAuto() ? '0' : '1'); LS.removeItem('nx_prof_lastbal'); } catch (e) {}",
     "            try { LS.setItem('nx_prof_ipauto', profIpAuto() ? '0' : '1'); LS.removeItem('nx_prof_lastbal'); LS.removeItem('nx_prof_movc'); } catch (e) {} // b367: смена сообщества = новый леджер"),
    ('b367-builddoc',
     "        function profBuildDoc(key, remote, mergedFields, mergedCoins) {\n"
     "            const did = nxDeviceId();\n"
     "            const book = Object.assign({}, (remote && remote.book) || {});\n"
     "            book[did] = { at: Date.now(), bal: mergedCoins, dev: nxDeviceLabel(), ip: nxPublicIp(), n: getPlayerName() };\n"
     "            return {\n"
     "                v: 1, ts: Date.now(), by: did, code: profCode(),\n"
     "                state: Object.assign({}, mergedFields, { coins: mergedCoins }),\n"
     "                minerLvl: Math.max(profMinerLvl(), profNum(remote && remote.minerLvl)),\n"
     "                book: book\n"
     "            };\n"
     "        }",
     "        function profBuildDoc(key, remote, mergedFields, mergedCoins, base, mov) {\n"
     "            const did = nxDeviceId();\n"
     "            const book = Object.assign({}, (remote && remote.book) || {});\n"
     "            book[did] = { at: Date.now(), bal: mergedCoins, dev: nxDeviceLabel(), ip: nxPublicIp(), n: getPlayerName() };\n"
     "            return {\n"
     "                v: 2, ts: Date.now(), by: did, code: profCode(),\n"
     "                base: Math.max(0, Math.floor(base) || 0), // b367: общая база (миграция доков v1)\n"
     "                mov: mov || {},                          // b367: леджер накопительных взносов устройств\n"
     "                state: Object.assign({}, mergedFields, { coins: mergedCoins }),\n"
     "                minerLvl: Math.max(profMinerLvl(), profNum(remote && remote.minerLvl)),\n"
     "                book: book\n"
     "            };\n"
     "        }"),
    ('b367-ledger',
     "                const myDelta = myDelta0; // b366: дельта зафиксирована до await\n"
     "                const mergedFields = profMergeState(profSnap(), rState);\n"
     "                const mergedCoins = Math.max(0, (rState ? profNum(rState.coins) : 0) + myDelta);",
     "                const myDelta = myDelta0; // b366: дельта зафиксирована до await\n"
     "                const mergedFields = profMergeState(profSnap(), rState);\n"
     "                // b367: ЛЕДЖЕР взносов: coins = base + Σ mov[did]. Устройство\n"
     "                // перезаписывает только СВОЙ mov (накопительно из LS), поэтому чужой\n"
     "                // пуш по несвежей читке не съедает вашу дельту — потеря\n"
     "                // восстанавливается следующей синхронизацией автора. Старое правило\n"
     "                // «doc + моя дельта» при клоббере или сбросе дока обнуляло\n"
     "                // заработанный баланс — именно это и приходили пользователи.\n"
     "                const mov = {};\n"
     "                const rMov = (remote && remote.mov && typeof remote.mov === 'object') ? remote.mov : {};\n"
     "                for (const mk in rMov) mov[String(mk).slice(0, 24)] = profNum(rMov[mk]);\n"
     "                let base = 0;\n"
     "                if (remote) {\n"
     "                    const sumMov = Object.keys(mov).reduce((s, k) => s + mov[k], 0);\n"
     "                    base = (typeof remote.base === 'number' && isFinite(remote.base))\n"
     "                        ? Math.max(0, Math.floor(remote.base))\n"
     "                        : Math.max(0, profNum(remote.coins) - sumMov); // миграция доков v1 без леджера\n"
     "                }\n"
     "                const myC = profNum(LS.getItem('nx_prof_movc')) + myDelta;\n"
     "                mov[did] = myC;\n"
     "                const mergedCoins = Math.max(0, base + Object.keys(mov).reduce((s, k) => s + mov[k], 0));"),
    ('b367-pull-noset',
     "                if (rState) {\n"
     "                    profApply(Object.assign({}, mergedFields, { coins: mergedCoins }), Math.max(profMinerLvl(), profNum(remote && remote.minerLvl)));\n"
     "                    try { LS.setItem('nx_prof_lastbal', String(mergedCoins)); } catch (e) {}\n"
     "                }",
     "                if (rState) {\n"
     "                    // b367: на чистом pull базу дельт НЕ трогаем: свой неопубликованный\n"
     "                    // взнос остаётся в (myCoins - lastBal) до успешного пуша\n"
     "                    profApply(Object.assign({}, mergedFields, { coins: mergedCoins }), Math.max(profMinerLvl(), profNum(remote && remote.minerLvl)));\n"
     "                }"),
    ('b367-push-set',
     "                return profPushDoc(key, doc).then(() => {\n"
     "                    try { LS.setItem('nx_prof_lastbal', String(mergedCoins)); } catch (e) {}\n"
     "                    profLastRemote = doc;",
     "                return profPushDoc(key, doc).then(() => {\n"
     "                    // b367: база = монеты на СТАРТЕ синка (изменения после старта\n"
     "                    // попадут в следующую дельту); взнос помечен опубликованным\n"
     "                    try { LS.setItem('nx_prof_lastbal', String(myCoins0)); LS.setItem('nx_prof_movc', String(myC)); } catch (e) {}\n"
     "                    profLastRemote = doc;"),
    ('b367-doc-call',
     "                const doc = profBuildDoc(key, remote, mergedFields, mergedCoins);",
     "                const doc = profBuildDoc(key, remote, mergedFields, mergedCoins, base, mov);"),
    ('b367-cycle2',
     "                            const r2 = chk.state || null;\n"
     "                            const d2 = Math.max(0, Math.floor(state.coins) || 0) - mergedCoins;\n"
     "                            const f2 = profMergeState(profSnap(), r2);\n"
     "                            const c2 = Math.max(0, (r2 ? profNum(r2.coins) : 0) + d2);\n"
     "                            profApply(Object.assign({}, f2, { coins: c2 }), Math.max(profMinerLvl(), profNum(chk && chk.minerLvl)));\n"
     "                            const doc2 = profBuildDoc(key, chk, f2, c2);\n"
     "                            return profPushDoc(key, doc2).then(() => { try { LS.setItem('nx_prof_lastbal', String(c2)); } catch (e) {} });",
     "                            const r2 = chk.state || null;\n"
     "                            const mov2 = {};\n"
     "                            const rMov2 = (chk && chk.mov && typeof chk.mov === 'object') ? chk.mov : {};\n"
     "                            for (const mk in rMov2) mov2[String(mk).slice(0, 24)] = profNum(rMov2[mk]);\n"
     "                            const sum2 = Object.keys(mov2).reduce((s, k) => s + mov2[k], 0);\n"
     "                            const base2 = (typeof chk.base === 'number' && isFinite(chk.base)) ? Math.max(0, Math.floor(chk.base)) : Math.max(0, profNum(chk.coins) - sum2);\n"
     "                            const myC2 = myC + (Math.max(0, Math.floor(state.coins) || 0) - myCoins0);\n"
     "                            mov2[did] = myC2;\n"
     "                            const f2 = profMergeState(profSnap(), r2);\n"
     "                            const c2 = Math.max(0, base2 + Object.keys(mov2).reduce((s, k) => s + mov2[k], 0));\n"
     "                            profApply(Object.assign({}, f2, { coins: c2 }), Math.max(profMinerLvl(), profNum(chk && chk.minerLvl)));\n"
     "                            const doc2 = profBuildDoc(key, chk, f2, c2, base2, mov2);\n"
     "                            return profPushDoc(key, doc2).then(() => { try { LS.setItem('nx_prof_lastbal', String(Math.max(0, Math.floor(state.coins) || 0))); LS.setItem('nx_prof_movc', String(myC2)); } catch (e) {} });"),
    ('b367-flush',
     "                const lastBal = parseInt(LS.getItem('nx_prof_lastbal') || '', 10);\n"
     "                const myDelta = Math.max(0, Math.floor(state.coins) || 0) - (isFinite(lastBal) ? lastBal : 0);\n"
     "                if (myDelta === 0 && profLastRemote) return;\n"
     "                const rState = profLastRemote && profLastRemote.state ? profLastRemote.state : null;\n"
     "                const fields = profMergeState(profSnap(), rState);\n"
     "                const coins = Math.max(0, (rState ? profNum(rState.coins) : 0) + myDelta);\n"
     "                profPushDoc(key, profBuildDoc(key, profLastRemote, fields, coins), true);",
     "                const lastBal = parseInt(LS.getItem('nx_prof_lastbal') || '', 10);\n"
     "                const myCoins0 = Math.max(0, Math.floor(state.coins) || 0);\n"
     "                const myDelta = myCoins0 - (isFinite(lastBal) ? lastBal : 0);\n"
     "                if (myDelta === 0 && profLastRemote) return;\n"
     "                const r = profLastRemote;\n"
     "                // b367: тот же леджер, что в обычном синке; LS не трогаем: если\n"
     "                // keepalive-пуш не дойдёт, дельту подберёт следующий круг\n"
     "                const mov = {};\n"
     "                const rMov = (r && r.mov && typeof r.mov === 'object') ? r.mov : {};\n"
     "                for (const mk in rMov) mov[String(mk).slice(0, 24)] = profNum(rMov[mk]);\n"
     "                const sumMov = Object.keys(mov).reduce((s, k) => s + mov[k], 0);\n"
     "                const base = r ? ((typeof r.base === 'number' && isFinite(r.base)) ? Math.max(0, Math.floor(r.base)) : Math.max(0, profNum(r.coins) - sumMov)) : 0;\n"
     "                const myC = profNum(LS.getItem('nx_prof_movc')) + myDelta;\n"
     "                mov[nxDeviceId()] = myC;\n"
     "                const fields = profMergeState(profSnap(), r && r.state ? r.state : null);\n"
     "                const coins = Math.max(0, base + Object.keys(mov).reduce((s, k) => s + mov[k], 0));\n"
     "                profPushDoc(key, profBuildDoc(key, r, fields, coins, base, mov), true);"),
]

QR_EDITS = []
MONO_EDITS = [
    ('b367-ui-text',
     "Пока кода нет — устройства с одним IP связываются сами.",
     "Пока кода нет — устройства можно связать тумблером «Авто по IP» (по умолчанию ВЫКЛ: общий IP ещё не значит общий владелец, а за CGNAT провайдера сидят сотни чужих людей)."),
]

for lbl, o, n in QR_EDITS:
    c = qr_head.count(o)
    assert c == 1, '%s: в базе qr-transfer.js %d вхождений (нужно 1)' % (lbl, c)
print('проверено: все old-блоки уникальны в базе HEAD')

HEADER = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Незакоммиченные правки в виде old -> new (сейчас: b366 — прогресс+профиль в одном QR).

  python3 tools/apply_fix.py check      # показать, что ляжет (ничего не пишет)
  python3 tools/apply_fix.py assets     # применить к assets/*.js
  python3 tools/apply_fix.py monolith   # применить к tools/source-index.html

После монолита: python3 tools/sync_build_blocks.py && python3 tools/build.py --no-media
Пересобирается скриптом tools/_regen_apply_fix.py.
"""
import sys, os, io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

'''

FOOTER = '''

def apply(text, edits, log):
    bad = 0
    for label, old, new in edits:
        c = text.count(old)
        if c == 1:
            text = text.replace(old, new, 1)
            log.append("  · %s: применено" % label)
        elif c == 0 and new in text:
            log.append("  · %s: уже в файле" % label)
        else:
            log.append("  ! %s: найдено %d вхождений old — правка НЕ применена" % (label, c))
            bad += 1
    return text, bad


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "check"
    log, total_bad = [], 0
    if target in ("assets", "check"):
        for name, edits in (("app.js", APP_EDITS), ("qr-transfer.js", QR_EDITS)):
            if not edits:
                continue
            p = os.path.join(ROOT, "assets", name)
            t = io.open(p, encoding="utf-8").read()
            t2, bad = apply(t, edits, log)
            total_bad += bad
            print("assets/%s:" % name); print("\\n".join(log)); log = []
            if target == "assets" and t2 != t:
                if bad:
                    print("  ЕСТЬ НЕПРИМЕНЁННЫЕ ПРАВКИ — файл не записан"); continue
                io.open(p, "w", encoding="utf-8", newline="").write(t2)
                print("  записано")
    if target == "monolith":
        p = os.path.join(ROOT, "tools", "source-index.html")
        t = io.open(p, encoding="utf-8").read()
        t2, bad = apply(t, APP_EDITS + QR_EDITS + MONO_EDITS, log)
        total_bad += bad
        print("tools/source-index.html:"); print("\\n".join(log))
        if bad:
            print("ЕСТЬ НЕПРИМЕНЁННЫЕ ПРАВКИ — монолит не записан"); return 1
        if t2 != t:
            io.open(p, "w", encoding="utf-8", newline="\\r\\n").write(t2)
            print("  записано (%+d строк)" % (t2.count("\\n") - t.count("\\n")))
    if not (APP_EDITS or QR_EDITS or MONO_EDITS):
        print("список правок пуст: всё уже в репозитории")
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
'''


def dump(name, edits):
    out = name + ' = [\n'
    for lbl, o, n in edits:
        out += '    (%s,\n     %s,\n     %s),\n' % (repr(lbl), repr(o), repr(n))
    return out + ']\n'


src = HEADER + dump('APP_EDITS', APP_EDITS) + '\n' + dump('QR_EDITS', QR_EDITS) + '\n' + dump('MONO_EDITS', MONO_EDITS) + FOOTER
ast.parse(src)
io.open(AP, 'w', encoding='utf-8', newline='').write(src)
print('apply_fix.py пересобран под b366: блоков', len(QR_EDITS))
