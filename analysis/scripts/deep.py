import pickle, collections, json
import core
KW=core.KW; EXCL_BRAND=core.EXCL_BRAND
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
snaps=pickle.load(open("snaps2.pkl","rb"))
META={"группа 3":["Generator_11page","Гр.3","11 страниц · генератор","?","?",5],
      "группа 1":["7page_yandex","Гр.1","7 страниц · сайты из выдачи","—","?",10],
      "группа 4":["Generator_11page_2","Гр.4","11 страниц · генератор","?","?",5],
      "группа 5":["Generator_v5","Гр.5","7 страниц · генератор","v5","Theme2",5],
      "группа 6":["Generator_v4_2","Гр.6","7 страниц · генератор","v4_2","Theme1",5],
      "группа 2":["generator v4","Гр.2","7 страниц · генератор","v4","?",10]}
ORD=["группа 3","группа 1","группа 4","группа 5","группа 6","группа 2"]

out={}
for sn in ORD:
    bs=[b for b in snaps[sn] if b["label"] and 'Снимок' in b["label"]]
    s1,s2=bs[0]["data"],bs[1]["data"]
    doms=bs[0]["doms"]
    G={"meta":META[sn],"labels":[b["label"].replace('Снимок ','').replace(' XML','') for b in bs],
       "doms":[]}
    for d in doms:
        keys=[]
        allq=set(s1.get(d,{}))|set(s2.get(d,{}))
        for q in allq:
            m=KW.get(q)
            if not m: continue
            br,vol,cl=m
            if br in EXCL_BRAND: continue
            p1=s1.get(d,{}).get(q); p2=s2.get(d,{}).get(q)
            keys.append({"q":q,"b":br,"v":vol,"t":tier(vol),"p1":p1,"p2":p2})
        keys.sort(key=lambda x:(x["p2"] if x["p2"] else 999, -x["v"]))
        # brand rollup on snapshot 2
        bl={}
        for k in keys:
            if k["p2"] is None or k["p2"]>30: continue
            e=bl.setdefault(k["b"],{"b":k["b"],"v":k["v"],"t":k["t"],"best":999,"n":0,"t10":0,"t3":0})
            e["best"]=min(e["best"],k["p2"]); e["n"]+=1
            if k["p2"]<=10: e["t10"]+=1
            if k["p2"]<=3: e["t3"]+=1
        brands=sorted(bl.values(), key=lambda x:(x["best"],-x["v"]))
        def cnt(p,lo,hi,t=None):
            return sum(1 for k in keys if k[p] is not None and lo<=k[p]<=hi and (t is None or k["t"]==t))
        G["doms"].append({"d":d,
          "t30a":cnt("p1",1,30),"t30b":cnt("p2",1,30),
          "t100a":cnt("p1",1,100),"t100b":cnt("p2",1,100),
          "t3":cnt("p2",1,3),"t10":cnt("p2",1,10),
          "vch10":cnt("p2",1,10,"ВЧ"),"sch10":cnt("p2",1,10,"СЧ"),"nch10":cnt("p2",1,10,"НЧ"),
          "vch30":cnt("p2",1,30,"ВЧ"),"sch30":cnt("p2",1,30,"СЧ"),
          "brands":brands,"keys":[k for k in keys if (k["p2"] and k["p2"]<=50) or (k["p1"] and k["p1"]<=50)][:120],
          "nkeys":len(keys)})
    G["doms"].sort(key=lambda x:-x["t30b"])
    out[sn]=G
json.dump(out, open("deep.json","w"), ensure_ascii=False)
tot=sum(len(g["doms"]) for g in out.values())
print("групп",len(out),"доменов",tot,"размер",len(open("deep.json").read())//1024,"KB")
for sn in ORD:
    g=out[sn]; n=len(g["doms"])
    print(f"  {g['meta'][0]:20s} n={n:2d} Т30 {sum(d['t30a'] for d in g['doms'])/n:5.1f} → {sum(d['t30b'] for d in g['doms'])/n:5.1f}")
