#!/usr/bin/env python3
"""Концентрация трафика: считать по доменам (домен и все его поддомены) или по сайтам.

В реестре `domain_id` стоит у каждого поддомена, по строке на штуку, а
зарегистрированный домен — это `content_domain_url` со 150–206 поддоменами
`бренд.база.зона`. Поэтому «домен и все его поддомены» — это группировка по
`content_domain_url`, и разбор `domeny_po_klikam.py` уже сделан на этом уровне.
Здесь две кривые концентрации рядом, чтобы видеть, что меняет укрупнение.

Отдельно считаются базы, которых нет в реестре запусков вовсе: Analytics Export
API не отдаёт ничего раньше 01.08.2026 ни по одному полю даты, а трафик с таких
хостов идёт и конвертится под нашей меткой.

    python3 domen_vs_poddomen.py --kesh api/kesh.tsv --clicks api/tracker_clicks_*.jsonl \
        --okno 7 --konec 2026-10-22 --out export/domen_vs_poddomen.txt
"""
import collections
import csv
import datetime as dt
import json
import statistics
import sys

NASHI = {'dorgen_engine', 'dorgne_fenix'}

opt = collections.defaultdict(list)
klyuch = None
for a in sys.argv[1:]:
    if a.startswith('--'):
        klyuch = a[2:]
    else:
        opt[klyuch].append(a)

konec = dt.date.fromisoformat(opt['konec'][0])
okno = int(opt['okno'][0])
zrelost = int((opt['zrelost'] or [3])[0])
dni_okna = {(konec - dt.timedelta(days=i)).isoformat() for i in range(okno)}
predel = (konec - dt.timedelta(days=zrelost)).isoformat()

stroki = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    stroki.append(s)


dom = collections.defaultdict(lambda: dict(zapushcheno=0, pervyy=None))
sait2dom = {}
with open(opt['kesh'][0], encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        sait2dom[r['subdomain']] = r['base']
        if not r['recrawl']:
            continue
        g = dom[r['base']]
        g['zapushcheno'] += 1
        d = r['recrawl'][:10]
        if not g['pervyy'] or d < g['pervyy']:
            g['pervyy'] = d

po_domenu = collections.Counter()
po_saitu = collections.Counter()
saity_domena = collections.defaultdict(set)
vne_reestra = collections.Counter()
for put in opt['clicks']:
    with open(put, encoding='utf-8') as f:
        for stroka in f:
            r = json.loads(stroka)
            if r.get('campaign') not in NASHI or r['at'][:10] not in dni_okna:
                continue
            if r.get('is_bot') or 'yandex.' not in (r.get('referer') or ''):
                continue
            host = r.get('subdomain') or ''
            baza = sait2dom.get(host)
            if baza is None:
                if host.count('.') >= 2:
                    vne_reestra[host.split('.', 1)[1]] += 1
                continue
            po_domenu[baza] += 1
            po_saitu[host] += 1
            saity_domena[baza].add(host)

aktivnye = [b for b, g in dom.items() if g['zapushcheno'] and g['pervyy'] and g['pervyy'] <= predel]
saitov = sum(dom[b]['zapushcheno'] for b in aktivnye)
vsego = sum(po_domenu[b] for b in aktivnye)

P(f'окно {okno} сут по {konec}')
P(f'активных доменов {len(aktivnye)}, в них запущенных поддоменов {saitov}')
P(f'живых поисковых кликов {vsego}')
P('')
s_klikom_d = sum(1 for b in aktivnye if po_domenu[b])
P(f'доменов хотя бы с одним живым кликом:    {s_klikom_d:>6} из {len(aktivnye)}  ({s_klikom_d/len(aktivnye):.1%})')
P(f'поддоменов хотя бы с одним живым кликом: {len(po_saitu):>6} из {saitov}  ({len(po_saitu)/saitov:.2%})')
P('')

P('КОНЦЕНТРАЦИЯ ТРАФИКА — две кривые рядом')
P(f'  {"верхние N":<10} {"по доменам":>12} {"доля":>7}   {"по поддоменам":>14} {"доля":>7}')
rd = sorted((po_domenu[b] for b in aktivnye), reverse=True)
rs = sorted(po_saitu.values(), reverse=True)
for n in (1, 3, 5, 10, 25, 50, 100, 250, 500, 1000):
    a, c = sum(rd[:n]), sum(rs[:n])
    P(f'  {n:<10} {a:>12} {a/vsego:>7.1%}   {c:>14} {c/vsego:>7.1%}')
P('')

rabochie = sorted((b for b in aktivnye if po_domenu[b]), key=lambda b: -po_domenu[b])
P('СКОЛЬКО ПОДДОМЕНОВ КОРМИТ ДОМЕН')
P(f'  {"домен":<20} {"кликов":>7} {"в сутки":>8} {"поддоменов с кликом":>20} {"из":>5} {"доля верхнего":>14}')
for b in rabochie[:20]:
    verh = max(po_saitu[s] for s in saity_domena[b])
    P(f'  {b:<20} {po_domenu[b]:>7} {po_domenu[b]/okno:>8.1f} {len(saity_domena[b]):>20} '
      f'{dom[b]["zapushcheno"]:>5} {verh/po_domenu[b]:>13.0%}')
n_saitov = [len(saity_domena[b]) for b in rabochie]
doli = [max(po_saitu[s] for s in saity_domena[b]) / po_domenu[b] for b in rabochie]
P('')
P(f'по всем {len(rabochie)} доменам с трафиком: медиана поддоменов с кликом '
  f'{statistics.median(n_saitov):.0f} из {statistics.median([dom[b]["zapushcheno"] for b in rabochie]):.0f}; '
  f'медианная доля верхнего поддомена {statistics.median(doli):.0%}')
P('')

P('БАЗЫ ВНЕ РЕЕСТРА ЗАПУСКОВ')
P(f'  баз {len(vne_reestra)}, живых кликов {sum(vne_reestra.values())} '
  f'({sum(vne_reestra.values())/(vsego+sum(vne_reestra.values())):.1%} всего живого трафика)')
zony = collections.Counter()
for b, c in vne_reestra.items():
    zony[b.rsplit('.', 1)[-1]] += c
P(f'  по зонам: {dict(zony.most_common())}')
P(f'  {"база":<20} {"кликов":>7}')
for b, c in vne_reestra.most_common(20):
    P(f'  {b:<20} {c:>7}')

if opt['out']:
    with open(opt['out'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(stroki) + '\n')
    print(f'\nзаписано: {opt["out"][0]}')
