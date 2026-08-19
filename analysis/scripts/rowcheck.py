import io, openpyxl, os, re, hashlib
D="data/Dorgen test/"
def load(p): return openpyxl.load_workbook(io.BytesIO(open(D+p,'rb').read()), data_only=True)
files=sorted(f for f in os.listdir(D) if f.endswith('.xlsx') and not f.startswith('.')
             and not f.startswith('enemies') and f not in
             ('brands_master.xlsx','converstion.xlsx','our-list-brands.xlsx','motor.xlsx'))
print("файлы с листами неполного размера (ядро = 1570 ключей):")
for f in files:
    wb=load(f); info=[]
    for sn in wb.sheetnames:
        ws=wb[sn]
        nk=sum(1 for r in ws.iter_rows(min_row=2,max_col=1,values_only=True) if r[0] not in (None,''))
        info.append((sn,nk))
    if any(k<1500 for _,k in info):
        print(f"  {f:20s}", ", ".join(f"{s}={k}" for s,k in info))
