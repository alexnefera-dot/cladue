import json,statistics as st,cfg
EXCL_DOM={'5374.team','2535.team'}
H=json.load(open('hist.json'))
G=[]
for sn,v in H.items():
    c=cfg.C[sn]; hdr=v['doms']
    ds=[d for d in hdr if d.endswith('.team') and d not in EXCL_DOM]
    if not ds: ds=[d for d in hdr if d not in EXCL_DOM]
    snaps=[]
    for s in v['snaps']:
        dm=s['dom']
        vals=sorted((dm[d]['t10'] for d in ds),reverse=True); n=len(ds)
        snaps.append(dict(lab=s['lab'],quart=s['quart'],corelen=s['corelen'],n=n,
            mean=round(sum(vals)/n,3),med=st.median(vals),
            wo=round(sum(vals[1:])/(n-1),3) if n>1 else 0,vals=vals,
            t3=sum(dm[d]['t3'] for d in ds),t30=sum(dm[d]['t30'] for d in ds),
            t100=sum(dm[d]['t100'] for d in ds),
            vch=sum(dm[d]['vch'] for d in ds),sch=sum(dm[d]['sch'] for d in ds),
            topb=s.get('topb'),nbrands=s.get('nbrands'),
            trunc=bool(s['quart'][3]==0 and s['quart'][0]>=5 and sum(s['quart'])>=10)))
    doms=[]
    for d in hdr:
        tr=[v['snaps'][i]['dom'][d]['t10'] for i in range(len(v['snaps']))]
        L=v['snaps'][-1]['dom'][d]
        doms.append(dict(d=d,tm=d.endswith('.team'),excl=d in EXCL_DOM,tr=tr,
            t3=L['t3'],t10=L['t10'],t30=L['t30'],t100=L['t100'],vch=L['vch'],sch=L['sch'],
            nb=L['nb'],keys=L.get('keys',[])))
    doms.sort(key=lambda x:(-x['t10'],-x['t30']))
    G.append(dict(sheet=sn,**c,ntm=len(ds),ndom=len(hdr),snaps=snaps,doms=doms,
        labs=[s['lab'] for s in snaps],ser=[s['mean'] for s in snaps],serwo=[s['wo'] for s in snaps],
        good=[i for i,s in enumerate(snaps) if not s['trunc']]))
ORDC=['26-27.08','25-26.08','24-25.08','архив']
G.sort(key=lambda g:(ORDC.index(g['coh']),g['test'],g['name']))
json.dump({'g':G},open('full.json','w'),ensure_ascii=False)
print('групп:',len(G))
for g in G:
    if g['coh']!='архив': continue
for c in ORDC:
    print('\n===',c,'===')
    for g in G:
        if g['coh']!=c: continue
        print(f"  {g['name'][:44]:46s} {g['test']:9s} n={g['ntm']:2d}  " + " → ".join(f"{l} {m:.2f}" for l,m in zip(g['labs'],g['ser'])))
