#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b436: тихое фоновое авто-обновление — игра сама обновляется и не отвлекает игроков.

Заявка владельца: баннер «Версия игры обновилась (nxmob151)… Обновить» отвлекал
игроков; нужно, чтобы игра сама применяла обновление в фоне.

Что делает патч:
  1. app.js, jpPath(): hot-swap общего документа банка без перезагрузки —
     window.__nxJpSwap переключает синхронизацию на новый документ.
  2. app.js: вместо nxVersionNudge с янтарным баннером и кнопкой «Обновить» —
     блок b436 (nxAutoUpdCheck / nxAutoUpdApply / nxJpHotSwap /
     nxSilentReloadPlan / nxSilentReloadTry / nxReloadSafe): детект новой
     сборки тот же, но реакция тихая — перезагрузка в фоне или после 2 минут
     простоя видимой вкладки, без спинов/модалок/музыки; перед ней jpFlush.
  3. app.js: проверка версии крутится и в фоне + стартует при скрытии вкладки.
  4. Тег сборки nxmob151 -> nxmob152 (index.html ?v= x8, sw.js VERSION,
     tools/build.py BUILD_TAG).

Проверка/применение:
    python3 tools/_b436_patch.py --check   # только проверить, что всё легло
    python3 tools/_b436_patch.py           # применить (идемпотентно)
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

JP_PATH_OLD = """        function jpPath() {
            // b421: синхронизация переехала на документ v3."""
JP_PATH_NEW = """        function jpPath() {
            // b436: тихое авто-обновление уже перевело синхронизацию на новый
            // документ общего банка (hot-swap без перезагрузки страницы)
            try { if (window.__nxJpSwap) return CLOUD.db ? CLOUD.db + '/' + window.__nxJpSwap.room : 'https://textdb.dev/api/data/' + window.__nxJpSwap.doc; } catch (e) {}
            // b421: синхронизация переехала на документ v3."""

OLD_NUDGE = '        function nxVersionNudge() {\n            try {\n                const own = nxOwnTag();\n                if (!own || document.getElementById(\'nx-ver-toast\')) return;\n                fetch(\'index.html?nc=\' + Date.now(), { cache: \'no-store\' }).then(r => (r && r.ok) ? r.text() : \'\').then(t => {\n                    const m = String(t || \'\').match(/assets\\/app\\.js\\?v=(nxmob\\d+)/);\n                    if (!m || m[1] === own) return;\n                    if (document.getElementById(\'nx-ver-toast\')) return;\n                    const c = document.getElementById(\'toast-container\');\n                    if (!c) return;\n                    positionToastContainer();\n                    const el = document.createElement(\'div\');\n                    el.id = \'nx-ver-toast\';\n                    el.className = \'pointer-events-auto w-full px-3.5 py-3 flex items-center gap-2.5 rounded-xl border border-amber-500/40 bg-amber-950/95 text-amber-100 text-[11px] font-bold leading-snug shadow-lg\';\n                    el.innerHTML = \'<i class="fa-solid fa-rotate text-amber-300"></i><span>Версия игры обновилась (\' + m[1] + \'). Эта вкладка синхронизируется по старому документу и видит свой банк — обновите, чтобы играть со всеми.</span>\' +\n                        \'<button type="button" onclick="location.reload()" class="px-2.5 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-[11px] font-black shrink-0 transition">Обновить</button>\';\n                    c.appendChild(el);\n                }).catch(() => {});\n            } catch (e) {}\n        }\n'
NEW_NUDGE = "        // b436: ТИХОЕ АВТО-ОБНОВЛЕНИЕ. Старая вкладка сама замечает новую сборку и\n        // сама же её применяет — без баннера и кнопки, которые отвлекали игроков:\n        //  1) если сборка перенесла общий документ банка — синхронизация прямо на\n        //     лету переключается на него (hot-swap jpPath без перезагрузки), и\n        //     «свой банк» старой вкладки вливается в общий при ближайшем пуше;\n        //  2) перезагрузка страницы ради нового кода планируется на момент, когда\n        //     игрок НЕ смотрит на экран: вкладка в фоне (скрыта) или видима, но\n        //     простаивает (нет спинов, открытых окон, музыки и касаний 2 минуты).\n        // Перед перезагрузкой банк срочно отправляется в облако (jpFlush).\n        // Диагностика без UI: window.__nxAutoUpd = {tag, at, swapped, plan, reloads}.\n        const NX_AUTOUPD_IDLE_MS = 120000; // b436: видимая вкладка перезагружается только после 2 минут простоя\n        let nxAutoUpdTimer = 0, nxAutoUpdVis = null;\n        window.__nxLastInputAt = Date.now();\n        ['pointerdown', 'keydown', 'touchstart', 'wheel'].forEach(ev => {\n            try { window.addEventListener(ev, () => { window.__nxLastInputAt = Date.now(); }, { passive: true, capture: true }); } catch (e) {}\n        });\n        function nxAutoUpdLog() { return window.__nxAutoUpd = window.__nxAutoUpd || { tag: '', at: 0, swapped: '', plan: '', reloads: 0, reloadAt: 0 }; }\n        function nxAudioPlaying() {\n            try { if (CardMusic.audio && !CardMusic.audio.paused) return true; } catch (e) {}\n            try { if (PackMusic.playing) return true; } catch (e) {}\n            return false;\n        }\n        function nxModalOpen() {\n            try {\n                const list = document.querySelectorAll('.fixed.inset-0');\n                for (let i = 0; i < list.length; i++) if (!list[i].classList.contains('hidden')) return true;\n            } catch (e) {}\n            return false;\n        }\n        function nxReloadSafe() {\n            try {\n                if (nxAudioPlaying()) return false;  // не обрываем трек карты/пака\n                if (slots.spinning || lines.spinning || grid.spinning) return false; // не рвём спин\n                if (nxModalOpen()) return false;     // вскрытие, просмотр карты, ежедневка, пароль студии\n                if (document.hidden) return true;    // вкладка в фоне — перезагрузку никто не видит\n                if (Date.now() - (window.__nxLastInputAt || 0) < NX_AUTOUPD_IDLE_MS) return false; // игрок трогает игру\n                const st = document.getElementById('tab-studio');\n                if (st && !st.classList.contains('hidden')) return false; // в студии могли остаться несохранённые формы\n                return true;\n            } catch (e) { return false; }\n        }\n        function nxAutoUpdCheck() {\n            try {\n                const own = nxOwnTag();\n                if (!own) return;\n                fetch('index.html?nc=' + Date.now(), { cache: 'no-store' }).then(r => (r && r.ok) ? r.text() : '').then(t => {\n                    const m = String(t || '').match(/assets\\/app\\.js\\?v=(nxmob\\d+)/);\n                    if (!m || m[1] === own) return;\n                    nxAutoUpdApply(m[1]);\n                }).catch(() => {});\n            } catch (e) {}\n        }\n        function nxVersionNudge() { nxAutoUpdCheck(); } // b422 → b436: та же проверка, но теперь тихая\n        function nxAutoUpdApply(tag) {\n            const S = nxAutoUpdLog();\n            S.tag = tag; S.at = Date.now();\n            nxJpHotSwap(tag);        // сначала — общий документ без перезагрузки\n            nxSilentReloadPlan(tag); // затем — новый код в тихий момент\n        }\n        function nxJpHotSwap(tag) {\n            const S = nxAutoUpdLog();\n            if (S.hotFor === tag) return; S.hotFor = tag;\n            // читаем новый app.js текстом: если банк переехал на другой документ —\n            // переключаем jpPath прямо в этой вкладке и мерджим свой банк в общий\n            fetch('assets/app.js?nc=' + Date.now(), { cache: 'no-store' }).then(r => (r && r.ok) ? r.text() : '').then(t => {\n                t = String(t || '');\n                const mDoc = t.match(/nexus-tcg-jackpot-v(\\d+)/);\n                const mRoom = t.match(/nexus-jackpot-v(\\d+)\\.json/);\n                const newN = (mDoc && mDoc[1]) || (mRoom && mRoom[1]) || '';\n                const curN = (jpPath().match(/jackpot-v(\\d+)/) || [])[1] || '';\n                if (!newN || newN === curN) return;\n                window.__nxJpSwap = { doc: 'nexus-tcg-jackpot-v' + newN, room: 'nexus-jackpot-v' + newN + '.json' };\n                S.swapped = newN;\n                try { jpSyncNow(); } catch (e) {} // свой банк вливается в новый общий документ\n            }).catch(() => {});\n        }\n        function nxSilentReloadPlan(tag) {\n            nxAutoUpdLog().plan = tag;\n            if (nxAutoUpdTimer) return;\n            nxAutoUpdVis = () => { try { if (document.hidden) nxSilentReloadTry(tag); } catch (e) {} };\n            document.addEventListener('visibilitychange', nxAutoUpdVis);\n            nxAutoUpdTimer = setInterval(() => { try { nxSilentReloadTry(tag); } catch (e) {} }, 15000);\n            nxSilentReloadTry(tag); // вкладка уже в фоне — обновляемся сразу\n        }\n        function nxAutoUpdStop() {\n            try { if (nxAutoUpdTimer) clearInterval(nxAutoUpdTimer); } catch (e) {}\n            nxAutoUpdTimer = 0;\n            try { if (nxAutoUpdVis) document.removeEventListener('visibilitychange', nxAutoUpdVis); } catch (e) {}\n            nxAutoUpdVis = null;\n        }\n        function nxSilentReloadTry(tag) {\n            const S = nxAutoUpdLog();\n            let tried = [];\n            try { tried = String(sessionStorage.getItem('nxAutoUpdTried') || '').split(',').filter(Boolean); } catch (e) {}\n            if (tried.indexOf(tag) >= 0) { nxAutoUpdStop(); return; } // в этот тег уже заходили: сервер всё ещё отдаёт старое — не зацикливаемся\n            if (!nxReloadSafe()) return;                              // игрок занят — ждём тихий момент\n            try { sessionStorage.setItem('nxAutoUpdTried', tried.concat([tag]).join(',')); } catch (e) {}\n            S.reloadAt = Date.now(); S.reloads = (S.reloads || 0) + 1;\n            try { jpFlush(); } catch (e) {} // банк уходит в облако до перезагрузки\n            try { location.reload(); } catch (e) {}\n        }\n"

INTERVAL_OLD = "                setInterval(() => { try { if (!document.hidden) nxVersionNudge(); } catch (e) {} }, 180000); // b422: старая вкладка узнаёт, что она старая"
INTERVAL_NEW = "                setInterval(() => { try { nxAutoUpdCheck(); } catch (e) {} }, 180000); // b436: проверка и в фоне тоже — фон и есть шанс обновиться незаметно\n                document.addEventListener('visibilitychange', () => { try { if (document.hidden) nxAutoUpdCheck(); } catch (e) {} }); // b436: вкладку скрыли — запускаем тихое авто-обновление"

TAG_OLD = 'nxmob151'
TAG_NEW = 'nxmob152'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, text):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
        f.write(text)


def apply():
    app = read('assets/app.js')
    if JP_PATH_NEW not in app:
        assert JP_PATH_OLD in app, 'b436: не найден якорь jpPath()'
        app = app.replace(JP_PATH_OLD, JP_PATH_NEW, 1)
    if NEW_NUDGE not in app:
        assert OLD_NUDGE in app, 'b436: не найден старый nxVersionNudge с баннером'
        app = app.replace(OLD_NUDGE, NEW_NUDGE, 1)
    if INTERVAL_NEW not in app:
        assert INTERVAL_OLD in app, 'b436: не найден якорь интервала проверки'
        app = app.replace(INTERVAL_OLD, INTERVAL_NEW, 1)
    write('assets/app.js', app)
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t:
            assert TAG_OLD in t, 'b436: не найден тег %s в %s' % (TAG_OLD, rel)
            t = t.replace(TAG_OLD, TAG_NEW)
            write(rel, t)
    print('b436: применено')


def check():
    app = read('assets/app.js')
    problems = []
    if JP_PATH_NEW not in app:
        problems.append('jpPath: нет hot-swap строки window.__nxJpSwap')
    if 'nx-ver-toast' in app:
        problems.append('остался старый баннер nx-ver-toast')
    if NEW_NUDGE not in app:
        problems.append('нет блока b436')
    if INTERVAL_NEW not in app:
        problems.append('интервал проверки не переведён на nxAutoUpdCheck')
    for rel in TAG_FILES:
        t = read(rel)
        if TAG_NEW not in t or TAG_OLD in t:
            problems.append('%s: тег не nxmob152' % rel)
    if problems:
        print('b436 --check: ПРОБЛЕМЫ:')
        for p in problems:
            print('  -', p)
        raise SystemExit(1)
    print('b436 --check: всё на месте (hot-swap, тихий план, тег nxmob152)')


if __name__ == '__main__':
    check() if '--check' in sys.argv else apply()
