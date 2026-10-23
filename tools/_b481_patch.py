#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b481: экспорт карты сам находит арт и АВТОМАТИЧЕСКИ сохраняет его на GitHub.

Жалоба владельца (скриншот тоста): «Не удалось скачать карточку: NetworkError
when attempting to fetch resource… чего она автоматически не сохраняет на
гитхаб?»

Разбор
------
downloadCardPng (b479) тянул арт одним fetch(mediaUrl(card.image)). Он падал с
NetworkError, когда ссылка внешняя без CORS или http:// на https-странице
(mixed-content: <img> такую картинку показывает, а fetch браузер запрещает).
Байты при этом иногда добыть можно из ДРУГИХ копий арта, которые уже есть у
сайта: миниатюры media/t3/t2/t, вшитый в сборку арт (NX_EMBED_MEDIA),
https-версия той же ссылки. А если байты добыты вне media/ — владелец хочет,
чтобы сайт сам положил их в репозиторий, как это делает кнопка «Загрузить с
устройства → GitHub».

Лечение
-------
1. nxExportArtBlob(card) (assets/app.js, блок b479) пробует копии арта по
   цепочке: мастер mediaUrl → миниатюры t3/t2/t (nxBigFor/nxThumbFor) →
   вшитый арт NX_EMBED_MEDIA (data:-URL) → апгрейд http:// → https://
   (mixed-content) → исходная ссылка напрямую (если вдруг отдаёт CORS).
   Первый ответ с байтами побеждает; в ошибке перечисляется, что пробовали.
2. АВТОСОХРАНЕНИЕ НА GITHUB: если байты добыты НЕ из мастера media/ (источник
   embed / https-upgrade / raw) и в Студии сохранён токен GitHub (nxGhToken —
   тот же, что использует автоотправка картинок b343/b359), экспорт кладёт
   копию в media/ через nxGhPushMedia (имя card_<время>_auto.<ext>),
   перезаписывает card.image на свежую публичную ссылку media/… (как
   nxUploadToGithub), помечает файл в nxMediaPushedSet, сохраняет состояние и
   публикует в комнату: следующий экспорт и все игроки берут арт уже с
   GitHub, а не с чужого хоста. Тоста об автосохранении хватает на один раз;
   без токена — тихо пропускаем (экспорт продолжается из добытых байтов).
   Миниатюрные источники (thumb-*) намеренно НЕ сохраняются как мастер:
   незачем понижать качество карты в репозитории.
3. Тост об ошибке уточнён: перечисляет причины (внешняя ссылка без CORS,
   http на https-странице) и совет залить арт кнопкой «Загрузить с
   устройства → GitHub».

Менялся только assets/app.js — тег сборки nxmob224 -> nxmob225.

Проверка/применение:
    python3 tools/_b481_patch.py --check
    python3 tools/_b481_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob224'
TAG_NEW = 'nxmob225'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

# --------------------------------------------------------------------------- #
# assets/app.js: nxArtBlobUrl -> nxExportArtBlob с цепочкой копий арта
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''        function nxArtBlobUrl(url) {
            // fetch→blob→objectURL: canvas не tainted даже с внешним хостом (если
            // тот отдаёт CORS), а_same-origin media/ прилетает из кэша мгновенно
            return fetch(url, { mode: 'cors' }).then(r => {
                if (!r.ok) throw new Error('арт не ответил (' + r.status + ')');
                return r.blob();
            }).then(b => URL.createObjectURL(b));
        }''',
              r'''        // b481: цепочка копий арта для экспорта: мастер (same-origin/зеркало) →
        // миниатюры media/t3/t2/t → вшитый в сборку арт (NX_EMBED_MEDIA, data:-URL)
        // → апгрейд http://→https:// (mixed-content: <img> такую картинку
        // показывает, а fetch браузер запрещает) → исходная ссылка напрямую
        // (если вдруг отдаёт CORS). Первый ответ с байтами побеждает.
        async function nxExportArtBlob(card) {
            const tried = [];
            const grab = async (url, src) => {
                if (!url || tried.indexOf(url) >= 0) return null;
                tried.push(url);
                try {
                    const r = await fetch(url, { mode: 'cors' });
                    if (!r.ok) return null;
                    const b = await r.blob();
                    return (b && b.size) ? { blob: b, src: src } : null;
                } catch (e) { return null; }
            };
            const main = mediaUrl(card.image) || card.image;
            let hit = await grab(main, 'master');
            if (hit) return hit;
            const tiers = [];
            try { tiers.push([nxBigFor(card.image), 'thumb-t3']); } catch (e) {}
            try { tiers.push([nxThumbFor(card.image, 'mid'), 'thumb-t2']); } catch (e) {}
            try { tiers.push([nxThumbFor(card.image, 'small'), 'thumb-t']); } catch (e) {}
            for (const t of tiers) {
                hit = await grab(t[0], t[1]);
                if (hit) return hit;
            }
            try {
                const key = nxMediaKey(main) || nxMediaKey(card.image);
                const emb = key && typeof NX_EMBED_MEDIA !== 'undefined' ? NX_EMBED_MEDIA[key] : '';
                hit = await grab(emb, 'embed');
                if (hit) return hit;
            } catch (e) {}
            if (String(main).indexOf('http://') === 0) {
                hit = await grab('https://' + main.slice(7), 'https-upgrade');
                if (hit) return hit;
            }
            if (main !== card.image) {
                hit = await grab(card.image, 'raw');
                if (hit) return hit;
            }
            throw new Error('арт недоступен ни в одной копии (мастер, миниатюры, вшитый, https, напрямую; попыток: ' + tried.length + ')');
        }
        function nxArtBlobUrl(url) { // совместимость: objectURL из первой добытой копии
            return nxExportArtBlob({ image: url }).then(a => URL.createObjectURL(a.blob));
        }'''))

# --------------------------------------------------------------------------- #
# assets/app.js: downloadCardPng — автосохранение арта на GitHub
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            let objUrl = '';
            try {
                objUrl = await nxArtBlobUrl(mediaUrl(card.image) || card.image);
                const img = new Image();''',
              r'''            let objUrl = '';
            try {
                const art = await nxExportArtBlob(card);
                // b481: АВТОСОХРАНЕНИЕ АРТА НА GITHUB. Байты добыты не из мастера
                // media/ (вшитый арт, https-апгрейд, внешняя ссылка с CORS) и в
                // Студии сохранён токен — кладём копию в media/ тем же механизмом,
                // что кнопка «Загрузить с устройства → GitHub» (nxGhPushMedia),
                // и перезаписываем ссылку карты: следующий экспорт и все игроки
                // берут арт с GitHub, а не с чужого хоста. Миниатюры (thumb-*)
                // мастером не сохраняем нарочно — не понижаем качество в репо.
                if (['embed', 'https-upgrade', 'raw'].indexOf(art.src) >= 0) {
                    let saved = '';
                    try {
                        if (typeof nxGhToken === 'function' && nxGhToken() && typeof nxGhPushMedia === 'function') {
                            const bt = String(art.blob.type || '');
                            const ext = bt === 'image/webp' ? '.webp' : bt === 'image/png' ? '.png' : bt === 'image/gif' ? '.gif' : '.jpg';
                            const name = 'card_' + Date.now().toString(36) + '_auto' + ext;
                            await new Promise((res, rej) => nxGhPushMedia(nxGhRepoName(), [{ name: name, blob: art.blob }], res, m => rej(new Error(m))));
                            card.image = nxMediaPublicUrl(name);
                            try { NX_EMBED_MEDIA[name] = 'media/' + name; } catch (e) {}
                            try { const s = nxMediaPushedSet(); s.add(name); nxMediaSavePushed(s); } catch (e) {}
                            saveState();
                            try { cloudPublishSoon(); } catch (e) {}
                            saved = name;
                        }
                    } catch (e) { saved = ''; } // без токена/без прав — тихо: экспорт продолжится из добытых байтов
                    if (saved) showToast('📦 Арт автоматически сохранён на GitHub: media/' + saved + ' — ссылка карты обновлена', 'success');
                }
                objUrl = URL.createObjectURL(art.blob);
                const img = new Image();'''))

PAIRS.append(('assets/app.js', 1,
              r'''                showToast('Не удалось скачать карточку: ' + (e && e.message ? e.message : e) + '. Если арт по внешней ссылке без CORS — залейте картинку на GitHub кнопкой «Загрузить с устройства»', 'error');''',
              r'''                showToast('Не удалось скачать карточку: ' + (e && e.message ? e.message : e) + '. Частые причины: внешняя ссылка без CORS или http:// на https-странице. Залейте картинку на GitHub кнопкой «Загрузить с устройства → GitHub» — и экспорт заработает', 'error');'''))


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
        print('b481: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b481: экспорт сам находит арт и автосохраняет его в media/ GitHub; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
