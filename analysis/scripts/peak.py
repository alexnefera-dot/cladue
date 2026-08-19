import pickle, collections, statistics
traj=pickle.load(open("traj.pkl","rb"))
drop=[]; grow=[]; flat=[]
for k,sns in traj.items():
    if len(sns)<3: continue
    doms=set(sns[-1])
    for d in doms:
        series=[s.get(d,{}).get('t30',0) for s in sns]
        if len(series)<3: continue
        pk=max(series); pi=series.index(pk)
        fin=sns[-1][d]['hs']
        if pk==0: flat.append(fin); continue
        if pi<len(series)-1 and series[-1] < pk*0.8: drop.append((k,d,pk,series[-1],fin))
        elif series[-1]>=pk*0.95: grow.append((k,d,pk,series[-1],fin))
print("=== 'ПРОСЕЛ ПОСЛЕ ПИКА' (Т30 финал < 80% пика) ===")
print(f"n={len(drop)}, медиана финала ВЧ+СЧ = {statistics.median([x[4] for x in drop]):.1f}, "
      f"среднее = {statistics.mean([x[4] for x in drop]):.2f}, с результатом: "
      f"{sum(1 for x in drop if x[4]>0)/len(drop)*100:.0f}%")
print("=== 'РАСТЁТ ДО КОНЦА' (финал >= 95% пика) ===")
print(f"n={len(grow)}, медиана финала = {statistics.median([x[4] for x in grow]):.1f}, "
      f"среднее = {statistics.mean([x[4] for x in grow]):.2f}, с результатом: "
      f"{sum(1 for x in grow if x[4]>0)/len(grow)*100:.0f}%")
print("\nпросевшие домены с ненулевым финалом:")
for x in sorted([y for y in drop if y[4]>0], key=lambda y:-y[4])[:10]:
    print(f"  {x[0]:6s} {x[1]:20s} пик Т30={x[2]:4d} финал Т30={x[3]:4d} ВЧ+СЧ={x[4]}")

print("\n=== ДОЛЯ 'РАСТЁТ ДО КОНЦА' ПО ЗАПУСКАМ ===")
print(f"{'запуск':7s} {'n':>3s} {'растёт':>7s} {'просел':>7s} {'финал/дом':>10s}")
for k,sns in sorted(traj.items()):
    if len(sns)<3 or len(sns[-1])<7: continue
    g=d0=0
    for dd in sns[-1]:
        s=[x.get(dd,{}).get('t30',0) for x in sns]
        pk=max(s)
        if pk==0: continue
        if s[-1]>=pk*0.95: g+=1
        elif s[-1]<pk*0.8: d0+=1
    n=len(sns[-1]); fin=sum(x['hs'] for x in sns[-1].values())/n
    print(f"{k:7s} {n:3d} {g/n*100:6.0f}% {d0/n*100:6.0f}% {fin:10.2f}")
