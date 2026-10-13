#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b424 — «в наградах ачивки-награды в кружочки за собранные альбомы… с обложками».

Просьба владельца: во вкладке «Награды» показать достижения за альбомы в виде
КРУГЛЫХ значков с обложками альбомов.

Стало:

* новая карточка «Значки альбомов» в секции наград (после «Достижений»):
  по круглому значку на каждый альбом (pack) игры;
* собранный альбом — яркий значок: обложка пака в круге, янтарное кольцо,
  свечение и галочка; несобранный — серый (grayscale, затемнение) с дробью
  «собрано/всего» прямо на обложке;
* под значком — название альбома, в шапке — счётчик «Собрано: N из M»;
* обложка берётся тем же путём, что в Альбомах и Магазине:
  mediaThumb(pack.image) с фолбэком mediaUrl и imgErrorChain;
* рендер вызывается из renderRewards(), то есть значки обновляются при каждом
  открытии вкладки и после каждого вскрытия пака (renderRewardsIfVisible);
* монет за значки не начисляется — это витрина коллекции: монетные награды за
  альбомы уже есть в достижениях (album_complete, albums_3/5/10).

Запуск:  python3 tools/_b424_patch.py            — применить
         python3 tools/_b424_patch.py --check    — только проверить якоря
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_V = 'nxmob85'
NEW_V = 'nxmob86'

# --------------------------------------------------------------------------- #
# index.html: новая карточка в секции наград
# --------------------------------------------------------------------------- #
HTML_PATCHES = [
    ('карточка «Значки альбомов»',
     """                <div id="rewards-achievements-grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"></div>
            </div>
        </section>""",
     """                <div id="rewards-achievements-grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"></div>
            </div>

            <!-- b424: круглые значки за собранные альбомы — с обложками -->
            <div class="bg-slate-900/80 p-4 sm:p-6 rounded-2xl border border-slate-800 space-y-4">
                <div class="flex flex-wrap justify-between items-center gap-2">
                    <h3 class="text-lg font-bold text-white flex items-center space-x-2">
                        <i class="fa-solid fa-medal text-amber-400"></i>
                        <span>Значки альбомов</span>
                    </h3>
                    <span class="text-xs text-slate-400" id="album-badges-counter"></span>
                </div>
                <p class="text-[11px] text-slate-500 leading-snug">Круглый значок с обложкой загорается янтарём, когда альбом собран полностью: обложка, кольцо и галочка. Несобранные альбомы — серые, с прогрессом «собрано/всего» прямо на обложке.</p>
                <div id="rewards-album-badges" class="flex flex-wrap gap-3 sm:gap-4"></div>
            </div>
        </section>"""),
]

# --------------------------------------------------------------------------- #
# app.js: рендер значков + вызов из renderRewards
# --------------------------------------------------------------------------- #
OLD_REWARDS_TAIL = """            }).join('');
        }
"""
# якорь уточняем контекстом: конец renderRewards — последний .join('') перед закрытием функции,
# после блока достижений. Берём уникальный хвост блока достижений:
OLD_ACH_TAIL = """                            ${prog && !unlocked ? `
                                <div class="mt-2 flex items-center gap-2">
                                    <div class="flex-grow bg-slate-800 rounded-full h-1.5 overflow-hidden"><div class="bg-slate-500 h-full transition-all duration-500" style="width: ${pct}%"></div></div>
                                    <span class="text-[10px] font-mono text-slate-500 whitespace-nowrap">${prog[0]}/${prog[1]}</span>
                                </div>` : ''}
                        </div>
                    </div>`;
            }).join('');
"""

NEW_ACH_TAIL = OLD_ACH_TAIL + """
            // b424: круглые значки за собранные альбомы — с обложками
            renderAlbumBadges();
"""

MODULE_ANCHOR = "        // ============ ВКЛАДКА «НАГРАДЫ» ============\n"

MODULE = r'''        // ============ b424: ЗНАЧКИ АЛЬБОМОВ — КРУЖОЧКИ С ОБЛОЖКАМИ ============
        // По значку на каждый альбом игры: собранный — обложка в янтарном кольце
        // с галочкой и свечением; несобранный — серый, с дробью прогресса поверх
        // обложки. Монет не начисляет: это витрина коллекции (монетные награды за
        // альбомы уже живут в достижениях album_complete / albums_3/5/10).
        function albumPackProgress(p) {
            const cs = (state.cards || []).filter(c => c.packId === p.id);
            let have = 0;
            for (let i = 0; i < cs.length; i++) if (state.collection && state.collection[cs[i].id]) have++;
            return [have, cs.length];
        }
        function renderAlbumBadges() {
            const box = document.getElementById('rewards-album-badges');
            if (!box) return;
            const packs = state.packs || [];
            const items = packs.map(p => {
                const pr = albumPackProgress(p);
                return { p: p, have: pr[0], total: pr[1], done: pr[1] > 0 && pr[0] >= pr[1] };
            });
            const cnt = document.getElementById('album-badges-counter');
            if (cnt) {
                const doneN = items.filter(i => i.done).length;
                cnt.innerHTML = 'Собрано: <b class="text-amber-400">' + doneN + '</b> из ' + items.length;
            }
            box.innerHTML = items.map(i => {
                const cover = mediaThumb(i.p.image) || mediaUrl(i.p.image);
                const title = jpcEsc(i.p.title || i.p.id);
                return '<div class="flex flex-col items-center gap-1.5" style="width:5.5rem">' +
                    '<div class="relative w-20 h-20 rounded-full overflow-hidden border-2 shrink-0 ' +
                        (i.done ? 'border-amber-400 shadow-[0_0_18px_rgba(251,191,36,.45)]' : 'border-slate-700') + '" ' +
                        'title="' + title + ' — ' + i.have + '/' + i.total + '">' +
                        '<img src="' + cover + '" alt="' + title + '" class="w-full h-full object-cover ' + (i.done ? '' : 'grayscale') + '" loading="lazy" decoding="async" onerror="this.onerror=null;imgErrorChain(this);">' +
                        (i.done
                            ? '<div class="absolute inset-0 flex items-end justify-center pb-1.5 bg-gradient-to-t from-amber-950/85 via-transparent to-transparent"><i class="fa-solid fa-check text-amber-300 text-sm"></i></div>'
                            : '<div class="absolute inset-0 bg-slate-950/70 flex items-center justify-center"><span class="text-[11px] font-mono font-bold text-slate-300">' + i.have + '/' + i.total + '</span></div>') +
                    '</div>' +
                    '<span class="text-[10px] font-bold text-center leading-tight line-clamp-2 ' + (i.done ? 'text-amber-300' : 'text-slate-500') + '">' + title + '</span>' +
                '</div>';
            }).join('');
        }

'''

JS_PATCHES = [
    ('модуль значков альбомов', MODULE_ANCHOR, MODULE + MODULE_ANCHOR),
    ('вызов из renderRewards', OLD_ACH_TAIL, NEW_ACH_TAIL),
]


# --------------------------------------------------------------------------- #
def patch_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise AssertionError('якорь «%s» встретился %d раз (нужно 1)' % (label, n))
    return text.replace(old, new, 1)


def main():
    check = '--check' in sys.argv
    js = os.path.join(ROOT, 'assets', 'app.js')
    html = os.path.join(ROOT, 'index.html')

    if check:
        bad = 0
        s = open(js, encoding='utf-8').read()
        for label, old, _n in JS_PATCHES:
            n = s.count(old); bad += (n != 1); print('  %s %-36s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        h = open(html, encoding='utf-8').read()
        for label, old, _n in HTML_PATCHES:
            n = h.count(old); bad += (n != 1); print('  %s %-36s %d' % ('OK ' if n == 1 else 'BAD', label, n))
        return 1 if bad else 0

    s = open(js, encoding='utf-8').read()
    for label, old, new in JS_PATCHES:
        s = patch_once(s, old, new, label); print('  · %-36s ok' % label)
    open(js, 'w', encoding='utf-8', newline='').write(s)

    h = open(html, encoding='utf-8').read()
    for label, old, new in HTML_PATCHES:
        h = patch_once(h, old, new, label); print('  · %-36s ok' % label)
    open(html, 'w', encoding='utf-8', newline='').write(h)

    for p, old, new in ((html, '?v=' + OLD_V, '?v=' + NEW_V),
                        (os.path.join(ROOT, 'sw.js'), "const VERSION = '%s';" % OLD_V, "const VERSION = '%s';" % NEW_V),
                        (os.path.join(ROOT, 'tools', 'build.py'), "BUILD_TAG = '%s'" % OLD_V, "BUILD_TAG = '%s'" % NEW_V)):
        t = open(p, encoding='utf-8').read()
        n = t.count(old)
        if n:
            open(p, 'w', encoding='utf-8', newline='').write(t.replace(old, new))
        print('  · версия %-28s ×%d → %s' % (os.path.basename(p), n, NEW_V))
    return 0


if __name__ == '__main__':
    sys.exit(main())
