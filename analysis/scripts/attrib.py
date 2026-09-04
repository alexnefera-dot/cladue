# Разбор конверсий с привязкой к группе запуска и дню. Объединяет все выгрузки.
import json,collections,datetime as dt,re,os
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
AN='/home/user/cladue/analysis/'
# --- все источники + дедуп
E=[]
c2=json.load(open(SP+'conv2.json'))
for e in c2['ev']: E.append(dict(t=e['ts'][:16],type=e['type'],dom=e['dom'],sub=e.get('brand',''),geo=e.get('geo',''),src='1'))
for e in json.load(open(SP+'conv3.json')): E.append(dict(t=e['ts'][:16],type=e['type'],dom=e['dom'],sub=e.get('brand',''),geo=e.get('geo',''),src='2'))
for e in json.load(open(SP+'conv4.json')): E.append(dict(t=e['t'][:16],type=e['type'],dom=e['dom'],sub=e.get('sub',''),geo=e.get('geo',''),src='3'))
for e in json.load(open(SP+'conv5.json')): E.append(dict(t=e['t'][:16],type=e['type'],dom=e['dom'],sub=e.get('sub',''),geo=e.get('geo',''),src='4'))
seen=set(); EV=[]
for e in sorted(E,key=lambda x:(x['t'],x['dom'],x['type'],x['src'])):
    k=(e['t'],e['type'],e['dom'],e['sub'])
    if k in seen: continue
    seen.add(k); EV.append(e)
print(f"событий во всех выгрузках {len(E)} → уникальных {len(EV)}: "
      f"рег {sum(1 for e in EV if e['type']=='reg')}, деп {sum(1 for e in EV if e['type']=='dep')}")
json.dump(EV,open(SP+'convall.json','w'),ensure_ascii=False)

# --- карта домен → группа, день, конфигурация
db=json.load(open(SP+'db.json')); SN=json.load(open(SP+'snapr.json'))
M={}
for d,v in db.items():
    if d=='базовый домен': continue
    M[d]=dict(g=v.get('group') or v.get('sheet',''),day=str(v.get('made'))[:5],
              cfg=f"{v.get('pages','?')} стр, {v.get('dates','?')}")
for p in SN['pools']:
    if p.get('excl'): continue
    for d in p['doms']: M[d]=dict(g=p['name'],day=p['ltx'][:5],cfg=f"{p['pages']} стр, {p['dates']}")
def add(names,g,day,cfg,z=None):
    for x in names.split():
        d=x if '.' in x else x+'.'+(z or 'team')
        M[d]=dict(g=g,day=day,cfg=cfg)
add('bmtq cnwv dprz fkxb glhd hjsf 1524 1893 2367 2745 4328','7page_1…_11 (партия 2)','27.08','7 стр, ?')
add('2139 2483 ogax byai 7186 4087 2084 2304 7440 0302','7page_1_1…_10_1','27.08','7 стр, ?')
add('3596 b8rn c5vt d3mw f9kq f9pb h7nd j2t k6m r9v','Generator_11page_old_27.08','27.08','11 стр, ?')
add('m7s3','nabory264268_01.09','01.09','наборы, ?')
for f,g,day,cfg in [('launch_03.09_flat.txt','NEW50_3 styled','03.09','7/12 стр, styled')]:
    for l in open(AN+f):
        l=l.strip()
        if l: M[l]=dict(g=g,day=day,cfg=cfg)
add('9124.lol casinoprb.lol casino01.lol casinoj1.lol qlcasino.lol xycasino.lol 9090.lol '
    'casinogh.lol casino0962.lol casino1430.lol','Generator_A4_staryy_stil','03.09','старый стиль, ?')
add('c2u3.lol oxvl.lol ukfw.team casino01.team xoacasino.team t1o.team casino876.team n7k.team '
    'ubgh.team bvve.lol','Generator_11page_01.09 · партия A','день не установлен','11 стр, ?')
add('dpcasino.team casinoprb.team emnc.team casino876.lol lvqv.lol',
    'Generator_11page_01.09 · партия B','день не установлен','11 стр, ?')

NEW=json.load(open(SP+'conv5.json'))
reg=collections.Counter(e['dom'] for e in EV if e['type']=='reg')
dep=collections.Counter(e['dom'] for e in EV if e['type']=='dep')
print(f"\n=== НОВАЯ ВЫГРУЗКА: {len(NEW)} событий, {len(set(e['dom'] for e in NEW))} доменов ===")
rows=collections.defaultdict(lambda:[0,0,collections.Counter(),[]])
for e in NEW:
    r=rows[e['dom']]
    if e['type']=='reg': r[0]+=1
    else: r[1]+=1
    r[2][e['sub']]+=1; r[3].append(e['t'])
print(f"{'домен':<15}{'рег':>4}{'деп':>4}  {'группа':<40}{'день':<12}{'конфиг':<20}бренды")
new=0
for d,(r,dp,subs,ts) in sorted(rows.items(),key=lambda x:(-x[1][0],-x[1][1])):
    m=M.get(d)
    if not m: m=dict(g='не опознан',day='?',cfg='—'); new+=1
    print(f"{d:<15}{r:>4}{dp:>4}  {str(m['g'])[:40]:<40}{str(m['day']):<12}{str(m['cfg'])[:20]:<20}"
          +', '.join(b+('×'+str(n) if n>1 else '') for b,n in subs.most_common(4)))
print(f"\nне опознано доменов: {new}")

print('\n=== Новая выгрузка по дню запуска ===')
G=collections.defaultdict(lambda:[0,0,set()])
for d,(r,dp,_,_) in rows.items():
    k=M.get(d,{}).get('day','не опознан')
    G[k][0]+=r; G[k][1]+=dp; G[k][2].add(d)
for k in sorted(G,key=lambda x:-G[x][0]):
    print(f"  {k:<20} рег {G[k][0]:>3}  деп {G[k][1]:>2}  доменов {len(G[k][2]):>2}")
print('\n=== Новая выгрузка по группам ===')
G2=collections.defaultdict(lambda:[0,0,set()])
for d,(r,dp,_,_) in rows.items():
    k=M.get(d,{}).get('g','не опознан')
    G2[k][0]+=r; G2[k][1]+=dp; G2[k][2].add(d)
for k in sorted(G2,key=lambda x:-G2[x][0]):
    print(f"  {str(k)[:46]:<46} рег {G2[k][0]:>3}  деп {G2[k][1]:>2}  дом {len(G2[k][2]):>2}")
json.dump({d:M[d] for d in M},open(SP+'dommap.json','w'),ensure_ascii=False)
