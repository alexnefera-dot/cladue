# -*- coding: utf-8 -*-
import json, sys, collections
sys.path.insert(0, '/tmp/p27/legendy')
from l3 import LEG3
from l4 import LEG4
from l5 import LEG5
from l6 import LEG6
from l7 import LEG7

путь = '/home/user/cladue/engine/data-v5/pools.json'
p = json.load(open(путь, encoding='utf-8'))
легенды = p['общие']['легенды']

# чужие маркеры уже занятых легенд — не дублировать
занято = set()
for v in легенды.values():
    занято.update(v['слова'])

новые = {}
for пачка in (LEG3, LEG4, LEG5, LEG6, LEG7):
    новые.update(пачка)

# проверка дословных повторов текстов
все_тексты = collections.Counter()
for v in легенды.values():
    for поле in ('h3', 'пункты', 'проза', 'финал'):
        for э in v[поле]:
            все_тексты[э['т'] if isinstance(э, dict) else э] += 1

добавлено = 0
for имя, v in новые.items():
    if имя in легенды:
        print('уже есть, пропуск:', имя); continue
    слова = [с for с in v['слова'] if с not in занято]
    занято.update(слова)
    запись = {'слова': слова}
    for поле in ('h3', 'пункты', 'проза', 'финал'):
        запись[поле] = [{'т': т, 'д': 'лег'} for т in v[поле]]
        for т in v[поле]:
            все_тексты[т] += 1
    легенды[имя] = запись
    добавлено += 1

повторы = [т for т, n in все_тексты.items() if n > 1]
print('добавлено легенд:', добавлено, '| всего:', len(легенды))
print('дословных повторов между легендами:', len(повторы))
for т in повторы[:5]:
    print('  !', т)

json.dump(p, open(путь, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
