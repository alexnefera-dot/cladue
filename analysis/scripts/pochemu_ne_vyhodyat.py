#!/usr/bin/env python3
"""Почему 86% сайтов не выходят в поиск.

Восемь проверок подряд, каждая снимает по одному объяснению:

1. это вопрос времени — доля дошедших за 1, 3, 7, 14 и 30 суток;
2. это отдельные мёртвые базы или ровный провал по всем;
3. что объясняет провал сильнее — база, бренд, контент, зона или день;
4. доходят ли они вообще до переобхода (пайплайн и верификация);
5. как выход в поиск распределён по брендам;
6. сколько провала остаётся, если снять брендов-аутсайдеров;
7. что решает внутри хорошего бренда;
8. то же в фиксированном окне трёх суток, где день перестаёт мешать.

Сила фактора меряется хи-квадратом однородности, делённым на число степеней
свободы: у фактора с двумя сотнями уровней и у фактора с двумя это делает
числа сравнимыми.

    python3 pochemu_ne_vyhodyat.py
"""
import json,collections,datetime,statistics,math
S='/tmp/claude-0/-home-user-cladue/de95974e-6e28-5d1d-820f-f09c0d0e2b43/scratchpad/'
P={}
for line in open(S+'klikprof2.jsonl',encoding='utf-8'):
    a=json.loads(line); P[a[0]]=a[1:]
rows=[]
for line in open('/tmp/panel_25.jsonl',encoding='utf-8'):
    r=json.loads(line)
    d=(r.get('recrawl_sent_at') or '')[:10]
    b=r.get('content_domain_url')
    if not d or not b: continue
    p=P.get(r['subdomain'],[0,0,0,0,None,None,None,None])
    yaf=p[4]
    lag=(datetime.date.fromisoformat(yaf)-datetime.date.fromisoformat(d)).days if yaf else None
    rows.append({'sub':r['subdomain'],'base':b,'day':d,'brand':r.get('brand_label'),
        'tld':r.get('tld'),'content':r.get('content') or 'НЕ ЗАПИСАН',
        'stage':r.get('yandex_pipeline_stage'),'ver':r.get('verification_status'),
        'vfail':r.get('verification_fail_count') or 0,
        'n':p[0],'bot':p[1],'ya':p[2],'lag':lag,'reg':r.get('reg',0)})
LAST=datetime.date(2026,9,21)
print('=== 1. ЭТО ВОПРОС ВРЕМЕНИ?  доля сайтов, дошедших до поиска за K суток')
for K in (1,3,7,14,30):
    e=[r for r in rows if (LAST-datetime.date.fromisoformat(r['day'])).days>=K]
    h=sum(1 for r in e if r['lag'] is not None and 0<=r['lag']<=K)
    print('   %2d суток: %5.1f%%  (досмотрено %d сайтов)'%(K,100*h/len(e),len(e)))
ever=sum(1 for r in rows if r['ya'])
print('   когда-либо, без ограничения по сроку: %.1f%% (%d из %d)'%(100*ever/len(rows),ever,len(rows)))

print('\n=== 2. ЭТО РОВНО РАЗМАЗАНО ПО БАЗАМ ИЛИ ЕСТЬ ЖИВЫЕ И МЁРТВЫЕ БАЗЫ?')
bb=collections.defaultdict(lambda:[0,0])
for r in rows:
    t=bb[r['base']]; t[0]+=1
    if r['ya']: t[1]+=1
sh=sorted(100*t[1]/t[0] for t in bb.values())
print('   баз %d; доля сайтов с поиском по базе:'%len(sh))
for q,name in ((0,'минимум'),(10,'10-й процентиль'),(25,'четверть'),(50,'медиана'),
               (75,'три четверти'),(90,'90-й процентиль'),(100,'максимум')):
    i=min(len(sh)-1,int(q/100*len(sh)))
    print('     %-18s %5.1f%%'%(name,sh[i]))
print('   баз, где до поиска не дошёл НИ ОДИН сайт: %d'%sum(1 for x in sh if x==0))
print('   баз, где дошло меньше 5%% сайтов: %d'%sum(1 for x in sh if x<5))

print('\n=== 3. КТО ОБЪЯСНЯЕТ ПРОВАЛ: БАЗА, БРЕНД ИЛИ КОНТЕНТ?')
def between(keyf,name):
    g=collections.defaultdict(lambda:[0,0])
    for r in rows:
        t=g[keyf(r)]; t[0]+=1; t[1]+= 1 if r['ya'] else 0
    p=sum(t[1] for t in g.values())/sum(t[0] for t in g.values())
    # избыточный разброс сверх биномиального
    obs=sum((t[1]-t[0]*p)**2/(t[0]*p*(1-p)) for t in g.values() if t[0])
    df=len(g)-1
    print('   %-12s групп %5d, хи-квадрат %9.0f при df %5d, отношение %6.1f'%(
        name,len(g),obs,df,obs/df if df else 0))
between(lambda r:r['base'],'база')
between(lambda r:r['brand'],'бренд')
between(lambda r:r['content'],'контент')
between(lambda r:r['tld'],'зона')
between(lambda r:r['day'],'день')

print('\n=== 4. ПАЙПЛАЙН: ДОШЛИ ЛИ ОНИ ВООБЩЕ ДО ПЕРЕОБХОДА')
c=collections.Counter()
for r in rows:
    k=('вышел' if r['ya'] else 'не вышел')
    c[(k,r['stage'])]+=1
    c[(k,'верификация '+str(r['ver']))]+=1
    c[(k,'ошибки верификации' if r['vfail'] else 'без ошибок верификации')]+=1
for k in sorted(c):
    print('   %-12s %-28s %7d'%(k[0],k[1],c[k]))

print('\n=== 5. РАСПРЕДЕЛЕНИЕ ПО БРЕНДАМ: КТО ВООБЩЕ ВЫХОДИТ В ПОИСК')
br=collections.defaultdict(lambda:[0,0,0,0])
for r in rows:
    t=br[r['brand']]; t[0]+=1; t[1]+= 1 if r['ya'] else 0; t[2]+=r['ya']; t[3]+=r['reg']
o=sorted(br.items(),key=lambda x:-x[1][1]/x[1][0])
print('   %-22s %8s %9s %10s %6s'%('бренд','сайтов','вышли %','кликов','рег'))
for b,t in o[:12]:
    print('   %-22s %8d %8.1f%% %10d %6d'%(str(b)[:22],t[0],100*t[1]/t[0],t[2],t[3]))
print('   ...')
for b,t in o[-8:]:
    print('   %-22s %8d %8.1f%% %10d %6d'%(str(b)[:22],t[0],100*t[1]/t[0],t[2],t[3]))
sh=[100*t[1]/t[0] for _,t in o]
print('\n   медиана по брендам %.1f%%, верхняя четверть от %.1f%%, нижняя до %.1f%%'%(
    statistics.median(sh),sh[len(sh)//4],sh[3*len(sh)//4]))
tot=sum(t[1] for _,t in o)
cum=0
for i,(b,t) in enumerate(o,1):
    cum+=t[1]
    if cum>=tot/2:
        print('   половину всех вышедших в поиск сайтов дают %d брендов из %d'%(i,len(o)))
        break
z=sum(1 for _,t in o if t[1]/t[0]<0.02)
print('   брендов, у которых в поиск выходит меньше 2%% сайтов: %d (сайтов под ними %d)'%(
    z,sum(t[0] for _,t in o if t[1]/t[0]<0.02)))

print('\n=== 6. ЕСЛИ УБРАТЬ БРЕНДЫ-АУТСАЙДЕРЫ, СКОЛЬКО ОСТАЁТСЯ ПРОВАЛА')
good=[b for b,t in br.items() if t[1]/t[0]>=0.10]
gs=sum(br[b][0] for b in good); gh=sum(br[b][1] for b in good)
print('   брендов с выходом 10%%+: %d, сайтов %d, выход %.1f%%'%(len(good),gs,100*gh/gs))
print('   остальные %d брендов: сайтов %d, выход %.1f%%'%(
    len(br)-len(good),len(rows)-gs,100*(sum(t[1] for t in br.values())-gh)/(len(rows)-gs)))

print('\n=== 7. ВНУТРИ ХОРОШЕГО БРЕНДА — ЧТО РЕШАЕТ ДАЛЬШЕ')
top={b for b,t in br.items() if t[1]/t[0]>=0.25}
sub=[r for r in rows if r['brand'] in top]
print('   сайтов у брендов с выходом 25%%+: %d, из них вышли %.1f%%'%(
    len(sub),100*sum(1 for r in sub if r['ya'])/len(sub)))
for keyf,name in ((lambda r:r['tld'],'зона'),(lambda r:r['content'],'контент'),
                  (lambda r:r['base'],'база'),(lambda r:r['day'],'день')):
    g=collections.defaultdict(lambda:[0,0])
    for r in sub:
        t=g[keyf(r)]; t[0]+=1; t[1]+= 1 if r['ya'] else 0
    p=sum(t[1] for t in g.values())/sum(t[0] for t in g.values())
    obs=sum((t[1]-t[0]*p)**2/(t[0]*p*(1-p)) for t in g.values() if t[0])
    df=len(g)-1
    print('     %-10s групп %5d, хи-квадрат/df %7.1f'%(name,len(g),obs/df if df else 0))

print('\n=== 8. ТО ЖЕ, НО В ФИКСИРОВАННОМ ОКНЕ ТРЁХ СУТОК (день перестаёт мешать)')
EDGE='2026-09-18'
E=[r for r in rows if r['day']<=EDGE]
for r in E: r['hit3']=1 if (r['lag'] is not None and 0<=r['lag']<=3) else 0
p=sum(r['hit3'] for r in E)/len(E)
print('   сайтов в расчёте %d, выход %.1f%%'%(len(E),100*p))
def chi(keyf,name):
    g=collections.defaultdict(lambda:[0,0])
    for r in E:
        t=g[keyf(r)]; t[0]+=1; t[1]+=r['hit3']
    obs=sum((t[1]-t[0]*p)**2/(t[0]*p*(1-p)) for t in g.values() if t[0])
    df=len(g)-1
    print('   %-10s групп %5d, хи-квадрат/df %8.1f'%(name,len(g),obs/df if df else 0))
chi(lambda r:r['brand'],'бренд')
chi(lambda r:r['day'],'день')
chi(lambda r:r['tld'],'зона')
chi(lambda r:r['content'],'контент')
chi(lambda r:r['base'],'база')
print('\n   бренд внутри дня и контента (страта «контент+день»):')
sp=collections.defaultdict(lambda:[0,0])
for r in E:
    t=sp[(r['content'],r['day'])]; t[0]+=1; t[1]+=r['hit3']
g=collections.defaultdict(lambda:[0,0,0.0])
for r in E:
    n,h=sp[(r['content'],r['day'])]     # n — сайтов в страте, h — вышедших
    if n<60: continue
    t=g[r['brand']]; t[0]+=1; t[1]+=r['hit3']; t[2]+= h/n
o=sorted(g.items(),key=lambda x:-(x[1][1]/x[1][2] if x[1][2] else 0))
print('   %-22s %8s %9s %9s'%('бренд','сайтов','выход %','к страте'))
for b,t in o[:10]:
    print('   %-22s %8d %8.1f%% %9.2f'%(str(b)[:22],t[0],100*t[1]/t[0],t[1]/t[2] if t[2] else 0))
print('   ...')
for b,t in o[-8:]:
    print('   %-22s %8d %8.1f%% %9.2f'%(str(b)[:22],t[0],100*t[1]/t[0],t[1]/t[2] if t[2] else 0))
