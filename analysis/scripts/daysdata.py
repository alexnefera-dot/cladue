# Данные для отчёта «Дни запуска и окна конверсий».
import json,collections,math,random,re,datetime as dt
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
EV=json.load(open(SP+'convall.json'))
db=json.load(open(SP+'db.json'))
SN=json.load(open(SP+'snapr.json')); QD=SN['qd']
reg=collections.Counter(e['dom'] for e in EV if e['type']=='reg')
dep=collections.Counter(e['dom'] for e in EV if e['type']=='dep')
TODAY=dt.date(2026,9,3)
CURVE=[0,18,49,75,90,95,99]          # накопленный % заработка к концу N-х суток
DATA0=dt.date(2026,8,21)             # первый день, покрытый выгрузкой конверсий

DAY={}; GRP={}; POS={}; SRC={}
def bucket(src,group=''):
    src=str(src or ''); g=str(group or '')
    if 'наш генератор' in src or g.startswith('Generator'): return 'генератор'
    if 'чужой контент' in src or 'NEW' in g: return 'готовый пак'
    if 'наборы' in src or 'nabor' in g.lower() or 'аккаунт' in g or 'Вебмастера' in g: return 'наборы'
    if 'выдач' in src: return 'сайты из выдачи'
    return 'не указано'
for d,v in db.items():
    if d=='базовый домен': continue
    DAY[d]=str(v.get('made'))[:5]; GRP[d]=v.get('group') or v.get('sheet','')
    bs=v['b']; POS[d]=sum(x['t10'] for x in bs.values())
    SRC[d]=bucket(v.get('src'),v.get('group') or v.get('sheet',''))
for p in SN['pools']:
    if p.get('excl'): continue
    s=p['snaps'][-1]
    for i,x in enumerate(p['doms']):
        DAY[x]=p['ltx'][:5]; GRP[x]=p['name']; SRC[x]=bucket('',p['name'])
        POS[x]=sum(1 for r in s['rows'] if r[1]==i and r[2]<=10)
D2708={'bmtq cnwv dprz fkxb glhd hjsf 1524 1893 2367 2745 4328':'7page_1…_11 (партия 2)',
       '2139 2483 ogax byai 7186 4087 2084 2304 7440 0302':'7page_1_1…_10_1',
       '3596 b8rn c5vt d3mw f9kq f9pb h7nd j2t k6m r9v':'Generator_11page_old_27.08'}
for names,g in D2708.items():
    for x in names.split():
        DAY[x+'.team']='27.08'; GRP[x+'.team']=g
        SRC[x+'.team']='генератор' if g.startswith('Generator') else 'не указано'
# запуск 03.09 — позиций ещё нет, но день существует
for x in open('/home/user/cladue/analysis/launch_03.09.txt'):
    x=x.strip()
    if x and not x.startswith('#'):
        DAY[x]='03.09'; GRP[x]='NEW50_3 styled (четыре ветки)'; SRC[x]='готовый пак'
def dat(s):
    m=re.match(r'(\d\d)\.(\d\d)',str(s)); 
    return dt.date(2026,int(m.group(2)),int(m.group(1))) if m else None

G=collections.defaultdict(list)
for d in DAY:
    if dat(DAY[d]): G[DAY[d]].append(d)
BASE=[d for d in DAY if dat(DAY[d]) and (TODAY-dat(DAY[d])).days>=6 and dat(DAY[d])>=dt.date(2026,8,22)]
base=sum(1 for d in BASE if reg[d])/len(BASE)

DAYS=[]
for k in sorted(G,key=lambda x:dat(x)):
    ds=G[k]; a=dat(k); age=(TODAY-a).days
    n=len(ds); w=sum(1 for d in ds if reg[d]); r=sum(reg[d] for d in ds); dp=sum(dep[d] for d in ds)
    pct=CURVE[min(age,6)] if age<6 else 100
    lost=max(0,(DATA0-a).days)                      # сколько суток жизни не покрыто выгрузкой
    lostpct=CURVE[min(lost,6)] if lost else 0
    q='ok'
    if lost>0: q='усечено'
    elif age<6: q='окно открыто'
    se=100*math.sqrt(base*(1-base)/n)
    gg=collections.Counter()
    for d in ds: gg[GRP[d]]+=1
    grows=[]
    for g,c in gg.most_common():
        sub=[d for d in ds if GRP[d]==g]
        np_=sum(1 for d in sub if d in POS)
        grows.append(dict(g=g,n=c,w=sum(1 for d in sub if reg[d]),
                          r=sum(reg[d] for d in sub),
                          t10=(round(sum(POS.get(d,0) for d in sub if d in POS)/np_,1) if np_ else None)))
    DAYS.append(dict(day=k,n=n,w=w,r=r,dep=dp,share=100*w/n,rpd=r/n,age=age,pct=pct,
        lost=lost,lostpct=lostpct,q=q,se=se,z=(100*w/n-100*base)/se if se else 0,
        t10=(round(sum(POS.get(d,0) for d in ds if d in POS)/max(1,sum(1 for d in ds if d in POS)),1)
             if any(d in POS for d in ds) else None),
        npos=sum(1 for d in ds if d in POS),groups=grows,
        src=[dict(k=k,n=c,w=sum(1 for x in ds if SRC.get(x)==k and reg[x]),
                  r=sum(reg[x] for x in ds if SRC.get(x)==k))
             for k,c in collections.Counter(SRC.get(d,'не указано') for d in ds).most_common()],
        zone=[dict(k=k,n=c,w=sum(1 for x in ds if '.'+x.split('.')[-1]==k and reg[x]),
                   r=sum(reg[x] for x in ds if '.'+x.split('.')[-1]==k))
              for k,c in collections.Counter('.'+d.split('.')[-1] for d in ds).most_common()],
        proj=(r/n)/(pct/100) if pct and age<6 else None))

# дни без запусков внутри периода
have={d['day'] for d in DAYS}
gap=[]
c=dt.date(2026,8,19)
while c<=TODAY:
    if c.strftime('%d.%m') not in have: gap.append(c.strftime('%d.%m'))
    c+=dt.timedelta(days=1)

arr=collections.Counter(e['t'][:10] for e in EV if e['type']=='reg')
ARR=[dict(d=k[8:10]+'.'+k[5:7],n=v) for k,v in sorted(arr.items())]
# возраст домена на момент регистрации
agebuck=collections.Counter()
for e in EV:
    if e['type']!='reg' or e['dom'] not in DAY: continue
    a=dat(DAY[e['dom']])
    if not a: continue
    h=(dt.datetime.strptime(e['t'],'%Y-%m-%d %H:%M').date()-a).days
    if h>=0: agebuck[min(h+1,7)]+=1
AGE=[dict(d=k,n=v) for k,v in sorted(agebuck.items())]

# симуляция размаха на пригодных днях
good=[d for d in DAYS if d['q']=='ok' and d['n']>=20]
obs=max(x['share'] for x in good)-min(x['share'] for x in good)
sizes=[x['n'] for x in good]; hit=0
for _ in range(20000):
    ps=[100*sum(1 for _ in range(n) if random.random()<base)/n for n in sizes]
    if max(ps)-min(ps)>=obs: hit+=1
SIM=dict(obs=obs,p=100*hit/20000,days=[x['day'] for x in good],base=100*base)
SUM={}
for key,fn in [('src',lambda d:SRC.get(d,'не указано')),('zone',lambda d:'.'+d.split('.')[-1])]:
    agg=collections.defaultdict(lambda:[0,0,0,0])
    for d in DAY:
        if not dat(DAY[d]): continue
        e=agg[fn(d)]; e[0]+=1; e[1]+=1 if reg[d] else 0; e[2]+=reg[d]; e[3]+=dep[d]
    closed=collections.defaultdict(lambda:[0,0,0])
    for d in BASE:
        e=closed[fn(d)]; e[0]+=1; e[1]+=1 if reg[d] else 0; e[2]+=reg[d]
    SUM[key]=sorted([dict(k=k,n=v[0],w=v[1],r=v[2],dep=v[3],
                          cn=closed[k][0],cw=closed[k][1],cr=closed[k][2])
                     for k,v in agg.items()],key=lambda x:-x['n'])
json.dump(dict(days=DAYS,sum=SUM,gap=gap,arr=ARR,age=AGE,sim=SIM,curve=CURVE,
               reg=sum(reg.values()),dep=sum(dep.values()),
               built=dt.datetime.now().strftime('%d.%m %H:%M')),
          open(SP+'days.json','w'),ensure_ascii=False)
print('дней:',len(DAYS),'| без запусков:',gap)
for x in DAYS:
    print(f"  {x['day']}  дом {x['n']:>3}  рег {x['r']:>3}  доля {x['share']:>5.1f}%  "
          f"возраст {x['age']} сут ({x['pct']}% окна)  {x['q']:<12} групп {len(x['groups'])}")
print('симуляция:',SIM)
