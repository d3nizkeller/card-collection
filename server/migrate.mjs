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
 *
 *   --room <код>           комната СЕРВЕРА (заголовок x-nx-room), по умолчанию 'site'
 *   --catalog-room <код>   комната КАТАЛОГА в textdb (nexus-tcg-room-<код>).
 *                          По умолчанию берётся из assets/app.js → CLOUD_DEFAULT_ROOM,
 *                          то есть ровно та комната, которую использует сайт.
 *   --allow-empty          отправить миграцию, даже если найдено 0 игроков и 0 лотов
 *                          (без него скрипт отказывается — иначе банк затрётся нулями)
 *
 * b465: исправлено чтение textdb.dev (двойной JSON при Accept: application/json —
 * из-за него переносилось 0 игроков) и адрес каталога (строился из --room='site'
 * вместо настоящей комнаты игры — из-за него не переносились паки, карты и
 * учётка Студии).
 */

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const TEXTDB_JP = 'https://textdb.dev/api/data/nexus-tcg-jackpot-v3';
const TEXTDB_ROOM = 'https://textdb.dev/api/data/nexus-tcg-room-';

function arg(name, dflt) {
    const i = process.argv.indexOf('--' + name);
    if (i > 0 && process.argv[i + 1] && process.argv[i + 1].indexOf('--') !== 0) return process.argv[i + 1];
    return dflt;
}
function has(name) { return process.argv.indexOf('--' + name) >= 0; }
function warn(t) { console.log('   ⚠️  ' + t); }

/* b465. КОМНАТА КАТАЛОГА ≠ КОМНАТА СЕРВЕРА.
 *
 * --room задаёт комнату сервера (заголовок x-nx-room; 'site' = общий банк сайта).
 * Каталог паков и карт лежит в ОТДЕЛЬНОМ документе textdb с кодом комнаты игры —
 * это CLOUD_DEFAULT_ROOM из assets/app.js (сейчас '7j8uytui'), а вовсе не 'site'.
 * Раньше адрес каталога строился из --room, поэтому скрипт по умолчанию читал
 * пустой nexus-tcg-room-site и переносил игру БЕЗ паков и карт — сервер после
 * этого не мог вскрывать паки, а Студия оставалась без учётки.
 * Теперь код комнаты берётся из assets/app.js ровно так же, как его берёт сайт. */
function detectCatalogRoom() {
    const explicit = String(arg('catalog-room', process.env.NX_CATALOG_ROOM || '')).trim();
    if (explicit) return explicit;
    try {
        const src = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        const m = src.match(/CLOUD_DEFAULT_ROOM\s*=\s*'([^']+)'/);
        if (m && m[1]) return m[1];
    } catch (e) { /* app.js недоступен — ниже запасной код */ }
    return '7j8uytui';
}
const CATALOG_ROOM = detectCatalogRoom();

const API = String(arg('api', process.env.NX_API || '')).replace(/\/+$/, '');
const ROOM = String(arg('room', process.env.NX_ROOM || 'site'));
const JP_URL = String(arg('jp-url', process.env.NX_JP_URL || TEXTDB_JP));
const ROOM_URL = String(arg('room-url', process.env.NX_ROOM_URL || (TEXTDB_ROOM + CATALOG_ROOM)));
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

/* b465: textdb.dev хранит документ как ТЕКСТ и на заголовок `Accept:
 * application/json` отвечает JSON-строкой внутри JSON-строки:
 *     "{\"jp\":{…}}"   ← тело ответа
 * Один JSON.parse даёт из этого строку, а не объект, поэтому `doc.jp`
 * оказывался undefined и миграция молча переносила НОЛЬ игроков, нулевой банк
 * и пустой зал славы, отчитываясь «✅ готово».
 *
 * Чиним с двух сторон: (1) не шлём Accept: application/json — тогда textdb
 * отдаёт чистый текст, как его читает сама игра в jpFetch(); (2) на всякий
 * случай распаковываем строку повторно, если после parse получилась строка.
 * Для Firebase (.json) и для нашего воркера оба варианта одинаково работают. */
async function getJson(url, label) {
    try {
        const r = await fetch(url, { cache: 'no-store' });
        if (!r.ok) { console.error('  ⚠️  ' + label + ': HTTP ' + r.status + ' (' + url + ')'); return null; }
        const txt = await r.text();
        if (!txt.trim()) { console.log('  ·  ' + label + ': документ пустой'); return null; }
        let j;
        try { j = JSON.parse(txt); } catch (e) { console.error('  ⚠️  ' + label + ': не JSON'); return null; }
        for (let i = 0; i < 3 && typeof j === 'string'; i++) {   // двойная (и тройная) упаковка textdb
            try { j = JSON.parse(j); } catch (e) { console.error('  ⚠️  ' + label + ': не JSON после распаковки'); return null; }
        }
        if (!j || typeof j !== 'object' || Array.isArray(j)) {
            console.error('  ⚠️  ' + label + ': ожидался объект, получено ' + typeof j);
            return null;
        }
        return j;
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

    /* b465: страховка от «тихой пустой миграции». Если документ прочитался, но
     * в нём нет ни одного игрока, ни одной записи зала славы и нет каталога —
     * почти наверняка прочитан не тот адрес (или документ действительно пуст).
     * Отправлять такое на сервер нельзя: /api/migrate затрёт банк нулями. */
    const looksEmpty = !players.length && !hall && !lots && (!catalog || (!catalog.packs.length && !catalog.cards.length));
    if (looksEmpty && !has('allow-empty')) {
        console.error('\n❌ Ничего не найдено: 0 игроков, 0 записей зала славы, 0 лотов, каталога нет.');
        console.error('   Отказываюсь отправлять пустоту — иначе серверный банк обнулится.');
        console.error('   Проверьте адреса:');
        console.error('     банк/реестр: ' + JP_URL);
        console.error('     каталог:     ' + ROOM_URL + '   (комната игры: ' + CATALOG_ROOM + ')');
        console.error('   Код комнаты игры лежит в assets/app.js → CLOUD_DEFAULT_ROOM.');
        console.error('   Задать вручную:  --catalog-room <код>   или   --jp-url/--room-url <адрес>');
        console.error('   Если вы уверены, что данных действительно нет: добавьте --allow-empty');
        process.exit(3);
    }
    if (doc && !players.length) warn('в реестре 0 игроков — балансы не перенесутся');

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
