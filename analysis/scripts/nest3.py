# Между соседними замерами: если у ключа выросла вложенность — вырос ли он в позиции?
# Отдельно по всем ключам и отдельно по ВЧ/СЧ.
import json,statistics as st,collections
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
D=json.load(open(SP+'snapr.json')); QD=D['qd']; PD=D['pd']
VS=('ВЧ','СЧ')
PAIRS=[]
for p in D['pools']:
    if p.get('excl'): continue
    for i in range(len(p['snaps'])-1):
        A={(r[0],r[1]):r for r in p['snaps'][i]['rows']}
        B={(r[0],r[1]):r for r in p['snaps'][i+1]['rows']}
        for k in set(A)&set(B):
            a,b=A[k],B[k]
            if a[3]<0 or b[3]<0: continue
            PAIRS.append(dict(pool=p['id'],lab=p['snaps'][i]['lab']+'→'+p['snaps'][i+1]['lab'],
                q=QD[a[0]][0],br=QD[a[0]][1],t=QD[a[0]][2],dom=p['doms'][a[1]],
                p0=a[2],p1=b[2],dp=b[2]-a[2],d0=a[3],d1=b[3],dd=b[3]-a[3],
                pg0=PD[a[4]],pg1=PD[b[4]],pgch=a[4]!=b[4]))
def bucket(x):
    if x<0: return 'стала мельче'
    if x==0: return 'не менялась'
    if x<=5: return 'глубже на 1–5'
    if x<=15: return 'глубже на 6–15'
    return 'глубже на 16+'
ORD=['стала мельче','не менялась','глубже на 1–5','глубже на 6–15','глубже на 16+']
def rep(rows,title):
    print('\n===',title,f'— всего пар ключ×домен: {len(rows)}')
    print(f"{'что стало с вложенностью':<20}{'пар':>6}{'медиана сдвига':>16}{'выросли':>10}{'упали':>8}"
          f"{'зашли в Т10':>13}{'вылетели из Т10':>17}")
    G=collections.defaultdict(list)
    for r in rows: G[bucket(r['dd'])].append(r)
    for k in ORD:
        g=G.get(k)
        if not g: continue
        up=sum(1 for r in g if r['dp']<0); dn=sum(1 for r in g if r['dp']>0)
        inn=sum(1 for r in g if r['p0']>10 and r['p1']<=10)
        out=sum(1 for r in g if r['p0']<=10 and r['p1']>10)
        base10=sum(1 for r in g if r['p0']>10) or 1
        was10=sum(1 for r in g if r['p0']<=10) or 1
        print(f"{k:<20}{len(g):>6}{st.median([r['dp'] for r in g]):>16.0f}"
              f"{100*up/len(g):>9.0f}%{100*dn/len(g):>7.0f}%"
              f"{inn:>7} ({100*inn/base10:>3.0f}%){out:>9} ({100*out/was10:>3.0f}%)")
rep(PAIRS,'ВСЕ КЛЮЧИ')
rep([r for r in PAIRS if r['t'] in VS],'ТОЛЬКО ВЧ И СЧ')
rep([r for r in PAIRS if r['t']=='ВЧ'],'ТОЛЬКО ВЧ')

print('\n=== Развязка: сменился адрес или только глубина (ВЧ+СЧ) ===')
vs=[r for r in PAIRS if r['t'] in VS]
for nm,sel in [('адрес тот же, глубина та же',lambda r:not r['pgch'] and r['dd']==0),
               ('адрес тот же, стало глубже',lambda r:not r['pgch'] and r['dd']>0),
               ('адрес сменился, глубина та же',lambda r:r['pgch'] and r['dd']==0),
               ('адрес сменился, стало глубже',lambda r:r['pgch'] and r['dd']>0),
               ('стало мельче',lambda r:r['dd']<0)]:
    g=[r for r in vs if sel(r)]
    if not g: print(f'  {nm:<32} пар 0'); continue
    up=sum(1 for r in g if r['dp']<0)
    print(f"  {nm:<32} пар {len(g):>4}  медиана сдвига {st.median([r['dp'] for r in g]):>5.0f}  выросли {100*up/len(g):>3.0f}%")

print('\n=== Только те ВЧ/СЧ, что залетели в десятку между замерами ===')
inn=[r for r in vs if r['p0']>10 and r['p1']<=10]
print(f'  таких пар: {len(inn)}')
for r in sorted(inn,key=lambda x:x['p1'])[:20]:
    print(f"   {r['p0']:>3} → {r['p1']:>2}  вложенность {r['d0']:>2} → {r['d1']:>2}"
          f"  {'адрес сменился' if r['pgch'] else 'адрес тот же ':<15} {r['q'][:34]:<34} {r['br']:<10} {r['dom']}")
if inn:
    print(f"  из них стало глубже: {sum(1 for r in inn if r['dd']>0)}, глубина не менялась: "
          f"{sum(1 for r in inn if r['dd']==0)}, стало мельче: {sum(1 for r in inn if r['dd']<0)}")
    print(f"  медианный рост глубины у зашедших: {st.median([r['dd'] for r in inn]):.0f}")
    ost=[r for r in vs if not(r['p0']>10 and r['p1']<=10) and r['p0']>10]
    print(f"  для сравнения — у не зашедших ВЧ/СЧ (были ниже 10 и остались, {len(ost)} пар): "
          f"медианный рост глубины {st.median([r['dd'] for r in ost]):.0f}")

print('\n=== Контроль на стартовую позицию: сравниваем внутри одинаковых полос ===')
BANDS=[(1,10),(11,30),(31,60),(61,100)]
for nm,rows in [('ВСЕ КЛЮЧИ',PAIRS),('ВЧ+СЧ',[r for r in PAIRS if r['t'] in VS])]:
    print(f'\n {nm}:')
    print(f"   {'старт':<10}{'глубина не менялась':>34}{'глубина изменилась':>32}")
    print(f"   {'':<10}{'пар':>8}{'медиана':>10}{'выросли':>10}{'пар':>10}{'медиана':>10}{'выросли':>10}")
    for lo,hi in BANDS:
        g=[r for r in rows if lo<=r['p0']<=hi]
        a=[r for r in g if r['dd']==0]; b=[r for r in g if r['dd']!=0]
        if not a or not b: continue
        f=lambda L:(len(L),st.median([r['dp'] for r in L]),100*sum(1 for r in L if r['dp']<0)/len(L))
        na,ma,ua=f(a); nb,mb,ub=f(b)
        print(f"   {str(lo)+'–'+str(hi):<10}{na:>8}{ma:>10.0f}{ua:>9.0f}%{nb:>10}{mb:>10.0f}{ub:>9.0f}%")

print('\n=== Глубже против мельче, внутри полос (все ключи) ===')
print(f"   {'старт':<10}{'стало глубже':>26}{'стало мельче':>26}")
print(f"   {'':<10}{'пар':>8}{'медиана':>9}{'выросли':>9}{'пар':>9}{'медиана':>9}{'выросли':>9}")
for lo,hi in BANDS:
    g=[r for r in PAIRS if lo<=r['p0']<=hi]
    a=[r for r in g if r['dd']>0]; b=[r for r in g if r['dd']<0]
    if not a or not b: continue
    f=lambda L:(len(L),st.median([r['dp'] for r in L]),100*sum(1 for r in L if r['dp']<0)/len(L))
    na,ma,ua=f(a); nb,mb,ub=f(b)
    print(f"   {str(lo)+'–'+str(hi):<10}{na:>8}{ma:>9.0f}{ua:>8.0f}%{nb:>9}{mb:>9.0f}{ub:>8.0f}%")
