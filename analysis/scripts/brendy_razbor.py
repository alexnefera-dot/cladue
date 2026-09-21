#!/usr/bin/env python3
"""Разбор брендов: девять проверок, каждая против одной из прежних гипотез.

1. выход бренда — устойчивое свойство или шум (расщепление пополам и проверка
   вне выборки: ранжируем по августу, меряем по сентябрю);
2. спрос или подача — меняется ли бренд от зоны и контента;
3. выход и деньги — это одни и те же бренды;
4. 55 брендов остатка — дело в позиции или в бренде;
5. что в имени бренда;
6. регистрации на сайт по третям выхода — главная таблица;
7. кто даёт деньги;
8. бренд внутри контента;
9. что даст перераспределение.

Единица — сайт, окно трёх суток, запуски по 18.09 (у более поздних окно не
закрыто).

    python3 brendy_razbor.py
"""
import json,collections,re,math,random,statistics
S='/tmp/claude-0/-home-user-cladue/de95974e-6e28-5d1d-820f-f09c0d0e2b43/scratchpad/'
W={}
for line in open(S+'okno3.jsonl',encoding='utf-8'):
    a=json.loads(line); W[a[0]]=a[1:]
rows=[];bd=collections.defaultdict(set)
for line in open('/tmp/panel_25.jsonl',encoding='utf-8'):
    r=json.loads(line)
    d=(r.get('recrawl_sent_at') or '')[:10]; b=r.get('content_domain_url')
    if not d or not b or d>'2026-09-18': continue
    bd[b].add(d)
    w=W.get(r['subdomain'],[0,0,0,0,0])
    rows.append({'base':b,'day':d,'tld':r.get('tld'),'brand':r.get('brand_label'),
        'lab':r.get('subdomain_label') or r['subdomain'].split('.')[0],
        'content':re.sub(r'[_\-]\d+$','',r.get('content') or 'НЕ ЗАПИСАН'),
        'hit':1 if w[2] else 0,'cl':w[2],'reg':w[3],'fd':w[4]})
order={b:{d:i for i,d in enumerate(sorted(ds))} for b,ds in bd.items()}
for r in rows: r['wave']=min(order[r['base']][r['day']],1)
def spear(a,b):
    def rk(v):
        s=sorted(range(len(v)),key=lambda i:v[i]);r=[0.0]*len(v);i=0
        while i<len(s):
            j=i
            while j+1<len(s) and v[s[j+1]]==v[s[i]]: j+=1
            m=(i+j)/2+1
            for t in range(i,j+1): r[s[t]]=m
            i=j+1
        return r
    ra,rb=rk(a),rk(b);n=len(a);ma=sum(ra)/n;mb=sum(rb)/n
    num=sum((ra[i]-ma)*(rb[i]-mb) for i in range(n))
    den=math.sqrt(sum((x-ma)**2 for x in ra)*sum((x-mb)**2 for x in rb))
    return num/den if den else 0

print('=== 1. ВЫХОД БРЕНДА — УСТОЙЧИВОЕ СВОЙСТВО ИЛИ ШУМ')
br=collections.defaultdict(list)
for r in rows: br[r['brand']].append(r['hit'])
random.seed(5)
A=[];B=[]
for b,v in br.items():
    if len(v)<400: continue
    v=v[:]; random.shuffle(v); h=len(v)//2
    A.append(sum(v[:h])/h); B.append(sum(v[h:])/len(v[h:]))
print('  расщепление пополам внутри бренда: Спирмен %.2f (брендов %d)'%(spear(A,B),len(A)))
ag=collections.defaultdict(lambda:[0,0]); sp=collections.defaultdict(lambda:[0,0])
for r in rows:
    t=(ag if r['day'][:7]=='2026-08' else sp)[r['brand']]
    t[0]+=r['hit']; t[1]+=1
both=[b for b in ag if ag[b][1]>=200 and sp[b][1]>=200]
print('  август против сентября (вне выборки): Спирмен %.2f (брендов %d)'%(
    spear([ag[b][0]/ag[b][1] for b in both],[sp[b][0]/sp[b][1] for b in both]),len(both)))
q=sorted(both,key=lambda b:-ag[b][0]/ag[b][1])
k=len(q)//4
print('    верхняя четверть по августу -> в сентябре %.1f%%'%(
    100*sum(sp[b][0] for b in q[:k])/sum(sp[b][1] for b in q[:k])))
print('    нижняя четверть по августу  -> в сентябре %.1f%%'%(
    100*sum(sp[b][0] for b in q[-k:])/sum(sp[b][1] for b in q[-k:])))

print('\n=== 2. ЭТО СПРОС ИЛИ ПОДАЧА: одинаков ли бренд в разных зонах и контентах')
for keyf,nm in ((lambda r:r['tld'],'зона'),(lambda r:r['content'],'контент')):
    g=collections.defaultdict(lambda:[0,0])
    for r in rows: 
        t=g[(r['brand'],keyf(r))]; t[0]+=r['hit']; t[1]+=1
    pairs=collections.defaultdict(list)
    for (b,k),t in g.items():
        if t[1]>=300: pairs[b].append(t[0]/t[1])
    v=[x for x in pairs.values() if len(x)>=2]
    rng=[max(x)/min(x) if min(x)>0 else None for x in v]
    ok=[x for x in rng if x is not None]
    print('  %-8s брендов с двумя+ уровнями: %3d, медиана отношения лучший/худший %.1f'%(
        nm,len(v),statistics.median(ok) if ok else 0))

print('\n=== 3. ВЫХОД И ДЕНЬГИ — ЭТО ОДНИ И ТЕ ЖЕ БРЕНДЫ?')
m=collections.defaultdict(lambda:[0,0,0,0])
for r in rows:
    t=m[r['brand']]; t[0]+=r['hit']; t[1]+=1; t[2]+=r['cl']; t[3]+=r['reg']
sel=[b for b,t in m.items() if t[2]>=1500]
print('  брендов с 1500+ кликами: %d'%len(sel))
print('  Спирмен «выход в поиск ↔ регистраций на 10 тыс. кликов»: %.2f'%spear(
    [m[b][0]/m[b][1] for b in sel],[10000*m[b][3]/m[b][2] for b in sel]))
top=sorted(sel,key=lambda b:-m[b][0]/m[b][1])[:len(sel)//3]
bot=sorted(sel,key=lambda b:m[b][0]/m[b][1])[:len(sel)//3]
for nm,g in (('треть с лучшим выходом',top),('треть с худшим выходом',bot)):
    t=[sum(m[b][i] for b in g) for i in range(4)]
    print('    %-24s выход %5.1f%%, кликов %7d, рег %3d, рег/10т %.1f'%(
        nm,100*t[0]/t[1],t[2],t[3],10000*t[3]/t[2] if t[2] else 0))

print('\n=== 4. 55 БРЕНДОВ ОСТАТКА: ПОЗИЦИЯ ИЛИ БРЕНД')
w2=collections.defaultdict(lambda:[0,0])
for r in rows:
    t=w2[r['brand']]; t[0]+=r['wave']; t[1]+=1
late={b for b,t in w2.items() if t[0]/t[1]>0.9}
early={b for b,t in w2.items() if t[0]/t[1]<0.1}
for nm,s in (('всегда в первых 150',early),('всегда в остатке 56',late)):
    t=[0,0,0,0]
    for r in rows:
        if r['brand'] in s:
            t[0]+=r['hit']; t[1]+=1; t[2]+=r['cl']; t[3]+=r['reg']
    print('  %-22s брендов %3d, сайтов %6d, выход %5.1f%%, рег %3d, рег/10т %.1f'%(
        nm,len(s),t[1],100*t[0]/t[1],t[3],10000*t[3]/t[2] if t[2] else 0))
print('  те же бренды в августе (когда порядок мог быть другим):')
for nm,s in (('первые 150',early),('остаток 56',late)):
    t=[0,0]
    for r in rows:
        if r['brand'] in s and r['day'][:7]=='2026-08': t[0]+=r['hit']; t[1]+=1
    print('    %-12s сайтов %6d, выход %5.1f%%'%(nm,t[1],100*t[0]/t[1] if t[1] else 0))

print('\n=== 5. ЧТО В ИМЕНИ БРЕНДА')
feat=collections.defaultdict(lambda:[0,0])
for r in rows:
    lab=r['lab']
    for k,cond in (('кириллица в имени бренда',bool(re.search(r'[а-яё]',str(r['brand']),re.I))),
                   ('цифры в сабдомене',bool(re.search(r'\d',lab))),
                   ('длина метки <= 5',len(lab)<=5),
                   ('длина метки 6-9',6<=len(lab)<=9),
                   ('длина метки 10+',len(lab)>=10)):
        if cond:
            t=feat[k]; t[0]+=r['hit']; t[1]+=1
tot=sum(r['hit'] for r in rows)/len(rows)
print('  всего выход %.1f%%'%(100*tot))
for k,t in sorted(feat.items(),key=lambda x:-x[1][0]/x[1][1]):
    print('  %-28s сайтов %7d, выход %5.1f%%, к среднему %.2f'%(k,t[1],100*t[0]/t[1],(t[0]/t[1])/tot))

print('\n=== 6. ГЛАВНОЕ: РЕГИСТРАЦИИ НА САЙТ ПО ТРЕТЯМ ВЫХОДА')
sel2=[b for b,t in m.items() if t[1]>=800]
srt=sorted(sel2,key=lambda b:-m[b][0]/m[b][1])
k=len(srt)//3
print('  %-26s %5s %8s %8s %9s %6s %10s %12s'%('треть по выходу','брендов','сайтов','выход %','кликов','рег','рег/10т кл','рег на 100 сайтов'))
for nm,g in (('лучшая треть по выходу',srt[:k]),('средняя',srt[k:2*k]),('худшая треть по выходу',srt[2*k:])):
    t=[sum(m[b][i] for b in g) for i in range(4)]
    print('  %-26s %5d %8d %7.1f%% %9d %6d %10.1f %12.3f'%(
        nm,len(g),t[1],100*t[0]/t[1],t[2],t[3],10000*t[3]/t[2] if t[2] else 0,100*t[3]/t[1]))
print('\n  то же, но десятками брендов:')
print('  %-14s %8s %8s %9s %6s %12s'%('десятка','сайтов','выход %','кликов','рег','рег на 100'))
for i in range(0,len(srt)-9,20):
    g=srt[i:i+20]
    t=[sum(m[b][j] for b in g) for j in range(4)]
    print('  %-14s %8d %7.1f%% %9d %6d %12.3f'%('%d-%d'%(i+1,i+len(g)),t[1],100*t[0]/t[1],t[2],t[3],100*t[3]/t[1]))

print('\n=== 7. КТО ДАЁТ ДЕНЬГИ: ТОП-20 ПО РЕГИСТРАЦИЯМ НА СТО САЙТОВ')
rich=sorted([b for b,t in m.items() if t[1]>=800 and t[3]>0],key=lambda b:-m[b][3]/m[b][1])
print('  %-22s %8s %8s %9s %6s %12s %10s'%('бренд','сайтов','выход %','кликов','рег','рег на 100','рег/10т кл'))
for b in rich[:20]:
    t=m[b]
    print('  %-22s %8d %7.1f%% %9d %6d %12.3f %10.1f'%(str(b)[:22],t[1],100*t[0]/t[1],t[2],t[3],100*t[3]/t[1],10000*t[3]/t[2]))
print('  ... брендов без регистраций: %d'%sum(1 for b,t in m.items() if t[1]>=800 and t[3]==0))

print('\n=== 8. БРЕНД ВНУТРИ КОНТЕНТА — порог ниже')
g=collections.defaultdict(lambda:[0,0])
for r in rows:
    t=g[(r['brand'],r['content'])]; t[0]+=r['hit']; t[1]+=1
pairs=collections.defaultdict(list)
for (b,c),t in g.items():
    if t[1]>=120: pairs[b].append(t[0]/t[1])
v=[x for x in pairs.values() if len(x)>=3]
rng=[max(x)/min(x) for x in v if min(x)>0]
print('  брендов с тремя+ контентами по 120+ сайтов: %d'%len(v))
print('  медиана отношения лучший контент/худший внутри бренда: %.1f'%(statistics.median(rng) if rng else 0))
print('  для сравнения: отношение лучшего бренда к худшему внутри контента — сотни раз')

print('\n=== 9. ЧТО ДАЁТ ПЕРЕРАСПРЕДЕЛЕНИЕ')
tot_sites=sum(m[b][1] for b in m); tot_reg=sum(m[b][3] for b in m)
print('  сейчас: %d сайтов, %d регистраций, %.3f на сто сайтов'%(tot_sites,tot_reg,100*tot_reg/tot_sites))
sel3=[b for b,t in m.items() if t[1]>=800]
srt3=sorted(sel3,key=lambda b:-m[b][0]/m[b][1])
def rate(g):
    s=sum(m[b][1] for b in g); r=sum(m[b][3] for b in g)
    return r/s if s else 0,s,r
for cut in (60,80,100):
    drop=srt3[-cut:]
    keep=[b for b in sel3 if b not in set(drop)]
    kr,ks,krg=rate(keep); dr,ds,drg=rate(drop)
    print('  снять %d худших по выходу: освободится %d сайтов (%.0f%%), потеряется %d рег;'
          ' на ставке оставшихся вернётся %.0f -> прирост %+.0f (%+.0f%%)'%(
        cut,ds,100*ds/tot_sites,drg,ds*kr,ds*kr-drg,100*(ds*kr-drg)/tot_reg))
best=sorted(sel3,key=lambda b:-m[b][3]/m[b][1])
for n in (40,60,80):
    g=best[:n]; br_,bs,brg=rate(g)
    print('  отдать всё %d лучшим ПО РЕГИСТРАЦИЯМ НА САЙТ (ставка %.3f): %d сайтов дали бы %.0f рег (%+.0f%%)'%(
        n,100*br_,tot_sites,tot_sites*br_,100*(tot_sites*br_-tot_reg)/tot_reg))
print('\n  осторожно: ставка лучших брендов измерена на них самих; при переносе объёма')
print('  она почти наверняка упадёт — спрос на бренд не растёт от того, что ему дали больше сайтов')
