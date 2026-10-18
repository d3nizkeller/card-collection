/* server/worker/src/crypto.js — токены и пароли (b463)
 *
 * Что здесь и зачем
 * -----------------
 * 1) ТОКЕН УСТРОЙСТВА. Аккаунтов в игре нет: игрок — это устройство с cid из
 *    localStorage. Раньше этого было достаточно, чтобы «предъявить» серверу
 *    чужой cid и забрать чужой баланс. Теперь сервер выдаёт подписанный токен
 *    (HMAC-SHA256 от cid + срока действия). Подделать подпись без секрета
 *    NX_SECRET невозможно, значит и чужой баланс не получить.
 *
 * 2) АДМИН-ТОКЕН. Пароль Студии больше НЕ хранится и НЕ сравнивается в
 *    клиентском коде: клиент отправляет логин+пароль на /api/studio/login,
 *    сервер сверяет их со своим хэшем (PBKDF2-SHA256, 150 000 итераций, соль)
 *    и выдаёт отдельный админ-токен. Все действия админки требуют его.
 *
 * 3) СЛУЧАЙНЫЕ ЧИСЛА. crypto.getRandomValues вместо Math.random — см. util.js.
 *
 * Секрет NX_SECRET задаётся в wrangler secret put NX_SECRET (в репозиторий не
 * попадает). Без него воркер отказывается выдавать токены.
 */

const enc = new TextEncoder();

function b64url(buf) {
    const b = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
    let s = '';
    for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
    return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function b64urlDecode(str) {
    const s = String(str).replace(/-/g, '+').replace(/_/g, '/');
    const bin = atob(s + '='.repeat((4 - (s.length % 4)) % 4));
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
}

async function hmacKey(secret) {
    return crypto.subtle.importKey('raw', enc.encode(String(secret)), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
}

async function sign(secret, msg) {
    const k = await hmacKey(secret);
    return b64url(await crypto.subtle.sign('HMAC', k, enc.encode(msg)));
}

/** Постоянное сравнение — чтобы нельзя было подобрать подпись по времени ответа. */
export function safeEq(a, b) {
    const x = String(a), y = String(b);
    if (x.length !== y.length) return false;
    let d = 0;
    for (let i = 0; i < x.length; i++) d |= x.charCodeAt(i) ^ y.charCodeAt(i);
    return d === 0;
}

export const TOKEN_TTL_MS = 30 * 24 * 3600 * 1000;      // токен устройства — 30 дней
export const ADMIN_TTL_MS = 12 * 3600 * 1000;          // админ-сессия — 12 часов

/** Выдать токен устройства: v1.<cid>.<exp>.<sig> */
export async function issueDeviceToken(secret, cid, ttlMs = TOKEN_TTL_MS) {
    const exp = Date.now() + ttlMs;
    const body = 'v1.' + cid + '.' + exp;
    return body + '.' + (await sign(secret, body));
}

/** Проверить токен устройства → cid или null. */
export async function verifyDeviceToken(secret, token) {
    try {
        const parts = String(token || '').split('.');
        if (parts.length !== 4 || parts[0] !== 'v1') return null;
        const body = parts.slice(0, 3).join('.');
        if (!safeEq(await sign(secret, body), parts[3])) return null;
        if (!(Number(parts[2]) > Date.now())) return null;
        return parts[1];
    } catch (e) { return null; }
}

/** Выдать админ-токен: a1.<login>.<exp>.<sig> */
export async function issueAdminToken(secret, login, ttlMs = ADMIN_TTL_MS) {
    const exp = Date.now() + ttlMs;
    const body = 'a1.' + encodeURIComponent(login) + '.' + exp;
    return body + '.' + (await sign(secret, body));
}

/** Проверить админ-токен → логин или null. */
export async function verifyAdminToken(secret, token) {
    try {
        const parts = String(token || '').split('.');
        if (parts.length !== 4 || parts[0] !== 'a1') return null;
        const body = parts.slice(0, 3).join('.');
        if (!safeEq(await sign(secret, body), parts[3])) return null;
        if (!(Number(parts[2]) > Date.now())) return null;
        return decodeURIComponent(parts[1]);
    } catch (e) { return null; }
}

// ---------------------- пароль Студии (PBKDF2) ----------------------
const PBKDF2_ITERS = 150000;

export function randomSalt(bytes = 16) {
    const b = new Uint8Array(bytes);
    crypto.getRandomValues(b);
    let s = '';
    for (let i = 0; i < b.length; i++) s += b[i].toString(16).padStart(2, '0');
    return s;
}

/** Хэш пароля: PBKDF2-SHA256. В базу пишется только он + соль. */
export async function hashPassword(pass, salt, iters = PBKDF2_ITERS) {
    const base = await crypto.subtle.importKey('raw', enc.encode(String(pass)), 'PBKDF2', false, ['deriveBits']);
    const bits = await crypto.subtle.deriveBits(
        { name: 'PBKDF2', salt: enc.encode(String(salt)), iterations: iters, hash: 'SHA-256' }, base, 256);
    return 'pbkdf2$' + iters + '$' + b64url(bits);
}

export async function verifyPassword(pass, stored) {
    try {
        const parts = String(stored || '').split('$');
        if (parts.length !== 3 || parts[0] !== 'pbkdf2') return false;
        const iters = Math.max(1000, parseInt(parts[1], 10) || PBKDF2_ITERS);
        const base = await crypto.subtle.importKey('raw', enc.encode(String(pass)), 'PBKDF2', false, ['deriveBits']);
        const bits = await crypto.subtle.deriveBits(
            { name: 'PBKDF2', salt: enc.encode(parts[2].slice(0, 32)), iterations: iters, hash: 'SHA-256' }, base, 256);
        return safeEq(parts[2].slice(32), b64url(bits));
    } catch (e) { return false; }
}

/**
 * Склеить соль и хэш в одну строку формата pbkdf2$iters$<salt32><hash>.
 * Так в базе лежит одно поле, а verifyPassword() сам разбирает его обратно.
 */
export async function makePasswordRecord(pass, iters = PBKDF2_ITERS) {
    const salt = randomSalt(16);
    const base = await crypto.subtle.importKey('raw', enc.encode(String(pass)), 'PBKDF2', false, ['deriveBits']);
    const bits = await crypto.subtle.deriveBits(
        { name: 'PBKDF2', salt: enc.encode(salt), iterations: iters, hash: 'SHA-256' }, base, 256);
    return 'pbkdf2$' + iters + '$' + salt + b64url(bits);
}

/** Нормализация логина — та же, что была в клиенте (cloudAuthNorm). */
export function normLogin(l) { return String(l == null ? '' : l).trim().toLowerCase(); }

/** Валидация логина/пароля — текст ошибок перенесён из cloudAuthValidate(). */
export function validateCreds(login, pass) {
    const l = normLogin(login), p = String(pass == null ? '' : pass);
    if (!l) return 'Введите логин комнаты';
    if (l.length < 3) return 'Логин — минимум 3 символа';
    if (l.length > 24) return 'Логин — максимум 24 символа';
    if (!/^[a-z0-9а-яё_\-.@]+$/.test(l)) return 'Логин: буквы, цифры и знаки _ - . @ (без пробелов)';
    if (p.length < 4) return 'Пароль — минимум 4 символа';
    if (p.length > 64) return 'Пароль — максимум 64 символа';
    return '';
}
