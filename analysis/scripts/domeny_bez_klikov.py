#!/usr/bin/env python3
"""Домены, не давшие ни одного живого поискового клика за всю историю.

Важно читать ВСЕ файлы кликов, а не только свежие: домен, запущенный в августе,
мог отработать в августе и замолчать. Если взять только октябрь, он попадёт в
«без кликов вообще» ошибочно.

    python3 domeny_bez_klikov.py <out.txt> --kesh ... --clicks <все файлы>
"""
import sys, csv, json, collections

out_p = sys.argv[1]
opt = collections.defaultdict(list); cur = None
for a in sys.argv[2:]:
    if a.startswith('--'):
        cur = a[2:]
    else:
        opt[cur].append(a)

dom = collections.defaultdict(lambda: dict(n=0, z=None, first=None, last=None, brands=set()))
sub2dom = {}
with open(opt['kesh'][0], encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        if not r['recrawl']:
            continue
        b = r['base']; g = dom[b]
        g['n'] += 1; g['z'] = r['tld']
        d = r['recrawl'][:10]
        if not g['first'] or d < g['first']:
            g['first'] = d
        if not g['last'] or d > g['last']:
            g['last'] = d
        sub2dom[r['subdomain']] = b

ever = set(); okt = set()
for p in opt['clicks']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        if r.get('is_bot'):
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        b = sub2dom.get((r.get('subdomain') or '').lower())
        if b:
            ever.add(b)
            if r['at'][:10] >= '2026-10-01':
                okt.add(b)

dead = sorted((b for b in dom if b not in ever), key=lambda b: (dom[b]['first'] or '', b))
dead_okt = [b for b in dom if b not in okt]
with open(out_p, 'w', encoding='utf-8') as f:
    f.write(f'Домены без единого живого поискового клика за всю историю наблюдений\n')
    f.write(f'Всего доменов с переобходом: {len(dom)}, сайтов на них {sum(g["n"] for g in dom.values())}.\n')
    f.write(f'Без кликов ВООБЩЕ: {len(dead)} доменов ({100*len(dead)/len(dom):.1f}%), '
            f'{sum(dom[b]["n"] for b in dead)} сайтов.\n')
    f.write(f'Для сравнения, без кликов в октябре: {len(dead_okt)} доменов.\n')
    f.write('Клики прочитаны из всех выгрузок, что есть на диске.\n\n')
    f.write(f'{"#":>5}  {"домен":<24} {"зона":<8} {"сайтов":>7} {"первый переобход":<18} {"последний":<12}\n')
    f.write('-' * 84 + '\n')
    for i, b in enumerate(dead, 1):
        g = dom[b]
        f.write(f'{i:>5}  {b:<24} {str(g["z"]):<8} {g["n"]:>7} {g["first"] or "—":<18} {g["last"] or "—":<12}\n')
    # сводка по дням запуска
    D = collections.Counter(); DA = collections.Counter()
    for b, g in dom.items():
        if g['first']:
            DA[g['first']] += 1
            if b not in ever:
                D[g['first']] += 1
    f.write('\n\nПо дню первого переобхода: сколько доменов запущено и сколько из них без кликов\n\n')
    f.write(f'{"день":<12} {"доменов":>8} {"без кликов":>11} {"доля":>7}\n')
    f.write('-' * 42 + '\n')
    for d in sorted(DA):
        f.write(f'{d:<12} {DA[d]:>8} {D[d]:>11} {100*D[d]/DA[d]:>6.1f}%\n')
    f.write('\n\nТолько домены, по одному в строке:\n\n')
    for b in dead:
        f.write(b + '\n')
print(f'доменов всего {len(dom)}, без кликов вообще {len(dead)}, без кликов в октябре {len(dead_okt)}')
