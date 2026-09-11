# Конверсии за 10 и 11 сентября: к каким группам запуска относятся домены.
import json,collections,re,glob,datetime as dt
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
AN='/home/user/cladue/analysis/'
BAD={'yandex.ru','','—','ru.search.yahoo.com','alice.yandex.ru','youtube.com','ya.ru',
     'google.com','yahoo.com','yandex.kz','yandex.by','yandex.uz'}
EV=[e for e in json.load(open(SP+'conv9.json')) if e['dom'] not in BAD]
LAST=[e for e in EV if e['t'][:10] in ('2026-09-10','2026-09-11')]
# карта домен → (день, группа)
D={}
for f in sorted(glob.glob(AN+'launch_*.txt')):
    if '_flat' in f: continue
    md=re.search(r'launch_(\d\d\.\d\d)',f)
    if not md: continue
    day=md.group(1); main=None; extra=None; prev=False
    for l in open(f):
        l=l.rstrip(); s=l.strip(); h=None
        if l.startswith('## '): h=l[3:].strip()
        elif s.startswith('===') and s.endswith('==='): h=s.strip('= ').strip()
        elif s and not re.match(r'^[a-z0-9\-]+\.[a-z]+$',s) and not l.startswith('#'): h=s
        if h is not None:
            if prev and main: extra=h
            else: main=h; extra=None
            prev=True
        elif re.match(r'^[a-z0-9\-]+\.[a-z]+$',s):
            prev=False
            if 'ОДНИМ СПИСКОМ' in (main or '').upper(): continue
            D[s]=(day,main or '')
def clean(g):
    g=re.sub(r'\s*[—,(]\s*(id|создан|\d+\s*дом)[^,)]*\)?','',g or '')
    return re.sub(r'_?\d*…_\d+','',g).strip(' _·,')
print(f"конверсий за 10–11.09: {len(LAST)}  "
      f"(рег {sum(1 for e in LAST if e['type']=='reg')}, деп {sum(1 for e in LAST if e['type']=='dep')})")
print(f"доменов: {len({e['dom'] for e in LAST})}\n")

agg=collections.defaultdict(lambda:{'r':0,'d':0,'doms':collections.defaultdict(lambda:[0,0,collections.Counter()])})
for e in LAST:
    day,g = D.get(e['dom'],('?','— списка не было —'))
    k=(day,clean(g))
    a=agg[k]; a['r']+= e['type']=='reg'; a['d']+= e['type']=='dep'
    x=a['doms'][e['dom']]; x[0]+= e['type']=='reg'; x[1]+= e['type']=='dep'; x[2][e['sub']]+=1
print(f"{'день зап.':<10}{'группа':<46}{'рег':>4}{'деп':>4}{'дом':>5}")
for k in sorted(agg,key=lambda x:(-(agg[x]['r']+agg[x]['d']),x[0])):
    a=agg[k]
    print(f"{k[0]:<10}{k[1][:44]:<46}{a['r']:>4}{a['d']:>4}{len(a['doms']):>5}")
print()
print("--- поимённо ---")
for k in sorted(agg,key=lambda x:(-(agg[x]['r']+agg[x]['d']),x[0])):
    a=agg[k]
    print(f"\n{k[0]}  {k[1]}")
    for dom,(r,dp,br) in sorted(a['doms'].items(),key=lambda x:(-x[1][1],-x[1][0])):
        bs=' '.join(b+('×%d'%n if n>1 else '') for b,n in br.most_common())
        print(f"   {dom:<20}рег {r}  деп {dp}   {bs}")
# сводки
print("\n--- по дню запуска ---")
c=collections.defaultdict(lambda:[0,0,set()])
for e in LAST:
    day,_=D.get(e['dom'],('?',''))
    x=c[day]; x[0]+= e['type']=='reg'; x[1]+= e['type']=='dep'; x[2].add(e['dom'])
for k in sorted(c,key=lambda s:(s[3:],s[:2]) if s!='?' else ('99','99')):
    print(f"   {k:<8}рег {c[k][0]:>2}  деп {c[k][1]:>2}  доменов {len(c[k][2])}")
print("\n--- по зоне ---")
z=collections.defaultdict(lambda:[0,0,set()])
for e in LAST:
    k='.'+e['dom'].split('.')[-1]
    z[k][0]+= e['type']=='reg'; z[k][1]+= e['type']=='dep'; z[k][2].add(e['dom'])
for k,v in sorted(z.items(),key=lambda x:-x[1][0]):
    print(f"   {k:<9}рег {v[0]:>2}  деп {v[1]:>2}  доменов {len(v[2])}")

# знаменатели: сколько доменов в каждой группе и какая доля уже сработала за всё время
import datetime as dt2
TODAY=dt2.date(2026,9,11)
def dat(s):
    m=re.match(r'(\d\d)\.(\d\d)',s); return dt2.date(2026,int(m.group(2)),int(m.group(1))) if m else None
GR=collections.defaultdict(list)
for d,(day,g) in D.items(): GR[(day,clean(g))].append(d)
ALL=[e for e in json.load(open(SP+'convall.json')) if e['dom'] not in BAD]
regall=collections.Counter(e['dom'] for e in ALL if e['type']=='reg')
depall=collections.Counter(e['dom'] for e in ALL if e['type']=='dep')
print("\n--- те же группы со знаменателем (за всё время, не только 10–11.09) ---")
print(f"{'день':<8}{'группа':<44}{'дом':>4}{'с рег':>6}{'доля':>7}{'рег':>5}{'деп':>4}  окно")
rows=[]
for k in sorted(agg,key=lambda x:(-(agg[x]['r']+agg[x]['d']),x[0])):
    if k[0]=='?':
        print(f"{'?':<8}{k[1][:42]:<44}{'—':>4}{'—':>6}{'—':>7}{'—':>5}{'—':>4}  дня нет"); continue
    ds=GR.get(k,[])
    if not ds: continue
    n=len(ds); w=sum(1 for d in ds if regall[d]); r=sum(regall[d] for d in ds); dp=sum(depall[d] for d in ds)
    age=(TODAY-dat(k[0])).days
    win='закрыто' if age>=6 else f'открыто, {age} из 6'
    print(f"{k[0]:<8}{k[1][:42]:<44}{n:>4}{w:>6}{100*w/n:>6.0f}%{r:>5}{dp:>4}  {win}")
    rows.append((k[0],k[1],n,w,r,dp,win))
json.dump(dict(rows=rows),open(SP+'last2d.json','w'),ensure_ascii=False)
