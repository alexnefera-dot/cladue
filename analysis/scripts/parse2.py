import io, openpyxl, hashlib, pickle, collections
import core
KW=core.KW; EXCL_BRAND=core.EXCL_BRAND
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")

def blocks(ws):
    rows=list(ws.iter_rows(values_only=True))
    idx=[i for i,r in enumerate(rows) if r[0] and isinstance(r[0],str) and r[0].startswith('Ключ')]
    out=[]
    for j,h in enumerate(idx):
        end=idx[j+1]-1 if j+1<len(idx) else len(rows)
        # snapshot label sits just above the header, if present
        lbl=None
        if h>0 and rows[h-1][0] and isinstance(rows[h-1][0],str) and 'Снимок' in rows[h-1][0]:
            lbl=rows[h-1][0]
        doms=[str(c).strip().lower() for c in rows[h][1:] if c not in (None,'')]
        data={d:{} for d in doms}
        for r in rows[h+1:end]:
            q=r[0]
            if q in (None,'') or (isinstance(q,str) and ('Снимок' in q or q.startswith('Ключ'))): continue
            q=str(q).strip().lower()
            for i,d in enumerate(doms):
                v=r[1+i]
                if v is None: continue
                try: p=int(v)
                except: continue
                if p>=1: data[d][q]=p
        fp=hashlib.md5(repr(sorted((d,sorted(v.items())) for d,v in data.items())).encode()).hexdigest()
        out.append({"label":lbl,"doms":doms,"data":data,"fp":fp,
                    "npos":sum(len(v) for v in data.values())})
    return out

wb=openpyxl.load_workbook(io.BytesIO(open("launches2.xlsx",'rb').read()), data_only=True)
snaps={}
for sn in wb.sheetnames[1:]:
    bs=blocks(wb[sn])
    seen={}; keep=[]
    for b in bs:
        if b["fp"] in seen:
            print(f"  {sn}: блок '{b['label'] or 'без метки'}' дублирует '{seen[b['fp']]}' — пропущен")
            continue
        seen[b["fp"]]=b["label"] or "без метки"; keep.append(b)
    snaps[sn]=keep
    print(f"{sn}: блоков={len(bs)} уникальных={len(keep)} " +
          " | ".join(f"{b['label'] or 'без метки'}: {b['npos']} позиций" for b in keep))
pickle.dump(snaps, open("snaps2.pkl","wb"))
