#!/usr/bin/env python3
"""Ротация сайтов по типам между двумя посайтовыми съёмами.

Считает удержание и по типизации парсера (колонка «Тип»), и по разбору
на 19 форматов — так видно, из чего на самом деле состоит каждая корзина.

    python3 -I scripts/rotaciya_po_tipam.py <csv A> <csv B>
"""
import collections
import contextlib
import importlib.util
import io
import sys

PUT_A, PUT_B = sys.argv[1], sys.argv[2]
sys.path.insert(0, 'scripts')
spec = importlib.util.spec_from_file_location('sp', 'scripts/serp_podtipy.py')


def chitat(put):
    sys.argv = ['serp_podtipy', put]
    with contextlib.redirect_stdout(io.StringIO()):
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    return m


A, B = chitat(PUT_A), chitat(PUT_B)


def srez(znach, pole):
    a = {r['Сайт'].lower() for r in A.rows if r[pole] == znach}
    b = {r['Сайт'].lower() for r in B.rows if r[pole] == znach}
    if not a:
        return
    print(f'{znach:<42} A {len(a):>5} B {len(b):>5} общих {len(a & b):>5} '
          f'выпало {len(a - b):>4} новых {len(b - a):>4} '
          f'удержание {100.0 * len(a & b) / len(a):.1f}%')


print('ПО ТИПИЗАЦИИ ПАРСЕРА (колонка «Тип»)')
for t in sorted({r['Тип'] for r in A.rows}, key=lambda t: -sum(1 for r in A.rows if r['Тип'] == t)):
    srez(t, 'Тип')
print()
print('ПО РАЗБОРУ НА ФОРМАТЫ')
for t in sorted({r['_pod'] for r in A.rows}, key=lambda t: -sum(1 for r in A.rows if r['_pod'] == t)):
    srez(t, '_pod')
print()
for t in sorted({r['Тип'] for r in A.rows}):
    sost = collections.Counter(r['_pod'] for r in A.rows if r['Тип'] == t)
    print(f'«{t}» состоит из: ' + ', '.join(f'{k} {v}' for k, v in sost.most_common(6)))
