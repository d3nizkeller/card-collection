#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Незакоммиченные правки в виде old -> new (сейчас: b365 — QR-код профиля).

  python3 tools/apply_fix.py check      # показать, что ляжет (ничего не пишет)
  python3 tools/apply_fix.py assets     # применить к assets/app.js и assets/qr-transfer.js
  python3 tools/apply_fix.py monolith   # применить к tools/source-index.html (включая MONO_EDITS)

После монолита: python3 tools/sync_build_blocks.py && python3 tools/build.py --no-media
Пересобирается скриптом tools/_regen_apply_fix.py.
"""
import sys, os, io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

APP_EDITS = [
    ('b365-module',
     '        function nxStatsGroupOn() {',
     '        // ============ b365: QR-КОД ПРОФИЛЯ — привязка устройств сканированием ============\n        // На основном устройстве «QR-код» показывает код ссылки ?prof=КОД: его можно\n        // отсканировать системной камерой телефона (откроется сайт и сам привяжет\n        // устройство по параметру URL — это уже умеет profInit) ИЛИ кнопкой\n        // «Сканировать QR» внутри сайта (переиспользуется камера-сканер переноса\n        // прогресса: qrGoScan -> jsQR -> qrxHandleCode, где ссылка распознаётся).\n        function profLink() {\n            try { return location.origin + location.pathname + \'?prof=\' + (profCode() || \'\'); }\n            catch (e) { return \'?prof=\' + (profCode() || \'\'); }\n        }\n        function profQrDraw(cv, text) { // тот же рендер, что qrxRender, но на свой canvas\n            const qr = qrcode(0, \'L\'); // уровень L: меньше модулей, камере проще\n            qr.addData(text, \'Byte\');\n            qr.make();\n            const n = qr.getModuleCount(), qz = 4, m = 8;\n            cv.width = cv.height = (n + qz * 2) * m;\n            const ctx = cv.getContext(\'2d\');\n            ctx.fillStyle = \'#ffffff\'; ctx.fillRect(0, 0, cv.width, cv.height);\n            ctx.fillStyle = \'#0b1220\';\n            for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) ctx.fillRect((c + qz) * m, (r + qz) * m, m, m);\n        }\n        function profQrShow() {\n            let c = profCode();\n            if (!c) { c = profGenCode(); profSetCode(c, true); } // нет кода — создаём сразу\n            let mo = document.getElementById(\'nx-prof-qr-modal\');\n            if (!mo) {\n                mo = document.createElement(\'div\');\n                mo.id = \'nx-prof-qr-modal\';\n                mo.className = \'fixed inset-0 z-[80] bg-slate-950/90 backdrop-blur-md hidden flex items-center justify-center p-4 overflow-y-auto\';\n                mo.innerHTML = \'<div class="relative w-full max-w-sm rounded-2xl border border-slate-700 bg-slate-900 p-4 text-center space-y-3">\' +\n                    \'<button type="button" onclick="profQrClose()" class="absolute top-3 right-3 text-slate-400 hover:text-white transition"><i class="fa-solid fa-xmark"></i></button>\' +\n                    \'<h3 class="text-sm font-bold text-white"><i class="fa-solid fa-qrcode text-emerald-400 mr-1"></i>QR-код вашего профиля</h3>\' +\n                    \'<p class="text-[11px] text-slate-400 leading-snug">Отсканируйте на втором устройстве обычной камерой телефона (ссылка откроется и устройство само привяжется) или в сайте кнопкой «Сканировать QR».</p>\' +\n                    \'<div class="mx-auto w-fit bg-white rounded-2xl p-3 shadow-lg shadow-emerald-500/10"><canvas id="nx-prof-qr-canvas" class="block w-[220px] h-[220px] sm:w-[260px] sm:h-[260px]"></canvas></div>\' +\n                    \'<p class="text-xs font-mono text-emerald-300" id="nx-prof-qr-code"></p>\' +\n                    \'<div class="flex flex-wrap justify-center gap-1.5">\' +\n                        \'<button type="button" onclick="profCopyLink()" class="px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-[11px] font-bold rounded-xl transition"><i class="fa-solid fa-link mr-1"></i>Копировать ссылку</button>\' +\n                        \'<button type="button" onclick="profQrScan()" class="px-3 py-2 bg-emerald-700 hover:bg-emerald-600 text-white text-[11px] font-bold rounded-xl transition"><i class="fa-solid fa-camera mr-1"></i>Сканировать другой QR</button>\' +\n                    \'</div>\' +\n                \'</div>\';\n                document.body.appendChild(mo);\n            }\n            mo.classList.remove(\'hidden\');\n            try {\n                profQrDraw(document.getElementById(\'nx-prof-qr-canvas\'), profLink());\n                const ce = document.getElementById(\'nx-prof-qr-code\');\n                if (ce) ce.textContent = \'Код профиля: \' + c;\n                profUI();\n            } catch (e) { try { showToast(\'Не удалось нарисовать QR: \' + String((e && e.message) || e), \'error\'); } catch (e2) {} }\n        }\n        function profQrClose() { const mo = document.getElementById(\'nx-prof-qr-modal\'); if (mo) mo.classList.add(\'hidden\'); }\n        function profQrScan() { // открыть существующий камера-сканер (из переноса прогресса)\n            profQrClose();\n            const m = document.getElementById(\'modal-qr\');\n            if (!m) { try { showToast(\'Сканер QR недоступен в этой сборке\', \'error\'); } catch (e) {} return; }\n            m.classList.remove(\'hidden\');\n            try { qrGoScan(); } catch (e) { try { showToast(\'Камера недоступна: \' + String((e && e.message) || e), \'error\'); } catch (e2) {} }\n            const st = document.getElementById(\'qr-scan-status\');\n            if (st) st.innerHTML = \'<i class="fa-solid fa-qrcode text-emerald-300 mr-1"></i>Наведите камеру на QR-код профиля с экрана другого устройства (кнопка «QR-код» в блоке синхронизации)…\';\n        }\n        function profQrFromText(raw) { // распознать код профиля из отсканированного текста; \'\' — не профиль\n            const s = String(raw || \'\').trim();\n            let m = s.match(/[?&]prof=([A-Za-z0-9-]{4,12})/);\n            if (!m) m = s.match(/^NXPROF:([A-Za-z0-9]{4,12})$/i);\n            return m ? m[1].toUpperCase().replace(/[^A-Z0-9]/g, \'\') : \'\';\n        }\n        function nxStatsGroupOn() {'),
]

QR_EDITS = [
    ('b365-lookslikecode',
     "function qrxLooksLikeCode(s) {\n    const t = String(s == null ? '' : s).trim();\n    if (!t) return false;\n    if (t.indexOf(QRX_DIRECT) === 0 || t.indexOf(QRX_RELAY) === 0) return true;\n    return t.charAt(0) === '{';\n}",
     "function qrxLooksLikeCode(s) {\n    const t = String(s == null ? '' : s).trim();\n    if (!t) return false;\n    if (t.indexOf(QRX_DIRECT) === 0 || t.indexOf(QRX_RELAY) === 0) return true;\n    if (/[?&]prof=[A-Za-z0-9-]{4,12}/i.test(t)) return true;  // b365: QR профиля синхронизации\n    if (/^NXPROF:[A-Za-z0-9]{4,12}$/i.test(t)) return true;   // b365: голый код профиля\n    return t.charAt(0) === '{';\n}"),
    ('b365-handlecode',
     "async function qrxHandleCode(raw) {\n    const s = String(raw || '').trim();\n    const st = document.getElementById('qr-scan-status');\n    if (!s) { showToast('Пустой код переноса', 'error'); return; }",
     "async function qrxHandleCode(raw) {\n    const s = String(raw || '').trim();\n    const st = document.getElementById('qr-scan-status');\n    if (!s) { showToast('Пустой код переноса', 'error'); return; }\n    // b365: QR синхронизации профиля (ссылка ?prof=КОД или NXPROF:КОД) —\n    // привязываем устройство к профилю вместо переноса прогресса\n    try {\n        const pc = (typeof profQrFromText === 'function') ? profQrFromText(s) : '';\n        if (pc) {\n            try { qrxStopScan(); } catch (e) {}\n            try { closeQrModal(); } catch (e) {}\n            try { profSetCode(pc); } catch (e) {}\n            try { showToast('Устройство привязано к профилю ' + pc + ' через QR — синхронизирую баланс и прогресс…', 'success'); } catch (e) {}\n            return;\n        }\n    } catch (e) {}"),
]

MONO_EDITS = [
    ('b365-ui-buttons',
     '                    <button type="button" onclick="profCopyLink()" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-[10px] font-bold transition"><i class="fa-solid fa-link mr-1"></i>Ссылка на устройство</button>',
     '                    <button type="button" onclick="profCopyLink()" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-[10px] font-bold transition"><i class="fa-solid fa-link mr-1"></i>Ссылка на устройство</button>\n                    <button type="button" onclick="profQrShow()" title="Показать QR-код профиля: второе устройство привяжется сканированием" class="px-2.5 py-1.5 rounded-lg bg-emerald-950/60 hover:bg-emerald-900/60 border border-emerald-800/60 text-emerald-300 text-[10px] font-bold transition"><i class="fa-solid fa-qrcode mr-1"></i>QR-код</button>\n                    <button type="button" onclick="profQrScan()" title="Сканировать QR профиля с экрана другого устройства" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-[10px] font-bold transition"><i class="fa-solid fa-camera mr-1"></i>Сканировать QR</button>'),
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
        t = io.open(p, encoding="utf-8").read()   # CRLF -> LF при чтении
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
