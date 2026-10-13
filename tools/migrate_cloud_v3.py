#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b421: переезд синхронизации банка с nexus-tcg-jackpot-v2 на -v3.

Зачем: в v2 накопились 8 283 ключа реестра (наследие вёдер b418 и разрядов)
и история rm; клиенты ДО nxmob82 продолжают пушить туда раздутый документ,
а max-merge не позволяет вычистить старые ключи из общего документа —
любая уборка в v2 откатывается их следующим пушем. На v3 пишут только
сборки с эпохами (ep) и обрезанным rm: документ стартует лёгким и таким
и остаётся.

Что делает скрипт (один раз):

  1. читает v2 (байт-в-байт бэкап в ~/jp-backups/);
  2. mk.rm — prune по возрасту (2 ч) и количеству (300), как marketRemovedPrune;
  3. jp.led / jp.won — все разряды каждого cid сводит в минимальный каскад
     (суммы сохраняются до монеты, банк не меняется);
  4. jp.ep = 1 — все клиенты b420+ примут этот реестр целиком, и старые
     ключи ниоткуда не вернутся;
  5. POST в v3 (если там уже есть живой документ с ep — ничего не трогает).

Остальное (lots, ledger, st, jpc, hall, hallCut, names, wins) копирует как есть.

Запуск:  python3 tools/migrate_cloud_v3.py            — применить
         python3 tools/migrate_cloud_v3.py --dry      — только показать
"""
import json
import os
import sys
import time
import urllib.request
from decimal import Decimal

SRC = 'https://textdb.dev/api/data/nexus-tcg-jackpot-v2'
DST = 'https://textdb.dev/api/data/nexus-tcg-jackpot-v3'
TIER0, TIER_MUL, TIERS = Decimal(10) ** 13, Decimal(1000), 24
RM_TTL = 2 * 60 * 60 * 1000
RM_MAX = 300
BACKUP_DIR = os.path.expanduser('~/jp-backups')


def fetch(url):
    req = urllib.request.Request(url + '?nc=%d' % int(time.time() * 1000),
                                headers={'User-Agent': 'b421-migrate', 'Cache-Control': 'no-store'})
    try:
        raw = urllib.request.urlopen(req, timeout=60).read().decode('utf-8')
    except Exception:
        return None, ''
    raw = raw.strip()
    if not raw:
        return None, ''
    return json.loads(raw, parse_float=Decimal, parse_int=int), raw


def tier_cap(i):
    return TIER0 * (TIER_MUL ** i)


def rebuild(field):
    totals = {}
    for k, v in (field or {}).items():
        k = str(k)
        h = k.find('#')
        base = k[:h] if h > 0 else k
        totals[base] = totals.get(base, Decimal(0)) + Decimal(int(v))
    out = {}
    for base, total in totals.items():
        left, i = total, 0
        while left > 0 and i < TIERS:
            put = min(left, tier_cap(i))
            if put > 0:
                out[base + ('#%d' % i if i else '')] = int(put)
                left -= put
            i += 1
        if left > 0:
            raise AssertionError('не хватит разрядов для %s' % base)
    return out


def prune_rm(rm):
    cut = int(time.time() * 1000) - RM_TTL
    keep = {k: int(v) for k, v in (rm or {}).items() if int(v) >= cut}
    if len(keep) > RM_MAX:
        for k in sorted(keep, key=lambda k: keep[k])[:len(keep) - RM_MAX]:
            del keep[k]
    return keep


def main():
    dry = '--dry' in sys.argv
    doc, raw = fetch(SRC)
    if not doc:
        print('v2 пуст или недоступен — выходить не с чем')
        return 1
    exist, exist_raw = fetch(DST)
    if exist and (exist.get('jp') or {}).get('ep') and (int(time.time() * 1000) - int(str(exist.get('updatedAt', '0')).split('-')[0] or 0) < 24 * 3600 * 1000):
        print('v3 уже живой (ep=%s, обновлялся недавно) — миграция не нужна' % exist['jp'].get('ep'))
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = os.path.join(BACKUP_DIR, 'v2-pre-migrate-%s.json' % time.strftime('%Y%m%d-%H%M%S'))
    with open(bak, 'w', encoding='utf-8') as f:
        f.write(raw)
    print('бэкап v2: %s (%d КБ)' % (bak, len(raw) // 1024))

    mk = doc.get('mk') or {}
    rm0 = len(mk.get('rm') or {})
    mk['rm'] = prune_rm(mk.get('rm'))
    jp = doc.get('jp') or {}
    led0, won0 = len(jp.get('led') or {}), len(jp.get('won') or {})
    raw_before = 1000 + sum(Decimal(int(v)) for v in (jp.get('led') or {}).values()) - sum(Decimal(int(v)) for v in (jp.get('won') or {}).values())
    jp['led'] = rebuild(jp.get('led'))
    jp['won'] = rebuild(jp.get('won'))
    jp['ep'] = 1
    raw_after = 1000 + sum(Decimal(v) for v in jp['led'].values()) - sum(Decimal(v) for v in jp['won'].values())
    assert raw_before == raw_after, 'суммы реестра изменились!'
    doc['updatedAt'] = '%d-b421migrate' % int(time.time() * 1000)
    body = json.dumps(doc, ensure_ascii=False, separators=(',', ':'), default=int).encode('utf-8')

    print('— v2 БЫЛО — rm %d, led %d, won %d, %d КБ' % (rm0, led0, won0, len(raw) // 1024))
    print('— v3 СТАЛО — rm %d, led %d, won %d, %d КБ, ep=1, raw=%s' % (len(mk['rm']), len(jp['led']), len(jp['won']), len(body) // 1024, raw_after))
    if dry:
        print('\n--dry: v3 НЕ записан')
        return 0
    r = urllib.request.urlopen(urllib.request.Request(DST, data=body, method='POST',
                                                      headers={'Content-Type': 'text/plain', 'User-Agent': 'b421-migrate'}), timeout=90)
    print('POST v3 %d КБ → HTTP %s' % (len(body) // 1024, r.status))
    chk, chkraw = fetch(DST)
    cjp = chk.get('jp') or {}
    print('— ПРОВЕРКА v3 — %d КБ, rm %d, led %d, ep %s, raw %s' % (
        len(chkraw) // 1024, len((chk.get('mk') or {}).get('rm') or {}), len(cjp.get('led') or {}), cjp.get('ep'),
        1000 + sum(Decimal(int(v)) for v in (cjp.get('led') or {}).values()) - sum(Decimal(int(v)) for v in (cjp.get('won') or {}).values())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
