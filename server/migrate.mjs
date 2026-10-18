#!/usr/bin/env node
/* server/migrate.mjs — перенос ТЕКУЩИХ данных игроков на сервер (b463)
 *
 * Зачем
 * ─────
 * Общий банк, зал славы, реестр игроков (с их балансами), блокировки, лоты
 * биржи и каталог комнаты сейчас лежат в общем облачном документе:
 *   • простое хранилище  → https://textdb.dev/api/data/nexus-tcg-jackpot-v3
 *   • свой Firebase      → https://<проект>…/nexus-jackpot-v3.json
 * Каталог комнаты и учётка Студии — в документе комнаты:
 *   • https://textdb.dev/api/data/nexus-tcg-room-<код>
 *   • https://<проект>…/nexus-rooms/<код>.json
 *
 * Скрипт читает оба документа и отправляет их на воркер в /api/migrate.
 * Сервер переносит:
 *   банк       floor + Σвзносов − Σвыплат (разряды cid#N складываются),
 *   балансы    bal каждого игрока из реестра — как есть,
 *   имена/статистику/IP/устройства,
 *   блокировки (b) и обнуления (z),
 *   зал славы  (последние 40 срывов),
 *   настройки джекпота (jpc),
 *   лоты биржи и неоплаченные квитанции,
 *   каталог    паки и карты с редкостями (нужны серверу для честных вскрытий),
 *   учётку Студии — прежним хэшем, чтобы владелец вошёл СВОИМ паролем
 *              (сервер при первом входе переложит его в PBKDF2).
 *
 * Ничего не теряется: повторный запуск безопасен — игрок, который уже играл
 * на сервере, не перезаписывается (если не указан --force).
 *
 * Запуск
 * ──────
 *   node server/migrate.mjs --api https://nexus-card-api.<аккаунт>.workers.dev \
 *        --login <логин Студии> --pass <пароль Студии>
 *
 *   # первый прогон, когда учётки Студии на сервере ещё нет:
 *   node server/migrate.mjs --api https://… --setup-login owner --setup-pass 'длинный-пароль' \
 *        [--setup-key <NX_SETUP_KEY>]
 *
 *   # свои адреса документов:
 *   node server/migrate.mjs --api https://… --jp-url https://<проект>.firebaseio.com/nexus-jackpot-v3.json \
 *        --room-url https://<проект>.firebaseio.com/nexus-rooms/<код>.json --room <код>
 *
 *   --dry-run   только показать, что нашлось (ничего не отправлять)
 *   --force     перезаписать балансы даже у тех, кто уже играл на сервере
 *   --json      напечатать сырой отчёт сервера
 */

import process from 'node:process';

const TEXTDB_JP = 'https://textdb.dev/api/data/nexus-tcg-jackpot-v3';
const TEXTDB_ROOM = 'https://textdb.dev/api/data/nexus-tcg-room-';

function arg(name, dflt) {
    const i = process.argv.indexOf('--' + name);
    if (i > 0 && process.argv[i + 1] && process.argv[i + 1].indexOf('--') !== 0) return process.argv[i + 1];
    return dflt;
}
function has(name) { return process.argv.indexOf('--' + name) >= 0; }

const API = String(arg('api', process.env.NX_API || '')).replace(/\/+$/, '');
const ROOM = String(arg('room', process.env.NX_ROOM || 'site'));
const JP_URL = String(arg('jp-url', process.env.NX_JP_URL || TEXTDB_JP));
const ROOM_URL = String(arg('room-url', process.env.NX_ROOM_URL || (TEXTDB_ROOM + ROOM)));
const LOGIN = arg('login', process.env.NX_LOGIN || '');
const PASS = arg('pass', process.env.NX_PASS || '');
const SETUP_LOGIN = arg('setup-login', '');
const SETUP_PASS = arg('setup-pass', '');
const SETUP_KEY = arg('setup-key', process.env.NX_SETUP_KEY || '');
const DRY = has('dry-run');
const FORCE = has('force');
const RAW = has('json');

if (!API) {
    console.error('Нужен адрес API:  --api https://nexus-card-api.<аккаунт>.workers.dev');
    process.exit(2);
}

async function getJson(url, label) {
    try {
        const r = await fetch(url, { headers: { accept: 'application/json' }, cache: 'no-store' });
        if (!r.ok) { console.error('  ⚠️  ' + label + ': HTTP ' + r.status + ' (' + url + ')'); return null; }
        const txt = await r.text();
        if (!txt.trim()) { console.log('  ·  ' + label + ': документ пустой'); return null; }
        try { return JSON.parse(txt); } catch (e) { console.error('  ⚠️  ' + label + ': не JSON'); return null; }
    } catch (e) {
        console.error('  ⚠️  ' + label + ': ' + (e && e.message));
        return null;
    }
}

async function post(path, body, adminToken) {
    const headers = { 'content-type': 'application/json', 'x-nx-room': ROOM };
    if (adminToken) headers['x-nx-admin'] = adminToken;
    const r = await fetch(API + path, { method: 'POST', headers, body: JSON.stringify(body) });
    let j = null;
    try { j = await r.json(); } catch (e) { j = { ok: false, error: 'bad_response', status: r.status }; }
    j.status = r.status;
    return j;
}

function fmt(n) {
    const v = Number(n) || 0;
    if (v >= 1e15) return (v / 1e15).toFixed(2).replace(/\.?0+$/, '') + 'q';
    if (v >= 1e12) return (v / 1e12).toFixed(2).replace(/\.?0+$/, '') + 't';
    if (v >= 1e9) return (v / 1e9).toFixed(2).replace(/\.?0+$/, '') + 'b';
    if (v >= 1e6) return (v / 1e6).toFixed(2).replace(/\.?0+$/, '') + 'm';
    if (v >= 1e3) return (v / 1e3).toFixed(1).replace(/\.0$/, '') + 'k';
    return String(v);
}

async function main() {
    console.log('═══ Перенос данных «Коллекционера карт» на сервер (b463) ═══');
    console.log('  API:      ' + API);
    console.log('  комната:  ' + ROOM);
    console.log('  банк/реестр: ' + JP_URL);
    console.log('  каталог:  ' + ROOM_URL);
    if (DRY) console.log('  режим:    --dry-run (ничего не отправляем)');
    console.log('');

    const health = await getJson(API + '/api/health', 'проверка API');
    if (!health || !health.ok) {
        console.error('❌ API не отвечает. Задеплойте воркер (server/README.md) и повторите.');
        process.exit(1);
    }
    if (!health.secret) console.log('  ⚠️  на воркере не задан NX_SECRET — токены не выдаются');

    console.log('1. Читаю текущие документы…');
    const doc = await getJson(JP_URL, 'общий документ (банк/реестр)');
    const roomDoc = await getJson(ROOM_URL, 'комната (каталог)');

    const jp = (doc && (doc.jp || doc)) || {};
    const st = (doc && doc.st) || {};
    const mk = (doc && doc.mk) || {};
    const players = Object.keys(st.p || {});
    const sumBal = players.reduce((s, k) => s + (Number((st.p[k] || {}).bal) || 0), 0);
    const blocked = Object.keys(st.b || {}).filter(k => (st.b[k] || {}).on).length;
    const hall = Array.isArray(jp.hall) ? jp.hall.length : 0;
    const lots = Array.isArray(mk.lots) ? mk.lots.length : 0;

    console.log('   игроков в реестре: ' + players.length + ' (сумма балансов ' + fmt(sumBal) + ')');
    console.log('   заблокировано: ' + blocked + ', обнулено: ' + Object.keys(st.z || {}).length);
    console.log('   записей в зале славы: ' + hall + ', лотов биржи: ' + lots);
    console.log('   взносов в банк (Σled): ' + fmt(Object.values(jp.led || {}).reduce((s, v) => s + (Number(v) || 0), 0)) +
        ', выплат (Σwon): ' + fmt(Object.values(jp.won || {}).reduce((s, v) => s + (Number(v) || 0), 0)));

    const catalog = roomDoc ? {
        packs: Array.isArray(roomDoc.packs) ? roomDoc.packs : [],
        cards: Array.isArray(roomDoc.cards) ? roomDoc.cards : []
    } : null;
    if (catalog) console.log('   каталог комнаты: паков ' + catalog.packs.length + ', карт ' + catalog.cards.length);
    else console.log('   ⚠️  каталог комнаты не найден — сервер не сможет вскрывать паки, опубликуйте его из Студии');

    const legacyAuth = (roomDoc && roomDoc.auth && roomDoc.auth.login && roomDoc.auth.hash) ? roomDoc.auth : null;
    console.log('   учётка Студии в документе: ' + (legacyAuth ? legacyAuth.login + ' (перенесу прежним хэшем)' : 'не найдена'));

    if (DRY) { console.log('\n--dry-run: ничего не отправлено.'); return; }

    console.log('\n2. Получаю админ-доступ на сервере…');
    let adminToken = '';
    if (SETUP_LOGIN && SETUP_PASS) {
        const s = await post('/api/studio/setup', { login: SETUP_LOGIN, pass: SETUP_PASS, setupKey: SETUP_KEY });
        if (s.ok && s.adminToken) { adminToken = s.adminToken; console.log('   создана учётка Студии: ' + SETUP_LOGIN + (s.first ? ' (первая)' : '')); }
        else console.log('   ·  учётка не создана (' + (s.error || 'уже существует') + ') — пробую войти');
    }
    if (!adminToken) {
        const login = LOGIN || SETUP_LOGIN || (legacyAuth && legacyAuth.login) || '';
        const pass = PASS || SETUP_PASS || '';
        if (!pass) {
            console.error('❌ Нужен пароль Студии: --login <логин> --pass <пароль>');
            console.error('   (или создайте учётку: --setup-login owner --setup-pass "…" [--setup-key …])');
            process.exit(2);
        }
        const l = await post('/api/studio/login', { login: login, pass: pass });
        if (!l.ok || !l.adminToken) {
            console.error('❌ Сервер не принял пароль: ' + (l.error || 'HTTP ' + l.status));
            console.error('   Если учётка ещё не перенесена, сначала создайте её: --setup-login/--setup-pass');
            process.exit(1);
        }
        adminToken = l.adminToken;
        console.log('   вход выполнен: ' + login + (l.upgraded ? ' (пароль переложен в PBKDF2)' : ''));
    }

    console.log('\n3. Отправляю данные на сервер…');
    const res = await post('/api/migrate', { doc: doc || {}, catalog: catalog, legacyAuth: legacyAuth, force: FORCE }, adminToken);
    if (!res.ok) {
        console.error('❌ Миграция отклонена: ' + (res.error || 'HTTP ' + res.status));
        process.exit(1);
    }
    const m = res.migrate || {};
    console.log('   ✅ перенесено игроков: ' + (m.players || 0) + ' (пропущено, уже играли: ' + (m.skipped || 0) + ')');
    console.log('   ✅ заблокировано: ' + (m.blocked || 0) + ', обнулено: ' + (m.zeroed || 0));
    console.log('   ✅ зал славы: ' + (m.hall || 0) + ' записей, лоты биржи: ' + (m.lots || 0) + ', квитанции: ' + (m.ledger || 0));
    if (m.bank) console.log('   ✅ банк сайта: ' + fmt(m.bank.pot) + ' (пол ' + fmt(m.bank.floor) + ', Σвзносов ' + fmt(m.bank.fed) + ', Σвыплат ' + fmt(m.bank.won) + ')');
    if (m.catalog) console.log('   ✅ каталог: паков ' + m.catalog.packs + ', карт ' + m.catalog.cards);
    if (m.studioAuth) console.log('   ✅ учётка Студии перенесена: ' + m.studioAuth + ' — вход прежним паролем');
    if (RAW) console.log('\n' + JSON.stringify(res, null, 2));

    console.log('\n4. Проверяю витрину…');
    const pub = await getJson(API + '/api/public?room=' + encodeURIComponent(ROOM), 'публичное состояние');
    if (pub && pub.ok) {
        console.log('   банк на сервере: ' + fmt(pub.bank.pot) + ', игроков: ' + pub.players + ', каталог: ' + (pub.hasCatalog ? 'есть' : 'НЕТ'));
        console.log('   топ-3 джекпотов: ' + ((pub.top || []).map(t => t.n + ' +' + fmt(t.a)).join(', ') || 'пусто'));
    }

    console.log('\n═══ Готово ═══');
    console.log('Дальше:');
    console.log('  1) в игре откройте Студию → «Облако» и укажите адрес API');
    console.log('     (или задайте его заранее: localStorage.setItem("nx_api_url", "' + API + '"))');
    console.log('  2) войдите в Студию своим паролем — сервер выдаст права');
    console.log('  3) нажмите «Опубликовать» в Студии: каталог комнаты уйдёт и на сервер');
}

main().catch(e => { console.error('❌ ' + ((e && e.stack) || e)); process.exit(1); });
