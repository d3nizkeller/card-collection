// ============ b279: ПЕРЕНОС ПРОГРЕССА МЕЖДУ УСТРОЙСТВАМИ ПО QR ============
// Кнопка с иконкой QR в шапке (и в мобильном меню) открывает модалку: сверху —
// QR-код этого устройства, внизу — кнопка «Отсканировать код». Передаётся ВЕСЬ
// личный прогресс: баланс, коллекция, статистика, достижения, миссии, колода,
// история, альбомные бонусы, статистика паков/окон (b277) и имя игрока.
// Каталог паков/карт общий через облако комнаты, поэтому в QR кладём только
// личный прогресс: сжимаем deflate-raw + base64url и зашиваем прямо в QR.
// Если прогресс не помещается в QR — кладём снимок в транзитное облако textdb,
// а в QR пишем короткий ключ NXR1.… Получатель поддерживает оба формата,
// плюс ручную вставку кода и старые полные JSON-резервки (applyImportObject).
const QRX_DIRECT = 'NXQ1.', QRX_RELAY = 'NXR1.';
const QRX_MAX_DIRECT = 2300; // потолок байт QR (v40, уровень M) с запасом
let qrxStream = null, qrxTimer = null, qrxPending = null, qrxCode = '', qrxBuilding = false;

function qrxSnapshot() {
    let nm = ''; try { nm = LS.getItem(PLAYER_NAME_KEY) || ''; } catch (e) {}
    return {
        v: 1, t: Date.now(),
        c: state.coins,
        col: state.collection || {},
        st: state.stats || {},
        dy: state.daily || {},
        mi: state.missions || { date: null, list: [] },
        ac: state.achievements || {},
        pi: state.pity || { packsSinceEpic: 0 },
        dk: Array.isArray(state.deck) ? state.deck : [],
        hi: (state.history || []).slice(0, 30),
        ab: state.albumBonus || {},
        ps: state.packStats || {},   // b277
        wb: state.windowBuys || {},  // b277
        nm: nm
    };
}
function qrxSumOf(col) {
    let cards = 0, uniq = 0;
    for (const k in (col || {})) { uniq++; cards += Math.max(0, (col || {})[k] | 0); }
    return { cards: cards, uniq: uniq };
}
function qrxSelfSummary(d) {
    const s = qrxSumOf(d.col);
    return { coins: (d.c | 0), cards: s.cards, uniq: s.uniq, opened: ((d.st || {}).packsOpened) | 0 };
}
function qrxFillChips(id, sum) {
    const el = document.getElementById(id); if (!el) return;
    el.innerHTML =
        '<span class="px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px] font-semibold"><i class="fa-solid fa-coins mr-1"></i>' + Number(sum.coins).toLocaleString('ru-RU') + '</span>' +
        '<span class="px-2.5 py-1 rounded-full bg-violet-500/10 border border-violet-500/30 text-violet-300 text-[11px] font-semibold"><i class="fa-solid fa-layer-group mr-1"></i>' + sum.cards + ' карт</span>' +
        '<span class="px-2.5 py-1 rounded-full bg-sky-500/10 border border-sky-500/30 text-sky-300 text-[11px] font-semibold"><i class="fa-solid fa-images mr-1"></i>' + sum.uniq + ' уникальных</span>' +
        '<span class="px-2.5 py-1 rounded-full bg-fuchsia-500/10 border border-fuchsia-500/30 text-fuchsia-300 text-[11px] font-semibold"><i class="fa-solid fa-box-open mr-1"></i>' + sum.opened + ' паков</span>';
}
// ---- base64url и deflate-raw (нативные CompressionStream, где доступны) ----
function qrxB64(bytes) {
    let bin = ''; const CH = 0x8000;
    for (let i = 0; i < bytes.length; i += CH) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function qrxB64d(s) {
    s = String(s).replace(/-/g, '+').replace(/_/g, '/');
    while (s.length % 4) s += '=';
    const bin = atob(s), out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
}
async function qrxDeflate(u8) {
    if (typeof CompressionStream === 'undefined') return null;
    try {
        const st = new Blob([u8]).stream().pipeThrough(new CompressionStream('deflate-raw'));
        return new Uint8Array(await new Response(st).arrayBuffer());
    } catch (e) { return null; }
}
async function qrxInflate(u8) {
    if (typeof DecompressionStream === 'undefined') return null;
    try {
        const st = new Blob([u8]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
        return new TextDecoder().decode(new Uint8Array(await new Response(st).arrayBuffer()));
    } catch (e) { return null; }
}
// ---- транзитное облако (когда прогресс не помещается в QR напрямую) ----
function qrxRelayUrl(key) { return 'https://textdb.dev/api/data/nexus-tcg-qr-' + key; }
async function qrxRelayPush(obj) {
    const key = Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
    const r = await fetch(qrxRelayUrl(key), { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify(obj) });
    if (!r.ok) throw new Error('транзитное облако: HTTP ' + r.status);
    return key;
}
async function qrxRelayFetch(key) {
    const r = await fetch(qrxRelayUrl(String(key).trim()) + '?nc=' + Date.now(), { cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const t = String(await r.text() || '').trim();
    if (!t || t === 'null') return null;
    return JSON.parse(t);
}
// ---- отрисовка QR на canvas ----
function qrxRender(text) {
    const cv = document.getElementById('qr-canvas'); if (!cv) throw new Error('нет canvas');
    const qr = qrcode(0, 'L'); // b280: уровень L — меньше модулей, камере проще прочитать плотный код
    qr.addData(text, 'Byte');
    qr.make();
    const n = qr.getModuleCount(), qz = 4, m = 8; // b280: крупнее модуль в canvas — резче на hiDPI
    cv.width = cv.height = (n + qz * 2) * m;
    const ctx = cv.getContext('2d');
    ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.fillStyle = '#0b1220';
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) ctx.fillRect((c + qz) * m, (r + qz) * m, m, m);
}
// ---- модалка и виды ----
function openQrModal() {
    const m = document.getElementById('modal-qr'); if (!m) return;
    m.classList.remove('hidden');
    qrxPending = null;
    qrxView('show');
    qrxBuild();
}
function closeQrModal() {
    qrxStopScan();
    const m = document.getElementById('modal-qr'); if (m) m.classList.add('hidden');
}
function qrxView(name) {
    ['show', 'scan', 'conf'].forEach(v => {
        const el = document.getElementById('qr-view-' + v);
        if (el) el.classList.toggle('hidden', v !== name);
    });
    const pd = document.getElementById('qr-paste-details');
    if (pd) pd.classList.toggle('hidden', name === 'conf');
}
function qrxRebuild() { qrxBuilding = false; qrxBuild(); }
async function qrxBuild() {
    if (qrxBuilding) return; qrxBuilding = true;
    const status = document.getElementById('qr-show-status');
    const wrap = document.getElementById('qr-canvas-wrap');
    if (status) status.textContent = 'Готовим код…';
    try {
        const snap = qrxSnapshot();
        const json = JSON.stringify(snap);
        qrxFillChips('qr-self-chips', qrxSelfSummary(snap));
        let code = '';
        const def = await qrxDeflate(new TextEncoder().encode(json));
        if (def) {
            const cand = QRX_DIRECT + qrxB64(def);
            if (cand.length <= QRX_MAX_DIRECT) {
                try { qrxRender(cand); code = cand; } catch (e) { code = ''; }
            }
        }
        if (!code) {
            if (status) status.innerHTML = '<i class="fa-solid fa-cloud-arrow-up text-violet-300 mr-1"></i>Прогресс крупный — кладём снимок в транзитное облако…';
            const key = await qrxRelayPush({ d: snap });
            code = QRX_RELAY + key;
            qrxRender(code);
        }
        qrxCode = code;
        if (wrap) wrap.classList.remove('hidden');
        if (status) status.innerHTML = code.indexOf(QRX_DIRECT) === 0
            ? '<i class="fa-solid fa-bolt text-amber-300 mr-1"></i>Прямой код: весь прогресс зашит прямо в QR (' + code.length + ' символов)'
            : '<i class="fa-solid fa-cloud text-violet-300 mr-1"></i>Облачный ключ: снимок прогресса в транзитном облаке, в QR только ключ';
    } catch (e) {
        if (wrap) wrap.classList.add('hidden');
        if (status) status.innerHTML = '<span class="text-rose-400"><i class="fa-solid fa-triangle-exclamation mr-1"></i>Не удалось собрать код: ' + String((e && e.message) || e) + '. Ниже можно скопировать прогресс текстом.</span>';
    } finally { qrxBuilding = false; }
}
// ---- b280: нативный сканер Telegram (для мини-приложения) ----
(function () {
    if (typeof window === 'undefined' || typeof document === 'undefined') return; // b280: вне браузера нечего делать
    if (window.Telegram && window.Telegram.WebApp) return;
    try {
        const s = document.createElement('script');
        s.src = 'https://telegram.org/js/telegram-web-app.js';
        s.async = true;
        s.onload = function () { try { if (window.Telegram && Telegram.WebApp && Telegram.WebApp.isInit) Telegram.WebApp.ready(); } catch (e) {} };
        document.head.appendChild(s);
    } catch (e) {}
})();
function qrxTg() {
    const tw = typeof window !== 'undefined' && window.Telegram && window.Telegram.WebApp;
    if (!tw || typeof tw.showScanQrPopup !== 'function') return null;
    if (!tw.platform || tw.platform === 'unknown') return null; // обычный браузер — не Telegram
    return tw;
}
function qrxLooksLikeCode(s) {
    const t = String(s == null ? '' : s).trim();
    if (!t) return false;
    if (t.indexOf(QRX_DIRECT) === 0 || t.indexOf(QRX_RELAY) === 0) return true;
    if (/[?&]prof=[A-Za-z0-9-]{4,12}/i.test(t)) return true;  // b365: QR профиля синхронизации
    if (/^NXPROF:[A-Za-z0-9]{4,12}$/i.test(t)) return true;   // b365: голый код профиля
    return t.charAt(0) === '{';
}
let qrxTgHandler = null;
function qrxStartTgScan(tw) { // true = системный сканер открыт, false = fallback на веб-камеру
    const st = document.getElementById('qr-scan-status');
    const h = function (ev) {
        const txt = ev && ev.data != null ? String(ev.data) : '';
        if (!qrxLooksLikeCode(txt)) { // чужой код — не закрываем сканер, ждём наш
            try { tw.HapticFeedback && tw.HapticFeedback.notificationOccurred && tw.HapticFeedback.notificationOccurred('error'); } catch (e) {}
            return;
        }
        qrxTgHandler = null;
        try { tw.offEvent('qrTextReceived', h); } catch (e) {}
        try { tw.closeScanQrPopup(); } catch (e) {}
        qrxHandleCode(txt);
    };
    try {
        qrxTgHandler = h;
        tw.onEvent('qrTextReceived', h);
        tw.showScanQrPopup({ text: 'Наведите камеру на код переноса со второго устройства' });
    } catch (e) {
        qrxTgHandler = null;
        try { tw.offEvent('qrTextReceived', h); } catch (e) {}
        return false;
    }
    if (st) st.innerHTML = '<i class="fa-solid fa-qrcode text-violet-300 mr-1"></i>Системный сканер Telegram открыт поверх приложения — наведите его на код второго устройства. Закрыли случайно — нажмите «Отсканировать код» ещё раз.';
    return true;
}
// ---- сканер камеры ----
function qrGoScan() { qrxView('scan'); qrxStartScan(); }
function qrxBackShow() {
    qrxStopScan();
    qrxView('show');
    if (!qrxCode) qrxBuild();
}
async function qrxStartScan() {
    const st = document.getElementById('qr-scan-status');
    const video = document.getElementById('qr-video');
    qrxStopScan();
    const tw = qrxTg(); // b280: в Telegram мини-приложении веб-камера часто заблокирована — берём системный сканер
    if (tw && qrxStartTgScan(tw)) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        if (st) st.innerHTML = '<span class="text-amber-300">Камера в этом браузере недоступна — вставьте код вручную ниже.</span>';
        return;
    }
    if (st) st.innerHTML = '<i class="fa-solid fa-camera text-violet-300 mr-1"></i>Включаем камеру…';
    try {
        qrxStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    } catch (e) {
        if (st) st.innerHTML = '<span class="text-amber-300">Камера недоступна (' + String((e && e.name) || e) + ') — вставьте код вручную ниже.</span>';
        return;
    }
    if (video) { video.srcObject = qrxStream; try { await video.play(); } catch (e) {} }
    if (st) st.innerHTML = '<i class="fa-solid fa-camera text-violet-300 mr-1"></i>Наведите камеру на QR-код второго устройства…';
    qrxTimer = setInterval(qrxTick, 150);
    setTimeout(function () { // b280: сторож — камера включилась, но кадр не пошёл (WebView без медиа)
        if (qrxTimer && video && !video.videoWidth) {
            if (st) st.innerHTML = '<span class="text-amber-300">Камера включилась, но картинка не пошла — система мини-приложения блокирует поток. Откройте сканер ещё раз или вставьте код текстом ниже.</span>';
        }
    }, 3000);
}
function qrxDecodeOnce(img, w, h, inv) {
    try { return jsQR(img.data, w, h, { inversionAttempts: inv }); } catch (e) { return null; }
}
function qrxTick() {
    const video = document.getElementById('qr-video');
    if (!video || !video.videoWidth) return;
    const vw = video.videoWidth, vh = video.videoHeight;
    let cv = document.getElementById('qr-scan-canvas');
    if (!cv) {
        cv = document.createElement('canvas'); cv.id = 'qr-scan-canvas'; cv.style.display = 'none';
        document.body.appendChild(cv);
    }
    const ctx = cv.getContext('2d', { willReadFrequently: true });
    let res = null, img = null;
    // b280 проход 1: весь кадр до 1100px — плотные коды не рассыпаются при уменьшении
    const w1 = Math.min(1100, vw);
    const h1 = Math.max(1, Math.round(vh * (w1 / vw)));
    cv.width = w1; cv.height = h1;
    ctx.drawImage(video, 0, 0, w1, h1);
    try { img = ctx.getImageData(0, 0, w1, h1); res = qrxDecodeOnce(img, w1, h1, 'dontInvert'); } catch (e) { img = null; }
    if (!res) {
        // b280 проход 2: зум в центр в родном разрешении — код далеко или мелкий на экране
        const sw = Math.round(vw * 0.62), sh = Math.round(vh * 0.62);
        const sx = Math.round((vw - sw) / 2), sy = Math.round((vh - sh) / 2);
        const w2 = Math.min(900, sw), h2 = Math.max(1, Math.round(sh * (w2 / sw)));
        cv.width = w2; cv.height = h2;
        ctx.drawImage(video, sx, sy, sw, sh, 0, 0, w2, h2);
        try { img = ctx.getImageData(0, 0, w2, h2); res = qrxDecodeOnce(img, w2, h2, 'attemptBoth'); } catch (e) { img = null; }
    }
    if (res && res.data) {
        const code = res.data;
        qrxStopScan();
        qrxHandleCode(code);
    }
}
function qrxStopScan() {
    if (qrxTgHandler) { // b280: гасим системный сканер Telegram и подписку
        const tw = qrxTg();
        if (tw) { try { tw.offEvent('qrTextReceived', qrxTgHandler); tw.closeScanQrPopup(); } catch (e) {} }
        qrxTgHandler = null;
    }
    if (qrxTimer) { clearInterval(qrxTimer); qrxTimer = null; }
    if (qrxStream) { qrxStream.getTracks().forEach(t => t.stop()); qrxStream = null; }
    const video = document.getElementById('qr-video'); if (video) video.srcObject = null;
}
// ---- разбор полученного кода ----
async function qrxHandleCode(raw) {
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
    } catch (e) {}
    try {
        if (s.indexOf(QRX_RELAY) === 0) {
            if (st) st.innerHTML = '<i class="fa-solid fa-cloud-arrow-down text-violet-300 mr-1"></i>Получаем прогресс из транзитного облака…';
            const obj = await qrxRelayFetch(s.slice(QRX_RELAY.length));
            if (!obj || !obj.d) throw new Error('облако не вернуло данные');
            qrxShowConfirm(obj.d, null);
            return;
        }
        if (s.indexOf(QRX_DIRECT) === 0) {
            const json = await qrxInflate(qrxB64d(s.slice(QRX_DIRECT.length)));
            if (!json) throw new Error('не удалось распаковать код');
            qrxShowConfirm(JSON.parse(json), null);
            return;
        }
        if (s.charAt(0) === '{') {
            const o = JSON.parse(s);
            if (o && o.v === 1 && o.col) { qrxShowConfirm(o, null); return; }
            if (o && o.packs && o.cards) { qrxShowConfirm(null, o); return; }
        }
        throw new Error('не похоже на код переноса');
    } catch (e) {
        showToast('Код не читается: ' + String((e && e.message) || e), 'error');
        if (st) st.innerHTML = '<span class="text-rose-400">Код не распознан. Наведите камеру ещё раз или вставьте текст кода вручную.</span>';
    }
}
function qrxShowConfirm(d, legacy) {
    qrxPending = legacy ? { legacy: legacy } : d;
    let sum;
    if (legacy) {
        const s = qrxSumOf(legacy.collection);
        sum = { coins: legacy.coins | 0, cards: s.cards, uniq: s.uniq, opened: ((legacy.stats || {}).packsOpened) | 0 };
    } else {
        sum = qrxSelfSummary(d);
    }
    qrxFillChips('qr-conf-chips', sum);
    const when = document.getElementById('qr-conf-when');
    if (when) when.innerHTML = legacy
        ? '<i class="fa-solid fa-file-lines mr-1"></i>Полная резервная копия сохранения (JSON)'
        : '<i class="fa-solid fa-clock mr-1"></i>Снимок прогресса от ' + new Date(d.t || Date.now()).toLocaleString('ru-RU');
    qrxView('conf');
}
function qrxCancelConf() { qrxPending = null; qrxView('show'); }
function qrxAccept() {
    const p = qrxPending; qrxPending = null;
    if (!p) return;
    if (p.legacy) { applyImportObject(p.legacy); closeQrModal(); return; }
    qrxApplyProgress(p);
    closeQrModal();
}
// ---- применение принятого прогресса (каталог паков/карт не трогаем — он общий в облаке) ----
function qrxApplyProgress(d) {
    if (typeof d.c === 'number' && isFinite(d.c)) state.coins = Math.max(0, Math.round(d.c));
    if (d.col && typeof d.col === 'object') state.collection = d.col;
    state.stats = Object.assign({}, defaultStats, d.st || {});
    state.stats.oppWins = Object.assign({}, state.stats.oppWins || {});
    state.daily = Object.assign({ lastClaimDate: null, streak: 0, lastDurakWinDate: null }, d.dy || {});
    state.missions = (d.mi && d.mi.list) ? d.mi : { date: null, list: [] };
    if (d.ac && typeof d.ac === 'object') state.achievements = d.ac;
    state.pity = Object.assign({ packsSinceEpic: 0 }, d.pi || {});
    if (Array.isArray(d.dk)) state.deck = d.dk.filter(id => state.cards.some(c => c.id === id));
    if (Array.isArray(d.hi)) state.history = d.hi.slice(0, 30);
    state.albumBonus = (d.ab && typeof d.ab === 'object') ? d.ab : {};
    state.packStats = (d.ps && typeof d.ps === 'object') ? d.ps : {};   // b277
    state.windowBuys = (d.wb && typeof d.wb === 'object') ? d.wb : {};  // b277
    if (d.nm) {
        try { LS.setItem(PLAYER_NAME_KEY, d.nm); } catch (e) {}
        const inp = document.getElementById('player-name-input'); if (inp) inp.value = d.nm;
        try { nameNeedUI(); nameRemindClose(); } catch (e) {} // b287: имя привезено по QR — напоминание не нужно
    }
    state.currentAlbumPackId = null;
    saveState();
    updateCoinDisplay();
    checkAlbumRewards();
    ensureDailyMissions();
    updateDailyDot();
    jpSyncSoon(); // b277: пусть реестр сайта сразу увидит новый баланс устройства
    switchTab('store');
    checkAchievements();
    showToast('Прогресс принят! Баланс и коллекция теперь такие же, как на устройстве-отправителе', 'success');
}
function nxInjectExtras(out, extras) {
        // b340: кэшированные арты, которых нет в карте имён, дописываются в неё —
        // тогда ЛЮБАЯ ссылка с этим именем файла (даже приходящая из облака) получит вшитый арт
        try {
            const marker = 'const NX_EMBED_MEDIA = {';
            const i = out.indexOf(marker);
            if (i < 0 || !extras || !extras.length) return out;
            const j = out.indexOf('};', i);
            if (j < 0) return out;
            const mapSlice = out.slice(i, j);
            let add = '';
            extras.forEach(x => {
                const b = x[0], d = x[1];
                if (!b || !d || mapSlice.indexOf('"' + b + '":') >= 0) return;
                add += '"' + b.replace(/"/g, '') + '":"' + d + '",';
            });
            if (!add) return out;
            return out.slice(0, i + marker.length) + add + out.slice(i + marker.length);
        } catch (e) { return out; }
    }
// ---- b330: «Вшить в сайт»: коммит собранного файла прямо в репозиторий GitHub ----
function nxGhToken() { try { return String(LS.getItem('nx_gh_token') || '').trim(); } catch (e) { return ''; } }
/*PATCH-b342-solo*/
function nxStatus(msg, kind) { // b342-solo: видимая статус-строка вместо тишины
    try {
        var b = document.getElementById('nx-status-bar');
        if (!b) {
            var anchor = document.getElementById('nx-autoembed-btn') || document.getElementById('nx-gh-token');
            if (!anchor || !anchor.parentNode) return;
            b = document.createElement('div'); b.id = 'nx-status-bar';
            b.setAttribute('style', 'display:none;margin-top:6px;padding:6px 10px;border-radius:8px;background:#0b1220;border:1px solid #334155;color:#cbd5e1;font-size:11px;font-family:ui-monospace,monospace;white-space:pre-wrap;word-break:break-word');
            anchor.parentNode.insertBefore(b, anchor.nextSibling);
        }
        if (!msg) { b.style.display = 'none'; b.textContent = ''; return; }
        b.style.display = 'block';
        b.style.borderColor = kind === 'err' ? '#7f1d1d' : (kind === 'ok' ? '#14532d' : '#334155');
        b.style.color = kind === 'err' ? '#fca5a5' : (kind === 'ok' ? '#86efac' : '#cbd5e1');
        b.textContent = msg;
        try { console.log('[status] ' + msg); } catch (e) {}
    } catch (e) {}
}
function nxSayOnce(key, msg) { // одна запись в журнал на причину, без спама
    try {
        var k = 'nx_said_' + key;
        if (LS.getItem(k)) return;
        LS.setItem(k, String(Date.now()));
        nxCrashLog(msg);
    } catch (e) {}
}

function nxProgress(pct, label, kind) { // b342-solo: видимая ШКАЛА прогресса
    try {
        var wrap = document.getElementById('nx-progress-wrap');
        if (!wrap) {
            var row = null;
            var a = document.getElementById('nx-autoembed-btn') || document.getElementById('nx-embed-all');
            if (a && a.parentNode && a.parentNode.parentNode) row = a.parentNode;
            if (!row) return;
            wrap = document.createElement('div');
            wrap.id = 'nx-progress-wrap';
            wrap.setAttribute('style', 'width:100%;margin-top:8px;padding:8px 10px;border-radius:8px;background:#0b1220;border:1px solid #334155;font-size:11px;color:#cbd5e1;font-family:ui-monospace,monospace');
            wrap.innerHTML = '<div id="nx-progress-label" style="margin-bottom:5px;white-space:pre-wrap;word-break:break-word"></div>' +
                '<div style="height:7px;background:#1e293b;border-radius:5px;overflow:hidden">' +
                '<div id="nx-progress-bar" style="height:100%;width:0%;background:linear-gradient(90deg,#a21caf,#6366f1,#22c55e);transition:width .35s ease;border-radius:5px"></div></div>';
            if (row.parentNode) row.parentNode.insertBefore(wrap, row.nextSibling);
        }
        try { wrap.style.display = 'block'; } catch (e) {}
        var bar = document.getElementById('nx-progress-bar');
        var lab = document.getElementById('nx-progress-label');
        if (lab && label != null) lab.textContent = label;
        if (bar) {
            bar.style.width = Math.max(0, Math.min(100, Math.round((pct || 0) * 100))) + '%';
            bar.style.background = kind === 'err' ? '#ef4444' : (kind === 'ok' ? '#22c55e' : 'linear-gradient(90deg,#a21caf,#6366f1,#22c55e)');
        }
        if (label) { try { console.log('[progress ' + Math.round((pct || 0) * 100) + '%] ' + label); } catch (e) {} }
    } catch (e) {}
}
function nxUpdateCounts() { // b342-solo: сколько артов где лежит
    try {
        var mapN = 0;
        try { mapN = Object.keys(NX_EMBED_MEDIA).length; } catch (e) {}
        var urls = nxAllMediaUrls();
        Promise.all(urls.map(function (u) {
            return imgCacheObjUrl(u).then(function (x) { return x ? 1 : 0; }, function () { return 0; });
        })).then(function (h) {
            var dev = h.reduce(function (a, b) { return a + b; }, 0);
            nxStatus('На этом устройстве в кэше: ' + dev + '/' + urls.length +
                ' • В файле сайта (видно ВСЕМ игрокам): ' + mapN +
                ' • Автовшивание: ' + (nxAutoEmbedOn() ? 'вкл' : 'выкл'), 'ok');
        });
    } catch (e) {}
}

function nxArtOwners() { // b342-solo: кто ссылается на арты: паки и карточки (стандарт + ваши)
    var packs = [], cards = [];
    try { packs = packs.concat(typeof defaultPacks !== 'undefined' ? defaultPacks : []); } catch (e) {}
    try { cards = cards.concat(typeof defaultCards !== 'undefined' ? defaultCards : []); } catch (e) {}
    try {
        if (typeof state !== 'undefined' && state) {
            packs = packs.concat(state.packs || []);
            cards = cards.concat(state.cards || []);
        }
    } catch (e) {}
    var pt = {};
    packs.forEach(function (p) { try { pt[p.id] = p.title || p.name || p.id; } catch (e) {} });
    var seen = {}, out = [];
    packs.forEach(function (p) {
        var u = String(p && p.image || '').trim();
        if (!u) return;
        var k = 'p|' + u;
        if (seen[k]) return; seen[k] = 1;
        out.push({ kind: 'pack', name: p.title || p.name || p.id, pack: '', url: u });
    });
    cards.forEach(function (c) {
        var u = String(c && c.image || '').trim();
        if (!u) return;
        var k = 'c|' + u;
        if (seen[k]) return; seen[k] = 1;
        out.push({ kind: 'card', name: c.name || c.id, pack: pt[c.packId] || '', url: u });
    });
    return out;
}
function nxCheckLinks(silent) { // b342-solo: мёртвая ссылка + нет кэша -> сказать, ГДЕ именно
    try {
        var items = nxArtOwners();
        var total = items.length;
        if (!total) return;
        var problems = [], doneN = 0;
        // если у того же имени уже есть рабочая картинка (вшита или в кэше) —
        // дубль с мёртвой ссылкой не считаем ошибкой: пользователь видит картинку
        var good = {};
        items.forEach(function (it) {
            var e = it.url;
            try { e = mediaUrl(it.url); } catch (e2) {}
            if (String(e).indexOf('data:') === 0) { good[it.name] = 1; return; }
            try { if (NX_EMBED_MEDIA[nxMediaKey(e)]) good[it.name] = 1; } catch (e2) {}
        });
        nxProgress(0, 'Проверяю ссылки карточек и паков: 0/' + total);
        var fin = function () {
            doneN++;
            if (doneN % 4 === 0 || doneN === total) nxProgress(doneN / total, 'Проверяю ссылки карточек и паков: ' + doneN + '/' + total);
            if (doneN < total) return;
            if (!problems.length) {
                nxProgress(1, 'Ссылки: все ' + total + ' паков/карточек — картинки рабочие или в кэше', 'ok');
                if (!silent) { try { nxOwnerToast('Ссылки на картинки: всё в порядке (' + total + ')', 'success'); } catch (e) {} }
                return;
            }
            var msg = 'Нет картинок (' + problems.length + '): ' + problems.slice(0, 6).join('; ') + (problems.length > 6 ? '… и ещё ' + (problems.length - 6) : '');
            nxProgress(1, msg, 'err');
            try { nxCrashLog('check-links: ' + msg); } catch (e) {}
            if (!silent) { try { showToast(msg, 'error'); } catch (e) {} }
            else { nxSayOnce('links_bad_' + problems.length, msg); }
            nxStatus(msg + '  →  замените ссылку или добавьте арт в кэш («Скачать все арты»)', 'err');
        };
        items.forEach(function (it) {
            var eff = it.url;
            try { eff = mediaUrl(it.url); } catch (e) {}
            var where = it.kind === 'pack'
                ? 'пак «' + it.name + '»'
                : 'карточка «' + it.name + '»' + (it.pack ? ' из пака «' + it.pack + '»' : '');
            if (String(eff).indexOf('data:') === 0) { // вшито в файл: проверяем читаемость
                var im = new Image();
                im.onload = function () { fin(); };
                im.onerror = function () { if (!good[it.name]) problems.push(where + ': вшитая картинка битая'); fin(); };
                im.src = eff;
                return;
            }
            imgCacheObjUrl(eff).then(function (ou) {
                if (ou) { fin(); return; } // есть в кэше устройства — покажем из кэша
                // кэша нет: жива ли ссылка (таймаут 12 сек на «молча мертвый» хост)
                var done = false;
                var t = setTimeout(function () {
                    if (done) return; done = true;
                    if (!good[it.name]) problems.push(where + ': нет кэша, ссылка молчит');
                    fin();
                }, 12000);
                var im2 = new Image();
                im2.onload = function () { if (done) return; done = true; clearTimeout(t); fin(); };
                im2.onerror = function () {
                    if (done) return; done = true; clearTimeout(t);
                    if (!good[it.name]) problems.push(where + ': ссылка не работает и нет кэша');
                    fin();
                };
                im2.src = eff;
            }, function () { fin(); });
        });
    } catch (e) {}
}

function nxCheckArts(silent) { // b342-solo: проверить, что все картинки реально читаются
    try {
        var keys = [];
        try { keys = Object.keys(NX_EMBED_MEDIA); } catch (e) {}
        var total = keys.length, ok = 0, bad = [], doneN = 0;
        if (!total) { nxProgress(1, 'В файле нет встроенных картинок', 'err'); return; }
        nxProgress(0, 'Проверяю картинки: 0/' + total);
        var fin = function () {
            doneN++;
            nxProgress(doneN / total, 'Проверяю картинки: ' + doneN + '/' + total);
            if (doneN < total) return;
            var msg = 'Картинки: ' + ok + '/' + total + ' читаются' +
                (bad.length ? '; битых: ' + bad.length + ' (' + bad.slice(0, 3).join(', ') + ')' : ' — все целы');
            nxProgress(1, msg, bad.length ? 'err' : 'ok');
            try { nxCrashLog('check-arts: ' + msg); } catch (e) {}
            if (!silent) { try { showToast(msg, bad.length ? 'error' : 'success'); } catch (e) {} }
            nxUpdateCounts();
            try { nxCheckLinks(silent); } catch (e) {}
        };
        keys.forEach(function (k) {
            var im = new Image();
            im.onload = function () { ok++; fin(); };
            im.onerror = function () { bad.push(k); fin(); };
            im.src = NX_EMBED_MEDIA[k];
        });
    } catch (e) {}
}
function nxBuildProgressUI() { // кнопка «Проверить картинки» рядом с остальными
    try {
        var a = document.getElementById('nx-autoembed-btn');
        if (!a || !a.parentNode || document.getElementById('nx-check-arts-btn')) return;
        var b = document.createElement('button');
        b.type = 'button';
        b.id = 'nx-check-arts-btn';
        b.className = a.className;
        b.innerHTML = '<i class="fa-solid fa-images mr-1"></i>Проверить картинки';
        b.title = 'Проверить, что все встроенные картинки читаются, и показать, сколько артов в кэше устройства и в файле сайта';
        b.onclick = function () { nxCheckArts(false); };
        a.parentNode.insertBefore(b, a.nextSibling);
    } catch (e) {}
}

function nxAutoEmbedOn() { // b342: эта функция была ПОТЕРЯНА — из-за неё автовшивание молча не работало
    try { return LS.getItem('nx_autoembed') === '1'; } catch (e) { return false; }
}
function nxSrcGet() { // b342: исходник без повторной загрузки всех мегабайт на каждый пуш
    var C = window.__nxSrcCache || (window.__nxSrcCache = { text: '', etag: '', lm: '', ts: 0 });
    var TTL = 15 * 60 * 1000;
    var h = {};
    if (C.etag) h['If-None-Match'] = C.etag;
    if (C.lm) h['If-Modified-Since'] = C.lm;
    return fetch(location.href, { cache: 'no-store', headers: h }).then(function (r) {
        if (r.status === 304 && C.text) { C.ts = Date.now(); return C.text; }
        if (!r.ok) throw new Error('исходник HTTP ' + r.status);
        C.etag = r.headers.get('ETag') || ''; C.lm = r.headers.get('Last-Modified') || '';
        return r.text().then(function (t) { C.text = t; C.ts = Date.now(); return t; });
    }).catch(function (e) {
        if (C.text && Date.now() - C.ts < TTL) { try { nxCrashLog('автовшивание: исходник из кэша вкладки (сеть недоступна)'); } catch (e2) {} return C.text; }
        throw e;
    });
}

function nxSaveGhToken() {
    const i = document.getElementById('nx-gh-token');
    const r = document.getElementById('nx-gh-repo');
    try { LS.setItem('nx_gh_token', i ? i.value.trim() : ''); if (r) LS.setItem('nx_gh_repo', r.value.trim()); } catch (e) {}
    try { showToast(nxGhToken() ? 'Токен сохранён (только на этом устройстве)' : 'Токен удалён', 'success'); } catch (e) {}
}
function nxGhApi(path, opts) {
    const o = Object.assign({ headers: {} }, opts || {});
    o.headers['Accept'] = 'application/vnd.github+json';
    const t = nxGhToken(); if (t) o.headers['Authorization'] = 'Bearer ' + t;
    return fetch('https://api.github.com' + path, o).then(r => {
        if (!r.ok) return r.text().then(t2 => {
            let m = 'HTTP ' + r.status + ' ' + String(t2).slice(0, 140);
            if (r.status === 403 && /not accessible by personal access token/i.test(t2)) m = 'у токена нет права ЗАПИСИ в репозиторий: classic-токен — отметьте public_repo; fine-grained — Permissions → Contents → Read and write';
            else if (r.status === 401) m = 'GitHub не принял токен (401): проверьте, что вставили актуальный токен';
            else if (r.status === 404) m = 'репозиторий не найден (404): проверьте поле «владелец/имя» и что токен имеет доступ к этому репо';
            throw new Error(m);
        });
        return r.json();
    });
}
function nxBytesToB64(u8) { // b359: base64 через массив кусков и один join.
    // Было: bin += String.fromCharCode(...) в цикле — на файле в несколько МБ это
    // квадратичная склейка строк (сотни МБ мусора и блокировка главного потока).
    const CH = 0x8000, parts = [];
    for (let i = 0; i < u8.length; i += CH) parts.push(String.fromCharCode.apply(null, u8.subarray(i, i + CH)));
    return btoa(parts.join(''));
}
function nxB64(str) { // base64 для огромных строк — кусками, без переполнения стека
    return nxBytesToB64(new TextEncoder().encode(str));
}
function nxGitShaOf(str) { // b361: git-sha содержимого (blob), считается на устройстве
    try {
        const bytes = new TextEncoder().encode(str);
        const head = new TextEncoder().encode('blob ' + bytes.length + '\0');
        const all = new Uint8Array(head.length + bytes.length);
        all.set(head, 0); all.set(bytes, head.length);
        return crypto.subtle.digest('SHA-1', all).then(b => Array.from(new Uint8Array(b)).map(x => x.toString(16).padStart(2, '0')).join(''));
    } catch (e) { return Promise.resolve(''); }
}
function nxGhFileSha(repo, path) { // b361: sha файла в ветке по умолчанию
    return nxGhApi('/repos/' + repo + '/contents/' + path, { headers: { 'Accept': 'application/vnd.github+json' } })
        .then(d => (d && d.sha) || '').catch(() => '');
}
function nxGhPush(repo, content, ok, fail) {
    // b332: если ветка уехала вперёд (422 not a fast forward) — перечитываем head
    // и пересоздаём коммит поверх нового; до 3 попыток
    let blobSha = null;
    const attempt = n => {
        nxGhApi('/repos/' + repo).then(info => {
            const branch = info.default_branch || 'main';
            return nxGhApi('/repos/' + repo + '/git/ref/heads/' + branch).then(ref => {
                const head = ref.object.sha;
                return nxGhApi('/repos/' + repo + '/git/commits/' + head).then(cm => {
                    const blobP = blobSha
                        ? Promise.resolve({ sha: blobSha })
                        : nxGhApi('/repos/' + repo + '/git/blobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: nxB64(content), encoding: 'base64' }) }).then(bl => { blobSha = bl.sha; return bl; });
                    return blobP.then(bl =>
                        nxGhApi('/repos/' + repo + '/git/trees', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ base_tree: cm.tree.sha, tree: [{ path: 'index.html', mode: '100644', type: 'blob', sha: bl.sha }] }) }).then(tr =>
                            nxGhApi('/repos/' + repo + '/git/commits', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: 'авто: вшитые арты из игры (b330)', parents: [head], tree: tr.sha }) }).then(nc =>
                                nxGhApi('/repos/' + repo + '/git/refs/heads/' + branch, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sha: nc.sha }) })
                            )
                        )
                    );
                });
            });
        }).then(() => ok()).catch(e => {
            if (n < 3 && /not a fast forward/i.test(String(e && e.message))) { setTimeout(() => attempt(n + 1), 1500); return; }
            fail(String((e && e.message) || e));
        });
    };
    attempt(1);
}
function nxPushEmbedded(auto) {
    if (!nxGhToken()) {
        try { nxOwnerToast('Сначала сохраните токен GitHub в этой строке настроек — без него игра не может закоммитить в репозиторий', 'error'); } catch (e) {}
        const i = document.getElementById('nx-gh-token'); if (i) { i.focus(); i.scrollIntoView({ block: 'center' }); }
        return;
    }
    const repo = ((document.getElementById('nx-gh-repo') || {}).value || '').trim() || (LS.getItem('nx_gh_repo') || '').trim() || 'd3nizkeller/card-collection';
    const btn = document.getElementById('nx-push-embed'); if (btn) btn.disabled = true;
    nxStatus('Собираю файл для вшивания…');
    const say = m => { try { nxOwnerToast(m, 'success'); } catch (e) {} };
    const err = m => { if (btn) btn.disabled = false; try { showToast(m, 'error'); } catch (e) {} nxStatus(m, 'err'); };
    nxSrcGet().then(src => { // b342-solo: было fetch(location.href,{cache:'no-store'}) — перезакачка всего файла каждый раз
        nxProgress(0.15, 'Читаю исходник и список артов…');
        const pairs = [];
        nxAllMediaUrls().forEach(raw => { let eff = raw; try { eff = mediaUrl(raw); } catch (e) {} pairs.push({ raw: raw, eff: eff }); });
        // b360: вшивание ВСЕЙ коллекции делает из index.html строку в сотни мегабайт
        // (замер: только 8 артов = 9.7 МБ строки, на 82 арта было бы ~190 МБ), а потом
        // тащит её одним запросом в GitHub. На телефоне это гарантированная смерть
        // вкладки, поэтому считаем объём заранее и не начинаем, если он безумный.
        const MAX_EMBED_MB = 40;
        imgCacheSizeOf(pairs.map(p => p.eff)).then(mb => {
            if (mb > MAX_EMBED_MB) {
                err('Вшивать так много нельзя: арты в кэше занимают ' + mb.toFixed(0) + ' МБ — index.html вырос бы до ~' + Math.round(mb * 1.37) + ' МБ, и вкладка упадёт ещё на сборке (лимит ' + MAX_EMBED_MB + ' МБ). Используйте «Отправить в media/» — картинки уйдут файлами, а сайт останется лёгким.');
                return;
            }
            nxEmbedRun(repo, src, pairs, auto, btn, say, err);
        }).catch(() => nxEmbedRun(repo, src, pairs, auto, btn, say, err));
    }).catch(e => err('Не удалось собрать файл: ' + e.message));
}
function imgCacheSizeOf(urls) { // b360: суммарный вес артов в кэше — БЕЗ загрузки их в память
    return new Promise(function (res) {
        var total = 0, i = 0;
        var step = function () {
            if (i >= urls.length) { res(total / 1048576); return; }
            var u = urls[i++];
            imgCacheGetBlob(u).then(function (b) { if (b && b.size) total += b.size; step(); }, function () { step(); });
        };
        step();
    });
}
function nxEmbedRun(repo, src, pairs, auto, btn, say, err) {
    {
        let out = src, pending = pairs.length, replaced = 0; const extras = []; // b340
        const finalize = () => { nxProgress(0.65, 'Собираю файл с артами…'); out = nxInjectExtras(out, extras); // b340
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
        };
        const apply = (raw, dataUrl) => { if (dataUrl) { if (out.indexOf(raw) >= 0) { out = out.split(raw).join(dataUrl); replaced++; } try { const bb = nxMediaKey(raw); if (bb) extras.push([bb, dataUrl]); } catch (e) {} } if (pending > 0) nxProgress(0.15 + 0.45 * (1 - pending / Math.max(1, pairs.length)), 'Достаю арты из кэша устройства: ' + (pairs.length - pending) + '/' + pairs.length); if (--pending === 0) finalize(); };
        if (!pending) { finalize(); return; }
        pairs.forEach(p => {
            imgCacheGetBlob(p.eff).then(blob => {
                if (!blob || !blob.size) return apply(p.raw, null);
                const fr = new FileReader();
                fr.onload = () => apply(p.raw, String(fr.result));
                fr.onerror = () => apply(p.raw, null);
                fr.readAsDataURL(blob);
            }, () => apply(p.raw, null));
        });
    }
}
try {
    const gi = document.getElementById('nx-gh-token'); if (gi) gi.value = nxGhToken();
    const gr = document.getElementById('nx-gh-repo'); if (gr) gr.value = LS.getItem('nx_gh_repo') || '';
} catch (e) {}
// ---- b354: системные уведомления (загрузки, автоотправка, лечение) видны ТОЛЬКО в студии ----
function nxInStudio() {
    try {
        var s = document.getElementById('tab-studio');
        return !!s && !s.classList.contains('hidden') && s.offsetParent !== null;
    } catch (e) { return false; }
}
function nxOwnerToast(msg, kind) {
    try { if (nxInStudio()) showToast(msg, kind); } catch (e) {}
}
// ---- b343-media: АВТООТПРАВКА картинок в папку media/ репозитория ----
function nxMediaFolder() { // папка media/ рядом с index.html на GitHub Pages
    try { return String(location.pathname || '/').replace(/[^/]*$/, '') + 'media/'; } catch (e) { return 'media/'; }
}
function nxAutoMediaOn() {
    try {
        if (LS.getItem('nx_automedia') == null) return !!nxGhToken(); // токен уже есть -> авто включено по умолчанию
        return LS.getItem('nx_automedia') === '1';
    } catch (e) { return false; }
}
function nxAutoMediaLabel() {
    var b = document.getElementById('nx-automedia-btn'); if (!b) return;
    var on = nxAutoMediaOn();
    b.innerHTML = '<i class="fa-solid fa-robot mr-1"></i>Автоотправка на GitHub: ' + (on ? 'ВКЛ' : 'выкл');
    try { b.style.borderColor = on ? '#047857' : '#475569'; b.style.background = on ? 'rgba(4,120,87,.35)' : ''; } catch (e) {}
}
function nxToggleAutoMedia() {
    try { LS.setItem('nx_automedia', nxAutoMediaOn() ? '0' : '1'); } catch (e) {}
    nxAutoMediaLabel();
    try { nxOwnerToast(nxAutoMediaOn() ? 'Автоотправка ВКЛ: новые картинки сами уйдут в media/ репозитория' : 'Автоотправка выключена', 'success'); } catch (e) {}
    if (nxAutoMediaOn()) nxMaybeAutoMediaPush(true);
}
var NX_MEDIA_PUSHED = null, NX_MEDIA_PUSHING = false, NX_MEDIA_LAST = 0, NX_MEDIA_TIMER = 0;
function nxMediaPushedSet() {
    if (NX_MEDIA_PUSHED) return NX_MEDIA_PUSHED;
    try { NX_MEDIA_PUSHED = new Set(JSON.parse(LS.getItem('nx_gh_media_pushed') || '[]')); } catch (e) { NX_MEDIA_PUSHED = new Set(); }
    return NX_MEDIA_PUSHED;
}
function nxMediaSavePushed(set) { try { LS.setItem('nx_gh_media_pushed', JSON.stringify(Array.from(set).slice(-400))); } catch (e) {} }
function nxNoteCachedMedia(url) { // хук из кэша: пришла новая картинка
    try {
        if (!url || String(url).indexOf('http') !== 0) return;
        var n = nxMediaKey(url); if (!n || NX_EMBED_MEDIA[n]) return;
        if (nxMediaPushedSet().has(n)) return;
        nxMaybeAutoMediaPush(false);
    } catch (e) {}
}
function nxGhRepoName() {
    return ((document.getElementById('nx-gh-repo') || {}).value || '').trim() ||
        (function () { try { return String(LS.getItem('nx_gh_repo') || '').trim(); } catch (e) { return ''; } })() ||
        'd3nizkeller/card-collection';
}
function nxPendingMediaList() { // b359: только СПИСОК (имя + ссылка), ничего не грузим в память
    var set = nxMediaPushedSet(), pairs = [];
    try {
        nxAllMediaUrls().forEach(function (raw) {
            var eff = raw; try { eff = mediaUrl(raw); } catch (e) {}
            if (String(eff).indexOf('http') !== 0) return;
            var n = nxMediaKey(eff); if (!n || NX_EMBED_MEDIA[n] || set.has(n)) return;
            if (pairs.some(function (p) { return p.name === n; })) return;
            pairs.push({ name: n, url: eff });
        });
    } catch (e) {}
    return pairs;
}
function nxCollectPendingMedia(limit) { // какие картинки лежат в кэше, но ещё не отправлены
    // b359: раньше сюда брали ВСЕ блобы сразу (замер: 82 арта = 156 МБ в памяти
    // вкладки, и это в момент, когда игрок ещё и 3D крутит) — мобильный браузер
    // просто убивал страницу. Теперь берём не больше limit штук за подход.
    var pairs = nxPendingMediaList();
    if (limit) pairs = pairs.slice(0, limit);
    var out = [], i = 0;
    return new Promise(function (res) {
        var step = function () {
            if (i >= pairs.length) { res(out); return; }
            var p = pairs[i++];
            try {
                imgCacheGetBlob(p.url).then(function (b) { if (b && b.size) out.push({ name: p.name, blob: b, url: p.url }); step(); }, function () { step(); });
            } catch (e) { step(); }
        };
        step();
    });
}
function nxPushCap(manual) { // b359: сколько файлов отправляем за один подход
    try { if (typeof nxLowRam === 'function' && nxLowRam()) return manual ? 8 : 3; } catch (e) {}
    return manual ? 20 : 6;
}
function nxYield() { // b359: отдаём главный поток браузеру между файлами — игра не подвисает
    return new Promise(function (res) { setTimeout(res, 0); });
}
function nxMaybeAutoMediaPush(force) { // дебаунс + троттлинг: не чаще раза в 10 минут
    try {
        if (!nxAutoMediaOn() || !nxGhToken() || !navigator.onLine || NX_MEDIA_PUSHING) return;
        if (!force && document.hidden) return; // браузер глушит фоновую работу
        if (!force && Date.now() - NX_MEDIA_LAST < 10 * 60 * 1000) return;
        if (NX_MEDIA_TIMER) return;
        NX_MEDIA_TIMER = setTimeout(function () { NX_MEDIA_TIMER = 0; nxAutoMediaPushRun(false); }, force ? 4000 : 90000);
    } catch (e) {}
}
function nxGhPushMedia(repo, items, ok, fail) { // один коммит: все новые файлы в media/
    // b359: файлы кодируются и уходят ПО ОДНОМУ. Раньше blobOf() вызывался для
    // каждого файла внутри общей цепочки, а все блобы лежали в памяти до конца
    // коммита: 82 арта = 156 МБ + base64 поверх них. Теперь в памяти живёт один файл.
    function blobOf(it) {
        return (it.blob
            ? Promise.resolve(it.blob)
            : imgCacheGetBlob(it.url).then(function (b) { if (!b || !b.size) throw new Error('нет в кэше: ' + it.name); return b; })
        ).then(function (b) {
            return b.arrayBuffer().then(function (ab) { return nxBytesToB64(new Uint8Array(ab)); });
        }).then(function (b64) {
            return nxGhApi('/repos/' + repo + '/git/blobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: b64, encoding: 'base64' }) }).then(function (bl) { return bl.sha; });
        });
    }
    var attempt = function (n) {
        nxGhApi('/repos/' + repo).then(function (info) {
            var branch = info.default_branch || 'main';
            return nxGhApi('/repos/' + repo + '/git/ref/heads/' + branch).then(function (ref) {
                var head = ref.object.sha;
                return nxGhApi('/repos/' + repo + '/git/commits/' + head).then(function (cm) {
                    var chain = Promise.resolve([]), doneCnt = 0;
                    items.forEach(function (it) {
                        chain = chain.then(function (acc) {
                            return blobOf(it).then(function (sh) {
                                acc.push({ path: 'media/' + it.name, mode: '100644', type: 'blob', sha: sh });
                                it.blob = null; // b359: файл отправлен — блоб больше не держим
                                doneCnt++;
                                try { nxProgress(0.15 + 0.7 * (doneCnt / items.length), 'Отправляю ' + doneCnt + '/' + items.length + ': ' + it.name); } catch (e) {}
                                return nxYield();
                            }).then(function () { return acc; });
                        });
                    });
                    return chain.then(function (entries) {
                        return nxGhApi('/repos/' + repo + '/git/trees', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ base_tree: cm.tree.sha, tree: entries }) }).then(function (tr) {
                            return nxGhApi('/repos/' + repo + '/git/commits', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: 'авто: картинки из кэша игры -> media/ (' + entries.length + ')', parents: [head], tree: tr.sha }) }).then(function (nc) {
                                return nxGhApi('/repos/' + repo + '/git/refs/heads/' + branch, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sha: nc.sha }) });
                            });
                        });
                    });
                });
            });
        }).then(function () { ok(); }).catch(function (e) {
            if (n < 3 && /not a fast forward/i.test(String(e && e.message))) { setTimeout(function () { attempt(n + 1); }, 1500); return; }
            fail(String((e && e.message) || e));
        });
    };
    attempt(1);
}
function nxAutoMediaPushRun(manual, done) {
    // b359: защита от параллельных запусков СТАВИТСЯ СРАЗУ. Раньше NX_MEDIA_PUSHING
    // включался только после сбора картинок, поэтому несколько триггеров подряд
    // (каждый новый арт в кэше зовёт nxMaybeAutoMediaPush) запускали по 2-3 сбора
    // одновременно — память удваивалась ровно в момент игры.
    if (NX_MEDIA_PUSHING) { if (done) done(0); return; }
    NX_MEDIA_PUSHING = true;
    var finish = function (sent) {
        NX_MEDIA_PUSHING = false;
        NX_MEDIA_LAST = Date.now(); // b359: троттлинг считаем и после ошибки:
                                    // раньше неудача не обновляла NX_MEDIA_LAST,
                                    // и авто-отправка долбила каждые 5 минут до краша вкладки
        if (done) { try { done(sent || 0); } catch (e) {} }
    };
    if (!nxGhToken()) {
        if (manual) { try { nxOwnerToast('Сначала сохраните токен GitHub в поле ниже — без него сайт не может отправить файлы', 'error'); } catch (e) {} var ti = document.getElementById('nx-gh-token'); if (ti) { ti.focus(); ti.scrollIntoView({ block: 'center' }); } }
        finish(0); return;
    }
    var repo = nxGhRepoName();
    var btn = document.getElementById('nx-push-media-btn'); if (manual && btn) btn.disabled = true;
    var unblock = function () { if (manual && btn) btn.disabled = false; };
    var cap = nxPushCap(manual);
    nxStatus((manual ? '' : 'Автоотправка: ') + 'смотрю, какие картинки уже в кэше…');
    var pendingAll = [];
    try { pendingAll = nxPendingMediaList(); } catch (e) {}
    nxCollectPendingMedia(cap).then(function (items) {
        if (!items.length) {
            if (manual) { nxStatus('Отправлять нечего: новых картинок в кэше нет. Нажмите «Шаг 1. Скачать все картинки»', 'err'); try { nxOwnerToast('В кэше нет новых картинок для отправки', 'error'); } catch (e) {} }
            else nxStatus('');
            unblock(); finish(0); return;
        }
        var rest = Math.max(0, pendingAll.length - items.length);
        nxProgress(0.15, 'Отправляю ' + items.length + ' картинок в media/ репозитория' + (rest ? ' (осталось в очереди: ' + rest + ')' : '') + '…');
        nxGhPushMedia(repo, items, function () {
            var s = nxMediaPushedSet(); items.forEach(function (it) { s.add(it.name); }); nxMediaSavePushed(s);
            nxProgress(1, 'Готово: ' + items.length + ' картинок ушло в media/' + (rest ? ', в очереди ещё ' + rest : '') + '. GitHub Pages обновится за 1–2 минуты', 'ok');
            nxStatus('Отправлено в ' + repo + '/media/: ' + items.map(function (x) { return x.name; }).join(', '), 'ok');
            try { nxOwnerToast('Картинки отправлены на GitHub (' + items.length + ' шт. в media/)' + (rest ? ' — остальные дойдут следующими заходами' : ''), 'success'); } catch (e) {}
            unblock(); finish(items.length);
            // b359: остаток очереди — следующим заходом, не сейчас (память и канал)
            if (rest > 0) { try { nxMaybeAutoMediaPush(false); } catch (e) {} }
        }, function (msg) {
            nxProgress(0, ''); nxStatus('Ошибка отправки на GitHub: ' + msg, 'err');
            if (manual) { try { nxOwnerToast('Ошибка отправки: ' + msg, 'error'); } catch (e) {} }
            unblock(); finish(0);
        });
    }, function () { unblock(); finish(0); });
}
function nxPushMediaNow() { nxAutoMediaPushRun(true); }
// ---- b344: прямая загрузка файла с устройства в media/ репозитория ----
function nxPickFileFor(inputId, kind) {
    var audio = kind === 'audio';
    var inp = document.createElement('input');
    inp.type = 'file'; inp.accept = audio ? 'audio/*' : 'image/*';
    inp.onchange = function () { var f = inp.files && inp.files[0]; if (f) nxUploadToGithub(f, inputId, kind); };
    inp.click();
}
function nxUploadToGithub(file, inputId, kind) {
    if (!nxGhToken()) {
        try { nxOwnerToast('Сначала сохраните токен GitHub в блоке «Картинки сайта → GitHub» (Шаг 3 / автоотправка)', 'error'); } catch (e) {}
        var t = document.getElementById('nx-gh-token'); if (t) { t.focus(); t.scrollIntoView({ block: 'center' }); }
        return;
    }
    var repo = nxGhRepoName();
    var audio = kind === 'audio';
    var ext = audio
        ? (file.type === 'audio/ogg' ? '.ogg' : file.type === 'audio/wav' || file.type === 'audio/x-wav' ? '.wav' : file.type === 'audio/aac' ? '.aac' : file.type === 'audio/mp4' || file.type === 'audio/x-m4a' ? '.m4a' : '.mp3')
        : (file.type === 'image/png' ? '.png' : file.type === 'image/webp' ? '.webp' : file.type === 'image/gif' ? '.gif' : '.jpg');
    var base = String(file.name || '').replace(/\.[a-z0-9]+$/i, '').replace(/[^\wа-яё-]+/gi, '_').replace(/^_+|_+$/g, '').slice(0, 40) || 'art';
    var name = (audio ? 'track_' : 'card_') + Date.now().toString(36) + '_' + base + ext;
    var lamp = document.getElementById(inputId + '-upl');
    if (lamp) lamp.textContent = 'Заливаю ' + name + '…';
    nxStatus('Заливаю ' + (audio ? 'трек' : 'картинку') + ' в ' + repo + '/media/…');
    nxProgress(0.3, 'Загрузка ' + (audio ? 'трека ' : 'картинки ') + file.name + ' → media/' + name);
    nxGhPushMedia(repo, [{ name: name, blob: file }], function () {
        var url = 'media/' + name;
        try { if (location.protocol === 'http:' || location.protocol === 'https:') url = location.href.replace(/[^/]*$/, '') + url; } catch (e) {}
        var field = document.getElementById(inputId);
        if (field) { field.value = url; try { field.dispatchEvent(new Event('input')); } catch (e) {} }
        try { NX_EMBED_MEDIA[name] = 'media/' + name; } catch (e) {}
        var s = nxMediaPushedSet(); s.add(name); nxMediaSavePushed(s);
        nxProgress(1, 'Готово: media/' + name + ' в репозитории. Pages обновится за 1–2 минуты', 'ok');
        nxStatus((audio ? 'Трек загружен' : 'Картинка загружена') + ': media/' + name, 'ok');
        if (lamp) lamp.textContent = '✓ media/' + name;
        try { nxOwnerToast((audio ? 'Трек загружен' : 'Картинка загружена') + ' на GitHub: media/' + name, 'success'); } catch (e) {}
    }, function (msg) {
        nxProgress(0, ''); nxStatus('Ошибка загрузки: ' + msg, 'err');
        if (lamp) lamp.textContent = 'ошибка загрузки';
        try { nxOwnerToast('Ошибка загрузки на GitHub: ' + msg, 'error'); } catch (e) {}
    });
}

// ---- b352: авто-лечение ссылок — всё, что лежит в media/, ссылается на GitHub, а не на мёртвые хосты ----
function nxMediaPublicUrl(name) {
    var rel = 'media/' + name;
    try { if (location.protocol === 'http:' || location.protocol === 'https:') return location.href.replace(/[^/]*$/, '') + rel; } catch (e) {}
    return rel;
}
function nxHealMediaLinks() {
    var fixed = 0;
    var has = function (n) { try { return !!NX_EMBED_MEDIA[n] || nxMediaPushedSet().has(n); } catch (e) { return false; } };
    var heal = function (o) {
        try {
            if (!o || typeof o.image !== 'string' || !o.image) return;
            var s = o.image;
            if (s.indexOf('http') !== 0 && s.indexOf('media/') !== 0) return;
            var n = nxMediaKey(s); if (!n || !has(n)) return;
            var want = nxMediaPublicUrl(n);
            if (s !== want) { o.image = want; o.updatedAt = Date.now(); fixed++; } // свежая дата — слияние комнаты примет лечащую версию
        } catch (e) {}
    };
    try {
        if (typeof state !== 'undefined' && state) { (state.packs || []).forEach(heal); (state.cards || []).forEach(heal); }
    } catch (e) {}
    return fixed;
}
function nxHealAndSave() {
    try {
        if (nxHealMediaLinks()) {
            try { saveState(); } catch (e) {}
            try { cloudPublishSoon(); } catch (e) {} // исправленные ссылки уезжают в комнату, чтобы облако тоже вылечилось
            try { nxOwnerToast('Ссылки на картинки исправлены на GitHub media/', 'success'); } catch (e) {}
        }
    } catch (e) {}
}
try {
    setTimeout(nxHealAndSave, 3000);
    setInterval(nxHealAndSave, 60000);
} catch (e) {}
// ---- b351: возврат файлов, удалённых уборкой media/ ----
function nxGhHead(repo) {
    return nxGhApi('/repos/' + repo).then(function (info) {
        var branch = info.default_branch || 'main';
        return nxGhApi('/repos/' + repo + '/git/ref/heads/' + branch).then(function (ref) {
            return nxGhApi('/repos/' + repo + '/git/commits/' + ref.object.sha).then(function (cm) {
                return { branch: branch, head: ref.object.sha, tree: cm.tree.sha };
            });
        });
    });
}
function nxRestoreLastCleanup() {
    if (!nxGhToken()) {
        try { nxOwnerToast('Сначала сохраните токен GitHub в блоке «Картинки сайта → GitHub»', 'error'); } catch (e) {}
        var t = document.getElementById('nx-gh-token'); if (t) { t.focus(); t.scrollIntoView({ block: 'center' }); }
        return;
    }
    var repo = nxGhRepoName();
    nxStatus('Ищу последнюю уборку в истории…');
    nxGhApi('/repos/' + repo + '/commits?per_page=40').then(function (list) {
        var target = null;
        for (var i = 0; i < (list || []).length; i++) {
            if (String(list[i].commit.message).indexOf('авто: уборка лишних media/') === 0) { target = list[i]; break; }
        }
        if (!target) { nxStatus('Уборок в истории не найдено — восстанавливать нечего', 'ok'); return; }
        var parent = target.parents[0].sha;
        return nxGhApi('/repos/' + repo + '/commits/' + target.sha).then(function (det) {
            var deleted = (det.files || []).filter(function (f) { return f.status === 'removed'; });
            if (!deleted.length) { nxStatus('В последней уборке не было удалений', 'ok'); return; }
            return nxGhApi('/repos/' + repo + '/contents/media?ref=' + parent).then(function (oldList) {
                var shaByName = {}; (oldList || []).forEach(function (f) { shaByName[f.name] = f.sha; });
                var entries = [];
                deleted.forEach(function (f) {
                    var name = String(f.filename).replace(/^media\//, '');
                    if (shaByName[name]) entries.push({ path: f.filename, mode: '100644', type: 'blob', sha: shaByName[name] });
                });
                if (!entries.length) { nxStatus('Не нашёл исходники для восстановления', 'err'); return; }
                nxProgress(0.3, 'Восстанавливаю ' + entries.length + ' файлов из истории…');
                return nxGhHead(repo).then(function (h) {
                    return nxGhApi('/repos/' + repo + '/git/trees', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ base_tree: h.tree, tree: entries }) }).then(function (tr) {
                        return nxGhApi('/repos/' + repo + '/git/commits', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: 'авто: возврат удалённых media/ (' + entries.length + ')', parents: [h.head], tree: tr.sha }) }).then(function (nc) {
                            return nxGhApi('/repos/' + repo + '/git/refs/heads/' + h.branch, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sha: nc.sha }) });
                        });
                    });
                }).then(function () {
                    nxProgress(1, 'Готово: ' + entries.length + ' файлов вернулись в media/', 'ok');
                    nxStatus('Восстановлено после уборки: ' + entries.length + ' файлов', 'ok');
                    try { nxOwnerToast('Вернул ' + entries.length + ' файлов в media/! Pages обновится за 1–2 минуты', 'success'); } catch (e) {}
                });
            });
        });
    }).catch(function (e) { nxProgress(0, ''); nxStatus('Ошибка восстановления: ' + e.message, 'err'); });
}
// ---- b350: аудит media/ — лишние файлы удаляются, остаются только рабочие ----
var NX_MEDIA_EXTRA = [];
function nxMediaUsedNames() { // имена файлов, которые сайт реально использует
    var used = {};
    try { Object.keys(NX_EMBED_MEDIA).forEach(function (k) { used[k] = 1; }); } catch (e) {} // стандартные арты карты имён
    try {
        nxAllMediaUrls().forEach(function (raw) { // все ссылки паков и карт (включая авторские)
            var eff = raw; try { eff = mediaUrl(raw); } catch (e) {}
            var s = String(eff || '');
            var n = nxMediaKey(s); if (!n) return;
            if (s.indexOf('/media/') >= 0 || s.indexOf('media/') === 0 || NX_EMBED_MEDIA[n]) used[n] = 1;
        });
    } catch (e) {}
    try { // b351: прямой скан живой памяти по именам файлов (любые формы ссылок)
        if (typeof state !== 'undefined' && state) {
            (state.packs || []).forEach(function (p) { var n = nxMediaKey(p && p.image); if (n) used[n] = 1; });
            (state.cards || []).forEach(function (c) { var n = nxMediaKey(c && c.image); if (n) used[n] = 1; });
        }
    } catch (e) {}
    try { // b351: всё, что сайт сам заливал на GitHub, по определению в работе
        nxMediaPushedSet().forEach(function (n) { used[n] = 1; });
    } catch (e) {}
    return used;
}
function nxMediaAudit() {
    if (!nxGhToken()) {
        try { nxOwnerToast('Сначала сохраните токен GitHub в блоке «Картинки сайта → GitHub»', 'error'); } catch (e) {}
        var t = document.getElementById('nx-gh-token'); if (t) { t.focus(); t.scrollIntoView({ block: 'center' }); }
        return;
    }
    var repo = nxGhRepoName();
    nxStatus('Читаю список файлов media/ на GitHub…');
    nxGhApi('/repos/' + repo + '/contents/media').then(function (list) {
        var files = (list || []).filter(function (f) { return f.type === 'file'; });
        var used = nxMediaUsedNames();
        NX_MEDIA_EXTRA = files.filter(function (f) { return f.name !== 'manifest.json' && !used[f.name]; }).map(function (f) { return f.name; });
        var usedCount = files.length - NX_MEDIA_EXTRA.length;
        var msg = 'media/: ' + files.length + ' файл(ов), из них в работе ' + usedCount +
            (NX_MEDIA_EXTRA.length ? '; лишних ' + NX_MEDIA_EXTRA.length + ': ' + NX_MEDIA_EXTRA.slice(0, 8).join(', ') + (NX_MEDIA_EXTRA.length > 8 ? '…' : '') : '; лишних нет');
        nxStatus(msg, NX_MEDIA_EXTRA.length ? '' : 'ok');
        var r = document.getElementById('nx-audit-result'); if (r) r.textContent = msg;
        var b = document.getElementById('nx-audit-del-btn');
        if (b) { b.disabled = !NX_MEDIA_EXTRA.length; b.innerHTML = '<i class="fa-solid fa-trash mr-1"></i>Удалить лишнее: ' + (NX_MEDIA_EXTRA.length || '—'); }
        try { nxOwnerToast(NX_MEDIA_EXTRA.length ? 'Лишних файлов в media/: ' + NX_MEDIA_EXTRA.length + ' — список в статус-строке' : 'Лишних файлов нет: всё в media/ используется сайтом', 'success'); } catch (e) {}
    }).catch(function (e) { nxStatus('Ошибка аудита: ' + e.message, 'err'); });
}
function nxMediaAuditApply() {
    if (!NX_MEDIA_EXTRA.length) return;
    if (!window.confirm('Удалить ' + NX_MEDIA_EXTRA.length + ' лишних файл(ов) из media/?\n\n' + NX_MEDIA_EXTRA.slice(0, 15).join('\n') + (NX_MEDIA_EXTRA.length > 15 ? '\n…' : '') + '\n\nОстанутся только картинки, которые использует сайт. Восстановить можно из истории GitHub.')) return;
    var repo = nxGhRepoName();
    nxStatus('Удаляю лишнее из media/…');
    nxProgress(0.2, 'Готовлю коммит удаления…');
    (function attempt(n) {
        nxGhApi('/repos/' + repo).then(function (info) {
            var branch = info.default_branch || 'main';
            return nxGhApi('/repos/' + repo + '/git/ref/heads/' + branch).then(function (ref) {
                var head = ref.object.sha;
                return nxGhApi('/repos/' + repo + '/git/commits/' + head).then(function (cm) {
                    var entries = NX_MEDIA_EXTRA.map(function (name) { return { path: 'media/' + name, mode: '100644', type: 'blob', sha: null }; });
                    return nxGhApi('/repos/' + repo + '/git/trees', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ base_tree: cm.tree.sha, tree: entries }) }).then(function (tr) {
                        return nxGhApi('/repos/' + repo + '/git/commits', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: 'авто: уборка лишних media/ (' + NX_MEDIA_EXTRA.length + ')', parents: [head], tree: tr.sha }) }).then(function (nc) {
                            return nxGhApi('/repos/' + repo + '/git/refs/heads/' + branch, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sha: nc.sha }) });
                        });
                    });
                });
            });
        }).then(function () {
            var del = NX_MEDIA_EXTRA.slice();
            try { var s = nxMediaPushedSet(); del.forEach(function (d) { s.delete(d); }); nxMediaSavePushed(s); } catch (e) {}
            NX_MEDIA_EXTRA = [];
            var b = document.getElementById('nx-audit-del-btn'); if (b) { b.disabled = true; b.innerHTML = '<i class="fa-solid fa-trash mr-1"></i>Удалить лишнее: —'; }
            var r = document.getElementById('nx-audit-result'); if (r) r.textContent = 'Удалено лишних: ' + del.length + '. В media/ остались только рабочие картинки.';
            nxProgress(1, 'Готово: ' + del.length + ' лишних файл(ов) удалено из media/', 'ok');
            nxStatus('Лишнее удалено: ' + del.join(', '), 'ok');
            try { nxOwnerToast('Удалено ' + del.length + ' лишних файл(ов) из media/', 'success'); } catch (e) {}
        }).catch(function (e) {
            if (n < 3 && /not a fast forward/i.test(String(e && e.message))) { setTimeout(function () { attempt(n + 1); }, 1500); return; }
            nxProgress(0, ''); nxStatus('Ошибка удаления: ' + e.message, 'err');
        });
    })(1);
}
// ---- b345: возврат артов из старой сборки (если media/ пуста) ----
function nxOldBuildUrl() { return 'https://raw.githubusercontent.com/' + nxGhRepoName() + '/15b635af139ba580a5f49c38a21f88d4a54ea559/index.html'; }
function nxCheckMediaMissing() {
    try {
        if (!(location.protocol === 'http:' || location.protocol === 'https:')) return;
        if (!nxGhToken()) return; // b348: служебные плашки видят только владельцы с токеном
        fetch(nxMediaFolder() + '0001_doktor.jpg', { method: 'HEAD' }).then(function (r) {
            var row = document.getElementById('nx-migrate-row');
            if (r.status === 404) {
                if (row) row.style.display = '';
                nxStatus('В папке media/ нет картинок — нажмите «Вернуть арты из старой версии»', 'err');
            } else if (row) row.style.display = 'none';
        }).catch(function () {});
    } catch (e) {}
}
function nxMigrateOldArts() {
    if (!nxGhToken()) {
        try { nxOwnerToast('Сначала сохраните токен GitHub в блоке «Картинки сайта → GitHub»', 'error'); } catch (e) {}
        var t = document.getElementById('nx-gh-token'); if (t) { t.focus(); t.scrollIntoView({ block: 'center' }); }
        return;
    }
    var repo = nxGhRepoName();
    nxStatus('Скачиваю старую версию сайта с артами (одноразово, ~17 МБ)…');
    nxProgress(0.05, 'Читаю старую сборку из истории GitHub…');
    fetch(nxOldBuildUrl(), { cache: 'no-store' }).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); }).then(function (t) {
        var m = 'const NX_EMBED_MEDIA = ';
        var i = t.indexOf(m); if (i < 0) throw new Error('в старой сборке нет карты артов');
        var j = t.indexOf('/*NX_EMBED_MEDIA_END', i); if (j < 0) throw new Error('в старой сборке нет карты артов');
        var obj = JSON.parse(t.slice(i + m.length, j));
        var names = Object.keys(obj);
        nxProgress(0.35, 'Распаковываю арты: ' + names.length + '…');
        var items = [];
        names.forEach(function (n) {
            try {
                var b64 = String(obj[n]).split(',')[1] || '';
                var bin = atob(b64); var u = new Uint8Array(bin.length);
                for (var k = 0; k < bin.length; k++) u[k] = bin.charCodeAt(k);
                items.push({ name: n, blob: new Blob([u], { type: 'image/jpeg' }) });
            } catch (e) {}
        });
        if (!items.length) throw new Error('не удалось распаковать ни одного арта');
        nxProgress(0.5, 'Отправляю ' + items.length + ' файлов в media/ (один коммит)…');
        nxGhPushMedia(repo, items, function () {
            var s = nxMediaPushedSet(); items.forEach(function (it) { s.add(it.name); }); nxMediaSavePushed(s);
            nxProgress(1, 'Готово: ' + items.length + ' артов лежат в media/. Pages обновится за 1–2 минуты', 'ok');
            nxStatus('Арты возвращены: ' + items.length + ' файлов в media/', 'ok');
            try { nxOwnerToast('Арты возвращены в media/ (' + items.length + ' файлов)! Pages обновится за 1–2 минуты', 'success'); } catch (e) {}
            var row = document.getElementById('nx-migrate-row'); if (row) row.style.display = 'none';
        }, function (msg) {
            nxProgress(0, ''); nxStatus('Ошибка возврата артов: ' + msg, 'err');
            try { nxOwnerToast('Ошибка: ' + msg, 'error'); } catch (e) {}
        });
    }).catch(function (e) { nxProgress(0, ''); nxStatus('Не удалось скачать старую версию: ' + e.message, 'err'); });
}
// ---- b349: service worker — вечный кэш media/ в браузерах пользователей, разгрузка GitHub Pages ----
function nxRegisterMediaSW() {
    try {
        if (!('serviceWorker' in navigator) || location.protocol !== 'https:') return;
        var swUrl = String(location.pathname || '/').replace(/[^/]*$/, '') + 'sw.js';
        window.addEventListener('load', function () {
            try { navigator.serviceWorker.register(swUrl).catch(function () {}); } catch (e) {}
        });
    } catch (e) {}
}
nxRegisterMediaSW();
try {
    nxAutoMediaLabel();
    setTimeout(function () { try { if (nxAutoMediaOn()) nxCollectPendingMedia().then(function (it) { if (it.length) nxMaybeAutoMediaPush(false); }); } catch (e) {} }, 20000);
    setInterval(function () { try { if (!nxAutoMediaOn() || document.hidden) return; nxCollectPendingMedia().then(function (it) { if (it.length) nxMaybeAutoMediaPush(false); }); } catch (e) {} }, 5 * 60 * 1000);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) { try { nxMaybeAutoMediaPush(false); } catch (e) {} } });
} catch (e) {}
// ---- b329: кнопка «Вшить всё»: авто-скачивание всех артов + автосборка файла ----
function nxAutoCacheAll(done) {
    const jobs = [];
    try {
        nxAllMediaUrls().forEach(raw => { let eff = raw; try { eff = mediaUrl(raw); } catch (e) {} if (eff && eff.indexOf('http') === 0) jobs.push(eff); });
    } catch (e) { done(0); return; }
    if (!jobs.length) { done(0); return; }
    let i = 0, fresh = 0, active = 0, finished = false;
    const fin = () => { if (!finished && i >= jobs.length && active === 0) { finished = true; done(fresh); } };
    const next = () => {
        if (i >= jobs.length) { fin(); return; }
        const u = jobs[i++]; active++;
        const step = () => { active--; fin(); next(); };
        imgCacheObjUrl(u).then(hit => {
            if (hit) { step(); return; }
            try { IMG_FAIL.delete(u); } catch (e) {}
            imgCacheStoreFromNetwork(u).then(ou => { if (ou) fresh++; step(); }, () => step());
        }, () => step());
    };
    next(); next(); next();
}
function nxEmbedAll() {
    const btn = document.getElementById('nx-embed-all'); if (btn) btn.disabled = true;
    try { nxOwnerToast('«Вшить всё»: собираю все арты, до которых дотянется сайт…', 'success'); } catch (e) {}
    nxAutoCacheAll(fresh => {
        try { nxOwnerToast('Скачано нового: ' + fresh + '. Собираю файл со вшитыми артами…', 'success'); } catch (e) {}
        setTimeout(() => {
            try { nxExportEmbedded(); } catch (e) {}
            if (btn) btn.disabled = false;
        }, 600);
    });
}
// ---- b341: авто-пуш новых артов в сайт (без кнопок) ----
function nxNewBasesForMap() { // имена файлов, которые есть в ссылках, но ещё не в карте имён
    const out = [];
    try {
        nxAllMediaUrls().forEach(raw => {
            let eff = raw; try { eff = mediaUrl(raw); } catch (e) {}
            if (!eff || eff.indexOf('http') !== 0) return;
            const b = nxMediaKey(eff);
            if (b && !NX_EMBED_MEDIA[b] && out.indexOf(b) < 0) out.push(b);
        });
    } catch (e) {}
    return out;
}
function nxMediaUrlForBase(b) { // любая внешняя ссылка с этим именем файла (для проверки кэша)
    try {
        const all = nxAllMediaUrls();
        for (let i = 0; i < all.length; i++) { const e = mediaUrl(all[i]); if (e && e.indexOf('http') === 0 && nxMediaKey(e) === b) return e; }
    } catch (e) {}
    return '';
}
function nxScheduleAutoPush() {
    try {
        const last = parseInt(LS.getItem('nx_last_autopush') || '0', 10);
        if (Date.now() - last < 600000) return; // b342-solo: не чаще раза в 10 минут (было 30)
        if (window.__nxAutoPushT) return;
        window.__nxAutoPushT = setTimeout(() => {
            window.__nxAutoPushT = 0;
            try {
                if (!navigator.onLine || document.hidden || !nxAutoEmbedOn() || !nxGhToken()) return;
                const bases = nxNewBasesForMap();
                if (!bases.length) return;
                Promise.all(bases.slice(0, 40).map(b => imgCacheObjUrl(nxMediaUrlForBase(b)).then(ou => ou ? 1 : 0, () => 0))).then(h => {
                    const have = h.reduce((a, x) => a + x, 0);
                    if (!have) return;
                    LS.setItem('nx_last_autopush', String(Date.now()));
                    try { nxCrashLog('autoembed: авто-пуш ' + have + ' новых артов на сайт'); } catch (e) {}
                    nxStatus('Автовшивание: собираю и пушу файл…');
                    nxPushEmbedded(true);
                });
            } catch (e) { try { nxCrashLog('autoembed-schedule: ' + ((e && e.message) || e)); } catch (e2) {} }
        }, 120000); // дебаунс 2 минуты: копим пачку нового
    } catch (e) {}
}
setInterval(() => { // фоновая проверка раз в 5 минут: появилось ли новое для авто-пуша
    try {
        if (!nxAutoEmbedOn()) { nxSayOnce('autoembed_off', 'Автовшивание выключено (кнопка «Автовшивание: выкл») — авто-пуша не будет'); nxStatus('Автовшивание выключено — новые арты сами не уходят. Нажмите «Автовшивание: выкл», чтобы включить'); return; }
        if (!nxGhToken()) { nxSayOnce('autoembed_notoken', 'Автовшивание: нет токена GitHub — коммитить нечем'); nxStatus('Автовшивание: нет токена GitHub — сохраните токен в настройках', 'err'); return; }
        if (document.hidden) { nxSayOnce('autoembed_hidden', 'Автовшивание: вкладка в фоне — браузер глушит таймеры, пуш откладывается'); return; }
        if (!navigator.onLine) { nxSayOnce('autoembed_offline', 'Автовшивание: нет сети'); return; }
        var nb = nxNewBasesForMap();
        if (nb.length) { nxStatus('Автовшивание: новых артов — ' + nb.length + ', скоро соберу файл и запушу'); nxScheduleAutoPush(); }
    } catch (e) { try { nxCrashLog('autoembed-check: ' + ((e && e.message) || e)); } catch (e2) {} }
}, 300000);
// ---- b328: лампочка-индикатор у полей ссылки на арт: вшит / в кэше / нет ----
const NX_LAMP_COLORS = { off: '#475569', emb: '#22c55e', cache: '#eab308', none: '#ef4444' };
function nxLampPaint(inputId, st) {
    const lamp = document.getElementById(inputId + '-lamp');
    if (!lamp) return;
    lamp.dataset.st = st;
    const c = NX_LAMP_COLORS[st] || NX_LAMP_COLORS.off;
    lamp.style.background = c;
    lamp.style.boxShadow = '0 0 8px ' + c;
}
function nxEmbedLampRefresh(inputId) {
    try {
        const inp = document.getElementById(inputId);
        if (!inp) return;
        const url = String(inp.value || '').trim();
        lamp_url_set: {
            const lamp = document.getElementById(inputId + '-lamp');
            if (lamp) lamp.dataset.url = url;
        }
        if (!url) { nxLampPaint(inputId, 'off'); return; }
        let eff = url;
        try { eff = mediaUrl(url); } catch (e) {}
        if (eff !== url || String(eff).indexOf('data:') === 0) { nxLampPaint(inputId, 'emb'); return; } // вшит в сборку (base64 или файл media/)
        nxLampPaint(inputId, 'none'); // пока считаем «не вшит», уточним по кэшу
        imgCacheObjUrl(url).then(ou => {
            const lamp = document.getElementById(inputId + '-lamp');
            if (lamp && lamp.dataset.url !== url) return; // ссылка уже поменялась
            nxLampPaint(inputId, ou ? 'cache' : 'none');
        }, () => {});
    } catch (e) {}
}
setInterval(() => { // пока редактор открыт — лампочки живут своей жизнью (кэш мог дотянуться)
    try {
        ['pack-image', 'card-image'].forEach(id => {
            const inp = document.getElementById(id);
            if (!inp || !inp.offsetParent) return;
            const lamp = document.getElementById(id + '-lamp');
            if (lamp && lamp.dataset.st === 'emb') return;
            nxEmbedLampRefresh(id);
        });
    } catch (e) {}
}, 5000);
// ---- b324: АВТОзакачка артов по ссылкам в постоянный кэш устройства ----
let nxAutoRunning = false;
function nxAutoCacheOnce() {
    // тихо, фоном: всё, что ещё не в кэше, тянем в постоянный кэш (IndexedDB).
    // Ретраим даже «мёртвые» ссылки: когда хост оживёт, арты подтянутся сами.
    if (nxAutoRunning || !navigator.onLine || document.hidden) return;
    const jobs = [];
    try {
        nxAllMediaUrls().forEach(raw => {
            let eff = raw; try { eff = mediaUrl(raw); } catch (e) {}
            if (eff && eff.indexOf('http') === 0) jobs.push(eff);
        });
    } catch (e) { return; }
    if (!jobs.length) return;
    nxAutoRunning = true;
    const CAP = 10; // за подход не больше 10 файлов — не забиваем канал
    let i = 0, done = 0, fresh = 0;
    const step = () => {
        if (i >= jobs.length || done >= CAP) {
            nxAutoRunning = false;
            if (fresh) { try { nxOwnerToast('Автокэш артов: +' + fresh + ' сохранено в устройстве', 'success'); } catch (e) {} }
            try { nxUpdateCounts(); } catch (e) {}
            // b327: хост ожил и всё дотянулось — радуемся один раз
            try {
                if (fresh && !window.__nxAllCached && i >= jobs.length) {
                    let miss = 0;
                    jobs.forEach(u => { if (!IMG_OBJ.has(u)) miss++; });
                    if (miss === 0) { window.__nxAllCached = 1; nxOwnerToast('Все арты коллекции закэшированы! Игра полностью офлайн-готова', 'success'); }
                }
            } catch (e) {}
            // b341: автовшивание — любые НОВЫЕ арты из кэша сами уходят коммитом на сайт
            try {
                if (nxAutoEmbedOn() && nxGhToken() && (fresh > 0 || nxNewBasesForMap().length)) {
                    nxScheduleAutoPush();
                }
            } catch (e) { try { nxCrashLog('autoembed-after-cache: ' + ((e && e.message) || e)); } catch (e2) {} }
            return;
        }
        nxProgress(done / Math.max(1, jobs.length), 'Автокэш картинок: ' + done + '/' + jobs.length + ' (новых за подход: ' + fresh + ')');
        const u = jobs[i++];
        imgCacheObjUrl(u).then(hit => {
            if (hit) { done++; step(); return; }
            try { IMG_FAIL.delete(u); } catch (e) {} // b324: ссылку могли считать мёртвой до оживления хоста
            imgCacheStoreFromNetwork(u).then(ou => { if (ou) fresh++; done++; step(); }, () => { done++; step(); });
        }, () => { done++; step(); });
    };
    step(); step();
}
setTimeout(() => { try { nxAutoCacheOnce(); } catch (e) {} }, 8000); // сразу после старта
setInterval(() => { try { nxAutoCacheOnce(); } catch (e) {} }, 60000); // и каждую минуту
window.addEventListener('online', () => { setTimeout(() => { try { nxAutoCacheOnce(); } catch (e) {} }, 3000); });
// ---- b306: анти-краш: журнал аварий, сторож памяти, диагностика ----
const NX_BUILD = 'b323-2026-10-07';
try { nx3dBtnInit(); } catch (e) {}
try { nxAutoEmbedUI(); } catch (e) {}
try { nxBuildProgressUI(); } catch (e) {}
setTimeout(function () { try { nxCheckArts(true); } catch (e) {} }, 9000);
setTimeout(function () { try { nxUpdateCounts(); } catch (e) {} }, 3000);
function nxCrashLog(msg) {
    try {
        const arr = JSON.parse(LS.getItem('nx_crash_log') || '[]');
        arr.push({ t: Date.now(), m: String(msg).slice(0, 300) });
        while (arr.length > 6) arr.shift();
        LS.setItem('nx_crash_log', JSON.stringify(arr));
    } catch (e) {}
}
window.addEventListener('error', ev => {
    try {
        if (ev.target && ev.target !== window && !ev.message) return; // битая картинка и т.п. — не авария
        nxCrashLog('error: ' + (ev.message || '?') + ' @' + String(ev.filename || '').slice(-24) + ':' + ev.lineno);
    } catch (e) {}
}, true);
window.addEventListener('unhandledrejection', ev => {
    try { nxCrashLog('rejection: ' + String((ev.reason && ev.reason.message) || ev.reason || '?')); } catch (e) {}
});
// детект «прошлая сессия умерла без прощания» (белый экран / убийство WebView)
(function () {
    try {
        const bye = LS.getItem('nx_bye');
        const beatRaw = String(LS.getItem('nx_beat') || '0');
        const beat = parseInt(beatRaw, 10) || 0;
        const beatSnap = beatRaw.indexOf('|') > 0 ? beatRaw.slice(beatRaw.indexOf('|')) : '';
        LS.setItem('nx_bye', '');
        if (!bye && beat && Date.now() - beat < 180000) {
            nxCrashLog('подозрение на аварийное завершение прошлой сессии (белый экран/OOM). Последний пульс' + (beatSnap ? ' ' + beatSnap : '') + ', возраст ' + Math.round((Date.now() - beat) / 1000) + ' с');
            // b358: два аварийных завершения подряд — устройство 3D не тянет,
            // сами переводим игры в плоский режим (в Студии 3D можно вернуть)
            try {
                const hc = (parseInt(LS.getItem('nx_hard_crash') || '0', 10) || 0) + 1;
                LS.setItem('nx_hard_crash', String(hc));
                if (hc >= 2 && !nxForce3d()) {
                    LS.setItem('nx_weak_gpu', '1');
                    setTimeout(() => { try { showToast('Прошлые сессии обрывались браузером (нехватка памяти) — 3D отключено, игры в плоском режиме. Вернуть 3D можно в Студии', 'error'); } catch (e) {} }, 3200);
                }
            } catch (e) {}
            setTimeout(() => { try { nxOwnerToast('Прошлая сессия оборвалась аварийно. Если это повторяется: Настройки → «Диагностика» → пришлите код создателю', 'error'); } catch (e) {} }, 2500);
        }
        // b358: в «пульс» пишем не только время, но и слепок состояния (heap,
        // число живых 3D-контекстов, размер кэша картинок). Когда вкладку убивает
        // браузер, JS не успевает записать ничего — зато последний пульс за 0–5 с до
        // смерти остаётся, и в журнале аварий видно, что именно её добило.
        setInterval(() => {
            try {
                var snap = '';
                try {
                    var pm = (window.performance && performance.memory) ? performance.memory : null;
                    var heapMB = pm ? Math.round(pm.usedJSHeapSize / 1048576) : -1;
                    var live3d = 0;
                    try {
                        live3d = (typeof slots !== 'undefined' && slots.renderer ? 1 : 0)
                            + (typeof grid3d !== 'undefined' && grid3d.renderer ? 1 : 0)
                            + (typeof wheel !== 'undefined' && wheel.renderer ? 1 : 0)
                            + (typeof lines3d !== 'undefined' && lines3d.renderer ? 1 : 0)
                            + (typeof battle3d !== 'undefined' && battle3d ? 1 : 0);
                    } catch (e) {}
                    var imgN = -1; try { imgN = (typeof IMG_OBJ !== 'undefined' && IMG_OBJ.size != null) ? IMG_OBJ.size : -1; } catch (e) {}
                    snap = '|heap:' + heapMB + 'MB|3d:' + live3d + '|img:' + imgN;
                } catch (e) {}
                LS.setItem('nx_beat', String(Date.now()) + snap);
            } catch (e) {}
        }, 5000);
        const byeFn = () => { try { LS.setItem('nx_bye', '1'); LS.setItem('nx_hard_crash', '0'); } catch (e) {} };
        window.addEventListener('pagehide', byeFn);
        window.addEventListener('beforeunload', byeFn);
    } catch (e) {}
})();
// сторож памяти: на слабых WebView Telegram кэш и 3D съедают всё — разгружаемся заранее
setInterval(() => {
    try {
        const pm = (window.performance && performance.memory) ? performance.memory : null;
        if (!pm) return;
        const mb = pm.usedJSHeapSize / 1048576;
        // Порог не абсолютный: на слабых Android jsHeapSizeLimit бывает ~256 МБ,
        // и фиксированные 350 МБ не достигались НИКОГДА — сторож просто не работал.
        let lim = 350;
        try { if (pm.jsHeapSizeLimit > 0) lim = Math.min(350, Math.floor(pm.jsHeapSizeLimit / 1048576 * 0.55)); } catch (e) {}
        if (lim < 120) lim = 120;
        if (mb < lim) return; // b318: WebView Telegram живёт в меньшем лимите
        try { IMG_OBJ.forEach(ou => { try { URL.revokeObjectURL(ou); } catch (e) {} }); IMG_OBJ.clear(); } catch (e) {}
        try { imgQueue.length = 0; } catch (e) {}
        try { nx3dPauseAll(); } catch (e) {} // b357: сначала остановить кадры, потом отдавать контексты
        try { nx3dReleaseHidden('__all__'); } catch (e) {}
        try { if (battleMode !== 'arena' && typeof battle3d !== 'undefined' && battle3d) battle3dDispose(); } catch (e) {}
        try { if (battleMode !== 'durak' && typeof durak3dDispose === 'function') durak3dDispose(); } catch (e) {}
        nxCrashLog('memguard: heap ' + Math.round(mb) + ' МБ — разгружены blob-кэш и 3D');
        if (mb > 650) { // b318
            const last = parseInt(LS.getItem('nx_memreload') || '0', 10);
            if (Date.now() - last > 600000) {
                LS.setItem('nx_memreload', String(Date.now()));
                try { LS.setItem('nx_weak_gpu', '1'); } catch (e) {} // b309
                nxCrashLog('memguard: мягкая перезагрузка при heap ' + Math.round(mb) + ' МБ');
                try { saveState(); } catch (e) {}
                try { showToast('Память устройства на пределе — перезагружаю игру, прогресс сохранён', 'error'); } catch (e) {}
                setTimeout(() => location.reload(), 1500);
            }
        }
    } catch (e) {}
}, 10000);
function nxShowDiag() {
    const L = [];
    L.push('сборка: ' + NX_BUILD);
    L.push('устройство: ' + String(navigator.userAgent).slice(0, 120));
    try {
        const pm = (window.performance && performance.memory) ? performance.memory : null;
        if (pm) L.push('heap: ' + Math.round(pm.usedJSHeapSize / 1048576) + ' МБ из ' + Math.round(pm.jsHeapSizeLimit / 1048576) + ' МБ');
    } catch (e) {}
    try { L.push('режим: ' + battleMode); } catch (e) {}
    try {
        const jobs = [];
        nxAllMediaUrls().forEach(raw => { let eff = raw; try { eff = mediaUrl(raw); } catch (e) {} if (eff && eff.indexOf('http') === 0) jobs.push(eff); });
        L.push('ссылок на внешние арты: ' + jobs.length + ' (0 = всё вшито в файл)');
        Promise.all(jobs.map(u => imgCacheObjUrl(u).then(ou => ou ? 1 : 0, () => 0))).then(h => {
            const line = 'в авто-кэше устройства: ' + h.reduce((a, b) => a + b, 0) + '/' + jobs.length;
            try { window.prompt('Диагностика (обновлено): нажмите и удерживайте → копировать', L.concat(line).join('\n')); } catch (e) {}
        });
    } catch (e) {}
    try {
        const arr = JSON.parse(LS.getItem('nx_crash_log') || '[]');
        if (!arr.length) L.push('журнал аварий пуст');
        arr.forEach(x => L.push(new Date(x.t).toLocaleString() + ' — ' + x.m));
    } catch (e) {}
    const text = L.join('\n');
    try { console.log(text); } catch (e) {}
    try { window.prompt('Диагностика: нажмите и удерживайте текст → копировать → пришлите создателю', text); } catch (e) { showToast(text, 'error'); }
}
// ---- b304: автозакачка артов и экспорт сборки со встроенными артами ----
function nxAllMediaUrls() { // все ссылки артов: стандарт + авторские паки/карты
    const out = [];
    const add = u => { const s = String(u || '').trim(); if (s && s.indexOf('http') === 0 && out.indexOf(s) < 0) out.push(s); };
    try {
        defaultPacks.forEach(p => add(p.image));
        defaultCards.forEach(c => add(c.image));
        if (typeof state !== 'undefined' && state) { // b351: const state не лежит на window — проверка через typeof
            (state.packs || []).forEach(p => add(p.image));
            (state.cards || []).forEach(c => add(c.image));
        }
    } catch (e) {}
    return out;
}
let nxCacheAllRunning = false;
function nxCacheAll() { // фоном тянет всю коллекцию в постоянный кэш (IndexedDB)
    if (nxCacheAllRunning) { showToast('Уже качаю коллекцию — смотрите прогресс выше', 'success'); return; }
    const raws = nxAllMediaUrls();
    const jobs = [];
    raws.forEach(raw => {
        let eff = raw;
        try { eff = mediaUrl(raw); } catch (e) {}
        if (eff && eff.indexOf('http') === 0) jobs.push({ raw: raw, eff: eff });
    });
    if (!jobs.length) { nxOwnerToast('Нечего качать: все арты уже вшиты в файл', 'error'); return; }
    nxCacheAllRunning = true;
    const btn = document.getElementById('nx-cache-all-btn'); if (btn) btn.disabled = true;
    const total = jobs.length;
    let done = 0, fresh = 0, ptr = 0;
    const tick = () => {
        done++;
        if (done % 4 === 0 || done === total) nxOwnerToast('Качаю арты: ' + done + '/' + total + (fresh ? ', новых: ' + fresh : ''), 'success');
        next();
    };
    const next = () => {
        if (ptr >= jobs.length) {
            if (done >= total) {
                nxCacheAllRunning = false; if (btn) btn.disabled = false;
                nxOwnerToast('Готово: коллекция закэширована (' + fresh + ' новых артов). Альбомы откроются без сети', 'success');
            }
            return;
        }
        const j = jobs[ptr++];
        imgCacheObjUrl(j.eff).then(hit => {
            if (hit) { tick(); return; } // уже в кэше — сеть не трогаем
            imgCacheStoreFromNetwork(j.eff).then(ou => { if (ou) fresh++; tick(); }, () => tick());
        }, () => tick());
    };
    nxOwnerToast('Старт: ' + total + ' артов в очереди на закачку в кэш', 'success');
    for (let i = 0; i < 3; i++) next();
}
function nxExportEmbedded() { // собирает копию файла игры с кэшированными артами внутри
    const btn = document.getElementById('nx-export-btn'); if (btn) btn.disabled = true;
    const fin = (m, t) => { if (btn) btn.disabled = false; showToast(m, t || 'success'); };
    nxSrcGet().then(src => { // b342-solo
        const pairs = [];
        nxAllMediaUrls().forEach(raw => {
            let eff = raw;
            try { eff = mediaUrl(raw); } catch (e) {}
            pairs.push({ raw: raw, eff: eff });
        });
        let out = src, pending = pairs.length, replaced = 0; const extras = []; // b340
        if (!pending) { fin('Кэш пуст: сначала нажмите «Скачать все арты»', 'error'); return; }
        const finalize = () => { out = nxInjectExtras(out, extras); // b340
            const blob = new Blob([out], { type: 'text/html' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'index_embedded.html';
            document.body.appendChild(a); a.click();
            setTimeout(() => { try { URL.revokeObjectURL(a.href); a.remove(); } catch (e) {} }, 4000);
            fin('Сборка скачана: артов вшито — ' + (replaced + extras.length) + '. Залейте index_embedded.html как новую версию игры');
        };
        const apply = (raw, dataUrl) => {
            if (dataUrl) {
                if (out.indexOf(raw) >= 0) { out = out.split(raw).join(dataUrl); replaced++; }
                try { const bb = nxMediaKey(raw); if (bb) extras.push([bb, dataUrl]); } catch (e) {} // b340
            }
            if (--pending === 0) finalize();
        };
        pairs.forEach(p => {
            imgCacheGetBlob(p.eff).then(blob => {
                if (!blob || !blob.size) return apply(p.raw, null);
                const fr = new FileReader();
                fr.onload = () => apply(p.raw, String(fr.result));
                fr.onerror = () => apply(p.raw, null);
                fr.readAsDataURL(blob);
            }, () => apply(p.raw, null));
        });
    }).catch(e => fin('Не удалось взять исходник сборки с хоста: ' + e.message, 'error'));
}
// ---- копирование и ручная вставка ----
function qrxCopy() {
    const text = qrxCode || JSON.stringify(qrxSnapshot());
    const done = () => showToast('Код переноса скопирован — вставьте его на втором устройстве', 'success');
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, () => qrxCopyFallback(text, done));
    else qrxCopyFallback(text, done);
}
function qrxCopyFallback(text, done) {
    try {
        const ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta);
        done();
    } catch (e) { showToast('Браузер не дал скопировать — попробуйте ещё раз', 'error'); }
}
function qrxPasteApply() {
    const ta = document.getElementById('qr-paste-input');
    qrxHandleCode(ta ? ta.value : '');
}