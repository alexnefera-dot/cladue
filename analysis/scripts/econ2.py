# Стоит ли .casino своих $7: сравнение зон по деньгам, а не по «заходу».
import json,collections,math,re,glob,datetime as dt
from math import comb
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
BAD={'yandex.ru','','—','ru.search.yahoo.com','alice.yandex.ru','youtube.com','ya.ru',
     'google.com','yahoo.com','yandex.kz','yandex.by','yandex.uz'}
PRICE={'casino':7.0,'team':2.0,'lol':1.0,'buzz':1.0}
DEP=40.0; TODAY=dt.date(2026,9,12)
EV=[e for e in json.load(open(SP+'convall.json')) if e['dom'] not in BAD]
reg=collections.Counter(); dp=collections.Counter()
for e in EV: (reg if e['type']=='reg' else dp)[e['dom']]+=1
def dat(s):
    m=re.match(r'(\d\d)\.(\d\d)',s)
    return dt.date(2026,int(m.group(2)),int(m.group(1))) if m else None
def fisher(a,b,c,d):
    n=a+b+c+d; r1=a+b; c1=a+c
    tot=comb(n,r1); obs=comb(c1,a)*comb(n-c1,b); p=0
    for x in range(max(0,r1-(n-c1)),min(r1,c1)+1):
        v=comb(c1,x)*comb(n-c1,r1-x)
        if v<=obs+1e-9: p+=v
    return p/tot
D={}
for f in sorted(glob.glob('/home/user/cladue/analysis/launch_*.txt')):
    if '_flat' in f: continue
    md=re.search(r'launch_(\d\d\.\d\d)',f)
    if not md: continue
    day=md.group(1); main=None; prev=False
    for l in open(f):
        l=l.rstrip(); s2=l.strip(); h=None
        if l.startswith('## '): h=l[3:].strip()
        elif s2.startswith('===') and s2.endswith('==='): h=s2.strip('= ').strip()
        elif s2 and not re.match(r'^[a-z0-9\-]+\.[a-z]+$',s2) and not l.startswith('#'): h=s2
        if h is not None:
            if not (prev and main): main=h
            prev=True
        elif re.match(r'^[a-z0-9\-]+\.[a-z]+$',s2):
            prev=False
            if 'ОДНИМ СПИСКОМ' in (main or '').upper(): continue
            D[s2]=(day,main or '')
CLOSED={d:v for d,v in D.items() if dat(v[0]) and (TODAY-dat(v[0])).days>=6}
zone=lambda d:d.split('.')[-1]

print("=== ЗОНЫ НА ЗАКРЫТЫХ ОКНАХ: сколько зона даёт и сколько стоит ===")
print(f"{'зона':<9}{'доменов':>8}{'рег':>5}{'рег/дом':>9}{'деп':>5}{'деп/дом':>9}{'цена$':>7}{'$выр/дом':>10}{'$итог/дом':>11}{'ROI':>7}")
Z={}
for z in ('casino','team','lol'):
    ds=[d for d in CLOSED if zone(d)==z]
    n=len(ds); r=sum(reg[d] for d in ds); p=sum(dp[d] for d in ds)
    pr=PRICE[z]; rv=p*DEP/n
    Z[z]=(n,r,p)
    print(f".{z:<8}{n:>8}{r:>5}{r/n:>9.3f}{p:>5}{p/n:>9.4f}{pr:>7.0f}{rv:>10.2f}{rv-pr:>11.2f}{rv/pr:>6.2f}x")

print("\n=== ВО СКОЛЬКО РАЗ .casino ДОЛЖЕН БЫТЬ ЛУЧШЕ, ЧТОБЫ ОКУПИТЬСЯ ===")
for z in ('team','lol'):
    need=PRICE['casino']/PRICE[z]
    nb,rb,pb=Z[z]; nc,rc,pc=Z['casino']
    fact=(pc/nc)/(pb/nb) if pb else float('inf')
    print(f"против .{z}: должен быть лучше в {need:.1f}x, по факту в {fact:.2f}x  ->  "
          f"{'окупается' if fact>=need else 'НЕ окупается'}")
    a,b=pc,nc-pc; c,d=pb,nb-pb
    print(f"   деп: {pc}/{nc} против {pb}/{nb}, Fisher p={fisher(a,b,c,d):.3f}")
    a,b=rc,nc-rc; c,d=rb,nb-rb
    print(f"   рег: {rc}/{nc} против {rb}/{nb}, Fisher p={fisher(a,b,c,d):.3f}")

print("\n=== СЦЕНАРИИ: те же 559 доменов, другая раскладка по зонам ===")
n_all=len(CLOSED); r_all=sum(reg[d] for d in CLOSED); p_all=sum(dp[d] for d in CLOSED)
c_all=sum(PRICE[zone(d)] for d in CLOSED)
print(f"как есть: ${c_all:.0f} затрат, {p_all} деп, ${p_all*DEP:.0f} выручки, итог ${p_all*DEP-c_all:+.0f}, ROI {p_all*DEP/c_all:.2f}x")
base=p_all/n_all
for name,pr,rate in [
    ('всё в .lol, зона не важна',1.0,base),
    ('всё в .lol по её факт. ставке',1.0,Z['lol'][2]/Z['lol'][0]),
    ('всё в .team, зона не важна',2.0,base),
    ('всё в .casino по её факт. ставке',7.0,Z['casino'][2]/Z['casino'][0]),
]:
    c=pr*n_all; p=rate*n_all
    print(f"{name:<34} ${c:>5.0f} затрат, {p:>5.1f} деп, ${p*DEP:>6.0f} выручки, "
          f"итог ${p*DEP-c:>+6.0f}, ROI {p*DEP/c:.2f}x")

print("\n=== ЧТО ДАЁТ БОЛЬШЕ: сменить зону или улучшить контент ===")
print(f"сейчас на закрытых окнах: {p_all} деп на {n_all} доменов = {base:.4f} деп/домен, ROI {p_all*DEP/c_all:.2f}x")
print(f"перевести всё в .lol при той же ставке: ROI {base*DEP/1.0:.2f}x  (рост в {(base*DEP/1.0)/(p_all*DEP/c_all):.1f}x)")
for lift in (1.5,2.0,3.0):
    print(f"поднять конверсию в {lift}x при текущих зонах: ROI {lift*p_all*DEP/c_all:.2f}x")

print("\n=== СКОЛЬКО ЗАПУСКОВ НУЖНО, ЧТОБЫ ЗАКРЫТЬ ВОПРОС ЗОНЫ ПО ДЕПОЗИТАМ ===")
# мощность: обнаружить, что .casino лучше .lol в 7x по депозитам
pl=Z['lol'][2]/Z['lol'][0]
import random
def power(n,p1,p2,it=4000):
    hit=0
    for _ in range(it):
        a=sum(1 for _ in range(n) if random.random()<p1)
        b=sum(1 for _ in range(n) if random.random()<p2)
        if a+b and fisher(a,n-a,b,n-b)<0.05: hit+=1
    return hit/it
random.seed(7)
for n in (100,200,400):
    print(f"  n={n} на зону: чтобы увидеть разницу 7x ({100*pl:.1f}% против {100*pl*7:.1f}%) "
          f"мощность {100*power(n,pl*7,pl):.0f}%")
