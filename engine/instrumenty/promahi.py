# -*- coding: utf-8 -*-
"""Какие поля приёмки валятся чаще: сводка по наборам, по манере.
   Считает и сами промахи, и сторону — ниже полосы или выше."""
import json, os, shutil, subprocess, sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

КОРЕНЬ = '/home/user/cladue'
БАЗА = sys.argv[1]
СИДЫ = [int(x) for x in sys.argv[2].split(',')]
МАНЕРА = os.environ.get('V5_MANERA', 'обычная')

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
    и, сид = задание
    п = os.path.join(БАЗА, 's%d' % сид)
    shutil.rmtree(п, ignore_errors=True)
    php('engine/generator-v5.php', '--выход=' + п, '--сид=%d' % сид, '--тихо',
        '--данные=' + os.path.join(БАЗА, 'pesok%d' % и), '--манера=' + МАНЕРА)
    if not os.path.isdir(п) or len(os.listdir(п)) < 12:
        return None
    php('engine/perekrut-v5.php', п, '--сид=%d' % сид, '--тихо')
    try:
        итог = json.loads(php('engine/priyomka-v5.php', п, '--json').stdout)
    except Exception:
        return None
    промахи = []
    for тип, s in итог.get('страницы', {}).items():
        # Пустой список промахов PHP отдаёт как [], а не как объект.
        мимо = s.get('мимо') if isinstance(s, dict) else None
        if not isinstance(мимо, dict):
            continue
        плохая = s.get('процент', 100) < 95
        for поле, пара in мимо.items():
            промахи.append((поле, тип, плохая, пара))
    shutil.rmtree(п, ignore_errors=True)
    return промахи

os.makedirs(БАЗА, exist_ok=True)
for и in range(4):
    песочница(и)
задания = [(i % 4, с) for i, с in enumerate(СИДЫ)]
всё = []
with ThreadPoolExecutor(max_workers=4) as ex:
    for r in ex.map(один, задания):
        if r:
            всё.extend(r)

поля = Counter(п for п, _, _, _ in всё)
наСтраницахПровала = Counter(п for п, _, пл, _ in всё if пл)
print('наборов %d, промахов всего %d' % (len(СИДЫ), len(всё)))
def сторона(пара):
    # В «мимо» либо [наше, цель], либо [наше, 'низ–верх'] для полосы.
    наше, цель = pair = пара[0], пара[1]
    try:
        if isinstance(цель, str) and '–' in цель:
            низ, верх = (float(x) for x in цель.split('–'))
            return наше - верх if наше > верх else (наше - низ if наше < низ else 0.0)
        return float(наше) - float(цель)
    except Exception:
        return None

print('%-20s %7s %10s %9s  %s' % ('поле', 'всего', 'на прова-', 'сторона', 'типы'))
print('%-20s %7s %10s %9s' % ('', '', 'ленных', 'медиана'))
for поле, n in поля.most_common(25):
    типы = Counter(т for п, т, _, _ in всё if п == поле)
    отклон = [с for п, _, _, пара in всё if п == поле
              for с in [сторона(пара)] if с is not None]
    отклон.sort()
    мед = отклон[len(отклон)//2] if отклон else 0.0
    знак = 'ниже' if мед < 0 else ('выше' if мед > 0 else '—')
    print('%-20s %7d %10d %5s%+5.1f  %s' % (поле, n, наСтраницахПровала[поле], знак, мед,
          ' '.join('%s×%d' % (т, k) for т, k in типы.most_common(5))))
