#!/usr/bin/env python3
"""Каталоги APK и приложений: какие бренды они забирают и сколько.

Два источника: посайтовая выгрузка (кто есть в выдаче и под какие бренды)
и побрендовая (сколько всего сайтов в выдаче бренда). Доля считается по
сайтам — это точно; делить строки выдачи многобрендового сайта между
брендами выгрузка не позволяет, поэтому таких оценок здесь нет.

    python3 -I scripts/serp_apk.py <сайты.csv> <бренды.csv> [json]
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

apk = [r for r in sp.rows if r['_pod'] == 'Каталоги APK и приложений']
br = list(csv.DictReader(open(BRENDY, encoding='utf-8-sig'), delimiter=';'))
brend_sajtov = {r['Бренд']: int(r['Всего сайтов'] or 0) for r in br}
brend_strok = {r['Бренд']: int(r['Строк выдачи'] or 0) for r in br}
VSEGO_BRENDOV = len(br)


def spisok_brendov(r):
    out, obrez = [], 0
    for x in (r['Бренды'] or '').split(','):
        x = x.strip()
        if not x:
            continue
        if x.startswith('…') or x.startswith('ещё'):
            obrez = int(''.join(c for c in x if c.isdigit()) or 0)
            continue
        out.append(x)
    return out, obrez


sajty = []
po_brendu = collections.defaultdict(lambda: dict(sajty=[], top3=0))
ne_brend = collections.Counter()
obrezano = 0
for r in sorted(apk, key=lambda r: (-int(r['В топ-3'] or 0), -int(r['Строк выдачи'] or 0))):
    bl, ob = spisok_brendov(r)
    obrezano += ob
    nastoyashie = [b for b in bl if b in brend_sajtov]
    for b in bl:
        if b not in brend_sajtov:
            ne_brend[b] += 1
    sajty.append({
        'imya': r['Сайт'], 'brendov': int(r['Брендов'] or 0),
        'brendy': nastoyashie, 'brendy_vne': [b for b in bl if b not in brend_sajtov],
        'obrezano': ob,
        'strok': int(r['Строк выдачи'] or 0), 'top3': int(r['В топ-3'] or 0),
        'poziciya': int(r['Лучшая позиция'] or 0),
    })
    for b in nastoyashie:
        po_brendu[b]['sajty'].append(r['Сайт'])
        po_brendu[b]['top3'] += 1 if int(r['В топ-3'] or 0) else 0

VSTR = sum(x['strok'] for x in sajty)
VT = sum(x['top3'] for x in sajty)
for x in sajty:
    x['dolya_strok'] = round(100.0 * x['strok'] / VSTR, 1)
    x['dolya_top3'] = round(100.0 * x['top3'] / VT, 1) if VT else 0.0

brendy_t = []
for b, g in po_brendu.items():
    vsego = brend_sajtov.get(b, 0)
    brendy_t.append({
        'imya': b, 'apk_sajtov': len(g['sajty']), 'vsego_sajtov': vsego,
        'dolya': round(100.0 * len(g['sajty']) / vsego, 1) if vsego else 0.0,
        'strok_brenda': brend_strok.get(b, 0), 's_top3': g['top3'],
        'sajty': sorted(g['sajty']),
    })
brendy_t.sort(key=lambda x: (-x['dolya'], -x['apk_sajtov']))
# «без бренда» — это корзина ключей без бренда, а не бренд: считаем отдельно
bez = next((x for x in brendy_t if x['imya'] == 'без бренда'), None)
brendy_t = [x for x in brendy_t if x['imya'] != 'без бренда']

otchet = {
    'sajtov': len(sajty), 'strok': VSTR, 'top3': VT,
    'brendov_zatronuto': len(brendy_t), 'brendov_vsego': VSEGO_BRENDOV - 1,
    'dolya_brendov': round(100.0 * len(brendy_t) / (VSEGO_BRENDOV - 1), 1),
    'bez_brenda': bez,
    'obrezano': obrezano, 'vne_spiska': dict(ne_brend),
    'sajty': sajty, 'brendy': brendy_t,
    's_top3': sum(1 for x in sajty if x['top3']),
    'brendov_s_top3': sum(1 for x in brendy_t if x['s_top3']),
}

print(f'Каталогов APK и приложений: {len(sajty)}; строк выдачи {VSTR}, мест в топ-3 {VT}')
print(f'Брендов затронуто: {len(brendy_t)} из {VSEGO_BRENDOV} = {otchet["dolya_brendov"]}%'
      f'; из них с APK-сайтом в топ-3: {otchet["brendov_s_top3"]}')
print(f'Сайтов с местом в топ-3: {otchet["s_top3"]} из {len(sajty)}')
if obrezano:
    print(f'ВНИМАНИЕ: в выгрузке обрезаны списки брендов, не видно {obrezano} упоминаний')
if ne_brend:
    print(f'Значения вне списка брендов: {dict(ne_brend)}')
print()
print(f'{"сайт":<34} {"брендов":>7} {"строк":>6} {"% строк":>8} {"топ-3":>6} {"% топ-3":>8} {"поз":>4}  бренды')
for x in sajty:
    print(f'{x["imya"]:<34} {x["brendov"]:>7} {x["strok"]:>6} {x["dolya_strok"]:>7}% '
          f'{x["top3"]:>6} {x["dolya_top3"]:>7}% {x["poziciya"]:>4}  {", ".join(x["brendy"])}'
          + (f' (+{x["obrezano"]} не видно)' if x['obrezano'] else ''))
print()
print(f'{"бренд":<20} {"APK-сайтов":>11} {"всего сайтов":>13} {"доля":>7} {"строк бренда":>13}  сайты')
for x in brendy_t:
    print(f'{x["imya"]:<20} {x["apk_sajtov"]:>11} {x["vsego_sajtov"]:>13} {x["dolya"]:>6}% '
          f'{x["strok_brenda"]:>13}  {", ".join(x["sajty"][:4])}')

if JSON_OUT:
    json.dump(otchet, open(JSON_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n-> {JSON_OUT}')
