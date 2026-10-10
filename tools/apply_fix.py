#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правки b355..b360 (краш сайта во время игры) в виде списка old->new.

Применяется ДВАЖДЫ:
  1) к assets/app.js и assets/qr-transfer.js (то, что реально отдаётся сайтом);
  2) к tools/source-index.html — монолиту, из которого python3 tools/build.py
     заново генерирует assets/*. Без этого следующая сборка затёрла бы правки.

Запуск:  python3 tools/apply_fix.py <цель: assets|monolith|check>
"""
import sys, os, io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- app.js -----
APP_EDITS = [
    # b355: NX_TRAIL объявлен в конце файла, а nxTrail() зовётся с самого начала
    # -> ReferenceError (TDZ) проглатывался try/catch, «чёрный ящик» был всегда пуст
    ("trail-decl",
     "        // ============ ЗВУК (Web Audio API, синтез) ============",
     "        // b355: «чёрный ящик» событий объявлен ДО первого использования: раньше\n"
     "        // const NX_TRAIL лежал в конце файла, nxTrail() падал в ReferenceError (TDZ),\n"
     "        // ошибка проглатывалась try/catch — и диагностика крашей всегда была пустой.\n"
     "        var NX_TRAIL = [];\n"
     "\n"
     "        // ============ ЗВУК (Web Audio API, синтез) ============"),
    ("trail-old-decl",
     "        const NX_TRAIL = [];\n        function nxTrail(tag) {",
     "        function nxTrail(tag) {"),

    # b355: 40 blob:URL по 8 МБ = до 320 МБ живой памяти только под кэш картинок
    ("img-obj-max",
     "        const IMG_OBJ_MAX = 40;",
     "        // b355: 40 blob:URL по 8 МБ — это до 320 МБ живой памяти только под кэш\n"
     "        // картинок; на телефоне именно это добивало вкладку. Держим меньше, а на\n"
     "        // устройствах с малой памятью — совсем мало (диск IndexedDB никуда не девается).\n"
     "        const IMG_OBJ_MAX = (function () { try { if (typeof nxLowRam === 'function' && nxLowRam()) return 10; } catch (e) {} return 18; })();"),

    # b356: «Линии» и арена не освобождали WebGL-контекст при уходе на другую игру
    ("release-hidden",
     "                if (m !== 'wheel' && wheel.renderer) { cancelAnimationFrame(wheel.animId); wheel.animId = 0; nx3dDrop(wheel.renderer); wheel.renderer = null; wheel.ready = false; wheel.fallback = false; }\n"
     "            } catch (e) {}\n"
     "        }",
     "                if (m !== 'wheel' && wheel.renderer) { cancelAnimationFrame(wheel.animId); wheel.animId = 0; nx3dDrop(wheel.renderer); wheel.renderer = null; wheel.ready = false; wheel.fallback = false; }\n"
     "                // b356: «Линии» раньше НЕ освобождались — их 3D-контекст и rAF-цикл\n"
     "                // продолжали крутиться на скрытом экране до конца сессии (замер:\n"
     "                // 8 кадров/с вхолостую после ухода в «Магазин»). Теперь поле уходит в\n"
     "                // плоский режим, а при возврате linesTry3D() поднимет 3D заново.\n"
     "                if (m !== 'lines' && lines3d.renderer) {\n"
     "                    cancelAnimationFrame(lines3d.animId); lines3d.animId = 0;\n"
     "                    nx3dDrop(lines3d.renderer); lines3d.renderer = null;\n"
     "                    lines3d.reels = []; lines3d.pending = null;\n"
     "                    lines.mode3d = false; lines.no3d = false;\n"
     "                    try {\n"
     "                        const box = document.getElementById('lines-3d-box'), board = document.getElementById('lines-board');\n"
     "                        if (box) box.classList.add('hidden');\n"
     "                        if (board) board.classList.remove('hidden');\n"
     "                    } catch (e) {}\n"
     "                }\n"
     "                // b356: арена — 3D-сцена боя (небо, звёзды, угли, меши карт) жила,\n"
     "                // пока игрок крутил слоты/колесо. Освобождаем; при возврате в арену\n"
     "                // battle3dInit() поднимется заново (см. setBattleMode).\n"
     "                if (m !== 'arena' && battle3d) { try { battle3dDispose(); } catch (e) {} }\n"
     "            } catch (e) {}\n"
     "        }\n"
     "        // ============ b357: ПАУЗА 3D В ФОНЕ ============\n"
     "        // Вкладка спрятана — ни один 3D-цикл не должен жечь CPU/GPU/батарею:\n"
     "        // на мобильном именно фоновые кадры добивают память, и браузер убивает вкладку.\n"
     "        // Каждый цикл в первом же кадре видит флаг и «отпускает» сам себя (не планируя\n"
     "        // следующий кадр), поэтому второй цикл при возврате не заводится: мы просто\n"
     "        // дёргаем ту же функцию ещё раз.\n"
     "        let nx3dFrozen = false;\n"
     "        const NX3D_LOOPS = [];\n"
     "        function nx3dRegLoop(tag, tick, holder, idKey, tKey) { NX3D_LOOPS.push({ tag: tag, tick: tick, holder: holder, idKey: idKey, tKey: tKey }); }\n"
     "        function nx3dPauseAll() { nx3dFrozen = true; }\n"
     "        function nx3dResumeAll() {\n"
     "            nx3dFrozen = false;\n"
     "            if (document.hidden) return;\n"
     "            for (let i = 0; i < NX3D_LOOPS.length; i++) {\n"
     "                const L = NX3D_LOOPS[i];\n"
     "                try {\n"
     "                    const h = L.holder ? L.holder() : null;\n"
     "                    if (!h || h[L.idKey]) continue; // живой цикл уже есть — не дублируем\n"
     "                    if (L.tKey) h[L.tKey] = performance.now(); // dt без скачка после паузы\n"
     "                    L.tick();\n"
     "                } catch (e) {}\n"
     "            }\n"
     "        }\n"
     "        nx3dRegLoop('slots', function () { try { if (slots.__loop) slots.__loop(); } catch (e) {} }, () => (slots && slots.renderer) ? slots : null, 'animId', 'lastT');\n"
     "        nx3dRegLoop('grid', function () { try { if (grid3d.__loop) grid3d.__loop(); } catch (e) {} }, () => (grid3d && grid3d.renderer) ? grid3d : null, 'animId', 'lastT');\n"
     "        nx3dRegLoop('wheel', function () { try { if (wheel.__loop) wheel.__loop(); } catch (e) {} }, () => (wheel && wheel.renderer) ? wheel : null, 'animId', 'lastT');\n"
     "        nx3dRegLoop('lines', function () { try { lines3dTick(); } catch (e) {} }, () => (lines3d && lines3d.renderer) ? lines3d : null, 'animId', null);\n"
     "        nx3dRegLoop('battle', function () { try { battle3dTick(); } catch (e) {} }, () => (battle3d && battle3d.renderer) ? battle3d : null, 'raf', null);\n"
     "        nx3dRegLoop('durak', function () { try { durak3dTick(); } catch (e) {} }, () => (durak3d && durak3d.renderer) ? durak3d : null, 'raf', null);\n"
     "        nx3dRegLoop('pack3d', function () { try { animatePack3D(); } catch (e) {} }, () => pack3d, 'animId', null);\n"
     "        document.addEventListener('visibilitychange', () => { try { if (document.hidden) { nxTrail('bg-pause'); nx3dPauseAll(); } else { nxTrail('fg-resume'); nx3dResumeAll(); } } catch (e) {} });"),

    # b357: сами циклы должны видеть флаг паузы
    ("loop-slots",
     "            slots.lastT = performance.now();\n"
     "            const loop = () => {\n"
     "                slots.animId = requestAnimationFrame(loop);",
     "            slots.lastT = performance.now();\n"
     "            const loop = () => {\n"
     "                if (nx3dFrozen) { slots.animId = 0; return; } // b357: в фоне кадры не крутим\n"
     "                slots.animId = requestAnimationFrame(loop);"),
    ("loop-grid",
     "            grid3d.lastT = performance.now();\n"
     "            const loop = () => {\n"
     "                grid3d.animId = requestAnimationFrame(loop);",
     "            grid3d.lastT = performance.now();\n"
     "            const loop = () => {\n"
     "                if (nx3dFrozen) { grid3d.animId = 0; return; } // b357\n"
     "                grid3d.animId = requestAnimationFrame(loop);"),
    ("loop-wheel",
     "            wheel.lastT = performance.now();\n"
     "            const loop = () => {\n"
     "                wheel.animId = requestAnimationFrame(loop);",
     "            wheel.lastT = performance.now();\n"
     "            const loop = () => {\n"
     "                if (nx3dFrozen) { wheel.animId = 0; return; } // b357\n"
     "                wheel.animId = requestAnimationFrame(loop);"),
    ("loop-slots-pub",
     "            };\n            loop();\n        }\n        function slotsTheta(",
     "            };\n            slots.__loop = loop; // b357: цикл доступен для возврата из фона\n            loop();\n        }\n        function slotsTheta("),
    ("loop-lines",
     "        function lines3dTick() {\n            lines3d.animId = requestAnimationFrame(lines3dTick);",
     "        function lines3dTick() {\n            if (nx3dFrozen) { lines3d.animId = 0; return; } // b357\n            lines3d.animId = requestAnimationFrame(lines3dTick);"),
    ("loop-battle",
     "        function battle3dTick() {\n            if (!battle3d) return;\n            battle3d.raf = requestAnimationFrame(battle3dTick);",
     "        function battle3dTick() {\n            if (!battle3d) return;\n            if (nx3dFrozen) { battle3d.raf = 0; return; } // b357\n            battle3d.raf = requestAnimationFrame(battle3dTick);"),
    ("loop-durak",
     "        function durak3dTick() {\n            if (!durak3d) return;\n            durak3d.raf = requestAnimationFrame(durak3dTick);",
     "        function durak3dTick() {\n            if (!durak3d) return;\n            if (nx3dFrozen) { durak3d.raf = 0; return; } // b357\n            durak3d.raf = requestAnimationFrame(durak3dTick);"),
    ("loop-pack3d",
     "        function animatePack3D() {\n            if (!pack3d) return;\n            pack3d.animId = requestAnimationFrame(animatePack3D);",
     "        function animatePack3D() {\n            if (!pack3d) return;\n            if (nx3dFrozen) { pack3d.animId = 0; return; } // b357: фоновое вскрытие не крутим\n            pack3d.animId = requestAnimationFrame(animatePack3D);"),

    # b356: возврат в арену должен заново поднять 3D-сцену боя
    ("arena-reinit",
     "            if (m === 'lines') { linesEnsure(); renderLinesUI(); } // b103",
     "            if (m === 'lines') { linesEnsure(); renderLinesUI(); } // b103\n"
     "            // b356: вернулись в арену после другой игры — 3D-сцену боя нужно поднять\n"
     "            // заново (её освободил nx3dReleaseHidden), иначе бой останется плоским\n"
     "            if (m === 'arena' && battle && !battle3d) { try { battle3dInit(); renderArena(); } catch (e) {} }"),

    # b356: вернулись в «Линии» — 3D надо поднять заново. linesEnsure() выходил
    # по lines.built ДО вызова linesTry3D(), и поле навсегда оставалось плоским.
    ("lines-3d-retry",
     "        function linesEnsure() {\n"
     "            const board = document.getElementById('lines-board');\n"
     "            if (!board || lines.built) return;",
     "        function linesEnsure() {\n"
     "            const board = document.getElementById('lines-board');\n"
     "            // b356: поле уже построено — но 3D-контекст мог быть освобождён при уходе\n"
     "            // на другую игру (nx3dReleaseHidden), поэтому пробуем поднять 3D снова\n"
     "            if (!board) return;\n"
     "            if (lines.built) { if (!lines.mode3d && !lines.no3d) { try { linesTry3D(); } catch (e) {} } return; }"),

    # b356: уход на ДРУГУЮ вкладку (Магазин/Альбомы/Биржа) тоже должен отдавать
    # WebGL-контексты, а возврат — поднимать 3D текущей игры заново
    ("tab-release",
     "            if (tabId !== 'battle') stopAllGameAutos('переход на другую вкладку');",
     "            if (tabId !== 'battle') stopAllGameAutos('переход на другую вкладку');\n"
     "            // b356: 3D-контексты нужны только во вкладке игр — уходим отдаём их\n"
     "            // браузеру (иначе скрытая игра держит контекст и крутит кадры до конца сессии)\n"
     "            if (tabId !== 'battle') { try { nx3dReleaseHidden('__all__'); } catch (e) {} }"),
    ("tab-restore",
     "            if (tabId === 'battle') renderBattleTab();",
     "            if (tabId === 'battle') {\n"
     "                renderBattleTab();\n"
     "                // b356: вернулись во вкладку игр — поднимаем 3D текущей игры заново\n"
     "                try {\n"
     "                    if (battleMode === 'slots') slotsEnsure();\n"
     "                    else if (battleMode === 'grid') gridEnsure();\n"
     "                    else if (battleMode === 'wheel') wheelEnsure();\n"
     "                    else if (battleMode === 'lines') linesEnsure();\n"
     "                    else if (battleMode === 'arena' && battle && !battle3d) battle3dInit();\n"
     "                } catch (e) {}\n"
     "            }"),
]

# --------------------------------------------------------- qr-transfer.js ----
QR_EDITS = [
    # b359: base64 квадратичной склейкой строк
    ("b64",
     "function nxB64(str) { // base64 для огромных строк — кусками, без переполнения стека\n"
     "    const bytes = new TextEncoder().encode(str);\n"
     "    let bin = ''; const CH = 0x8000;\n"
     "    for (let i = 0; i < bytes.length; i += CH) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));\n"
     "    return btoa(bin);\n"
     "}",
     "function nxBytesToB64(u8) { // b359: base64 через массив кусков и один join.\n"
     "    // Было: bin += String.fromCharCode(...) в цикле — на файле в несколько МБ это\n"
     "    // квадратичная склейка строк (сотни МБ мусора и блокировка главного потока).\n"
     "    const CH = 0x8000, parts = [];\n"
     "    for (let i = 0; i < u8.length; i += CH) parts.push(String.fromCharCode.apply(null, u8.subarray(i, i + CH)));\n"
     "    return btoa(parts.join(''));\n"
     "}\n"
     "function nxB64(str) { // base64 для огромных строк — кусками, без переполнения стека\n"
     "    return nxBytesToB64(new TextEncoder().encode(str));\n"
     "}"),
]


QR_EDITS += [
    ('qr-645-649',
     "function nxB64(str) { // base64 для огромных строк — кусками, без переполнения стека\n    const bytes = new TextEncoder().encode(str);\n    let bin = ''; const CH = 0x8000;\n    for (let i = 0; i < bytes.length; i += CH) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));\n    return btoa(bin);",
     "function nxBytesToB64(u8) { // b359: base64 через массив кусков и один join.\n    // Было: bin += String.fromCharCode(...) в цикле — на файле в несколько МБ это\n    // квадратичная склейка строк (сотни МБ мусора и блокировка главного потока).\n    const CH = 0x8000, parts = [];\n    for (let i = 0; i < u8.length; i += CH) parts.push(String.fromCharCode.apply(null, u8.subarray(i, i + CH)));\n    return btoa(parts.join(''));\n}\nfunction nxB64(str) { // base64 для огромных строк — кусками, без переполнения стека\n    return nxBytesToB64(new TextEncoder().encode(str));"),
    ('qr-695-713',
     "        let out = src, pending = pairs.length, replaced = 0; const extras = []; // b340\n        const finalize = () => { nxProgress(0.65, 'Собираю файл с артами…'); out = nxInjectExtras(out, extras); // b340\n            if (!replaced && !extras.length) { err('Вшивать нечего: кэш пуст. Нажмите «Вшить всё» или дождитесь авто-кэша — и повторите'); return; }\n            say((auto ? 'Автовшивание: ' : '') + 'файл собран (' + (replaced + extras.length) + ' артов). Пушу коммит в GitHub…');\n            nxStatus((auto ? 'Автовшивание: ' : '') + 'файл собран (' + (replaced + extras.length) + ' артов), загружаю ~' + (out.length / 1048576).toFixed(1) + ' МБ в GitHub…');\n            nxGhPush(repo, out, () => { if (btn) btn.disabled = false; say((auto ? 'Автовшивание: ' : '') + 'вшито в сайт! Pages обновится за 1–2 минуты'); try { nxCrashLog('push-embed ok: ' + (replaced + extras.length) + ' артов'); } catch (e) {} nxStatus('Готово: вшито ' + (replaced + extras.length) + ' артов. Pages обновится за 1–2 минуты', 'ok'); }, err);\n        };\n        const apply = (raw, dataUrl) => { if (dataUrl) { if (out.indexOf(raw) >= 0) { out = out.split(raw).join(dataUrl); replaced++; } try { const bb = nxMediaKey(raw); if (bb) extras.push([bb, dataUrl]); } catch (e) {} } if (pending > 0) nxProgress(0.15 + 0.45 * (1 - pending / Math.max(1, pairs.length)), 'Достаю арты из кэша устройства: ' + (pairs.length - pending) + '/' + pairs.length); if (--pending === 0) finalize(); };\n        if (!pending) { finalize(); return; }\n        pairs.forEach(p => {\n            imgCacheGetBlob(p.eff).then(blob => {\n                if (!blob || !blob.size) return apply(p.raw, null);\n                const fr = new FileReader();\n                fr.onload = () => apply(p.raw, String(fr.result));\n                fr.onerror = () => apply(p.raw, null);\n                fr.readAsDataURL(blob);\n            }, () => apply(p.raw, null));\n        });\n    }).catch(e => err('Не удалось собрать файл: ' + e.message));",
     "        // b360: вшивание ВСЕЙ коллекции делает из index.html строку в сотни мегабайт\n        // (замер: только 8 артов = 9.7 МБ строки, на 82 арта было бы ~190 МБ), а потом\n        // тащит её одним запросом в GitHub. На телефоне это гарантированная смерть\n        // вкладки, поэтому считаем объём заранее и не начинаем, если он безумный.\n        const MAX_EMBED_MB = 40;\n        imgCacheSizeOf(pairs.map(p => p.eff)).then(mb => {\n            if (mb > MAX_EMBED_MB) {\n                err('Вшивать так много нельзя: арты в кэше занимают ' + mb.toFixed(0) + ' МБ — index.html вырос бы до ~' + Math.round(mb * 1.37) + ' МБ, и вкладка упадёт ещё на сборке (лимит ' + MAX_EMBED_MB + ' МБ). Используйте «Отправить в media/» — картинки уйдут файлами, а сайт останется лёгким.');\n                return;\n            }\n            nxEmbedRun(repo, src, pairs, auto, btn, say, err);\n        }).catch(() => nxEmbedRun(repo, src, pairs, auto, btn, say, err));\n    }).catch(e => err('Не удалось собрать файл: ' + e.message));\n}\nfunction imgCacheSizeOf(urls) { // b360: суммарный вес артов в кэше — БЕЗ загрузки их в память\n    return new Promise(function (res) {\n        var total = 0, i = 0;\n        var step = function () {\n            if (i >= urls.length) { res(total / 1048576); return; }\n            var u = urls[i++];\n            imgCacheGetBlob(u).then(function (b) { if (b && b.size) total += b.size; step(); }, function () { step(); });\n        };\n        step();\n    });\n}\nfunction nxEmbedRun(repo, src, pairs, auto, btn, say, err) {\n    {\n        let out = src, pending = pairs.length, replaced = 0; const extras = []; // b340\n        const finalize = () => { nxProgress(0.65, 'Собираю файл с артами…'); out = nxInjectExtras(out, extras); // b340\n            if (!replaced && !extras.length) { err('Вшивать нечего: кэш пуст. Нажмите «Вшить всё» или дождитесь авто-кэша — и повторите'); return; }\n            say((auto ? 'Автовшивание: ' : '') + 'файл собран (' + (replaced + extras.length) + ' артов). Пушу коммит в GitHub…');\n            nxStatus((auto ? 'Автовшивание: ' : '') + 'файл собран (' + (replaced + extras.length) + ' артов), загружаю ~' + (out.length / 1048576).toFixed(1) + ' МБ в GitHub…');\n            nxGhPush(repo, out, () => { if (btn) btn.disabled = false; say((auto ? 'Автовшивание: ' : '') + 'вшито в сайт! Pages обновится за 1–2 минуты'); try { nxCrashLog('push-embed ok: ' + (replaced + extras.length) + ' артов'); } catch (e) {} nxStatus('Готово: вшито ' + (replaced + extras.length) + ' артов. Pages обновится за 1–2 минуты', 'ok'); }, err);\n        };\n        const apply = (raw, dataUrl) => { if (dataUrl) { if (out.indexOf(raw) >= 0) { out = out.split(raw).join(dataUrl); replaced++; } try { const bb = nxMediaKey(raw); if (bb) extras.push([bb, dataUrl]); } catch (e) {} } if (pending > 0) nxProgress(0.15 + 0.45 * (1 - pending / Math.max(1, pairs.length)), 'Достаю арты из кэша устройства: ' + (pairs.length - pending) + '/' + pairs.length); if (--pending === 0) finalize(); };\n        if (!pending) { finalize(); return; }\n        pairs.forEach(p => {\n            imgCacheGetBlob(p.eff).then(blob => {\n                if (!blob || !blob.size) return apply(p.raw, null);\n                const fr = new FileReader();\n                fr.onload = () => apply(p.raw, String(fr.result));\n                fr.onerror = () => apply(p.raw, null);\n                fr.readAsDataURL(blob);\n            }, () => apply(p.raw, null));\n        });\n    }"),
    ('qr-771-874',
     "function nxCollectPendingMedia() { // какие картинки лежат в кэше, но ещё не отправлены\n    var set = nxMediaPushedSet(), pairs = [];\n    try {\n        nxAllMediaUrls().forEach(function (raw) {\n            var eff = raw; try { eff = mediaUrl(raw); } catch (e) {}\n            if (String(eff).indexOf('http') !== 0) return;\n            var n = nxMediaKey(eff); if (!n || NX_EMBED_MEDIA[n] || set.has(n)) return;\n            if (pairs.some(function (p) { return p.name === n; })) return;\n            pairs.push({ name: n, url: eff });\n        });\n    } catch (e) {}\n    var out = [], i = 0;\n    return new Promise(function (res) {\n        var step = function () {\n            if (i >= pairs.length) { res(out); return; }\n            var p = pairs[i++];\n            try {\n                imgCacheGetBlob(p.url).then(function (b) { if (b && b.size) out.push({ name: p.name, blob: b }); step(); }, function () { step(); });\n            } catch (e) { step(); }\n        };\n        step();\n    });\n}\nfunction nxMaybeAutoMediaPush(force) { // дебаунс + троттлинг: не чаще раза в 10 минут\n    try {\n        if (!nxAutoMediaOn() || !nxGhToken() || !navigator.onLine || NX_MEDIA_PUSHING) return;\n        if (!force && document.hidden) return; // браузер глушит фоновую работу\n        if (!force && Date.now() - NX_MEDIA_LAST < 10 * 60 * 1000) return;\n        if (NX_MEDIA_TIMER) return;\n        NX_MEDIA_TIMER = setTimeout(function () { NX_MEDIA_TIMER = 0; nxAutoMediaPushRun(false); }, force ? 4000 : 90000);\n    } catch (e) {}\n}\nfunction nxGhPushMedia(repo, items, ok, fail) { // один коммит: все новые файлы в media/\n    function blobOf(it) {\n        return it.blob.arrayBuffer().then(function (ab) {\n            var u = new Uint8Array(ab), bin = '';\n            for (var i = 0; i < u.length; i += 0x8000) bin += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000));\n            return btoa(bin);\n        }).then(function (b64) {\n            return nxGhApi('/repos/' + repo + '/git/blobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: b64, encoding: 'base64' }) }).then(function (bl) { return bl.sha; });\n        });\n    }\n    var attempt = function (n) {\n        nxGhApi('/repos/' + repo).then(function (info) {\n            var branch = info.default_branch || 'main';\n            return nxGhApi('/repos/' + repo + '/git/ref/heads/' + branch).then(function (ref) {\n                var head = ref.object.sha;\n                return nxGhApi('/repos/' + repo + '/git/commits/' + head).then(function (cm) {\n                    var chain = Promise.resolve([]);\n                    items.forEach(function (it) {\n                        chain = chain.then(function (acc) {\n                            return blobOf(it).then(function (sh) { acc.push({ path: 'media/' + it.name, mode: '100644', type: 'blob', sha: sh }); return acc; });\n                        });\n                    });\n                    return chain.then(function (entries) {\n                        return nxGhApi('/repos/' + repo + '/git/trees', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ base_tree: cm.tree.sha, tree: entries }) }).then(function (tr) {\n                            return nxGhApi('/repos/' + repo + '/git/commits', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: 'авто: картинки из кэша игры -> media/ (' + items.length + ')', parents: [head], tree: tr.sha }) }).then(function (nc) {\n                                return nxGhApi('/repos/' + repo + '/git/refs/heads/' + branch, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sha: nc.sha }) });\n                            });\n                        });\n                    });\n                });\n            });\n        }).then(function () { ok(); }).catch(function (e) {\n            if (n < 3 && /not a fast forward/i.test(String(e && e.message))) { setTimeout(function () { attempt(n + 1); }, 1500); return; }\n            fail(String((e && e.message) || e));\n        });\n    };\n    attempt(1);\n}\nfunction nxAutoMediaPushRun(manual, done) {\n    if (NX_MEDIA_PUSHING) { if (done) done(0); return; }\n    if (!nxGhToken()) {\n        if (manual) { try { nxOwnerToast('Сначала сохраните токен GitHub в поле ниже — без него сайт не может отправить файлы', 'error'); } catch (e) {} var ti = document.getElementById('nx-gh-token'); if (ti) { ti.focus(); ti.scrollIntoView({ block: 'center' }); } }\n        return;\n    }\n    var repo = nxGhRepoName();\n    var btn = document.getElementById('nx-push-media-btn'); if (manual && btn) btn.disabled = true;\n    nxStatus((manual ? '' : 'Автоотправка: ') + 'смотрю, какие картинки уже в кэше…');\n    nxCollectPendingMedia().then(function (items) {\n        if (!items.length) {\n            if (manual) { nxStatus('Отправлять нечего: новых картинок в кэше нет. Нажмите «Шаг 1. Скачать все картинки»', 'err'); try { nxOwnerToast('В кэше нет новых картинок для отправки', 'error'); } catch (e) {} }\n            else nxStatus('');\n            if (manual && btn) btn.disabled = false;\n            if (done) done(0);\n            return;\n        }\n        NX_MEDIA_PUSHING = true;\n        nxProgress(0.15, 'Отправляю ' + items.length + ' картинок в media/ репозитория…');\n        nxGhPushMedia(repo, items, function () {\n            NX_MEDIA_PUSHING = false; NX_MEDIA_LAST = Date.now();\n            var s = nxMediaPushedSet(); items.forEach(function (it) { s.add(it.name); }); nxMediaSavePushed(s);\n            nxProgress(1, 'Готово: ' + items.length + ' картинок ушло в media/. GitHub Pages обновится за 1–2 минуты', 'ok');\n            nxStatus('Отправлено в ' + repo + '/media/: ' + items.map(function (x) { return x.name; }).join(', '), 'ok');\n            try { nxOwnerToast('Картинки отправлены на GitHub (' + items.length + ' шт. в media/)', 'success'); } catch (e) {}\n            if (manual && btn) btn.disabled = false;\n            if (done) done(items.length);\n        }, function (msg) {\n            NX_MEDIA_PUSHING = false;\n            nxProgress(0, ''); nxStatus('Ошибка отправки на GitHub: ' + msg, 'err');\n            if (manual) { try { nxOwnerToast('Ошибка отправки: ' + msg, 'error'); } catch (e) {} if (btn) btn.disabled = false; }\n            if (done) done(0);\n        });\n    }, function () { NX_MEDIA_PUSHING = false; if (manual && btn) btn.disabled = false; if (done) done(0); });",
     "function nxPendingMediaList() { // b359: только СПИСОК (имя + ссылка), ничего не грузим в память\n    var set = nxMediaPushedSet(), pairs = [];\n    try {\n        nxAllMediaUrls().forEach(function (raw) {\n            var eff = raw; try { eff = mediaUrl(raw); } catch (e) {}\n            if (String(eff).indexOf('http') !== 0) return;\n            var n = nxMediaKey(eff); if (!n || NX_EMBED_MEDIA[n] || set.has(n)) return;\n            if (pairs.some(function (p) { return p.name === n; })) return;\n            pairs.push({ name: n, url: eff });\n        });\n    } catch (e) {}\n    return pairs;\n}\nfunction nxCollectPendingMedia(limit) { // какие картинки лежат в кэше, но ещё не отправлены\n    // b359: раньше сюда брали ВСЕ блобы сразу (замер: 82 арта = 156 МБ в памяти\n    // вкладки, и это в момент, когда игрок ещё и 3D крутит) — мобильный браузер\n    // просто убивал страницу. Теперь берём не больше limit штук за подход.\n    var pairs = nxPendingMediaList();\n    if (limit) pairs = pairs.slice(0, limit);\n    var out = [], i = 0;\n    return new Promise(function (res) {\n        var step = function () {\n            if (i >= pairs.length) { res(out); return; }\n            var p = pairs[i++];\n            try {\n                imgCacheGetBlob(p.url).then(function (b) { if (b && b.size) out.push({ name: p.name, blob: b, url: p.url }); step(); }, function () { step(); });\n            } catch (e) { step(); }\n        };\n        step();\n    });\n}\nfunction nxPushCap(manual) { // b359: сколько файлов отправляем за один подход\n    try { if (typeof nxLowRam === 'function' && nxLowRam()) return manual ? 8 : 3; } catch (e) {}\n    return manual ? 20 : 6;\n}\nfunction nxYield() { // b359: отдаём главный поток браузеру между файлами — игра не подвисает\n    return new Promise(function (res) { setTimeout(res, 0); });\n}\nfunction nxMaybeAutoMediaPush(force) { // дебаунс + троттлинг: не чаще раза в 10 минут\n    try {\n        if (!nxAutoMediaOn() || !nxGhToken() || !navigator.onLine || NX_MEDIA_PUSHING) return;\n        if (!force && document.hidden) return; // браузер глушит фоновую работу\n        if (!force && Date.now() - NX_MEDIA_LAST < 10 * 60 * 1000) return;\n        if (NX_MEDIA_TIMER) return;\n        NX_MEDIA_TIMER = setTimeout(function () { NX_MEDIA_TIMER = 0; nxAutoMediaPushRun(false); }, force ? 4000 : 90000);\n    } catch (e) {}\n}\nfunction nxGhPushMedia(repo, items, ok, fail) { // один коммит: все новые файлы в media/\n    // b359: файлы кодируются и уходят ПО ОДНОМУ. Раньше blobOf() вызывался для\n    // каждого файла внутри общей цепочки, а все блобы лежали в памяти до конца\n    // коммита: 82 арта = 156 МБ + base64 поверх них. Теперь в памяти живёт один файл.\n    function blobOf(it) {\n        return (it.blob\n            ? Promise.resolve(it.blob)\n            : imgCacheGetBlob(it.url).then(function (b) { if (!b || !b.size) throw new Error('нет в кэше: ' + it.name); return b; })\n        ).then(function (b) {\n            return b.arrayBuffer().then(function (ab) { return nxBytesToB64(new Uint8Array(ab)); });\n        }).then(function (b64) {\n            return nxGhApi('/repos/' + repo + '/git/blobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: b64, encoding: 'base64' }) }).then(function (bl) { return bl.sha; });\n        });\n    }\n    var attempt = function (n) {\n        nxGhApi('/repos/' + repo).then(function (info) {\n            var branch = info.default_branch || 'main';\n            return nxGhApi('/repos/' + repo + '/git/ref/heads/' + branch).then(function (ref) {\n                var head = ref.object.sha;\n                return nxGhApi('/repos/' + repo + '/git/commits/' + head).then(function (cm) {\n                    var chain = Promise.resolve([]), doneCnt = 0;\n                    items.forEach(function (it) {\n                        chain = chain.then(function (acc) {\n                            return blobOf(it).then(function (sh) {\n                                acc.push({ path: 'media/' + it.name, mode: '100644', type: 'blob', sha: sh });\n                                it.blob = null; // b359: файл отправлен — блоб больше не держим\n                                doneCnt++;\n                                try { nxProgress(0.15 + 0.7 * (doneCnt / items.length), 'Отправляю ' + doneCnt + '/' + items.length + ': ' + it.name); } catch (e) {}\n                                return nxYield();\n                            }).then(function () { return acc; });\n                        });\n                    });\n                    return chain.then(function (entries) {\n                        return nxGhApi('/repos/' + repo + '/git/trees', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ base_tree: cm.tree.sha, tree: entries }) }).then(function (tr) {\n                            return nxGhApi('/repos/' + repo + '/git/commits', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: 'авто: картинки из кэша игры -> media/ (' + entries.length + ')', parents: [head], tree: tr.sha }) }).then(function (nc) {\n                                return nxGhApi('/repos/' + repo + '/git/refs/heads/' + branch, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sha: nc.sha }) });\n                            });\n                        });\n                    });\n                });\n            });\n        }).then(function () { ok(); }).catch(function (e) {\n            if (n < 3 && /not a fast forward/i.test(String(e && e.message))) { setTimeout(function () { attempt(n + 1); }, 1500); return; }\n            fail(String((e && e.message) || e));\n        });\n    };\n    attempt(1);\n}\nfunction nxAutoMediaPushRun(manual, done) {\n    // b359: защита от параллельных запусков СТАВИТСЯ СРАЗУ. Раньше NX_MEDIA_PUSHING\n    // включался только после сбора картинок, поэтому несколько триггеров подряд\n    // (каждый новый арт в кэше зовёт nxMaybeAutoMediaPush) запускали по 2-3 сбора\n    // одновременно — память удваивалась ровно в момент игры.\n    if (NX_MEDIA_PUSHING) { if (done) done(0); return; }\n    NX_MEDIA_PUSHING = true;\n    var finish = function (sent) {\n        NX_MEDIA_PUSHING = false;\n        NX_MEDIA_LAST = Date.now(); // b359: троттлинг считаем и после ошибки:\n                                    // раньше неудача не обновляла NX_MEDIA_LAST,\n                                    // и авто-отправка долбила каждые 5 минут до краша вкладки\n        if (done) { try { done(sent || 0); } catch (e) {} }\n    };\n    if (!nxGhToken()) {\n        if (manual) { try { nxOwnerToast('Сначала сохраните токен GitHub в поле ниже — без него сайт не может отправить файлы', 'error'); } catch (e) {} var ti = document.getElementById('nx-gh-token'); if (ti) { ti.focus(); ti.scrollIntoView({ block: 'center' }); } }\n        finish(0); return;\n    }\n    var repo = nxGhRepoName();\n    var btn = document.getElementById('nx-push-media-btn'); if (manual && btn) btn.disabled = true;\n    var unblock = function () { if (manual && btn) btn.disabled = false; };\n    var cap = nxPushCap(manual);\n    nxStatus((manual ? '' : 'Автоотправка: ') + 'смотрю, какие картинки уже в кэше…');\n    var pendingAll = [];\n    try { pendingAll = nxPendingMediaList(); } catch (e) {}\n    nxCollectPendingMedia(cap).then(function (items) {\n        if (!items.length) {\n            if (manual) { nxStatus('Отправлять нечего: новых картинок в кэше нет. Нажмите «Шаг 1. Скачать все картинки»', 'err'); try { nxOwnerToast('В кэше нет новых картинок для отправки', 'error'); } catch (e) {} }\n            else nxStatus('');\n            unblock(); finish(0); return;\n        }\n        var rest = Math.max(0, pendingAll.length - items.length);\n        nxProgress(0.15, 'Отправляю ' + items.length + ' картинок в media/ репозитория' + (rest ? ' (осталось в очереди: ' + rest + ')' : '') + '…');\n        nxGhPushMedia(repo, items, function () {\n            var s = nxMediaPushedSet(); items.forEach(function (it) { s.add(it.name); }); nxMediaSavePushed(s);\n            nxProgress(1, 'Готово: ' + items.length + ' картинок ушло в media/' + (rest ? ', в очереди ещё ' + rest : '') + '. GitHub Pages обновится за 1–2 минуты', 'ok');\n            nxStatus('Отправлено в ' + repo + '/media/: ' + items.map(function (x) { return x.name; }).join(', '), 'ok');\n            try { nxOwnerToast('Картинки отправлены на GitHub (' + items.length + ' шт. в media/)' + (rest ? ' — остальные дойдут следующими заходами' : ''), 'success'); } catch (e) {}\n            unblock(); finish(items.length);\n            // b359: остаток очереди — следующим заходом, не сейчас (память и канал)\n            if (rest > 0) { try { nxMaybeAutoMediaPush(false); } catch (e) {} }\n        }, function (msg) {\n            nxProgress(0, ''); nxStatus('Ошибка отправки на GitHub: ' + msg, 'err');\n            if (manual) { try { nxOwnerToast('Ошибка отправки: ' + msg, 'error'); } catch (e) {} }\n            unblock(); finish(0);\n        });\n    }, function () { unblock(); finish(0); });"),
    ('beat-read',
     "        const beat = parseInt(LS.getItem('nx_beat') || '0', 10);\n        LS.setItem('nx_bye', '');",
     "        const beatRaw = String(LS.getItem('nx_beat') || '0');\n        const beat = parseInt(beatRaw, 10) || 0;\n        const beatSnap = beatRaw.indexOf('|') > 0 ? beatRaw.slice(beatRaw.indexOf('|')) : '';\n        LS.setItem('nx_bye', '');"),
    ('crashlog-snap',
     "            nxCrashLog('подозрение на аварийное завершение прошлой сессии (белый экран/OOM)');",
     "            nxCrashLog('подозрение на аварийное завершение прошлой сессии (белый экран/OOM). Последний пульс' + (beatSnap ? ' ' + beatSnap : '') + ', возраст ' + Math.round((Date.now() - beat) / 1000) + ' с');\n            // b358: два аварийных завершения подряд — устройство 3D не тянет,\n            // сами переводим игры в плоский режим (в Студии 3D можно вернуть)\n            try {\n                const hc = (parseInt(LS.getItem('nx_hard_crash') || '0', 10) || 0) + 1;\n                LS.setItem('nx_hard_crash', String(hc));\n                if (hc >= 2 && !nxForce3d()) {\n                    LS.setItem('nx_weak_gpu', '1');\n                    setTimeout(() => { try { showToast('Прошлые сессии обрывались браузером (нехватка памяти) — 3D отключено, игры в плоском режиме. Вернуть 3D можно в Студии', 'error'); } catch (e) {} }, 3200);\n                }\n            } catch (e) {}"),
    ('beat-setInterval',
     "        setInterval(() => { try { LS.setItem('nx_beat', String(Date.now())); } catch (e) {} }, 5000);",
     "        // b358: в «пульс» пишем не только время, но и слепок состояния (heap,\n        // число живых 3D-контекстов, размер кэша картинок). Когда вкладку убивает\n        // браузер, JS не успевает записать ничего — зато последний пульс за 0–5 с до\n        // смерти остаётся, и в журнале аварий видно, что именно её добило.\n        setInterval(() => {\n            try {\n                var snap = '';\n                try {\n                    var pm = (window.performance && performance.memory) ? performance.memory : null;\n                    var heapMB = pm ? Math.round(pm.usedJSHeapSize / 1048576) : -1;\n                    var live3d = 0;\n                    try {\n                        live3d = (typeof slots !== 'undefined' && slots.renderer ? 1 : 0)\n                            + (typeof grid3d !== 'undefined' && grid3d.renderer ? 1 : 0)\n                            + (typeof wheel !== 'undefined' && wheel.renderer ? 1 : 0)\n                            + (typeof lines3d !== 'undefined' && lines3d.renderer ? 1 : 0)\n                            + (typeof battle3d !== 'undefined' && battle3d ? 1 : 0);\n                    } catch (e) {}\n                    var imgN = -1; try { imgN = (typeof IMG_OBJ !== 'undefined' && IMG_OBJ.size != null) ? IMG_OBJ.size : -1; } catch (e) {}\n                    snap = '|heap:' + heapMB + 'MB|3d:' + live3d + '|img:' + imgN;\n                } catch (e) {}\n                LS.setItem('nx_beat', String(Date.now()) + snap);\n            } catch (e) {}\n        }, 5000);"),
    ('bye-reset',
     "        const byeFn = () => { try { LS.setItem('nx_bye', '1'); } catch (e) {} };",
     "        const byeFn = () => { try { LS.setItem('nx_bye', '1'); LS.setItem('nx_hard_crash', '0'); } catch (e) {} };"),
    ('memguard-pause',
     "        try { nx3dReleaseHidden('__all__'); } catch (e) {}",
     "        try { nx3dPauseAll(); } catch (e) {} // b357: сначала остановить кадры, потом отдавать контексты\n        try { nx3dReleaseHidden('__all__'); } catch (e) {}"),
]

def apply(text, edits, log):
    for label, old, new in edits:
        c = text.count(old)
        if c == 1:
            text = text.replace(old, new, 1)
            log.append("  · %s: применено" % label)
        elif c == 0 and text.count(new) >= 1:
            log.append("  · %s: уже применено" % label)
        else:
            log.append("  ! %s: НАЙДЕНО %d вхождений — правка НЕ применена" % (label, c))
    return text


def crlf(text):
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "check"
    log = []
    if target in ("assets", "check"):
        for name, edits in (("app.js", APP_EDITS), ("qr-transfer.js", QR_EDITS)):
            p = os.path.join(ROOT, "assets", name)
            t = io.open(p, encoding="utf-8").read()
            t2 = apply(t, edits, log)
            bad = [l for l in log if l.strip().startswith("!")]
            print("assets/%s:" % name); print("\n".join(log)); log = []
            if bad:
                print("  ЕСТЬ НЕПРИМЕНЁННЫЕ ПРАВКИ — файл не записан"); return 1
            if target == "assets" and t2 != t:
                io.open(p, "w", encoding="utf-8", newline="").write(t2)
                print("  записано")
    if target == "monolith":
        p = os.path.join(ROOT, "tools", "source-index.html")
        # читаем с универсальными переводами строк (CRLF -> LF), правим LF-текст,
        # пишем обратно newline=None -> LF снова станет CRLF, как в монолите
        t = io.open(p, encoding="utf-8").read()
        all_edits = [(l, o, n) for l, o, n in APP_EDITS + QR_EDITS]
        t2 = apply(t, all_edits, log)
        bad = [l for l in log if l.strip().startswith("!")]
        print("tools/source-index.html (блоки app_js + qr_xfer):"); print("\n".join(log)); log = []
        if bad:
            print("ЕСТЬ НЕПРИМЕНЁННЫЕ ПРАВКИ — монолит не записан"); return 1
        if t2 != t:
            # newline='\r\n': монолит хранится с CRLF — при записи LF обязан стать CRLF
            io.open(p, "w", encoding="utf-8", newline="\r\n").write(t2)
            print("  записано (%+d строк)" % (t2.count("\n") - t.count("\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
