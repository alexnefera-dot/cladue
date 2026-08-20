import pickle, collections
res=pickle.load(open("m3res.pkl","rb"))
T=lambda d: d.endswith(".team")
def sub(sn,p=None):
    r=res[sn]; ds=[d for d in r["per"] if (p(d) if p else True)]; n=len(ds)
    S=lambda k: sum(r["per"][d][k] for d in ds)
    return {"n":n,"t10":S("t10")/n,"t30":S("t30")/n,"t100":S("t100")/n,
            "vch":S("vch"),"sch":S("sch"),"t3":S("t3"),
            "z":sum(1 for d in ds if r["per"][d]["t30"]==0)}
def show(t,note,rows):
    print(f"\n=== {t} ===");  print("   "+note)
    print(f"{'сторона':36s} {'n':>2s} {'Т10/дом':>8s} {'Т30/дом':>8s} {'ВЧ':>3s} {'СЧ':>3s} {'Т3':>3s} {'пусто':>5s}")
    for nm,s in rows:
        print(f"{nm:36s} {s['n']:2d} {s['t10']:8.1f} {s['t30']:8.1f} {s['vch']:3d} {s['sch']:3d} {s['t3']:3d} {s['z']:5d}")

show("ШАБЛОН · 12 страниц с датами · только .team",
     "Одна партия контентов, разбитая после генерации. Состав .team совпадает: 7 против 7.",
  [("Theme1", sub("12pages_withdate · Theme1",T)),("Theme2", sub("12pages_withdate · Theme2",T))])
show("ДАТЫ · 12 страниц · Theme1 · только .team",
     "Контенты созданы с разницей в минуту (11:30 и 11:31), шаблон и объём совпадают.",
  [("с датами", sub("12pages_withdate · Theme1",T)),("без дат", sub("12pages_nodate",T))])
show("ВСЕ ГРУППЫ ЗАМЕРА 17:34 · только .team", "Возраст записи о запуске одинаковый — 13 минут.",
  [(res[s]["name"][:36], sub(s,T)) for s in res])
print("\n=== ЗОНЫ · 12pages_withdate · Theme2 ===")
for d,v in sorted(res["12pages_withdate · Theme2"]["per"].items(), key=lambda x:-x[1]["t10"]):
    print(f"   {d:16s} Т10={v['t10']:3d} Т30={v['t30']:3d} ВЧ={v['vch']} СЧ={v['sch']} Т3={v['t3']}")
print("\n=== ДОМЕНЫ · 12pages_withdate · Theme1 ===")
for d,v in sorted(res["12pages_withdate · Theme1"]["per"].items(), key=lambda x:-x[1]["t10"]):
    print(f"   {d:16s} Т10={v['t10']:3d} Т30={v['t30']:3d} ВЧ={v['vch']} СЧ={v['sch']} Т3={v['t3']} брендов={len(v['brands'])}")
print("\n=== ДОМЕНЫ · 12pages_nodate ===")
for d,v in sorted(res["12pages_nodate"]["per"].items(), key=lambda x:-x[1]["t10"]):
    print(f"   {d:16s} Т10={v['t10']:3d} Т30={v['t30']:3d} Т100={v['t100']:3d} Т3={v['t3']}")
print("\n=== ДОМЕНЫ · имена и наборы ===")
for sn in ("doregn.net 7 page","dorgen.net 12 page","7pages_nodate"):
    print(f"  {res[sn]['name']}:")
    for d,v in res[sn]["per"].items():
        print(f"   {d:16s} Т10={v['t10']:3d} Т30={v['t30']:3d} Т100={v['t100']:3d}")
print("\n=== ДОРОГИЕ БРЕНДЫ В ТОП-10 (все новые группы) ===")
for sn,r in res.items():
    for d,v in r["per"].items():
        for b in v["brands"]:
            if b["t"]!="НЧ":
                print(f"   {r['name'][:26]:26s} {d:14s} {b['b']:14s} {b['t']} {b['v']/1e6:.1f}M поз={b['best']} ключей={b['n']}")
