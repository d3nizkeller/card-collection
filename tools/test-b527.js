/* b527: «Медиа-хранилище и автоочистка» — Unused photo and mp3 are removed from media/
   automatically (once a day), and manually via two buttons.

   Owner (panel mockup): «add auto-deletion of unused photo and mp3 to the cloud:
   auto-deleted if not tied to a pack or card, if the media is not used in the game —
   so that hosting is not burdened with unused files».

   A. Sources: panel in index.html (3 controls + status), music pack in
      nxMediaUsedNames, base protection, elapsed time 6 hours, thumbnails together with master,
      tag nxmob274.
   B. Calculation: from the list media/ excludes in-use (card image, pack music,
      deep scan of state — jackpot), base (NX_EMBED_MEDIA), fresh (<6 hours) and
      manifest.json; for unused masters, picks up thumbnails t/.
   C. Auto mode: checkbox on + token + elapsed >24 hours → deletion WITHOUT confirmation,
      one commit (masters + thumbnails), message as in b350 (b351 can revert),
      LS nx_last_autoclean is updated.
   D. Manual mode: «Delete now» asks for confirmation; «No» — no commit.

   Launch:  JSDOM_PATH=/tmp/t/node_modules/jsdom node tools/test-b527.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH || '/tmp/t/node_modules/jsdom');

const ROOT = path.join(__dirname, '..');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; console.log((c ? '  ✅ ' : '  ❌ ') + m); if (!c) fails++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));

function boot() {
    const html = '<!doctype html><html><body>'
        + '<input id="nx-gh-token"><input id="nx-gh-repo">'
        + '<p id="nx-clean-status"></p><button id="nx-clean-del-btn" disabled></button>'
        + '<button id="nx-audit-del-btn" disabled></button><span id="nx-audit-result"></span>'
        + '<input type="checkbox" id="nx-autoclean-chk">'
        + '<div id="nx-status-bar"></div><div id="nx-progress-wrap"><div id="nx-progress-label"></div><div id="nx-progress-bar"></div></div>'
        + '</body></html>';
    const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'https://d3nizkeller.github.io/card-collection/' });
    const w = dom.window;
    dom.virtualConsole.on('jsdomError', () => {});
    const mem = {};
    w.LS = {
        getItem: k => (Object.prototype.hasOwnProperty.call(mem, k) ? mem[k] : null),
        setItem: (k, v) => { mem[k] = String(v); },
        removeItem: k => { delete mem[k]; }
    };
    w.__toasts = [];
    w.showToast = (m, k) => { w.__toasts.push([String(m), k || 'success']); };
    // game environment mini-layer: live state with cards, pack music and jackpot queue
    const pre = w.document.createElement('script');
    pre.textContent = 'var state = { packs: [{ id: "p1", image: "https://x/media/used.jpg", musicUrl: "https://x/media/track_used.mp3" }],'
        + ' cards: [{ id: "c1", image: "https://x/media/card_used.png" }],'
        + ' jackpot: { queue: ["https://x/media/jp_hold.jpg"] } };'
        + ' var defaultPacks = []; var defaultCards = [];'
        + ' var NX_EMBED_MEDIA = { "base_art.jpg": "media/base_art.jpg" };';
    w.document.body.appendChild(pre);
    const sc = w.document.createElement('script');
    sc.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'qr-transfer.js'), 'utf8');
    w.document.body.appendChild(sc);
    w.nxInStudio = () => true;
    // app.js не грузим: эти две функции-хелпера заменяем эквивалентами
    w.nxMediaKey = u => { let t = String(u == null ? '' : u).split('?')[0].split('#')[0]; try { t = decodeURIComponent(t); } catch (e) {} return t.slice(t.lastIndexOf('/') + 1); };
    w.mediaUrl = u => String(u == null ? '' : u);
    w.__api = { calls: [], trees: [], commits: [], refs: [] };
    const OLD = new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString();
    const NEW = new Date().toISOString();
    const files = ['used.jpg', 'card_used.png', 'track_used.mp3', 'base_art.jpg', 'manifest.json', 'fresh_new.jpg', 'unused_old.jpg', 'track_unused.mp3', 'jp_hold.jpg', 'remote_hold.jpg'];
    w.fetch = u => Promise.resolve({ ok: true, json: () => Promise.resolve(String(u).indexOf('jackpot') >= 0 ? { queue: [] } : { cards: [{ image: 'https://x/media/remote_hold.jpg' }] }) });
    w.nxGhToken = () => 'token-test';
    w.nxGhRepoName = () => 'o/r';
    w.nxGhHead = () => Promise.resolve({ branch: 'main', head: 'h1', tree: 't1' });
    w.nxGhApi = (p, opts) => {
        w.__api.calls.push(p);
        const m = (opts && opts.method) || 'GET';
        if (p === '/repos/o/r/contents/media') return Promise.resolve(files.map(n => ({ name: n, type: 'file' })));
        if (p === '/repos/o/r/contents/media/t') return Promise.resolve([{ name: 'unused_old.webp', type: 'file' }, { name: 'used.webp', type: 'file' }]);
        if (p === '/repos/o/r/contents/media/t2' || p === '/repos/o/r/contents/media/t3') return Promise.resolve([]);
        if (p.indexOf('/repos/o/r/commits?path=') === 0) {
            const name = decodeURIComponent(p.replace('/repos/o/r/commits?path=', '').split('&')[0]).replace('media/', '');
            return Promise.resolve([{ commit: { committer: { date: name === 'fresh_new.jpg' ? NEW : OLD } } }]);
        }
        if (m === 'POST' && p === '/repos/o/r/git/trees') { w.__api.trees.push(JSON.parse(opts.body)); return Promise.resolve({ sha: 'tr' }); }
        if (m === 'POST' && p === '/repos/o/r/git/commits') { w.__api.commits.push(JSON.parse(opts.body)); return Promise.resolve({ sha: 'nc' }); }
        if (m === 'PATCH' && p.indexOf('/repos/o/r/git/refs/heads/') === 0) { w.__api.refs.push(JSON.parse(opts.body)); return Promise.resolve({}); }
        return Promise.reject(new Error('unexpected api ' + m + ' ' + p));
    };
    w.__confirm = 0;
    w.confirm = () => { w.__confirm++; return true; };
    return w;
}

(async () => {
    console.log('A. Sources: panel, tags, music in used-set');
    {
        const q = fs.readFileSync(path.join(ROOT, 'assets', 'qr-transfer.js'), 'utf8');
        const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
        const sw = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
        ok(html.indexOf('id="nx-clean-show-btn"') > 0 && html.indexOf('onclick="nxMediaShowUnused()"') > 0, 'panel: button «Show unused»');
        ok(html.indexOf('id="nx-clean-del-btn"') > 0 && html.indexOf('onclick="nxMediaDeleteNow(false)"') > 0, 'panel: button «Delete now»');
        ok(html.indexOf('id="nx-autoclean-chk"') > 0 && html.indexOf('nxAutoCleanSet(this.checked)') > 0, 'panel: checkbox «Auto-clean (once a day)»');
        ok(html.indexOf('Базовые арты и музыка защищены всегда') > 0 && html.indexOf('менее 6 ч') > 0, 'panel: protection description (base, 6 hours)');
        ok(/function nxMediaUsedNames[\s\S]{0,2200}?nxMediaKey\(p && p\.musicUrl\)/.test(q), 'used-set: pack music (musicUrl)');
        ok(q.indexOf('nxMediaDeepNames(state, used, 0)') >= 0, 'used-set: deep scan of state (jackpot/album/missions)');
        ok(q.indexOf('function nxMediaRemoteDocsNames(done)') >= 0 && q.indexOf('nexus-tcg-jackpot-v3') >= 0, 'used-set: scan of cloud room and jackpot document');
        ok(q.indexOf('nxMediaPushedSet().forEach(function (n) { used[n] = 1; })') < 0, 'no rule of "pushed = in-use forever" (orphaned files can be deleted)');
        ok(q.indexOf('function nxMediaBaseProtected()') >= 0 && q.indexOf("if (a.ageH < 6) return;") >= 0, 'protection: base set and elapsed time 6 hours');
        ok(q.indexOf("['t/', 't2/', 't3/'].forEach") >= 0, 'unused master takes thumbnails t/t2/t3 with it');
        ok(q.indexOf("message: 'авто: уборка лишних media/ (' + paths.length + ')'") >= 0, 'deletion commit message as in b350 (b351 can revert)');
        ok(!/nxmob273/.test(html) && /nxmob274/.test(html) && /const VERSION = 'nxmob274';/.test(sw), 'tag nxmob274 (index.html + sw.js)');
    }

    console.log('B. Calculation: unused = masters - in-use - base - fresh');
    {
        const w = boot();
        w.nxMediaShowUnused();
        await sleep(120);
        const masters = w.eval('NX_CLEAN.masters').slice().sort();
        ok(JSON.stringify(masters) === JSON.stringify(['track_unused.mp3', 'unused_old.jpg']),
            'unused only 2 (unused master + unused mp3): ' + masters.join(', '));
        ok(JSON.stringify(w.eval('NX_CLEAN.deriv')) === JSON.stringify(['t/unused_old.webp']), 'thumbnail of unused master picked up');
        ok(String(w.document.getElementById('nx-clean-status').textContent).indexOf('неиспользуемых: 2') >= 0, 'status shows count 2');
        ok(!w.document.getElementById('nx-clean-del-btn').disabled, '«Delete now» became enabled');
        w.close();
    }

    console.log('C. Auto mode: once a day, no confirmation, one commit');
    {
        const w = boot();
        w.LS.setItem('nx_autoclean', '1');
        w.LS.setItem('nx_last_autoclean', '0');
        w.confirm = () => { w.__confirm++; return true; };
        w.nxMaybeAutoClean();
        await sleep(150);
        ok(w.__confirm === 0, 'auto mode did not ask for confirmation');
        ok(w.__api.trees.length === 1, 'exactly one deletion commit');
        const paths = (w.__api.trees[0] || { tree: [] }).tree.map(e => e.path).sort();
        ok(JSON.stringify(paths) === JSON.stringify(['media/t/unused_old.webp', 'media/track_unused.mp3', 'media/unused_old.jpg']),
            'in commit: masters + thumbnails: ' + paths.join(', '));
        ok((w.__api.trees[0] || { tree: [] }).tree.every(e => e.sha === null), 'entries with sha:null (deletion)');
        ok(String(w.__api.commits[0].message).indexOf('авто: уборка лишних media/ (3)') === 0, 'commit message: ' + w.__api.commits[0].message);
        ok(w.LS.getItem('nx_last_autoclean') !== '0', 'LS nx_last_autoclean updated (won\'t hammer more than once a day)');
        // second launch on the same day — silence
        const calls0 = w.__api.calls.length;
        w.nxMaybeAutoClean();
        await sleep(60);
        ok(w.__api.calls.length === calls0, 're-launch on same day: no requests to GitHub');
        w.close();
    }

    console.log('D. Manual mode: confirmation controls the commit');
    {
        const w = boot();
        w.eval('NX_CLEAN = { masters: ["unused_old.jpg"], deriv: ["t/unused_old.webp"], ready: true, running: false }');
        w.confirm = () => { w.__confirm++; return false; };
        w.nxMediaDeleteNow(false);
        await sleep(60);
        ok(w.__api.trees.length === 0, 'answer «No» to confirmation — no commit');
        w.confirm = () => { w.__confirm++; return true; };
        w.__confirm = 0;
        w.nxMediaDeleteNow(false);
        await sleep(60);
        ok(w.__api.trees.length === 1 && w.__confirm === 1, 'answer «Yes» — commit executed after confirmation');
        ok(w.document.getElementById('nx-clean-del-btn').disabled, 'button disabled again after deletion');
        w.close();
    }

    console.log(fails ? ('\n❌ b527: fails ' + fails + ' of ' + checks) : ('\n✅ b527: all ' + checks + ' checks green'));
    process.exit(fails ? 1 : 0);
})().catch(e => { console.error('crash:', e); process.exit(1); });
