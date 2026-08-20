import pickle, collections, json
import core
KW=core.KW; EXCL_BRAND=core.EXCL_BRAND
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
snaps=pickle.load(open("snaps2.pkl","rb"))
ORD=["группа 3","группа 1","группа 4","группа 5","группа 6","группа 2"]
META={"группа 1":("7 стр · из выдачи","—","?"),"группа 2":("7 стр · генератор","v4","?"),
      "группа 3":("11 стр · генератор","?","?"),"группа 4":("11 стр · генератор #2","?","?"),
      "группа 5":("7 стр · генератор","v5","Theme2"),"группа 6":("7 стр · генератор #2","v4_2","Theme1")}

def score(data, doms):
    out={}
    for d in doms:
        c=collections.Counter(); brands=set()
        for q,pos in data.get(d,{}).items():
            m=KW.get(q)
            if not m: continue
            b,vol,_=m
            if b in EXCL_BRAND: continue
            t=tier(vol)
            for tp in (3,10,30,50,100):
                if pos<=tp: c[(t,tp)]+=1
            if pos<=30: brands.add(b)
        out[d]={"vch":c[("ВЧ",10)],"sch":c[("СЧ",10)],"nch":c[("НЧ",10)],
                "hs":c[("ВЧ",10)]+c[("СЧ",10)],
                "t3":sum(c[(t,3)] for t in ("ВЧ","СЧ","НЧ")),
                "t30":sum(c[(t,30)] for t in ("ВЧ","СЧ","НЧ")),
                "t100":sum(c[(t,100)] for t in ("ВЧ","СЧ","НЧ")),
                "vch30":c[("ВЧ",30)],"sch30":c[("СЧ",30)],
                "brands":sorted(brands)}
    return out

res={}
for sn in ORD:
    bs=[b for b in snaps[sn] if b["label"] and 'Снимок' in b["label"]]
    doms=bs[0]["doms"]
    res[sn]={"meta":META[sn],"doms":doms,
             "snaps":[{"label":b["label"].replace('Снимок ','').replace(' XML',''),
                       "per":score(b["data"],doms)} for b in bs]}

print("=== ЗАМЕР 1 → ЗАМЕР 2 (все группы сняты 20.08 10:08-10:09) ===")
print(f"{'группа':9s} {'конфигурация':22s} {'n':>2s} | {'Т30/дом':>15s} | {'ВЧ+СЧ Т10':>13s} | {'ВЧ Т30':>11s}")
for sn in ORD:
    r=res[sn]; n=len(r["doms"]); s1,s2=r["snaps"][0]["per"],r["snaps"][1]["per"]
    t1=sum(x["t30"] for x in s1.values())/n; t2=sum(x["t30"] for x in s2.values())/n
    h1=sum(x["hs"] for x in s1.values()); h2=sum(x["hs"] for x in s2.values())
    v1=sum(x["vch30"] for x in s1.values()); v2=sum(x["vch30"] for x in s2.values())
    arrow="↑" if t2>t1 else ("↓" if t2<t1 else "=")
    print(f"{sn:9s} {r['meta'][0]:22s} {n:2d} | {t1:6.1f} → {t2:6.1f} {arrow} | {h1:5d} → {h2:5d} | {v1:4d} → {v2:4d}")
pickle.dump(res, open("m2res.pkl","wb"))
