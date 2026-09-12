# Свой контент против присланного, с поправкой на то, что clean/archive/NEW — присланный.
import json,collections,math,re,glob,datetime as dt
from math import comb
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
BAD={'yandex.ru','','—','ru.search.yahoo.com','alice.yandex.ru','youtube.com','ya.ru',
     'google.com','yahoo.com','yandex.kz','yandex.by','yandex.uz'}
EV=[e for e in json.load(open(SP+'convall.json')) if e['dom'] not in BAD]
reg=collections.Counter(e['dom'] for e in EV if e['type']=='reg')
dep=collections.Counter(e['dom'] for e in EV if e['type']=='dep')
TODAY=dt.date(2026,9,12)
def dat(s):
    m=re.match(r'(\d\d)\.(\d\d)',s); return dt.date(2026,int(m.group(2)),int(m.group(1))) if m else None
D={}
for f in sorted(glob.glob('analysis/launch_*.txt')):
    if '_flat' in f: continue
    md=re.search(r'launch_(\d\d\.\d\d)',f)
    if not md: continue
    day=md.group(1); main=None; prev=False
    for l in open(f):
        l=l.rstrip(); s=l.strip(); h=None
        if l.startswith('## '): h=l[3:].strip()
        elif s.startswith('===') and s.endswith('==='): h=s.strip('= ').strip()
        elif s and not re.match(r'^[a-z0-9\-]+\.[a-z]+$',s) and not l.startswith('#'): h=s
        if h is not None:
            if not (prev and main): main=h
            prev=True
        elif re.match(r'^[a-z0-9\-]+\.[a-z]+$',s):
            prev=False
            if 'ОДНИМ СПИСКОМ' in (main or '').upper(): continue
            D[s]=(day,main or '')
def src(g):
    g=g or ''
    if re.search(r'Generator|генератор',g,re.I): return 'свой · генератор'
    if re.search(r'nabor|Набор|аккаунт|Вебмастера|вебмастера',g,re.I): return 'свой · наборы'
    if re.search(r'NEW\d|clean\d|archive\d|Content_script|script_yandex|content-\d|page_|7page|12page',g): return 'присланный'
    if re.search(r'Выдача|выдач',g,re.I): return 'сайты из выдачи'
    return None
CL={d:v for d,v in D.items() if dat(v[0]) and (TODAY-dat(v[0])).days>=6}
def fisher(a,b,c,d):
    n=a+b+c+d; r1=a+b; c1=a+c
    tot=comb(n,r1); obs=comb(c1,a)*comb(n-c1,b); p=0
    for x in range(max(0,r1-(n-c1)),min(r1,c1)+1):
        v=comb(c1,x)*comb(n-c1,r1-x)
        if v<=obs+1e-9: p+=v
    return p/tot
G=collections.defaultdict(list)
unk=[]
for d,v in CL.items():
    k=src(v[1])
    if k: G[k].append(d)
    else: unk.append((d,v[1]))
print("свой контент против присланного, только закрытые окна:")
print(f"{'':<22}{'доменов':>8}{'с рег':>7}{'доля':>8}{'±':>6}{'рег':>6}{'деп':>5}")
res={}
for k,ds in sorted(G.items(),key=lambda x:-len(x[1])):
    n=len(ds); w=sum(1 for d in ds if reg[d]); p=w/n
    se=100*math.sqrt(p*(1-p)/n)
    res[k]=(n,w)
    print(f"{k:<22}{n:>8}{w:>7}{100*p:>7.1f}%{se:>6.1f}{sum(reg[d] for d in ds):>6}{sum(dep[d] for d in ds):>5}")
own=[d for k in G if k.startswith('свой') for d in G[k]]
ext=G.get('присланный',[])
no=len(own); wo=sum(1 for d in own if reg[d])
ne=len(ext); we=sum(1 for d in ext if reg[d])
print(f"\nсвой (генератор+наборы): {wo}/{no} = {100*wo/no:.1f}%")
print(f"присланный:              {we}/{ne} = {100*we/ne:.1f}%")
print(f"Fisher p = {fisher(wo,no-wo,we,ne-we):.4f}")
print(f"\nне классифицировано: {len(unk)} доменов")
c=collections.Counter(g for _,g in unk)
for g,n in c.most_common(6): print(f"   {n:>3}  {g[:60]}")

print("\n=== не перепутан ли источник со страницами? ===")
def pages(g):
    m=re.search(r'(?:^|[^\d])(\d+)\s*(?:pages|page|стр|str)',g) or re.match(r'clean(\d+)',g)
    return m.group(1) if m else None
tab=collections.defaultdict(lambda:[0,0])
for d,v in CL.items():
    k=src(v[1]); pg=pages(v[1])
    if not k or not pg: continue
    kk=('свой' if k.startswith('свой') else 'присланный', pg+' стр')
    tab[kk][0]+=1; tab[kk][1]+= 1 if reg[d] else 0
print(f"{'источник':<14}{'страниц':<10}{'дом':>5}{'с рег':>7}{'доля':>8}")
for k in sorted(tab,key=lambda x:(x[0],x[1])):
    n,w=tab[k]
    print(f"{k[0]:<14}{k[1]:<10}{n:>5}{w:>7}{100*w/n:>7.1f}%")
print("\nвывод: у 'своего' контента страницы в имени почти не указаны,")
print("поэтому сравнение источников и сравнение страниц пересекаются.")
