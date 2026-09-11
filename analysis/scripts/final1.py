# Сводка на закрытых окнах после выгрузки от 11.09 (история с 12.08 — усечения нет).
import json,collections,math,re,glob,datetime as dt
from math import comb
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
BAD={'yandex.ru','','—','ru.search.yahoo.com','alice.yandex.ru','youtube.com','ya.ru','google.com','yahoo.com','yandex.kz','yandex.by','yandex.uz'}
EV=[e for e in json.load(open(SP+'convall.json')) if e['dom'] not in BAD]
reg=collections.Counter(); dep=collections.Counter()
for e in EV: (reg if e['type']=='reg' else dep)[e['dom']]+=1
TODAY=dt.date(2026,9,11)
def dat(s):
    m=re.match(r'(\d\d)\.(\d\d)',s); return dt.date(2026,int(m.group(2)),int(m.group(1))) if m else None
def fisher(a,b,c,d):
    n=a+b+c+d; r1=a+b; c1=a+c
    tot=comb(n,r1); obs=comb(c1,a)*comb(n-c1,b); p=0
    for x in range(max(0,r1-(n-c1)),min(r1,c1)+1):
        v=comb(c1,x)*comb(n-c1,r1-x)
        if v<=obs+1e-9: p+=v
    return p/tot
# домены с известным днём и группой
D={}
for f in sorted(glob.glob('/home/user/cladue/analysis/launch_*.txt')):
    if '_flat' in f: continue
    md=re.search(r'launch_(\d\d\.\d\d)',f)
    if not md: continue
    day=md.group(1); main=None; extra=None; prev=False
    for l in open(f):
        l=l.rstrip(); s2=l.strip()
        h=None
        if l.startswith('## '): h=l[3:].strip()
        elif s2.startswith('===') and s2.endswith('==='): h=s2.strip('= ').strip()
        elif s2 and not re.match(r'^[a-z0-9\-]+\.[a-z]+$',s2) and not l.startswith('#'): h=s2
        if h is not None:
            if prev and main: extra=h
            else: main=h; extra=None
            prev=True
        elif re.match(r'^[a-z0-9\-]+\.[a-z]+$',s2):
            prev=False
            if 'ОДНИМ СПИСКОМ' in (main or '').upper(): continue
            D[s2]=(day,main or '',extra or '')
CLOSED={d:v for d,v in D.items() if dat(v[0]) and (TODAY-dat(v[0])).days>=6}
print(f"доменов со списком {len(D)}, из них с закрытым окном {len(CLOSED)}")
print(f"регистраций у них {sum(reg[d] for d in CLOSED)}, депозитов {sum(dep[d] for d in CLOSED)}")

def block(title,keyf,doms=None,minn=10):
    doms=doms or CLOSED
    G=collections.defaultdict(list)
    for d in doms:
        k=keyf(d,doms[d] if isinstance(doms,dict) else D[d])
        if k is not None: G[k].append(d)
    print(f"\n=== {title} ===")
    print(f"{'значение':<22}{'доменов':>8}{'с рег':>7}{'доля':>8}{'±':>6}{'рег':>6}{'деп':>5}")
    out={}
    for k,ds in sorted(G.items(),key=lambda x:-len(x[1])):
        if len(ds)<minn: continue
        n=len(ds); w=sum(1 for d in ds if reg[d]); p=w/n
        se=100*math.sqrt(p*(1-p)/n)
        print(f"{str(k)[:22]:<22}{n:>8}{w:>7}{100*p:>7.1f}%{se:>6.1f}"
              f"{sum(reg[d] for d in ds):>6}{sum(dep[d] for d in ds):>5}")
        out[k]=(n,w)
    return out

def pages(d,v):
    g=v[1]
    m=re.search(r'(?:^|[^\d])(\d+)\s*(?:pages|page|стр)',g)
    if m: return m.group(1)+' стр'
    m=re.match(r'clean(\d+)',g)
    if m: return m.group(1)+' стр'
    return None
def dates(d,v):
    g=(v[1]+' '+v[2]).lower()
    if 'withdate' in g or 'с датами' in g or 'сдатой' in g: return 'с датами'
    if 'nodate' in g or 'без дат' in g or 'бездаты' in g: return 'без дат'
    return None
P=block('СТРАНИЦ',pages)
Dt=block('ДАТЫ',dates)
Z=block('ЗОНА',lambda d,v:'.'+d.split('.')[-1])
if '12 стр' in P and '7 стр' in P:
    (n1,w1),(n2,w2)=P['12 стр'],P['7 стр']
    print(f"\n12 против 7: {w1}/{n1} = {100*w1/n1:.1f}%  против  {w2}/{n2} = {100*w2/n2:.1f}%"
          f"   Fisher p = {fisher(w1,n1-w1,w2,n2-w2):.4f}")
if 'с датами' in Dt and 'без дат' in Dt:
    (n1,w1),(n2,w2)=Dt['без дат'],Dt['с датами']
    print(f"без дат против с датами: {w1}/{n1} = {100*w1/n1:.1f}%  против  {w2}/{n2} = {100*w2/n2:.1f}%"
          f"   Fisher p = {fisher(w1,n1-w1,w2,n2-w2):.4f}")

print("\n=== СТРАНИЦЫ ВНУТРИ ДНЯ (контроль на день запуска) ===")
byday=collections.defaultdict(lambda:collections.defaultdict(list))
for d,v in CLOSED.items():
    pg=pages(d,v)
    if pg in ('12 стр','7 стр'): byday[v[0]][pg].append(d)
print(f"{'день':<8}{'12 стр':>18}{'7 стр':>18}")
a_=e_=v_=0; tot12=tot7=w12=w7=0
for day in sorted(byday,key=lambda x:dat(x)):
    c=byday[day]
    if '12 стр' not in c or '7 стр' not in c: continue
    n1=len(c['12 стр']); w1=sum(1 for d in c['12 стр'] if reg[d])
    n2=len(c['7 стр']);  w2=sum(1 for d in c['7 стр'] if reg[d])
    tot12+=n1; tot7+=n2; w12+=w1; w7+=w2
    n=n1+n2; m1=w1+w2
    if 0<m1<n:
        a_+=w1; e_+=n1*m1/n; v_+=n1*n2*m1*(n-m1)/(n*n*(n-1))
    print(f"{day:<8}{f'{w1}/{n1} = {100*w1/n1:.0f}%':>18}{f'{w2}/{n2} = {100*w2/n2:.0f}%':>18}")
print(f"{'ИТОГО':<8}{f'{w12}/{tot12} = {100*w12/tot12:.1f}%':>18}{f'{w7}/{tot7} = {100*w7/tot7:.1f}%':>18}")
if v_>0:
    from math import erfc,sqrt
    z=(abs(a_-e_)-0.5)/sqrt(v_)
    print(f"Мантель-Хензель с контролем на день: z = {z:.2f}, p = {erfc(z/sqrt(2)):.4f}")
print(f"Fisher без контроля на тех же днях: p = {fisher(w12,tot12-w12,w7,tot7-w7):.4f}")

print("\n=== ДОМЕНЫ БЕЗ СПИСКА ЗАПУСКА ===")
orph=[d for d in reg if d not in D]
print(f"доменов {len(orph)}, регистраций {sum(reg[d] for d in orph)}, депозитов {sum(dep[d] for d in orph)}")
print(f"это {100*sum(reg[d] for d in orph)/sum(reg.values()):.0f}% всех регистраций")
