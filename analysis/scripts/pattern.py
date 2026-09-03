# Есть ли закономерность у доменов, давших конверсию.
# Главное: считать долю от ВСЕХ запущенных доменов с таким признаком, а не только среди конвертнувших.
import json,collections,csv,math,re,datetime as dt
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
AN='/home/user/cladue/analysis/'
EV=json.load(open(SP+'convall.json'))
db=json.load(open(SP+'db.json'))
SN=json.load(open(SP+'snapr.json')); QD=SN['qd']
reg=collections.Counter(e['dom'] for e in EV if e['type']=='reg')
dep=collections.Counter(e['dom'] for e in EV if e['type']=='dep')

# ---------- знаменатель: все домены, у которых известна конфигурация
def norm_pages(x):
    x=str(x)
    m=re.search(r'\d+',x); return m.group(0) if m else '?'
def norm_dates(x):
    x=str(x).lower()
    if 'без' in x: return 'без дат'
    if 'дат' in x: return 'с датами'
    return '?'
BASE={}
for d,v in db.items():
    if d=='базовый домен': continue
    BASE[d]=dict(pages=norm_pages(v.get('pages')),dates=norm_dates(v.get('dates')),
                 zone=v.get('zone') or '.'+d.split('.')[-1],day=str(v.get('coh','?')),
                 group=v.get('group') or v.get('sheet',''),src='db')
for p in SN['pools']:
    if p.get('excl'): continue
    for d in p['doms']:
        BASE[d]=dict(pages=norm_pages(p['pages']),dates=norm_dates(p['dates']),
                     zone='.'+d.split('.')[-1],day=p['ltx'][:5],group=p['name'],src='snapr')
print(f"знаменатель: {len(BASE)} доменов с известной конфигурацией")
print(f"из них дали регистрацию: {sum(1 for d in BASE if reg[d])} "
      f"({100*sum(1 for d in BASE if reg[d])/len(BASE):.1f}%)")
print(f"регистраций у них: {sum(reg[d] for d in BASE)} из {sum(reg.values())} всего")
un=[d for d in reg if d not in BASE]
print(f"домены с деньгами вне знаменателя: {len(un)} ({sum(reg[d] for d in un)} рег) — конфигурация неизвестна\n")

# ---------- окно: закрыто ли
TODAY=dt.date(2026,9,3)
def opened(day):
    m=re.search(r'(\d\d)\.(\d\d)',str(day))
    if not m: return None
    return dt.date(2026,int(m.group(2)),int(m.group(1)))
def closed(d):
    a=opened(BASE[d]['day'])
    return a is None or (TODAY-a).days>=6      # архив/старое считаем закрытым

def rate(sel,doms=None):
    doms=[d for d in (doms or BASE) if sel(d)]
    n=len(doms); w=sum(1 for d in doms if reg[d]); r=sum(reg[d] for d in doms)
    p=w/n if n else 0
    se=math.sqrt(p*(1-p)/n) if n else 0
    return n,w,r,100*p,100*se,(r/n if n else 0)

def block(title,keyf,doms=None,minn=8):
    print(f'=== {title} ===')
    print(f"{'значение':<24}{'доменов':>8}{'с рег.':>7}{'доля':>8}{'±':>6}{'рег':>6}{'рег/дом':>9}")
    G=collections.defaultdict(list)
    for d in (doms or BASE):
        G[keyf(d)].append(d)
    for k,ds in sorted(G.items(),key=lambda x:-len(x[1])):
        if len(ds)<minn: continue
        n,w,r,p,se,rp=rate(lambda x:True,ds)
        print(f"{str(k)[:24]:<24}{n:>8}{w:>7}{p:>7.1f}%{se:>6.1f}{r:>6}{rp:>9.2f}")
    small=[(k,len(v)) for k,v in G.items() if len(v)<minn]
    if small: print(f"   (пропущены группы меньше {minn} доменов: "
                    +', '.join(f'{k}={n}' for k,n in sorted(small,key=lambda x:-x[1])[:8])+')')
    print()

CL=[d for d in BASE if closed(d)]
print(f"### ДОМЕНЫ С ЗАКРЫТЫМ ОКНОМ: {len(CL)} из {len(BASE)}\n")
block('СТРАНИЦ',lambda d:BASE[d]['pages']+' стр',CL)
block('ДАТЫ В ТЕКСТЕ',lambda d:BASE[d]['dates'],CL)
block('ЗОНА',lambda d:BASE[d]['zone'],CL)
block('ДЕНЬ ЗАПУСКА',lambda d:BASE[d]['day'],CL,minn=5)

# ---------- имя домена
def nametype(d):
    b=d.rsplit('.',1)[0]
    if b.isdigit(): return 'только цифры'
    if b.isalpha(): return 'только буквы'
    return 'микс букв и цифр'
block('ТИП ИМЕНИ',lambda d:nametype(d),CL)
block('ДЛИНА ИМЕНИ',lambda d:f"{len(d.rsplit('.',1)[0])} символа",CL)
def firstchar(d):
    c=d[0]
    return 'цифра' if c.isdigit() else 'буква'
block('ПЕРВЫЙ СИМВОЛ',lambda d:firstchar(d),CL)
def lastdigit(d):
    b=d.rsplit('.',1)[0]
    return f'последняя цифра {b[-1]}' if b[-1].isdigit() else 'кончается буквой'
block('ПОСЛЕДНИЙ СИМВОЛ',lambda d:lastdigit(d),CL,minn=10)

# ---------- бренды
TIER={}
for r in csv.DictReader(open(AN+'keys/keys_stats.csv',encoding='utf-8-sig'),delimiter=';'):
    TIER.setdefault(r['бренд'],r['тир'])
print('=== БРЕНДЫ, КОТОРЫЕ ДАЮТ КОНВЕРСИЮ ===')
mb=collections.Counter(e['sub'] for e in EV if e['type']=='reg')
tc=collections.Counter()
for b,n in mb.items(): tc[TIER.get(b,'нет в ядре')]+=n
tot=sum(tc.values())
print('  распределение РЕГИСТРАЦИЙ по тиру бренда:')
for k,v in tc.most_common(): print(f'     {k:<12}{v:>4}  ({100*v/tot:.0f}%)')
# для сравнения — распределение позиций Т10 по тиру на тех же доменах
t10=collections.Counter()
for p in SN['pools']:
    if p.get('excl'): continue
    s=p['snaps'][-1]
    for r in s['rows']:
        if r[2]<=10 and QD[r[0]][2]: t10[QD[r[0]][2]]+=1
tt=sum(t10.values())
print('  для сравнения — распределение КЛЮЧЕЙ В Т10 по тиру (свежие пулы):')
for k,v in t10.most_common(): print(f'     {k:<12}{v:>4}  ({100*v/tt:.0f}%)')
print('  и распределение самого ядра по тиру:')
core=collections.Counter(TIER.values()); ct=sum(core.values())
for k,v in core.most_common(): print(f'     {k:<12}{v:>4}  ({100*v/ct:.0f}%)')
print()
print('  сколько брендов дали 1 / 2 / 3+ регистрации:')
c=collections.Counter(mb.values())
for k in sorted(c,reverse=True): print(f'     {k} рег: {c[k]} брендов')
print(f'  всего брендов с деньгами: {len(mb)}; в ядре {len(TIER)} брендов')

print('\n\n############ ПРОВЕРКА НА ЛОЖНЫЕ СВЯЗИ ############')
def nt(d):
    b=d.rsplit('.',1)[0]
    return 'цифры' if b.isdigit() else ('буквы' if b.isalpha() else 'микс')
print('\n=== Тип имени против группы: раздаётся ли он случайно? ===')
G=collections.defaultdict(collections.Counter)
for d in CL: G[BASE[d]['group'][:38]][nt(d)]+=1
big=[(g,c) for g,c in G.items() if sum(c.values())>=15]
print(f"{'группа':<40}{'цифры':>7}{'буквы':>7}{'микс':>6}")
for g,c in sorted(big,key=lambda x:-sum(x[1].values()))[:14]:
    print(f"{g:<40}{c['цифры']:>7}{c['буквы']:>7}{c['микс']:>6}")
print('\n=== Тип имени ВНУТРИ одной группы (там имена раздаются случайно) ===')
print(f"{'группа':<34}{'тип':<8}{'дом':>5}{'с рег':>7}{'доля':>8}")
tot=collections.defaultdict(lambda:[0,0])
for g,c in big:
    ds=[d for d in CL if BASE[d]['group'][:38]==g]
    if len(set(nt(d) for d in ds))<2: continue
    for t in ['цифры','буквы','микс']:
        sub=[d for d in ds if nt(d)==t]
        if len(sub)<4: continue
        w=sum(1 for d in sub if reg[d])
        tot[t][0]+=len(sub); tot[t][1]+=w
        print(f"{g[:34]:<34}{t:<8}{len(sub):>5}{w:>7}{100*w/len(sub):>7.0f}%")
print(f"\n{'ИТОГО внутри групп':<34}{'':<8}{'дом':>5}{'с рег':>7}{'доля':>8}")
for t,(n,w) in tot.items():
    se=100*math.sqrt((w/n)*(1-w/n)/n) if n else 0
    print(f"{'':<34}{t:<8}{n:>5}{w:>7}{100*w/n:>7.1f}% ± {se:.1f}")

print('\n=== 7 страниц против 12: не смешано ли с днём запуска? ===')
print(f"{'день':<14}{'7 стр: дом/с рег':>20}{'12 стр: дом/с рег':>22}")
for day in sorted(set(BASE[d]['day'] for d in CL)):
    a=[d for d in CL if BASE[d]['day']==day and BASE[d]['pages']=='7']
    b=[d for d in CL if BASE[d]['day']==day and BASE[d]['pages']=='12']
    if len(a)<4 or len(b)<4: continue
    wa=sum(1 for d in a if reg[d]); wb=sum(1 for d in b if reg[d])
    print(f"{day:<14}{f'{len(a)}/{wa} = {100*wa/len(a):.0f}%':>20}{f'{len(b)}/{wb} = {100*wb/len(b):.0f}%':>22}")

print('\n=== Последняя цифра: сколько корзин и чего ждать случайно ===')
import random
base=sum(1 for d in CL if reg[d])/len(CL)
sizes=[]
for k in range(10):
    s=[d for d in CL if d.rsplit('.',1)[0][-1]==str(k)]
    if s: sizes.append(len(s))
hi=0
for _ in range(20000):
    m=0
    for n in sizes:
        w=sum(1 for _ in range(n) if random.random()<base)
        m=max(m,w/n)
    if m>=0.50: hi+=1
print(f'  базовая доля {100*base:.1f}%, корзин {len(sizes)}, размеры {sizes}')
print(f'  вероятность, что ХОТЯ БЫ одна корзина случайно даст 50%+: {100*hi/20000:.0f}%')
