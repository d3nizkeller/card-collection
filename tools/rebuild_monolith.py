#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rebuild_monolith.py — пересобрать tools/source-index.html из СОБРАННЫХ файлов.

Зачем
─────
build.py режет монолит по абсолютным номерам строк (BLOCKS) и применяет к блокам
серию patch_once(OLD → NEW). Монолит в репозитории разошёлся с реальностью:
он на b397, а assets/app.js — на b441+, границы блоков съехали, и переводы строк
LF вместо CRLF. Сборщик сегодня падает на первой же проверке:

    источник: 1 строк, 3.32 МБ
    IndexError: list index out of range          (inner(), lines[3619-1])

Этот скрипт собирает монолит заново из того, что реально работает:
assets/app.js, assets/stories.js, assets/qrcode.min.js, assets/qr-transfer.js,
assets/app.css и разметка из index.html.

Как
───
1. Все правила сборщика (patch_once / patch_all) ВЫЧИТЫВАЮТСЯ из tools/build.py
   исполнением его же исходника в песочнице — список правок не хардкодится и не
   устаревает.
2. Каждое правило ИНВЕРТИРУЕТСЯ: NEW → OLD. Так монолит снова содержит
   «до-патченый» код, и build.py сможет применить свои правки заново.
   Инверсия выполняется только если NEW найден, а OLD отсутствует — иначе правило
   пропускается и попадает в отчёт (значит, оно уже неактуально).
3. <img loading="lazy" decoding="async"> убираются: их добавляет add_img_attrs().
4. Разметка берётся из index.html, но head пересобирается по образцу монолита:
   build.py генерирует head сам (tw_cdn/tw_config/three/fa/app_css + ссылки),
   поэтому в монолите должны лежать ИСХОДНЫЕ блоки, а не собранные.
5. Границы блоков пересчитываются:BLOCKS/BODY_CLOSE в build.py обновляются
   (та же логика, что в tools/sync_build_blocks.py).
6. Проверка: build.py --no-media запускается на результате, и его вывод
   сравнивается с текущими собранными файлами. Расхождения печатаются.

Запуск
──────
    python3 tools/rebuild_monolith.py --check     # только отчёт, ничего не пишет
    python3 tools/rebuild_monolith.py             # собрать монолит + обновить build.py
    python3 tools/rebuild_monolith.py --verify    # собрать и прогнать round-trip

Безопасность: старые файлы сохраняются как source-index.html.bak и build.py.bak.
"""
import io
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'tools', 'source-index.html')
BLD = os.path.join(ROOT, 'tools', 'build.py')
ASSETS = os.path.join(ROOT, 'assets')

BLOCK_KEYS = ['app_css', 'app_js', 'stories', 'qrcode', 'qr_xfer']


def say(*a):
    print(*a)


RULES_CACHE = []


def read(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def write(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


# --------------------------------------------------------------------------- #
# 1. Правила сборщика: исполняем build.py в песочнице и перехватываем patch_once
# --------------------------------------------------------------------------- #
def sync_blocks_text(monolith_text, bld_text):
    """Пересчитать BLOCKS/BODY_CLOSE в тексте build.py под данный монолит."""
    lines = monolith_text.replace('\r\n', '\n').split('\n')
    pairs = find_pairs(lines)
    scripts = [(x, y) for x, y, k in pairs if k == 'script']
    styles = [(x, y) for x, y, k in pairs if k == 'style']
    if not scripts or not styles:
        raise SystemExit('в монолите не нашлось <script>/<style>')
    app_css = max(styles, key=lambda p: p[1] - p[0])
    after_css = [p for p in scripts if p[0] > app_css[1]]
    if len(after_css) < 4:
        raise SystemExit('после app_css ожидалось >=4 <script>, найдено %d' % len(after_css))
    app_js = max(after_css, key=lambda p: p[1] - p[0])
    tail = sorted([p for p in after_css if p[0] > app_js[1]])
    if len(tail) < 3:
        raise SystemExit('после app_js ожидалось 3 блока, найдено %d' % len(tail))
    stories, qrcode, qr_xfer = tail[0], tail[1], tail[2]
    body_close = qr_xfer[1] + 1
    if lines[body_close - 1].strip() != '</body>':
        raise SystemExit('строка %d — не </body>, а %r' % (body_close, lines[body_close - 1][:60]))
    found = {'app_css': app_css, 'app_js': app_js, 'stories': stories,
             'qrcode': qrcode, 'qr_xfer': qr_xfer}
    s = bld_text
    for key in BLOCK_KEYS:
        x, y = found[key]
        pat = re.compile(r"(^\s*'%s':\s*\()\s*\d+\s*,\s*\d+(\s*,)" % re.escape(key), re.M)
        s, n = pat.subn(lambda m: '%s%d, %d%s' % (m.group(1), x, y, m.group(2)), s, count=1)
        if n != 1:
            raise SystemExit('в build.py не нашлась строка блока %r' % key)
    s, n = re.subn(r'^BODY_CLOSE\s*=\s*\d+', 'BODY_CLOSE = %d' % body_close, s, count=1, flags=re.M)
    if n != 1:
        raise SystemExit('в build.py не нашёлся BODY_CLOSE')
    return s, found, body_close


def harvest_rules():
    """
    Правила сборщика живут ВНУТРИ main(), поэтому просто исполнить build.py
    недостаточно — его надо запустить. Делаем это на копии старого монолита
    (приведённой к CRLF и с пересчитанными границами), перехватывая patch_once
    и всю запись файлов. Вывод сборки не нужен, нужен список правил.
    """
    import tempfile

    tmp = tempfile.mkdtemp(prefix='nxmono-')
    try:
        os.makedirs(os.path.join(tmp, 'tools'))
        os.makedirs(os.path.join(tmp, 'assets'))
        for f in ('app.js', 'stories.js', 'qrcode.min.js', 'qr-transfer.js', 'three.min.js',
                  'app.css', 'tailwind.css', 'fa.css', 'fa-solid-900.woff2'):
            src = os.path.join(ASSETS, f)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(tmp, 'assets', f))
        shutil.copy2(os.path.join(ROOT, 'index.html'), os.path.join(tmp, 'index.html'))
        for d in ('media', os.path.join('media', 't'), os.path.join('media', 't2'),
                  os.path.join('media', 't3')):
            os.makedirs(os.path.join(tmp, d), exist_ok=True)

        mon = read(SRC).replace('\r\n', '\n').replace('\n', '\r\n')
        bld = read(BLD)
        bld2, _found, _bc = sync_blocks_text(mon, bld)
        write(os.path.join(tmp, 'tools', 'source-index.html'), mon)
        write(os.path.join(tmp, 'tools', 'build.py'), bld2)

        ns = {'__name__': 'build_probe', '__file__': os.path.join(tmp, 'tools', 'build.py')}
        with io.open(os.path.join(tmp, 'tools', 'build.py'), encoding='utf-8') as f:
            code = compile(f.read(), 'build.py', 'exec')
        exec(code, ns)

        rules = []
        real_once = ns['patch_once']
        real_all = ns['patch_all']

        def traced_once(text, old, new, label, required=True, want=None):
            rules.append((label, old, new, bool(required)))
            return real_once(text, old, new, label, required, want)

        def traced_all(text, old, new, label):
            rules.append((label, old, new, False))
            return real_all(text, old, new, label)

        # Пишем по-настоящему: w() после записи делает os.path.getsize(),
        # а shutil.copy/os.remove ожидают файл на диске. Перехват нужен только
        # чтобы не трогать настоящий репозиторий — работаем в tmp.
        written = {}

        def traced_write_lf(path, text):
            written[path] = text
            with io.open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(text.replace('\r\n', '\n'))

        def traced_write_crlf(path, text):
            written[path] = text
            with io.open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(text.replace('\r\n', '\n').replace('\n', '\r\n'))

        ns['patch_once'] = traced_once
        ns['patch_all'] = traced_all
        ns['write_lf'] = traced_write_lf
        ns['write_crlf'] = traced_write_crlf

        old_argv = sys.argv
        old_cwd = os.getcwd()
        sys.argv = ['build.py', '--no-media']
        try:
            os.chdir(tmp)
            ns['main']()
        except SystemExit:
            pass
        except Exception as e:
            say('  ! прогон сборщика для сбора правил прервался: %s' % e)
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)
        return rules, ns
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- #
# 2. Инверсия правил: NEW → OLD
# --------------------------------------------------------------------------- #
def invert(text, rules, report):
    """NEW → OLD. Возвращает (текст, число_замен, статусы) где статусы —
    список (label, old, new, required, inverted)."""
    applied = 0
    status = []
    for label, old, new, required in rules:
        if not old or not new or old == new:
            status.append((label, old, new, required, False))
            continue
        n_new = text.count(new)
        n_old = text.count(old)
        if n_new == 0:
            report.append(('нет NEW', label, required))
            status.append((label, old, new, required, False))
            continue
        if n_old > 0:
            report.append(('OLD и NEW одновременно', label, required))
            status.append((label, old, new, required, False))
            continue
        text = text.replace(new, old)
        applied += n_new
        status.append((label, old, new, required, True))
    return text, applied, status


def obsolete_labels(monolith_text, status, exclude_inverted_elsewhere):
    """
    Правила, которые ИНВЕРТИРОВАТЬ не удалось, но чей OLD в новом монолите всё
    ещё встречается. Такие правила сборщик применит и испортит результат:
    их надо выключить явно, по имени.
    """
    out = set()
    for label, old, new, required, inverted in status:
        if inverted or not old:
            continue
        if label in exclude_inverted_elsewhere:
            continue                      # правило нужно другому блоку — не трогаем
        if monolith_text.count(old) > 0:
            out.add(label)
    return out


def strip_img_attrs(text):
    """add_img_attrs() добавляет loading="lazy" и decoding="async" каждому <img."""
    n = text.count(' loading="lazy"')
    text = text.replace(' loading="lazy"', '')
    m = text.count(' decoding="async"')
    text = text.replace(' decoding="async"', '')
    return text, n, m


def strip_appended(text, bns, what):
    """Убрать хвост, который сборщик дописывает сам: w('app.css', app_css + APP_CSS_EXTRA)."""
    extra = (bns or {}).get('APP_CSS_EXTRA', '') if isinstance(bns, dict) else ''
    if extra and text.endswith(extra):
        say('%s: снят дописываемый хвост APP_CSS_EXTRA (%d байт)' % (what, len(extra)))
        return text[:-len(extra)]
    if extra:
        i = text.rfind(extra.strip()[:120])
        if i > 0:
            say('%s: APP_CSS_EXTRA найден не в самом конце — обрезано с позиции %d' % (what, i))
            return text[:i].rstrip('\n') + '\n'
        say('  ! %s: APP_CSS_EXTRA не найден (возможно, блок уже изменён)' % what)
    return text


def strip_injected(text, bns, const, what):
    """
    Убрать блок, который сборщик ВСТАВЛЯЕТ в середину файла (THUMB_HELPERS:
    карты миниатюр + nxThumbFor/mediaThumb/…). Границы берём из первой и последней
    непустой строки самой константы — содержимое между ними заполняется реальными
    картами миниатюр, поэтому дословно блок не совпадёт.
    """
    blk = (bns or {}).get(const, '') if isinstance(bns, dict) else ''
    if not blk:
        return text
    lines = [l for l in blk.split('\n') if l.strip()]
    if not lines:
        return text
    head, tail = lines[0].strip(), lines[-1].strip()
    i = text.find(head)
    if i < 0:
        say('  ! %s: внедряемый блок %s не найден (начало %r)' % (what, const, head[:60]))
        return text
    j = text.find(tail, i)
    if j < 0:
        say('  ! %s: найден конец внедряемого блока %s' % (what, const))
        return text
    end = j + len(tail)
    # съедаем перевод строки после блока
    while end < len(text) and text[end] in '\r\n':
        end += 1
        break
    start = text.rfind('\n', 0, i) + 1
    say('%s: снят внедряемый блок %s (%d байт)' % (what, const, end - start))
    return text[:start] + text[end:]


# --------------------------------------------------------------------------- #
# 3. Сборка монолита
# --------------------------------------------------------------------------- #
def build_monolith():
    report = []
    rules, bns = harvest_rules()
    RULES_CACHE.append(rules)
    RULES_CACHE.append(bns)
    say('правил сборщика вычитано: %d' % len(rules))

    js = read(os.path.join(ASSETS, 'app.js')).replace('\r\n', '\n')
    stories = read(os.path.join(ASSETS, 'stories.js')).replace('\r\n', '\n')
    qrcode = read(os.path.join(ASSETS, 'qrcode.min.js')).replace('\r\n', '\n')
    qrxfer = read(os.path.join(ASSETS, 'qr-transfer.js')).replace('\r\n', '\n')
    app_css = read(os.path.join(ASSETS, 'app.css')).replace('\r\n', '\n')

    js = strip_injected(js, bns, 'THUMB_HELPERS', 'app.js')
    js, n_applied, js_status = invert(js, rules, report)
    js, n_lazy, n_dec = strip_img_attrs(js)
    say('app.js: инвертировано замен %d, пропущено правил %d, убрано loading=%d decoding=%d'
        % (n_applied, len(js_status) - n_applied, n_lazy, n_dec))

    # qr-transfer тоже правится сборщиком (b377/b379)
    qrxfer, q_applied, q_status = invert(qrxfer, rules, report)
    qrxfer, _, _ = strip_img_attrs(qrxfer)
    say('qr-transfer.js: инвертировано %d' % q_applied)

    # правила, успешно инвертированные для qr-transfer, глобально выключать нельзя
    qrxfer_ok = {st[0] for st in q_status if st[4]}
    obsolete = obsolete_labels(js, js_status, qrxfer_ok)
    say('устаревших правил, которые надо выключить в build.py: %d' % len(obsolete))

    old_mon = read(SRC).replace('\r\n', '\n')
    old_lines = old_mon.split('\n')

    head = build_head(old_lines, app_css)
    body = build_body()

    parts = []
    parts.extend(head)
    parts.extend(body)
    parts.append('    <script>')
    parts.extend(js.rstrip('\n').split('\n'))
    parts.append('    </script>')
    parts.append('    <script>')
    parts.extend(stories.rstrip('\n').split('\n'))
    parts.append('    </script>')
    parts.append('    <script>')
    parts.extend(qrcode.rstrip('\n').split('\n'))
    parts.append('    </script>')
    parts.append('    <script>')
    parts.extend(qrxfer.rstrip('\n').split('\n'))
    parts.append('    </script>')
    parts.append('</body>')
    parts.append('</html>')

    text = '\r\n'.join(parts) + '\r\n'
    return text, report, rules, obsolete


def build_head(old_lines, app_css):
    """
    Head монолита: берём из СТАРОГО монолита всё до блока app_css включительно —
    там лежат исходные tw_cdn/tw_config/three/fa, которые build.py заменяет на
    прекомпилированные. app_css подставляется из assets/app.css (он собран из
    монолитного <style> плюс APP_CSS_EXTRA, поэтому инвертируем и его).
    """
    # ищем в старом монолите последний <style> перед кодом игры
    idx_css_open = idx_css_close = None
    for i, l in enumerate(old_lines):
        if l.strip().startswith('<style') and idx_css_open is None and i > 140:
            idx_css_open = i
        elif l.strip() == '</style>' and idx_css_open is not None and idx_css_close is None:
            idx_css_close = i
            break
    if idx_css_open is None or idx_css_close is None:
        raise SystemExit('в старом монолите не найден блок <style> с CSS игры')

    css_body = strip_appended(app_css, RULES_CACHE[1] if len(RULES_CACHE) > 1 else None, 'app.css')
    css_body, n_app, css_status = invert(css_body, RULES_CACHE[0], [])
    say('app.css: инвертировано %d, пропущено %d' % (n_app, len(css_status) - n_app))

    head = old_lines[:idx_css_open + 1]           # … <style>
    head.extend(css_body.rstrip('\n').split('\n'))
    head.append('    </style>')
    return head


def build_body():
    """
    Разметка body: берём из собранного index.html всё между <body …> и первым
    <script src="assets/…"> (дальше идут теги, которые build.py генерирует сам).
    """
    html = read(os.path.join(ROOT, 'index.html')).replace('\r\n', '\n')
    lines = html.split('\n')
    try:
        i_body = next(i for i, l in enumerate(lines) if l.strip().startswith('<body'))
    except StopIteration:
        raise SystemExit('в index.html не найден <body>')
    try:
        i_first_script = next(i for i, l in enumerate(lines)
                              if i > i_body and '<script src="assets/' in l)
    except StopIteration:
        i_first_script = len(lines)
    # скрипт nx-cloud.js (если подключён) — не часть монолита, его добавляет сборщик
    while i_first_script > i_body and 'nx-cloud.js' in lines[i_first_script - 1]:
        i_first_script -= 1
    body = lines[i_body:i_first_script]
    while body and not body[-1].strip():
        body.pop()
    say('index.html: разметка body — %d строк' % len(body))
    return body


# --------------------------------------------------------------------------- #
# 3bis. Список устаревших правил → в build.py
# --------------------------------------------------------------------------- #
OBS_START = 'NX_OBSOLETE = {'
OBS_DEFAULT = 'NX_OBSOLETE = set()  # заполняется tools/rebuild_monolith.py'


def write_obsolete(bld_text, labels):
    """Вставить/обновить NX_OBSOLETE в build.py.

    Эти правила сборщик применить НЕ может: их OLD-текст переписан более
    поздними правками (b414+), которых в списке патчей нет. Если их не выключить,
    сборка заменит то, что заменять уже не нужно, и результат разъедется с продом.
    """
    body = 'NX_OBSOLETE = {\n' + ''.join("    %r,\n" % l for l in sorted(labels)) + '}'
    if OBS_START in bld_text:
        a = bld_text.index(OBS_START)
        b = None  # конец литерала множества ищем ниже
        depth = 0
        for i in range(a, len(bld_text)):
            if bld_text[i] == '{':
                depth += 1
            elif bld_text[i] == '}':
                depth -= 1
                if depth == 0:
                    b = i + 1
                    break
        return bld_text[:a] + body + bld_text[b:]
    # вставляем перед def patch_once
    anchor = 'def patch_once(text, old, new, label, required=True, want=None):'
    if anchor not in bld_text:
        say('  ! в build.py не найден patch_once — NX_OBSOLETE не вставлен')
        return bld_text
    guard = (body + '\n\n\ndef patch_once(text, old, new, label, required=True, want=None):\n'
             '    if label in NX_OBSOLETE:\n'
             "        say('  · %s — устарело (переписано правками b414+), пропущено' % label)\n"
             '        return text, 0')
    return bld_text.replace(anchor, guard, 1)


# --------------------------------------------------------------------------- #
# 4. Пересчёт границ блоков в build.py
# --------------------------------------------------------------------------- #
def find_pairs(lines):
    pairs, opened = [], None
    for i, l in enumerate(lines, 1):
        st = l.strip()
        if st.startswith('<script') or st.startswith('<style'):
            opened = (i, 'style' if st.startswith('<style') else 'script')
        elif st in ('</script>', '</style>'):
            if opened:
                pairs.append((opened[0], i, opened[1]))
                opened = None
    return pairs


def sync_blocks(monolith_text):
    lines = monolith_text.replace('\r\n', '\n').split('\n')
    pairs = find_pairs(lines)
    scripts = [(a, b) for a, b, k in pairs if k == 'script']
    styles = [(a, b) for a, b, k in pairs if k == 'style']
    if not scripts or not styles:
        raise SystemExit('в новом монолите не нашлось <script>/<style>')
    app_css = max(styles, key=lambda p: p[1] - p[0])
    after_css = [p for p in scripts if p[0] > app_css[1]]
    if len(after_css) < 4:
        raise SystemExit('после app_css ожидалось >=4 <script>, найдено %d' % len(after_css))
    app_js = max(after_css, key=lambda p: p[1] - p[0])
    tail = sorted([p for p in after_css if p[0] > app_js[1]])
    if len(tail) < 3:
        raise SystemExit('после app_js ожидалось 3 блока, найдено %d' % len(tail))
    stories, qrcode, qr_xfer = tail[0], tail[1], tail[2]

    body_close = qr_xfer[1] + 1
    if lines[body_close - 1].strip() != '</body>':
        raise SystemExit('строка %d — не </body>, а %r' % (body_close, lines[body_close - 1][:60]))

    found = {'app_css': app_css, 'app_js': app_js, 'stories': stories,
             'qrcode': qrcode, 'qr_xfer': qr_xfer}
    s = read(BLD)
    for key in BLOCK_KEYS:
        a, b = found[key]
        pat = re.compile(r"(^\s*'%s':\s*\()\s*\d+\s*,\s*\d+(\s*,)" % re.escape(key), re.M)
        s, n = pat.subn(lambda m: '%s%d, %d%s' % (m.group(1), a, b, m.group(2)), s, count=1)
        if n != 1:
            raise SystemExit('в build.py не нашлась строка блока %r' % key)
    s, n = re.subn(r'^BODY_CLOSE\s*=\s*\d+', 'BODY_CLOSE = %d' % body_close, s, count=1, flags=re.M)
    if n != 1:
        raise SystemExit('в build.py не нашёлся BODY_CLOSE')
    return s, found, body_close


# --------------------------------------------------------------------------- #
# 5. Round-trip проверка
# --------------------------------------------------------------------------- #
def verify():
    say('')
    say('проверка: запускаю build.py --no-media на новом монолите…')
    env = dict(os.environ)
    r = subprocess.run([sys.executable, os.path.join('tools', 'build.py'), '--no-media'],
                       cwd=ROOT, capture_output=True, text=True, env=env)
    tail = (r.stdout or '').strip().split('\n')[-6:]
    for l in tail:
        say('  | ' + l)
    if r.returncode != 0:
        say('  ! build.py завершился с кодом %d' % r.returncode)
        for l in (r.stderr or '').strip().split('\n')[-12:]:
            say('  ! ' + l)
        return False
    say('  ✓ сборка прошла')
    return True


def main():
    args = sys.argv[1:]
    do_check = '--check' in args
    do_verify = '--verify' in args

    say('rebuild_monolith: собираю tools/source-index.html из assets/* и index.html')
    say('─' * 68)
    text, report, rules, obsolete = build_monolith()

    required_missing = [r for r in report if r[2] and r[0] == 'нет NEW']
    say('')
    say('правил не применено: %d (из них обязательных без NEW: %d)' % (len(report), len(required_missing)))
    for kind, label, req in report[:25]:
        say('  · [%s] %s%s' % (kind, label, '  (required)' if req else ''))
    if len(report) > 25:
        say('  … и ещё %d' % (len(report) - 25))

    new_blocks, body_close = None, None
    if not do_check:
        shutil.copy2(SRC, SRC + '.bak')
        shutil.copy2(BLD, BLD + '.bak')
        write(SRC, text)
        say('')
        say('записан tools/source-index.html: %.2f МБ, %d строк (копия: .bak)'
            % (len(text.encode()) / 1048576.0, text.count('\r\n')))
        bld, found, body_close = sync_blocks(text)
        bld = write_obsolete(bld, obsolete)
        write(BLD, bld)
        say('обновлены границы блоков в tools/build.py:')
        for k in BLOCK_KEYS:
            say('  · %-8s %d–%d' % (k, found[k][0], found[k][1]))
        say('  · BODY_CLOSE %d' % body_close)

    if do_verify:
        ok = verify()
        if not ok and not do_check:
            say('')
            say('откат: monolith и build.py восстановлены из .bak? — НЕТ, копии рядом:')
            say('  %s.bak' % SRC)
            say('  %s.bak' % BLD)
        return 0 if ok else 1

    if do_check:
        say('')
        say('--check: ничего не записано. Монолит был бы %.2f МБ / %d строк'
            % (len(text.encode()) / 1048576.0, text.count('\r\n')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
