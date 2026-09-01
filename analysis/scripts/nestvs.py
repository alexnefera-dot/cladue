# То же самое, но только по ВЧ/СЧ ключам и с фокусом на вход в ТОП-10.
import json,re,csv,collections,statistics as st,os
def depth(u):
    if not isinstance(u,str): return None
    p=u.split('://',1)[-1]; p='/'+p.split('/',1)[1] if '/' in p else '/'
    return len(re.findall(r'/ru(?=/|$)',p))
TIER={}
with open('/home/user/cladue/analysis/keys/keys_stats.csv',encoding='utf-8-sig') as f:
    for r in csv.DictReader(f,delimiter=';'): TIER.setdefault(r['ключ'].strip(),(r['бренд'],r['тир']))
CAPP={'7page_27.08 · партия 1','Generator_11page_old_27.08','Generator_11page_test .com (ru','apex, banda'}
P1={'2139.team','2483.team','ogax.team','byai.team','7186.team','4087.team','2084.team','2304.team','7440.team','0302.team'}
OLD={'3596.team','b8rn.team','c5vt.team','d3mw.team','f9kq.team','f9pb.team','h7nd.team','j2t.team','k6m.team','r9v.team'}
U=[];seen=set()
def add(pool,snaps):
    for i in range(len(snaps)-1):
        a,b=snaps[i],snaps[i+1]
        for d in set(a.get('per',{}))|set(b.get('per',{})):
            A={k['q']:k for k in a['per'].get(d,[])}; B={k['q']:k for k in b['per'].get(d,[])}
            for q in set(A)&set(B):
                u0,u1=A[q].get('u'),B[q].get('u'); d0,d1=depth(u0),depth(u1)
                if d0 is None or d1 is None: continue
                k=(pool,a['lab'],b['lab'],d,q)
                if k in seen: continue
                seen.add(k)
                br,t=TIER.get(q,(None,'—'))
                U.append(dict(pool=pool,pair=f"{a['lab']} → {b['lab']}",dom=d,q=q,b=br,t=t,
                    p0=A[q]['p'],p1=B[q]['p'],d0=d0,d1=d1,same=(u0==u1),
                    cap=(pool in CAPP or d in P1 or d in OLD),u1=u1))
for f in ['p21','p22','p23','p24','p31b','p01']:
    if not os.path.exists(f+'.json'): continue
    for sheet,snaps in json.load(open(f+'.json')).items():
        add(sheet,sorted(snaps,key=lambda s:s['lab']))
VS=[r for r in U if r['t'] in ('ВЧ','СЧ')]
NCH=[r for r in U if r['t']=='НЧ']
def grp(r):
    if r['same']: return 'адрес не менялся'
    if r['d1']==r['d0']: return 'сменился, длина та же'
    return 'стал длиннее' if r['d1']>r['d0'] else 'стал короче'
GN=['адрес не менялся','стал длиннее','стал короче','сменился, длина та же']
def stat(v):
    d=[x['p1']-x['p0'] for x in v]
    return dict(n=len(d),med=(st.median(d) if d else None),
                up=sum(1 for x in d if x<0),shup=(round(100*sum(1 for x in d if x<0)/len(d)) if d else None))
OUT=dict(vs={g:stat([r for r in VS if grp(r)==g]) for g in GN},
         nch={g:stat([r for r in NCH if grp(r)==g]) for g in GN})
# вход в ТОП-10: был вне десятки, стал в десятке
def entered(r): return r['p0']>10 and r['p1']<=10
def stayed(r): return r['p0']>10 and r['p1']>10
for nm,S in [('vs',VS),('nch',NCH)]:
    ent=[r for r in S if entered(r)]; sty=[r for r in S if stayed(r)]
    OUT[nm+'_enter']=dict(
        n_ent=len(ent), n_out=len(ent)+len(sty),
        rate=round(100*len(ent)/(len(ent)+len(sty)),1) if (ent or sty) else None,
        by={g:dict(ent=sum(1 for r in ent if grp(r)==g),tot=sum(1 for r in ent+sty if grp(r)==g)) for g in GN})
    for g in GN:
        b=OUT[nm+'_enter']['by'][g]
        b['rate']=round(100*b['ent']/b['tot'],1) if b['tot'] else None
# длина адреса у тех, кто В десятке (последнее состояние) — ВЧ/СЧ отдельно
def lb(d): return '0' if d==0 else ('1–5' if d<=5 else ('6–15' if d<=15 else ('16–25' if d<=25 else ('26–40' if d<=40 else '41+'))))
LV=['0','1–5','6–15','16–25','26–40','41+']
for nm,S in [('vs',VS),('nch',NCH)]:
    c=collections.defaultdict(lambda:[0,0])
    for r in S:
        c[lb(r['d1'])][0]+=1
        if r['p1']<=10: c[lb(r['d1'])][1]+=1
    OUT[nm+'_lvl']={b:dict(n=c[b][0],t10=c[b][1],sh=round(100*c[b][1]/c[b][0],1) if c[b][0] else None) for b in LV}
# длина адреса именно у ВЧ/СЧ ключей, стоящих в ТОП-10
top=[r for r in VS if r['p1']<=10]
OUT['vs_top_depth']=collections.Counter(lb(r['d1']) for r in top)
OUT['vs_top_examples']=sorted([dict(q=r['q'],b=r['b'],t=r['t'],p=r['p1'],d=r['d1'],dom=r['dom'],
    was=r['p0'],d0=r['d0'],pool=r['pool']) for r in top],key=lambda x:x['p'])[:40]
OUT['meta']=dict(nvs=len(VS),nnch=len(NCH),lv=LV,gn=GN)
json.dump(OUT,open('nestvs.json','w'),ensure_ascii=False)
print('ВЧ/СЧ пар:',len(VS),'| НЧ пар:',len(NCH))
print('\nВЧ/СЧ:')
for g in GN:
    s=OUT['vs'][g]
    if s['n']: print(f"   {g:<24} n={s['n']:>4} медиана {s['med']:+.0f} вверх {s['shup']}%")
print('НЧ:')
for g in GN:
    s=OUT['nch'][g]
    if s['n']: print(f"   {g:<24} n={s['n']:>4} медиана {s['med']:+.0f} вверх {s['shup']}%")
print('\nвход в ТОП-10 из-за пределов десятки:')
for nm,lab in [('vs','ВЧ/СЧ'),('nch','НЧ')]:
    e=OUT[nm+'_enter']
    print(f"   {lab}: залетели {e['n_ent']} из {e['n_out']} = {e['rate']}%")
    for g in GN:
        b=e['by'][g]
        if b['tot']: print(f"      {g:<24} {b['ent']:>3}/{b['tot']:<4} = {b['rate']}%")
print('\nдоля в ТОП-10 по длине адреса:')
for nm,lab in [('vs','ВЧ/СЧ'),('nch','НЧ')]:
    print(' ',lab,{b:f"{v['t10']}/{v['n']}={v['sh']}%" for b,v in OUT[nm+'_lvl'].items() if v['n']})
