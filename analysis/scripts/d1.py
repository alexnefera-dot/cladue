import openpyxl,io,collections,statistics as st,core
KW=core.KW; EXCL=core.EXCL_BRAND
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
wb=openpyxl.load_workbook(io.BytesIO(open('launches12.xlsx','rb').read()),data_only=True)
SH={'ТЕСТ B · Generator_11page_img_2':'B_img','ТЕСТ B · Generator_11page_NOimg':'B_noimg',
    'ТЕСТ C · вебмастера, блок 1 (10':'C1','ТЕСТ C · вебмастера, блок 2 (10':'C2'}
DOM={}
for sn,tag in SH.items():
    ws=wb[sn]; rows=list(ws.iter_rows(values_only=True))
    idx=[i for i,r in enumerate(rows) if r[0] and isinstance(r[0],str) and r[0].startswith('Ключ')]
    h=idx[0]; end=idx[1]-1 if len(idx)>1 else len(rows)
    hdr=[str(c).strip().lower() for c in rows[h][1:] if c not in (None,'')]
    for d in hdr: DOM[d]={'t':tag,'k':[],'z':'.'+d.split('.')[-1]}
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
            if 1<=p<=100: DOM[d]['k'].append((p,br,vol,tier(vol)))
C1_img=set('2428.team 7672.team y8db.team 5367.team khbr.team'.split())
C2_img=set('4757.team 8304.team 8300.team 7039.team nwcs.team'.split())
for d,v in DOM.items():
    if v['t']=='B_img': v['img']=True
    elif v['t']=='B_noimg': v['img']=False
    else: v['img']= d in C1_img or d in C2_img
def stat(ds,nm):
    t10=sorted((sum(1 for p,*_ in DOM[d]['k'] if p<=10) for d in ds),reverse=True)
    t3=sum(sum(1 for p,*_ in DOM[d]['k'] if p<=3) for d in ds)
    t30=sum(sum(1 for p,*_ in DOM[d]['k'] if p<=30) for d in ds)
    t100=sum(len(DOM[d]['k']) for d in ds)
    hs=sum(sum(1 for p,b,v,t in DOM[d]['k'] if p<=10 and t in('ВЧ','СЧ')) for d in ds)
    z0=sum(1 for d in ds if not DOM[d]['k'])
    n=len(ds)
    wo=sum(t10[1:])/(n-1) if n>1 else 0
    print('%-26s n=%2d | Т10/дом %5.2f | мед %4.1f | б/лид %5.2f | Т3 %3d | Т30 %4d | Т100 %4d | ВЧ+СЧ %2d | пусто %d | %s'%(
        nm,n,sum(t10)/n,st.median(t10),wo,t3,t30,t100,hs,z0,t10))
tm=lambda f:[d for d,v in DOM.items() if v['z']=='.team' and f(v,d)]
print('=== ТЕСТ B: картинки против без (только .team) ===')
stat(tm(lambda v,d:v['t']=='B_img'),'B · с картинками')
stat(tm(lambda v,d:v['t']=='B_noimg'),'B · без картинок')
print()
print('=== ТЕСТ B: пары .lol ===')
stat([d for d,v in DOM.items() if v['z']=='.lol' and v['t']=='B_img'],'.lol с картинками')
stat([d for d,v in DOM.items() if v['z']=='.lol' and v['t']=='B_noimg'],'.lol без картинок')
print()
print('=== ТЕСТ C: блок 1 против блока 2 ===')
stat(tm(lambda v,d:v['t']=='C1'),'блок 1')
stat(tm(lambda v,d:v['t']=='C2'),'блок 2')
print()
print('=== картинки внутри теста C ===')
for b in ('C1','C2'):
    stat(tm(lambda v,d,b=b:v['t']==b and v['img']),'%s · с картинками'%b)
    stat(tm(lambda v,d,b=b:v['t']==b and not v['img']),'%s · без картинок'%b)
print()
print('=== СВОДНО картинки: B + C, 19 против 19 ===')
stat(tm(lambda v,d:v['img']),'ВСЕ с картинками')
stat(tm(lambda v,d:not v['img']),'ВСЕ без картинок')
print()
print('=== домены ===')
for d,v in sorted(DOM.items(),key=lambda x:-sum(1 for p,*_ in x[1]['k'] if p<=10)):
    ks=v['k']; t10=sum(1 for p,*_ in ks if p<=10)
    brs=collections.Counter(b for p,b,vv,t in ks if p<=10)
    print('  %-12s %-8s %-8s Т10 %3d Т30 %3d Т100 %3d Т3 %2d | %s'%(d,v['t'],'img' if v['img'] else 'noimg',
        t10,sum(1 for p,*_ in ks if p<=30),len(ks),sum(1 for p,*_ in ks if p<=3),
        ', '.join('%s'%b for b,_ in brs.most_common(5)) or '—'))
