#!/usr/bin/env python3
"""Карточка бренда: из чего состоит его выдача, кто держит, где мы.

Собирается из двух посайтовых съёмов 16.11 (A и B) и двух побрендовых
выгрузок 16 и 17.11.

    python3 -I scripts/brend_karta.py <сайты_A.csv> <сайты_B.csv> <бренды_16.csv> <бренды_17.csv> <бренд> [бренд ...]
"""
import collections
import contextlib
import csv
import importlib.util
import io
import re
import sys

PUT_A, PUT_B, BR16, BR17 = sys.argv[1:5]
NUZHNY = sys.argv[5:]
sys.path.insert(0, 'scripts')
spec = importlib.util.spec_from_file_location('sp', 'scripts/serp_podtipy.py')


def chitat(put):
    sys.argv = ['serp_podtipy', put]
    with contextlib.redirect_stdout(io.StringIO()):
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    return m


A, B = chitat(PUT_A), chitat(PUT_B)
b16 = {r['Бренд']: r for r in csv.DictReader(open(BR16, encoding='utf-8-sig'), delimiter=';')}
b17 = {r['Бренд']: r for r in csv.DictReader(open(BR17, encoding='utf-8-sig'), delimiter=';')}


def norm(x):
    return re.sub(r'[^a-zа-я0-9]', '', (x or '').lower())


imena = {norm(k): k for k in b17}
celi = []
for z in NUZHNY:
    k = imena.get(norm(z))
    if k:
        celi.append(k)
    else:
        print(f'! бренд «{z}» в выгрузке не найден')


def sajty(sp, brend):
    out = []
    for r in sp.rows:
        bl = [x.strip() for x in (r['Бренды'] or '').split(',')
              if x.strip() and not x.strip().startswith(('…', 'ещё'))]
        if brend in bl:
            out.append(r)
    return out


def f(x):
    return float((x or '0').replace(',', '.'))


def i(x):
    return int(x or 0)


for brend in celi:
    sa, sb = sajty(A, brend), sajty(B, brend)
    r16, r17 = b16.get(brend, {}), b17.get(brend, {})
    tip = collections.Counter(r['_pod'] for r in sa)
    # показы многобрендового сайта к одному бренду не отнести: его строки —
    # это сумма по всем брендам. Поэтому строки и топ-3 считаем только по
    # сайтам ровно с одним брендом, а число сайтов — по всем.
    odin = [r for r in sa if i(r['Брендов']) == 1]
    mnogo = [r for r in sa if i(r['Брендов']) > 1]
    strok = collections.Counter()
    top3 = collections.Counter()
    for r in odin:
        strok[r['_pod']] += i(r['Строк выдачи'])
        top3[r['_pod']] += i(r['В топ-3'])
    vs_strok = sum(strok.values()) or 1
    vs_top3 = sum(top3.values()) or 1
    print('=' * 78)
    print(f'{brend}  —  сайтов в выдаче {len(sa)}, строк выдачи {r17.get("Строк выдачи","—")}, '
          f'ключей {r17.get("Ключей", "—")} (по побрендовой выгрузке)')
    print(f'  строки и топ-3 ниже — только по {len(odin)} сайтам с одним брендом; '
          f'ещё {len(mnogo)} сайтов обслуживают несколько брендов'
          + (': ' + ', '.join(r['Сайт'] for r in mnogo[:6]) if mnogo else ''))
    print(f'  лидер 16.11: {r16.get("Лидер", "—")} ({r16.get("Тип лидера", "—")}, '
          f'{r16.get("Доля лидера %", "—")}%)')
    print(f'  лидер 17.11: {r17.get("Лидер", "—")} ({r17.get("Тип лидера", "—")}, '
          f'{r17.get("Доля лидера %", "—")}%)'
          + ('   ← сменился' if r16.get('Лидер') != r17.get('Лидер') else ''))
    print(f'  доля доров: {r16.get("Доля доров %", "—")}% -> {r17.get("Доля доров %", "—")}%; '
          f'сайтов всего {r16.get("Всего сайтов","—")} -> {r17.get("Всего сайтов","—")}; '
          f'появилось {r17.get("Появилось с прошлого сбора","—")}, '
          f'пропало {r17.get("Пропало с прошлого сбора","—")}')
    print(f'  мы: доля {r16.get("Наша доля %","—")}% -> {r17.get("Наша доля %","—")}%, '
          f'наших доров {r16.get("Наших доров","—")} -> {r17.get("Наших доров","—")}, '
          f'лучший {r17.get("Наш лучший сайт") or "—"} поз. {r17.get("Наша лучшая позиция") or "—"}')
    print(f'  {"формат":<36} {"сайтов":>6} {"%":>6} {"строк*":>6} {"%":>6} {"топ-3*":>6} {"%":>6}')
    for t, n in tip.most_common():
        print(f'  {t:<36} {n:>6} {100.0*n/len(sa):>5.1f}% {strok[t]:>6} '
              f'{100.0*strok[t]/vs_strok:>5.1f}% {top3[t]:>6} {100.0*top3[t]/vs_top3:>5.1f}%')
    # брендовые домены и ротация между съёмами
    F = 'Брендовые домены (зеркала и клоны)'
    da = {r['Сайт'].lower() for r in sa if r['_pod'] == F}
    db = {r['Сайт'].lower() for r in sb if r['_pod'] == F}
    print(f'  брендовых доменов: {len(da)} -> {len(db)}, общих {len(da & db)}, '
          f'выпало {len(da - db)}, новых {len(db - da)}')
    if da:
        luch = sorted((r for r in sa if r['_pod'] == F),
                      key=lambda r: -i(r['В топ-3']))[:6]
        for r in luch:
            print(f'     {r["Сайт"]:<36} строк {r["Строк выдачи"]:>3} топ-3 {r["В топ-3"]:>3} '
                  f'поз {r["Лучшая позиция"]:>2} доля в бренде {r["Лучшая доля в бренде %"]}%')
    # верх выдачи: только сайты одного бренда, у многобрендовых цифры не по нему
    print('  верх выдачи бренда (сайты с одним брендом):')
    for r in sorted(odin, key=lambda r: (-i(r['В топ-3']), i(r['Лучшая позиция'])))[:8]:
        nash = ' ← наш' if r['Наш'] == 'да' else ''
        print(f'     {r["Сайт"]:<40} {r["_pod"]:<34} топ-3 {r["В топ-3"]:>3} '
              f'поз {r["Лучшая позиция"]:>2}{nash}')
    if mnogo:
        print('  многобрендовые площадки в этой выдаче (их цифры относятся ко всем брендам '
              'сразу, не к этому):')
        print('     ' + ', '.join(f'{r["Сайт"]} ({r["Брендов"]} брендов)' for r in mnogo))
    nashi = [r for r in sa if r['Наш'] == 'да']
    if nashi:
        print(f'  наши сайты в выдаче ({len(nashi)}):')
        for r in sorted(nashi, key=lambda r: i(r['Лучшая позиция'])):
            print(f'     {r["Сайт"]:<40} поз {r["Лучшая позиция"]:>2} строк {r["Строк выдачи"]:>3} '
                  f'топ-3 {r["В топ-3"]:>3} доля {r["Лучшая доля в бренде %"]}%')
    else:
        print('  наших сайтов в выдаче нет')
    print()
