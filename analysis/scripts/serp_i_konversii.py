#!/usr/bin/env python3
"""Проверка гипотезы: конвертят те бренды, чья выдача забрана дорами.

Логика, которую проверяем: если выдачу по бренду держат доры, туда можно
влезть — значит будут клики и реги. Если выдача занята тематическими доменами
и соцсетями, влезть нечем, и бренд молчит.

Цепочка, которую надо разделить:
    доля доров в выдаче -> наша доля и позиция -> живые клики -> реги
Корреляция первого с последним ничего не значит, если посередине рвётся.

Выгрузка SERP — данные со стороны, читаются только как данные; путь передаётся
аргументом, запускать интерпретатор из её каталога не нужно.

    python3 serp_i_konversii.py --serp <выгрузка.csv> --kesh api/kesh.tsv \
        --kesh-klikov api/kesh_klikov.tsv --conv api/tracker_conversions_*.jsonl \
        --clicks api/tracker_clicks_*.jsonl --out export/serp_i_konversii.txt
"""
import collections
import csv
import json
import math
import sys

NASHI = {'dorgen_engine', 'dorgne_fenix'}
ZONY = {'lol', 'team', 'casino', 'buzz'}

ALIASY = {
    'olimp': 'олимп', 'selector': 'селектор', 'pokerdom': 'покердом',
    'fresh': 'фреш', 'everum': 'эверум', 'lootrun': 'лутран',
    'melbet': 'мелбет', 'volna': 'волна',
    'vulkan24': 'вулкан24', 'vulkanvegas': 'вулканвегас', 'vulkanmega': 'вулканмега',
    'vulkanprestige': 'вулканпрестиж', 'vulkanrussia': 'вулканроссия',
    'vulkanstars': 'вулканстарс', 'clubvulkan': 'клубвулкан',
    # имена, которые в выгрузке выдачи длиннее реестровых
    'unlimcasino': 'unlim', 'auroracasino': 'aurora', 'mostbetbookmaker': 'mostbet',
    'vulkanprestizh': 'вулканпрестиж', 'vulkanroial': 'вулканроссия',
}

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


def kb(imya):
    k = (imya or '?').strip().lower().replace(' ', '').replace('-', '').replace('.', '')
    return ALIASY.get(k, k)


def chislo(s):
    s = (s or '').strip().replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


# 1. наши конверсии и трафик по брендам
pokaz = {}
sait2br = {}
br = collections.defaultdict(lambda: dict(saitov=0, zapushcheno=0, kliki=0, zhivye=0, reg=0, fd=0))
with open(opt['kesh'][0], encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        k = kb(r['brand'])
        pokaz[k] = (r['brand'] or '?').strip()
        sait2br[r['subdomain']] = k
        br[k]['saitov'] += 1
        if r['recrawl']:
            br[k]['zapushcheno'] += 1


def brend_hosta(host):
    if host.count('.') < 2 or host.rsplit('.', 1)[-1] not in ZONY:
        return None
    return kb(host.split('.', 1)[0])


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
            k = sait2br.get(r.get('subdomain')) or brend_hosta(r.get('subdomain') or '')
            if k:
                br[k]['zhivye'] += 1

vidennye = set()
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
            k = sait2br.get(r.get('subdomain')) or brend_hosta(r.get('subdomain') or '')
            if k:
                br[k]['reg' if r['event'] == 'reg' else 'fd'] += 1

# 2. выдача
serp = {}
with open(opt['serp'][0], encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f, delimiter=';'):
        imya = (r.get('Бренд') or '').strip()
        if not imya or imya == 'без бренда':
            continue
        serp[kb(imya)] = dict(
            imya=imya,
            chem=(r.get('Чем забран') or '').strip(),
            dolya_dorov=chislo(r.get('Доля доров %')),
            dorov=chislo(r.get('Доров сайтов')),
            vsego=chislo(r.get('Всего сайтов')),
            strok=chislo(r.get('Строк выдачи')),
            tip_lidera=(r.get('Тип лидера') or '').strip(),
            dolya_lidera=chislo(r.get('Доля лидера %')),
            nasha_dolya=chislo(r.get('Наша доля %')),
            nash_sait=(r.get('Наш лучший сайт') or '').strip(),
            nasha_poz=chislo(r.get('Наша лучшая позиция')),
            nashih_dorov=chislo(r.get('Наших доров')),
        )

obshchie = [k for k in serp if k in br and br[k]['saitov']]
P('ВЫДАЧА И НАШИ КОНВЕРСИИ')
P(f'  в выгрузке выдачи брендов {len(serp)}, у нас в реестре {sum(1 for k in br if br[k]["saitov"])}, '
  f'сошлось {len(obshchie)}')
ne_soshlis = sorted(serp[k]['imya'] for k in serp if k not in obshchie)
if ne_soshlis:
    P(f'  нет в реестре: {", ".join(ne_soshlis)}')
P('')

# 3. главный разрез: чем забрана выдача
P('ЧЕМ ЗАБРАНА ВЫДАЧА -> ЧТО МЫ С НЕЁ ПОЛУЧАЕМ')
P(f'  {"группа":<22} {"брендов":>8} {"доля доров":>11} {"наша доля":>10} {"в выдаче":>9} '
  f'{"живых кликов":>13} {"рег":>5} {"ФД":>4} {"рег на бренд":>13} {"брендов с рег":>14}')
gruppy = collections.defaultdict(list)
for k in obshchie:
    gruppy[serp[k]['chem'] or '?'].append(k)
PORYADOK = ['забран дорами', 'гибрид', 'забран не дорами']
for g in PORYADOK + [g for g in gruppy if g not in PORYADOK]:
    ks = gruppy.get(g)
    if not ks:
        continue
    dd = [serp[k]['dolya_dorov'] for k in ks if serp[k]['dolya_dorov'] is not None]
    nd = [serp[k]['nasha_dolya'] for k in ks if serp[k]['nasha_dolya'] is not None]
    v_vydache = sum(1 for k in ks if (serp[k]['nasha_dolya'] or 0) > 0)
    rg = sum(br[k]['reg'] for k in ks)
    P(f'  {g:<22} {len(ks):>8} {sum(dd)/len(dd):>10.1f}% {sum(nd)/len(nd):>9.2f}% {v_vydache:>9} '
      f'{sum(br[k]["zhivye"] for k in ks):>13} {rg:>5} {sum(br[k]["fd"] for k in ks):>4} '
      f'{rg/len(ks):>13.2f} {sum(1 for k in ks if br[k]["reg"]):>14}')
P('')

# 4. разрез по нашему присутствию в выдаче — середина цепочки
P('ЕСТЬ ЛИ МЫ В ВЫДАЧЕ -> ЧТО МЫ С НЕЁ ПОЛУЧАЕМ')
P(f'  {"группа":<28} {"брендов":>8} {"доля доров":>11} {"живых кликов":>13} '
  f'{"рег":>5} {"ФД":>4} {"рег на бренд":>13} {"брендов с рег":>14}')
for podpis, otbor in (
        ('нас нет в выдаче', lambda k: not (serp[k]['nasha_dolya'] or 0)),
        ('наша доля до 1%', lambda k: 0 < (serp[k]['nasha_dolya'] or 0) < 1),
        ('наша доля 1% и выше', lambda k: (serp[k]['nasha_dolya'] or 0) >= 1)):
    ks = [k for k in obshchie if otbor(k)]
    if not ks:
        continue
    dd = [serp[k]['dolya_dorov'] for k in ks if serp[k]['dolya_dorov'] is not None]
    rg = sum(br[k]['reg'] for k in ks)
    P(f'  {podpis:<28} {len(ks):>8} {sum(dd)/len(dd):>10.1f}% '
      f'{sum(br[k]["zhivye"] for k in ks):>13} {rg:>5} {sum(br[k]["fd"] for k in ks):>4} '
      f'{rg/len(ks):>13.2f} {sum(1 for k in ks if br[k]["reg"]):>14}')
P('')

# 5. корреляции Спирмена
def spirmen(pary):
    pary = [(a, b) for a, b in pary if a is not None and b is not None]
    n = len(pary)
    if n < 8:
        return None, n

    def ranki(xs):
        por = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        i = 0
        while i < len(por):
            j = i
            while j + 1 < len(por) and xs[por[j + 1]] == xs[por[i]]:
                j += 1
            sredniy = (i + j) / 2 + 1
            for t in range(i, j + 1):
                r[por[t]] = sredniy
            i = j + 1
        return r

    ra, rb = ranki([a for a, _ in pary]), ranki([b for _, b in pary])
    sa, sb = sum(ra) / n, sum(rb) / n
    chis = sum((x - sa) * (y - sb) for x, y in zip(ra, rb))
    zn = math.sqrt(sum((x - sa) ** 2 for x in ra) * sum((y - sb) ** 2 for y in rb))
    return (chis / zn if zn else 0.0), n


P('КОРРЕЛЯЦИИ (Спирмен, по брендам)')
pary = [
    ('доля доров в выдаче', 'реги', lambda k: (serp[k]['dolya_dorov'], br[k]['reg'])),
    ('доля доров в выдаче', 'живые клики', lambda k: (serp[k]['dolya_dorov'], br[k]['zhivye'])),
    ('доля доров в выдаче', 'наша доля в выдаче', lambda k: (serp[k]['dolya_dorov'], serp[k]['nasha_dolya'])),
    ('наша доля в выдаче', 'живые клики', lambda k: (serp[k]['nasha_dolya'], br[k]['zhivye'])),
    ('наша доля в выдаче', 'реги', lambda k: (serp[k]['nasha_dolya'], br[k]['reg'])),
    ('живые клики', 'реги', lambda k: (br[k]['zhivye'], br[k]['reg'])),
    ('клики за всю жизнь', 'реги', lambda k: (br[k]['kliki'], br[k]['reg'])),
    ('сайтов в выдаче всего', 'реги', lambda k: (serp[k]['vsego'], br[k]['reg'])),
    ('доля лидера', 'реги', lambda k: (serp[k]['dolya_lidera'], br[k]['reg'])),
]
for a, b, f in pary:
    ro, n = spirmen([f(k) for k in obshchie])
    P(f'  {a:<24} ~ {b:<22} ro = {ro:+.2f}   (n={n})' if ro is not None else f'  {a} ~ {b}: мало данных')
P('')

# 6. лидер выдачи
P('КТО ДЕРЖИТ ПЕРВОЕ МЕСТО -> ЧТО МЫ ПОЛУЧАЕМ')
P(f'  {"тип лидера":<26} {"брендов":>8} {"доля доров":>11} {"живых кликов":>13} {"рег":>5} {"ФД":>4} {"рег на бренд":>13}')
po_lideru = collections.defaultdict(list)
for k in obshchie:
    po_lideru[serp[k]['tip_lidera'] or '?'].append(k)
for t, ks in sorted(po_lideru.items(), key=lambda kv: -sum(br[k]['reg'] for k in kv[1]) / len(kv[1])):
    dd = [serp[k]['dolya_dorov'] for k in ks if serp[k]['dolya_dorov'] is not None]
    rg = sum(br[k]['reg'] for k in ks)
    P(f'  {t:<26} {len(ks):>8} {sum(dd)/len(dd):>10.1f}% {sum(br[k]["zhivye"] for k in ks):>13} '
      f'{rg:>5} {sum(br[k]["fd"] for k in ks):>4} {rg/len(ks):>13.2f}')
P('')

SHAPKA = (f'  {"бренд":<20} {"чем забран":<20} {"доля доров":>10} {"сайтов":>7} {"наша доля":>10} '
          f'{"наша поз":>9} {"наш сайт":<26} {"живых":>7} {"рег":>5} {"ФД":>4}')


def strochka(k):
    s, g = serp[k], br[k]
    return (f'  {pokaz.get(k, s["imya"]):<20} {s["chem"]:<20} '
            f'{(s["dolya_dorov"] if s["dolya_dorov"] is not None else 0):>9.1f}% {int(s["vsego"] or 0):>7} '
            f'{(s["nasha_dolya"] or 0):>9.2f}% '
            f'{(str(int(s["nasha_poz"])) if s["nasha_poz"] else "—"):>9} {(s["nash_sait"] or "—"):<26} '
            f'{g["zhivye"]:>7} {g["reg"]:>5} {g["fd"]:>4}')


P('ТОП-25 НАШИХ БРЕНДОВ ПО РЕГАМ — какая у них выдача')
P(SHAPKA)
for k in sorted(obshchie, key=lambda k: -br[k]['reg'])[:25]:
    P(strochka(k))
P('')

pustye = [k for k in obshchie if not br[k]['reg'] and not br[k]['fd']]
P(f'БРЕНДЫ БЕЗ ЕДИНОЙ КОНВЕРСИИ — {len(pustye)} шт., по убыванию доли доров в выдаче')
P(SHAPKA)
for k in sorted(pustye, key=lambda k: -(serp[k]['dolya_dorov'] or 0)):
    P(strochka(k))
P('')

P(f'ВСЕ {len(obshchie)} БРЕНДОВ, по убыванию регов')
P(SHAPKA)
for k in sorted(obshchie, key=lambda k: (-br[k]['reg'], -br[k]['fd'])):
    P(strochka(k))

if opt['out']:
    with open(opt['out'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(stroki) + '\n')
    print(f'\nзаписано: {opt["out"][0]}')
