# Эпохи запусков и возраст домена -> wk.json (ключи era, eraday, age, oldbase)
# Запускается после wk.py, в одной папке с conv2.json / db.json / wk.json / pools.json
import json,collections,datetime as dt
db=json.load(open('db.json')); C=json.load(open('conv2.json')); W=json.load(open('wk.json'))
import os
EXTRA=json.load(open('conv3.json')) if os.path.exists('conv3.json') else []   # плоская выгрузка 29-31.08
POOLS=json.load(open('pools.json'))
# дата ВЫКЛАДКИ группы. По умолчанию = дата создания контента, кроме двух групп,
# где неиспользованный контент 21.08 выложили позже (см. launches.md).
OV={'NEW50_5_7pages_nodate_21.08 _7…_17':'25.08',
    'КОНТРОЛЬ NEW50_5_7pages_nodate_21.08 _18…_24':'26.08'}
P1=['2139.team','2483.team','ogax.team','byai.team','7186.team','4087.team','2084.team','2304.team','7440.team','0302.team']
P2=['bmtq.team','cnwv.team','dprz.team','fkxb.team','glhd.team','hjsf.team','1524.team','1893.team','2367.team','2745.team','4328.team']
G27=['3596.team','b8rn.team','c5vt.team','d3mw.team','f9kq.team','f9pb.team','h7nd.team','j2t.team','k6m.team','r9v.team']
L={}
for d,v in db.items():
    if d=='базовый домен': continue
    L[d]=OV.get(v['group'], v['made'][:5])
for d in P1+P2+G27: L[d]='27.08'
def dd(s): return dt.date(2026,int(s[3:5]),int(s[:2]))
ERA=lambda d: ('19–20.08' if L[d] in ('19.08','20.08') else '21–27.08') if d in L else 'до 19.08'
TR={d:v for d,v in C['tr'].items() if v['is_dom']}
def GRP(d):
    if d in db and d!='базовый домен': return db[d]['group']
    if d in set(P1): return '7page_27.08 · партия 1'
    if d in set(P2): return '7page_27.08 · партия 2'
    if d in set(G27): return 'Generator_11page_old_27.08'
    return 'наши запуски до 19.08'
ALLEV=C['ev']+EXTRA
regs=[e for e in ALLEV if e['type']=='reg']; deps=[e for e in ALLEV if e['type']=='dep']
rd=collections.Counter(e['dom'] for e in regs); dp=collections.Counter(e['dom'] for e in deps)
B=collections.defaultdict(lambda:dict(n=0,reg=0,dep=0,uniq=0,hits=0,sub=0))
for d,v in TR.items():
    b=B[ERA(d)]; b['n']+=1; b['reg']+=rd.get(d,0); b['dep']+=dp.get(d,0)
    b['uniq']+=v['uniq']; b['hits']+=v['hits']; b['sub']+=v['sub']
DAYS=sorted({e['d'] for e in regs})
byday=collections.defaultdict(collections.Counter)
for e in regs: byday[ERA(e['dom'])][e['d']]+=1
ERAS=[]
for k in ['21–27.08','19–20.08','до 19.08']:
    b=B[k]; ERAS.append(dict(k=k,n=b['n'],reg=b['reg'],dep=b['dep'],uniq=b['uniq'],sub=b['sub'],
        rpd=round(b['reg']/b['n'],3),days=[byday[k][d] for d in DAYS],
        l2=sum(byday[k][d] for d in DAYS[-2:])))
# возраст домена на момент регистрации + экспозиция дом*суток
today=dt.date(2026,8,31)
ages=collections.Counter(); expo=collections.Counter()
for e in regs:
    if e['dom'] in L: ages[(dd(e['d'])-dd(L[e['dom']])).days]+=1
for d,l in L.items():
    for a in range(0,(today-dd(l)).days+1): expo[a]+=1
AGE=[dict(a=a,reg=ages[a],expo=expo[a],rate=round(100*ages[a]/expo[a],2)) for a in sorted(expo) if a<=11]
ob=B['до 19.08']; obdd=ob['n']*len(DAYS)
OB=dict(n=ob['n'],reg=ob['reg'],dep=ob['dep'],uniq=ob['uniq'],sub=ob['sub'],
        domdays=obdd,rate=round(100*ob['reg']/obdd,2))
fresh_r=sum(ages[a] for a in (1,2,3,4,5,6)); fresh_e=sum(expo[a] for a in (1,2,3,4,5,6))
# --- бренды вне списка отслеживания и «мёртвые» в ядре, но с деньгами
import csv as _csv
CORE=set()
with open('/home/user/cladue/analysis/keys/keys_stats.csv',encoding='utf-8-sig') as fh:
    for row in _csv.DictReader(fh,delimiter=';'):
        if row.get('бренд'): CORE.add(row['бренд'])
nrm=lambda b: b.replace(' ','').replace('-','').lower()
CN={nrm(c):c for c in CORE}
rbz=collections.Counter(e['brand'] for e in regs if e.get('brand'))
MISS=sorted([dict(b=b,reg=c) for b,c in rbz.items() if nrm(b) not in CN],key=lambda x:-x['reg'])
K10={x['b']:x['k10'] for x in W['br']}
DEAD=sorted([dict(b=CN[nrm(b)],reg=c) for b,c in rbz.items() if nrm(b) in CN and K10.get(CN[nrm(b)],0)==0],
            key=lambda x:-x['reg'])
ZERO=[x['b'] for x in W['br'] if x['reg']==0 and x['k10']>=20]
W['miss']=MISS; W['deadconv']=DEAD; W['zero']=ZERO
L2D=DAYS[-2:]
_l2=collections.Counter()
for e in regs:
    if e['d'] in L2D:
        d=e['dom']
        _l2[GRP(d)]+=1
W['l2']=dict(days=L2D,tot=sum(_l2.values()),rows=[dict(g=g,c=c) for g,c in _l2.most_common()])
W.update(era=ERAS,eradays=DAYS,age=AGE,oldbase=OB,
         fresh=dict(reg=fresh_r,expo=fresh_e,rate=round(100*fresh_r/fresh_e,2)))
for p in POOLS:
    if 'вне наблюдения' in p['g']:
        p['g']='наши запуски до 19.08'; p['cfg']='старая база, контент не в реестре'
        p['days']=len(DAYS); p['rpdd']=ob['reg']/ob['n']/len(DAYS)
W['pools']=POOLS
for d in W['dm']:
    if d['group']=='вне наблюдения':
        d['group']='наши запуски до 19.08'; d['src']='контент не заведён в реестр'
    d['era']=ERA(d['d'])
# --- доля доменов, вообще давших регистрацию
HIT=[]
for k in ['21–27.08','19–20.08','до 19.08']:
    ds=[d for d in TR if ERA(d)==k]; w=[d for d in ds if rd.get(d,0)]
    HIT.append(dict(k=k,n=len(ds),w=len(w),z=len(ds)-len(w),sh=round(100*len(w)/len(ds),1),
        reg=sum(rd[d] for d in w),dist=sorted(collections.Counter(rd[d] for d in w).items())))
NEWD=[d for d in TR if d in L and L[d] not in ('19.08','20.08')]
GG=collections.defaultdict(lambda:dict(n=0,w=0,reg=0,dep=0,ld=None))
for d in NEWD:
    g=GG[GRP(d)]; g['n']+=1; g['reg']+=rd.get(d,0); g['dep']+=dp.get(d,0); g['ld']=L[d]
    if rd.get(d,0): g['w']+=1
GH=[dict(g=g,ld=v['ld'],n=v['n'],w=v['w'],z=v['n']-v['w'],sh=round(100*v['w']/v['n']),reg=v['reg'],dep=v['dep'])
    for g,v in sorted(GG.items(),key=lambda x:(-x[1]['w']/x[1]['n'],-x[1]['reg']))]
DMI={d['d']:d for d in W['dm']}
POS=[]
for lo,hi,lab in [(0,0,'ни одного'),(1,4,'1–4'),(5,14,'5–14'),(15,49,'15–49'),(50,9999,'50 и больше')]:
    ds=[d for d in NEWD if d in DMI and lo<=DMI[d]['t10']<=hi]
    if not ds: continue
    w=[d for d in ds if rd.get(d,0)]
    POS.append(dict(lab=lab,n=len(ds),w=len(w),sh=round(100*len(w)/len(ds)),reg=sum(rd[d] for d in w)))
W.update(hit=HIT,grouphit=GH,poshit=POS)
# --- пулы: итог по регистрациям на домен, без деления на сутки
cum={}; c=0
for x in range(0,9):
    c+=ages[x]; cum[x]=c/sum(ages.values())
GP=collections.defaultdict(lambda:dict(n=0,reg=0,dep=0,uniq=0,ld=None))
for d in TR:
    if d not in L: continue
    g=GP[GRP(d)]; g['n']+=1; g['reg']+=rd.get(d,0); g['dep']+=dp.get(d,0)
    g['uniq']+=TR[d]['uniq']; g['ld']=L[d]
CFG={}
for d,v in db.items():
    if d=='базовый домен': continue
    CFG.setdefault(v['group'],' · '.join(x for x in [v['src'],(v['pages']+' стр' if v['pages'] not in ('?','—') else ''),v['dates'],v['img']] if x and x!='—'))
CFG.update({'7page_27.08 · партия 1':'7 страниц · id 1004-1013 · создан 27.08 17:33-17:40',
            '7page_27.08 · партия 2':'7 страниц · id и время не присланы',
            'Generator_11page_old_27.08':'наш генератор · 11 стр · «old» · id 1014-1023'})
P2N=[]
for g,v in GP.items():
    age=(today-dd(v['ld'])).days; sh=cum[min(age,8)]
    P2N.append(dict(g=g,cfg=CFG.get(g,'—'),ld=v['ld'],age=age,n=v['n'],reg=v['reg'],dep=v['dep'],
        uniq=v['uniq'],rpd=round(v['reg']/v['n'],2),share=round(100*sh),
        proj=(round(v['reg']/v['n']/sh,2) if sh and age<6 else None),done=age>=6))
P2N.sort(key=lambda x:(-x['rpd'],-x['reg']))
W['pools2']=P2N; W['cum']=[dict(a=x,sh=round(100*cum[x])) for x in range(0,7)]
json.dump(W,open('wk.json','w'),ensure_ascii=False)
print('эпохи',[(e['k'],e['n'],e['reg']) for e in ERAS])
print('возраст',[(a['a'],a['reg'],a['rate']) for a in AGE])
print('старая база',OB,'свежие 1-4 сут',W['fresh'])

# --- эффективность захвата по частотности бренда
import csv as _c2
TIER={}
with open('/home/user/cladue/analysis/keys/keys_stats.csv',encoding='utf-8-sig') as _f2:
    for _r in _c2.DictReader(_f2,delimiter=';'):
        if _r.get('бренд'): TIER.setdefault(_r['бренд'],_r['тир'])
_CN2={nrm(c):c for c in TIER}
_rt=collections.Counter(); _kt=collections.Counter(); _dt=collections.Counter()
for e in regs:
    b=_CN2.get(nrm(e['brand'] or '')) if e.get('brand') else None
    _rt[TIER.get(b,'вне списка') if b else 'вне списка']+=1
for x in W['br']:
    if x['k10']: _kt[x['tier'] or '—']+=x['k10']; _dt[x['tier'] or '—']+=x['d10']
_tk=sum(_kt.values()); _tr=sum(_rt.values())
W['tier']=[dict(t=t,k10=_kt[t],ksh=round(100*_kt[t]/_tk),reg=_rt[t],rsh=round(100*_rt[t]/_tr),
               eff=round(100*_rt[t]/_kt[t],1) if _kt[t] else None) for t in ['ВЧ','СЧ','НЧ']]
W['tier'].append(dict(t='вне списка',k10=0,ksh=0,reg=_rt['вне списка'],
                      rsh=round(100*_rt['вне списка']/_tr),eff=None))
_vch=[b for b,t in TIER.items() if t=='ВЧ']
_BR={x['b']:x for x in W['br']}
W['vch']=dict(total=len(_vch),held=len([b for b in _vch if _BR.get(b,{}).get('k10',0)>0]))
json.dump(W,open('wk.json','w'),ensure_ascii=False)
print('тир:',W['tier'],'ВЧ:',W['vch'])
