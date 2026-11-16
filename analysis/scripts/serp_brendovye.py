#!/usr/bin/env python3
"""Брендовые домены (зеркала и клоны): по брендам, зонам и стилю имени.

Здесь обрезка списков брендов не мешает: имя бренда стоит в самом домене,
а сайтов с несколькими брендами в формате почти нет. Доли показов считаются
по сайтам ровно с одним брендом — у них строки относятся к бренду без дележа.

    python3 -I scripts/serp_brendovye.py <сайты.csv> <бренды.csv> [json]
"""
import collections
import contextlib
import csv
import importlib.util
import io
import json
import re
import sys

SAJTY, BRENDY = sys.argv[1], sys.argv[2]
JSON_OUT = sys.argv[3] if len(sys.argv) > 3 else None

sys.path.insert(0, 'scripts')
sys.argv = ['serp_podtipy', SAJTY]
spec = importlib.util.spec_from_file_location('sp', 'scripts/serp_podtipy.py')
with contextlib.redirect_stdout(io.StringIO()):
    sp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sp)
S = sp.S

bd = [r for r in sp.rows if r['_pod'] == 'Брендовые домены (зеркала и клоны)']
br = list(csv.DictReader(open(BRENDY, encoding='utf-8-sig'), delimiter=';'))
VSEGO = len(br)
vsego_sajtov = {r['Бренд']: int(r['Всего сайтов'] or 0) for r in br}
vsego_strok = {r['Бренд']: int(r['Строк выдачи'] or 0) for r in br}
lider = {r['Бренд']: r['Лидер'] for r in br}


def norm(x):
    return re.sub(r'[^a-zа-я0-9]', '', (x or '').lower())


def spisok(r):
    out = []
    for x in (r['Бренды'] or '').split(','):
        x = x.strip()
        if x and not x.startswith('…') and not x.startswith('ещё'):
            out.append(x)
    return out


def stil(imya, b):
    """Как собрано имя домена вокруг бренда."""
    i = imya.replace('-', '').replace('.', '')
    bn = norm(b)
    hvost = i.split(bn, 1)[-1] if bn and bn in i else ''
    nachalo = i.split(bn, 1)[0] if bn and bn in i else ''
    if i == bn:
        return 'ровно имя бренда'
    if nachalo and nachalo.isdigit():
        return 'цифры + бренд'
    if hvost.isdigit() and hvost:
        return 'бренд + цифры'
    if '-' in imya and not any(c.isdigit() for c in imya):
        return 'бренд + слово через дефис'
    if any(c.isdigit() for c in imya):
        return 'бренд + слово + цифры'
    return 'бренд + слово'


VSTR = sum(int(r['Строк выдачи'] or 0) for r in bd)
VT = sum(int(r['В топ-3'] or 0) for r in bd)
po_brendu = collections.defaultdict(lambda: dict(n=0, strok=0, top3=0, odin_strok=0,
                                                 sajty=[], zony=collections.Counter()))
zony = collections.Counter()
stili = collections.Counter()
primery_stil = collections.defaultdict(list)
mnogo_brendov = 0
sajty = []
for r in sorted(bd, key=lambda r: (-int(r['В топ-3'] or 0), -int(r['Строк выдачи'] or 0))):
    bl = spisok(r)
    zona, imya, _ = S.razbor(r['Сайт'].lower(), r['Домен'].lower())
    poimeni = S.brend_v(re.sub(r'[^a-z0-9]', '', imya))
    if len(bl) == 1:
        b = bl[0]
    else:
        mnogo_brendov += 1
        b = next((x for x in bl if norm(x) and norm(x) in imya.replace('-', '')), bl[0] if bl else '')
    g = po_brendu[b]
    g['n'] += 1
    g['strok'] += int(r['Строк выдачи'] or 0)
    g['top3'] += int(r['В топ-3'] or 0)
    if len(bl) == 1:
        g['odin_strok'] += int(r['Строк выдачи'] or 0)
    g['sajty'].append(r['Сайт'])
    g['zony'][zona] += 1
    zony[zona] += 1
    st = stil(imya, b or poimeni)
    stili[st] += 1
    if len(primery_stil[st]) < 4:
        primery_stil[st].append(r['Сайт'])
    sajty.append({'imya': r['Сайт'], 'brend': b, 'zona': zona,
                  'strok': int(r['Строк выдачи'] or 0), 'top3': int(r['В топ-3'] or 0),
                  'poziciya': int(r['Лучшая позиция'] or 0),
                  'dolya_v_brende': float((r['Лучшая доля в бренде %'] or '0').replace(',', '.')),
                  'stil': st})

brendy = []
for b, g in po_brendu.items():
    vs = vsego_sajtov.get(b, 0)
    vstr = vsego_strok.get(b, 0)
    brendy.append({
        'imya': b, 'n': g['n'], 'vsego_sajtov': vs,
        'dolya_sajtov': round(100.0 * g['n'] / vs, 1) if vs else 0.0,
        'strok': g['strok'], 'odin_strok': g['odin_strok'], 'vsego_strok': vstr,
        'dolya_strok': round(100.0 * g['odin_strok'] / vstr, 1) if vstr else 0.0,
        'top3': g['top3'], 'lider_brendovyy': lider.get(b, '') in g['sajty'],
        'zona': g['zony'].most_common(1)[0][0] if g['zony'] else '',
    })
brendy.sort(key=lambda x: -x['n'])
bez = [r['Бренд'] for r in br if r['Бренд'] not in po_brendu]

otchet = {
    'sajtov': len(bd), 'strok': VSTR, 'top3': VT,
    'vsego_strok_vydachi': sp.VSTR, 'vsego_top3_vydachi': sp.VT, 'vsego_sajtov_vydachi': sp.VS,
    'dolya_sajtov': round(100.0 * len(bd) / sp.VS, 1),
    'dolya_strok': round(100.0 * VSTR / sp.VSTR, 1),
    'dolya_top3': round(100.0 * VT / sp.VT, 1),
    'brendov': len(po_brendu), 'brendov_vsego': VSEGO,
    'dolya_brendov': round(100.0 * len(po_brendu) / VSEGO, 1),
    'bez_brendovyh': bez, 'mnogo_brendov': mnogo_brendov,
    'na_brend': round(len(bd) / len(po_brendu), 1),
    's_top3': sum(1 for x in sajty if x['top3']),
    'liderov': sum(1 for x in brendy if x['lider_brendovyy']),
    'zony': [{'imya': k, 'n': v, 'dolya': round(100.0 * v / len(bd), 1)}
             for k, v in zony.most_common(12)],
    'zon_vsego': len(zony),
    'stili': [{'imya': k, 'n': v, 'dolya': round(100.0 * v / len(bd), 1),
               'primery': primery_stil[k]} for k, v in stili.most_common()],
    'brendy': brendy,
    'top_sajty': sajty[:40],
}

print(f'Брендовых доменов: {len(bd)} ({otchet["dolya_sajtov"]}% сайтов выдачи), '
      f'строк {VSTR} ({otchet["dolya_strok"]}%), мест в топ-3 {VT} ({otchet["dolya_top3"]}%)')
print(f'Место в топ-3 есть у {otchet["s_top3"]} сайтов из {len(bd)}')
print(f'Брендов покрыто: {len(po_brendu)} из {VSEGO} = {otchet["dolya_brendov"]}%, '
      f'в среднем {otchet["na_brend"]} домена на бренд')
print(f'Сайтов с несколькими брендами: {mnogo_brendov}')
print(f'Брендов без единого брендового домена: {len(bez)} — {", ".join(bez)}')
print(f'Брендов, где брендовый домен — лидер выдачи: {otchet["liderov"]}')
print()
print('ЗОНЫ')
for x in otchet['zony']:
    print(f'  .{x["imya"]:<10} {x["n"]:>5} {x["dolya"]:>5}%')
print()
print('СТИЛЬ ИМЕНИ')
for x in otchet['stili']:
    print(f'  {x["imya"]:<28} {x["n"]:>5} {x["dolya"]:>5}%   {", ".join(x["primery"][:3])}')
print()
print(f'{"бренд":<20} {"доменов":>7} {"всего сайтов":>13} {"доля сайтов":>12} {"строк":>6} '
      f'{"доля показов":>13} {"топ-3":>6} {"лидер"}')
for x in brendy[:45]:
    print(f'{x["imya"]:<20} {x["n"]:>7} {x["vsego_sajtov"]:>13} {x["dolya_sajtov"]:>11}% '
          f'{x["strok"]:>6} {x["dolya_strok"]:>12}% {x["top3"]:>6} '
          f'{"да" if x["lider_brendovyy"] else ""}')

if JSON_OUT:
    json.dump(otchet, open(JSON_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n-> {JSON_OUT}')
