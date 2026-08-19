import io, openpyxl, pickle, collections
D="data/Dorgen test/"
def load(p):
    return openpyxl.load_workbook(io.BytesIO(open(D+p,'rb').read()), data_only=True)

wb=load("brands_master.xlsx")
sv=wb["Сводка"]
brands={}   # sheet -> (brand, volume)
for r in sv.iter_rows(min_row=3, values_only=True):
    if r[0] is None: continue
    brand, sheet, vol = r[0], r[1], r[4]
    if sheet is None: continue
    brands[sheet]=(str(brand).strip(), float(vol or 0))
print("brands in Сводка:", len(brands))

kw2brand={}
dupes=collections.Counter()
for sheet,(brand,vol) in brands.items():
    if sheet not in wb.sheetnames:
        print("MISSING SHEET:", sheet); continue
    ws=wb[sheet]
    for row in ws.iter_rows(min_row=2, max_col=2, values_only=True):
        q=row[0]
        if q is None: continue
        q=str(q).strip().lower()
        if q in kw2brand and kw2brand[q][0]!=brand:
            dupes[(kw2brand[q][0],brand)]+=1
            # keep higher-volume brand
            if vol<=kw2brand[q][1]: continue
        kw2brand[q]=(brand,vol,float(row[1] or 0))
print("unique keywords mapped:", len(kw2brand))
print("cross-brand dupe pairs:", len(dupes), "total collisions:", sum(dupes.values()))
for k,v in dupes.most_common(10): print("  ",k,v)

def tier(vol):
    if vol>=1_000_000: return "ВЧ"
    if vol>=700_000: return "СЧ"
    return "НЧ"
tc=collections.Counter(tier(v[1]) for v in kw2brand.values())
print("keywords by tier:", dict(tc))
bt=collections.Counter(tier(v) for b,v in brands.values())
print("brands by tier:", dict(bt))
pickle.dump({"kw2brand":kw2brand,"brands":brands}, open("brands.pkl","wb"))
