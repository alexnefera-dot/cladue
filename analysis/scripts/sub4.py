# Класс бренда против денег, со правильным знаменателем: набор брендов одинаков на всех доменах.
import json,collections,math,re,glob,datetime as dt
from statistics import NormalDist
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
BAD={'yandex.ru','','—','ru.search.yahoo.com','alice.yandex.ru','youtube.com','ya.ru',
     'google.com','yahoo.com','yandex.kz','yandex.by','yandex.uz'}
TODAY=dt.date(2026,9,12); DEPV=40.0
K=json.load(open(SP+'keys.json'))
BV={}
for k,v in K.items():
    b=v.get('b')
    if b: BV[b]=(v.get('v') or 0, v.get('t') or '')
print(f"=== БРЕНДЫ С ИЗВЕСТНОЙ ЧАСТОТНОСТЬЮ ===")
print(f"в keys.json брендов: {len(BV)}")
cl=collections.Counter(t for _,(v,t) in BV.items())
print("по классам:",dict(cl))

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
nD=len(CLOSED)
RG=[e for e in EV if e['dom'] in CLOSED and e.get('sub') and e['type']=='reg']
DP=[e for e in EV if e['dom'] in CLOSED and e.get('sub') and e['type']!='reg']
conv=set(e['sub'] for e in RG)
print(f"\nбрендов дали регистрацию: {len(conv)}, из них частотность известна: "
      f"{len(conv&set(BV))}, неизвестна: {len(conv-set(BV))}")
unk=sorted(conv-set(BV))
if unk: print("  без частотности:", ', '.join(unk[:20]))

print("\n=== СТАВКА НА ПОДДОМЕН ПО КЛАССУ БРЕНДА ===")
print("знаменатель: (число брендов класса) x (559 доменов)")
print(f"{'класс':<8}{'брендов':>8}{'поддоменов':>12}{'рег':>5}{'рег/поддомен':>14}{'деп':>5}{'$/домен':>9}")
rows={}
for t in ('ВЧ','СЧ','НЧ'):
    bs=[b for b,(v,tt) in BV.items() if tt==t]
    nb=len(bs)
    if not nb: continue
    ns=nb*nD
    r=sum(1 for e in RG if e['sub'] in set(bs))
    dd=sum(1 for e in DP if e['sub'] in set(bs))
    rows[t]=(nb,ns,r,dd)
    print(f"{t:<8}{nb:>8}{ns:>12}{r:>5}{100*r/ns:>13.4f}%{dd:>5}{dd*DEPV/nD:>9.3f}")
def ztest(a,na,b,nb_):
    p1,p2=a/na,b/nb_
    p=(a+b)/(na+nb_)
    se=math.sqrt(p*(1-p)*(1/na+1/nb_))
    if se==0: return 1.0
    z=(p1-p2)/se
    return 2*(1-NormalDist().cdf(abs(z))),z
print()
for x,y in (('ВЧ','НЧ'),('ВЧ','СЧ'),('СЧ','НЧ')):
    if x in rows and y in rows:
        nb1,ns1,r1,_=rows[x]; nb2,ns2,r2,_=rows[y]
        p,z=ztest(r1,ns1,r2,ns2)
        rat=(r1/ns1)/(r2/ns2) if r2 else float('inf')
        print(f"{x} против {y}: {100*r1/ns1:.4f}% против {100*r2/ns2:.4f}% "
              f"= {rat:.2f}x, z={z:+.2f}, p={p:.4f}")

print("\n=== НЕПРЕРЫВНО: ставка против частотности ===")
bins=[(0,200000,'до 200k'),(200000,500000,'200-500k'),(500000,1000000,'500k-1M'),
      (1000000,10**9,'свыше 1M')]
print(f"{'частотность':<12}{'брендов':>8}{'поддоменов':>12}{'рег':>5}{'рег/поддомен':>14}{'индекс':>8}")
basel=None
for lo,hi,lab in bins:
    bs=set(b for b,(v,t) in BV.items() if lo<=v<hi)
    if not bs: continue
    ns=len(bs)*nD; r=sum(1 for e in RG if e['sub'] in bs)
    rate=r/ns
    if basel is None: basel=rate
    print(f"{lab:<12}{len(bs):>8}{ns:>12}{r:>5}{100*rate:>13.4f}%{rate/basel if basel else 0:>7.2f}x")

print("\n=== ПОЧЕМУ СТАРАЯ АНОМАЛИЯ '13 ИЗ 92' БЫЛА АРТЕФАКТОМ ===")
print("Я сравнивал бренд конверсии с ядром ключей ДОМЕНА. Но ядро домена — это")
print("объединение 200 поддоменных ядер, а ранжируется поддомен. Совпадение")
print("бренда конверсии с 'ядром домена' поэтому ничего не значило.")
# сколько брендов в среднем на домен в ключах
nd_per_brand=[v.get('nd',0) for v in K.values()]
print(f"в ключевых данных на один ключ приходится в среднем "
      f"{sum(nd_per_brand)/len(nd_per_brand):.1f} доменов — то есть ключи мерились")
print("по доменам, а не по поддоменам. Это и есть подмена единицы.")
