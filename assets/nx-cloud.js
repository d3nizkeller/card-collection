/* ============================================================================
 * assets/nx-cloud.js — клиентская часть серверной экономики (b463)
 * ----------------------------------------------------------------------------
 * Зачем этот файл
 * ---------------
 * Игра статическая (GitHub Pages), поэтому раньше все деньги считались в
 * браузере: ставка, результат спина, выплата, банк джекпота, покупки и обмен.
 * Любой игрок мог открыть консоль и написать себе баланс или объявить себя
 * победителем джекпота.
 *
 * Теперь деньги считает сервер (Cloudflare Worker + D1, код в server/).
 * Этот файл — тонкий клиент: он ходит на сервер по HTTPS и отдаёт игре готовые
 * результаты. Никаких секретов здесь нет и быть не может: файл публичный,
 * поэтому всё ценное (балансы, банк, раскладка мин, пароль Студии) хранится
 * только на сервере.
 *
 * Что получает игра (window.*):
 *   NXS — состояние игрока: вход, баланс, спины, паки, мины, шахта, награды,
 *         сторож баланса (возвращает подменённое число к серверному);
 *   NXJ — общий банк джекпота: взносы, срыв, витрина, зал славы, топ-3;
 *   NXM — биржа дубликатов: эскроу, покупка, снятие лота, витрина лотов;
 *   NXA — Студия: вход по паролю (проверяет сервер) и действия админки.
 *
 * Совместимость
 * -------------
 * app.js уже знал про NXJ и NXM (b443/b444) и проверял их через available():
 * флаг становится true ТОЛЬКО после успешного ответа сервера. Поэтому если
 * воркер не задеплоен или сеть пропала, игра работает ровно как раньше —
 * на локальной логике, ничего не ломается и не тормозит.
 *
 * Настройка адреса API (один раз, в Студии → «Облако»):
 *   localStorage.nx_api_url = 'https://nexus-card-api.<ваш-аккаунт>.workers.dev'
 * Адрес можно задать и без Студии, консолью:
 *   localStorage.setItem('nx_api_url','https://…'); location.reload()
 * ========================================================================== */
(function (root) {
    'use strict';

    var LS = (function () {
        try {
            var t = '__nx__'; root.localStorage.setItem(t, '1'); root.localStorage.removeItem(t);
            return root.localStorage;
        } catch (e) {
            var m = {};
            return { getItem: function (k) { return Object.prototype.hasOwnProperty.call(m, k) ? m[k] : null; }, setItem: function (k, v) { m[k] = String(v); }, removeItem: function (k) { delete m[k]; } };
        }
    })();

    var CFG = {
        url: String(LS.getItem('nx_api_url') || (root.__NX_API || '') || '').replace(/\/+$/, ''),
        room: String(LS.getItem('nexus_cloud_room') || 'site'),
        timeout: 15000,
        debug: LS.getItem('nx_api_debug') === '1'
    };

    var S = {
        live: false,          // сервер ответил успешно — можно доверять
        fails: 0,             // подряд неудач: после 3 уходим в локальный режим
        token: String(LS.getItem('nx_token') || ''),
        adminToken: String(LS.getItem('nx_admin_token') || ''),
        cid: '',
        bal: null,            // BigInt-строка баланса с сервера (истина)
        balN: 0,              // то же числом для витрины
        bank: null,
        cfg: null,
        hall: [],
        top: [],
        player: null,
        inv: {},
        lastSync: 0,
        pending: 0,
        blocked: false,
        deleted: false,
        zeroAt: 0,
        catalog: false
    };

    var listeners = {};
    function on(ev, cb) { (listeners[ev] = listeners[ev] || []).push(cb); }
    function emit(ev, data) {
        var l = listeners[ev] || [];
        for (var i = 0; i < l.length; i++) { try { l[i](data); } catch (e) {} }
    }
    function log() { if (CFG.debug && root.console) console.log.apply(console, ['[nx-cloud]'].concat([].slice.call(arguments))); }

    function apiUrl() { return CFG.url; }
    function configured() { return !!CFG.url; }
    /** true только если сервер настроен И уже ответил успешно. */
    function available() { return configured() && S.live; }

    function timeoutMs() { return CFG.timeout; }

    function request(path, body, opts) {
        opts = opts || {};
        if (!configured()) return Promise.resolve({ ok: false, offline: true, error: 'api_not_configured' });
        var headers = { 'content-type': 'application/json', 'x-nx-room': CFG.room };
        if (!opts.noAuth && S.token) headers['authorization'] = 'Bearer ' + S.token;
        if (opts.admin && S.adminToken) headers['x-nx-admin'] = S.adminToken;
        var ctrl = null;
        var init = { method: opts.method || (body ? 'POST' : 'GET'), headers: headers, cache: 'no-store' };
        if (body) init.body = JSON.stringify(body);
        try {
            ctrl = new AbortController();
            init.signal = ctrl.signal;
            setTimeout(function () { try { ctrl.abort(); } catch (e) {} }, timeoutMs());
        } catch (e) {}
        return fetch(apiUrl() + path, init).then(function (r) {
            return r.text().then(function (txt) {
                var j = null;
                try { j = txt ? JSON.parse(txt) : {}; } catch (e) { j = { ok: false, error: 'bad_response' }; }
                if (r.status === 401) { S.token = ''; try { LS.removeItem('nx_token'); } catch (e) {} }
                if (r.status === 403 && (j.error === 'admin_required')) { S.adminToken = ''; try { LS.removeItem('nx_admin_token'); } catch (e) {} }
                if (r.ok || j.ok === false) { S.fails = 0; S.live = true; }
                j.status = r.status;
                return j;
            });
        }).catch(function (e) {
            S.fails++;
            if (S.fails >= 3) { S.live = false; emit('offline', { fails: S.fails }); }
            log('сеть недоступна:', path, e && e.message);
            return { ok: false, offline: true, error: 'network' };
        });
    }

    // ------------------------------ баланс ------------------------------
    /** BigInt-строка → число для витрины (как и раньше, fmtCoins работает с числом). */
    function num(v) {
        if (v === null || v === undefined) return 0;
        if (typeof v === 'object' && v.s !== undefined) return Number(v.s);
        return Number(v);
    }
    function applyBalance(m) {
        if (!m) return;
        S.bal = String(m.s);
        S.balN = Number(m.s);
        S.lastSync = Date.now();
        emit('balance', { s: S.bal, n: S.balN });
    }
    function applyBank(b) {
        if (!b) return;
        S.bank = b;
        emit('bank', b);
    }
    function applyPlayer(p) {
        if (!p) return;
        S.player = p;
        S.blocked = !!p.blocked;
        S.deleted = !!p.del;
        S.zeroAt = Number(p.zeroAt) || 0;
        if (S.blocked || S.deleted) emit('blocked', { blocked: S.blocked, deleted: S.deleted });
        if (p.name || p.st) emit('player', p);
    }

    // ============================== NXS ==============================
    var NXS = {
        configured: configured,
        available: available,
        url: apiUrl,
        on: on,

        setUrl: function (u) {
            CFG.url = String(u || '').trim().replace(/\/+$/, '');
            try { if (CFG.url) LS.setItem('nx_api_url', CFG.url); else LS.removeItem('nx_api_url'); } catch (e) {}
            S.live = false;
            return configured();
        },
        setRoom: function (r) { CFG.room = String(r || 'site'); },
        room: function () { return CFG.room; },
        token: function () { return S.token; },
        adminToken: function () { return S.adminToken; },
        cid: function () { return S.cid; },
        bal: function () { return S.bal; },
        balNum: function () { return S.balN; },
        bank: function () { return S.bank; },
        bankPot: function () { return S.bank ? Number(S.bank.pot) : 0; },
        cfgJpc: function () { return S.cfg; },
        player: function () { return S.player; },
        inv: function () { return S.inv; },
        isBlocked: function () { return S.blocked; },
        lastSync: function () { return S.lastSync; },
        debug: function (v) { CFG.debug = !!v; try { LS.setItem('nx_api_debug', v ? '1' : '0'); } catch (e) {} },

        /**
         * Вход: показываем серверу свой cid, получаем подписанный токен.
         * Токен — доказательство, что владелец баланса именно это устройство.
         */
        boot: function (info) {
            if (!configured()) return Promise.resolve({ ok: false, error: 'api_not_configured' });
            info = info || {};
            S.cid = String(info.cid || S.cid || '');
            return request('/api/boot', {
                cid: S.cid, name: info.name || '', room: CFG.room,
                dev: info.dev || '', did: info.did || '', prof: info.prof || ''
            }).then(function (r) {
                if (r && r.ok) {
                    S.token = r.token; S.live = true; S.fails = 0;
                    try { LS.setItem('nx_token', S.token); } catch (e) {}
                    if (r.cid) S.cid = r.cid;
                    applyBalance(r.player && r.player.bal);
                    applyBank(r.bank);
                    applyPlayer(r.player);
                    S.cfg = r.cfg || null;
                    S.hall = r.hall || [];
                    S.top = r.top || [];
                    S.catalog = !!r.catalog;
                    emit('ready', { cid: S.cid, catalog: S.catalog });
                }
                return r;
            });
        },

        /** Полное состояние: баланс, банк, инвентарь, зал славы. */
        state: function () {
            return request('/api/state', null, { method: 'GET' }).then(function (r) {
                if (r && r.ok) {
                    applyBalance(r.bal); applyBank(r.bank); applyPlayer(r.player);
                    S.inv = r.inv || {}; S.hall = r.hall || []; S.top = r.top || [];
                }
                return r;
            });
        },

        /** Витрина банка без токена (для гостей и для первого экрана). */
        publicState: function () {
            return request('/api/public', null, { method: 'GET', noAuth: true }).then(function (r) {
                if (r && r.ok) { applyBank(r.bank); S.cfg = r.cfg; S.hall = r.hall || []; S.top = r.top || []; S.catalog = !!r.hasCatalog; }
                return r;
            });
        },

        /**
         * ГЛАВНЫЙ ЗАПРОС ИГРЫ: «крутить со ставкой N».
         * Клиент отправляет только игру, ставку и какие карты стоят на барабанах.
         * Всё остальное — случайные числа, выплата, банк — считает сервер.
         */
        spin: function (game, bet, cards, oid) {
            return request('/api/spin', {
                game: game, bet: bet, cards: cards || [], room: CFG.room,
                oid: oid || ('s-' + game + '-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8))
            }).then(function (r) {
                if (r && r.ok) {
                    applyBalance(r.bal); applyBank(r.bank);
                    if (r.hall) S.hall = r.hall;
                    if (r.top) S.top = r.top;
                    if (r.st) emit('stats', r.st);
                    if (r.inv) for (var k in r.inv) S.inv[k] = r.inv[k];
                    if (r.pityG) emit('pity', r.pityG);
                    if (r.minerLvl) emit('minerLvl', r.minerLvl);
                } else if (r && r.bal) {
                    applyBalance(r.bal); // например not_enough: баланс всё равно уточняем
                }
                return r;
            });
        },

        mines: function (act, params) {
            return request('/api/mines', Object.assign({ act: act, room: CFG.room }, params || {})).then(function (r) {
                if (r && r.bal) applyBalance(r.bal);
                if (r && r.bank) applyBank(r.bank);
                return r;
            });
        },

        pack: function (packId, qty, price) {
            return request('/api/pack', { packId: packId, qty: qty || 1, price: price, room: CFG.room }).then(function (r) {
                if (r && r.bal) applyBalance(r.bal);
                if (r && r.inv) for (var k in r.inv) S.inv[k] = (S.inv[k] || 0) + 1;
                return r;
            });
        },

        miner: function (act) {
            return request('/api/miner', { act: act || 'claim', room: CFG.room }).then(function (r) {
                if (r && r.bal) applyBalance(r.bal);
                return r;
            });
        },

        reward: function (kind, params) {
            return request('/api/reward', Object.assign({ kind: kind, room: CFG.room }, params || {})).then(function (r) {
                if (r && r.bal) applyBalance(r.bal);
                return r;
            });
        },

        /**
         * Сторож баланса. В серверном режиме баланс — это то, что сказал сервер.
         * Если кто-то поправил state.coins в консоли или в localStorage, сторож
         * вернёт серверное значение. design не меняется: игрок видит то же число,
         * просто оно больше не подделывается.
         *
         * get() — текущее число в игре; set(v) — записать обратно.
         */
        startWatchdog: function (get, set, intervalMs) {
            if (S.watch) return;
            var grace = 0;
            S.watch = setInterval(function () {
                try {
                    if (!available()) return;
                    if (S.pending > 0) return;              // идёт запрос — баланс ещё не устоялся
                    if (Date.now() - grace < 1500) return;   // дали анимации доехать
                    var local = Math.floor(Number(get()) || 0);
                    var srv = Math.floor(Number(S.balN) || 0);
                    if (local !== srv) {
                        log('сторож баланса: локально ' + local + ', на сервере ' + srv + ' — возвращаю серверное');
                        set(srv);
                        emit('tamper', { local: local, server: srv });
                    }
                } catch (e) {}
            }, Math.max(1000, intervalMs || 4000));
            NXS.watchdogGrace = function () { grace = Date.now(); };
        },
        stopWatchdog: function () { if (S.watch) { clearInterval(S.watch); S.watch = null; } },
        /** «Не трогать баланс N мс» — вызывается игрой вокруг анимаций начисления. */
        watchdogGrace: function () {},
        /** На время серверного запроса сторож не мешает. */
        guard: function (fn) {
            S.pending++;
            try { return Promise.resolve(fn()).then(function (r) { S.pending--; return r; }, function (e) { S.pending--; throw e; }); }
            catch (e) { S.pending--; throw e; }
        },

        catalogPublished: function () { return S.catalog; }
    };

    // ============================== NXJ ==============================
    // Банк джекпота. app.js уже умеет с ним работать (b444): feed() — взнос,
    // win() — срыв. В серверном режиме деньги двигает сервер, поэтому эти
    // методы нужны только чтобы сообщить о факте и обновить витрину.
    var NXJ = {
        available: available,
        pot: function () { return S.bank ? S.bank.pot : null; },
        bank: function () { return S.bank; },
        hall: function () { return S.hall; },
        top: function () { return S.top; },
        cfg: function () { return S.cfg; },
        feed: function (p) { emit('feed', p || {}); return Promise.resolve({ ok: true, server: true }); },
        win: function (p) { emit('win', p || {}); return Promise.resolve({ ok: true, server: true }); },
        refresh: function () { return NXS.publicState(); },
        /** Админка: поставить банк / выдать джекпот (нужен админ-токен). */
        poolSet: function (value) { return NXA.act('poolSet', { value: value }); },
        poolNudge: function (delta) { return NXA.act('poolNudge', { delta: delta }); },
        grant: function (cid, amount) { return NXA.act('grant', { cid: cid, amount: amount }); },
        grantAll: function (amount) { return NXA.act('grant', { cid: '*', amount: amount }); },
        hallReset: function () { return NXA.act('hallReset', {}); },
        setCfg: function (cfg) { return NXA.act('cfg', { cfg: cfg }); },
        resetCfg: function () { return NXA.act('cfgReset', {}); }
    };

    // ============================== NXM ==============================
    // Биржа дубликатов. Контракт — ровно тот, что уже ждёт app.js (b443):
    // list(lots), buy(lotId, sid, name) → {ok, receipt} | {offline} | {error},
    // cancel(lotId, sid), lots(filter, limit) → {ok, lots}.
    var QUEUE_KEY = 'nx_market_queue';

    function queueLoad() { try { return JSON.parse(LS.getItem(QUEUE_KEY) || '[]'); } catch (e) { return []; } }
    function queueSave(a) { try { LS.setItem(QUEUE_KEY, JSON.stringify(a.slice(-40))); } catch (e) {} }

    function flushQueue() {
        if (!available()) return;
        var q = queueLoad();
        if (!q.length) return;
        queueSave([]);
        q.forEach(function (item) {
            if (item && item.type === 'list') NXM.list(item.lots);
            if (item && item.type === 'cancel') NXM.cancel(item.id, item.sid);
        });
    }

    var NXM = {
        available: available,
        lots: function (filter, limit) {
            return request('/api/market/lots?limit=' + Math.max(1, Math.min(400, limit || 400)), null, { method: 'GET' }).then(function (r) {
                if (!r || !r.ok) return { ok: false, lots: [], offline: !!(r && r.offline) };
                return { ok: true, lots: r.lots || [], count: r.count || 0 };
            });
        },
        /** Выставить лоты. Копии карт сервер забирает в эскроу после проверки владения. */
        list: function (lots) {
            var arr = Array.isArray(lots) ? lots : [lots];
            if (!arr.length) return Promise.resolve({ ok: true, listed: 0 });
            if (!available()) {
                var q = queueLoad(); q.push({ type: 'list', lots: arr, at: Date.now() }); queueSave(q);
                return Promise.resolve({ ok: false, offline: true, queued: arr.length });
            }
            return request('/api/market/list', { lots: arr, room: CFG.room }).then(function (r) {
                if (r && r.ok) flushQueue();
                return r;
            });
        },
        /** Купить лот: деньги списывает сервер, продавец получает их сразу. */
        buy: function (lotId, sid, name) {
            if (!available()) return Promise.resolve({ ok: false, offline: true });
            return request('/api/market/buy', { id: lotId, name: name || '', room: CFG.room }).then(function (r) {
                if (r && r.ok) return { ok: true, receipt: r.receipt, card: r.card, dup: r.dup, bal: r.bal };
                if (r && r.offline) return { ok: false, offline: true };
                return { ok: false, error: (r && r.error) || 'Лот уже куплен или снят' };
            });
        },
        cancel: function (lotId, sid) {
            if (!available()) {
                var q = queueLoad(); q.push({ type: 'cancel', id: lotId, sid: sid, at: Date.now() }); queueSave(q);
                return Promise.resolve({ ok: false, offline: true });
            }
            return request('/api/market/cancel', { id: lotId, sid: sid || '', room: CFG.room });
        },
        flush: flushQueue
    };

    // ============================== NXA ==============================
    // Студия и админка. Пароля здесь нет: клиент только пересылает его на
    // сервер, а сервер сверяет со своим хэшем и выдаёт админ-токен на 12 часов.
    var NXA = {
        available: function () { return configured() && !!S.adminToken; },
        login: function (login, pass) {
            if (!configured()) return Promise.resolve({ ok: false, error: 'api_not_configured' });
            return request('/api/studio/login', { login: login, pass: pass }, { noAuth: true }).then(function (r) {
                if (r && r.ok && r.adminToken) {
                    S.adminToken = r.adminToken; S.live = true;
                    try { LS.setItem('nx_admin_token', S.adminToken); } catch (e) {}
                    emit('admin', { login: r.login, upgraded: r.upgraded });
                }
                return r;
            });
        },
        logout: function () {
            S.adminToken = '';
            try { LS.removeItem('nx_admin_token'); } catch (e) {}
            emit('admin', null);
            return Promise.resolve({ ok: true });
        },
        hasToken: function () { return !!S.adminToken; },
        /** Создать первую учётку Студии (или сменить пароль — по админ-токену). */
        setup: function (login, pass, currentPass, setupKey) {
            return request('/api/studio/setup', { login: login, pass: pass, currentPass: currentPass || '', setupKey: setupKey || '' }, { admin: true }).then(function (r) {
                if (r && r.ok && r.adminToken) { S.adminToken = r.adminToken; try { LS.setItem('nx_admin_token', S.adminToken); } catch (e) {} }
                return r;
            });
        },
        /** Любое действие админки: zero/block/unblock/delete/grant/poolSet/cfg/… */
        act: function (act, params) {
            if (!configured()) return Promise.resolve({ ok: false, error: 'api_not_configured' });
            if (!S.adminToken) return Promise.resolve({ ok: false, error: 'admin_required' });
            return request('/api/admin', Object.assign({ act: act, room: CFG.room }, params || {}), { admin: true }).then(function (r) {
                if (r && r.ok && r.bank) applyBank(r.bank);
                return r;
            });
        },
        users: function () {
            return request('/api/admin/users', null, { method: 'GET', admin: true }).then(function (r) {
                if (r && r.ok) { applyBank(r.bank); S.cfg = r.cfg || S.cfg; emit('users', r.players); }
                return r;
            });
        },
        /** Опубликовать каталог комнаты на сервере (нужно для честных вскрытий). */
        publishCatalog: function (packs, cards) {
            return NXA.act('catalog', { packs: packs, cards: cards });
        },
        audit: function () { return NXA.act('audit', {}); },
        /** Перенести текущие данные игроков из старого общего документа. */
        migrate: function (doc, catalog, legacyAuth, force) {
            return request('/api/migrate', { doc: doc, catalog: catalog, legacyAuth: legacyAuth, force: !!force, room: CFG.room }, { admin: true });
        }
    };

    root.NXS = NXS;
    root.NXJ = NXJ;
    root.NXM = NXM;
    root.NXA = NXA;
    root.NXCLOUD = { version: 'b463', S: S, CFG: CFG, request: request, num: num, flushQueue: flushQueue };

    // При старте: если адрес API задан — молча поднимаем сессию и витрину банка.
    try {
        if (configured()) {
            NXS.publicState();
            if (S.token) NXS.state();
        }
    } catch (e) {}
})(typeof window !== 'undefined' ? window : globalThis);
