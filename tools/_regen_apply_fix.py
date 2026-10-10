#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пересобирает tools/apply_fix.py под правку b363 («один IP = один пользователь»,
определение устройств). Блоки: APP_EDITS (assets/app.js + монолит), MONO_EDITS
(только монолит: кнопка в шапке панели), QR_EDITS пусто.
Большие куски (рендер панели, html-строка) читаются из файлов tools/_b363_*.txt.
"""
import io, os, ast, subprocess

AP = 'tools/apply_fix.py'
app_head = subprocess.run(['git', 'show', 'HEAD:assets/app.js'], capture_output=True, text=True).stdout
mono_head_html = subprocess.run(['git', 'show', 'HEAD:index.html'], capture_output=True, text=True).stdout

OLD_RENDER = io.open('tools/_b363_old_render.txt', encoding='utf-8').read().rstrip('\n')
NEW_RENDER = io.open('tools/_b363_new_render.txt', encoding='utf-8').read().rstrip('\n')
OLD_HTML = io.open('tools/_b363_old_html.txt', encoding='utf-8').read().rstrip('\n')
NEW_HTML = ('<button type="button" id="nx-groupip-btn" onclick="nxToggleGroupIp()" '
            'title="Группировать записи реестра по IP: устройства с одним IP показываем как одного пользователя со списком устройств" '
            'class="px-2.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 text-[10px] font-bold transition mr-1.5"></button>'
            + OLD_HTML)

HELPERS = """        // ============ b363: УСТРОЙСТВА И IP — «один IP = один пользователь» ============
        function nxDeviceId() { // устойчивый ID браузера: переживает перезаходы, уникален на устройство/профиль
            try {
                let id = LS.getItem('nx_device_id');
                if (!id) {
                    id = 'dv' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
                    LS.setItem('nx_device_id', id);
                }
                return id;
            } catch (e) { return ''; }
        }
        function nxDeviceLabel() { // человекочитаемый портрет устройства: ОС, браузер, форм-фактор, экран, железо
            try {
                const ua = String(navigator.userAgent || '');
                let os = 'неизвестная ОС';
                if (/iPhone|iPad|iPod/.test(ua)) { const v = ua.match(/OS (\\d+)[_.](\\d+)/); os = (/iPad/.test(ua) ? 'iPadOS ' : 'iOS ') + (v ? v[1] + '.' + v[2] : ''); }
                else if (/Android/.test(ua)) { const v = ua.match(/Android (\\d+(\\.\\d+)?)/); os = 'Android ' + (v ? v[1] : ''); }
                else if (/Windows NT 10/.test(ua)) os = 'Windows 10/11';
                else if (/Windows/.test(ua)) os = 'Windows';
                else if (/Mac OS X/.test(ua)) { const v = ua.match(/Mac OS X (\\d+)[_.](\\d+)/); os = 'macOS ' + (v ? v[1] + '.' + v[2] : ''); }
                else if (/CrOS/.test(ua)) os = 'ChromeOS';
                else if (/Linux/.test(ua)) os = 'Linux';
                let br = '';
                if (/Telegram/i.test(ua)) br = 'Telegram';
                else if (/YaBrowser/i.test(ua)) br = 'Яндекс';
                else if (/Edg\\//i.test(ua)) br = 'Edge';
                else if (/OPR\\//i.test(ua)) br = 'Opera';
                else if (/Firefox\\//i.test(ua)) br = 'Firefox';
                else if (/Chrome\\//i.test(ua)) br = 'Chrome';
                else if (/Safari\\//i.test(ua)) br = 'Safari';
                const tab = /iPad|Tablet|(Android(?!.*Mobile))/i.test(ua);
                const mob = /Mobile|iPhone|iPod|Android.*Mobile/i.test(ua);
                const form = tab ? 'планшет' : (mob ? 'телефон' : 'ПК');
                const scr = (screen.width || 0) + '×' + (screen.height || 0) + '@' + (Math.round((window.devicePixelRatio || 1) * 100) / 100) + 'x';
                const hw = [(navigator.hardwareConcurrency ? navigator.hardwareConcurrency + ' яд.' : ''), (navigator.deviceMemory ? navigator.deviceMemory + ' ГБ' : '')].filter(Boolean).join(', ');
                return [os, br, form, scr, hw].filter(Boolean).join(' · ');
            } catch (e) { return ''; }
        }
        function nxDvIcon(dev) { // иконка по форм-фактору из строки устройства
            const s = String(dev || '');
            if (s.indexOf('планшет') >= 0) return 'fa-tablet-screen-button';
            if (s.indexOf('телефон') >= 0) return 'fa-mobile-screen';
            return 'fa-desktop';
        }
        let nxIpFetch = 0;
        function nxPublicIp() { // публичный IP: не чаще раза в 6 часов, кэш в LS; '' если сервисы недоступны
            try {
                const raw = String(LS.getItem('nx_pub_ip') || '');
                const at = parseInt(LS.getItem('nx_pub_ip_at') || '0', 10) || 0;
                if (raw && Date.now() - at < 6 * 3600000) return raw;
                const failAt = parseInt(LS.getItem('nx_pub_ip_fail') || '0', 10) || 0;
                if (!raw && Date.now() - failAt < 600000) return ''; // не долбим сервисы после неудачи
                if (!nxIpFetch) {
                    nxIpFetch = 1;
                    const urls = ['https://api.ipify.org?format=json', 'https://api64.ipify.org?format=json', 'https://ifconfig.co/json'];
                    const tryOne = i => {
                        if (i >= urls.length) { nxIpFetch = 0; try { LS.setItem('nx_pub_ip_fail', String(Date.now())); } catch (e) {} return; }
                        fetch(urls[i], { cache: 'no-store' }).then(r => (r.ok ? r.json() : Promise.reject(new Error('http ' + r.status))))
                            .then(j => {
                                nxIpFetch = 0;
                                const ip = String((j && (j.ip || j.ip_addr)) || '').slice(0, 45);
                                if (ip) { try { LS.setItem('nx_pub_ip', ip); LS.setItem('nx_pub_ip_at', String(Date.now())); } catch (e) {} }
                            })
                            .catch(() => tryOne(i + 1));
                    };
                    tryOne(0);
                }
                return raw; // первый ответ придёт в фоне: подхватится следующим heartbeat (30 с)
            } catch (e) { return ''; }
        }
"""

GROUPFNS = """        function statsGroupList(ids) { return String(ids || '').split(',').filter(Boolean); }
        function statsZeroGroup(ids, btn) { // b363: обнулить все устройства одного пользователя
            const list = statsGroupList(ids);
            statsConfirm(btn, 'Обнулить баланс на всех ' + list.length + ' устройствах?', () => {
                if (statsAdminGuard()) return;
                const t = Date.now();
                list.forEach(cid => {
                    siteStats.z[cid] = t; siteStatsSave();
                    if (cid === JACKPOT_CID) { try { LS.setItem('nexus_stats_zero_ack', String(t)); } catch (e) {} state.coins = 0; saveState(); updateCoinDisplay(); }
                });
                try { jpSyncNow(); } catch (e) {}
                statsRender();
                showToast('💸 Обнулено устройств: ' + list.length + ' — после синхронизации у игроков будет 0', 'success');
            });
        }
        function statsBlockGroup(ids, on, btn) { // b363: блок/разблок всех устройств пользователя
            const list = statsGroupList(ids);
            statsConfirm(btn, on ? 'Заблокировать все ' + list.length + ' устройства?' : 'Разблокировать все ' + list.length + ' устройства?', () => {
                if (statsAdminGuard()) return;
                list.forEach(cid => {
                    siteStats.b[cid] = { on: on ? 1 : 0, at: Date.now() };
                    if (on) siteStats.z[cid] = Date.now(); // блокировка обнуляет баланс
                });
                siteStatsSave();
                try { jpSyncNow(); } catch (e) {}
                statsRender();
                showToast(on ? '🚫 Заблокировано устройств: ' + list.length : '✅ Разблокировано устройств: ' + list.length, on ? 'info' : 'success');
            });
        }
        function statsDeleteGroup(ids, btn) { // b363: удалить пользователя со всеми устройствами
            const list = statsGroupList(ids);
            statsConfirm(btn, 'Удалить пользователя со всеми ' + list.length + ' устройствами?', () => {
                if (statsAdminGuard()) return;
                list.forEach(cid => {
                    siteStats.b[cid] = { on: 1, del: 1, at: Date.now() };
                    siteStats.z[cid] = Date.now();
                    delete siteStats.p[cid];
                });
                siteStatsSave();
                try { jpSyncNow(); } catch (e) {}
                statsRender();
                showToast('🗑 Удалено устройств: ' + list.length + ' — балансы обнулены, доступ отключён', 'info');
            });
        }
        function nxStatsGroupOn() { try { return LS.getItem('nx_stats_group_ip') !== '0'; } catch (e) { return true; } }
        function nxToggleGroupIp() {
            try { LS.setItem('nx_stats_group_ip', nxStatsGroupOn() ? '0' : '1'); } catch (e) {}
            try { window.__nxStatsSig = ''; statsRender(); } catch (e) {}
        }
        function nxGroupIpLabel() {
            const b = document.getElementById('nx-groupip-btn');
            if (!b) return;
            const on = nxStatsGroupOn();
            b.innerHTML = '<i class="fa-solid fa-network-wired mr-1"></i>Один IP = 1 пользователь: ' + (on ? 'вкл' : 'выкл');
            b.title = on ? 'Записи с одним IP показываются одной карточкой со списком устройств' : 'Группировка выключена: каждое устройство отдельной строкой';
        }
"""

APP_EDITS = [
    ('b363-counters',
     "            const chip = (ic, col, lab, val, ttl) => '<div class=\"rounded-xl border border-slate-800 bg-slate-950/60 px-2.5 py-2 min-w-0\"'",
     "            // b363: пользователи — сгруппированные по IP записи; устройства — сами записи\n"
     "            const nxDevTotal = plist.length;\n"
     "            const nxUserTotal = (function () { const m = {}; plist.forEach(e => { const k = e.ip ? 'ip:' + e.ip : (e.did ? 'dev:' + e.did : 'cid:' + e.cid); m[k] = 1; }); return Object.keys(m).length; })();\n"
     "            const chip = (ic, col, lab, val, ttl) => '<div class=\"rounded-xl border border-slate-800 bg-slate-950/60 px-2.5 py-2 min-w-0\"'"),
    ('b363-users-chip',
     "chip('fa-users', 'text-sky-400', 'Игроков', String(plist.length)) +",
     "chip('fa-users', 'text-sky-400', 'Пользователей · устройств', nxUserTotal + ' · ' + nxDevTotal, 'b363: записи с одним IP считаются одним пользователем; второе число — устройства (отдельные браузеры/телефоны)') +"),
    ('b363-norm',
     "                won: Math.max(0, Math.floor(e.won) || 0),\n                at: Math.floor(e.at) || 0,",
     "                won: Math.max(0, Math.floor(e.won) || 0),\n                at: Math.floor(e.at) || 0,\n"
     "                ip: String(e.ip || '').slice(0, 45),   // b363: публичный IP устройства\n"
     "                dev: String(e.dev || '').slice(0, 90), // b363: ОС/браузер/форм-фактор/экран\n"
     "                did: String(e.did || '').slice(0, 24), // b363: устойчивый ID браузера"),
    ('b363-self',
     "                e.at = Date.now();\n                siteStats.p[JACKPOT_CID] = e;",
     "                e.did = nxDeviceId();    // b363: устойчивый ID устройства\n"
     "                e.dev = nxDeviceLabel(); // b363: портрет устройства для панели\n"
     "                e.ip = nxPublicIp();     // b363: IP из кэша, первый запрос идёт фоном\n"
     "                e.at = Date.now();\n                siteStats.p[JACKPOT_CID] = e;"),
    ('b363-doc',
     "p[e.cid] = { n: e.n, bal: e.bal, op: e.op, jp: e.jp, fed: e.fed, won: e.won, at: e.at, pk: e.pk, alb: e.alb }; }); // b278: + альбомы",
     "p[e.cid] = { n: e.n, bal: e.bal, op: e.op, jp: e.jp, fed: e.fed, won: e.won, at: e.at, pk: e.pk, alb: e.alb, ip: e.ip, dev: e.dev, did: e.did }; }); // b278: + альбомы; b363: + IP/устройство/ID"),
    ('b363-helpers',
     "        function siteStatsSelfUpdate() {",
     HELPERS + "        function siteStatsSelfUpdate() {"),
    ('b363-groupfns',
     "        function statsRenderIfVisible() {",
     GROUPFNS + "        function statsRenderIfVisible() {"),
    ('b363-render', OLD_RENDER, NEW_RENDER),
]

QR_EDITS = []  # qr-transfer не трогаем
MONO_EDITS = [
    ('b363-html-btn', OLD_HTML, NEW_HTML),
]


MODULE_B364 = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_b364_module.txt'), encoding='utf-8').read().rstrip('\n')
UI_B364 = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_b364_ui.txt'), encoding='utf-8').read().rstrip('\n')

OLD_AGG = """                g.bal = g.members.reduce((s, m) => s + (m.bal || 0), 0);
                g.op = g.members.reduce((s, m) => s + (m.op || 0), 0);
                g.jp = g.members.reduce((s, m) => s + (m.jp || 0), 0);
                g.fed = g.members.reduce((s, m) => s + (m.fed || 0), 0);"""
NEW_AGG = """                // b364: устройства, связанные профилем, держат ОДИН баланс и общие
                // счётчики (зеркало), поэтому берём максимум; без синхронизации
                // балансы устройств независимы — тогда сумма.
                g.prof = g.members.map(m => m.prof || '').filter(Boolean)[0] || '';
                const agg = f => g.members.reduce((s, m) => (g.prof ? Math.max(s, m[f] || 0) : s + (m[f] || 0)), 0);
                g.bal = agg('bal');
                g.op = agg('op');
                g.jp = agg('jp');
                g.fed = agg('fed');"""
OLD_IPBADGE = "                        (g.ip ? badge('fa-location-dot', 'IP ' + cloudEsc(g.ip), 'text-sky-300', 'Все устройства ниже приходили с этого IP — считаем их одним пользователем') : badge('fa-location-dot', 'IP не сообщил', 'text-slate-600', 'Старый клиент или IP-сервис недоступен: группируем по ID устройства')) +"
PROF_BADGE = "                        (g.prof ? badge('fa-rotate', 'синхронизированы: ' + cloudEsc(g.prof), 'text-emerald-300', 'b364: эти устройства делят общий баланс и прогресс через облачный профиль') : '') +"
OLD_COINTITLE = "badge('fa-coins', fmtCoins(g.bal), 'text-amber-300', multi ? 'Сумма по всем устройствам этого пользователя' : '') +"
NEW_COINTITLE = "badge('fa-coins', fmtCoins(g.bal), 'text-amber-300', multi ? (g.prof ? 'Общий баланс: устройства синхронизированы профилем (b364)' : 'Сумма по устройствам пользователя (без синхронизации)') : '') +"
OLD_UICARD = """            <div class="bg-slate-900/80 p-3 sm:p-4 rounded-2xl border border-slate-800 space-y-2.5">
                <h3 class="text-sm font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-users text-sky-400"></i>"""

APP_EDITS += [
    ('b364-module', "        function nxStatsGroupOn() {", MODULE_B364 + "\n        function nxStatsGroupOn() {"),
    ('b364-norm',
     "                did: String(e.did || '').slice(0, 24), // b363: устойчивый ID браузера",
     "                did: String(e.did || '').slice(0, 24), // b363: устойчивый ID браузера\n                prof: String(e.prof || '').slice(0, 24), // b364: под каким профилем синхронизируется устройство"),
    ('b364-self',
     "                e.ip = nxPublicIp();     // b363: IP из кэша, первый запрос идёт фоном",
     "                e.ip = nxPublicIp();     // b363: IP из кэша, первый запрос идёт фоном\n                e.prof = (function () { try { const c = profCode(); if (c) return 'код ' + c; if (profIpAuto() && nxPublicIp()) return 'IP-авто'; } catch (e) {} return ''; })(); // b364"),
    ('b364-doc',
     "alb: e.alb, ip: e.ip, dev: e.dev, did: e.did }; }); // b278: + альбомы; b363: + IP/устройство/ID",
     "alb: e.alb, ip: e.ip, dev: e.dev, did: e.did, prof: e.prof }; }); // b278: + альбомы; b363: + IP/устройство; b364: + профиль синхронизации"),
    ('b364-agg', OLD_AGG, NEW_AGG),
    ('b364-profbadge', OLD_IPBADGE, OLD_IPBADGE + "\n" + PROF_BADGE),
    ('b364-cointitle', OLD_COINTITLE, NEW_COINTITLE),
    ('b364-init', "            cloudInit();", "            cloudInit();\n            try { profInit(); } catch (e) {} // b364: облачный профиль между устройствами"),
]
MONO_EDITS += [
    ('b364-ui', OLD_UICARD, UI_B364 + "\n" + OLD_UICARD),
]

# b363 уже в HEAD — оставляем только новые правки (b364)
APP_EDITS = [e for e in APP_EDITS if e[0].startswith('b364')]
MONO_EDITS = [e for e in MONO_EDITS if e[0].startswith('b364')]

for lbl, o, n in APP_EDITS + QR_EDITS:
    assert app_head.count(o) == 1, '%s: в базе app.js %d вхождений (нужно 1)' % (lbl, app_head.count(o))
for lbl, o, n in MONO_EDITS:
    assert mono_head_html.count(o) == 1, '%s: в базе index.html %d вхождений (нужно 1)' % (lbl, mono_head_html.count(o))
print('проверено: все old-блоки уникальны в базе HEAD')

HEADER = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Незакоммиченные правки в виде old -> new (сейчас: b363 — группировка
пользователей по IP и определение устройств в панели «Пользователи»).

  python3 tools/apply_fix.py check      # показать, что ляжет (ничего не пишет)
  python3 tools/apply_fix.py assets     # применить к assets/app.js (+ qr-transfer, если есть правки)
  python3 tools/apply_fix.py monolith   # применить к tools/source-index.html (включая MONO_EDITS)

После монолита: python3 tools/sync_build_blocks.py && python3 tools/build.py --no-media
Пересобирается скриптом tools/_regen_apply_fix.py.
"""
import sys, os, io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

'''

FOOTER = '''

def apply(text, edits, log):
    bad = 0
    for label, old, new in edits:
        c = text.count(old)
        if c == 1:
            text = text.replace(old, new, 1)
            log.append("  · %s: применено" % label)
        elif c == 0 and new in text:
            log.append("  · %s: уже в файле" % label)
        else:
            log.append("  ! %s: найдено %d вхождений old — правка НЕ применена" % (label, c))
            bad += 1
    return text, bad


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "check"
    log, total_bad = [], 0
    if target in ("assets", "check"):
        for name, edits in (("app.js", APP_EDITS), ("qr-transfer.js", QR_EDITS)):
            if not edits:
                continue
            p = os.path.join(ROOT, "assets", name)
            t = io.open(p, encoding="utf-8").read()
            t2, bad = apply(t, edits, log)
            total_bad += bad
            print("assets/%s:" % name); print("\\n".join(log)); log = []
            if target == "assets" and t2 != t:
                if bad:
                    print("  ЕСТЬ НЕПРИМЕНЁННЫЕ ПРАВКИ — файл не записан"); continue
                io.open(p, "w", encoding="utf-8", newline="").write(t2)
                print("  записано")
    if target == "monolith":
        p = os.path.join(ROOT, "tools", "source-index.html")
        t = io.open(p, encoding="utf-8").read()   # CRLF -> LF при чтении
        t2, bad = apply(t, APP_EDITS + QR_EDITS + MONO_EDITS, log)
        total_bad += bad
        print("tools/source-index.html:"); print("\\n".join(log))
        if bad:
            print("ЕСТЬ НЕПРИМЕНЁННЫЕ ПРАВКИ — монолит не записан"); return 1
        if t2 != t:
            io.open(p, "w", encoding="utf-8", newline="\\r\\n").write(t2)
            print("  записано (%+d строк)" % (t2.count("\\n") - t.count("\\n")))
    if not (APP_EDITS or QR_EDITS or MONO_EDITS):
        print("список правок пуст: всё уже в репозитории")
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
'''


def dump(name, edits):
    out = name + ' = [\n'
    for lbl, o, n in edits:
        out += '    (%s,\n     %s,\n     %s),\n' % (repr(lbl), repr(o), repr(n))
    return out + ']\n'


src = HEADER + dump('APP_EDITS', APP_EDITS) + '\n' + dump('QR_EDITS', QR_EDITS) + '\n' + dump('MONO_EDITS', MONO_EDITS) + FOOTER
ast.parse(src)
io.open(AP, 'w', encoding='utf-8', newline='').write(src)
print('apply_fix.py пересобран под b363:', len(src), 'байт; app-блоков', len(APP_EDITS), ', mono-блоков', len(MONO_EDITS))
