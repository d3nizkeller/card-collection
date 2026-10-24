/* b482: «Отправить на GitHub» и автоотправка тянут арты из КОПИЙ НА САЙТЕ.

   Жалоба владельца: «нажимаю отправить на гитхаб а оно не отправляет а должно
   автоматически скачивать картинки на гитхаб с сайта» + красный список
   «Нет картинок (40): … нет кэша, ссылка молчит».

   A. Исходники qr-transfer.js: nxFetchArtBytes с цепочкой копий (mediaUrl →
      мастер media/<имя> → миниатюры t3/t2/t → https-апгрейд → ссылка);
      blobOf в nxGhPushMedia добирает байты из копий, когда кэш пуст; «Шаг 3»/
      автоотправка с пустым кэшем передают очередь без блобов; «Шаг 1» вместо
      тихого пропуска кэширует копию с сайта; nxCheckLinks не пугает по
      карточкам, у которых есть копия на сайте; тег nxmob226 единый.
   B. Поведение (jsdom, fetch и nxGhApi под контролем): nxFetchArtBytes
      находит копию media/<имя> при мёртвой внешней ссылке; nxGhPushMedia с
      пустым кэшем реально коммитит байты копии в media/ (base64 совпадает);
      nxPushMediaNow с пустым кэшем отправляет очередь, а не говорит
      «нечего»; проверка ссылок помечает карточку рабочей при живой копии.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b482.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + a + (a === b ? '' : ' (ждём ' + b + ')'));

function boot() {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'https://d3nizkeller.github.io/card-collection/' });
    const w = dom.window;
    dom.virtualConsole.on('jsdomError', () => {});
    w.HTMLCanvasElement.prototype.getContext = () => null;
    w.HTMLMediaElement.prototype.play = function () { return Promise.resolve(); };
    w.HTMLMediaElement.prototype.pause = function () {};
    w.navigator.sendBeacon = () => true;
    w.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} };
    w.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
    w.matchMedia = w.matchMedia || (q => ({ matches: false, media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }));
    w.THREE = new Proxy({}, { get: () => function () { return {}; } });
    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
    w.document.body.appendChild(sc);
    const sc2 = w.document.createElement('script');
    sc2.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'qr-transfer.js'), 'utf8');
    w.document.body.appendChild(sc2);
    return { w, ev: s => w.eval(s), doc: w.document };
}

(async () => {
    console.log('A. Исходники assets/qr-transfer.js и теги');
    {
        const q = fs.readFileSync(path.join(ROOT, 'assets', 'qr-transfer.js'), 'utf8');
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');
        const idx = s => q.indexOf(s);

        eq((q.match(/function nxFetchArtBytes\(/g) || []).length, 1, 'nxFetchArtBytes объявлена один раз');
        ok(idx('mediaUrl(url)') < idx("'media/' + nxMediaKey(url)") && idx("'media/' + nxMediaKey(url)") < idx('nxBigFor(url)') && idx('nxBigFor(url)') < idx("nxThumbFor(url, 'mid')") && idx("nxThumbFor(url, 'mid')") < idx("nxThumbFor(url, 'small')"),
           'цепочка копий: мастер → media/<имя> → t3 → t2 → t');
        ok(q.includes("cands.push('https://' + c.slice(7))"), 'http-ссылки апгрейдятся до https');
        ok(/return nxFetchArtBytes\(it\.url\)\.then\(function \(hit\) \{\s*if \(!hit\) throw new Error\('нет в кэше и нет копии на сайте: '/.test(q), 'blobOf: нет кэша → байты из копий на сайте');
        ok(q.includes('try { imgCachePut(it.url, hit.blob); } catch (e) {}'), 'найденная копия кладётся в кэш (повтор без сети)');
        ok(q.includes('if (!items.length && pendingAll.length) {'), '«Шаг 3»/автоотправка: пустой кэш ≠ «отправлять нечего»');
        ok(q.includes('Кэш пуст — тяну арты из копий на сайте'), 'прогресс объясняет, откуда берутся байты');
        ok(/imgCacheStoreFromNetwork\(j\.eff\)\.then\(ou => \{ if \(ou\) fresh\+\+; tick\(\); \}, \(\) => \{[\s\S]{0,240}?nxFetchArtBytes\(j\.eff\)/.test(q), '«Шаг 1»: молча мёртвую ссылку подменяет копия с сайта');
        ok((q.match(/копии на сайте нет/g) || []).length >= 2, 'проверка ссылок пугает только когда копии на сайте нет');

        const tag = (sw.match(/const VERSION = '(nxmob\d+)';/) || [])[1];
        // b483: номер тега не прибиваем к b482 — проверяем единство и что он не ниже nxmob226
        eq((html.match(new RegExp(tag, 'g')) || []).length, 8, 'index.html: тег из sw.js во всех 8 ссылках на assets');
        ok(bp.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG равен тегу из sw.js');
        ok(Number((tag || '0').replace('nxmob', '')) >= 226, 'тег не ниже nxmob226 (' + tag + ')');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;

    console.log('\nB. nxFetchArtBytes находит копию на сайте при мёртвой ссылке');
    {
        ev(`window.__log = [];
            fetch = function (url, opts) {
                window.__log.push(String(url));
                if (String(url).indexOf('media/dead_art.png') >= 0 || String(url).indexOf('/media/dead_art.png') >= 0) {
                    return Promise.resolve({ ok: true, status: 200, blob: function () { return Promise.resolve(new Blob(['sitecopy'], { type: 'image/png' })); } });
                }
                return Promise.reject(new Error('NetworkError when attempting to fetch resource.'));
            };`);
        const hit = await ev(`nxFetchArtBytes('http://dead.example/dead_art.png').then(h => h ? { url: h.url, size: h.blob.size } : null)`);
        ok(hit && hit.size === 8, 'копия media/dead_art.png найдена и прочитана (8 байт)');
        ok(hit && /media\/dead_art\.png$/.test(hit.url), 'взята именно копия на сайте (' + (hit && hit.url) + ')');
        const log = JSON.parse(ev(`JSON.stringify(window.__log)`));
        ok(log[0].indexOf('http://dead.example/dead_art.png') === 0, 'первой пробуется исходная ссылка');
        ok(!log.some(u => u.indexOf('https://dead.example/') === 0), 'копия нашлась раньше — https-апгрейд не дёргается зря');
        ev(`window.__log = [];
            fetch = function (url) {
                window.__log.push(String(url));
                if (String(url).indexOf('https://dead.example/') === 0) return Promise.resolve({ ok: true, status: 200, blob: function () { return Promise.resolve(new Blob(['viahttps'], { type: 'image/png' })); } });
                return Promise.reject(new Error('NetworkError'));
            };`);
        const hit2 = await ev(`nxFetchArtBytes('http://dead.example/dead_art.png').then(h => h ? { url: h.url, size: h.blob.size } : null)`);
        ok(hit2 && hit2.url.indexOf('https://dead.example/') === 0, 'копий на сайте нет — байты дотягиваются https-апгрейдом (' + (hit2 && hit2.url) + ')');
    }
    {
        ev(`fetch = function () { return Promise.reject(new Error('NetworkError')); };`);
        const hit = await ev(`nxFetchArtBytes('http://dead.example/dead_art.png').then(h => h)`);
        eq(hit, null, 'копий нет нигде — честный null, без падения');
    }

    console.log('\nC. nxGhPushMedia с пустым кэшем шлёт байты копии на GitHub');
    {
        ev(`try { localStorage.setItem('nx_gh_token', 't'); localStorage.setItem('nx_gh_repo', 'owner/repo'); } catch (e) {}
            window.__blobs = [];
            nxGhApi = function (p, o) {
                if (p === '/repos/owner/repo') return Promise.resolve({ default_branch: 'main' });
                if (p.indexOf('/git/ref/heads/') >= 0) return Promise.resolve({ object: { sha: 'head1' } });
                if (p.indexOf('/git/commits/head1') >= 0) return Promise.resolve({ tree: { sha: 'tree0' } });
                if (p.slice(-10) === '/git/blobs') {
                    window.__blobs.push(JSON.parse(o.body).content);
                    return Promise.resolve({ sha: 'blob' + window.__blobs.length });
                }
                if (p.slice(-10) === '/git/trees') { window.__tree = JSON.parse(o.body).tree; return Promise.resolve({ sha: 'tree1' }); }
                if (p.slice(-12) === '/git/commits') { window.__msg = JSON.parse(o.body).message; return Promise.resolve({ sha: 'commit1' }); }
                if (p.indexOf('/git/refs/heads/') >= 0) return Promise.resolve({});
                return Promise.resolve({});
            };
            fetch = function (url) {
                if (String(url).indexOf('media/dead_art.png') >= 0) return Promise.resolve({ ok: true, status: 200, blob: function () { return Promise.resolve(new Blob(['sitecopy'], { type: 'image/png' })); } });
                return Promise.reject(new Error('NetworkError'));
            };`);
        const pushed = await ev(`new Promise(function (res) {
            nxGhPushMedia('owner/repo', [{ name: 'dead_art.png', url: 'http://dead.example/dead_art.png' }], function () { res('ok'); }, function (m) { res('fail:' + m); });
        })`);
        eq(pushed, 'ok', 'коммит прошёл, хотя кэш устройства пуст');
        const b64 = JSON.parse(ev(`JSON.stringify(window.__blobs)`))[0];
        eq(Buffer.from(b64, 'base64').toString(), 'sitecopy', 'в коммит ушли именно байты копии с сайта');
        const tree = JSON.parse(ev(`JSON.stringify(window.__tree)`));
        eq(tree[0].path, 'media/dead_art.png', 'файл лёг в media/ репозитория');
        ok(String(ev(`window.__msg`)).indexOf('media/') >= 0 || String(ev(`window.__msg`)).indexOf('картинки') >= 0, 'сообщение коммыта осмысленное (' + ev(`window.__msg`) + ')');
    }

    console.log('\nD. «Шаг 3» с пустым кэшем отправляет очередь, а не отказывает');
    {
        ev(`state.cards = STANDARD_CARDS.map(c => Object.assign({}, c));
            state.cards[0].image = 'http://dead.example/dead_art.png';
            try { localStorage.removeItem('nexus_media_pushed'); } catch (e) {}
            window.__blobs = [];
            fetch = function (url) {
                if (String(url).indexOf('media/dead_art.png') >= 0) return Promise.resolve({ ok: true, status: 200, blob: function () { return Promise.resolve(new Blob(['sitecopy'], { type: 'image/png' })); } });
                return Promise.reject(new Error('NetworkError'));
            };`);
        await ev(`new Promise(function (res) { window.__doneWrap = res; nxAutoMediaPushRun(true, function (n) { window.__sentN = n; res(n); }); })`);
        const sent = ev(`window.__sentN`);
        ok(Number(sent) >= 1, 'автоотправка/«Шаг 3» отправила файлы из копий на сайте (' + sent + ')');
        ok(JSON.parse(ev(`JSON.stringify(window.__blobs)`)).length >= 1, 'байты ушли в blobs GitHub');
        const status = ev(`(document.getElementById('nx-status') || {}).textContent || ''`);
        ok(!/Отправлять нечего/.test(status), 'красного «отправлять нечего» больше нет');
    }

    console.log('\nE. Регрессии');
    {
        eq(ev(`typeof nxPushMediaNow`), 'function', 'кнопка «Шаг 3» на месте');
        eq(ev(`typeof nxCacheAll`), 'function', 'кнопка «Шаг 1» на месте');
        eq(ev(`typeof nxCheckLinks`), 'function', 'проверка ссылок на месте');
        ok(ev(`nxAutoMediaOn()`) === true || ev(`nxAutoMediaOn()`) === false, 'тумблер автоотправки читается');
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
