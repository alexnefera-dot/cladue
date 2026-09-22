#!/usr/bin/env python3
"""Конверсии последних суток: какие сайты их дали и что на этих сайтах стояло.

Собирает по каждой конверсии: сайт, базу, бренд, набор контента, день
переобхода, возраст базы на момент конверсии, зону и вложенность страницы
(поле landing_path, которое трекер начал передавать 22.09).

    python3 svezhie_konversii.py <конверсии.jsonl> <реестр.jsonl> <свод.csv> <с даты> <out.txt>
"""
import sys, json, csv, collections, datetime

conv_p, reg_p, svod_p, since, out_p = sys.argv[1:6]

REG = {}
for line in open(reg_p, encoding='utf-8'):
    r = json.loads(line)
    s = (r.get('subdomain') or '').lower()
    if s:
        REG[s] = {'content': r.get('content_label') or '',
                  'recrawl': (r.get('recrawl_sent_at') or '')[:10],
                  'brand': r.get('brand_label') or '',
                  'tld': r.get('tld') or s.rsplit('.', 1)[-1]}

SVOD = {r['домен']: r for r in csv.DictReader(open(svod_p, encoding='utf-8'))}

# бренд у сайтов вне реестра берём по префиксу сабдомена: тот же префикс
# в реестре уже сопоставлен человеческому названию бренда
PREFIX = {}
for s_, v in REG.items():
    if v['brand']:
        PREFIX.setdefault(s_.split('.', 1)[0], v['brand'])

C = [json.loads(l) for l in open(conv_p, encoding='utf-8')]
C = [r for r in C if r.get('campaign') == 'dorgen_engine' and r['at'][:10] >= since]

def base(s): return s.split('.', 1)[1]
def seg(p):  return [x for x in (p or '').split('/') if x]

rows = []
for r in C:
    s = r['subdomain']; b = base(s)
    reg = REG.get(s, {})
    sv = SVOD.get(b, {})
    content = reg.get('content') or sv.get('набор контента', '')
    launch = sv.get('день запуска') or reg.get('recrawl', '')
    age = ''
    if launch:
        age = (datetime.date.fromisoformat(r['at'][:10]) - datetime.date.fromisoformat(launch)).days
    rows.append({'дата': r['at'][:10], 'время': r['at'][11:16], 'событие': r['event'],
                 'сайт': s, 'база': b, 'бренд': reg.get('brand') or PREFIX.get(s.split('.')[0], s.split('.')[0]),
                 'зона': s.rsplit('.', 1)[-1], 'набор контента': content or 'нет в реестре',
                 'день запуска базы': launch or '—', 'возраст базы, дней': age,
                 'вложенность': len(seg(r.get('landing_path'))) if r.get('landing_path') else '',
                 'раздел': (seg(r.get('landing_path')) or ['(корень)'])[0] if r.get('landing_path') else '',
                 'страна': r.get('country') or '', 'clickid': r['clickid']})

L = []
P = L.append
regs = [r for r in rows if r['событие'] == 'reg']
fds  = [r for r in rows if r['событие'] == 'fd']
P(f'КОНВЕРСИИ С {since}: {len(regs)} регистраций, {len(fds)} первых депозитов')
P(f'сайтов {len({r["сайт"] for r in rows})}, баз {len({r["база"] for r in rows})}, брендов {len({r["бренд"] for r in rows})}')
P('')
P('ПО ДНЯМ')
d = collections.defaultdict(collections.Counter)
for r in rows: d[r['дата']][r['событие']] += 1
for k in sorted(d): P(f'   {k}: {d[k]["reg"]} регистраций, {d[k]["fd"]} ФД')
P('')
P('ВОЗРАСТ БАЗЫ НА МОМЕНТ КОНВЕРСИИ')
a = collections.Counter(r['возраст базы, дней'] for r in rows if r['возраст базы, дней'] != '')
for k in sorted(a): P(f'   {k:>3} суток после запуска: {a[k]}')
P('')
P('НАБОРЫ КОНТЕНТА')
c = collections.Counter(r['набор контента'] for r in rows)
for k, v in c.most_common(): P(f'   {v:>3}  {k}')
P('')
P('БРЕНДЫ')
br = collections.Counter(r['бренд'] for r in rows)
P('   ' + ', '.join(f'{k} ({v})' for k, v in br.most_common()))
P('')
P('ЗОНЫ: ' + ', '.join(f'{k} {v}' for k, v in collections.Counter(r['зона'] for r in rows).most_common()))
P('')
P('ВЛОЖЕННОСТЬ СТРАНИЦЫ (новое поле трекера)')
withp = [r for r in rows if r['вложенность'] != '']
P(f'   конверсий с записанным путём: {len(withp)} из {len(rows)}')
if withp:
    g = collections.Counter()
    for r in withp:
        n = r['вложенность']
        g['0 корень' if n == 0 else '1–3' if n <= 3 else '4–9' if n <= 9 else '10–19' if n <= 19 else '20+'] += 1
    for k in ['0 корень', '1–3', '4–9', '10–19', '20+']:
        P(f'   {k:<9} {g[k]}')
    P('   разделы: ' + ', '.join(f'{k} {v}' for k, v in collections.Counter(r['раздел'] for r in withp).most_common()))
P('')
P('ВСЕ КОНВЕРСИИ ПОИМЁННО')
P(f'   {"дата":<11}{"время":<7}{"событие":<9}{"сайт":<32}{"возраст":>8}  набор контента')
for r in sorted(rows, key=lambda r: (r['дата'], r['время'])):
    P(f'   {r["дата"]:<11}{r["время"]:<7}{r["событие"]:<9}{r["сайт"]:<32}{str(r["возраст базы, дней"]):>8}  {r["набор контента"]}')

open(out_p, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
with open(out_p.replace('.txt', '.csv'), 'w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print('\n'.join(L))
