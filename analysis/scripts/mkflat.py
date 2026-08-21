import pickle, collections, statistics, json, re
import core
KW=core.KW; EXCL_BRAND=core.EXCL_BRAND
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
G=pickle.load(open("full.pkl","rb"))
ORD=["группа 3","группа 1","группа 4","группа 5","группа 6","группа 2",
     "12pages_withdate · Theme1","12pages_withdate · Theme2","12pages_nodate",
     "7pages_nodate","doregn.net 7 page","dorgen.net 12 page","Generation 50"]
# конфигурация групп
CFG={
 "группа 3":{"fmt":"11 страниц, генератор","pages":"11","src":"генератор","ver":"?","theme":"?","cont":"Generator_11page_19.08_1…5 (id 695-699)","map":None},
 "группа 1":{"fmt":"7 страниц, контент из выдачи","pages":"7","src":"сайты из выдачи","ver":"—","theme":"?","cont":"7page_yandex_1/3/6/8 + 7page (888starz, baboss, banda, clubnika, ezcash, fenix)","map":None},
 "группа 4":{"fmt":"11 страниц, генератор (партия 2)","pages":"11","src":"генератор","ver":"?","theme":"?","cont":"Generator_11page_2_19.08_1…5 (id 706-710)","map":None},
 "группа 5":{"fmt":"7 страниц, генератор v5","pages":"7","src":"генератор","ver":"v5","theme":"Theme2","cont":"Generator_v5_19.08_1…5 (id 700-704)","map":None},
 "группа 6":{"fmt":"7 страниц, генератор v4_2","pages":"7","src":"генератор","ver":"v4_2","theme":"Theme1","cont":"Generator_v4_2_19.08_1…5 (id 711-715)","map":None},
 "группа 2":{"fmt":"7 страниц, генератор v4","pages":"7","src":"генератор","ver":"v4","theme":"?","cont":"один контент на всех","map":None},
 "12pages_withdate · Theme1":{"fmt":"12 страниц с датами","pages":"12 + даты","src":"генератор","ver":"—","theme":"Theme1","cont":"12pages_withdate_20.08_11…18 (id 758-765)","map":None},
 "12pages_withdate · Theme2":{"fmt":"12 страниц с датами","pages":"12 + даты","src":"генератор","ver":"—","theme":"Theme2","cont":"12pages_withdate_20.08_1…10 (id 748-757)","map":None},
 "12pages_nodate":{"fmt":"12 страниц без дат","pages":"12 без дат","src":"генератор","ver":"—","theme":"Theme1","cont":"12pages_nodate_20.08_1…5 (id 743-747)","map":None},
 "7pages_nodate":{"fmt":"7 страниц без дат","pages":"7 без дат","src":"генератор","ver":"—","theme":"Theme2","cont":"7pages_nodate_20.08_1-2 (716-717) + MultiContentTest_1/3 (653, 655)","map":None},
 "doregn.net 7 page":{"fmt":"7 страниц, именованные контенты","pages":"7","src":"именованные","ver":"—","theme":"—","cont":"kostoreznaya1, krahmalnya1, machtovaya1, pergamentnaya1, sinilnya1",
   "map":{"bfkq.team":"kostoreznaya1","cglr.team":"krahmalnya1","dhmt.team":"machtovaya1",
          "1073.team":"pergamentnaya1","1284.team":"sinilnya1"}},
 "dorgen.net 12 page":{"fmt":"12 страниц, наборы","pages":"12","src":"наборы","ver":"—","theme":"—","cont":"nabor28gotovyi…nabor32gotovyi",
   "map":{"1596.team":"nabor28gotovyi","f7n.team":"nabor29gotovyi","g2k.team":"nabor30gotovyi",
          "h5r.team":"nabor31gotovyi","1739.team":"nabor32gotovyi"}},
 "Generation 50":{"fmt":"конфигурация не присылалась","pages":"?","src":"?","ver":"?","theme":"?","cont":"не присланы","map":None},
}
PAT=[("зеркало",r"зеркал|mirror"),("вход",r"\bвход\b|войти|log ?in"),
     ("регистрация",r"регистрац|\bреги\b|sign ?up|создать аккаунт"),
     ("офиц. сайт",r"официальн|\bофиц\b|official"),
     ("бонус/промокод",r"бонус|промокод|промо|фриспин|freespin|бездеп|no ?deposit"),
     ("играть/деньги",r"играть|на деньги|на реальные|игровые автоматы|слоты|игра\b"),
     ("приложение",r"приложени|скачать|apk|андроид|android|\bios\b|мобильн|download|app\b"),
     ("отзывы",r"отзыв|review|развод|вывод"),("личный кабинет",r"кабинет|личный|аккаунт|account|профил"),
     ("бренд + казино",r"казино|casino|kazino")]
def cls(q):
    for n,rx in PAT:
        if re.search(rx,q): return n
    return "бренд без добавок" if len(q.split())<=3 else "прочее"

doms=[]; brand_idx={}; catc=collections.Counter(); cat3=collections.Counter()
catex=collections.defaultdict(list); zones=collections.defaultdict(lambda:{"n":0,"t10":0,"hs":0,"t3":0,"ent":0})
groups={}
for sn in ORD:
    g=G[sn]; cfg=CFG[sn]; snaps=g["snaps"]; last=snaps[-1]["per"]
    tm=[d for d in g["doms"] if d.endswith(".team")] or g["doms"]
    v=sorted([last[d]["t10"] for d in tm],reverse=True)
    groups[sn]={"name":g["name"],"cfg":g["cfg"],"wave":g["wave"],
      "labels":[s["label"] for s in snaps],"n":len(g["doms"]),"ntm":len(tm),
      "pages":cfg["pages"],"fmt":cfg["fmt"],"src":cfg["src"],"ver":cfg["ver"],"theme":cfg["theme"],"cont":cfg["cont"],
      "t10":sum(v)/len(v),"med":statistics.median(v),
      "wo":(sum(v[1:])/(len(v)-1)) if len(v)>1 else 0,"vals":v,
      "ser":[round(sum(s["per"][d]["t10"] for d in tm)/len(tm),2) for s in snaps],
      "serhs":[sum(s["per"][d]["vch"]+s["per"][d]["sch"] for d in g["doms"]) for s in snaps],
      "vch":sum(last[d]["vch"] for d in g["doms"]),"sch":sum(last[d]["sch"] for d in g["doms"]),
      "t3":sum(last[d]["t3"] for d in g["doms"]),
      "z100":sum(1 for d in g["doms"] if last[d]["t100"]==0),
      "brands":len({b["b"] for d in g["doms"] for b in last[d]["brands"]}),
      "leadshare":(max(v)/sum(v)) if sum(v) else 0}
    for d in g["doms"]:
        zone="."+d.rsplit(".",1)[-1]
        p=last[d]
        # ключи с историей позиций
        allq=set()
        for s in snaps: allq |= set(x["q"] for x in s["per"][d]["keys"])
        keys=[]
        for q in allq:
            m=KW.get(q)
            if not m: continue
            br,vol,_=m
            hist=[]
            for s in snaps:
                kk=[x for x in s["per"][d]["keys"] if x["q"]==q]
                hist.append(kk[0]["p"] if kk else None)
            if hist[-1] is None and not any(hist): continue
            keys.append({"q":q,"b":br,"v":vol,"t":tier(vol),"c":cls(q),"h":hist,"p":hist[-1]})
        keys.sort(key=lambda x:(x["p"] if x["p"] else 99,-x["v"]))
        for k in keys:
            if k["p"] is None: continue
            e=brand_idx.setdefault(k["b"],{"b":k["b"],"v":k["v"],"t":k["t"],"keys":[],"doms":set(),"gr":set()})
            e["keys"].append({"q":k["q"],"p":k["p"],"c":k["c"],"d":d,"g":g["name"],"h":k["h"]})
            e["doms"].add(d); e["gr"].add(g["name"])
            catc[k["c"]]+=1
            if k["p"]<=3: cat3[k["c"]]+=1
            if len(catex[k["c"]])<8: catex[k["c"]].append({"q":k["q"],"p":k["p"],"b":k["b"]})
        z=zones[zone]; z["n"]+=1; z["t10"]+=p["t10"]; z["hs"]+=p["vch"]+p["sch"]; z["t3"]+=p["t3"]
        if p["t10"]>0: z["ent"]+=1
        doms.append({"d":d,"zone":zone,"g":sn,"gname":g["name"],"wave":g["wave"],
          "pages":cfg["pages"],"fmt":cfg["fmt"],"src":cfg["src"],"theme":cfg["theme"],"ver":cfg["ver"],
          "cont":(cfg["map"] or {}).get(d),
          "tr":[s["per"][d]["t10"] for s in snaps],
          "tr30":[s["per"][d]["t30"] for s in snaps],
          "tr100":[s["per"][d]["t100"] for s in snaps],
          "labels":[s["label"] for s in snaps],
          "t10":p["t10"],"t30":p["t30"],"t100":p["t100"],"t3":p["t3"],
          "vch":p["vch"],"sch":p["sch"],"nch":p["nch"],
          "best":min([k["p"] for k in keys if k["p"]], default=None),
          "nb":len(p["brands"]),"nbh":sum(1 for b in p["brands"] if b["t"]!="НЧ"),
          "brands":p["brands"],"keys":keys[:130]})
doms.sort(key=lambda x:(-(x["vch"]*3+x["sch"]*2+x["t10"]/10),-x["t10"]))
brands=[]
for b,e in brand_idx.items():
    e["keys"].sort(key=lambda x:x["p"])
    brands.append({"b":b,"v":e["v"],"t":e["t"],"n":len(e["keys"]),
      "best":min(k["p"] for k in e["keys"]),"t3":sum(1 for k in e["keys"] if k["p"]<=3),
      "nd":len(e["doms"]),"groups":sorted(e["gr"]),
      "cats":dict(collections.Counter(k["c"] for k in e["keys"])),"keys":e["keys"][:250]})
brands.sort(key=lambda x:(-x["n"],x["best"]))
cats=[{"c":c,"t10":catc[c],"t3":cat3.get(c,0),"ex":catex[c]} for c in catc]
cats.sort(key=lambda x:-x["t10"])
zl=[{"z":k,**v} for k,v in zones.items()]
zl.sort(key=lambda x:-x["n"])
json.dump({"order":ORD,"groups":groups,"doms":doms,"brands":brands,"cats":cats,"zones":zl,
  "tot":{"doms":len(doms),"groups":len(ORD),"t10":sum(catc.values()),
         "t3":sum(cat3.values()),"brands":len(brands),
         "hs":sum(d["vch"]+d["sch"] for d in doms)}},
  open("flat.json","w"), ensure_ascii=False)
print("доменов",len(doms),"брендов",len(brands),"ключей Т10",sum(catc.values()),
      "размер",len(open("flat.json").read())//1024,"KB")
print("зоны:", [(z["z"],z["n"],z["t10"]) for z in zl])
