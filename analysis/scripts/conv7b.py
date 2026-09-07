# Что новая выгрузка (05-07.09) даёт по дням запуска и по подтверждённым рычагам.
import json,collections,re,datetime as dt,glob,os
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
AN='/home/user/cladue/analysis/'
BAD={'yandex.ru','—','ru.search.yahoo.com','alice.yandex.ru'}
EV=[e for e in json.load(open(SP+'convall.json')) if e['dom'] not in BAD]
M=json.load(open(SP+'dommap.json'))
def clean(g):
    g=re.sub(r'\s*[—,]\s*(id|создан).*$','',g or '')
    return re.sub(r'_?\d*…_\d+','',g).strip(' _')

# знаменатель: все запущенные домены по дням из launch_*.txt + реестр
DAY=collections.defaultdict(list); GRP=collections.defaultdict(list)
for f in sorted(glob.glob(AN+'launch_*.txt')):
    if '_flat' in f: continue
    d=re.search(r'launch_(\d\d\.\d\d)',f)
    if not d: continue
    d=d.group(1)
    cur=None
    for l in open(f):
        l=l.rstrip()
        if l.startswith('## '): cur=l[3:]
        elif re.match(r'^[a-z0-9\-]+\.[a-z]+$',l.strip()):
            x=l.strip()
            if x not in DAY[d]: DAY[d].append(x)          # 31.08/26.08 описаны в двух файлах
            if x not in GRP[(d,cur)]: GRP[(d,cur)].append(x)

reg=collections.Counter(); dep=collections.Counter()
for e in EV:
    (reg if e['type']=='reg' else dep)[e['dom']]+=1

TODAY=dt.date(2026,9,7)
def dd(s):
    m,dnum=s.split('.'); return dt.date(2026,int(dnum),int(m))
print('=== ДНИ ЗАПУСКА: доля доменов с регистрацией (данные по 07.09) ===')
print(f"{'день':<8}{'доменов':>8}{'с рег':>7}{'доля':>8}{'рег':>6}{'деп':>5}   окно")
for d in sorted(DAY,key=dd):
    doms=DAY[d]; wr=sum(1 for x in doms if reg[x]); r=sum(reg[x] for x in doms); p=sum(dep[x] for x in doms)
    age=(TODAY-dd(d)).days
    w='закрыто' if age>=6 else f'открыто, день {age} из 6'
    print(f"{d:<8}{len(doms):>8}{wr:>7}{100*wr/len(doms):>7.1f}%{r:>6}{p:>5}   {w}")

print('\n=== ТОЛЬКО СВЕЖИЕ ДНИ 04-06.09: разбивка по группам ===')
print(f"{'день':<7}{'группа':<46}{'дом':>4}{'с рег':>6}{'рег':>5}{'деп':>5}")
for (d,g),doms in sorted(GRP.items(),key=lambda x:(dd(x[0][0]),x[0][1] or '')):
    if d not in ('04.09','05.09','06.09'): continue
    gn=re.sub(r'\s*—\s*id.*$','',g or '?'); gn=re.sub(r'_1…_\d+$','',gn)
    wr=sum(1 for x in doms if reg[x]); r=sum(reg[x] for x in doms); p=sum(dep[x] for x in doms)
    print(f"{d:<7}{gn[:44]:<46}{len(doms):>4}{wr:>6}{r:>5}{p:>5}")

CURVE=[0,18,49,75,90,95,99]
print('\n=== ПРОЕКЦИЯ НА ЗАКРЫТОЕ ОКНО (кривая накопления) ===')
print(f"{'день':<8}{'дом':>5}{'с рег':>6}{'факт':>8}{'% окна':>8}{'прогноз':>9}")
proj={}
for d in sorted(DAY,key=dd):
    doms=DAY[d]; wr=sum(1 for x in doms if reg[x]); age=(TODAY-dd(d)).days
    c=CURVE[min(age,6)]
    if c==0: continue
    f=100*wr/len(doms); pr=f*99/c
    proj[d]=pr
    print(f"{d:<8}{len(doms):>5}{wr:>6}{f:>7.1f}%{c:>7}%{pr:>8.1f}%")

print('\n=== 12 vs 7 страниц: только семейства NEW*, дни 04-06.09 ===')
fam=collections.defaultdict(lambda:[0,0,0])
for (d,g),doms in GRP.items():
    if d not in ('04.09','05.09','06.09') or not g: continue
    m=re.search(r'(\d+)pages',g)
    if not m: continue
    k=(m.group(1)+' стр','withdate' if 'withdate' in g else 'nodate')
    a=fam[k]; a[0]+=len(doms); a[1]+=sum(1 for x in doms if reg[x]); a[2]+=sum(reg[x] for x in doms)
for k in sorted(fam):
    n,w,r=fam[k]; print(f"  {k[0]}, {k[1]:<9} доменов {n:>3}  с рег {w:>2}  {100*w/n:>5.1f}%  рег {r}")
for ax,f in (('страницы',lambda k:k[0]),('даты',lambda k:k[1])):
    agg=collections.defaultdict(lambda:[0,0])
    for k,(n,w,r) in fam.items(): a=agg[f(k)]; a[0]+=n; a[1]+=w
    print(f"  --- {ax}: "+' | '.join(f"{k} {w}/{n} = {100*w/n:.1f}%" for k,(n,w) in sorted(agg.items())))

from math import comb
def fisher(a,b,c,d):
    n=a+b+c+d; r1=a+b; c1=a+c
    tot=comb(n,r1); p=0
    obs=comb(c1,a)*comb(n-c1,b)
    for x in range(max(0,r1-(n-c1)),min(r1,c1)+1):
        v=comb(c1,x)*comb(n-c1,r1-x)
        if v<=obs+1e-9: p+=v
    return p/tot
print(f"\n  двусторонний Fisher для 5/30 vs 1/30: p = {fisher(5,25,1,29):.3f}")

print('\n=== ДЕПОЗИТЫ за всю историю ===')
dm=collections.Counter()
for e in EV:
    if e['type']=='dep': dm[e['dom']]+=1
print(f"  всего депозитов {sum(dm.values())} на {len(dm)} доменах; с 2+ депами: {sum(1 for v in dm.values() if v>1)}")
for d,v in dm.most_common():
    m=M.get(d,{}); print(f"    {d:<18}{v:>2} деп, рег {reg[d]:>2}  {m.get('day','?'):<8}{re.sub(r'  *—  *id.*','',m.get('g','—'))[:44]}")

print('\n=== ЛАГ ДЕПОЗИТА ОТ РЕГИСТРАЦИИ (тот же домен+бренд) ===')
import datetime as DT
byd=collections.defaultdict(list)
for e in EV: byd[(e['dom'],e['sub'])].append(e)
lags=[]
for k,es in byd.items():
    rs=sorted(x['t'] for x in es if x['type']=='reg'); ds=sorted(x['t'] for x in es if x['type']=='dep')
    for d in ds:
        pr=[r for r in rs if r<=d]
        if not pr: lags.append(None); continue
        a=DT.datetime.strptime(pr[-1],'%Y-%m-%d %H:%M'); b=DT.datetime.strptime(d,'%Y-%m-%d %H:%M')
        lags.append((b-a).total_seconds()/3600)
ok=[x for x in lags if x is not None]
print(f"  депозитов {len(lags)}, из них с найденной регистрацией {len(ok)}, без неё {len(lags)-len(ok)}")
buck=collections.Counter()
for x in ok: buck['< 1 ч' if x<1 else '1-6 ч' if x<6 else '6-24 ч' if x<24 else '1-3 сут' if x<72 else '> 3 сут']+=1
for k in ['< 1 ч','1-6 ч','6-24 ч','1-3 сут','> 3 сут']:
    print(f"    {k:<10}{buck[k]:>3}")
print(f"  медиана {sorted(ok)[len(ok)//2]:.1f} ч, максимум {max(ok):.0f} ч")

print('\n=== 31.08 — самый высокий день (40%), состав ===')
for (d,g),doms in sorted(GRP.items(),key=lambda x:(x[0][0],x[0][1] or '')):
    if d!='31.08': continue
    wr=sum(1 for x in doms if reg[x])
    print(f"  {re.sub(r'  *—  *id.*','',g or '?')[:50]:<52}{len(doms):>3} дом, с рег {wr:>2}, рег {sum(reg[x] for x in doms):>2}, деп {sum(dep[x] for x in doms)}")

# ── данные для вкладки «Новая выгрузка» в отчёте по дням
NEW=json.load(open(SP+'conv7.json'))
NEW=[e for e in NEW if e['dom'] not in BAD]
drows=[]
dm2=collections.Counter(e['dom'] for e in EV if e['type']=='dep')
for d,v in dm2.most_common():
    m=M.get(d,{})
    drows.append(dict(d=d,dep=v,reg=reg[d],day=m.get('day','?'),
                      g=clean(m.get('g','—'))))
nrows=[]
agg=collections.defaultdict(lambda:[0,0,collections.Counter()])
for e in NEW:
    a=agg[e['dom']]; a[0]+= e['type']=='reg'; a[1]+= e['type']=='dep'; a[2][e['sub']]+=1
for d,(r,p,br) in sorted(agg.items(),key=lambda x:(-x[1][1],-x[1][0])):
    m=M.get(d)
    nrows.append(dict(d=d,r=r,p=p,day=m['day'] if m else None,
                      g=clean(m['g']) if m else None,
                      br=[[b,n] for b,n in br.most_common()]))
FRESH=dict(
  n=len(NEW),reg=sum(1 for e in NEW if e['type']=='reg'),dep=sum(1 for e in NEW if e['type']=='dep'),
  days=[[k,v] for k,v in sorted(collections.Counter(e['t'][:10] for e in NEW).items())],
  skipped=[[k,v] for k,v in sorted(collections.Counter(
      e['dom'] for e in json.load(open(SP+'conv7.json')) if e['dom'] in BAD).items())],
  rows=nrows, deps=drows,
  lag=dict(b=[[k,buck[k]] for k in ['< 1 ч','1-6 ч','6-24 ч','1-3 сут','> 3 сут']],
           med=round(sorted(ok)[len(ok)//2],1),mx=round(max(ok)),n=len(ok),orphan=len(lags)-len(ok)),
  fam=[dict(p=k[0],dt=k[1],n=v[0],w=v[1],r=v[2]) for k,v in sorted(fam.items())],
  fisher=round(fisher(5,25,1,29),3))
json.dump(FRESH,open(SP+'fresh.json','w'),ensure_ascii=False)
print(f"\nfresh.json: {len(nrows)} доменов, {len(drows)} с депозитами")
