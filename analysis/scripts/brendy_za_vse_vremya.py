#!/usr/bin/env python3
"""Конверсии по брендам за всю историю трекера.

Бренд сайта берётся из реестра (`brand_label`). У сайтов, которых в реестре нет
(Analytics Export API не отдаёт ничего раньше 01.08.2026, а трафик и конверсии
с таких хостов идут под нашей меткой), бренд берётся из первой метки хоста:
`gizbo.vspz.team` -> `gizbo`. Такие имена приводятся к нижнему регистру и
склеиваются с реестровыми, иначе один бренд считается дважды.

    python3 brendy_za_vse_vremya.py --kesh api/kesh.tsv --kesh-klikov api/kesh_klikov.tsv \
        --conv api/tracker_conversions_*.jsonl --clicks api/tracker_clicks_*.jsonl \
        --out export/brendy_za_vse_vremya.txt
"""
import collections
import csv
import json
import sys

NASHI = {'dorgen_engine', 'dorgne_fenix'}
ZONY = {'lol', 'team', 'casino', 'buzz'}
CENA_REG, CENA_FD = 8.11, 40.0

opt = collections.defaultdict(list)
klyuch = None
for a in sys.argv[1:]:
    if a.startswith('--'):
        klyuch = a[2:]
    else:
        opt[klyuch].append(a)

stroki = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    stroki.append(s)


# Часть брендов названа в реестре кириллицей, а на сайтах старше 01.08 метка хоста
# стоит латиницей: `olimp.<база>` против `Олимп`. Без этой таблицы один бренд
# считался бы двумя записями, у одной из которых нет сайтов, а у другой — конверсий.
ALIASY = {
    'olimp': 'олимп', 'selector': 'селектор', 'pokerdom': 'покердом',
    'fresh': 'фреш', 'everum': 'эверум', 'lootrun': 'лутран',
    'melbet': 'мелбет', 'volna': 'волна',
    'vulkan24': 'вулкан24', 'vulkanvegas': 'вулканвегас', 'vulkanmega': 'вулканмега',
    'vulkanprestige': 'вулканпрестиж', 'vulkanrussia': 'вулканроссия',
    'vulkanstars': 'вулканстарс', 'clubvulkan': 'клубвулкан',
}


# Реестровое имя бренда — показываемое; ключ склейки — нижний регистр без пробелов.
def klyuch_brenda(imya):
    k = (imya or '?').strip().lower().replace(' ', '').replace('-', '')
    return ALIASY.get(k, k)


pokaz = {}
sait2br = {}
br = collections.defaultdict(lambda: dict(saitov=0, zapushcheno=0, kliki=0, zhivye=0,
                                          reg=0, fd=0, saity_s_konv=set(), domeny=set(),
                                          zony=collections.Counter(), pervaya=None, poslednyaya=None))
with open(opt['kesh'][0], encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        k = klyuch_brenda(r['brand'])
        pokaz[k] = (r['brand'] or '?').strip()
        sait2br[r['subdomain']] = k
        g = br[k]
        g['saitov'] += 1
        g['domeny'].add(r['base'])
        g['zony'][r['tld'] or '?'] += 1
        if r['recrawl']:
            g['zapushcheno'] += 1


def brend_hosta(host):
    """Хост вне реестра -> бренд из первой метки, только в наших зонах."""
    if host.count('.') < 2 or host.rsplit('.', 1)[-1] not in ZONY:
        return None
    return klyuch_brenda(host.split('.', 1)[0])


with open(opt['kesh-klikov'][0], encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        k = sait2br.get(r['subdomain'])
        if k:
            br[k]['kliki'] += int(r['clicks_sum'] or 0)

for put in opt['clicks']:
    with open(put, encoding='utf-8') as f:
        for stroka in f:
            r = json.loads(stroka)
            if r.get('campaign') not in NASHI:
                continue
            if r.get('is_bot') or 'yandex.' not in (r.get('referer') or ''):
                continue
            host = r.get('subdomain') or ''
            k = sait2br.get(host) or brend_hosta(host)
            if k:
                br[k]['zhivye'] += 1
                pokaz.setdefault(k, host.split('.', 1)[0])

vidennye = set()
vne_reestra = collections.Counter()
for put in opt['conv']:
    with open(put, encoding='utf-8') as f:
        for stroka in f:
            r = json.loads(stroka)
            if r.get('campaign') not in NASHI:
                continue
            kk = (r['clickid'], r['event'], r['at'])
            if kk in vidennye:
                continue
            vidennye.add(kk)
            host = r.get('subdomain') or ''
            k = sait2br.get(host)
            if not k:
                k = brend_hosta(host)
                if not k:
                    continue
                vne_reestra[r['event']] += 1
                pokaz.setdefault(k, host.split('.', 1)[0])
            g = br[k]
            g['reg' if r['event'] == 'reg' else 'fd'] += 1
            g['saity_s_konv'].add(host)
            d = r['at'][:10]
            if not g['pervaya'] or d < g['pervaya']:
                g['pervaya'] = d
            if not g['poslednyaya'] or d > g['poslednyaya']:
                g['poslednyaya'] = d

vse = sorted(br, key=lambda k: (-br[k]['reg'], -br[k]['fd'], -br[k]['zhivye']))
s_konv = [k for k in vse if br[k]['reg'] or br[k]['fd']]
vsego_reg = sum(br[k]['reg'] for k in vse)
vsego_fd = sum(br[k]['fd'] for k in vse)
vsego_zh = sum(br[k]['zhivye'] for k in vse)

P('КОНВЕРСИИ ПО БРЕНДАМ ЗА ВСЮ ИСТОРИЮ ТРЕКЕРА')
P('  бренд сайта из реестра (brand_label); у сайтов вне реестра — первая метка хоста')
P('  живые клики только за выгруженные дни трекера, клики из реестра — за всю жизнь сайта')
P(f'  деньги посчитаны при {CENA_REG:.2f}$ за регу и {CENA_FD:.0f}$ за ФД')
P('')
P(f'  брендов всего {len(vse)}, с конверсиями {len(s_konv)}, без единой — {len(vse)-len(s_konv)}')
P(f'  регистраций {vsego_reg}, ФД {vsego_fd}, выручка '
  f'{vsego_reg*CENA_REG + vsego_fd*CENA_FD:,.0f}$'.replace(',', ' '))
P(f'  конверсий с сайтов вне реестра: рег {vne_reestra["reg"]}, ФД {vne_reestra["fd"]}')
P('')

SHAPKA = (f'  {"бренд":<20} {"сайтов":>7} {"запущ":>7} {"кликов":>9} {"живых":>8} '
          f'{"рег":>5} {"ФД":>4} {"ФД/рег":>7} {"кликов/рег":>11} {"выручка":>10} '
          f'{"первая":<11} {"последняя":<11}')


def strochka(k):
    g = br[k]
    na_regu = f'{g["kliki"]/g["reg"]:.0f}' if g['reg'] else '—'
    fd_reg = f'{g["fd"]/g["reg"]:.0%}' if g['reg'] else '—'
    dengi = g['reg'] * CENA_REG + g['fd'] * CENA_FD
    return (f'  {pokaz.get(k, k):<20} {g["saitov"]:>7} {g["zapushcheno"]:>7} {g["kliki"]:>9} '
            f'{g["zhivye"]:>8} {g["reg"]:>5} {g["fd"]:>4} {fd_reg:>7} {na_regu:>11} '
            f'{dengi:>9.0f}$ {(g["pervaya"] or "—"):<11} {(g["poslednyaya"] or "—"):<11}')


P('ТОП-40 ПО РЕГИСТРАЦИЯМ')
P(SHAPKA)
for k in vse[:40]:
    P(strochka(k))
P('')

P('ЛУЧШИЕ ПО ДЕПОЗИТАМ — от 3 ФД')
P(SHAPKA)
for k in sorted((k for k in vse if br[k]['fd'] >= 3), key=lambda k: -br[k]['fd']):
    P(strochka(k))
P('')

P('ЛУЧШИЕ ПО КОНВЕРСИИ ТРАФИКА — от 5 рег, по кликам на регу')
P(SHAPKA)
for k in sorted((k for k in vse if br[k]['reg'] >= 5 and br[k]['kliki']),
                key=lambda k: br[k]['kliki'] / br[k]['reg']):
    P(strochka(k))
P('')

pustye = sorted((k for k in vse if not br[k]['reg'] and not br[k]['fd'] and br[k]['kliki']),
                key=lambda k: -br[k]['kliki'])
P(f'ПУСТЫЕ — {len(pustye)} брендов с трафиком и без единой конверсии за всю историю')
P(f'  их клики: {sum(br[k]["kliki"] for k in pustye)} из {sum(br[k]["kliki"] for k in vse)} '
  f'= {sum(br[k]["kliki"] for k in pustye)/max(sum(br[k]["kliki"] for k in vse),1):.1%} '
  f'всего трафика сети; сайтов под ними {sum(br[k]["saitov"] for k in pustye)}')
P(SHAPKA)
for k in pustye[:30]:
    P(strochka(k))
P('')

P(f'ВСЕ {len(vse)} БРЕНДОВ, по убыванию регистраций')
P(SHAPKA)
for k in vse:
    P(strochka(k))

if opt['out']:
    with open(opt['out'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(stroki) + '\n')
    print(f'\nзаписано: {opt["out"][0]}')
