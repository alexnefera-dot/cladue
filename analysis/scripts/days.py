# Есть ли удачные дни запуска, или разброс между днями — обычная случайность.
import json,collections,math,random,re,datetime as dt
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
EV=json.load(open(SP+'convall.json'))
db=json.load(open(SP+'db.json'))
SN=json.load(open(SP+'snapr.json'))
reg=collections.Counter(e['dom'] for e in EV if e['type']=='reg')

DAY={}
for d,v in db.items():
    if d=='базовый домен': continue
    DAY[d]=str(v.get('made'))[:5]           # дата создания = прокси дня запуска для архива
for p in SN['pools']:
    if p.get('excl'): continue
    for x in p['doms']: DAY[x]=p['ltx'][:5]
MAN={'1893.team':'27.08','4328.team':'27.08','dprz.team':'27.08','glhd.team':'27.08',
     'hjsf.team':'27.08','ogax.team':'27.08','c5vt.team':'27.08','k6m.team':'27.08'}
DAY.update(MAN)
TODAY=dt.date(2026,9,3)
def dat(s):
    m=re.match(r'(\d\d)\.(\d\d)',s)
    return dt.date(2026,int(m.group(2)),int(m.group(1))) if m else None
CL=[d for d in DAY if dat(DAY[d]) and (TODAY-dat(DAY[d])).days>=6]
print(f"доменов с известным днём запуска: {len(DAY)}; с закрытым окном: {len(CL)}")
base=sum(1 for d in CL if reg[d])/len(CL)
print(f"базовая доля доменов с регистрацией: {100*base:.1f}%\n")

G=collections.defaultdict(list)
for d in CL: G[DAY[d]].append(d)
rows=[]
for k in sorted(G,key=lambda x:dat(x)):
    ds=G[k]; n=len(ds); w=sum(1 for d in ds if reg[d]); r=sum(reg[d] for d in ds)
    se=100*math.sqrt(base*(1-base)/n)
    z=(100*w/n-100*base)/se if se else 0
    rows.append((k,n,w,100*w/n,se,r,r/n,z))
print(f"{'день запуска':<14}{'доменов':>8}{'с рег.':>7}{'доля':>8}{'ожид.±':>8}{'откл.':>7}{'рег':>6}{'рег/дом':>9}")
for k,n,w,p,se,r,rp,z in rows:
    mark=' ←' if abs(z)>=2 else ''
    print(f"{k:<14}{n:>8}{w:>7}{p:>7.1f}%{se:>7.1f}{z:>+7.1f}σ{r:>6}{rp:>9.2f}{mark}")

# симуляция: насколько велик разброс, если дни ни при чём
obs=max(p for _,_,_,p,_,_,_,_ in rows)-min(p for _,_,_,p,_,_,_,_ in rows)
sizes=[n for _,n,_,_,_,_,_,_ in rows]
big=0; spreads=[]
for _ in range(20000):
    ps=[100*sum(1 for _ in range(n) if random.random()<base)/n for n in sizes]
    s=max(ps)-min(ps); spreads.append(s)
    if s>=obs: big+=1
spreads.sort()
print(f"\nразмах между лучшим и худшим днём: {obs:.1f} п.п.")
print(f"если дни ни при чём, такой размах при этих размерах групп бывает в {100*big/20000:.0f}% случаев")
print(f"типичный случайный размах: медиана {spreads[10000]:.1f} п.п., "
      f"в 95% случаев до {spreads[19000]:.1f} п.п.")

print('\n=== Читаем иначе: в какие дни ПРИХОДИЛИ конверсии ===')
byday=collections.Counter(e['t'][:10] for e in EV if e['type']=='reg')
print(f"регистрации приходили в {len(byday)} разных дней из "
      f"{(dt.date(2026,9,3)-dt.date(2026,8,21)).days+1} в периоде")
for k in sorted(byday): print(f"   {k}: {'█'*byday[k]} {byday[k]}")
v=list(byday.values())
print(f"   минимум {min(v)}, максимум {max(v)}, в среднем {sum(v)/len(v):.1f} в сутки")

print('\n=== Сколько РАЗНЫХ дней запуска дали хоть одну конверсию ===')
alld=collections.Counter(DAY[d] for d in DAY if dat(DAY[d]))
hit=collections.Counter(DAY[d] for d in DAY if reg[d] and dat(DAY[d]))
print(f"   дней запуска всего: {len(alld)}; из них дали хоть одну конверсию: {len(hit)}")
for k in sorted(alld,key=lambda x:dat(x)):
    print(f"   {k}: доменов {alld[k]:>3}, с деньгами {hit.get(k,0):>2}"
          +('' if hit.get(k) else '   ← ни одной'))

print('\n\n############ ПРОВЕРКА: ЧТО ИЗ ЭТОГО АРТЕФАКТ ############')
first=min(e['t'] for e in EV)[:10]
print(f"\n1) Выгрузка конверсий начинается {first}. Три четверти регистраций приходят")
print("   в первые двое суток жизни домена. Значит у доменов, запущенных до 22.08,")
print("   самые доходные дни ПРОСТО НЕ ПОПАЛИ в данные.")
for k in ['19.08','20.08','21.08']:
    a=dat(k); miss=(dt.date(2026,8,21)-a).days
    print(f"   запуск {k}: не покрыто первых {miss} сут. жизни — а это ~"
          f"{[0,18,49,75,90,95][min(miss,5)]}% всего заработка домена")

print("\n2) Домены 27.08 я добавил вручную ИМЕННО ПОТОМУ, что они были в списке")
print("   с конверсиями. Отсюда 8 из 8 = 100%: это отбор по результату, а не результат.")

OK=[d for d in CL if dat(DAY[d])>=dt.date(2026,8,22) and DAY[d]!='27.08']
print(f"\n3) Чистая выборка: запуск с 22.08, окно закрыто, без ручного 27.08 — {len(OK)} доменов")
b2=sum(1 for d in OK if reg[d])/len(OK)
G2=collections.defaultdict(list)
for d in OK: G2[DAY[d]].append(d)
print(f"   базовая доля {100*b2:.1f}%\n")
print(f"{'день запуска':<14}{'доменов':>8}{'с рег.':>7}{'доля':>8}{'ожид.±':>8}{'откл.':>7}{'рег/дом':>9}")
rows2=[]
for k in sorted(G2,key=lambda x:dat(x)):
    ds=G2[k]; n=len(ds); w=sum(1 for d in ds if reg[d]); r=sum(reg[d] for d in ds)
    se=100*math.sqrt(b2*(1-b2)/n); z=(100*w/n-100*b2)/se if se else 0
    rows2.append((k,n,100*w/n)); 
    print(f"{k:<14}{n:>8}{w:>7}{100*w/n:>7.1f}%{se:>7.1f}{z:>+7.1f}σ{r/n:>9.2f}")
obs2=max(p for _,_,p in rows2)-min(p for _,_,p in rows2)
sizes2=[n for _,n,_ in rows2]
big=0; sp=[]
for _ in range(20000):
    ps=[100*sum(1 for _ in range(n) if random.random()<b2)/n for n in sizes2]
    s=max(ps)-min(ps); sp.append(s)
    if s>=obs2: big+=1
sp.sort()
print(f"\n   размах между днями: {obs2:.1f} п.п.")
print(f"   случайно такой размах бывает в {100*big/20000:.0f}% случаев "
      f"(медиана случайного размаха {sp[10000]:.1f}, 95-й процентиль {sp[19000]:.1f})")
big2=0
sizes3=[n for k,n,_ in rows2 if n>=20]
if len(sizes3)>=2:
    rows3=[(k,n,p) for k,n,p in rows2 if n>=20]
    obs3=max(p for _,_,p in rows3)-min(p for _,_,p in rows3)
    for _ in range(20000):
        ps=[100*sum(1 for _ in range(n) if random.random()<b2)/n for n in sizes3]
        if max(ps)-min(ps)>=obs3: big2+=1
    print(f"   только дни от 20 доменов ({', '.join(k for k,_,_ in rows3)}): "
          f"размах {obs3:.1f} п.п., случайно в {100*big2/20000:.0f}% случаев")
