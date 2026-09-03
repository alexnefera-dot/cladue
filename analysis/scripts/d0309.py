# Первый замер 03.09 12:03 по 67 доменам запуска 02.09 (возраст ~19,7 ч).
import json,sys,os,csv,statistics as st,collections,re
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import p01
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
AN='/home/user/cladue/analysis/'
TIER={}
for r in csv.DictReader(open(AN+'keys/keys_stats.csv',encoding='utf-8-sig'),delimiter=';'):
    TIER[r['ключ'].strip()]=(r['бренд'],r['тир'])
O,_=p01.parse(SP+'L05.xlsx')
S=O['02.09'][0]

G=[]
def g(name,cfg,doms): G.append(dict(n=name,c=cfg,d=doms))
g('12стр с датами NEW50 (_7…_10)','12/даты/NEW50',['kzgq.team','tgmb.team','t8n2.team','8193.team'])
g('7стр с датами NEW50 (_7…_11)','7/даты/NEW50',['qmpl.team','7326.team','0040.team','2465.team','4967.team'])
g('7стр БЕЗ дат NEW50 (_1…_14)','7/безДат/NEW50',
  ['j0s0.team','0348.team','4502.team','ciye.team','9012.team','5580.team','syoo.team',
   'ikmd.team','xfdr.team','3654.team','2369.team','8640.team','1185.team','7570.team'])
g('7стр с датами NEW50_2','7/даты/NEW50_2',['4235.team','0413.team','3242.team','8730.team','0540.team','oasc.team'])
g('12стр БЕЗ дат NEW50_2','12/безДат/NEW50_2',['8829.lol','tvuy.team','7395.lol','1083.lol','2418.lol','7590.team'])
g('12стр с датами NEW50_2','12/даты/NEW50_2',
  ['q7a.team','c2u3.team','9158.lol','rza.lol','0665.team','4229.team','4729.team','tgmb.lol',
   '2955.team','izlx.team','vzto.team','7395.team','3349.team','o5h7.team','9957.team','2801.team','5230.team'])
g('наборы 294303','наборы',['u0s.team','4202.team','c4x3.team','3064.lol','7180.lol','f4w.lol'])
g('наборы 284293','наборы',['9061.lol','0728.lol','7119.lol'])
g('наборы 274283','наборы',['7590.lol','0040.lol','8730.lol','h6k8.team','7027.team','5671.team'])

VS=('ВЧ','СЧ')
def stat(doms,tf=None):
    per={}
    for d in doms:
        ks=[k for k in S['per'].get(d,[]) if not tf or TIER.get(k['q'],(None,None))[1] in tf]
        per[d]=ks
    t10=[sum(1 for k in per[d] if k['p']<=10) for d in doms]
    t100=[len(per[d]) for d in doms]
    return dict(n=len(doms),t10=sum(t10),t100=sum(t100),per=sum(t10)/len(doms),
                med=st.median(t10),hit=sum(1 for x in t10 if x>0),
                nolead=(sum(t10)-max(t10))/(len(t10)-1) if len(t10)>1 else None,
                t3=sum(1 for d in doms for k in per[d] if k['p']<=3),
                dom=dict(zip(doms,t10)))
def line(tag,a,w=34):
    nl='—' if a['nolead'] is None else f"{a['nolead']:.2f}"
    print(f"  {tag:<{w}} дом {a['n']:>2}  Т10 {a['t10']:>4}  на дом {a['per']:>5.2f}  "
          f"мед {a['med']:>4.1f}  без лидера {nl:>5}  зашло {a['hit']}/{a['n']}  сотня {a['t100']:>4}")

print('ЗАМЕР 03.09 12:03 — запуск 02.09 ~16:20, возраст ~19,7 ч, 67 доменов\n')
print('=== По веткам, все ключи ===')
for x in sorted(G,key=lambda y:-stat(y['d'])['per']): line(x['n'],stat(x['d']))
print('\n=== По веткам, только ВЧ+СЧ ===')
for x in sorted(G,key=lambda y:-stat(y['d'],VS)['per']): line(x['n'],stat(x['d'],VS))

BY={x['n']:x['d'] for x in G}
tm=lambda L:[d for d in L if d.endswith('.team')]
lo=lambda L:[d for d in L if d.endswith('.lol')]

print('\n=== ЧИСТЫЕ СРЕЗЫ ПО ДАТАМ ===')
CUTS=[
 ('7 стр · NEW50 · .team  (всё совпадает)',
  BY['7стр БЕЗ дат NEW50 (_1…_14)'],BY['7стр с датами NEW50 (_7…_11)']),
 ('12 стр · NEW50_2 · .lol  (всё совпадает)',
  lo(BY['12стр БЕЗ дат NEW50_2']),lo(BY['12стр с датами NEW50_2'])),
 ('12 стр · NEW50_2 · .team  (перекос 2 против 14)',
  tm(BY['12стр БЕЗ дат NEW50_2']),tm(BY['12стр с датами NEW50_2'])),
 ('7 стр · .team · семейства разные',
  BY['7стр БЕЗ дат NEW50 (_1…_14)'],BY['7стр с датами NEW50_2']),
]
for nm,a,b in CUTS:
    print(f'\n {nm}')
    for tf,t in [(None,'все ключи'),(VS,'ВЧ+СЧ   ')]:
        A,B=stat(a,tf),stat(b,tf)
        w='БЕЗ ДАТ' if A['per']>B['per'] else ('с датами' if B['per']>A['per'] else 'ничья')
        print(f'   {t}:  без дат {A["per"]:>5.2f} Т10/дом (зашло {A["hit"]}/{A["n"]})   '
              f'с датами {B["per"]:>5.2f} (зашло {B["hit"]}/{B["n"]})   → {w}')

print('\n=== ЗОНЫ ВНУТРИ НАБОРОВ (три на три, один контент) ===')
for nm in ['наборы 294303','наборы 274283']:
    print(f' {nm}')
    line('.team',stat(tm(BY[nm])),8); line('.lol',stat(lo(BY[nm])),8)
a=tm(BY['наборы 294303'])+tm(BY['наборы 274283']); b=lo(BY['наборы 294303'])+lo(BY['наборы 274283'])
print(' обе ветки вместе')
line('.team',stat(a),8); line('.lol',stat(b),8)

print('\n=== ЗОНЫ ВНУТРИ 12стр с датами NEW50_2 (14 .team против 3 .lol) ===')
line('.team',stat(tm(BY['12стр с датами NEW50_2'])),8)
line('.lol',stat(lo(BY['12стр с датами NEW50_2'])),8)

print('\n=== ДЕНЬ ЗАПУСКА: один контент, две партии, обе на возрасте ~20 ч ===')
Y=json.load(open(SP+'snapr.json')); QD=Y['qd']; P={p['id']:p for p in Y['pools']}
def ystat(pid,doms,tf=None):
    p=P[pid]; s=p['snaps'][-1]; idx={d:p['doms'].index(d) for d in doms}
    R=[r for r in s['rows'] if not tf or QD[r[0]][2] in tf]
    t10=[sum(1 for r in R if r[1]==idx[d] and r[2]<=10) for d in doms]
    t100=[sum(1 for r in R if r[1]==idx[d]) for d in doms]
    return dict(n=len(doms),t10=sum(t10),t100=sum(t100),per=sum(t10)/len(doms),
                med=st.median(t10),hit=sum(1 for x in t10 if x>0),lab=s['lab'],age=s['age'],
                nolead=(sum(t10)-max(t10))/(len(t10)-1) if len(t10)>1 else None)
PAIRS=[
 ('NEW50_7pages_withdate_01.09 · только .team',
  ('вчера, _1…_6', lambda tf: ystat('p7wt',['0864.team','pbfj.team','rvue.team','mmbr.team'],tf)),
  ('сегодня, _7…_11', lambda tf: stat(BY['7стр с датами NEW50 (_7…_11)'],tf))),
 ('NEW50_12pages_withdate_01.09 · только .team',
  ('вчера, _1…_6', lambda tf: ystat('p12wt',['l5n.team','6348.team','7612.team','7925.team'],tf)),
  ('сегодня, _7…_10', lambda tf: stat(BY['12стр с датами NEW50 (_7…_10)'],tf))),
]
for nm,(an,af),(bn,bf) in PAIRS:
    print(f'\n {nm}')
    for tf,t in [(None,'все ключи'),(VS,'ВЧ+СЧ   ')]:
        A,B=af(tf),bf(tf)
        print(f'   {t}:  {an:<16} {A["per"]:>5.2f} Т10/дом (зашло {A["hit"]}/{A["n"]}, сотня {A["t100"]})   '
              f'{bn:<16} {B["per"]:>5.2f} (зашло {B["hit"]}/{B["n"]}, сотня {B["t100"]})')

print('\n=== 12 СТРАНИЦ ПРОТИВ 7: чистые срезы, всё кроме страниц совпадает ===')
PG=[('NEW50_2 · с датами · .team',tm(BY['12стр с датами NEW50_2']),BY['7стр с датами NEW50_2']),
    ('NEW50 · с датами · .team',BY['12стр с датами NEW50 (_7…_10)'],BY['7стр с датами NEW50 (_7…_11)'])]
for nm,a,b in PG:
    print(f'\n {nm}')
    for tf,t in [(None,'все ключи'),(VS,'ВЧ+СЧ   ')]:
        A,B=stat(a,tf),stat(b,tf)
        print(f'   {t}:  12 стр {A["per"]:>5.2f} Т10/дом (дом {A["n"]}, зашло {A["hit"]})   '
              f'7 стр {B["per"]:>5.2f} (дом {B["n"]}, зашло {B["hit"]})   '
              f'→ {"12 СТРАНИЦ" if A["per"]>B["per"] else "7 страниц"}')
print('\n=== Итог дня ===')
al=[d for x in G for d in x['d']]
for tf,t in [(None,'все ключи'),(VS,'ВЧ+СЧ')]:
    a=stat(al,tf); print(f"  {t:<10} 67 доменов: Т3 {a['t3']}, Т10 {a['t10']}, сотня {a['t100']}, "
                         f"на домен {a['per']:.2f}, зашло {a['hit']}/67")
