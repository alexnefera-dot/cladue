# Данные для отчёта по пулам 31.08-01.09: бренды, ключи, вложенность, страницы.
import json,re,csv,collections,statistics as st
D=json.load(open('p01.json'))
TIER={}; VOL={}
with open('/home/user/cladue/analysis/keys/keys_stats.csv',encoding='utf-8-sig') as f:
    for r in csv.DictReader(f,delimiter=';'):
        q=r['ключ'].strip()
        TIER[q]=(r['бренд'],r['тир'])
        try: VOL[r['бренд']]=int(r['частотность'])
        except: pass
def parts(u):
    if not isinstance(u,str): return None,None,None
    rest=u.split('://',1)[-1]; host=rest.split('/',1)[0]
    path='/'+rest.split('/',1)[1] if '/' in rest else '/'
    segs=[s for s in path.split('/') if s]
    pg=[s for s in segs if s!='ru']
    return host,('/'+'/'.join(pg) if pg else '/'),len([s for s in segs if s=='ru'])
POOLS=[]
CFG={'Generator_11page_test .com (ru':dict(name='Generator_11page_test · .com',cap='потолок 20',
        plat='dorgen com',ld='31.08 16:39',ids='1055-1063',pages='11'),
     'Generator_11page_test .net (ru':dict(name='nabor-244…253 · .net',cap='без потолка',
        plat='dorgen.net',ld='31.08 19:30–22:45 (точно не прислано)',ids='nabor-244…253',pages='не прислано'),
     'apex, banda':dict(name='apex, banda (узкое ядро 70 ключей)',cap='потолок 20',
        plat='dorgen com',ld='31.08 16:39',ids='1055-1063',pages='11')}
ROWS=[]
for sn,snaps in D.items():
    cfg=CFG.get(sn,dict(name=sn,cap='?',plat='?',ld='?',ids='?',pages='?'))
    labs=[s['lab'] for s in snaps]
    last=snaps[-1]
    per_dom=[]
    for d in snaps[0]['doms']:
        tl=[]
        for s in snaps:
            ks=s['per'].get(d,[])
            tl.append(dict(lab=s['lab'],t3=sum(1 for k in ks if k['p']<=3),
                t10=sum(1 for k in ks if k['p']<=10),t30=sum(1 for k in ks if k['p']<=30),t100=len(ks)))
        ks=last['per'].get(d,[])
        ds=[k['d'] for k in ks if k['d'] is not None]
        pgs=collections.Counter(); subs=collections.Counter(); brs=collections.Counter()
        for k in ks:
            ho,pg,dp=parts(k['u'])
            if pg: pgs[pg]+=1
            if ho: subs[ho.split('.')[0]]+=1
            b=TIER.get(k['q'],(None,None))[0]
            if b and k['p']<=10: brs[b]+=1
        per_dom.append(dict(d=d,tl=tl,best=min([k['p'] for k in ks],default=None),
            dmax=max(ds) if ds else 0,dmed=round(st.median(ds)) if ds else 0,
            dover=round(100*sum(1 for x in ds if x>20)/len(ds)) if ds else 0,
            nsub=len(subs),pages=pgs.most_common(6),brands=brs.most_common(8)))
        for k in ks:
            ho,pg,dp=parts(k['u'])
            b,t=TIER.get(k['q'],(None,None))
            ROWS.append(dict(pool=cfg['name'],cap=cfg['cap'],dom=d,q=k['q'],p=k['p'],
                b=b,t=t,vol=VOL.get(b,0),sub=(ho.split('.')[0] if ho else None),
                page=pg,d=dp,u=k['u']))
    tot=[]
    for s in snaps:
        f=lambda n: sum(1 for ks in s['per'].values() for k in ks if k['p']<=n)
        tot.append(dict(lab=s['lab'],t3=f(3),t10=f(10),t30=f(30),
                        t100=sum(len(v) for v in s['per'].values())))
    ds=[k['d'] for ks in last['per'].values() for k in ks if k['d'] is not None]
    pgs=collections.Counter(); brs=collections.Counter(); tie=collections.Counter(); tie10=collections.Counter()
    for ks in last['per'].values():
        for k in ks:
            ho,pg,dp=parts(k['u'])
            if pg: pgs[pg]+=1
            b,t=TIER.get(k['q'],(None,None))
            if b: brs[b]+= (1 if k['p']<=10 else 0)
            if t: tie[t]+=1; tie10[t]+= (1 if k['p']<=10 else 0)
    # эффект смены адреса между двумя последними съёмами
    eff=None
    if len(snaps)>=2:
        a,b2=snaps[-2],snaps[-1]; ch=[];sm=[]
        for d in a['doms']:
            A={k['q']:k for k in a['per'].get(d,[])}; B={k['q']:k for k in b2['per'].get(d,[])}
            for q in set(A)&set(B):
                if A[q]['d'] is None or B[q]['d'] is None: continue
                (ch if A[q]['d']!=B[q]['d'] else sm).append(B[q]['p']-A[q]['p'])
        eff=dict(ch=len(ch),chmed=round(st.median(ch)) if ch else None,
                 sm=len(sm),smmed=round(st.median(sm)) if sm else None,
                 keep=sum(len({k['q'] for k in a['per'].get(d,[])}&{k['q'] for k in b2['per'].get(d,[])}) for d in a['doms']),
                 was=sum(len(a['per'].get(d,[])) for d in a['doms']))
    POOLS.append(dict(**cfg,sheet=sn,n=len(snaps[0]['doms']),labs=labs,tot=tot,dom=per_dom,
        dmax=max(ds) if ds else 0,dmed=round(st.median(ds)) if ds else 0,
        dover=round(100*sum(1 for x in ds if x>20)/len(ds)) if ds else 0,
        dhist=[[lo,sum(1 for x in ds if lo<=x<=hi)] for lo,hi in [(0,0),(1,5),(6,10),(11,20),(21,30),(31,40),(41,99)]],
        pgtop=pgs.most_common(10),brands=brs.most_common(25),tier=dict(tie),tier10=dict(tie10),eff=eff))
json.dump(dict(pools=POOLS,rows=ROWS),open('pools_rep.json','w'),ensure_ascii=False)
print('пулов',len(POOLS),'строк ключ×домен',len(ROWS))
for p in POOLS: print(' ',p['name'],p['n'],'дом |',[t['t10'] for t in p['tot']],'| /ru мед',p['dmed'],'макс',p['dmax'],'| страниц',len(p['pgtop']))
