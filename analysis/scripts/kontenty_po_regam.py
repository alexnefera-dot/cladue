#!/usr/bin/env python3
"""Контенты по регистрациям за период: кто реально принёс деньги.

Берутся все конверсии, пришедшие в окне, независимо от даты запуска сайта —
старые сайты продолжают приносить регистрации, и отбрасывать их нельзя.
Рядом показывается дата переобхода, чтобы было видно возраст.

    python3 kontenty_po_regam.py <с> <по> <out.txt> --kesh ... --conv ... [--clicks ... --cday ...]
"""
import sys, csv, json, re, collections

lo, hi, out_p = sys.argv[1:4]
opt = collections.defaultdict(list); cur = None
for a in sys.argv[4:]:
    if a.startswith('--'):
        cur = a[2:]
    else:
        opt[cur].append(a)
cday = opt['cday'][0] if opt['cday'] else None

site = {}
with open(opt['kesh'][0], encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        site[r['subdomain']] = (r['content'], r['tld'], r['recrawl'][:10], r['base'])
clicks = collections.Counter()
for p in opt['clicks']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        if r.get('is_bot') or (cday and r['at'][:10] != cday):
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        s = (r.get('subdomain') or '').lower()
        if s in site:
            clicks[site[s][0]] += 1

seen = set()
K = collections.defaultdict(lambda: collections.Counter())
meta = {}
lost = collections.Counter()
for p in opt['conv']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        k = (r['clickid'], r['event'], r['at']); d = r['at'][:10]
        if k in seen or r.get('campaign') != 'dorgen_engine' or r['event'] not in ('reg', 'fd'):
            continue
        if not (lo <= d <= hi):
            continue
        seen.add(k)
        s = (r.get('subdomain') or '').lower()
        v = site.get(s)
        if not v or not v[0]:
            # две разные причины: сайта вовсе нет в реестре, либо он старый и
            # поле content_label у него не заполнялось
            why = 'нет в реестре' if not v else f'без имени контента, переобход {v[2] or "—"}'
            lost[f'{s or "(пусто)"} — {why}'] += 1
            continue
        K[v[0]][r['event']] += 1
        K[v[0]]['sites'] += 0
        meta.setdefault(v[0], [set(), set(), set()])
        meta[v[0]][0].add(v[1]); meta[v[0]][1].add(v[2]); meta[v[0]][2].add(v[3])
# размер контента и размер всей группы: знаменатель должен включать и те тексты
# группы, что не дали ни одной регистрации, иначе доля выходит константой
SZ = collections.Counter(); BS = collections.defaultdict(set)
for s, (c, z, d, b) in site.items():
    if c in K:
        SZ[c] += 1; BS[c].add(b)


def fam(c):
    m = re.match(r'content-\d{4}-\d{2}-\d{2}-(.+?)_\d+$', c) or re.match(r'content-\d{4}-\d{2}-\d{2}-(.+)$', c)
    if m:
        return m.group(1)
    m = re.match(r'(nabory?-[\d-]+[^_]*)_\d+$', c)
    if m:
        return m.group(1)
    return re.sub(r'_\d+$', '', c)


rows = sorted(K, key=lambda c: (-K[c]['reg'], -K[c]['fd'], c))
tot_r = sum(K[c]['reg'] for c in rows); tot_f = sum(K[c]['fd'] for c in rows)
with open(out_p, 'w', encoding='utf-8') as f:
    f.write(f'Контенты по регистрациям за {lo} — {hi}\n')
    f.write(f'Всего {tot_r} регистраций и {tot_f} ФД на {len(rows)} контентах.\n')
    f.write('Считаются все конверсии окна, независимо от даты запуска сайта: старые сайты\n')
    f.write('продолжают приносить регистрации. Колонка «переобход» показывает возраст.\n')
    if cday:
        f.write(f'Клики — живые поисковые за {cday}, по всем сайтам контента.\n')
    f.write('\n')
    f.write(f'{"#":>4}  {"контент":<44} {"зона":<10} {"сайтов":>7} {"доменов":>8} {"переобход":<22} '
            f'{"рег":>4} {"ФД":>3} {"кликов":>8}\n')
    f.write('-' * 128 + '\n')
    for i, c in enumerate(rows, 1):
        z, dd, bb = meta[c]
        f.write(f'{i:>4}  {c[:44]:<44} {"/".join(sorted(z)):<10} {SZ[c]:>7} {len(BS[c]):>8} '
                f'{"/".join(sorted(d[5:] for d in dd if d))[:22]:<22} '
                f'{K[c]["reg"]:>4} {K[c]["fd"]:>3} {clicks.get(c, 0):>8}\n')
    # группы
    G = collections.defaultdict(collections.Counter)
    for c in rows:
        g = G[fam(c)]; g['reg'] += K[c]['reg']; g['fd'] += K[c]['fd']; g['t'] += 1
        g['sites'] += SZ[c]
    GALL = collections.Counter(); GT = collections.defaultdict(set)
    for s, (c, z, d, b) in site.items():
        if not c:
            continue
        ff = fam(c)
        if ff in G:
            GALL[ff] += 1; GT[ff].add(c)
    f.write('\n\nПо группам контента:\n\n')
    f.write('Знаменатель — все сайты группы за всё время, включая тексты без регистраций.\n\n')
    f.write(f'{"группа":<34} {"текстов":>8} {"из них с рег":>13} {"сайтов всего":>13} {"рег":>5} {"ФД":>4} '
            f'{"рег на 10тыс":>13}\n')
    f.write('-' * 96 + '\n')
    for g in sorted(G, key=lambda g: (-G[g]['reg'], -G[g]['fd'])):
        x = G[g]; n = GALL[g]
        f.write(f'{g[:34]:<34} {len(GT[g]):>8} {x["t"]:>13} {n:>13} {x["reg"]:>5} {x["fd"]:>4} '
                f'{(10000*x["reg"]/n if n else 0):>13.2f}\n')
    if lost:
        f.write(f'\nНе привязались к контенту — {sum(lost.values())} конверсий:\n')
        for s, n in lost.most_common():
            f.write(f'    {n} x  {s}\n')
    f.write('\n\nТолько имена, по одному в строке:\n\n')
    for c in sorted(rows):
        f.write(c + '\n')
print(f'контентов с конверсиями {len(rows)}, рег {tot_r}, ФД {tot_f}, не сопоставлено {sum(lost.values())}')
