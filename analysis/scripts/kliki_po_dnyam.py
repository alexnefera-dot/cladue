#!/usr/bin/env python3
"""Живые поисковые клики по сети, по дням: идёт индекс или затухает.

Живой поисковый клик — не бот и в referer есть yandex. Клики дедуплицируются
по clickid: выгрузки трекера перекрываются по датам.

Общее число кликов по дню берётся как максимум по файлам, покрывающим этот
день: перекрытия считать нельзя, а оборванный файл даёт заниженное число.
День, который покрыт только оборванной выгрузкой, помечен звёздочкой.

Использование:
    python3 -I scripts/kliki_po_dnyam.py [YYYY-MM-DD отсечка когорты]
"""
import collections
import glob
import json
import os
import sys

RUBEZH = sys.argv[1] if len(sys.argv) > 1 else '2026-10-10'
ZONY = {'lol', 'team', 'buzz', 'casino'}


def pole(ln, imya):
    k = ln.find('"' + imya + '":')
    if k < 0:
        return ''
    j = k + len(imya) + 3
    while j < len(ln) and ln[j] == ' ':
        j += 1
    if ln[j:j + 1] == '"':
        return ln[j + 1:ln.find('"', j + 1)]
    return ln[j:min(x for x in (ln.find(',', j), ln.find('}', j), len(ln)) if x > 0)].strip()


# когда создана база домена
sozdan = {}
for put in sorted(glob.glob('api/dorgen_subdomains_*.jsonl')):
    if not os.path.getsize(put):
        continue
    for ln in open(put):
        b = pole(ln, 'content_domain_url')
        d = pole(ln, 'domain_created')[:10]
        if b and d[:1].isdigit():
            sozdan[b] = min(sozdan.get(b, '9999'), d)

vid = set()
zhiv = collections.defaultdict(collections.Counter)      # дата -> счётчики
sajty = collections.defaultdict(set)
bazy_d = collections.defaultdict(set)
vsego = collections.defaultdict(collections.Counter)     # файл -> дата -> кликов

for put in sorted(p for p in glob.glob('api/tracker_clicks_*.jsonl') if not p.endswith('.state')):
    f = os.path.basename(put)
    for ln in open(put):
        k = ln.find('"subdomain": "')
        if k < 0:
            continue
        s = ln[k + 14:ln.find('"', k + 14)]
        p = s.split('.')
        if len(p) < 3 or p[-1] not in ZONY:
            continue                                     # чужая форма ключа
        dt = ln[8:18]
        vsego[dt][f] += 1
        if '"is_bot": true' in ln:
            continue
        rk = ln.find('"referer": "')
        if rk < 0 or 'yandex.' not in ln[rk + 12:ln.find('"', rk + 12)]:
            continue
        ci = pole(ln, 'clickid')
        if (ci, dt) in vid:
            continue
        vid.add((ci, dt))
        b = '.'.join(p[-2:])
        zhiv[dt]['vse'] += 1
        zhiv[dt]['novye' if sozdan.get(b, '') > RUBEZH else 'starye'] += 1
        sajty[dt].add(s)
        bazy_d[dt].add(b)

print(f'Живые поисковые клики по дням (когорта «новые» — база создана после {RUBEZH})')
print()
print(f'{"день":<12} {"кликов всего":>13} {"живых":>7} {"новые":>6} {"старые":>7} '
      f'{"сайтов":>7} {"доменов":>8}')
for dt in sorted(set(list(zhiv) + list(vsego))):
    v = max(vsego[dt].values()) if vsego[dt] else 0
    g = zhiv[dt]
    print(f'{dt:<12} {v:>13} {g["vse"]:>7} {g["novye"]:>6} {g["starye"]:>7} '
          f'{len(sajty[dt]):>7} {len(bazy_d[dt]):>8}')
