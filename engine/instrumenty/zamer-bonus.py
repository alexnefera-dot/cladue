# -*- coding: utf-8 -*-
"""Непрерывный замер bonus на одних сидах: сырые метрики страницы и процент
пересечения с худшим соседом. Бинарное «прошло/не прошло» у порога тратит
почти весь сигнал — на 186 сидах оно не отличило от шума правку, которая по
значениям видна на двух десятках. Здесь пишутся сами величины.
Мастер-журнал только читается."""
import importlib.util, json, os, shutil, sys
from concurrent.futures import ThreadPoolExecutor

сп = importlib.util.spec_from_file_location('drv', '/home/user/cladue/engine/instrumenty/driver-v5.py')
drv = importlib.util.module_from_spec(сп); сп.loader.exec_module(drv)
БАЗА, СИД0, N, ВЫХОД = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
МАНЕРА = sys.argv[5] if len(sys.argv) > 5 else 'густая'
drv.БАЗА = БАЗА; os.makedirs(БАЗА, exist_ok=True)

# Подменный pools.json шестым аргументом: сторона «до» мерится без правки
# рабочего дерева. Прежде я выкладывал прежний файл через git checkout, и
# дерево стояло грязным весь замер — а при перезапуске контейнера это ещё и
# единственное, что осталось бы от правки.
if len(sys.argv) > 6:
    свой = os.path.join(БАЗА, 'мастер')
    os.makedirs(свой, exist_ok=True)
    for имя in os.listdir(drv.МАСТЕР):
        цель = os.path.join(свой, имя)
        if os.path.lexists(цель):
            continue
        if имя == 'pools.json':
            shutil.copyfile(sys.argv[6], цель)
        else:
            os.symlink(os.path.join(drv.МАСТЕР, имя), цель)
    drv.МАСТЕР = свой

def одна(задание):
    и, сид = задание
    d = drv.песочница(и); drv.синхр(d)
    п = os.path.join(БАЗА, 'z%d-%d' % (и, сид))
    shutil.rmtree(п, ignore_errors=True)
    try:
        drv.php('engine/generator-v5.php', '--выход=' + п, '--сид=%d' % сид,
                '--данные=' + d, '--тихо', '--имя=zamer', '--манера=' + МАНЕРА)
        if not os.path.isdir(п) or len(os.listdir(п)) < 12: return None
        drv.php('engine/perekrut-v5.php', п, '--сид=%d' % сид, '--тихо')
        итог = {'сид': сид}
        r = drv.php('engine/instrumenty/metriki-nabora.php', п)
        итог['метрики'] = json.loads(r.stdout)
        r = drv.php('engine/priyomka-v5.php', п, '--json')
        j = json.loads(r.stdout)
        итог['уник'] = {т: {'процент': u.get('процент'), 'потолок': u.get('потолок'),
                            'худший': u.get('худший')}
                        for т, u in (j.get('уникальность') or {}).items()}
        итог['промахи'] = {т: list((s.get('мимо') or {}).keys())
                           for т, s in (j.get('страницы') or {}).items()}
        return итог
    except Exception:
        return None
    finally:
        shutil.rmtree(п, ignore_errors=True)

for и in range(drv.РАБОТНИКОВ): drv.песочница(и)
with open(ВЫХОД, 'w', buffering=1, encoding='utf-8') as ф:
    with ThreadPoolExecutor(max_workers=drv.РАБОТНИКОВ) as ex:
        for r in ex.map(одна, [(i % drv.РАБОТНИКОВ, СИД0 + i) for i in range(N)]):
            if r: ф.write(json.dumps(r, ensure_ascii=False) + '\n')
print('готово')
