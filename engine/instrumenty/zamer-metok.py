# -*- coding: utf-8 -*-
"""Замер по меткам пунктов: пунктов, ведущий strong, оценочные и тематические
метки, плюс промахи приёмки и уникальность. Подменные пулы и журнал — аргументы,
чтобы сторона «до» мерилась без правок рабочего дерева."""
import importlib.util, json, os, re, shutil, sys
from concurrent.futures import ThreadPoolExecutor

КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
сп = importlib.util.spec_from_file_location('drv', os.path.join(КОРЕНЬ, 'engine/instrumenty/driver-v5.py'))
drv = importlib.util.module_from_spec(сп); сп.loader.exec_module(drv)
БАЗА, СИД0, N, ВЫХОД = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
МАНЕРА = sys.argv[5] if len(sys.argv) > 5 else 'обычная'
ПУЛЫ   = sys.argv[6] if len(sys.argv) > 6 else None
ЖУРНАЛ = sys.argv[7] if len(sys.argv) > 7 else None
ГЕН    = sys.argv[8] if len(sys.argv) > 8 else 'engine/generator-v5.php'
ПЕР    = sys.argv[9] if len(sys.argv) > 9 else 'engine/perekrut-v5.php'
# Номер первого набора. Если задан, наборы зовутся «nabor-N» по возрастанию, и
# манера мечения берётся из номера последовательностью Вейля, а не из сида.
# Без него манера читалась из crc32 сида и на коротких отрезках выпадала
# комками: по кругам настройки выходило 12/5/7, 7/5/12, 12/3/9, 7/7/10 и даже
# 15/0/9 вместо корпусных 9/5/9 на 24 набора — а в последнем случае обычных
# наборов не было вовсе, и парный замер порога обычной манеры оказался пустым
# по построению. Номера 900–923 дают 9/6/9 и три «вы»-набора.
НАБОР0 = int(sys.argv[10]) if len(sys.argv) > 10 else 0
drv.БАЗА = БАЗА; os.makedirs(БАЗА, exist_ok=True)

if ПУЛЫ or ЖУРНАЛ:
    свой = os.path.join(БАЗА, 'мастер'); os.makedirs(свой, exist_ok=True)
    for имя in os.listdir(drv.МАСТЕР):
        цель = os.path.join(свой, имя)
        if os.path.lexists(цель): continue
        if имя == 'pools.json' and ПУЛЫ: shutil.copyfile(ПУЛЫ, цель)
        elif имя == 'vydano.json' and ЖУРНАЛ: shutil.copyfile(ЖУРНАЛ, цель)
        else: os.symlink(os.path.join(drv.МАСТЕР, имя), цель)
    drv.МАСТЕР = свой

# Три кучи ярлыков: голая оценка, оценка словами, тема без оценки. Корпусные
# доли у них 1.8 %, 2.0 % и 17.0 % по медиане — считать вместе нельзя.
МЕТКА = re.compile(r'^\s*([А-ЯЁ][^:<]{2,40}):\s*\S')
ГОЛАЯ = re.compile(r'^(плюс|минус|важно|честно|риск|совет|итог|факт)$', re.I)
ОЦСЛОВ = re.compile(r'\b(плюс\w*|минус\w*|риск\w*|важно|честно|совет|итог\w*|факт\w*)\b', re.I)
ТЕГИ = re.compile(r'(?s)<[^>]+>')

def метки(п):
    в = s = о = осл = м = 0
    for ф in sorted(os.listdir(п)):
        if not ф.endswith('.html'): continue
        txt = open(os.path.join(п, ф), encoding='utf-8', errors='replace').read()
        for x in re.finditer(r'(?is)<li\b[^>]*>(.*?)</li>', txt):
            вн = x.group(1); ч = re.sub(r'\s+', ' ', ТЕГИ.sub('', вн)).strip()
            if len(ч.split()) < 4: continue
            в += 1
            if re.match(r'(?is)\s*<strong\b', вн): s += 1
            я = МЕТКА.match(ч)
            if not я: continue
            я = я.group(1).strip()
            if ГОЛАЯ.match(я): о += 1
            elif ОЦСЛОВ.search(я): осл += 1
            else: м += 1
    return {'пунктов': в, 'strong': s, 'оцен': о, 'оцсл': осл, 'темат': м}

def одна(задание):
    и, сид = задание
    d = drv.песочница(и); drv.синхр(d)
    п = os.path.join(БАЗА, 'z%d-%d' % (и, сид))
    shutil.rmtree(п, ignore_errors=True)
    имя = 'nabor-%d' % (НАБОР0 + (сид - СИД0)) if НАБОР0 else 'zamer'
    try:
        drv.php(ГЕН, '--выход=' + п, '--сид=%d' % сид,
                '--данные=' + d, '--тихо', '--имя=' + имя, '--манера=' + МАНЕРА)
        if not os.path.isdir(п) or len(os.listdir(п)) < 12: return None
        итог = {'сид': сид, 'имя': имя, 'ген': метки(п)}
        drv.php(ПЕР, п, '--сид=%d' % сид, '--тихо')
        итог['пер'] = метки(п)
        j = json.loads(drv.php('engine/priyomka-v5.php', п, '--json').stdout)
        итог['промахи'] = {т: list((s.get('мимо') or {}).keys())
                           for т, s in (j.get('страницы') or {}).items()}
        итог['уник'] = {т: u.get('процент') for т, u in (j.get('уникальность') or {}).items()}
        итог['метрики'] = json.loads(drv.php('engine/instrumenty/metriki-nabora.php', п).stdout)
        return итог
    except Exception:
        return None
    finally:
        shutil.rmtree(п, ignore_errors=True)

for и in range(drv.РАБОТНИКОВ): drv.песочница(и)
with open(ВЫХОД, 'w', buffering=1, encoding='utf-8') as ф:
    задания = [(i % drv.РАБОТНИКОВ, СИД0 + i) for i in range(N)]
    with ThreadPoolExecutor(max_workers=drv.РАБОТНИКОВ) as пул:
        for r in пул.map(одна, задания):
            if r: ф.write(json.dumps(r, ensure_ascii=False) + '\n')
print('готово')
