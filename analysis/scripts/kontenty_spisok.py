#!/usr/bin/env python3
"""Список контентов за период: сайты, домены, зона, клики, регистрации.

Берёт кэш реестра (scripts/kesh_reestra.py), поэтому не читает выгрузки dorgen.
Клики считаются за один день наблюдения, регистрации — за всё время по сайтам
этих контентов. «К фону» — клики на сайт, делённые на средний сайт того же дня
переобхода и той же зоны, иначе поздние запуски выглядят хуже просто потому,
что успели меньше.

    python3 kontenty_spisok.py <с> <по> <день кликов> <out.txt> --kesh ... --clicks ... --conv ...
"""
import sys, csv, json, glob, collections

lo, hi, cday, out_p = sys.argv[1:5]
opt = collections.defaultdict(list); cur = None
for a in sys.argv[5:]:
    if a.startswith('--'):
        cur = a[2:]
    else:
        opt[cur].append(a)

site = {}
with open(opt['kesh'][0], encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        d = r['recrawl'][:10]
        if d and lo <= d <= hi and r['content']:
            site[r['subdomain']] = (r['content'], r['tld'], r['base'], d)

clicks = collections.Counter()
for p in opt['clicks']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        if r.get('is_bot') or r['at'][:10] != cday:
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        s = (r.get('subdomain') or '').lower()
        if s in site:
            clicks[s] += 1
seen = set(); conv = collections.defaultdict(collections.Counter)
for p in opt['conv']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        k = (r['clickid'], r['event'], r['at'])
        if k in seen or r.get('campaign') != 'dorgen_engine' or r['event'] not in ('reg', 'fd'):
            continue
        seen.add(k)
        s = (r.get('subdomain') or '').lower()
        if s in site:
            conv[site[s][0]][r['event']] += 1

# фон: средний сайт того же дня переобхода и той же зоны
cell = collections.defaultdict(lambda: [0, 0])
for s, (c, z, b, d) in site.items():
    g = cell[(d, z)]; g[0] += clicks.get(s, 0); g[1] += 1
base = {k: a / n for k, (a, n) in cell.items() if n}

K = collections.defaultdict(lambda: dict(n=0, c=0, hit=0, exp=0.0, z=set(), b=set(), days=set()))
for s, (c, z, b, d) in site.items():
    g = K[c]; g['n'] += 1; g['c'] += clicks.get(s, 0); g['z'].add(z); g['b'].add(b); g['days'].add(d)
    g['exp'] += base.get((d, z), 0)
    if clicks.get(s, 0):
        g['hit'] += 1

# сортировка по факту, а не по коэффициенту: в выдохшихся когортах фон почти ноль,
# и пара кликов даёт десятки «иксов», которые ничего не значат
rows = sorted(K, key=lambda c: (-K[c]['c'], c))
MIN_EXP = 5.0      # ниже этого ожидания коэффициент не показываем
with open(out_p, 'w', encoding='utf-8') as f:
    f.write(f'Контенты, запущенные {lo} — {hi}: {len(rows)} шт.\n')
    f.write(f'Клики — живые поисковые за {cday}. Регистрации — за всё время по этим сайтам.\n')
    f.write('«К фону» — клики на сайт против среднего сайта того же дня и той же зоны;\n')
    f.write('прочерк там, где ожидание меньше 5 кликов и коэффициент ничего не значит.\n')
    f.write('Отсортировано по кликам. Сравнивать контенты разных дней запуска напрямую нельзя:\n')
    f.write('запущенный позже успел меньше.\n\n')
    f.write(f'{"#":>4}  {"контент":<44} {"зона":<6} {"сайтов":>7} {"доменов":>8} {"дни запуска":<14} '
            f'{"кликов":>7} {"кл/сайт":>8} {"прорыв":>7} {"к фону":>7} {"рег":>4} {"ФД":>3}\n')
    f.write('-' * 138 + '\n')
    for i, c in enumerate(rows, 1):
        g = K[c]
        dd = '/'.join(d[8:10] for d in sorted(g['days']))
        kf = (f'{g["c"]/g["exp"]:>6.2f}x' if g['exp'] >= MIN_EXP else f'{"—":>7}')
        f.write(f'{i:>4}  {c[:44]:<44} {"/".join(sorted(g["z"])):<6} {g["n"]:>7} {len(g["b"]):>8} {dd:<14} '
                f'{g["c"]:>7} {g["c"]/g["n"]:>8.2f} {100*g["hit"]/g["n"]:>6.1f}% {kf} {conv[c]["reg"]:>4} {conv[c]["fd"]:>3}\n')
    f.write('\n\nТолько имена, по одному в строке:\n\n')
    for c in sorted(rows):
        f.write(c + '\n')
tot_n = sum(K[c]['n'] for c in rows); tot_c = sum(K[c]['c'] for c in rows)
print(f'контентов {len(rows)}, сайтов {tot_n}, кликов за {cday} {tot_c}, '
      f'рег {sum(conv[c]["reg"] for c in rows)}, ФД {sum(conv[c]["fd"] for c in rows)}')
