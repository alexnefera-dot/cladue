# Что закрывается за неделю при текущем объёме запусков, а что нет.
import json,collections,math,re,glob,random,datetime as dt
from math import comb
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
BAD={'yandex.ru','','—','ru.search.yahoo.com','alice.yandex.ru','youtube.com','ya.ru',
     'google.com','yahoo.com','yandex.kz','yandex.by','yandex.uz'}
PRICE={'casino':7.0,'team':2.0,'lol':1.0,'buzz':1.0}; DEPV=40.0
TODAY=dt.date(2026,9,12)
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
zone=lambda d:d.split('.')[-1]
ALL=set(x.strip() for x in open('/home/user/cladue/analysis/domains_flat.txt') if x.strip())|set(D)

# темп запусков за последние 7 дней
print("=== ТЕМП ЗАПУСКОВ ===")
byday=collections.Counter()
for d,v in D.items():
    dd=dat(v[0])
    if dd: byday[dd]+=1
last=sorted(byday)[-8:]
for dd in last: print(f"  {dd.strftime('%d.%m %a')}  {byday[dd]:>4} доменов")
wk=sum(byday[dd] for dd in last[-7:])
print(f"  за 7 дней: {wk} доменов, в среднем {wk/7:.0f}/день")

print("\n=== ЗОНА: закроется сама, без затрат ===")
for z in ('casino','lol','team'):
    tot=[d for d in ALL if zone(d)==z]
    cl=[d for d in D if zone(d)==z and dat(D[d][0]) and (TODAY-dat(D[d][0])).days>=6]
    op=len(tot)-len(cl)
    print(f".{z:<8} всего {len(tot):>4}, закрытых окон {len(cl):>4}, в полёте {op:>4}")
# мощность когда окна текущих .casino закроются
random.seed(11)
def power_asym(n1,p1,n2,p2,it=3000):
    hit=0
    for _ in range(it):
        a=sum(1 for _ in range(n1) if random.random()<p1)
        b=sum(1 for _ in range(n2) if random.random()<p2)
        if a+b and fisher(a,n1-a,b,n2-b)<0.05: hit+=1
    return hit/it
pl=3/110
ncas=len([d for d in ALL if zone(d)=='casino']); nlol=len([d for d in ALL if zone(d)=='lol'])
print(f"\nкогда закроются все окна ({ncas} .casino против {nlol} .lol):")
for mult,lab in ((7,'ровно порог окупаемости 7x'),(5,'5x'),(3.2,'наблюдаемое 3.2x')):
    print(f"  увидеть разницу {lab:<28} мощность {100*power_asym(ncas,pl*mult,nlol,pl):>3.0f}%")
print("  => порог 7x различим на уже купленных доменах. Платить за тест не нужно.")

print("\n=== ЭКСПЕРИМЕНТ ЗА НЕДЕЛЮ: сколько значений можно сравнивать ===")
base=106/559
print(f"базовый заход {100*base:.1f}%. Неделя = ~{wk} доменов на закрытых окнах не будет:")
print("закрытое окно к 7-му дню получат только запуски 1-2 дня, т.е. ~%d доменов."%(2*wk//7))
for arms in (2,3,4):
    n=wk//arms
    print(f"\n  {arms} ветки по {n} доменов (вся неделя, окна закроются на 13-й день):")
    for lift in (1.3,1.5,2.0):
        print(f"    заход {100*base:.0f}% -> {100*base*lift:.0f}% ({lift}x): мощность "
              f"{100*power_asym(n,base*lift,n,base):>3.0f}%")
    ndep=wk/arms*(27/559)
    print(f"    депозитов в ветке ожидается {ndep:.1f} — по деньгам ветка нечитаема")

print("\n=== ПОДДОМЕНЫ: во сколько раз растёт выборка ===")
for nd,lab in ((wk,'неделя запусков'),(len(ALL),'весь реестр')):
    print(f"{lab:<22} {nd:>5} доменов -> {nd*200:>8} поддоменов")
rw=wk*(179/559)
print(f"\nза неделю ожидается ~{rw:.0f} регистраций на ~{wk*200} поддоменов = "
      f"{100*rw/(wk*200):.3f}% на поддомен")
print("сравнение классов брендов (ВЧ/СЧ/НЧ), если классы делят поддомены примерно поровну:")
p_sub=rw/(wk*200)
for arms in (2,3):
    n=wk*200//arms
    for lift in (1.5,2.0):
        print(f"  {arms} класса по {n} поддоменов, разница {lift}x: мощность "
              f"{100*power_asym(n,p_sub*lift,n,p_sub,800):>3.0f}%")

print("\n=== ЧАС ПОСТАНОВКИ: когда станет читаемым ===")
for weeks in (1,2,4,8):
    n=wk*weeks
    perblock=n//4
    print(f"{weeks:>2} нед = {n:>5} доменов, блок суток {perblock:>4} доменов: "
          f"мощность на 1.5x {100*power_asym(perblock,base*1.5,perblock,base,1200):>3.0f}%")
