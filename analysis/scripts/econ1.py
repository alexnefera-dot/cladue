# Юнит-экономика запусков: цена домена по зоне против выручки с депозитов.
# Цены: .casino $7, .team $2, .lol $1, контент бесплатный. Один депозит = $40.
import json,collections,math,re,glob,datetime as dt
from math import comb
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
BAD={'yandex.ru','','—','ru.search.yahoo.com','alice.yandex.ru','youtube.com','ya.ru',
     'google.com','yahoo.com','yandex.kz','yandex.by','yandex.uz'}
PRICE={'casino':7.0,'team':2.0,'lol':1.0,'buzz':1.0}
DEP_VAL=40.0
TODAY=dt.date(2026,9,12)

EV=[e for e in json.load(open(SP+'convall.json')) if e['dom'] not in BAD]
reg=collections.Counter(); dep=collections.Counter()
for e in EV: (reg if e['type']=='reg' else dep)[e['dom']]+=1

def dat(s):
    m=re.match(r'(\d\d)\.(\d\d)',s)
    return dt.date(2026,int(m.group(2)),int(m.group(1))) if m else None

# ---- карта домен -> (день, группа, доп.заголовок, час создания)
D={}
for f in sorted(glob.glob('/home/user/cladue/analysis/launch_*.txt')):
    if '_flat' in f: continue
    md=re.search(r'launch_(\d\d\.\d\d)',f)
    if not md: continue
    day=md.group(1); main=None; extra=None; hour=None; prev=False
    for l in open(f):
        l=l.rstrip(); s2=l.strip(); h=None
        if l.startswith('## '): h=l[3:].strip()
        elif s2.startswith('===') and s2.endswith('==='): h=s2.strip('= ').strip()
        elif s2 and not re.match(r'^[a-z0-9\-]+\.[a-z]+$',s2) and not l.startswith('#'): h=s2
        if h is not None:
            mh=re.search(r'создан\s+(\d\d):(\d\d)',h)
            if prev and main:
                extra=h
                if mh: hour=int(mh.group(1))
            else:
                main=h; extra=None; hour=int(mh.group(1)) if mh else None
            prev=True
        elif re.match(r'^[a-z0-9\-]+\.[a-z]+$',s2):
            prev=False
            if 'ОДНИМ СПИСКОМ' in (main or '').upper(): continue
            D[s2]=(day,main or '',extra or '',hour)

# все домены реестра (включая те, у которых нет разбивки по группам)
ALL=set(x.strip() for x in open('/home/user/cladue/analysis/domains_flat.txt') if x.strip())
ALL|=set(D)

def zone(d): return d.split('.')[-1]
def cost(d): return PRICE.get(zone(d),1.0)

CLOSED={d:v for d,v in D.items() if dat(v[0]) and (TODAY-dat(v[0])).days>=6}

def econ(title,groups,note=''):
    print(f"\n=== {title} ===" + (f"  ({note})" if note else ''))
    print(f"{'':<18}{'доменов':>8}{'затраты$':>10}{'рег':>6}{'деп':>5}{'выручка$':>10}{'итог$':>9}{'ROI':>8}{'$/домен':>9}")
    tot=[0,0.0,0,0]
    for k,ds in groups:
        n=len(ds); c=sum(cost(d) for d in ds)
        r=sum(reg[d] for d in ds); p=sum(dep[d] for d in ds)
        rev=p*DEP_VAL; prof=rev-c
        print(f"{str(k)[:18]:<18}{n:>8}{c:>10.0f}{r:>6}{p:>5}{rev:>10.0f}{prof:>9.0f}"
              f"{(rev/c if c else 0):>7.2f}x{prof/n:>9.2f}")
        tot[0]+=n; tot[1]+=c; tot[2]+=r; tot[3]+=p
    n,c,r,p=tot; rev=p*DEP_VAL; prof=rev-c
    print(f"{'ИТОГО':<18}{n:>8}{c:>10.0f}{r:>6}{p:>5}{rev:>10.0f}{prof:>9.0f}"
          f"{(rev/c if c else 0):>7.2f}x{(prof/n if n else 0):>9.2f}")
    return tot

# 1. Порог безубыточности по зонам
print("=== ПОРОГ БЕЗУБЫТОЧНОСТИ ===")
print(f"{'зона':<10}{'цена$':>8}{'нужно деп на 1 домен':>24}{'или 1 деп на N доменов':>26}")
for z,pr in sorted(PRICE.items(),key=lambda x:-x[1]):
    if z=='buzz': continue
    print(f".{z:<9}{pr:>8.0f}{pr/DEP_VAL:>24.3f}{DEP_VAL/pr:>26.1f}")

# 2. Вся история по зонам (все домены реестра)
byz=collections.defaultdict(list)
for d in ALL: byz['.'+zone(d)].append(d)
econ('ПО ЗОНАМ — весь реестр',sorted(byz.items(),key=lambda x:-len(x[1])),
     f'{len(ALL)} доменов, окна частью открыты')

# 3. По зонам, только закрытые окна
byzc=collections.defaultdict(list)
for d in CLOSED: byzc['.'+zone(d)].append(d)
econ('ПО ЗОНАМ — закрытые окна',sorted(byzc.items(),key=lambda x:-len(x[1])),
     f'{len(CLOSED)} доменов')

# 4. По страницам (закрытые окна)
def pages(v):
    g=v[1]
    m=re.search(r'(?:^|[^\d])(\d+)\s*(?:pages|page|стр)',g)
    if m: return m.group(1)+' стр'
    m=re.match(r'clean(\d+)',g)
    if m: return m.group(1)+' стр'
    return None
byp=collections.defaultdict(list)
for d,v in CLOSED.items():
    k=pages(v)
    if k: byp[k].append(d)
econ('ПО СТРАНИЦАМ — закрытые окна',
     sorted(byp.items(),key=lambda x:-len(x[1])),'контент бесплатный, затраты = только домены')

# 5. Страницы x зона
bypz=collections.defaultdict(list)
for d,v in CLOSED.items():
    k=pages(v)
    if k: bypz[f'{k} / .{zone(d)}'].append(d)
econ('СТРАНИЦЫ x ЗОНА',[(k,v) for k,v in sorted(bypz.items(),key=lambda x:-len(x[1])) if len(v)>=15])

# 6. Источник контента
def src(v):
    g=(v[1]+' '+v[2]).lower()
    if re.match(r'nabor',g) or 'набор' in g: return 'свой: наборы'
    if 'content_script' in g or 'script_yandex' in g or 'content-2026' in g: return 'свой: генератор'
    if g.startswith('new') or 'clean' in g or 'archive' in g: return 'присланный'
    return None
bys=collections.defaultdict(list)
for d,v in CLOSED.items():
    k=src(v)
    if k: bys[k].append(d)
econ('ПО ИСТОЧНИКУ КОНТЕНТА',sorted(bys.items(),key=lambda x:-len(x[1])))

# 7. Час запуска
byh=collections.defaultdict(list)
for d,v in CLOSED.items():
    if v[3] is not None: byh[v[3]].append(d)
print(f"\n=== ЧАС ЗАПУСКА — закрытые окна, {sum(len(v) for v in byh.values())} доменов ===")
print(f"{'час':<6}{'доменов':>8}{'с рег':>7}{'заход':>8}{'рег':>6}{'деп':>5}{'итог$':>9}")
for h in sorted(byh):
    ds=byh[h]; n=len(ds); w=sum(1 for d in ds if reg[d])
    c=sum(cost(d) for d in ds); p=sum(dep[d] for d in ds)
    print(f"{h:02d}:00{'':<1}{n:>8}{w:>7}{100*w/n:>7.1f}%{sum(reg[d] for d in ds):>6}{p:>5}{p*DEP_VAL-c:>9.0f}")
# агрегат по блокам суток
blocks={'ночь 00-05':range(0,6),'утро 06-11':range(6,12),'день 12-17':range(12,18),'вечер 18-23':range(18,24)}
bb=collections.defaultdict(list)
for h,ds in byh.items():
    for name,rng in blocks.items():
        if h in rng: bb[name].extend(ds)
econ('БЛОК СУТОК',[(k,bb[k]) for k in blocks if bb[k]])

# 8. День недели
bwd=collections.defaultdict(list)
WD=['пн','вт','ср','чт','пт','сб','вс']
for d,v in CLOSED.items():
    dd=dat(v[0])
    if dd: bwd[f'{WD[dd.weekday()]}'].append(d)
econ('ДЕНЬ НЕДЕЛИ',[(k,bwd[k]) for k in WD if bwd[k]])

# 9. Что нужно для положительной математики
print("\n=== ЧТО НУЖНО, ЧТОБЫ МАТЕМАТИКА БИЛАСЬ ===")
n=len(ALL); c=sum(cost(d) for d in ALL)
p=sum(dep[d] for d in ALL); r=sum(reg[d] for d in ALL)
print(f"весь реестр: {n} доменов, затраты ${c:.0f}, {r} рег, {p} деп, выручка ${p*DEP_VAL:.0f}, итог ${p*DEP_VAL-c:+.0f}")
if r: print(f"конверсия рег->деп: {100*p/r:.1f}%  ({p}/{r})")
print(f"депозитов на домен сейчас: {p/n:.4f}   нужно в среднем: {c/n/DEP_VAL:.4f}")
print(f"то есть {'хватает с запасом x%.2f'%(p*DEP_VAL/c) if p*DEP_VAL>c else 'не хватает'}")
# при текущей рег->деп конверсии сколько нужно регистраций на домен
if r:
    k=p/r
    print(f"\nпри конверсии рег->деп {100*k:.1f}% один домен должен давать регистраций:")
    for z,pr in sorted(PRICE.items(),key=lambda x:-x[1]):
        if z=='buzz': continue
        print(f"  .{z:<8} {pr/DEP_VAL/k:.3f} рег/домен   (сейчас по реестру {r/n:.3f})")
