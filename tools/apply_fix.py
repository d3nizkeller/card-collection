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
    ('b368-sig-helpers',
     "        function profApply(s, mlvl) { // приложить слитое состояние к игре\n"
     "            if (!s) return;\n"
     "            state.coins = Math.max(0, profNum(s.coins));",
     "        function profSig() { // b368: отпечаток состояния: изменилось ли что-то реально\n"
     "            try {\n"
     "                return [\n"
     "                    Math.floor(state.coins) || 0,\n"
     "                    (state.packs || []).map(p => p && p.id).join('.'),\n"
     "                    (state.cards || []).map(c => c && c.id).join('.'),\n"
     "                    JSON.stringify(state.collection || {}),\n"
     "                    JSON.stringify(state.albumBonus || {}),\n"
     "                    JSON.stringify(state.packStats || {}),\n"
     "                    JSON.stringify(state.achievements || {}),\n"
     "                    (state.deck || []).join('.'),\n"
     "                    (state.missions && state.missions.date) || '',\n"
     "                    (state.daily && state.daily.lastClaimDate) || '',\n"
     "                    (state.stats && state.stats.packsOpened) || 0\n"
     "                ].join('|');\n"
     "            } catch (e) { return 'err' + Math.random(); }\n"
     "        }\n"
     "        function profStructSig(sig) { // b368: отпечаток без баланса: смена баланса — не повод перерисовывать вкладки\n"
     "            const i = String(sig).indexOf('|');\n"
     "            return i < 0 ? '' : String(sig).slice(i + 1);\n"
     "        }\n"
     "        function profApply(s, mlvl) { // приложить слитое состояние к игре\n"
     "            if (!s) return;\n"
     "            const pre = profSig(); // b368: снимаем отпечаток ДО применения\n"
     "            state.coins = Math.max(0, profNum(s.coins));"),
    ('b368-no-flicker',
     "            try { // кирка шахты: уровень не теряется между устройствами\n"
     "                if (mlvl && typeof miner !== 'undefined' && miner && mlvl > (miner.lvl || 0)) { miner.lvl = mlvl; try { minerSave(); } catch (e) {} }\n"
     "            } catch (e) {}\n"
     "            saveState();\n"
     "            updateCoinDisplay();\n"
     "            try { refreshVisibleTabs(); } catch (e) {}\n"
     "        }",
     "            let minerCh = false;\n"
     "            try { // кирка шахты: уровень не теряется между устройствами\n"
     "                if (mlvl && typeof miner !== 'undefined' && miner && mlvl > (miner.lvl || 0)) { miner.lvl = mlvl; minerCh = true; try { minerSave(); } catch (e) {} }\n"
     "            } catch (e) {}\n"
     "            // b368: НЕ мигаем интерфейсом на каждую синхронизацию. Полная\n"
     "            // перерисовка вкладок — только если реально изменились карты/паки/\n"
     "            // альбомы/колода; если поменялся лишь баланс — обновляем только\n"
     "            // счётчик монет; если не изменилось ничего — не трогаем DOM вовсе.\n"
     "            const post = profSig();\n"
     "            if (post === pre && !minerCh) return;\n"
     "            saveState();\n"
     "            updateCoinDisplay();\n"
     "            if (minerCh || profStructSig(post) !== profStructSig(pre)) {\n"
     "                try { refreshVisibleTabs(); } catch (e) {}\n"
     "            }\n"
     "        }"),
    ('b367-diff-5189-5189',
     '                const remoteMyMov = Object.prototype.hasOwnProperty.call(rMov, did) ? rMov[did] : null;',
     '                const remoteMyMov = Object.prototype.hasOwnProperty.call(rMov, did) ? rMov[did] : null; // b367: мой взнос по версии дока'),
]

QR_EDITS = []

MONO_EDITS = [
    ('b367-ui-text',
     'Пока кода нет — устройства с одним IP связываются сами.',
     'Пока кода нет — устройства можно связать тумблером «Авто по IP» (по умолчанию ВЫКЛ: общий IP ещё не значит общий владелец, а за CGNAT провайдера сидят сотни чужих людей).'),
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
