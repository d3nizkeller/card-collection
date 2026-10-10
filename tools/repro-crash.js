/* Репро краша сайта во время игры.
   Запуск: node tools/repro-crash.js <url> [режим: loop|push|both]
   Что меряем:
     1) сколько WebGL-контекстов живо и сколько из них РЕАЛЬНО рисуют кадры,
        когда игрок ушёл на другой экран (утечка rAF-циклов);
     2) сколько памяти/времени съедает авто-отправка картинок в GitHub
        (nxCollectPendingMedia держит ВСЕ блобы сразу + base64 склейкой). */
// playwright-core ищется здесь (переопределите PW_PATH, если он установлен иначе):
//   npm i playwright-core --prefix /tmp/pw && npx playwright install chromium
const PW = process.env.PW_PATH || '/tmp/pw/node_modules/playwright-core';
const { chromium, devices } = require(PW);

const URL = process.argv[2] || 'http://127.0.0.1:8123/index.html';
const MODE = process.argv[3] || 'both';
const GH = 'https://d3nizkeller.github.io/card-collection/';
const GH_STATS = { calls: 0, bytes: 0, worst: 0 };
let BLOBS = 0;

const INSTR = `
window.__nxLive = new Set(); window.__nxMade = 0; window.__nxDropped = new Set();
window.__renderCount = new Map(); window.__liveRenderers = new Set();
(function () {
  var tryHook = function () {
    if (!window.THREE || !THREE.WebGLRenderer) { return setTimeout(tryHook, 50); }
    var Orig = THREE.WebGLRenderer;
    function Hooked(opts) {
      var r = new Orig(opts);
      r.__id = ++window.__nxMade;
      window.__nxLive.add(r.__id);
      var d = r.dispose.bind(r);
      r.dispose = function () { window.__nxLive.delete(r.__id); window.__nxDropped.add(r.__id); try { return d(); } catch (e) {} };
      var proto = Object.getPrototypeOf(r);
      if (proto && proto.render && !proto.__nxHooked) {
        proto.__nxHooked = 1;
        var or = proto.render;
        proto.render = function () {
          if (this.__id) { window.__liveRenderers.add(this.__id); window.__renderCount.set(this.__id, (window.__renderCount.get(this.__id) || 0) + 1); }
          return or.apply(this, arguments);
        };
      }
      return r;
    }
    Hooked.prototype = Orig.prototype;
    THREE.WebGLRenderer = Hooked;
    window.__nxHooked = 1;
  };
  tryHook();
})();
window.__lt = { count: 0, total: 0, worst: 0 };
try { new PerformanceObserver(l => { for (const e of l.getEntries()) { window.__lt.count++; window.__lt.total += e.duration; if (e.duration > window.__lt.worst) window.__lt.worst = e.duration; } }).observe({ entryTypes: ['longtask'] }); } catch (e) {}
window.__rafIds = new Set(); window.__rafNext = 1; window.__rafFired = 0; window.__rafFrames = 0; window.__rafCancel = 0;
(function () {
  var raf = window.requestAnimationFrame.bind(window), caf = window.cancelAnimationFrame.bind(window);
  window.requestAnimationFrame = function (cb) {
    var id = window.__rafNext++;
    window.__rafIds.add(id);
    return raf(function (t) { window.__rafIds.delete(id); window.__rafFired++; window.__rafFrames++; try { return cb(t); } finally {} });
  };
  window.cancelAnimationFrame = function (id) { if (window.__rafIds.delete(id)) window.__rafCancel++; return caf(id); };
})();
window.__rafReset = function () { window.__rafFired = 0; };
window.__heap = function () { var m = performance.memory; return m ? Math.round(m.usedJSHeapSize / 1048576) : -1; };
window.__snap = function () { return { heapMB: window.__heap(), made: window.__nxMade, live: Array.from(window.__nxLive), dropped: window.__nxDropped.size }; };
`;

/* локальные копии настоящих артов: подменяем боевой origin на локальный сервер,
   чтобы кэш картинок наполнялся без внешнего трафика */
async function newPage(browser, opts) {
  const ctx = await browser.newContext(Object.assign({
    viewport: { width: 393, height: 851 },
    deviceScaleFactor: 1,
    isMobile: true,
    hasTouch: true,
    userAgent: devices['Pixel 5'].userAgent,
  }, opts || {}));
  // маршрутизацию не включаем: страница и media/ идут с одного локального origin

  const page = await ctx.newPage();
  if (process.env.NO3D) await page.addInitScript(() => { try { localStorage.setItem('nx_weak_gpu', '1'); localStorage.setItem('nx_force3d', ''); } catch (e) {} });
  await page.addInitScript(INSTR);
  const errs = [];
  page.on('pageerror', e => errs.push('pageerror: ' + e.message));
  page.on('console', m => { const t = m.text(); if (m.type() === 'error') errs.push('console: ' + t.slice(0, 160)); if (process.env.VERBOSE) console.log('    [page]', m.type(), t.slice(0, 200)); });
  page.on('crash', () => { errs.push('*** PAGE CRASHED ***'); console.log('  *** СТРАНИЦА УМЕРЛА (crash) ***'); });
  return { ctx, page, errs };
}

async function heap(page) { try { return await page.evaluate(() => window.__heap()); } catch (e) { return -1; } }

async function part1_loops(page, errs) {
  console.log('\n=== ЧАСТЬ 1: WebGL-контексты и rAF-циклы при переходе между играми ===');
  await page.goto(URL, { waitUntil: 'load', timeout: 60000 });
  await page.waitForFunction(() => window.__nxHooked === 1, { timeout: 20000 }).catch(() => console.log('  (хук THREE не встал)'));
  await page.waitForTimeout(4000);

  const games = (process.env.GAMES || 'slots,grid,wheel,lines,mines,arena,durak').split(',');
  for (const g of games) {
    await page.evaluate(m => { try { switchTab('battle'); } catch (e) {} try { setBattleMode(m); } catch (e) { return 'ERR ' + e.message; } return 'ok'; }, g);
    await page.waitForTimeout(Number(process.env.SETTLE || 2600));
    await page.evaluate(() => window.__rafReset());
    await page.waitForTimeout(2000);
    const r = await page.evaluate(() => ({ loops: window.__rafIds.size, fired: window.__rafFired }));
    const s = await page.evaluate(() => {
      const sn = window.__snap();
      let bmp = 0, n = 0, worst = 0;
      for (const im of document.images) {
        if (!im.complete || !im.naturalWidth) continue;
        const b = im.naturalWidth * im.naturalHeight * 4; bmp += b; n++;
        if (b > worst) worst = b;
      }
      sn.bmpMB = +(bmp / 1048576).toFixed(1); sn.imgs = n; sn.worstMB = +(worst / 1048576).toFixed(1);
      return sn;
    });
    console.log(`  экран «${g}»: WebGL-рендеров создано ${s.made}, живо ${s.live.length} [${s.live.join(',')}], rAF-циклов ${r.loops} (${r.fired} за 2 с), heap ${s.heapMB} МБ, битмапов ${s.bmpMB} МБ на ${s.imgs} картинках (худшая ${s.worstMB} МБ)`);
  }

  // ушли в магазин — всё лишнее должно погаснуть
  await page.evaluate(() => { try { switchTab('store'); } catch (e) {} });
  await page.waitForTimeout(1500);
  await page.evaluate(() => window.__rafReset());
  await page.waitForTimeout(3000);
  const idle = await page.evaluate(() => ({ loops: window.__rafIds.size, fired: window.__rafFired, snap: window.__snap() }));
  console.log(`\n  ПОСЛЕ ухода со всех игр (вкладка «Магазин»):`);
  console.log(`    живых WebGL-контекстов: ${idle.snap.live.length} [${idle.snap.live.join(',')}]`);
  console.log(`    rAF-циклов крутится вхолостую: ${idle.loops}, вызовов за 3 с: ${idle.fired}`);
  console.log(`    heap: ${idle.snap.heapMB} МБ`);
  if (errs.length) console.log('  ошибки страницы:', errs.slice(0, 6));
  return idle;
}


async function part3_b64(page) {
  console.log('\n=== ЧАСТЬ 3: сколько стоит «собрать и отправить» всю коллекцию (base64 склейкой, как в коде) ===');
  const r = await page.evaluate(async () => {
    const out = { steps: [] };
    const t = (label, ms) => out.steps.push({ label, ms: Math.round(ms) });
    // 1. собираем ВСЕ арты каталога в память — ровно это делает nxCollectPendingMedia()
    const urls = [];
    nxAllMediaUrls().forEach(raw => { let e = raw; try { e = mediaUrl(raw); } catch (x) {} if (String(e).indexOf('http') === 0 && urls.indexOf(e) < 0) urls.push(e); });
    let h0 = window.__heap(), t0 = performance.now();
    const blobs = [];
    const LIMIT = Number(window.__NX_LIMIT || 0) || urls.length;
    for (const u of urls.slice(0, LIMIT)) {
      try { const rr = await fetch(u, { cache: 'force-cache' }); const b = await rr.blob(); if (b && b.size) blobs.push(b); } catch (e) {}
      if (blobs.length % 10 === 0) console.log('[b64] собрано ' + blobs.length + ' (' + (blobs.reduce((s, x) => s + x.size, 0) / 1048576).toFixed(1) + ' МБ), heap ' + window.__heap() + ' МБ');
    }
    const totalMB = blobs.reduce((s, b) => s + b.size, 0) / 1048576;
    t('собрали ' + blobs.length + ' артов (' + totalMB.toFixed(1) + ' МБ) в ОЗУ', performance.now() - t0);
    out.afterCollectMB = +(totalMB).toFixed(1);
    out.heapAfterCollect = window.__heap();
    // 2. так код делает base64 для КАЖДОГО файла: склейка строки + btoa
    t0 = performance.now();
    let worst = 0, worstName = '';
    for (let i = 0; i < blobs.length; i++) {
      const ab = await blobs[i].arrayBuffer();
      const u8 = new Uint8Array(ab);
      let bin = '';
      const ts = performance.now();
      for (let k = 0; k < u8.length; k += 0x8000) bin += String.fromCharCode.apply(null, u8.subarray(k, k + 0x8000));
      const b64 = btoa(bin);
      const body = JSON.stringify({ content: b64, encoding: 'base64' });
      const dt = performance.now() - ts;
      if (dt > worst) { worst = dt; worstName = (urls[i] || '').split('/').pop(); }
      if (i === 0) out.oneFileMB = +((blobs[0].size / 1048576).toFixed(2));
      out.bodyMB = +((body.length / 1048576).toFixed(2));
    }
    t('base64+JSON для всех ' + blobs.length + ' файлов (худший один: ' + worst.toFixed(0) + ' мс — ' + worstName + ')', performance.now() - t0);
    out.heapAfterB64 = window.__heap();
    out.longTasks = window.__lt ? { n: window.__lt.count, worst: Math.round(window.__lt.worst) } : null;
    // 3. «Вшить всё» (nxPushEmbedded): тот же трюк, но для index.html со ВСЕМИ артами сразу
    t0 = performance.now();
    let acc = '';
    for (let i = 0; i < Math.min(blobs.length, 8); i++) {
      const fr = new FileReader(); const du = await new Promise(res => { fr.onload = () => res(String(fr.result)); fr.readAsDataURL(blobs[i]); });
      acc += du;
    }
    t('data-URL только для 8 артов = ' + (acc.length / 1048576).toFixed(1) + ' МБ строка', performance.now() - t0);
    out.embed8MB = +((acc.length / 1048576).toFixed(1));
    out.heapAfterEmbed = window.__heap();
    return out;
  });
  console.log('  артов в каталоге: собрано в память —', r.afterCollectMB, 'МБ, heap:', r.heapAfterCollect, 'МБ');
  r.steps.forEach(s => console.log('   •', s.label, '=', s.ms, 'мс'));
  console.log('  тело ОДНОГО запроса к GitHub (один арт):', r.bodyMB, 'МБ (файл', r.oneFileMB, 'МБ)');
  console.log('  heap после base64-прогона:', r.heapAfterB64, 'МБ; длинные задачи:', JSON.stringify(r.longTasks));
  console.log('  «Вшить всё»: только 8 артов = строка', r.embed8MB, 'МБ, heap', r.heapAfterEmbed, 'МБ (для всех 82 → x10)');
}


async function part4_hidden(page) {
  console.log('\n=== ЧАСТЬ 4: вкладка в фоне — крутятся ли 3D-циклы ===');
  await page.evaluate(() => { try { switchTab('battle'); setBattleMode('slots'); } catch (e) {} });
  await page.waitForTimeout(2500);
  const measure = async label => {
    await page.evaluate(() => window.__rafReset());
    await page.waitForTimeout(2500);
    const r = await page.evaluate(() => ({ loops: window.__rafIds.size, fired: window.__rafFired, snap: window.__snap(), frozen: window.nx3dFrozen }));
    console.log(`  ${label}: rAF-циклов ${r.loops}, вызовов за 2.5 с ${r.fired}, WebGL-контекстов живо ${r.snap.live.length}, nx3dFrozen=${r.frozen}`);
    return r;
  };
  await measure('вкладка видна, экран «Слоты»');
  await page.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' }); document.dispatchEvent(new Event('visibilitychange')); });
  await page.waitForTimeout(600);
  await measure('вкладка СПРЯТАНА');
  await page.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => false }); Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' }); document.dispatchEvent(new Event('visibilitychange')); });
  await page.waitForTimeout(600);
  await measure('вернулись на вкладку');
}


async function part5_smoke(page, errs) {
  console.log('\n=== ЧАСТЬ 5: дымовой тест — игры реально играются, ошибок нет ===');
  const step = async (label, fn) => {
    const before = errs.length;
    const r = await page.evaluate(fn).catch(e => 'EVAL ERR: ' + e.message);
    await page.waitForTimeout(900);
    const newErrs = errs.slice(before);
    console.log(`  ${label}: ${typeof r === 'string' ? r : JSON.stringify(r)}${newErrs.length ? ' | ОШИБКИ: ' + newErrs.slice(0, 2).join(' ; ') : ' | без ошибок'}`);
  };
  await step('вкладка «Игры»', () => { switchTab('battle'); return document.getElementById('battle-lobby') ? 'ok' : 'нет лобби'; });
  await step('Мины: старт раунда', () => { try { state.coins = Math.max(state.coins, 100000); mines.bet = 100; mines.m = 5; minesStart(); return { active: mines.active, mines: mines.mines.length, tiles: document.querySelectorAll('#mines-board button').length }; } catch (e) { return 'ERR ' + e.message; } });
  await step('Мины: 6 открытий', () => { let opened = 0; for (let i = 0; i < 25 && opened < 6; i++) { if (mines.mines.indexOf(i) < 0) { minesPick(i); opened++; } } return { opened: mines.picked.length, active: mines.active, mult: minesMult(mines.picked.length, mines.m) }; });
  await step('Мины: забрать выигрыш', () => { const c0 = state.coins; minesCashout(); return { coinsDelta: state.coins - c0, active: mines.active }; });
  await step('Мины: раунд до мины', () => { minesStart(); const m = mines.mines[0]; minesPick(m); return { active: mines.active, result: (document.getElementById('mines-result') || {}).textContent }; });
  await step('Слоты: спин (плоский режим)', () => { setBattleMode('slots'); slots.bet = 100; try { slotsSpin(); return { spinning: slots.spinning, fallback: !!slots.fallback }; } catch (e) { return 'ERR ' + e.message; } });
  await step('Линии: поле', () => { setBattleMode('lines'); return { tiles: document.querySelectorAll('#lines-board .lines-tile').length, mode3d: lines.mode3d }; });
  await step('Колесо', () => { setBattleMode('wheel'); return { ready: wheel.ready, fallback: !!wheel.fallback }; });
  await step('Шахта', () => { setBattleMode('miner'); return { lvl: (typeof miner !== 'undefined' && miner) ? miner.lvl : '?' }; });
  await step('Магазин/альбомы/биржа', () => { switchTab('store'); switchTab('albums'); switchTab('market'); switchTab('rewards'); switchTab('store'); return 'ok'; });
  const diag = await page.evaluate(() => { try { return { errlog: localStorage.getItem('nexus_errlog') || '[]', crashlog: localStorage.getItem('nx_crash_log') || '[]' }; } catch (e) { return { errlog: '?', crashlog: '?' }; } });
  console.log('  журнал ошибок страницы:', diag.errlog.slice(0, 300));
  console.log('  журнал аварий:', diag.crashlog.slice(0, 300));
  console.log('  всего ошибок за прогон:', errs.length);
}

async function part2_push(page, errs) {
  console.log('\n=== ЧАСТЬ 2: авто-отправка картинок в GitHub (то, что работает по таймеру во время игры) ===');
  await page.evaluate(() => {
    try {
      localStorage.setItem('nx_gh_token', 'ghp_FAKE_TOKEN_FOR_REPRO');
      localStorage.setItem('nx_gh_repo', 'd3nizkeller/card-collection');
      localStorage.setItem('nx_automedia', '1');
      localStorage.removeItem('nx_gh_media_pushed');
    } catch (e) {}
  });
  // мок GitHub API: считаем, сколько и какого размера приходит
  // тела запросов НЕ читаем в Node (иначе сам перехватчик падает по памяти —
  // это отдельное доказательство размера). Считаем размеры внутри страницы.
  await page.addInitScript(() => {
    window.__gh = { calls: 0, bytes: 0, worst: 0, worstUrl: '' };
    const of = window.fetch;
    window.fetch = function (u, o) {
      try {
        const url = String(u && u.url ? u.url : u);
        if (url.indexOf('api.github.com') >= 0) {
          let n = 0;
          try { n = (o && o.body && o.body.length) || 0; } catch (e) {}
          window.__gh.calls++; window.__gh.bytes += n;
          if (n > window.__gh.worst) { window.__gh.worst = n; window.__gh.worstUrl = url.replace('https://api.github.com', ''); }
        }
      } catch (e) {}
      return of.apply(this, arguments);
    };
  });
  // GitHub API мокаем, но тело запроса НЕ читаем (иначе CDP буферизует его в Node
  // и сам процесс падает по памяти — раньше именно так и было, что уже говорит о размере).
  await page.route('https://api.github.com/**', async route => {
    const u = route.request().url();
    let json = {};
    if (/\/git\/blobs$/.test(u)) { BLOBS++; json = { sha: 'blob' + BLOBS }; }
    else if (/\/git\/trees$/.test(u)) json = { sha: 'tree1' };
    else if (/\/git\/commits\/[0-9a-f]+$/.test(u)) json = { sha: 'c1', tree: { sha: 't0' } };
    else if (/\/git\/commits$/.test(u)) json = { sha: 'c2' };
    else if (/\/git\/ref\/heads\//.test(u)) json = { object: { sha: 'c1' } };
    else if (/\/repos\/[^/]+\/[^/]+$/.test(u)) json = { default_branch: 'main' };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(json) });
  });

  // наполняем постоянный кэш (IndexedDB) настоящими артами — как кнопка «Скачать все картинки»
  const N = Number(process.env.NX_FILES || 30);
  const filled = await page.evaluate(async (n) => {
    const t0 = performance.now();
    const urls = [];
    try {
      nxAllMediaUrls().forEach(raw => { let e = raw; try { e = mediaUrl(raw); } catch (x) {} if (String(e).indexOf('http') === 0) urls.push(e); });
    } catch (e) { return { err: 'nxAllMediaUrls: ' + e.message }; }
    const pick = urls.slice(0, n);
    let ok = 0, bytes = 0;
    for (const u of pick) {
      try {
        const r = await fetch(u, { cache: 'force-cache' });
        const b = await r.blob();
        if (!b.size) continue;
        await imgCachePut(u, b);
        ok++; bytes += b.size;
      } catch (e) {}
    }
    return { total: urls.length, cached: ok, mb: +(bytes / 1048576).toFixed(1), sec: +((performance.now() - t0) / 1000).toFixed(1) };
  }, N);
  console.log(`  артов в каталоге: ${filled.total}, закэшировано в IndexedDB: ${filled.cached} (${filled.mb} МБ) за ${filled.sec} с`);

  const pending = await page.evaluate(async () => {
    const t0 = performance.now();
    const h0 = window.__heap();
    const items = await nxCollectPendingMedia();
    const h1 = window.__heap();
    const mb = items.reduce((s, i) => s + (i.blob ? i.blob.size : 0), 0) / 1048576;
    return { count: items.length, blobMB: +mb.toFixed(1), heapBefore: h0, heapAfter: h1, sec: +((performance.now() - t0) / 1000).toFixed(1) };
  });
  console.log(`  nxCollectPendingMedia(): держит в памяти ОДНОВРЕМЕННО ${pending.count} картинок = ${pending.blobMB} МБ`);
  console.log(`    heap до ${pending.heapBefore} МБ -> после ${pending.heapAfter} МБ, ${pending.sec} с`);

  console.log('  запускаем саму отправку (nxAutoMediaPushRun) — как это делает таймер каждые 5 минут...');
  await page.evaluate(() => {
    window.__mem = { peakHeap: 0, peakTotal: 0, n: 0 };
    window.__memT = setInterval(() => {
      const m = performance.memory; if (!m) return;
      window.__mem.n++;
      window.__mem.peakHeap = Math.max(window.__mem.peakHeap, m.usedJSHeapSize);
      window.__mem.peakTotal = Math.max(window.__mem.peakTotal, m.totalJSHeapSize);
    }, 100);
  });
  const t0 = Date.now();
  let crashed = false;
  try {
    await page.evaluate(() => { window.__pushDone = false; nxAutoMediaPushRun(true, function () { window.__pushDone = true; }); });
    await page.waitForFunction(() => window.__pushDone === true, { timeout: 180000 });
  } catch (e) {
    crashed = true;
    console.log('  !!! отправка не завершилась за 180 с или страница умерла:', String(e.message).slice(0, 120));
  }
  const dt = ((Date.now() - t0) / 1000).toFixed(1);
  const st = await page.evaluate(() => ({ heap: window.__heap(), lt: window.__lt ? { n: window.__lt.count, worst: Math.round(window.__lt.worst) } : null })).catch(() => ({ heap: -1, lt: null }));
  const gh = await page.evaluate(() => window.__gh || { calls: 0, bytes: 0, worst: 0, worstUrl: '?' }).catch(() => ({ calls: 0, bytes: 0, worst: 0, worstUrl: '?' }));
  st.calls = gh.calls; st.mb = +(gh.bytes / 1048576).toFixed(1); st.worst = +(gh.worst / 1048576).toFixed(2); st.worstUrl = gh.worstUrl;
  console.log(`    время: ${dt} с, heap после: ${st.heap} МБ, запросов к GitHub: ${st.calls}, отправлено ${st.mb} МБ (макс. тело ОДНОГО запроса ${st.worst} МБ -> ${st.worstUrl})`);
  const mem = await page.evaluate(() => { try { clearInterval(window.__memT); } catch (e) {} const m = window.__mem || {}; return { peakHeap: Math.round((m.peakHeap || 0) / 1048576), peakTotal: Math.round((m.peakTotal || 0) / 1048576), n: m.n || 0 }; }).catch(() => ({ peakHeap: -1, peakTotal: -1, n: 0 }));
  const pushed = await page.evaluate(() => { try { return JSON.parse(localStorage.getItem('nx_gh_media_pushed') || '[]').length; } catch (e) { return -1; } }).catch(() => -1);
  console.log(`    страница${crashed ? ' УПАЛА/зависла' : ' выжила'}`);
  console.log(`    блобов в одном коммите: ${BLOBS} (лимит за подход: 6 авто / 20 вручную), отмечено отправленными: ${pushed}`);
  console.log(`    пик памяти страницы за время отправки: heap ${mem.peakHeap} МБ, totalJS ${mem.peakTotal} МБ (${mem.n} замеров)`);
  if (errs.length) console.log('  ошибки страницы:', errs.slice(0, 8));
}

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || '/tmp/.cache/ms-playwright/chromium-1134/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--js-flags=--max-old-space-size=1024', '--no-sandbox'],
  });
  const { page, errs } = await newPage(browser);
  try {
    if (MODE === 'loop' || MODE === 'both') await part1_loops(page, errs);
    if (MODE === 'b64' || MODE === 'push' || MODE === 'hidden' || MODE === 'smoke') { await page.goto(URL, { waitUntil: 'load', timeout: 60000 }); await page.waitForTimeout(3500); }
    if (MODE === 'b64') await part3_b64(page);
    if (MODE === 'hidden') await part4_hidden(page);
    if (MODE === 'smoke') await part5_smoke(page, errs);
    if (MODE === 'push' || MODE === 'both') await part2_push(page, errs);
  } catch (e) {
    console.log('СБОЙ ПРОГОНА:', e.message);
  }
  await browser.close();
})();
