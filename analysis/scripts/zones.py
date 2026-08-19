import pickle, collections, statistics
traj=pickle.load(open("traj.pkl","rb"))
FMT={"D273":"12page+даты","D274":"7page+даты","D265":"12page бренд","D266":"12page бренд",
     "D267":"12page бренд","D262":"7page бренд","D268":"7page бренд","D248":"nu 6page",
     "D249":"nu 6page","D252":"nu 6page","D253":"nu 6page","D255":"переисп.",
     "D258":"именованные","D269":"предметные","D261":"ген .casino"}
print("=== ПРОГНОЗ ЗАПУСКА ПО Т30 НА ЗАМЕРЕ 2 ===")
print(f"{'Запуск':7s} {'формат':16s} {'n':>3s} {'Т30/дом@2':>9s} {'ВЧ+СЧ/дом@2':>11s} {'финал':>7s}")
rows=[]
for k,sns in sorted(traj.items()):
    if len(sns)<3: continue
    m2,fin=sns[1],sns[-1]
    if len(m2)<7: continue
    t30=sum(s['t30'] for s in m2.values())/len(m2)
    h2=sum(s['hs'] for s in m2.values())/len(m2)
    hf=sum(s['hs'] for s in fin.values())/len(fin)
    rows.append((k,t30,h2,hf))
rows.sort(key=lambda r:-r[3])
for k,t30,h2,hf in rows:
    print(f"{k:7s} {FMT.get(k,''):16s} {len(traj[k][-1]):3d} {t30:9.1f} {h2:11.2f} {hf:7.2f}")
def corr(xs,ys):
    mx,my=statistics.mean(xs),statistics.mean(ys)
    n=sum((a-mx)*(b-my) for a,b in zip(xs,ys))
    d=(sum((a-mx)**2 for a in xs)*sum((b-my)**2 for b in ys))**.5
    return n/d if d else 0
print(f"\nкорреляция Т30/дом@2 -> финал:      {corr([r[1] for r in rows],[r[3] for r in rows]):.3f}")
print(f"корреляция ВЧ+СЧ/дом@2 -> финал:   {corr([r[2] for r in rows],[r[3] for r in rows]):.3f}")

print("\n=== ЗОНЫ (все домены, последний замер каждого запуска) ===")
z=collections.defaultdict(lambda:[0,0,0,0])
for k,sns in traj.items():
    if not sns: continue
    for dom,s in sns[-1].items():
        zone="."+dom.rsplit(".",1)[-1]
        a=z[zone]; a[0]+=1; a[1]+=s['hs']; a[2]+= (1 if s['hs']>0 else 0); a[3]+=s['t30']
print(f"{'зона':10s} {'дом':>4s} {'ВЧ+СЧ':>6s} {'/дом':>6s} {'зашло':>6s} {'Т30/дом':>8s}")
for zn,(n,h,e,t) in sorted(z.items(), key=lambda x:-x[1][0]):
    if n<3: continue
    print(f"{zn:10s} {n:4d} {h:6d} {h/n:6.2f} {e/n*100:5.0f}% {t/n:8.1f}")
print("\nредкие зоны (<3 доменов):", {k:v[0] for k,v in z.items() if v[0]<3})
