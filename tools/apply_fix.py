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
    ('b371-4776-4776',
     "                e.prof = (function () { try { const c = profCode(); if (c) return 'код ' + c; if (profIpAuto() && nxPublicIp()) return 'IP-авто'; } catch (e) {} return ''; })(); // b364",
     "                e.prof = (function () { try { const c = profCode(); if (c) return 'код ' + c; } catch (e) {} return ''; })(); // b364; b371: синхронизация только по коду/QR"),
    ('b371-5033-5039',
     "        function profIpAuto() { try { return LS.getItem('nx_prof_ipauto') === '1'; } catch (e) { return false; } } // b367: ПО УМОЛЧАНИЮ ВЫКЛ: за одним IP провайдера (CGNAT) сидят сотни чужих людей — их балансы смешивались\n        function profDocKey() { // ключ облачного документа профиля: код важнее IP\n            const c = profCode();\n            if (c) return 'c-' + c.toLowerCase();\n            if (!profIpAuto()) return '';\n            const ip = nxPublicIp();\n            return ip ? 'i-' + profHashIp(ip) : '';",
     "        // b371: синхронизация по IP удалена по решению владельца: у каждого игрока\n        // свой баланс, как раньше. Общий баланс и прогресс — только у устройств,\n        // привязанных кодом профиля (вручную или QR-кодом).\n        function profDocKey() { // ключ облачного документа профиля: только код/QR\n            const c = profCode();\n            return c ? 'c-' + c.toLowerCase() : '';"),
    ('b371-5398-5419',
     '        function profToggleIpAuto() {\n            try { LS.setItem(\'nx_prof_ipauto\', profIpAuto() ? \'0\' : \'1\'); LS.removeItem(\'nx_prof_lastbal\'); LS.removeItem(\'nx_prof_movc\'); } catch (e) {} // b367: смена сообщества = новый леджер\n            profUI(); profSyncSoon();\n        }\n        function profLabel() {\n            const c = profCode();\n            if (c) return \'код \' + c;\n            if (!profIpAuto()) return \'выключен\';\n            const ip = nxPublicIp();\n            return ip ? \'авто по IP \' + ip : \'авто по IP (IP ещё не известен)\';\n        }\n        function profUI() {\n            const st = document.getElementById(\'nx-prof-status\');\n            if (st) {\n                const book = (profLastRemote && profLastRemote.book) ? Object.keys(profLastRemote.book).length : 0;\n                st.innerHTML =\n                    \'<span class="text-[10px] text-slate-400">Профиль: <b class="text-slate-200">\' + cloudEsc(profLabel()) + \'</b></span>\' +\n                    \'<span class="text-[10px] text-slate-500">устройств в профиле: <b class="text-slate-300">\' + book + \'</b></span>\' +\n                    \'<span class="text-[10px] text-slate-500">синхронизация: <b class="text-slate-300">\' + (profLastTs ? statsAgo(profLastTs) : \'ещё не была\') + \'</b></span>\';\n            }\n            const b = document.getElementById(\'nx-prof-ipauto-btn\');\n            if (b) b.innerHTML = \'<i class="fa-solid fa-location-dot mr-1"></i>Авто по IP: \' + (profIpAuto() ? \'вкл\' : \'выкл\');',
     '        function profLabel() { // b371: профиль — только код; без кода у устройства свой баланс\n            const c = profCode();\n            return c ? \'код \' + c : \'не создан — баланс только этого устройства\';\n        }\n        function profUI() {\n            const st = document.getElementById(\'nx-prof-status\');\n            if (st) {\n                const book = (profLastRemote && profLastRemote.book) ? Object.keys(profLastRemote.book).length : 0;\n                st.innerHTML =\n                    \'<span class="text-[10px] text-slate-400">Профиль: <b class="text-slate-200">\' + cloudEsc(profLabel()) + \'</b></span>\' +\n                    \'<span class="text-[10px] text-slate-500">устройств в профиле: <b class="text-slate-300">\' + book + \'</b></span>\' +\n                    \'<span class="text-[10px] text-slate-500">синхронизация: <b class="text-slate-300">\' + (profLastTs ? statsAgo(profLastTs) : \'ещё не была\') + \'</b></span>\';\n            }'),
    ('b371-5655-5655',
     '                        \'<span class="text-[11px] font-black truncate max-w-[240px] \' + (g.blk ? \'text-rose-300\' : \'text-white\') + \'">\' + (i + 1) + \'. \' + cloudEsc(name) + (multi ? \' <span class="text-sky-300">— устройств: \' + g.members.length + \', это один пользователь</span>\' : \'\') + \'</span>\' +',
     '                        \'<span class="text-[11px] font-black truncate max-w-[240px] \' + (g.blk ? \'text-rose-300\' : \'text-white\') + \'">\' + (i + 1) + \'. \' + cloudEsc(name) + (multi ? (g.prof ? \' <span class="text-emerald-300">— устройств: \' + g.members.length + \', синхронизированы профилем (код/QR)</span>\' : \' <span class="text-sky-300">— устройств: \' + g.members.length + \' с одного IP, балансы отдельные</span>\') : \'\') + \'</span>\' +'),
]

QR_EDITS = [
    ('b369-embed-err',
     "    const err = m => { if (btn) btn.disabled = false; try { showToast(m, 'error'); } catch (e) {} nxStatus(m, 'err'); };",
     "    const err = m => { if (btn) btn.disabled = false; try { nxOwnerToast(m, 'error'); } catch (e) {} nxStatus(m, 'err'); }; // b369: системные ошибки вшивания — только в Студии (скриншот-жалоба: тост о лимите вшивания пугал игроков посреди игры)"),
    ('b369-crash-toast',
     "showToast('Прошлые сессии обрывались браузером (нехватка памяти) — 3D отключено, игры в плоском режиме. Вернуть 3D можно в Студии', 'error')",
     "nxOwnerToast('Прошлые сессии обрывались браузером (нехватка памяти) — 3D отключено, игры в плоском режиме. Вернуть 3D можно в Студии', 'error')"),
    ('b369-memguard-toast',
     "showToast('Память устройства на пределе — перезагружаю игру, прогресс сохранён', 'error')",
     "nxOwnerToast('Память устройства на пределе — перезагружаю игру, прогресс сохранён', 'error')"),
]

MONO_EDITS = [
    ('b371-ui-btn',
     '                    <button type="button" id="nx-prof-ipauto-btn" onclick="profToggleIpAuto()" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-[10px] font-bold transition"></button>\n',
     ''),
    ('b371-ui-text',
     'Пока кода нет — устройства можно связать тумблером «Авто по IP» (по умолчанию ВЫКЛ: общий IP ещё не значит общий владелец, а за CGNAT провайдера сидят сотни чужих людей).',
     'Синхронизация по IP удалена (b371): у каждого игрока свой баланс, как раньше. Общий баланс и прогресс — только у устройств, привязанных кодом профиля или QR-кодом.'),
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
