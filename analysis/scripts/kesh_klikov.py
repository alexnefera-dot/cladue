#!/usr/bin/env python3
"""Кэш трафика из реестра: сабдомен -> clicks_sum, views_sum, первый клик.

Реестры весят почти три гигабайта, и каждый разбор перечитывал их ради трёх
полей. Собирается один раз, дописывается новыми выгрузками так же, как
kesh_reestra.py.

    python3 kesh_klikov.py <кэш.tsv> <выгрузка.jsonl ...>
"""
import json
import os
import sys

out_p, srcs = sys.argv[1], sys.argv[2:]
have = {}
done = set()
if os.path.exists(out_p):
    with open(out_p, encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            have[p[0]] = p
if os.path.exists(out_p + '.src'):
    done = set(open(out_p + '.src', encoding='utf-8').read().split('\n')) - {''}

added = 0
for put in srcs:
    name = os.path.basename(put)
    if name in done:
        continue
    with open(put, encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            s = r['subdomain'].lower()
            if s in have:
                continue
            have[s] = [s, str(r.get('clicks_sum') or 0), str(r.get('views_sum') or 0),
                       (r.get('first_click_at') or '')[:10]]
            added += 1
    done.add(name)

with open(out_p, 'w', encoding='utf-8') as f:
    f.write('subdomain\tclicks_sum\tviews_sum\tfirst_click\n')
    for p in have.values():
        f.write('\t'.join(p) + '\n')
with open(out_p + '.src', 'w', encoding='utf-8') as f:
    f.write('\n'.join(sorted(done)) + '\n')
print(f'{out_p}: {len(have)} сайтов, добавлено {added}, выгрузок учтено {len(done)}')
