#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b467: отдельная ссылка на Студию — из обычного интерфейса она больше не открывается.

Просьба владельца: «сделаем отдельную ссылку админ-панели Студия, чтоб
пользователи туда не могли попасть со стандартного интерфейса».

Как было
--------
Раздел «Студия» открывался жестом: 5 быстрых нажатий по вкладке «Награды»
(HIDDEN_TAPS_NEEDED=5, окно 1600 мс). Жест выдавали подсказка-прогресс
«●●○○○» и тики звука, поэтому находился перебором. Хуже того, флаг
разблокировки писался в localStorage ('ui_prefs_v1'.section=1) и жил вечно:
однажды найденная кнопка «Студия» оставалась в меню навсегда, в том числе
на чужом телефоне и после «Сброса прогресса».

Как стало
---------
1. Жест УДАЛЁН целиком: onHiddenGestureTap, hiddenTapHintShow, счётчики
   hiddenTapCount/Last/Timer/Hint, константы HIDDEN_TAB_GESTURE,
   HIDDEN_TAPS_NEEDED, HIDDEN_TAP_WINDOW. Слушатель на «Награды» больше
   не вешается — вкладка снова обычная.
2. Вход — по ссылке  ?studio=<ключ>  (понимается и #studio=<ключ>).
   Ключ: STUDIO_LINK_KEY в assets/app.js.
3. Ключ стирается из адресной строки через history.replaceState сразу после
   чтения, поэтому скопированный адрес не отдаёт рабочий вход.
4. Флаг разблокировки переехал из localStorage в sessionStorage: переживает
   перезагрузку вкладки (включая тихое автообновление), умирает вместе с ней.
   Если sessionStorage заблокирован (приватный режим, часть WebView), работает
   запасной флаг в памяти hiddenSessionMem — владелец не останется за дверью.
5. revokeLegacyHiddenUnlock() при старте удаляет 'ui_prefs_v1'.section —
   у всех, кто жест уже нашёл, кнопка «Студия» пропадает.
6. lockHiddenTab() (кнопка «Скрыть раздел» в Студии, index.html:898) теперь
   гасит сессионный флаг; подсказки переписаны под ссылку.

Что НЕ изменилось
-----------------
Настоящая защита — пароль комнаты (studioGateNeeded / submitStudioPass, b133).
Ссылка только показывает вход, впускает пароль. Ключ ссылки лежит в app.js
открыто, как и весь клиентский код: это защита от случайного входа, а не
секрет. hiddenUiPrefs/saveHiddenUiPrefs оставлены — их читают альбомы
(albumsUiState, saveAlbumsUiPrefs), трогать их было нельзя.
Секретных достижений в игре нет (фильтр !a.secret на 4084 защитный), поэтому
удаление жеста ничего не сломало в «Наградах».

app.js и index.html менялись — тег сборки nxmob188 -> nxmob189.

Проверка/применение:
    python3 tools/_b467_patch.py --check
    python3 tools/_b467_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob188'
TAG_NEW = 'nxmob189'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

# 1) весь блок «СКРЫТЫЙ РАЗДЕЛ» — от заголовка до конца initHiddenTab()
PAIRS.append(('assets/app.js', '''        // ============ СКРЫТЫЙ РАЗДЕЛ («Студия») ============
        // Вкладка-редактор спрятана от обычных пользователей: кнопок в навигации не видно,
        // упоминаний в интерфейсе нет, а прямой вызов switchTab('studio') не срабатывает.
        // Открывается жестом: 5 быстрых нажатий по вкладке «Награды» (пауза между
        // нажатиями — не больше HIDDEN_TAP_WINDOW мс, иначе счёт начинается заново).
        // Флаг хранится отдельно от игрового сейва: «Сброс прогресса» и экспорт/импорт
        // JSON его не трогают и не раскрывают.
        const HIDDEN_TAB = 'studio';
        const HIDDEN_TAB_NAV = ['nav-studio', 'mob-nav-studio'];
        const HIDDEN_TAB_GESTURE = ['nav-rewards', 'mob-nav-rewards']; // по чему жмём
        const HIDDEN_TAPS_NEEDED = 5;
        const HIDDEN_TAP_WINDOW = 1600;
        const HIDDEN_UI_KEY = 'ui_prefs_v1'; // неприметное имя: похоже на обычные настройки интерфейса

        let hiddenTapCount = 0;
        let hiddenTapLast = 0;
        let hiddenTapTimer = null;
        let hiddenTapHint = null;

        function hiddenUiPrefs() {
            try { return JSON.parse(LS.getItem(HIDDEN_UI_KEY) || '{}') || {}; } catch (e) { return {}; }
        }
        function saveHiddenUiPrefs(p) {
            try { LS.setItem(HIDDEN_UI_KEY, JSON.stringify(p)); } catch (e) { /* работаем без сохранения */ }
        }
        function isHiddenTabUnlocked() {
            return hiddenUiPrefs().section === 1;
        }
        // switchTab() перезаписывает className кнопок, поэтому видимость держим в style.display
        function applyHiddenTabVisibility() {
            const on = isHiddenTabUnlocked();
            HIDDEN_TAB_NAV.forEach(id => {
                const b = document.getElementById(id);
                if (b) b.style.display = on ? '' : 'none';
            });
        }

        // крошечная подсказка-прогресс у «Наград» — видна только во время жеста
        function hiddenTapHintShow(count, anchor) {
            if (!hiddenTapHint) {
                hiddenTapHint = document.createElement('div');
                hiddenTapHint.className = 'fixed pointer-events-none px-2 py-1 rounded-full bg-slate-950/90 border border-slate-700/70 text-[9px] font-mono tracking-[0.2em] text-slate-400 shadow-lg transition-opacity duration-300';
                hiddenTapHint.style.zIndex = '9999';
                document.body.appendChild(hiddenTapHint);
            }
            let dots = '';
            for (let i = 0; i < HIDDEN_TAPS_NEEDED; i++) dots += i < count ? '●' : '○';
            hiddenTapHint.textContent = dots;
            const r = anchor.getBoundingClientRect();
            hiddenTapHint.style.left = Math.max(8, Math.min(window.innerWidth - 96, r.left + r.width / 2 - 44)) + 'px';
            hiddenTapHint.style.top = Math.max(4, r.top - 28) + 'px';
            hiddenTapHint.style.opacity = '1';
            clearTimeout(hiddenTapTimer);
            hiddenTapTimer = setTimeout(() => {
                hiddenTapCount = 0;
                if (hiddenTapHint) hiddenTapHint.style.opacity = '0';
            }, HIDDEN_TAP_WINDOW);
        }

        function onHiddenGestureTap(btn) {
            if (isHiddenTabUnlocked()) return;
            const now = Date.now();
            hiddenTapCount = (now - hiddenTapLast <= HIDDEN_TAP_WINDOW) ? hiddenTapCount + 1 : 1;
            hiddenTapLast = now;
            if (hiddenTapCount < 2) { // одиночное нажатие — обычный переход на вкладку, без реакций
                clearTimeout(hiddenTapTimer);
                hiddenTapTimer = setTimeout(() => { hiddenTapCount = 0; }, HIDDEN_TAP_WINDOW);
                return;
            }
            if (hiddenTapCount >= HIDDEN_TAPS_NEEDED) {
                clearTimeout(hiddenTapTimer);
                hiddenTapCount = 0;
                if (hiddenTapHint) hiddenTapHint.style.opacity = '0';
                unlockHiddenTab();
                return;
            }
            // тихий тик — с каждым нажатием чуть выше, ничего не объясняя
            if (SoundFX.enabled) { try { SoundFX.tone(300 + hiddenTapCount * 90, 0.05, 'sine', 0.05); } catch (e) {} }
            hiddenTapHintShow(hiddenTapCount, btn);
        }

        function unlockHiddenTab() {
            const p = hiddenUiPrefs(); p.section = 1; saveHiddenUiPrefs(p);
            applyHiddenTabVisibility();
            if (SoundFX.enabled) {
                try {
                    SoundFX.tone(523, 0.12, 'sine', 0.1);
                    SoundFX.tone(784, 0.14, 'sine', 0.1, 0.09);
                    SoundFX.tone(1047, 0.22, 'sine', 0.1, 0.18);
                } catch (e) {}
            }
            showToast('🔓 Открыт скрытый раздел: «Студия» появилась в меню', 'success');
            renderRewardsIfVisible(); // секретное достижение снова показывается
        }

        function lockHiddenTab() {
            const p = hiddenUiPrefs(); p.section = 0; saveHiddenUiPrefs(p);
            hiddenTapCount = 0;
            clearTimeout(hiddenTapTimer);
            if (hiddenTapHint) hiddenTapHint.style.opacity = '0';
            applyHiddenTabVisibility();
            const tab = document.getElementById('tab-' + HIDDEN_TAB);
            if (tab && !tab.classList.contains('hidden')) switchTab('store');
            renderRewardsIfVisible();
            showToast('Раздел снова скрыт — доступ по жесту: 5 нажатий на «Награды»', 'info');
        }

        function initHiddenTab() {
            applyHiddenTabVisibility();
            HIDDEN_TAB_GESTURE.forEach(id => {
                const b = document.getElementById(id);
                if (b && !b.dataset.hiddenGesture) {
                    b.dataset.hiddenGesture = '1';
                    b.addEventListener('click', () => onHiddenGestureTap(b));
                }
            });
        }''',
              '''        // ============ СКРЫТЫЙ РАЗДЕЛ («Студия») ============
        // b467: вход в Студию — ТОЛЬКО по отдельной ссылке. Жеста больше нет.
        //
        // Раньше раздел открывался пятью быстрыми нажатиями по вкладке «Награды»,
        // а флаг навсегда оставался в localStorage ('ui_prefs_v1'.section).
        // Жест находился перебором, его выдавали подсказка-прогресс и тики звука,
        // а однажды найденная кнопка «Студия» оставалась в меню навсегда —
        // в том числе на чужом телефоне.
        //
        // Теперь:
        //   • вход — ссылка  ?studio=<ключ>  (работает и вариант #studio=<ключ>);
        //   • ключ сразу стирается из адресной строки (history.replaceState),
        //     поэтому «скопировать адрес и переслать» больше не отдаёт чужому
        //     рабочий вход — в адресе остаётся обычный index.html;
        //   • флаг живёт в sessionStorage: переживает перезагрузку вкладки
        //     (в том числе тихое автообновление nxSilentReload), но умирает
        //     вместе с вкладкой — на общем телефоне следов не остаётся;
        //   • если sessionStorage недоступен (приватный режим, часть WebView),
        //     работает запасной флаг в памяти — владелец не останется за дверью;
        //   • старые постоянные разблокировки отзываются при старте, поэтому
        //     у тех, кто жест уже нашёл, кнопка «Студия» пропадает.
        //
        // Ссылка только ПОКАЗЫВАЕТ вход. Впускает по-прежнему пароль комнаты
        // (studioGateNeeded / submitStudioPass, b133) — настоящая защита именно
        // он: ключ ссылки лежит в app.js открыто, как и весь клиентский код.
        const HIDDEN_TAB = 'studio';
        const HIDDEN_TAB_NAV = ['nav-studio', 'mob-nav-studio'];
        const HIDDEN_UI_KEY = 'ui_prefs_v1';      // общие UI-настройки (их читают альбомы)
        const HIDDEN_SESSION_KEY = 'ui_sess_v1';  // b467: разблокировка раздела — только на сессию
        const STUDIO_LINK_KEY = '8bpr1tprya2g';   // b467: ключ ссылки-входа; менять здесь

        function hiddenUiPrefs() {
            try { return JSON.parse(LS.getItem(HIDDEN_UI_KEY) || '{}') || {}; } catch (e) { return {}; }
        }
        function saveHiddenUiPrefs(p) {
            try { LS.setItem(HIDDEN_UI_KEY, JSON.stringify(p)); } catch (e) { /* работаем без сохранения */ }
        }

        // b467: сессионный флаг. sessionStorage переживает перезагрузку вкладки;
        // если он заблокирован, остаётся копия в памяти — до конца жизни страницы.
        let hiddenSessionMem = null;
        function hiddenSessionPrefs() {
            try { return JSON.parse(sessionStorage.getItem(HIDDEN_SESSION_KEY) || '{}') || {}; } catch (e) { return hiddenSessionMem || {}; }
        }
        function saveHiddenSessionPrefs(p) {
            hiddenSessionMem = p;
            try { sessionStorage.setItem(HIDDEN_SESSION_KEY, JSON.stringify(p)); } catch (e) { /* приватный режим */ }
        }
        function isHiddenTabUnlocked() {
            return hiddenSessionPrefs().section === 1;
        }
        // switchTab() перезаписывает className кнопок, поэтому видимость держим в style.display
        function applyHiddenTabVisibility() {
            const on = isHiddenTabUnlocked();
            HIDDEN_TAB_NAV.forEach(id => {
                const b = document.getElementById(id);
                if (b) b.style.display = on ? '' : 'none';
            });
        }

        // b467: отзываем постоянные разблокировки, оставленные жестом до b467.
        // Без этого у нашедшего жест кнопка «Студия» осталась бы в меню навсегда.
        function revokeLegacyHiddenUnlock() {
            const p = hiddenUiPrefs();
            if (p.section === undefined) return false;
            delete p.section;
            saveHiddenUiPrefs(p);
            return true;
        }

        // b467: ключ входа из адреса — ?studio=<ключ> или #studio=<ключ>
        function nxStudioLinkKey() {
            try {
                const q = new URLSearchParams(String(location.search || '')).get('studio');
                if (q) return String(q);
                const m = String(location.hash || '').match(/[#&]studio=([^&]+)/);
                if (m && m[1]) return decodeURIComponent(m[1]);
            } catch (e) { /* URLSearchParams недоступен — вход по ссылке не сработает, гейт пароля цел */ }
            return '';
        }
        // b467: убираем ключ из адресной строки, сохраняя остальные параметры и хэш.
        // Иначе владелец сам раздал бы рабочий вход, скопировав адрес из браузера.
        function nxStudioLinkClean() {
            try {
                if (!window.history || !history.replaceState) return;
                const q = new URLSearchParams(String(location.search || ''));
                q.delete('studio');
                const qs = q.toString();
                const hash = String(location.hash || '').replace(/^#/, '')
                    .split('&').filter(p => p && p.indexOf('studio=') !== 0).join('&');
                history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + (hash ? '#' + hash : ''));
            } catch (e) {}
        }

        function unlockHiddenTab() {
            const p = hiddenSessionPrefs(); p.section = 1; saveHiddenSessionPrefs(p);
            applyHiddenTabVisibility();
            if (SoundFX.enabled) {
                try {
                    SoundFX.tone(523, 0.12, 'sine', 0.1);
                    SoundFX.tone(784, 0.14, 'sine', 0.1, 0.09);
                    SoundFX.tone(1047, 0.22, 'sine', 0.1, 0.18);
                } catch (e) {}
            }
            showToast('🔓 «Студия» добавлена в меню — до конца этой вкладки', 'success');
            renderRewardsIfVisible(); // секретное достижение снова показывается
        }

        function lockHiddenTab() {
            const p = hiddenSessionPrefs(); p.section = 0; saveHiddenSessionPrefs(p);
            applyHiddenTabVisibility();
            const tab = document.getElementById('tab-' + HIDDEN_TAB);
            if (tab && !tab.classList.contains('hidden')) switchTab('store');
            renderRewardsIfVisible();
            showToast('Раздел скрыт — вход снова только по ссылке', 'info');
        }

        function initHiddenTab() {
            // b467: сначала отзываем чужие постоянные разблокировки, потом читаем ссылку
            try { if (revokeLegacyHiddenUnlock()) applyHiddenTabVisibility(); } catch (e) {}
            const key = nxStudioLinkKey();
            if (key) {
                nxStudioLinkClean();                 // ключ не должен остаться в адресной строке
                if (key === STUDIO_LINK_KEY) {
                    if (!isHiddenTabUnlocked()) unlockHiddenTab();
                } else {
                    showToast('Неверная ссылка на раздел', 'error');
                }
            }
            applyHiddenTabVisibility();
        }'''))

# 2) страж в switchTab(): комментарий про жест больше не правда
PAIRS.append(('assets/app.js', '''            // скрытый раздел недоступен, пока не открыт жестом
            if (tabId === HIDDEN_TAB && !isHiddenTabUnlocked()) {''',
              '''            // b467: скрытый раздел недоступен, пока не открыт по ссылке ?studio=…
            if (tabId === HIDDEN_TAB && !isHiddenTabUnlocked()) {'''))

# 3) место вызова initHiddenTab(): жест больше не вешается
PAIRS.append(('assets/app.js', '''            initHiddenTab(); // скрытый раздел: прячем кнопки навигации и вешаем жест на «Награды»''',
              '''            initHiddenTab(); // b467: прячем кнопки навигации; вход в раздел — только по ссылке ?studio=…'''))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8', newline='') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, old, new in PAIRS:
        txt = files.get(rel) or read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        if txt.count(o) != 1:
            problems.append('%s: якорь встретился %d раз: %s...' % (rel, txt.count(o), o[:60]))
            continue
        files[rel] = txt.replace(o, n, 1)
    for rel in TAG_FILES:
        txt = files.get(rel) or read(rel)
        if TAG_NEW in txt:
            problems.append('%s: тег уже %s' % (rel, TAG_NEW))
            continue
        if TAG_OLD not in txt:
            problems.append('%s: нет тега %s' % (rel, TAG_OLD))
            continue
        files[rel] = txt.replace(TAG_OLD, TAG_NEW)
    if problems:
        for p in problems:
            print('ПРОБЛЕМА:', p)
        return 1
    if '--check' in sys.argv:
        print('b467: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b467: Студия только по ссылке ?studio=…; жест удалён; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
