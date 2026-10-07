# -*- coding: utf-8 -*-
"""Модель осевшего журнала для четырёх новых траншей.

Новым записям присваиваются номера наборов из того же распределения, что у
существующих записей прорези «пункты» того же типа: невыданное идёт вне очереди
и выше ключа «хуже», поэтому замер на свежем журнале мерит переходное
состояние, а не рычаг. Это модель для замера, в пулы она не пишется.
"""
import os, hashlib, importlib.util, json, random, sys

КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SB = os.path.dirname(os.path.abspath(__file__))
ТИПЫ = ['zerkalo', 'vhod', 'info', 'partnery']
ВХОД = sys.argv[1] if len(sys.argv) > 1 else '/tmp/vydano-model.json'
ВЫХОД = sys.argv[2] if len(sys.argv) > 2 else '/tmp/vydano-model2.json'

журнал = json.load(open(ВХОД, encoding='utf-8'))
пулы = json.load(open(КОРЕНЬ + '/engine/data-v5/pools.json', encoding='utf-8'))

владельцы = {}
for ключ, зн in журнал.items():
    части = ключ.split('|')
    if len(части) >= 4 and части[-2] == 'пункты':
        владельцы.setdefault(части[0], []).append(зн)

rng = random.Random(20261008)
добавлено = 0
for тип in ТИПЫ:
    сп = importlib.util.spec_from_file_location('o_' + тип, '%s/%s.py' % (SB, тип))
    m = importlib.util.module_from_spec(сп)
    сп.loader.exec_module(m)
    мои = {('<strong>%s:</strong> %s' % (я, т)) if в else ('%s: %s' % (я, т))
           for v in m.ПУНКТЫ.values() for я, т, в in v}
    пул = владельцы.get(тип) or ['nabor-700']
    for h2, r in пулы['разделы'][тип].items():
        for x in r['пункты']:
            т = str(x.get('т', ''))
            if т not in мои:
                continue
            ключ = '%s|%s|пункты|%s' % (тип, h2, hashlib.md5(т.encode()).hexdigest())
            if ключ in журнал:
                continue
            журнал[ключ] = rng.choice(пул)
            добавлено += 1
    print('%-9s помечено выданными: %d (пул номеров %d)' % (тип, добавлено, len(пул)))

with open(ВЫХОД, 'w', encoding='utf-8') as ф:
    json.dump(журнал, ф, ensure_ascii=False, separators=(',', ':'))
print('модель журнала: %s, ключей %d' % (ВЫХОД, len(журнал)))
