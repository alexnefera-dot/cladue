# Зоны: три уровня строгости. Сырые события → доли от всех запущенных → парное
# сравнение внутри групп, где одна и та же партия разошлась по двум зонам.
import json,collections,math,re
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
G=json.load(open(SP+'groups.json'))
E=json.load(open(SP+'e50.json'))          # последняя выгрузка, 128 событий
from math import comb
def fisher(a,b,c,d):
    n=a+b+c+d; r1=a+b; c1=a+c
    tot=comb(n,r1); obs=comb(c1,a)*comb(n-c1,b); p=0
    for x in range(max(0,r1-(n-c1)),min(r1,c1)+1):
        v=comb(c1,x)*comb(n-c1,r1-x)
        if v<=obs+1e-9: p+=v
    return p/tot

print('=== 1. СЫРЫЕ СОБЫТИЯ последней выгрузки (без знаменателя — так считать нельзя) ===')
a=collections.defaultdict(lambda:[0,0,set()])
for e in E['ev']:
    x=a[e['zone']]; x[0]+= e['type']=='reg'; x[1]+= e['type']=='dep'; x[2].add(e['dom'])
for z,(r,d,ds) in sorted(a.items(),key=lambda x:-x[1][0]):
    print(f"  {z:<9} рег {r:>3}  деп {d:>3}  доменов {len(ds):>3}")

print('\n=== 2. ДОЛЯ ОТ ВСЕХ ЗАПУЩЕННЫХ, только закрытые окна ===')
z=collections.defaultdict(lambda:[0,0,0,0])
for r in G['rows']:
    if r['q']!='закрыто': continue
    for d in r['doms']:
        k='.'+d['d'].split('.')[-1]
        z[k][0]+=1; z[k][1]+= 1 if d['r'] else 0; z[k][2]+=d['r']; z[k][3]+=d['p']
print(f"  {'зона':<9}{'доменов':>8}{'с рег':>7}{'доля':>8}{'±':>6}{'рег':>6}{'деп':>5}{'рег/дом':>9}")
for k,(n,w,r,dp) in sorted(z.items(),key=lambda x:-x[1][0]):
    if n<5: continue
    p=w/n; se=100*math.sqrt(p*(1-p)/n)
    print(f"  {k:<9}{n:>8}{w:>7}{100*p:>7.1f}%{se:>6.1f}{r:>6}{dp:>5}{r/n:>9.2f}")
sm=[(k,v[0]) for k,v in z.items() if v[0]<5]
if sm: print("   (меньше пяти доменов, пропущены: "+', '.join(f'{k}={n}' for k,n in sm)+')')

print('\n=== 3. ПАРНОЕ СРАВНЕНИЕ внутри групп, разошедшихся по двум зонам ===')
print('   Одна партия, один контент, один день — различается только зона.')
pairs=collections.defaultdict(lambda:collections.defaultdict(lambda:[0,0]))
mixed=[]
for r in G['rows']:
    if r['q']=='нет дня': continue
    byz=collections.defaultdict(lambda:[0,0])
    for d in r['doms']:
        k='.'+d['d'].split('.')[-1]
        byz[k][0]+=1; byz[k][1]+= 1 if d['r'] else 0
    if len(byz)<2: continue
    mixed.append((r,byz))
    for k,(n,w) in byz.items(): pairs['all'][k][0]+=n; pairs['all'][k][1]+=w
print(f"   смешанных групп: {len(mixed)}")
for k,(n,w) in sorted(pairs['all'].items(),key=lambda x:-x[1][0]):
    print(f"   {k:<9}{w:>3} из {n:<4} = {100*w/n:>5.1f}%")
t,l=pairs['all']['.team'],pairs['all'].get('.lol',[0,0])
c=pairs['all'].get('.casino',[0,0])
if t[0] and l[0]: print(f"   .team против .lol:    Fisher p = {fisher(t[1],t[0]-t[1],l[1],l[0]-l[1]):.3f}")
if t[0] and c[0]: print(f"   .team против .casino: Fisher p = {fisher(t[1],t[0]-t[1],c[1],c[0]-c[1]):.3f}")
print('\n   по группам:')
for r,byz in sorted(mixed,key=lambda x:-sum(v[0] for v in x[1].values()))[:16]:
    s=' | '.join(f"{k} {v[1]}/{v[0]}" for k,v in sorted(byz.items(),key=lambda x:-x[1][0]))
    print(f"     {r['day']} {r['g'][:38]:<40}{s}")

print('\n=== 4. ТО ЖЕ, НО ТОЛЬКО ЗАКРЫТЫЕ ОКНА (открытые партии перекошены по зонам) ===')
def paired(filt,label):
    pr=collections.defaultdict(lambda:[0,0]); strata=[]
    for r in G['rows']:
        if not filt(r): continue
        byz=collections.defaultdict(lambda:[0,0])
        for d in r['doms']:
            k='.'+d['d'].split('.')[-1]
            byz[k][0]+=1; byz[k][1]+= 1 if d['r'] else 0
        if '.team' in byz and '.lol' in byz:
            strata.append((r,byz['.team'],byz['.lol']))
            for k in ('.team','.lol'): pr[k][0]+=byz[k][0]; pr[k][1]+=byz[k][1]
    if not strata: print(f"  {label}: пар нет"); return
    t,l=pr['.team'],pr['.lol']
    print(f"  {label}: групп {len(strata)}")
    print(f"    .team {t[1]}/{t[0]} = {100*t[1]/t[0]:.1f}%   .lol {l[1]}/{l[0]} = {100*l[1]/l[0]:.1f}%"
          f"   Fisher p = {fisher(t[1],t[0]-t[1],l[1],l[0]-l[1]):.3f}")
    # Мантель-Хензель: учитывает, что группы разные
    num=den=0; a_=e_=v_=0
    for r,(nt,wt),(nl,wl) in strata:
        n=nt+nl; m1=wt+wl
        if n==0 or m1==0 or m1==n: continue
        a_+=wt; e_+=nt*m1/n; v_+=nt*nl*m1*(n-m1)/(n*n*(n-1))
    if v_>0:
        z=(abs(a_-e_)-0.5)/math.sqrt(v_)
        from math import erfc
        print(f"    Мантель-Хензель по группам: z = {z:.2f}, p = {erfc(z/math.sqrt(2)):.3f}")
    for r,(nt,wt),(nl,wl) in sorted(strata,key=lambda x:-(x[1][0]+x[2][0]))[:12]:
        print(f"      {r['day']} {r['g'][:36]:<38}.team {wt}/{nt:<4} .lol {wl}/{nl}")
paired(lambda r:r['q']=='закрыто','только закрытые окна')
paired(lambda r:r['q'] in ('закрыто','усечено','открыто'),'все окна (для сравнения)')

print('\n=== 5. ЧТО В ЗОНАХ СЕЙЧАС ЗАПУЩЕНО (перекос по окнам) ===')
w=collections.defaultdict(lambda:collections.Counter())
for r in G['rows']:
    for d in r['doms']:
        k='.'+d['d'].split('.')[-1]
        if k in ('.team','.lol','.casino'): w[k][r['q']]+=1
print(f"  {'зона':<9}{'закрыто':>9}{'открыто':>9}{'усечено':>9}{'нет дня':>9}")
for k in ('.team','.lol','.casino'):
    c=w[k]; print(f"  {k:<9}{c['закрыто']:>9}{c['открыто']:>9}{c['усечено']:>9}{c['нет дня']:>9}")
