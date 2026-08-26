import openpyxl,io,collections,statistics as st,core,json
KW=core.KW; EXCL=core.EXCL_BRAND; EXCL_DOM={'5374.team','2535.team'}
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
wb=openpyxl.load_workbook(io.BytesIO(open('launches19.xlsx','rb').read()),data_only=True)
SH=[('NEW33_12pages_nodate+img_25.08 ','ТЕСТ F · без дат','F','без дат','NEW33 · 12 стр · чужой контент + картинки','25.08 18:26-18:30'),
    ('NEW33_12pages_withdate+img_25.0','ТЕСТ F · с датами','F','с датами','NEW33 · 12 стр · чужой контент + картинки','25.08 18:30-18:31'),
    ('NEW17_NOimg_withdate_26.08','ТЕСТ E · без картинок','E','без картинок','NEW17 · чужой контент с датами','26.08 14:06'),
    ('NEW17_img_withdate_26.08','ТЕСТ E · с картинками','E','с картинками','NEW17 · чужой контент с датами','26.08 14:09-14:10'),
    ('КОНТРОЛЬ NEW50_5_7pages_nodate_','КОНТРОЛЬ','CTRL','контроль','7 стр без дат · прогон 21.08, третья дата','21.08 13:29'),
    ('Generator_A_staryy_stil (nabor-','ТЕСТ G · A','G','A · старый стиль','наш генератор · старый стиль','—'),
    ('Generator_A2_staryy_stil (nabor','ТЕСТ G · A2','G','A2 · старый стиль','наш генератор · старый стиль','—'),
    ('Generator_B_novyy_bez_img','ТЕСТ G · B','G','B · новый, без img','наш генератор · новый стиль','—'),
    ('Generator_B2_novyy_bez_img','ТЕСТ G · B2','G','B2 · новый, без img','наш генератор · новый стиль','—'),
    ('Generator_C_novyy_img','ТЕСТ G · C','G','C · новый + img','наш генератор · новый стиль + картинки','—'),
    ('Generator_C2_novyy_img','ТЕСТ G · C2','G','C2 · новый + img','наш генератор · новый стиль + картинки','—')]
out=[]
for sn,name,test,arm,cfg,made in SH:
    ws=wb[sn]; rows=list(ws.iter_rows(values_only=True))
    allh=[i for i,r in enumerate(rows) if r[0] and isinstance(r[0],str) and r[0].strip().startswith('Ключ \\')]
    allsn=[h for h in allh if 'Снимок' in str(rows[h-1][0])]
    hdr=[str(c).strip().lower() for c in rows[allsn[0]][1:] if c not in (None,'')]
    h=allsn[0]; nxt=[i for i in allh if i>h]; end=(nxt[0]-1) if nxt else len(rows)
    b=[r for r in rows[h+1:end] if isinstance(r[0],str) and r[0].strip().lower()!='ключ']
    q=len(b)//4
    quart=[sum(1 for r in b[i*q:(i+1)*q] if any(v is not None for v in r[1:1+len(hdr)])) for i in range(4)]
    lab=str(rows[h-1][0]).replace('Снимок ','').replace(' XML','')
    per={d:[] for d in hdr}
    for r in b:
        qq=r[0].strip().lower(); mm=KW.get(qq)
        if not mm: continue
        br,vol,_=mm
        if br in EXCL: continue
        for i,d in enumerate(hdr):
            try: p=int(r[1+i])
            except: continue
            if 1<=p<=100: per[d].append({'p':p,'b':br,'t':tier(vol),'q':qq,'v':vol})
    ds=[d for d in hdr if d not in EXCL_DOM and d.endswith('.team')]
    v=sorted((sum(1 for x in per[d] if x['p']<=10) for d in ds),reverse=True); n=max(len(ds),1)
    doms=[]
    for d in hdr:
        ks=per[d]
        top=sorted([x for x in ks if x['p']<=10],key=lambda x:(x['p'],-x['v']))[:12]
        doms.append({'d':d,'tm':d.endswith('.team'),'t3':sum(1 for x in ks if x['p']<=3),
          't10':sum(1 for x in ks if x['p']<=10),'t30':sum(1 for x in ks if x['p']<=30),'t100':len(ks),
          'vch':sum(1 for x in ks if x['p']<=10 and x['t']=='ВЧ'),'sch':sum(1 for x in ks if x['p']<=10 and x['t']=='СЧ'),
          'nb':len({x['b'] for x in ks}),
          'keys':[{'q':x['q'],'p':x['p'],'b':x['b'],'t':x['t']} for x in top]})
    doms.sort(key=lambda x:(-x['t10'],-x['t30']))
    bc=collections.Counter()
    for d in ds:
        for x in per[d]:
            if x['p']<=10: bc[x['b']]+=1
    out.append(dict(name=name,test=test,arm=arm,cfg=cfg,made=made,sheet=sn.strip(),lab=lab,
      quart=quart,tot=sum(quart),corelen=len(b),ndom=len(hdr),ntm=len(ds),
      mean=round(sum(v)/n,3),med=st.median(v) if v else 0,wo=round((sum(v[1:])/(n-1)) if n>1 else 0,3),vals=v,
      t3=sum(sum(1 for x in per[d] if x['p']<=3) for d in ds),
      t30=sum(sum(1 for x in per[d] if x['p']<=30) for d in ds),
      t100=sum(len(per[d]) for d in ds),
      vch=sum(1 for d in ds for x in per[d] if x['p']<=10 and x['t']=='ВЧ'),
      sch=sum(1 for d in ds for x in per[d] if x['p']<=10 and x['t']=='СЧ'),
      nbrands=len(bc),topb=bc.most_common(10),doms=doms))
json.dump({'g':out,'excl':sorted(EXCL_DOM),'file':'launches_20260827_001030.xlsx'},open('n2.json','w'),ensure_ascii=False)
print('ok',len(out))
for r in out: print(f"{r['name'][:22]:24s} {r['lab']} n={r['ntm']} mean={r['mean']:.2f} wo={r['wo']:.2f} t3={r['t3']} t30={r['t30']} вч+сч={r['vch']+r['sch']} четверти={r['quart']}")
