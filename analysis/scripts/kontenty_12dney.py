#!/usr/bin/env python3
"""Наборы контента за последние N дней: индекс, клики, деньги.

По каждому набору: сколько доменов и сайтов запущено, сколько сайтов дошло
до поискового клика за трое суток от переобхода и сколько вообще, сколько
собрано поисковых кликов, сколько регистраций и первых депозитов.

    python3 kontenty_12dney.py <с даты> <по дату> <out.csv> <out.txt>
        --reg <реестр.jsonl> ... --clicks <клики.jsonl> ... --conv <конверсии.jsonl> ...

Окно трёх суток считается закрытым, если с переобхода прошло ≥3 суток к дате
последнего дня выгрузки кликов; у более свежих запусков колонка «за 3 суток»
пустая, а «всего» уже что-то показывает.
"""
import sys, json, re, csv, collections, datetime

args = sys.argv[1:]
SINCE, UNTIL, OUT_CSV, OUT_TXT = args[:4]
def group(flag):
    if flag not in args: return []
    i = args.index(flag) + 1
    out = []
    while i < len(args) and not args[i].startswith('--'):
        out.append(args[i]); i += 1
    return out
REG_P, CLICK_P, CONV_P = group('--reg'), group('--clicks'), group('--conv')

day = lambda s: datetime.date.fromisoformat(s)
root = lambda name: re.sub(r'_\d+$', '', name)          # хвост с номером домена — не набор

SUB = {}
for p in REG_P:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        s = (r.get('subdomain') or '').lower()
        rc = (r.get('recrawl_sent_at') or '')[:10]
        if not s or not rc or not (SINCE <= rc <= UNTIL):
            continue
        SUB[s] = {'rc': rc, 'set': root(r.get('content_label') or 'не записан'),
                  'base': s.split('.', 1)[1], 'tld': s.rsplit('.', 1)[-1]}
    print(f'  реестр {p.split("/")[-1]}: накоплено {len(SUB)} сайтов', flush=True)

first, ya = {}, collections.Counter()
last_click_day = ''
for p in CLICK_P:
    n = 0
    for line in open(p, encoding='utf-8'):
        r = json.loads(line); n += 1
        s = (r.get('subdomain') or '').lower()
        if s not in SUB or r.get('is_bot'):
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        d = r['at'][:10]
        if d > last_click_day: last_click_day = d
        ya[s] += 1
        if s not in first or d < first[s]:
            first[s] = d
    print(f'  клики {p.split("/")[-1]}: {n} строк, сайтов с поиском {len(first)}', flush=True)

CONV = collections.defaultdict(collections.Counter)
for p in CONV_P:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        if r.get('campaign') != 'dorgen_engine':
            continue
        s = (r.get('subdomain') or '').lower()
        if s not in SUB:
            continue
        lag = (day(r['at'][:10]) - day(SUB[s]['rc'])).days
        c = CONV[s]
        c[r['event']] += 1
        if 0 <= lag <= 3:
            c[r['event'] + '3'] += 1

G = collections.defaultdict(lambda: collections.Counter())
DOM = collections.defaultdict(set); DAYS = collections.defaultdict(set); ZONES = collections.defaultdict(collections.Counter)
for s, v in SUB.items():
    g = G[v['set']]
    g['sites'] += 1
    DOM[v['set']].add(v['base']); DAYS[v['set']].add(v['rc']); ZONES[v['set']][v['tld']] += 1
    closed = last_click_day and (day(last_click_day) - day(v['rc'])).days >= 3
    if closed:
        g['sites3'] += 1
    if s in first:
        g['idx'] += 1
        if closed and (day(first[s]) - day(v['rc'])).days <= 3:
            g['idx3'] += 1
    g['ya'] += ya[s]
    c = CONV.get(s)
    if c:
        g['reg'] += c['reg']; g['fd'] += c['fd']; g['reg3'] += c['reg3']; g['fd3'] += c['fd3']

rows = []
for k, g in G.items():
    rows.append({
        'набор контента': k, 'доменов': len(DOM[k]), 'сайтов': g['sites'],
        'дни запуска': ' '.join(sorted(d[5:] for d in DAYS[k])),
        'зоны': ' '.join(f'{z}:{n}' for z, n in ZONES[k].most_common()),
        'окно 3 суток закрыто у сайтов': g['sites3'],
        'в индексе за 3 суток': g['idx3'] if g['sites3'] else '',
        'в индексе за 3 суток %': round(100 * g['idx3'] / g['sites3'], 1) if g['sites3'] else '',
        'в индексе всего': g['idx'],
        'в индексе всего %': round(100 * g['idx'] / g['sites'], 1),
        'не в индексе': g['sites'] - g['idx'],
        'поисковых кликов': g['ya'],
        'кликов на сайт': round(g['ya'] / g['sites'], 2),
        'кликов на вышедший сайт': round(g['ya'] / g['idx'], 1) if g['idx'] else 0,
        'регистраций': g['reg'], 'ФД': g['fd'],
        'регистраций в окне 3 суток': g['reg3'], 'ФД в окне': g['fd3'],
        'рег на 100 сайтов': round(100 * g['reg'] / g['sites'], 3),
        'рег на 10 тыс. кликов': round(1e4 * g['reg'] / g['ya'], 1) if g['ya'] else '',
    })
rows.sort(key=lambda r: (-(r['в индексе всего %']), -r['сайтов']))
with open(OUT_CSV, 'w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

T = collections.Counter()
for g in G.values():
    for k in g: T[k] += g[k]
L = []
P = L.append
P(f'НАБОРЫ КОНТЕНТА, ЗАПУСКИ {SINCE} – {UNTIL} (клики по {last_click_day} включительно)')
P(f'наборов {len(rows)}, доменов {sum(r["доменов"] for r in rows)}, сайтов {T["sites"]}')
P(f'в индексе {T["idx"]} ({100*T["idx"]/T["sites"]:.1f}%), не в индексе {T["sites"]-T["idx"]} ({100*(T["sites"]-T["idx"])/T["sites"]:.1f}%)')
P(f'поисковых кликов {T["ya"]}, регистраций {T["reg"]}, ФД {T["fd"]}; '
  f'{100*T["reg"]/T["sites"]:.3f} рег на 100 сайтов, {1e4*T["reg"]/max(T["ya"],1):.2f} рег на 10 тыс. кликов')
P('')
h = f'{"набор":<40}{"дом":>5}{"сайтов":>8}{"индекс 3с":>11}{"индекс всего":>14}{"кл/сайт":>9}{"рег":>5}{"ФД":>4}{"рег/100":>9}{"рег/10тыс":>11}'
P(h); P('-' * len(h))
for r in rows:
    i3 = f'{r["в индексе за 3 суток %"]}%' if r['в индексе за 3 суток %'] != '' else '—'
    P(f'{r["набор контента"][:39]:<40}{r["доменов"]:>5}{r["сайтов"]:>8}{i3:>11}'
      f'{str(r["в индексе всего %"])+"%":>14}{r["кликов на сайт"]:>9}{r["регистраций"]:>5}{r["ФД"]:>4}'
      f'{r["рег на 100 сайтов"]:>9}{str(r["рег на 10 тыс. кликов"]):>11}')
open(OUT_TXT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
