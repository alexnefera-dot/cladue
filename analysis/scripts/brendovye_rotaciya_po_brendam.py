#!/usr/bin/env python3
"""Брендовые домены: насколько меняется их набор внутри бренда.

Два съёма одного дня. «Новые» здесь — домены, которых не было в первом
съёме: это не обязательно свежая регистрация, чаще домен просто поднялся
в видимую десятку. Отличить одно от другого может только whois.

    python3 -I scripts/brendovye_rotaciya_po_brendam.py <csv A> <csv B> [json]
"""
import collections
import contextlib
import csv
import importlib.util
import io
import json
import sys

PUT_A, PUT_B = sys.argv[1], sys.argv[2]
JSON_OUT = sys.argv[3] if len(sys.argv) > 3 else None
sys.path.insert(0, 'scripts')
spec = importlib.util.spec_from_file_location('sp', 'scripts/serp_podtipy.py')


def chitat(put):
    sys.argv = ['serp_podtipy', put]
    with contextlib.redirect_stdout(io.StringIO()):
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    return m


A, B = chitat(PUT_A), chitat(PUT_B)
FORMAT = 'Брендовые домены (зеркала и клоны)'


def karta(sp):
    d = collections.defaultdict(set)
    for r in sp.rows:
        if r['_pod'] != FORMAT:
            continue
        bl = [x.strip() for x in (r['Бренды'] or '').split(',')
              if x.strip() and not x.strip().startswith(('…', 'ещё'))]
        d[bl[0] if bl else '—'].add(r['Сайт'].lower())
    return d


ka, kb = karta(A), karta(B)
brendy = []
for b in sorted(set(ka) | set(kb)):
    a, bb = ka.get(b, set()), kb.get(b, set())
    brendy.append({'imya': b, 'a': len(a), 'b': len(bb), 'obsh': len(a & bb),
                   'ushlo': len(a - bb), 'novyh': len(bb - a),
                   'obnovlenie': round(100.0 * len(bb - a) / len(bb), 1) if bb else 0.0,
                   'novye': sorted(bb - a), 'ushli': sorted(a - bb)})
brendy.sort(key=lambda x: -x['a'])
s_dom = [x for x in brendy if x['b']]
itog = {
    'a': sum(x['a'] for x in brendy), 'b': sum(x['b'] for x in brendy),
    'obsh': sum(x['obsh'] for x in brendy), 'ushlo': sum(x['ushlo'] for x in brendy),
    'novyh': sum(x['novyh'] for x in brendy), 'brendov': len(s_dom),
    'na_brend': round(sum(x['b'] for x in brendy) / len(s_dom), 1),
    'novyh_na_brend': round(sum(x['novyh'] for x in brendy) / len(s_dom), 2),
    'raspred': dict(sorted(collections.Counter(x['novyh'] for x in s_dom).items())),
    'brendy': brendy,
}
print(f'Брендовых доменов: A {itog["a"]}, B {itog["b"]}, общих {itog["obsh"]}, '
      f'выпало {itog["ushlo"]}, новых {itog["novyh"]}')
print(f'Брендов с такими доменами: {itog["brendov"]}; на бренд {itog["na_brend"]} доменов, '
      f'новых между съёмами {itog["novyh_na_brend"]}')
print(f'Сколько новых доменов пришло бренду: {itog["raspred"]}')
print()
print(f'{"бренд":<18} {"в A":>4} {"в B":>4} {"общих":>6} {"выпало":>7} {"новых":>6} {"обновление":>11}')
for x in brendy:
    if x['a'] >= 5 or x['novyh'] >= 3:
        print(f'{x["imya"]:<18} {x["a"]:>4} {x["b"]:>4} {x["obsh"]:>6} {x["ushlo"]:>7} '
              f'{x["novyh"]:>6} {x["obnovlenie"]:>10}%')
if JSON_OUT:
    json.dump(itog, open(JSON_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n-> {JSON_OUT}')
