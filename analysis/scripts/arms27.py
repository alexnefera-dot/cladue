# Сравнение трёх групп 27.08: 7page партия 1 (потолок 20), 7page партия 2 (без потолка),
# Generator_11page_old (потолок 20). Дописывает ключ arms в keys28.json.
import json,re,collections,statistics as st
S={}
for f in ['p21','p22','p23','p24']:
    for sheet,snaps in json.load(open(f+'.json')).items():
        for s in snaps: S.setdefault((sheet,s['lab']),s)
P1=['2139.team','2483.team','ogax.team','byai.team','7186.team','4087.team','2084.team','2304.team','7440.team','0302.team']
P2=['bmtq.team','cnwv.team','dprz.team','fkxb.team','glhd.team','hjsf.team','1524.team','1893.team','2367.team','2745.team','4328.team']
OLD=['3596.team','b8rn.team','c5vt.team','d3mw.team','f9kq.team','f9pb.team','h7nd.team','j2t.team','k6m.team','r9v.team']
ARMS=[('7page партия 1','7page_27.08',P1,True,'7 страниц · id 1004-1013 · создан 27.08 17:33-17:40'),
      ('7page партия 2','7page_27.08',P2,False,'7 страниц · id и время не присланы'),
      ('Generator_11page_old','Generator_11page_old_27.08',OLD,True,'наш генератор · 11 стр · «old» · id 1014-1023')]
LABS=['27.08 19:31','27.08 21:47','28.08 00:30','28.08 12:43']
ALT={'Generator_11page_old_27.08':{'27.08 19:31':'27.08 19:32'}}
def depth(u):
    if not u: return None
    p=u.split('://',1)[-1]; p='/'+p.split('/',1)[1] if '/' in p else '/'
    return len(re.findall(r'/ru(?=/|$)',p))
cnt=lambda ks,n: sum(1 for k in ks if k['p']<=n)
C=json.load(open('conv2.json')); TR=C['tr']; EV=C['ev']
OUT=[]
for nm,sh,doms,cap,cfg in ARMS:
    snaps=[]
    for lab in LABS:
        s=S.get((sh,ALT.get(sh,{}).get(lab,lab)))
        if not s: snaps.append(None); continue
        per={d:s['per'].get(d,[]) for d in doms}
        t10=[cnt(v,10) for v in per.values()]; srt=sorted(t10,reverse=True)
        ds=[x for v in per.values() for x in (depth(k.get('u')) for k in v) if x is not None]
        snaps.append(dict(lab=lab,t3=sum(cnt(v,3) for v in per.values()),t10=sum(t10),
            t30=sum(cnt(v,30) for v in per.values()),t100=sum(len(v) for v in per.values()),
            per_dom=round(st.mean(t10),2),nolead=round(st.mean(srt[1:]),2),
            brands=len({k['b'] for v in per.values() for k in v if k['p']<=10}),
            dmax=max(ds) if ds else 0,dmed=(st.median(ds) if ds else 0)))
    s=S.get((sh,ALT.get(sh,{}).get(LABS[-1],LABS[-1])))
    dom=[]
    for d in doms:
        v=s['per'].get(d,[]) if s else []
        t=TR.get(d,{})
        dom.append(dict(d=d,t3=cnt(v,3),t10=cnt(v,10),t30=cnt(v,30),t100=len(v),
            nb=len({k['b'] for k in v if k['p']<=10}),best=min([k['p'] for k in v],default=None),
            sub=t.get('sub',0),uniq=t.get('uniq',0),hits=t.get('hits',0),
            reg=t.get('reg',0),dep=t.get('dep',0)))
    B=collections.defaultdict(list)
    if s:
        for d in doms:
            for k in s['per'].get(d,[]):
                if k['p']<=10: B[k['b']].append((k['p'],d))
    OUT.append(dict(nm=nm,cfg=cfg,cap=cap,n=len(doms),snaps=snaps,dom=dom,
        brands={b:min(v) for b,v in B.items()},
        sub=sum(TR[d]['sub'] for d in doms if d in TR),
        uniq=sum(TR[d]['uniq'] for d in doms if d in TR),
        hits=sum(TR[d]['hits'] for d in doms if d in TR),
        reg=sum(1 for e in EV if e['type']=='reg' and e['dom'] in doms),
        dep=sum(1 for e in EV if e['type']=='dep' and e['dom'] in doms)))
D=json.load(open('keys28.json')); D['arms']=OUT; D['labs']=LABS
json.dump(D,open('keys28.json','w'),ensure_ascii=False)
for a in OUT:
    print(a['nm'],'| Т10 по съёмам',[s['t10'] if s else None for s in a['snaps']],
          '| подд',a['sub'],'| рег',a['reg'],'| брендов Т10',len(a['brands']))
