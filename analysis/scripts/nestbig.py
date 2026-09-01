# Массовый анализ: даёт ли РОСТ вложенности /ru более высокую позицию.
# Ключевой контроль — разделить «Яндекс переобошёл и сменил URL» и «URL стал глубже»:
#   URL тот же | URL сменился, глубина та же | URL сменился, глубже | URL сменился, мельче
import json,re,collections,statistics as st,os,math
def depth(u):
    if not isinstance(u,str): return None
    p=u.split('://',1)[-1]; p='/'+p.split('/',1)[1] if '/' in p else '/'
    return len(re.findall(r'/ru(?=/|$)',p))
CAP={'7page_27.08 · партия 1','Generator_11page_old_27.08','Generator_11page_test .com (ru','apex, banda'}
P1={'2139.team','2483.team','ogax.team','byai.team','7186.team','4087.team','2084.team','2304.team','7440.team','0302.team'}
OLD={'3596.team','b8rn.team','c5vt.team','d3mw.team','f9kq.team','f9pb.team','h7nd.team','j2t.team','k6m.team','r9v.team'}
PAIRS=[]
def add(src,pool,snaps):
    for i in range(len(snaps)-1):
        a,b=snaps[i],snaps[i+1]
        for d in set(a.get('per',{}))|set(b.get('per',{})):
            A={k['q']:k for k in a['per'].get(d,[])}; B={k['q']:k for k in b['per'].get(d,[])}
            cap = pool in CAP or d in P1 or d in OLD
            for q in set(A)&set(B):
                u0,u1=A[q].get('u'),B[q].get('u')
                d0,d1=depth(u0),depth(u1)
                if d0 is None or d1 is None: continue
                PAIRS.append(dict(src=src,pool=pool,pair=f"{a['lab']} → {b['lab']}",dom=d,q=q,
                    p0=A[q]['p'],p1=B[q]['p'],d0=d0,d1=d1,same=(u0==u1),cap=bool(cap)))
# 27-28.08 (старый формат: p2x.json = {sheet: [snaps]})
for f in ['p21','p22','p23','p24']:
    if not os.path.exists(f+'.json'): continue
    for sheet,snaps in json.load(open(f+'.json')).items():
        snaps=sorted(snaps,key=lambda s:s['lab'])
        add(f,sheet,snaps)
# 31.08-01.09
for f,src in [('p31b','31.08'),('p01','01.09')]:
    if not os.path.exists(f+'.json'): continue
    for sheet,snaps in json.load(open(f+'.json')).items():
        add(src,sheet,snaps)
# дедупликация: одна и та же пара съёмов могла попасть из разных файлов
seen=set(); U=[]
for r in PAIRS:
    k=(r['pool'],r['pair'],r['dom'],r['q'])
    if k in seen: continue
    seen.add(k); U.append(r)
print('пар ключ×домен×переход:',len(U),'| уникальных переходов',len({(r['pool'],r['pair']) for r in U}))
def grp(r):
    if r['same']: return 'URL тот же'
    if r['d1']==r['d0']: return 'URL сменился, глубина та же'
    return 'URL сменился, глубже' if r['d1']>r['d0'] else 'URL сменился, мельче'
GN=['URL тот же','URL сменился, глубина та же','URL сменился, глубже','URL сменился, мельче']
def band(p): return '1–10' if p<=10 else ('11–30' if p<=30 else ('31–60' if p<=60 else '61–100'))
def stat(v):
    d=[x['p1']-x['p0'] for x in v]
    return dict(n=len(d),med=(st.median(d) if d else None),mean=(round(st.mean(d),1) if d else None),
                up=sum(1 for x in d if x<0),dn=sum(1 for x in d if x>0),
                shup=(round(100*sum(1 for x in d if x<0)/len(d)) if d else None))
OUT={'total':{g:stat([r for r in U if grp(r)==g]) for g in GN}}
OUT['bands']={b:{g:stat([r for r in U if grp(r)==g and band(r['p0'])==b]) for g in GN}
              for b in ['1–10','11–30','31–60','61–100']}
# величина прироста глубины
def mag(r):
    dd=r['d1']-r['d0']
    return 'мельче' if dd<0 else ('без изменений' if dd==0 else ('+1…+5' if dd<=5 else ('+6…+15' if dd<=15 else '+16 и больше')))
MG=['мельче','без изменений','+1…+5','+6…+15','+16 и больше']
OUT['mag']={m:stat([r for r in U if not r['same'] and mag(r)==m]) for m in MG}
# стратифицированное сравнение внутри домена и полосы старта
strata=collections.defaultdict(lambda:collections.defaultdict(list))
for r in U: strata[(r['pool'],r['pair'],r['dom'],band(r['p0']))][grp(r)].append(r['p1']-r['p0'])
def paired(gA,gB):
    diffs=[];w=0
    for k,v in strata.items():
        if v.get(gA) and v.get(gB):
            diffs.append((st.mean(v[gA])-st.mean(v[gB]),min(len(v[gA]),len(v[gB]))))
            w+=min(len(v[gA]),len(v[gB]))
    if not diffs: return None
    m=sum(d*n for d,n in diffs)/sum(n for _,n in diffs)
    pos=sum(1 for d,_ in diffs if d<0)
    return dict(strata=len(diffs),w=w,diff=round(m,1),better=pos,worse=len(diffs)-pos)
OUT['paired']={'глубже против URL тот же':paired('URL сменился, глубже','URL тот же'),
 'глубже против сменился без изменения глубины':paired('URL сменился, глубже','URL сменился, глубина та же'),
 'сменился без изменения глубины против URL тот же':paired('URL сменился, глубина та же','URL тот же'),
 'мельче против URL тот же':paired('URL сменился, мельче','URL тот же')}
# срез: уровень глубины против позиции (не изменение, а сам уровень)
lvl=collections.defaultdict(list)
for r in U:
    b='0' if r['d1']==0 else ('1–5' if r['d1']<=5 else ('6–15' if r['d1']<=15 else ('16–25' if r['d1']<=25 else ('26–40' if r['d1']<=40 else '41+'))))
    lvl[b].append(r['p1'])
OUT['level']={k:dict(n=len(v),med=st.median(v),t10=round(100*sum(1 for x in v if x<=10)/len(v))) for k,v in lvl.items()}
# по пулам с потолком и без
OUT['bycap']={('с потолком' if c else 'без потолка'):{g:stat([r for r in U if r['cap']==c and grp(r)==g]) for g in GN}
              for c in (True,False)}
OUT['meta']=dict(n=len(U),pools=sorted({r['pool'] for r in U}),
                 pairs=sorted({r['pair'] for r in U}),doms=len({r['dom'] for r in U}))
json.dump(OUT,open('nestbig.json','w'),ensure_ascii=False)
print()
for g in GN:
    s=OUT['total'][g]
    print(f"{g:<34} n={s['n']:>5} медиана {s['med']:+.0f}  среднее {s['mean']:+.1f}  вверх {s['shup']}%")
print()
for k,v in OUT['paired'].items():
    print(f"{k:<48} {v}")
print()
print('уровень глубины → позиция:',OUT['level'])

# --- уровень глубины против позиции ВНУТРИ домена (контроль качества домена)
LV=['0','1–5','6–15','16–25','26–40','41+']
def lb(d): return '0' if d==0 else ('1–5' if d<=5 else ('6–15' if d<=15 else ('16–25' if d<=25 else ('26–40' if d<=40 else '41+'))))
byd=collections.defaultdict(lambda:collections.defaultdict(list))
for r in U: byd[(r['pool'],r['pair'],r['dom'])][lb(r['d1'])].append(r['p1'])
DIFF=collections.defaultdict(list)
for k,v in byd.items():
    if '0' not in v: continue
    base=st.median(v['0'])
    for b in LV:
        if b!='0' and v.get(b): DIFF[b].append((st.median(v[b])-base,min(len(v[b]),len(v['0']))))
WD={b:dict(n=len(v),w=sum(n for _,n in v),
           diff=round(sum(d*n for d,n in v)/sum(n for _,n in v),1),
           better=sum(1 for d,_ in v if d<0)) for b,v in DIFF.items()}
# порог прироста × полоса старта
MG2=['мельче','+1…+5','+6…+15','+16 и больше']
CROSS={m:{b:stat([r for r in U if not r['same'] and mag(r)==m and band(r['p0'])==b]) for b in
          ['1–10','11–30','31–60','61–100']} for m in MG2}
O=json.load(open('nestbig.json'))
O.update(withindom=WD,cross=CROSS,magorder=MG2,lvorder=LV)
json.dump(O,open('nestbig.json','w'),ensure_ascii=False)
print('\nвнутри домена: позиция относительно чистых адресов того же домена')
for b in LV[1:]:
    if b in WD: print(f"   глубина {b:<7} страт {WD[b]['n']:>3}  разница медиан {WD[b]['diff']:+.1f}  лучше в {WD[b]['better']} случаях")
