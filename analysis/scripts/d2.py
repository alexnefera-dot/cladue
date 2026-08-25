import openpyxl,io,collections,statistics as st,core,json
KW=core.KW; EXCL=core.EXCL_BRAND
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
wb=openpyxl.load_workbook(io.BytesIO(open('launches13.xlsx','rb').read()),data_only=True)
SH={'ТЕСТ B · Generator_11page_img_2':'B_img','ТЕСТ B · Generator_11page_NOimg':'B_noimg',
    'ТЕСТ C · вебмастера, блок 1 (10':'C1','ТЕСТ C · вебмастера, блок 2 (10':'C2'}
DOM={}; LAB=[]
for sn,tag in SH.items():
    ws=wb[sn]; rows=list(ws.iter_rows(values_only=True))
    idx=[i for i,r in enumerate(rows) if r[0] and isinstance(r[0],str) and r[0].startswith('Ключ')]
    snaps=[i for i in idx if 'Снимок' in str(rows[i-1][0])]     # ловушка «Среднее по съёмам»
    labs=[str(rows[i-1][0]).replace('Снимок ','').replace(' XML','') for i in snaps]
    LAB=labs
    hdr=[str(c).strip().lower() for c in rows[snaps[0]][1:] if c not in (None,'')]
    for d in hdr: DOM[d]={'t':tag,'z':'.'+d.split('.')[-1],'s':[[] for _ in snaps]}
    for j,h in enumerate(snaps):
        nxt=[i for i in idx if i>h]; end=(nxt[0]-1) if nxt else len(rows)
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
                if 1<=p<=100: DOM[d]['s'][j].append((p,br,vol,tier(vol),q.strip().lower()))
C_img=set('2428.team 7672.team y8db.team 5367.team khbr.team 4757.team 8304.team 8300.team 7039.team nwcs.team'.split())
for d,v in DOM.items():
    v['img']= v['t']=='B_img' or (v['t'] in ('C1','C2') and d in C_img)
def m(ks,lo): return sum(1 for p,*_ in ks if p<=lo)
def stat(ds,nm,j=-1):
    ks=[DOM[d]['s'][j] for d in ds]
    t10=sorted((m(k,10) for k in ks),reverse=True); n=len(ds)
    hs=sum(sum(1 for p,b,v,t,q in k if p<=10 and t in('ВЧ','СЧ')) for k in ks)
    print('%-24s n=%2d | Т10/дом %5.2f | мед %4.1f | б/лид %5.2f | Т3 %3d | Т30 %4d | Т100 %4d | ВЧ+СЧ %2d | пусто %d | %s'%(
        nm,n,sum(t10)/n,st.median(t10),sum(t10[1:])/(n-1) if n>1 else 0,
        sum(m(k,3) for k in ks),sum(m(k,30) for k in ks),sum(len(k) for k in ks),hs,
        sum(1 for k in ks if not k),t10))
tm=lambda f:[d for d,v in DOM.items() if v['z']=='.team' and f(v,d)]
print('замеры:',LAB)
for j,lb in enumerate(LAB):
    print('\n########## %s ##########'%lb)
    print('--- ТЕСТ B, только .team ---')
    stat(tm(lambda v,d:v['t']=='B_img'),'B · с картинками',j)
    stat(tm(lambda v,d:v['t']=='B_noimg'),'B · без картинок',j)
    print('--- пары .lol ---')
    stat([d for d,v in DOM.items() if v['z']=='.lol' and v['t']=='B_img'],'.lol с картинками',j)
    stat([d for d,v in DOM.items() if v['z']=='.lol' and v['t']=='B_noimg'],'.lol без картинок',j)
    print('--- ТЕСТ C ---')
    stat(tm(lambda v,d:v['t']=='C1'),'блок 1',j)
    stat(tm(lambda v,d:v['t']=='C2'),'блок 2',j)
    print('--- картинки сводно B+C ---')
    stat(tm(lambda v,d:v['img']),'ВСЕ с картинками',j)
    stat(tm(lambda v,d:not v['img']),'ВСЕ без картинок',j)
json.dump({d:{'t':v['t'],'z':v['z'],'img':v['img'],
              'tr':[m(k,10) for k in v['s']],'tr30':[m(k,30) for k in v['s']],
              'tr100':[len(k) for k in v['s']],'t3':[m(k,3) for k in v['s']],
              'hs':[sum(1 for p,b,vv,t,q in k if p<=10 and t in('ВЧ','СЧ')) for k in v['s']],
              'keys':[[list(x) for x in k] for k in v['s']]} for d,v in DOM.items()},
          open('d2.json','w',encoding='utf-8'),ensure_ascii=False)
