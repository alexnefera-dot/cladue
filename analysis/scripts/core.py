import io, openpyxl, pickle, hashlib, os, collections
D="data/Dorgen test/"
B=pickle.load(open("brands.pkl","rb")); KW=B["kw2brand"]
EXCL_DOM={"5936.team","cvnp.team","jvbs.team","zbrn.team","vmqk.team",
          "casino28w.team","casino51m.team","kdnb.team"}
EXCL_BRAND={"vovan","pari"}
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
def load(p): return openpyxl.load_workbook(io.BytesIO(open(D+p,'rb').read()), data_only=True)

def sheet_table(ws):
    rows=list(ws.iter_rows(values_only=True))
    if not rows: return None
    hdr=rows[0]
    doms=[str(c).strip().lower() for c in hdr[1:] if c not in (None,'')]
    data={}; n=0
    for r in rows[1:]:
        q=r[0]
        if q in (None,''): continue
        q=str(q).strip().lower()
        for i,dom in enumerate(doms):
            v=r[1+i]
            if v in (None,'','—','-'): continue
            try: pos=int(v)
            except: continue
            if pos<1: continue
            data.setdefault(dom,{})[q]=pos; n+=1
    return (doms,data,n) if n else None

def fingerprint(data):
    h=hashlib.md5()
    for d in sorted(data):
        h.update(d.encode())
        for q in sorted(data[d]): h.update(f"{q}:{data[d][q]}".encode())
    return h.hexdigest()

def measurements(f):
    wb=load(f); meas=[]; seen=set()
    for sn in wb.sheetnames:
        t=sheet_table(wb[sn])
        if t is None: continue
        if fingerprint(t[1]) in seen: continue
        seen.add(fingerprint(t[1])); meas.append((sn,t[1]))
    return meas

TOPS=[3,10,30,50,100]
def score(data, use_excl=True):
    """data: dom -> {kw:pos}. returns dom -> {(tier,top):count}, plus brand sets"""
    res={}
    for dom,kws in data.items():
        if use_excl and dom in EXCL_DOM: continue
        c=collections.Counter(); brands=collections.defaultdict(set)
        for q,pos in kws.items():
            m=KW.get(q)
            if not m: continue
            brand,vol,_=m
            if use_excl and brand in EXCL_BRAND: continue
            t=tier(vol)
            for tp in TOPS:
                if pos<=tp: c[(t,tp)]+=1
            if pos<=10: brands[t].add(brand)
        res[dom]={"c":c,"brands":{k:sorted(v) for k,v in brands.items()},"raw":len(kws)}
    return res

if __name__=="__main__":
    import sys, json
    files=sorted(f for f in os.listdir(D) if f.endswith('.xlsx') and not f.startswith('.')
                 and not f.startswith('enemies') and f not in
                 ('brands_master.xlsx','converstion.xlsx','our-list-brands.xlsx','motor.xlsx'))
    allm={}
    for f in files:
        allm[f]=measurements(f)
        print(f, len(allm[f]), flush=True)
    pickle.dump(allm, open("meas.pkl","wb"))
