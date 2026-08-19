import pickle, collections, statistics
traj=pickle.load(open("traj.pkl","rb"))
pairs=[]  # (launch, dom, t30@2, hs@2, hs_final, n_meas)
for k,sns in traj.items():
    if len(sns)<3: continue
    m2=sns[1]; fin=sns[-1]
    for dom in fin:
        if dom not in m2: continue
        pairs.append((k,dom,m2[dom]['t30'],m2[dom]['hs'],fin[dom]['hs']))
print("выборка доменов (запуски с >=3 замерами):", len(pairs))

def corr(xs,ys):
    mx,my=statistics.mean(xs),statistics.mean(ys)
    num=sum((a-mx)*(b-my) for a,b in zip(xs,ys))
    den=(sum((a-mx)**2 for a in xs)*sum((b-my)**2 for b in ys))**.5
    return num/den if den else 0
print("корреляция T30@замер2 -> ВЧ+СЧ финал:", round(corr([p[2] for p in pairs],[p[4] for p in pairs]),3))

low=[p for p in pairs if p[2]<=2]
print(f"\n<=2 ключа в Т30 на замере 2: n={len(low)}, остались в нуле: "
      f"{sum(1 for p in low if p[4]==0)/len(low)*100:.0f}%")
hi=[p for p in pairs if p[3]>0]
print(f"есть ВЧ/СЧ в Т10 на замере 2: n={len(hi)}, дошли до результата: "
      f"{sum(1 for p in hi if p[4]>0)/len(hi)*100:.0f}%")
zero=[p for p in pairs if p[3]==0]
print(f"ноль ВЧ/СЧ на замере 2:      n={len(zero)}, остались в нуле: "
      f"{sum(1 for p in zero if p[4]==0)/len(zero)*100:.0f}%, "
      f"выстрелили позже: {sum(1 for p in zero if p[4]>0)/len(zero)*100:.0f}%")

print("\n--- ЧТО БЫ ОТСЕВ УБИЛ: домены с <=2 Т30 на замере 2, но с результатом в финале ---")
sur=[p for p in low if p[4]>0]
sur.sort(key=lambda p:-p[4])
print(f"таких {len(sur)} из {len(low)} ({len(sur)/len(low)*100:.0f}%)")
for p in sur[:15]: print(f"  {p[0]:6s} {p[1]:16s} T30@2={p[2]}  финал ВЧ+СЧ={p[4]}")

print("\n--- D273 на замере 2 ---")
m2=traj['D273'][1]; fin=traj['D273'][-1]
for dom in sorted(fin, key=lambda d:-fin[d]['hs']):
    print(f"  {dom:14s} T30@2={m2.get(dom,{}).get('t30',0):3d} ВЧ+СЧ@2={m2.get(dom,{}).get('hs',0):3d}"
          f"  ->  финал T30={fin[dom]['t30']:4d} ВЧ+СЧ={fin[dom]['hs']:3d}")
