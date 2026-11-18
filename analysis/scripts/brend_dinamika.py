#!/usr/bin/env python3
"""Динамика одного бренда: по дням из побрендовых выгрузок и поимённо
из двух посайтовых съёмов одного дня.

    python3 -I scripts/brend_dinamika.py <бренд> <сайты_A.csv> <сайты_B.csv> <бренды1.csv> [бренды2.csv ...]
"""
import collections
import contextlib
import csv
import importlib.util
import io
import re
import sys

BREND, PUT_A, PUT_B = sys.argv[1], sys.argv[2], sys.argv[3]
BRFILES = sys.argv[4:]
sys.path.insert(0, 'scripts')
spec = importlib.util.spec_from_file_location('sp', 'scripts/serp_podtipy.py')


def chitat(put):
    sys.argv = ['serp_podtipy', put]
    with contextlib.redirect_stdout(io.StringIO()):
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    return m


A, B = chitat(PUT_A), chitat(PUT_B)


def norm(x):
    return re.sub(r'[^a-zа-я0-9]', '', (x or '').lower())


def i(x):
    return int(x or 0)


def f(x):
    return float((x or '0').replace(',', '.'))


# по дням
print(f'=== {BREND}: по дням (побрендовые выгрузки) ===')
print(f'{"файл":<34} {"сайтов":>6} {"строк":>6} {"доров":>6} {"доля доров":>11} '
      f'{"появ":>5} {"проп":>5} {"наша доля":>10} {"наших":>6}  лидер')
stroki = []
for p in BRFILES:
    d = {norm(r['Бренд']): r for r in csv.DictReader(open(p, encoding='utf-8-sig'), delimiter=';')}
    r = d.get(norm(BREND))
    if not r:
        print(f'{p.split("/")[-1]:<34} бренд не найден')
        continue
    stroki.append(r)
    print(f'{p.split("/")[-1][-24:]:<34} {r["Всего сайтов"]:>6} {r["Строк выдачи"]:>6} '
          f'{r["Доров сайтов"]:>6} {r["Доля доров %"]:>10}% {r["Появилось с прошлого сбора"]:>5} '
          f'{r["Пропало с прошлого сбора"]:>5} {r["Наша доля %"]:>9}% {r["Наших доров"]:>6}  '
          f'{r["Лидер"]} ({r["Тип лидера"]})')
if stroki:
    print()
    print('  состав по типам (их типизация):')
    KOL = ['доры (поддомены)', 'тематические домены', 'соцсети и видео',
           'известные сайты рунета', 'прочие домены']
    print(f'  {"тип":<26} ' + ' '.join(f'{n:>8}' for n in range(1, len(stroki) + 1)))
    for k in KOL:
        print(f'  {k:<26} ' + ' '.join(f'{i(r[k]):>8}' for r in stroki))
    print(f'  {"лучший дор":<26} ' + ' '.join(f'{r["Лучший дор"] or "—":>8}' for r in stroki))

# поимённо между двумя съёмами
def sajty(sp):
    out = {}
    for r in sp.rows:
        bl = [x.strip() for x in (r['Бренды'] or '').split(',')
              if x.strip() and not x.strip().startswith(('…', 'ещё'))]
        if any(norm(x) == norm(BREND) for x in bl):
            out[r['Сайт'].lower()] = r
    return out


sa, sb = sajty(A), sajty(B)
obsh = set(sa) & set(sb)
print()
print(f'=== поимённо, два съёма одного дня ===')
print(f'сайтов: A {len(sa)}, B {len(sb)}, общих {len(obsh)}, выпало {len(sa)-len(obsh)}, '
      f'новых {len(sb)-len(obsh)}, удержание {100.0*len(obsh)/len(sa):.1f}%')
po_formatu = collections.defaultdict(lambda: dict(a=0, b=0, obsh=0))
for h, r in sa.items():
    g = po_formatu[r['_pod']]
    g['a'] += 1
    if h in sb:
        g['obsh'] += 1
for h, r in sb.items():
    po_formatu[r['_pod']]['b'] += 1
print(f'{"формат":<36} {"A":>4} {"B":>4} {"общих":>6} {"удержание":>10}')
for k, g in sorted(po_formatu.items(), key=lambda x: -x[1]['a']):
    print(f'{k:<36} {g["a"]:>4} {g["b"]:>4} {g["obsh"]:>6} '
          f'{(100.0*g["obsh"]/g["a"] if g["a"] else 0):>9.1f}%')
print()
print('выпали:')
for h in sorted(set(sa) - obsh):
    r = sa[h]
    print(f'  {h:<42} {r["_pod"]:<34} топ-3 {r["В топ-3"]:>2} поз {r["Лучшая позиция"]:>2}')
print('пришли:')
for h in sorted(set(sb) - obsh):
    r = sb[h]
    print(f'  {h:<42} {r["_pod"]:<34} топ-3 {r["В топ-3"]:>2} поз {r["Лучшая позиция"]:>2}')
