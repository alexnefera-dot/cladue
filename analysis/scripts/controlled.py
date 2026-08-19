import pickle, collections, statistics
P=pickle.load(open("perdom.pkl","rb")); per=P["per"]; DL=P["dom_launch"]
def hs(d): return per[d]["ВЧ10"]+per[d]["СЧ10"]

def within(pred, name_a, name_b):
    """paired comparison inside each launch that contains both groups"""
    byL=collections.defaultdict(lambda:([],[]))
    for d in per:
        (byL[DL[d]][0] if pred(d) else byL[DL[d]][1]).append(hs(d))
    wins=draws=loss=0; rows=[]
    ta=tb=na=nb=0
    for L,(a,b) in sorted(byL.items()):
        if len(a)<2 or len(b)<2: continue
        ma,mb=statistics.mean(a),statistics.mean(b)
        ta+=sum(a); na+=len(a); tb+=sum(b); nb+=len(b)
        rows.append((L,len(a),ma,len(b),mb))
        if ma>mb: wins+=1
        elif ma<mb: loss+=1
        else: draws+=1
    print(f"\n=== {name_a} vs {name_b} (внутри запусков, где есть обе группы) ===")
    print(f"{'запуск':7s} {'n_'+name_a:>10s} {'ср':>6s} {'n_'+name_b:>10s} {'ср':>6s}")
    for L,la,ma,lb,mb in rows:
        print(f"{L:7s} {la:10d} {ma:6.2f} {lb:10d} {mb:6.2f}")
    if na and nb:
        print(f"ИТОГО   {na:10d} {ta/na:6.2f} {nb:10d} {tb/nb:6.2f}")
    print(f"запусков где {name_a} лучше: {wins}, хуже: {loss}, поровну: {draws}")

within(lambda d: d.endswith(".buzz"), "buzz", "team")
within(lambda d: "casino" in d.split(".")[0], "casino", "прочие")
within(lambda d: d.endswith(".casino"), ".casino", "прочие")

print("\n=== .buzz vs .team ТОЛЬКО внутри D249 (подробно) ===")
for d in sorted([x for x in per if DL[x]=="D249"], key=lambda x:-hs(x)):
    print(f"  {d:22s} {'buzz' if d.endswith('.buzz') else 'team':5s} ВЧ={per[d]['ВЧ10']:3d} СЧ={per[d]['СЧ10']:3d}")
