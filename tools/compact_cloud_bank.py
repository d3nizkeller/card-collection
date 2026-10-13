#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b420: разовая уборка облачного документа nexus-tcg-jackpot-v2.

Делает то же, что b420 в игре, но прямо в облаке, чтобы синхронизация
починилась у всех сразу (включая клиентов, которые ещё не обновились):

  1. mk.rm — tombstone снятых лотов: оставляем только моложе 2 часов и не
     больше 300 записей (было 16 918 = 728 КБ);
  2. jp.led / jp.won — все «#»-разряды и старые ключи каждого cid сводятся в
     минимальный каскад разрядов (1e13, 1e16, 1e19, …): суммы сохраняются,
     банк не меняется (было 4200 ключей = 134 КБ);
  3. jp.ep = 1 — клиенты b420+ примут уплотнённый реестр целиком.

Остальное (lots, ledger, st, jpc, hall, hallCut, names, wins) не трогает.
Перед записью — байт-в-байт бэкап в ~/jp-backups/ и перечитывание самой
свежей версии прямо перед POST (чтобы не затереть пуши живых игроков).

Запуск:  python3 tools/compact_cloud_bank.py            — применить
         python3 tools/compact_cloud_bank.py --dry      — только показать
"""
import json
import os
import sys
import time
import urllib.request
from decimal import Decimal

URL = 'https://textdb.dev/api/data/nexus-tcg-jackpot-v2'
TIER0, TIER_MUL, TIERS = Decimal(10) ** 13, Decimal(1000), 24
RM_TTL = 2 * 60 * 60 * 1000
RM_MAX = 300
BACKUP_DIR = os.path.expanduser('~/jp-backups')


def fetch():
    req = urllib.request.Request(URL + '?nc=%d' % int(time.time() * 1000),
                                headers={'User-Agent': 'b420-compact', 'Cache-Control': 'no-store'})
    raw = urllib.request.urlopen(req, timeout=60).read().decode('utf-8')
    return json.loads(raw, parse_float=Decimal, parse_int=int), raw


def tier_cap(i):
    return TIER0 * (TIER_MUL ** i)


def cascade(total):
    out, left, i = {}, total, 0
    while left > 0 and i < TIERS:
        put = min(left, tier_cap(i))
        if put > 0:
            out[i] = put
            left -= put
        i += 1
    return out, left


def rebuild(field):
    totals = {}
    for k, v in (field or {}).items():
        k = str(k)
        h = k.find('#')
        base = k[:h] if h > 0 else k
        totals[base] = totals.get(base, Decimal(0)) + Decimal(int(v))
    out = {}
    for base, total in totals.items():
        parts, left = cascade(Decimal(int(total)))
        if left > 0:
            raise AssertionError('не хватит разрядов для %s: %s' % (base, total))
        for i, v in parts.items():
            out[base + ('#%d' % i if i else '')] = int(v)
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
    doc, raw = fetch()
    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = os.path.join(BACKUP_DIR, 'pre-compact-%s.json' % time.strftime('%Y%m%d-%H%M%S'))
    with open(bak, 'w', encoding='utf-8') as f:
        f.write(raw)
    print('бэкап: %s (%d КБ)' % (bak, len(raw) // 1024))

    with_ledger = '--ledger' in sys.argv
    mk = doc.get('mk') or {}
    rm0 = len(mk.get('rm') or {})
    mk['rm'] = prune_rm(mk.get('rm'))
    jp = doc.get('jp') or {}
    led0, won0 = len(jp.get('led') or {}), len(jp.get('won') or {})
    raw_before = 1000 + sum(Decimal(int(v)) for v in (jp.get('led') or {}).values()) - sum(Decimal(int(v)) for v in (jp.get('won') or {}).values())
    if with_ledger:
        # ВНИМАНИЕ: уплотнение реестра безопасно только когда в игре нет клиентов
        # ДО b420 (они не знают ep и при max-слиянии удвоят банк старыми ключами).
        # Игра делает это сама (кнопка «Уплотнить реестр» / авто-триггер с охраной);
        # сюда флаг --ledger — на крайний случай.
        jp['led'] = rebuild(jp.get('led'))
        jp['won'] = rebuild(jp.get('won'))
        jp['ep'] = max(1, int(jp.get('ep') or 0) + 1)
    raw_after = 1000 + sum(Decimal(int(v)) for v in jp['led'].values()) - sum(Decimal(int(v)) for v in jp['won'].values())

    print('\n— БЫЛО —  rm: %d, led: %d, won: %d, документ %d КБ' % (rm0, led0, won0, len(raw) // 1024))
    size = len(json.dumps(doc, ensure_ascii=False, separators=(',', ':'), default=int).encode('utf-8'))
    print('— СТАЛО — rm: %d, led: %d, won: %d, документ ~%d КБ, ep=%s' % (len(mk['rm']), len(jp['led']), len(jp['won']), size // 1024, jp.get('ep', 0)))
    print('raw банка: %s → %s (должен совпасть)' % (raw_before, raw_after))
    assert raw_before == raw_after, 'суммы реестра изменились!'
    if dry:
        print('\n--dry: документ НЕ отправлен')
        return 0

    fresh, _ = fetch()
    if fresh.get('updatedAt') != doc.get('updatedAt'):
        print('(документ обновился игроками между чтением и записью — перечитываю и повторяю)')
        doc = fresh
        mk = doc.get('mk') or {}
        mk['rm'] = prune_rm(mk.get('rm'))
        jp = doc.get('jp') or {}
        if with_ledger:
            jp['led'] = rebuild(jp.get('led'))
            jp['won'] = rebuild(jp.get('won'))
            jp['ep'] = max(1, int(jp.get('ep') or 0) + 1)
    doc['updatedAt'] = '%d-b420compact' % int(time.time() * 1000)
    body = json.dumps(doc, ensure_ascii=False, separators=(',', ':'), default=int).encode('utf-8')
    t0 = time.time()
    r = urllib.request.urlopen(urllib.request.Request(URL, data=body, method='POST',
                                                      headers={'Content-Type': 'text/plain', 'User-Agent': 'b420-compact'}), timeout=90)
    print('POST %d КБ → HTTP %s за %.1f с' % (len(body) // 1024, r.status, time.time() - t0))

    chk, chkraw = fetch()
    cjp = chk.get('jp') or {}
    cmk = chk.get('mk') or {}
    craw = 1000 + sum(Decimal(int(v)) for v in (cjp.get('led') or {}).values()) - sum(Decimal(int(v)) for v in (cjp.get('won') or {}).values())
    print('\n— ПРОВЕРКА — документ %d КБ, rm %d, led %d, won %d, ep %s, raw %s' % (
        len(chkraw) // 1024, len(cmk.get('rm') or {}), len(cjp.get('led') or {}), len(cjp.get('won') or {}), cjp.get('ep'), craw))
    return 0


if __name__ == '__main__':
    sys.exit(main())
