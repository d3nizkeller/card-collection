#!/usr/bin/env python3
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

APP_EDITS = [
]

QR_EDITS = [
]


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
            print("assets/%s:" % name); print("\n".join(log)); log = []
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
        print("tools/source-index.html (блоки app_js + qr_xfer):"); print("\n".join(log))
        if bad:
            print("ЕСТЬ НЕПРИМЕНЁННЫЕ ПРАВКИ — монолит не записан"); return 1
        if t2 != t:
            io.open(p, "w", encoding="utf-8", newline="\r\n").write(t2)
            print("  записано (%+d строк)" % (t2.count("\n") - t.count("\n")))
    if not APP_EDITS and not QR_EDITS:
        print("список правок пуст: всё уже в репозитории")
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
