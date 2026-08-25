import openpyxl,io,collections,statistics as st,core,json
KW=core.KW; EXCL=core.EXCL_BRAND
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
wb=openpyxl.load_workbook(io.BytesIO(open('launches14.xlsx','rb').read()),data_only=True)
SH={'NEW33_12pages_nodate_25.08 (8)':'A_nodate','NEW33_12pages_withdate_25.08 (8':'A_withdate',
    'Generator_11page_NOimg_25.08 (1':'B_noimg','Generator_11page_img_25.08 (5)':'B_img',
    'NEW50_5_7pages_nodate_21.08 (11':'CTRL'}
DOM={}
for sn,tag in SH.items():
    ws=wb[sn]; rows=list(ws.iter_rows(values_only=True))
    idx=[i for i,r in enumerate(rows) if r[0] and isinstance(r[0],str) and r[0].startswith('Ключ')]
    snaps=[i for i in idx if 'Снимок' in str(rows[i-1][0])]
    h=snaps[0]; nxt=[i for i in idx if i>h]; end=(nxt[0]-1) if nxt else len(rows)
    hdr=[str(c).strip().lower() for c in rows[h][1:] if c not in (None,'')]
    for d in hdr: DOM[d]={'t':tag,'z':'.'+d.split('.')[-1],'k':[]}
    for r in rows[h+1:end]:
        q=r[0]
        if not isinstance(q,str): continue
        m=KW.get(q.strip().lower())
        if not m: continue
        br,vol,_=m
        if br in EXCL: continue
        for i,d in enumerate(hdr):
            try: p=int(r[1+i])
            except: continue
            if 1<=p<=100: DOM[d]['k'].append((p,br,vol,tier(vol),q.strip().lower()))
def m(k,t): return sum(1 for p,*_ in k if p<=t)
def stat(ds,nm):
    ks=[DOM[d]['k'] for d in ds]; n=len(ds)
    v=sorted((m(k,10) for k in ks),reverse=True)
    hs=sum(sum(1 for p,b,vv,t,q in k if p<=10 and t in('ВЧ','СЧ')) for k in ks)
    print('%-26s n=%2d | Т10/дом %6.2f | мед %5.1f | б/лид %6.2f | Т3 %3d | Т30 %4d | Т100 %4d | ВЧ+СЧ %2d | пусто %d | %s'%(
        nm,n,sum(v)/n,st.median(v),sum(v[1:])/(n-1) if n>1 else 0,
        sum(m(k,3) for k in ks),sum(m(k,30) for k in ks),sum(len(k) for k in ks),hs,
        sum(1 for k in ks if not k),v))
tm=lambda t:[d for d,vv in DOM.items() if vv['t']==t and vv['z']=='.team']
print('СЪЁМ 25.08 23:21-23:22 · только .team\n')
print('--- ТЕСТ A: даты против без дат, 12 стр, чужой контент ---')
stat(tm('A_withdate'),'A · 12 стр + даты')
stat(tm('A_nodate'),'A · 12 стр без дат')
print()
print('--- ТЕСТ B день 2: картинки ---')
stat(tm('B_img'),'B · с картинками')
stat(tm('B_noimg'),'B · без картинок')
print()
print('--- КОНТРОЛЬ: контенты 21.08 на новых доменах ---')
stat(tm('CTRL'),'контроль 7 стр без дат')
print()
print('--- зоны .lol ---')
for t in ('B_noimg','CTRL'):
    ds=[d for d,vv in DOM.items() if vv['t']==t and vv['z']=='.lol']
    if ds: stat(ds,'%s .lol'%t)
print()
print('--- ВСЕ домены ---')
for d,v in sorted(DOM.items(),key=lambda x:-m(x[1]['k'],10)):
    k=v['k']; br=collections.Counter(b for p,b,vv,t,q in k if p<=10)
    hi=[(b,p,t) for p,b,vv,t,q in k if p<=10 and t in('ВЧ','СЧ')]
    print('  %-12s %-11s %-6s Т10 %3d Т30 %3d Т100 %3d Т3 %2d ВЧ+СЧ %2d | %s'%(d,v['t'],v['z'],
        m(k,10),m(k,30),len(k),m(k,3),len(hi),', '.join('%s'%b for b,_ in br.most_common(6))))
json.dump({d:{'t':v['t'],'z':v['z'],'k':[list(x) for x in v['k']]} for d,v in DOM.items()},
          open('d3.json','w',encoding='utf-8'),ensure_ascii=False)
