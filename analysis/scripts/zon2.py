# Зоны на свежих запусках 01.09: парные сравнения при одинаковом контенте.
import json,statistics as st
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
D=json.load(open(SP+'snapr.json')); QD=D['qd']
P={p['id']:p for p in D['pools']}
VS=('ВЧ','СЧ')
def stats(pid,doms=None,snap=-1,tf=None):
    p=P[pid]; s=p['snaps'][snap]; doms=doms or p['doms']
    idx={d:p['doms'].index(d) for d in doms}
    R=[r for r in s['rows'] if not tf or QD[r[0]][2] in tf]
    per={d:[r for r in R if r[1]==idx[d]] for d in doms}
    t10=[sum(1 for r in per[d] if r[2]<=10) for d in doms]
    t100=[len(per[d]) for d in doms]
    return dict(n=len(doms),lab=s['lab'],age=s['age'],t10=sum(t10),t100=sum(t100),
                per=round(sum(t10)/len(doms),2),med=st.median(t10),
                hit=sum(1 for x in t10 if x>0),
                nolead=round((sum(t10)-max(t10))/(len(t10)-1),2) if len(t10)>1 else None,
                dom={d:t for d,t in zip(doms,t10)})
def zsplit(pid,z): return [d for d in P[pid]['doms'] if d.endswith(z)]

def line(tag,a):
    print(f"  {tag:<26} дом {a['n']:>2}  Т10 {a['t10']:>4}  на домен {a['per']:>5}  "
          f"медиана {a['med']:>4}  без лидера {str(a['nolead']):>5}  зашло {a['hit']}/{a['n']}  сотня {a['t100']:>4}")

print('=== ПАРА A: 12 страниц с датами, создано 17:06, разница только в зоне (возраст 20 ч) ===')
for tf,nm in [(None,'все ключи'),(VS,'только ВЧ+СЧ')]:
    print(f' {nm}:')
    line('.casino (7 доменов)',stats('p12wd',tf=tf))
    line('.team+.lol (6 доменов)',stats('p12wt',tf=tf))

print('\n=== ПАРА B: внутри одной группы 1093-1098 (12 стр, даты) ===')
for tf,nm in [(None,'все ключи'),(VS,'только ВЧ+СЧ')]:
    print(f' {nm}:')
    line('.team (4)',stats('p12wt',zsplit('p12wt','.team'),tf=tf))
    line('.lol  (2)',stats('p12wt',zsplit('p12wt','.lol'),tf=tf))

print('\n=== ПАРА C: внутри одной группы 1118-1123 (7 стр, даты) ===')
for tf,nm in [(None,'все ключи'),(VS,'только ВЧ+СЧ')]:
    print(f' {nm}:')
    line('.team (4)',stats('p7wt',zsplit('p7wt','.team'),tf=tf))
    line('.lol  (2)',stats('p7wt',zsplit('p7wt','.lol'),tf=tf))

print('\n=== rvue.team против rvue.lol — одно имя, одна группа, один контент ===')
for tf,nm in [(None,'все'),(VS,'ВЧ+СЧ')]:
    a=stats('p7wt',['rvue.team'],tf=tf); b=stats('p7wt',['rvue.lol'],tf=tf)
    print(f"  {nm:<7} rvue.team Т10 {a['t10']:>3} сотня {a['t100']:>3}   |   rvue.lol Т10 {b['t10']:>3} сотня {b['t100']:>3}")

print('\n=== Все зоны 01.09 на последнем замере ===')
byz={}
for pid in ['p12nd','p12wd','p12wt','p7wt','nab']:
    for d in P[pid]['doms']:
        byz.setdefault('.'+d.split('.')[-1],[]).append((pid,d))
for z,lst in sorted(byz.items(),key=lambda x:-len(x[1])):
    for tf,nm in [(None,'все'),(VS,'ВЧ+СЧ')]:
        t10=sum(stats(pid,[d],tf=tf)['t10'] for pid,d in lst)
        t100=sum(stats(pid,[d],tf=tf)['t100'] for pid,d in lst)
        hit=sum(1 for pid,d in lst if stats(pid,[d],tf=tf)['t10']>0)
        print(f"  {z:<9}{nm:<7} дом {len(lst):>2}  Т10 {t10:>4}  на домен {t10/len(lst):>5.2f}  зашло {hit}/{len(lst)}  сотня {t100:>4}")

print('\n=== Динамика пары A по замерам (расходятся или сходятся) ===')
for si in range(3):
    a=stats('p12wd',snap=si); 
    b=stats('p12wt',snap=min(si,len(P['p12wt']['snaps'])-1))
    print(f"  замер {si+1}: .casino {a['lab']} +{a['age']}ч Т10/дом {a['per']:>5}   |   "
          f".team/.lol {b['lab']} +{b['age']}ч Т10/дом {b['per']:>5}")
