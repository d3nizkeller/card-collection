#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b416: ремонт ОБЛАЧНОГО документа общего банка (textdb nexus-tcg-jackpot-v2).

Алгоритм — ровно тот, что встроен в игру (jpRepairLedger в assets/app.js):
  1. выбросить счётчики led/won вне диапазона [0, JP_LED_CAP] (мусор, из-за
     которого банк замерзал: на 1e57 шаг double ≈ 8.7e40 и взносы исчезали);
  2. образовавшийся долг (Σвыплат > Σвзносов) покрыть ОДНОЙ служебной записью
     'house' — она общая для всех клиентов и сливается правилом max, поэтому
     ремонт идемпотентен.

Трогаем только jp.led и jp.won. Настройки (jpc), биржа (mk), статистика
игроков (st), зал славы (hall), имена и счётчик побед — без изменений.

Запуск:  python3 tools/repair_cloud_bank.py            — применить
         python3 tools/repair_cloud_bank.py --dry      — только показать
"""
import json
import os
import sys
import time
import urllib.request
from decimal import Decimal

URL = 'https://textdb.dev/api/data/nexus-tcg-jackpot-v2'
CAP = 10 ** 13          # JP_LED_CAP
SEED = 1000             # JACKPOT_SEED
HOUSE = 'house'         # JP_HOUSE
BACKUP_DIR = os.path.expanduser('~/jp-backups')


def fetch():
    # ВАЖНО: без «Accept: application/json» — с ним textdb отдаёт документ
    # двойным кодированием (JSON-строкой), а игра (jpFetch) читает его обычным текстом.
    req = urllib.request.Request(URL + '?nc=' + str(int(time.time() * 1000)),
                                headers={'User-Agent': 'b416-repair', 'Cache-Control': 'no-store'})
    raw = urllib.request.urlopen(req, timeout=45).read().decode('utf-8')
    # parse_int=int — целые в Python точные; parse_float=Decimal — чтобы 1e57 и
    # 4.9e18 не потеряли разряды при разборе
    return json.loads(raw, parse_float=Decimal, parse_int=int), raw


def dec(o):
    """Decimal → int/float для обратной сериализации (целые остаются целыми)."""
    return int(o) if o == o.to_integral_value() else float(o)


def bad(v):
    """jpLedBad: запись пригодна, только если это целое в [0, CAP]."""
    try:
        d = Decimal(str(v))
    except Exception:
        return True
    if not d.is_finite() or d < 0 or d > CAP:
        return True
    return d != d.to_integral_value()


def main():
    dry = '--dry' in sys.argv
    doc, raw = fetch()
    jp = doc.get('jp') or doc

    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    bak = os.path.join(BACKUP_DIR, 'nexus-tcg-jackpot-v2.%s.json' % stamp)
    with open(bak, 'w', encoding='utf-8') as f:
        f.write(raw)   # байт-в-байт копия того, что лежало в облаке
    print('бэкап документа (%d байт): %s' % (os.path.getsize(bak), bak))

    led, won = jp.get('led') or {}, jp.get('won') or {}
    dropped = [(k, str(v)) for k, v in list(led.items()) + list(won.items()) if bad(v)]
    nled = {k: int(Decimal(str(v))) for k, v in led.items() if not bad(v)}
    nwon = {k: int(Decimal(str(v))) for k, v in won.items() if not bad(v)}

    raw = SEED + sum(nled.values()) - sum(nwon.values())
    debt = SEED - raw
    if debt > 0:
        cur = nled.get(HOUSE, 0)
        nled[HOUSE] = min(cur + debt, CAP)
    raw2 = SEED + sum(nled.values()) - sum(nwon.values())

    def pool(led_sum, won_sum, floor):
        return max(0, floor) + max(0, (SEED + led_sum - won_sum) - SEED)

    fl = int(Decimal(str((doc.get('jpc') or {}).get('floor', SEED))))
    print('\n— ДО —')
    print('  записей led/won        : %d / %d' % (len(led), len(won)))
    print('  испорченных записей    : %d' % len(dropped))
    for k, v in sorted(dropped, key=lambda x: -Decimal(x[1]))[:6]:
        print('      %-14s %s' % (k, v))
    print('  банк (max(floor, raw)) : %s' % max(fl, int(SEED + sum(int(Decimal(str(v))) if not bad(v) else 0 for v in led.values()) - sum(int(Decimal(str(v))) if not bad(v) else 0 for v in won.values()))))
    print('  raw / долг             : %d / %d' % (raw, max(0, debt)))
    print('\n— ПОСЛЕ —')
    print('  записей led/won        : %d / %d' % (len(nled), len(nwon)))
    print('  запись дома (house)    : %s' % nled.get(HOUSE))
    print('  raw                    : %d' % raw2)
    print('  БАНК                   : %d  (пол %d + накоплено %d)' % (pool(sum(nled.values()), sum(nwon.values()), fl), fl, max(0, raw2 - SEED)))
    print('  зал славы / имена / победы / биржа / статистика: не трогаем (%d / %d / %d / %s / %s)' % (
        len(jp.get('hall') or []), len(jp.get('names') or {}), sum(int(v) for v in (jp.get('wins') or {}).values()),
        'да' if doc.get('mk') else 'нет', 'да' if doc.get('st') else 'нет'))

    if dry:
        print('\n--dry: документ НЕ отправлен')
        return 0

    # пишем максимально свежую версию: между чтением и записью живые игроки
    # могут запушить свои взносы/лоты — чиним ровно тот документ, который
    # лежит в облаке прямо сейчас (алгоритм детерминирован и идемпотентен)
    fresh, _raw2 = fetch()
    if fresh.get('updatedAt') != doc.get('updatedAt'):
        print('\n(документ обновился игроками между чтением и записью — чиним свежую версию %s)' % fresh.get('updatedAt'))
        doc = fresh
        jp = doc.get('jp') or doc
        led, won = jp.get('led') or {}, jp.get('won') or {}
        nled = {k: int(Decimal(str(v))) for k, v in led.items() if not bad(v)}
        nwon = {k: int(Decimal(str(v))) for k, v in won.items() if not bad(v)}
        raw2 = SEED + sum(nled.values()) - sum(nwon.values())
        if SEED - raw2 > 0:
            nled[HOUSE] = min(nled.get(HOUSE, 0) + (SEED - raw2), CAP)

    jp['led'], jp['won'] = nled, nwon
    doc['jp'] = jp
    doc['updatedAt'] = '%d-b416repair' % int(time.time() * 1000)
    body = json.dumps(doc, ensure_ascii=False, separators=(',', ':'), default=dec).encode('utf-8')
    # ровно как jpPush в игре: textdb — POST с text/plain (простой запрос без CORS-префлайта)
    req = urllib.request.Request(URL, data=body, method='POST',
                                headers={'Content-Type': 'text/plain', 'User-Agent': 'b416-repair'})
    r = urllib.request.urlopen(req, timeout=60)
    print('\nPOST → HTTP %d (%d байт)' % (r.status, len(body)))

    chk, _raw3 = fetch()
    cjp = chk.get('jp') or chk
    cl, cw = cjp.get('led') or {}, cjp.get('won') or {}
    left = [k for k, v in list(cl.items()) + list(cw.items()) if bad(v)]
    craw = SEED + sum(int(Decimal(str(v))) for v in cl.values() if not bad(v)) - sum(int(Decimal(str(v))) for v in cw.values() if not bad(v))
    print('\n— ПРОВЕРКА ОБЛАКА —')
    print('  испорченных записей осталось : %d' % len(left))
    print('  записей led/won              : %d / %d' % (len(cl), len(cw)))
    print('  raw / банк                   : %d / %d' % (craw, max(fl, craw)))
    print('  зал славы / статистика       : %d / %d игроков' % (len(cjp.get('hall') or []), len((chk.get('st') or {}).get('p') or {})))
    print('  биржа (mk) на месте          : %s' % ('да' if chk.get('mk') else 'нет'))
    print('  настройки (jpc) на месте     : %s' % ('да' if chk.get('jpc') else 'нет'))
    return 0 if not left else 1


if __name__ == '__main__':
    sys.exit(main())
