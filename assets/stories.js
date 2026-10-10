/* b254: Нарезчик сторис 9:16 — встроен в Студию, изолирован IIFE-скоупом */
(function () {

"use strict";
/* =========================================================================
   Модель координат
   -------------------------------------------------------------------------
   q-пространство = повёрнутое изображение, вписанное в свой габаритный
   прямоугольник B (начало координат — левый верхний угол B).
   Рамка кадра state.crop {x,y,w,h} задана в q-пространстве и ВСЕГДА
   имеет пропорции 9:16, на экране остаётся вертикальной.
   Экспорт: output = k * (q - q0),  k = W / crop.w
   ========================================================================= */
const ASPECT = 9 / 16;

const state = {
  img: null, name: 'image', iw: 0, ih: 0,
  rot: 0, flip: false,
  crop: { x: 0, y: 0, w: 0, h: 0 },
  view: { s: 1, ox: 0, oy: 0 },
  fmt: 'image/png', quality: 0.92,
  counter: 0, nameMode: 'num_name', baseName: '', baseNameDirty: false,
  bgMode: 'auto', bgColor: '#000000',
  showGrid: true, showSafe: false
};

const $ = (id) => document.getElementById(id);
const view = $('s9-view'), vctx = view.getContext('2d');
const prev = $('s9-preview'), pctx = prev.getContext('2d');
const clamp = (v, a, b) => v < a ? a : (v > b ? b : v);
const rootVisible = () => { const r = document.getElementById('s9-root'); return !!r && r.offsetParent !== null; };
const rad = d => d * Math.PI / 180;

function bounds(w, h, a) {
  const c = Math.abs(Math.cos(a)), s = Math.abs(Math.sin(a));
  return { w: w * c + h * s, h: w * s + h * c };
}
const B = () => bounds(state.iw, state.ih, rad(state.rot));

function computeView() {
  const cw = view.clientWidth || view.width, ch = view.clientHeight || view.height;
  const b = B();
  const s = Math.max(1e-4, Math.min((cw - 40) / b.w, (ch - 40) / b.h));
  state.view = { s, ox: (cw - b.w * s) / 2, oy: (ch - b.h * s) / 2 };
}
const qToView = (x, y) => ({ x: state.view.ox + x * state.view.s, y: state.view.oy + y * state.view.s });
const viewToQ = (px, py) => ({ x: (px - state.view.ox) / state.view.s, y: (py - state.view.oy) / state.view.s });
function cropRectView() {
  const p = qToView(state.crop.x, state.crop.y);
  return { x: p.x, y: p.y, w: state.crop.w * state.view.s, h: state.crop.h * state.view.s };
}

/* --- нормализация / пресеты рамки --- */
function normCrop() {
  const b = B(), c = state.crop;
  c.w = clamp(c.w, 8, Math.max(b.w, b.h) * 8);
  c.h = c.w / ASPECT;
  c.x = clamp(c.x, Math.min(0, b.w - c.w), Math.max(0, b.w - c.w));
  c.y = clamp(c.y, Math.min(0, b.h - c.h), Math.max(0, b.h - c.h));
}
/* максимальный кадр 9:16 ВНУТРИ изображения — фото заполняет кадр без полей */
function fitInside() {
  const b = B(), w = Math.min(b.w, b.h * ASPECT);
  state.crop = { x: (b.w - w) / 2, y: (b.h - w / ASPECT) / 2, w, h: w / ASPECT };
}
/* кадр покрывает весь снимок целиком — по краям возможны поля */
function fitWhole() {
  const b = B(), w = Math.max(b.w, b.h * ASPECT);
  state.crop = { x: (b.w - w) / 2, y: (b.h - w / ASPECT) / 2, w, h: w / ASPECT };
}
function centerCrop() {
  const b = B();
  state.crop.x = (b.w - state.crop.w) / 2;
  state.crop.y = (b.h - state.crop.h) / 2;
  normCrop();
}
/* смена поворота: держим относительный центр рамки, размер подгоняем под новый габарит */
function keepCropOnRotate(prevCrop, prevB) {
  const nx = (prevCrop.x + prevCrop.w / 2) / prevB.w;
  const ny = (prevCrop.y + prevCrop.h / 2) / prevB.h;
  const b = B();
  let w = prevCrop.w;
  if (w > b.w || w / ASPECT > b.h) w = Math.min(b.w, b.h * ASPECT);  // не влезает — уменьшаем до максимума
  state.crop = { x: nx * b.w - w / 2, y: ny * b.h - (w / ASPECT) / 2, w, h: w / ASPECT };
  normCrop();
}

/* =========================================================================
   Отрисовка
   ========================================================================= */
function bgFill(ctx, W, H) {
  const need = state.bgMode === 'color' || (state.bgMode === 'auto' && state.fmt === 'image/jpeg');
  if (!need) return;
  ctx.save(); ctx.fillStyle = state.bgColor; ctx.fillRect(0, 0, W, H); ctx.restore();
}
/* общая функция вывода: помещает область crop на холст W×H */
function drawExport(ctx, W, H) {
  const b = B(), c = state.crop, k = W / c.w;
  ctx.save();
  ctx.clearRect(0, 0, W, H);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  bgFill(ctx, W, H);
  ctx.translate(k * (b.w / 2 - c.x), k * (b.h / 2 - c.y));
  ctx.scale(k, k);
  ctx.rotate(rad(state.rot));
  if (state.flip) ctx.scale(-1, 1);
  ctx.drawImage(state.img, -state.iw / 2, -state.ih / 2, state.iw, state.ih);
  ctx.restore();
}

function renderView() {
  if (!state.img) return;
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const cw = view.clientWidth, ch = view.clientHeight;
  view.width = Math.max(1, Math.round(cw * dpr));
  view.height = Math.max(1, Math.round(ch * dpr));
  vctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  computeView();
  normCrop();
  vctx.clearRect(0, 0, cw, ch);

  const b = B(), s = state.view.s;

  // фото
  vctx.save();
  vctx.translate(state.view.ox, state.view.oy);
  vctx.scale(s, s);
  vctx.translate(b.w / 2, b.h / 2);
  vctx.rotate(rad(state.rot));
  if (state.flip) vctx.scale(-1, 1);
  vctx.imageSmoothingQuality = 'high';
  vctx.drawImage(state.img, -state.iw / 2, -state.ih / 2, state.iw, state.ih);
  vctx.restore();

  const r = cropRectView();

  // затемнение вне кадра
  vctx.save();
  vctx.beginPath();
  vctx.rect(0, 0, cw, ch);
  vctx.rect(r.x, r.y, r.w, r.h);
  vctx.fillStyle = 'rgba(6,8,12,.66)';
  vctx.fill('evenodd');
  vctx.restore();

  // содержимое внутри кадра поверх затемнения не нужно — рамка рисуется контуром
  vctx.save();
  vctx.beginPath(); vctx.rect(r.x, r.y, r.w, r.h); vctx.clip();
  if (state.showGrid) {
    vctx.strokeStyle = 'rgba(255,255,255,.3)'; vctx.lineWidth = 1;
    for (let i = 1; i <= 2; i++) {
      vctx.beginPath(); vctx.moveTo(r.x + r.w * i / 3, r.y); vctx.lineTo(r.x + r.w * i / 3, r.y + r.h); vctx.stroke();
      vctx.beginPath(); vctx.moveTo(r.x, r.y + r.h * i / 3); vctx.lineTo(r.x + r.w, r.y + r.h * i / 3); vctx.stroke();
    }
  }
  if (state.showSafe) {
    const zones = [[.06, .12, .88, .10], [.06, .74, .88, .20]];   // верх (имя/часы) и низ (текст/кнопки)
    vctx.fillStyle = 'rgba(255,107,107,.18)';
    vctx.strokeStyle = 'rgba(255,107,107,.85)'; vctx.lineWidth = 1.5;
    zones.forEach(z => {
      const x = r.x + r.w * z[0], y = r.y + r.h * z[1], w = r.w * z[2], h = r.h * z[3];
      vctx.fillRect(x, y, w, h); vctx.strokeRect(x, y, w, h);
    });
  }
  vctx.restore();

  // контур рамки
  vctx.save();
  vctx.strokeStyle = 'rgba(0,0,0,.6)'; vctx.lineWidth = 3; vctx.strokeRect(r.x, r.y, r.w, r.h);
  vctx.strokeStyle = '#fff'; vctx.lineWidth = 1.5; vctx.strokeRect(r.x, r.y, r.w, r.h);

  // ручки
  handles().forEach(h => {
    vctx.beginPath(); vctx.rect(h.x - 6, h.y - 6, 12, 12);
    vctx.fillStyle = '#fff'; vctx.fill();
    vctx.strokeStyle = '#7c5cff'; vctx.lineWidth = 2; vctx.stroke();
  });

  // подпись размера области — внутри рамки сверху
  const label = Math.round(state.crop.w) + ' × ' + Math.round(state.crop.h) + ' px';
  vctx.font = '600 12px ui-sans-serif,system-ui,sans-serif';
  const tw = vctx.measureText(label).width;
  let bx = clamp(r.x + r.w / 2 - tw / 2 - 8, r.x + 6, Math.max(r.x + 6, r.x + r.w - tw - 22));
  let by = clamp(r.y + 8, 6, ch - 30);
  vctx.fillStyle = 'rgba(10,12,16,.88)';
  roundRect(vctx, bx, by, tw + 16, 23, 7); vctx.fill();
  vctx.strokeStyle = 'rgba(255,255,255,.14)'; vctx.lineWidth = 1; vctx.stroke();
  vctx.fillStyle = '#e8ecf3'; vctx.textBaseline = 'middle';
  vctx.fillText(label, bx + 8, by + 12);
  vctx.restore();

  renderPreview();
  updateInfo();
}
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

function outSize() {
  const sel = $('s9-sizeSel').value;
  if (sel === 'custom') {
    return { w: clamp(parseInt($('s9-cw').value, 10) || 1080, 90, 8000),
             h: clamp(parseInt($('s9-ch').value, 10) || 1920, 160, 14000) };
  }
  if (sel === 'native') {
    const w = clamp(Math.round(state.crop.w), 90, 8000);
    return { w, h: clamp(Math.round(w / ASPECT), 160, 14000) };
  }
  const p = sel.split('x').map(Number);
  return { w: p[0], h: p[1] };
}
function renderPreview() {
  if (!state.img) return;
  const o = outSize();
  const box = $('s9-prevBox').clientWidth - 16; // b256: предпросмотр во всю ширину карточки
  const dispH = clamp(Math.round(box / (o.w / o.h)), 200, 640);
  const dispW = Math.round(dispH * (o.w / o.h));
  prev.style.width = dispW + 'px'; prev.style.height = dispH + 'px';
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  prev.width = Math.round(dispW * dpr); prev.height = Math.round(dispH * dpr);
  drawExport(pctx, prev.width, prev.height);
}
function renderPlaceholder() {
  const boxW = Math.max(180, ($('s9-prevBox').clientWidth || 320) - 16);
  const ph = Math.min(560, Math.round(boxW / ASPECT));
  const pw = Math.round(ph * ASPECT);
  prev.width = pw; prev.height = ph;
  prev.style.width = pw + 'px'; prev.style.height = ph + 'px';
  pctx.fillStyle = '#0b0e13'; pctx.fillRect(0, 0, prev.width, prev.height);
  pctx.strokeStyle = '#2a323f'; pctx.setLineDash([6, 6]);
  pctx.strokeRect(9, 9, prev.width - 18, prev.height - 18); pctx.setLineDash([]);
  pctx.fillStyle = '#5c6675'; pctx.textAlign = 'center'; pctx.textBaseline = 'middle';
  pctx.font = '700 22px ui-sans-serif,system-ui,sans-serif';
  pctx.fillText('9 : 16', prev.width / 2, prev.height / 2 - 12);
  pctx.font = '500 13px ui-sans-serif,system-ui,sans-serif';
  pctx.fillText('здесь будет предпросмотр', prev.width / 2, prev.height / 2 + 16);
}

function updateInfo() {
  const c = state.crop, o = outSize(), b = B();
  $('s9-infoCrop').textContent = Math.round(c.w) + ' × ' + Math.round(c.h) + ' px';
  $('s9-infoSrc').textContent = state.iw + ' × ' + state.ih + ' px' + (state.rot ? ' · поворот ' + state.rot + '°' : '');
  $('s9-infoOut').textContent = o.w + ' × ' + o.h + ' px · ' +
    (state.fmt === 'image/png' ? 'PNG' : state.fmt === 'image/jpeg' ? 'JPG' : 'WebP');
  const z = Math.round(b.w / c.w * 100);
  $('s9-zoomRange').value = String(clamp(z, 5, 600));
  $('s9-zoomVal').textContent = 'зум ×' + (z / 100).toFixed(2).replace(/\.?0+$/, '');
  $('s9-rotVal').textContent = state.rot + '°';
  $('s9-rotRange').value = String(state.rot);
  $('s9-dlBtn').disabled = false;
  $('s9-dlFabTxt').textContent = 'Скачать ' + o.w + '×' + o.h;
  updateNameHint();
}

/* =========================================================================
   Загрузка
   ========================================================================= */
function onImageReady(im, name, w, h) {
  state.img = im; state.name = name; state.iw = w; state.ih = h;
  if (!state.baseNameDirty) { state.baseName = name; $('s9-baseName').value = name; }
  state.rot = 0; state.flip = false;
  fitInside();
  $('s9-empty').classList.add('hide');
  $('s9-stageHint').style.display = 'block';
  $('s9-dlFab').style.display = 'inline-flex';
  $('s9-flip').classList.remove('on');
  resizeStage(); renderView();
}
function setImageFromSrc(src, name) {
  return new Promise((res, rej) => {
    const im = new Image();
    im.onload = () => { onImageReady(im, name, im.naturalWidth, im.naturalHeight); res(im); };
    im.onerror = () => rej(new Error('Не удалось декодировать изображение'));
    im.src = src;
  });
}
function loadBlob(blob, name) {
  if (!blob || !blob.type || !blob.type.startsWith('image/')) { urlNote('Это не изображение', 'err'); return; }
  imgTainted = false; // b255: blob-загрузка всегда «чистая»
  if (typeof createImageBitmap === 'function') {
    createImageBitmap(blob).then(bmp => onImageReady(bmp, name, bmp.width, bmp.height))
      .catch(() => urlNote('Не удалось прочитать изображение (повреждённый файл?)', 'err'));
  } else {
    const fr = new FileReader();
    fr.onload = () => setImageFromSrc(fr.result, name).catch(() => urlNote('Не удалось прочитать файл', 'err'));
    fr.readAsDataURL(blob);
  }
}
let imgTainted = false; // b255: картинка загружена без CORS — холст «замаран»
function loadViaImg(src, name, cross) {
  return new Promise((res, rej) => {
    const im = new Image();
    if (cross) im.crossOrigin = 'anonymous';
    im.onload = () => { imgTainted = !cross; onImageReady(im, name, im.naturalWidth, im.naturalHeight); res(im); };
    im.onerror = () => rej(new Error('img fail'));
    im.src = src;
  });
}
function loadFile(file) {
  if (!file) return;
  imgTainted = false;
  loadBlob(file, (file.name || 'image').replace(/\.[^.]+$/, ''));
}
function urlNote(t, cls, sticky) {
  const n = $('s9-urlNote');
  if (!t) { n.className = 'note'; n.textContent = ''; return; }
  n.className = 'note show ' + (cls || '');
  n.textContent = t;
  if (!sticky) { clearTimeout(n._t); n._t = setTimeout(() => urlNote(''), cls === 'err' ? 9000 : 4000); }
}
const PROXIES = [
  u => 'https://images.weserv.nl/?url=' + encodeURIComponent(u.replace(/^https?:\/\//, '')), // b255: image-прокси с CORS
  u => 'https://corsproxy.io/?url=' + encodeURIComponent(u),
  u => 'https://api.allorigins.win/raw?url=' + encodeURIComponent(u),
  u => 'https://api.codetabs.com/v1/proxy/?quest=' + encodeURIComponent(u)
];
function fetchWithTimeout(url, ms) {
  const ctl = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const tm = ctl ? setTimeout(() => ctl.abort(), ms) : null;
  return fetch(url, { mode: 'cors', credentials: 'omit', signal: ctl ? ctl.signal : undefined })
    .then(r => { if (tm) clearTimeout(tm); return r; }, e => { if (tm) clearTimeout(tm); throw e; });
}
async function fetchUrl(raw) {
  const u = String(raw || '').trim();
  if (!u) { urlNote('Введите ссылку на изображение', 'err'); return; }
  if (!/^https?:\/\//i.test(u)) { urlNote('Ссылка должна начинаться с http:// или https://', 'err'); return; }
  $('s9-urlBtn').disabled = true;
  const nm = (u.split('/').pop() || 'image').split('?')[0].replace(/\.[^.]+$/, '').slice(0, 40) || 'image';
  try {
    // 1) напрямую
    try {
      urlNote('Загружаю напрямую…', '', true);
      const r = await fetchWithTimeout(u, 10000);
      if (r.ok) {
        const blob = await r.blob();
        if (blob.type.startsWith('image/')) { loadBlob(blob, nm); urlNote('Готово: изображение загружено напрямую', 'ok'); return; }
      }
    } catch (_) { /* идём дальше */ }
    // 2) как изображение с CORS (чистый холст, без прокси)
    try {
      urlNote('Пробую загрузить как изображение…', '', true);
      await loadViaImg(u, nm, true);
      urlNote('Готово: изображение загружено', 'ok');
      return;
    } catch (_) { /* идём дальше */ }
    // 3) прокси с таймаутом на каждый
    if ($('s9-proxyChk').checked) {
      for (const mk of PROXIES) {
        try {
          urlNote('Напрямую не отдаёт — пробую через прокси…', '', true);
          const r = await fetchWithTimeout(mk(u), 12000);
          if (r.ok) {
            const blob = await r.blob();
            if (blob.type.startsWith('image/')) { loadBlob(blob, nm); urlNote('Готово: загружено через прокси', 'ok'); return; }
          }
        } catch (_) { /* следующий прокси */ }
      }
    }
    // 4) показ без CORS: кадрирование работает, экспорт может быть запрещён
    try {
      await loadViaImg(u, nm, false);
      imgTainted = true;
      urlNote('Картинка показана без CORS: кадрирование работает, но экспорт может быть запрещён сервером — тогда скачайте файл и загрузите вручную.', 'err', true);
      return;
    } catch (_) { /* совсем никак */ }
    urlNote('Не вышло: сервер блокирует доступ к файлу. Самый надёжный способ — скачать картинку и перетащить её в окно (или Ctrl+V из буфера).', 'err', true);
  } finally {
    $('s9-urlBtn').disabled = false;
  }
}

/* =========================================================================
   Экспорт
   ========================================================================= */
const pad4 = n => String(Math.max(0, Math.floor(n))).padStart(4, '0');
function loadCounter() {
  try { const v = parseInt(localStorage.getItem('story916.counter'), 10); return (isFinite(v) && v >= 0) ? v : 0; }
  catch (_) { return 0; }
}
function saveCounter() { try { localStorage.setItem('story916.counter', String(state.counter)); } catch (_) {} }

function fileExt() { return state.fmt === 'image/png' ? 'png' : state.fmt === 'image/jpeg' ? 'jpg' : 'webp'; }
function baseNameSan() {
  const raw = (state.baseName && state.baseName.trim()) ? state.baseName.trim() : (state.name || 'story');
  return String(raw).replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 60) || 'story';
}
function nextFilename() {
  const ext = fileExt();
  const n = pad4(state.counter);
  if (state.nameMode === 'num') return n + '.' + ext;
  const base = baseNameSan();
  return state.nameMode === 'name_num' ? base + '_' + n + '.' + ext : n + '_' + base + '.' + ext;
}
function updateNameHint() {
  $('s9-nextName').textContent = nextFilename();
  $('s9-resetCounter').textContent = '⟲ Счётчик: ' + pad4(state.counter);
}

function download() {
  if (!state.img) return;
  const o = outSize();
  const c = document.createElement('canvas');
  c.width = o.w; c.height = o.h;
  drawExport(c.getContext('2d'), o.w, o.h);
  const q = state.fmt === 'image/png' ? undefined : state.quality;
  const fname = nextFilename();
  try {
  c.toBlob(blob => {
    if (!blob) { toast('Браузер не смог создать файл — попробуйте другой формат или размер', 'err'); return; }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = fname;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    state.counter++; saveCounter(); updateNameHint();
    toast('Сохранено: ' + fname + ' · следующий будет ' + nextFilename() + ' · ' +
      (blob.size / 1024 < 1024 ? (blob.size / 1024).toFixed(0) + ' КБ' : (blob.size / 1048576).toFixed(2) + ' МБ'), 'ok');
  }, state.fmt, q);
  } catch (e) { // b255: tainted-холст (CORS) — toBlob бросает SecurityError
    toast('Сервер изображения запрещает экспорт (CORS). Скачайте файл и загрузите его через «Выбрать файл».', 'err');
  }
}
let toastT;
function toast(text, cls) {
  const n = $('s9-expNote');
  n.className = 'note show ' + (cls || 'ok');
  n.textContent = text;
  clearTimeout(toastT);
  toastT = setTimeout(() => { n.className = 'note'; }, 6000);
}

/* =========================================================================
   Мышь / палец: перемещение и изменение рамки
   ========================================================================= */
function handles() {
  const r = cropRectView();
  return [
    { id: 'nw', x: r.x,         y: r.y,         cur: 'nwse-resize' },
    { id: 'ne', x: r.x + r.w,   y: r.y,         cur: 'nesw-resize' },
    { id: 'se', x: r.x + r.w,   y: r.y + r.h,   cur: 'nwse-resize' },
    { id: 'sw', x: r.x,         y: r.y + r.h,   cur: 'nesw-resize' },
    { id: 'n',  x: r.x + r.w/2, y: r.y,         cur: 'ns-resize' },
    { id: 's',  x: r.x + r.w/2, y: r.y + r.h,   cur: 'ns-resize' },
    { id: 'w',  x: r.x,         y: r.y + r.h/2, cur: 'ew-resize' },
    { id: 'e',  x: r.x + r.w,   y: r.y + r.h/2, cur: 'ew-resize' }
  ];
}
function hitHandle(px, py) {
  let best = null, bd = 18;
  handles().forEach(h => { const d = Math.hypot(h.x - px, h.y - py); if (d <= bd) { bd = d; best = h; } });
  return best;
}
function inRect(px, py) {
  const r = cropRectView();
  return px >= r.x && px <= r.x + r.w && py >= r.y && py <= r.y + r.h;
}

let drag = null, pinch = null;
const pointers = new Map();
const local = e => { const r = view.getBoundingClientRect(); return { px: e.clientX - r.left, py: e.clientY - r.top }; };

view.addEventListener('pointerdown', e => {
  if (!state.img) return;
  view.setPointerCapture(e.pointerId);
  const p = local(e);
  pointers.set(e.pointerId, p);

  if (pointers.size === 2) {                       // пинч = масштаб кадра
    const [a, b] = [...pointers.values()];
    const mid = viewToQ((a.px + b.px) / 2, (a.py + b.py) / 2);
    pinch = { d: Math.max(1, Math.hypot(a.px - b.px, a.py - b.py)), w0: state.crop.w, anchor: mid };
    drag = null; e.preventDefault(); return;
  }

  const h = hitHandle(p.px, p.py);
  if (e.shiftKey || e.altKey) {
    drag = { mode: 'panimg', start: p, crop: { ...state.crop } };        // двигаем фото под рамкой
  } else if (h) {
    drag = { mode: 'resize', id: h.id, start: p, crop: { ...state.crop } };
  } else if (inRect(p.px, p.py)) {
    drag = { mode: 'move', start: p, crop: { ...state.crop } };
  } else {                                                               // клик мимо — перенести рамку сюда
    const q = viewToQ(p.px, p.py);
    state.crop.x = q.x - state.crop.w / 2; state.crop.y = q.y - state.crop.h / 2;
    normCrop(); renderView();
    drag = { mode: 'move', start: p, crop: { ...state.crop } };
  }
  e.preventDefault();
});

view.addEventListener('pointermove', e => {
  const p = local(e);
  if (pointers.has(e.pointerId)) pointers.set(e.pointerId, p);

  if (pinch && pointers.size >= 2) {
    const [a, b] = [...pointers.values()];
    const d = Math.hypot(a.px - b.px, a.py - b.py);
    const k = clamp(pinch.d / Math.max(1, d), 0.1, 10);
    zoomAround(pinch.anchor, pinch.w0 * k);
    return;
  }
  if (!drag) {
    const h = state.img ? hitHandle(p.px, p.py) : null;
    view.style.cursor = h ? h.cur : (state.img && inRect(p.px, p.py) ? 'move' : 'crosshair');
    return;
  }

  const s = state.view.s, c = drag.crop;
  const dxq = (p.px - drag.start.px) / s, dyq = (p.py - drag.start.py) / s;

  if (drag.mode === 'move') {
    state.crop.x = c.x + dxq; state.crop.y = c.y + dyq;
    normCrop(); renderView(); return;
  }
  if (drag.mode === 'panimg') {                       // рамка на месте, фото едет под ней
    state.crop.x = c.x - dxq; state.crop.y = c.y - dyq;
    normCrop(); renderView(); return;
  }
  /* resize */
  const b = B();
  const id = drag.id;
  let { x, y, w, h } = c;
  const minW = 9;
  const cursor = viewToQ(p.px, p.py);
  if (id === 'n' || id === 's') {
    const fixedY = id === 's' ? y : y + h;            // противоположная грань
    let nh = Math.max(minW / ASPECT, Math.abs(cursor.y - fixedY));
    let nw = nh * ASPECT;
    state.crop = { x: x + w / 2 - nw / 2, y: id === 's' ? fixedY : fixedY - nh, w: nw, h: nh };
  } else if (id === 'w' || id === 'e') {
    const fixedX = id === 'e' ? x : x + w;
    let nw = Math.max(minW, Math.abs(cursor.x - fixedX));
    let nh = nw / ASPECT;
    state.crop = { x: id === 'e' ? fixedX : fixedX - nw, y: y + h / 2 - nh / 2, w: nw, h: nh };
  } else {
    const fx = (id === 'ne' || id === 'se') ? x : x + w;
    const fy = (id === 'sw' || id === 'se') ? y : y + h;
    let nw = Math.max(minW, Math.abs(cursor.x - fx));
    let nh = Math.max(minW / ASPECT, Math.abs(cursor.y - fy));
    let avg = Math.max(nw, nh * ASPECT);
    nw = avg; nh = avg / ASPECT;
    const sx = (id === 'ne' || id === 'se') ? 1 : -1;
    const sy = (id === 'sw' || id === 'se') ? 1 : -1;
    state.crop = { x: sx > 0 ? fx : fx - nw, y: sy > 0 ? fy : fy - nh, w: nw, h: nh };
  }
  normCrop(); renderView();
});

function endPtr(e) {
  pointers.delete(e.pointerId);
  if (pointers.size < 2) pinch = null;
  if (pointers.size === 0) drag = null;
}
view.addEventListener('pointerup', endPtr);
view.addEventListener('pointercancel', endPtr);
window.addEventListener('blur', () => { pointers.clear(); pinch = null; drag = null; });

function zoomAround(anchorQ, newW) {
  const b = B();
  newW = clamp(newW, 8, Math.max(b.w, b.h) * 8);
  const ratio = newW / state.crop.w;
  state.crop.w = newW; state.crop.h = newW / ASPECT;
  state.crop.x = anchorQ.x + (state.crop.x - anchorQ.x) * ratio;
  state.crop.y = anchorQ.y + (state.crop.y - anchorQ.y) * ratio;
  normCrop(); renderView();
}
view.addEventListener('wheel', e => {
  if (!state.img) return;
  e.preventDefault();
  const p = local(e);
  zoomAround(viewToQ(p.px, p.py), state.crop.w * Math.exp(e.deltaY * 0.0016));
}, { passive: false });

/* =========================================================================
   Контролы
   ========================================================================= */
$('s9-zoomRange').addEventListener('input', e => {
  const z = parseInt(e.target.value, 10) || 100;
  const b = B();
  const cx = state.crop.x + state.crop.w / 2, cy = state.crop.y + state.crop.h / 2;
  state.crop.w = clamp(b.w * 100 / z, 8, Math.max(b.w, b.h) * 8);
  state.crop.h = state.crop.w / ASPECT;
  state.crop.x = cx - state.crop.w / 2; state.crop.y = cy - state.crop.h / 2;
  normCrop(); renderView();
});
$('s9-rotRange').addEventListener('input', e => {
  const keep = { ...state.crop }, prevB = B();
  state.rot = parseInt(e.target.value, 10) || 0;
  keepCropOnRotate(keep, prevB); renderView();
});
$('s9-rotL').onclick = () => { setRot(state.rot - 90); };
$('s9-rotR').onclick = () => { setRot(state.rot + 90); };
function setRot(r) {
  r = ((r + 180) % 360 + 360) % 360 - 180;
  const keep = { ...state.crop }, prevB = B();
  state.rot = r;
  keepCropOnRotate(keep, prevB); renderView();
}
$('s9-flip').onclick = () => {
  const b = B();
  state.flip = !state.flip;
  state.crop.x = b.w - state.crop.w - state.crop.x;      // та же область фото, зеркально
  $('s9-flip').classList.toggle('on', state.flip);
  normCrop(); renderView();
};
$('s9-fitCover').onclick = () => { fitInside(); renderView(); };
$('s9-fitContain').onclick = () => { fitWhole(); renderView(); };
$('s9-center').onclick = () => { centerCrop(); renderView(); };
$('s9-resetAll').onclick = () => { state.rot = 0; state.flip = false; $('s9-flip').classList.remove('on'); fitInside(); renderView(); };
$('s9-gridChk').onchange = e => { state.showGrid = e.target.checked; renderView(); };
$('s9-safeChk').onchange = e => { state.showSafe = e.target.checked; renderView(); };

$('s9-fmtSeg').addEventListener('click', e => {
  const btn = e.target.closest('button'); if (!btn) return;
  [...$('s9-fmtSeg').children].forEach(x => x.classList.remove('on'));
  btn.classList.add('on');
  state.fmt = btn.dataset.fmt;
  $('s9-qWrap').style.display = state.fmt === 'image/png' ? 'none' : 'block';
  renderPreview(); updateInfo(); updateNameHint();
});
$('s9-qRange').addEventListener('input', e => { state.quality = e.target.value / 100; $('s9-qVal').textContent = e.target.value + '%'; });
$('s9-sizeSel').addEventListener('change', e => {
  $('s9-customWrap').style.display = e.target.value === 'custom' ? 'block' : 'none';
  renderPreview(); updateInfo();
});
['s9-cw', 's9-ch'].forEach(id => $(id).addEventListener('input', () => { renderPreview(); updateInfo(); }));
$('s9-bgMode').addEventListener('change', e => { state.bgMode = e.target.value; renderPreview(); });
$('s9-bgColor').addEventListener('input', e => {
  state.bgColor = e.target.value;
  if (state.bgMode === 'transparent') { state.bgMode = 'color'; $('s9-bgMode').value = 'color'; }
  renderPreview();
});
$('s9-dlBtn').onclick = download;
$('s9-dlFab').onclick = download;
$('s9-nameMode').addEventListener('change', e => { state.nameMode = e.target.value; updateNameHint(); });
$('s9-baseName').addEventListener('input', e => {
  state.baseName = e.target.value;
  state.baseNameDirty = e.target.value.trim() !== '';
  updateNameHint();
});
$('s9-resetCounter').onclick = () => {
  state.counter = 0; saveCounter(); updateNameHint();
  toast('Счётчик обнулён: следующий файл — ' + nextFilename(), 'ok');
};

$('s9-pickBtn').onclick = $('s9-pickBtn2').onclick = () => $('s9-fileInput').click();
$('s9-fileInput').onchange = e => { loadFile(e.target.files[0]); e.target.value = ''; };
$('s9-urlBtn').onclick = () => fetchUrl($('s9-urlInput').value);
$('s9-urlInput').addEventListener('keydown', e => { if (e.key === 'Enter') fetchUrl($('s9-urlInput').value); });

/* демо-картинка (рисуется на canvas, сеть не нужна) */
$('s9-demoBtn').onclick = () => {
  const c = document.createElement('canvas'); c.width = 1600; c.height = 1000;
  const g = c.getContext('2d');
  const gr = g.createLinearGradient(0, 0, 1600, 1000);
  gr.addColorStop(0, '#2b5876'); gr.addColorStop(.5, '#4e4376'); gr.addColorStop(1, '#e96443');
  g.fillStyle = gr; g.fillRect(0, 0, 1600, 1000);
  for (let i = 0; i < 26; i++) {
    g.beginPath();
    g.arc(Math.random() * 1600, Math.random() * 1000, 20 + Math.random() * 160, 0, 7);
    g.fillStyle = 'rgba(255,255,255,' + (0.03 + Math.random() * 0.09).toFixed(3) + ')'; g.fill();
  }
  g.fillStyle = 'rgba(255,255,255,.9)'; g.font = '700 64px ui-sans-serif,system-ui,sans-serif';
  g.textAlign = 'center'; g.fillText('ДЕМО 1600 × 1000', 800, 520);
  c.toBlob(b => loadBlob(b, 'demo'), 'image/png');
};

/* drag & drop во всё окно */
let dragDepth = 0;
window.addEventListener('dragenter', e => { if (!rootVisible()) return; e.preventDefault(); dragDepth++; $('s9-stageWrap').classList.add('drop-on'); });
window.addEventListener('dragover', e => { if (!rootVisible()) return; e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; });
window.addEventListener('dragleave', e => { if (!rootVisible()) return; e.preventDefault(); if (--dragDepth <= 0) { dragDepth = 0; $('s9-stageWrap').classList.remove('drop-on'); } });
window.addEventListener('drop', e => {
  if (!rootVisible()) return;
  e.preventDefault(); dragDepth = 0; $('s9-stageWrap').classList.remove('drop-on');
  const dt = e.dataTransfer; if (!dt) return;
  if (dt.files && dt.files.length) { loadFile(dt.files[0]); return; }
  const u = dt.getData('text/uri-list') || dt.getData('text/plain');
  if (u && /^https?:\/\//i.test(u.trim())) { $('s9-urlInput').value = u.trim(); fetchUrl(u.trim()); }
});

/* вставка из буфера */
window.addEventListener('paste', e => {
  if (!rootVisible()) return;
  const cd = e.clipboardData; if (!cd) return;
  for (const it of cd.items || []) {
    if (it.kind === 'file' && it.type.startsWith('image/')) {
      const f = it.getAsFile(); if (f) { loadFile(f); e.preventDefault(); return; }
    }
  }
  const t = (cd.getData('text') || '').trim();
  if (/^https?:\/\//i.test(t)) { $('s9-urlInput').value = t; fetchUrl(t); e.preventDefault(); }
});

/* клавиатура */
window.addEventListener('keydown', e => {
  if (!rootVisible()) return;
  if (!state.img) return;
  const tag = (e.target.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'select' || tag === 'textarea') return;
  const step = (e.shiftKey ? 40 : 8) * clamp(state.crop.w / 900, .3, 4);
  switch (e.key) {
    case 'ArrowLeft':  state.crop.x -= step; e.preventDefault(); break;
    case 'ArrowRight': state.crop.x += step; e.preventDefault(); break;
    case 'ArrowUp':    state.crop.y -= step; e.preventDefault(); break;
    case 'ArrowDown':  state.crop.y += step; e.preventDefault(); break;
    case '+': case '=': zoomAround({ x: state.crop.x + state.crop.w / 2, y: state.crop.y + state.crop.h / 2 }, state.crop.w / 1.1); return;
    case '-': case '_': zoomAround({ x: state.crop.x + state.crop.w / 2, y: state.crop.y + state.crop.h / 2 }, state.crop.w * 1.1); return;
    case '0': state.rot = 0; state.flip = false; $('s9-flip').classList.remove('on'); fitInside(); renderView(); return;
    case 'Enter': if (e.ctrlKey || e.metaKey) { download(); return; } break;
    default: return;
  }
  normCrop(); renderView();
});

/* =========================================================================
   Раскладка
   ========================================================================= */
function resizeStage() {
  const wrap = $('s9-stageWrap');
  const w = Math.max(280, wrap.clientWidth - 28);
  const stretched = wrap.clientHeight - 28; // b257: карточка холста выровнена по высоте предпросмотра
  const h = Math.max(320, stretched > 340 ? stretched : Math.min(window.innerHeight - 180, Math.round(w * 0.66)));
  view.style.width = w + 'px'; view.style.height = h + 'px';
  if (state.img) renderView(); else renderPlaceholder();
}
let rt;
window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(resizeStage, 90); });

state.counter = loadCounter();
updateNameHint();
resizeStage();
renderPlaceholder();
window.s9OnShow = function () { resizeStage(); };
window.s9Toggle = function (h) { const c = h.closest('.card'); if (c) c.classList.toggle('closed'); };

})();