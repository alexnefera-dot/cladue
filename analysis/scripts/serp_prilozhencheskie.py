#!/usr/bin/env python3
"""Домены с android/ios в имени: кого покрывают и насколько.

Источников два, и они видят выдачу по-разному.

* Построчный снимок (`serp_nashi_*.json`) показывает всю выдачу: каждый хост на
  каждой позиции. По нему картина полная, но он есть только за сентябрь и не
  содержит 24 брендов, включая 1xbet, Melbet и Fonbet.
* Сводка по брендам (CSV) покрывает все 165 брендов, но из примерно сорока
  сайтов выдачи называет только три: лидера, наш лучший сайт и лучший дор.
  По ней видно присутствие, но не полный список.

Скрипт сводит оба в одну таблицу и помечает, откуда взята каждая строка.

    python3 serp_prilozhencheskie.py --snimok export/serp_nashi_*.json \
        --svodka <csv ...> --kesh api/kesh.tsv --out export/prilozhencheskie.txt
"""
import collections
import csv
import json
import re
import statistics
import sys

STROGO = re.compile(r'andro?id|(?<![a-z])ios(?![a-z])', re.I)
SHIRE = re.compile(r'andro|(?<![a-z])ios(?![a-z])|apk|(?<![a-z])app(?![a-z])|mobil', re.I)

opt = collections.defaultdict(list)
klyuch = None
for a in sys.argv[1:]:
    if a.startswith('--'):
        klyuch = a[2:]
    else:
        opt[klyuch].append(a)

sys.path.insert(0, 'scripts')
from brend_zaprosa import Opredelitel, skelet

stroki = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    stroki.append(s)


def chislo(s):
    s = (s or '').strip().replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


nashi_bazy = set()
imena = set()
with open(opt['kesh'][0], encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        nashi_bazy.add(r['base'])
        b = (r['brand'] or '').strip()
        if b and len(b) >= 3:
            imena.add(b)
opr = Opredelitel(sorted(imena))

# 1. построчный снимок — полная картина по своим брендам
iz_snimka = collections.defaultdict(lambda: dict(brendy=collections.defaultdict(set), strok=0, poz=[], top3=0))
klyuchey = collections.Counter()
brendy_snimka = set()
for put in opt['snimok']:
    d = json.load(open(put, encoding='utf-8'))
    for z, rows in d['queries'].items():
        b = opr(z)
        if b:
            klyuchey[b] += 1
            brendy_snimka.add(b)
        for r in rows:
            h = r['host']
            if not SHIRE.search(h):
                continue
            g = iz_snimka[h]
            g['strok'] += 1
            g['poz'].append(r.get('pos') or 99)
            if (r.get('pos') or 99) <= 3:
                g['top3'] += 1
            if b:
                g['brendy'][b].add(z)

# 2. сводки — видно только три поля на бренд
POLYA = [('Лидер', 'лидер', 'Доля лидера %', 'Ключей у лидера', 'Лучшая позиция лидера'),
         ('Наш лучший сайт', 'наш лучший', 'Наша доля %', None, 'Наша лучшая позиция'),
         ('Лучший дор', 'лучший дор', 'Доля лучшего дора %', None, None)]
iz_svodki = collections.defaultdict(list)
brendy_svodki = set()
klyuchey_svodki = {}
for put in opt['svodka']:
    den = re.search(r'(\d{4}-\d{2}-\d{2})', put)
    den = den.group(1)[5:].replace('-', '.') if den else put.split('/')[-1][:8]
    with open(put, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f, delimiter=';'):
            n = (r.get('Бренд') or '').strip()
            if not n or n == 'без бренда':
                continue
            brendy_svodki.add(n)
            klyuchey_svodki[n] = chislo(r.get('Ключей'))
            for pole, podpis, dolya, klyuchi, poz in POLYA:
                h = (r.get(pole) or '').strip()
                if h and SHIRE.search(h):
                    iz_svodki[h].append(dict(den=den, brend=n, pole=podpis,
                                             dolya=chislo(r.get(dolya)),
                                             klyuchi=chislo(r.get(klyuchi)) if klyuchi else None,
                                             poz=chislo(r.get(poz)) if poz else None,
                                             vsego=klyuchey_svodki[n]))

P('ДОМЕНЫ С ANDROID/IOS В ИМЕНИ: КОГО ПОКРЫВАЮТ И НАСКОЛЬКО')
P('')
P(f'  построчный снимок: брендов {len(brendy_snimka)}, по ним видна вся выдача')
P(f'  сводки по брендам: брендов {len(brendy_svodki)}, по ним видны только лидер, наш лучший сайт и лучший дор')
# имена в сводке латиницей, в снимке бывают кириллицей: сверяем по скелету
sk_snimka = {skelet(b) for b in brendy_snimka}
net = sorted(b for b in brendy_svodki
             if b not in brendy_snimka and skelet(b) not in sk_snimka)
P(f'  брендов только в сводках (в снимке их нет): {len(net)}')
P('    ' + ', '.join(net))
P('')

vse = set(iz_snimka) | set(iz_svodki)
P(f'ВСЕГО ТАКИХ ДОМЕНОВ НАЙДЕНО: {len(vse)}; из них строго с android/ios: '
  f'{sum(1 for h in vse if STROGO.search(h))}')
nashih = [h for h in vse if (h.split('.', 1)[1] if h.count('.') >= 2 else h) in nashi_bazy]
P(f'  наших среди них: {len(nashih)}' + (f' — {", ".join(nashih)}' if nashih else ' (ни одного)'))
P('')

P('ПО ПОСТРОЧНОМУ СНИМКУ — полная выдача')
P(f'  {"домен":<30} {"брендов":>8} {"строк":>6} {"в топ-3":>8} {"мед.поз":>8}  покрытие по брендам')
for h, g in sorted(iz_snimka.items(), key=lambda kv: (-len(kv[1]['brendy']), -kv[1]['strok'])):
    gl = sorted(((b, len(zs) / klyuchey[b] if klyuchey[b] else 0, len(zs))
                 for b, zs in g['brendy'].items()), key=lambda x: -x[1])
    P(f'  {h:<30} {len(gl):>8} {g["strok"]:>6} {g["top3"]:>8} '
      f'{statistics.median(g["poz"]):>8.0f}  ' +
      ', '.join(f'{b} {dl:.0%} ({k} из {klyuchey[b]})' for b, dl, k in gl))
P('')

P('ПО СВОДКАМ — видно только присутствие в трёх полях, но брендов больше')
P(f'  {"домен":<30} {"сбор":<7} {"бренд":<22} {"поле":<12} {"доля строк":>11} {"ключей":>8} {"позиция":>8}')
for h in sorted(iz_svodki, key=lambda h: -max(z['dolya'] or 0 for z in iz_svodki[h])):
    for z in sorted(iz_svodki[h], key=lambda z: (z['brend'], z['den'])):
        kl = f'{z["klyuchi"]:.0f} из {z["vsego"]:.0f}' if z['klyuchi'] and z['vsego'] else '—'
        poz = f'{z["poz"]:.0f}' if z['poz'] else '—'
        dolya = z['dolya'] if z['dolya'] is not None else 0
        P(f'  {h:<30} {z["den"]:<7} {z["brend"]:<22} {z["pole"]:<12} '
          f'{dolya:>10.1f}% {kl:>8} {poz:>8}')
P('')

tolko_svodka = {h for h in iz_svodki} - set(iz_snimka)
P(f'ЧЕГО НЕ БЫЛО ВИДНО В СНИМКЕ: {len(tolko_svodka)} доменов — {", ".join(sorted(tolko_svodka)) or "нет"}')
P('')
P('ЧТО ОСТАЁТСЯ НЕИЗМЕРЕННЫМ')
P(f'  в сводке на бренд приходится около 39 сайтов выдачи, а названы 3 — это 8% состава.')
P(f'  по {len(net)} брендам, которых нет в построчном снимке, остальные 92% не видны:')
P(f'  там может стоять сколько угодно приложенческих доменов на позициях 2-10.')

if opt['out']:
    with open(opt['out'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(stroki) + '\n')
    print(f'\nзаписано: {opt["out"][0]}')
