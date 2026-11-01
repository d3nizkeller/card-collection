/* b528: «не удаляет, выдаёт ошибку» — 422 GitRPC::BadObjectState на устаревшем списке.

   Разбор жалобы: автоочистка в 12:39 уже удалила 100 файлов (коммит fc4f46c),
   а клик «Удалить сейчас» из другой вкладки / после удаления шёл со СТАРЫМ
   списком: tree API с sha:null по несуществующему пути отвечает
   422 GitRPC::BadObjectState (проверено на живом API) — коммит не создавался,
   владелец видел ошибку. Теперь nxMediaDeleteNow перед коммитом сверяет список
   с живым media/ (masters + t/t2/t3): исчезнувшие имена пропускаются, ошибка
   дублируется в статус-строку панели.

   Проверки: исходники (filter по have, тег nxmob275) + jsdom: устаревший список
   режется до живых путей; полностью удалённый список → «нечего» без коммита;
   ошибка удаления видна в #nx-clean-status.

   Запуск:  JSDOM_PATH=/tmp/t/node_modules/jsdom node tools/test-b528.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));

function boot(opts) {
    const html = '<!doctype html><html><body>'
        + '<input id="nx-gh-token"><input id="nx-gh-repo">'
        + '<p id="nx-clean-status"></p><button id="nx-clean-del-btn"></button>'
        + '<button id="nx-audit-del-btn"></button><span id="nx-audit-result"></span>'
        + '<input type="checkbox" id="nx-autoclean-chk">'
        + '<div id="nx-status-bar"></div><div id="nx-progress-wrap"><div id="nx-progress-label"></div><div id="nx-progress-bar"></div></div>'
        + '</body></html>';
    const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'https://d3nizkeller.github.io/card-collection/' });
    const w = dom.window;
    dom.virtualConsole.on('jsdomError', () => {});
    const mem = {};
    w.LS = { getItem: k => (Object.prototype.hasOwnProperty.call(mem, k) ? mem[k] : null), setItem: (k, v) => { mem[k] = String(v); }, removeItem: k => { delete mem[k]; } };
    w.__toasts = [];
    w.showToast = (m, k) => { w.__toasts.push([String(m), k || 'success']); };
    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'qr-transfer.js'), 'utf8');
    w.document.body.appendChild(sc);
    w.nxInStudio = () => true;
    w.nxMediaKey = u => { let t = String(u == null ? '' : u).split('?')[0].split('#')[0]; try { t = decodeURIComponent(t); } catch (e) {} return t.slice(t.lastIndexOf('/') + 1); };
    w.mediaUrl = u => String(u == null ? '' : u);
    w.__api = { trees: [], commits: [] };
    const live = (opts && opts.live) || ['unused_old.jpg'];
    const liveT = (opts && opts.liveT) || ['unused_old.webp'];
    w.nxGhToken = () => 'token-test';
    w.nxGhRepoName = () => 'o/r';
    w.nxGhHead = () => Promise.resolve({ branch: 'main', head: 'h1', tree: 't1' });
    w.nxGhApi = (p, o) => {
        const m = (o && o.method) || 'GET';
        if (p === '/repos/o/r/contents/media') return Promise.resolve(live.map(n => ({ name: n, type: 'file' })));
        if (p === '/repos/o/r/contents/media/t') return Promise.resolve(liveT.map(n => ({ name: n, type: 'file' })));
        if (p === '/repos/o/r/contents/media/t2' || p === '/repos/o/r/contents/media/t3') return Promise.resolve([]);
        if (m === 'POST' && p === '/repos/o/r/git/trees') { w.__api.trees.push(JSON.parse(o.body)); return Promise.resolve({ sha: 'tr' }); }
        if (m === 'POST' && p === '/repos/o/r/git/commits') { w.__api.commits.push(JSON.parse(o.body)); return Promise.resolve({ sha: 'nc' }); }
        if (m === 'PATCH') return Promise.resolve({});
        return Promise.reject(new Error('unexpected ' + m + ' ' + p));
    };
    w.confirm = () => true;
    return w;
}

(async () => {
    console.log('A. Исходники');
    {
        const q = fs.readFileSync(path.join(ROOT, 'assets', 'qr-transfer.js'), 'utf8');
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        ok(q.indexOf('var refreshHave = function (cb2)') >= 0, 'перед коммитом — сверка списка с живым media/');
        ok(q.indexOf("NX_CLEAN.masters.filter(function (m) { return have['media/' + m]; })") >= 0, 'исчезнувшие мастера пропускаются');
        ok(q.indexOf('Удалять нечего: неиспользуемые файлы уже удалены') >= 0, 'полностью устаревший список → честное «нечего»');
        ok(q.indexOf("var s3 = document.getElementById('nx-clean-status'); if (s3) s3.textContent = em;") >= 0, 'ошибка видна в статус-строке панели');
        ok(/nxmob275/.test(html) && !/nxmob274/.test(html) && /const VERSION = 'nxmob275';/.test(sw), 'тег nxmob275');
    }
    console.log('B. Устаревший список: коммит только по живым путям');
    {
        const w = boot({ live: ['unused_old.jpg'], liveT: ['unused_old.webp'] });
        w.eval('NX_CLEAN = { masters: ["gone1.jpg", "unused_old.jpg", "gone2.mp3"], deriv: ["t/unused_old.webp", "t/gone1.webp"], ready: true, running: false }');
        w.nxMediaDeleteNow(false);
        await sleep(80);
        const paths = (w.__api.trees[0] || { tree: [] }).tree.map(e => e.path).sort();
        ok(JSON.stringify(paths) === JSON.stringify(['media/t/unused_old.webp', 'media/unused_old.jpg']),
            'в коммит ушли только живые пути: ' + paths.join(', '));
        ok(String(w.__api.commits[0].message).indexOf('авто: уборка лишних media/ (2)') === 0, 'коммит: ' + w.__api.commits[0].message);
        w.close();
    }
    console.log('C. Список удалён целиком: коммита нет, 422 не будет');
    {
        const w = boot({ live: ['other.jpg'], liveT: [] });
        w.eval('NX_CLEAN = { masters: ["gone1.jpg"], deriv: ["t/gone1.webp"], ready: true, running: false }');
        w.nxMediaDeleteNow(false);
        await sleep(80);
        ok(w.__api.trees.length === 0, 'tree API не дёргается (никакого 422 BadObjectState)');
        ok(String(w.document.getElementById('nx-clean-status').textContent).indexOf('уже удалены') >= 0,
            'статус панели: ' + w.document.getElementById('nx-clean-status').textContent);
        ok(w.document.getElementById('nx-clean-del-btn').disabled, 'кнопка «Удалить сейчас» погашена');
        w.close();
    }
    console.log(fails ? ('\n❌ b528: провалов ' + fails + ' из ' + checks) : ('\n✅ b528: все ' + checks + ' проверок зелёные'));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('crash:', e); process.exit(1); });
