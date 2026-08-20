import io, openpyxl, pickle, collections, statistics, json
import core
KW=core.KW; EXCL_BRAND=core.EXCL_BRAND
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
wb=openpyxl.load_workbook(io.BytesIO(open("launches.xlsx",'rb').read()), data_only=True)

META={"группа 1":("7 стр · из выдачи","—","?"),
      "группа 2":("7 стр · генератор","v4","?"),
      "группа 3":("11 стр · генератор","?","?"),
      "группа 4":("11 стр · генератор #2","?","?"),
      "группа 5":("7 стр · генератор","v5","Theme2"),
      "группа 6":("7 стр · генератор #2","v4_2","Theme1")}

G={}
for sn in wb.sheetnames[1:]:
    rows=list(ws.iter_rows(values_only=True)) if False else list(wb[sn].iter_rows(values_only=True))
    doms=[str(c).strip().lower() for c in rows[1][1:] if c not in (None,'')]
    data={d:{} for d in doms}
    for r in rows[2:1572]:
        q=r[0]
        if q in (None,''): continue
        q=str(q).strip().lower()
        for i,d in enumerate(doms):
            v=r[1+i]
            if v is None: continue
            try: p=int(v)
            except: continue
            if p>=1: data[d][q]=p
    G[sn]=(doms,data)

print("=== ЗАМЕР 1 · 20.08.2026 ===")
print(f"{'группа':9s} {'конфигурация':24s} {'дом':>3s} {'ВЧ10':>5s} {'СЧ10':>5s} {'НЧ10':>5s} "
      f"{'ВЧ+СЧ/дом':>9s} {'Т30':>5s} {'Т30/дом':>8s} {'Т100':>5s} {'зашло':>6s}")
res={}
for sn in ["группа 1","группа 2","группа 3","группа 4","группа 5","группа 6"]:
    doms,data=G[sn]
    c=collections.Counter(); perdom={}
    for d in doms:
        pc=collections.Counter(); brands=set()
        for q,pos in data[d].items():
            m=KW.get(q)
            if not m: continue
            b,vol,_=m
            if b in EXCL_BRAND: continue
            t=tier(vol)
            for tp in (3,10,30,50,100):
                if pos<=tp: pc[(t,tp)]+=1; c[(t,tp)]+=1
            if pos<=30: brands.add(b)
        perdom[d]={"hs":pc[("ВЧ",10)]+pc[("СЧ",10)],
                   "vch":pc[("ВЧ",10)],"sch":pc[("СЧ",10)],"nch":pc[("НЧ",10)],
                   "t30":sum(pc[(t,30)] for t in ("ВЧ","СЧ","НЧ")),
                   "t100":sum(pc[(t,100)] for t in ("ВЧ","СЧ","НЧ")),
                   "t3":sum(pc[(t,3)] for t in ("ВЧ","СЧ","НЧ")),
                   "brands":sorted(brands)}
    n=len(doms)
    hs=sum(p["hs"] for p in perdom.values()); t30=sum(p["t30"] for p in perdom.values())
    t100=sum(p["t100"] for p in perdom.values())
    ent=sum(1 for p in perdom.values() if p["hs"]>0)
    res[sn]={"n":n,"perdom":perdom,"hs":hs,"t30":t30,"t100":t100,"ent":ent,"meta":META[sn]}
    print(f"{sn:9s} {META[sn][0]:24s} {n:3d} {c[('ВЧ',10)]:5d} {c[('СЧ',10)]:5d} {c[('НЧ',10)]:5d} "
          f"{hs/n:9.2f} {t30:5d} {t30/n:8.1f} {t100:5d} {ent/n*100:5.0f}%")
pickle.dump(res, open("newres.pkl","wb"))
