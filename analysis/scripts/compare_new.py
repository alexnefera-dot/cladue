import pickle
res=pickle.load(open("newres.pkl","rb"))
def sub(sn, pred=lambda d: True):
    r=res[sn]; ds=[d for d in r["perdom"] if pred(d)]
    n=len(ds)
    return {"n":n,
      "t30":sum(r["perdom"][d]["t30"] for d in ds)/n,
      "t100":sum(r["perdom"][d]["t100"] for d in ds)/n,
      "hs":sum(r["perdom"][d]["hs"] for d in ds)/n,
      "vch":sum(r["perdom"][d]["vch"] for d in ds),
      "t3":sum(r["perdom"][d]["t3"] for d in ds),
      "ent":sum(1 for d in ds if r["perdom"][d]["t30"]>0)/n}
T=lambda d: d.endswith(".team")

def show(title, pairs):
    print(f"\n=== {title} ===")
    print(f"{'сторона':34s} {'n':>2s} {'Т30/дом':>8s} {'Т100/дом':>9s} {'ВЧ Т10':>7s} {'Т3':>4s} {'есть Т30':>9s}")
    for name,s in pairs:
        print(f"{name:34s} {s['n']:2d} {s['t30']:8.1f} {s['t100']:9.1f} {s['vch']:7d} {s['t3']:4d} {s['ent']*100:8.0f}%")

show("ИСТОЧНИК КОНТЕНТА · 7 страниц · полные группы",
     [("Гр.1 из выдачи", sub("группа 1")), ("Гр.2 генератор v4", sub("группа 2"))])
show("ИСТОЧНИК КОНТЕНТА · только .team",
     [("Гр.1 из выдачи (.team)", sub("группа 1",T)), ("Гр.2 генератор v4 (.team)", sub("группа 2",T))])
show("ОБЪЁМ СТРАНИЦ · только .team",
     [("7 стр · Гр.2 (.team)", sub("группа 2",T)),
      ("11 стр · Гр.3", sub("группа 3",T)), ("11 стр · Гр.4 (.team)", sub("группа 4",T))])
show("ДВЕ ПАРТИИ ОДНОГО ФОРМАТА · 11 страниц",
     [("Гр.3 · Generator_11page", sub("группа 3")), ("Гр.4 · Generator_11page_2", sub("группа 4"))])
show("ДВЕ ПАРТИИ ОДНОГО ФОРМАТА · 7 страниц генератор",
     [("Гр.2 · v4", sub("группа 2",T)), ("Гр.5 · v5 Theme2", sub("группа 5",T)),
      ("Гр.6 · v4_2 Theme1", sub("группа 6",T))])
show("ЗОНЫ · внутри Гр.1 и Гр.2",
     [("Гр.1 .team", sub("группа 1",T)),
      ("Гр.1 .buzz/.quest/.bond", sub("группа 1", lambda d: not T(d))),
      ("Гр.2 .team", sub("группа 2",T)),
      ("Гр.2 .buzz/.icu/.top", sub("группа 2", lambda d: not T(d)))])
