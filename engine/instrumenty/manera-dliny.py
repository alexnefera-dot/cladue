# -*- coding: utf-8 -*-
"""Длины абзаца по типам: один и тот же сид в двух манерах.

Сводка промахов показала, что words_per_para, nausea_acad и terms_total
смотрят ниже цели на одних и тех же длинных типах густого набора. Сравнение
двух готовых наборов слабое — там разные сиды. Здесь каждый сид собирается и
густым, и обычным, так что разница остаётся только от манеры.
"""
import json, os, shutil, statistics as st, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

КОРЕНЬ = '/home/user/cladue'
БАЗА = sys.argv[1]
СИДЫ = [int(x) for x in sys.argv[2].split(',')]
ДЛИННЫЕ = ['obzor', 'promo', 'news', 'partnery', 'info', 'slots']

def php(*а, т=900):
    return subprocess.run(['php'] + list(а), cwd=КОРЕНЬ, capture_output=True, text=True, timeout=т)

def песочница(и):
    d = os.path.join(БАЗА, 'pesok%d' % и)
    os.makedirs(d, exist_ok=True)
    мастер = os.path.join(КОРЕНЬ, 'engine/data-v5')
    for имя in os.listdir(мастер):
        цель = os.path.join(d, имя)
        if имя == 'vydano.json':
            shutil.copyfile(os.path.join(мастер, имя), цель)
        elif not os.path.exists(цель):
            os.symlink(os.path.join(мастер, имя), цель)
    return d

def один(задание):
    и, сид, манера = задание
    п = os.path.join(БАЗА, '%s-%d' % (манера, сид))
    shutil.rmtree(п, ignore_errors=True)
    php('engine/generator-v5.php', '--выход=' + п, '--сид=%d' % сид, '--тихо',
        '--данные=' + os.path.join(БАЗА, 'pesok%d' % и), '--манера=' + манера,
        '--имя=замер-%d' % сид)
    if not os.path.isdir(п) or len(os.listdir(п)) < 12:
        return None
    php('engine/perekrut-v5.php', п, '--сид=%d' % сид, '--тихо')
    r = php('engine/instrumenty/dliny.php', п)
    try:
        карта = json.loads(r.stdout)
    except Exception:
        return None
    shutil.rmtree(п, ignore_errors=True)
    return (сид, манера, карта)

os.makedirs(БАЗА, exist_ok=True)
for и in range(4):
    песочница(и)
задания = []
for i, с in enumerate(СИДЫ):
    задания.append((i % 4, с, 'густая'))
    задания.append(((i + 2) % 4, с, 'обычная'))
итоги = []
with ThreadPoolExecutor(max_workers=4) as ex:
    for r in ex.map(один, задания):
        if r:
            итоги.append(r)

print('сидов %d, сборок %d\n' % (len(СИДЫ), len(итоги)))
print('%-10s %-26s %-26s' % ('тип', 'густая (слов/абз, фраз)', 'обычная (слов/абз, фраз)'))
for т in ДЛИННЫЕ:
    стр = []
    for манера in ('густая', 'обычная'):
        сл = [к[т]['слов_абз'] for _, м, к in итоги if м == манера and т in к]
        фр = [к[т]['фраз_абз'] for _, м, к in итоги if м == манера and т in к]
        стр.append('%5.1f  фраз %4.2f  (n=%d)' % (
            st.median(сл) if сл else 0, st.median(фр) if фр else 0, len(сл)))
    print('%-10s %-26s %-26s' % (т, стр[0], стр[1]))
