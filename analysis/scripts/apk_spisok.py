#!/usr/bin/env python3
"""Список андроид-порталов и каталогов приложений из съёмов выдачи.

Объединение всех переданных съёмов, без повторов. Для каждого сайта —
в скольких съёмах он есть, сколько брендов покрывает, строки, топ-3,
лучшая позиция и сами бренды.

    python3 -I scripts/apk_spisok.py <выход.txt> <csv> [csv ...]
"""
import collections
import contextlib
import csv
import importlib.util
import io
import sys

VYHOD, FAJLY = sys.argv[1], sys.argv[2:]
sys.path.insert(0, 'scripts')
spec = importlib.util.spec_from_file_location('sp', 'scripts/serp_podtipy.py')

sajty = {}
for n, put in enumerate(FAJLY):
    sys.argv = ['serp_podtipy', put]
    with contextlib.redirect_stdout(io.StringIO()):
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    for r in m.rows:
        if r['_pod'] != 'Каталоги APK и приложений':
            continue
        h = r['Сайт'].lower()
        bl = [x.strip() for x in (r['Бренды'] or '').split(',')
              if x.strip() and not x.strip().startswith(('…', 'ещё'))]
        g = sajty.setdefault(h, {'syomki': set(), 'brendov': 0, 'strok': 0, 'top3': 0,
                                 'poz': 99, 'brendy': set()})
        g['syomki'].add(n)
        g['brendov'] = max(g['brendov'], int(r['Брендов'] or 0))
        g['strok'] = max(g['strok'], int(r['Строк выдачи'] or 0))
        g['top3'] = max(g['top3'], int(r['В топ-3'] or 0))
        p = int(r['Лучшая позиция'] or 99)
        g['poz'] = min(g['poz'], p if p else 99)
        g['brendy'] |= set(bl)

por = sorted(sajty.items(), key=lambda x: (-x[1]['top3'], -x[1]['brendov'], x[0]))
with open(VYHOD, 'w', encoding='utf-8') as f:
    f.write(f'# Андроид-порталы и каталоги приложений в выдаче\n')
    f.write(f'# Съёмов обработано: {len(FAJLY)}; сайтов найдено: {len(sajty)}\n#\n')
    f.write(f'{"сайт":<34} {"съёмов":>6} {"брендов":>7} {"строк":>6} {"топ-3":>6} {"поз":>4}  бренды\n')
    for h, g in por:
        f.write(f'{h:<34} {len(g["syomki"]):>6} {g["brendov"]:>7} {g["strok"]:>6} '
                f'{g["top3"]:>6} {(g["poz"] if g["poz"] < 99 else "—"):>4}  '
                f'{", ".join(sorted(g["brendy"]))}\n')
    f.write('\n# Список в столбик\n')
    for h, _ in por:
        f.write(h + '\n')

print(f'Съёмов: {len(FAJLY)}, сайтов: {len(sajty)}')
print(f'С местом в топ-3: {sum(1 for _, g in por if g["top3"])}')
print(f'Есть во всех съёмах: {sum(1 for _, g in por if len(g["syomki"]) == len(FAJLY))}')
print(f'{"сайт":<34} {"съёмов":>6} {"брендов":>7} {"строк":>6} {"топ-3":>6} {"поз":>4}')
for h, g in por:
    print(f'{h:<34} {len(g["syomki"]):>6} {g["brendov"]:>7} {g["strok"]:>6} {g["top3"]:>6} '
          f'{(g["poz"] if g["poz"] < 99 else "—"):>4}')
print(f'\n-> {VYHOD}')
