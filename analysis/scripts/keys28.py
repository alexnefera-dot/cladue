# Ключи и бренды на съёме 28.08 12:43 против 28.08 00:30, с разбивкой
# по ограничению вложенности /ru (партия 1 + Generator_11page_old ограничены 20).
import json,re,collections,statistics as st
S={}
for f in ['p21','p22','p23','p24']:
    for sheet,snaps in json.load(open(f+'.json')).items():
        for s in snaps: S.setdefault((sheet,s['lab']),s)
def depth(u):
    if not u: return None
    p=u.split('://',1)[-1]; p='/'+p.split('/',1)[1] if '/' in p else '/'
    return len(re.findall(r'/ru(?=/|$)',p))
P1=['2139.team','2483.team','ogax.team','byai.team','7186.team','4087.team','2084.team','2304.team','7440.team','0302.team']
OLD=['3596.team','b8rn.team','c5vt.team','d3mw.team','f9kq.team','f9pb.team','h7nd.team','j2t.team','k6m.team','r9v.team']
P2=['bmtq.team','cnwv.team','dprz.team','fkxb.team','glhd.team','hjsf.team','1524.team','1893.team','2367.team','2745.team','4328.team']
GR={**{d:'7page партия 1' for d in P1},**{d:'Generator_11page_old' for d in OLD},**{d:'7page партия 2' for d in P2}}
CAP=set(P1)|set(OLD)
PREV,LAST='28.08 00:30','28.08 12:43'
K={}
for sh in {k[0] for k in S}:
    for lab,tag in ((PREV,0),(LAST,1)):
        src=S.get((sh,lab))
        if not src: continue
        for dom,ks in src['per'].items():
            if dom not in GR: continue
            for k in ks:
                e=K.setdefault((k['b'],k['q'],dom),dict(b=k['b'],q=k['q'],dom=dom,t=k.get('t'),v=k.get('v'),
                    grp=GR[dom],cap=dom in CAP,p0=None,p1=None,d0=None,d1=None,u=None))
                e['p%d'%tag]=k['p']; e['d%d'%tag]=depth(k.get('u'))
                if tag: e['u']=k.get('u')
rows=list(K.values())
def block(sel):
    r=[x for x in rows if sel(x) and x['p0'] and x['p1'] and x['d0'] is not None and x['d1'] is not None]
    ch=[x for x in r if x['d1']!=x['d0']]; sm=[x for x in r if x['d1']==x['d0']]
    g=lambda v:[x['p1']-x['p0'] for x in v]
    f=lambda v:dict(n=len(v),med=(st.median(g(v)) if v else None),
                    up=sum(1 for x in g(v) if x<0),dn=sum(1 for x in g(v) if x>0))
    return dict(n=len(r),ch=f(ch),sm=f(sm),
                items=sorted([{kk:x[kk] for kk in ('b','q','dom','grp','p0','p1','d0','d1','t')} for x in ch],
                             key=lambda x:x['p1']-x['p0']))
CMP=[dict(k='Ограничен ≤20',sub='7page партия 1 + Generator_11page_old · 20 доменов',**block(lambda x:x['cap'])),
     dict(k='Без ограничения',sub='7page партия 2 · 11 доменов',**block(lambda x:not x['cap']))]
B=collections.defaultdict(list)
for r in rows: B[r['b']].append(r)
BR=[]
for b,v in B.items():
    both=[x for x in v if x['p0'] and x['p1']]
    d=[x['p1']-x['p0'] for x in both]
    cur=sorted([x for x in v if x['p1']],key=lambda x:x['p1'])
    capc=[x for x in cur if x['cap']]; unc=[x for x in cur if not x['cap']]
    BR.append(dict(b=b,t=v[0]['t'],vol=v[0]['v'],now=len(cur),gone=len([x for x in v if x['p0'] and not x['p1']]),
        new=len([x for x in v if x['p1'] and not x['p0']]),med=(st.median(d) if d else None),
        t10=len([x for x in cur if x['p1']<=10]),t3=len([x for x in cur if x['p1']<=3]),
        best=(cur[0]['p1'] if cur else None),bdom=(cur[0]['dom'] if cur else None),bgrp=(cur[0]['grp'] if cur else None),
        capbest=(capc[0]['p1'] if capc else None),capdom=(capc[0]['dom'] if capc else None),
        uncbest=(unc[0]['p1'] if unc else None),uncdom=(unc[0]['dom'] if unc else None),
        keys=sorted([{kk:x[kk] for kk in ('q','dom','grp','cap','p0','p1','d0','d1','u')} for x in v],
                    key=lambda x:(x['p1'] or 999))))
BR.sort(key=lambda x:(-(x['t10']),x['best'] if x['best'] else 999,-x['now']))
json.dump(dict(cmp=CMP,br=BR,prev=PREV,last=LAST,
    tot=dict(rows=len(rows),now=len([x for x in rows if x['p1']]),
             gone=len([x for x in rows if x['p0'] and not x['p1']]),
             new=len([x for x in rows if x['p1'] and not x['p0']]),brands=len(BR))),
    open('keys28.json','w'),ensure_ascii=False)
print('брендов',len(BR),'строк',len(rows))
for c in CMP: print(c['k'],c['n'],'| URL сменился',c['ch'],'| тот же',c['sm'])
