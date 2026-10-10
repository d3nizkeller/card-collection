#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пересобирает tools/apply_fix.py под правку b365 (QR-код профиля синхронизации).

База — HEAD (b364 уже в репозитории). Каждый old обязан встречаться в базе РОВНО
один раз. Одноразовый служебный скрипт: после коммита b365 список станет пустым.
"""
import io, os, ast, subprocess

AP = 'tools/apply_fix.py'
HERE = os.path.dirname(os.path.abspath(__file__))

app_head = subprocess.run(['git', 'show', 'HEAD:assets/app.js'], capture_output=True, text=True).stdout
qr_head = subprocess.run(['git', 'show', 'HEAD:assets/qr-transfer.js'], capture_output=True, text=True).stdout
idx_head = subprocess.run(['git', 'show', 'HEAD:index.html'], capture_output=True, text=True).stdout
assert app_head and qr_head and idx_head, 'HEAD не читается'

MODULE = io.open(os.path.join(HERE, '_b365_module.txt'), encoding='utf-8').read().rstrip('\n')

QRX_LOOKS_OLD = """function qrxLooksLikeCode(s) {
    const t = String(s == null ? '' : s).trim();
    if (!t) return false;
    if (t.indexOf(QRX_DIRECT) === 0 || t.indexOf(QRX_RELAY) === 0) return true;
    return t.charAt(0) === '{';
}"""
QRX_LOOKS_NEW = """function qrxLooksLikeCode(s) {
    const t = String(s == null ? '' : s).trim();
    if (!t) return false;
    if (t.indexOf(QRX_DIRECT) === 0 || t.indexOf(QRX_RELAY) === 0) return true;
    if (/[?&]prof=[A-Za-z0-9-]{4,12}/i.test(t)) return true;  // b365: QR профиля синхронизации
    if (/^NXPROF:[A-Za-z0-9]{4,12}$/i.test(t)) return true;   // b365: голый код профиля
    return t.charAt(0) === '{';
}"""

QRX_HANDLE_OLD = """async function qrxHandleCode(raw) {
    const s = String(raw || '').trim();
    const st = document.getElementById('qr-scan-status');
    if (!s) { showToast('Пустой код переноса', 'error'); return; }"""
QRX_HANDLE_NEW = """async function qrxHandleCode(raw) {
    const s = String(raw || '').trim();
    const st = document.getElementById('qr-scan-status');
    if (!s) { showToast('Пустой код переноса', 'error'); return; }
    // b365: QR синхронизации профиля (ссылка ?prof=КОД или NXPROF:КОД) —
    // привязываем устройство к профилю вместо переноса прогресса
    try {
        const pc = (typeof profQrFromText === 'function') ? profQrFromText(s) : '';
        if (pc) {
            try { qrxStopScan(); } catch (e) {}
            try { closeQrModal(); } catch (e) {}
            try { profSetCode(pc); } catch (e) {}
            try { showToast('Устройство привязано к профилю ' + pc + ' через QR — синхронизирую баланс и прогресс…', 'success'); } catch (e) {}
            return;
        }
    } catch (e) {}"""

BTN_ANCHOR = '                    <button type="button" onclick="profCopyLink()" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-[10px] font-bold transition"><i class="fa-solid fa-link mr-1"></i>Ссылка на устройство</button>'
BTN_NEW = BTN_ANCHOR + '\n' + \
    '                    <button type="button" onclick="profQrShow()" title="Показать QR-код профиля: второе устройство привяжется сканированием" class="px-2.5 py-1.5 rounded-lg bg-emerald-950/60 hover:bg-emerald-900/60 border border-emerald-800/60 text-emerald-300 text-[10px] font-bold transition"><i class="fa-solid fa-qrcode mr-1"></i>QR-код</button>\n' + \
    '                    <button type="button" onclick="profQrScan()" title="Сканировать QR профиля с экрана другого устройства" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-[10px] font-bold transition"><i class="fa-solid fa-camera mr-1"></i>Сканировать QR</button>'

APP_EDITS = [
    ('b365-module', "        function nxStatsGroupOn() {", MODULE + "\n        function nxStatsGroupOn() {"),
]
QR_EDITS = [
    ('b365-lookslikecode', QRX_LOOKS_OLD, QRX_LOOKS_NEW),
    ('b365-handlecode', QRX_HANDLE_OLD, QRX_HANDLE_NEW),
]
MONO_EDITS = [
    ('b365-ui-buttons', BTN_ANCHOR, BTN_NEW),
]

for lbl, o, n in APP_EDITS:
    assert app_head.count(o) == 1, '%s: в базе app.js %d вхождений (нужно 1)' % (lbl, app_head.count(o))
for lbl, o, n in QR_EDITS:
    assert qr_head.count(o) == 1, '%s: в базе qr-transfer.js %d вхождений (нужно 1)' % (lbl, qr_head.count(o))
for lbl, o, n in MONO_EDITS:
    assert idx_head.count(o) == 1, '%s: в базе index.html %d вхождений (нужно 1)' % (lbl, idx_head.count(o))
print('проверено: все old-блоки уникальны в базе HEAD')

HEADER = '''#!/usr/bin/env python3
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
        t = io.open(p, encoding="utf-8").read()   # CRLF -> LF при чтении
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
print('apply_fix.py пересобран под b365:', len(src), 'байт; блоков', len(APP_EDITS), '+', len(QR_EDITS), '+', len(MONO_EDITS))
