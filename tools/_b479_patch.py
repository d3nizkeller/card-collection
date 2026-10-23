#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b479: кнопка «Скачать готовую карточку» — PNG со всем лицом карты.

Заявка владельца: «добавь кнопку скачать готовую карточку с нумерацией и всем
остальным».

Разбор
------
Готового изображения карты в проекте нет: лицо собирается из DOM-слоёв поверх
арта (b475–b478: скрытие, место, расположение, форма и размер статов). Владелец
хочет получать файл карты таким, каким его видит игрок: с номером #N,
редкостью, именем, описанием и статами.

Лечение
-------
1. nxCardFaceCanvas(card, img, W, H) рисует лицо карты в canvas 9:16:
   * арт с тем же кадрированием, что в CSS (cardArtStyle: object-position +
     translate/scale из artZoom/artPosX/artPosY), поверх — тот же градиент
     from-slate-950/85 via-/5 to-/20;
   * рамка цвета редкости (RAR_COLORS) и скруглённые углы;
   * бейджи: слева #N (номер карты в паке, getCardLocalNumber), справа — ♪
     (своя музыка), ×N (копии) и редкость;
   * имя и описание (до 2 строк, перенос по словам, выравнивание по L.align)
     в тех же зонах верх/низ, что в cardTextZones, с тенью текста;
   * статы — те же чипы, что на экране: форма b477 (квадрат/кружок/ромб/
     звезда/шестиугольник/щит) рисуется silhouette-слоями (цветной кант
     currentColor + тёмная подложка), размер b478 (--k = 1/1.3/1.65), место и
     расположение b477 (низ/верх в потоке, лево/право у кромки, ряд/столбик);
     иконки — векторные молния и сердце, без зависимости от шрифтов/FA;
   * «Скрыть» b475 уважается: чего нет на карте — того нет и в файле.
   Эффекты/блик и ауру в файл не кладём: это живые CSS-анимации, у них нет
   статичного кадра (об этом сказано в комментарии и в FIXES).
2. downloadCardPng(cardId): арт тянется fetch→blob→objectURL, поэтому canvas
   не tainted даже с внешним хостом с CORS; без CORS/без арта — понятный тост
   с советом залить картинку на GitHub кнопкой «Загрузить с устройства».
   Файл: card_001_Имя.png (имя санитизируется), скачивается обычным <a download>.
3. Кнопки: в форме Студии под живым предпросмотром («Скачать готовую карточку
   (PNG)», downloadCardPngOfForm — берёт сохранённую карту редактирования) и в
   каждой строке списков Студии (иконка скачивания рядом с «Редактировать»,
   только владельцу: у гостей там по-прежнему плашка «просмотр»).

app.js и index.html менялись — тег сборки nxmob222 -> nxmob223.

Проверка/применение:
    python3 tools/_b479_patch.py --check
    python3 tools/_b479_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob222'
TAG_NEW = 'nxmob223'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

# --------------------------------------------------------------------------- #
# assets/app.js — экспорт лица карты в PNG
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            applyCardAura(document.getElementById('card-preview-aura'), fake, 'aura-preview');
            try { nxCardPreviewBind(); } catch (e) {} // b460: колесо/драг/даблклик по превью
        }''',
              r'''            applyCardAura(document.getElementById('card-preview-aura'), fake, 'aura-preview');
            try { nxCardPreviewBind(); } catch (e) {} // b460: колесо/драг/даблклик по превью
        }

        // ============ b479: ЭКСПОРТ ГОТОВОЙ КАРТОЧКИ В PNG ============
        // Владелец: «кнопка скачать готовую карточку с нумерацией и всем
        // остальным». Файл = лицо карты таким, каким его видит игрок: арт с
        // кадрированием, #N, редкость, копии, ♪, имя, описание и статы со ВСЕМИ
        // настройками b475–b478 (скрытие, место, расположение, форма, размер).
        // Эффекты/блик и ауру не экспортируем: это живые CSS-анимации, статики
        // у них нет. Рисование — без зависимостей от шрифтов и FA: иконки
        // статов векторные, текст — Inter/sans-serif с фолбэком.
        const NX_STAT_POLYS = {
            diamond: [50, 0, 100, 50, 50, 100, 0, 50],
            star: [50, 0, 61, 35, 98, 35, 68, 57, 79, 91, 50, 70, 21, 91, 32, 57, 2, 35, 39, 35],
            hex: [25, 0, 75, 0, 100, 50, 75, 100, 25, 100, 0, 50],
            shield: [0, 0, 100, 0, 100, 68, 50, 100, 0, 68]
        };
        function nxCardExportName(card) {
            const n = getCardLocalNumber(card);
            const nm = String(card.name || '').replace(/[^\wа-яёА-ЯЁ\- ]/g, '').trim().replace(/\s+/g, '_').slice(0, 40);
            return 'card_' + n + (nm ? '_' + nm : '') + '.png';
        }
        function nxArtBlobUrl(url) {
            // fetch→blob→objectURL: canvas не tainted даже с внешним хостом (если
            // тот отдаёт CORS), а_same-origin media/ прилетает из кэша мгновенно
            return fetch(url, { mode: 'cors' }).then(r => {
                if (!r.ok) throw new Error('арт не ответил (' + r.status + ')');
                return r.blob();
            }).then(b => URL.createObjectURL(b));
        }
        function nxPolyPath(g, x, y, w, h, pts, inset) {
            g.beginPath();
            for (let i = 0; i < pts.length; i += 2) {
                let px = x + pts[i] / 100 * w, py = y + pts[i + 1] / 100 * h;
                if (inset) {
                    px = x + w / 2 + (px - x - w / 2) * Math.max(0, 1 - inset * 2 / w);
                    py = y + h / 2 + (py - y - h / 2) * Math.max(0, 1 - inset * 2 / h);
                }
                if (i) g.lineTo(px, py); else g.moveTo(px, py);
            }
            g.closePath();
        }
        function nxDrawBolt(g, x, y, s) {
            g.beginPath();
            g.moveTo(x + s * 0.58, y); g.lineTo(x + s * 0.16, y + s * 0.56); g.lineTo(x + s * 0.44, y + s * 0.56);
            g.lineTo(x + s * 0.34, y + s); g.lineTo(x + s * 0.84, y + s * 0.4); g.lineTo(x + s * 0.52, y + s * 0.4);
            g.closePath(); g.fill();
        }
        function nxDrawHeart(g, x, y, s) {
            g.beginPath();
            g.moveTo(x + s / 2, y + s * 0.92);
            g.bezierCurveTo(x - s * 0.14, y + s * 0.42, x + s * 0.06, y - s * 0.12, x + s / 2, y + s * 0.24);
            g.bezierCurveTo(x + s * 0.94, y - s * 0.12, x + s * 1.14, y + s * 0.42, x + s / 2, y + s * 0.92);
            g.closePath(); g.fill();
        }
        // один чип стата: цветной кант-силуэт + тёмная подложка + иконка + число
        function nxDrawChip(g, x, y, color, kind, val, k, u, shape) {
            const fs = 10 * u * k, padX = 8 * u * k, padY = 3 * u * k, ic = 9 * u * k, inset = 2 * u * k;
            g.font = '700 ' + fs + 'px Inter, sans-serif';
            const tw = g.measureText(String(val)).width;
            const w = padX * 2 + ic + 4 * u * k + tw, h = padY * 2 + fs * 1.25;
            const sil = ins => {
                if (shape === 'circle') { g.beginPath(); g.ellipse(x + w / 2, y + h / 2, Math.max(1, w / 2 - ins), Math.max(1, h / 2 - ins), 0, 0, Math.PI * 2); return; }
                if (NX_STAT_POLYS[shape]) { nxPolyPath(g, x, y, w, h, NX_STAT_POLYS[shape], ins); return; }
                roundRectCanvas(g, x + ins, y + ins, w - ins * 2, h - ins * 2, Math.max(2, 6 * u * k - ins));
            };
            g.save(); sil(0); g.globalAlpha = .45; g.fillStyle = color; g.fill(); g.restore();
            sil(inset); g.fillStyle = 'rgba(2,6,23,.9)'; g.fill();
            g.fillStyle = color;
            if (kind === 'atk') nxDrawBolt(g, x + padX, y + (h - ic) / 2, ic); else nxDrawHeart(g, x + padX, y + (h - ic) / 2, ic);
            g.textAlign = 'left'; g.textBaseline = 'middle';
            g.fillText(String(val), x + padX + ic + 4 * u * k, y + h / 2 + fs * 0.06);
            return { w: w, h: h };
        }
        function nxCardFaceCanvas(card, img, W, H) {
            const L = cardLayoutOf(card);
            const cv = document.createElement('canvas');
            cv.width = W; cv.height = H;
            const g = cv.getContext('2d');
            if (!g) throw new Error('canvas недоступен');
            const u = W / 360, p = 16 * u, R = W * 0.055;
            const k = L.statsSize === 'lg' ? 1.65 : (L.statsSize === 'md' ? 1.3 : 1); // b478: тот же --k
            const st = getCardStats(card);
            g.save();
            roundRectCanvas(g, 0, 0, W, H, R); g.clip();
            // --- арт с кадрированием владельца (как cardArtStyle в CSS) ---
            g.fillStyle = '#0b1220'; g.fillRect(0, 0, W, H);
            if (img && (img.naturalWidth || img.width)) {
                const iw = img.naturalWidth || img.width, ih = img.naturalHeight || img.height;
                const c = Math.max(W / iw, H / ih);
                const dw = iw * c, dh = ih * c;
                const dx = -(dw - W) * (50 + L.artPosX / 2) / 100, dy = -(dh - H) * (50 + L.artPosY / 2) / 100;
                const s = L.artZoom / 100, mx = (s - 1) * 50;
                const tx = (L.artPosX / 100) * mx / 100 * W, ty = (L.artPosY / 100) * mx / 100 * H;
                g.save();
                g.translate(W / 2 + tx, H / 2 + ty); g.scale(s, s);
                g.drawImage(img, dx - W / 2, dy - H / 2, dw, dh);
                g.restore();
            }
            const lg = g.createLinearGradient(0, H, 0, 0);
            lg.addColorStop(0, 'rgba(2,6,23,.85)'); lg.addColorStop(.5, 'rgba(2,6,23,.05)'); lg.addColorStop(1, 'rgba(2,6,23,.2)');
            g.fillStyle = lg; g.fillRect(0, 0, W, H);
            // --- служебные бейджи: #N слева; ♪, ×N, редкость справа ---
            const badgeH = 20 * u, br = 5 * u;
            const pill = (txt, font, fg, bg, strokeCol) => {
                g.font = font;
                const tw = g.measureText(txt).width;
                const w = tw + 16 * u, h = badgeH;
                return { txt, font, fg, bg, strokeCol, w, h, tw };
            };
            const drawPill = (b, x, y) => {
                g.font = b.font;
                roundRectCanvas(g, x, y, b.w, b.h, br);
                g.fillStyle = b.bg; g.fill();
                if (b.strokeCol) { g.strokeStyle = b.strokeCol; g.lineWidth = u; g.stroke(); }
                g.fillStyle = b.fg; g.textAlign = 'left'; g.textBaseline = 'middle';
                g.fillText(b.txt, x + 8 * u, y + b.h / 2 + u);
            };
            const numB = pill('#' + getCardLocalNumber(card), '700 ' + 12 * u + 'px ui-monospace, SFMono-Regular, monospace', '#e2e8f0', 'rgba(2,6,23,.7)', null);
            drawPill(numB, p, p);
            const rarLabel = String(RARITY_LABELS_RU[card.rarity] || card.rarity).toUpperCase();
            const right = [];
            if (card.musicUrl) right.push(pill('♪', '700 ' + 11 * u + 'px Inter, sans-serif', '#f0abfc', 'rgba(217,70,239,.12)', 'rgba(217,70,239,.35)'));
            const copies = cardCopies(card.id);
            if (copies > 1) right.push(pill('×' + copies, '900 ' + 10 * u + 'px Inter, sans-serif', '#fde68a', 'rgba(245,158,11,.25)', 'rgba(251,191,36,.4)'));
            right.push(pill(rarLabel, '700 ' + 10 * u + 'px Inter, sans-serif', RAR_COLORS[card.rarity] || '#e2e8f0', 'rgba(15,23,42,.8)', 'rgba(51,65,85,1)'));
            let rx = W - p;
            for (let i = right.length - 1; i >= 0; i--) { rx -= right[i].w; drawPill(right[i], rx, p); rx -= 4 * u; }
            // --- текстовые блоки и статы: те же зоны, что в cardTextZones ---
            const shadow = fn => { g.save(); g.shadowColor = 'rgba(0,0,0,.7)'; g.shadowBlur = 6 * u; g.shadowOffsetY = 2 * u; fn(); g.restore(); };
            const alignX = () => L.align === 'center' ? W / 2 : (L.align === 'right' ? W - p : p);
            const nameBlock = cardNameShown(L) ? {
                h: 20 * u,
                draw: y => shadow(() => {
                    g.font = '800 ' + 16 * u + 'px Inter, sans-serif';
                    g.fillStyle = '#ffffff'; g.textAlign = L.align === 'center' ? 'center' : (L.align === 'right' ? 'right' : 'left');
                    g.textBaseline = 'middle';
                    g.fillText(cardDisplayName(card), alignX(), y + 10 * u);
                })
            } : null;
            let descLines = [];
            if (L.descPos !== 'hide' && String(card.description || '').trim()) {
                g.font = '400 ' + 12 * u + 'px Inter, sans-serif';
                const words = String(card.description).split(/\s+/);
                let line = '';
                for (const wd of words) {
                    const t = line ? line + ' ' + wd : wd;
                    if (g.measureText(t).width > W - p * 2 && line) { descLines.push(line); line = wd; } else line = t;
                    if (descLines.length === 2) break;
                }
                if (descLines.length < 2 && line) descLines.push(line);
                else if (descLines.length === 2 && line && descLines[1] !== line) descLines[1] = line.length > descLines[1].length ? descLines[1] : line;
            }
            const descBlock = descLines.length ? {
                h: descLines.length * 16 * u,
                draw: y => shadow(() => {
                    g.font = '400 ' + 12 * u + 'px Inter, sans-serif';
                    g.fillStyle = '#cbd5e1'; g.textAlign = L.align === 'center' ? 'center' : (L.align === 'right' ? 'right' : 'left');
                    g.textBaseline = 'middle';
                    descLines.forEach((ln, i) => g.fillText(ln, alignX(), y + 8 * u + i * 16 * u));
                })
            } : null;
            const chipsMeta = () => {
                g.font = '700 ' + 10 * u * k + 'px Inter, sans-serif';
                const meas = v => g.measureText(String(v)).width;
                const cw = v => 16 * u * k + 9 * u * k + 4 * u * k + meas(v);
                const ch = 6 * u * k + 10 * u * k * 1.25;
                return { cw, ch, gap: 4 * u * k };
            };
            const statsBlock = cardStatsShown(L) && L.statsPos !== 'left' && L.statsPos !== 'right' ? {
                h: chipsMeta().ch,
                draw: y => {
                    const m = chipsMeta();
                    const w1 = m.cw(st.atk), w2 = m.cw(st.hp), gap = m.gap;
                    const total = w1 + gap + w2;
                    let x = L.statsDir === 'col'
                        ? (L.align === 'center' ? W / 2 - w1 / 2 : (L.align === 'right' ? W - p - w1 : p))
                        : (L.align === 'center' ? W / 2 - total / 2 : (L.align === 'right' ? W - p - total : p));
                    nxDrawChip(g, x, y, '#fbbf24', 'atk', st.atk, k, u, L.statsShape);
                    if (L.statsDir === 'col') { x = L.align === 'center' ? W / 2 - w2 / 2 : (L.align === 'right' ? W - p - w2 : p); nxDrawChip(g, x, y + m.ch + gap, '#fb7185', 'hp', st.hp, k, u, L.statsShape); }
                    else nxDrawChip(g, x + w1 + gap, y, '#fb7185', 'hp', st.hp, k, u, L.statsShape);
                }
            } : null;
            const topList = [], bottomList = [];
            if (nameBlock) (L.namePos === 'top' ? topList : bottomList).push(nameBlock);
            if (descBlock) (L.descPos === 'top' ? topList : bottomList).push(descBlock);
            if (statsBlock) (L.statsPos === 'top' ? topList : bottomList).push(statsBlock);
            const gap = 4 * u;
            let cy = p + badgeH + gap;
            topList.forEach(b => { b.draw(cy); cy += b.h + gap; });
            cy = H - p;
            bottomList.slice().reverse().forEach(b => { cy -= b.h; b.draw(cy); cy -= gap; });
            // --- статы у кромки (left/right) — как боковой слой на экране ---
            if (cardStatsShown(L) && (L.statsPos === 'left' || L.statsPos === 'right')) {
                const m = chipsMeta();
                const w1 = m.cw(st.atk), w2 = m.cw(st.hp);
                const xs = w => L.statsPos === 'left' ? p : W - p - w;
                if (L.statsDir === 'col') {
                    const total = m.ch * 2 + m.gap;
                    let y = H / 2 - total / 2;
                    nxDrawChip(g, xs(w1), y, '#fbbf24', 'atk', st.atk, k, u, L.statsShape);
                    nxDrawChip(g, xs(w2), y + m.ch + m.gap, '#fb7185', 'hp', st.hp, k, u, L.statsShape);
                } else {
                    const total = w1 + m.gap + w2;
                    const x0 = L.statsPos === 'left' ? p : W - p - total;
                    nxDrawChip(g, x0, H / 2 - m.ch / 2, '#fbbf24', 'atk', st.atk, k, u, L.statsShape);
                    nxDrawChip(g, x0 + w1 + m.gap, H / 2 - m.ch / 2, '#fb7185', 'hp', st.hp, k, u, L.statsShape);
                }
            }
            // --- рамка редкости поверх всего, как border-2 на карте ---
            g.strokeStyle = RAR_COLORS[card.rarity] || '#94a3b8';
            g.lineWidth = 2 * u;
            roundRectCanvas(g, u, u, W - u * 2, H - u * 2, R - u);
            g.stroke();
            g.restore();
            return cv;
        }
        async function downloadCardPng(cardId) {
            const card = state.cards.find(c => c.id === cardId);
            if (!card) { showToast('Карточка не найдена', 'error'); return; }
            let objUrl = '';
            try {
                objUrl = await nxArtBlobUrl(mediaUrl(card.image) || card.image);
                const img = new Image();
                await new Promise((res, rej) => {
                    img.onload = res;
                    img.onerror = () => rej(new Error('арт не загрузился'));
                    img.src = objUrl;
                });
                const cv = nxCardFaceCanvas(card, img, 1080, 1920);
                const blob = await new Promise(res => cv.toBlob(res, 'image/png'));
                if (!blob) throw new Error('canvas не отдал файл');
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = nxCardExportName(card);
                document.body.appendChild(a); a.click(); a.remove();
                setTimeout(() => URL.revokeObjectURL(a.href), 5000);
                showToast('✅ Карточка #' + getCardLocalNumber(card) + ' скачана PNG-файлом', 'success');
            } catch (e) {
                showToast('Не удалось скачать карточку: ' + (e && e.message ? e.message : e) + '. Если арт по внешней ссылке без CORS — залейте картинку на GitHub кнопкой «Загрузить с устройства»', 'error');
            } finally {
                if (objUrl) setTimeout(() => URL.revokeObjectURL(objUrl), 5000);
            }
        }
        function downloadCardPngOfForm() {
            const id = (document.getElementById('edit-card-id') || {}).value || '';
            if (!id) { showToast('Сначала создайте карточку: скачивание работает у сохранённой карты — кнопка есть и в списке карточек', 'error'); return; }
            downloadCardPng(id);
        }'''))

# --------------------------------------------------------------------------- #
# assets/app.js — кнопка скачивания в строке карточки Студии
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r''' : `<button onclick="editCard('${c.id}')" class="w-7 h-7 rounded-lg bg-violet-500/10 hover:bg-violet-500/20 text-violet-400 flex items-center justify-center transition" title="Редактировать"><i class="fa-solid fa-pen text-xs"></i></button>''',
              r''' : `<button onclick="downloadCardPng('${c.id}')" class="w-7 h-7 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-emerald-300 flex items-center justify-center transition" title="Скачать карточку PNG-файлом: арт, номер, редкость, имя, описание и статы со всеми настройками"><i class="fa-solid fa-download text-xs"></i></button>
                        <button onclick="editCard('${c.id}')" class="w-7 h-7 rounded-lg bg-violet-500/10 hover:bg-violet-500/20 text-violet-400 flex items-center justify-center transition" title="Редактировать"><i class="fa-solid fa-pen text-xs"></i></button>'''))

# --------------------------------------------------------------------------- #
# index.html — кнопка скачивания под живым предпросмотром
# --------------------------------------------------------------------------- #
PAIRS.append(('index.html', 1,
              r'''                            <p class="text-[10px] text-slate-500 mt-1.5 text-center">Живой предпросмотр карты и ауры за ней</p>''',
              r'''                            <p class="text-[10px] text-slate-500 mt-1.5 text-center">Живой предпросмотр карты и ауры за ней</p>
                            <!-- b479: экспорт сохранённой карты в PNG со всем лицом -->
                            <button type="button" id="card-download-btn" onclick="downloadCardPngOfForm()" class="mt-2 w-full px-3 py-2 rounded-xl bg-emerald-700/70 hover:bg-emerald-600 border border-emerald-500/40 text-[11px] font-bold text-white transition" title="Скачать сохранённую карточку PNG-файлом: арт с кадрированием, номер #N, редкость, копии, имя, описание и статы со всеми настройками (эффекты и аура — живые анимации, в файл не входят)"><i class="fa-solid fa-download mr-1"></i>Скачать готовую карточку (PNG)</button>'''))


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
        txt = files.get(rel) or read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        if n in txt:
            problems.append('%s: правка уже применена: %s...' % (rel, o[:60]))
            continue
        if txt.count(o) != cnt:
            problems.append('%s: якорь встретился %d раз вместо %d: %s...' % (rel, txt.count(o), cnt, o[:60]))
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
        print('b479: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b479: кнопка «Скачать готовую карточку (PNG)» в Студии; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
