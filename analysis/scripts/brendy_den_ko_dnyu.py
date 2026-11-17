#!/usr/bin/env python3
"""Сравнение двух побрендовых выгрузок: что изменилось за сутки.

    python3 -I scripts/brendy_den_ko_dnyu.py <вчера.csv> <сегодня.csv> [json]
"""
import collections
import csv
import json
import sys

A = {r['Бренд']: r for r in csv.DictReader(open(sys.argv[1], encoding='utf-8-sig'), delimiter=';')}
B = {r['Бренд']: r for r in csv.DictReader(open(sys.argv[2], encoding='utf-8-sig'), delimiter=';')}
JSON_OUT = sys.argv[3] if len(sys.argv) > 3 else None
obsh = sorted(set(A) & set(B))


def f(x):
    return float((x or '0').replace(',', '.'))


def i(x):
    return int(x or 0)


smena_sajta = [k for k in obsh if A[k]['Лидер'] != B[k]['Лидер']]
smena_tipa = [k for k in obsh if A[k]['Тип лидера'] != B[k]['Тип лидера']]
nash_a = {k: f(A[k]['Наша доля %']) for k in obsh if f(A[k]['Наша доля %']) > 0}
nash_b = {k: f(B[k]['Наша доля %']) for k in obsh if f(B[k]['Наша доля %']) > 0}

sdvig_dor = sorted(((f(B[k]['Доля доров %']) - f(A[k]['Доля доров %']), k) for k in obsh),
                   key=lambda x: -abs(x[0]))
poyavilos = sum(i(B[k]['Появилось с прошлого сбора']) for k in obsh)
propalo = sum(i(B[k]['Пропало с прошлого сбора']) for k in obsh)
vsego_sajtov = sum(i(B[k]['Всего сайтов']) for k in obsh)

otchet = {
    'brendov': len(obsh),
    'sajtov_a': sum(i(A[k]['Всего сайтов']) for k in obsh), 'sajtov_b': vsego_sajtov,
    'strok_a': sum(i(A[k]['Строк выдачи']) for k in obsh),
    'strok_b': sum(i(B[k]['Строк выдачи']) for k in obsh),
    'dorov_a': sum(i(A[k]['Доров сайтов']) for k in obsh),
    'dorov_b': sum(i(B[k]['Доров сайтов']) for k in obsh),
    'nashih_dorov_a': sum(i(A[k]['Наших доров']) for k in obsh),
    'nashih_dorov_b': sum(i(B[k]['Наших доров']) for k in obsh),
    'dolya_dorov_a': round(sum(f(A[k]['Доля доров %']) for k in obsh) / len(obsh), 1),
    'dolya_dorov_b': round(sum(f(B[k]['Доля доров %']) for k in obsh) / len(obsh), 1),
    'smena_sajta': len(smena_sajta), 'smena_tipa': len(smena_tipa),
    'smena_tipa_spisok': [{'imya': k, 'bylo': A[k]['Тип лидера'], 'stalo': B[k]['Тип лидера'],
                           'lider': B[k]['Лидер']} for k in smena_tipa],
    'nashih_brendov_a': len(nash_a), 'nashih_brendov_b': len(nash_b),
    'nashi_novye': sorted(set(nash_b) - set(nash_a)),
    'nashi_ushli': sorted(set(nash_a) - set(nash_b)),
    'nashi_top': sorted(({'imya': k, 'dolya': v, 'sajt': B[k]['Наш лучший сайт'],
                          'poziciya': B[k]['Наша лучшая позиция'],
                          'dorov': i(B[k]['Наших доров'])} for k, v in nash_b.items()),
                        key=lambda x: -x['dolya'])[:20],
    'sdvigi_dorov': [{'imya': k, 'bylo': f(A[k]['Доля доров %']), 'stalo': f(B[k]['Доля доров %']),
                      'raznica': round(d, 1)} for d, k in sdvig_dor[:15]],
    'poyavilos': poyavilos, 'propalo': propalo,
    'rotaciya_na_brend': round((poyavilos + propalo) / 2 / len(obsh), 1),
    'tipy_liderov_b': dict(collections.Counter(B[k]['Тип лидера'] for k in obsh).most_common()),
}

print(f'Брендов {len(obsh)}; сайтов {otchet["sajtov_a"]} -> {otchet["sajtov_b"]}, '
      f'строк {otchet["strok_a"]} -> {otchet["strok_b"]}')
print(f'Доров сайтов {otchet["dorov_a"]} -> {otchet["dorov_b"]}, '
      f'наших доров {otchet["nashih_dorov_a"]} -> {otchet["nashih_dorov_b"]}')
print(f'Средняя доля доров в бренде {otchet["dolya_dorov_a"]}% -> {otchet["dolya_dorov_b"]}%')
print(f'Сменился лидер-сайт у {len(smena_sajta)} брендов, лидер сменил тип у {len(smena_tipa)}')
print(f'За сутки по данным выгрузки появилось {poyavilos} сайтов, пропало {propalo} — '
      f'{otchet["rotaciya_na_brend"]} на бренд')
print(f'Брендов, где мы видны: {len(nash_a)} -> {len(nash_b)}')
print(f'  пришли: {", ".join(otchet["nashi_novye"]) or "нет"}')
print(f'  ушли:   {", ".join(otchet["nashi_ushli"]) or "нет"}')
print()
print('НАШИ ЛУЧШИЕ БРЕНДЫ СЕГОДНЯ')
print(f'  {"бренд":<18} {"наша доля":>10} {"наших доров":>12} {"лучший сайт":<34} {"позиция"}')
for x in otchet['nashi_top']:
    print(f'  {x["imya"]:<18} {x["dolya"]:>9}% {x["dorov"]:>12} {x["sajt"]:<34} {x["poziciya"]}')
print()
print('САМЫЕ БОЛЬШИЕ СДВИГИ ДОЛИ ДОРОВ ЗА СУТКИ')
for x in otchet['sdvigi_dorov']:
    print(f'  {x["imya"]:<18} {x["bylo"]:>5}% -> {x["stalo"]:>5}%  ({x["raznica"]:+})')
print()
print('ЛИДЕР СМЕНИЛ ТИП')
for x in otchet['smena_tipa_spisok']:
    print(f'  {x["imya"]:<18} {x["bylo"]:<26} -> {x["stalo"]:<26} {x["lider"]}')

if JSON_OUT:
    json.dump(otchet, open(JSON_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n-> {JSON_OUT}')
