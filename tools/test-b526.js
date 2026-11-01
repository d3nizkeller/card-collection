/* b526: «Шаг 1. Скачать все картинки» и «Шаг 3. Отправить на GitHub» чинятся реально.

   Жалоба владельца: «почини скачку и отправку на гитхаб» (скрин панели из трёх
   шагов). Разбор кода показал три дефекта конвейера:

   A. МЁРТВЫЙ ФОЛБЭК В ШАГЕ 1. imgCacheStoreFromNetwork() глотает любую ошибку
      внутри и возвращает null (никогда не reject). Фолбэк b482 (копии байтов с
      сайта: media/, миниатюры, https-апгрейд) висел на reject-обработчике —
      не срабатывал НИКОГДА: молчащая/CORS-закрытая ссылка помечалась
      «скачанной», кэш оставался пустым, Шаг 3 потом не находил байтов.
      Фолбэк переехал на null-результат (и в nxAutoCacheOnce тоже).
   B. ЗАВИСАНИЕ БЕЗ ТАЙМАУТА. fetch в конвейере жил без предохранителя:
      «молчащий» хост (TCP принял, ответа нет) держал очередь до таймаута
      браузера (минуты) — кнопка Шага 1 заблокирована, прогресс стоит,
      автоотправка вязнет. Новый nxWithTimeout(): 25 с на ступень загрузки,
      20 с на fetch/blob в nxFetchArtBytes.
   C. ОДИНОЧНЫЕ КОММИТЫ В ШАГЕ 3. Копии с сайта добирались в пачку только при
      ПОЛНОСТЫВ пустом кэше; с полупустым кэшем коммит уносил 1-2 файла,
      очередь растягивалась сотнями одиночных коммитов (в истории репо
      13 коммитов по 1 файлу за 20 минут). Пачка теперь всегда добирается до
      cap: кэш + копии сайта.

   Проверки: исходники (паттерны + единый тег nxmob273) и поведение в jsdom:
   фолбэк Шага 1 реально кладёт байты копии в кэш после null из store;
   nxWithTimeout гасит висячий промис; Шаг 3 добирает пачку до cap из копий
   сайта при полупустом кэше.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom node tools/test-b526.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };

function boot() {
    const html = '<!doctype html><html><body>'
        + '<button id="nx-cache-all-btn"></button><button id="nx-push-media-btn"></button>'
        + '<input id="nx-gh-token"><input id="nx-gh-repo">'
        + '<div id="nx-status-bar"></div><div id="nx-progress-wrap"><div id="nx-progress-label"></div><div id="nx-progress-bar"></div></div>'
        + '</body></html>';
    const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'https://d3nizkeller.github.io/card-collection/' });
    const w = dom.window;
    dom.virtualConsole.on('jsdomError', () => {});
    // мини-окружение вместо app.js: qr-transfer.js обращается к этим глобалам
    const mem = {};
    w.LS = {
        getItem: k => (Object.prototype.hasOwnProperty.call(mem, k) ? mem[k] : null),
        setItem: (k, v) => { mem[k] = String(v); },
        removeItem: k => { delete mem[k]; }
    };
    w.showToast = (m, k) => { w.__toasts.push([String(m), k || 'success']); };
    w.__toasts = [];
    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'qr-transfer.js'), 'utf8');
    w.document.body.appendChild(sc);
    w.nxInStudio = () => true; // тосты владельца пишутся в __toasts
    return w;
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
    console.log('A. Исходники assets/qr-transfer.js и теги сборки');
    {
        const q = fs.readFileSync(path.join(ROOT, 'assets', 'qr-transfer.js'), 'utf8');
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');

        ok(/function nxWithTimeout\(p, ms\)/.test(q), 'есть предохранитель nxWithTimeout');
        ok(q.indexOf('nxWithTimeout(imgCacheStoreFromNetwork(j.eff), 25000).then(ou => {') >= 0,
            'Шаг 1: фолбэк на копиях сайта повешен на null-результат store, а не на мёртвый reject');
        ok(q.indexOf('imgCacheStoreFromNetwork(j.eff).then(ou => { if (ou) fresh++; tick(); }, () => {') < 0,
            'Шаг 1: старая мёртвая связка (reject-фолбэк) удалена');
        ok(q.indexOf('nxWithTimeout(imgCacheStoreFromNetwork(u), 25000).then(ou => {') >= 0,
            'авто-кэш: тот же фолбэк и предохранитель в nxAutoCacheOnce');
        ok(q.indexOf('nxWithTimeout(fetch(u, { mode: \'cors\' }), 20000)') >= 0,
            'nxFetchArtBytes: fetch с предохранителем 20 с');
        ok(q.indexOf('if (items.length < cap && pendingAll.length)') >= 0,
            'Шаг 3: пачка добирается до cap копиями с сайта даже при полупустом кэше');
        ok(!/nxmob27[0-3]/.test(html) && /nxmob274/.test(html), 'index.html: текущий тег nxmob274 (клиенты перечитают js)');
        ok(/const VERSION = 'nxmob274';/.test(sw), 'sw.js: новый кэш ассетов nxmob274');
        ok(/BUILD_TAG = 'nxmob274'/.test(bp), 'build.py: BUILD_TAG nxmob274');
    }

    console.log('B. nxWithTimeout гасит висячий промис');
    {
        const w = boot();
        const never = new Promise(() => {});
        let rejected = false;
        await w.nxWithTimeout(never, 30).then(() => {}, () => { rejected = true; });
        ok(rejected, 'висячий промис отклонён по таймауту');
        const fast = w.nxWithTimeout(Promise.resolve(7), 30);
        ok((await fast) === 7, 'быстрый промис проходит без задержки');
        w.close();
    }

    console.log('C. Шаг 1: null из store → байты добираются копией с сайта');
    {
        const w = boot();
        const puts = [];
        w.nxAllMediaUrls = () => ['https://dead-host.example/art1.jpg'];
        w.mediaUrl = u => u;
        w.imgCacheObjUrl = () => Promise.resolve(null);          // кэш пуст
        w.imgCacheStoreFromNetwork = () => Promise.resolve(null); // «молчащая» ссылка: null без reject
        w.imgCachePut = (u, b) => { puts.push(u); return Promise.resolve(true); };
        w.nxFetchArtBytes = u => Promise.resolve({ blob: new w.Blob(['bytes'], { type: 'image/jpeg' }), url: u });
        w.nxCacheAll();
        await sleep(120);
        ok(puts.length === 1 && puts[0] === 'https://dead-host.example/art1.jpg',
            'копия с сайта положена в кэш устройства (раньше фолбэк не срабатывал)');
        const done = w.__toasts.filter(t => t[0].indexOf('Готово: коллекция закэширована (1 новых') === 0);
        ok(done.length === 1, 'финиш-тост считает арт новым: ' + (done[0] ? done[0][0] : w.__toasts.map(t => t[0]).join(' | ')));
        const btn = w.document.getElementById('nx-cache-all-btn');
        ok(!btn.disabled, 'кнопка Шага 1 разблокирована после финиша');
        w.close();
    }

    console.log('D. Шаг 3: полупустой кэш → пачка до cap, а не 1 файл');
    {
        const w = boot();
        let committed = null;
        w.nxGhToken = () => 'token-test';
        w.nxGhRepoName = () => 'd3nizkeller/card-collection';
        w.nxPendingMediaList = () => [1, 2, 3, 4, 5].map(i => ({ name: 'card_' + i + '.jpg', url: 'https://x/media/card_' + i + '.jpg' }));
        w.nxCollectPendingMedia = () => Promise.resolve([{ name: 'card_1.jpg', url: 'https://x/media/card_1.jpg', blob: new w.Blob(['1']) }]);
        w.nxGhPushMedia = (repo, items, okCb) => { committed = items; okCb(); };
        w.nxPushMediaNow();
        await sleep(80);
        ok(committed && committed.length === 5, 'в коммит ушли все 5 (1 кэш + 4 копии сайта), а не 1: ' + (committed ? committed.length : 'нет коммита'));
        const names = (committed || []).map(i => i.name);
        ok(new Set(names).size === names.length, 'имена в пачке без дублей');
        w.close();
    }

    console.log(fails ? ('\n❌ b526: провалов ' + fails + ' из ' + checks) : ('\n✅ b526: все ' + checks + ' проверок зелёные'));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('crash:', e); process.exit(1); });
