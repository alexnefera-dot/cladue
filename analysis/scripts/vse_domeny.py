#!/usr/bin/env python3
"""Сводная таблица по всем доменам: клики, регистрации, депозиты.

Домен — зарегистрированная база вида `l9g0.lol` вместе со всеми её поддоменами
`бренд.база.зона`. Базы, которых нет в реестре запусков, в таблицу тоже входят:
Analytics Export API не отдаёт ничего раньше 01.08.2026, а трафик и регистрации
с таких хостов идут под нашей меткой.

Окна разные и это важно: клики есть только за те дни, что выгружены, а
конверсии — за всю историю трекера. В таблице по столбцу на каждое окно.

    python3 vse_domeny.py --kesh api/kesh.tsv --clicks api/tracker_clicks_*.jsonl \
        --conv api/tracker_conversions_2026-08-01_2026-10-23.jsonl \
        --clicks-ot 2026-10-11 --clicks-do 2026-10-23 --out export/vse_domeny.txt
"""
import collections
import csv
import json
import sys

NASHI = {'dorgen_engine', 'dorgne_fenix'}
CENA = {'casino': 7.0, 'buzz': 3.0, 'team': 2.0, 'lol': 1.0}

opt = collections.defaultdict(list)
klyuch = None
for a in sys.argv[1:]:
    if a.startswith('--'):
        klyuch = a[2:]
    else:
        opt[klyuch].append(a)

ot, do = opt['clicks-ot'][0], opt['clicks-do'][0]
dney = (int(do[-2:]) - int(ot[-2:])) + 1

stroki = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    stroki.append(s)


# Зоны, в которых сеть вообще живёт. База вне реестра принимается только в них:
# без параметра `site=` трекер подставляет в ключ хост реферера, и туда попадают
# посадочные рекламодателя (`evaportal180.top`, `admiralx-ee.click`) и поисковики.
ZONY = {'lol', 'team', 'casino', 'buzz'}


def baza_hosta(host):
    """Хост -> зарегистрированный домен, если он похож на наш. Иначе None."""
    if host.count('.') < 2:
        return None
    b = host.split('.', 1)[1]
    return b if b.rsplit('.', 1)[-1] in ZONY else None


# 1. реестр
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


def dobavit_bazu(b):
    return dom.setdefault(b, dict(zona=b.rsplit('.', 1)[-1], poddomenov=0, zapushcheno=0,
                                  pervyy=None, posledniy=None, v_reestre=False))


# 2. клики
zhivye = collections.Counter()
vse_kliki = collections.Counter()
brend_kliki = collections.Counter()
brend_reg = collections.Counter()
brend_fd = collections.Counter()
saity_s_klikom = collections.defaultdict(set)
for put in opt['clicks']:
    with open(put, encoding='utf-8') as f:
        for stroka in f:
            r = json.loads(stroka)
            if r.get('campaign') not in NASHI:
                continue
            b = sait2dom.get(r.get('subdomain')) or baza_hosta(r.get('subdomain') or '')
            if not b:
                continue
            dobavit_bazu(b)
            vse_kliki[b] += 1
            if r.get('is_bot') or 'yandex.' not in (r.get('referer') or ''):
                continue
            zhivye[b] += 1
            saity_s_klikom[b].add(r['subdomain'])
            brend = sait2brend.get(r['subdomain'])
            if brend:
                brend_kliki[brend] += 1

# 3. конверсии
reg_vsego = collections.Counter()
fd_vsego = collections.Counter()
reg_okno = collections.Counter()
vidennye = set()
with open(opt['conv'][0], encoding='utf-8') as f:
    for stroka in f:
        r = json.loads(stroka)
        if r.get('campaign') not in NASHI:
            continue
        k = (r['clickid'], r['event'], r['at'])
        if k in vidennye:
            continue
        vidennye.add(k)
        b = sait2dom.get(r.get('subdomain')) or baza_hosta(r.get('subdomain') or '')
        if not b:
            continue
        dobavit_bazu(b)
        host = r.get('subdomain') or ''
        brend = sait2brend.get(host) or (host.split('.', 1)[0] if host.count('.') >= 2 else None)
        v_okne = ot <= r['at'][:10] <= do
        if r['event'] == 'reg':
            reg_vsego[b] += 1
            if v_okne:
                reg_okno[b] += 1
                if brend:
                    brend_reg[brend] += 1
        else:
            fd_vsego[b] += 1
            if v_okne and brend:
                brend_fd[brend] += 1

vse = sorted(dom)
P(f'клики за {ot}..{do} ({dney} сут), конверсии за всю историю трекера (01.08..23.10)')
P('живой клик = не бот, реферер Яндекса, метка dorgen_engine или dorgne_fenix')
P('')

# ТАБЛИЦА 1 — сколько у нас доменов
v_reestre = [b for b in vse if dom[b]['v_reestre']]
vne = [b for b in vse if not dom[b]['v_reestre']]
zapushchennye = [b for b in v_reestre if dom[b]['zapushcheno']]
P('ТАБЛИЦА 1. СКОЛЬКО У НАС ДОМЕНОВ')
P(f'  {"всего доменов":<46} {len(vse):>7}')
P(f'  {"  из них в реестре запусков":<46} {len(v_reestre):>7}')
P(f'  {"  из них нет в реестре (старше 01.08)":<46} {len(vne):>7}')
P(f'  {"запущено (есть сайты с переобходом)":<46} {len(zapushchennye):>7}')
P(f'  {"поддоменов всего":<46} {sum(dom[b]["poddomenov"] for b in vse):>7}')
P(f'  {"поддоменов запущено":<46} {sum(dom[b]["zapushcheno"] for b in vse):>7}')
P(f'  {f"доменов с живым кликом за {dney} сут":<46} {sum(1 for b in vse if zhivye[b]):>7}')
P(f'  {"доменов с регистрацией за всю историю":<46} {sum(1 for b in vse if reg_vsego[b]):>7}')
P(f'  {"доменов с депозитом за всю историю":<46} {sum(1 for b in vse if fd_vsego[b]):>7}')
P('')
po_zone = collections.Counter(dom[b]['zona'] for b in vse)
P(f'  {"зона":<10} {"доменов":>8} {"поддоменов":>11} {"живых кликов":>13} {"рег":>6} {"ФД":>5}')
for z, n in po_zone.most_common():
    gr = [b for b in vse if dom[b]['zona'] == z]
    P(f'  {z:<10} {n:>8} {sum(dom[b]["poddomenov"] for b in gr):>11} '
      f'{sum(zhivye[b] for b in gr):>13} {sum(reg_vsego[b] for b in gr):>6} {sum(fd_vsego[b] for b in gr):>5}')
P('')

# ТАБЛИЦА 2 — группы по кликам
P(f'ТАБЛИЦА 2. ДОМЕНЫ ПО КОЛИЧЕСТВУ ЖИВЫХ КЛИКОВ ЗА {dney} СУТОК')
GRANI = [(0, 0, '0 кликов'), (1, 9, '1-9'), (10, 49, '10-49'), (50, 199, '50-199'),
         (200, 499, '200-499'), (500, 1999, '500-1999'), (2000, 10 ** 9, '2000 и больше')]
P(f'  {"группа":<16} {"доменов":>8} {"живых кликов":>13} {"доля трафика":>13} '
  f'{"рег всего":>10} {"ФД":>5} {"рег на домен":>13} {"кликов на рег":>14}')
vsego_zh = sum(zhivye.values())
for lo, hi, imya in GRANI:
    gr = [b for b in vse if lo <= zhivye[b] <= hi]
    if not gr:
        continue
    k = sum(zhivye[b] for b in gr)
    rg = sum(reg_vsego[b] for b in gr)
    fdd = sum(fd_vsego[b] for b in gr)
    na_reg = f'{k/rg:.0f}' if rg else '—'
    P(f'  {imya:<16} {len(gr):>8} {k:>13} {k/vsego_zh:>12.1%} {rg:>10} {fdd:>5} '
      f'{rg/len(gr):>13.2f} {na_reg:>14}')
P(f'  {"ИТОГО":<16} {len(vse):>8} {vsego_zh:>13} {1:>12.0%} '
  f'{sum(reg_vsego.values()):>10} {sum(fd_vsego.values()):>5}')
P('')

# ТАБЛИЦА 3 — топ-40
P('ТАБЛИЦА 3. ТОП-40 ДОМЕНОВ ПО ЖИВЫМ КЛИКАМ')
P(f'  {"домен":<22} {"зона":<7} {"запущ":>6} {"первый переобход":<17} {"живых":>7} '
  f'{"в сутки":>8} {"всего кликов":>12} {"сайтов с кликом":>15} {"рег":>5} {"ФД":>4}')
for b in sorted(vse, key=lambda b: -zhivye[b])[:40]:
    g = dom[b]
    P(f'  {b:<22} {g["zona"]:<7} {g["zapushcheno"]:>6} {(g["pervyy"] or "нет в реестре"):<17} '
      f'{zhivye[b]:>7} {zhivye[b]/dney:>8.1f} {vse_kliki[b]:>12} {len(saity_s_klikom[b]):>15} '
      f'{reg_vsego[b]:>5} {fd_vsego[b]:>4}')
P('')

# ТАБЛИЦА 4 — все домены
P(f'ТАБЛИЦА 4. ВСЕ ДОМЕНЫ — {len(vse)} шт., по убыванию живых кликов')
P(f'  {"домен":<22} {"зона":<7} {"поддом":>6} {"запущ":>6} {"первый переобход":<17} '
  f'{"последний":<12} {"живых":>7} {"в сутки":>8} {"всего кликов":>12} '
  f'{"сайтов с кликом":>15} {"рег всего":>9} {f"рег {ot[5:]}..{do[5:]}":>14} {"ФД":>4} {"цена":>6}')
for b in sorted(vse, key=lambda b: (-zhivye[b], -reg_vsego[b], b)):
    g = dom[b]
    P(f'  {b:<22} {g["zona"]:<7} {g["poddomenov"]:>6} {g["zapushcheno"]:>6} '
      f'{(g["pervyy"] or "нет в реестре"):<17} {(g["posledniy"] or "—"):<12} '
      f'{zhivye[b]:>7} {zhivye[b]/dney:>8.1f} {vse_kliki[b]:>12} {len(saity_s_klikom[b]):>15} '
      f'{reg_vsego[b]:>9} {reg_okno[b]:>14} {fd_vsego[b]:>4} {CENA.get(g["zona"], 0):>5.0f}$')

# ТАБЛИЦА 5 — бренды в одном окне с кликами
P('')
P(f'ТАБЛИЦА 5. БРЕНДЫ — клики и регистрации в одном окне {ot}..{do}')
P('  оффер один на все бренды, значит бренд здесь — это оформление посадочной')
vk, vr = sum(brend_kliki.values()), sum(brend_reg.values())
pustye = [b for b in brend_kliki if not brend_reg[b]]
P(f'  брендов с трафиком {len(brend_kliki)}, из них без единой реги {len(pustye)}: '
  f'{sum(brend_kliki[b] for b in pustye)} кликов = '
  f'{sum(brend_kliki[b] for b in pustye)/vk:.1%} всего живого трафика')
P(f'  по сети: {vk} живых кликов на {vr} рег — {vk/vr:.0f} кликов на регу')
P('')
P(f'  {"бренд":<20} {"живых кликов":>13} {"рег":>5} {"ФД":>4} {"кликов на рег":>14}')
for b in sorted(brend_kliki, key=lambda b: -brend_kliki[b]):
    na_reg = f'{brend_kliki[b]/brend_reg[b]:.0f}' if brend_reg[b] else 'рег нет'
    P(f'  {b:<20} {brend_kliki[b]:>13} {brend_reg[b]:>5} {brend_fd[b]:>4} {na_reg:>14}')

if opt['out']:
    with open(opt['out'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(stroki) + '\n')
    print(f'\nзаписано: {opt["out"][0]}')
