import pickle, collections, re, json
import core
KW=core.KW; EXCL_BRAND=core.EXCL_BRAND
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
snaps=pickle.load(open("snaps2.pkl","rb"))

PAT=[("зеркало",      r"зеркал|mirror"),
     ("вход",         r"\bвход\b|войти|log ?in"),
     ("регистрация",  r"регистрац|\bреги\b|sign ?up|создать аккаунт"),
     ("офиц. сайт",   r"официальн|\bофиц\b|official"),
     ("бонус/промокод",r"бонус|промокод|промо|фриспин|freespin|бездеп|no ?deposit"),
     ("играть/деньги",r"играть|на деньги|на реальные|игровые автоматы|слоты|игра\b"),
     ("приложение",   r"приложени|скачать|apk|андроид|android|\bios\b|мобильн|download|app\b"),
     ("отзывы",       r"отзыв|review|развод|вывод"),
     ("личный кабинет",r"кабинет|личный|аккаунт|account|профил"),
     ("рабочее/актуальное",r"рабоч|актуальн|сегодня|新|свеж"),
     ("casino/казино",r"казино|casino|kazino"),
    ]
def cls(q, brand):
    for name,rx in PAT:
        if re.search(rx,q): return name
    # bare brand?
    core_q=re.sub(r"\s+"," ",q).strip()
    if core_q==brand.lower() or core_q.replace(" ","")==brand.lower().replace(" ",""):
        return "голый бренд"
    return "прочее"

rows=[]
for sn,bs in snaps.items():
    bb=[b for b in bs if b["label"] and 'Снимок' in b["label"]]
    s1,s2=bb[0]["data"],bb[1]["data"]
    for d in bb[0]["doms"]:
        for q,p in s2.get(d,{}).items():
            m=KW.get(q)
            if not m: continue
            br,vol,_=m
            if br in EXCL_BRAND: continue
            rows.append({"g":sn,"d":d,"q":q,"b":br,"v":vol,"t":tier(vol),
                         "p":p,"p1":s1.get(d,{}).get(q),"c":cls(q,br),
                         "lat":all(ord(c)<128 for c in q)})
top10=[r for r in rows if r["p"]<=10]
print(f"всего ранжирующихся на замере 2: {len(rows)}, из них в ТОП-10: {len(top10)}")

print("\n=== ТИПЫ ЗАПРОСОВ В ТОП-10 ===")
c=collections.Counter(r["c"] for r in top10)
call=collections.Counter(r["c"] for r in rows)
print(f"{'тип':22s} {'Т10':>5s} {'доля':>6s} {'всего':>6s} {'конверсия в Т10':>15s}")
for k,v in c.most_common():
    print(f"{k:22s} {v:5d} {v/len(top10)*100:5.0f}% {call[k]:6d} {v/call[k]*100:14.0f}%")

print("\n=== ЛАТИНИЦА vs КИРИЛЛИЦА В ТОП-10 ===")
for lat in (True,False):
    g=[r for r in top10 if r["lat"]==lat]
    ga=[r for r in rows if r["lat"]==lat]
    print(f"  {'латиница' if lat else 'кириллица':10s}: Т10={len(g):4d} ({len(g)/len(top10)*100:3.0f}%) "
          f"из {len(ga):4d} ранжирующихся, конверсия {len(g)/len(ga)*100:.0f}%")

print("\n=== ТИПЫ ЗАПРОСОВ ПО ТИРАМ (ТОП-10) ===")
for t in ("ВЧ","СЧ","НЧ"):
    g=[r for r in top10 if r["t"]==t]
    if not g: continue
    cc=collections.Counter(r["c"] for r in g)
    print(f"  {t} (n={len(g)}): " + ", ".join(f"{k} {v}" for k,v in cc.most_common(6)))
json.dump(rows, open("keyrows.json","w"), ensure_ascii=False)
