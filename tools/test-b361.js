/* Проверка b361: авто-«вшивание» не должно создавать коммит, если собранный
   index.html совпадает с тем, что уже лежит в ветке.
   Запуск: node tools/test-b361.js [url]   (нужен локальный python3 -m http.server) */
const PW = process.env.PW_PATH || '/tmp/pw/node_modules/playwright-core';
const { chromium } = require(PW);
const crypto = require('crypto');
const fs = require('fs');

const URL = process.argv[2] || 'http://127.0.0.1:8123/index.html';
const CHROME = process.env.CHROME_PATH || '/tmp/.cache/ms-playwright/chromium-1134/chrome-linux/chrome';

function gitSha(buf) {
  const head = Buffer.from('blob ' + buf.length + '\0', 'utf8');
  return crypto.createHash('sha1').update(Buffer.concat([head, buf])).digest('hex');
}

(async () => {
  // sha того index.html, который отдаёт локальный сервер (= «уже лежит в ветке»)
  const live = fs.readFileSync('index.html');
  const liveSha = gitSha(live);
  console.log('index.html на диске: %d байт, git-sha %s', live.length, liveSha);

  const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 393, height: 851 } });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 140)); });
  page.on('crash', () => errs.push('*** CRASH ***'));

  await page.goto(URL, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(3000);

  // мок GitHub API: contents/index.html отдаёт ТОТ ЖЕ sha, что насчитает страница
  let calls = { contents: 0, blobs: 0, commits: 0, refs: 0 };
  await page.route('https://api.github.com/**', async route => {
    const u = route.request().url();
    let json = {};
    if (/\/contents\/index\.html/.test(u)) { calls.contents++; json = { sha: liveSha, name: 'index.html', path: 'index.html' }; }
    else if (/\/git\/blobs$/.test(u)) { calls.blobs++; json = { sha: 'blob1' }; }
    else if (/\/git\/trees$/.test(u)) json = { sha: 'tree1' };
    else if (/\/git\/commits\/[0-9a-f]+$/.test(u)) json = { sha: 'c1', tree: { sha: 't0' } };
    else if (/\/git\/commits$/.test(u)) { calls.commits++; json = { sha: 'c2' }; }
    else if (/\/git\/ref\/heads\//.test(u)) { calls.refs++; json = { object: { sha: 'c1' } }; }
    else if (/\/repos\/[^/]+\/[^/]+$/.test(u)) json = { default_branch: 'main' };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(json) });
  });

  const res = await page.evaluate(async (liveSha) => {
    try { localStorage.setItem('nx_gh_token', 'ghp_FAKE_FOR_TEST'); localStorage.setItem('nx_gh_repo', 'd3nizkeller/card-collection'); } catch (e) {}
    const out = {};
    // 1) помощники b361 считают sha так же, как git
    const txt = await (await fetch(location.href, { cache: 'no-store' })).text();
    out.pageLen = txt.length;
    out.pageSha = await nxGitShaOf(txt);
    out.remoteSha = await nxGhFileSha('d3nizkeller/card-collection', 'index.html');
    // 2) сам «Вшить файл в сайт» — должен отказаться от коммита
    const toasts = [];
    const origToast = window.showToast;
    window.showToast = function (m, k) { toasts.push(String(m)); try { return origToast.apply(this, arguments); } catch (e) {} };
    const origOwner = window.nxOwnerToast;
    window.nxOwnerToast = function (m) { toasts.push(String(m)); };
    // nxInStudio() требует открытую Студию — иначе owner-тосты молчат; ломаем проверку
    window.nxInStudio = () => true;
    nxPushEmbedded(true);
    await new Promise(r => setTimeout(r, 6000));
    out.toasts = toasts.slice(0, 6);
    out.status = (document.getElementById('nx-status-bar') || {}).textContent || '';
    return out;
  }, liveSha);

  console.log('длина index.html, как её видит страница:', res.pageLen);
  console.log('sha, который насчитала страница      :', res.pageSha);
  console.log('sha, который вернул «репозиторий»    :', res.remoteSha);
  console.log('совпали:', res.pageSha === res.remoteSha);
  console.log('сообщения страницы:', JSON.stringify(res.toasts, null, 1));
  console.log('статус-строка:', String(res.status).slice(0, 160));
  console.log('запросы к GitHub:', JSON.stringify(calls));
  const ok = res.pageSha === res.remoteSha && calls.commits === 0 && calls.refs === 0 && calls.blobs === 0;
  console.log(ok
    ? '\n✓ b361 РАБОТАЕТ: файл совпал с веткой — коммита нет (0 запросов на создание блоба/коммита/refs)'
    : '\n✗ b361 НЕ сработал: коммит всё равно готовится');
  if (errs.length) console.log('ошибки страницы:', errs.slice(0, 5));
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
