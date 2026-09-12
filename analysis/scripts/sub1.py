# Поддоменный анализ: набор брендов одинаков на всех доменах,
# значит знаменатель для каждого бренда = число запущенных доменов.
import json,collections,math,re,glob,datetime as dt
from statistics import NormalDist
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
BAD={'yandex.ru','','—','ru.search.yahoo.com','alice.yandex.ru','youtube.com','ya.ru',
     'google.com','yahoo.com','yandex.kz','yandex.by','yandex.uz'}
PRICE={'casino':7.0,'team':2.0,'lol':1.0,'buzz':1.0}; DEPV=40.0
NBRAND=200; TODAY=dt.date(2026,9,12)
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
CLOSED=set(d for d,v in D.items() if dat(v[0]) and (TODAY-dat(v[0])).days>=6)
zone=lambda d:d.split('.')[-1]
ALL=set(x.strip() for x in open('/home/user/cladue/analysis/domains_flat.txt') if x.strip())|set(D)

CE=[e for e in EV if e['dom'] in CLOSED and e.get('sub')]
NOSUB=[e for e in EV if e['dom'] in CLOSED and not e.get('sub')]
nD=len(CLOSED); nS=nD*NBRAND
print(f"=== МАСШТАБ ===")
print(f"доменов с закрытым окном      {nD:>8}")
print(f"поддоменов (х200 брендов)     {nS:>8}")
print(f"событий с известным брендом   {len(CE):>8}  (без бренда {len(NOSUB)})")
rg=[e for e in CE if e['type']=='reg']; dpv=[e for e in CE if e['type']!='reg']
print(f"регистраций {len(rg)}, депозитов {len(dpv)}")
print(f"\nставка на ПОДДОМЕН: {100*len(rg)/nS:.4f}% рег, {100*len(dpv)/nS:.4f}% деп")
print(f"ставка на ДОМЕН:    {100*len(rg)/nD:.2f}% рег ({len(rg)/nD:.3f} на домен)")

print("\n=== КОНЦЕНТРАЦИЯ ПО БРЕНДАМ ===")
br=collections.Counter(e['sub'] for e in rg)
brd=collections.Counter(e['sub'] for e in dpv)
obs=len(br)
print(f"брендов дали хотя бы 1 рег: {obs} из {NBRAND} -> {NBRAND-obs} брендов молчат полностью")
counts=sorted(br.values(),reverse=True)+[0]*(NBRAND-obs)
tot=sum(counts)
for k in (5,10,20,50):
    print(f"  топ-{k:<3} брендов дают {100*sum(counts[:k])/tot:>5.1f}% регистраций")
print(f"\n{'бренд':<16}{'рег':>5}{'ставка/домен':>14}{'деп':>5}{'$/домен':>9}")
for b,c in br.most_common(15):
    print(f"{b:<16}{c:>5}{100*c/nD:>13.2f}%{brd[b]:>5}{brd[b]*DEPV/nD:>9.2f}")

print("\n=== ЭТО БРЕНД ИЛИ ШУМ? ===")
# если 200 брендов одинаковы, счётчики ~ Пуассон(mean=tot/200)
m=tot/NBRAND
var=sum((c-m)**2 for c in counts)/(NBRAND-1)
chi=sum((c-m)**2 for c in counts)/m
print(f"среднее на бренд {m:.3f}, дисперсия {var:.3f}, отношение {var/m:.2f}")
print(f"если бренды взаимозаменяемы, отношение должно быть ~1.00")
df=NBRAND-1
z=(chi-df)/math.sqrt(2*df)
p=2*(1-NormalDist().cdf(abs(z)))
print(f"хи-квадрат {chi:.1f} при {df} ст.св., z={z:.1f}, p={p:.2e}")
print("=> " + ("бренды НЕ взаимозаменяемы: разброс сильно выше случайного"
      if p<0.01 and var>m else "нельзя отличить от случайного"))

print("\n=== СКОЛЬКО БРЕНДОВ РАБОТАЕТ НА ОДНОМ ДОМЕНЕ ===")
perdom=collections.defaultdict(set)
for e in rg: perdom[e['dom']].add(e['sub'])
work=[len(v) for v in perdom.values()]
print(f"домены с хотя бы 1 рег: {len(work)} из {nD}")
print(f"разных брендов на сработавшем домене: в среднем {sum(work)/len(work):.2f}, максимум {max(work)}")
h=collections.Counter(work)
for k in sorted(h): print(f"  {k} бренд(ов): {h[k]} доменов")

print("\n=== ГЛАВНОЕ СЛЕДСТВИЕ: ЦЕНА БРЕНДА ===")
dep_per_dom=len(dpv)/nD
print(f"домен даёт {dep_per_dom:.4f} деп = ${dep_per_dom*DEPV:.2f} при 200 брендах")
print(f"значит один бренд в среднем стоит ${dep_per_dom*DEPV/NBRAND:.4f} на домен")
print(f"но топ-бренд даёт ${brd[br.most_common(1)[0][0]]*DEPV/nD:.2f} — "
      f"в {brd[br.most_common(1)[0][0]]*DEPV/nD/(dep_per_dom*DEPV/NBRAND):.0f}x больше среднего")
print(f"\nподдомены бесплатны. Если добавить ещё 100 брендов такого же качества,")
print(f"домен даст ${dep_per_dom*DEPV*300/200:.2f} вместо ${dep_per_dom*DEPV:.2f} при той же цене домена")
for extra in (100,200,300):
    n2=NBRAND+extra
    rev=dep_per_dom*DEPV*n2/NBRAND
    c=sum(PRICE.get(zone(d),1.0) for d in CLOSED)/nD
    print(f"  {n2} брендов: ${rev:.2f}/домен против цены ${c:.2f} -> ROI {rev/c:.2f}x")
