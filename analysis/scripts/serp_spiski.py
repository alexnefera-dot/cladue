#!/usr/bin/env python3
"""Два списка из съёмов выдачи, объединённых и без повторов.

1. Базовые домены, под которыми в выдаче были поддомены (сетки доров).
2. Голые домены (без поддоменов), в имени которых есть имя бренда целиком
   или куском — зеркала, клоны и тематические под бренд.

    python3 -I scripts/serp_spiski.py <выход1.txt> <выход2.txt> <csv> [csv ...]
"""
import collections
import contextlib
import csv
import importlib.util
import io
import re
import sys

OUT1, OUT2 = sys.argv[1], sys.argv[2]
FAJLY = sys.argv[3:]

sys.path.insert(0, 'scripts')
sys.argv = ['serp_podtipy', FAJLY[0]]
spec = importlib.util.spec_from_file_location('sp', 'scripts/serp_podtipy.py')
with contextlib.redirect_stdout(io.StringIO()):
    sp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sp)
S = sp.S

PLOSHADKI = ('google.com', 'yandex.ru', 'apple.com', 'mail.ru', 'vk.com', 'vk.ru', 'ok.ru',
             'youtube.com', 'wikipedia.org', 'ruwiki.ru', 'archive.org', 'sports.ru', 'avito.ru',
             'rbc.ru', 'lenta.ru', 'viber.com', 'maxline.by', 'vbr.ru', 'ldplayer.net',
             'championat.com', 'kinopoisk.ru', 'pinterest.com', 'telegram.org', 'divxland.org')

bazy, brendovye = {}, {}
vsego = collections.Counter()
for put in FAJLY:
    for r in csv.DictReader(open(put, encoding='utf-8-sig'), delimiter=';'):
        h, d = r['Сайт'].lower().strip(), r['Домен'].lower().strip()
        if not h:
            continue
        vsego['строк'] += 1
        zona, imya, est_pod = S.razbor(h, d)
        baza = imya + '.' + zona
        if est_pod:
            if any(baza == p or baza.endswith('.' + p) for p in PLOSHADKI):
                vsego['площадки пропущены'] += 1
            else:
                bazy.setdefault(baza, set()).add(h)
        else:
            b = S.brend_v(re.sub(r'[^a-z0-9]', '', imya))
            if b and len(b) >= 4:
                brendovye.setdefault(baza, set()).add(b)

with open(OUT1, 'w', encoding='utf-8') as f:
    for x in sorted(bazy):
        f.write(x + '\n')
with open(OUT2, 'w', encoding='utf-8') as f:
    for x in sorted(brendovye):
        f.write(x + '\n')

print(f'файлов съёмов: {len(FAJLY)}, строк прочитано: {vsego["строк"]}')
print(f'{OUT1}: {len(bazy)} уникальных баз с поддоменами '
      f'(поддоменов под ними {sum(len(v) for v in bazy.values())})')
print(f'  пропущено как известные площадки: {vsego["площадки пропущены"]} строк')
print(f'{OUT2}: {len(brendovye)} голых доменов с именем бренда в названии')
zony1 = collections.Counter(x.rsplit('.', 1)[-1] for x in bazy)
zony2 = collections.Counter(x.rsplit('.', 1)[-1] for x in brendovye)
print(f'  зоны баз: {dict(zony1.most_common(8))}')
print(f'  зоны брендовых: {dict(zony2.most_common(8))}')
