#!/usr/bin/env python3
"""Сравнение двух съёмов выдачи: что держится, что ротируется.

    python3 -I scripts/serp_sravnenie.py <csv A> <csv B> [json]

Съёмы одного дня по одним и тем же брендам. Объём (строки, топ-3) почти
совпадает, а состав сайтов — нет: это и меряем, по типам и зонам.
"""
import collections
import csv
import json
import re
import sys

sys.path.insert(0, 'scripts')
import serp_tipy as S

A = list(csv.DictReader(open(sys.argv[1], encoding='utf-8-sig'), delimiter=';'))
B = list(csv.DictReader(open(sys.argv[2], encoding='utf-8-sig'), delimiter=';'))
JSON_OUT = sys.argv[3] if len(sys.argv) > 3 else None
for R in (A, B):
    for r in R:
        r['_tip'] = S.tip(r)
ka = {r['Сайт']: r for r in A}
kb = {r['Сайт']: r for r in B}
obshie = set(ka) & set(kb)


def itogi(R):
    return dict(sajtov=len(R), strok=sum(int(r['Строк выдачи'] or 0) for r in R),
                top3=sum(int(r['В топ-3'] or 0) for r in R),
                nashi=sum(1 for r in R if r['Наш'] == 'да'))


def dolya(n, vs):
    return round(100.0 * n / vs, 1) if vs else 0.0


# 1. типы: доли и удержание
tipy = []
ta = collections.Counter(r['_tip'] for r in A)
tb = collections.Counter(r['_tip'] for r in B)
for t in sorted(set(ta) | set(tb), key=lambda x: -ta[x]):
    v_a = [h for h, r in ka.items() if r['_tip'] == t]
    ost = sum(1 for h in v_a if h in kb)
    tipy.append({'imya': t, 'a': ta[t], 'b': tb[t],
                 'dolya_a': dolya(ta[t], len(A)), 'dolya_b': dolya(tb[t], len(B)),
                 'ostalos': ost, 'uderzhanie': dolya(ost, ta[t])})

# 2. зоны доров
zony = collections.Counter()
zony_b = collections.Counter()
zony_ost = collections.Counter()
for h, r in ka.items():
    if r['_tip'] != 'доры (поддомены)':
        continue
    z = S.razbor(h, r['Домен'].lower())[0]
    zony[z] += 1
    if h in kb:
        zony_ost[z] += 1
for h, r in kb.items():
    if r['_tip'] == 'доры (поддомены)':
        zony_b[S.razbor(h, r['Домен'].lower())[0]] += 1
zony_t = [{'imya': z, 'a': n, 'b': zony_b[z], 'dolya_a': dolya(n, sum(zony.values())),
           'dolya_b': dolya(zony_b[z], sum(zony_b.values())),
           'ostalos': zony_ost[z], 'uderzhanie': dolya(zony_ost[z], n)}
          for z, n in zony.most_common(12)]

# 3. топ-3: держится ли место
top3_a = [h for h, r in ka.items() if int(r['В топ-3'] or 0) > 0]
top3_derzhit = sum(1 for h in top3_a if h in kb and int(kb[h]['В топ-3'] or 0) > 0)
top3_po_tipu = []
for t in sorted({r['_tip'] for r in A}):
    v = [h for h in top3_a if ka[h]['_tip'] == t]
    if len(v) < 10:
        continue
    d = sum(1 for h in v if h in kb and int(kb[h]['В топ-3'] or 0) > 0)
    top3_po_tipu.append({'imya': t, 'a': len(v), 'derzhit': d, 'dolya': dolya(d, len(v))})
top3_po_tipu.sort(key=lambda x: -x['dolya'])

# 4. наши
nashi_a = {h for h, r in ka.items() if r['Наш'] == 'да'}
nashi_b = {h for h, r in kb.items() if r['Наш'] == 'да'}

# 5. доля доров по брендам в обоих съёмах
def po_brendu(R):
    d = collections.defaultdict(collections.Counter)
    for r in R:
        if int(r['Брендов'] or 0) != 1:
            continue
        b = (r['Бренды'] or '').strip()
        if b:
            d[b]['vse'] += int(r['Строк выдачи'] or 0)
            if r['_tip'] == 'доры (поддомены)':
                d[b]['dory'] += int(r['Строк выдачи'] or 0)
    return {b: round(100.0 * c['dory'] / c['vse'], 1) for b, c in d.items() if c['vse'] >= 10}


pa, pb = po_brendu(A), po_brendu(B)
obshie_br = sorted(set(pa) & set(pb))
pary = [(pa[b], pb[b]) for b in obshie_br]
n = len(pary)
sr_a = sum(x for x, _ in pary) / n
sr_b = sum(y for _, y in pary) / n
cov = sum((x - sr_a) * (y - sr_b) for x, y in pary)
da = sum((x - sr_a) ** 2 for x, _ in pary) ** 0.5
db = sum((y - sr_b) ** 2 for _, y in pary) ** 0.5
korr = round(cov / (da * db), 3) if da and db else 0
sdvigi = sorted(((abs(pa[b] - pb[b]), b, pa[b], pb[b]) for b in obshie_br), reverse=True)

otchet = {
    'a': itogi(A), 'b': itogi(B),
    'obshih': len(obshie), 'tolko_a': len(ka) - len(obshie), 'tolko_b': len(kb) - len(obshie),
    'dolya_obshih_a': dolya(len(obshie), len(ka)), 'dolya_obshih_b': dolya(len(obshie), len(kb)),
    'tipy': tipy, 'zony': zony_t,
    'top3_a': len(top3_a), 'top3_derzhit': top3_derzhit,
    'top3_dolya': dolya(top3_derzhit, len(top3_a)), 'top3_po_tipu': top3_po_tipu,
    'nashi_a': len(nashi_a), 'nashi_b': len(nashi_b),
    'nashi_ostalis': len(nashi_a & nashi_b), 'nashi_ushli': sorted(nashi_a - nashi_b),
    'nashi_novye': sorted(nashi_b - nashi_a),
    'brendov': n, 'korrelyaciya': korr,
    'sredn_dolya_a': round(sr_a, 1), 'sredn_dolya_b': round(sr_b, 1),
    'sdvigi': [{'imya': b, 'a': x, 'b': y, 'raznica': round(y - x, 1)} for _, b, x, y in sdvigi[:12]],
    'sredn_sdvig': round(sum(d for d, _, _, _ in sdvigi) / n, 1),
}

print(f"Съём A: {otchet['a']['sajtov']} сайтов, {otchet['a']['strok']} строк, "
      f"{otchet['a']['top3']} мест в топ-3, наших {otchet['a']['nashi']}")
print(f"Съём B: {otchet['b']['sajtov']} сайтов, {otchet['b']['strok']} строк, "
      f"{otchet['b']['top3']} мест в топ-3, наших {otchet['b']['nashi']}")
print(f"Общих сайтов {otchet['obshih']} = {otchet['dolya_obshih_a']}% от A; "
      f"только в A {otchet['tolko_a']}, только в B {otchet['tolko_b']}")
print()
print(f'{"тип":<36} {"A":>5} {"B":>5} {"%A":>6} {"%B":>6} {"осталось":>9} {"удержание":>10}')
for x in tipy:
    print(f'{x["imya"]:<36} {x["a"]:>5} {x["b"]:>5} {x["dolya_a"]:>5}% {x["dolya_b"]:>5}% '
          f'{x["ostalos"]:>9} {x["uderzhanie"]:>9}%')
print()
print(f'Топ-3: сайтов с местом в A {otchet["top3_a"]}, сохранили место в B '
      f'{otchet["top3_derzhit"]} = {otchet["top3_dolya"]}%')
for x in top3_po_tipu:
    print(f'  {x["imya"]:<36} {x["derzhit"]:>4} из {x["a"]:<5} {x["dolya"]:>5}%')
print()
print(f'Зоны доров:')
for x in zony_t:
    print(f'  .{x["imya"]:<9} A {x["a"]:>5} B {x["b"]:>5}  {x["dolya_a"]:>5}% -> {x["dolya_b"]:>5}%  '
          f'удержание {x["uderzhanie"]:>5}%')
print()
print(f'Наши: A {otchet["nashi_a"]}, B {otchet["nashi_b"]}, в обоих {otchet["nashi_ostalis"]}')
print('  ушли:', ', '.join(otchet['nashi_ushli']) or 'нет')
print('  новые:', ', '.join(otchet['nashi_novye']) or 'нет')
print()
print(f'Доля доров по брендам: корреляция между съёмами {otchet["korrelyaciya"]}, '
      f'средняя {otchet["sredn_dolya_a"]}% -> {otchet["sredn_dolya_b"]}%, '
      f'средний сдвиг {otchet["sredn_sdvig"]} п.п. по {n} брендам')
for x in otchet['sdvigi'][:8]:
    print(f'  {x["imya"]:<18} {x["a"]:>5}% -> {x["b"]:>5}%  ({x["raznica"]:+})')

if JSON_OUT:
    json.dump(otchet, open(JSON_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n-> {JSON_OUT}')
