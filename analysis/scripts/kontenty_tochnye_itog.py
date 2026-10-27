#!/usr/bin/env python3
"""Точные контенты сентября-октября по регистрациям: что именно выкачивать и разбирать.

Контент здесь — полное имя из `content_label` вида
`content-2026-09-16-7str-oform-2_48`, а не набор `7str`: число в конце и есть
номер экземпляра. Один контент занимает примерно один домен (медиана 206
сайтов), поэтому сравнение контентов — это во многом сравнение доменов, и на
хвосте таблицы сидит шум. Чтобы его отделить, рядом с фактом стоит ожидание:
сколько регистраций дал бы контент такого размера при средней по сети отдаче,
и превышает ли факт ожидание больше чем на два корня (грубый порог Пуассона).

Клики берутся из реестра (`clicks_sum`) — это весь трафик сайта с ботами, зато
за всю его жизнь. Живые поисковые клики есть только за дни, что выгружены из
трекера, и стоят отдельной колонкой.

    python3 kontenty_tochnye_itog.py --reestr api/dorgen_subdomains_*.jsonl \
        --conv api/tracker_conversions_*.jsonl --clicks api/tracker_clicks_*.jsonl \
        --ot 2026-09-01 --do 2026-10-27 --out export/kontenty_tochnye.txt
"""
import collections
import json
import math
import sys

NASHI = {'dorgen_engine', 'dorgne_fenix'}
ZONY = {'lol', 'team', 'casino', 'buzz'}

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


def nabor(imya):
    """Контент -> набор: `content-2026-09-16-7str-oform-2_48` -> `7str-oform-2`."""
    telo = imya[len('content-'):] if imya.startswith('content-') else imya
    telo = telo.rsplit('_', 1)[0]
    chasti = telo.split('-')
    while chasti and (chasti[0].isdigit() or len(chasti[0]) == 4 and chasti[0].isdigit()):
        chasti.pop(0)
    return '-'.join(chasti) or telo


# 1. реестр: контент -> сайты, переобход, зоны, домены, клики
kont = collections.defaultdict(lambda: dict(
    saitov=0, zapushcheno=0, pervyy=None, posledniy=None, zony=collections.Counter(),
    domeny=set(), kliki=0, s_klikom=0, shablon=collections.Counter(), stranic=collections.Counter()))
sait2kont = {}
for put in opt['reestr']:
    with open(put, encoding='utf-8') as f:
        for stroka in f:
            r = json.loads(stroka)
            imya = r.get('content_label')
            if not imya:
                continue
            g = kont[imya]
            g['saitov'] += 1
            sait2kont[r['subdomain']] = imya
            g['zony'][r.get('tld') or '?'] += 1
            g['domeny'].add(r.get('content_domain_url'))
            g['kliki'] += r.get('clicks_sum') or 0
            if r.get('first_click_at'):
                g['s_klikom'] += 1
            if r.get('template'):
                g['shablon'][r['template']] += 1
            if r.get('pages_count'):
                g['stranic'][r['pages_count']] += 1
            d = (r.get('recrawl_sent_at') or '')[:10]
            if not d:
                continue
            g['zapushcheno'] += 1
            if not g['pervyy'] or d < g['pervyy']:
                g['pervyy'] = d
            if not g['posledniy'] or d > g['posledniy']:
                g['posledniy'] = d

# 2. живые поисковые клики за выгруженные дни
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

# 3. конверсии за всю историю
reg = collections.Counter()
fd = collections.Counter()
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
            if imya:
                (reg if r['event'] == 'reg' else fd)[imya] += 1
            else:
                bez_imeni[r['event']] += 1

# 4. отбор окна запуска
v_okne = [i for i, g in kont.items() if g['pervyy'] and ot <= g['pervyy'] <= do]
saitov = sum(kont[i]['zapushcheno'] for i in v_okne)
vsego_reg = sum(reg[i] for i in v_okne)
stavka = vsego_reg / saitov if saitov else 0

P(f'контенты с первым переобходом {ot}..{do}')
P(f'  контентов {len(v_okne)}, запущенных сайтов {saitov}, регистраций {vsego_reg}, '
  f'ФД {sum(fd[i] for i in v_okne)}')
P(f'  средняя отдача: {stavka*1000:.2f} реги на 1000 сайтов — '
  f'контент медианного размера (206 сайтов) даёт {stavka*206:.2f} реги')
P(f'  конверсий на сайтах без имени контента (август и раньше): '
  f'рег {bez_imeni["reg"]}, ФД {bez_imeni["fd"]} — в таблицу не попадают')
P('')


def strochka(i):
    g = kont[i]
    ozhid = g['zapushcheno'] * stavka
    porog = ozhid + 2 * math.sqrt(ozhid) if ozhid else 0
    flag = '  ВЫШЕ ШУМА' if reg[i] > porog and reg[i] >= 3 else ''
    zona = g['zony'].most_common(1)[0][0]
    na_regu = f'{g["kliki"]/reg[i]:.0f}' if reg[i] else '—'
    return (f'  {i:<42} {nabor(i):<20} {zona:<7} {g["zapushcheno"]:>5} '
            f'{(g["pervyy"] or ""):<11} {len(g["domeny"]):>4} {g["kliki"]:>9} {zhivye[i]:>8} '
            f'{reg[i]:>4} {fd[i]:>3} {ozhid:>7.2f} {na_regu:>9}{flag}')


SHAPKA = (f'  {"контент":<42} {"набор":<20} {"зона":<7} {"сайтов":>5} '
          f'{"переобход":<11} {"дом":>4} {"кликов":>9} {"живых":>8} '
          f'{"рег":>4} {"ФД":>3} {"ожид":>7} {"кликов/рег":>9}')

P('ТОП-40 ПО РЕГИСТРАЦИЯМ')
P(SHAPKA)
for i in sorted(v_okne, key=lambda i: (-reg[i], -fd[i], -zhivye[i]))[:40]:
    P(strochka(i))
P('')

luchshie = [i for i in v_okne
            if reg[i] >= 3 and reg[i] > kont[i]['zapushcheno'] * stavka + 2 * math.sqrt(kont[i]['zapushcheno'] * stavka)]
P(f'ВЫШЕ ШУМА — {len(luchshie)} контентов: от 3 рег и факт выше ожидания на два корня')
P(SHAPKA)
for i in sorted(luchshie, key=lambda i: -reg[i]):
    P(strochka(i))
P('')

P('ТО ЖЕ ПО МЕСЯЦАМ ЗАПУСКА')
for mes, podpis in (('2026-09', 'сентябрь'), ('2026-10', 'октябрь')):
    gr = [i for i in v_okne if kont[i]['pervyy'].startswith(mes)]
    if not gr:
        continue
    s = sum(kont[i]['zapushcheno'] for i in gr)
    rg = sum(reg[i] for i in gr)
    P(f'  {podpis}: контентов {len(gr)}, сайтов {s}, рег {rg}, ФД {sum(fd[i] for i in gr)}, '
      f'отдача {rg/s*1000:.2f} на 1000 сайтов')
    P(f'    с регами {sum(1 for i in gr if reg[i])}, из них от 3 рег — {sum(1 for i in gr if reg[i] >= 3)}')
P('')

P(f'ВСЕ {len(v_okne)} КОНТЕНТОВ ОКНА, по убыванию регистраций')
P(SHAPKA)
for i in sorted(v_okne, key=lambda i: (-reg[i], -fd[i], -zhivye[i], i)):
    P(strochka(i))

if opt['out']:
    with open(opt['out'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(stroki) + '\n')
    print(f'\nзаписано: {opt["out"][0]}')
if opt['spisok']:
    with open(opt['spisok'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(sorted(luchshie, key=lambda i: -reg[i])) + '\n')
    print(f'список лучших: {opt["spisok"][0]} ({len(luchshie)} строк)')
