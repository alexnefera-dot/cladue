# Можно ли ранжировать бренды на текущих данных, или разброс есть, а рейтинг — нет.
import json,collections,math,random,re,glob,datetime as dt
from statistics import NormalDist
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
BAD={'yandex.ru','','—','ru.search.yahoo.com','alice.yandex.ru','youtube.com','ya.ru',
     'google.com','yahoo.com','yandex.kz','yandex.by','yandex.uz'}
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
CLOSED=sorted(d for d,v in D.items() if dat(v[0]) and (TODAY-dat(v[0])).days>=6)
RG=[e for e in EV if e['dom'] in CLOSED and e.get('sub') and e['type']=='reg']
nD=len(CLOSED)

print("=== 1. БРЕНД ИЛИ УДАЧНЫЙ ДОМЕН: повторяемость ===")
bd=collections.defaultdict(set)
for e in RG: bd[e['sub']].add(e['dom'])
br=collections.Counter(e['sub'] for e in RG)
multi=[(b,c,len(bd[b])) for b,c in br.items() if c>=2]
print(f"брендов с 2+ регистрациями: {len(multi)}")
same=sum(1 for b,c,nd in multi if nd==1)
print(f"из них повторились на РАЗНЫХ доменах: {len(multi)-same}, на одном домене: {same}")
print("=> повторение на разных доменах = свойство бренда, а не удачного домена")
print(f"{'бренд':<14}{'рег':>5}{'разных доменов':>16}")
for b,c,nd in sorted(multi,key=lambda x:-x[1])[:10]:
    print(f"{b:<14}{c:>5}{nd:>16}")

print("\n=== 2. СКОЛЬКО НУЛЕЙ ОЖИДАЕТСЯ ПО СЛУЧАЮ ===")
tot=len(RG); m=tot/NBRAND
exp0=NBRAND*math.exp(-m)
obs0=NBRAND-len(br)
print(f"регистраций {tot}, в среднем {m:.3f} на бренд")
print(f"нулевых брендов: наблюдаем {obs0}, по Пуассону ожидается {exp0:.0f}")
print(f"=> {obs0-exp0:.0f} 'лишних' нулей. Часть нулей — просто малая выборка,")
print("   поэтому «126 брендов не работают» читать нельзя: большинство просто не измерено.")

print("\n=== 3. МОЖНО ЛИ РАНЖИРОВАТЬ БРЕНДЫ: сплит-половина ===")
random.seed(3)
def spearman(xs,ys):
    def rk(v):
        s=sorted(range(len(v)),key=lambda i:v[i])
        r=[0]*len(v); i=0
        while i<len(s):
            j=i
            while j+1<len(s) and v[s[j+1]]==v[s[i]]: j+=1
            avg=(i+j)/2+1
            for k in range(i,j+1): r[s[k]]=avg
            i=j+1
        return r
    a,b=rk(xs),rk(ys); n=len(a)
    ma,mb=sum(a)/n,sum(b)/n
    num=sum((a[i]-ma)*(b[i]-mb) for i in range(n))
    den=math.sqrt(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b))
    return num/den if den else 0
cors=[]
brands=sorted(br)
for _ in range(200):
    dom=CLOSED[:]; random.shuffle(dom)
    h1=set(dom[:nD//2]); 
    c1=collections.Counter(e['sub'] for e in RG if e['dom'] in h1)
    c2=collections.Counter(e['sub'] for e in RG if e['dom'] not in h1)
    cors.append(spearman([c1[b] for b in brands],[c2[b] for b in brands]))
cors.sort()
print(f"корреляция рангов между случайными половинами доменов:")
print(f"  медиана {cors[100]:.3f}, 5%-95% [{cors[10]:.3f}; {cors[190]:.3f}]")
rel=2*cors[100]/(1+cors[100]) if cors[100]>0 else 0
print(f"надёжность полного набора (Spearman-Brown) {rel:.2f}")
print("=> " + ("рейтинг брендов воспроизводим" if rel>0.6 else
      "рейтинг брендов НЕ воспроизводим: разброс реален, но кто именно лучше — пока не измерено"))

print("\n=== 4. СКОЛЬКО НУЖНО, ЧТОБЫ РАНЖИРОВАТЬ БРЕНДЫ ===")
rate=tot/nD  # рег на домен
for mult in (2,4,8,16):
    n=nD*mult
    m2=rate*n/NBRAND
    print(f"  {n:>5} доменов ({mult}x): {m2:.1f} рег на бренд в среднем — "
          f"{'хватит на рейтинг' if m2>=10 else 'хватит на классы' if m2>=4 else 'мало'}")
print(f"\nа при делении на 3 класса (ВЧ/СЧ/НЧ) уже сейчас на класс приходится "
      f"~{tot/3:.0f} регистраций и ~{nD*NBRAND//3} поддоменов — это считается.")
