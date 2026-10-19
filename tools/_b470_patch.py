#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b470: CI перестаёт поднимать тег сборки из-за новых артов.

Вторая половина лечения «игра постоянно моргает» (первая — b468 на клиенте,
промежуточная — b469 в sync_thumb_maps.py).

Цепочка, которая и давала перезагрузки:

  автоотправка артов (b343/b341, assets/qr-transfer.js) коммитит новые арты
  в media/ — замер по истории origin/main: 24 пуша за 1,9 часа, ~12,8 в час,
  медиана 213 с, минимум 83 с
    -> экшен media-thumbs (on: push, paths: media/**)
    -> tools/thumbs_for_media.py догенерирует media/t, t2, t3
    -> шаг «Обновить карты и поднять ?v=» с guard'ом if: need == '1'
    -> guard СРАБАТЫВАЛ: после нового арта карты NX_EMBED_THUMB в app.js
       действительно расходятся, --check возвращает 1
    -> sync_thumb_maps.py --bump-version поднимает nxmobNN в index.html, sw.js,
       tools/build.py  (за вечер nxmob189 -> nxmob213, 24 подъёма)
    -> у каждого клиента nxAutoUpdCheck() (каждые 180 с и на каждое
       visibilitychange) видит расхождение тега и планирует тихую перезагрузку
    -> расхождение не рассасывалось, тег уезжал снова => перезагрузки постоянно

Почему подъём тега здесь не нужен по существу
---------------------------------------------
nxThumbFor() (assets/app.js:2111) для арта, которого ещё нет в картах сборки,
достраивает путь ПО СОГЛАШЕНИЮ media/t/<имя>.webp (b377), а файл к этому
моменту уже создан шагом «Догенерация миниатюр». При 404 imgErrorChain
откатывается на data-nx-full. То есть клиент с прежним app.js всё равно
получает миниатюру — перезагрузка не нужна. Карты синхронизируются ради
следующих сборок, а не ради текущих клиентов.

Цена отказа от подъёма тега — узкое окно: если клиент успел обратиться к
миниатюре ДО её генерации и запомнил 404, он до следующей естественной
перезагрузки может грузить мастер. Это несопоставимо мягче, чем постоянные
перезагрузки всех вкладок каждые 3 минуты.

Изменён ОДИН шаг в .github/workflows/media-thumbs.yml: --bump-version убран,
название и комментарий объясняют причину. --bump-version остаётся рабочим для
ручного запуска (b469 сделал его условным).

assets/app.js и index.html не менялись — тег сборки не поднимается.
Для пуша правки в .github/workflows/ нужен scope `workflow` у токена.

Проверка/применение:
    python3 tools/_b470_patch.py --check
    python3 tools/_b470_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = [
    ('.github/workflows/media-thumbs.yml', '''      # Версию кэша поднимаем ТОЛЬКО когда реально изменился assets/app.js:
      # иначе каждый добавленный трек mp3 сбрасывал бы кэш всем игрокам.
      - name: Обновить карты и поднять ?v=
        if: steps.sync.outputs.need == '1'
        run: python tools/sync_thumb_maps.py --bump-version''', '''      # b470: версию кэша здесь больше НЕ поднимаем.
      #
      # Прежняя защита (if: need == '1') не спасала. После каждого нового арта
      # карты NX_EMBED_THUMB действительно расходятся, need=1, тег nxmobNN
      # поднимался — а каждый подъём рассылает всем открытым вкладкам команду
      # «тихо перезагрузиться» (nxAutoUpdCheck каждые 180 с и на каждое
      # visibilitychange). Автоотправка артов пушит ~12,8 раза в час (замер по
      # истории: 24 пуша за 1,9 ч, медиана 213 с, минимум 83 с), за вечер тег
      # уехал nxmob189 -> nxmob213. Расхождение не рассасывалось никогда — тег
      # успевал уехать снова, поэтому вкладки перезагружались постоянно:
      # «игра моргает, невозможно играть», а у владельца вместе с перезагрузкой
      # улетала заполненная форма карточки в Студии.
      #
      # Подъём тега здесь не нужен по существу: nxThumbFor() для арта, которого
      # ещё нет в картах сборки, достраивает путь по соглашению media/t/<имя>.webp
      # (b377), а сам файл к этому моменту уже создан шагом «Догенерация
      # миниатюр». При 404 imgErrorChain откатывается на data-nx-full. То есть
      # клиент с прежним app.js всё равно получает миниатюру — без перезагрузки.
      # Карты синхронизируются ради следующих сборок, а не ради текущих клиентов.
      #
      # --bump-version оставлен в sync_thumb_maps.py для РУЧНОГО запуска, когда
      # правка app.js действительно должна доехать до всех сразу (b469: теперь он
      # поднимает тег только при реальном изменении app.js).
      - name: Обновить карты NX_EMBED_THUMB (без подъёма ?v= — см. b470)
        if: steps.sync.outputs.need == '1'
        run: python tools/sync_thumb_maps.py'''),
]


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8', newline='') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, old, new in PAIRS:
        txt = files.get(rel) or read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        if txt.count(o) != 1:
            problems.append('%s: якорь встретился %d раз' % (rel, txt.count(o)))
            continue
        files[rel] = txt.replace(o, n, 1)
    if problems:
        for p in problems:
            print('ПРОБЛЕМА:', p)
        return 1
    if '--check' in sys.argv:
        print('b470: якорь на месте, можно применять')
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b470: CI больше не поднимает ?v= из-за новых артов')
    return 0


if __name__ == '__main__':
    sys.exit(main())
