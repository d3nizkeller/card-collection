#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b460: кадрирование арта мышью прямо в живом предпросмотре.

Просьба владельца: «зачем ползунки, если можно мышкой и колесиком мыши
по просмотру». Ползунки остались (точный ввод с клавиатуры/тача), но
теперь панель превью — полноценный контрол кадрирования:
  · колесо мыши вверх/вниз — масштаб арта ±5% (100–220), курсор на
    превью; preventDefault, чтобы страница не скроллилась;
  · зажал и тянешь — сдвиг картины по обеим осям (картина следует за
    курсором; pointer-события, работают и тачем; touch-action:none на
    панели, чтобы палец не скроллил страницу вместо панорамы);
  · двойной клик — сброс 100/0/0.
Прямое управление пишет значения в ТЕ ЖЕ слайдеры card-artzoom/arty/artx
и дёргает renderCardPreview() — источник истины один, сохранение в
layout карты (artZoom/artPosY/artPosX) работает без изменений. Сдвиг
ограничен диапазоном слайдеров ±100 (трансформ и так режет ±(S−1)*50%).
При масштабе 100% панорама не двигается (смотреть некуда) — сперва
накрутите зум колесом.

Подпись под превью получила строку-подсказку: «Колесо — масштаб,
перетаскивание — сдвиг, двойной клик — сброс».

app.js менялся — тег сборки nxmob182 -> nxmob183 (index.html, sw.js,
tools/build.py), кэш nx-assets перечитается сразу.

Проверка/применение:
    python3 tools/_b460_patch.py --check
    python3 tools/_b460_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob182'
TAG_NEW = 'nxmob183'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

# ---------- index.html: подсказка под превью ----------
PAIRS.append(('index.html', '''                            <p class="text-[10px] text-slate-500 mt-1.5 text-center">Живой предпросмотр карты и ауры за ней</p>''',
              '''                            <p class="text-[10px] text-slate-500 mt-1.5 text-center">Живой предпросмотр карты и ауры за ней</p>
                            <!-- b460: прямое управление кадрированием мышью/тачем -->
                            <p class="text-[10px] text-slate-600 mt-0.5 text-center">Колесо — масштаб, перетаскивание — сдвиг, двойной клик — сброс</p>'''))

# ---------- app.js: биндинг прямого управления ----------
PAIRS.append(('assets/app.js', '''        // живой предпросмотр карты в форме Студии
        function renderCardPreview() {''',
              '''        // b460: прямое управление кадрированием арта прямо в превью: колесо мыши —
        // масштаб, перетаскивание — сдвиг по обеим осям (картина следует за курсором),
        // двойной клик — сброс 100/0/0. Значения пишутся в те же слайдеры
        // card-artzoom/arty/artx: источник истины один, сохранение в layout не меняется.
        function nxCardPreviewBind() {
            const wrap = document.getElementById('card-preview-wrap');
            if (!wrap || wrap.__nxBound) return;
            wrap.__nxBound = 1;
            wrap.style.touchAction = 'none';
            wrap.style.cursor = 'grab';
            wrap.addEventListener('wheel', function (e) {
                e.preventDefault();
                const z = document.getElementById('card-artzoom');
                if (!z) return;
                let v = (Number(z.value) || 100) + (e.deltaY < 0 ? 5 : -5);
                v = Math.max(100, Math.min(220, v));
                if (String(v) !== z.value) { z.value = v; renderCardPreview(); }
            }, { passive: false });
            let drag = null;
            wrap.addEventListener('pointerdown', function (e) {
                if (e.pointerType === 'mouse' && e.button !== 0) return;
                const z = document.getElementById('card-artzoom');
                const Y = document.getElementById('card-arty');
                const X = document.getElementById('card-artx');
                if (!z || !Y || !X) return;
                drag = {
                    x: e.clientX, y: e.clientY,
                    sx: Number(X.value) || 0, sy: Number(Y.value) || 0,
                    s: (Number(z.value) || 100) / 100,
                    h: wrap.clientHeight || 1, w: wrap.clientWidth || 1
                };
                try { wrap.setPointerCapture(e.pointerId); } catch (e2) {}
                wrap.style.cursor = 'grabbing';
                e.preventDefault();
            });
            wrap.addEventListener('pointermove', function (e) {
                if (!drag) return;
                const maxY = (drag.s - 1) * 50;
                if (maxY <= 0) return; // масштаб 100%: панорамить нечего
                const Y = document.getElementById('card-arty');
                const X = document.getElementById('card-artx');
                if (!Y || !X) return;
                const dyPct = (e.clientY - drag.y) / drag.h * 100;
                const dxPct = (e.clientX - drag.x) / drag.w * 100;
                let uy = drag.sy + (dyPct / maxY) * 100;
                let ux = drag.sx + (dxPct / maxY) * 100;
                uy = Math.max(-100, Math.min(100, Math.round(uy / 5) * 5));
                ux = Math.max(-100, Math.min(100, Math.round(ux / 5) * 5));
                if (String(uy) !== Y.value || String(ux) !== X.value) {
                    Y.value = uy; X.value = ux; renderCardPreview();
                }
            });
            const up = function () { drag = null; wrap.style.cursor = 'grab'; };
            wrap.addEventListener('pointerup', up);
            wrap.addEventListener('pointercancel', up);
            wrap.addEventListener('dblclick', function () {
                const z = document.getElementById('card-artzoom');
                const Y = document.getElementById('card-arty');
                const X = document.getElementById('card-artx');
                if (z) z.value = 100;
                if (Y) Y.value = 0;
                if (X) X.value = 0;
                renderCardPreview();
            });
        }

        // живой предпросмотр карты в форме Студии
        function renderCardPreview() {'''))

# ---------- app.js: вызов биндинга в конце renderCardPreview ----------
PAIRS.append(('assets/app.js', '''            applyCardAura(document.getElementById('card-preview-aura'), fake, 'aura-preview');
        }''',
              '''            applyCardAura(document.getElementById('card-preview-aura'), fake, 'aura-preview');
            try { nxCardPreviewBind(); } catch (e) {} // b460: колесо/драг/даблклик по превью
        }'''))


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
        print('b460: якоря и тег %s на месте, можно применять' % TAG_OLD)
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b460: колесо/перетаскивание/даблклик по превью; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
