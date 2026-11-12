#!/usr/bin/env python3
"""Поддомены с конверсиями за период (по умолчанию ноябрь).

Фильтр по метке кампании больше не годится: метка размножилась по брендам
(dorgen_engine, dorgne_fenix, eva_engine, gizbo_engine, cryptoboss_engine ...),
и все они сидят на наших поддоменах. Наш признак — форма ключа `бренд.база.зона`
и база в реестре; метку только показываем.

Использование:
    python3 -I scripts/konversii_noyabr.py [YYYY-MM-DD YYYY-MM-DD]
"""
import collections
import glob
import json
import os
import sys

ZONY = {'lol', 'team', 'buzz', 'casino'}


def bazy():
    """Все базовые домены: из выгрузок реестра и из domains_flat.txt."""
    d = set()
    if os.path.exists('domains_flat.txt'):
        d |= {l.strip().lower() for l in open('domains_flat.txt') if l.strip()}
    for put in glob.glob('api/dorgen_subdomains_*.jsonl'):
        if not os.path.getsize(put):
            continue
        for ln in open(put):
            k = ln.find('"content_domain_url":')
            if k < 0:
                continue
            hv = ln[k + 21:k + 70]
            if '"' in hv:
                d.add(hv.split('"')[1].lower())
    return d


def nash(s, doms):
    p = (s or '').lower().split('.')
    if len(p) < 3 or p[-1] not in ZONY:
        return ''                                   # чужая форма: поисковик или чужая сетка
    b = '.'.join(p[-2:])
    return b if b in doms else b + ' (нет в реестре)'


def main(argv):
    ot = argv[0] if argv else '2026-11-01'
    do = argv[1] if len(argv) > 1 else '2026-11-30'
    doms = bazy()

    vid, nashi, chuzhie, bez = set(), collections.defaultdict(collections.Counter), [], []
    for put in glob.glob('api/tracker_conversions_*.jsonl'):
        for ln in open(put):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            dt = str(r.get('at'))[:10]
            if not (ot <= dt <= do):
                continue
            k = (r.get('clickid'), r.get('event'), dt, str(r.get('at'))[11:19])
            if k in vid:
                continue
            vid.add(k)
            s = (r.get('subdomain') or '').lower()
            if not s:
                bez.append((r.get('at'), r.get('event'), r.get('clickid')))
                continue
            b = nash(s, doms)
            if not b:
                chuzhie.append((r.get('at'), r.get('event'), s, r.get('campaign')))
                continue
            g = nashi[s]
            g[r.get('event')] += 1
            g['_baza'] = b
            g['_' + dt] += 1
            g['_m_' + str(r.get('campaign'))] += 1

    print(f'# Конверсии {ot}..{do}: {len(nashi)} поддоменов, '
          f'{sum(v["reg"] for v in nashi.values())} рег, {sum(v["fd"] for v in nashi.values())} фд')
    print()
    print(f'{"поддомен":<34} {"база":<24} {"рег":>4} {"фд":>3}  даты')
    poryadok = sorted(nashi.items(), key=lambda x: (-x[1]['reg'] - x[1]['fd'], x[0]))
    for s, g in poryadok:
        daty = ', '.join(sorted(k[1:] for k in g if k.startswith('_2'))[:6])
        print(f'{s:<34} {g["_baza"]:<24} {g["reg"]:>4} {g["fd"]:>3}  {daty}')
    print()
    print('# Список поддоменов в столбик')
    for s, _ in poryadok:
        print(s)
    if chuzhie:
        print()
        print('# Ключ чужой формы (поисковик вместо поддомена или чужая сетка)')
        for at, ev, s, m in chuzhie:
            print(f'  {at[:19]}  {ev}  {s}  метка {m}')
    if bez:
        print()
        print('# Без поддомена в трекере (не привязать к домену)')
        for at, ev, ci in bez:
            print(f'  {at[:19]}  {ev}  clickid {ci}')
    print()
    metki = collections.Counter()
    for g in nashi.values():
        for k, v in g.items():
            if k.startswith('_m_'):
                metki[k[3:]] += v
    print('# Метки кампаний на наших конверсиях:', dict(metki.most_common()))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
