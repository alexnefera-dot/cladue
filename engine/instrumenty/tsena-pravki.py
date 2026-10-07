# -*- coding: utf-8 -*-
"""Цена правки по приёмке: промахи, страницы с провалом, уникальность и разбивка
по признакам. Знаковый критерий на парных сидах."""
import json, sys, statistics as st
from collections import Counter

def читать(ф):
    d = {}
    for с in open(ф, encoding='utf-8'):
        r = json.loads(с); d[r['сид']] = r
    return d

плечи = [(имя, читать(ф)) for имя, ф in zip(sys.argv[1::2], sys.argv[2::2])]
общие = sorted(set.intersection(*[set(d) for _, d in плечи]))
print('парных сидов: %d\n' % len(общие))

def знаковый(a, b):
    плюс = сум = 0
    for x, y in zip(a, b):
        if x != y: сум += 1
        if y > x: плюс += 1
    return плюс, сум

def промахов(r): return sum(len(v) for v in r['промахи'].values())
def провалов(r): return sum(1 for v in r['промахи'].values() if v)
def уник(r): return st.mean([v for v in r['уник'].values() if v is not None])
def уникмин(r): return min([v for v in r['уник'].values() if v is not None])

МЕРЫ = [('промахов', промахов), ('страниц с провалом', провалов),
        ('уник. среднее', уник), ('уник. минимум', уникмин)]
print('%-20s' % '' + ''.join('%12s' % имя for имя, _ in плечи))
for имя, f in МЕРЫ:
    print('%-20s' % имя + ''.join('%12.2f' % st.mean(f(d[с]) for с in общие) for _, d in плечи))
print()
for i in range(1, len(плечи)):
    и0, d0 = плечи[0]; и1, d1 = плечи[i]
    print('знаковый %s → %s:' % (и0, и1))
    for имя, f in МЕРЫ:
        a = [f(d0[с]) for с in общие]; b = [f(d1[с]) for с in общие]
        пл, су = знаковый(a, b)
        print('  %-20s %+7.2f  вверх %d из %d' % (имя, st.mean(b) - st.mean(a), пл, су))
    c0 = Counter(); c1 = Counter()
    for с in общие:
        for v in d0[с]['промахи'].values(): c0.update(v)
        for v in d1[с]['промахи'].values(): c1.update(v)
    сдвиги = sorted(((c1[k] - c0[k], k) for k in set(c0) | set(c1)), key=lambda x: -abs(x[0]))
    print('  признаки (всего по %d наборам): %s' % (len(общие),
          ', '.join('%s %+d (%d→%d)' % (k, d, c0[k], c1[k]) for d, k in сдвиги[:8] if d)) or '  признаки не сдвинулись')
    print()
