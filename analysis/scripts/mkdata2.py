import pickle, collections, statistics, json
G=pickle.load(open("full.pkl","rb"))
ORD=["группа 3","группа 1","группа 4","группа 5","группа 6","группа 2",
     "12pages_withdate · Theme1","12pages_withdate · Theme2","12pages_nodate",
     "7pages_nodate","doregn.net 7 page","dorgen.net 12 page","Generation 50"]
T=lambda d: d.endswith(".team")
groups={}; brand_idx={}; catc=collections.Counter(); catall=collections.Counter(); cat3=collections.Counter()
catex=collections.defaultdict(list); ranked=0; t10n=0; t3n=0
for sn in ORD:
    g=G[sn]; last=g["snaps"][-1]["per"]; first=g["snaps"][0]["per"]
    tm=[d for d in g["doms"] if T(d)] or g["doms"]
    def series(k,ds):
        return [round(sum(s["per"][d][k] for d in ds)/len(ds),2) for s in g["snaps"]]
    v=sorted([last[d]["t10"] for d in tm],reverse=True)
    doms=[]
    for d in sorted(g["doms"], key=lambda x:-last[x]["t10"]):
        p=last[d]
        doms.append({"d":d,"t10":p["t10"],"t30":p["t30"],"t100":p["t100"],"t3":p["t3"],
          "vch":p["vch"],"sch":p["sch"],"nch":p["nch"],
          "t10a":first[d]["t10"],"t100a":first[d]["t100"],
          "tr":[s["per"][d]["t10"] for s in g["snaps"]],
          "brands":p["brands"],"keys":p["keys"][:150]})
        for k in p["keys"]:
            e=brand_idx.setdefault(k["b"],{"b":k["b"],"v":k["v"],"t":k["t"],"keys":[],"doms":set(),"gr":set()})
            e["keys"].append({"q":k["q"],"p":k["p"],"c":k["c"],"d":d,"g":g["name"]})
            e["doms"].add(d); e["gr"].add(g["name"])
            catc[k["c"]]+=1; t10n+=1
            if k["p"]<=3: cat3[k["c"]]+=1; t3n+=1
            if len(catex[k["c"]])<6: catex[k["c"]].append({"q":k["q"],"p":k["p"],"b":k["b"]})
    groups[sn]={"name":g["name"],"cfg":g["cfg"],"wave":g["wave"],
      "labels":[s["label"] for s in g["snaps"]],
      "n":len(g["doms"]),"ntm":len(tm),
      "t10":sum(v)/len(v),"med":statistics.median(v),
      "wo":(sum(v[1:])/(len(v)-1)) if len(v)>1 else 0,
      "vals":v,
      "ser":series("t10",tm),"ser30":series("t30",tm),
      "vch":sum(last[d]["vch"] for d in g["doms"]),"sch":sum(last[d]["sch"] for d in g["doms"]),
      "t3":sum(last[d]["t3"] for d in g["doms"]),
      "z100":sum(1 for d in g["doms"] if last[d]["t100"]==0),
      "z100a":sum(1 for d in g["doms"] if first[d]["t100"]==0),
      "brands":len({b["b"] for d in g["doms"] for b in last[d]["brands"]}),
      "hb":len({b["b"] for d in g["doms"] for b in last[d]["brands"] if b["t"]!="НЧ"}),
      "leadshare": (max(v)/sum(v)) if sum(v) else 0,
      "doms":doms}
# денominator: ranked keys at last snapshot
import core
KW=core.KW
for sn in ORD:
    g=G[sn]
    pass
brands=[]
for b,e in brand_idx.items():
    e["keys"].sort(key=lambda x:x["p"])
    brands.append({"b":b,"v":e["v"],"t":e["t"],"n":len(e["keys"]),
      "best":min(k["p"] for k in e["keys"]),"t3":sum(1 for k in e["keys"] if k["p"]<=3),
      "nd":len(e["doms"]),"groups":sorted(e["gr"]),
      "cats":dict(collections.Counter(k["c"] for k in e["keys"])),"keys":e["keys"][:200]})
brands.sort(key=lambda x:(-x["n"],x["best"]))
cats=[{"c":c,"t10":catc[c],"t3":cat3.get(c,0),"ex":catex[c]} for c in catc]
cats.sort(key=lambda x:-x["t10"])
json.dump({"order":ORD,"groups":groups,"brands":brands,"cats":cats,
           "tot":{"t10":t10n,"t3":t3n,"brands":len(brands),
                  "doms":sum(groups[s]["n"] for s in ORD),"groups":len(ORD)}},
          open("full.json","w"), ensure_ascii=False)
print("групп",len(ORD),"доменов",sum(groups[s]["n"] for s in ORD),
      "ключей Т10",t10n,"брендов",len(brands),
      "размер",len(open("full.json").read())//1024,"KB")
