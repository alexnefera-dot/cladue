# Разрешаем противоречие: сверхразброс есть, а сплит-половина дала ноль. Кто прав.
import json,collections,math,random,re,glob,datetime as dt
from math import comb,exp,factorial
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
BAD={'yandex.ru','','—','ru.search.yahoo.com','alice.yandex.ru','youtube.com','ya.ru',
     'google.com','yahoo.com','yandex.kz','yandex.by','yandex.uz'}
NBRAND=200; TODAY=dt.date(2026,9,12); DEPV=40.0
EV=[e for e in json.load(open(SP+'convall.json')) if e['dom'] not in BAD]
def dat(s):
    m=re.match(r'(\d\d)\.(\d\d)',s)
    return dt.date(2026,int(m.group(2)),int(m.group(1))) if m else None
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
CLOSED=sorted(d for d,v in D.items() if dat(v[0]) and (TODAY-dat(v[0])).days>=6)
RG=[e for e in EV if e['dom'] in CLOSED and e.get('sub') and e['type']=='reg']
nD=len(CLOSED); tot=len(RG); m=tot/NBRAND
br=collections.Counter(e['sub'] for e in RG)

print("=== ТЕСТ 1. Мог ли luckybird набрать 10 регистраций случайно ===")
def ppois_ge(k,lam): return 1-sum(exp(-lam)*lam**i/factorial(i) for i in range(k))
p1=ppois_ge(10,m)
pany=1-(1-p1)**NBRAND
print(f"при равных брендах каждый ждёт {m:.3f} регистраций")
print(f"P(конкретный бренд >= 10) = {p1:.2e}")
print(f"P(хоть один из 200 >= 10) = {pany:.2e}")
mx=max(br.values())
print(f"наблюдаемый максимум {mx} (luckybird), и он на 10 РАЗНЫХ доменах")
print("=> случайностью 10 не объясняется. Разброс между брендами реален.")

print("\n=== ТЕСТ 2. Можно ли действовать по рейтингу: топ-K из половины ===")
random.seed(5)
for K in (10,20,40):
    lifts=[]
    for _ in range(400):
        dom=CLOSED[:]; random.shuffle(dom)
        h1=set(dom[:nD//2]); h2=[d for d in dom[nD//2:]]
        c1=collections.Counter(e['sub'] for e in RG if e['dom'] in h1)
        top=[b for b,_ in c1.most_common(K)]
        if len(top)<K: continue
        ts=set(top)
        r2=[e for e in RG if e['dom'] not in h1]
        n2=len(h2)
        inrate=sum(1 for e in r2 if e['sub'] in ts)/(n2*K)
        outrate=sum(1 for e in r2 if e['sub'] not in ts)/(n2*(NBRAND-K))
        if outrate>0: lifts.append(inrate/outrate)
    lifts.sort()
    print(f"  топ-{K:<3} из одной половины даёт в другой половине в "
          f"{lifts[len(lifts)//2]:.2f}x больше регистраций на поддомен "
          f"(5-95%: {lifts[len(lifts)//20]:.2f}-{lifts[-len(lifts)//20]:.2f})")
print("=> рейтинг на 179 регистрациях уже даёт работающий отбор, хотя ранги отдельных")
print("   брендов не воспроизводятся: работает верхняя группа, а не конкретный порядок.")

print("\n=== ТЕСТ 3. Сколько денег в разбросе брендов ===")
counts=sorted(br.values(),reverse=True)+[0]*(NBRAND-len(br))
dep=collections.Counter(e['sub'] for e in EV
    if e['dom'] in CLOSED and e.get('sub') and e['type']!='reg')
ndep=sum(dep.values())
print(f"сейчас: 200 брендов, {ndep} деп, ${ndep*DEPV/nD:.2f} на домен")
for K in (20,50,100):
    top=set(b for b,_ in br.most_common(K))
    dk=sum(dep[b] for b in top)
    print(f"  топ-{K:<4} брендов дают {sum(counts[:K])}/{tot} рег и {dk}/{ndep} деп")

print("\n=== ТЕСТ 4. Стоит ли добавлять бренды сверх 200 ===")
print("поддомен бесплатен, значит порог окупаемости нового бренда = ноль:")
print("любой бренд с ненулевой ставкой добавляет деньги. Но сколько — неизвестно:")
print("новые бренды идут вниз по популярности, а разброс как раз по популярности.")
def ztest_power(n,p1,p2):
    from statistics import NormalDist
    pbar=(p1+p2)/2
    se0=math.sqrt(2*pbar*(1-pbar)/n); se1=math.sqrt(p1*(1-p1)/n+p2*(1-p2)/n)
    return NormalDist().cdf((abs(p1-p2)-1.959964*se0)/se1)
base=106/nD
print(f"\nпроверка 200 против 300 брендов, метрика — заход домена ({100*base:.1f}%):")
for lift,lab in ((1.15,'+15% (новые бренды вдвое хуже средних)'),
                 (1.25,'+25%'),(1.5,'+50% (новые бренды как средние)')):
    for n in (293,587):
        print(f"  {lab:<42} n={n} на ветку: мощность {100*ztest_power(n,base*lift,base):>3.0f}%")
