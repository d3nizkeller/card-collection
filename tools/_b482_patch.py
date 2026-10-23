#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b482: «Отправить на GitHub» и автоотправка тянут арты из КОПИЙ НА САЙТЕ, а не только из кэша.

Жалоба владельца (скриншот блока «Картинки сайта → GitHub»): «я нажимаю
отправить на гитхаб а оно не отправляет а должно автоматически скачивать
картинки на гитхаб с сайта». На скриншоте — красный список «Нет картинок (40):
… нет кэша, ссылка молчит».

Разбор
------
Конвейер отправки (b344/b359) устроен так: «Шаг 1» кэширует арты в IndexedDB
устройства (imgCacheStoreFromNetwork тянет байты fetch-ом исходной ссылки),
«Шаг 3» и автоотправка берут байты ТОЛЬКО из этого кэша
(nxCollectPendingMedia → imgCacheGetBlob) и коммитят их в media/. Если ссылка
карточки мертва или молчит (хост не отвечает / без CORS / http на
https-странице), байт нет ни в кэше, ни по ссылке — «Шаг 3» честно говорит
«отправлять нечего», владелец видит красную простыню и считает, что кнопка
сломана.

При этом копии арта часто ЖИВУТ НА САМОМ САЙТЕ: мастер media/<имя>, миниатюры
media/t3|t2|t/<имя>.webp (остались в репозитории от прежних сборок), https-
версия ссылки. Владелец прямо просит: скачивать на GitHub с сайта.

Лечение
-------
1. nxFetchArtBytes(url) (assets/qr-transfer.js) — цепочка копий: mediaUrl →
   мастер media/<имя> на этом сайте → миниатюры t3/t2/t (nxBigFor/nxThumbFor)
   → https-апгрейд http-ссылки → исходная ссылка. Первые найденные байты
   побеждают; каждый найденный байт ещё и кладётся в кэш устройства
   (imgCachePut), чтобы следующие проходы не дёргали сеть.
2. nxGhPushMedia.blobOf: нет блоба в кэше — раньше было «нет в кэше: имя» и
   пропуск файла; теперь байты добираются nxFetchArtBytes (копии с сайта).
   Именно это делает «Шаг 3» рабочей кнопкой «скачать с сайта → на GitHub».
3. nxAutoMediaPushRun: кэш пуст, а в очереди есть файлы — раньше «отправлять
   нечего»; теперь очередь передаётся в nxGhPushMedia без блобов (байты
   доберутся на шаге 2), с прогрессом «кэш пуст — тяну арты из копий на
   сайте». Работает и для автоотправки (тумблер ВКЛ): те же 6 файлов за
   подход, троттлинг 10 минут не меняется.
4. nxCacheAll («Шаг 1»): ссылка молчит/без CORS — пробуем копии с сайта и
   кладём их в кэш, вместо тихого пропуска.
5. nxCheckLinks: «нет кэша, ссылка молчит» / «ссылка не работает» теперь
   сначала спрашивают копии на сайте: копия есть — карточка помечается
   рабочей (и сразу кэшируется), нет — в сообщении честно «…копии на сайте
   тоже нет». Красная простыня остаётся только для реально безнадёжных карт.

Менялся только assets/qr-transfer.js — тег сборки nxmob225 -> nxmob226
(index.html ×8, sw.js, tools/build.py): qr-transfer.js кешируется отдельно.

Проверка/применение:
    python3 tools/_b482_patch.py --check
    python3 tools/_b482_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob225'
TAG_NEW = 'nxmob226'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

# --------------------------------------------------------------------------- #
# qr-transfer.js: цепочка копий арта на сайте
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/qr-transfer.js', 1,
              r'''function nxPendingMediaList() { // b359: только СПИСОК (имя + ссылка), ничего не грузим в память''',
              r'''// b482: байты арта из ЛЮБОЙ копии, доступной с сайта: мастер mediaUrl
// (same-origin/зеркало) → мастер media/<имя> на этом сайте → миниатюры
// t3/t2/t → https-апгрейд http-ссылки (mixed-content) → исходная ссылка.
// Владелец: «должно автоматически скачивать картинки на гитхаб с сайта» —
// этого хватателя байтов не хватало конвейеру отправки (b344/b359), который
// умел брать байты только из кэша устройства.
function nxFetchArtBytes(url) {
    var tries = [];
    var get = function (u) {
        if (!u || tries.indexOf(u) >= 0) return Promise.resolve(null);
        tries.push(u);
        return fetch(u, { mode: 'cors' }).then(function (r) {
            if (!r.ok) return null;
            return r.blob().then(function (b) { return (b && b.size) ? { blob: b, url: u } : null; });
        }).catch(function () { return null; });
    };
    var cands = [];
    try { cands.push(mediaUrl(url)); } catch (e) { cands.push(url); }
    try { cands.push('media/' + nxMediaKey(url)); } catch (e) {}
    try { var t3 = nxBigFor(url); if (t3) cands.push(t3); } catch (e) {}
    try { var t2 = nxThumbFor(url, 'mid'); if (t2) cands.push(t2); } catch (e) {}
    try { var t1 = nxThumbFor(url, 'small'); if (t1) cands.push(t1); } catch (e) {}
    cands.slice().forEach(function (c) { if (String(c).indexOf('http://') === 0) cands.push('https://' + c.slice(7)); });
    var chain = Promise.resolve(null);
    cands.forEach(function (c) { chain = chain.then(function (hit) { return hit || get(c); }); });
    return chain;
}
function nxPendingMediaList() { // b359: только СПИСОК (имя + ссылка), ничего не грузим в память'''))

# --------------------------------------------------------------------------- #
# qr-transfer.js: blobOf добирает байты из копий на сайте
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/qr-transfer.js', 1,
              r'''    function blobOf(it) {
        return (it.blob
            ? Promise.resolve(it.blob)
            : imgCacheGetBlob(it.url).then(function (b) { if (!b || !b.size) throw new Error('нет в кэше: ' + it.name); return b; })
        ).then(function (b) {''',
              r'''    function blobOf(it) {
        return (it.blob
            ? Promise.resolve(it.blob)
            : imgCacheGetBlob(it.url).then(function (b) {
                if (b && b.size) return b;
                // b482: кэша нет — ищем байты среди копий на сайте (мастер media/,
                // миниатюры t3/t2/t, https-версия ссылки): «Шаг 3» и автоотправка
                // шлют арт на GitHub даже с пустым кэшем устройства
                return nxFetchArtBytes(it.url).then(function (hit) {
                    if (!hit) throw new Error('нет в кэше и нет копии на сайте: ' + it.name);
                    try { imgCachePut(it.url, hit.blob); } catch (e) {} // следующий пройдёт без сети
                    return hit.blob;
                });
            })
        ).then(function (b) {'''))

# --------------------------------------------------------------------------- #
# qr-transfer.js: пустой кэш — не повод отказывать «Шагу 3» и автоотправке
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/qr-transfer.js', 1,
              r'''        if (!items.length) {
            if (manual) { nxStatus('Отправлять нечего: новых картинок в кэше нет. Нажмите «Шаг 1. Скачать все картинки»', 'err'); try { nxOwnerToast('В кэше нет новых картинок для отправки', 'error'); } catch (e) {} }
            else nxStatus('');
            unblock(); finish(0); return;
        }''',
              r'''        if (!items.length && pendingAll.length) {
            // b482: кэш пуст — не повод отказывать: байты дотянутся из копий на
            // сайте прямо в nxGhPushMedia (blobOf). Владелец: «должно
            // автоматически скачивать картинки на гитхаб с сайта».
            items = pendingAll.slice(0, cap).map(function (p) { return { name: p.name, url: p.url }; });
            nxProgress(0.1, 'Кэш пуст — тяну арты из копий на сайте: ' + items.length + ' из ' + pendingAll.length);
        }
        if (!items.length) {
            if (manual) { nxStatus('Отправлять нечего: новых картинок в кэше нет и копий на сайте не нашлось. Нажмите «Шаг 1. Скачать все картинки»', 'err'); try { nxOwnerToast('В кэше нет новых картинок для отправки', 'error'); } catch (e) {} }
            else nxStatus('');
            unblock(); finish(0); return;
        }'''))

# --------------------------------------------------------------------------- #
# qr-transfer.js: «Шаг 1» — молча мёртвую ссылку подменяем копией с сайта
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/qr-transfer.js', 1,
              r'''            imgCacheStoreFromNetwork(j.eff).then(ou => { if (ou) fresh++; tick(); }, () => tick());''',
              r'''            imgCacheStoreFromNetwork(j.eff).then(ou => { if (ou) fresh++; tick(); }, () => {
                // b482: ссылка молчит/без CORS — пробуем копии на сайте (мастер
                // media/, миниатюры, https-версия) и кладём их байты в кэш
                nxFetchArtBytes(j.eff).then(hit => {
                    if (hit) { try { imgCachePut(j.eff, hit.blob); } catch (e) {} fresh++; }
                    tick();
                }, () => tick());
            });'''))

# --------------------------------------------------------------------------- #
# qr-transfer.js: проверка ссылок не пугает, если копия живёт на сайте
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/qr-transfer.js', 1,
              r'''                var t = setTimeout(function () {
                    if (done) return; done = true;
                    if (!good[it.name]) problems.push(where + ': нет кэша, ссылка молчит');
                    fin();
                }, 12000);''',
              r'''                var t = setTimeout(function () {
                    if (done) return; done = true;
                    // b482: ссылка молчит — сперва спрашиваем копии на сайте
                    // (media/, миниатюры): копия есть → карточка рабочая, её
                    // восстановит автоотправка; пугаем только безнадёжными
                    if (!good[it.name]) {
                        nxFetchArtBytes(eff).then(function (hit) {
                            if (hit) { try { imgCachePut(eff, hit.blob); } catch (e2) {} good[it.name] = 1; fin(); return; }
                            problems.push(where + ': нет кэша, ссылка молчит, копии на сайте нет');
                            fin();
                        }, function () { problems.push(where + ': нет кэша, ссылка молчит, копии на сайте нет'); fin(); });
                        return;
                    }
                    fin();
                }, 12000);'''))

PAIRS.append(('assets/qr-transfer.js', 1,
              r'''                im2.onerror = function () {
                    if (done) return; done = true; clearTimeout(t);
                    if (!good[it.name]) problems.push(where + ': ссылка не работает и нет кэша');
                    fin();
                };''',
              r'''                im2.onerror = function () {
                    if (done) return; done = true; clearTimeout(t);
                    // b482: ссылка не работает — но копия на сайте спасает карточку
                    if (!good[it.name]) {
                        nxFetchArtBytes(eff).then(function (hit) {
                            if (hit) { try { imgCachePut(eff, hit.blob); } catch (e2) {} good[it.name] = 1; fin(); return; }
                            problems.push(where + ': ссылка не работает, кэша и копии на сайте нет');
                            fin();
                        }, function () { problems.push(where + ': ссылка не работает, кэша и копии на сайте нет'); fin(); });
                        return;
                    }
                    fin();
                };'''))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8', newline='') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, cnt, old, new in PAIRS:
        txt = files.get(rel) or read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        if n in txt:
            problems.append('%s: правка уже применена: %s...' % (rel, o[:60]))
            continue
        if txt.count(o) != cnt:
            problems.append('%s: якорь встретился %d раз вместо %d: %s...' % (rel, txt.count(o), cnt, o[:60]))
            continue
        files[rel] = txt.replace(o, n, 1)
    for rel in TAG_FILES:
        txt = files.get(rel) or read(rel)
        if TAG_NEW in txt:
            problems.append('%s: тег уже %s' % (rel, TAG_NEW))
            continue
        if TAG_OLD not in txt:
            problems.append('%s: нет тега %s' % (rel, TAG_OLD))
            continue
        files[rel] = txt.replace(TAG_OLD, TAG_NEW)
    if problems:
        for p in problems:
            print('ПРОБЛЕМА:', p)
        return 1
    if '--check' in sys.argv:
        print('b482: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b482: отправка на GitHub тянет арты из копий на сайте; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
