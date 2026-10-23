#!/usr/bin/env python3
"""Домены с трафиком, но без единой конверсии: кликам есть, рег и ФД нет вовсе.

Это не мёртвые домены — те вообще не получают переходов. Здесь обратный случай:
домен в выдаче, люди на него заходят, а до регистрации не доходит никто.
Берутся все конверсии за всю историю трекера, не за окно, чтобы «вообще» было
честным словом.

    python3 domeny_bez_konversiy.py --kesh api/kesh.tsv --clicks api/tracker_clicks_*.jsonl \
        --conv api/tracker_conversions_*.jsonl --clicks-ot 2026-10-11 --clicks-do 2026-10-23 \
        --out export/domeny_bez_konversiy.txt --spisok export/domeny_bez_konversiy_spisok.txt
"""
import collections
import csv
import json
import sys

NASHI = {'dorgen_engine', 'dorgne_fenix'}
ZONY = {'lol', 'team', 'casino', 'buzz'}
CENA = {'casino': 7.0, 'buzz': 3.0, 'team': 2.0, 'lol': 1.0}

opt = collections.defaultdict(list)
klyuch = None
for a in sys.argv[1:]:
    if a.startswith('--'):
        klyuch = a[2:]
    else:
        opt[klyuch].append(a)

ot, do = opt['clicks-ot'][0], opt['clicks-do'][0]
dney = int((opt['dney'] or [13])[0])

stroki = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    stroki.append(s)


def baza_hosta(host):
    if host.count('.') < 2:
        return None
    b = host.split('.', 1)[1]
    return b if b.rsplit('.', 1)[-1] in ZONY else None


dom = {}
sait2dom = {}
sait2brend = {}
with open(opt['kesh'][0], encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        b = r['base']
        g = dom.setdefault(b, dict(zona=r['tld'] or b.rsplit('.', 1)[-1], poddomenov=0,
                                   zapushcheno=0, pervyy=None, posledniy=None, v_reestre=True))
        g['poddomenov'] += 1
        sait2dom[r['subdomain']] = b
        sait2brend[r['subdomain']] = r['brand'] or '?'
        if not r['recrawl']:
            continue
        g['zapushcheno'] += 1
        d = r['recrawl'][:10]
        if not g['pervyy'] or d < g['pervyy']:
            g['pervyy'] = d
        if not g['posledniy'] or d > g['posledniy']:
            g['posledniy'] = d


def dobavit(b):
    return dom.setdefault(b, dict(zona=b.rsplit('.', 1)[-1], poddomenov=0, zapushcheno=0,
                                  pervyy=None, posledniy=None, v_reestre=False))


zhivye = collections.Counter()
vse_kliki = collections.Counter()
saity = collections.defaultdict(set)
brendy = collections.defaultdict(collections.Counter)
for put in opt['clicks']:
    with open(put, encoding='utf-8') as f:
        for stroka in f:
            r = json.loads(stroka)
            if r.get('campaign') not in NASHI:
                continue
            host = r.get('subdomain') or ''
            b = sait2dom.get(host) or baza_hosta(host)
            if not b:
                continue
            dobavit(b)
            vse_kliki[b] += 1
            if r.get('is_bot') or 'yandex.' not in (r.get('referer') or ''):
                continue
            zhivye[b] += 1
            saity[b].add(host)
            brendy[b][sait2brend.get(host) or host.split('.', 1)[0]] += 1

konv = collections.Counter()
vidennye = set()
dni_konv = set()
for put in opt['conv']:
    with open(put, encoding='utf-8') as f:
        for stroka in f:
            r = json.loads(stroka)
            if r.get('campaign') not in NASHI:
                continue
            k = (r['clickid'], r['event'], r['at'])
            if k in vidennye:
                continue
            vidennye.add(k)
            dni_konv.add(r['at'][:10])
            b = sait2dom.get(r.get('subdomain')) or baza_hosta(r.get('subdomain') or '')
            if b:
                dobavit(b)
                konv[b] += 1

nemye = sorted((b for b in dom if zhivye[b] and not konv[b]), key=lambda b: -zhivye[b])
s_trafikom = [b for b in dom if zhivye[b]]

P(f'клики за {ot}..{do} ({dney} сут); конверсии за всю историю трекера '
  f'({min(dni_konv)}..{max(dni_konv)})')
P('живой клик = не бот, реферер Яндекса, метка dorgen_engine или dorgne_fenix')
P('')
P(f'доменов всего {len(dom)}; с живым трафиком {len(s_trafikom)}; '
  f'из них БЕЗ ЕДИНОЙ конверсии {len(nemye)} ({len(nemye)/len(s_trafikom):.1%})')
P(f'их живые клики: {sum(zhivye[b] for b in nemye)} из {sum(zhivye.values())} = '
  f'{sum(zhivye[b] for b in nemye)/sum(zhivye.values()):.1%} всего живого трафика')
P('')

P('ПО ГРУППАМ ТРАФИКА')
GRANI = [(1, 9, '1-9 кликов'), (10, 49, '10-49'), (50, 199, '50-199'),
         (200, 499, '200-499'), (500, 1999, '500-1999'), (2000, 10 ** 9, '2000 и больше')]
P(f'  {"группа":<16} {"немых":>7} {"всего с трафиком":>17} {"доля немых":>11} '
  f'{"их кликов":>10} {"доля трафика":>13} {"закопано":>10}')
for lo, hi, imya in GRANI:
    gr = [b for b in nemye if lo <= zhivye[b] <= hi]
    vsya = [b for b in s_trafikom if lo <= zhivye[b] <= hi]
    if not vsya:
        continue
    k = sum(zhivye[b] for b in gr)
    dengi = sum(CENA.get(dom[b]['zona'], 0) for b in gr)
    P(f'  {imya:<16} {len(gr):>7} {len(vsya):>17} {len(gr)/len(vsya):>11.1%} '
      f'{k:>10} {k/sum(zhivye.values()):>12.1%} {dengi:>9.0f}$')
P(f'  {"ИТОГО":<16} {len(nemye):>7} {len(s_trafikom):>17} {len(nemye)/len(s_trafikom):>11.1%} '
  f'{sum(zhivye[b] for b in nemye):>10} '
  f'{sum(zhivye[b] for b in nemye)/sum(zhivye.values()):>12.1%} '
  f'{sum(CENA.get(dom[b]["zona"], 0) for b in nemye):>9.0f}$')
P('')

P('ПО ЗОНАМ')
P(f'  {"зона":<10} {"немых":>7} {"с трафиком":>11} {"доля":>7} {"их кликов":>10}')
zn = collections.Counter(dom[b]['zona'] for b in nemye)
za = collections.Counter(dom[b]['zona'] for b in s_trafikom)
for z in sorted(za, key=lambda z: -zn[z]):
    k = sum(zhivye[b] for b in nemye if dom[b]['zona'] == z)
    P(f'  {z:<10} {zn[z]:>7} {za[z]:>11} {zn[z]/za[z]:>7.1%} {k:>10}')
P('')

P(f'ТАБЛИЦА — {len(nemye)} доменов с трафиком и без конверсий, по убыванию кликов')
P(f'  {"домен":<22} {"зона":<7} {"запущ":>6} {"первый переобход":<17} {"последний":<12} '
  f'{"живых":>7} {"в сутки":>8} {"всего кликов":>12} {"сайтов":>7} {"главный бренд":<18} {"его доля":>9} {"цена":>6}')
for b in nemye:
    g = dom[b]
    brend, bk = brendy[b].most_common(1)[0]
    P(f'  {b:<22} {g["zona"]:<7} {g["zapushcheno"]:>6} {(g["pervyy"] or "нет в реестре"):<17} '
      f'{(g["posledniy"] or "—"):<12} {zhivye[b]:>7} {zhivye[b]/dney:>8.1f} {vse_kliki[b]:>12} '
      f'{len(saity[b]):>7} {brend:<18} {bk/zhivye[b]:>8.0%} {CENA.get(g["zona"], 0):>5.0f}$')

P('')
P('ЧЬИ ЭТО ДОМЕНЫ — бренды, собравшие трафик немых доменов')
svod = collections.Counter()
skolko_dom = collections.Counter()
for b in nemye:
    for brend, k in brendy[b].items():
        svod[brend] += k
    skolko_dom[brendy[b].most_common(1)[0][0]] += 1
# сколько тот же бренд принёс конверсий по всей сети
brend_konv = collections.Counter()
for put in opt['conv']:
    with open(put, encoding='utf-8') as f:
        for stroka in f:
            r = json.loads(stroka)
            if r.get('campaign') not in NASHI:
                continue
            host = r.get('subdomain') or ''
            brend = sait2brend.get(host) or (host.split('.', 1)[0] if host.count('.') >= 2 else None)
            if brend:
                brend_konv[brend] += 1
P(f'  {"бренд":<20} {"кликов на немых":>16} {"немых доменов":>14} {"конверсий бренда везде":>23}')
for brend, k in svod.most_common(25):
    P(f'  {brend:<20} {k:>16} {skolko_dom[brend]:>14} {brend_konv[brend]:>23}')

if opt['out']:
    with open(opt['out'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(stroki) + '\n')
    print(f'\nзаписано: {opt["out"][0]}')
if opt['spisok']:
    with open(opt['spisok'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(nemye) + '\n')
    print(f'список доменов: {opt["spisok"][0]} ({len(nemye)} строк)')
