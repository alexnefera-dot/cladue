#!/usr/bin/env python3
"""Кэш реестра запусков: сабдомен -> переобход, зона, база, контент, бренд.

Каждый разбор заново читал все выгрузки dorgen (больше двух гигабайт) только ради
четырёх полей. Кэш собирается один раз и дописывается новыми выгрузками.

    python3 kesh_reestra.py <кэш.tsv> <выгрузка.jsonl ...>
"""
import sys, json, os

out_p, srcs = sys.argv[1], sys.argv[2:]
have = {}
done = set()
if os.path.exists(out_p):
    with open(out_p, encoding='utf-8') as f:
        head = f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            have[p[0]] = p
if os.path.exists(out_p + '.src'):
    done = set(open(out_p + '.src', encoding='utf-8').read().split('\n')) - {''}

added = 0
for p in srcs:
    name = os.path.basename(p)
    if name in done:
        continue
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        s = r['subdomain'].lower()
        if s in have:
            continue
        have[s] = [s, (r.get('recrawl_sent_at') or '')[:19], r.get('tld') or '',
                   r['content_domain_url'], r.get('content_label') or '', r.get('brand_label') or '']
        added += 1
    done.add(name)

with open(out_p, 'w', encoding='utf-8') as f:
    f.write('subdomain\trecrawl\ttld\tbase\tcontent\tbrand\n')
    for s in sorted(have):
        f.write('\t'.join(have[s]) + '\n')
open(out_p + '.src', 'w', encoding='utf-8').write('\n'.join(sorted(done)))
print(f'{out_p}: {len(have)} сайтов, добавлено {added}, выгрузок учтено {len(done)}')
