#!/usr/bin/env python3
"""Активные домены с провалом по трафику: без кликов за окно или меньше порога в сутки.

Домен = контент-база вида `v2ld.lol`, на ней 150–206 сайтов `бренд.база.зона`.
Активным считается домен, у которого хотя бы один сайт получил переобход и
последний переобход случился не позже чем за `--zrelost` суток до конца окна:
сайту нужно несколько дней, чтобы попасть в выдачу, иначе свежий запуск попадёт
в мёртвые просто потому, что не успел.

Клики считаются двумя мерами:
  * живые поисковые — не бот, реферер Яндекса; с них приходят деньги;
  * все наши — обе метки кампании (`dorgen_engine` и `dorgne_fenix`), с ботами.

    python3 domeny_po_klikam.py --kesh api/kesh.tsv --clicks api/tracker_clicks_*.jsonl \
        --okno 7 --konec 2026-10-23 --porog 100 --out export/domeny_po_klikam.txt
"""
import collections
import csv
import datetime as dt
import json
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
porog = float(opt['porog'][0])
zrelost = int((opt['zrelost'] or [3])[0])
dni_okna = {(konec - dt.timedelta(days=i)).isoformat() for i in range(okno)}
predel_zapuska = (konec - dt.timedelta(days=zrelost)).isoformat()

stroki = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    stroki.append(s)


# 1. реестр: домен -> сайты, даты переобхода
dom = collections.defaultdict(lambda: dict(saitov=0, zapushcheno=0, pervyy=None, posledniy=None, zona=None))
sait2dom = {}
with open(opt['kesh'][0], encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        baza = r['base']
        g = dom[baza]
        g['saitov'] += 1
        g['zona'] = r['tld'] or baza.rsplit('.', 1)[-1]
        sait2dom[r['subdomain']] = baza
        if not r['recrawl']:
            continue
        g['zapushcheno'] += 1
        d = r['recrawl'][:10]
        if not g['pervyy'] or d < g['pervyy']:
            g['pervyy'] = d
        if not g['posledniy'] or d > g['posledniy']:
            g['posledniy'] = d

# 2. клики окна
zhivye = collections.Counter()
vse = collections.Counter()
zhivye_saity = collections.defaultdict(set)
dni_s_klikami = collections.defaultdict(set)
for put in opt['clicks']:
    with open(put, encoding='utf-8') as f:
        for stroka in f:
            r = json.loads(stroka)
            if r.get('campaign') not in NASHI:
                continue
            den = r['at'][:10]
            if den not in dni_okna:
                continue
            baza = sait2dom.get(r.get('subdomain'))
            if baza is None:
                continue
            vse[baza] += 1
            if r.get('is_bot') or 'yandex.' not in (r.get('referer') or ''):
                continue
            zhivye[baza] += 1
            zhivye_saity[baza].add(r['subdomain'])
            dni_s_klikami[baza].add(den)

# 3. отбор активных
aktivnye = [b for b, g in dom.items()
            if g['zapushcheno'] and g['pervyy'] and g['pervyy'] <= predel_zapuska]
P(f'окно {okno} сут по {konec}, порог {porog:g} живых кликов в сутки на домен')
P(f'доменов в реестре {len(dom)}, из них запущено и вызрело (переобход до {predel_zapuska}) — {len(aktivnye)}')
P('')

mertvye, slabye, rabochie = [], [], []
for b in aktivnye:
    v_sutki = zhivye[b] / okno
    (mertvye if zhivye[b] == 0 else slabye if v_sutki < porog else rabochie).append(b)

vsego_zhivyh = sum(zhivye[b] for b in aktivnye)
P(f'{"мертвы по трафику (0 живых кликов)":<42} {len(mertvye):>5} дом.  {len(mertvye)/len(aktivnye):>6.1%}')
P(f'{f"слабые (меньше {porog:g} живых в сутки)":<42} {len(slabye):>5} дом.  {len(slabye)/len(aktivnye):>6.1%}'
  f'   кликов {sum(zhivye[b] for b in slabye):>8}  ({sum(zhivye[b] for b in slabye)/max(vsego_zhivyh,1):.1%} трафика)')
P(f'{f"рабочие ({porog:g} и больше)":<42} {len(rabochie):>5} дом.  {len(rabochie)/len(aktivnye):>6.1%}'
  f'   кликов {sum(zhivye[b] for b in rabochie):>8}  ({sum(zhivye[b] for b in rabochie)/max(vsego_zhivyh,1):.1%} трафика)')
P('')

# распределение, чтобы было видно где на самом деле проходит граница
P('распределение активных доменов по живым кликам в сутки')
grani = [0, 1, 5, 10, 25, 50, 100, 250, 500, 1000, 10 ** 9]
imena = ['0', '0–1', '1–5', '5–10', '10–25', '25–50', '50–100', '100–250', '250–500', '500–1000', '1000+']
raspr = collections.Counter()
for b in aktivnye:
    v = zhivye[b] / okno
    for i in range(len(grani)):
        if v == 0:
            raspr['0'] = raspr['0'] + 1
            break
        if v < grani[i + 1]:
            raspr[imena[i + 1]] += 1
            break
P(f'  {"кликов/сут":<12} {"доменов":>8} {"доля":>7}')
for im in imena:
    if raspr[im]:
        P(f'  {im:<12} {raspr[im]:>8} {raspr[im]/len(aktivnye):>7.1%}')
P('')

# 4. таблица
plohie = sorted(mertvye + slabye, key=lambda b: (zhivye[b], -dom[b]['zapushcheno']))
P(f'ДОМЕНЫ НИЖЕ ПОРОГА — {len(plohie)} шт.')
P(f'  {"домен":<22} {"зона":<7} {"сайтов":>6} {"запущ":>6} {"переобход":<22} '
  f'{"живых":>7} {"в сутки":>8} {"сайтов с кликом":>15} {"дней с кликом":>13} {"всего кликов":>12}')
for b in plohie:
    g = dom[b]
    period = g['pervyy'] if g['pervyy'] == g['posledniy'] else f"{g['pervyy']}..{g['posledniy']}"
    P(f'  {b:<22} {g["zona"]:<7} {g["saitov"]:>6} {g["zapushcheno"]:>6} {period:<22} '
      f'{zhivye[b]:>7} {zhivye[b]/okno:>8.1f} {len(zhivye_saity[b]):>15} {len(dni_s_klikami[b]):>13} {vse[b]:>12}')

# 5. кто вытягивает сеть
P('')
luchshie = sorted(aktivnye, key=lambda b: -zhivye[b])[:25]
P('ТОП-25 ПО ЖИВЫМ КЛИКАМ')
P(f'  {"домен":<22} {"зона":<7} {"запущ":>6} {"переобход":<22} {"живых":>7} {"в сутки":>8} {"сайтов с кликом":>15}')
for b in luchshie:
    g = dom[b]
    period = g['pervyy'] if g['pervyy'] == g['posledniy'] else f"{g['pervyy']}..{g['posledniy']}"
    P(f'  {b:<22} {g["zona"]:<7} {g["zapushcheno"]:>6} {period:<22} '
      f'{zhivye[b]:>7} {zhivye[b]/okno:>8.1f} {len(zhivye_saity[b]):>15}')

# 6. разрез мёртвых: зона, неделя запуска, деньги
CENA = {'casino': 7.0, 'buzz': 3.0, 'team': 2.0, 'lol': 1.0}


def nedelya(d):
    data = dt.date.fromisoformat(d)
    pon = data - dt.timedelta(days=data.weekday())
    return pon.isoformat()


P('')
P('МЁРТВЫЕ ПО ЗОНАМ (0 живых кликов за окно)')
P(f'  {"зона":<8} {"мертво":>7} {"активно":>8} {"доля":>7} {"цена домена":>12} {"закопано":>10}')
po_zone_m = collections.Counter(dom[b]['zona'] for b in mertvye)
po_zone_a = collections.Counter(dom[b]['zona'] for b in aktivnye)
zakopano = 0.0
for z in sorted(po_zone_a, key=lambda z: -po_zone_m[z]):
    cena = CENA.get(z, 0.0)
    summa = po_zone_m[z] * cena
    zakopano += summa
    P(f'  {z:<8} {po_zone_m[z]:>7} {po_zone_a[z]:>8} {po_zone_m[z]/po_zone_a[z]:>7.1%} '
      f'{cena:>11.0f}$ {summa:>9.0f}$')
P(f'  {"итого":<8} {len(mertvye):>7} {len(aktivnye):>8} {len(mertvye)/len(aktivnye):>7.1%} '
  f'{"":>12} {zakopano:>9.0f}$')

P('')
P('МЁРТВЫЕ ПО НЕДЕЛЕ ПЕРВОГО ПЕРЕОБХОДА')
P(f'  {"неделя с":<12} {"активно":>8} {"мертво":>7} {"доля":>7} {"медиана живых/сут":>18}')
po_ned = collections.defaultdict(list)
for b in aktivnye:
    po_ned[nedelya(dom[b]['pervyy'])].append(b)
for ned in sorted(po_ned):
    gruppa = po_ned[ned]
    m = sum(1 for b in gruppa if zhivye[b] == 0)
    med = sorted(zhivye[b] / okno for b in gruppa)[len(gruppa) // 2]
    P(f'  {ned:<12} {len(gruppa):>8} {m:>7} {m/len(gruppa):>7.1%} {med:>18.2f}')

if opt['out']:
    with open(opt['out'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(stroki) + '\n')
    print(f'\nзаписано: {opt["out"][0]}')
