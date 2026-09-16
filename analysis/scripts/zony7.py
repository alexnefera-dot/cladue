"""Зоны на контролируемом окне: сравниваем только те дни запуска,
когда обе зоны были активны. Иначе .team тянет за собой мёртвый август."""
import csv,collections,re,glob
from math import comb
AN='/home/user/cladue/analysis/'
PRICE={'team':2,'lol':1,'casino':7,'buzz':3}
NEED={'team':1.0,'lol':0.5,'casino':3.5,'buzz':1.5}   # во сколько раз лучше .team ради окупаемости

rows=[r for r in csv.DictReader(open(AN+'konversii_7dney.csv',encoding='utf-8-sig'))]
for r in rows: r['base']='.'.join(r['source'].split('.')[1:])
day={}
for f in sorted(glob.glob(AN+'launch_*.txt')):
    if '_flat' in f: continue
    m=re.search(r'launch_(\d\d\.\d\d)',f)
    if not m: continue
    for l in open(f):
        s=l.strip()
        if re.fullmatch(r'[a-z0-9][a-z0-9.-]*\.[a-z]+', s): day.setdefault(s,m.group(1))
depc=collections.Counter(r['base'] for r in rows if r['event']=='dep')

def run(days,label):
    dom=[d for d,dd in day.items() if dd in days]
    z=collections.Counter(d.rsplit('.',1)[-1] for d in dom)
    fd=collections.Counter(d.rsplit('.',1)[-1] for d in dom for _ in range(depc[d]))
    base=fd['team']/z['team'] if z['team'] else 0
    print(f"\n=== {label} ===")
    print(f"{'зона':<9}{'дом':>6}{'ФД':>4}{'ФД/дом':>9}{'к .team':>9}{'нужно':>7}"
          f"{'расход':>8}{'доход':>7}{'на домен':>10}")
    for k in ('team','lol','casino','buzz'):
        if not z[k]: continue
        rate=fd[k]/z[k]; cost=z[k]*PRICE[k]; inc=fd[k]*40
        print(f".{k:<8}{z[k]:>6}{fd[k]:>4}{rate:>9.4f}{rate/base if base else 0:>8.2f}x"
              f"{NEED[k]:>6.1f}x{cost:>8}{inc:>7}{(inc-cost)/z[k]:>+10.2f}")
    a,na,b,nb=fd['casino'],z['casino'],fd['team'],z['team']
    if a+b:
        n=a+b; p0=na/(na+nb)
        pv=min(1,2*sum(comb(n,k)*p0**k*(1-p0)**(n-k) for k in range(a,n+1)))
        print(f"  .casino {a} ФД из {n}, ожидание {n*p0:.2f}, точный двусторонний p = {pv:.3f}")

run([f'{d:02d}.09' for d in range(7,13)], 'запуски 07–12.09 — обе зоны активны')
run(['08.09','09.09','10.09'],            'запуски 08–10.09 — окно закрыто у всех')
run(sorted(set(day.values())),            'ВЕСЬ реестр — знаменатель спутан с возрастом')
print("\nПоследний срез оставлен намеренно: на нём .casino даёт 4.0x и p=0.009,")
print("и это артефакт. .casino не запускался после 12.09, а .team и .lol запускались,")
print("плюс в знаменателе .team сотни августовских доменов вне своего окна.")
