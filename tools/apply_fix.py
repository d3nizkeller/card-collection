#!/usr/bin/env python3
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

APP_EDITS = [
    ('b366-race-hold',
     '        let profBusy = false, profLastRemote = null, profLastTs = 0, profT = 0;',
     '        let profBusy = false, profLastRemote = null, profLastTs = 0, profT = 0;\n        let profHoldUntil = 0; // b366: на время применения переноса фоновый синк не трогает баланс\n        function profHold(ms) { profHoldUntil = Date.now() + (ms || 2000); }'),
    ('b366-race-delta',
     "            profBusy = true;\n            const did = nxDeviceId();\n            let lastBal = parseInt(LS.getItem('nx_prof_lastbal') || '', 10);\n            const first = !isFinite(lastBal);\n            if (first) lastBal = 0; // первое подключение: весь мой баланс — это моя дельта\n            return profFetch(key).then(remote => {",
     "            profBusy = true;\n            const did = nxDeviceId();\n            // b366: монеты и базу дельты снимаем СИНХРОННО, до любых await: иначе\n            // перенос/accept, вклинившийся между fetch и применением, учтётся как\n            // «моя дельта» и баланс задвоится (тест ловил 8842 вместо 4321)\n            const myCoins0 = Math.max(0, Math.floor(state.coins) || 0);\n            let lastBal = parseInt(LS.getItem('nx_prof_lastbal') || '', 10);\n            const first = !isFinite(lastBal);\n            if (first) lastBal = 0; // первое подключение: весь мой баланс — это моя дельта\n            const myDelta0 = myCoins0 - lastBal;\n            return profFetch(key).then(remote => {\n                if (Date.now() < profHoldUntil) return 'held'; // b366: сейчас применяют перенос — не трогаем"),
    ('b366-race-use',
     '                const myDelta = Math.max(0, Math.floor(state.coins) || 0) - lastBal;',
     '                const myDelta = myDelta0; // b366: дельта зафиксирована до await'),
    ('b366-race-held',
     '              .then(v => { profBusy = false; return v; });',
     "              .then(v => { profBusy = false; return v === 'held' ? false : v; });"),
]

QR_EDITS = [
    ('b366-snap-prof',
     '        const snap = qrxSnapshot();\n        const json = JSON.stringify(snap);',
     '        const snap = qrxSnapshot();\n        // b366: в тот же QR зашиваем код профиля синхронизации: устройство,\n        // отсканировавшее этот код, не только получит прогресс, но и привяжется\n        // к профилю — баланс и прогресс станут общими (правила b364).\n        try { let pc = profCode(); if (!pc) { pc = profGenCode(); profSetCode(pc, true); } snap.prof = pc; } catch (e) {}\n        const json = JSON.stringify(snap);'),
    ('b366-status',
     '        if (status) status.innerHTML = code.indexOf(QRX_DIRECT) === 0\n            ? \'<i class="fa-solid fa-bolt text-amber-300 mr-1"></i>Прямой код: весь прогресс зашит прямо в QR (\' + code.length + \' символов)\'\n            : \'<i class="fa-solid fa-cloud text-violet-300 mr-1"></i>Облачный ключ: снимок прогресса в транзитном облаке, в QR только ключ\';',
     '        if (status) status.innerHTML = (code.indexOf(QRX_DIRECT) === 0\n            ? \'<i class="fa-solid fa-bolt text-amber-300 mr-1"></i>Прямой код: весь прогресс зашит прямо в QR (\' + code.length + \' символов)\'\n            : \'<i class="fa-solid fa-cloud text-violet-300 mr-1"></i>Облачный ключ: снимок прогресса в транзитном облаке, в QR только ключ\')\n            + (snap.prof ? \' <span class="text-emerald-300">• в QR также код профиля \' + cloudEsc(snap.prof) + \' — второе устройство сразу привяжется</span>\' : \'\');'),
    ('b366-helper',
     'async function qrxHandleCode(raw) {',
     "function qrxApplyProf(o) { // b366: в коде переноса может лежать код профиля — привязываем устройство сразу\n    try {\n        const pc = (o && typeof o.prof === 'string') ? o.prof.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 12) : '';\n        if (pc && pc !== profCode()) {\n            profSetCode(pc);\n            try { showToast('Устройство привязано к профилю ' + pc + ' вместе с переносом — баланс и прогресс станут общими', 'success'); } catch (e) {}\n        }\n    } catch (e) {}\n}\nasync function qrxHandleCode(raw) {"),
    ('b366-relay',
     "            const obj = await qrxRelayFetch(s.slice(QRX_RELAY.length));\n            if (!obj || !obj.d) throw new Error('облако не вернуло данные');\n            qrxShowConfirm(obj.d, null);",
     "            const obj = await qrxRelayFetch(s.slice(QRX_RELAY.length));\n            if (!obj || !obj.d) throw new Error('облако не вернуло данные');\n            qrxApplyProf(obj.d || obj); // b366: в relay-ветке профиль лежит внутри obj.d\n            qrxShowConfirm(obj.d, null);"),
    ('b366-direct',
     "            const json = await qrxInflate(qrxB64d(s.slice(QRX_DIRECT.length)));\n            if (!json) throw new Error('не удалось распаковать код');\n            qrxShowConfirm(JSON.parse(json), null);",
     "            const json = await qrxInflate(qrxB64d(s.slice(QRX_DIRECT.length)));\n            if (!json) throw new Error('не удалось распаковать код');\n            const objD = JSON.parse(json);\n            qrxApplyProf(objD); // b366\n            qrxShowConfirm(objD, null);"),
    ('b366-accept-baseline',
     '    qrxApplyProgress(p);\n    closeQrModal();',
     "    try { profHold(2500); } catch (e) {} // b366: фоновый синк не перетирает привезённый сейв\n    qrxApplyProgress(p);\n    // b366: база дельт = ПРИВЕЗЁННЫЙ баланс: локальные бонусы после accept\n    // (достижения и т.п.) уходят в общий профиль обычной дельтой, а сам перенос\n    // не прибавляется к общему балансу вторым разом\n    try { LS.setItem('nx_prof_lastbal', String(Math.max(0, Math.round(Number(p && p.c) || 0)))); } catch (e) {}\n    closeQrModal();"),
    ('b366-json',
     "        if (s.charAt(0) === '{') {\n            const o = JSON.parse(s);\n            if (o && o.v === 1 && o.col) { qrxShowConfirm(o, null); return; }",
     "        if (s.charAt(0) === '{') {\n            const o = JSON.parse(s);\n            qrxApplyProf(o); // b366\n            if (o && o.v === 1 && o.col) { qrxShowConfirm(o, null); return; }"),
    ('b366-selfcheck-helper',
     'async function qrxBuild() {',
     "function qrxSelfCheck(text) { // b366: самопроверка — читает ли НАШ сканер нарисованный QR\n    // У плотных версий QR бывают «неудачные» сочетания маски/версии, которые jsQR\n    // не берёт с чистого канваса (замер: 1040 символов — нет, 1400 — да). Такой QR\n    // и камера вероятнее всего не возьмёт, поэтому вместо него показываем короткий\n    // облачный ключ: короткий QR читается всегда.\n    try {\n        const cv = document.getElementById('qr-canvas');\n        if (!cv || !cv.width) return false;\n        const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height);\n        const r = jsQR(d.data, cv.width, cv.height);\n        return !!(r && r.data === text);\n    } catch (e) { return false; }\n}\nasync function qrxBuild() {"),
    ('b366-selfcheck-use',
     "        if (def) {\n            const cand = QRX_DIRECT + qrxB64(def);\n            if (cand.length <= QRX_MAX_DIRECT) {\n                try { qrxRender(cand); code = cand; } catch (e) { code = ''; }\n            }\n        }",
     "        if (def) {\n            const cand = QRX_DIRECT + qrxB64(def);\n            if (cand.length <= QRX_MAX_DIRECT) {\n                try { qrxRender(cand); code = cand; } catch (e) { code = ''; }\n                if (code && !qrxSelfCheck(cand)) code = ''; // b366: не читается самим собой — в облако\n            }\n        }"),
]

MONO_EDITS = [
]


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
            print("assets/%s:" % name); print("\n".join(log)); log = []
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
        print("tools/source-index.html:"); print("\n".join(log))
        if bad:
            print("ЕСТЬ НЕПРИМЕНЁННЫЕ ПРАВКИ — монолит не записан"); return 1
        if t2 != t:
            io.open(p, "w", encoding="utf-8", newline="\r\n").write(t2)
            print("  записано (%+d строк)" % (t2.count("\n") - t.count("\n")))
    if not (APP_EDITS or QR_EDITS or MONO_EDITS):
        print("список правок пуст: всё уже в репозитории")
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
