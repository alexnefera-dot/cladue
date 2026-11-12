#!/usr/bin/env python3
"""Клики по сайтам на доменах, зарегистрированных после заданной даты.

Живой поисковый клик — не бот и в referer есть yandex. (как в
domeny_po_klikam.py). Прочие клики — это редиректы, прямые заходы и боты,
они индексом не являются и регистраций не дают.

Сайты берутся из выгрузок реестра по полю domain_created, клики — из всех
выгрузок трекера. Разбор быстрый: сначала строковый префильтр по ключу,
полный разбор строки только для попавших сайтов.

Использование:
    python3 -I scripts/kliki_posle_10_10.py [YYYY-MM-DD]
"""
import collections
import glob
import json
import os
import sys

RUBEZH = sys.argv[1] if len(sys.argv) > 1 else '2026-10-10'


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


# 1. сайты на доменах, созданных после рубежа
sait_baza, baza = {}, collections.defaultdict(lambda: dict(
    saitov=0, rec=0, sozdan=set(), st=collections.Counter()))
for put in sorted(glob.glob('api/dorgen_subdomains_*.jsonl')):
    if not os.path.getsize(put):
        continue
    for ln in open(put):
        sd = pole(ln, 'domain_created')[:10]
        if not sd[:1].isdigit() or sd <= RUBEZH:
            continue
        s = pole(ln, 'subdomain')
        if not s or s in sait_baza:
            continue
        b = pole(ln, 'content_domain_url')
        sait_baza[s] = b
        g = baza[b]
        g['saitov'] += 1
        g['sozdan'].add(sd)
        if pole(ln, 'recrawl_sent_at')[:1].isdigit():
            g['rec'] += 1
        g['st'][pole(ln, 'yandex_pipeline_stage')] += 1

print(f'Домены, созданные после {RUBEZH}: {len(baza)}, сайтов на них {len(sait_baza)}')
print(f'  отправлено на переобход сайтов: {sum(g["rec"] for g in baza.values())}')
stad = collections.Counter()
for g in baza.values():
    stad.update(g['st'])
print(f'  стадии конвейера: {dict(stad.most_common(6))}')

# 2. клики
vsego = collections.Counter()
zhivye = collections.Counter()
zhivye_dni = collections.defaultdict(set)
strok = 0
fajly = sorted(p for p in glob.glob('api/tracker_clicks_*.jsonl') if not p.endswith('.state'))
for put in fajly:
    n0, z0 = sum(vsego.values()), sum(zhivye.values())
    for ln in open(put):
        k = ln.find('"subdomain": "')
        if k < 0:
            continue
        s = ln[k + 14:ln.find('"', k + 14)]
        if s not in sait_baza:
            continue
        strok += 1
        b = sait_baza[s]
        vsego[b] += 1
        if '"is_bot": true' in ln:
            continue
        rk = ln.find('"referer": "')
        if rk < 0 or 'yandex.' not in ln[rk + 12:ln.find('"', rk + 12)]:
            continue
        zhivye[b] += 1
        zhivye_dni[s].add(pole(ln, 'at')[:10])
    print(f'  {os.path.basename(put):<46} +{sum(vsego.values()) - n0:>8} кликов, '
          f'+{sum(zhivye.values()) - z0:>4} живых поисковых')

print()
print(f'ИТОГО по доменам после {RUBEZH}:')
print(f'  кликов всего:            {sum(vsego.values())}')
print(f'  живых поисковых кликов:  {sum(zhivye.values())}')
print(f'  сайтов с живым кликом:   {len(zhivye_dni)} из {len(sait_baza)}')
print(f'  домен с живым кликом:    {len(zhivye)} из {len(baza)}')
if zhivye:
    print()
    print(f'{"домен":<12} {"создан":<22} {"сайтов":>6} {"переобх":>7} {"кликов":>9} {"живых":>6}')
    for b, z in zhivye.most_common():
        g = baza[b]
        sz = sorted(g['sozdan'])
        print(f'{b:<12} {(sz[0] if len(sz) == 1 else sz[0] + ".." + sz[-1]):<22} '
              f'{g["saitov"]:>6} {g["rec"]:>7} {vsego[b]:>9} {z:>6}')
    print()
    for s, dni in sorted(zhivye_dni.items()):
        print(f'  {s:<30} живые клики: {", ".join(sorted(dni))}')
print()
top = vsego.most_common(10)
print('Топ-10 доменов по кликам всего (при нуле живых это боты и редиректы):')
for b, n in top:
    print(f'  {b:<12} {n:>9} кликов, живых {zhivye.get(b, 0)}')
