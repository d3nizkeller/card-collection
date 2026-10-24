/* b485: тамагочи оживает — много анимаций.

   Владелец: «тамогочи скучно смотрится геде анимацыя нужно очень многа
   анимаый».

   A. CSS: кейфреймы idle (tama-bob, tama-glow, tama-shadow), болезни
      (tama-sick), реакций (tama-chomp/jump/wiggle/sway/pop), частиц
      (tama-fly), блика полосок (tama-shine); prefers-reduced-motion глушит
      бесконечное; плавные transition ширины полосок и опыта; hover/active
      кнопок.
   B. Разметка панели: сцена tama-stage (свечение + морда + тень + слой
      частиц), полоски tama-bar/tama-bar-fill, кнопки tama-btn, яйцо тоже
      покачивается.
   C. Поведение (jsdom): действие вешает одноразовый класс реакции на морду и
      сыплет частицы в #tama-fx (7 штук, сами удаляются); уровень добавляет
      вторую волну частиц и зовёт launchConfetti; больной питомец носит
      tama-sick; полоски получают ширину по значению; регрессии цен b483.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b485.js
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
    Object.defineProperty(w, 'fetch', { value: () => Promise.resolve({ ok: false, status: 0, text: () => Promise.resolve(''), json: () => Promise.resolve(null) }), configurable: true });
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
    console.log('A. CSS-анимации и теги');
    {
        const css = fs.readFileSync(path.join(ROOT, 'assets', 'app.css'), 'utf8');
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');
        ['tama-bob', 'tama-glow', 'tama-shadow', 'tama-sick', 'tama-chomp', 'tama-jump', 'tama-wiggle', 'tama-sway', 'tama-pop', 'tama-fly', 'tama-shine'].forEach(k =>
            ok(css.includes('@keyframes ' + k), 'кейфрейм ' + k + ' на месте'));
        ok(/@media \(prefers-reduced-motion: reduce\)/.test(css), 'prefers-reduced-motion глушит бесконечные анимации');
        ok(/\.tama-bar-fill\{[^}]*transition:width \.6s/.test(css), 'ширина полосок едет плавно');
        ok(/\.tama-bar-fill::after\{[^}]*animation:tama-shine/.test(css), 'стеклянный блик поверх полосок');
        ok(/\.tama-xp-fill\{transition:width/.test(css), 'полоса опыта тоже плавная');
        ok(/\.tama-btn:hover\{transform:translateY\(-1px\)\}/.test(css) && /\.tama-btn:active\{transform:scale\(\.94\)\}/.test(css), 'кнопки действий: hover-подъём и active-сжатие');
        ok(/\.tama-pet\{[^}]*animation:tama-bob 3s ease-in-out infinite/.test(css), 'питомец дышит в простое');
        const tag = (sw.match(/const VERSION = '(nxmob\d+)';/) || [])[1];
        eq(tag, 'nxmob229', 'sw.js: боевой тег nxmob229');
        eq((html.match(new RegExp(tag, 'g')) || []).length, 8, 'index.html: тег во всех 8 ссылках на assets');
        ok(bp.includes("BUILD_TAG = 'nxmob229'"), 'tools/build.py: BUILD_TAG = nxmob229');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;

    console.log('\nB. Панель: сцена, полоски, кнопки');
    ev(`state.coins = 2000; state.cards = STANDARD_CARDS.map(c => Object.assign({}, c)); state.collection = state.collection || {}; state.cards.slice(0, 6).forEach(c => state.collection[c.id] = 1); tamaAdopt();`);
    {
        const panel = doc.getElementById('tama-panel').innerHTML;
        ['tama-stage', 'tama-glow', 'id="tama-pet"', 'tama-shadow', 'id="tama-fx"', 'tama-bar', 'tama-bar-fill', 'tama-btn', 'tama-xp-fill'].forEach(s =>
            ok(panel.includes(s), 'в панели есть ' + s));
        ok(/tama-pet[^"]*"/.test(panel), 'морда обёрнута в tama-pet (idle-дыхание)');
    }

    console.log('\nC. Реакции и частицы');
    {
        ev(`document.getElementById('tama-fx').innerHTML = '';`);
        ev(`tamaAct('feed')`);
        ok(doc.getElementById('tama-pet').className.includes('tama-act-feed'), 'кормление вешает реакцию tama-act-feed на морду');
        ok(doc.getElementById('tama-fx').children.length === 7, 'над питомцем сыпется 7 частиц (' + doc.getElementById('tama-fx').children.length + ')');
        ev(`tamaAct('play')`);
        ok(doc.getElementById('tama-pet').className.includes('tama-act-play'), 'игра вешает tama-act-play');
        ok(!doc.getElementById('tama-pet').className.includes('tama-act-feed'), 'прошлая реакция не залипает на морде');
        ok(doc.getElementById('tama-fx').children.length >= 7, 'частицы игры добавились к живым');
        ev(`tamaAct('wash'); tamaAct('sleep')`);
        ok(doc.getElementById('tama-pet').className.includes('tama-act-sleep'), 'сон вешает tama-act-sway-реакцию (tama-act-sleep)');
    }
    {
        // уровень: вторая волна частиц + конфетти
        ev(`window.__cf = 0; window.__cfSave = launchConfetti; launchConfetti = function (n) { window.__cf = n; };`);
        ev(`state.tamagotchi.xp = tamaXpNeed(state.tamagotchi.level) - 10;`);
        const fxBefore = ev(`document.getElementById('tama-fx').children.length`);
        ev(`tamaAct('feed')`);
        ok(ev(`window.__cf`) === 60, 'уровень запускает общий конфетти launchConfetti(60)');
        ok(ev(`document.getElementById('tama-fx').children.length`) > fxBefore, 'уровень сыплет вторую волну частиц');
        ev(`launchConfetti = window.__cfSave;`);
    }
    {
        // болезнь: морда носит tama-sick
        ev(`state.tamagotchi.hunger = 5; state.tamagotchi.mood = 5; state.tamagotchi.energy = 5; state.tamagotchi.clean = 5; state.tamagotchi.sick = true; renderTamagotchi();`);
        ok(doc.getElementById('tama-pet').className.includes('tama-sick'), 'больной питомец покачивается и десатурится (tama-sick)');
        ev(`state.tamagotchi.sick = false; state.coins = 2000; tamaAct('heal')`);
        ok(!doc.getElementById('tama-pet').className.includes('tama-sick'), 'после лечения морда без tama-sick');
        ok(doc.getElementById('tama-pet').className.includes('tama-act-heal'), 'лечение даёт пружинный pop');
    }
    {
        // полоски реагируют на значения
        ev(`state.tamagotchi.hunger = 42; renderTamagotchi();`);
        const width = parseFloat(ev(`document.querySelector('#tama-panel .tama-bar-fill').style.width`));
        ok(Math.abs(width - 42) < 0.1, 'ширина полоски = значению характеристики (' + width + '%, transition доедет сам)');
    }

    console.log('\nD. Регрессии b483');
    {
        const c0 = ev('state.coins');
        ev(`tamaAct('wash')`);
        eq(c0 - ev('state.coins'), 10, 'мытьё по-прежнему стоит 10 монет');
        eq(ev(`typeof tamaSpawnFx`), 'function', 'tamaSpawnFx объявлена');
        eq(ev(`typeof TAMA_FX_EMOJI`), 'object', 'наборы эмодзи частиц на месте');
        ok(!ev(`JSON.stringify(TAMA_FX_EMOJI)`).includes(",''"), 'пустых эмодзи-частиц нет');
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
