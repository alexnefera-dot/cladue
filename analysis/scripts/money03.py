# Конверсии из Book2 (27.08–03.09) в разрезе групп запуска.
import json,collections,datetime as dt,sys,os
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
AN='/home/user/cladue/analysis/'
EV=json.load(open(SP+'conv4.json'))
D=json.load(open(SP+'snapr.json')); P={p['id']:p for p in D['pools'] if not p.get('excl')}
GRP={}
for pid,p in P.items():
    for d in p['doms']: GRP[d]=p['name']
LD={pid:p['ltx'][:5] for pid,p in P.items()}
reg=collections.Counter(e['dom'] for e in EV if e['type']=='reg')
dep=collections.Counter(e['dom'] for e in EV if e['type']=='dep')
known=set(GRP)
print('=== Покрытие ===')
inn=[d for d in reg if d in known]
print(f"доменов с регистрациями: {len(reg)}; из них в отслеживаемых пулах: {len(inn)}; "
      f"регистраций у них: {sum(reg[d] for d in inn)} из {sum(reg.values())}")
print()
print('=== По пулам последних запусков ===')
print(f"{'Пул':<42}{'дом':>5}{'рег':>5}{'деп':>5}{'рег/дом':>9}{'заход':>8}")
rows=[]
for pid,p in P.items():
    r=sum(reg[d] for d in p['doms']); dp=sum(dep[d] for d in p['doms'])
    h=sum(1 for d in p['doms'] if reg[d])
    rows.append((p['name'],len(p['doms']),r,dp,r/len(p['doms']),h,p['ltx'][:5]))
for n,nd,r,dp,rp,h,ld in sorted(rows,key=lambda x:-x[4]):
    print(f"{n[:42]:<42}{nd:>5}{r:>5}{dp:>5}{rp:>9.2f}{h}/{nd:>4}   ({ld})")
print()
print('=== Домены сегодняшнего запуска (02.09), давшие регистрации ===')
T=[pid for pid in P if P[pid]['ltx'].startswith('02.09')]
for pid in T:
    for d in P[pid]['doms']:
        if reg[d]:
            subs=collections.Counter(e['sub'] for e in EV if e['dom']==d and e['type']=='reg')
            ts=sorted(e['t'] for e in EV if e['dom']==d and e['type']=='reg')
            print(f"  {d:<14} рег {reg[d]}  деп {dep[d]}  {P[pid]['name'][:40]:<40} "
                  f"бренды: {', '.join(f'{k} ({v})' for k,v in subs.most_common())}  первая: {ts[0]}")
print()
print('=== Возраст домена на момент регистрации (все известные пулы) ===')
LT={}
for pid,p in P.items():
    for d in p['doms']: LT[d]=p['ltx'][:11]
def parse(s):
    try: return dt.datetime.strptime('2026 '+s.split(' (')[0].strip(),'%Y %d.%m %H:%M')
    except: return None
buck=collections.Counter()
for e in EV:
    if e['type']!='reg' or e['dom'] not in LT: continue
    a=parse(LT[e['dom']])
    if not a: continue
    h=(dt.datetime.strptime(e['t'],'%Y-%m-%d %H:%M')-a).total_seconds()/3600
    if h<0: continue
    buck[int(h//24)+1]+=1
tot=sum(buck.values())
for k in sorted(buck): print(f'  сутки {k}: {buck[k]:>3} рег  ({100*buck[k]/tot:.0f}%)')
print()
print('=== Гео ===')
g=collections.Counter(e['geo'] for e in EV if e['type']=='reg')
for k,v in g.most_common(): print(f'  {k:<8}{v:>4}  ({100*v/sum(g.values()):.0f}%)')
print()
print('=== Бренды, дающие деньги ===')
b=collections.Counter(e['sub'] for e in EV if e['type']=='reg')
for k,v in b.most_common(15): print(f'  {k:<16}{v:>4}')
json.dump(dict(reg=dict(reg),dep=dict(dep)),open(SP+'money03.json','w'),ensure_ascii=False)
