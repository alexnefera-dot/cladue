import pickle, statistics, collections
traj=pickle.load(open("traj.pkl","rb"))
rows=[]
for k,sns in traj.items():
    if len(sns)<3 or len(sns[-1])<7: continue
    m1=sns[0]; fin=sns[-1]
    if not m1: continue
    rows.append((k, sum(s['t30'] for s in m1.values())/len(m1),
                 sum(s['hs'] for s in m1.values())/len(m1),
                 sum(s['hs'] for s in fin.values())/len(fin), len(fin)))
rows.sort(key=lambda r:-r[1])
print("АРХИВ: Т30/дом на ЗАМЕРЕ 1 → финал")
print(f"{'запуск':7s} {'n':>3s} {'Т30/дом@1':>9s} {'ВЧ+СЧ/дом@1':>11s} {'финал':>7s}")
for k,t,h,f,n in rows: print(f"{k:7s} {n:3d} {t:9.1f} {h:11.2f} {f:7.2f}")
def corr(xs,ys):
    mx,my=statistics.mean(xs),statistics.mean(ys)
    a=sum((p-mx)*(q-my) for p,q in zip(xs,ys))
    b=(sum((p-mx)**2 for p in xs)*sum((q-my)**2 for q in ys))**.5
    return a/b if b else 0
print(f"\nкорреляция Т30/дом@1 -> финал: {corr([r[1] for r in rows],[r[3] for r in rows]):.3f}")
print(f"корреляция ВЧ+СЧ/дом@1 -> финал: {corr([r[2] for r in rows],[r[3] for r in rows]):.3f}")
med=statistics.median([r[1] for r in rows])
print(f"медиана Т30/дом@1 по архиву: {med:.1f}")
succ=[r for r in rows if r[3]>=2]; fail=[r for r in rows if r[3]<0.5]
print(f"успешные (финал>=2): n={len(succ)} медиана Т30@1={statistics.median([r[1] for r in succ]):.1f} "
      f"диапазон {min(r[1] for r in succ):.1f}-{max(r[1] for r in succ):.1f}")
print(f"провальные (финал<0.5): n={len(fail)} медиана Т30@1={statistics.median([r[1] for r in fail]):.1f} "
      f"диапазон {min(r[1] for r in fail):.1f}-{max(r[1] for r in fail):.1f}")

# domain-level: t30@1 vs final
pairs=[]
for k,sns in traj.items():
    if len(sns)<3: continue
    m1,fin=sns[0],sns[-1]
    for d in fin:
        if d in m1: pairs.append((m1[d]['t30'], fin[d]['hs']))
print(f"\nдомены n={len(pairs)}, корреляция Т30@1 -> финал: {corr([p[0] for p in pairs],[p[1] for p in pairs]):.3f}")
for lo,hi in [(0,0),(1,4),(5,14),(15,39),(40,10**6)]:
    g=[p for p in pairs if lo<=p[0]<=hi]
    if g: print(f"  Т30@1 {lo}-{hi if hi<10**6 else '+':>3}: n={len(g):3d} "
                f"дошли до результата {sum(1 for p in g if p[1]>0)/len(g)*100:3.0f}%  "
                f"медиана финала {statistics.median([p[1] for p in g]):.1f}")
