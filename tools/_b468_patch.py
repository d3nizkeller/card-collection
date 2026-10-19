#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b468: игра перестаёт перезагружаться на ходу; формы Студии не теряют введённое.

Жалоба владельца: «постоянно игра моргает и невозможно играть, и в Студии тоже
всё моргает, и при создании сбиваются описание и категории — приходится заново
пересоздавать». Уточнено: страница ПЕРЕЗАГРУЖАЕТСЯ целиком, хаотично, везде;
карточка создаётся не в том паке.

Причины (все четыре найдены в коде, а не угаданы)
-------------------------------------------------
1. ЕДИНСТВЕННАЯ автоматическая перезагрузка в игре — nxSilentReloadTry().
   Защита от зацикливания у неё жила только в sessionStorage
   ('nxAutoUpdTried'). Там, где sessionStorage недоступен или чистится
   (WebView Телеграма, приватный режим, нехватка места), список прочитанных
   тегов всегда пуст — и пока расхождение тега не рассосётся, вкладка
   перезагружается КАЖДЫЕ 15 СЕКУНД. Это и есть «постоянно моргает,
   невозможно играть».
2. nxReloadSafe() проверял document.hidden РАНЬШЕ, чем «открыта ли Студия».
   Стоило вкладке уйти в фон (отошёл, свернул, погас экран) — перезагрузка
   разрешалась немедленно, вместе с заполненной формой карточки. Отсюда
   «сбиваются описание и категории».
3. renderStudio() пересоздавал <select id="card-pack-id"> и НЕ возвращал
   выбранное значение, хотя соседний bulk-pack-id прямо под ним его сохраняет.
   renderStudio() вызывается после каждого сохранения карточки (17812), поэтому
   пак каждый раз перескакивал на первый — «карточка создаётся не в том паке».
4. jpPullLight() каждые 15 секунд безусловно звал jackpotRender(), а тот трижды
   перезаписывал innerHTML списков топа. Данные обычно не менялись — DOM
   пересобирался впустую, блок гас и появлялся заново.
   (Биржа уже защищена: у renderMarket() есть сигнатура __nxMktSig и сохранение
   выбора фильтров — именно этот образец и взят за основу.)

Лечение
-------
1. Журнал тихих перезагрузок переехал в localStorage ('nx_reload_log'):
   не больше NX_RELOAD_CAP=3 перезагрузок за NX_RELOAD_CAP_MS=6 часов и не
   больше одной в один тег. По достижении потолка nxAutoUpdStop() — клиент
   остаётся на текущей сборке вместо бесконечного цикла. Запись делается ДО
   location.reload(), иначе счётчик не успевает сохраниться.
2. Расхождение тега должно подтвердиться дважды (nxUpdSeenTag/nxUpdSeenAt,
   не раньше чем через 20 с): разовое расхождение — это кэш CDN или старый
   index.html из сервис-воркера, а не новая сборка.
3. nxFormDirty() — курсор в любом поле ИЛИ видимая форма Студии с введёнными
   значениями ⇒ перезагрузка запрещена. Проверка стоит ДО document.hidden,
   и отдельно Студия блокирует тихую перезагрузку всегда, а не только в
   видимой вкладке.
4. nxSetHtml(el, html) — запись innerHTML только при реальном отличии.
   Применён к трём спискам топа в jackpotRender() и к превью карточки.
5. renderCardPreviewSoon() — дебаунс 180 мс; 14 inline-обработчиков в
   index.html переведены на него. Плюс className превью перезаписывается
   только при изменении (иначе на каждый символ заново стартовали CSS-анимации
   голографии и ауры). Прямые вызовы renderCardPreview() в app.js оставлены
   немедленными — там нужен синхронный результат.

app.js и index.html менялись — тег сборки nxmob189 -> nxmob190.

Проверка/применение:
    python3 tools/_b468_patch.py --check
    python3 tools/_b468_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob213'
TAG_NEW = 'nxmob214'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

PAIRS.append(('assets/app.js', 1,
              '''        function jackpotRender() {
            const pool = jackpotPool();''',
              '''        // b468: запись innerHTML ТОЛЬКО если содержимое реально отличается.
        // jpPullLight() дёргает jackpotRender() каждые 15 секунд «на всякий случай»
        // (b431: «залипнуть на старом DOM невозможно»), и пересборка идентичного
        // списка выглядела как мерцание: блок гаснет и появляется заново,
        // сбрасываются скролл и наведение.
        function nxSetHtml(el, html) {
            if (!el) return false;
            if (el.innerHTML === html) return false;
            el.innerHTML = html;
            return true;
        }
        function jackpotRender() {
            const pool = jackpotPool();'''))

PAIRS.append(('assets/app.js', 1,
              '''            if (la) la.innerHTML = html;
            if (lb) lb.innerHTML = html;''',
              '''            nxSetHtml(la, html);   // b468
            nxSetHtml(lb, html);   // b468'''))

PAIRS.append(('assets/app.js', 1,
              '''            if (lv) lv.innerHTML = html;''',
              '''            nxSetHtml(lv, html);   // b468'''))

PAIRS.append(('assets/app.js', 1,
              '''        function nxReloadSafe() {
            try {
                if (nxAudioPlaying()) return false;  // не обрываем трек карты/пака
                if (slots.spinning || lines.spinning || grid.spinning) return false; // не рвём спин
                if (nxModalOpen()) return false;     // вскрытие, просмотр карты, ежедневка, пароль студии
                if (document.hidden) return true;    // вкладка в фоне — перезагрузку никто не видит
                if (Date.now() - (window.__nxLastInputAt || 0) < NX_AUTOUPD_IDLE_MS) return false; // игрок трогает игру
                const st = document.getElementById('tab-studio');
                if (st && !st.classList.contains('hidden')) return false; // в студии могли остаться несохранённые формы
                return true;
            } catch (e) { return false; }
        }''',
              '''        // b468: есть ли на экране несохранённая работа. Проверяется ДО «вкладка в
        // фоне» — раньше фоновая вкладка перезагружалась немедленно, и владелец,
        // отошедший на минуту от заполненной формы карточки, возвращался к пустой:
        // описание и выбранный пак пропадали, карточку приходилось создавать заново.
        function nxFormDirty() {
            try {
                const ae = document.activeElement;
                if (ae && ae.tagName && /^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName) && !ae.disabled) return true;
                const st = document.getElementById('tab-studio');
                if (!st || st.classList.contains('hidden')) return false;
                const forms = st.querySelectorAll('form');
                for (let i = 0; i < forms.length; i++) {
                    const f = forms[i];
                    if (f.classList.contains('hidden')) continue;
                    const els = f.querySelectorAll('input, textarea, select');
                    for (let j = 0; j < els.length; j++) {
                        const el = els[j];
                        const ty = String(el.type || '').toLowerCase();
                        if (ty === 'hidden' || ty === 'submit' || ty === 'button' || el.disabled) continue;
                        if (ty === 'checkbox' || ty === 'radio') { if (el.checked !== el.defaultChecked) return true; continue; }
                        const v = String(el.value == null ? '' : el.value);
                        const d = String(el.defaultValue == null ? '' : el.defaultValue);
                        if (v !== '' && v !== d) return true;
                    }
                }
            } catch (e) { return false; }
            return false;
        }
        function nxReloadSafe() {
            try {
                if (nxAudioPlaying()) return false;  // не обрываем трек карты/пака
                if (slots.spinning || lines.spinning || grid.spinning) return false; // не рвём спин
                if (nxModalOpen()) return false;     // вскрытие, просмотр карты, ежедневка, пароль студии
                if (nxFormDirty()) return false;     // b468: курсор в поле или форма заполнена — не перезагружаем
                const st = document.getElementById('tab-studio');
                if (st && !st.classList.contains('hidden')) return false; // b468: Студия — всегда, а не только в видимой вкладке
                if (document.hidden) return true;    // вкладка в фоне — перезагрузку никто не видит
                if (Date.now() - (window.__nxLastInputAt || 0) < NX_AUTOUPD_IDLE_MS) return false; // игрок трогает игру
                return true;
            } catch (e) { return false; }
        }'''))

PAIRS.append(('assets/app.js', 1,
              '''        function nxAutoUpdCheck() {
            try {
                const own = nxOwnTag();
                if (!own) return;
                fetch('index.html?nc=' + Date.now(), { cache: 'no-store' }).then(r => (r && r.ok) ? r.text() : '').then(t => {
                    const m = String(t || '').match(/assets\/app\.js\?v=(nxmob\d+)/);
                    if (!m || m[1] === own) return;
                    nxAutoUpdApply(m[1]);
                }).catch(() => {});
            } catch (e) {}
        }''',
              '''        // b468: расхождение тега должно подтвердиться ДВАЖДЫ, прежде чем мы
        // решимся на перезагрузку. Разовое расхождение — это обычно кэш CDN или
        // отданный сервис-воркером старый index.html, а не новая сборка.
        let nxUpdSeenTag = '', nxUpdSeenAt = 0;
        function nxAutoUpdCheck() {
            try {
                const own = nxOwnTag();
                if (!own) return;
                fetch('index.html?nc=' + Date.now(), { cache: 'no-store' }).then(r => (r && r.ok) ? r.text() : '').then(t => {
                    const m = String(t || '').match(/assets\/app\.js\?v=(nxmob\d+)/);
                    if (!m || m[1] === own) { nxUpdSeenTag = ''; nxUpdSeenAt = 0; return; }
                    if (nxUpdSeenTag !== m[1]) { nxUpdSeenTag = m[1]; nxUpdSeenAt = Date.now(); return; }
                    if (Date.now() - nxUpdSeenAt < 20000) return;   // ждём второго подтверждения
                    nxAutoUpdApply(m[1]);
                }).catch(() => {});
            } catch (e) {}
        }'''))

PAIRS.append(('assets/app.js', 1,
              '''        function nxSilentReloadTry(tag) {
            const S = nxAutoUpdLog();
            let tried = [];
            try { tried = String(sessionStorage.getItem('nxAutoUpdTried') || '').split(',').filter(Boolean); } catch (e) {}
            if (tried.indexOf(tag) >= 0) { nxAutoUpdStop(); return; } // в этот тег уже заходили: сервер всё ещё отдаёт старое — не зацикливаемся
            if (!nxReloadSafe()) return;                              // игрок занят — ждём тихий момент
            try { sessionStorage.setItem('nxAutoUpdTried', tried.concat([tag]).join(',')); } catch (e) {}
            S.reloadAt = Date.now(); S.reloads = (S.reloads || 0) + 1;
            try { jpFlush(); } catch (e) {} // банк уходит в облако до перезагрузки
            try { location.reload(); } catch (e) {}
        }''',
              '''        // b468: журнал тихих перезагрузок в localStorage.
        // Прежняя защита от цикла жила ТОЛЬКО в sessionStorage: там, где он
        // недоступен (WebView Телеграма, приватный режим, очистка хранилища),
        // вкладка перезагружалась бесконечно — каждые 15 секунд, пока тег не
        // сойдётся. Для игрока это и есть «игра постоянно моргает».
        const NX_RELOAD_CAP = 3;                 // не больше трёх тихих перезагрузок…
        const NX_RELOAD_CAP_MS = 6 * 3600000;    // …за шесть часов
        function nxReloadLedger() {
            let l = null;
            try { l = JSON.parse(LS.getItem('nx_reload_log') || 'null'); } catch (e) {}
            if (!l || typeof l !== 'object' || !Array.isArray(l.at)) l = { at: [], tags: {} };
            if (!l.tags || typeof l.tags !== 'object') l.tags = {};
            const cut = Date.now() - NX_RELOAD_CAP_MS;
            l.at = l.at.filter(t => Number(t) > cut);
            return l;
        }
        function nxReloadAllowed(tag) {
            const l = nxReloadLedger();
            if (l.at.length >= NX_RELOAD_CAP) return false;                            // потолок
            if (Number(l.tags[tag] || 0) > Date.now() - NX_RELOAD_CAP_MS) return false; // в этот тег уже заходили
            return true;
        }
        function nxReloadNote(tag) {
            const l = nxReloadLedger();
            l.at.push(Date.now());
            l.tags[tag] = Date.now();
            try { LS.setItem('nx_reload_log', JSON.stringify(l)); } catch (e) {}
        }
        function nxSilentReloadTry(tag) {
            const S = nxAutoUpdLog();
            let tried = [];
            try { tried = String(sessionStorage.getItem('nxAutoUpdTried') || '').split(',').filter(Boolean); } catch (e) {}
            if (tried.indexOf(tag) >= 0) { nxAutoUpdStop(); return; } // в этот тег уже заходили: сервер всё ещё отдаёт старое — не зацикливаемся
            if (!nxReloadAllowed(tag)) { nxAutoUpdStop(); S.capped = tag; return; } // b468: потолок — остаёмся на текущей сборке
            if (!nxReloadSafe()) return;                              // игрок занят — ждём тихий момент
            try { sessionStorage.setItem('nxAutoUpdTried', tried.concat([tag]).join(',')); } catch (e) {}
            nxReloadNote(tag);                                        // b468: пишем ДО reload — иначе счётчик не успеет сохраниться
            S.reloadAt = Date.now(); S.reloads = (S.reloads || 0) + 1;
            try { jpFlush(); } catch (e) {} // банк уходит в облако до перезагрузки
            try { location.reload(); } catch (e) {}
        }'''))

PAIRS.append(('assets/app.js', 1,
              '''            const select = document.getElementById('card-pack-id');
            if (state.packs.length === 0) {
                select.innerHTML = `<option value="">Сначала создайте пак</option>`;
            } else {
                select.innerHTML = state.packs.map(p => `<option value="${p.id}">${p.title}</option>`).join('');
            }''',
              '''            const select = document.getElementById('card-pack-id');
            if (select) {
                // b468: выбор пака СОХРАНЯЕМ. Раньше список пересоздавался, и
                // «категория» карточки сбрасывалась на первый пак — при поточном
                // создании карточек они уезжали не в тот пак, их приходилось
                // удалять и создавать заново. Соседний bulk-pack-id ниже так и делает.
                const keepPack = select.value;
                if (state.packs.length === 0) {
                    select.innerHTML = `<option value="">Сначала создайте пак</option>`;
                } else {
                    select.innerHTML = state.packs.map(p => `<option value="${p.id}">${p.title}</option>`).join('');
                }
                if (keepPack && state.packs.some(p => p.id === keepPack)) select.value = keepPack;
            }'''))

PAIRS.append(('assets/app.js', 1,
              '''        // живой предпросмотр карты в форме Студии''',
              '''        // b468: превью перерисовывается НЕ на каждое нажатие клавиши, а через
        // 180 мс после последнего. oninput="renderCardPreview()" стоял на 14 полях
        // формы: каждый символ полностью пересобирал превью вместе с <img> арта,
        // картинка вспыхивала, а набор текста на телефоне подтормаживал.
        let cardPreviewT = 0;
        function renderCardPreviewSoon() {
            try { clearTimeout(cardPreviewT); } catch (e) {}
            cardPreviewT = setTimeout(() => { cardPreviewT = 0; try { renderCardPreview(); } catch (e) {} }, 180);
        }
        // живой предпросмотр карты в форме Студии'''))

PAIRS.append(('assets/app.js', 1,
              '''            const z = cardTextZones(L, badge, nameHtml, descHtml, statsHtml);
            box.className = `relative z-10 w-full card-aspect rounded-xl overflow-hidden border-2 shadow-xl flex flex-col justify-between p-2.5 ${getRarityClass(rarity)} ${cardHoloClass(fake)}`;
            box.innerHTML = `${image ? `<img src="${mediaThumbMid(image)}" data-nx-full="${mediaUrl(image)}" alt="" onerror="imgErrorChain(this)"${cardArtStyle(fake)} class="absolute inset-0 w-full h-full object-cover z-0" loading="lazy" decoding="async">` : ''}
                <div class="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-transparent to-slate-950/10 z-10"></div>
                ${z.top}${z.bottom}${cardShineOverlay(fake, 25)}`;
            applyCardAura(document.getElementById('card-preview-aura'), fake, 'aura-preview');
            try { nxCardPreviewBind(); } catch (e) {} // b460: колесо/драг/даблклик по превью
        }''',
              '''            const z = cardTextZones(L, badge, nameHtml, descHtml, statsHtml);
            // b468: className перезаписываем только если он изменился — иначе на
            // каждый символ заново стартовали CSS-анимации голографии и ауры,
            // и превью заметно вспыхивало. Сам DOM — тоже только при отличии.
            const cls = `relative z-10 w-full card-aspect rounded-xl overflow-hidden border-2 shadow-xl flex flex-col justify-between p-2.5 ${getRarityClass(rarity)} ${cardHoloClass(fake)}`;
            if (box.className !== cls) box.className = cls;
            nxSetHtml(box, `${image ? `<img src="${mediaThumbMid(image)}" data-nx-full="${mediaUrl(image)}" alt="" onerror="imgErrorChain(this)"${cardArtStyle(fake)} class="absolute inset-0 w-full h-full object-cover z-0" loading="lazy" decoding="async">` : ''}
                <div class="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-transparent to-slate-950/10 z-10"></div>
                ${z.top}${z.bottom}${cardShineOverlay(fake, 25)}`);
            applyCardAura(document.getElementById('card-preview-aura'), fake, 'aura-preview');
            try { nxCardPreviewBind(); } catch (e) {} // b460: колесо/драг/даблклик по превью
        }'''))

PAIRS.append(('index.html', 1,
              '''oninput="renderCardPreview();nxEmbedLampRefresh('card-image')"''',
              '''oninput="renderCardPreviewSoon();nxEmbedLampRefresh('card-image')"'''))

PAIRS.append(('index.html', 7,
              '''oninput="renderCardPreview()"''',
              '''oninput="renderCardPreviewSoon()"'''))

PAIRS.append(('index.html', 6,
              '''onchange="renderCardPreview()"''',
              '''onchange="renderCardPreviewSoon()"'''))

def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8', newline='') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, cnt, old, new in PAIRS:
        txt = files.get(rel)
        if txt is None:
            txt = read(rel)
        if txt.count(old) != cnt:
            problems.append('%s: якорь встретился %d раз вместо %d: %s...' % (rel, txt.count(old), cnt, old[:60]))
            continue
        files[rel] = txt.replace(old, new)
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
        print('b468: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b468: перезагрузки ограничены, формы Студии не теряются; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
