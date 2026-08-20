import pickle, collections, re, json
import core
KW=core.KW; EXCL_BRAND=core.EXCL_BRAND
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
snaps=pickle.load(open("snaps2.pkl","rb"))
META={"группа 3":["Generator_11page","Гр.3","11 страниц · генератор","?","?"],
      "группа 1":["7page_yandex","Гр.1","7 страниц · сайты из выдачи","—","?"],
      "группа 4":["Generator_11page_2","Гр.4","11 страниц · генератор","?","?"],
      "группа 5":["Generator_v5","Гр.5","7 страниц · генератор","v5","Theme2"],
      "группа 6":["Generator_v4_2","Гр.6","7 страниц · генератор","v4_2","Theme1"],
      "группа 2":["generator v4","Гр.2","7 страниц · генератор","v4","?"]}
ORD=["группа 3","группа 1","группа 4","группа 5","группа 6","группа 2"]

PAT=[("зеркало",       r"зеркал|mirror"),
     ("вход",          r"\bвход\b|войти|log ?in"),
     ("регистрация",   r"регистрац|\bреги\b|sign ?up|создать аккаунт"),
     ("офиц. сайт",    r"официальн|\bофиц\b|official"),
     ("бонус/промокод",r"бонус|промокод|промо|фриспин|freespin|бездеп|no ?deposit"),
     ("играть/деньги", r"играть|на деньги|на реальные|игровые автоматы|слоты|игра\b"),
     ("приложение",    r"приложени|скачать|apk|андроид|android|\bios\b|мобильн|download|app\b"),
     ("отзывы",        r"отзыв|review|развод|вывод"),
     ("личный кабинет",r"кабинет|личный|аккаунт|account|профил"),
     ("бренд + казино",r"казино|casino|kazino")]
def cls(q):
    for n,rx in PAT:
        if re.search(rx,q): return n
    return "бренд без добавок" if len(q.split())<=3 else "прочее"

rows=[]
for sn in ORD:
    bb=[b for b in snaps[sn] if b["label"] and 'Снимок' in b["label"]]
    s1,s2=bb[0]["data"],bb[1]["data"]
    for d in bb[0]["doms"]:
        for q in set(s1.get(d,{}))|set(s2.get(d,{})):
            m=KW.get(q)
            if not m: continue
            br,vol,_=m
            if br in EXCL_BRAND: continue
            rows.append({"g":sn,"d":d,"q":q,"b":br,"v":vol,"t":tier(vol),
                         "p1":s1.get(d,{}).get(q),"p2":s2.get(d,{}).get(q),"c":cls(q)})

def inT(r,n): return r["p2"] is not None and r["p2"]<=n
T10=[r for r in rows if inT(r,10)]

# --- группы ---
groups={}
for sn in ORD:
    bb=[b for b in snaps[sn] if b["label"] and 'Снимок' in b["label"]]
    doms=bb[0]["doms"]
    G={"meta":META[sn],"labels":[b["label"].replace('Снимок ','').replace(' XML','') for b in bb],"doms":[]}
    for d in doms:
        kr=[r for r in rows if r["g"]==sn and r["d"]==d]
        k10=[r for r in kr if inT(r,10)]
        k10a=[r for r in kr if r["p1"] is not None and r["p1"]<=10]
        bl={}
        for k in k10:
            e=bl.setdefault(k["b"],{"b":k["b"],"v":k["v"],"t":k["t"],"best":999,"n":0,"t3":0,"cats":{}})
            e["best"]=min(e["best"],k["p2"]); e["n"]+=1
            if k["p2"]<=3: e["t3"]+=1
            e["cats"][k["c"]]=e["cats"].get(k["c"],0)+1
        G["doms"].append({"d":d,"t10a":len(k10a),"t10b":len(k10),
          "t3":sum(1 for r in k10 if r["p2"]<=3),
          "vch":sum(1 for r in k10 if r["t"]=="ВЧ"),"sch":sum(1 for r in k10 if r["t"]=="СЧ"),
          "nch":sum(1 for r in k10 if r["t"]=="НЧ"),
          "t30":sum(1 for r in kr if inT(r,30)),
          "brands":sorted(bl.values(),key=lambda x:(x["best"],-x["v"])),
          "keys":sorted([{"q":k["q"],"b":k["b"],"v":k["v"],"t":k["t"],"c":k["c"],
                          "p1":k["p1"],"p2":k["p2"]} for k in k10],
                        key=lambda x:(x["p2"],-x["v"]))})
    G["doms"].sort(key=lambda x:-x["t10b"])
    groups[sn]=G

# --- бренды ---
bi={}
for r in T10:
    e=bi.setdefault(r["b"],{"b":r["b"],"v":r["v"],"t":r["t"],"keys":[],"doms":set(),"groups":set()})
    e["keys"].append({"q":r["q"],"p":r["p2"],"p1":r["p1"],"c":r["c"],"d":r["d"],
                      "g":META[r["g"]][0]})
    e["doms"].add(r["d"]); e["groups"].add(META[r["g"]][0])
brands=[]
for b,e in bi.items():
    e["keys"].sort(key=lambda x:x["p"])
    brands.append({"b":b,"v":e["v"],"t":e["t"],"n":len(e["keys"]),
      "best":min(k["p"] for k in e["keys"]),
      "t3":sum(1 for k in e["keys"] if k["p"]<=3),
      "nd":len(e["doms"]),"groups":sorted(e["groups"]),
      "cats":dict(collections.Counter(k["c"] for k in e["keys"])),
      "keys":e["keys"]})
brands.sort(key=lambda x:(-x["n"],x["best"]))

# --- типы запросов ---
cats=[]
ranked=[r for r in rows if r["p2"] is not None]
allc=collections.Counter(r["c"] for r in ranked)
t10c=collections.Counter(r["c"] for r in T10)
t3c=collections.Counter(r["c"] for r in T10 if r["p2"]<=3)
for c in allc:
    cats.append({"c":c,"all":allc[c],"t10":t10c.get(c,0),"t3":t3c.get(c,0),
                 "conv":t10c.get(c,0)/allc[c],
                 "ex":[{"q":r["q"],"p":r["p2"],"b":r["b"]} for r in
                       sorted([x for x in T10 if x["c"]==c],key=lambda x:x["p2"])[:6]]})
cats.sort(key=lambda x:-x["t10"])
bytier={}
for t in ("ВЧ","СЧ","НЧ"):
    g=[r for r in T10 if r["t"]==t]
    bytier[t]={"n":len(g),"cats":dict(collections.Counter(r["c"] for r in g))}
bygroup={}
for sn in ORD:
    g=[r for r in T10 if r["g"]==sn]
    bygroup[META[sn][0]]={"n":len(g),"cats":dict(collections.Counter(r["c"] for r in g))}

json.dump({"groups":groups,"brands":brands,"cats":cats,"bytier":bytier,"bygroup":bygroup,
           "tot":{"rows":len(rows),"ranked":len(ranked),"t10":len(T10),"t3":sum(1 for r in T10 if r["p2"]<=3)}},
          open("deep10.json","w"), ensure_ascii=False)
print("ключей всего",len(rows),"в ТОП-10",len(T10),"брендов",len(brands),
      "размер",len(open("deep10.json").read())//1024,"KB")
print("\nтипы:", " | ".join(f"{c['c']} {c['t10']}({c['conv']*100:.0f}%)" for c in cats))
