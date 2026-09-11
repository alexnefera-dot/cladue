#!/usr/bin/env python3
"""Сверка нового архива с ранее разобранными: не приходил ли тот же текст в прошлых партиях.

Использование:
    python3 scripts/dedup_across.py <старый архив|папка> [ещё старые …] <новый архив>

Метод тот же, что в D2: 6-словные цепочки, выборка 1/8, шаблонные цепочки (больше чем
на 50 страницах) не считаются, совпадение — доля цепочек страницы, найденных в старом
корпусе. В выводе — таблица «сайт → с чем совпал → на сколько». Порог тот же, 60 %.
"""
import os, re, sys, zlib
from collections import defaultdict, Counter

CUT = re.compile(r'(?is)<(head|script|style|header|footer|nav)\b.*?</\1>')
TAG = re.compile(r'(?s)<[^>]+>')
СЛОВО = re.compile(r'[а-яё]+')

def цепочки(путь):
    t = TAG.sub(' ', CUT.sub(' ', open(путь, encoding='utf-8', errors='replace').read())).lower()
    сл = СЛОВО.findall(t)
    ц = {zlib.crc32(' '.join(сл[i:i + 6]).encode()) for i in range(len(сл) - 5)}
    в = {h for h in ц if h % 8 == 0}
    return в if len(в) >= 8 else ц

def страницы(корень):
    for путь, _, файлы in os.walk(корень):
        for f in файлы:
            if f.endswith('.html'):
                yield os.path.join(путь, f)

def сайт(путь, корень):
    отн = os.path.relpath(путь, корень)
    части = отн.split(os.sep)
    return '/'.join(части[:-1]) or os.path.basename(корень)

старые, новый = sys.argv[1:-1], sys.argv[-1]
индекс = defaultdict(list)      # цепочка -> [(архив, сайт, страница)]
частота = Counter()
всего = 0
for корень in старые:
    архив = os.path.basename(корень.rstrip('/'))
    for p in страницы(корень):
        ид = (архив, сайт(p, корень), os.path.basename(p)[:-5])
        ц = цепочки(p)
        всего += 1
        for h in ц:
            индекс[h].append(ид)
        частота.update(set(ц))
print('старых страниц: %d, цепочек в индексе: %d' % (всего, len(индекс)))

# шаблонные цепочки (встречаются больше чем на 50 страницах) не считаем
шаблон = {h for h, c in частота.items() if c > 50}
print('шаблонных цепочек снято: %d' % len(шаблон))

итог = {}
for p in страницы(новый):
    ц = цепочки(p) - шаблон
    if not ц:
        continue
    счёт = Counter()
    for h in ц:
        for ид in индекс.get(h, ()):
            счёт[ид] += 1
    if not счёт:
        continue
    ид, общих = счёт.most_common(1)[0]
    доля = общих / len(ц)
    с = сайт(p, новый)
    if с not in итог or доля > итог[с][0]:
        итог[с] = (доля, ид, os.path.basename(p)[:-5])

print()
print('| Сайт | Совпадение | С чем | Страница |')
print('|---|---:|---|---|')
for с, (доля, ид, стр) in sorted(итог.items(), key=lambda x: -x[1][0]):
    print('| %s | %d %% | %s/%s (%s) | %s |' % (с, round(доля * 100), ид[0], ид[1], ид[2], стр))
