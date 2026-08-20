import pickle
res=pickle.load(open("newres.pkl","rb"))
NAMES={"группа 1":"Гр.1 · 7стр из выдачи","группа 2":"Гр.2 · 7стр v4",
       "группа 3":"Гр.3 · 11стр","группа 4":"Гр.4 · 11стр #2",
       "группа 5":"Гр.5 · 7стр v5 Theme2","группа 6":"Гр.6 · 7стр v4_2 Theme1"}
for sn in ["группа 3","группа 1","группа 4","группа 5","группа 6","группа 2"]:
    r=res[sn]
    print(f"\n=== {NAMES[sn]} ===")
    print(f"{'домен':16s} {'ВЧ10':>4s} {'СЧ10':>4s} {'НЧ10':>4s} {'Т3':>3s} {'Т30':>4s} {'Т100':>5s} брендов_в_Т30")
    for d,p in sorted(r["perdom"].items(), key=lambda x:-x[1]["t30"]):
        print(f"{d:16s} {p['vch']:4d} {p['sch']:4d} {p['nch']:4d} {p['t3']:3d} {p['t30']:4d} "
              f"{p['t100']:5d} {len(p['brands']):3d}")
print("\n=== ЛУЧШИЕ ДОМЕНЫ ПО Т30 (все группы) ===")
allr=[]
for sn,r in res.items():
    for d,p in r["perdom"].items(): allr.append((d,sn,p))
allr.sort(key=lambda x:-x[2]["t30"])
for d,sn,p in allr[:12]:
    print(f"{d:16s} {NAMES[sn]:26s} Т30={p['t30']:4d} ВЧ10={p['vch']:2d} СЧ10={p['sch']:2d} "
          f"брендов={len(p['brands']):3d}")
print("\nбренды в Т30 у лидера:", ", ".join(allr[0][2]["brands"][:30]))
