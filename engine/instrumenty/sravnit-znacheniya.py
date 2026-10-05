# -*- coding: utf-8 -*-
"""Парное сравнение значений (не промахов) на одних сидах."""
import json, statistics, sys

ТИП = sys.argv[3] if len(sys.argv) > 3 else 'bonus'
до = {json.loads(l)['сид']: json.loads(l) for l in open(sys.argv[1])}
по = {json.loads(l)['сид']: json.loads(l) for l in open(sys.argv[2])}
общ = sorted(set(до) & set(по))
print('общих сидов: %d, тип %s' % (len(общ), ТИП))

def знак(пары):
    """Критерий знаков: сколько пар сдвинулось вверх, сколько вниз, и p."""
    from math import comb
    в = sum(1 for a, b in пары if b > a); н = sum(1 for a, b in пары if b < a)
    n = в + н
    if n == 0: return в, н, 1.0
    k = min(в, н)
    return в, н, min(1.0, sum(comb(n, i) for i in range(k + 1)) / 2 ** n * 2)

ПОЛЯ = ['words', 'paragraphs', 'words_per_para', 'water', 'nausea_acad', 'adj_pct',
        'terms_total', 'questions_total', 'faq', 'numbers_per100', 'fact_values',
        'h2', 'sections', 'lists', 'para_spread', 'honest', 'h3_question_pct', 'on_topic_pct']
print('\n%-18s %9s %9s %8s %6s %6s %8s' % ('поле', 'до', 'после', 'разн.', 'вверх', 'вниз', 'p'))
for f in ПОЛЯ:
    пары = []
    for с in общ:
        a = (до[с]['метрики'].get(ТИП) or {}).get(f)
        b = (по[с]['метрики'].get(ТИП) or {}).get(f)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)): пары.append((a, b))
    if not пары: continue
    в, н, p = знак(пары)
    ср_а = statistics.mean(a for a, _ in пары); ср_б = statistics.mean(b for _, b in пары)
    print('%-18s %9.2f %9.2f %+8.2f %6d %6d %8.2g' % (f, ср_а, ср_б, ср_б - ср_а, в, н, p))

print('\nпересечение с худшим соседом:')
пары = [((до[с]['уник'].get(ТИП) or {}).get('процент'), (по[с]['уник'].get(ТИП) or {}).get('процент'))
        for с in общ]
пары = [(a, b) for a, b in пары if a is not None and b is not None]
в, н, p = знак(пары)
порог = (до[общ[0]]['уник'].get(ТИП) or {}).get('потолок')
print('до %.2f %%, после %.2f %% (разн. %+.2f), вверх %d, вниз %d, p = %.2g, порог %.1f'
      % (statistics.mean(a for a, _ in пары), statistics.mean(b for _, b in пары),
         statistics.mean(b - a for a, b in пары), в, н, p, порог or 0))
print('выше порога: до %d из %d, после %d из %d'
      % (sum(1 for a, _ in пары if a > порог), len(пары), sum(1 for _, b in пары if b > порог), len(пары)))

print('\nпромахи страницы %s по полям:' % ТИП)
import collections
a = collections.Counter(f for с in общ for f in (до[с]['промахи'].get(ТИП) or []))
b = collections.Counter(f for с in общ for f in (по[с]['промахи'].get(ТИП) or []))
for f in sorted(set(a) | set(b), key=lambda f: -(b[f] - a[f])):
    print('  %-18s %3d → %3d  (%+d)' % (f, a[f], b[f], b[f] - a[f]))
