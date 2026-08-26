import openpyxl,io,collections,statistics as st,core,json
KW=core.KW; EXCL=core.EXCL_BRAND
EXCL_DOM={'5374.team','2535.team'}
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
wb=openpyxl.load_workbook(io.BytesIO(open('launches17.xlsx','rb').read()),data_only=True)
SH={'NEW33_12pages_nodate_25.08 (8)':('A · 12 стр без дат','чужой'),
    'NEW33_12pages_withdate_25.08 (8':('A · 12 стр + даты','чужой'),
    'Generator_11page_NOimg_25.08 (1':('B · без картинок','наш'),
    'Generator_11page_img_25.08 (5)':('B · с картинками','наш'),
    'NEW50_5_7pages_nodate_21.08 (11':('Контроль (контент 21.08)','чужой'),
    'Старые аккаунты (nabor-149…153)':('D · наборы, старые акк.','наборы'),
    'Новые аккаунты (nabor-144…148)':('D · наборы, новые акк.','наборы')}
# общий срез ядра — минимальная покрытая длина по всем листам
PREFIX=948
DOM={}
for sn,(g,aut) in SH.items():
    ws=wb[sn]; rows=list(ws.iter_rows(values_only=True))
    allh=[i for i,r in enumerate(rows) if r[0] and isinstance(r[0],str) and r[0].strip().startswith('Ключ \\')]
    snaps=[h for h in allh if 'Снимок' in str(rows[h-1][0])]
    labs=[str(rows[h-1][0]).replace('Снимок ','').replace(' XML','') for h in snaps]
    hdr=[str(c).strip().lower() for c in rows[snaps[0]][1:] if c not in (None,'')]
    for d in hdr:
        if d in EXCL_DOM: continue
        DOM[d]={'g':g,'aut':aut,'z':'.'+d.split('.')[-1],'s':[[] for _ in snaps],'labs':labs}
    for j,h in enumerate(snaps):
        nxt=[i for i in allh if i>h]; end=(nxt[0]-1) if nxt else len(rows)
        body=[r for r in rows[h+1:end] if isinstance(r[0],str) and r[0].strip().lower()!='ключ']
        for r in body[:PREFIX]:
            q=r[0].strip().lower(); m=KW.get(q)
            if not m: continue
            br,vol,_=m
            if br in EXCL: continue
            for i,d in enumerate(hdr):
                if d in EXCL_DOM: continue
                try: p=int(r[1+i])
                except: continue
                if 1<=p<=100: DOM[d]['s'][j].append((p,br,vol,tier(vol),q))
def m(k,t): return sum(1 for x in k if x[0]<=t)
def stat(ds,nm,j):
    ks=[DOM[d]['s'][j] for d in ds]; n=len(ds)
    v=sorted((m(k,10) for k in ks),reverse=True)
    hs=sum(1 for k in ks for x in k if x[0]<=10 and x[3] in('ВЧ','СЧ'))
    return dict(n=n,mean=sum(v)/n,med=st.median(v),wo=sum(v[1:])/(n-1) if n>1 else 0,
      t3=sum(m(k,3) for k in ks),t30=sum(m(k,30) for k in ks),t100=sum(len(k) for k in ks),hs=hs,v=v)
tm=lambda g:[d for d,x in DOM.items() if x['g']==g and x['z']=='.team']
print('СРЕЗ ПО ОБЩЕЙ ЧАСТИ ЯДРА — первые %d ключей из 1570'%PREFIX)
print('(второй съём обрезан: данные только по первым 60-70%% ядра)\n')
print('%-26s %4s | %-28s | %-28s'%('ветка','дом','съём 1','съём 2'))
print('%-26s %4s | %7s %5s %6s %6s | %7s %5s %6s %6s'%('','','Т10/дом','мед','б/лид','ВЧ+СЧ','Т10/дом','мед','б/лид','ВЧ+СЧ'))
ORD=['Контроль (контент 21.08)','A · 12 стр без дат','A · 12 стр + даты','B · без картинок','B · с картинками','D · наборы, старые акк.','D · наборы, новые акк.']
R={}
for g in ORD:
    ds=tm(g)
    a=stat(ds,g,0); b=stat(ds,g,1); R[g]=(a,b)
    print('%-26s %4d | %7.2f %5.1f %6.2f %6d | %7.2f %5.1f %6.2f %6d'%(g,a['n'],
        a['mean'],a['med'],a['wo'],a['hs'],b['mean'],b['med'],b['wo'],b['hs']))
print()
for g in ORD:
    a,b=R[g]; print('  %-26s значения: %s  →  %s'%(g,a['v'],b['v']))
json.dump({d:{'g':v['g'],'aut':v['aut'],'z':v['z'],
  'tr':[m(k,10) for k in v['s']],'tr30':[m(k,30) for k in v['s']],'tr100':[len(k) for k in v['s']],
  't3':[m(k,3) for k in v['s']],'hs':[sum(1 for x in k if x[0]<=10 and x[3] in('ВЧ','СЧ')) for k in v['s']],
  'labs':v['labs'],'keys':[[list(x) for x in k] for k in v['s']]} for d,v in DOM.items()},
  open('d4.json','w',encoding='utf-8'),ensure_ascii=False)
