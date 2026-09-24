#!/usr/bin/env python3
"""Индекс (доля сайтов с поисковым кликом за сутки 0–3) по группам контента и доменным зонам.

Берёт по-доменную таблицу okupaemost_domenov.py; группа = имя контента без номера экземпляра.
Сравнение зон — внутри групп, где есть и зона, и другие зоны (O/E к индексу своей группы).

    python3 nabory_po_zonam.py <okupaemost_domenov.csv> <out.txt> <out.csv>
"""
import sys, csv, re, collections

inp, out_p, csv_p = sys.argv[1:4]
Z = ['casino', 'team', 'lol', 'buzz']
G = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0.0, 0, 0, 0]))
for r in csv.DictReader(open(inp, encoding='utf-8')):
    g = re.sub(r'_\d+$', '', r['content'])
    n = int(r['sites'])
    for k in (r['zone'], 'все'):
        c = G[g][k]
        c[0] += n; c[1] += float(r['index']) * n / 100; c[2] += 1; c[3] += int(r['reg']); c[4] += int(r['fd'])
out = []
rows = sorted(G.items(), key=lambda kv: -kv[1]['все'][1] / kv[1]['все'][0])
head = f'{"группа контента":<44} {"доменов":>7} {"индекс":>7} {"рег":>4} {"ФД":>3} | ' + ' | '.join(f'{z:^15}' for z in Z)
out.append(head)
recs = []
for g, d in rows:
    a = d['все']
    cells = []
    rec = dict(content=g, domains=a[2], index=round(100 * a[1] / a[0], 1), reg=a[3], fd=a[4])
    for z in Z:
        c = d.get(z)
        if c and c[2]:
            cells.append(f'{100*c[1]/c[0]:>5.1f}% ({c[2]:>3} д.)')
            rec[z] = round(100 * c[1] / c[0], 1); rec[z + '_domains'] = c[2]
        else:
            cells.append(f'{"—":^15}')
    out.append(f'{g:<44} {a[2]:>7} {100*a[1]/a[0]:>6.1f}% {a[3]:>4} {a[4]:>3} | ' + ' | '.join(cells))
    recs.append(rec)
out.append('\nЗона против своей группы (группы, где зона стоит рядом хотя бы с одной другой):')
for z in Z:
    o = e = 0.0; ng = nd = 0; better = 0
    for g, d in rows:
        if z in d and len([k for k in d if k != 'все']) >= 2:
            c = d[z]; a = d['все']
            o += c[1]; e += c[0] * a[1] / a[0]; ng += 1; nd += c[2]
            better += (c[1] / c[0]) > (a[1] / a[0])
    if ng:
        out.append(f'   .{z:<7} групп {ng:>3}, доменов {nd:>4}: индекс к своей группе {o/e:.2f}×; выше своей группы в {better} из {ng}')
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
keys = ['content', 'domains', 'index', 'reg', 'fd'] + [x for z in Z for x in (z, z + '_domains')]
with open(csv_p, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(recs)
print('\n'.join(out))
