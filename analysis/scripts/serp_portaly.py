#!/usr/bin/env python3
"""Порталы и рейтинги казино: охват брендов, места, лидерство.

Ограничение выгрузки: у крупных порталов список брендов обрезан
(видно 12 имён и счётчик «ещё N»). Само число брендов точное, имена — нет,
поэтому поимённой таблицы «бренд -> сколько порталов» здесь не будет.
Вместо неё точный срез из побрендовой выгрузки: кто лидер выдачи бренда
и какой он формат.

    python3 -I scripts/serp_portaly.py <сайты.csv> <бренды.csv> [json]
"""
import collections
import contextlib
import csv
import importlib.util
import io
import json
import sys

SAJTY, BRENDY = sys.argv[1], sys.argv[2]
JSON_OUT = sys.argv[3] if len(sys.argv) > 3 else None

sys.path.insert(0, 'scripts')
sys.argv = ['serp_podtipy', SAJTY]
spec = importlib.util.spec_from_file_location('sp', 'scripts/serp_podtipy.py')
with contextlib.redirect_stdout(io.StringIO()):
    sp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sp)

port = [r for r in sp.rows if r['_pod'] == 'Порталы и рейтинги казино']
po_hostu = {r['Сайт']: r for r in sp.rows}
br = list(csv.DictReader(open(BRENDY, encoding='utf-8-sig'), delimiter=';'))
VSEGO = len(br)


def chislo(x):
    return float((x or '0').replace(',', '.'))


def spisok(r):
    out, obrez = [], 0
    for x in (r['Бренды'] or '').split(','):
        x = x.strip()
        if not x:
            continue
        if x.startswith('…') or x.startswith('ещё'):
            obrez = int(''.join(c for c in x if c.isdigit()) or 0)
        else:
            out.append(x)
    return out, obrez


VSTR = sum(int(r['Строк выдачи'] or 0) for r in port)
VT = sum(int(r['В топ-3'] or 0) for r in port)
sajty = []
vidny_brendy = collections.defaultdict(list)
for r in sorted(port, key=lambda r: -int(r['В топ-3'] or 0)):
    bl, ob = spisok(r)
    for b in bl:
        vidny_brendy[b].append(r['Сайт'])
    sajty.append({
        'imya': r['Сайт'], 'brendov': int(r['Брендов'] or 0),
        'ohvat': round(100.0 * int(r['Брендов'] or 0) / VSEGO, 1),
        'strok': int(r['Строк выдачи'] or 0), 'top3': int(r['В топ-3'] or 0),
        'poziciya': int(r['Лучшая позиция'] or 0),
        'dolya_strok': round(100.0 * int(r['Строк выдачи'] or 0) / VSTR, 1),
        'dolya_top3': round(100.0 * int(r['В топ-3'] or 0) / VT, 1) if VT else 0.0,
        'luchshaya_dolya': chislo(r['Лучшая доля в бренде %']), 'gde': r['Где эта доля'],
        'vidno': bl, 'obrezano': ob,
    })

# лидеры выдачи брендов — это точно, хост лидера назван
lider_format = collections.Counter()
lider_sajt = collections.Counter()
portaly_lidiruyut = []
for r in br:
    h = r['Лидер']
    rr = po_hostu.get(h)
    f = rr['_pod'] if rr else 'нет в посайтовой выгрузке'
    lider_format[f] += 1
    lider_sajt[h] += 1
    if f == 'Порталы и рейтинги казино':
        portaly_lidiruyut.append({'brend': r['Бренд'], 'sajt': h,
                                  'dolya': chislo(r['Доля лидера %']),
                                  'poziciya': r['Лучшая позиция лидера'],
                                  'vsego_sajtov': int(r['Всего сайтов'] or 0)})
portaly_lidiruyut.sort(key=lambda x: -x['dolya'])

otchet = {
    'sajtov': len(sajty), 'strok': VSTR, 'top3': VT, 'brendov_vsego': VSEGO,
    'vsego_strok_vydachi': sp.VSTR, 'vsego_top3_vydachi': sp.VT,
    'dolya_strok': round(100.0 * VSTR / sp.VSTR, 1),
    'dolya_top3': round(100.0 * VT / sp.VT, 1),
    'max_ohvat': max(x['brendov'] for x in sajty),
    'max_ohvat_sajt': max(sajty, key=lambda x: x['brendov'])['imya'],
    'summa_upominaniy': sum(x['brendov'] for x in sajty),
    'na_brend': round(sum(x['brendov'] for x in sajty) / VSEGO, 1),
    'obrezano_sajtov': sum(1 for x in sajty if x['obrezano']),
    'sajty': sajty,
    'lider_format': [{'imya': k, 'n': v, 'dolya': round(100.0 * v / VSEGO, 1)}
                     for k, v in lider_format.most_common()],
    'portaly_lidiruyut': portaly_lidiruyut,
    'lider_sajt_top': [{'imya': k, 'n': v} for k, v in lider_sajt.most_common(10)],
    's_top3': sum(1 for x in sajty if x['top3']),
}

print(f'Порталов и рейтингов: {len(sajty)}; строк {VSTR} ({otchet["dolya_strok"]}% выдачи), '
      f'мест в топ-3 {VT} ({otchet["dolya_top3"]}%)')
print(f'Сайтов с местом в топ-3: {otchet["s_top3"]} из {len(sajty)}')
print(f'Крупнейший охват: {otchet["max_ohvat_sajt"]} — {otchet["max_ohvat"]} брендов из {VSEGO}')
print(f'Сумма упоминаний брендов: {otchet["summa_upominaniy"]}, то есть {otchet["na_brend"]} портала '
      f'на бренд в среднем')
print(f'У {otchet["obrezano_sajtov"]} сайтов списки брендов в выгрузке обрезаны — '
      f'поимённой таблицы по брендам не будет')
print()
print(f'{"сайт":<28} {"брендов":>7} {"охват":>6} {"строк":>6} {"% строк":>8} {"топ-3":>6} '
      f'{"% топ-3":>8} {"поз":>4} {"лучшая доля":>12} {"где"}')
for x in sajty:
    print(f'{x["imya"]:<28} {x["brendov"]:>7} {x["ohvat"]:>5}% {x["strok"]:>6} {x["dolya_strok"]:>7}% '
          f'{x["top3"]:>6} {x["dolya_top3"]:>7}% {x["poziciya"]:>4} {x["luchshaya_dolya"]:>11}% {x["gde"]}')
print()
print('Кто лидирует в выдаче брендов (формат лидера, по всем брендам):')
for x in otchet['lider_format']:
    print(f'  {x["imya"]:<36} {x["n"]:>4} брендов  {x["dolya"]:>5}%')
print()
print(f'Бренды, где лидер — портал ({len(portaly_lidiruyut)}):')
for x in portaly_lidiruyut:
    print(f'  {x["brend"]:<18} {x["sajt"]:<24} доля {x["dolya"]:>5}%  '
          f'позиция {x["poziciya"]}  сайтов у бренда {x["vsego_sajtov"]}')

if JSON_OUT:
    json.dump(otchet, open(JSON_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n-> {JSON_OUT}')
