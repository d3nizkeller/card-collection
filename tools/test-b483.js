/* b483: новая игра «Тамагочи» во вкладке «Игры» — все действия тратят баланс.

   Заявка владельца: «добавь в игры игру тамагочи чтоб все действия тратили
   баланс».

   A. Разметка/теги: девятая плитка режима «Тамагочи» (fa-paw,
      setBattleMode('tama')), лобби #lobby-tama с панелью #tama-panel, сетка
      переключателей grid-cols-9; тег nxmob227 единый.
   B. Исходники app.js: цены действий (яйцо 100, корм 15, игра 20, мытьё 10,
      сон 5, лечение 40), decay-тарифы и офлайн-кап 12 часов; все функции
      модуля объявлены один раз; state.tamagotchi читается из
      nexus_tamagotchi и сохраняется в saveState; setBattleMode переключает
      лобби/плитку и рисует панель; тик 30 секунд.
   C. Поведение (jsdom): покупка яйца списывает 100 и создаёт питомца; каждое
      действие списывает свою цену и меняет характеристики; не хватает монет —
      тост и ноль изменений; больной питомец пускает только к лечению; лечение
      здорового отклоняется; офлайн-тлен считает по lastTs и упирается в кап
      12 часов; среднее <25 → болезнь; опыт и уровень: на новом уровне питомец
      дарит карту (коллекция растёт); renderTamagotchi рисует морду/кнопки с
      ценами; setBattleMode('tama') открывает лобби и подсвечивает плитку.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom NODE_PATH=/tmp/t/node_modules node tools/test-b483.js
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
    console.log('A. Разметка и теги');
    {
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        const bp = fs.readFileSync(path.join(ROOT, 'tools', 'build.py'), 'utf8');
        ok(/<button onclick="setBattleMode\('tama'\)" id="mode-tama-btn"/.test(html), 'плитка режима «Тамагочи» в переключателе игр');
        ok(/id="mode-tama-btn"[\s\S]{0,400}?fa-paw/.test(html), 'плитка с иконкой fa-paw');
        ok(/<div class=\"grid grid-cols-5 sm:grid-cols-9 gap-1 sm:gap-2 w-full py-0.5\">/.test(html), 'сетка переключателей: 5 колонок на телефоне, 9 от sm (b484)');
        ok(html.includes('id="lobby-tama"') && html.includes('id="tama-panel"'), 'лобби #lobby-tama с панелью #tama-panel');
        const tag = (sw.match(/const VERSION = '(nxmob\d+)';/) || [])[1];
        // b484: номер тега не прибиваем к b483 — проверяем единство и что он не ниже nxmob227
        eq((html.match(new RegExp(tag, 'g')) || []).length, 8, 'index.html: тег из sw.js во всех 8 ссылках на assets');
        ok(bp.includes("BUILD_TAG = '" + tag + "'"), 'tools/build.py: BUILD_TAG равен тегу из sw.js');
        ok(Number((tag || '0').replace('nxmob', '')) >= 227, 'тег не ниже nxmob227 (' + tag + ')');
    }

    console.log('\nB. Исходники app.js');
    {
        const app = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
        const count = re => (app.match(re) || []).length;
        ok(app.includes('const TAMA_COST = { adopt: 100, feed: 15, play: 20, wash: 10, sleep: 5, heal: 40 };'), 'цены: яйцо 100, корм 15, игра 20, мытьё 10, сон 5, лечение 40');
        ok(app.includes('const TAMA_OFFLINE_CAP_MIN = 12 * 60;'), 'офлайн-тлен ограничен 12 часами');
        ['tamaAdopt', 'tamaAct', 'tamaSync', 'tamaFace', 'tamaGift', 'tamaSpend', 'tamaBar', 'renderTamagotchi', 'tamaXpNeed'].forEach(fn =>
            eq(count(new RegExp('function ' + fn + '\\(', 'g')), 1, fn + '() объявлена один раз'));
        ok(app.includes("tamagotchi: JSON.parse(LS.getItem('nexus_tamagotchi')"), 'state.tamagotchi читается из localStorage');
        ok(app.includes("LS.setItem('nexus_tamagotchi', JSON.stringify(state.tamagotchi || null));"), 'saveState сохраняет питомца');
        ok(app.includes("const lt = document.getElementById('lobby-tama');"), 'setBattleMode переключает лобби тамагочи');
        ok(app.includes("setModeBtn('mode-tama-btn', m === 'tama', 'lq-on');"), 'плитка подсвечивается в режиме tama');
        ok(app.includes("if (m === 'tama') renderTamagotchi();"), 'вход в режим рисует панель');
        ok(/setInterval\(function \(\) \{[\s\S]{0,300}?\}, 30000\);/.test(app), 'тик 30 секунд: до-тление, сейв, перерисовка');
    }

    const G = boot();
    const w = G.w, ev = G.ev, doc = G.doc;
    const coins = () => ev('state.coins');
    const tama = () => JSON.parse(ev('JSON.stringify(state.tamagotchi)'));
    const toastHtml = () => doc.getElementById('toast-container').innerHTML;
    const clearToast = () => { doc.getElementById('toast-container').innerHTML = ''; };

    console.log('\nC. Покупка яйца и траты баланса');
    eq(tama(), null, 'питомца по умолчанию нет');
    ev('renderTamagotchi()');
    ok(doc.getElementById('tama-panel').innerHTML.includes('Купить яйцо'), 'без питомца панель предлагает купить яйцо');
    {
        ev('state.coins = 50; updateCoinDisplay();');
        clearToast();
        ev('tamaAdopt()');
        eq(tama(), null, 'с 50 монетами яйцо не купить');
        ok(toastHtml().includes('Не хватает монет'), 'тост о нехватке монет');
        eq(coins(), 50, 'баланс не тронут');
    }
    {
        ev('state.coins = 1000; updateCoinDisplay();');
        clearToast();
        ev('tamaAdopt()');
        const t = tama();
        ok(t && t.level === 1 && Math.round(t.hunger) === 80, 'питомец вылупился: уровень 1, характеристики 80');
        eq(coins(), 900, 'яйцо списало 100 монет');
        ok(ev(`localStorage.getItem('nexus_tamagotchi')`) !== null, 'питомец сохранён в localStorage');
        clearToast();
        ev('tamaAdopt()');
        ok(toastHtml().includes('уже живёт'), 'повторная покупка отклоняется');
    }

    console.log('\nD. Действия тратят монеты и меняют характеристики');
    {
        clearToast();
        ev("tamaAct('feed')");
        eq(coins(), 885, 'корм списал 15');
        ok(tama().hunger > 99, 'сытость поднята до капа 100 (' + Math.round(tama().hunger) + ')');
        ev("tamaAct('play')");
        eq(coins(), 865, 'игра списала 20');
        ok(tama().mood > 99 && tama().energy < 80, 'игра: настроение вверх, энергия вниз');
        ev("tamaAct('wash')");
        eq(coins(), 855, 'мытьё списало 10');
        ev("tamaAct('sleep')");
        eq(coins(), 850, 'сон списал 5');
        ok(tama().energy > 60, 'сон поднял энергию');
        eq(tama().xp, 40, 'четыре действия дали 40 опыта');
        clearToast();
        ev("tamaAct('heal')");
        ok(toastHtml().includes('здоров'), 'лечение здорового отклоняется');
        eq(coins(), 850, 'за отказ лечения монеты не взяты');
    }
    {
        ev('state.coins = 10; updateCoinDisplay();');
        clearToast();
        const h = tama().hunger;
        ev("tamaAct('feed')");
        ok(toastHtml().includes('Не хватает монет'), 'дорогое действие при пустом балансе отклоняется тостом');
        eq(coins(), 10, 'баланс не ушёл в минус');
        ok(Math.abs(tama().hunger - h) < 0.01, 'характеристики без оплаты не меняются');
        ev('state.coins = 500; updateCoinDisplay();');
    }

    console.log('\nE. Тление, болезнь, лечение');
    {
        const h0 = tama().hunger;
        ev(`state.tamagotchi.lastTs = Date.now() - 60 * 60 * 1000; tamaSync();`);
        const t = tama();
        ok(Math.abs((h0 - t.hunger) - 30) < 1, 'час офлайна: сытость −30 (' + Math.round(h0) + ' → ' + Math.round(t.hunger) + ')');
        ev(`state.tamagotchi.lastTs = Date.now() - 48 * 60 * 60 * 1000; tamaSync();`);
        const t2 = tama();
        eq(t2.hunger, 0, '48 часов офлайна: сытость у пола (кап тления сработал)');
        eq(t2.sick, true, 'среднее ниже 25 → питомец заболел');
        clearToast();
        const c0 = coins();
        ev("tamaAct('feed')");
        ok(toastHtml().includes('болен'), 'больному доступны не все действия — подсказка про лечение');
        eq(coins(), c0, 'монеты за заблокированное действие не взяты');
        ev("tamaAct('heal')");
        eq(tama().sick, false, 'лечение сняло болезнь');
        ok(tama().hunger > 34.5 && tama().energy > 34.5 && tama().mood > 34.5, 'лечение подтянуло тонус выше порога болезни (без мгновенной повторной болезни)');
        eq(coins(), c0 - 40, 'лечение списало 40 монет');
    }

    console.log('\nF. Уровень и подарок картой');
    {
        const before = ev(`Object.values(state.collection).reduce((s, x) => s + x, 0)`);
        ev(`state.tamagotchi.xp = tamaXpNeed(state.tamagotchi.level) - 10; state.tamagotchi.level = 1;`);
        clearToast();
        ev("tamaAct('wash')"); // +10 xp → уровень 2
        const t = tama();
        eq(t.level, 2, 'опыт действия довёл до уровня 2');
        const after = ev(`Object.values(state.collection).reduce((s, x) => s + x, 0)`);
        ok(after === before + 1, 'подарок за уровень: коллекция +1 карта');
        ok(toastHtml().includes('Уровень 2') && toastHtml().includes('принёс'), 'тост о подарке за уровень');
    }

    console.log('\nG. Панель и переключение режима');
    {
        ev('renderTamagotchi()');
        const panel = doc.getElementById('tama-panel').innerHTML;
        ok(/text-5xl/.test(panel), 'морда питомца на панели');
        ok(panel.includes('Покормить') && panel.includes('15'), 'кнопка «Покормить» с ценой 15');
        ok(panel.includes('Лечить') && panel.includes('40'), 'кнопка «Лечить» с ценой 40');
        ok(panel.includes('Сытость') && panel.includes('Чистота'), 'полоски характеристик на панели');
        ev("setBattleMode('tama')");
        eq(doc.getElementById('lobby-tama').classList.contains('hidden'), false, 'лобби тамагочи открыто');
        eq(doc.getElementById('lobby-arena').classList.contains('hidden'), true, 'лобби арены скрыто');
        ok(doc.getElementById('mode-tama-btn').className.includes('lq-on'), 'плитка «Тамагочи» подсвечена');
        ev("setBattleMode('arena')");
        eq(doc.getElementById('lobby-tama').classList.contains('hidden'), true, 'выход из режима прячет лобби');
    }

    console.log('\n' + (fails ? '❌ ПРОВАЛОВ: ' + fails + ' из ' + checks : '✅ Все проверки пройдены: ' + checks));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('ТЕСТ УПАЛ:', e && e.stack || e); process.exit(2); });
