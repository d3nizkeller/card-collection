/* b430: скрытое открытие Студии — 30 секунд на пароль, иначе Студия закрывается.

   A. Окно пароля показывает обратный отсчёт (число + полоса).
   B. Пароль не введён за лимит → окно закрыто, тост «Студия закрыта», таймер снят.
   C. Закрыли окно сами → таймер снят, ложного срабатывания нет.
   D. Пароль принят → таймер снят, Студия остаётся открытой.
   E. Если вкладка Студии открыта без разблокировки — по таймауту уходим на Магазин.

   Запуск:  node tools/test-b430.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + a + (a === b ? '' : ' (ждём ' + b + ')'));
const sleep = ms => new Promise(r => setTimeout(r, ms));

function boot() {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const dom = new JSDOM(html, {
        runScripts: 'dangerously',
        pretendToBeVisual: true,
        url: 'https://d3nizkeller.github.io/card-collection/',
    });
    const w = dom.window;
    w.HTMLCanvasElement.prototype.getContext = () => null;
    w.HTMLMediaElement.prototype.play = function () { return Promise.resolve(); };
    w.HTMLMediaElement.prototype.pause = function () {};
    Object.defineProperty(w, 'fetch', {
        value: () => Promise.resolve({ ok: false, status: 0, text: () => Promise.resolve(''), json: () => Promise.resolve(null) }),
        configurable: true,
    });
    w.navigator.sendBeacon = () => true;
    w.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} };
    w.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
    w.matchMedia = w.matchMedia || (q => ({ matches: false, media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }));
    w.THREE = new Proxy({}, { get: () => function () { return {}; } });
    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
    w.document.body.appendChild(sc);
    return { w, ev: s => w.eval(s), doc: w.document };
}
const toasts = doc => Array.from((doc.getElementById('toast-container') || { children: [] }).children).map(t => t.textContent).join(' | ');
const modalHidden = doc => doc.getElementById('modal-studio-pass').classList.contains('hidden');

(async () => {
    console.log('\nA. Обратный отсчёт виден');
    const A = boot();
    A.ev('openStudioPassModal()');
    eq(modalHidden(A.doc), false, 'окно пароля открыто');
    eq(A.doc.getElementById('studio-pass-timer').textContent, '30', 'отсчёт стартует с 30 с');
    eq(A.doc.getElementById('studio-pass-bar').style.width, '100%', 'полоса полная');
    await sleep(2200);
    const t2 = Number(A.doc.getElementById('studio-pass-timer').textContent);
    ok(t2 <= 28 && t2 >= 26, 'через ~2 с отсчёт тикает: ' + t2);
    ok(parseFloat(A.doc.getElementById('studio-pass-bar').style.width) < 100, 'полоса убывает');
    A.ev('closeStudioPassModal()');

    console.log('\nB. Не ввели пароль за лимит — Студия закрывается');
    const B = boot();
    B.ev('window.__nxStudioPassSec = 2');
    B.ev('openStudioPassModal()');
    eq(B.doc.getElementById('studio-pass-timer').textContent, '2', 'лимит настраивается (тестам — 2 с)');
    await sleep(2800);
    eq(modalHidden(B.doc), true, 'окно пароля закрыто по таймауту');
    ok(/Пароль не введён за 2 секунд — Студия закрыта/.test(toasts(B.doc)), 'тост: ' + (toasts(B.doc).match(/Пароль не введён[^|]*/) || ['?'])[0]);
    eq(B.ev('studioPassTimer'), null, 'таймер снят после срабатывания');

    console.log('\nC. Закрыли сами — ложного срабатывания нет');
    const C = boot();
    C.ev('window.__nxStudioPassSec = 2');
    C.ev('openStudioPassModal()');
    C.ev('closeStudioPassModal()');
    const tn = C.doc.querySelectorAll('#toast-container > *').length;
    await sleep(2800);
    eq(modalHidden(C.doc), true, 'окно закрыто');
    eq(C.doc.querySelectorAll('#toast-container > *').length, tn, 'таймаут-тост не прилетел после ручного закрытия');

    console.log('\nD. Пароль принят — таймер снят, Студия открыта');
    const D = boot();
    D.ev('window.__nxStudioPassSec = 2');
    D.ev('unlockHiddenTab()'); // в бою жест открывает скрытую вкладку раньше пароля
    D.ev('openStudioPassModal()');
    await D.ev('submitStudioPass()'); // без пароля комнаты в облаке гейт проходит сразу
    eq(D.ev('studioUnlocked'), true, 'студия разблокирована');
    eq(modalHidden(D.doc), true, 'окно пароля закрыто');
    await sleep(2800);
    ok(!/Студия закрыта/.test(toasts(D.doc)), 'таймаут-тоста нет после успешного входа');
    eq(D.doc.getElementById('tab-studio').classList.contains('hidden'), false, 'вкладка Студии осталась открытой');

    console.log('\nE. Студия открыта без разблокировки — таймаут уводит с неё');
    const E = boot();
    E.ev('window.__nxStudioPassSec = 1');
    E.ev('studioUnlocked = false');
    E.ev('document.getElementById("tab-studio").classList.remove("hidden")'); // имитируем открытую вкладку
    E.ev('openStudioPassModal()');
    await sleep(1800);
    eq(E.doc.getElementById('tab-studio').classList.contains('hidden'), true, 'по таймауту ушли со вкладки Студии');
    eq(modalHidden(E.doc), true, 'окно пароля закрыто');

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
