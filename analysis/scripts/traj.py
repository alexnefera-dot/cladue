import pickle, re, collections
from core import EXCL_DOM, EXCL_BRAND
import core
allm=pickle.load(open("meas.pkl","rb")); KW=core.KW
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
def lab(f): return "D"+re.search(r'(\d{3})', f.replace('dorgne247','dorgen248')).group(1)

def snap(data):
    """returns dom -> dict of counts"""
    out={}
    for dom,kws in data.items():
        if dom in EXCL_DOM: continue
        hs=0; t30=0; brands=set()
        for q,pos in kws.items():
            m=KW.get(q)
            if not m: continue
            brand,vol,_=m
            if brand in EXCL_BRAND: continue
            t=tier(vol)
            if pos<=10 and t in ("ВЧ","СЧ"): hs+=1; brands.add(brand)
            if pos<=30: t30+=1
        out[dom]={"hs":hs,"t30":t30,"brands":brands}
    return out

traj={}
for f,meas in allm.items():
    traj[lab(f)]=[snap(d) for _,d in meas]
pickle.dump(traj, open("traj.pkl","wb"))

print("ВЧ+СЧ в ТОП-10 на домен, по номеру замера (n доменов в скобках)")
print(f"{'Запуск':7s} {'n':>3s} " + " ".join(f"{'з'+str(i+1):>7s}" for i in range(9)))
order=sorted(traj, key=lambda k:-max((sum(s['hs'] for s in sn.values())/max(len(sn),1)) for sn in traj[k]) if traj[k] else 0)
for k in order:
    sns=traj[k]
    if not sns: continue
    n=len(sns[-1])
    cells=[]
    for i in range(9):
        if i<len(sns):
            m=sns[i]; cells.append(f"{sum(s['hs'] for s in m.values())/max(len(m),1):7.2f}")
        else: cells.append(f"{'':>7s}")
    print(f"{k:7s} {n:3d} " + " ".join(cells))
