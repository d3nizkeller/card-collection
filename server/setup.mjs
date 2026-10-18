#!/usr/bin/env node
/* server/setup.mjs — «ОДНА КОМАНДА» вместо шести (b465)
 *
 * Зачем
 * ─────
 * Раньше, чтобы поднять сервер, нужно было руками: wrangler login → d1 create →
 * скопировать database_id в wrangler.toml → openssl rand → secret put ×2 →
 * deploy → migrate.mjs с длинными аргументами → вписать адрес в index.html.
 * Восемь шагов, в каждом можно ошибиться. Этот скрипт делает всё сам.
 *
 * Запуск
 * ──────
 *   npm run nexus                      ← из корня репозитория, интерактивно
 *   node server/setup.mjs              ← то же самое
 *
 * Без вопросов (например, когда токен уже есть в переменных окружения):
 *   node server/setup.mjs --token <CF_API_TOKEN> [--account <ID>] \
 *        --studio-login owner --studio-pass 'пароль' [--skip-migrate] [--push]
 *
 * Что делает по шагам
 * ───────────────────
 *   1. проверяет Node ≥ 18 и ставит wrangler в server/worker, если его нет
 *   2. проверяет токен Cloudflare и находит ваш аккаунт
 *   3. включает поддомен workers.dev, если он ещё не включён
 *   4. создаёт базу D1 «nexus-bank» (или находит уже созданную)
 *   5. сам вписывает database_id в wrangler.toml
 *   6. сам генерирует NX_SECRET и NX_SETUP_KEY (openssl не нужен)
 *   7. деплоит воркер и загружает оба секрета
 *   8. проверяет /api/health — сервер жив, база d1, секрет задан
 *   9. переносит текущие данные игроков (запускает server/migrate.mjs)
 *  10. вписывает адрес API в index.html (window.__NX_API) — сайт сразу знает сервер
 *  11. сохраняет ключи в server/.nexus.local.json (файл в .gitignore)
 *  12. с --push — коммитит и пушит изменения index.html
 *
 * Скрипт идемпотентен: повторный запуск ничего не ломает и не дублирует.
 *
 * Безопасность
 * ────────────
 * NX_SECRET и NX_SETUP_KEY уходят в Cloudflare только через `wrangler secret`
 * и никогда не коммитятся. Локальная копия пишется в server/.nexus.local.json,
 * который добавлен в .gitignore.
 */

import { spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const WORKER = path.join(HERE, 'worker');
const WRANGLER_TOML = path.join(WORKER, 'wrangler.toml');
const INDEX_HTML = path.join(ROOT, 'index.html');
const STATE_FILE = path.join(HERE, '.nexus.local.json');
const CF = 'https://api.cloudflare.com/client/v4';
const DB_NAME = 'nexus-bank';
const WORKER_NAME = 'nexus-card-api';

/* ────────────────────────── мелочи вывода ────────────────────────── */

const C = process.stdout.isTTY
    ? { r: '\x1b[0m', b: '\x1b[1m', dim: '\x1b[2m', g: '\x1b[32m', y: '\x1b[33m', red: '\x1b[31m', c: '\x1b[36m' }
    : { r: '', b: '', dim: '', g: '', y: '', red: '', c: '' };

let STEP = 0;
const step = (t) => console.log(`\n${C.b}${C.c}[${++STEP}/12]${C.r}${C.b} ${t}${C.r}`);
const ok = (t) => console.log(`  ${C.g}✓${C.r} ${t}`);
const note = (t) => console.log(`  ${C.dim}${t}${C.r}`);
const warn = (t) => console.log(`  ${C.y}! ${t}${C.r}`);
function die(t, hint) {
    console.error(`\n${C.red}${C.b}✗ ${t}${C.r}`);
    if (hint) console.error(`${C.dim}${hint}${C.r}`);
    process.exit(1);
}

/* ────────────────────────── аргументы и ввод ────────────────────────── */

function arg(name, dflt) {
    const i = process.argv.indexOf('--' + name);
    if (i > 0 && process.argv[i + 1] && process.argv[i + 1].indexOf('--') !== 0) return process.argv[i + 1];
    return dflt;
}
const has = (name) => process.argv.indexOf('--' + name) >= 0;

let rl = null;
function ask(q, { dflt = '', secret = false, required = true } = {}) {
    if (!process.stdin.isTTY) return Promise.resolve(dflt);   // не-интерактивный запуск
    rl = rl || readline.createInterface({ input: process.stdin, output: process.stdout, terminal: true });
    return new Promise((res) => {
        const label = dflt ? `${q} ${C.dim}[${dflt}]${C.r}: ` : `${q}: `;
        const done = (a) => {
            a = String(a || '').trim();
            if (!a && dflt) a = dflt;
            if (!a && required) {
                console.log(`${C.y}  пусто — спрашиваю ещё раз${C.r}`);
                return ask(q, { dflt, secret, required }).then(res);
            }
            res(a);
        };
        if (!secret) return rl.question(label, done);
        // Пароль/токен: в raw-режиме терминал сам не повторяет ввод, это делает
        // readline через _writeToOutput. Глушим его — символы не видны вообще,
        // а приглашение печатаем сами. Так надёжнее, чем рисовать звёздочки.
        const orig = rl._writeToOutput;
        rl._writeToOutput = function () {};
        process.stdout.write(label);
        rl.question('', (a) => {
            rl._writeToOutput = orig;
            process.stdout.write('\n');
            rl._refreshLine();                 // вернуть строку ввода в нормальное состояние
            done(a);
        });
    });
}
const secretHex = (n = 32) => crypto.randomBytes(n).toString('hex');

/* ────────────────────────── Cloudflare API ────────────────────────── */

let TOKEN = '';
async function cf(p, { method = 'GET', body } = {}) {
    const r = await fetch(CF + p, {
        method,
        headers: { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json', 'User-Agent': 'nexus-setup/1.0' },
        body: body ? JSON.stringify(body) : undefined
    });
    let j = null;
    try { j = await r.json(); } catch { /* не JSON — вернём как есть */ }
    if (!r.ok || (j && j.success === false)) {
        const msg = (j && j.errors || []).map(e => `${e.code || ''} ${e.message || ''}`.trim()).join('; ') || `HTTP ${r.status}`;
        throw new Error(msg);
    }
    return j ? j.result : null;
}

/* ────────────────────────── wrangler ────────────────────────── */

function wranglerBin() {
    const exe = process.platform === 'win32' ? 'wrangler.cmd' : 'wrangler';
    const p = path.join(WORKER, 'node_modules', '.bin', exe);
    return fs.existsSync(p) ? p : null;
}
function runWrangler(args, { env = {}, input, quiet = false } = {}) {
    const bin = wranglerBin();
    const cmd = bin || (process.platform === 'win32' ? 'npx.cmd' : 'npx');
    const full = bin ? args : ['--yes', 'wrangler@3', ...args];
    const r = spawnSync(cmd, full, {
        cwd: WORKER,
        encoding: 'utf8',
        input,
        env: { ...process.env, CLOUDFLARE_API_TOKEN: TOKEN, CLOUDFLARE_ACCOUNT_ID: ACCOUNT_ID || process.env.CLOUDFLARE_ACCOUNT_ID || '', ...env },
        // ВАЖНО: перехватываем ОБА потока. С 'inherit' r.stdout === null, и тогда
        // из вывода деплоя нельзя достать адрес https://….workers.dev.
        stdio: ['pipe', 'pipe', 'pipe'],
        // на Windows .cmd-обёртки (wrangler.cmd / npx.cmd) запускаются только через shell
        shell: process.platform === 'win32',
        maxBuffer: 32 * 1024 * 1024
    });
    const out = `${r.stdout || ''}\n${r.stderr || ''}`;
    if (!quiet && out.trim()) console.log(out.replace(/^/gm, '    ').trimEnd());
    return { code: r.status ?? 1, out };
}

/* Адрес воркера: сначала из вывода wrangler deploy, потом из поддомена аккаунта. */
async function resolveWorkerUrl(deployOut) {
    const fromOut = (deployOut.match(/https:\/\/[a-z0-9-]+(?:\.[a-z0-9-]+)*\.workers\.dev/i) || [])[0];
    if (fromOut) return fromOut.replace(/\/+$/, '');
    try {
        const sd = await cf(`/accounts/${ACCOUNT_ID}/workers/subdomain`);
        const raw = String((sd && (sd.subdomain || sd.preapproved_subdomain)) || '');
        const prefix = raw.replace(/\.workers\.dev$/i, '');
        if (prefix) return `https://${WORKER_NAME}.${prefix}.workers.dev`;
    } catch { /* поддомен не читается — ниже ещё одна попытка */ }
    return '';
}

/* ────────────────────────── состояние ────────────────────────── */

let ACCOUNT_ID = '';
const STATE = fs.existsSync(STATE_FILE) ? JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')) : {};
function saveState(patch) {
    Object.assign(STATE, patch);
    fs.writeFileSync(STATE_FILE, JSON.stringify(STATE, null, 2), 'utf8');
    try { fs.chmodSync(STATE_FILE, 0o600); } catch { /* Windows */ }
}

/* ═══════════════════════════ ШАГИ ═══════════════════════════ */

async function main() {
    console.log(`${C.b}Сервер «Коллекционера карт» — установка одной командой${C.r}`);
    note('Ничего руками править не нужно: скрипт сам создаст базу, секреты, задеплоит,');
    note('перенесёт данные игроков и пропишет адрес сервера в игру.');

    /* 1. окружение */
    step('Проверяю окружение');
    const major = Number(process.versions.node.split('.')[0]);
    if (major < 18) die(`Node.js ${process.versions.node} — слишком старый, нужен 18+`, 'Скачайте свежий: https://nodejs.org (кнопка LTS).');
    ok(`Node.js ${process.versions.node}`);
    if (!wranglerBin()) {
        note('ставлю wrangler в server/worker (один раз, ~30 сек)…');
        const r = spawnSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['install', '--no-audit', '--no-fund'], { cwd: WORKER, stdio: 'inherit' });
        if (r.status !== 0) die('npm install не прошёл', 'Проверьте интернет и повторите: cd server/worker && npm install');
    }
    ok(`wrangler ${wranglerBin() ? 'на месте' : 'будет взят через npx'}`);

    /* 2. токен и аккаунт */
    step('Подключаюсь к Cloudflare');
    TOKEN = arg('token', process.env.CLOUDFLARE_API_TOKEN || STATE.token || '');
    if (!TOKEN) {
        console.log(`\n${C.dim}  Нужен API-токен Cloudflare. Как получить (2 минуты):
    1. https://dash.cloudflare.com  → войти/зарегистрироваться
    2. справа вверху значок профиля → «My Profile» → «API Tokens»
    3. «Create Token» → «Create Custom Token»
    4. Permissions:  Account | Workers Scripts | Edit
                     Account | D1             | Edit
    5. Account Resources: Include | ваш аккаунт
    6. «Continue to summary» → «Create Token» → скопировать токен${C.r}\n`);
        TOKEN = await ask('Вставьте API-токен Cloudflare', { secret: true });
    }
    if (!TOKEN) die('Токен не получен', 'Без токена Cloudflare деплой невозможен. См. подсказку выше.');
    try {
        const v = await cf('/user/tokens/verify');
        if (!v || v.status !== 'active') throw new Error('токен не активен');
        ok('токен действителен');
    } catch (e) {
        die(`Cloudflare не принял токен: ${e.message}`,
            'Проверьте, что токен создан с правами Account → Workers Scripts → Edit и Account → D1 → Edit.');
    }

    const accounts = await cf('/accounts?per_page=50').catch(() => []);
    if (!accounts || !accounts.length) die('В аккаунте Cloudflare не найдено ни одного account', 'Зайдите на dash.cloudflare.com и убедитесь, что аккаунт создан.');
    ACCOUNT_ID = arg('account', process.env.CLOUDFLARE_ACCOUNT_ID || STATE.accountId || '');
    if (!ACCOUNT_ID || !accounts.some(a => a.id === ACCOUNT_ID)) {
        ACCOUNT_ID = accounts.length === 1 ? accounts[0].id
            : await ask(`Аккаунтов несколько. Выберите (${accounts.map((a, i) => `${i + 1}=${a.name}`).join(', ')})`, { dflt: '1' });
        if (!/^[0-9a-f]{32}$/i.test(ACCOUNT_ID)) {
            const n = Number(ACCOUNT_ID) - 1;
            ACCOUNT_ID = (accounts[n] || accounts[0]).id;
        }
    }
    const accName = (accounts.find(a => a.id === ACCOUNT_ID) || {}).name || ACCOUNT_ID;
    ok(`аккаунт: ${accName}`);
    saveState({ accountId: ACCOUNT_ID, accountName: accName });

    /* 3. поддомен workers.dev */
    step('Проверяю поддомен workers.dev');
    let subdomain = '';
    try {
        const sd = await cf(`/accounts/${ACCOUNT_ID}/workers/subdomain`);
        subdomain = String((sd && (sd.subdomain || sd.preapproved_subdomain)) || '').replace(/\.workers\.dev$/i, '');
        if (sd && sd.enabled === false) {
            const want = subdomain || `nexus-card-${crypto.randomBytes(3).toString('hex')}`;   // только префикс, без .workers.dev
            note(`поддомен выключен — включаю «${want}»…`);
            await cf(`/accounts/${ACCOUNT_ID}/workers/subdomain`, { method: 'PUT', body: { subdomain: want } });
            subdomain = want;
        }
    } catch (e) {
        warn(`не удалось прочитать/включить поддомен автоматически: ${e.message}`);
        note('Если деплой упадёт с ошибкой про workers.dev: откройте dash.cloudflare.com →');
        note('Workers & Pages → справа «Your workers.dev subdomain» → придумайте имя → Save.');
    }
    if (subdomain) ok(`поддомен: ${subdomain}.workers.dev`);
    saveState({ subdomain });

    /* 4. база D1 */
    step(`Создаю базу D1 «${DB_NAME}»`);
    let dbId = '';
    const existing = await cf(`/accounts/${ACCOUNT_ID}/d1/database?per_page=100`).catch(() => []);
    const found = (existing || []).find(d => d.name === DB_NAME);
    if (found) { dbId = found.uuid; ok(`база уже есть, использую её (${dbId})`); }
    else {
        const created = await cf(`/accounts/${ACCOUNT_ID}/d1/database`, { method: 'POST', body: { name: DB_NAME } })
            .catch(e => die(`Не удалось создать базу D1: ${e.message}`, 'Нужно право Account → D1 → Edit в токене.'));
        dbId = created.uuid;
        ok(`база создана (${dbId})`);
    }
    saveState({ databaseId: dbId });

    /* 5. wrangler.toml */
    step('Вписываю database_id в wrangler.toml');
    let toml = fs.readFileSync(WRANGLER_TOML, 'utf8');
    const re = /^(\s*database_id\s*=\s*")[^"]*("\s*)$/m;
    if (!re.test(toml)) die('В wrangler.toml не найдена строка database_id', 'Восстановите файл: git checkout -- server/worker/wrangler.toml');
    const cur = toml.match(re)[0];
    if (cur.includes(dbId)) ok('уже вписан');
    else {
        toml = toml.replace(re, `$1${dbId}$2`);
        fs.writeFileSync(WRANGLER_TOML, toml, 'utf8');
        ok('вписан');
    }

    /* 6. секреты */
    step('Генерирую секреты');
    const NX_SECRET = STATE.nxSecret || secretHex(32);
    const NX_SETUP_KEY = STATE.nxSetupKey || secretHex(16);
    ok(`NX_SECRET   = ${NX_SECRET.slice(0, 6)}…${NX_SECRET.slice(-4)}  ${C.dim}(подпись токенов игроков и админки)${C.r}`);
    ok(`NX_SETUP_KEY = ${NX_SETUP_KEY.slice(0, 4)}…${NX_SETUP_KEY.slice(-4)}  ${C.dim}(ключ первой регистрации Студии)${C.r}`);
    saveState({ nxSecret: NX_SECRET, nxSetupKey: NX_SETUP_KEY });

    /* 7. деплой */
    step('Деплою воркер (первый раз ~40 сек)');
    let dep = runWrangler(['deploy']);
    if (dep.code !== 0) {
        console.error(dep.out);
        if (/subdomain/i.test(dep.out)) {
            die('Деплой не прошёл: не включён поддомен workers.dev',
                'dash.cloudflare.com → Workers & Pages → «Your workers.dev subdomain» → задать имя → Save. Затем повторите npm run nexus.');
        }
        die('Деплой не прошёл', 'Текст ошибки выше. Чаще всего — не хватает прав в токене (Workers Scripts → Edit).');
    }
    // --api-url <адрес> — если воркер уже поднят и адрес известен заранее
    let url = String(arg('api-url', '') || '').replace(/\/+$/, '') || await resolveWorkerUrl(dep.out);
    if (!url && subdomain) url = `https://${WORKER_NAME}.${subdomain}.workers.dev`;
    if (!url) die('Воркер задеплоен, но я не смог определить его адрес',
        'Посмотрите его в dash.cloudflare.com → Workers & Pages → nexus-card-api и перезапустите скрипт с --api-url <адрес>.');
    url = url.replace(/\/+$/, '');
    ok(`воркер поднят: ${C.b}${url}${C.r}`);
    saveState({ apiUrl: url });

    /* 8. секреты на воркер + health */
    step('Загружаю секреты на воркер и проверяю живость');
    for (const [name, value] of [['NX_SECRET', NX_SECRET], ['NX_SETUP_KEY', NX_SETUP_KEY]]) {
        const r = runWrangler(['secret', 'put', name], { input: value + '\n', quiet: true });
        if (r.code !== 0) { console.error(r.out); die(`Не удалось загрузить секрет ${name}`, 'Попробуйте руками: cd server/worker && npx wrangler secret put ' + name); }
        ok(`секрет ${name} загружен`);
    }
    let health = null;
    for (let i = 0; i < 10 && !(health && health.ok); i++) {
        await new Promise(r => setTimeout(r, 1500));
        try { health = await (await fetch(`${url}/api/health`)).json(); } catch { /* воркер ещё прогревается */ }
    }
    if (!health || !health.ok) die('Воркер отвечает, но /api/health не ok', JSON.stringify(health));
    ok(`health: store=${health.store}, secret=${health.secret}`);
    if (health.store !== 'd1') warn(`хранилище ${health.store}, ожидалось d1 — проверьте database_id в wrangler.toml`);

    /* 9. перенос данных */
    step('Переношу текущие данные игроков (банк, балансы, зал славы, каталог)');
    let migrated = false;
    if (has('skip-migrate')) {
        warn('пропущено (--skip-migrate)');
    } else {
        const login = arg('studio-login', STATE.studioLogin || '') || await ask('Логин Студии (вход останется таким же)', { dflt: STATE.studioLogin || 'owner' });
        let pass = arg('studio-pass', '') || '';
        if (!pass) pass = await ask('Пароль Студии', { secret: true });
        saveState({ studioLogin: login });
        const already = STATE.migratedOnce;
        const args = [path.join(HERE, 'migrate.mjs'), '--api', url, '--setup-key', NX_SETUP_KEY];
        if (already && !has('force-setup')) args.push('--login', login, '--pass', pass);
        else args.push('--setup-login', login, '--setup-pass', pass);
        const r = spawnSync(process.execPath, args, { cwd: ROOT, stdio: 'inherit' });
        if (r.status === 0) { migrated = true; saveState({ migratedOnce: true }); ok('данные перенесены'); }
        else {
            warn('миграция вернула ошибку — сервер при этом работает.');
            note('Повторить позже:  node server/migrate.mjs --api ' + url + ' --setup-login ' + login + ' --setup-pass \'<пароль>\' --setup-key <NX_SETUP_KEY>');
            note('Посмотреть, что нашлось, ничего не меняя: добавьте --dry-run');
        }
    }

    /* 10. адрес API в index.html */
    step('Прописываю адрес сервера в index.html');
    let html = fs.readFileSync(INDEX_HTML, 'utf8');
    const line = `    <script>window.__NX_API = '${url}';</script>\n`;
    if (/window\.__NX_API\s*=/.test(html)) {
        html = html.replace(/^[ \t]*<script>window\.__NX_API\s*=[^<]*<\/script>\n?/m, line);
        ok('адрес обновлён');
    } else {
        const anchor = html.match(/^[ \t]*<script src="assets\/nx-rules\.js[^\n]*\n/m);
        if (!anchor) die('В index.html не найден тег assets/nx-rules.js', 'Впишите строку вручную перед ним: ' + line.trim());
        html = html.replace(anchor[0], line + anchor[0]);
        ok('строка window.__NX_API добавлена перед nx-rules.js');
    }
    fs.writeFileSync(INDEX_HTML, html, 'utf8');

    /* 11. файл с ключами */
    step('Сохраняю ключи локально');
    ok(`server/.nexus.local.json ${C.dim}(файл в .gitignore — в репозиторий не попадёт)${C.r}`);
    note('NX_SETUP_KEY понадобится, если будете менять пароль Студии. NX_SECRET — при переустановке воркера.');

    /* 12. пуш */
    step('Публикую изменение сайта');
    if (has('push')) {
        const g = (...a) => spawnSync('git', a, { cwd: ROOT, encoding: 'utf8' });
        g('add', 'index.html', 'server/setup.mjs', 'server/worker/wrangler.toml', '.gitignore', 'package.json', 'server/README.md', 'FIXES.md');
        const c = g('commit', '-m', `b465: сервер развёрнут (${url}); адрес API прописан в index.html; setup.mjs — установка одной командой`);
        if (/nothing to commit/i.test(c.stdout || '')) ok('коммитить нечего');
        else if (c.status !== 0) warn('коммит не прошёл: ' + (c.stderr || '').trim().split('\n')[0]);
        else {
            const p = g('push');
            if (p.status === 0) ok('запушено в main — GitHub Pages обновит сайт за ~1 минуту');
            else warn('push не прошёл: ' + (p.stderr || '').trim().split('\n')[0]);
        }
    } else {
        note('изменения только локальные. Опубликовать сайт:');
        note('  git add index.html && git commit -m "адрес API" && git push');
        note('или запустите этот скрипт ещё раз с флагом --push');
    }

    /* итог */
    console.log(`\n${C.b}${C.g}Готово.${C.r}`);
    console.log(`${C.b}  Адрес сервера:${C.r}  ${url}`);
    console.log(`${C.b}  Здоровье:${C.r}       ${url}/api/health`);
    console.log(`${C.b}  Студия:${C.r}         откройте сайт → Студия → войдите ${loginHint()}`);
    console.log(`${C.b}  Данные:${C.r}         ${migrated ? 'перенесены на сервер' : 'НЕ перенесены — см. подсказку выше'}`);
    console.log(`\n${C.dim}Что дальше: ничего. Игра сама увидит window.__NX_API и начнёт считать деньги,`);
    console.log(`спины, паки, биржу и админку на сервере. Если сервер недоступен — игра`);
    console.log(`продолжит работать на локальной логике, ничего не сломается.${C.r}\n`);
}

function loginHint() {
    return STATE.studioLogin ? `как «${STATE.studioLogin}» своим паролем` : 'своим логином и паролем';
}

main().catch(e => {
    console.error(`\n${C.red}${C.b}✗ Сбой: ${e && e.message || e}${C.r}`);
    if (e && e.stack) console.error(C.dim + e.stack.split('\n').slice(1, 4).join('\n') + C.r);
    note('Что уже сделано — сохранено в server/.nexus.local.json, повторный запуск продолжит с этого места.');
    process.exit(1);
});
if (rl) process.on('exit', () => rl && rl.close());
