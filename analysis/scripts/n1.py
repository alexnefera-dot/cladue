import openpyxl,io,collections,statistics as st,core,json
KW=core.KW; EXCL=core.EXCL_BRAND; EXCL_DOM={'5374.team','2535.team'}
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
wb=openpyxl.load_workbook(io.BytesIO(open('launches19.xlsx','rb').read()),data_only=True)
SH=[('NEW33_12pages_nodate+img_25.08 ','ТЕСТ F · без дат + img','F','без дат'),
    ('NEW33_12pages_withdate+img_25.0','ТЕСТ F · с датами + img','F','с датами'),
    ('NEW17_NOimg_withdate_26.08','ТЕСТ E · без картинок','E','без картинок'),
    ('NEW17_img_withdate_26.08','ТЕСТ E · с картинками','E','с картинками'),
    ('КОНТРОЛЬ NEW50_5_7pages_nodate_','КОНТРОЛЬ 26.08','CTRL','контроль'),
    ('Generator_A_staryy_stil (nabor-','ТЕСТ G · A старый стиль','G','A'),
    ('Generator_A2_staryy_stil (nabor','ТЕСТ G · A2 старый стиль','G','A2'),
    ('Generator_B_novyy_bez_img','ТЕСТ G · B новый без img','G','B'),
    ('Generator_B2_novyy_bez_img','ТЕСТ G · B2 новый без img','G','B2'),
    ('Generator_C_novyy_img','ТЕСТ G · C новый + img','G','C'),
    ('Generator_C2_novyy_img','ТЕСТ G · C2 новый + img','G','C2')]
out=[]
for sn,name,test,arm in SH:
    ws=wb[sn]; rows=list(ws.iter_rows(values_only=True))
    allh=[i for i,r in enumerate(rows) if r[0] and isinstance(r[0],str) and r[0].strip().startswith('Ключ \\')]
    allsn=[h for h in allh if 'Снимок' in str(rows[h-1][0])]
    hdr=[str(c).strip().lower() for c in rows[allsn[0]][1:] if c not in (None,'')]
    def body(h):
        nxt=[i for i in allh if i>h]; end=(nxt[0]-1) if nxt else len(rows)
        return [r for r in rows[h+1:end] if isinstance(r[0],str) and r[0].strip().lower()!='ключ']
    h=allsn[0]; b=body(h)
    covi=max((i for i,r in enumerate(b) if any(v is not None for v in r[1:1+len(hdr)])),default=-1)+1
    lab=str(rows[h-1][0]).replace('Снимок ','').replace(' XML','')
    per={d:[] for d in hdr}
    for r in b:
        q=r[0].strip().lower(); mm=KW.get(q)
        if not mm: continue
        br,vol,_=mm
        if br in EXCL: continue
        for i,d in enumerate(hdr):
            try: p=int(r[1+i])
            except: continue
            if 1<=p<=100: per[d].append((p,tier(vol),br,q))
    ds=[d for d in hdr if d not in EXCL_DOM and d.endswith('.team')]
    ks={d:per[d] for d in ds}
    v=sorted((sum(1 for p,t,_,_ in ks[d] if p<=10) for d in ds),reverse=True)
    n=max(len(ds),1)
    rec=dict(name=name,test=test,arm=arm,sheet=sn.strip(),lab=lab,cov=covi,corelen=len(b),
      ndom=len(hdr),ntm=len(ds),nexcl=len([d for d in hdr if d in EXCL_DOM]),
      mean=sum(v)/n,med=st.median(v) if v else 0,wo=(sum(v[1:])/(n-1)) if n>1 else 0,vals=v,
      t3=sum(sum(1 for p,t,_,_ in ks[d] if p<=3) for d in ds),
      t30=sum(sum(1 for p,t,_,_ in ks[d] if p<=30) for d in ds),
      t100=sum(len(ks[d]) for d in ds),
      vch=sum(1 for d in ds for p,t,_,_ in ks[d] if p<=10 and t=='ВЧ'),
      sch=sum(1 for d in ds for p,t,_,_ in ks[d] if p<=10 and t=='СЧ'),
      doms=sorted([(d,sum(1 for p,t,_,_ in per[d] if p<=10),sum(1 for p,t,_,_ in per[d] if p<=3),len(per[d]),d.endswith('.team')) for d in hdr],key=lambda x:-x[1]),
      brands=len({br for d in ds for p,t,br,q in ks[d]}))
    out.append(rec)
json.dump(out,open('n1.json','w'),ensure_ascii=False)
print(f"{'ветка':26s} {'снимок':12s} {'покр':>10s} {'.team':>5s} {'сред':>6s} {'мед':>5s} {'безлид':>7s} {'Т3':>4s} {'Т30':>5s} {'Т100':>5s} {'ВЧ':>3s} {'СЧ':>3s}  значения")
for r in out:
    print(f"{r['name'][:25]:26s} {r['lab']:12s} {r['cov']}/{r['corelen']:>4d} {r['ntm']:5d} {r['mean']:6.2f} {r['med']:5.1f} {r['wo']:7.2f} {r['t3']:4d} {r['t30']:5d} {r['t100']:5d} {r['vch']:3d} {r['sch']:3d}  {r['vals']}")
