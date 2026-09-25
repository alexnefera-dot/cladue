# -*- coding: utf-8 -*-
"""Сравнение ворот на одних и тех же сидах: сколько провалов приёмки,
находок смысла и какие средние по сверке."""
import json, os, re, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
КОРЕНЬ=os.environ.get('V5_KOREN', '/home/user/cladue')
БАЗА=sys.argv[1]; СИДЫ=[int(x) for x in sys.argv[2].split(',')]
МАНЕРА=os.environ.get('V5_MANERA','обычная')
def php(*a, t=900):
    return subprocess.run(['php']+list(a), cwd=КОРЕНЬ, capture_output=True, text=True, timeout=t)
def песочница(и=0):
    """Свой журнал выдачи на каждого работника: общий журнал четыре
    параллельных генератора пишут наперегонки и рвут друг другу выдачу, а
    общий на прогон делает нечестным второй замер — он стартовал бы с
    журнала, который уже перелопатил первый."""
    d=os.path.join(БАЗА,'pesok%d'%и); os.makedirs(d, exist_ok=True)
    мастер=os.path.join(КОРЕНЬ,'engine/data-v5')
    for имя in os.listdir(мастер):
        цель=os.path.join(d,имя)
        if имя=='vydano.json':
            shutil.copyfile(os.path.join(мастер,имя), цель)
        elif not os.path.exists(цель):
            os.symlink(os.path.join(мастер,имя), цель)
    return d

def один(задание):
    и, сид = задание
    п=os.path.join(БАЗА,'s%d'%сид); shutil.rmtree(п, ignore_errors=True)
    php('engine/generator-v5.php','--выход='+п,'--сид=%d'%сид,'--тихо',
        '--данные='+os.path.join(БАЗА,'pesok%d'%и),'--манера='+МАНЕРА)
    if not os.path.isdir(п) or len(os.listdir(п))<12: return сид, None
    php('engine/perekrut-v5.php',п,'--сид=%d'%сид,'--тихо')
    try:
        стр=list(json.loads(php('engine/sverka-v5.php',п,'--json').stdout).values())[0]['страницы']
    except Exception:
        return сид, None
    зн=list(стр.values()); ср=lambda k: sum(v[k] for v in зн)/len(зн)
    r=php('engine/priyomka-v5.php',п)
    # Пройденная приёмка не печатает строку с числом провалов — она печатает
    # «приёмка пройдена». Без этой ветки чистый набор писался как −1 и тянул
    # среднее вниз, а в счёте «прошло всё» не учитывался вовсе.
    м=re.findall(r'провалов:\s*(\d+)', r.stdout)
    if м:
        провалов=int(м[-1])
    elif 'приёмка пройдена' in r.stdout:
        провалов=0
    else:
        провалов=-1
    if провалов < 0:
        open(os.path.join(БАЗА,'приёмка-%d.err'%сид),'w',encoding='utf-8').write(r.stdout+'\n=== stderr ===\n'+r.stderr)
    try: находок=len(json.loads(php('engine/smysl-v5.php',п,'--json').stdout).get('находки',[]))
    except Exception: находок=-1
    итог=dict(сид=сид, провалов=провалов, находок=находок,
              обрывки=sum(v['fragments'] for v in зн),
              мантра=round(ср('mantra_max'),2), rtp=round(ср('rtp_spread'),2),
              абзацы=round(ср('paragraphs'),2), слов_абз=round(ср('words_per_para'),2),
              джекпот=max(v['jackpot_uniq'] for v in зн), выплаты=round(ср('payout_uniq'),2))
    shutil.rmtree(п, ignore_errors=True)
    return сид, итог
os.makedirs(БАЗА, exist_ok=True)
for и in range(4): песочница(и)
с=[]
задания=[(i % 4, с_) for i, с_ in enumerate(СИДЫ)]
with ThreadPoolExecutor(max_workers=4) as ex:
    for сид, r in ex.map(один, задания):
        if r: с.append(r); print(json.dumps(r, ensure_ascii=False), flush=True)
if с:
    прошло=sum(1 for r in с if r['провалов']==0 and r['находок']==0 and r['обрывки']==0)
    print('сидов %d, без провалов приёмки %d, без находок смысла %d, прошло всё %d'
          % (len(с), sum(1 for r in с if r['провалов']==0), sum(1 for r in с if r['находок']==0), прошло))
    for k in ['провалов','находок','мантра','rtp','абзацы','слов_абз','джекпот','выплаты']:
        v=[r[k] for r in с]; print('  %-9s среднее %.2f  макс %.2f' % (k, sum(v)/len(v), max(v)))
