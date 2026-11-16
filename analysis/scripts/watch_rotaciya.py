#!/usr/bin/env python3
"""Ротация внутри бренда по построчным снимкам выдачи (watch-выгрузки).

Снимки идут с шагом 4 часа, по три в день, два дня с разницей в неделю.
Здесь видно то, чего нет в сводных выгрузках: полные url, даты регистрации
доменов (whois) и поимённый состав выдачи на каждый час.

    python3 -I scripts/watch_rotaciya.py <snapshots.json> [json]
"""
import collections
import contextlib
import datetime as dt
import io
import json
import re
import sys

VHOD = sys.argv[1]
JSON_OUT = sys.argv[2] if len(sys.argv) > 2 else None

sys.path.insert(0, 'scripts')
with contextlib.redirect_stdout(io.StringIO()):
    import serp_tipy as S

snim = json.load(open(VHOD, encoding='utf-8'))
snim.sort(key=lambda s: s['scrape'])

BRENDY = {'lilbet casino': 'Lilbet', 'casino lilbet': 'Lilbet', 'казино лилбет': 'Lilbet',
          'спейсвин казино': 'SpaceWin', 'spacewin казино': 'SpaceWin'}


def tip_hosta(host, base, brend):
    """Грубый тип по тем же правилам, что и в сводном отчёте."""
    r = {'Сайт': host, 'Домен': base, 'Брендов': '1', 'Бренды': brend}
    return S.tip(r)


def vozrast(w, kogda):
    if not w:
        return None
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', str(w))
    if not m:
        return None
    d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return (kogda - d).days


# состав выдачи на каждый снимок
sostav = []            # [(ts, brend, query, {host: pos})]
vse_hosty = {}
for s in snim:
    ts = s['scrape'][:19]
    den = dt.date(int(ts[:4]), int(ts[5:7]), int(ts[8:10]))
    for q, rows in s['queries'].items():
        b = BRENDY.get(q, q)
        m = {}
        for r in rows:
            m[r['host']] = r['pos']
            vse_hosty.setdefault(r['host'], {'base': r['base'], 'whois': r.get('whois'),
                                             'brend': b, 'vozrast': vozrast(r.get('whois'), den),
                                             'url': r['url']})
        sostav.append({'ts': ts, 'den': str(den), 'brend': b, 'query': q, 'hosty': m})

tochki = sorted({x['ts'] for x in sostav})
zaprosy = sorted({x['query'] for x in sostav})

# ротация по запросу между соседними снимками
pary = []
for q in zaprosy:
    ser = [x for x in sostav if x['query'] == q]
    ser.sort(key=lambda x: x['ts'])
    for a, b in zip(ser, ser[1:]):
        A, B = set(a['hosty']), set(b['hosty'])
        chas = (dt.datetime.fromisoformat(b['ts']) - dt.datetime.fromisoformat(a['ts'])).total_seconds() / 3600
        pary.append({'query': q, 'brend': a['brend'], 'ot': a['ts'], 'do': b['ts'],
                     'chasov': round(chas), 'bylo': len(A), 'stalo': len(B),
                     'ostalos': len(A & B), 'ushlo': len(A - B), 'prishlo': len(B - A),
                     'uderzhanie': round(100.0 * len(A & B) / len(A), 1) if A else 0,
                     'ushli': sorted(A - B), 'prishli': sorted(B - A)})

# окно 8 часов: первый и последний срез дня, и неделя
okna = []
po_dnyam = collections.defaultdict(lambda: collections.defaultdict(list))
for x in sostav:
    po_dnyam[x['query']][x['den']].append((x['ts'], set(x['hosty'])))
for q in sorted(po_dnyam):
    for den in sorted(po_dnyam[q]):
        ser = sorted(po_dnyam[q][den])
        A, B = ser[0][1], ser[-1][1]
        vse = set().union(*[z[1] for z in ser])
        okna.append({'query': q, 'brend': BRENDY.get(q, q), 'den': den, 'mest': len(A),
                     'sovpalo': len(A & B), 'smenilos': len(A - B), 'raznyh': len(vse),
                     'oborot': len(vse) - len(A)})

po_brendu_dni = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(set)))
for x in sostav:
    po_brendu_dni[x['brend']][x['den']][x['ts']] |= set(x['hosty'])
brend_okna = []
for b in sorted(po_brendu_dni):
    for den in sorted(po_brendu_dni[b]):
        ser = sorted(po_brendu_dni[b][den].items())
        A, B = ser[0][1], ser[-1][1]
        vse = set().union(*[z[1] for z in ser])
        brend_okna.append({'brend': b, 'den': den, 'pervyy': len(A), 'posledniy': len(B),
                           'sovpalo': len(A & B), 'smenilos': len(A - B), 'raznyh': len(vse)})
    dni = sorted(po_brendu_dni[b])
    p1 = set().union(*po_brendu_dni[b][dni[0]].values())
    p2 = set().union(*po_brendu_dni[b][dni[-1]].values())
    brend_okna.append({'brend': b, 'den': f'{dni[0]} → {dni[-1]}', 'pervyy': len(p1),
                       'posledniy': len(p2), 'sovpalo': len(p1 & p2),
                       'smenilos': len(p1 - p2), 'raznyh': len(p1 | p2)})

# ядро и однодневки по бренду
po_brendu = {}
for b in sorted({x['brend'] for x in sostav}):
    vstrech = collections.Counter()
    vsego_tochek = collections.Counter()
    for x in sostav:
        if x['brend'] != b:
            continue
        vsego_tochek[x['query']] += 1
        for h in x['hosty']:
            vstrech[h] += 1
    maks = max(vsego_tochek.values()) if vsego_tochek else 0
    zapr = len(vsego_tochek)
    yadro = [h for h, n in vstrech.items() if n >= maks * zapr * 0.9]
    odin = [h for h, n in vstrech.items() if n == 1]
    po_brendu[b] = {
        'hostov_vsego': len(vstrech), 'snimkov': maks, 'zaprosov': zapr,
        'yadro': sorted(yadro), 'odnodnevki': sorted(odin),
        'dolya_yadra': round(100.0 * len(yadro) / len(vstrech), 1) if vstrech else 0,
        'dolya_odnodnevok': round(100.0 * len(odin) / len(vstrech), 1) if vstrech else 0,
        'vstrechaemost': sorted(vstrech.items(), key=lambda x: -x[1]),
    }

# возраст домена против устойчивости
gruppy = collections.defaultdict(list)
for b, g in po_brendu.items():
    for h, n in g['vstrechaemost']:
        v = vse_hosty[h]['vozrast']
        if v is None:
            continue
        dolya = n / (g['snimkov'] * g['zaprosov'])
        gruppy['ядро (в 90%+ снимков)' if dolya >= 0.9 else
               'середина' if dolya >= 0.3 else 'мелькнули'].append(v)
vozrasta = []
for k in ('ядро (в 90%+ снимков)', 'середина', 'мелькнули'):
    v = sorted(gruppy[k])
    if not v:
        continue
    vozrasta.append({'imya': k, 'n': len(v), 'median': v[len(v) // 2],
                     'sredn': round(sum(v) / len(v)), 'min': v[0], 'max': v[-1],
                     'svezhih_30': sum(1 for x in v if x <= 30),
                     'dolya_svezhih': round(100.0 * sum(1 for x in v if x <= 30) / len(v), 1)})

# типы и телеграм-каналы
tipy = collections.Counter()
for h, g in vse_hosty.items():
    tipy[tip_hosta(h, g['base'], g['brend'])] += 1
kanaly = sorted({g['url'] for h, g in vse_hosty.items() if h in ('t.me', 'telegram.me')})

otchet = {
    'snimkov': len(tochki), 'tochki': tochki, 'zaprosov': len(zaprosy), 'zaprosy': zaprosy,
    'hostov': len(vse_hosty), 'brendy': po_brendu, 'pary': pary,
    'okna': okna, 'brend_okna': brend_okna,
    'sredn_mest': round(sum(x['mest'] for x in okna) / len(okna), 1),
    'sredn_smenilos': round(sum(x['smenilos'] for x in okna) / len(okna), 1),
    'sredn_raznyh': round(sum(x['raznyh'] for x in okna) / len(okna), 1),
    'vozrasta': vozrasta, 'tipy': [{'imya': k, 'n': v} for k, v in tipy.most_common()],
    'kanaly': kanaly,
}

print(f'Снимков: {len(tochki)} — {", ".join(tochki)}')
print(f'Запросов: {len(zaprosy)} ({", ".join(zaprosy)}), хостов всего: {len(vse_hosty)}')
print()
for b, g in po_brendu.items():
    print(f'{b}: хостов за всё время {g["hostov_vsego"]}, '
          f'ядро {len(g["yadro"])} ({g["dolya_yadra"]}%), '
          f'мелькнули один раз {len(g["odnodnevki"])} ({g["dolya_odnodnevok"]}%)')
    print(f'  ядро: {", ".join(g["yadro"])}')
print()
print(f'{"запрос":<18} {"от":<17} {"часов":>5} {"было":>5} {"осталось":>9} {"ушло":>5} '
      f'{"пришло":>7} {"удержание":>10}')
for x in pary:
    print(f'{x["query"]:<18} {x["ot"][5:16]:<17} {x["chasov"]:>5} {x["bylo"]:>5} {x["ostalos"]:>9} '
          f'{x["ushlo"]:>5} {x["prishlo"]:>7} {x["uderzhanie"]:>9}%')
print()
print('ОКНО 8 ЧАСОВ: сколько сайтов сменилось')
for x in okna:
    print(f'  {x["query"]:<18} {x["den"]} мест {x["mest"]:>3} совпало {x["sovpalo"]:>3} '
          f'сменилось {x["smenilos"]:>3} разных за день {x["raznyh"]:>3}')
print(f'  в среднем: мест {otchet_sredn_mest if False else round(sum(x["mest"] for x in okna)/len(okna),1)}, '
      f'сменилось {round(sum(x["smenilos"] for x in okna)/len(okna),1)}, '
      f'разных {round(sum(x["raznyh"] for x in okna)/len(okna),1)}')
print()
print('ПО БРЕНДУ ЦЕЛИКОМ')
for x in brend_okna:
    print(f'  {x["brend"]:<10} {x["den"]:<24} было {x["pervyy"]:>3} стало {x["posledniy"]:>3} '
          f'совпало {x["sovpalo"]:>3} сменилось {x["smenilos"]:>3} разных {x["raznyh"]:>3}')
print()
print('ВОЗРАСТ ДОМЕНА И УСТОЙЧИВОСТЬ (дней с регистрации на момент съёма)')
for x in vozrasta:
    print(f'  {x["imya"]:<22} хостов {x["n"]:>3}  медиана {x["median"]:>5}  средний {x["sredn"]:>5}  '
          f'моложе 30 дней {x["svezhih_30"]:>3} = {x["dolya_svezhih"]}%')
print()
print('ТИПЫ ХОСТОВ:', dict(tipy.most_common()))
print('ТЕЛЕГРАМ-КАНАЛЫ В ВЫДАЧЕ:', ', '.join(kanaly) or 'нет')

if JSON_OUT:
    json.dump(otchet, open(JSON_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n-> {JSON_OUT}')
