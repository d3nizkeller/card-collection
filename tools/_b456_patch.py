#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b456: масштаб арта карты в живом предпросмотре — картина садится ровно.

Просьба владельца: в форме «Новая Карточка» дать масштабирование картинки
в живом предпросмотре, чтобы ровно выравнивать картину в рамке карты
(арт 9:16 не всегда совпадает с кадрированием object-cover: лицо или
логотип уезжают под текст/кромку).

Лечение:
  1. в форме под полем «Ссылка на картинку» — два слайдера:
     «Масштаб арта» 100–220% (шаг 5) и «Сдвиг по вертикали» −100…100
     (шаг 5); оба дёргают renderCardPreview() на input;
  2. значения пишутся в layout карты (artZoom, artPosY) через
     readCardLayoutForm() — то есть сохраняются в карте и уезжают в облако
     вместе с остальной компоновкой; cardLayoutOf() нормализует их
     (100–220 / −100…100, по умолчанию 100/0 — старые карты не меняются);
  3. новый хелпер cardArtStyle(card) даёт inline-transform для <img> арта:
     translateY(Y%) scale(S), где Y ограничен ±(S−1)*50% — при любом
     масштабе края картинки не оголяются (дыр по краям рамки нет);
     при дефолтных 100/0 хелпер возвращает пустую строку — hover-зум
     group-hover:scale-105 на обычных картах не глушится;
  4. transform применён во ВСЕХ пяти местах рендера арта: список пака,
     две сетки альбома/просмотра, большой просмотр и живой предпросмотр —
     масштаб из редактора виден везде одинаково;
  5. editCard() подставляет сохранённые значения в слайдеры, сброс формы
     возвращает 100/0 (form.reset + value-атрибуты).
Классы и иконки — только из собранного tailwind.css/fa.css
(accent-violet-500, grid-cols-2, fa-search, fa-image).

Проверка/применение:
    python3 tools/_b456_patch.py --check
    python3 tools/_b456_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = []

# ---------- index.html: слайдеры под полем ссылки на картинку ----------
PAIRS.append(('index.html', '''                            <div class="flex items-center gap-2 mt-1"><button type="button" onclick="nxPickFileFor('card-image')" class="px-2.5 py-1.5 bg-emerald-700/70 hover:bg-emerald-600 border border-emerald-500/40 rounded-lg text-[11px] font-semibold text-white transition" title="Выберите файл картинки на устройстве — сайт сам зальёт его в папку media/ репозитория GitHub и подставит готовую ссылку в поле"><i class="fa-solid fa-upload mr-1"></i>Загрузить с устройства &rarr; GitHub</button><span id="card-image-upl" class="text-[10px] text-slate-500"></span></div>
''', '''                            <div class="flex items-center gap-2 mt-1"><button type="button" onclick="nxPickFileFor('card-image')" class="px-2.5 py-1.5 bg-emerald-700/70 hover:bg-emerald-600 border border-emerald-500/40 rounded-lg text-[11px] font-semibold text-white transition" title="Выберите файл картинки на устройстве — сайт сам зальёт его в папку media/ репозитория GitHub и подставит готовую ссылку в поле"><i class="fa-solid fa-upload mr-1"></i>Загрузить с устройства &rarr; GitHub</button><span id="card-image-upl" class="text-[10px] text-slate-500"></span></div>
                            <!-- b456: масштаб арта и сдвиг по вертикали в живом предпросмотре:
                                 картина ровно садится в рамку карты; значения сохраняются
                                 в layout карты (artZoom/artPosY) и видны во всех рендерах -->
                            <div class="grid grid-cols-2 gap-3 mt-2">
                                <div class="flex flex-col">
                                    <label class="block text-[11px] font-medium text-slate-400 mb-1"><i class="fa-solid fa-search text-violet-400 mr-1"></i>Масштаб арта <span id="card-artzoom-val" class="text-slate-300 font-bold">100%</span></label>
                                    <input type="range" id="card-artzoom" min="100" max="220" step="5" value="100" oninput="renderCardPreview()" class="w-full accent-violet-500">
                                </div>
                                <div class="flex flex-col">
                                    <label class="block text-[11px] font-medium text-slate-400 mb-1"><i class="fa-solid fa-image text-sky-400 mr-1"></i>Сдвиг по вертикали <span id="card-arty-val" class="text-slate-300 font-bold">0</span></label>
                                    <input type="range" id="card-arty" min="-100" max="100" step="5" value="0" oninput="renderCardPreview()" class="w-full accent-violet-500">
                                </div>
                            </div>
'''))

# ---------- app.js: layout читает/нормализует новые поля ----------
PAIRS.append(('assets/app.js', '''            return { namePos: g('card-name-pos'), descPos: g('card-desc-pos'), align: g('card-align'), shine: g('card-shine') };''',
              '''            return { namePos: g('card-name-pos'), descPos: g('card-desc-pos'), align: g('card-align'), shine: g('card-shine'), artZoom: g('card-artzoom'), artPosY: g('card-arty') }; // b456: + масштаб/сдвиг арта'''))

PAIRS.append(('assets/app.js', '''                shine: (CARD_FX.indexOf(L.shine) >= 0 || L.shine === 'none') ? L.shine : 'auto',''',
              '''                shine: (CARD_FX.indexOf(L.shine) >= 0 || L.shine === 'none') ? L.shine : 'auto',
                // b456: масштаб арта 100–220% и сдвиг по вертикали −100…100 (сырые
                // значения из формы/облака нормализуются здесь)
                artZoom: Math.max(100, Math.min(220, Number(L.artZoom) || 100)),
                artPosY: Math.max(-100, Math.min(100, Number(L.artPosY) || 0)),'''))

# ---------- app.js: хелпер трансформа арта ----------
PAIRS.append(('assets/app.js', '''        function cardHoloClass(card) {''',
              '''        // b456: inline-transform арта в рамке карты: масштаб + вертикальный сдвиг,
        // ограниченный ±(S−1)*50% — края картины не оголяются ни при каком зуме.
        // При дефолте (100/0) возвращает пустую строку: hover-зум group-hover:scale-105
        // на обычных картах не глушится inline-стилем.
        function cardArtStyle(card) {
            const L = cardLayoutOf(card);
            if (L.artZoom === 100 && L.artPosY === 0) return '';
            const s = L.artZoom / 100;
            const maxY = (s - 1) * 50;
            const y = (L.artPosY / 100) * maxY;
            return ' style="transform:translateY(' + y.toFixed(2) + '%) scale(' + s.toFixed(2) + ')"';
        }
        function cardHoloClass(card) {'''))

# ---------- app.js: transform в пяти рендерах арта ----------
PAIRS.append(('assets/app.js', '''<img src="${mediaThumbMid(card.image)}" data-nx-full="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);" class="absolute inset-0 w-full h-full object-cover z-0" loading="lazy" decoding="async">''',
              '''<img src="${mediaThumbMid(card.image)}" data-nx-full="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);"${cardArtStyle(card)} class="absolute inset-0 w-full h-full object-cover z-0" loading="lazy" decoding="async">'''))

PAIRS.append(('assets/app.js', '''<img src="${artFn(card.image)}" data-nx-full="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);" loading="lazy" decoding="async" class="absolute inset-0 w-full h-full object-cover z-0 group-hover:scale-105 transition duration-500">''',
              '''<img src="${artFn(card.image)}" data-nx-full="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);" loading="lazy" decoding="async"${cardArtStyle(card)} class="absolute inset-0 w-full h-full object-cover z-0 group-hover:scale-105 transition duration-500">'''))

PAIRS.append(('assets/app.js', '''<img src="${mediaBig(card.image)}" data-nx-full="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);" class="absolute inset-0 w-full h-full object-cover z-0" loading="lazy" decoding="async">''',
              '''<img src="${mediaBig(card.image)}" data-nx-full="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);"${cardArtStyle(card)} class="absolute inset-0 w-full h-full object-cover z-0" loading="lazy" decoding="async">'''))

PAIRS.append(('assets/app.js', '''<img src="${mediaThumbMid(image)}" data-nx-full="${mediaUrl(image)}" alt="" onerror="imgErrorChain(this)" class="absolute inset-0 w-full h-full object-cover z-0" loading="lazy" decoding="async">''',
              '''<img src="${mediaThumbMid(image)}" data-nx-full="${mediaUrl(image)}" alt="" onerror="imgErrorChain(this)"${cardArtStyle(fake)} class="absolute inset-0 w-full h-full object-cover z-0" loading="lazy" decoding="async">'''))

# ---------- app.js: превью показывает значения слайдеров ----------
PAIRS.append(('assets/app.js', '''            const L = cardLayoutOf(fake);
            const st = getCardStats(fake);''',
              '''            // b456: подписи значений слайдеров масштаба/сдвига
            const azv = document.getElementById('card-artzoom-val');
            if (azv) azv.textContent = (Number(gv('card-artzoom')) || 100) + '%';
            const ayv = document.getElementById('card-arty-val');
            if (ayv) ayv.textContent = String(Number(gv('card-arty')) || 0);
            const L = cardLayoutOf(fake);
            const st = getCardStats(fake);'''))

# ---------- app.js: editCard подставляет сохранённые значения ----------
PAIRS.append(('assets/app.js', '''            document.getElementById('card-shine').value = L0.shine;''',
              '''            document.getElementById('card-shine').value = L0.shine;
            // b456: слайдеры масштаба/сдвига арта — из сохранённого layout
            const azEl = document.getElementById('card-artzoom');
            if (azEl) azEl.value = L0.artZoom;
            const ayEl = document.getElementById('card-arty');
            if (ayEl) ayEl.value = L0.artPosY;'''))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, old, new in PAIRS:
        txt = files.get(rel) or read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        cnt = txt.count(o)
        want = 2 if '${artFn(card.image)}' in o else 1
        if cnt != want:
            problems.append('%s: якорь встретился %d раз (ждаем %d): %s...' % (rel, cnt, want, o[:60]))
            continue
        files[rel] = txt.replace(o, n) if want == 1 else txt.replace(o, n)
    if problems:
        for p in problems:
            print('ПРОБЛЕМА:', p)
        return 1
    if '--check' in sys.argv:
        print('b456: якоря на месте, можно применять')
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b456: масштаб арта в предпросмотре карты добавлен (%d правок)' % len(files))
    return 0


if __name__ == '__main__':
    sys.exit(main())
