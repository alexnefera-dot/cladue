#!/usr/bin/env python3
"""Час запуска и аккаунт: проверка со всё более тесной стратой.

В разрезах по отдельным группам контента ночь выглядит провальной почти
везде. Это обманчиво: группа контента живёт несколько дней, а час уезжает
вместе с днём. Поэтому страта наращивается по шагам — день, контент+день,
плюс зона, плюс бренд — и видно, на каком шаге эффект исчезает.

    python3 chas_i_akkaunt.py
"""
import json,collections,re,math
S='/tmp/claude-0/-home-user-cladue/de95974e-6e28-5d1d-820f-f09c0d0e2b43/scratchpad/'
W={}
for line in open(S+'okno3.jsonl',encoding='utf-8'):
    a=json.loads(line); W[a[0]]=a[1:]
acc={}
for line in open('/tmp/yaacc.jsonl',encoding='utf-8'):
    a=json.loads(line); acc[a[0]]=a[1]
def blk(h): return None if h is None else '00-05' if h<6 else '06-11' if h<12 else '12-17' if h<18 else '18-23'
rows=[];bd=collections.defaultdict(set)
for line in open('/tmp/panel_25.jsonl',encoding='utf-8'):
    r=json.loads(line)
    d=(r.get('recrawl_sent_at') or '')[:10]; b=r.get('content_domain_url')
    if not d or not b or d>'2026-09-18': continue
    bd[b].add(d)
    w=W.get(r['subdomain'],[0,0,0,0,0])
    h=r.get('recrawl_hour')
    if h is None and r.get('recrawl_sent_at'): h=int(r['recrawl_sent_at'][11:13])
    rows.append({'base':b,'day':d,'tld':r.get('tld'),'hour':h,'blk':blk(h),
        'content':re.sub(r'[_\-]\d+$','',r.get('content') or 'НЕ ЗАПИСАН'),
        'brand':r.get('brand_label'),
        'ya':r.get('ya_account_id') if r.get('ya_account_id') is not None else acc.get(r['subdomain']),
        'hit':1 if w[2] else 0,'cl':w[2],'reg':w[3]})
first={b:min(ds) for b,ds in bd.items()}
byacc=collections.defaultdict(set)
for r in rows:
    if r['ya'] is not None: byacc[r['ya']].add(r['base'])
seq={}
for a,bs in byacc.items():
    for i,b in enumerate(sorted(bs,key=lambda x:(first[x],x))): seq[b]=i+1
for r in rows: r['acc']='свежий' if seq.get(r['base'])==1 else 'повторный' if seq.get(r['base']) else '?'
def strat(level,stratum,title,minn=2000,minstrat=80):
    sp=collections.defaultdict(lambda:[0,0])
    for r in rows:
        k=stratum(r)
        if k is None: continue
        t=sp[k]; t[0]+=r['hit']; t[1]+=1
    g=collections.defaultdict(lambda:[0,0,0.0,0,0])
    for r in rows:
        k,v=stratum(r),level(r)
        if k is None or v is None: continue
        h,n=sp[k]
        if n<minstrat: continue
        t=g[v]; t[0]+=r['hit']; t[1]+=1; t[2]+=h/n; t[3]+=r['reg']; t[4]+=r['cl']
    o=[(v,t) for v,t in g.items() if t[1]>=minn]
    if len(o)<2: print('\n'+title+'\n  уровней нет'); return
    o.sort(key=lambda x:-(x[1][0]/x[1][2] if x[1][2] else 0))
    print('\n'+title)
    print('  %-12s %9s %8s %9s %6s %10s'%('уровень','сайтов','выход %','к страте','рег','рег/10т'))
    for v,t in o:
        print('  %-12s %9d %7.1f%% %9.2f %6d %10.1f'%(v,t[1],100*t[0]/t[1],
            t[0]/t[2] if t[2] else 0,t[3],10000*t[3]/t[4] if t[4] else 0))
print('ВЫХОД В ПОИСК ЗА ТРОЕ СУТОК, %d сайтов, %.1f%%'%(len(rows),100*sum(r['hit'] for r in rows)/len(rows)))
strat(lambda r:r['blk'],lambda r:r['day'],'ЧАС | страта: день')
strat(lambda r:r['blk'],lambda r:(r['content'],r['day']),'ЧАС | страта: контент + день')
strat(lambda r:r['blk'],lambda r:(r['content'],r['day'],r['tld']),'ЧАС | страта: контент + день + зона')
strat(lambda r:r['blk'],lambda r:(r['content'],r['day'],r['tld'],r['brand']),
      'ЧАС | страта: контент + день + зона + бренд',minstrat=6)
strat(lambda r:r['acc'] if r['acc']!='?' else None,lambda r:(r['content'],r['day']),
      'АККАУНТ | страта: контент + день')
print('\nСОСТАВ АККАУНТОВ ВНУТРИ ГРУПП КОНТЕНТА')
g=collections.defaultdict(lambda: collections.Counter())
for r in rows: g[r['content']][r['acc']]+=1
mix=[c for c,v in g.items() if len(v)>1 and min(v.values())>=300 and sum(v.values())>=1500]
print('  групп контента, где есть и свежие, и повторные аккаунты (по 300+ сайтов): %d из %d'%(
    len(mix),sum(1 for c,v in g.items() if sum(v.values())>=1500)))
for c in mix[:10]:
    v=g[c]; print('    %-40s %s'%(c[:40],dict(v)))
