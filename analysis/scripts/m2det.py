import pickle
res=pickle.load(open("m2res.pkl","rb"))
NAMES={"группа 1":"Гр.1 · 7page_yandex","группа 2":"Гр.2 · generator v4",
       "группа 3":"Гр.3 · Generator_11page","группа 4":"Гр.4 · Generator_11page_2",
       "группа 5":"Гр.5 · Generator_v5","группа 6":"Гр.6 · Generator_v4_2"}
print("=== ВОЗРАСТ vs КОНТЕНТ: Гр.3 и Гр.4 ===")
r3,r4=res["группа 3"],res["группа 4"]
t3_1=sum(x["t30"] for x in r3["snaps"][0]["per"].values())/5
t3_2=sum(x["t30"] for x in r3["snaps"][1]["per"].values())/5
t4_1=sum(x["t30"] for x in r4["snaps"][0]["per"].values())/5
t4_2=sum(x["t30"] for x in r4["snaps"][1]["per"].values())/5
print(f"  Гр.3 (контент создан 19.08 16:56): замер1 {t3_1:.1f} → замер2 {t3_2:.1f}")
print(f"  Гр.4 (контент создан 19.08 22:40): замер1 {t4_1:.1f} → замер2 {t4_2:.1f}")
print(f"  возраст Гр.3 на замере 1 ≈ 8,6 ч; возраст Гр.4 на замере 2 ≈ 11,5 ч")
print(f"  => Гр.4 СТАРШЕ на замере 2, чем Гр.3 была на замере 1, и всё равно ниже в {t3_1/t4_2:.1f} раза")

for sn in ["группа 3","группа 1","группа 4","группа 5","группа 6","группа 2"]:
    r=res[sn]; s1,s2=r["snaps"][0]["per"],r["snaps"][1]["per"]
    print(f"\n=== {NAMES[sn]} ===")
    print(f"{'домен':16s} {'Т30 з1':>7s} {'Т30 з2':>7s} {'ВЧ10':>5s} {'СЧ10':>5s} {'ВЧ30':>5s} {'Т3':>4s} {'брендов':>8s}")
    for d in sorted(r["doms"], key=lambda x:-s2[x]["t30"]):
        a,b=s1[d],s2[d]
        mark="↑" if b["t30"]>a["t30"] else ("↓" if b["t30"]<a["t30"] else "=")
        print(f"{d:16s} {a['t30']:7d} {b['t30']:6d}{mark} {b['vch']:5d} {b['sch']:5d} {b['vch30']:5d} "
              f"{b['t3']:4d} {len(b['brands']):8d}")

print("\n=== ПРАВИЛО ОТСЕВА НА ЗАМЕРЕ 2 (≤2 ключа в Т30 → 89% нулей по архиву) ===")
kill=[];keep=[]
for sn,r in res.items():
    s2=r["snaps"][1]["per"]
    for d in r["doms"]:
        (kill if s2[d]["t30"]<=2 else keep).append((d,NAMES[sn],s2[d]["t30"]))
print(f"под отсев: {len(kill)} из 40")
for d,g,t in sorted(kill,key=lambda x:x[1]): print(f"   {d:16s} {g:28s} Т30={t}")
