import io,openpyxl,statistics as st,core
KW=core.KW; EXCL=core.EXCL_BRAND
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
wb=openpyxl.load_workbook(io.BytesIO(open('launches11.xlsx','rb').read()),data_only=True)
SH={'NEW50_5_12pages_withdate_21.08':'12 стр + даты','NEW50_5_7pages_withdate_21.08':'7 стр + даты',
    'Generator_11page_img_22.08_5':'11 стр + картинки','NEW50_5_12pages_nodate_21.08':'12 стр без дат',
    'NEW50_5_7pages_nodate_21.08':'7 стр без дат'}
for sn,nm in SH.items():
    ws=wb[sn]; rows=list(ws.iter_rows(values_only=True))
    idx=[i for i,r in enumerate(rows) if r[0] and isinstance(r[0],str) and r[0].startswith('Ключ')]
    ids=[i for i in idx if rows[i-1][0] and 'Снимок' in str(rows[i-1][0])]
    blocks=[]
    for h in ids:
        nxt=[i for i in idx if i>h]
        end=(nxt[0]-1) if nxt else len(rows)
        hdr=[str(c).strip().lower() for c in rows[h][1:] if c not in (None,'') and str(c).strip().lower()!='базовый домен']
        blocks.append((str(rows[h-1][0]).replace('Снимок ','').replace(' XML',''),hdr,rows[h+1:end]))
    lbl,hdr,body=blocks[-1]
    last=max(i for i,r in enumerate(body) if any(v is not None for v in r[1:1+len(hdr)]))
    keys=set()
    for r in body[:last+1]:
        q=r[0]
        if isinstance(q,str) and q.strip(): keys.add(q.strip().lower())
    print('===',nm,'| срез: первые %d строк ядра (%d ключей)'%(last+1,len(keys)))
    for lb,hd,bd in blocks[-2:]:
        per={d:[] for d in hd}
        for r in bd:
            q=r[0]
            if not isinstance(q,str): continue
            q=q.strip().lower()
            if q not in keys: continue
            m=KW.get(q)
            if not m: continue
            br,vol,_=m
            if br in EXCL: continue
            for i,d in enumerate(hd):
                v=r[1+i]
                try: p=int(v)
                except: continue
                if 1<=p<=100: per[d].append((p,tier(vol)))
        tm=[d for d in hd if d.endswith('.team')]
        t10={d:sum(1 for p,t in per[d] if p<=10) for d in hd}
        t3=sum(1 for d in hd for p,t in per[d] if p<=3)
        hs=sum(1 for d in hd for p,t in per[d] if p<=10 and t in ('ВЧ','СЧ'))
        vals=sorted((t10[d] for d in tm),reverse=True)
        mean=sum(vals)/len(vals) if vals else 0
        wo=sum(vals[1:])/len(vals[1:]) if len(vals)>1 else 0
        print('   %-12s Т10/дом(.team) %5.1f | значения %-22s | мед %4.1f | б/лид %5.2f | ВЧ+СЧ %3d | Т3 %3d | всего Т10 %d'%(
            lb,mean,str(vals),st.median(vals) if vals else 0,wo,hs,t3,sum(t10.values())))
