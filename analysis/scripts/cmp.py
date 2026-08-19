import pickle, collections, statistics
traj=pickle.load(open("traj.pkl","rb"))
FMT={"D273":"12page+даты","D274":"7page+даты","D265":"12page под бренд",
     "D266":"12page под бренд","D267":"12page под бренд","D262":"7page под бренд",
     "D268":"7page под бренд","D248":"nu 6page","D249":"nu 6page","D252":"nu 6page",
     "D253":"nu 6page","D255":"nu 1page/переисп.","D258":"именованные","D269":"предметные",
     "D261":"генерации .casino"}
def hs(sn): return sum(s['hs'] for s in sn.values())/max(len(sn),1)
def ent(sn): return sum(1 for s in sn.values() if s['hs']>0)/max(len(sn),1)

print("=== СРАВНЕНИЕ НА ОДИНАКОВОМ НОМЕРЕ ЗАМЕРА (ВЧ+СЧ Т10 на домен) ===")
for M in (2,3,4,5):
    rows=[(k,hs(traj[k][M-1]),ent(traj[k][M-1]),len(traj[k][M-1])) for k in traj
          if len(traj[k])>=M and len(traj[k][M-1])>=7]
    rows.sort(key=lambda x:-x[1])
    print(f"\n-- замер {M} (запуски с n>=7 доменов) --")
    for k,v,e,n in rows[:10]:
        print(f"  {k:6s} {FMT.get(k,''):20s} n={n:3d}  {v:6.2f}  зашло {e*100:3.0f}%")

print("\n=== ФОРМАТЫ: агрегат по последнему замеру ===")
agg=collections.defaultdict(lambda:[0,0,0])
for k,sns in traj.items():
    if k not in FMT or not sns: continue
    sn=sns[-1]; a=agg[FMT[k]]
    a[0]+=sum(s['hs'] for s in sn.values()); a[1]+=len(sn)
    a[2]+=sum(1 for s in sn.values() if s['hs']>0)
print(f"{'Формат':22s} {'дом':>4s} {'ВЧ+СЧ':>6s} {'/дом':>6s} {'зашло':>6s}")
for f,(t,n,e) in sorted(agg.items(), key=lambda x:-x[1][0]/max(x[1][1],1)):
    print(f"{f:22s} {n:4d} {t:6d} {t/n:6.2f} {e/n*100:5.0f}%")

print("\n=== ФОРМАТЫ: на замере 2 (единый возраст) ===")
agg2=collections.defaultdict(lambda:[0,0,0])
for k,sns in traj.items():
    if k not in FMT or len(sns)<2: continue
    sn=sns[1]; a=agg2[FMT[k]]
    a[0]+=sum(s['hs'] for s in sn.values()); a[1]+=len(sn)
    a[2]+=sum(1 for s in sn.values() if s['hs']>0)
for f,(t,n,e) in sorted(agg2.items(), key=lambda x:-x[1][0]/max(x[1][1],1)):
    print(f"{f:22s} {n:4d} {t:6d} {t/n:6.2f} {e/n*100:5.0f}%")
