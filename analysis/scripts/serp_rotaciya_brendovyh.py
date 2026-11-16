#!/usr/bin/env python3
"""Ротация брендовых доменов между двумя съёмами одного дня.

Сколько доменов формата дожили от съёма A до съёма B, кто выпал, кто появился,
и держится ли место в топ-3. Разрез по брендам, зонам и стилю имени.

    python3 -I scripts/serp_rotaciya_brendovyh.py <csv A> <csv B> [json]
"""
import collections
import contextlib
import csv
import importlib.util
import io
import json
import re
import sys

A_CSV, B_CSV = sys.argv[1], sys.argv[2]
JSON_OUT = sys.argv[3] if len(sys.argv) > 3 else None

sys.path.insert(0, 'scripts')
sys.argv = ['serp_podtipy', A_CSV]
spec = importlib.util.spec_from_file_location('sp', 'scripts/serp_podtipy.py')
with contextlib.redirect_stdout(io.StringIO()):
    spA = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(spA)
sys.argv = ['serp_podtipy', B_CSV]
with contextlib.redirect_stdout(io.StringIO()):
    spB = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(spB)
S = spA.S

FORMAT = 'Брендовые домены (зеркала и клоны)'


def razobrat(sp):
    out = {}
    for r in sp.rows:
        if r['_pod'] != FORMAT:
            continue
        h = r['Сайт'].lower()
        zona, imya, _ = S.razbor(h, r['Домен'].lower())
        bl = [x.strip() for x in (r['Бренды'] or '').split(',')
              if x.strip() and not x.strip().startswith(('…', 'ещё'))]
        i = imya.replace('-', '').replace('.', '')
        if i == re.sub(r'[^a-zа-я0-9]', '', (bl[0] if bl else '').lower()):
            st = 'ровно имя бренда'
        elif any(c.isdigit() for c in imya) and '-' in imya:
            st = 'бренд + слово + цифры'
        elif any(c.isdigit() for c in imya):
            st = 'бренд + цифры'
        elif '-' in imya:
            st = 'бренд + слово через дефис'
        else:
            st = 'бренд + слово'
        out[h] = {'brend': bl[0] if bl else '', 'zona': zona, 'stil': st,
                  'top3': int(r['В топ-3'] or 0), 'strok': int(r['Строк выдачи'] or 0),
                  'poziciya': int(r['Лучшая позиция'] or 0)}
    return out


A, B = razobrat(spA), razobrat(spB)
obshie = set(A) & set(B)
ushli = sorted(set(A) - set(B))
novye = sorted(set(B) - set(A))


def dolya(n, v):
    return round(100.0 * n / v, 1) if v else 0.0


# по брендам
brendy = collections.defaultdict(lambda: dict(a=0, b=0, obsh=0, ushlo=0, novyh=0,
                                              top3_a=0, top3_derzhit=0))
for h, g in A.items():
    x = brendy[g['brend']]
    x['a'] += 1
    if h in B:
        x['obsh'] += 1
    else:
        x['ushlo'] += 1
    if g['top3']:
        x['top3_a'] += 1
        if h in B and B[h]['top3']:
            x['top3_derzhit'] += 1
for h, g in B.items():
    x = brendy[g['brend']]
    x['b'] += 1
    if h not in A:
        x['novyh'] += 1
br_t = [{'imya': k or '—', **v, 'uderzhanie': dolya(v['obsh'], v['a'])}
        for k, v in brendy.items() if v['a'] >= 5]
br_t.sort(key=lambda x: x['uderzhanie'])

# по зонам и стилям
def srez(klyuch):
    sch = collections.defaultdict(lambda: dict(a=0, obsh=0))
    for h, g in A.items():
        sch[g[klyuch]]['a'] += 1
        if h in B:
            sch[g[klyuch]]['obsh'] += 1
    out = [{'imya': k, 'a': v['a'], 'obsh': v['obsh'], 'uderzhanie': dolya(v['obsh'], v['a'])}
           for k, v in sch.items() if v['a'] >= 15]
    out.sort(key=lambda x: -x['uderzhanie'])
    return out


top3_a = [h for h, g in A.items() if g['top3']]
top3_derzhit = [h for h in top3_a if h in B and B[h]['top3']]
pervoe_a = [h for h, g in A.items() if g['poziciya'] == 1]
pervoe_derzhit = [h for h in pervoe_a if h in B and B[h]['poziciya'] == 1]

otchet = {
    'a': len(A), 'b': len(B), 'obshih': len(obshie),
    'uderzhanie': dolya(len(obshie), len(A)),
    'ushli': len(ushli), 'novyh': len(novye),
    'rotaciya': dolya(len(ushli) + len(novye), len(A) + len(B)),
    'top3_a': len(top3_a), 'top3_derzhit': len(top3_derzhit),
    'top3_dolya': dolya(len(top3_derzhit), len(top3_a)),
    'pervoe_a': len(pervoe_a), 'pervoe_derzhit': len(pervoe_derzhit),
    'pervoe_dolya': dolya(len(pervoe_derzhit), len(pervoe_a)),
    'ushli_s_top3': sum(1 for h in ushli if A[h]['top3']),
    'novye_s_top3': sum(1 for h in novye if B[h]['top3']),
    'zony': srez('zona'), 'stili': srez('stil'),
    'brendy': br_t,
    'primery_ushli': [h for h in sorted(ushli, key=lambda h: -A[h]['top3'])[:15]],
    'primery_novye': [h for h in sorted(novye, key=lambda h: -B[h]['top3'])[:15]],
}

print(f'Брендовых доменов: в A {len(A)}, в B {len(B)}, в обоих {len(obshie)} — '
      f'удержание {otchet["uderzhanie"]}%')
print(f'Выпало {len(ushli)}, появилось {len(novye)}; из выпавших имели топ-3 {otchet["ushli_s_top3"]}, '
      f'из новых сразу с топ-3 {otchet["novye_s_top3"]}')
print(f'Места в топ-3: было у {len(top3_a)} доменов, сохранили {len(top3_derzhit)} = {otchet["top3_dolya"]}%')
print(f'Первая позиция: была у {len(pervoe_a)}, осталась у {len(pervoe_derzhit)} = {otchet["pervoe_dolya"]}%')
print()
print('УДЕРЖАНИЕ ПО ЗОНАМ')
for x in otchet['zony']:
    print(f'  .{x["imya"]:<10} {x["obsh"]:>4} из {x["a"]:<5} {x["uderzhanie"]:>5}%')
print()
print('УДЕРЖАНИЕ ПО СТИЛЮ ИМЕНИ')
for x in otchet['stili']:
    print(f'  {x["imya"]:<28} {x["obsh"]:>4} из {x["a"]:<5} {x["uderzhanie"]:>5}%')
print()
print(f'{"бренд":<20} {"в A":>4} {"в B":>4} {"осталось":>9} {"удержание":>10} {"выпало":>7} {"новых":>6}')
for x in br_t:
    print(f'{x["imya"]:<20} {x["a"]:>4} {x["b"]:>4} {x["obsh"]:>9} {x["uderzhanie"]:>9}% '
          f'{x["ushlo"]:>7} {x["novyh"]:>6}')
print()
print('Выпали с наибольшим числом мест в топ-3:', ', '.join(otchet['primery_ushli'][:10]))
print('Появились с наибольшим числом мест в топ-3:', ', '.join(otchet['primery_novye'][:10]))

if JSON_OUT:
    json.dump(otchet, open(JSON_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n-> {JSON_OUT}')
