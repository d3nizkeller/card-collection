/* b426: музыка карты — кнопка «Плей/Стоп» в карте, без автозапуска и без каши треков.

   A. Открытие карты с музыкой: трека НЕТ (автозапуск убран), кнопка видна и зовёт включить.
   B. cardMusicToggle(): включает трек (кнопка «Стоп · имя файла»), выключает обратно.
   C. Карта без музыки: кнопки нет; предыдущий трек глушится при открытии.
   D. Взаимоисключение: музыка карты глушит трек пака и наоборот — одновременно
      не больше одного трека.
   E. Закрытие просмотра останавливает трек карты.

   Запуск:  node tools/test-b426.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
const TRACK = 'https://example.com/music/card-track.mp3';
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const eq = (a, b, m) => ok(a === b, m + '  → ' + a + (a === b ? '' : ' (ждём ' + b + ')'));

function boot() {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const dom = new JSDOM(html, {
        runScripts: 'dangerously',
        pretendToBeVisual: true,
        url: 'https://d3nizkeller.github.io/card-collection/',
    });
    const w = dom.window;
    const ctx2d = () => new Proxy({}, {
        get(t, k) {
            if (k === 'canvas') return { width: 256, height: 256, style: {} };
            if (k === 'measureText') return () => ({ width: 10 });
            if (k === 'getImageData') return () => ({ data: new Uint8ClampedArray(4) });
            if (k === 'createLinearGradient' || k === 'createRadialGradient') return () => ({ addColorStop() {} });
            if (k === 'createPattern') return () => null;
            return t[k] !== undefined ? t[k] : (() => {});
        },
        set(t, k, v) { t[k] = v; return true; },
    });
    w.HTMLCanvasElement.prototype.getContext = kind => (kind === '2d' ? ctx2d() : null);
    w.HTMLCanvasElement.prototype.toDataURL = () => 'data:image/png;base64,';
    w.HTMLMediaElement.prototype.play = function () { return Promise.resolve(); };
    w.HTMLMediaElement.prototype.pause = function () {};
    w.HTMLMediaElement.prototype.load = function () {};
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

(async () => {
    const G = boot();
    const ev = G.ev, doc = G.doc;
    ev('(function(){ state.cards = (state.cards || []).slice(); ' +
       'state.cards.push({ id: "cm1", packId: (state.packs[0] || {}).id, name: "Карта с музыкой", rarity: "epic", image: "media/g0.jpg", musicUrl: "' + TRACK + '" }); ' +
       'state.cards.push({ id: "cm2", packId: (state.packs[0] || {}).id, name: "Карта без музыки", rarity: "common", image: "media/s0.jpg" }); ' +
       'state.collection = state.collection || {}; state.collection.cm1 = 1; state.collection.cm2 = 1; })()');

    console.log('\nA. Автозапуска нет, кнопка зовёт включить');
    ev('inspectCard("cm1")');
    eq(doc.getElementById('modal-inspect').classList.contains('hidden'), false, 'просмотр карты открыт');
    eq(ev('CardMusic.url'), '', 'трек карты НЕ стартовал сам');
    const btn = doc.getElementById('inspect-music-btn');
    ok(btn && !btn.classList.contains('hidden'), 'кнопка музыки видна');
    ok(btn && /Включить трек карты/.test(btn.textContent), 'на кнопке: «' + (btn ? btn.textContent.trim() : '') + '»');
    ok((doc.getElementById('inspect-card-render') || {}).innerHTML.length > 50, 'карта отрисована');

    console.log('\nB. Плей/Стоп переключают трек');
    ev('cardMusicToggle()');
    ok(ev('CardMusic.url').indexOf('card-track.mp3') >= 0, 'трек включился: ' + ev('CardMusic.url'));
    ok(/Стоп/.test(btn.textContent) && !/\.mp3/.test(btn.textContent), 'кнопка стала «' + btn.textContent.trim() + '» (b427: без имени файла)');
    ev('cardMusicToggle()');
    eq(ev('CardMusic.url'), '', 'трек выключился');
    ok(/Включить трек карты/.test(btn.textContent), 'кнопка снова зовёт включить');

    console.log('\nC. Карта без музыки: кнопки нет, чужой трек глушится');
    ev('cardMusicToggle()'); // включим трек cm1
    ev('inspectCard("cm2")');
    eq(doc.getElementById('inspect-music-btn').classList.contains('hidden'), true, 'у карты без музыки кнопки нет');
    eq(ev('CardMusic.url'), '', 'трек предыдущей карты остановлен при открытии новой');

    console.log('\nD. Одновременно не больше одного трека');
    ev('inspectCard("cm1")');
    ev('PackMusic.playing = true; PackMusic.audio = { pause: function(){}, volume: 1 }; PackMusic.url = "p.mp3";');
    ev('CardMusic.play("' + TRACK + '")');
    eq(ev('PackMusic.playing'), false, 'музыка карты заглушила трек пака');
    ev('PackMusic.play("https://example.com/music/pack-track.mp3")');
    eq(ev('CardMusic.url'), '', 'трек пака заглушил музыку карты');
    ev('PackMusic.stop()');

    console.log('\nE. Закрытие просмотра останавливает трек');
    ev('inspectCard("cm1")');
    ev('cardMusicToggle()');
    ok(ev('CardMusic.url').length > 0, 'трек играет перед закрытием');
    ev('closeInspectModal()');
    eq(ev('CardMusic.url'), '', 'после закрытия просмотра трек остановлен');

    console.log('\nF. b427: без названия трека + промотка');
    ev('inspectCard("cm1")');
    ev('cardMusicToggle()');
    ok(!/\.mp3|Simple|track/i.test(doc.getElementById('inspect-music-btn').textContent), 'на кнопке нет имени файла: «' + doc.getElementById('inspect-music-btn').textContent.trim() + '»');
    const seek = doc.getElementById('inspect-music-seek');
    ok(seek && !seek.classList.contains('hidden'), 'полоса промотки видна пока трек играет');
    // подменяем audio на управляемый стаб и проверяем полосу/перемотку
    ev('CardMusic.audio = { currentTime: 30, duration: 120, pause: function(){}, paused: false };');
    ev('cardMusicSeekRender()');
    eq(doc.getElementById('inspect-music-cur').textContent, '0:30', 'текущее время 0:30');
    eq(doc.getElementById('inspect-music-dur').textContent, '2:00', 'длительность 2:00');
    ok(doc.getElementById('inspect-music-bar').style.background.indexOf('25%') >= 0, 'полоса на 25% (градиент прогресса)');
    ev('cardMusicSeekTo(0.5)');
    eq(ev('CardMusic.audio.currentTime'), 60, 'промотка на середину (0.5 × 120 = 60)');
    ev('cardMusicSeekTo(2)');
    eq(ev('CardMusic.audio.currentTime'), 120, 'frac > 1 режется в конец');
    ev('CardMusic.audio = { currentTime: 5, duration: NaN, pause: function(){} };');
    ev('cardMusicSeekTo(0.5)');
    eq(ev('CardMusic.audio.currentTime'), 5, 'при NaN-длительности промотка не трогает трек');
    ev('CardMusic.stop()');
    ev('cardMusicSeekRender()');
    eq(seek.classList.contains('hidden'), true, 'без играющего трека полоса скрыта');
    eq(ev('nxTimeFmt(75)'), '1:15', 'формат времени 75 → 1:15');

    console.log('\n' + (fails ? '💥 ' + fails + ' из ' + checks + ' провалено' : '✅ ALL PASS: ' + checks + ' проверок'));
    process.exit(fails ? 1 : 0);
})();
