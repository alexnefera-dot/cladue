import pickle, collections, statistics, re
from core import EXCL_DOM, EXCL_BRAND
import core
allm=pickle.load(open("meas.pkl","rb")); KW=core.KW; BR=core.B["brands"]
vol={b:v for b,v in BR.values()}
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
st=collections.defaultdict(lambda: {"t3":0,"t10":0,"t30":0,"doms":set(),"best":999})
for f,meas in allm.items():
    if not meas: continue
    _,data=meas[-1]
    for dom,kws in data.items():
        if dom in EXCL_DOM: continue
        for q,pos in kws.items():
            m=KW.get(q)
            if not m: continue
            b,v,_=m
            if b in EXCL_BRAND: continue
            s=st[b]
            if pos<=3: s["t3"]+=1
            if pos<=10: s["t10"]+=1; s["doms"].add(dom)
            if pos<=30: s["t30"]+=1
            s["best"]=min(s["best"],pos)
rows=[(b,vol.get(b,0),s["t3"],s["t10"],s["t30"],len(s["doms"]),s["best"]) for b,s in st.items()]
print("=== ВЧ/СЧ БРЕНДЫ, взятые лучше всего (по числу ключей в Т10) ===")
print(f"{'бренд':18s} {'объём':>10s} {'тир':>3s} {'Т3':>4s} {'Т10':>5s} {'Т30':>5s} {'дом':>4s} {'лучш':>5s}")
for r in sorted([x for x in rows if x[1]>=700_000], key=lambda x:-x[3])[:25]:
    print(f"{r[0]:18s} {r[1]:10,.0f} {tier(r[1]):>3s} {r[2]:4d} {r[3]:5d} {r[4]:5d} {r[5]:4d} {r[6]:5d}")

print("\n=== ЗАВИСИМОСТЬ ОТ ОБЪЁМА БРЕНДА (все ВЧ/СЧ бренды) ===")
buckets=[(700_000,1e6,"700k-1M (СЧ)"),(1e6,2e6,"1-2M"),(2e6,5e6,"2-5M"),(5e6,1e7,"5-10M"),(1e7,1e9,">10M")]
print(f"{'диапазон':14s} {'брендов':>8s} {'взято':>6s} {'Т10 ключей':>11s} {'Т10/бренд':>10s}")
for lo,hi,name in buckets:
    bs=[b for b,v in vol.items() if lo<=v<hi]
    taken=[b for b in bs if st.get(b,{}).get("t10",0)>0]
    tot=sum(st.get(b,{}).get("t10",0) for b in bs)
    if bs: print(f"{name:14s} {len(bs):8d} {len(taken)/len(bs)*100:5.0f}% {tot:11d} {tot/len(bs):10.1f}")
