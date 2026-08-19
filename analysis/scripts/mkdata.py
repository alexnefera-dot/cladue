import pickle, collections, statistics, json, re
from core import EXCL_DOM, EXCL_BRAND
import core
allm=pickle.load(open("meas.pkl","rb")); KW=core.KW; BR=core.B["brands"]
traj=pickle.load(open("traj.pkl","rb")); P=pickle.load(open("perdom.pkl","rb"))
import collections as _c
per=_c.defaultdict(_c.Counter, {k:_c.Counter(v) for k,v in P["per"].items()}); DL=P["dom_launch"]
vol={b:v for b,v in BR.values()}
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
FMT={"D273":"12page + даты","D274":"7page + даты","D265":"12page под бренд",
 "D266":"12page под бренд","D267":"12page под бренд","D262":"7page под бренд",
 "D268":"7page под бренд","D248":"nu 6page","D249":"nu 6page","D252":"nu 6page",
 "D253":"nu 6page","D255":"1page / переисп.","D258":"именованные","D269":"предметные",
 "D261":"генерации .casino"}
def lab(f): return "D"+re.search(r'(\d{3})', f.replace('dorgne247','dorgen248')).group(1)

# per-domain full detail incl brands at last measurement
domdet={}
for f,meas in allm.items():
    if not meas: continue
    _,data=meas[-1]
    for dom,kws in data.items():
        if dom in EXCL_DOM: continue
        bl=collections.defaultdict(lambda:[999,0])
        c=collections.Counter()
        for q,pos in kws.items():
            m=KW.get(q)
            if not m: continue
            b,v,_=m
            if b in EXCL_BRAND: continue
            t=tier(v)
            for tp in (3,10,30,50,100):
                if pos<=tp: c[f"{t}{tp}"]+=1
            if pos<=30:
                e=bl[b]; e[0]=min(e[0],pos); e[1]+=1
        domdet[dom]={"launch":lab(f),"c":dict(c),
            "brands":sorted([[b,vol.get(b,0),tier(vol.get(b,0)),v[0],v[1]] for b,v in bl.items()],
                            key=lambda x:(x[3],-x[1]))[:60]}

launches=[]
for k,sns in traj.items():
    if not sns: continue
    fin=sns[-1]; n=len(fin)
    if n==0: continue
    tot=sum(s['hs'] for s in fin.values())
    g=d0=0
    for dd in fin:
        s=[x.get(dd,{}).get('t30',0) for x in sns]
        pk=max(s)
        if pk==0: continue
        if s[-1]>=pk*0.95: g+=1
        elif s[-1]<pk*0.8: d0+=1
    launches.append({"id":k,"fmt":FMT.get(k,"—"),"n":n,"meas":len(sns),
      "hs":tot,"hsd":tot/n,"ent":sum(1 for s in fin.values() if s['hs']>0)/n,
      "t30d":sum(s['t30'] for s in fin.values())/n,
      "grow":g/n,"drop":d0/n,
      "series":[round(sum(s['hs'] for s in m.values())/max(len(m),1),2) for m in sns],
      "t30series":[round(sum(s['t30'] for s in m.values())/max(len(m),1),1) for m in sns],
      "doms":sorted([d for d in fin], key=lambda d:-(per[d]["ВЧ10"]+per[d]["СЧ10"]))})
launches.sort(key=lambda x:-x["hsd"])

brandrows=[]
st=collections.defaultdict(lambda:{"t3":0,"t10":0,"t30":0,"d":set()})
for dom,dd in domdet.items():
    for b,v,t,best,cnt in dd["brands"]:
        s=st[b]
        if best<=3: s["t3"]+=1
        if best<=10: s["t10"]+=1; s["d"].add(dom)
        s["t30"]+=1
for b,s in st.items():
    brandrows.append({"b":b,"v":vol.get(b,0),"t":tier(vol.get(b,0)),
                      "t3":s["t3"],"t10":s["t10"],"t30":s["t30"],"d":len(s["d"])})
brandrows.sort(key=lambda x:-x["t10"])

data={"launches":launches,"domdet":domdet,"brands":brandrows,
 "perdom":{d:{"vch":per[d]["ВЧ10"],"sch":per[d]["СЧ10"],"nch":per[d]["НЧ10"],
              "t30":per[d]["ВЧ30"]+per[d]["СЧ30"]+per[d]["НЧ30"],"L":DL[d]} for d in list(per)}}
json.dump(data, open("data.json","w"), ensure_ascii=False)
print("launches",len(launches),"domains",len(domdet),"brands",len(brandrows))
