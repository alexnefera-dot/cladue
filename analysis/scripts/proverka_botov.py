#!/usr/bin/env python3
"""Проверка главной метрики (индекса) на ботов.

Один проход по выгрузкам кликов: для каждого сайта «бренд.база.зона» — время первого
клика с реферером Яндекса в четырёх вариантах: любой (вместе с ботами), не бот (как
считаем сейчас), не бот из СНГ, и время второго не-бот клика. Плюс сводки по странам
и доле ботов.

    python3 proverka_botov.py <out.json> <клики:с:по> [ещё...]
"""
import sys, json, collections

CIS = {'RU', 'UA', 'KZ', 'BY', 'UZ', 'KG', 'AZ', 'AM', 'GE', 'MD', 'TJ', 'TM'}
out_p = sys.argv[1]
specs = []
for a in sys.argv[2:]:
    p, lo, hi = (a.split(':') + ['', ''])[:3]
    specs.append((p, lo or '0000', hi or '9999'))

first = {}   # сайт -> [любой, не бот, не бот СНГ, второй не бот]
stat = collections.Counter()
country = collections.Counter()
for p, lo, hi in specs:
    n = 0
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        d = r['at'][:10]
        if d < lo or d > hi:
            continue
        s = (r.get('subdomain') or '').lower()
        if s.count('.') != 2:
            continue
        h = r.get('referer') or ''
        ya = 'yandex' in h or 'ya.ru' in h
        bot = bool(r.get('is_bot'))
        stat[(p.split('/')[-1], bot, ya)] += 1
        if not ya:
            continue
        n += 1
        at = r['at']; c = r.get('country') or '?'
        f = first.setdefault(s, [None, None, None, None])
        if f[0] is None or at < f[0]:
            f[0] = at
        if bot:
            continue
        country[c] += 1
        if f[1] is None or at < f[1]:
            f[1], f[3] = at, f[1] if f[3] is None or (f[1] and f[1] < f[3]) else f[3]
        elif f[3] is None or at < f[3]:
            f[3] = at
        if c in CIS and (f[2] is None or at < f[2]):
            f[2] = at
    print(f'  {p.split("/")[-1]} [{lo}..{hi}]: поисковых {n}, сайтов {len(first)}', flush=True)

json.dump({'first': first, 'stat': [[k[0], k[1], k[2], v] for k, v in stat.items()],
           'country': country.most_common()}, open(out_p, 'w'))
