/* ВОСПРОИЗВЕДЕНИЕ: «число в банке не растёт» (жалоба владельца, 2026-10-13).

   Берём РЕАЛЬНЫЙ облачный документ банка (textdb: nexus-tcg-jackpot-v2),
   кладём его в localStorage и смотрим, что происходит со ставками.

   Запуск:  node tools/repro-jp-frozen.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
// По умолчанию — снимок настоящего облачного документа (tools/_jp_frozen_fixture.json).
// JP_DOC=/tmp/cloud_jp.json — проверить по полному живому документу.
const CLOUD = process.env.JP_DOC || path.join(ROOT, 'tools', '_jp_frozen_fixture.json');

(async () => {
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const dom = new JSDOM(html, {
        runScripts: 'dangerously',
        pretendToBeVisual: true,
        url: 'https://d3nizkeller.github.io/card-collection/',
    });
    const w = dom.window;
    const ev = s => w.eval(s);

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

    // ---- подкладываем ОБЛАЧНОЕ состояние банка до загрузки app.js ----
    const doc = JSON.parse(fs.readFileSync(CLOUD, 'utf8'));
    console.log('документ банка:', CLOUD);
    const jp = doc.jp || doc;
    const ownerCid = (doc.jpc && doc.jpc.by) || Object.keys(jp.led)[0];
    w.localStorage.setItem('nexus_jackpot_cid', ownerCid);       // играем за владельца
    w.localStorage.setItem('nexus_jackpot_v2', JSON.stringify(jp));
    w.localStorage.setItem('nexus_jackpot_cfg', JSON.stringify(doc.jpc || {}));

    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'app.js'), 'utf8');
    w.document.body.appendChild(sc);

    console.log('=== Состояние банка из облака ===');
    console.log('  cid игрока      :', ev('JACKPOT_CID'));
    console.log('  led[cid]        :', ev('jackpot.led[JACKPOT_CID]'));
    console.log('  won[cid]        :', ev('jackpot.won[JACKPOT_CID]'));
    console.log('  jpc.floor       :', ev('jpc.floor'));
    console.log('  jpc.feedBet     :', ev('jpc.feedBet') + ' %');
    console.log('  банк (pool)     :', ev('jackpotPool()'), '=', ev('fmtCoins(jackpotPool())'));
    console.log('  на экране       :', (w.document.getElementById('slots-jackpot') || {}).textContent);

    console.log('\n=== Точность double на таких величинах ===');
    console.log('  1e57 + 10000 === 1e57 ?', w.eval('1e57 + 10000 === 1e57'));
    console.log('  шаг (ulp) у 1e57      :', w.eval('(function(){var x=1e57;while(x+1e41===x)x*=1;var d=1;while(1e57+d===1e57)d*=2;return d;})()'));

    console.log('\n=== 50 ставок по 10k в Слотах (банк должен расти) ===');
    const before = ev('jackpotPool()');
    for (let i = 0; i < 50; i++) ev('jackpotFeed(10000)');
    const after = ev('jackpotPool()');
    console.log('  было            :', before);
    console.log('  стало           :', after);
    console.log('  взнос в реестре  :', ev('jackpot.led[JACKPOT_CID]'));
    console.log('  ВЫРОС ЛИ БАНК?  :', after > before ? 'ДА (+' + (after - before) + ')' : 'НЕТ ❌  ← вот она, жалоба');

    console.log('\n=== Проигрыш 250k → jackpotOnLoss ===');
    const b2 = ev('jackpotPool()');
    ev('jackpotOnLoss(250000)');
    console.log('  банк был/стал   :', b2, '/', ev('jackpotPool()'), ev('jackpotPool()') > b2 ? '(вырос)' : '(НЕ ВЫРОС ❌)');

    console.log('\n=== Ручная правка в Студии: «Поставить банк» 123456789 ===');
    ev('cloudGuest = () => false');
    const b3 = ev('jackpotPool()');
    ev('jpcSetPool(123456789)');
    console.log('  банк был/стал   :', b3, '/', ev('jackpotPool()'), '← ждали 123456789');

    console.log('\n=== Срыв джекпота при банке, прижатом к полу ===');
    const b4 = ev('jackpotPool()');
    const w4 = ev('jackpot.won[JACKPOT_CID]');
    ev('jackpotWin()');
    console.log('  выплата         :', ev('jackpot.won[JACKPOT_CID]') - w4);
    console.log('  банк был/стал   :', b4, '/', ev('jackpotPool()'));
    console.log('  won вырос на    :', ev('jackpot.won[JACKPOT_CID]') - w4, '← «фантомный долг»: банк снова прижат к полу');

    console.log('\n=== Итог ===');
    console.log('  банк сейчас     :', ev('jackpotPool()'), '=', ev('fmtCoins(jackpotPool())'));
    console.log('  починено записей :', ev('jpFixInfo.n'), 'долг покрыт домом:', ev('jpFixInfo.debt'));
    console.log('  raw (сид+взносы−выплаты):', ev('jpRawPool()'), 'сверх сида:', ev('jpExcess()'));
    process.exit(0);
})();
