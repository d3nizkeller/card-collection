/* b481: экспорт карты сам находит арт и АВТОМАТИЧЕСКИ сохраняет его на GitHub.

   Жалоба владельца: тост «Не удалось скачать карточку: NetworkError…» —
   «чего она автоматически не сохраняет на гитхаб?».

   A. Исходники app.js: nxExportArtBlob с цепочкой копий арта (мастер →
      миниатюры t3/t2/t → вшитый NX_EMBED_MEDIA → апгрейд http→https →
      исходная ссылка); автосохранение в media/ через nxGhPushMedia с
      перезаписью card.image, пометкой nxMediaPushedSet, saveState и
      публикацией в комнату; миниатюры мастером НЕ сохраняются; уточнённый
      тост ошибки; тег nxmob225 единый.
   B. Поведение (jsdom): цепочка реально идёт по копям и добирается до
      https-версии http-ссылки (mixed-content кейс владельца); когда копий нет
      — ошибка со списком попыток; с токеном GitHub добытый арт уезжает в
      media/ и ссылка карты перезаписывается; без токена — тихо, карта не
      трогается; лицо карты и скрытие b475 не задеты.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b481.js
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
    w.HTMLCanvasElement.prototype.getContext = () => null; // экспорт уходит в ветку тоста, как на машине без GPU
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
    console.log('A. Исходники assets/app.js');
    {
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');
        const idx = s => app.indexOf(s);

        eq((app.match(/async function nxExportArtBlob\(/g) || []).length, 1, 'nxExportArtBlob объявлена один раз');
        ok(idx('grab(main, \'master\'') < idx("'thumb-t3'") && idx("'thumb-t3'") < idx("'thumb-t2'") && idx("'thumb-t2'") < idx("'thumb-t']") && idx("'thumb-t']") < idx("'embed'") && idx("'embed'") < idx("'https-upgrade'") && idx("'https-upgrade'") < idx("'raw'"),
           'цепочка копий: мастер → t3 → t2 → t → вшитый → https-апгрейд → напрямую');
        ok(app.includes("if (String(main).indexOf('http://') === 0)"), 'http-ссылка апгрейдится до https (mixed-content кейс владельца)');
        ok(app.includes("['embed', 'https-upgrade', 'raw'].indexOf(art.src) >= 0"), 'автосохранение — только для полных копий, не для миниатюр');
        ok(/nxGhPushMedia\(nxGhRepoName\(\), \[\{ name: name, blob: art\.blob \}\]/.test(app), 'копия арта коммитится в media/ тем же механизмом, что ручная загрузка');
        ok(app.includes('card.image = nxMediaPublicUrl(name);'), 'ссылка карты перезаписывается на свежую media/…');
        ok(app.includes('nxMediaPushedSet()') && app.includes('nxMediaSavePushed(s)'), 'файл помечается отправленным (повторно не пушится)');
        ok(/saveState\(\);[\s\S]{0,80}?cloudPublishSoon\(\);/.test(app.slice(idx('b481: АВТОСОХРАНЕНИЕ'))), 'состояние сохраняется и публикуется в комнату');
        ok(app.includes('Арт автоматически сохранён на GitHub: media/'), 'тост об автосохранении');
        ok(/if \(typeof nxGhToken === 'function' && nxGhToken\(\)/.test(app), 'без сохранённого токена автосохранение тихо пропускается');
        ok(app.includes('function nxArtBlobUrl(url)'), 'nxArtBlobUrl осталась как совместимая обёртка');
        ok(app.includes('внешняя ссылка без CORS или http:// на https-странице'), 'тост ошибки объясняет обе частые причины');

        const tag = (sw.match(/const VERSION = '(nxmob\d+)';/) || [])[1];
        // b482: номер тега не прибиваем к b481 — проверяем единство: боевой тег из
        // sw.js повторён во всех 8 ссылках index.html и равен BUILD_TAG, не ниже nxmob225
        eq((html.match(new RegExp(tag, 'g')) || []).length, 8, 'index.html: тег из sw.js во всех 8 ссылках на assets');
        ok(bp.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG равен тегу из sw.js');
        ok(Number((tag || '0').replace('nxmob', '')) >= 225, 'тег не ниже nxmob225 (' + tag + ')');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;

    console.log('\nB. Цепочка копий арта (jsdom, fetch под контролем)');
    const id = JSON.parse(ev(`(function(){
        try { SoundFX.play = function(){}; } catch (e) {}
        state.cards = STANDARD_CARDS.map(c => Object.assign({}, c));
        state.collection = state.collection || {};
        const a = state.cards[0];
        a.name = 'Внешняя карта'; a.atk = 5; a.hp = 6;
        a.image = 'http://ext.example/art.png';          // mixed-content кейс
        state.collection[a.id] = 1;
        return JSON.stringify(a.id);
    })()`));
    {
        ev(`window.__fetchLog = [];
            fetch = function (url, opts) {
                window.__fetchLog.push(String(url));
                if (String(url).indexOf('https://ext.example/') === 0) {
                    return Promise.resolve({ ok: true, status: 200, blob: function () { return Promise.resolve(new Blob(['pngbytes'], { type: 'image/png' })); } });
                }
                return Promise.reject(new Error('NetworkError when attempting to fetch resource.'));
            };`);
        const art = await ev(`nxExportArtBlob(state.cards.find(c => c.id === ${JSON.stringify(id)})).then(a => ({ src: a.src, size: a.blob.size }))`);
        eq(art.src, 'https-upgrade', 'http-ссылка: байты добыты из https-версии');
        eq(art.size, 8, 'blob добыт (8 байт заглушки)');
        const log = JSON.parse(ev(`JSON.stringify(window.__fetchLog)`));
        ok(log[0] === 'http://ext.example/art.png', 'первой пробуется исходная ссылка (' + log[0] + ')');
        ok(log.some(u => u.indexOf('https://ext.example/art.png') === 0), 'https-апгрейд действительно дёргается');
        ok(log.length >= 2 && log.length <= 6, 'миниатюр у внешней ссылки нет — лишних попыток не делается (' + log.length + ')');
    }
    {
        ev(`fetch = function () { return Promise.reject(new Error('NetworkError when attempting to fetch resource.')); };`);
        let msg = '';
        try { await ev(`nxExportArtBlob(state.cards.find(c => c.id === ${JSON.stringify(id)}))`); } catch (e) { msg = String(e && e.message || e); }
        ok(/арт недоступен ни в одной копии/.test(msg), 'копий нет вообще — ошибка со списком попыток');
        ok(/попыток: \d+/.test(msg), 'в ошибке видно число попыток (' + msg.slice(-24) + ')');
    }

    console.log('\nC. Автосохранение арта на GitHub');
    {
        // с токеном: копия уезжает в media/, ссылка карты перезаписывается
        ev(`try { localStorage.setItem('nx_gh_token', 'test-token'); } catch (e) {}
            window.__push = null;
            nxGhPushMedia = function (repo, items, okc, failc) { window.__push = { repo: repo, names: items.map(i => i.name), blobs: items.map(i => i.blob) }; okc(); };
            nxGhRepoName = function () { return 'owner/repo'; };
            Image = class { set src(v) { this._s = v; setTimeout(() => { if (this.onload) this.onload(); }, 0); } get src() { return this._s; } };
            fetch = function (url) {
                if (String(url).indexOf('https://ext.example/') === 0) return Promise.resolve({ ok: true, status: 200, blob: function () { return Promise.resolve(new Blob(['pngbytes'], { type: 'image/png' })); } });
                return Promise.reject(new Error('NetworkError'));
            };`);
        await ev(`downloadCardPng(${JSON.stringify(id)})`);
        const push = JSON.parse(ev(`JSON.stringify(window.__push)`));
        ok(push && push.names.length === 1, 'nxGhPushMedia вызван ровно с одним файлом');
        ok(push && /^card_[a-z0-9]+_auto\.png$/.test(push.names[0]), 'имя файла в media/ — card_<время>_auto.png (' + (push && push.names[0]) + ')');
        const img = ev(`state.cards.find(c => c.id === ${JSON.stringify(id)}).image`);
        ok(img.indexOf('media/') >= 0 && img.indexOf('_auto.png') >= 0, 'ссылка карты перезаписана на media/… (' + img.slice(-28) + ')');
        ok(doc.getElementById('toast-container').innerHTML.includes('Арт автоматически сохранён на GitHub'), 'тост об автосохранении показан');
    }
    {
        // без токена: тихо, карта не трогается
        ev(`try { localStorage.removeItem('nx_gh_token'); } catch (e) {}
            window.__push = null;
            state.cards.find(c => c.id === ${JSON.stringify(id)}).image = 'http://ext.example/art.png';`);
        await ev(`downloadCardPng(${JSON.stringify(id)})`);
        eq(ev(`window.__push`), null, 'без токена ничего не пушится');
        eq(ev(`state.cards.find(c => c.id === ${JSON.stringify(id)}).image`), 'http://ext.example/art.png', 'без токена ссылка карты не трогается');
    }
    {
        // всё недоступно: понятный тост, игра не падает
        ev(`fetch = function () { return Promise.reject(new Error('NetworkError when attempting to fetch resource.')); };
            document.getElementById('toast-container').innerHTML = '';`);
        await ev(`downloadCardPng(${JSON.stringify(id)})`);
        const toast = doc.getElementById('toast-container').innerHTML;
        ok(toast.includes('Не удалось скачать карточку'), 'тост об ошибке на месте');
        ok(toast.includes('Загрузить с устройства'), 'в тосте совет залить арт кнопкой');
        ok(toast.includes('http:// на https-странице'), 'в тосте объяснение mixed-content причины');
    }

    console.log('\nD. Регрессии');
    {
        eq(ev(`cardLayoutOf({ layout: { statsPos: 'hide' } }).statsPos`), 'hide', 'скрытие статов b475 работает');
        eq(ev(`cardLayoutOf({ layout: { statsShape: 'star', statsSize: 'lg' } }).statsShape`), 'star', 'формы/размеры b477-b478 работают');
        ok(typeof ev(`nxCardFaceCanvas`) === 'function', 'экспортный canvas-рендерер на месте');
        ok(typeof ev(`downloadCardPngOfForm`) === 'function', 'кнопка формы b479 на месте');
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
