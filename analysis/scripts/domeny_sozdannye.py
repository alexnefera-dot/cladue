#!/usr/bin/env python3
"""Домены, созданные в окне: сгенерированы и на них есть сайты.

Создание и переобход — разные вещи. Домен может быть сгенерирован и стоять
без единой отправки в переобход; отбор здесь идёт по `domain_created`
(оно же `site_created`), а не по `recrawl_sent_at`.

Реестр отдаётся порциями по дате, и окно режется разными полями, поэтому на
вход подаются все выгрузки, какие есть: сайт берётся один раз, дубликаты
между файлами отбрасываются.

    python3 domeny_sozdannye.py --ot 2026-10-15 --do 2026-11-07 \
        --reestr api/dorgen_subdomains_*.jsonl --out export/domeny.txt --spisok export/spisok.txt
"""
import collections
import json
import sys

opt = collections.defaultdict(list)
klyuch = None
for a in sys.argv[1:]:
    if a.startswith('--'):
        klyuch = a[2:]
    else:
        opt[klyuch].append(a)

ot, do = opt['ot'][0], opt['do'][0]
stroki = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    stroki.append(s)


dom = collections.defaultdict(lambda: dict(
    saitov=0, zapushcheno=0, sozdan=None, pervyy=None, posledniy=None, zona=None,
    stadii=collections.Counter(), kontenty=collections.Counter(), brendy=set(),
    oshibki=collections.Counter(), pipeline=collections.Counter()))
vidennye = set()
vsego_v_okne = 0
for put in opt['reestr']:
    try:
        f = open(put, encoding='utf-8')
    except OSError:
        continue
    for stroka in f:
        r = json.loads(stroka)
        s = r['subdomain']
        if s in vidennye:
            continue
        sozdan = (r.get('domain_created') or r.get('site_created') or '')[:10]
        if not (ot <= sozdan <= do):
            continue
        vidennye.add(s)
        vsego_v_okne += 1
        b = r.get('content_domain_url') or s.split('.', 1)[-1]
        g = dom[b]
        g['saitov'] += 1
        g['zona'] = r.get('tld') or b.rsplit('.', 1)[-1]
        g['sozdan'] = sozdan if not g['sozdan'] else min(g['sozdan'], sozdan)
        g['stadii'][r.get('yandex_pipeline_stage')] += 1
        if r.get('content_label'):
            g['kontenty'][r['content_label']] += 1
        if r.get('brand_label'):
            g['brendy'].add(r['brand_label'])
        if r.get('pipeline_error'):
            g['oshibki'][str(r['pipeline_error'])[:40]] += 1
        ps = (r.get('pipeline_started') or '')[:10]
        if ps:
            g['pipeline'][ps] += 1
        d = (r.get('recrawl_sent_at') or '')[:10]
        if not d:
            continue
        g['zapushcheno'] += 1
        if not g['pervyy'] or d < g['pervyy']:
            g['pervyy'] = d
        if not g['posledniy'] or d > g['posledniy']:
            g['posledniy'] = d

spisok = sorted(dom, key=lambda b: (dom[b]['sozdan'], b))
P(f'ДОМЕНЫ, СОЗДАННЫЕ {ot} .. {do}')
P(f'  отбор по domain_created (оно же site_created), не по переобходу')
P(f'  доменов {len(spisok)}, сайтов на них {vsego_v_okne}')
zap = [b for b in spisok if dom[b]['zapushcheno']]
P(f'  из них с отправленным переобходом: {len(zap)}; без единой отправки: {len(spisok)-len(zap)}')
P('')

P('ПО ДАТАМ СОЗДАНИЯ')
P(f'  {"дата":<12} {"доменов":>8} {"сайтов":>8} {"запущено сайтов":>16} {"доменов с переобходом":>22}')
po_date = collections.defaultdict(list)
for b in spisok:
    po_date[dom[b]['sozdan']].append(b)
for d in sorted(po_date):
    bs = po_date[d]
    P(f'  {d:<12} {len(bs):>8} {sum(dom[b]["saitov"] for b in bs):>8} '
      f'{sum(dom[b]["zapushcheno"] for b in bs):>16} {sum(1 for b in bs if dom[b]["zapushcheno"]):>22}')
P('')

P('СТАДИИ КОНВЕЙЕРА ПО ВСЕМ ЭТИМ САЙТАМ')
vse_st = collections.Counter()
for b in spisok:
    vse_st.update(dom[b]['stadii'])
for st, n in vse_st.most_common():
    P(f'  {str(st):<14} {n:>7}  {n/vsego_v_okne:>6.1%}')
P('')

P('ТАБЛИЦА')
P(f'  {"домен":<22} {"зона":<7} {"создан":<11} {"сайтов":>6} {"запущ":>6} {"переобход":<22} '
  f'{"стадии":<40} {"контент"}')
for b in spisok:
    g = dom[b]
    per = (g['pervyy'] if g['pervyy'] == g['posledniy'] else f'{g["pervyy"]}..{g["posledniy"]}') \
        if g['pervyy'] else 'не отправлялся'
    st = ', '.join(f'{k} {v}' for k, v in g['stadii'].most_common(3))
    kont = g['kontenty'].most_common(1)[0][0] if g['kontenty'] else '—'
    P(f'  {b:<22} {g["zona"]:<7} {g["sozdan"]:<11} {g["saitov"]:>6} {g["zapushcheno"]:>6} '
      f'{per:<22} {st:<40} {kont}')

if opt['out']:
    with open(opt['out'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(stroki) + '\n')
    print(f'\nзаписано: {opt["out"][0]}')
if opt['spisok']:
    with open(opt['spisok'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(spisok) + '\n')
    print(f'список доменов: {opt["spisok"][0]} ({len(spisok)} строк)')
