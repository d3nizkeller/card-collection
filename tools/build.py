#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборка мобильно-оптимизированной версии «Коллекционер карт».

Было: один index.html на 3.2 МБ, внутри — JIT-компилятор Tailwind (пересобирает
CSS прямо в браузере при каждой мутации DOM), Font Awesome целиком (шрифт трижды),
three.js, и весь код игры. На телефоне это = долгий парсинг + постоянные
пересборки CSS в главном потоке + ~91 МБ распакованных картинок.

Стало: тонкий index.html (~0.25 МБ разметки) + отдельные кешируемые файлы.

Вход :  tools/source-index.html   — исходный монолит (копия текущего index.html)
Выход:  index.html, assets/*, media/t/*.webp

Запуск:  python3 tools/build.py            (пересобрать всё)
         python3 tools/build.py --no-media (не перегенерировать миниатюры)

Скрипт идемпотентен: его можно запускать после каждой правки игры.
Если вы правите сам index.html напрямую — сначала верните его в
tools/source-index.html, потом запускайте сборку.
"""

import base64
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'tools', 'source-index.html')
ASSETS = os.path.join(ROOT, 'assets')
MEDIA = os.path.join(ROOT, 'media')
THUMBS = os.path.join(MEDIA, 't')
MIDS = os.path.join(MEDIA, 't2')

BUILD_TAG = 'nxmob55'          # b382: защита будущих карт: меморизация отсутствующих миниатюр, --report, cron в CI — клиенты должны перечитать app.js
THUMB_W = 256                 # мелкая миниатюра (списки, компактные сетки), px
THUMB_Q = 72
MID_W = 512                   # средняя (обычные сетки, вскрытие пака), px
MID_Q = 78
MID_MIN_SRC = 640             # средняя миниатюра нужна только если мастер шире этого
# ВАЖНО: миниатюры строятся для ВСЕХ файлов media/, а не только для упомянутых
# в index.html. Каталог карт приходит из облака комнаты (textdb.dev) и ссылается
# на media/card_*.png напрямую — в HTML этих имён нет, но файлы рабочие.

log = []


def say(msg):
    print(msg)
    log.append(msg)


# --------------------------------------------------------------------------- #
# 0. читаем исходник (CRLF сохраняем как есть)
# --------------------------------------------------------------------------- #
def read_lines(path):
    with open(path, 'rb') as f:
        data = f.read().decode('utf-8')
    return data.split('\r\n')


def write_crlf(path, text):
    with open(path, 'wb') as f:
        f.write(text.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))


def write_lf(path, text):
    with open(path, 'wb') as f:
        f.write(text.replace('\r\n', '\n').encode('utf-8'))


# --------------------------------------------------------------------------- #
# 1. границы блоков в исходном монолите (1-based, включительно)
#    проверяем содержимое — если источник изменился, сборка упадёт громко,
#    а не молча соберёт кашу
# --------------------------------------------------------------------------- #
BLOCKS = {
    'tw_cdn':    (19, 105,    'script', 'Tailwind Play CDN'),
    'tw_config': (106, 122,   'script', 'tailwind.config'),
    'three':     (123, 132,   'script', 'three.js r128'),
    'fa':        (133, 144,   'style',  'Font Awesome 6.4.0'),
    'app_css':   (146, 1087,  'style',  'основной CSS игры'),
    'app_js':    (3619, 18863, 'script', 'код игры'),   # b355-b358: границы пересчитаны после правок монолита
    'stories':   (18864, 19605, 'script', 'нарезчик сторис 9:16'),
    'qrcode':    (19606, 19610, 'script', 'qrcode.js'),
    'qr_xfer':   (19611, 21358, 'script', 'перенос прогресса по QR'),  # b359-b360
}

# --------------------------------------------------------------------------- #
# b378: блок управления профилем-синхронизацией убран из модалки QR по просьбе
# владельца («Профиль: код … / устройств: … / синхронизация: …» + кнопки
# «Ввести код», «Ссылка на устройство», «Синхронизировать», «Отвязать»).
# Функционально ничего не теряется: ручной ввод кода живёт в #qr-paste-details,
# привязка по ссылке ?prof=CODE срабатывает при открытии (profInit),
# фоновая автосинхронизация профиля (b364/b365) не тронута. profUI() сама
# проверяет наличие #qr-prof-row и без него просто ничего не рисует.
# --------------------------------------------------------------------------- #
MARKUP_PROF_BLOCK_OLD = '\r\n'.join([
    '                <div id="qr-prof-row" class="flex flex-wrap items-center justify-center gap-1.5"></div>',
    '                <div class="flex flex-wrap justify-center gap-1.5">',
    '                    <button type="button" onclick="profEnterCode()" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-[10px] font-bold transition"><i class="fa-solid fa-keyboard mr-1"></i>Ввести код</button>',
    '                    <button type="button" onclick="profCopyLink()" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-[10px] font-bold transition"><i class="fa-solid fa-link mr-1"></i>Ссылка на устройство</button>',
    '                    <button type="button" onclick="profSyncNowBtn()" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-[10px] font-bold transition"><i class="fa-solid fa-arrows-rotate mr-1"></i>Синхронизировать</button>',
    '                    <button type="button" onclick="profUnlink()" class="px-2.5 py-1.5 rounded-lg bg-slate-950 hover:bg-rose-950/60 border border-slate-800 hover:border-rose-800/60 text-slate-400 hover:text-rose-300 text-[10px] font-bold transition"><i class="fa-solid fa-link-slash mr-1"></i>Отвязать</button>',
    '                </div>',
])

# --------------------------------------------------------------------------- #
# b379: СИНХРОНИЗАЦИЯ ПРОФИЛЕЙ УДАЛЕНА ЦЕЛИКОМ (решение владельца).
#
# Было (b364-b375): устройства одного пользователя привязывались кодом профиля
# (вручную, ссылкой ?prof=CODE или QR), общий баланс/коллекция/прогресс
# ездили через облачный документ textdb nexus-tcg-prof-<code> и сливались
# правилами profMergeState.
#
# Стало: подсистема выключена в точках входа, целиком и необратимо для игрока:
#   · profCode()      всегда ''  — устройство считается непривязанным;
#   · profSetCode()   не привязывает;
#   · profInit()      не читает ?prof=, не ставит таймеры и слушатели;
#   · profSyncOnce()  не ходит в сеть и не сливает состояния;
#   · profSyncSoon()/profFlush() не планируют отправку;
#   · profQrFromText() не распознаёт коды профиля;
#   · QR-перенос больше не несёт код профиля и не привязывает устройство.
# Точки входа выбраны так, что весь остальной код подсистемы становится
# недостижимым, а комнатное облако (каталог, биржа, джекпот) и разовый
# QR-перенос прогресса работают как раньше. Уже привязанные устройства просто
# становятся самостоятельными: их баланс остаётся последним слитым.
# --------------------------------------------------------------------------- #
PROFKILL_JS = [
    ('profCode всегда пустой',
     "        function profCode() { try { return String(LS.getItem('nx_prof_code') || '').toUpperCase(); } catch (e) { return ''; } }",
     "        function profCode() { return ''; } // b379: синхронизация профилей удалена"),
    ('profSyncOnce не ходит в сеть и не сливает',
     "        function profSyncOnce(force) {\n            const key = profDocKey();",
     "        function profSyncOnce(force) {\n            return Promise.resolve(false); // b379: синхронизация профилей удалена\n            const key = profDocKey();"),
    ('profSyncSoon не планирует отправку',
     "        function profSyncSoon() { clearTimeout(profT); profT = setTimeout(() => { profSyncOnce(false); }, 1500); }",
     "        function profSyncSoon() {} // b379: синхронизация профилей удалена"),
    ('profFlush не отправляет',
     "        function profFlush() { // аварийная отправка при скрытии вкладки: моя дельта не должна потеряться\n            try {",
     "        function profFlush() { // b379: синхронизация профилей удалена\n            return;\n            try {"),
    ('profInit не стартует подсистему',
     "        function profInit() {\n            try {\n                const m = String(location.search || '').match(/[?&]prof=([a-zA-Z0-9-]{4,12})/);",
     "        function profInit() {\n            return; // b379: синхронизация профилей удалена — код из ссылки не читаем, таймеры не ставим\n            try {\n                const m = String(location.search || '').match(/[?&]prof=([a-zA-Z0-9-]{4,12})/);"),
    ('profSetCode не привязывает устройство',
     "        function profSetCode(code, silent) {\n            code = String(code || '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 12);",
     "        function profSetCode(code, silent) {\n            return ''; // b379: синхронизация профилей удалена — привязка невозможна\n            code = String(code || '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 12);"),
    ('profQrFromText не распознаёт коды профиля',
     "        function profQrFromText(raw) { // распознать код профиля из отсканированного текста; '' — не профиль\n            const s = String(raw || '').trim();",
     "        function profQrFromText(raw) { // b379: синхронизация профилей удалена\n            return '';\n            const s = String(raw || '').trim();"),
]

PROFKILL_QR = [
    ('QR больше не несёт код профиля',
     "        try { let pc = profCode(); if (!pc) { pc = profGenCode(); profSetCode(pc, true); } snap.prof = pc; } catch (e) {}",
     "        // b379: синхронизация профилей удалена — QR несёт только снимок прогресса"),
    ('вставленный текст ?prof=/NXPROF: не считается кодом переноса',
     "    if (/[?&]prof=[A-Za-z0-9-]{4,12}/i.test(t)) return true;  // b365: QR профиля синхронизации\n    if (/^NXPROF:[A-Za-z0-9]{4,12}$/i.test(t)) return true;   // b365: голый код профиля\n",
     ""),
    ('qrxApplyProf не привязывает устройство',
     "function qrxApplyProf(o) { // b366: в коде переноса может лежать код профиля — привязываем устройство сразу\n    try {",
     "function qrxApplyProf(o) { // b379: синхронизация профилей удалена\n    return;\n    try {"),
]

# --------------------------------------------------------------------------- #
# b380: котик-шахтёр РАБОТАЕТ киркой; скала и берлога прокачиваются.
# Новый режим сцены 'work' (кирка поднята и бьёт по скале, щепа летит) вместо
# прежнего вечного сна, пока копилка не набрана. Внешний вид скалы и берлоги
# имеет 4 tier-а по уровню кирки: 1-4 / 5-9 / 10-19 / 20+ (крепь, фонари,
# рельсы, гирлянда; на скале: трещины -> руда -> кристаллы -> золотые жилы).
# --------------------------------------------------------------------------- #
SCENE_SVG_INSERT = '<!-- b383: пещера прокачивается вместе с киркой: 10 биомов (фон + крепь + скала).\n     Границы уровней: 1-2 / 3-4 / 5-9 / 10-19 / 20-34 / 35+. Переключает JS\n     (minerSceneRender), лишние группы display:none. Фон меняется ЦЕЛИКОМ:\n     порода, пол, свет и реквизит — каждое улучшение видно сразу. -->\n<path d="M4 120Q2 36 60 26Q118 36 116 120Z" fill="#0b1220"/>\n<g id="kc-bg-0"><path d="M10 118Q8 44 60 34Q112 44 110 118Z" fill="#241a12"/><path d="M28 60q6 10 2 22M84 56q-5 12-1 24M56 40q3 8 0 14" fill="none" stroke="#171009" stroke-width="1.6" opacity=".8"/><path d="M18 78q8-6 12 2M96 84q-8-6-12 2" fill="none" stroke="#57432c" stroke-width="1.4" opacity=".7"/><rect x="4" y="112" width="112" height="10" fill="#201509"/><ellipse cx="30" cy="115" rx="10" ry="2.6" fill="#2b1c0e"/><ellipse cx="86" cy="117" rx="12" ry="2.4" fill="#2b1c0e"/><ellipse cx="46" cy="114" rx="30" ry="6" fill="#f59e0b" opacity=".06"/><rect x="20" y="104" width="2.4" height="8" rx="1" fill="#78350f"/><circle cx="21.2" cy="102.6" r="2.6" fill="url(#kc-lamp-grad)"/><circle cx="21.2" cy="102.6" r="1.1" fill="#fde68a"/></g>\n<g id="kc-bg-1" style="display:none"><path d="M10 118Q8 44 60 34Q112 44 110 118Z" fill="#2b2016"/><g stroke="#3a2b1c" stroke-width="1.2" opacity=".8"><path d="M24 46v70M40 38v78M60 35v81M80 38v78M96 46v70"/></g><rect x="4" y="112" width="112" height="10" fill="#26190e"/><g fill="#3a2b1c"><rect x="6" y="113" width="16" height="2" rx="1"/><rect x="30" y="116" width="18" height="2" rx="1"/><rect x="62" y="113.6" width="16" height="2" rx="1"/><rect x="88" y="116.4" width="18" height="2" rx="1"/></g><path d="M60 30v10" stroke="#0f172a" stroke-width="1.4"/><rect x="56.6" y="38" width="6.8" height="8" rx="2" fill="#0f172a"/><circle cx="60" cy="42" r="7" fill="url(#kc-lamp-grad)"/><circle cx="60" cy="42" r="2.4" fill="#fde68a"/><path d="M14 66h10M14 66v10" stroke="#0f172a" stroke-width="1.2"/><path d="M16 68l6 6M22 68l-6 6" stroke="#57534e" stroke-width="1.4"/><ellipse cx="46" cy="114" rx="34" ry="6.5" fill="#f59e0b" opacity=".1"/></g>\n<g id="kc-bg-2" style="display:none"><path d="M10 118Q8 44 60 34Q112 44 110 118Z" fill="#232d38"/><g stroke="#2f3b49" stroke-width="1.2" opacity=".9"><path d="M14 62h20M34 52h22M56 44h22M78 52h20M20 82h24M64 82h26M14 100h30M62 100h32"/></g><rect x="4" y="112" width="112" height="10" fill="#1a222c"/><g fill="#3f3f46"><rect x="8" y="114" width="4" height="6"/><rect x="24" y="114" width="4" height="6"/><rect x="40" y="114" width="4" height="6"/><rect x="56" y="114" width="4" height="6"/><rect x="72" y="114" width="4" height="6"/><rect x="88" y="114" width="4" height="6"/><rect x="104" y="114" width="4" height="6"/></g><rect x="7" y="113.2" width="106" height="1.6" fill="#64748b"/><rect x="7" y="118.4" width="106" height="1.6" fill="#64748b"/><g><rect x="12" y="100" width="16" height="9" rx="2" fill="#334155"/><circle cx="16" cy="110" r="2.4" fill="#0f172a"/><circle cx="24" cy="110" r="2.4" fill="#0f172a"/><path d="M14 100l3-5h8l3 5" fill="#475569"/></g><circle cx="14" cy="56" r="6" fill="url(#kc-lamp-grad)"/><circle cx="14" cy="56" r="2" fill="#fde68a"/><circle cx="106" cy="56" r="6" fill="url(#kc-lamp-grad)"/><circle cx="106" cy="56" r="2" fill="#fde68a"/><g fill="#b45309"><circle cx="44" cy="70" r="1.6"/><circle cx="70" cy="64" r="1.4"/><circle cx="88" cy="76" r="1.7"/><circle cx="34" cy="92" r="1.5"/></g><ellipse cx="46" cy="114" rx="36" ry="6.5" fill="#f59e0b" opacity=".12"/></g>\n<g id="kc-bg-3" style="display:none"><path d="M10 118Q8 44 60 34Q112 44 110 118Z" fill="#1c2740"/><g stroke="#33415c" stroke-width="1.1" opacity=".9"><path d="M20 56l14-8 12 10M62 44l14 6 12-6M24 84l16-6 14 8M70 82l16-6 12 8"/></g><rect x="4" y="112" width="112" height="10" fill="#16203a"/><path d="M8 116q14-3 26 0t26 0 26 0 26 0" fill="none" stroke="#22d3ee" stroke-width="1.2" opacity=".45"/><g><path d="M18 112l4-12 4 12Z" fill="#22d3ee" opacity=".8"/><path d="M26 112l3-8 3 8Z" fill="#67e8f9" opacity=".7"/><path d="M92 112l4-14 4 14Z" fill="#a78bfa" opacity=".8"/><path d="M100 112l3-9 3 9Z" fill="#22d3ee" opacity=".7"/></g><g><path d="M36 34l3 8-3 3-3-3Z" fill="#67e8f9" opacity=".8"/><path d="M76 34l3 9-3 3-3-3Z" fill="#a78bfa" opacity=".8"/><path d="M56 30l2.6 7-2.6 3-2.6-3Z" fill="#e0f2fe" opacity=".85"/></g><ellipse cx="60" cy="70" rx="44" ry="34" fill="#67e8f9" opacity=".07"/><ellipse cx="46" cy="114" rx="36" ry="6.5" fill="#22d3ee" opacity=".1"/></g>\n<g id="kc-bg-4" style="display:none"><path d="M10 118Q8 44 60 34Q112 44 110 118Z" fill="#33230f"/><g stroke="#fbbf24" stroke-width="1.5" opacity=".55" fill="none"><path d="M18 62q10 6 8 16t10 14M96 58q-8 8-6 18t-10 12M40 40q6 8 2 14M78 42q-4 8 0 14"/></g><rect x="4" y="112" width="112" height="10" fill="#2a1c0c"/><g fill="#fcd34d"><circle cx="96" cy="110" r="2.2"/><circle cx="101" cy="112" r="2.6"/><circle cx="92" cy="112.6" r="2"/><circle cx="98" cy="107" r="1.8"/><circle cx="104" cy="108.6" r="1.6"/></g><path d="M88 112q10-8 20 0Z" fill="#b45309" opacity=".8"/><g fill="#fbbf24" opacity=".8"><circle cx="26" cy="74" r="1.4"/><circle cx="48" cy="62" r="1.2"/><circle cx="72" cy="70" r="1.5"/><circle cx="38" cy="94" r="1.3"/><circle cx="84" cy="92" r="1.4"/></g><circle cx="14" cy="54" r="7" fill="url(#kc-lamp-grad)"/><circle cx="14" cy="54" r="2.4" fill="#fffbeb"/><circle cx="106" cy="54" r="7" fill="url(#kc-lamp-grad)"/><circle cx="106" cy="54" r="2.4" fill="#fffbeb"/><ellipse cx="46" cy="114" rx="38" ry="7" fill="#fbbf24" opacity=".14"/></g>\n<g id="kc-bg-5" style="display:none"><path d="M10 118Q8 44 60 34Q112 44 110 118Z" fill="#241432"/><g stroke="#3b2a52" stroke-width="1.2" opacity=".9"><path d="M18 58l16-8 14 10M64 44l16 6 12-8M22 86l18-6 14 8M72 84l16-6 12 8"/></g><rect x="4" y="112" width="112" height="10" fill="#1b1026"/><path d="M6 116q16-4 30 0t30 0 30 0 18 0" fill="none" stroke="#f97316" stroke-width="1.6" opacity=".6"/><path d="M10 119q18-3 34 0t34 0 32 0" fill="none" stroke="#fb7185" stroke-width="1" opacity=".4"/><g fill="#e0f2fe"><path d="M30 60l2.2-5.4 2.2 5.4-2.2 1.8Z"/><path d="M84 56l2.2-5.4 2.2 5.4-2.2 1.8Z"/><path d="M58 40l1.8-4.4 1.8 4.4-1.8 1.5Z"/><path d="M44 84l1.8-4.4 1.8 4.4-1.8 1.5Z"/><path d="M76 88l1.8-4.4 1.8 4.4-1.8 1.5Z"/></g><g><path d="M16 112l4-13 4 13Z" fill="#e0f2fe" opacity=".85"/><path d="M96 112l4-15 4 15Z" fill="#a78bfa" opacity=".85"/><path d="M24 112l3-9 3 9Z" fill="#67e8f9" opacity=".8"/></g><path d="M44 30h32l-4 6h-24Z" fill="#7c3aed" opacity=".7"/><path d="M48 36l2 5 2-5M58 36l2 5 2-5M68 36l2 5 2-5" stroke="#fcd34d" stroke-width="1.2" fill="none"/><ellipse cx="60" cy="72" rx="46" ry="36" fill="#f97316" opacity=".06"/><ellipse cx="46" cy="114" rx="38" ry="7" fill="#e0f2fe" opacity=".08"/></g>\n<g id="kc-bg-6" style="display:none"><path d="M10 118Q8 44 60 34Q112 44 110 118Z" fill="#2a0f0a"/><g stroke="#3d150c" stroke-width="1.2" opacity=".9"><path d="M18 58l16-8 14 10M64 44l16 6 12-8M22 86l18-6 14 8M72 84l16-6 12 8"/></g><rect x="4" y="112" width="112" height="10" fill="#1c0906"/><path d="M4 116q18-3 34 0t34 0 34 0" fill="none" stroke="#f97316" stroke-width="2.4" opacity=".8"/><path d="M8 118q20-2 38 0t38 0 28 0" fill="none" stroke="#fbbf24" stroke-width="1" opacity=".7"/><g fill="#fb923c"><circle cx="30" cy="98" r="1.1"/><circle cx="44" cy="88" r=".9"/><circle cx="70" cy="94" r="1.2"/><circle cx="86" cy="84" r=".9"/><circle cx="58" cy="78" r=".8"/></g><g><rect x="14" y="102" width="14" height="4" rx="1.4" fill="#0f172a"/><rect x="17" y="106" width="8" height="6" rx="1.6" fill="#1e293b"/><rect x="12.6" y="100.6" width="16.8" height="2.4" rx="1.2" fill="#334155"/></g><circle cx="100" cy="104" r="6" fill="#f97316" opacity=".25"/><path d="M96 108q4-6 8 0Z" fill="#fbbf24" opacity=".8"/><ellipse cx="60" cy="72" rx="46" ry="36" fill="#f97316" opacity=".08"/><ellipse cx="46" cy="114" rx="38" ry="7" fill="#fb923c" opacity=".12"/></g>\n<g id="kc-bg-7" style="display:none"><path d="M10 118Q8 44 60 34Q112 44 110 118Z" fill="#10202c"/><g stroke="#1d3a4a" stroke-width="1.2" opacity=".9"><path d="M22 40v76M40 35v81M60 33v83M80 35v81M98 40v76"/></g><rect x="4" y="112" width="112" height="10" fill="#0b1720"/><g stroke="#7dd3fc" stroke-width=".8" opacity=".3"><path d="M7 114h106M7 117.5h106M7 121h106"/></g><path d="M16 70l8-6 6 8 8-6M72 62l8-6 6 8 8-6" fill="none" stroke="#e0f2fe" stroke-width="1.2" opacity=".7"/><g fill="#0f2530"><rect x="8" y="52" width="7" height="62" rx="2"/><rect x="105" y="52" width="7" height="62" rx="2"/></g><g fill="#16303e"><rect x="6.6" y="49" width="9.8" height="4" rx="1.6"/><rect x="103.6" y="49" width="9.8" height="4" rx="1.6"/></g><circle cx="11.5" cy="58" r="5.4" fill="#7dd3fc" opacity=".22"/><circle cx="108.5" cy="58" r="5.4" fill="#7dd3fc" opacity=".22"/><circle cx="11.5" cy="58" r="1.8" fill="#e0f2fe"/><circle cx="108.5" cy="58" r="1.8" fill="#e0f2fe"/><ellipse cx="60" cy="70" rx="44" ry="34" fill="#7dd3fc" opacity=".07"/><ellipse cx="46" cy="114" rx="36" ry="6.5" fill="#e0f2fe" opacity=".08"/></g>\n<g id="kc-bg-8" style="display:none"><path d="M10 118Q8 44 60 34Q112 44 110 118Z" fill="#2a0a12"/><g stroke="#e7d8c9" stroke-width="1.6" opacity=".5" fill="none"><path d="M20 116Q18 74 34 52M34 116Q34 78 46 60M86 116Q88 74 72 52M100 116Q100 78 88 60"/></g><rect x="4" y="112" width="112" height="10" fill="#3b1a08"/><g fill="#b45309"><ellipse cx="20" cy="113" rx="14" ry="4"/><ellipse cx="52" cy="115" rx="18" ry="4.4"/><ellipse cx="88" cy="113" rx="16" ry="4"/></g><g fill="#fcd34d"><circle cx="16" cy="111.6" r="1.6"/><circle cx="26" cy="112.4" r="1.4"/><circle cx="46" cy="113.6" r="1.7"/><circle cx="58" cy="114.4" r="1.4"/><circle cx="84" cy="111.8" r="1.6"/><circle cx="94" cy="112.6" r="1.4"/></g><g><circle cx="38" cy="110" r="1.8" fill="#ef4444"/><circle cx="70" cy="112" r="1.6" fill="#22d3ee"/><circle cx="102" cy="110.4" r="1.5" fill="#a78bfa"/></g><ellipse cx="60" cy="72" rx="46" ry="36" fill="#f59e0b" opacity=".1"/><ellipse cx="46" cy="114" rx="38" ry="7" fill="#fcd34d" opacity=".12"/></g>\n<g id="kc-bg-9" style="display:none"><path d="M10 118Q8 44 60 34Q112 44 110 118Z" fill="#0b1026"/><g fill="#e0e7ff"><circle cx="22" cy="52" r=".9"/><circle cx="34" cy="42" r=".7"/><circle cx="50" cy="38" r=".8"/><circle cx="70" cy="40" r=".7"/><circle cx="86" cy="46" r=".9"/><circle cx="98" cy="58" r=".7"/><circle cx="28" cy="76" r=".7"/><circle cx="92" cy="80" r=".8"/><circle cx="60" cy="34" r=".6"/></g><ellipse cx="38" cy="60" rx="20" ry="14" fill="#6d28d9" opacity=".16"/><ellipse cx="82" cy="66" rx="18" ry="12" fill="#0ea5e9" opacity=".13"/><path d="M14 44q20-10 46-8t46 8" fill="none" stroke="#22d3ee" stroke-width="1.2" opacity=".35"/><path d="M18 50q20-9 42-7t42 7" fill="none" stroke="#a78bfa" stroke-width="1" opacity=".35"/><rect x="4" y="112" width="112" height="10" fill="#0a0f22"/><path d="M6 116q18-3 34 0t34 0 34 0" fill="none" stroke="#a5b4fc" stroke-width="1.2" opacity=".5"/><g><path d="M30 84l2.6-6.4 2.6 6.4-2.6 2Z" fill="#a5b4fc" opacity=".85"/><path d="M84 78l2.6-6.4 2.6 6.4-2.6 2Z" fill="#e0e7ff" opacity=".85"/><path d="M58 90l2.2-5.4 2.2 5.4-2.2 1.8Z" fill="#67e8f9" opacity=".8"/></g><ellipse cx="60" cy="70" rx="46" ry="36" fill="#a5b4fc" opacity=".07"/><ellipse cx="46" cy="114" rx="38" ry="7" fill="#e0e7ff" opacity=".09"/></g>\n<g id="kc-den-0"><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#6b4a2f" stroke-width="7" opacity=".85"/><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#57534e" stroke-width="2.4" stroke-dasharray="3 6" opacity=".75"/><rect x="14" y="52" width="4" height="64" rx="2" fill="#78350f" transform="rotate(-4 16 84)"/><rect x="101" y="56" width="4" height="60" rx="2" fill="#78350f" transform="rotate(5 103 86)"/></g>\n<g id="kc-den-1" style="display:none"><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#7c5a3a" stroke-width="8" opacity=".9"/><rect x="11" y="46" width="6" height="70" rx="2" fill="#92400e"/><rect x="103" y="46" width="6" height="70" rx="2" fill="#92400e"/><rect x="7" y="41" width="106" height="6" rx="3" fill="#92400e"/><circle cx="14" cy="56" r="6.5" fill="url(#kc-lamp-grad)"/><rect x="12.4" y="52" width="3.2" height="6" rx="1.4" fill="#0f172a"/><circle cx="14" cy="56" r="2.2" fill="#fde68a"/></g>\n<g id="kc-den-2" style="display:none"><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#8a6540" stroke-width="8" opacity=".92"/><rect x="11" y="46" width="6" height="70" rx="2" fill="#a16207"/><rect x="103" y="46" width="6" height="70" rx="2" fill="#a16207"/><rect x="7" y="41" width="106" height="6" rx="3" fill="#a16207"/><rect x="9" y="43" width="102" height="1.6" fill="#fbbf24" opacity=".35"/><circle cx="14" cy="56" r="6.5" fill="url(#kc-lamp-grad)"/><circle cx="14" cy="56" r="2.2" fill="#fde68a"/><circle cx="106" cy="56" r="6.5" fill="url(#kc-lamp-grad)"/><circle cx="106" cy="56" r="2.2" fill="#fde68a"/><g fill="#3f3f46"><rect x="18" y="115" width="3" height="5"/><rect x="34" y="115" width="3" height="5"/><rect x="50" y="115" width="3" height="5"/><rect x="66" y="115" width="3" height="5"/></g><rect x="7" y="113.4" width="68" height="1.8" fill="#64748b"/></g>\n<g id="kc-den-3" style="display:none"><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#9a744a" stroke-width="9" opacity=".95"/><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#fbbf24" stroke-width="1.6" opacity=".5"/><rect x="11" y="46" width="6" height="70" rx="2" fill="#b45309"/><rect x="103" y="46" width="6" height="70" rx="2" fill="#b45309"/><rect x="7" y="41" width="106" height="6" rx="3" fill="#b45309"/><rect x="9" y="43" width="102" height="2" fill="#fbbf24" opacity=".75"/><g><circle cx="24" cy="47" r="1.5" fill="#fde68a"/><circle cx="40" cy="45.4" r="1.5" fill="#fca5a5"/><circle cx="56" cy="44.6" r="1.5" fill="#a7f3d0"/><circle cx="72" cy="45.2" r="1.5" fill="#93c5fd"/><circle cx="88" cy="46.6" r="1.5" fill="#fde68a"/></g><circle cx="14" cy="56" r="7.5" fill="url(#kc-lamp-grad)"/><circle cx="14" cy="56" r="2.4" fill="#fffbeb"/><circle cx="106" cy="56" r="7.5" fill="url(#kc-lamp-grad)"/><circle cx="106" cy="56" r="2.4" fill="#fffbeb"/><path d="M20 96l3.4-8 3.4 8-3.4 2.6Z" fill="#22d3ee" opacity=".8"/><path d="M96 100l3-7 3 7-3 2.4Z" fill="#a78bfa" opacity=".8"/><g fill="#3f3f46"><rect x="18" y="115" width="3" height="5"/><rect x="34" y="115" width="3" height="5"/><rect x="50" y="115" width="3" height="5"/><rect x="66" y="115" width="3" height="5"/></g><rect x="7" y="113.4" width="68" height="1.8" fill="#94a3b8"/></g>\n<g id="kc-den-4" style="display:none"><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#155e75" stroke-width="9" opacity=".95"/><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#67e8f9" stroke-width="2" opacity=".8"/><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#a78bfa" stroke-width="1.2" stroke-dasharray="4 7" opacity=".7"/><g><path d="M20 44l3-8 3 8-3 2.4Z" fill="#22d3ee"/><path d="M52 30l2.6-7 2.6 7-2.6 2Z" fill="#e0f2fe"/><path d="M92 44l3-8 3 8-3 2.4Z" fill="#a78bfa"/></g><circle cx="14" cy="56" r="7" fill="url(#kc-lamp-grad)"/><circle cx="14" cy="56" r="2.4" fill="#cffafe"/><circle cx="106" cy="56" r="7" fill="url(#kc-lamp-grad)"/><circle cx="106" cy="56" r="2.4" fill="#ddd6fe"/><g fill="#334155"><rect x="18" y="115" width="3" height="5"/><rect x="34" y="115" width="3" height="5"/><rect x="50" y="115" width="3" height="5"/><rect x="66" y="115" width="3" height="5"/></g><rect x="7" y="113.4" width="68" height="1.8" fill="#67e8f9" opacity=".7"/></g>\n<g id="kc-den-5" style="display:none"><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#713f12" stroke-width="10"/><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#fcd34d" stroke-width="3" opacity=".9"/><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#fffbeb" stroke-width="1" opacity=".8"/><rect x="9" y="44" width="7" height="72" rx="2" fill="#e2e8f0"/><rect x="104" y="44" width="7" height="72" rx="2" fill="#e2e8f0"/><rect x="9" y="46" width="7" height="3" fill="#fcd34d"/><rect x="104" y="46" width="7" height="3" fill="#fcd34d"/><g><path d="M30 40l3.4-8 3.4 8-3.4 2.8Z" fill="#e0f2fe"/><path d="M60 28l3.4-8 3.4 8-3.4 2.8Z" fill="#fffbeb"/><path d="M86 40l3.4-8 3.4 8-3.4 2.8Z" fill="#e0f2fe"/></g><circle cx="14" cy="56" r="8" fill="url(#kc-lamp-grad)"/><circle cx="14" cy="56" r="2.6" fill="#fffbeb"/><circle cx="106" cy="56" r="8" fill="url(#kc-lamp-grad)"/><circle cx="106" cy="56" r="2.6" fill="#fffbeb"/><circle cx="60" cy="34" r="9" fill="url(#kc-lamp-grad)"/><circle cx="60" cy="34" r="2.8" fill="#fffbeb"/><g fill="#334155"><rect x="18" y="115" width="3" height="5"/><rect x="34" y="115" width="3" height="5"/><rect x="50" y="115" width="3" height="5"/><rect x="66" y="115" width="3" height="5"/></g><rect x="7" y="113.4" width="68" height="2" fill="#fcd34d"/></g>\n<g id="kc-den-6" style="display:none"><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#7c2d12" stroke-width="9" opacity=".95"/><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#fb923c" stroke-width="2" opacity=".85"/><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#fbbf24" stroke-width="1.1" stroke-dasharray="3 8" opacity=".7"/><path d="M24 40v10M96 40v10" stroke="#0f172a" stroke-width="1.4"/><path d="M24 50q2 4 0 6M96 50q-2 4 0 6" fill="none" stroke="#334155" stroke-width="1.6"/><circle cx="14" cy="56" r="7" fill="#f97316" opacity=".3"/><circle cx="14" cy="56" r="2.4" fill="#fbbf24"/><circle cx="106" cy="56" r="7" fill="#f97316" opacity=".3"/><circle cx="106" cy="56" r="2.4" fill="#fbbf24"/><g fill="#3f3f46"><rect x="18" y="115" width="3" height="5"/><rect x="34" y="115" width="3" height="5"/><rect x="50" y="115" width="3" height="5"/><rect x="66" y="115" width="3" height="5"/></g><rect x="7" y="113.4" width="68" height="1.8" fill="#fb923c" opacity=".7"/></g>\n<g id="kc-den-7" style="display:none"><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#0e7490" stroke-width="9" opacity=".95"/><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#7dd3fc" stroke-width="2.2" opacity=".9"/><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#e0f2fe" stroke-width="1.1" stroke-dasharray="2 9" opacity=".8"/><g fill="#e0f2fe"><circle cx="24" cy="46" r="1.2"/><circle cx="40" cy="36" r="1.2"/><circle cx="60" cy="32" r="1.2"/><circle cx="80" cy="36" r="1.2"/><circle cx="96" cy="46" r="1.2"/></g><circle cx="14" cy="56" r="7" fill="#7dd3fc" opacity=".3"/><circle cx="14" cy="56" r="2.4" fill="#e0f2fe"/><circle cx="106" cy="56" r="7" fill="#7dd3fc" opacity=".3"/><circle cx="106" cy="56" r="2.4" fill="#e0f2fe"/><g fill="#334155"><rect x="18" y="115" width="3" height="5"/><rect x="34" y="115" width="3" height="5"/><rect x="50" y="115" width="3" height="5"/><rect x="66" y="115" width="3" height="5"/></g><rect x="7" y="113.4" width="68" height="1.8" fill="#7dd3fc" opacity=".8"/></g>\n<g id="kc-den-8" style="display:none"><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#7f1d1d" stroke-width="10"/><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#f59e0b" stroke-width="2.6" opacity=".9"/><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#fcd34d" stroke-width="1.2" stroke-dasharray="5 6" opacity=".8"/><path d="M30 38l4 8 4-8ZM52 32l4 8 4-8ZM74 38l4 8 4-8Z" fill="#7f1d1d"/><circle cx="14" cy="56" r="7.5" fill="#f59e0b" opacity=".32"/><circle cx="14" cy="56" r="2.5" fill="#fffbeb"/><circle cx="106" cy="56" r="7.5" fill="#f59e0b" opacity=".32"/><circle cx="106" cy="56" r="2.5" fill="#fffbeb"/><g fill="#fcd34d"><circle cx="20" cy="114" r="1.6"/><circle cx="40" cy="116" r="1.4"/><circle cx="60" cy="114.6" r="1.6"/><circle cx="72" cy="116" r="1.3"/></g><rect x="7" y="113.4" width="68" height="2" fill="#f59e0b"/></g>\n<g id="kc-den-9" style="display:none"><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#312e81" stroke-width="10"/><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#a5b4fc" stroke-width="2.4" opacity=".95"/><path d="M6 118Q4 40 60 30Q116 40 114 118" fill="none" stroke="#e0e7ff" stroke-width="1.1" stroke-dasharray="2 7" opacity=".9"/><g fill="#fffbeb"><path d="M24 44l1.8-4.4 1.8 4.4-1.8 1.5Z"/><path d="M58 30l1.8-4.4 1.8 4.4-1.8 1.5Z"/><path d="M92 44l1.8-4.4 1.8 4.4-1.8 1.5Z"/></g><circle cx="14" cy="56" r="8" fill="#a5b4fc" opacity=".3"/><circle cx="14" cy="56" r="2.6" fill="#e0e7ff"/><circle cx="106" cy="56" r="8" fill="#a5b4fc" opacity=".3"/><circle cx="106" cy="56" r="2.6" fill="#e0e7ff"/><circle cx="60" cy="32" r="8" fill="#e0e7ff" opacity=".18"/><g fill="#334155"><rect x="18" y="115" width="3" height="5"/><rect x="34" y="115" width="3" height="5"/><rect x="50" y="115" width="3" height="5"/><rect x="66" y="115" width="3" height="5"/></g><rect x="7" y="113.4" width="68" height="2" fill="#a5b4fc"/></g>\n<g id="kc-rock-0"><path d="M78 116L80 86Q83 70 96 66Q111 62 116 76L118 116Z" fill="#475569" stroke="#0f172a" stroke-width="2"/><path d="M84 86Q88 73 97 69" fill="none" stroke="#94a3b8" stroke-width="2" opacity=".5"/><path d="M92 80l4 8-3 7M104 76l-3 9 4 8" fill="none" stroke="#1e293b" stroke-width="1.6" stroke-linecap="round"/></g>\n<g id="kc-rock-1" style="display:none"><path d="M78 116L80 86Q83 70 96 66Q111 62 116 76L118 116Z" fill="#4b5563" stroke="#0f172a" stroke-width="2"/><path d="M84 86Q88 73 97 69" fill="none" stroke="#94a3b8" stroke-width="2" opacity=".5"/><circle cx="90" cy="88" r="2.2" fill="#b45309"/><circle cx="102" cy="80" r="1.9" fill="#92400e"/><circle cx="108" cy="96" r="2.4" fill="#b45309"/><circle cx="95" cy="103" r="1.8" fill="#78350f"/><circle cx="86" cy="99" r="1.6" fill="#92400e"/></g>\n<g id="kc-rock-2" style="display:none"><path d="M78 116L80 86Q83 70 96 66Q111 62 116 76L118 116Z" fill="#52525b" stroke="#0f172a" stroke-width="2"/><path d="M84 86Q88 73 97 69" fill="none" stroke="#a1a1aa" stroke-width="2" opacity=".6"/><circle cx="90" cy="90" r="2.2" fill="#b45309"/><circle cx="108" cy="98" r="2.4" fill="#b45309"/><path d="M96 88l3.6-8.6 3.6 8.6-3.6 2.8Z" fill="#22d3ee" opacity=".9"/><path d="M86 102l2.8-6.6 2.8 6.6-2.8 2.2Z" fill="#67e8f9" opacity=".85"/><path d="M104 78l1.2-3 1.2 3-1.2 1Z" fill="#e0f2fe"/><path d="M99 106l1.2-3 1.2 3-1.2 1Z" fill="#e0f2fe"/></g>\n<g id="kc-rock-3" style="display:none"><path d="M78 116L80 86Q83 70 96 66Q111 62 116 76L118 116Z" fill="#57534e" stroke="#0f172a" stroke-width="2"/><ellipse cx="98" cy="92" rx="24" ry="26" fill="url(#kc-lamp-grad)" opacity=".28"/><path d="M82 96q8-6 12 0t12-2" fill="none" stroke="#fbbf24" stroke-width="2.6" stroke-linecap="round"/><path d="M86 108q7-5 11 0t10-1" fill="none" stroke="#f59e0b" stroke-width="2.2" stroke-linecap="round"/><path d="M96 86l3.6-8.6 3.6 8.6-3.6 2.8Z" fill="#22d3ee"/><circle cx="88" cy="84" r="2.4" fill="#f472b6"/><circle cx="108" cy="88" r="2" fill="#a78bfa"/><circle cx="103" cy="104" r="2.2" fill="#fbbf24"/><path d="M92 74l1.4-3.4 1.4 3.4-1.4 1.2Z" fill="#fffbeb"/></g>\n<g id="kc-rock-4" style="display:none"><path d="M78 116L80 86Q83 70 96 66Q111 62 116 76L118 116Z" fill="#4a3a1c" stroke="#0f172a" stroke-width="2"/><ellipse cx="98" cy="92" rx="22" ry="24" fill="url(#kc-lamp-grad)" opacity=".3"/><path d="M84 92q8-5 12 0t12-2" fill="none" stroke="#fcd34d" stroke-width="2.6" stroke-linecap="round"/><g fill="#fcd34d"><circle cx="90" cy="84" r="2.6"/><circle cx="104" cy="80" r="2.2"/><circle cx="108" cy="98" r="2.8"/><circle cx="88" cy="104" r="2.2"/><circle cx="98" cy="108" r="1.8"/></g><path d="M96 74l2-4.6 2 4.6-2 1.6Z" fill="#fffbeb"/></g>\n<g id="kc-rock-5" style="display:none"><path d="M78 116L80 86Q83 70 96 66Q111 62 116 76L118 116Z" fill="#3b2a4a" stroke="#0f172a" stroke-width="2"/><ellipse cx="98" cy="112" rx="24" ry="8" fill="#f97316" opacity=".35"/><path d="M82 110q10-4 18 0t16 0" fill="none" stroke="#fb7185" stroke-width="1.6" opacity=".7"/><g fill="#e0f2fe"><path d="M90 88l2.6-6.4 2.6 6.4-2.6 2.2Z"/><path d="M104 84l2.2-5.4 2.2 5.4-2.2 1.8Z"/><path d="M98 102l2.2-5.4 2.2 5.4-2.2 1.8Z"/><path d="M86 100l1.8-4.4 1.8 4.4-1.8 1.5Z"/></g><path d="M96 72l1.6-3.8 1.6 3.8-1.6 1.3Z" fill="#fffbeb"/><circle cx="108" cy="94" r="1.8" fill="#a78bfa"/></g>\n<g id="kc-rock-6" style="display:none"><path d="M78 116L80 86Q83 70 96 66Q111 62 116 76L118 116Z" fill="#3f1d12" stroke="#0f172a" stroke-width="2"/><path d="M82 96q8-6 12 0t12-2M86 108q7-5 11 0t10-1" fill="none" stroke="#f97316" stroke-width="2.2" stroke-linecap="round"/><path d="M96 86l3.6-8.6 3.6 8.6-3.6 2.8Z" fill="#0f172a"/><path d="M96 86l3.6-8.6 3.6 8.6-3.6 2.8Z" fill="none" stroke="#fb923c" stroke-width="1.2"/><circle cx="88" cy="84" r="1.6" fill="#fbbf24"/><circle cx="108" cy="92" r="1.4" fill="#fb923c"/><ellipse cx="98" cy="114" rx="20" ry="5" fill="#f97316" opacity=".3"/></g>\n<g id="kc-rock-7" style="display:none"><path d="M78 116L80 86Q83 70 96 66Q111 62 116 76L118 116Z" fill="#17303c" stroke="#0f172a" stroke-width="2"/><path d="M84 92l8-5 6 7 8-5M86 106l8-4 6 6 8-4" fill="none" stroke="#e0f2fe" stroke-width="1.4" opacity=".8"/><path d="M96 84l2.6-6.4 2.6 6.4-2.6 2Z" fill="#7dd3fc"/><circle cx="88" cy="88" r="1.4" fill="#e0f2fe"/><circle cx="106" cy="98" r="1.4" fill="#e0f2fe"/><ellipse cx="98" cy="92" rx="20" ry="22" fill="#7dd3fc" opacity=".12"/></g>\n<g id="kc-rock-8" style="display:none"><path d="M78 116L80 86Q83 70 96 66Q111 62 116 76L118 116Z" fill="#4a2410" stroke="#0f172a" stroke-width="2"/><g fill="#fcd34d"><circle cx="82" cy="113" r="2.4"/><circle cx="88" cy="115" r="2"/><circle cx="110" cy="113.6" r="2.2"/><circle cx="115" cy="115" r="1.8"/></g><path d="M84 94q8-5 12 0t12-2" fill="none" stroke="#f59e0b" stroke-width="2.4" stroke-linecap="round"/><circle cx="92" cy="84" r="2.2" fill="#ef4444"/><circle cx="106" cy="90" r="1.8" fill="#ef4444"/><path d="M98 76l1.6-3.8 1.6 3.8-1.6 1.3Z" fill="#fffbeb"/><ellipse cx="98" cy="92" rx="20" ry="22" fill="#f59e0b" opacity=".16"/></g>\n<g id="kc-rock-9" style="display:none"><path d="M78 116L80 86Q83 70 96 66Q111 62 116 76L118 116Z" fill="#1e1b4b" stroke="#0f172a" stroke-width="2"/><ellipse cx="98" cy="92" rx="26" ry="10" fill="none" stroke="#a5b4fc" stroke-width="1.2" opacity=".5" transform="rotate(-16 98 92)"/><path d="M84 92l8-5 6 7 8-5M86 106l8-4 6 6 8-4" fill="none" stroke="#e0e7ff" stroke-width="1.4" opacity=".85"/><g fill="#fffbeb"><path d="M92 82l1.6-3.8 1.6 3.8-1.6 1.3Z"/><path d="M104 94l1.4-3.2 1.4 3.2-1.4 1.1Z"/><path d="M88 102l1.4-3.2 1.4 3.2-1.4 1.1Z"/></g><ellipse cx="98" cy="92" rx="20" ry="22" fill="#a5b4fc" opacity=".14"/></g>'

SCENE_PICK_INSERT = '<g id="kc-pick"><path d="M68 100L96 64" stroke="#92400e" stroke-width="4" stroke-linecap="round"/><path d="M84 56Q98 51 106 66" fill="none" stroke="#0f172a" stroke-width="8.6" stroke-linecap="round"/><path d="M84 56Q98 51 106 66" fill="none" stroke="#94a3b8" stroke-width="5.4" stroke-linecap="round"/><path d="M86 57.5Q96 54 102.5 63" fill="none" stroke="#e2e8f0" stroke-width="1.6" stroke-linecap="round" opacity=".7"/><circle cx="70" cy="97" r="4.8" fill="#0f172a"/><circle cx="70" cy="97" r="3.5" fill="#f59e0b"/></g>'

SCENE_CHIPS_INSERT = '<g id="kc-chips" aria-hidden="true"><path d="M98 84l3-2.2 1.2 3-3 1.2Z" fill="#94a3b8" style="--cx:7px;--cy:-11px"/><path d="M101 90l2.6-1.6 1 2.6-2.6 1Z" fill="#64748b" style="--cx:10px;--cy:-4px"/><path d="M96 92l2.4-2 .8 2.8-2.6 1Z" fill="#fbbf24" style="--cx:4px;--cy:-14px"/></g>'

MARKUP_SCENE = [
    ('сцена: берлога и скала за котиком + группа kc-cat',
     '<ellipse cx="60" cy="115" rx="35" ry="5" fill="#000" opacity=".35"/>',
     SCENE_SVG_INSERT + '<g id="kc-cat" transform="translate(-14,0)">' +
     '<ellipse cx="60" cy="115" rx="35" ry="5" fill="#000" opacity=".35"/>'),
    ('сцена: кирка в лапе (поверх лап, до головы)',
     '<g id="kc-head">',
     SCENE_PICK_INSERT + '<g id="kc-head">'),
    ('сцена: щепа от ударов (поверх котика)',
     '<circle cx="75.5" cy="63.5" r="3.4" fill="#fb7185" opacity=".3"/>',
     '<circle cx="75.5" cy="63.5" r="3.4" fill="#fb7185" opacity=".3"/>' +
     '</g>' + SCENE_CHIPS_INSERT),
    ('сцена: подпись под котиком про работу киркой',
     'Спит в темноте, пока копилка не набрана.',
     'Машет киркой, пока копилка не набрана.'),
    ('сцена: подсказка про прокачку скалы и берлоги',
     'Тап = погладить: подскок и сердечки.',
     'Тап = погладить: подскок и сердечки. Скала и берлога хорошеют с уровнем кирки!'),
]

PROFWORK_JS = [
    ('режим work: котик копает, пока копилка не набрана',
     "            const next = state.coins >= minerCost() ? 'ready' : 'sleep';",
     "            const next = state.coins >= minerCost() ? 'ready' : (miner.lvl > 0 ? 'work' : 'sleep'); // b380"),
    ('render: класс working на сцене и коробке',
     "                stage.classList.toggle('meowing', mode === 'ready');",
     "                stage.classList.toggle('meowing', mode === 'ready');\n                stage.classList.toggle('working', mode === 'work'); // b380"),
    ('render: класс working на коробке',
     "            box.classList.toggle('meowing', mode === 'ready');",
     "            box.classList.toggle('meowing', mode === 'ready');\n            box.classList.toggle('working', mode === 'work'); // b380"),
    ('render: улыбка и у работающего котика',
     "            setD('kc-mouth-smile', mode === 'ready');  // b179: бодрствует = довольная улыбка",
     "            setD('kc-mouth-smile', mode === 'ready' || mode === 'work');  // b179+b380"),
    ('render: кирка и щепа по режиму',
     "            setD('kc-tail-up2', mode !== 'sleep');",
     "            setD('kc-tail-up2', mode !== 'sleep');\n            setD('kc-pick', mode !== 'sleep'); // b380: кирка есть, пока не спит\n            setD('kc-chips', mode === 'work'); // b380: щепа летит только во время работы"),
    ('render: бейдж состояния про копку',
     "                st.textContent = mode === 'dance' ? '🎉 танцует и мяукает!' : (mode === 'ready' ? '👀 не спит — качай кирку!' : '💤 спит');",
     "                st.textContent = mode === 'dance' ? '🎉 танцует и мяукает!' : (mode === 'ready' ? '👀 не спит — качай кирку!' : (mode === 'work' ? '⛏ копает руду!' : '💤 спит')); // b380"),
    ('render: цвет бейджа для работы',
     "                st.className = 'text-[10px] font-black ' + (mode === 'dance' ? 'text-violet-300' : (mode === 'ready' ? 'text-amber-300' : 'text-sky-300'));",
     "                st.className = 'text-[10px] font-black ' + (mode === 'dance' ? 'text-violet-300' : (mode === 'ready' ? 'text-amber-300' : (mode === 'work' ? 'text-emerald-300' : 'text-sky-300'))); // b380"),
    ('render: перерисовать tier скалы/берлоги',
     "            if (bubble && !bubble.dataset.locked) {",
     "            try { minerSceneRender(); } catch (e) {} // b380\n            if (bubble && !bubble.dataset.locked) {"),
    ('реплики работающего котика',
     "        const arr = mode === 'dance' ? CAT_DANCE_PHRASES : (mode === 'ready' ? CAT_READY_PHRASES : CAT_SLEEP_PHRASES);",
     "        const arr = mode === 'dance' ? CAT_DANCE_PHRASES : (mode === 'ready' ? CAT_READY_PHRASES : (mode === 'work' ? CAT_WORK_PHRASES : CAT_SLEEP_PHRASES)); // b380"),
    ('словарь реплик работы',
     "        let minerCatMode = 'sleep';      // sleep | ready | dance",
     "        const CAT_WORK_PHRASES = [\n            '⛏ Тук-тук! Руда сыпется — монетки капают…',\n            'Котик машет киркой: {R} монет/сек уже твои 🐾',\n            '⛏ Копает-копает… каска не сползла? Мяу.',\n            'Удар! Ещё удар! Скала трещит по швам.',\n            '⛏ Работает за монетки и за погладить.',\n            'Кирка {L} уровня в деле: щепа летит! ✨'\n        ];\n        let minerCatMode = 'sleep';      // sleep | ready | work | dance"),
    ('tier скалы и берлоги по уровню кирки',
     "        function minerCatBox() { return document.getElementById('miner-cat-box'); }",
     "        function minerCatBox() { return document.getElementById('miner-cat-box'); }\n        // b386: прокачка пещеры до 1000 уровня: 10 биомов вместо 6. Экономика НЕ\n        // тронута (цена ×1.22 как была) — расширена только визуальная прогрессия:\n        // после 35-го пещера больше не «обустроена полностью», а уходит вглубь:\n        // Лавовая кузня, Мифриловый зал, Сокровищница дракона и Звёздная жила,\n        // а на 1000-м уровне бейдж показывает корону шахт.\n        const MINER_CAVE_NAMES = ['Глиняная нора', 'Крепь и фонарь', 'Рудный штрек', 'Кристальный грот', 'Золотая жила', 'Алмазное сердце', 'Лавовая кузня', 'Мифриловый зал', 'Сокровищница дракона', 'Звёздная жила'];\n        const MINER_CAVE_RANGE = ['ур. 1-2', 'ур. 3-4', 'ур. 5-9', 'ур. 10-19', 'ур. 20-34', 'ур. 35-59', 'ур. 60-99', 'ур. 100-249', 'ур. 250-499', 'ур. 500-1000'];\n        const MINER_CAVE_NEXT_LVL = [3, 5, 10, 20, 35, 60, 100, 250, 500, 1000];\n        function minerSceneTier() { const l = miner.lvl || 1; return l >= 500 ? 9 : (l >= 250 ? 8 : (l >= 100 ? 7 : (l >= 60 ? 6 : (l >= 35 ? 5 : (l >= 20 ? 4 : (l >= 10 ? 3 : (l >= 5 ? 2 : (l >= 3 ? 1 : 0)))))))); }\n        let minerDrawnTier = null;\n        function minerSceneRender(force) {\n            const t = minerSceneTier();\n            if (!force && minerDrawnTier === t) return;\n            minerDrawnTier = t;\n            const stage = document.getElementById('miner-cat-stage');\n            if (stage) stage.setAttribute('data-tier', String(t));\n            const box = minerCatBox();\n            if (box) box.setAttribute('data-tier', String(t));\n            for (let i = 0; i < 10; i++) {\n                const on = (i === t) ? '' : 'none';\n                const bg = document.getElementById('kc-bg-' + i), r = document.getElementById('kc-rock-' + i), d = document.getElementById('kc-den-' + i);\n                if (bg) bg.style.display = on;\n                if (r) r.style.display = on;\n                if (d) d.style.display = on;\n            }\n            const nm = document.getElementById('kc-cave-name'), nx = document.getElementById('kc-cave-next');\n            if (nm) nm.textContent = '🕳 ' + MINER_CAVE_NAMES[t] + ' · ' + MINER_CAVE_RANGE[t];\n            if (nx) {\n                const l = miner.lvl || 1;\n                if (l >= 1000) nx.textContent = '👑 уровень 1000: корона шахт!';\n                else if (t >= 9) nx.textContent = 'до короны шахт (ур. 1000): ' + (1000 - l) + ' улучш.';\n                else nx.textContent = 'до «' + MINER_CAVE_NAMES[t + 1] + '»: ' + Math.max(0, MINER_CAVE_NEXT_LVL[t] - l) + ' улучш.';\n            }\n        }"),
    ('b384: функция синхронизации мордочек',
     "        // перерисовка состояния: классы, подпись, бейдж состояния, мордочка (глаза/рот/хвост)",
     "        // b384: каваи-мордочки: одно состояние = одна готовая морда (глаза+брови+рот)\n        function minerCatFaceSync() {\n            const stage = document.getElementById('miner-cat-stage');\n            const pet = !!(stage && stage.classList.contains('petting'));\n            const m = minerCatMode;\n            const f = pet ? 'meow' : (m === 'sleep' ? 'sleep' : (m === 'dance' ? 'dance' : (m === 'work' ? 'work' : 'ready')));\n            const all = ['sleep', 'ready', 'work', 'dance', 'meow'];\n            for (let i = 0; i < all.length; i++) {\n                const e = document.getElementById('kc-face-' + all[i]);\n                if (e) e.style.display = (all[i] === f) ? '' : 'none';\n            }\n        }\n        // перерисовка состояния: классы, подпись, бейдж состояния, мордочка (глаза/рот/хвост)"),
    ('b384: мордочка по режиму',
     "            setD('kc-chips', mode === 'work'); // b380: щепа летит только во время работы",
     "            setD('kc-chips', mode === 'work'); // b380: щепа летит только во время работы\n            try { minerCatFaceSync(); } catch (e) {} // b384: каваи-мордочка по режиму"),
    ('b384: морда мяу при поглаживании',
     "            stage.classList.add('petting');",
     "            stage.classList.add('petting');\n            try { minerCatFaceSync(); } catch (e) {} // b384: морда «мяу» на время поглаживания"),
    ('b384: возврат морды после поглаживания',
     "if (s2) s2.classList.remove('petting'); }, 620);",
     "if (s2) s2.classList.remove('petting'); try { minerCatFaceSync(); } catch (e) {} }, 620); // b384"),
    ('b391: функции пакетного вскрытия',
     "        let currentUnboxingCards = [];",
     "// ===== b391: ПАКЕТНОЕ ВСКРЫТИЕ — открыть N паков за один раз =====\n        let nxPackQty = 1;\n        try { nxPackQty = Math.max(1, Math.min(99, parseInt(LS.getItem('nx_pack_qty') || '1', 10) || 1)); } catch (e) {}\n        const NX_QTY_PRESETS = [1, 5, 10, 20, 40];\n        function nxSetPackQty(q) {\n            nxPackQty = Math.max(1, Math.min(99, Math.floor(q) || 1));\n            try { LS.setItem('nx_pack_qty', String(nxPackQty)); } catch (e) {}\n            try { SoundFX.play('click'); } catch (e) {}\n            try { carouselUpdateDetail(); } catch (e) {}\n        }\n        function nxGrantCard(card) {\n            if (state.collection[card.id]) {\n                const refundMap = { common: 20, rare: 50, epic: 120, legendary: 300 };\n                const refund = refundMap[card.rarity] || 20;\n                state.collection[card.id] = cardCopies(card.id) + 1;\n                state.coins += refund;\n                state.stats.duplicatesSold++;\n                state.stats.coinsFromDupes += refund;\n                return { dup: true, refund: refund };\n            }\n            state.collection[card.id] = 1;\n            return { dup: false, refund: 0 };\n        }\n        let nxBatchDupIds = [];\n        // b395: кнопка «Продать дубликаты» в окне партии — лишние копии этой\n        // партии уходят на биржу ОДНИМ коммитом (marketListMany из b394)\n        function nxBatchSellDupes() {\n            const btn = document.getElementById('nx-batch-sell');\n            if (!CLOUD.connected()) { showToast('Биржа работает при подключённом облаке комнаты', 'error'); return; }\n            const ids = (nxBatchDupIds || []).slice();\n            if (!ids.length) { showToast('Дубликатов в этой партии нет', 'info'); return; }\n            const items = [];\n            ids.forEach(id => {\n                const card = state.cards.find(c => c.id === id);\n                if (!card || cardCopies(id) - 1 < 1) return; // одну копию оставляем себе\n                items.push({ id: id, price: marketRecommendPrice(card) });\n            });\n            if (!items.length) { showToast('Лишних копий для продажи не осталось', 'info'); if (btn) btn.disabled = true; return; }\n            if (btn) btn.disabled = true;\n            showToast('⏳ Выставляю ' + items.length + ' ' + pluralRu(items.length, 'лот', 'лота', 'лотов') + '…', 'info');\n            setTimeout(() => {\n                const r = marketListMany(items);\n                if (r.ok) {\n                    showToast('💰 Дубликаты партии на бирже: ' + r.ok + ' на сумму ' + fmtCoins(r.sum), 'success');\n                    if (btn) btn.innerHTML = '✅ Продано: ' + r.ok + ' · ' + fmtCoins(r.sum);\n                } else {\n                    showToast('Не удалось выставить дубликаты (нет подключения к облаку?)', 'error');\n                    if (btn) btn.disabled = false;\n                }\n            }, 30);\n        }\n        function nxPeelTile(el) { if (el) el.classList.add('nx-peel'); }\n        function nxPeelAll() {\n            const m = document.getElementById('nx-batch-modal'); if (!m) return;\n            const tiles = m.querySelectorAll('.nx-bt');\n            for (let i = 0; i < tiles.length; i++) {\n                tiles[i].style.setProperty('--nx-d', Math.min(i * 28, 1800) + 'ms');\n                tiles[i].classList.add('nx-peel');\n            }\n            const b = document.getElementById('nx-batch-peel'); if (b) b.disabled = true;\n            try { SoundFX.play('swap'); } catch (e) {}\n        }\n        function nxBatchClose() {\n            const m = document.getElementById('nx-batch-modal'); if (m) m.remove();\n            try { PackMusic.stop(); } catch (e) {}\n            try { updateCoinDisplay(); saveState(); checkAchievements(); } catch (e) {}\n            try { if (typeof renderAlbums === 'function') renderAlbums(); } catch (e) {}\n        }\n        function nxShowBatchReveal(pack, cards, sum) {\n            // b393: вся стилизация модалки — собственные классы app.css (.nx-batch,\n            // .nx-bp, .nx-grid, .nx-bt, .nx-btn…): прекомпилированный tailwind.css\n            // не знает произвольных утилит (z-[95], bg-[#…], grid-cols-6), из-за\n            // чего модалка оставалась без фона/z-индекса, а сетка схлопывалась\n            // в одну колонку и страница «висла» на 160 плитках.\n            const old = document.getElementById('nx-batch-modal'); if (old) old.remove();\n            const RAR = { common: ['Обычная', '#94a3b8'], rare: ['Редкая', '#38bdf8'], epic: ['Эпическая', '#a78bfa'], legendary: ['Легендарная', '#fbbf24'] };\n            const tiles = cards.map((c) => {\n                const r = RAR[c.rarity] || RAR.common;\n                return '<div class=\"nx-bt\" style=\"border-color:' + r[1] + '66\" onclick=\"nxPeelTile(this)\">' +\n                    '<img src=\"' + mediaThumb(c.image) + '\" data-nx-full=\"' + mediaUrl(c.image) + '\" alt=\"' + String(c.name || '').replace(/\"/g, '&quot;') + '\" class=\"nx-bt-img\" loading=\"lazy\" decoding=\"async\" onerror=\"imgErrorChain(this)\">' +\n                    '<div class=\"nx-bt-nm\" style=\"color:' + r[1] + '\">' + String(c.name || '') + '</div>' +\n                    '<div class=\"nx-foil\"></div></div>';\n            });\n            const chips = sum.byRar.map(x => {\n                const r = RAR[x[0]] || ['?', '#94a3b8'];\n                return '<span class=\"nx-chip\" style=\"color:' + r[1] + ';border-color:' + r[1] + '66\">' + r[0] + ': ' + x[1] + '</span>';\n            }).join('');\n            const m = document.createElement('div');\n            m.id = 'nx-batch-modal';\n            m.className = 'nx-batch';\n            m.innerHTML = '<div class=\"nx-bp\">' +\n                '<div class=\"nx-bh\"><div><h3>' + pack.title + ' × ' + sum.packs + '</h3>' +\n                '<p>' + cards.length + ' ' + pluralRu(cards.length, 'карта', 'карты', 'карт') + ' · новых ' + sum.new + ' · повторов ' + sum.dup + (sum.dupCoins ? ' (+' + fmtCoins(sum.dupCoins) + ' монет)' : '') + '</p></div>' +\n                '<button class=\"nx-x\" onclick=\"nxBatchClose()\" aria-label=\"Закрыть\">✕</button></div>' +\n                '<div class=\"nx-chips\">' + chips + '</div>' +\n                '<div class=\"nx-acts\"><button id=\"nx-batch-sell\" class=\"nx-btn nx-btn-sell\" onclick=\"nxBatchSellDupes()\" ' + (sum.dup ? '' : 'disabled') + '>' + (sum.dup ? '💰 Продать дубликаты (' + sum.dup + ')' : '💰 Дубликатов нет') + '</button>' +\n                '<button class=\"nx-btn nx-btn-take\" onclick=\"nxBatchClose()\">📦 Забрать ' + cards.length + ' ' + pluralRu(cards.length, 'карту', 'карты', 'карт') + '</button></div>' +\n                '<div class=\"nx-grid\"></div></div>';\n            nxBatchDupIds = sum.dupIds || [];\n            document.body.appendChild(m);\n            // чанковый рендер плиток (по 24 за тик): 160-396 плиток одним\n            // innerHTML вешали мобильный WebKit на первой отрисовке\n            const gridEl = m.querySelector('.nx-grid');\n            let pi = 0;\n            const CHUNK = 24;\n            const pushChunk = () => {\n                const wrap = document.createElement('div');\n                wrap.innerHTML = tiles.slice(pi, pi + CHUNK).join('');\n                while (wrap.firstChild) gridEl.appendChild(wrap.firstChild);\n                pi += CHUNK;\n                if (pi < tiles.length) setTimeout(pushChunk, 40);\n            };\n            pushChunk();\n            setTimeout(nxPeelAll, 450 + Math.ceil(tiles.length / CHUNK) * 40);\n        }\n        function buyPackBatch(pack, qty) {\n            const price = packSalePrice(pack);\n            const cards = [];\n            let opened = 0;\n            for (let i = 0; i < qty; i++) {\n                const r = rollPackCards(pack);\n                if (!r) { state.coins += price * (qty - i); updateCoinDisplay(); saveState(); break; }\n                opened++;\n                for (let k = 0; k < r.length; k++) cards.push(r[k]);\n            }\n            const sum = { packs: opened, new: 0, dup: 0, dupCoins: 0, byRar: {}, dupIds: [] };\n            for (let i = 0; i < cards.length; i++) {\n                const g = nxGrantCard(cards[i]);\n                if (g.dup) { sum.dup++; sum.dupCoins += g.refund; sum.dupIds.push(cards[i].id); } else sum.new++;\n                sum.byRar[cards[i].rarity] = (sum.byRar[cards[i].rarity] || 0) + 1;\n            }\n            sum.byRar = Object.keys(sum.byRar).map(k => [k, sum.byRar[k]]);\n            updateCoinDisplay(); saveState();\n            try { statsTouch(); } catch (e) {}\n            try { preloadImages(cards.map(c => c.image)); } catch (e) {}\n            try { PackMusic.startFor(pack); } catch (e) {}\n            nxShowBatchReveal(pack, cards, sum);\n        }"),
    ('b391: buyPack принимает количество',
     "        function buyPack(packId) {",
     "        function buyPack(packId, qty) { // b391: qty — сколько паков вскрыть за раз"),
    ('b391: q и итоговая цена',
     "            const packPrice = packSalePrice(pack); // b160: скидка окна продажи",
     "            const packPrice = packSalePrice(pack); // b160: скидка окна продажи\n            const q = Math.max(1, Math.min(99, Math.floor(qty) || 1)); // b391: количество паков\n            const packPriceTotal = packPrice * q; // b391: итоговая цена партии"),
    ('b391: проверка монет на партию',
     "            if (state.coins < packPrice) {\n                showToast('Недостаточно монет!', 'error');",
     "            if (state.coins < packPriceTotal) { // b391\n                showToast('Недостаточно монет! Нужно ' + fmtCoins(packPriceTotal) + (q > 1 ? ' за ' + q + ' ' + pluralRu(q, 'пак', 'пака', 'паков') : ''), 'error');"),
    ('b391: списание за партию',
     "            state.coins -= packPrice;",
     "            state.coins -= packPriceTotal; // b391"),
    ('b391: лимит окна на партию',
     "                if ((wb0[k0] || 0) >= pack.schedule.limitN) {",
     "                if ((wb0[k0] || 0) + q > pack.schedule.limitN) { /* b391: лимит на всю партию */"),
    ('b391: счётчик окна += q',
     "                if (swGuard) { const kk = pack.id + ':' + swGuard.start; wb[kk] = (wb[kk] || 0) + 1; }",
     "                if (swGuard) { const kk = pack.id + ':' + swGuard.start; wb[kk] = (wb[kk] || 0) + q; } // b391"),
    ('b391: статистика продаж += q',
     "                en.opens++; en.revenue += packPrice;",
     "                en.opens += q; en.revenue += packPriceTotal; // b391"),
    ('b391: дневной счётчик += q',
     "                en.days[dk] = (en.days[dk] || 0) + 1;",
     "                en.days[dk] = (en.days[dk] || 0) + q; // b391"),
    ('b391: ветка пакетного вскрытия',
     "            const cards = rollPackCards(pack);",
     "            if (q > 1) { // b391: пакетное вскрытие — без 3D и поштучной фольги\n                const pc = state.cards.filter(c => c.packId === pack.id);\n                if (!pc.length) { showToast('В этом паке пока нет карточек!', 'error'); state.coins += packPriceTotal; updateCoinDisplay(); saveState(); return; }\n                buyPackBatch(pack, q);\n                return;\n            }\n            const cards = rollPackCards(pack);"),
    ('b391: строка количества в панели пака (b392: сверху, под заголовком)',
     "<p class=\"text-[11px] sm:text-xs text-slate-400 mt-1.5 line-clamp-3 leading-relaxed\">${pack.description || ''}</p>",
     "<div class=\"mt-3 flex flex-wrap items-center gap-1.5\" id=\"nx-qty-row\">\n                            <span class=\"text-[10px] font-bold text-slate-400 mr-0.5\"><i class=\"fa-solid fa-layer-group mr-1 text-sky-300\"></i>Открыть сразу:</span>\n                            ${NX_QTY_PRESETS.map(v => '<button onclick=\"nxSetPackQty(' + v + ')\" class=\"px-2 py-1 rounded-lg text-[10px] font-black border ' + (nxPackQty === v ? 'bg-sky-500/20 border-sky-400/60 text-sky-200' : 'bg-slate-800/70 border-slate-700 text-slate-300 hover:bg-slate-700') + '\">' + v + '</button>').join('')}\n                            <button onclick=\"nxSetPackQty(Math.floor(state.coins / ${salePrice}))\" class=\"px-2 py-1 rounded-lg text-[10px] font-black border bg-slate-800/70 border-slate-700 text-amber-300 hover:bg-slate-700\" title=\"Открыть максимум паков на текущий баланс\">MAX</button>\n                            <input id=\"nx-qty-input\" type=\"number\" min=\"1\" max=\"99\" value=\"${nxPackQty}\" onchange=\"nxSetPackQty(this.value)\" class=\"w-14 px-1.5 py-1 rounded-lg bg-slate-800/80 border border-slate-700 text-[11px] font-black text-center text-slate-100\" aria-label=\"Количество паков\">\n                            <span class=\"text-[10px] font-bold text-amber-300\">итого ${fmtCoins(salePrice * nxPackQty)}</span>\n                        </div>\n                                                \n                        <p class=\"text-[11px] sm:text-xs text-slate-400 mt-1.5 line-clamp-3 leading-relaxed\">${pack.description || ''}</p>"),
    ('b394: ядро лота и пакетный коммит',
     "        function marketListCard() {",
     "        // ===== b394: массовая продажа без зависания =====\n        // Раньше каждый лот вызывал saveState() + jpSyncNow() (сетевой пуш в\n        // облако) + renderMarket() + marketEnforceLimit() + копирование массива\n        // лотов: 807 повторов = 807 пушей и O(N^2) → браузер крашился.\n        // Теперь лоты собираются в память, а коммит (save/sync/render/enforce)\n        // делается ОДИН раз на всю партию.\n        let nxLotSeq = 0;\n        function marketMakeLot(cardId, priceStr) {\n            if (statsBlockGuard('биржа')) return null; // b277\n            if (!CLOUD.connected()) return null;\n            const card = state.cards.find(c => c.id === cardId);\n            if (!card || cardCopies(cardId) < 1) return null;\n            const raw = parseBetStr(priceStr);\n            if (!isFinite(raw) || raw < 1) return null;\n            const price = normBet(raw);\n            marketSetCollection(cardId, cardCopies(cardId) - 1); // копия уходит в эскроу лота\n            const snap = Object.assign({}, card);\n            if (typeof snap.image === 'string' && snap.image.indexOf('data:') === 0) snap.image = ''; // не тащим base64 в облако\n            return {\n                id: 'lot-' + Date.now() + '-' + (nxLotSeq = (nxLotSeq + 1) % 1e6) + '-' + Math.floor(Math.random() * 1e6),\n                sid: cloudDeviceId(),\n                sname: getPlayerName() || ('Игрок-' + cloudDeviceId().slice(-4)),\n                price: price, at: Date.now(), card: snap\n            };\n        }\n        function marketCommitLots(lots) {\n            if (!lots || !lots.length) return 0;\n            CLOUD.market = marketLots().concat(lots);\n            saveState(); jpSyncNow(); jpSyncSoon(); renderMarket(); // ОДИН пуш на партию\n            marketEnforceLimit(); // b142: один проход лимита на партию\n            return lots.length;\n        }\n        function marketListMany(items) {\n            if (!CLOUD.connected()) { showToast('Биржа работает при подключённом облаке комнаты', 'error'); return { ok: 0, sum: 0 }; }\n            const lots = []; let sum = 0;\n            for (let i = 0; i < items.length; i++) {\n                const lot = marketMakeLot(items[i].id, String(items[i].price));\n                if (!lot) continue;\n                lots.push(lot); sum += lot.price;\n            }\n            marketCommitLots(lots);\n            return { ok: lots.length, sum: sum };\n        }\n        function marketListCard() {"),
    ('b394: продажа повторов альбома одним коммитом',
     "        // b144: продать все повторки альбома — лишние копии уходят на биржу по рекомендуемой цене\n        function sellAlbumDupes(packId) {\n            if (!CLOUD.connected()) { showToast('Биржа работает при подключённом облаке комнаты', 'error'); return; }\n            const cards = state.cards.filter(c => c.packId === packId);\n            let ok = 0, sum = 0;\n            cards.forEach(c => {\n                // одну копию каждой карты оставляем в коллекции — продаём только лишние\n                let excess = cardCopies(c.id) - 1;\n                while (excess-- > 0 && cardCopies(c.id) >= 1) {\n                    const price = marketRecommendPrice(c);\n                    if (marketListCardFor(c.id, String(price), true)) { ok++; sum += price; }\n                    else break;\n                }\n            });\n            if (ok) {\n                marketEnforceLimit(); // b142: защита от наводнения одинаковыми лотами\n                showToast('💰 Повторки альбома отправлены на биржу: ' + ok + ' на сумму ' + fmtCoins(sum), 'success');\n                try { renderAlbumsList(); } catch (e) {}\n            } else {\n                showToast('В этом альбоме нет лишних копий для продажи', 'info');\n            }\n        }",
     "        // b144+b394: продать все повторки альбома — ОДНИМ коммитом лотов\n        function sellAlbumDupes(packId) {\n            if (!CLOUD.connected()) { showToast('Биржа работает при подключённом облаке комнаты', 'error'); return; }\n            const cards = state.cards.filter(c => c.packId === packId);\n            const items = [];\n            cards.forEach(c => {\n                let excess = cardCopies(c.id) - 1; // одну копию оставляем в коллекции\n                const price = marketRecommendPrice(c);\n                while (excess-- > 0) items.push({ id: c.id, price: price });\n            });\n            if (!items.length) { showToast('В этом альбоме нет лишних копий для продажи', 'info'); return; }\n            showToast('⏳ Выставляю ' + items.length + ' ' + pluralRu(items.length, 'лот', 'лота', 'лотов') + '…', 'info');\n            setTimeout(() => { // даём тосту отрисоваться до тяжёлой работы\n                const r = marketListMany(items);\n                if (r.ok) {\n                    showToast('💰 Повторки альбома отправлены на биржу: ' + r.ok + ' на сумму ' + fmtCoins(r.sum), 'success');\n                    try { renderAlbumsList(); } catch (e) {}\n                } else {\n                    showToast('Не удалось выставить повторки (нет подключения к облаку?)', 'error');\n                }\n            }, 30);\n        }"),
    ('b394: продажа повторов вскрытия одним коммитом',
     "        // b143: одна кнопка — все раскрытые повторки улетают на биржу\n        function sellAllDupesToMarket() {\n            const idxs = Object.keys(unboxDupeIdx).map(Number).filter(i => !unboxListedIdx[i]);\n            if (!idxs.length) { showToast('Раскрытых повторок для продажи пока нет', 'info'); return; }\n            let ok = 0, sum = 0;\n            idxs.forEach(i => {\n                const card = (currentUnboxingCards || [])[i];\n                if (!card || cardCopies(card.id) < 1) return;\n                const price = marketRecommendPrice(card);\n                if (marketListCardFor(card.id, String(price), true)) {\n                    unboxListedIdx[i] = 1;\n                    ok++; sum += price;\n                    marketMarkListedBtn(i, price);\n                }\n            });\n            if (ok) showToast('💰 Повторки отправлены на биржу: ' + ok + ' на сумму ' + fmtCoins(sum), 'success');\n            else showToast('Не удалось выставить повторки (нет подключения к облаку?)', 'error');\n        }",
     "        // b143+b394: одна кнопка — все раскрытые повторки улетают на биржу ОДНИМ коммитом\n        function sellAllDupesToMarket() {\n            const idxs = Object.keys(unboxDupeIdx).map(Number).filter(i => !unboxListedIdx[i]);\n            if (!idxs.length) { showToast('Раскрытых повторок для продажи пока нет', 'info'); return; }\n            const items = []; const map = [];\n            idxs.forEach(i => {\n                const card = (currentUnboxingCards || [])[i];\n                if (!card || cardCopies(card.id) < 1) return;\n                items.push({ id: card.id, price: marketRecommendPrice(card) });\n                map.push(i);\n            });\n            if (!items.length) { showToast('Раскрытых повторок для продажи пока нет', 'info'); return; }\n            showToast('⏳ Выставляю ' + items.length + ' ' + pluralRu(items.length, 'лот', 'лота', 'лотов') + '…', 'info');\n            setTimeout(() => {\n                const r = marketListMany(items);\n                if (r.ok) {\n                    for (let k = 0; k < Math.min(r.ok, map.length); k++) { unboxListedIdx[map[k]] = 1; marketMarkListedBtn(map[k], items[k].price); }\n                    showToast('💰 Повторки отправлены на биржу: ' + r.ok + ' на сумму ' + fmtCoins(r.sum), 'success');\n                } else {\n                    showToast('Не удалось выставить повторки (нет подключения к облаку?)', 'error');\n                }\n            }, 30);\n        }"),
]

HEAD_END = 1088       # </head>
GOOGLE_FONTS = 145    # <link href="https://fonts.googleapis.com/...">
BODY_OPEN = 1089
BODY_CLOSE = 21359


def inner(lines, key):
    """содержимое блока без обрамляющих тегов <script>/<style>"""
    a, b, kind, _ = BLOCKS[key]
    first = lines[a - 1]
    last = lines[b - 1]
    assert first.strip().startswith('<' + kind), f'{key}: строка {a} — не <{kind}>, а {first[:60]!r}'
    assert last.strip() == '</%s>' % kind, f'{key}: строка {b} — не </{kind}>, а {last[:60]!r}'
    body = list(lines[a:b - 1])
    # у первого блока-opening тега может быть хвост после <script>
    body[0] = re.sub(r'^\s*<%s[^>]*>' % kind, '', body[0])
    return '\n'.join(body)


# --------------------------------------------------------------------------- #
# 2. Font Awesome: вырезаем подмножество
# --------------------------------------------------------------------------- #
FA_FIXES = {
    # этих иконок нет в Font Awesome 6 Free (только в Pro) — сейчас они
    # рисуются пустым квадратом. Меняем на ближайшие бесплатные аналоги.
    'fa-sack-coins': 'fa-sack-dollar',
    'fa-sparkles': 'fa-wand-magic-sparkles',
}
FA_NOISE = {
    'solid', 'regular', 'brands', 'classic', 'sharp', 'light', 'thin', 'duotone',
    '2xs', 'xs', 'sm', 'lg', 'xl', '2xl', 'fw', 'spin', 'pulse', 'shake', 'beat',
    'fade', 'beat-fade', 'bounce', 'flip', 'rotate', 'border', 'pull-left',
    'pull-right', 'stack', 'stack-1x', 'stack-2x', 'inverse', 'sr-only', 'ul',
    'li', 'fixed-width', 'swap-opacity', 'layers', 'sr-only-focusable',
}


def fa_used_icons(text_without_fa_css):
    names = set(re.findall(r'\bfa-([a-z0-9]+(?:-[a-z0-9]+)*)\b', text_without_fa_css))
    return {n for n in names if n not in FA_NOISE and not n[0].isdigit()}


def fa_codepoints(fa_css):
    """имя иконки -> codepoint; устойчиво к сгруппированным селекторам
       вида .fa-a:before,.fa-b:before{content:"\\f000"}"""
    cp = {}
    rx = re.compile(r'\{content:"\\([0-9a-fA-F]{2,6})"\}')
    for m in rx.finditer(fa_css):
        code = m.group(1).zfill(4)
        start = max(fa_css.rfind('}', 0, m.start()), fa_css.rfind('{', 0, m.start() - 1))
        sel = fa_css[start + 1:m.start()]
        for part in sel.split(','):
            part = part.strip()
            if part.endswith(':before') and part.startswith('.fa-'):
                cp.setdefault(part[4:-7], code)
    return cp


def build_fontawesome(fa_css, used):
    keep = {}
    cp = fa_codepoints(fa_css)
    for name in sorted(used):
        if name in cp:
            keep[name] = cp[name]
    unresolved = sorted(n for n in used if n not in cp)

    # шрифт: в исходнике один и тот же woff2 лежит base64 ТРИ раза
    b64 = re.search(r'url\(data:font/woff2;charset=utf-8;base64,([A-Za-z0-9+/=]+)\)', fa_css)
    assert b64, 'не найден встроенный woff2 Font Awesome'
    full = os.path.join(ROOT, 'tools', '_fa_solid_full.woff2')
    with open(full, 'wb') as f:
        f.write(base64.b64decode(b64.group(1)))

    subset = os.path.join(ASSETS, 'fa-solid-900.woff2')
    unicodes = ','.join('U+' + v for v in set(keep.values())) + ',U+0020'
    try:
        subprocess.run(
            [sys.executable, '-m', 'fontTools.subset', full,
             '--unicodes=' + unicodes, '--flavor=woff2',
             '--output-file=' + subset, '--layout-features=*',
             '--no-hinting', '--desubroutinize'],
            check=True, capture_output=True)
        font_note = 'собран из %d глифов' % len(set(keep.values()))
    except Exception as e:
        # нет fontTools — кладём полный шрифт, иконки всё равно будут работать
        shutil.copy(full, subset)
        font_note = 'fontTools недоступен (%s) — взят полный шрифт' % e
    os.remove(full)

    # CSS: выбрасываем все @font-face (сделаем один свой) и неиспользуемые иконки
    css = re.sub(r'@font-face\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', '', fa_css)
    rx = re.compile(r'\{content:"\\([0-9a-fA-F]{2,6})"\}')
    out, pos, dropped = [], 0, 0
    for m in rx.finditer(css):
        start = max(css.rfind('}', 0, m.start()), css.rfind('{', 0, m.start() - 1)) + 1
        sel = css[start:m.start()]
        names = [p.strip()[4:-7] for p in sel.split(',')
                 if p.strip().endswith(':before') and p.strip().startswith('.fa-')]
        if names and not any(n in keep for n in names):
            out.append(css[pos:start])
            pos = m.end()          # m.end() уже стоит ПОСЛЕ закрывающей скобки
            dropped += 1
    out.append(css[pos:])
    css = ''.join(out)
    css = css.replace('<style>', '').replace('</style>', '').strip()

    header = (
        '/* Font Awesome Free 6.4.0 (CC BY 4.0) — ПОДМНОЖЕСТВО: %d иконок из ~2000.\n'
        '   Собрано tools/build.py. Шрифт — один файл fa-solid-900.woff2 (%s),\n'
        '   вместо трёх одинаковых base64-копий по 150 КБ внутри CSS. */\n'
        '@font-face{font-family:"Font Awesome 6 Free";font-style:normal;font-weight:900;'
        'font-display:block;src:url(fa-solid-900.woff2) format("woff2")}\n'
        % (len(keep), font_note))
    return header + css + '\n', keep, unresolved, dropped


# --------------------------------------------------------------------------- #
# 3. миниатюры артов
# --------------------------------------------------------------------------- #
def used_media(src_text):
    files = [f for f in sorted(os.listdir(MEDIA))
             if os.path.isfile(os.path.join(MEDIA, f))]
    return [f for f in files if ('media/' + f) in src_text]


def all_media_images():
    """ВСЕ картинки media/ (облачный каталог ссылается на них напрямую)"""
    out = []
    for f in sorted(os.listdir(MEDIA)):
        p = os.path.join(MEDIA, f)
        if os.path.isfile(p) and f.lower().endswith('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.jfif', '.tif', '.tiff'):  # b382: тот же список, что в thumbs_for_media.py
            out.append(f)
    return out


def build_thumbs(files, force=False):
    """Два уровня: media/t/ (256px) для списков и media/t2/ (512px) для сеток.
       Полноразмерные мастера не трогаем — просмотр карты остаётся 1:1."""
    from PIL import Image
    os.makedirs(THUMBS, exist_ok=True)
    os.makedirs(MIDS, exist_ok=True)
    small, mid = {}, {}
    made = skipped = 0
    src_bytes = th_bytes = mid_bytes = 0
    src_px = th_px = mid_px = 0

    def encode(im, w, q, dst, mtime_ref):
        if os.path.exists(dst) and not force and os.path.getmtime(dst) > mtime_ref:
            return False, Image.open(dst).size
        ww, hh = im.size
        tw = w if ww > w else ww
        th = max(1, round(hh * tw / ww))
        im.resize((tw, th), Image.LANCZOS).save(dst, 'WEBP', quality=q, method=6)
        return True, (tw, th)

    for f in files:
        src = os.path.join(MEDIA, f)
        base = os.path.splitext(f)[0]
        s1 = os.path.getsize(src)
        src_bytes += s1
        try:
            im = Image.open(src)
            im.load()
        except Exception as e:
            say('  ! не читается %s: %s' % (f, e))
            continue
        if im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGB')
        w, h = im.size
        src_px += w * h * 4

        d1 = os.path.join(THUMBS, base + '.webp')
        ch, sz = encode(im, THUMB_W, THUMB_Q, d1, os.path.getmtime(src))
        made += ch
        skipped += (not ch)
        small[f] = 'media/t/' + base + '.webp'
        th_bytes += os.path.getsize(d1)
        th_px += sz[0] * sz[1] * 4

        if w > MID_MIN_SRC:
            d2 = os.path.join(MIDS, base + '.webp')
            ch2, sz2 = encode(im, MID_W, MID_Q, d2, os.path.getmtime(src))
            mid[f] = 'media/t2/' + base + '.webp'
            mid_bytes += os.path.getsize(d2)
            mid_px += sz2[0] * sz2[1] * 4
        im.close()

    say('миниатюры: создано %d, уже были %d' % (made, skipped))
    say('  мастера : %6.1f МБ на диске, %5.0f МБ распакованных битмапов' %
        (src_bytes / 1048576, src_px / 1048576))
    say('  t/ 256px: %6.1f МБ на диске, %5.0f МБ распакованных битмапов (%d шт.)' %
        (th_bytes / 1048576, th_px / 1048576, len(small)))
    say('  t2/512px: %6.1f МБ на диске, %5.0f МБ распакованных битмапов (%d шт.)' %
        (mid_bytes / 1048576, mid_px / 1048576, len(mid)))
    return small, mid


# --------------------------------------------------------------------------- #
# 4. правки кода игры
# --------------------------------------------------------------------------- #
def patch_once(text, old, new, label, required=True, want=None):
    """Заменяет ВСЕ вхождения `old`.

    b377: раньше здесь было `replace(old, new, 1)` — заменялось только ПЕРВОЕ
    вхождение, а в лог печаталось полное количество найденных. Сборка рапортовала
    «albumCardHTML: <img> обеих веток (2 вхожд.)», хотя вторая ветка оставалась
    нетронутой. Именно так обычная (не компактная) сетка альбома продолжила
    грузить мастера 1080x1920 по 2-4 МБ вместо миниатюры 512px: 96.6 МБ трафика
    и ~284 МБ распакованных битмапов на один альбом «Доктор Кто». На телефоне
    это и есть «картинки не загружаются».

    `want` — ожидаемое число вхождений: если источник изменился, сборка падает
    громко, а не молча собирает половину патчей.
    """
    n = text.count(old)
    if n == 0:
        if required:
            raise AssertionError('патч не найден: ' + label)
        say('  · %s — не найдено (пропущено)' % label)
        return text, 0
    if want is not None and n != want:
        raise AssertionError('патч «%s»: ожидалось %d вхождений, найдено %d '
                             '(источник изменился — обновите патч)' % (label, want, n))
    text = text.replace(old, new)
    say('  · %s (заменено %d)' % (label, n))
    return text, n


def patch_all(text, old, new, label):
    n = text.count(old)
    if n:
        text = text.replace(old, new)
    say('  · %s: %d' % (label, n))
    return text, n


def add_img_attrs(html):
    """loading=lazy + decoding=async каждому <img src=...> — без этого браузер
       декодирует все картинки списка сразу: ~1.3 МБ битмапы на карту."""
    added_l = added_d = 0

    def fix(m):
        nonlocal added_l, added_d
        tag = m.group(0)
        if 'src=' not in tag:
            return tag
        if 'loading=' not in tag:
            tag = tag[:-1].rstrip() + ' loading="lazy">'
            added_l += 1
        if 'decoding=' not in tag:
            tag = tag[:-1].rstrip() + ' decoding="async">'
            added_d += 1
        return tag

    return re.sub(r'<img\b[^>]*>', fix, html), added_l, added_d


# места, где карта показывается МЕЛКО (<= ~180 css px) — там достаточно миниатюры
THUMB_SITES = [
    # b377: этот <img> встречается ДВАЖДЫ и в двух разных по размеру местах —
    # строка лота (40-48 css px) и плитка лота в виде «Сетка» (2-4 колонки,
    # ~150-180 css px). До b377 патч с одним old-текстом заменял только первое
    # вхождение, и плитка биржи продолжала тянуть мастер. Разводим явно,
    # привязываясь к обёртке: строке — 256px, плитке — 512px.
    ('биржа, строка лота (40-48px)',
     '''<div class="relative w-10 sm:w-12 shrink-0 rounded-lg overflow-hidden border border-slate-700/60 bg-slate-950" style="aspect-ratio:3/4">
                    <img src="${mediaUrl(c.image)}" alt="${cloudEsc(c.name || '')}" loading="lazy" onerror="this.onerror=null;imgErrorChain(this);" class="w-full h-full object-cover">''',
     '''<div class="relative w-10 sm:w-12 shrink-0 rounded-lg overflow-hidden border border-slate-700/60 bg-slate-950" style="aspect-ratio:3/4">
                    <img src="${mediaThumb(c.image)}" data-nx-full="${mediaUrl(c.image)}" alt="${cloudEsc(c.name || '')}" loading="lazy" onerror="this.onerror=null;imgErrorChain(this);" class="w-full h-full object-cover">''',
     1),
    ('биржа, плитка лота в сетке (~150-180px)',
     '''<div class="relative w-full rounded-lg overflow-hidden border border-slate-700/60 bg-slate-950" style="aspect-ratio:3/4">
                    <img src="${mediaUrl(c.image)}" alt="${cloudEsc(c.name || '')}" loading="lazy" onerror="this.onerror=null;imgErrorChain(this);" class="w-full h-full object-cover">''',
     '''<div class="relative w-full rounded-lg overflow-hidden border border-slate-700/60 bg-slate-950" style="aspect-ratio:3/4">
                    <img src="${mediaThumbMid(c.image)}" data-nx-full="${mediaUrl(c.image)}" alt="${cloudEsc(c.name || '')}" loading="lazy" onerror="this.onerror=null;imgErrorChain(this);" class="w-full h-full object-cover">''',
     1),
    ('колода, список бойцов (88px)',
     '''<img src="${mediaUrl(c.image)}" alt="${c.name}" class="w-full h-20 object-cover rounded-lg" onerror="imgErrorChain(this);" data-card-id="${c.id}">''',
     '''<img src="${mediaThumb(c.image)}" data-nx-full="${mediaUrl(c.image)}" alt="${c.name}" class="w-full h-20 object-cover rounded-lg" onerror="imgErrorChain(this);" data-card-id="${c.id}">'''),
    ('колода, выбор карты (56px)',
     '''<img src="${mediaUrl(c.image)}" alt="${c.name}" class="w-full h-14 object-cover rounded" onerror="imgErrorChain(this);" data-card-id="${c.id}">''',
     '''<img src="${mediaThumb(c.image)}" data-nx-full="${mediaUrl(c.image)}" alt="${c.name}" class="w-full h-14 object-cover rounded" onerror="imgErrorChain(this);" data-card-id="${c.id}">'''),
    ('арена, выбор замены (96px)',
     '''<img src="${mediaUrl(x.f.image)}" class="w-full h-16 object-cover rounded-lg" onerror="imgErrorChain(this);" data-card-id="${x.f.cardId || ''}">''',
     '''<img src="${mediaThumb(x.f.image)}" data-nx-full="${mediaUrl(x.f.image)}" class="w-full h-16 object-cover rounded-lg" onerror="imgErrorChain(this);" data-card-id="${x.f.cardId || ''}">'''),
    ('арена, карточка бойца (80x112)',
     '''<img src="${mediaUrl(f.image)}" alt="${f.name}" class="w-20 h-28 object-cover rounded-xl shadow-lg shrink-0" onerror="imgErrorChain(this);" data-card-id="${f.cardId || ''}">''',
     '''<img src="${mediaThumb(f.image)}" data-nx-full="${mediaUrl(f.image)}" alt="${f.name}" class="w-20 h-28 object-cover rounded-xl shadow-lg shrink-0" onerror="imgErrorChain(this);" data-card-id="${f.cardId || ''}">'''),
    ('альбом, вид «строки» (36-44px)',
     '''<img src="${mediaUrl(card.image)}" alt="${card.name}" onerror="imgErrorChain(this);" class="absolute inset-0 w-full h-full object-cover">''',
     '''<img src="${mediaThumb(card.image)}" data-nx-full="${mediaUrl(card.image)}" alt="${card.name}" onerror="imgErrorChain(this);" class="absolute inset-0 w-full h-full object-cover">'''),
    ('студия, список паков (28x40)',
     '''<img src="${mediaUrl(p.image)}" class="w-7 h-10 object-cover rounded shrink-0" onerror="this.onerror=null;imgErrorChain(this);">''',
     '''<img src="${mediaThumb(p.image)}" data-nx-full="${mediaUrl(p.image)}" class="w-7 h-10 object-cover rounded shrink-0" onerror="this.onerror=null;imgErrorChain(this);">'''),
    ('студия, список карт (28x40)',
     '''<img src="${mediaUrl(c.image)}" class="w-7 h-10 object-cover rounded" onerror="imgErrorChain(this);" data-card-id="${c.id}">''',
     '''<img src="${mediaThumb(c.image)}" data-nx-full="${mediaUrl(c.image)}" class="w-7 h-10 object-cover rounded" onerror="imgErrorChain(this);" data-card-id="${c.id}">''',
     1),
    # b377: мини-игры. Символы слотов/сетки — это те же арты карт, и DOM-фолбэк
    # рисовал их мастерами: 9 ячеек слота x 2-4 МБ или 15 ячеек «сетки» x 7.9 МБ
    # распакованной битмапы. Ячейка на экране — 60-110 css px.
    ('слоты: DOM-фолбэк символа (aspect-square, ~90px)',
     '''const img = s.image ? `<img src="${mediaUrl(s.image)}" alt="${s.name}" class="w-full h-full object-cover" onerror="imgErrorChain(this)">` : '';''',
     '''const img = s.image ? `<img src="${mediaThumb(s.image)}" data-nx-full="${mediaUrl(s.image)}" alt="${s.name}" class="w-full h-full object-cover" onerror="imgErrorChain(this)">` : '';''',
     1),
    ('сетка: ячейка DOM-фолбэка (~60-110px, до 15 ячеек)',
     '''? `<img src="${mediaUrl(sym.image)}" alt="${sym.name}" class="absolute inset-0 w-full h-full object-cover" onerror="imgErrorChain(this)">`''',
     '''? `<img src="${mediaThumb(sym.image)}" data-nx-full="${mediaUrl(sym.image)}" alt="${sym.name}" class="absolute inset-0 w-full h-full object-cover" onerror="imgErrorChain(this)">`''',
     1),
    # b377: превью карты в Студии — одна карта, но мастер 2-4 МБ ради ~200 css px.
    ('студия: превью карты',
     '''box.innerHTML = `${image ? `<img src="${mediaUrl(image)}" alt="" onerror="imgErrorChain(this)" class="absolute inset-0 w-full h-full object-cover z-0">` : ''}''',
     '''box.innerHTML = `${image ? `<img src="${mediaThumbMid(image)}" data-nx-full="${mediaUrl(image)}" alt="" onerror="imgErrorChain(this)" class="absolute inset-0 w-full h-full object-cover z-0">` : ''}''',
     1),
]

# крупные сетки, где карт может быть 100+ — добавляем класс отложенной отрисовки
CV_SITES = [
    ('альбом: карточка (обычная)',
     '''<div onclick="inspectCard('${card.id}')" class="relative w-full card-aspect rounded-2xl border-2 ${getRarityClass(card.rarity)} ${cardHoloClass(card)} p-3 sm:p-4''',
     '''<div onclick="inspectCard('${card.id}')" class="nx-cv relative w-full card-aspect rounded-2xl border-2 ${getRarityClass(card.rarity)} ${cardHoloClass(card)} p-3 sm:p-4'''),
    ('альбом: карточка (компакт)',
     '''<div onclick="inspectCard('${card.id}')" class="relative w-full card-aspect rounded-xl border-2 ${getRarityClass(card.rarity)} ${cardHoloClass(card)} p-1.5 sm:p-2''',
     '''<div onclick="inspectCard('${card.id}')" class="nx-cv relative w-full card-aspect rounded-xl border-2 ${getRarityClass(card.rarity)} ${cardHoloClass(card)} p-1.5 sm:p-2'''),
    ('альбом: строка',
     '''<div onclick="inspectCard('${card.id}')" class="group flex items-center gap-2.5 sm:gap-3 rounded-xl border border-slate-800/80 bg-slate-900/60 p-2''',
     '''<div onclick="inspectCard('${card.id}')" class="nx-cv group flex items-center gap-2.5 sm:gap-3 rounded-xl border border-slate-800/80 bg-slate-900/60 p-2'''),
    ('биржа: строка лота',
     '''<div class="group flex items-center gap-2.5 rounded-xl border p-1.5 sm:p-2 transition-all duration-200 ${mine''',
     '''<div class="nx-cv group flex items-center gap-2.5 rounded-xl border p-1.5 sm:p-2 transition-all duration-200 ${mine'''),
    ('биржа: плитка лота',
     '''<div class="group relative rounded-xl border p-1.5 transition-all duration-200 flex flex-col gap-1.5 ${mine''',
     '''<div class="nx-cv group relative rounded-xl border p-1.5 transition-all duration-200 flex flex-col gap-1.5 ${mine'''),
]

# Альбом: уровень арта выбирается по виду сетки. «Галерея» (1 колонка на
# телефоне, карта ~358 css px) и просмотр карты остаются на полном арте —
# там качество видно. Остальные виды (2-8 колонок, ~120-180 css px) берут
# среднюю миниатюру 512px: на экране разница неотличима, а памяти в 4 раза меньше.
ALBUM_SITES = [
    ('albumCardHTML: выбор уровня арта',
     '            const compact = !!(opts && opts.compact);',
     '''            const compact = !!(opts && opts.compact);
            // 'full' — полный арт, 'mid' — 512px, 'thumb' — 256px (по умолчанию)
            const artTier = (opts && opts.art) || (compact ? 'thumb' : 'mid');
            const artFn = artTier === 'full' ? mediaUrl : (artTier === 'mid' ? mediaThumbMid : mediaThumb);'''),
    # b377: вхождений РОВНО 2 — компактная ветка и обычная. До b377 заменялось
    # только первое, поэтому обычная сетка альбома (вид по умолчанию) грузила
    # мастера 1080x1920 по 2-4 МБ на карту.
    ('albumCardHTML: <img> обеих веток (компакт + обычная)',
     '''<img src="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);" loading="lazy" decoding="async" class="absolute inset-0 w-full h-full object-cover z-0 group-hover:scale-105 transition duration-500">''',
     '''<img src="${artFn(card.image)}" data-nx-full="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);" loading="lazy" decoding="async" class="absolute inset-0 w-full h-full object-cover z-0 group-hover:scale-105 transition duration-500">''',
     2),
    ('renderAlbumGrid: вид «альбом» (страницы по 9)',
     "pg.map(c => albumCardHTML(c)).join('')",
     "pg.map(c => albumCardHTML(c, { art: 'mid' })).join('')"),
    ('renderAlbumGrid: сетка/галерея/компакт',
     "visible.map(c => albumCardHTML(c, { compact: cv === 'compact' })).join('')",
     "visible.map(c => albumCardHTML(c, { compact: cv === 'compact', art: cv === 'gallery' ? 'full' : (cv === 'compact' ? 'thumb' : 'mid') })).join('')"),
    # вскрытие пака: карта ~176 css px, но её рассматривают — берём 512px.
    # Отличается от просмотра карты отступом в 24 пробела (у просмотра — 16),
    # поэтому полный арт в модалке inspectCard остаётся нетронутым.
    ('вскрытие пака: карта на столе',
     '''                        <img src="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);" class="absolute inset-0 w-full h-full object-cover z-0">''',
     '''                        <img src="${mediaThumbMid(card.image)}" data-nx-full="${mediaUrl(card.image)}" alt="${card.name}" data-card-id="${card.id}" onerror="imgErrorChain(this);" class="absolute inset-0 w-full h-full object-cover z-0">'''),
]

# Витрина магазина и 3D-карусель паков. Именно они давали ~63 МБ распакованных
# битмапов ещё на СТАРТОВОМ экране: обложка пака показывается размером 176x235
# css-пикселей, а грузится арт 1152x2048 (9.0 МБ в памяти) или 1080x1920 (7.9 МБ).
# Пять плиток + пять «окон» бустера + панель выбранного пака = весь бюджет памяти
# WebView Telegram. На телефонах это и есть «игра вылетает / закрывается браузер».
PACK_SITES = [
    ('витрина: плитка пака (176x235 css)',
     '''<img src="${mediaUrl(pack.image)}" alt="${pack.title}" loading="lazy" onerror="this.onerror=null;imgErrorChain(this);">''',
     '''<img src="${mediaThumbMid(pack.image)}" data-nx-full="${mediaUrl(pack.image)}" alt="${pack.title}" loading="lazy" decoding="async" onerror="this.onerror=null;imgErrorChain(this);">''',
     1),
    ('карусель: «окно» бустера + панель выбранного пака (77-142 css)',
     '''<img src="${mediaUrl(pack.image)}" alt="${pack.title}" class="w-full h-full object-cover" onerror="this.onerror=null;imgErrorChain(this);">''',
     '''<img src="${mediaThumbMid(pack.image)}" data-nx-full="${mediaUrl(pack.image)}" alt="${pack.title}" class="w-full h-full object-cover" loading="lazy" decoding="async" onerror="this.onerror=null;imgErrorChain(this);">''',
     2),
    ('альбомы: обложка пака в сетке',
     '''<img src="${mediaUrl(pack.image)}" alt="${pack.title}" class="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-[1.07]" onerror="this.onerror=null;imgErrorChain(this);">''',
     '''<img src="${mediaThumbMid(pack.image)}" data-nx-full="${mediaUrl(pack.image)}" alt="${pack.title}" class="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-[1.07]" loading="lazy" decoding="async" onerror="this.onerror=null;imgErrorChain(this);">''',
     1),
    ('альбомы: обложка пака в списке (56-64 css)',
     '''<img src="${mediaUrl(pack.image)}" alt="${pack.title}" class="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.06]" onerror="this.onerror=null;imgErrorChain(this);">''',
     '''<img src="${mediaThumb(pack.image)}" data-nx-full="${mediaUrl(pack.image)}" alt="${pack.title}" class="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.06]" loading="lazy" decoding="async" onerror="this.onerror=null;imgErrorChain(this);">''',
     1),
    ('альбом: обложка в шапке (56-80 css)',
     '''<img src="${mediaUrl(pack.image)}" alt="" class="absolute inset-0 w-full h-full object-cover" onerror="this.onerror=null;imgErrorChain(this);">''',
     '''<img src="${mediaThumb(pack.image)}" data-nx-full="${mediaUrl(pack.image)}" alt="" class="absolute inset-0 w-full h-full object-cover" loading="lazy" decoding="async" onerror="this.onerror=null;imgErrorChain(this);">''',
     1),
    ('мокап бустера (вскрытие/превью)',
     '''<img src="${mediaUrl(image)}" alt="" class="w-full h-full object-cover" onerror="this.onerror=null;imgErrorChain(this);">''',
     '''<img src="${mediaThumbMid(image)}" data-nx-full="${mediaUrl(image)}" alt="" class="w-full h-full object-cover" loading="lazy" decoding="async" onerror="this.onerror=null;imgErrorChain(this);">''',
     1),
]

# Предзагрузка каталога. Раньше preloadAllGameImages() ставила в очередь ПОЛНЫЕ
# арты всех карт и паков. Для облачной комнаты это 156 файлов, из них 82 —
# PNG 1080x1920/1152x2048 по 2-4 МБ: ~157 МБ фонового трафика на старте,
# параллельно с витриной. На мобильной сети это минуты загрузки, забитый канал
# (картинки витрины не успевали) и непрерывная запись в IndexedDB.
# Теперь греются миниатюры: ~3 МБ вместо ~157 МБ.
PRELOAD_PATCHES = [
    ('preloadImages: греем миниатюры вместо полных артов',
     '''        function preloadImages(urls) {
            (urls || []).forEach(raw => {
                if (!raw || typeof raw !== 'string') return;
                const u = mediaUrl(raw);
                if (!u || u.indexOf('http') !== 0 || IMG_PRELOADED.has(u) || imgQueue.indexOf(u) >= 0) return;
                imgQueue.push(u);
            });
            imgPump();
        }''',
     '''        function preloadImages(urls, tier) {
            (urls || []).forEach(raw => {
                if (!raw || typeof raw !== 'string') return;
                // tier='full' — греть полный арт (нужно только для просмотра карты).
                // По умолчанию греем миниатюру 256px: полный арт облачного каталога
                // весит 2-4 МБ и показывается в списках размером 30-180 px.
                let u = mediaUrl(raw);
                if (tier !== 'full') { const t = mediaThumb(raw); if (t) u = t; }
                // b377: условие u.indexOf('http') === 0 отсекало ВСЕ встроенные арты
                // (NX_EMBED_MEDIA даёт относительные media/...), поэтому стандартный
                // каталог не грелся вообще и каждая карта грузилась «в момент показа».
                // Относительный путь браузер сам разрешит относительно документа.
                if (!u || IMG_PRELOADED.has(u) || imgQueue.indexOf(u) >= 0) return;
                if (u.indexOf('http') !== 0 && u.indexOf('media/') !== 0) return;
                imgQueue.push(u);
            });
            imgPump();
        }'''),
    ('injectPosterPreloads: <link rel=preload> на среднюю миниатюру',
     '''                    const u = mediaUrl(p.image);
                    if (IMG_OBJ.has(u)) return; // b180: постер уже в постоянном кэше — preload не нужен''',
     '''                    const u = mediaThumbMid(p.image) || mediaUrl(p.image);
                    if (IMG_OBJ.has(u)) return; // b180: постер уже в постоянном кэше — preload не нужен'''),
]

# loadImgSafe грузит арт для холста/WebGL-текстуры. Все её потребители рисуют
# на холст не крупнее 512x768 (текстура пака для three.js — 512x768, символы
# слотов — 224x512, «линии» — 256x368, карта в арене), но грузился ПОЛНЫЙ мастер:
# 1152x2048 = 9.0 МБ распакованной битмапы и 2-4 МБ трафика на каждый пак.
# Карусель магазина строит 5+ таких текстур на старте — отсюда десятки
# мегабайт и сотни мегабайт трафика ещё до первого клика.
LOADIMG_PATCH = (
    'loadImgSafe: текстуры из миниатюры 512px вместо мастера 1152x2048',
    '''            const first = mediaUrl(src);
            const cands = [first];
            if (first !== src) cands.push(src);''',
    '''            const first = mediaUrl(src);
            // Все потребители loadImgSafe рисуют арт на холст не крупнее 512x768,
            // поэтому сначала пробуем среднюю миниатюру 512px (1.8 МБ в памяти
            // вместо 9.0 МБ, ~60 КБ трафика вместо 2-4 МБ). Мастер — запасной
            // вариант: если миниатюры для файла нет, nxThumbFor вернёт пустоту.
            const mid = mediaThumbMid(src);
            const cands = [];
            if (mid && mid !== first) cands.push(mid);
            cands.push(first);
            if (first !== src) cands.push(src);''')

THUMB_HELPERS = '''
        // ===== УРОВНИ АРТОВ (tools/build.py) =====
        // Почему это главное исправление вылетов на телефоне:
        // каталог карт приходит из облака комнаты и ссылается на media/card_*.png
        // размером 1080x1920 и 1152x2048. Распакованная битмапа такого арта —
        // 7.9 и 9.0 МБ СООТВЕТСТВЕННО, а показывается он в списке размером
        // 76-176 css-пикселей. Стартовый экран держал ~63 МБ битмапов на 12
        // картинках; полный альбом — сотни мегабайт. iOS/Android убивают WebView.
        //
        // Теперь три уровня:
        //   media/t/  256px — списки, строки, компактные сетки  (~0.47 МБ в памяти)
        //   media/t2/ 512px — обычные сетки, вскрытие пака       (~1.9 МБ в памяти)
        //   мастер        — просмотр карты и вид «галерея» (1:1, как было)
        // Полноразмерные арты не пережаты и не изменены: там, где карта
        // показывается крупной, картинка осталась ровно той же.
        /*NX_EMBED_THUMB_START*/
        const NX_EMBED_THUMB = __THUMB_MAP__;
        const NX_EMBED_THUMB_MID = __THUMB_MID_MAP__;
        /*NX_EMBED_THUMB_END*/
        function nxThumbFor(u, tier) {
            try {
                const s = String(u == null ? '' : u);
                if (!s) return '';
                const full = mediaUrl(s);              // уже с учётом зеркала и NX_EMBED_MEDIA
                if (!full) return '';
                const map = (tier === 'mid') ? NX_EMBED_THUMB_MID : NX_EMBED_THUMB;
                const key = nxMediaKey(full) || nxMediaKey(s);
                const rel = map[key];
                if (rel) {
                    if (full.indexOf('http') !== 0) return rel;   // локальный арт — путь относительный
                    // облачная/зеркальная ссылка: миниатюра лежит рядом с мастером,
                    // подменяем только каталог media/ -> media/t/ (или media/t2/)
                    const i = full.lastIndexOf('/media/');
                    if (i < 0) return rel;
                    return full.slice(0, i + 7) + rel.slice(6);
                }
                // b377: файла нет в картах сборки. Так бывает, когда арт залила
                // автоотправка b343 уже после последней сборки — а значит, у него
                // НЕТ и миниатюры, и карта в сетке грузилась мастером 2-4 МБ.
                //
                // Если файл известен хотя бы в мелкой карте, значит средняя для
                // него не строилась намеренно (мастер уже 640px, MID_MIN_SRC) —
                // возвращаем пустоту, и mediaThumbMid() откатится на 256px,
                // без лишнего 404. Иначе путь-miniatury достраиваем по соглашению
                // media/t/<имя>.webp: если её на сервере нет, imgErrorChain
                // откатится на data-nx-full (полный арт) — заглушки не будет.
                if (tier === 'mid' && NX_EMBED_THUMB[key]) return '';
                if (!key) return '';
                const conv = (tier === 'mid' ? 'media/t2/' : 'media/t/')
                    + key.replace(/\.[^.]+$/, '') + '.webp';
                if (full.indexOf('http') !== 0) return conv;
                const j = full.lastIndexOf('/media/');
                if (j < 0) return conv;
                return full.slice(0, j + 7) + conv.slice(6);
            } catch (e) { return ''; }
        }
        function mediaThumb(u) {                       // 256px
            return nxThumbFor(u, 'small') || mediaUrl(u);
        }
        function mediaThumbMid(u) {                    // 512px, иначе мелкая, иначе мастер
            return nxThumbFor(u, 'mid') || nxThumbFor(u, 'small') || mediaUrl(u);
        }
'''

THUMB_ERROR_FALLBACK = '''                // миниатюра не отдалась (папки media/t/ или media/t2/ ещё не
                // задеплоены, файл битый, арт добавили после сборки) — показываем
                // полный арт: карта не должна оставаться заглушкой
                if (!el.__nxThumbTried && /\\/media\\/t2?\\//.test(u)) {
                    el.__nxThumbTried = 1;
                    const full = el.getAttribute && el.getAttribute('data-nx-full');
                    if (full && full !== u) { el.onerror = null; el.style.display = ''; el.src = full; return true; }
                }
'''

# --------------------------------------------------------------------------- #
# b377: фоновый трафик qr-transfer.js. Две функции качали МАСТЕРА у каждого
# игрока, в том числе на мобильной сети, и соревновались с загрузкой видимых
# карточек. Замер на стенде (iPhone 12, DPR 3, 36 реальных артов «Доктор Кто»):
#   было  — 167.4 МБ скачанных мастеров, 247.8 МБ распакованных битмапов;
#   стало —   4.9 МБ миниатюр,        68.8 МБ битмапов.
# --------------------------------------------------------------------------- #
AUTOCACHE_OLD = """    const jobs = [];
    try {
        nxAllMediaUrls().forEach(raw => {
            let eff = raw; try { eff = mediaUrl(raw); } catch (e) {}
            if (eff && eff.indexOf('http') === 0) jobs.push(eff);
        });
    } catch (e) { return; }"""

AUTOCACHE_NEW = """    const jobs = [];
    // b377: фоново кэшируем ТО, ЧТО РЕАЛЬНО ПОКАЗЫВАЕТСЯ НА ЭКРАНЕ — миниатюры
    // media/t/ (256px) и media/t2/ (512px), а не мастера 1080x1920.
    //
    // Раньше nxAutoCacheOnce() каждые 60 секунд ставила в очередь по 10 мастеров
    // по 1.6-4.3 МБ: ~30 МБ фонового трафика в минуту на КАЖДОМ устройстве,
    // включая мобильные, и без всякого участия игрока. Этот поток забивал канал
    // (видимые карточки не успевали прогрузиться) и наполнял IndexedDB файлами,
    // которые на экране не рисуются никогда. Именно так выглядит жалоба
    // «картинки не загружаются, особенно на телефоне».
    //
    // Мастера по-прежнему нужны, но только авто-вшиванию b341 и автоотправке
    // b343 в GitHub — а они работают лишь у владельца (нужен токен). Ему и
    // оставляем полный арт, всем остальным — миниатюры (в 21 раз меньше трафика,
    // офлайн-готовность интерфейса при этом сохраняется полностью).
    var nxAutoWantMaster = false;
    try { nxAutoWantMaster = !!nxGhToken() && (nxAutoEmbedOn() || nxAutoMediaOn()); } catch (e) {}
    try {
        nxAllMediaUrls().forEach(raw => {
            let eff = raw; try { eff = mediaUrl(raw); } catch (e) {}
            if (!eff || eff.indexOf('http') !== 0) return;
            if (nxAutoWantMaster) { jobs.push(eff); return; }
            let mid = '', small = '';
            try { mid = nxThumbFor(raw, 'mid'); small = nxThumbFor(raw, 'small'); } catch (e) {}
            // nxThumbFor возвращает '' для локальных (не http) артов и для файлов,
            // которых нет в картах сборки, — тогда остаётся мастер, как раньше.
            if (mid && mid.indexOf('http') === 0) jobs.push(mid);
            if (small && small.indexOf('http') === 0 && small !== mid) jobs.push(small);
            if (!mid && !small) jobs.push(eff);
        });
    } catch (e) { return; }"""

# миниатюры весят 18-62 КБ против 1.6-4.3 МБ у мастера — за подход можно взять
# больше файлов, и весь каталог прогреется за минуты, а не за полчаса.
AUTOCAP_OLD = "    const CAP = 10; // за подход не больше 10 файлов — не забиваем канал"
AUTOCAP_NEW = """    // b377: 10 — это было про мастера по 3 МБ. Миниатюры в 50 раз легче,
    // поэтому берём больше за подход и не держим канал занятым полчаса.
    const CAP = nxAutoWantMaster ? 10 : 40;"""

CHECKARTS_LOOP_OLD = """        keys.forEach(function (k) {
            var im = new Image();
            im.onload = function () { ok++; fin(); };
            im.onerror = function () { bad.push(k); fin(); };
            im.src = NX_EMBED_MEDIA[k];
        });"""
CHECKARTS_LOOP_NEW = """        // b377: раньше все 73 мастера открывались ОДНОВРЕМЕННО. Теперь очередь
        // с тремя потоками: диагностика не выбивает канал из-под видимых карточек.
        var ptr = 0;
        var pump = function () {
            if (ptr >= keys.length) return;
            var k = keys[ptr++];
            var im = new Image();
            im.decoding = 'async';
            im.onload = function () { ok++; fin(); pump(); };
            im.onerror = function () { bad.push(k); fin(); pump(); };
            im.src = NX_EMBED_MEDIA[k];
        };
        for (var q = 0; q < 3; q++) pump();"""

CHECKARTS_START_OLD = "setTimeout(function () { try { nxCheckArts(true); } catch (e) {} }, 9000);"
CHECKARTS_START_NEW = """// b377: автопроверка артов больше не запускается у каждого игрока.
// Через 9 секунд после старта она открывала 73 мастера одновременно — на
// мобильной сети канал вставал, и карточки, которые игрок реально видит,
// не успевали прогрузиться. Диагностика нужна владельцу (разблокированная
// «Студия»), кнопка «Проверить картинки» в Студии осталась на месте.
setTimeout(function () {
    try {
        var owner = false;
        try { owner = !!nxGhToken() || isHiddenTabUnlocked(); } catch (e) {}
        if (owner) nxCheckArts(true);
    } catch (e) {}
}, 9000);"""

# --------------------------------------------------------------------------- #
# b377: мёртвые blob:URL. IMG_OBJ держит не больше 18 записей и при вытеснении
# отзывает blob:URL. Если этот URL всё ещё висел на живой <img>, картинка
# мгновенно становилась битой, а imgErrorChain по blob: не делает НИЧЕГО:
# raw.indexOf('http') !== 0 -> ни ретраев, ни зеркала, ни кэша -> сразу
# заглушка. Игрок видит «?» вместо арта. На стенде это ловилось и до правки
# (3 случая), а после перевода на миниатюры — чаще (11), потому что разных URL
# в кэше стало больше. Чиним и причину (не отзываем занятое), и следствие
# (blob: -> обратно на реальный URL арта).
# --------------------------------------------------------------------------- #
BLOBTOUCH_OLD = """        function imgCacheTouch(url, ou) { // LRU «памяти»: свежая запись в конец, хвост отзываем
            try {
                IMG_OBJ.delete(url); IMG_OBJ.set(url, ou);
                while (IMG_OBJ.size > IMG_OBJ_MAX) {
                    const oldest = IMG_OBJ.keys().next().value;
                    const old = IMG_OBJ.get(oldest);
                    IMG_OBJ.delete(oldest);
                    try { URL.revokeObjectURL(old); } catch (e) {}
                }
            } catch (e) {}
        }"""

BLOBTOUCH_NEW = """        // b377: blob:URL, который ещё висит на живой <img>, отзывать НЕЛЬЗЯ —
        // картинка мгновенно становится битой, а imgErrorChain по blob: не ретраит
        // и не лезет в кэш, поэтому карта уходила в заглушку навсегда.
        // Занятые URL складываем в сироты и дожигаем, когда элемент уйдёт из DOM.
        const IMG_OBJ_ORPHANS = [];
        const IMG_OBJ_ORPHANS_MAX = 60;
        function nxBlobInUse(ou) {
            try {
                const imgs = document.images;
                for (let i = 0; i < imgs.length; i++) {
                    if (imgs[i].src === ou) return true;
                    const a = imgs[i].getAttribute && imgs[i].getAttribute('src');
                    if (a === ou) return true;
                }
            } catch (e) {}
            return false;
        }
        function nxBlobStillCached(ou) { // blob:URL снова вернулся в LRU — не трогаем
            try { for (const v of IMG_OBJ.values()) if (v === ou) return true; } catch (e) {}
            return false;
        }
        function nxBlobSweep() { // раз в минуту: отзываем то, что больше никому не нужно
            try {
                if (document.hidden) return;
                for (let i = IMG_OBJ_ORPHANS.length - 1; i >= 0; i--) {
                    const ou = IMG_OBJ_ORPHANS[i];
                    if (!ou) { IMG_OBJ_ORPHANS.splice(i, 1); continue; }
                    if (nxBlobStillCached(ou)) { IMG_OBJ_ORPHANS.splice(i, 1); continue; }
                    if (nxBlobInUse(ou) && IMG_OBJ_ORPHANS.length <= IMG_OBJ_ORPHANS_MAX) continue;
                    IMG_OBJ_ORPHANS.splice(i, 1);
                    try { URL.revokeObjectURL(ou); } catch (e) {}
                }
            } catch (e) {}
        }
        setInterval(nxBlobSweep, 60000);
        function imgCacheTouch(url, ou) { // LRU «памяти»: свежая запись в конец, хвост отзываем
            try {
                IMG_OBJ.delete(url); IMG_OBJ.set(url, ou);
                while (IMG_OBJ.size > IMG_OBJ_MAX) {
                    const oldest = IMG_OBJ.keys().next().value;
                    const old = IMG_OBJ.get(oldest);
                    IMG_OBJ.delete(oldest);
                    if (!old) continue;
                    if (nxBlobInUse(old)) {
                        if (IMG_OBJ_ORPHANS.indexOf(old) < 0) IMG_OBJ_ORPHANS.push(old);
                        continue;
                    }
                    try { URL.revokeObjectURL(old); } catch (e) {}
                }
            } catch (e) {}
        }"""

# запоминаем на элементе реальный http-URL арта: если blob: умрёт, откатываемся
# на него (это миниатюра, а не мастер), и тяжёлый арт зря не качается.
BLOBSAVE_OLD = """                const url = img.src; // абсолютный, уже после mediaUrl()-перезаписи зеркала
                if (!url || url.indexOf('http') !== 0) return;
                img.__nxC = 1;"""
BLOBSAVE_NEW = """                const url = img.src; // абсолютный, уже после mediaUrl()-перезаписи зеркала
                if (!url || url.indexOf('http') !== 0) return;
                img.__nxC = 1;
                img.__nxHttpUrl = url; // b377: куда вернуться, если blob:URL отзовут"""

BLOBCHAIN_OLD = """                if (!u || u.indexOf('data:') === 0) return false;"""
BLOBCHAIN_NEW = """                if (!u || u.indexOf('data:') === 0) return false;
                // b377: src оказался мёртвым blob:URL. Ниже по коду этот случай
                // не лечится вовсе: raw не начинается с http, поэтому ни ретраев,
                // ни зеркала, ни поиска в кэше — элемент сразу уходил в заглушку
                // и оставался с «?» навсегда. Возвращаем реальный URL арта:
                // сперва сохранённый http-адрес миниатюры (дёшево), потом
                // data-nx-full (мастер), потом запомненный оригинал.
                if (u.indexOf('blob:') === 0) {
                    el.__nxBlobRetry = (el.__nxBlobRetry || 0) + 1;
                    if (el.__nxBlobRetry <= 3) {
                        const cands = [el.__nxHttpUrl,
                                       el.getAttribute && el.getAttribute('data-nx-full'),
                                       el.__nxOrig, el.__nxThumbFor];
                        for (let ci = 0; ci < cands.length; ci++) {
                            const back = String(cands[ci] || '');
                            if (!back || back === u) continue;
                            if (back.indexOf('blob:') === 0 || back.indexOf('data:') === 0) continue;
                            el.__nxPh = 0; el.__nxRetry = 0; el.__nxCacheTried = 0;
                            el.__nxWait = 0; el.__nxOrig = back; el.__nxHttpUrl = back;
                            el.onerror = null; el.style.display = ''; el.src = back;
                            return true;
                        }
                    }
                }"""

MEMGUARD_OLD = "        if (mb < 350) return; // b318: пороги ниже — WebView Telegram живёт в меньшем лимите"
MEMGUARD_NEW = """        // Порог не абсолютный: на слабых Android jsHeapSizeLimit бывает ~256 МБ,
        // и фиксированные 350 МБ не достигались НИКОГДА — сторож просто не работал.
        let lim = 350;
        try { if (pm.jsHeapSizeLimit > 0) lim = Math.min(350, Math.floor(pm.jsHeapSizeLimit / 1048576 * 0.55)); } catch (e) {}
        if (lim < 120) lim = 120;
        if (mb < lim) return; // b318: WebView Telegram живёт в меньшем лимите"""

PIXELRATIO_OLD = """        function nxPixelRatio() { // b308: слабый GPU держит контекст живее без ретины 2x
            try {
                const d = window.devicePixelRatio || 1;
                const mob = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
                return Math.min(d, mob ? 1.5 : 2);
            } catch (e) { return 1; }
        }"""
PIXELRATIO_NEW = """        function nxLowRam() { // устройство с малой памятью / слабым CPU
            try {
                const dm = navigator.deviceMemory;               // Chrome/Android
                if (typeof dm === 'number' && dm > 0 && dm <= 3) return true;
                const hc = navigator.hardwareConcurrency;
                if (typeof hc === 'number' && hc > 0 && hc <= 3) return true;
            } catch (e) {}
            return false;
        }
        function nxPixelRatio() { // b308: слабый GPU держит контекст живее без ретины 2x
            try {
                const d = window.devicePixelRatio || 1;
                const mob = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
                // 1080x1920 канвас с DPR 3 = 3240x5760 = 74 МБ видеопамяти на ОДИН
                // рендерер. На устройствах с малой памятью режем до 1.0.
                return Math.min(d, mob ? (nxLowRam() ? 1 : 1.5) : 2);
            } catch (e) { return 1; }
        }"""

TAILWIND_GUARD_OLD = """            if (typeof window.tailwind === 'undefined') {
                setTimeout(() => showToast('⚠️ Нет доступа к CDN: стили/3D не загрузились. Откройте файл в браузере с интернетом', 'error'), 300);
            }"""
TAILWIND_GUARD_NEW = """            // Tailwind прекомпилирован в assets/tailwind.css — window.tailwind
            // больше не существует, и это нормально. Проверяем саму таблицу стилей.
            if (!document.getElementById('nx-tw-css')) {
                setTimeout(() => showToast('⚠️ Не загрузились стили (assets/tailwind.css). Проверьте подключение и обновите страницу', 'error'), 300);
            }"""

WATCHDOG_OLD = """        setInterval(() => {
            try {
                const imgs = document.images;
                for (let i = 0; i < imgs.length; i++) {
                    const el = imgs[i];
                    if (el.__nxPh || el.__nxWatch) continue;"""
WATCHDOG_NEW = """        setInterval(() => {
            try {
                if (document.hidden) return; // в фоне не сканируем: WebView и так под нагрузкой
                const imgs = document.images;
                for (let i = 0; i < imgs.length; i++) {
                    const el = imgs[i];
                    if (el.__nxPh || el.__nxWatch) continue;"""

TG_HARDENING = '''
// ===== Telegram Mini App / мобильная стабилизация (tools/build.py) =====
(function () {
    'use strict';
    function tg() {
        try { return (window.Telegram && window.Telegram.WebApp) || null; } catch (e) { return null; }
    }
    function harden() {
        var w = tg();
        if (!w) return;
        // Развернуть на весь экран: без этого мини-апп остаётся в маленьком окне,
        // а игра верстается под 100vh и получает обрезанный низ.
        try { w.expand(); } catch (e) {}
        // iOS: свайп сверху вниз закрывает мини-апп. Во время анимации вскрытия
        // пака или прокрутки альбома это срабатывает случайно — «игра сама закрылась».
        // Кнопка «Закрыть» при этом продолжает работать.
        try { if (w.disableVerticalSwipes) w.disableVerticalSwipes(); } catch (e) {}
        try { if (w.enableClosingConfirmation) w.enableClosingConfirmation(); } catch (e) {}
        // Клавиатура в WebView не двигает viewport — ловим сами, чтобы поле ввода
        // не уезжало под клавиатуру.
        try {
            if (w.onEvent) w.onEvent('viewportChanged', function () {
                try { window.dispatchEvent(new Event('resize')); } catch (e) {}
            });
        } catch (e) {}
    }
    if (tg()) harden();
    else {
        // telegram-web-app.js подгружается асинхронно — дожидаемся
        var tries = 0;
        var t = setInterval(function () {
            if (tg() || ++tries > 40) { clearInterval(t); harden(); }
        }, 100);
    }
    // --- защита от случайного масштабирования страницы -------------------
    // iOS 10+ и WKWebView (Telegram Mini App) игнорируют user-scalable=no,
    // поэтому масштаб закрывается здесь: отменяем системные жесты Safari,
    // двойной клик/тап и ctrl+колесо. Прокрутку и одиночные тапы не трогаем.
    ['gesturestart', 'gesturechange', 'gestureend'].forEach(function (t) {
        document.addEventListener(t, function (e) { e.preventDefault(); }, { passive: false });
    });
    document.addEventListener('dblclick', function (e) { e.preventDefault(); }, { passive: false });
    document.addEventListener('wheel', function (e) { if (e.ctrlKey) e.preventDefault(); }, { passive: false });
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && (e.key === '+' || e.key === '-' || e.key === '=' || e.key === '0')) e.preventDefault();
    });
    // Страховка для старых WebView: если страницу всё-таки растянули,
    // снимаем зум программно, возвращая масштаб к 1.
    (function () {
        var vv = window.visualViewport;
        if (!vv) return;
        var fix = function () {
            try {
                var s = vv.scale || 1;
                if (Math.abs(s - 1) > 0.02) {
                    // мета-тег уже просит scale=1; форсируем возврат жестом прокрутки
                    window.scrollTo(window.scrollX, window.scrollY);
                    try { nxCrashLog('zoomguard: visualViewport.scale=' + s.toFixed(2)); } catch (e) {}
                }
            } catch (e) {}
        };
        vv.addEventListener('resize', fix);
    })();

    // WebView Telegram замораживают, а не закрывают: pagehide может не прийти.
    // Сохраняемся на всех сигналах, иначе прогресс теряется при убийстве процесса.
    ['pagehide', 'freeze', 'visibilitychange'].forEach(function (ev) {
        window.addEventListener(ev, function () {
            try {
                if (ev === 'visibilitychange' && !document.hidden) return;
                if (typeof saveState === 'function') saveState();
            } catch (e) {}
        }, { passive: true });
    });
    // iOS Safari не даёт performance.memory — сторож памяти там молчал.
    // Дублируем его грубой, но работающей везде оценкой: сколько распакованных
    // битмапов держат <img> на странице.
    //
    // b381: КРИТИЧЕСКАЯ ПРАВКА. Раньше сторож делал im.removeAttribute('src')
    // и НИКОГДА не возвращал src обратно. Стоило альбому/вскрытию пака набрать
    // >160 МБ битмапов (а 59 карт «Евровидения» мастерами — это ~460 МБ), как
    // все уехавшие за экран карты гасли permanently: при скролле назад
    // пользователь видел чёрные дыры и «битые» картинки. Именно это чаще всего
    // и выглядело как «на телефоне карты не загружаются».
    // Теперь: src подменяется прозрачной заглушкой 1x1 (не removeAttribute —
    // WebKit на пустом src может пойти за самим документом), а всё выгруженное
    // возвращается, как только элемент снова приближается к экрану — и по
    // таймеру, и мгновенно на скролле.
    var NX_BLANK_GIF = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    function nxImgRestoreOne(im) {
        try {
            var back = im.__nxUnloaded;
            if (!back) return false;
            im.__nxUnloaded = 0;
            // сбрасываем флаги цепочки ошибок: URL тот же, но попытка новая
            im.__nxPh = 0; im.__nxRetry = 0; im.__nxWait = 0; im.__nxThumbTried = 0;
            im.__nxMediaTried = 0; im.__nxMir = 0; im.__nxCb = 0;
            im.__nxCacheTried = 0; im.__nxBlobRetry = 0; im.__nxWatch = 0;
            im.onerror = function () { try { imgErrorChain(this); } catch (e) {} };
            im.style.display = '';
            im.src = back;
            return true;
        } catch (e) { return false; }
    }
    function nxImgRestoreVisible() {
        try {
            var vh = window.innerHeight || 800;
            var imgs = document.images, n = 0;
            for (var i = 0; i < imgs.length; i++) {
                var im = imgs[i];
                if (!im.__nxUnloaded || !im.getBoundingClientRect) continue;
                var r = im.getBoundingClientRect();
                // возвращаем с запасом в экран сверху и снизу — без «догрузки на глазах»
                if (r.bottom < -vh || r.top > vh * 2) continue;
                if (nxImgRestoreOne(im)) n++;
            }
            return n;
        } catch (e) { return 0; }
    }
    var nxRestoreThrottle = 0;
    ['scroll', 'resize', 'orientationchange'].forEach(function (ev) {
        window.addEventListener(ev, function () {
            var now = Date.now();
            if (now - nxRestoreThrottle < 120) return;
            nxRestoreThrottle = now;
            nxImgRestoreVisible();
        }, { passive: true, capture: true });
    });
    setInterval(function () {
        try {
            if (document.hidden) return;
            var vh = window.innerHeight || 800;
            var imgs = document.images, bytes = 0, heavy = 0;
            // 1) сперва возвращаем выгруженное — иначе карта так и останется пустой
            nxImgRestoreVisible();
            // 2) теперь считаем битмапы тех, что реально рядом с экраном
            for (var i = 0; i < imgs.length; i++) {
                var el = imgs[i];
                if (!el.complete || !el.naturalWidth || el.__nxUnloaded) continue;
                if (!el.getBoundingClientRect) continue;
                var r = el.getBoundingClientRect();
                // за экраном битмап браузеру не нужна — не считаем
                if (r.bottom < -200 || r.top > vh + 200) continue;
                var b = el.naturalWidth * el.naturalHeight * 4;
                bytes += b;
                if (b > 2 * 1024 * 1024) heavy++;
            }
            var mb = bytes / 1048576;
            if (mb > 160 || heavy > 24) {
                // подменяем src у крупных картинок ЗА экраном — WebKit освободит битмапы
                var freed = 0;
                for (var j = 0; j < imgs.length; j++) {
                    var im = imgs[j];
                    if (!im.complete || !im.naturalWidth || im.__nxUnloaded) continue;
                    if (!im.getBoundingClientRect) continue;
                    if (im.naturalWidth * im.naturalHeight * 4 < 400000) continue;
                    var rr = im.getBoundingClientRect();
                    if (rr.bottom < -600 || rr.top > vh + 600) {
                        im.__nxUnloaded = im.src;
                        im.onerror = null;
                        im.src = NX_BLANK_GIF;
                        freed++;
                    }
                }
                if (freed) {
                    try { nxCrashLog('imgguard: на экране ~' + Math.round(mb) + ' МБ битмапов, выгружено ' + freed); } catch (e) {}
                }
            }
        } catch (e) {}
    }, 8000);
})();
'''

APP_CSS_EXTRA = '''

/* ===== b380: КОТИК РАБОТАЕТ КИРКОЙ; скала и берлога прокачиваются ===== */
#miner-cat-stage{height:132px}
#miner-cat-stage svg{width:152px;height:155px}
@media (max-width:639px){#miner-cat-stage{height:112px}#miner-cat-stage svg{width:128px;height:130px}}
#kc-pick{transform-origin:68px 100px}
.working #kc-pick{animation:catSwing .95s cubic-bezier(.45,.05,.55,.95) infinite}
@keyframes catSwing{0%,100%{transform:rotate(-24deg)}42%{transform:rotate(13deg)}52%{transform:rotate(11deg)}70%{transform:rotate(-6deg)}}
.working #kc-body{animation:catLean .95s ease-in-out infinite}
@keyframes catLean{0%,100%{transform:rotate(0) translateX(0)}42%,52%{transform:rotate(3.5deg) translateX(2.5px)}}
.working #kc-head{animation:catHeadWork .95s ease-in-out infinite}
@keyframes catHeadWork{0%,100%{transform:rotate(0)}42%,52%{transform:rotate(-3deg) translate(1.5px,1px)}}
#kc-chips{display:none}
.working #kc-chips{display:block}
#kc-chips path{opacity:0}
.working #kc-chips path{animation:catChip .95s ease-out infinite}
.working #kc-chips path:nth-child(2){animation-delay:.05s}
.working #kc-chips path:nth-child(3){animation-delay:.1s}
@keyframes catChip{0%,46%{opacity:0;transform:translate(0,0) scale(.7)}54%{opacity:1}100%{opacity:0;transform:translate(var(--cx,6px),var(--cy,-10px)) scale(1.05)}}
#kc-rock-3 ellipse{animation:rockGlow 2.6s ease-in-out infinite}
@keyframes rockGlow{0%,100%{opacity:.22}50%{opacity:.4}}
.working #kc-lamp-glow{animation:lampFlick 1.7s ease-in-out infinite}
@keyframes lampFlick{0%,100%{opacity:1}45%{opacity:.72}60%{opacity:.92}}
@media (prefers-reduced-motion:reduce){.working #kc-pick,.working #kc-body,.working #kc-head,.working #kc-chips path,#kc-rock-3 ellipse,.working #kc-lamp-glow{animation:none}}

/* ============================================================
   Дополнения мобильной сборки (tools/build.py)
   ============================================================ */

/* Отложенная отрисовка длинных списков. content-visibility:auto велит браузеру
   не считать layout и не рисовать то, что за пределами экрана; contain-intrinsic-size
   reserves место, чтобы полоса прокрутки не прыгала. В альбоме/на бирже бывает
   100-300 карточек — это главный источник подвисаний при прокрутке на телефоне.
   Браузеры без поддержки просто игнорируют правило. */
@supports (content-visibility: auto) {
    .nx-cv {
        content-visibility: auto;
        contain-intrinsic-size: auto 300px;
    }
}

/* iPhone: вырез/чёлка и нижняя полоса не должны перекрывать интерфейс */
@supports (padding: env(safe-area-inset-top)) {
    body {
        padding-top: env(safe-area-inset-top);
        padding-bottom: env(safe-area-inset-bottom);
        padding-left: env(safe-area-inset-left);
        padding-right: env(safe-area-inset-right);
    }
}

/* Меньше «резиновых» перерисовок при прокрутке на слабых GPU */
@media (max-width: 1023px) {
    .nx-cv { will-change: auto; }
}

/* ============================================================
   Защита от случайного «растягивания» игры (пинч-зум, двойной тап)
   ============================================================
   Жалоба игроков: случайный щипок или двойной тап растягивает страницу,
   раскладка уезжает, игра выглядит сломанной. Прокрутка и обычные тапы
   должны работать ровно как раньше — отключается ТОЛЬКО масштабирование.

   touch-action: pan-x pan-y  = разрешены прокрутка по обеим осям и тапы,
   запрещены pinch-zoom и double-tap zoom. Значение учитывается как
   пересечение по всей цепочке предков, поэтому html+body достаточно,
   чтобы закрыть всю страницу. Свои touch-обработчики игры (scratch-карта
   с touch-none, свайпы карусели с pan-x) не затрагиваются. */
html, body {
    touch-action: pan-x pan-y;
}
/* полям ввода оставляем привычное поведение: манипуляции без дабл-тап-зума,
   но без ограничений прокрутки внутри многострочных textarea */
input, textarea, select, [contenteditable="true"] {
    touch-action: manipulation;
}
/* ИСКЛЮЧЕНИЕ: у нарезчика сторис (#s9-view) собственный пинч и drag —
   масштаб кадра и перенос рамки. Там жесты отдаём приложению, а не браузеру,
   иначе pointercancel сломал бы редактору два пальца. */
#s9-view, #s9-root canvas {
    touch-action: none;
}
/* iOS: отключаем «резиновое» растягивание за пределы страницы */
html, body {
    overscroll-behavior: none;
}
/* ===== b383: 6 биомов пещеры + подпись прокачки ===== */
#kc-cave-bar{display:flex;align-items:center;justify-content:space-between;gap:6px;margin:0 0 4px;padding:3px 8px;border-radius:8px;border:1px solid rgba(51,65,85,.7);background:rgba(15,23,42,.6);transition:background .35s,border-color .35s}
#kc-cave-name{font-size:9px;font-weight:900;letter-spacing:.02em;color:#e2e8f0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#kc-cave-next{font-size:9px;font-weight:700;color:#94a3b8;white-space:nowrap}
#miner-cat-box[data-tier="0"] #kc-cave-bar{background:rgba(87,63,29,.22);border-color:rgba(120,83,45,.5)}
#miner-cat-box[data-tier="1"] #kc-cave-bar{background:rgba(146,64,14,.2);border-color:rgba(180,83,9,.5)}
#miner-cat-box[data-tier="2"] #kc-cave-bar{background:rgba(71,85,105,.2);border-color:rgba(100,116,139,.55)}
#miner-cat-box[data-tier="3"] #kc-cave-bar{background:rgba(8,145,178,.16);border-color:rgba(34,211,238,.5)}
#miner-cat-box[data-tier="3"] #kc-cave-name{color:#a5f3fc}
#miner-cat-box[data-tier="3"] #kc-cave-next{color:#67e8f9}
#miner-cat-box[data-tier="4"] #kc-cave-bar{background:rgba(180,83,9,.22);border-color:rgba(251,191,36,.55)}
#miner-cat-box[data-tier="4"] #kc-cave-name{color:#fde68a}
#miner-cat-box[data-tier="4"] #kc-cave-next{color:#fbbf24}
#miner-cat-box[data-tier="5"] #kc-cave-bar{background:linear-gradient(90deg,rgba(124,58,237,.25),rgba(249,115,22,.22));border-color:rgba(224,242,254,.5)}
#miner-cat-box[data-tier="5"] #kc-cave-name{color:#fffbeb}
#miner-cat-box[data-tier="5"] #kc-cave-next{color:#e0f2fe}
#miner-cat-box[data-tier="3"]{box-shadow:inset 0 0 34px rgba(34,211,238,.07)}
#miner-cat-box[data-tier="4"]{box-shadow:inset 0 0 34px rgba(251,191,36,.09)}
#miner-cat-box[data-tier="5"]{box-shadow:inset 0 0 40px rgba(224,242,254,.09)}

/* ===== b385: оси анимаций котика точно по геометрии (голова/хвост/кирка не «отлетают») ===== */
#kc-head{transform-origin:60px 78px}
#kc-ear-l{transform-origin:41px 38px}
#kc-ear-r{transform-origin:79px 38px}
#kc-tail-up{transform-origin:52px 98px}
#kc-paw-r{transform-origin:68px 90px}
#kc-pick{transform-origin:67px 94px}
/* ===== b386: биомы 6-9 (прокачка пещеры до 1000 уровня) ===== */
#miner-cat-box[data-tier="6"] #kc-cave-bar{background:rgba(124,45,18,.28);border-color:rgba(249,115,22,.55)}
#miner-cat-box[data-tier="6"] #kc-cave-name{color:#fdba74}
#miner-cat-box[data-tier="6"] #kc-cave-next{color:#fb923c}
#miner-cat-box[data-tier="7"] #kc-cave-bar{background:rgba(14,116,144,.22);border-color:rgba(125,211,252,.55)}
#miner-cat-box[data-tier="7"] #kc-cave-name{color:#cffafe}
#miner-cat-box[data-tier="7"] #kc-cave-next{color:#7dd3fc}
#miner-cat-box[data-tier="8"] #kc-cave-bar{background:rgba(127,29,29,.3);border-color:rgba(252,211,77,.6)}
#miner-cat-box[data-tier="8"] #kc-cave-name{color:#fde68a}
#miner-cat-box[data-tier="8"] #kc-cave-next{color:#fcd34d}
#miner-cat-box[data-tier="9"] #kc-cave-bar{background:linear-gradient(90deg,rgba(49,46,129,.4),rgba(14,165,233,.28));border-color:rgba(224,231,255,.6)}
#miner-cat-box[data-tier="9"] #kc-cave-name{color:#e0e7ff}
#miner-cat-box[data-tier="9"] #kc-cave-next{color:#a5b4fc}
#miner-cat-box[data-tier="6"]{box-shadow:inset 0 0 34px rgba(249,115,22,.1)}
#miner-cat-box[data-tier="7"]{box-shadow:inset 0 0 34px rgba(125,211,252,.09)}
#miner-cat-box[data-tier="8"]{box-shadow:inset 0 0 36px rgba(252,211,77,.1)}
#miner-cat-box[data-tier="9"]{box-shadow:inset 0 0 42px rgba(165,180,252,.12)}
/* ===== b391: пакетное вскрытие — фольга и волна распаковки ===== */
.nx-foil{background:linear-gradient(115deg,#c7ccd8 0%,#eef1f7 18%,#b9c0cf 32%,#f2f4fa 47%,#c2c8d6 61%,#e9ecf4 78%,#bfc6d4 100%);transition:transform .5s cubic-bezier(.4,0,.2,1) var(--nx-d,0ms),opacity .45s linear var(--nx-d,0ms)}
.nx-foil:after{content:'';position:absolute;inset:0;background:repeating-linear-gradient(45deg,rgba(255,255,255,.16) 0 6px,rgba(255,255,255,0) 6px 12px)}
.nx-peel .nx-foil{transform:translateY(-112%) rotate(7deg);opacity:0}
.nx-bt{cursor:pointer}
#nx-batch-modal .nx-bt img{transition:transform .3s}
#nx-batch-modal .nx-peel img{transform:scale(1.02)}
'''

SW_JS = '''/* nx-media-sw v2 (%s): cache-first для media/ и assets/, network-first для HTML.
   Арты и скрипты скачиваются с сервера ОДИН раз на браузер; дальше отдаются из
   кэша мгновенно — в Telegram Mini App повторное открытие становится мгновенным
   и работает без сети. Тихая сверка с сервером — не чаще раза в 7 дней на файл. */
const VERSION = '%s';
const CACHE_MEDIA = 'nx-media-v2';
const CACHE_ASSETS = 'nx-assets-' + VERSION;
const CACHE_PAGES = 'nx-pages-' + VERSION;
const MAX_ENTRIES = 500;
const REVALIDATE_MS = 7 * 24 * 60 * 60 * 1000;

self.addEventListener('install', e => {
    self.skipWaiting();
});
self.addEventListener('activate', e => {
    e.waitUntil((async () => {
        // старые версии кэшей не копятся: на слабом телефоне место на вес золота
        const keep = [CACHE_MEDIA, CACHE_ASSETS, CACHE_PAGES];
        for (const k of await caches.keys()) if (keep.indexOf(k) < 0) await caches.delete(k);
        await self.clients.claim();
    })());
});

self.addEventListener('message', e => {
    if (e && e.data === 'nx-skip-waiting') self.skipWaiting();
});

self.addEventListener('fetch', e => {
    const req = e.request;
    if (req.method !== 'GET') return;
    const url = new URL(req.url);
    if (url.origin !== self.location.origin) return;

    const p = url.pathname;
    if (p.indexOf('/media/') >= 0) { e.respondWith(mediaFirst(e, url, CACHE_MEDIA)); return; }
    if (p.indexOf('/assets/') >= 0) { e.respondWith(mediaFirst(e, url, CACHE_ASSETS)); return; }
    if (req.mode === 'navigate' || /\\.html?$/.test(p) || p.endsWith('/')) {
        e.respondWith(pageFirst(e, req));
    }
});

/* вечный cache-first: файл неизменяем, сверяемся редко и только в фоне */
async function mediaFirst(e, url, cacheName) {
    const bypass = url.searchParams.has('nxcb');
    const cache = await caches.open(cacheName);
    if (!bypass) {
        const hit = await cache.match(e.request.url, { ignoreSearch: true });
        if (hit) {
            const ts = Number(hit.headers.get('x-nx-ts') || 0);
            if (Date.now() - ts > REVALIDATE_MS) e.waitUntil(refresh(cache, e.request));
            return hit;
        }
    }
    try {
        const resp = await fetch(e.request);
        if (resp.ok && !bypass) e.waitUntil(store(cache, e.request, resp.clone()));
        return resp;
    } catch (err) {
        const stale = await cache.match(e.request.url, { ignoreSearch: true });
        if (stale) return stale;
        throw err;
    }
}

/* HTML: сначала сеть (иначе игрок застрянет на старой версии), кэш — запасной выход */
async function pageFirst(e, req) {
    const cache = await caches.open(CACHE_PAGES);
    try {
        const resp = await fetch(req);
        if (resp.ok) e.waitUntil(cache.put(req, resp.clone()));
        return resp;
    } catch (err) {
        const stale = await cache.match(req) || await cache.match('./');
        if (stale) return stale;
        throw err;
    }
}

async function store(cache, req, resp) {
    try {
        const headers = new Headers(resp.headers);
        headers.set('x-nx-ts', String(Date.now()));
        const body = await resp.blob();
        await cache.put(req, new Response(body, { status: resp.status, statusText: resp.statusText, headers: headers }));
        await trim(cache);
    } catch (e) {}
}

async function refresh(cache, req) {
    try {
        const resp = await fetch(req, { cache: 'no-store' });
        if (resp.ok) await store(cache, req, resp.clone());
    } catch (e) {}
}

async function trim(cache) {
    try {
        const keys = await cache.keys();
        if (keys.length <= MAX_ENTRIES) return;
        const stamped = [];
        for (const k of keys) {
            const r = await cache.match(k);
            stamped.push([Number((r && r.headers.get('x-nx-ts')) || 0), k]);
        }
        stamped.sort((a, b) => a[0] - b[0]);
        const drop = keys.length - MAX_ENTRIES;
        for (let i = 0; i < drop; i++) await cache.delete(stamped[i][1]);
    } catch (e) {}
}
'''


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    argv = sys.argv[1:]
    no_media = '--no-media' in argv

    if not os.path.exists(SRC):
        print('нет tools/source-index.html — положите туда текущий index.html')
        return 1
    os.makedirs(ASSETS, exist_ok=True)

    lines = read_lines(SRC)
    src_text = '\r\n'.join(lines)
    say('источник: %d строк, %.2f МБ' % (len(lines), len(src_text.encode()) / 1048576))

    # --- извлекаем блоки ------------------------------------------------- #
    three_js = inner(lines, 'three')
    app_js = inner(lines, 'app_js')
    stories_js = inner(lines, 'stories')
    qrcode_js = inner(lines, 'qrcode')
    qrxfer_js = inner(lines, 'qr_xfer')
    app_css = inner(lines, 'app_css')
    fa_css = inner(lines, 'fa')

    # --- миниатюры -------------------------------------------------------- #
    # Для ВСЕХ файлов media/: облачный каталог комнаты ссылается на card_*.png
    # напрямую, в HTML этих имён нет, но без миниатюр именно они роняют телефон.
    all_imgs = all_media_images()
    say('артов в media/: %d (в HTML упомянуто %d, остальные приходят из облака)'
        % (len(all_imgs), len(used_media(src_text))))
    thumb_map, mid_map = {}, {}
    if not no_media:
        thumb_map, mid_map = build_thumbs(all_imgs, force='--force-media' in argv)
    else:
        for f in all_imgs:
            b = os.path.splitext(f)[0]
            if os.path.exists(os.path.join(THUMBS, b + '.webp')):
                thumb_map[f] = 'media/t/' + b + '.webp'
            if os.path.exists(os.path.join(MIDS, b + '.webp')):
                mid_map[f] = 'media/t2/' + b + '.webp'
        say('миниатюры: пропущено (--no-media), найдено %d мелких / %d средних'
            % (len(thumb_map), len(mid_map)))

    # --- Font Awesome ----------------------------------------------------- #
    fa_scan = '\r\n'.join(lines[:BLOCKS['fa'][0] - 1] + lines[BLOCKS['fa'][1]:])
    used_icons = fa_used_icons(fa_scan)
    for bad, good in FA_FIXES.items():
        used_icons.discard(bad[3:])
        used_icons.add(good[3:])
    fa_out, keep, unresolved, dropped = build_fontawesome(fa_css, used_icons)
    say('Font Awesome: иконок %d (правлено битых имён: %d), CSS %d -> %d Б, правил удалено %d'
        % (len(keep), len(FA_FIXES), len(fa_css), len(fa_out), dropped))
    if unresolved:
        say('  ! не найдено в Font Awesome 6 Free: %s' % ', '.join(unresolved))
    write_lf(os.path.join(ASSETS, 'fa.css'), fa_out)
    say('  шрифт fa-solid-900.woff2: %d Б' % os.path.getsize(os.path.join(ASSETS, 'fa-solid-900.woff2')))

    # --- Tailwind --------------------------------------------------------- #
    tw_path = os.path.join(ASSETS, 'tailwind.css')
    if '--tw' in argv or not os.path.exists(tw_path):
        say('Tailwind: прекомпиляция через node ...')
        shutil.copy(SRC, os.path.join(ROOT, 'tools', '_tw_src.html'))
        r = subprocess.run(['node', os.path.join(ROOT, 'tools', 'twbuild.js')],
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode != 0:
            print(r.stdout, r.stderr)
            raise SystemExit('не удалось прекомпилировать Tailwind (нужен node + tailwindcss)')
        say('  ' + r.stdout.strip())
    say('Tailwind CSS: %d Б' % os.path.getsize(tw_path))

    # --- пишем ассеты ----------------------------------------------------- #
    def w(name, text):
        p = os.path.join(ASSETS, name)
        write_lf(p, text)
        say('assets/%-18s %8.1f КБ' % (name, os.path.getsize(p) / 1024))

    # сторож памяти живёт в блоке qr-transfer, а не в основном коде игры
    say('правки qr-transfer (b377, фоновый трафик):')
    qrxfer_js, _n = patch_once(qrxfer_js, MEMGUARD_OLD, MEMGUARD_NEW,
                               'сторож памяти: относительный порог heap')
    qrxfer_js, _n = patch_once(qrxfer_js, AUTOCACHE_OLD, AUTOCACHE_NEW,
                               'авто-кэш: качаем миниатюры, а не мастера 1.6-4.3 МБ')
    qrxfer_js, _n = patch_once(qrxfer_js, AUTOCAP_OLD, AUTOCAP_NEW,
                               'авто-кэш: очередь 40 миниатюр вместо 10 мастеров')
    qrxfer_js, _n = patch_once(qrxfer_js, CHECKARTS_LOOP_OLD, CHECKARTS_LOOP_NEW,
                               'проверка артов: 3 потока вместо 73 сразу')
    qrxfer_js, _n = patch_once(qrxfer_js, CHECKARTS_START_OLD, CHECKARTS_START_NEW,
                               'проверка артов: автозапуск только у владельца')
    for _lbl, _o, _n in PROFKILL_QR:
        qrxfer_js, _n2 = patch_once(qrxfer_js, _o, _n, 'b379: ' + _lbl)

    w('three.min.js', three_js)
    w('qrcode.min.js', qrcode_js)
    w('stories.js', stories_js)
    w('qr-transfer.js', qrxfer_js)
    w('app.css', app_css + APP_CSS_EXTRA)

    # --- правим код игры -------------------------------------------------- #
    say('правки кода:')
    js = app_js

    js, _ = patch_all(js, 'fa-solid fa-sack-coins', 'fa-solid fa-sack-dollar',
                      'иконка fa-sack-coins (нет в FA Free) -> fa-sack-dollar')
    js, _ = patch_all(js, 'fa-solid fa-sparkles', 'fa-solid fa-wand-magic-sparkles',
                      'иконка fa-sparkles (нет в FA Free) -> fa-wand-magic-sparkles')

    anchor = '/*NX_EMBED_MEDIA_END*/'
    assert anchor in js, 'не найден маркер NX_EMBED_MEDIA_END'
    js = js.replace(anchor, anchor + THUMB_HELPERS
                    .replace('__THUMB_MAP__', json.dumps(thumb_map, ensure_ascii=False, sort_keys=True))
                    .replace('__THUMB_MID_MAP__', json.dumps(mid_map, ensure_ascii=False, sort_keys=True)), 1)
    say('  · добавлены mediaThumb()/mediaThumbMid(): %d мелких + %d средних миниатюр'
        % (len(thumb_map), len(mid_map)))

    # b377: want по умолчанию 1 — любое расхождение с источником роняет сборку,
    # а не молча оставляет половину мест на мастерах.
    for site in ALBUM_SITES:
        label, old, new = site[0], site[1], site[2]
        want = site[3] if len(site) > 3 else 1
        js, _ = patch_once(js, old, new, 'уровни артов: ' + label, required=False, want=want)
    for label, old, new, want in PACK_SITES:
        n = js.count(old)
        if n != want:
            say('  ! витрина/карусель «%s»: ожидалось %d вхождений, найдено %d' % (label, want, n))
        js = js.replace(old, new)
        say('  · %s (заменено %d)' % (label, n))
    for site in THUMB_SITES:
        label, old, new = site[0], site[1], site[2]
        want = site[3] if len(site) > 3 else 1
        js, _ = patch_once(js, old, new, 'миниатюры: ' + label, required=False, want=want)
    for label, old, new in PRELOAD_PATCHES:
        js, _ = patch_once(js, old, new, label)
    js, _ = patch_once(js, LOADIMG_PATCH[1], LOADIMG_PATCH[2], LOADIMG_PATCH[0])
    for site in CV_SITES:
        label, old, new = site[0], site[1], site[2]
        want = site[3] if len(site) > 3 else 1
        js, _ = patch_once(js, old, new, 'content-visibility: ' + label, required=False, want=want)

    js, _ = patch_once(js,
                       'const raw = el.__nxOrig || u;',
                       THUMB_ERROR_FALLBACK + '                const raw = el.__nxOrig || u;',
                       'фолбэк миниатюра -> полный арт в imgErrorChain')
    # b379: синхронизация профилей удалена целиком
    say('правки b379 (синхронизация профилей удалена):')
    for _lbl, _o, _n in PROFKILL_JS:
        js, _ = patch_once(js, _o, _n, 'b379: ' + _lbl)
    say('правки b380 (котик работает киркой, скала и берлога прокачиваются):')
    for _lbl, _o, _n in PROFWORK_JS:
        js, _ = patch_once(js, _o, _n, 'b380: ' + _lbl)
    js = js.replace('onclick="buyPack(\'${pack.id}\')"', 'onclick="buyPack(\'${pack.id}\', nxPackQty)"')  # b391: все кнопки вскрытия уважают количество
    js, _ = patch_once(js, BLOBTOUCH_OLD, BLOBTOUCH_NEW,
                       'b377: не отзываем blob:URL, который ещё на живой <img>')
    js, _ = patch_once(js, BLOBSAVE_OLD, BLOBSAVE_NEW,
                       'b377: запоминаем http-URL арта на элементе')
    js, _ = patch_once(js, BLOBCHAIN_OLD, BLOBCHAIN_NEW,
                       'b377: imgErrorChain лечит мёртвый blob:URL')
    js, _ = patch_once(js, PIXELRATIO_OLD, PIXELRATIO_NEW, 'nxPixelRatio: учёт deviceMemory')
    js, _ = patch_once(js, TAILWIND_GUARD_OLD, TAILWIND_GUARD_NEW, 'убран ложный тост «нет CDN»')
    js, _ = patch_once(js, WATCHDOG_OLD, WATCHDOG_NEW, 'watchdog картинок: не работаем в фоне')

    js, n_l, n_d = add_img_attrs(js)
    say('  · <img>: добавлено loading="lazy" %d, decoding="async" %d' % (n_l, n_d))

    w('app.js', js)

    # --- собираем index.html --------------------------------------------- #
    say('сборка index.html:')
    v = BUILD_TAG
    head_new = [
        '    <!-- Мобильная сборка %s: тяжёлые библиотеки вынесены в assets/ и кешируются -->' % v,
        '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '    <!-- three.js нужен только в 3D-режимах и только по клику: defer не блокирует парсинг -->',
        '    <script src="assets/three.min.js?v=%s" defer></script>' % v,
        '    <link rel="stylesheet" href="assets/fa.css?v=%s">' % v,
        '    <!-- Inter грузится НЕ блокируя отрисовку: fonts.googleapis.com может быть',
        '         недоступен, и раньше страница висела до таймаута сети -->',
        '    <link rel="stylesheet" media="print" onload="this.media=\'all\'"',
        '          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap">',
        '    <noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"></noscript>',
        '    <link rel="stylesheet" href="assets/app.css?v=%s">' % v,
        '    <!-- ПРЕДКОМПИЛИРОВАННЫЙ Tailwind. Раньше здесь работал Tailwind Play CDN:',
        '         JIT-компилятор + PostCSS выполнялись В БРАУЗЕРЕ и пересобирали весь CSS',
        '         при каждой мутации DOM (~550 мс холодного прогона). На телефоне это',
        '         блокировало главный поток во время анимаций — отсюда подвисания и',
        '         закрытие WebView. Теперь CSS статический, а JS-компилятора нет вовсе. -->',
        '    <link id="nx-tw-css" rel="stylesheet" href="assets/tailwind.css?v=%s">' % v,
    ]

    # разметка тела: между <body> и первым скриптом игры (строки 1090..3611).
    # Скрипты 3612..20241 ушли в assets/ и подключаются отдельными тегами ниже.
    body = list(lines[BODY_OPEN:BLOCKS['app_js'][0] - 1])
    body_text = '\r\n'.join(body)
    for bad, good in FA_FIXES.items():
        c = body_text.count(bad)
        if c:
            body_text = body_text.replace(bad, good)
            say('  · разметка: %s -> %s (%d)' % (bad, good, c))
    # b378: блок профиля-синхронизации из модалки QR. В текущем монолите его
    # может уже не быть (убран) — тогда просто пропускаем; но если генератор
    # снова принесёт его, сборка уберёт блок сама.
    for _lbl, _a, _b in MARKUP_SCENE:
        _n2 = body_text.count(_a)
        if _n2 != 1:
            raise AssertionError('сцена котика «%s»: якорь встретился %d раз' % (_lbl, _n2))
        body_text = body_text.replace(_a, _b, 1)
        say('  · разметка: %s' % _lbl)
    _n = body_text.count(MARKUP_PROF_BLOCK_OLD)
    if _n > 1:
        raise AssertionError('разметка: блок профиля QR встретился %d раза' % _n)
    if _n == 1:
        body_text = body_text.replace(MARKUP_PROF_BLOCK_OLD, '')
        say('  · разметка: убран блок «Профиль/Ввести код/Ссылка/Синхронизировать/Отвязать» из модалки QR')
    body_text, bl, bd = add_img_attrs(body_text)
    say('  · разметка: <img> добавлено loading="lazy" %d, decoding="async" %d' % (bl, bd))

    out = []
    out.extend(lines[0:12])                            # 1..12: doctype … <meta charset>
    assert '<title>' in lines[16], 'строка 17 — не <title>: %r' % lines[16][:60]
    assert 'rel="icon"' in lines[17], 'строка 18 — не favicon: %r' % lines[17][:60]
    out.append(lines[16])                              # 17: <title>
    # пропускаем 3 no-cache мета-тега и старый viewport, ставим свой
    out.append('    <!-- Убраны <meta http-equiv="Cache-Control/Pragma/Expires" no-cache>:')
    out.append('         часть WebView честно их выполняла и каждый раз качала 3.2 МБ заново.')
    out.append('         Кешированием теперь занимается sw.js + версионирование ?v= -->')
    # maximum-scale/user-scalable=no работает на Android Chrome/WebView и старых iOS.
    # На iOS 10+ Safari их игнорирует (доступность) — там масштабу мешают
    # touch-action в app.css и отмена жестов в скрипте ниже.
    out.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">')
    out.append('    <meta name="theme-color" content="#020617">')
    out.append('    <meta name="mobile-web-app-capable" content="yes">')
    out.append('    <meta name="apple-mobile-web-app-capable" content="yes">')
    out.append('    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">')
    out.append('    <meta name="format-detection" content="telephone=no">')
    out.append(lines[17])                              # favicon
    out.extend(head_new)
    out.append('</head>')
    out.append(lines[BODY_OPEN - 1])                   # <body …>
    out.append(body_text)
    # скрипты в конце body — порядок как в оригинале
    out.append('    <!-- Код игры. Внешний файл: кешируется отдельно от разметки. -->')
    out.append('    <script src="assets/app.js?v=%s"></script>' % v)
    out.append('    <script src="assets/stories.js?v=%s"></script>' % v)
    out.append('    <script src="assets/qrcode.min.js?v=%s"></script>' % v)
    out.append('    <script src="assets/qr-transfer.js?v=%s"></script>' % v)
    out.append('    <script>%s</script>' % TG_HARDENING)
    out.append('</body>')
    out.append('</html>')

    html = '\r\n'.join(out)
    write_crlf(os.path.join(ROOT, 'index.html'), html)
    say('index.html: %.2f МБ -> %.2f МБ' % (len(src_text.encode()) / 1048576,
                                            len(html.encode()) / 1048576))

    # --- service worker --------------------------------------------------- #
    write_lf(os.path.join(ROOT, 'sw.js'), SW_JS % (v, v))
    say('sw.js: v2 (media/ + assets/ cache-first, HTML network-first)')

    # --- отчёт ------------------------------------------------------------ #
    total = sum(os.path.getsize(os.path.join(ASSETS, f))
                for f in os.listdir(ASSETS))
    say('assets/ всего: %.2f МБ' % (total / 1048576))
    say('')
    say('Первый визит качает: index.html + app.js + tailwind.css + fa.css + app.css + three.js')
    say('Повторный визит: всё из кэша SW, сеть не трогается.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
