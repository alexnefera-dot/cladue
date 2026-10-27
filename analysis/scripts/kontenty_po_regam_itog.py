#!/usr/bin/env python3
"""Точные контенты по регистрациям: что именно выкачивать и разбирать.

Контент — полное имя из `content_label`, например
`content-2026-09-15-7str-oform-2_48`; число в конце и есть номер экземпляра.
Набор (`7str-oform-2`) выводится рядом только для ориентира, отбор идёт по
точным именам.

Один контент занимает примерно один домен (медиана 206 сайтов), и вся сеть
даёт меньше одной реги на контент, поэтому голый счёт регистраций — это во
многом удача одного сайта. Чтобы отделить контент от сайта, считаются две
вещи:

* **ожидание** — сколько рег дал бы контент такого размера при средней отдаче
  по сети; «выше шума» значит факт больше ожидания на два корня (Пуассон);
* **сайтов и брендов с конверсией** — если все реги пришли с одного сайта, это
  свойство сайта и его бренда, а не контента. Доказательство за контентом —
  когда конверсии разнесены по трём и больше разным сайтам.

Источники — кэши, а не выгрузки: kesh_reestra.py даёт контент, бренд, базу,
зону и переобход, kesh_klikov.py — трафик за всю жизнь сайта.

    python3 kontenty_po_regam_itog.py --kesh api/kesh.tsv --kesh-klikov api/kesh_klikov.tsv \
        --conv api/tracker_conversions_*.jsonl --clicks api/tracker_clicks_*.jsonl \
        --ot 2026-09-01 --do 2026-10-27 --out export/kontenty.txt --spisok export/spisok.txt
"""
import collections
import csv
import json
import math
import re
import sys

NASHI = {'dorgen_engine', 'dorgne_fenix'}

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


DATA = re.compile(r'^content-\d{4}-\d{2}-\d{1,2}[a-zа-я]?-')


def nabor(imya):
    """`content-2026-09-15-7str-oform-2_48` -> `7str-oform-2`.

    Срезается только приставка с датой; день бывает с буквой (`14c`), а имена
    без даты (`NEW100-оформлено_41`) остаются как есть.
    """
    telo = DATA.sub('', imya)
    if telo == imya and imya.startswith('content-'):
        telo = imya[len('content-'):]
    return telo.rsplit('_', 1)[0]


kont = collections.defaultdict(lambda: dict(
    saitov=0, zapushcheno=0, pervyy=None, posledniy=None,
    zony=collections.Counter(), domeny=set(), brendy=set()))
sait2kont = {}
sait2brend = {}
with open(opt['kesh'][0], encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        imya = r['content']
        if not imya:
            continue
        g = kont[imya]
        g['saitov'] += 1
        sait2kont[r['subdomain']] = imya
        sait2brend[r['subdomain']] = r['brand'] or '?'
        g['zony'][r['tld'] or '?'] += 1
        g['domeny'].add(r['base'])
        g['brendy'].add(r['brand'] or '?')
        if not r['recrawl']:
            continue
        g['zapushcheno'] += 1
        d = r['recrawl'][:10]
        if not g['pervyy'] or d < g['pervyy']:
            g['pervyy'] = d
        if not g['posledniy'] or d > g['posledniy']:
            g['posledniy'] = d

kliki = collections.Counter()
s_klikom = collections.Counter()
with open(opt['kesh-klikov'][0], encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        imya = sait2kont.get(r['subdomain'])
        if not imya:
            continue
        kliki[imya] += int(r['clicks_sum'] or 0)
        if r['first_click']:
            s_klikom[imya] += 1

zhivye = collections.Counter()
for put in opt['clicks']:
    with open(put, encoding='utf-8') as f:
        for stroka in f:
            r = json.loads(stroka)
            if r.get('campaign') not in NASHI:
                continue
            if r.get('is_bot') or 'yandex.' not in (r.get('referer') or ''):
                continue
            imya = sait2kont.get(r.get('subdomain'))
            if imya:
                zhivye[imya] += 1

reg = collections.Counter()
fd = collections.Counter()
konv_saity = collections.defaultdict(set)
konv_brendy = collections.defaultdict(set)
bez_imeni = collections.Counter()
vidennye = set()
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
            imya = sait2kont.get(r.get('subdomain'))
            if not imya:
                bez_imeni[r['event']] += 1
                continue
            (reg if r['event'] == 'reg' else fd)[imya] += 1
            konv_saity[imya].add(r['subdomain'])
            konv_brendy[imya].add(sait2brend.get(r['subdomain'], '?'))

v_okne = [i for i, g in kont.items() if g['pervyy'] and ot <= g['pervyy'] <= do]
saitov = sum(kont[i]['zapushcheno'] for i in v_okne)
vsego_reg = sum(reg[i] for i in v_okne)
stavka = vsego_reg / saitov if saitov else 0

P(f'контенты с первым переобходом {ot}..{do}')
P(f'  контентов {len(v_okne)}, запущенных сайтов {saitov}, рег {vsego_reg}, '
  f'ФД {sum(fd[i] for i in v_okne)}')
P(f'  средняя отдача {stavka*1000:.2f} реги на 1000 сайтов: контент из 206 сайтов '
  f'даёт {stavka*206:.2f} реги, из 412 — {stavka*412:.2f}')
P(f'  на сайтах без имени контента (август и раньше) ещё рег {bez_imeni["reg"]}, '
  f'ФД {bez_imeni["fd"]} — в таблицу не входят')
P('')

SHAPKA = (f'  {"контент":<42} {"набор":<18} {"зона":<7} {"сайтов":>6} {"переобход":<11} '
          f'{"дом":>4} {"кликов":>8} {"живых":>7} {"рег":>4} {"ФД":>3} '
          f'{"сайтов с рег":>12} {"брендов":>8} {"ожид":>6} {"кликов/рег":>11}')


def vyshe_shuma(i):
    ozh = kont[i]['zapushcheno'] * stavka
    return reg[i] >= 3 and reg[i] > ozh + 2 * math.sqrt(ozh)


def strochka(i):
    g = kont[i]
    ozh = g['zapushcheno'] * stavka
    na_regu = f'{kliki[i]/reg[i]:.0f}' if reg[i] else '—'
    metka = ''
    if reg[i] >= 3 and len(konv_saity[i]) >= 3:
        metka = '  КОНТЕНТ'
    elif reg[i] >= 3 and len(konv_saity[i]) == 1:
        metka = f'  один сайт: {sorted(konv_saity[i])[0]}'
    elif vyshe_shuma(i):
        metka = '  выше шума'
    return (f'  {i:<42} {nabor(i):<18} {g["zony"].most_common(1)[0][0]:<7} {g["zapushcheno"]:>6} '
            f'{(g["pervyy"] or ""):<11} {len(g["domeny"]):>4} {kliki[i]:>8} {zhivye[i]:>7} '
            f'{reg[i]:>4} {fd[i]:>3} {len(konv_saity[i]):>12} {len(konv_brendy[i]):>8} '
            f'{ozh:>6.2f} {na_regu:>11}{metka}')


raznye = sorted((i for i in v_okne if reg[i] >= 3 and len(konv_saity[i]) >= 3),
                key=lambda i: (-len(konv_saity[i]), -reg[i]))
P(f'ГЛАВНОЕ — {len(raznye)} контентов, где от 3 рег пришли с трёх и более РАЗНЫХ сайтов')
P('  это и есть доказательство за контент, а не за один удачно вставший сайт')
P(SHAPKA)
for i in raznye:
    P(strochka(i))
P('')

odin = sorted((i for i in v_okne if reg[i] >= 3 and len(konv_saity[i]) == 1), key=lambda i: -reg[i])
P(f'ОБМАНКИ — {len(odin)} контентов с 3+ регами, но весь объём с ОДНОГО сайта')
P(f'  {"контент":<42} {"рег":>4} {"ФД":>3}  весь объём с')
for i in odin:
    P(f'  {i:<42} {reg[i]:>4} {fd[i]:>3}  {sorted(konv_saity[i])[0]} '
      f'({sorted(konv_brendy[i])[0]})')
P('')

P('ТОП-40 ПО ГОЛОМУ ЧИСЛУ РЕГИСТРАЦИЙ')
P(SHAPKA)
for i in sorted(v_okne, key=lambda i: (-reg[i], -fd[i], -zhivye[i]))[:40]:
    P(strochka(i))
P('')

P('ПО МЕСЯЦАМ ЗАПУСКА')
for mes, podpis in (('2026-09', 'сентябрь'), ('2026-10', 'октябрь')):
    gr = [i for i in v_okne if kont[i]['pervyy'].startswith(mes)]
    if not gr:
        continue
    s = sum(kont[i]['zapushcheno'] for i in gr)
    rg = sum(reg[i] for i in gr)
    P(f'  {podpis}: контентов {len(gr)}, сайтов {s}, рег {rg}, ФД {sum(fd[i] for i in gr)}, '
      f'отдача {rg/s*1000:.2f} на 1000 сайтов')
    P(f'    с регами {sum(1 for i in gr if reg[i])}; от 3 рег {sum(1 for i in gr if reg[i] >= 3)}; '
      f'разнесённых по 3+ сайтам {sum(1 for i in gr if reg[i] >= 3 and len(konv_saity[i]) >= 3)}')
P('')

P('НАБОРЫ — для ориентира, отбор всё равно по точным именам')
nab = collections.defaultdict(lambda: [0, 0, 0, 0])
for i in v_okne:
    g = nab[nabor(i)]
    g[0] += 1
    g[1] += kont[i]['zapushcheno']
    g[2] += reg[i]
    g[3] += fd[i]
P(f'  {"набор":<22} {"контентов":>10} {"сайтов":>8} {"рег":>5} {"ФД":>4} {"на 1000 сайтов":>15}')
for n, g in sorted(nab.items(), key=lambda kv: -kv[1][2])[:25]:
    P(f'  {n:<22} {g[0]:>10} {g[1]:>8} {g[2]:>5} {g[3]:>4} {g[2]/g[1]*1000:>15.2f}')
P('')

P(f'ВСЕ {len(v_okne)} КОНТЕНТОВ ОКНА, по убыванию рег')
P(SHAPKA)
for i in sorted(v_okne, key=lambda i: (-reg[i], -fd[i], -zhivye[i], i)):
    P(strochka(i))

if opt['out']:
    with open(opt['out'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(stroki) + '\n')
    print(f'\nзаписано: {opt["out"][0]}')
if opt['spisok']:
    otbor = raznye + [i for i in sorted(v_okne, key=lambda i: -reg[i])
                      if vyshe_shuma(i) and i not in set(raznye)]
    with open(opt['spisok'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(otbor) + '\n')
    print(f'список на выкачку: {opt["spisok"][0]} ({len(otbor)} строк)')
