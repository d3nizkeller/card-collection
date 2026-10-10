#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пересобирает tools/apply_fix.py — список правок, которых в репозитории ещё нет.

База — HEAD (то, что реально отдаётся сайтом). Правки b355–b360 уже в HEAD,
здесь остаётся: dedup b357 и b361. Каждый old обязан встречаться в базе РОВНО
один раз — иначе скрипт падает, а не портит файл.
Одноразовый служебный скрипт: после коммита этих правок список станет пустым.
"""
import io, ast, subprocess

AP = 'tools/apply_fix.py'

qr_head = subprocess.run(['git', 'show', 'HEAD:assets/qr-transfer.js'],
                         capture_output=True, text=True).stdout
assert qr_head and 'nxGhPush(repo, content, ok, fail)' in qr_head, 'HEAD:assets/qr-transfer.js не читается'

# --- b357-dedup: nx3dPauseAll() вклеился трижды ----------------------------
PAUSE = "        try { nx3dPauseAll(); } catch (e) {} // b357: сначала остановить кадры, потом отдавать контексты\n"
REL = "        try { nx3dReleaseHidden('__all__'); } catch (e) {}"
TRIPLE_OLD = PAUSE * 3 + REL
TRIPLE_NEW = PAUSE + REL

# --- b361: helpers для сверки с веткой ------------------------------------
SHA_OLD = "function nxGhPush(repo, content, ok, fail) {"
SHA_NEW = (
    "function nxGitShaOf(str) { // b361: git-sha содержимого (blob), считается на устройстве\n"
    "    try {\n"
    "        const bytes = new TextEncoder().encode(str);\n"
    "        const head = new TextEncoder().encode('blob ' + bytes.length + '\\0');\n"
    "        const all = new Uint8Array(head.length + bytes.length);\n"
    "        all.set(head, 0); all.set(bytes, head.length);\n"
    "        return crypto.subtle.digest('SHA-1', all).then(b => Array.from(new Uint8Array(b)).map(x => x.toString(16).padStart(2, '0')).join(''));\n"
    "    } catch (e) { return Promise.resolve(''); }\n"
    "}\n"
    "function nxGhFileSha(repo, path) { // b361: sha файла в ветке по умолчанию\n"
    "    return nxGhApi('/repos/' + repo + '/contents/' + path, { headers: { 'Accept': 'application/vnd.github+json' } })\n"
    "        .then(d => (d && d.sha) || '').catch(() => '');\n"
    "}\n"
    "function nxGhPush(repo, content, ok, fail) {")

# --- b361: холостой коммит не создаём -------------------------------------
PUSH_OLD = """        const finalize = () => { nxProgress(0.65, 'Собираю файл с артами…'); out = nxInjectExtras(out, extras); // b340
            if (!replaced && !extras.length) { err('Вшивать нечего: кэш пуст. Нажмите «Вшить всё» или дождитесь авто-кэша — и повторите'); return; }
            say((auto ? 'Автовшивание: ' : '') + 'файл собран (' + (replaced + extras.length) + ' артов). Пушу коммит в GitHub…');
            nxStatus((auto ? 'Автовшивание: ' : '') + 'файл собран (' + (replaced + extras.length) + ' артов), загружаю ~' + (out.length / 1048576).toFixed(1) + ' МБ в GitHub…');
            nxGhPush(repo, out, () => { if (btn) btn.disabled = false; say((auto ? 'Автовшивание: ' : '') + 'вшито в сайт! Pages обновится за 1–2 минуты'); try { nxCrashLog('push-embed ok: ' + (replaced + extras.length) + ' артов'); } catch (e) {} nxStatus('Готово: вшито ' + (replaced + extras.length) + ' артов. Pages обновится за 1–2 минуты', 'ok'); }, err);
        };"""
PUSH_NEW = """        const finalize = () => { nxProgress(0.65, 'Собираю файл с артами…'); out = nxInjectExtras(out, extras); // b340
            if (!replaced && !extras.length) { err('Вшивать нечего: кэш пуст. Нажмите «Вшить всё» или дождитесь авто-кэша — и повторите'); return; }
            // b361: сначала сверяем собранный файл с тем, что уже лежит в ветке, и
            // только потом обещаем коммит. На разделённой сборке (index.html +
            // assets/*) маркер NX_EMBED_MEDIA живёт в assets/app.js, поэтому
            // «вшивание» в index.html ничего не меняет — а пустые коммиты сайт
            // плодил каждые 10 минут (замер: коммит 7a2e45d не изменил ничего).
            const pushReal = () => {
                say((auto ? 'Автовшивание: ' : '') + 'файл собран (' + (replaced + extras.length) + ' артов). Пушу коммит в GitHub…');
                nxStatus((auto ? 'Автовшивание: ' : '') + 'файл собран (' + (replaced + extras.length) + ' артов), загружаю ~' + (out.length / 1048576).toFixed(1) + ' МБ в GitHub…');
                nxGhPush(repo, out, () => { if (btn) btn.disabled = false; say((auto ? 'Автовшивание: ' : '') + 'вшито в сайт! Pages обновится за 1–2 минуты'); try { nxCrashLog('push-embed ok: ' + (replaced + extras.length) + ' артов'); } catch (e) {} nxStatus('Готово: вшито ' + (replaced + extras.length) + ' артов. Pages обновится за 1–2 минуты', 'ok'); }, err);
            };
            Promise.all([nxGitShaOf(out), nxGhFileSha(repo, 'index.html')]).then(sh => {
                if (sh[0] && sh[0] === sh[1]) {
                    if (btn) btn.disabled = false;
                    say('Коммит не нужен: index.html в репозитории уже такой же');
                    nxStatus('Без изменений: собранный файл совпадает с тем, что уже в ветке — коммита не будет', 'ok');
                    try { nxCrashLog('push-embed: пропуск, собранный файл не отличается от ветки'); } catch (e) {}
                    return;
                }
                pushReal();
            }).catch(() => pushReal());
        };"""

# b362 (qrxB64 через массив+join) ОТМЕНЁН: замер в браузере показал, что
# склейка bin += String.fromCharCode(...) в V8 не квадратична (rope-конкатенация),
# а вариант с join вышел МЕДЛЕННЕЕ (2 МБ: 206 мс против 124 мс). Правка не нужна.

APP_EDITS = []   # b355–b358 уже в HEAD
# b357-dedup и b361 уже в HEAD — в списке остаётся только то, чего там ещё нет
QR_EDITS = [
    # b357-dedup, b361-sha-helpers и b361-noop-skip уже в HEAD — список пуст
]

for lbl, o, n in APP_EDITS + QR_EDITS:
    c = qr_head.count(o)
    assert c == 1, '%s: в базе %d вхождений (нужно ровно 1)' % (lbl, c)
print('проверено: все блоки встречаются в базе ровно один раз')

HEADER = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Незакоммиченные правки игры в виде списка old -> new.

Зачем этот файл: сайт собирается из монолита tools/source-index.html, поэтому
любую правку надо вносить ДВАЖДЫ — в assets/*.js (то, что отдаётся сайтом) и в
монолит (иначе следующая сборка её затрёт). Скрипт делает обе операции одним
набором блоков и не пишет файл, если хоть одна правка не легла.

  python3 tools/apply_fix.py check      # показать, что ляжет (ничего не пишет)
  python3 tools/apply_fix.py assets     # применить к assets/app.js, assets/qr-transfer.js
  python3 tools/apply_fix.py monolith   # применить к tools/source-index.html

После правки монолита:
  python3 tools/sync_build_blocks.py && python3 tools/build.py --no-media

Список пересобирается скриптом tools/_regen_apply_fix.py (нужен git).
История правок b355-b361 — в FIXES.md, раздел 6.
"""
import sys, os, io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

'''

FOOTER = '''

def apply(text, edits, log):
    """Возвращает (новый текст, число неприменённых правок)."""
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
        # читаем с универсальными переводами строк (CRLF -> LF), пишем обратно CRLF
        t = io.open(p, encoding="utf-8").read()
        t2, bad = apply(t, APP_EDITS + QR_EDITS, log)
        total_bad += bad
        print("tools/source-index.html (блоки app_js + qr_xfer):"); print("\\n".join(log))
        if bad:
            print("ЕСТЬ НЕПРИМЕНЁННЫЕ ПРАВКИ — монолит не записан"); return 1
        if t2 != t:
            io.open(p, "w", encoding="utf-8", newline="\\r\\n").write(t2)
            print("  записано (%+d строк)" % (t2.count("\\n") - t.count("\\n")))
    if not APP_EDITS and not QR_EDITS:
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


src = HEADER + dump('APP_EDITS', APP_EDITS) + '\n' + dump('QR_EDITS', QR_EDITS) + FOOTER
ast.parse(src)
io.open(AP, 'w', encoding='utf-8', newline='').write(src)
print('apply_fix.py пересобран:', len(src), 'байт; app-блоков', len(APP_EDITS), ', qr-блоков', len(QR_EDITS))
