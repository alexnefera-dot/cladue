import openpyxl,io,collections,statistics as st,core,json,re
KW=core.KW; EXCL=core.EXCL_BRAND; EXCL_DOM={'5374.team','2535.team'}
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
wb=openpyxl.load_workbook(io.BytesIO(open('launches17.xlsx','rb').read()),data_only=True)
SH=[('NEW33_12pages_nodate_25.08 (8)','NEW33_12pages_nodate','тест A · 12 стр без дат · чужой контент'),
    ('NEW33_12pages_withdate_25.08 (8','NEW33_12pages_withdate','тест A · 12 стр с датами · чужой контент'),
    ('Generator_11page_NOimg_25.08 (1','Generator_11page_NOimg','тест B · 11 стр без картинок · наш генератор'),
    ('Generator_11page_img_25.08 (5)','Generator_11page_img','тест B · 11 стр с картинками · наш генератор'),
    ('NEW50_5_7pages_nodate_21.08 (11','NEW50_5_7pages_nodate','контроль · 7 стр без дат · контент 21.08'),
    ('Старые аккаунты (nabor-149…153)','Старые аккаунты','тест D · наборы · старые вебмастер-аккаунты'),
    ('Новые аккаунты (nabor-144…148)','Новые аккаунты','тест D · наборы · новые вебмастер-аккаунты')]
def m(k,t): return sum(1 for x in k if x[0]<=t)
G=[]
for sn,name,cfg in SH:
    ws=wb[sn]; rows=list(ws.iter_rows(values_only=True))
    allh=[i for i,r in enumerate(rows) if r[0] and isinstance(r[0],str) and r[0].strip().startswith('Ключ \\')]
    snaps=[h for h in allh if 'Снимок' in str(rows[h-1][0])]
    labs=[str(rows[h-1][0]).replace('Снимок ','').replace(' XML','') for h in snaps]
    hdr=[str(c).strip().lower() for c in rows[snaps[0]][1:] if c not in (None,'')]
    def body(h):
        nxt=[i for i in allh if i>h]; end=(nxt[0]-1) if nxt else len(rows)
        return [r for r in rows[h+1:end] if isinstance(r[0],str) and r[0].strip().lower()!='ключ']
    b2=body(snaps[1]); cov=max(i for i,r in enumerate(b2) if any(v is not None for v in r[1:1+len(hdr)]))+1
    core_n=len(b2)
    def read(h,limit=None):
        per={d:[] for d in hdr}
        for r in (body(h)[:limit] if limit else body(h)):
            q=r[0].strip().lower(); mm=KW.get(q)
            if not mm: continue
            br,vol,_=mm
            if br in EXCL: continue
            for i,d in enumerate(hdr):
                try: p=int(r[1+i])
                except: continue
                if 1<=p<=100: per[d].append({'p':p,'b':br,'v':vol,'t':tier(vol),'q':q})
        return per
    FULL=[read(h) for h in snaps]; SLICE=[read(h,cov) for h in snaps]
    def agg(per):
        ds=[d for d in hdr if d not in EXCL_DOM and d.endswith('.team')]
        ks=[[(x['p'],x['t']) for x in per[d]] for d in ds]; n=max(len(ds),1)
        v=sorted((sum(1 for p,t in k if p<=10) for k in ks),reverse=True)
        return {'n':n,'mean':sum(v)/n,'med':st.median(v) if v else 0,
          'wo':sum(v[1:])/(n-1) if n>1 else 0,'vals':v,
          't3':sum(sum(1 for p,t in k if p<=3) for k in ks),
          't30':sum(sum(1 for p,t in k if p<=30) for k in ks),
          't100':sum(len(k) for k in ks),
          'vch':sum(1 for k in ks for p,t in k if p<=10 and t=='ВЧ'),
          'sch':sum(1 for k in ks for p,t in k if p<=10 and t=='СЧ')}
    snapdata=[]
    for j,lab in enumerate(labs):
        per=FULL[j]
        br=collections.Counter()
        for d in hdr:
            if d in EXCL_DOM: continue
            for x in per[d]:
                if x['p']<=10: br[x['b']]+=1
        hi=collections.defaultdict(list)
        for d in hdr:
            if d in EXCL_DOM: continue
            for x in per[d]:
                if x['p']<=10 and x['t'] in ('ВЧ','СЧ'): hi[(x['b'],x['t'],x['v'])].append((x['p'],d))
        hil=sorted(({'b':b,'t':t,'v':v,'best':min(p for p,_ in q),'dom':min(q)[1],'n':len(q)}
                    for (b,t,v),q in hi.items()),key=lambda x:x['best'])
        doms=[]
        for d in hdr:
            ks=sorted([x for x in per[d] if x['p']<=10],key=lambda x:x['p'])
            bb=collections.Counter(x['b'] for x in ks)
            doms.append({'d':d,'zone':'.'+d.split('.')[-1],'excl':d in EXCL_DOM,
              't10':len(ks),'t30':m([(x['p'],) for x in per[d]],30) if False else sum(1 for x in per[d] if x['p']<=30),
              't100':len(per[d]),'t3':sum(1 for x in per[d] if x['p']<=3),
              'vch':sum(1 for x in ks if x['t']=='ВЧ'),'sch':sum(1 for x in ks if x['t']=='СЧ'),
              'nb':len(bb),'brands':[b for b,_ in bb.most_common(6)],
              'keys':[{'q':x['q'],'p':x['p'],'b':x['b'],'t':x['t']} for x in ks[:8]]})
        doms.sort(key=lambda x:-x['t10'])
        snapdata.append({'lab':lab,'full':j==0 or cov>=core_n,'agg':agg(per),
          'brands':br.most_common(12),'nbrands':len(br),'hi':hil[:12],'nhi':sum(x['n'] for x in hil),'doms':doms})
    sl=[agg(SLICE[j]) for j in range(len(labs))]
    sldoms=[]
    for d in hdr:
        if d in EXCL_DOM: continue
        sldoms.append({'d':d,'zone':'.'+d.split('.')[-1],
          'a':[sum(1 for x in SLICE[j][d] if x['p']<=10) for j in range(len(labs))],
          'b':[sum(1 for x in SLICE[j][d] if x['p']<=30) for j in range(len(labs))]})
    sldoms.sort(key=lambda x:-x['a'][-1])
    G.append({'name':name,'cfg':cfg,'sheet':sn,'labs':labs,'cov':cov,'core':core_n,
              'ndom':len(hdr),'nexcl':sum(1 for d in hdr if d in EXCL_DOM),
              'snaps':snapdata,'slice':sl,'sldoms':sldoms})
json.dump({'g':G,'excl':sorted(EXCL_DOM)},open('snap.json','w',encoding='utf-8'),ensure_ascii=False)
for x in G:
    print('%-24s дом %2d | покрытие с2 %4d/%d (%.0f%%) | с1 %5.2f → с2 %5.2f (полн.) | срез %5.2f → %5.2f'%(
      x['name'],x['ndom'],x['cov'],x['core'],100*x['cov']/x['core'],
      x['snaps'][0]['agg']['mean'],x['snaps'][1]['agg']['mean'],x['slice'][0]['mean'],x['slice'][1]['mean']))
