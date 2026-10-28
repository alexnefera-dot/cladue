#!/usr/bin/env python3
"""Два сбора выдачи подряд: насколько устойчива картина за сутки.

Снимок выдачи — это один день. Прежде чем объяснять им четырёхмесячную
историю конверсий, надо знать, сколько в нём шума: если бренд за сутки
переезжает из «забран дорами» в «забран не дорами», признак нестабилен и
объяснять им ничего нельзя.

    python3 serp_dva_sbora.py <вчера.csv> <сегодня.csv> [--out файл]
"""
import collections
import csv
import statistics
import sys

puti = [a for a in sys.argv[1:] if not a.startswith('--')]
out_p = None
if '--out' in sys.argv:
    out_p = sys.argv[sys.argv.index('--out') + 1]
    puti = [p for p in puti if p != out_p]

stroki = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    stroki.append(s)


def chislo(s):
    s = (s or '').strip().replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def prochitat(put):
    d = {}
    with open(put, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f, delimiter=';'):
            imya = (r.get('Бренд') or '').strip()
            if not imya or imya == 'без бренда':
                continue
            d[imya] = dict(
                chem=(r.get('Чем забран') or '').strip(),
                dd=chislo(r.get('Доля доров %')),
                dorov=chislo(r.get('Доров сайтов')),
                vsego=chislo(r.get('Всего сайтов')),
                lider=(r.get('Лидер') or '').strip(),
                tip=(r.get('Тип лидера') or '').strip(),
                nd=chislo(r.get('Наша доля %')),
                sait=(r.get('Наш лучший сайт') or '').strip(),
                poz=chislo(r.get('Наша лучшая позиция')),
            )
    return d


a, b = prochitat(puti[0]), prochitat(puti[1])
obshchie = sorted(set(a) & set(b))
P(f'сборы: {puti[0].split("/")[-1]} и {puti[1].split("/")[-1]}')
P(f'брендов в обоих: {len(obshchie)}')
P('')

smena = collections.Counter()
for k in obshchie:
    smena[(a[k]['chem'], b[k]['chem'])] += 1
P('КАК ПОМЕНЯЛАСЬ КЛАССИФИКАЦИЯ ЗА СУТКИ')
P(f'  {"было":<20} -> {"стало":<20} {"брендов":>8}')
for (x, y), n in sorted(smena.items(), key=lambda kv: -kv[1]):
    metka = '' if x == y else '   сменилось'
    P(f'  {x:<20} -> {y:<20} {n:>8}{metka}')
ustoyalo = sum(n for (x, y), n in smena.items() if x == y)
P(f'  устояло {ustoyalo} из {len(obshchie)} = {ustoyalo/len(obshchie):.0%}; '
  f'сменило группу {len(obshchie)-ustoyalo}')
P('')

delty = [b[k]['dd'] - a[k]['dd'] for k in obshchie if a[k]['dd'] is not None and b[k]['dd'] is not None]
P('ДОЛЯ ДОРОВ: НА СКОЛЬКО ПУНКТОВ СДВИНУЛАСЬ ЗА СУТКИ')
P(f'  медиана сдвига по модулю: {statistics.median(abs(d) for d in delty):.1f} пункта')
P(f'  сдвиг больше 10 пунктов: {sum(1 for d in delty if abs(d) > 10)} брендов из {len(delty)}')
P(f'  сдвиг больше 20 пунктов: {sum(1 for d in delty if abs(d) > 20)}')
P('')

P('САМЫЕ БОЛЬШИЕ СДВИГИ')
P(f'  {"бренд":<20} {"было":<20} {"стало":<20} {"доля доров":>18} {"лидер сменился":<14}')
for k in sorted(obshchie, key=lambda k: -abs((b[k]['dd'] or 0) - (a[k]['dd'] or 0)))[:18]:
    sm = 'да' if a[k]['lider'] != b[k]['lider'] else 'нет'
    P(f'  {k:<20} {a[k]["chem"]:<20} {b[k]["chem"]:<20} '
      f'{a[k]["dd"]:>7.1f}% -> {b[k]["dd"]:>6.1f}% {sm:<14}')
P('')

smenili_lidera = [k for k in obshchie if a[k]['lider'] != b[k]['lider']]
P(f'ЛИДЕР ВЫДАЧИ СМЕНИЛСЯ У {len(smenili_lidera)} БРЕНДОВ ИЗ {len(obshchie)} '
  f'({len(smenili_lidera)/len(obshchie):.0%}) ЗА ОДНИ СУТКИ')
P('')

bylo_v = [k for k in obshchie if (a[k]['nd'] or 0) > 0]
stalo_v = [k for k in obshchie if (b[k]['nd'] or 0) > 0]
P('НАШЕ ПРИСУТСТВИЕ В ВЫДАЧЕ')
P(f'  были в выдаче вчера: {len(bylo_v)}; сегодня: {len(stalo_v)}; '
  f'в обоих сборах: {len(set(bylo_v) & set(stalo_v))}')
P(f'  появились за сутки: {len(set(stalo_v) - set(bylo_v))}; пропали: {len(set(bylo_v) - set(stalo_v))}')
P('')
P(f'  {"бренд":<20} {"наша доля вчера":>16} {"сегодня":>10} {"сайт вчера":<26} {"сайт сегодня":<26}')
for k in sorted(set(bylo_v) | set(stalo_v), key=lambda k: -max(a[k]['nd'] or 0, b[k]['nd'] or 0))[:20]:
    P(f'  {k:<20} {(a[k]["nd"] or 0):>15.2f}% {(b[k]["nd"] or 0):>9.2f}% '
      f'{(a[k]["sait"] or "—"):<26} {(b[k]["sait"] or "—"):<26}')

if out_p:
    with open(out_p, 'w', encoding='utf-8') as f:
        f.write('\n'.join(stroki) + '\n')
    print(f'\nзаписано: {out_p}')
