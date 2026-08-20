import pickle
res=pickle.load(open("m2res.pkl","rb"))
T=lambda d: d.endswith(".team")
def sub(sn,i=1,p=None):
    r=res[sn]; per=r["snaps"][i]["per"]
    ds=[d for d in r["doms"] if (p(d) if p else True)]; n=len(ds)
    return {"n":n,"t30":sum(per[d]["t30"] for d in ds)/n,
            "t100":sum(per[d]["t100"] for d in ds)/n,
            "hs":sum(per[d]["hs"] for d in ds),
            "vch30":sum(per[d]["vch30"] for d in ds),
            "grow":sum(1 for d in ds if per[d]["t30"]>r["snaps"][0]["per"][d]["t30"])/n,
            "drop":sum(1 for d in ds if per[d]["t30"]<r["snaps"][0]["per"][d]["t30"])/n}
def show(t,rows):
    print(f"\n=== {t} ===")
    print(f"{'сторона':30s} {'n':>2s} {'Т30/дом':>8s} {'Т100/дом':>9s} {'ВЧ+СЧ Т10':>10s} {'ВЧ Т30':>7s} {'растёт':>7s} {'просел':>7s}")
    for nm,s in rows:
        print(f"{nm:30s} {s['n']:2d} {s['t30']:8.1f} {s['t100']:9.1f} {s['hs']:10d} {s['vch30']:7d} "
              f"{s['grow']*100:6.0f}% {s['drop']*100:6.0f}%")
show("ИСТОЧНИК КОНТЕНТА · только .team · замер 2",
  [("Гр.1 · 7page_yandex (из выдачи)", sub("группа 1",1,T)),
   ("Гр.2 · generator v4", sub("группа 2",1,T))])
show("ОБЪЁМ СТРАНИЦ · только .team · замер 2",
  [("7 стр · Гр.2 v4", sub("группа 2",1,T)),
   ("7 стр · Гр.5 v5", sub("группа 5",1,T)),
   ("7 стр · Гр.6 v4_2", sub("группа 6",1,T)),
   ("11 стр · Гр.3 Generator_11page", sub("группа 3",1,T)),
   ("11 стр · Гр.4 Generator_11page_2", sub("группа 4",1,T))])
show("ВЕРСИЯ И ШАБЛОН · 7 страниц генератора · только .team",
  [("Гр.2 · v4 · шаблон ?", sub("группа 2",1,T)),
   ("Гр.5 · v5 · Theme2", sub("группа 5",1,T)),
   ("Гр.6 · v4_2 · Theme1", sub("группа 6",1,T))])
show("ЗОНЫ · замер 2",
  [("Гр.1 .team", sub("группа 1",1,T)),
   ("Гр.1 прочие", sub("группа 1",1,lambda d:not T(d))),
   ("Гр.2 .team", sub("группа 2",1,T)),
   ("Гр.2 прочие", sub("группа 2",1,lambda d:not T(d)))])
