#!/usr/bin/env python3
"""Разбор доров из выдачи: зоны, стиль имён, бренды, концентрация.

Тип сайта считает serp_tipy.py, здесь берутся только «доры (поддомены)».
Пишет текстовый отчёт и JSON для html-отчёта.

Использование:
    python3 -I scripts/serp_dory_razbor.py <csv> [json-файл]
"""
import collections
import csv
import json
import re
import sys

sys.path.insert(0, 'scripts')
import serp_tipy as S                      # классификатор и словарь брендов

CSV = sys.argv[1]
JSON_OUT = sys.argv[2] if len(sys.argv) > 2 else None

rows = list(csv.DictReader(open(CSV, encoding='utf-8-sig'), delimiter=';'))
for r in rows:
    r['_tip'] = S.tip(r)
dory = [r for r in rows if r['_tip'] == 'доры (поддомены)']
VS = len(dory)


def dolya(n, vs=None):
    return round(100.0 * n / (vs or VS), 1)


def tablica(sch, vsego=None, skolko=None):
    vs = vsego or sum(sch.values())
    p = sch.most_common(skolko) if skolko else sch.most_common()
    return [{'imya': k, 'n': v, 'dolya': dolya(v, vs)} for k, v in p]


KAZINO = ('casino', 'kazino', 'casin', 'kazin', 'cas1no', 'casi')
ZERKALO = ('zerkalo', 'zercalo', 'zerkal', 'mirror', 'zerk')


def stil(imya):
    """Стиль имени базы дора."""
    ch = bool(re.search(r'\d', imya))
    bukv = re.sub(r'[^a-z]', '', imya)
    if any(k in imya for k in ZERKALO):
        return 'зеркало + цифры' if ch else 'слово «зеркало»'
    if any(k in bukv for k in KAZINO) or 'casino' in imya.replace('1', 'i').replace('0', 'o'):
        return 'казино + цифры' if ch else 'слово «казино»'
    if S.brend_v(re.sub(r'[^a-z0-9]', '', imya)):
        return 'имя бренда'
    if imya.isdigit():
        return 'только цифры'
    if ch and bukv:
        return 'буквы и цифры вперемешку'
    if '-' in imya:
        return 'слова через дефис'
    if len(bukv) <= 5:
        return 'короткий набор букв'
    return 'словарное слово или набор букв'


zony = collections.Counter()
stili = collections.Counter()
metki = collections.Counter()
brendy = collections.Counter()
bazy = collections.Counter()
nashi = collections.Counter()
dlina = collections.Counter()
top3_zona = collections.Counter()
strok_zona = collections.Counter()
for r in dory:
    h, d = r['Сайт'].lower(), r['Домен'].lower()
    zona, imya, _ = S.razbor(h, d)
    metka = h.split('.')[0]
    zony[zona] += 1
    stili[stil(imya)] += 1
    bazy[imya + '.' + zona] += 1
    nashi['наши' if r['Наш'] == 'да' else 'чужие'] += 1
    dlina[len(re.sub(r'[^a-z0-9]', '', imya))] += 1
    top3_zona[zona] += int(r['В топ-3'] or 0)
    strok_zona[zona] += int(r['Строк выдачи'] or 0)
    b = S.brend_v(re.sub(r'[^a-z0-9]', '', metka))
    if b and (metka.startswith(b) or b == metka):
        metki['точное имя бренда' if b == re.sub(r'[^a-z0-9]', '', metka)
              else 'бренд + приставка/цифры'] += 1
    elif b:
        metki['бренд внутри слова'] += 1
    else:
        metki['не бренд'] += 1
    for x in (r['Бренды'] or '').split(','):
        x = x.strip()
        if x and not x.startswith('…') and not x.startswith('ещё'):
            brendy[x] += 1

raspred = collections.Counter(bazy.values())

# примеры на каждый стиль и зону — чтобы было видно, о чём речь
primery_stil = collections.defaultdict(list)
primery_zona = collections.defaultdict(list)
for r in dory:
    h, d = r['Сайт'].lower(), r['Домен'].lower()
    zona, imya, _ = S.razbor(h, d)
    st = stil(imya)
    if len(primery_stil[st]) < 4:
        primery_stil[st].append(h)
    if len(primery_zona[zona]) < 3:
        primery_zona[zona].append(h)

# на чьей выдаче стоят доры: берём сайты ровно с одним брендом,
# у них строки выдачи относятся к этому бренду без дележа
po_brendu = collections.defaultdict(collections.Counter)
for r in rows:
    if int(r['Брендов'] or 0) != 1:
        continue
    b = (r['Бренды'] or '').strip()
    if not b:
        continue
    po_brendu[b][r['_tip']] += int(r['Строк выдачи'] or 0)
    po_brendu[b]['_vsego'] += int(r['Строк выдачи'] or 0)
dory_dolya = []
for b, c in po_brendu.items():
    if c['_vsego'] < 10:
        continue
    dory_dolya.append({'imya': b, 'strok': c['_vsego'], 'dory': c['доры (поддомены)'],
                       'dolya': round(100.0 * c['доры (поддомены)'] / c['_vsego'], 1)})
dory_dolya.sort(key=lambda x: -x['dolya'])
otchet = {
    'vsego_dorov': VS,
    'vsego_sajtov': len(rows),
    'dolya_ot_vydachi': dolya(VS, len(rows)),
    'strok': sum(int(r['Строк выдачи'] or 0) for r in dory),
    'top3': sum(int(r['В топ-3'] or 0) for r in dory),
    'bazy': len(bazy),
    'na_bazu': round(VS / len(bazy), 2),
    'zony': tablica(zony, VS, 15),
    'zony_vse': len(zony),
    'stili': tablica(stili, VS),
    'metki': tablica(metki, VS),
    'brendy': tablica(brendy, sum(brendy.values()), 25),
    'brendov_vsego': len(brendy),
    'nashi': tablica(nashi, VS),
    'top_bazy': [{'imya': k, 'n': v, 'dolya': dolya(v)} for k, v in bazy.most_common(15)],
    'raspred_baz': [{'imya': f'{k} дор' + ('' if k == 1 else 'а' if k < 5 else 'ов'),
                     'n': v, 'dolya': dolya(v, len(bazy))}
                    for k, v in sorted(raspred.items())[:10]],
    'primery_stil': {k: v for k, v in primery_stil.items()},
    'primery_zona': {k: v for k, v in primery_zona.items()},
    'brend_dory_mnogo': dory_dolya[:15],
    'brend_dory_malo': dory_dolya[-15:],
    'brendov_s_dolyami': len(dory_dolya),
    'zony_kachestvo': [{'imya': z, 'n': n, 'dolya': dolya(n),
                        'strok': strok_zona[z], 'top3': top3_zona[z],
                        'top3_na_sajt': round(top3_zona[z] / n, 2)}
                       for z, n in zony.most_common(12)],
}

print(f'Доров (поддоменов): {VS} из {len(rows)} сайтов выдачи = {otchet["dolya_ot_vydachi"]}%')
print(f'Баз под ними: {len(bazy)}, в среднем {otchet["na_bazu"]} дора на базу')
print(f'Строк выдачи {otchet["strok"]}, мест в топ-3 {otchet["top3"]}')
print()
for nazv, klyuch in (('ЗОНЫ', 'zony'), ('СТИЛЬ ИМЕНИ БАЗЫ', 'stili'),
                     ('МЕТКА ПОДДОМЕНА', 'metki'), ('ЧЬИ', 'nashi'),
                     ('ТОП-25 БРЕНДОВ', 'brendy'), ('ТОП БАЗ', 'top_bazy'),
                     ('СКОЛЬКО ДОРОВ НА БАЗЕ', 'raspred_baz')):
    print(nazv)
    for x in otchet[klyuch]:
        print(f'  {x["imya"]:<34} {x["n"]:>5}  {x["dolya"]:>5}%')
    print()
print('КАЧЕСТВО ПО ЗОНАМ')
print(f'  {"зона":<10} {"доров":>6} {"%":>6} {"строк":>7} {"топ-3":>6} {"топ-3 на дор":>13}')
for x in otchet['zony_kachestvo']:
    print(f'  {x["imya"]:<10} {x["n"]:>6} {x["dolya"]:>5}% {x["strok"]:>7} {x["top3"]:>6} '
          f'{x["top3_na_sajt"]:>13}')

if JSON_OUT:
    json.dump(otchet, open(JSON_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n-> {JSON_OUT}')
