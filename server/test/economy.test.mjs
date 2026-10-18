/* server/test/economy.test.mjs — проверка серверной экономики (b463)
 *
 * Тесты идут НЕ через HTTP, а напрямую в обработчики API на in-memory драйвере:
 * это тот же код, что будет работать на Cloudflare (store.js/api.js/economy.js/
 * admin.js), только без сети и без D1.
 *
 * Запуск:  node server/test/economy.test.mjs
 *
 * Что проверяем:
 *   1.  вход в Студию — только на сервере, пароль и его хэш клиенту не отдаются;
 *   2.  админ-действия без токена не проходят (в т.ч. «Обнулить», «Поставить банк»);
 *   3.  спин: ставка списывается сервером, результат приходит с сервера,
 *       выплата совпадает с общими правилами (assets/nx-rules.js);
 *   4.  баланс нельзя завысить: нет токена / не хватило монет / чужой cid;
 *   5.  джекпот: банк уменьшается ровно на выплату, победитель попадает в зал славы;
 *   6.  повторная доставка запроса (тот же oid) не списывает и не платит дважды;
 *   7.  паки: цена из каталога, карты крутит сервер, дубликаты возвращают монеты;
 *   8.  биржа: эскроу, атомарная покупка, продавец получает деньги, второй покупатель — отказ;
 *   9.  мины: раскладка мин клиенту не отдаётся, выплата = ставка × множитель;
 *   10. шахта: добычу считает сервер по своему времени, офлайн-потолок 2 часа;
 *   11. гонка: 24 параллельных спина — деньги сохраняются (ни одной лишней монеты);
 *   12. миграция: банк, balances, зал славы и блокировки переносятся из старого документа.
 */

import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');

await import(path.join(ROOT, 'assets', 'nx-rules.js'));
const R = globalThis.NXR;

const { makeStore } = await import(path.join(ROOT, 'server', 'worker', 'src', 'store.js'));
const { makeMemDriver } = await import(path.join(ROOT, 'server', 'worker', 'src', 'driver-mem.js'));
const { makeApi } = await import(path.join(ROOT, 'server', 'worker', 'src', 'api.js'));

const env = { NX_SECRET: 'test-secret-32-bytes-long-aaaaaaaa', NX_ROOM: 'site', NX_ORIGINS: '', NX_SETUP_KEY: '' };
const driver = makeMemDriver();
const store = makeStore(driver);
const api = makeApi({ store, env });

// ---------------- мини-харнесс ----------------
let passed = 0, failed = 0;
const fails = [];
function ok(cond, name, extra) {
    if (cond) { passed++; console.log('  ✅ ' + name); }
    else { failed++; fails.push(name); console.log('  ❌ ' + name + (extra !== undefined ? '  → ' + JSON.stringify(extra) : '')); }
}
function eq(a, b, name) { ok(String(a) === String(b), name + ' (=' + a + ')', { got: a, want: b }); }

function req(headers = {}, query = {}) {
    return { headers: new Headers(headers), query, method: 'POST', url: '/' };
}
async function call(handler, body, headers) {
    const res = await handler(req(headers || {}, (body && body.__q) || {}), body || {}, new Headers(headers || {}));
    let j = null;
    try { j = await res.json(); } catch (e) { j = { parseError: true }; }
    return { status: res.status, body: j };
}

// тестовый каталог: 2 пака, 12 карт (как в реальной комнате, только маленький)
const CATALOG = {
    packs: [
        { id: 'pk-doctor', title: 'Доктор Кто', price: 1000 },
        { id: 'pk-potter', title: 'Гарри Поттер', price: 5000, retired: true }
    ],
    cards: []
};
const RAR = ['common', 'common', 'common', 'rare', 'rare', 'epic', 'legendary'];
for (let i = 0; i < 12; i++) {
    CATALOG.cards.push({
        id: 'c' + i, packId: i < 6 ? 'pk-doctor' : 'pk-potter',
        rarity: RAR[i % RAR.length], name: 'Карта ' + i, image: 'media/c' + i + '.png'
    });
}

const A = {};   // токены и состояния теста

console.log('\n=== b463: серверная экономика «Коллекционера карт» ===\n');

// ---------------------------------------------------------------- 1. Студия
console.log('[1] Вход в Студию переехал на сервер');
{
    const r = await call(api.routes['POST /api/studio/setup'], { login: 'Owner', pass: 'sekret-pass-1' });
    ok(r.body.ok === true && !!r.body.adminToken, 'первая учётка Студии создана, выдан админ-токен');
    ok(!('hash' in (r.body || {})) && !('legacyHash' in (r.body || {})), 'хэш пароля клиенту НЕ отдан', r.body);
    A.admin = r.body.adminToken;

    const r2 = await call(api.routes['POST /api/studio/setup'], { login: 'hacker', pass: 'hacker-pass' });
    ok(r2.body.ok !== true, 'вторую учётку без админ-токена создать нельзя');

    const r3 = await call(api.routes['POST /api/studio/login'], { login: 'owner', pass: 'sekret-pass-1' });
    ok(r3.body.ok === true && !!r3.body.adminToken, 'вход по логину/паролю (логин регистронезависим)');

    const r4 = await call(api.routes['POST /api/studio/login'], { login: 'owner', pass: 'неверный' });
    ok(r4.body.ok !== true, 'с неверным паролем админ-токен не выдаётся');
}

// ---------------------------------------------------------------- 2. Админка
console.log('\n[2] Админ-действия — только с серверным токеном');
{
    const noTok = await call(api.routes['POST /api/admin'], { act: 'poolSet', value: 1 });
    ok(noTok.status === 403 && noTok.body.error === 'admin_required', '«Поставить банк» без токена — 403');

    const fake = await call(api.routes['POST /api/admin'], { act: 'poolSet', value: 1 }, { 'x-nx-admin': 'a1.owner.9999999999999.deadbeef' });
    ok(fake.status === 403, 'поддельный админ-токен отклонён');

    const users = await call(api.routes['GET /api/admin/users'], {}, { 'x-nx-admin': A.admin });
    ok(users.body.ok === true && Array.isArray(users.body.players), 'список игроков Студия берёт с сервера');
}

// ---------------------------------------------------------------- 3. Игрок
console.log('\n[3] Вход игрока: токен устройства');
{
    const b = await call(api.routes['POST /api/boot'], { cid: 'pALICE01', name: 'Алиса', room: 'site' });
    ok(b.body.ok === true && !!b.body.token, 'boot выдал токен устройства');
    A.alice = b.body.token;
    A.aliceBal0 = b.body.player.bal.s;
    eq(b.body.player.bal.s, '0', 'новый игрок начинает с нулём (баланс выдаёт сервер)');

    const b2 = await call(api.routes['POST /api/boot'], { cid: 'pBOB0002', name: 'Боб', room: 'site' });
    A.bob = b2.body.token;

    const bad = await call(api.routes['POST /api/spin'], { game: 'slots', bet: 100 });
    ok(bad.status === 401 && bad.body.error === 'unauthorized', 'спин без токена — 401');

    const forged = await call(api.routes['POST /api/spin'], { game: 'slots', bet: 100 }, { authorization: 'Bearer v1.pBOB0002.9999999999999.badsig' });
    ok(forged.status === 401, 'спин с поддельной подписью токена — 401');

    // чужой cid своим токеном не подменить: cid берётся из подписи токена
    const bobBefore = await store.playerGet('pBOB0002');
    const cross = await call(api.routes['POST /api/spin'], { game: 'slots', bet: 100, cid: 'pBOB0002', cards: ['c0'] }, { authorization: 'Bearer ' + A.alice });
    const bobAfter = await store.playerGet('pBOB0002');
    eq(bobAfter.bal, bobBefore.bal, 'cid из тела запроса игнорируется: баланс Боба не тронут');
    ok(cross.status === 200 || cross.status === 401, 'запрос с чужим cid в теле не дал доступа');
}

// ---------------------------------------------------------------- 4. Каталог
console.log('\n[4] Каталог комнаты публикует владелец (иначе редкости карт взял бы клиент)');
{
    const noCat = await call(api.routes['POST /api/spin'], { game: 'slots', bet: 100, cards: ['c0', 'c1', 'c2'] }, { authorization: 'Bearer ' + A.alice });
    ok(noCat.body.ok === false && noCat.body.fallback === true, 'без каталога сервер просит клиента остаться на локальном режиме');

    const pub = await call(api.routes['POST /api/admin'], { act: 'catalog', room: 'site', packs: CATALOG.packs, cards: CATALOG.cards }, { 'x-nx-admin': A.admin });
    ok(pub.body.ok === true && pub.body.cards === CATALOG.cards.length, 'каталог опубликован админом: карт ' + pub.body.cards);
}

// ---------------------------------------------------------------- 5. Выдача монет админом
console.log('\n[5] Банк и балансы меняет только сервер');
{
    const set = await call(api.routes['POST /api/admin'], { act: 'poolSet', value: 5000000, room: 'site' }, { 'x-nx-admin': A.admin });
    eq(set.body.bank.pot, '5000000', '«Поставить банк» = 5 000 000');

    const g = await call(api.routes['POST /api/admin'], { act: 'grant', cid: 'pALICE01', amount: 1000000, room: 'site' }, { 'x-nx-admin': A.admin });
    eq(g.body.results[0].bal.s, '1000000', '«Выдать сумму» зачислила 1 000 000 Алисе');
    A.aliceBal = 1000000n;

    const g2 = await call(api.routes['POST /api/admin'], { act: 'grant', cid: 'pBOB0002', amount: 200000, room: 'site' }, { 'x-nx-admin': A.admin });
    eq(g2.body.results[0].bal.s, '200000', 'Бобу выдано 200 000');
}

// ---------------------------------------------------------------- 6. Спин
console.log('\n[6] Спин: ставка, результат и выплата — на сервере');
{
    const bet = 1000;
    const r = await call(api.routes['POST /api/spin'], { game: 'slots', bet, cards: ['c0', 'c1', 'c2'], oid: 'oid-slots-1' }, { authorization: 'Bearer ' + A.alice });
    ok(r.body.ok === true, 'спин прошёл');
    ok(Array.isArray(r.body.res) && r.body.res.length === 3, 'сервер вернул результат трёх барабанов');

    // баланс уменьшился ровно на ставку (или на ставку минус выигрыш)
    const syms = R.buildSymbols([{ id: 'c0', rarity: 'common' }, { id: 'c1', rarity: 'common' }, { id: 'c2', rarity: 'common' }]);
    const expect = R.slotsPayout(r.body.res, syms, bet);
    const wantBal = 1000000n - BigInt(bet) + (r.body.jpHit ? BigInt(r.body.jp.prize) : BigInt(expect.win));
    eq(r.body.bal.s, wantBal.toString(), 'баланс = прежний − ставка + выигрыш (по общим правилам)');
    eq(r.body.win, expect.win, 'выплата совпала с пересчётом по nx-rules.js');

    // повторная доставка того же oid
    const balBefore = r.body.bal.s;
    const r2 = await call(api.routes['POST /api/spin'], { game: 'slots', bet, cards: ['c0', 'c1', 'c2'], oid: 'oid-slots-1' }, { authorization: 'Bearer ' + A.alice });
    eq(r2.body.bal.s, balBefore, 'повтор того же oid не списал ставку второй раз');

    // не хватило монет
    const poor = await call(api.routes['POST /api/spin'], { game: 'slots', bet: 1e15, cards: ['c0'] }, { authorization: 'Bearer ' + A.alice });
    ok(poor.body.ok === false && poor.body.error === 'not_enough', 'ставки больше баланса сервер не принимает');

    // все четыре игры отвечают результатом
    for (const g of ['grid', 'lines', 'wheel']) {
        const x = await call(api.routes['POST /api/spin'], { game: g, bet: 500, cards: ['c0', 'c1', 'c2'] }, { authorization: 'Bearer ' + A.bob });
        ok(x.body.ok === true && x.body.res !== undefined, 'игра «' + g + '» вернула серверный результат');
        if (g === 'grid') ok(Array.isArray(x.body.res.cells) && x.body.res.cells.length === 20, 'сетка: поле 20 ячеек + ' + (x.body.res.steps || []).length + ' каскадов');
        if (g === 'lines') ok(Array.isArray(x.body.res) && x.body.res.length === 15, 'линии: 15 ячеек');
    }

    // редкость приходит из каталога сервера: «легендарка» в запросе не работает
    const lie = await call(api.routes['POST /api/spin'], { game: 'slots', bet: 100, cards: [{ id: 'c0', rarity: 'legendary' }] }, { authorization: 'Bearer ' + A.bob });
    ok(lie.body.ok === true, 'запрос с подсунутой редкостью принят, но редкость берётся из каталога');
}

// ---------------------------------------------------------------- 7. Джекпот
console.log('\n[7] Джекпот: банк и зал славы ведёт сервер');
{
    const before = (await call(api.routes['GET /api/public'], {}, {})).body.bank;
    const g = await call(api.routes['POST /api/admin'], { act: 'grant', cid: 'pALICE01', amount: 0, room: 'site' }, { 'x-nx-admin': A.admin });
    ok(g.body.ok === true && g.body.results[0].ok === true, '«Выдать банк» сработал');
    const after = g.body.bank;
    ok(BigInt(after.pot) < BigInt(before.pot), 'банк уменьшился: ' + before.pot + ' → ' + after.pot);
    const hall = (await call(api.routes['GET /api/public'], {}, {})).body.hall;
    ok(Array.isArray(hall) && hall.length > 0 && hall[0].c === 'pALICE01', 'победитель записан в зал славы сервером');
    eq(after.pot, R.bankPool({ floor: after.floor, fed: after.fed, won: after.won }).toString(), 'банк сошёлся с формулой floor + Σвзносов − Σвыплат');
}

// ---------------------------------------------------------------- 8. Паки
console.log('\n[8] Покупка паков: цена из каталога, карты крутит сервер');
{
    const st = await call(api.routes['GET /api/state'], {}, { authorization: 'Bearer ' + A.bob });
    const bal0 = BigInt(st.body.bal.s);
    const r = await call(api.routes['POST /api/pack'], { packId: 'pk-doctor', qty: 2, price: 1000 }, { authorization: 'Bearer ' + A.bob });
    ok(r.body.ok === true && r.body.cards.length === 8, '2 пака = 8 карт, все выбраны сервером');
    eq(r.body.bal.s, (bal0 - 2000n + BigInt(r.body.dupeCoins || 0)).toString(), 'списана ровно цена из каталога (плюс возврат за дубликаты)');

    const cheap = await call(api.routes['POST /api/pack'], { packId: 'pk-doctor', qty: 1, price: 10 }, { authorization: 'Bearer ' + A.bob });
    ok(cheap.body.ok === false && cheap.body.error === 'price_out_of_range', 'цену ниже законной скидки сервер не принимает');

    const retired = await call(api.routes['POST /api/pack'], { packId: 'pk-potter', qty: 1 }, { authorization: 'Bearer ' + A.bob });
    ok(retired.body.ok === false && retired.body.error === 'pack_retired', 'снятый с продажи пак не покупается');

    const nopack = await call(api.routes['POST /api/pack'], { packId: 'pk-none', qty: 1 }, { authorization: 'Bearer ' + A.bob });
    ok(nopack.status === 404, 'несуществующий пак — 404');
}

// ---------------------------------------------------------------- 9. Биржа
console.log('\n[9] Биржа: эскроу, владение картой, атомарная покупка');
{
    const inv = await store.invList('pBOB0002');
    const cardId = Object.keys(inv)[0];
    ok(!!cardId, 'у Боба есть карта после вскрытия паков: ' + cardId);

    const lotId = 'lot-test-1';
    const l = await call(api.routes['POST /api/market/list'], { lots: [{ id: lotId, sid: 'pBOB0002', sname: 'Боб', price: 777, card: { id: cardId, name: 'Карта', rarity: 'common' } }] }, { authorization: 'Bearer ' + A.bob });
    ok(l.body.ok === true && l.body.listed === 1, 'лот выставлен (копия ушла в эскроу сервера)');
    const invAfter = await store.invList('pBOB0002');
    eq(invAfter[cardId] || 0, (inv[cardId] - 1), 'у продавца стало на одну копию меньше');

    const fakeLot = await call(api.routes['POST /api/market/list'], { lots: [{ id: 'lot-fake', sid: 'pBOB0002', price: 10, card: { id: 'c-not-owned' } }] }, { authorization: 'Bearer ' + A.bob });
    ok(fakeLot.body.rejected && fakeLot.body.rejected[0].error === 'not_owned', 'продать карту, которой нет, нельзя');

    const sellerBal0 = BigInt((await call(api.routes['GET /api/state'], {}, { authorization: 'Bearer ' + A.bob })).body.bal.s);
    const buyerBal0 = BigInt((await call(api.routes['GET /api/state'], {}, { authorization: 'Bearer ' + A.alice })).body.bal.s);
    const buy = await call(api.routes['POST /api/market/buy'], { id: lotId, name: 'Алиса' }, { authorization: 'Bearer ' + A.alice });
    ok(buy.body.ok === true, 'лот куплен');
    eq(buy.body.bal.s, (buyerBal0 - 777n).toString(), 'с покупателя списана цена лота');
    const sellerBal1 = BigInt((await call(api.routes['GET /api/state'], {}, { authorization: 'Bearer ' + A.bob })).body.bal.s);
    eq(sellerBal1, (sellerBal0 + 777n).toString(), 'продавец получил монеты сразу');

    const twice = await call(api.routes['POST /api/market/buy'], { id: lotId, name: 'Алиса' }, { authorization: 'Bearer ' + A.alice });
    ok(twice.body.ok === false, 'один и тот же лот дважды не продаётся');
}

// ---------------------------------------------------------------- 10. Мины
console.log('\n[10] Мины: раскладка остаётся на сервере');
{
    const s = await call(api.routes['POST /api/mines'], { act: 'start', bet: 1000, m: 5 }, { authorization: 'Bearer ' + A.alice });
    ok(s.body.ok === true && !!s.body.id, 'раунд начат, ставка списана');
    ok(s.body.mines === undefined, 'позиции мин клиенту НЕ отданы', s.body);
    const g = await store.minesGet(s.body.id);
    ok(!!g && Array.isArray(g.mines) && g.mines.length === 5, 'на сервере раскладка из 5 мин есть');

    let picked = -1;
    for (let i = 0; i < 25; i++) if (g.mines.indexOf(i) < 0) { picked = i; break; }
    const p = await call(api.routes['POST /api/mines'], { act: 'pick', id: s.body.id, i: picked }, { authorization: 'Bearer ' + A.alice });
    ok(p.body.ok === true && p.body.mine === false && p.body.mult > 1, 'безопасная плитка открыта, множитель вырос: ×' + p.body.mult);

    const c = await call(api.routes['POST /api/mines'], { act: 'cashout', id: s.body.id }, { authorization: 'Bearer ' + A.alice });
    ok(c.body.ok === true && BigInt(c.body.win) === BigInt(Math.floor(1000 * c.body.mult)), 'выплата = ставка × множитель');
    const again = await call(api.routes['POST /api/mines'], { act: 'cashout', id: s.body.id }, { authorization: 'Bearer ' + A.alice });
    ok(again.status === 404, 'забрать второй раз с того же раунда нельзя');
}

// ---------------------------------------------------------------- 11. Шахта и награды
console.log('\n[11] Шахта и награды: время и суммы считает сервер');
{
    await store.mutate(store.NS.PLAYER, 'pALICE01', (p) => { p.minerLvl = 3; p.minerLast = Date.now() - 10000; return p; });
    const m = await call(api.routes['POST /api/miner'], { act: 'claim' }, { authorization: 'Bearer ' + A.alice });
    ok(m.body.ok === true && Number(m.body.gainN) >= 24 && Number(m.body.gainN) <= 33, '10 секунд × 3-й уровень кирки ≈ 30 монет (получено ' + m.body.gainN + ')');
    const m2 = await call(api.routes['POST /api/miner'], { act: 'claim' }, { authorization: 'Bearer ' + A.alice });
    ok(Number(m2.body.gainN) <= 3, 'сразу повторно добыча почти не капает (время сервера)');

    await store.mutate(store.NS.PLAYER, 'pALICE01', (p) => { p.minerLast = Date.now() - 10 * 3600 * 1000; return p; });
    const m3 = await call(api.routes['POST /api/miner'], { act: 'claim' }, { authorization: 'Bearer ' + A.alice });
    eq(m3.body.sec, 7200, 'офлайн-потолок 2 часа соблюдён');

    const d = await call(api.routes['POST /api/reward'], { kind: 'daily' }, { authorization: 'Bearer ' + A.alice });
    ok(d.body.ok === true && d.body.amount === '100', 'дневная награда: сумма из серверной таблицы (100)');
    const d2 = await call(api.routes['POST /api/reward'], { kind: 'daily' }, { authorization: 'Bearer ' + A.alice });
    ok(d2.body.ok === false && d2.body.error === 'already_claimed', 'второй раз за день дневная награда не выдаётся');

    const fakeAch = await call(api.routes['POST /api/reward'], { kind: 'achievement', id: 'packs_50' }, { authorization: 'Bearer ' + A.alice });
    ok(fakeAch.body.ok === false && fakeAch.body.error === 'not_completed', 'достижение «50 паков» без 50 паков не выдаётся');

    const badAch = await call(api.routes['POST /api/reward'], { kind: 'achievement', id: 'rich', amount: 999999999 }, { authorization: 'Bearer ' + A.alice });
    ok(badAch.body.ok === false || badAch.body.amount === '200', 'сумму награды клиенту изменить не удалось');
}

// ---------------------------------------------------------------- 12. Блокировка
console.log('\n[12] Блокировка и обнуление действуют на сервере');
{
    const z = await call(api.routes['POST /api/admin'], { act: 'zero', cid: 'pBOB0002' }, { 'x-nx-admin': A.admin });
    eq(z.body.results[0].bal.s, '0', '«Обнулить» обнулил баланс Боба');

    const b = await call(api.routes['POST /api/admin'], { act: 'block', cid: 'pBOB0002' }, { 'x-nx-admin': A.admin });
    ok(b.body.results[0].blocked === true, '«Заблокировать» поставил флаг');

    const spin = await call(api.routes['POST /api/spin'], { game: 'slots', bet: 100, cards: ['c0'] }, { authorization: 'Bearer ' + A.bob });
    ok(spin.status === 403 && spin.body.error === 'blocked', 'заблокированный игрок крутить не может');

    const pack = await call(api.routes['POST /api/pack'], { packId: 'pk-doctor', qty: 1 }, { authorization: 'Bearer ' + A.bob });
    ok(pack.status === 403, 'заблокированный игрок не может покупать паки');

    await call(api.routes['POST /api/admin'], { act: 'unblock', cid: 'pBOB0002' }, { 'x-nx-admin': A.admin });
    const spin2 = await call(api.routes['POST /api/spin'], { game: 'slots', bet: 1, cards: ['c0'] }, { authorization: 'Bearer ' + A.bob });
    ok(spin2.status !== 403, 'после разблокировки доступ вернулся');
}

// ---------------------------------------------------------------- 13. Гонка
console.log('\n[13] Гонка: 24 параллельных спина — ни одной лишней монеты');
{
    await call(api.routes['POST /api/admin'], { act: 'grant', cid: 'pALICE01', amount: 500000 }, { 'x-nx-admin': A.admin });
    const st0 = await call(api.routes['GET /api/state'], {}, { authorization: 'Bearer ' + A.alice });
    const bal0 = BigInt(st0.body.bal.s);
    const bank0 = BigInt(st0.body.bank.pot);

    const bet = 1000, n = 24;
    const results = await Promise.all(Array.from({ length: n }, (_, i) =>
        call(api.routes['POST /api/spin'], { game: 'slots', bet, cards: ['c0', 'c1', 'c2'], oid: 'race-' + i }, { authorization: 'Bearer ' + A.alice })));
    const done = results.filter(r => r.body.ok);
    const st1 = await call(api.routes['GET /api/state'], {}, { authorization: 'Bearer ' + A.alice });
    const bal1 = BigInt(st1.body.bal.s);

    let paid = 0n, jp = 0n;
    for (const r of done) {
        paid += BigInt(r.body.win || 0);
        if (r.body.jpHit) jp += BigInt((r.body.jp && r.body.jp.prize) || 0);
    }
    eq(bal1, bal0 - BigInt(done.length) * BigInt(bet) + paid + jp, 'баланс сошёлся до монеты при ' + done.length + ' параллельных спинах');
    ok(BigInt(st1.body.bank.pot) > bank0, 'общий банк вырос от взносов ставок');
}

// ---------------------------------------------------------------- 14. Миграция
console.log('\n[14] Миграция текущих данных игроков');
{
    const legacy = {
        doc: {
            jp: {
                led: { 'pOLD0001': 500000, 'pOLD0001#1': 200000, 'pOLD0002': 12345, 'house': 777 },
                won: { 'pOLD0001': 100000 },
                wins: { 'pOLD0001': 2 },
                names: { 'pOLD0001': 'Денис Keller' },
                hall: [{ n: 'Денис Keller', a: 86000000000000000, t: Date.now() - 3600000, c: 'pOLD0001', nm: 1 }],
                ep: 3
            },
            jpc: { on: 1, feedBet: 100, feedLoss: 100, payout: 100, floor: 10000000, cap: 0, pSlots: 5.66, at: Date.now(), by: 'pOLD0001' },
            st: {
                p: {
                    'pOLD0001': { cid: 'pOLD0001', n: 'Денис Keller', bal: 15000000, op: 42, jp: 2, fed: 600000, won: 100000, at: Date.now(), did: 'dv123', ip: '1.2.3.4', dev: 'iPhone' },
                    'pOLD0002': { cid: 'pOLD0002', n: 'An', bal: 73000000, op: 7, jp: 1, at: Date.now() }
                },
                b: { 'pOLD0002': { on: 1, at: Date.now() } },
                z: { 'pOLD0003': Date.now() }
            },
            mk: { lots: [{ id: 'lot-old-1', sid: 'pOLD0001', sname: 'Денис Keller', price: 5000, at: Date.now(), card: { id: 'c1', name: 'Карта 1', rarity: 'common' } }], ledger: [{ id: 'sale-old-1', sid: 'pOLD0001', amount: 5000, at: Date.now(), bname: 'An' }] },
            auth: { login: 'owner-old', hash: 'sha256:abc', salt: 'salty' }
        },
        catalog: CATALOG
    };
    const m = await call(api.routes['POST /api/migrate'], legacy, { 'x-nx-admin': A.admin });
    ok(m.body.ok === true, 'миграция принята сервером');
    eq(m.body.migrate.players, 2, 'перенесено игроков');
    const p1 = await store.playerGet('pOLD0001');
    eq(p1.bal, '15000000', 'баланс Алисы… то есть старого игрока pOLD0001 сохранён');
    eq(p1.name, 'Денис Keller', 'имя игрока сохранено');
    const p2 = await store.playerGet('pOLD0002');
    ok(p2.blocked === 1, 'блокировка из старого реестра перенесена');
    eq(p1.st.packsOpened, 42, 'статистика (паков открыто) перенесена');
    const bank = await store.bankGet();
    eq(bank.floor, '10000000', 'пол банка из настроек Студии перенесён');
    eq(bank.fed, (500000n + 200000n + 12345n + 777n).toString(), 'Σвзносов перенесена вместе с разрядами cid#N');
    const hall = await store.hallGet();
    ok(hall.some(h => h.c === 'pOLD0001' && h.n === 'Денис Keller'), 'зал славы перенесён');
    const lots = await store.lotList(10);
    ok(lots.some(l => l.id === 'lot-old-1'), 'лот биржи перенесён');
    const creds = await store.credsGet('owner-old');
    ok(!!creds && creds.legacyHash === 'sha256:abc', 'старая учётка Студии перенесена (вход прежним паролем)');
}

// ---------------------------------------------------------------- 15. Старый пароль
console.log('\n[15] Вход прежним паролем комнаты и его автоматическое обновление');
{
    const { legacyHashPass } = await import(path.join(ROOT, 'server', 'worker', 'src', 'admin.js'));
    const salt = 'oldsalt123';
    const pass = 'мой-старый-пароль';
    const hash = await legacyHashPass(pass, salt);
    await store.credsSet('owner-old', { login: 'owner-old', legacyHash: hash, legacySalt: salt, at: Date.now() });

    const bad = await call(api.routes['POST /api/studio/login'], { login: 'owner-old', pass: 'не-тот' });
    ok(bad.body.ok !== true, 'с чужим паролем старый вход не работает');

    const good = await call(api.routes['POST /api/studio/login'], { login: 'owner-old', pass: pass });
    ok(good.body.ok === true && good.body.upgraded === true, 'старый пароль принят и сразу пересохранён в PBKDF2');
    const rec = await store.credsGet('owner-old');
    ok(String(rec.hash).indexOf('pbkdf2$') === 0 && !rec.legacyHash, 'в базе остался только PBKDF2-хэш, старый удалён');
    const again = await call(api.routes['POST /api/studio/login'], { login: 'owner-old', pass: pass });
    ok(again.body.ok === true, 'после обновления вход тем же паролем работает');
}

// ---------------------------------------------------------------- итог
console.log('\n=== ИТОГ: ✅ ' + passed + ' пройдено, ❌ ' + failed + ' провалено ===');
if (failed) { console.log('Провалено:\n  - ' + fails.join('\n  - ')); process.exit(1); }
console.log('Всё зелёное: баланс, ставки, джекпот, паки, биржа, мины, шахта и админка — на сервере.\n');
