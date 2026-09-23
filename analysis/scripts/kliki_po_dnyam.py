#!/usr/bin/env python3
"""Суточный ряд поисковых кликов по каждому сайту.

Один проход по выгрузкам кликов трекера. Берутся только живые (is_bot = false)
клики с реферером Яндекса на сайтах нашей формы «бренд.база.зона». На выходе —
по строке на сайт: [сайт, {дата: кликов}].

Выгрузки перекрываются по датам, поэтому у каждой указывается окно:
    путь:с_даты:по_дату   (любую границу можно оставить пустой)

    python3 kliki_po_dnyam.py <out.jsonl> <клики:с:по> [ещё...]
"""
import sys, json, collections

out_p = sys.argv[1]
specs = []
for a in sys.argv[2:]:
    p, lo, hi = (a.split(':') + ['', ''])[:3]
    specs.append((p, lo or '0000', hi or '9999'))

D = collections.defaultdict(collections.Counter)
for p, lo, hi in specs:
    n = kept = 0
    for line in open(p, encoding='utf-8'):
        n += 1
        r = json.loads(line)
        d = r['at'][:10]
        if d < lo or d > hi or r.get('is_bot'):
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        s = (r.get('subdomain') or '').lower()
        if s.count('.') != 2:
            continue
        D[s][d] += 1
        kept += 1
    print(f'  {p.split("/")[-1]} [{lo}..{hi}]: строк {n}, поисковых живых {kept}, сайтов накоплено {len(D)}', flush=True)

with open(out_p, 'w', encoding='utf-8') as f:
    for s, c in D.items():
        f.write(json.dumps([s, dict(c)], ensure_ascii=False) + '\n')
print(f'ГОТОВО: {len(D)} сайтов, {sum(sum(c.values()) for c in D.values())} кликов')
