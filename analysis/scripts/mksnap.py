import openpyxl,io,collections,statistics as st,core,json,re
KW=core.KW; EXCL=core.EXCL_BRAND; EXCL_DOM={'5374.team','2535.team'}
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
wb=openpyxl.load_workbook(io.BytesIO(open('launches18.xlsx','rb').read()),data_only=True)
SH=[('NEW33_12pages_nodate_25.08 (8)','ТЕСТ A · без дат','NEW33_12pages_nodate','A','без дат','12 стр · чужой контент'),
    ('NEW33_12pages_withdate_25.08 (8','ТЕСТ A · с датами','NEW33_12pages_withdate','A','с датами','12 стр · чужой контент'),
    ('Generator_11page_NOimg_25.08 (1','ТЕСТ B · без картинок','Generator_11page_NOimg','B','без картинок','11 стр · наш генератор'),
    ('Generator_11page_img_25.08 (5)','ТЕСТ B · с картинками','Generator_11page_img','B','с картинками','11 стр · наш генератор'),
    ('NEW50_5_7pages_nodate_21.08 (11','КОНТРОЛЬ','NEW50_5_7pages_nodate','CTRL','контроль','7 стр · контент 21.08 на новых доменах'),
    ('Старые аккаунты (nabor-149…153)','ТЕСТ D · старые аккаунты','Старые аккаунты','D','старые','наборы · старые вебмастер-аккаунты'),
    ('Новые аккаунты (nabor-144…148)','ТЕСТ D · новые аккаунты','Новые аккаунты','D','новые','наборы · новые вебмастер-аккаунты')]
def m(k,t): return sum(1 for x in k if x[0]<=t)
G=[]
for sn,name,sheet,test,arm,cfg in SH:
    ws=wb[sn]; rows=list(ws.iter_rows(values_only=True))
    allh=[i for i,r in enumerate(rows) if r[0] and isinstance(r[0],str) and r[0].strip().startswith('Ключ \\')]
    allsn=[h for h in allh if 'Снимок' in str(rows[h-1][0])]
    hdr=[str(c).strip().lower() for c in rows[allsn[0]][1:] if c not in (None,'')]
    def body(h):
        nxt=[i for i in allh if i>h]; end=(nxt[0]-1) if nxt else len(rows)
        return [r for r in rows[h+1:end] if isinstance(r[0],str) and r[0].strip().lower()!='ключ']
    def coverage(h):
        b=body(h); return max((i for i,r in enumerate(b) if any(v is not None for v in r[1:1+len(hdr)])),default=-1)+1,len(b)
    # берём только ПОЛНЫЕ снимки (покрытие >=95% ядра), обрезанные пропускаем
    full=[h for h in allsn if coverage(h)[0]>=0.95*coverage(h)[1]]
    skipped=[str(rows[h-1][0]).replace('Снимок ','').replace(' XML','') for h in allsn if h not in full]
    snaps=[full[0],full[-1]]
    labs=[str(rows[h-1][0]).replace('Снимок ','').replace(' XML','') for h in snaps]
    cov,core_n=coverage(snaps[1])
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
    G.append({'name':name,'cfg':cfg,'sheet':sheet,'test':test,'arm':arm,'skipped':skipped,'labs':labs,'cov':cov,'core':core_n,
              'ndom':len(hdr),'nexcl':sum(1 for d in hdr if d in EXCL_DOM),
              'snaps':snapdata,'slice':sl,'sldoms':sldoms})
json.dump({'g':G,'excl':sorted(EXCL_DOM)},open('snap.json','w',encoding='utf-8'),ensure_ascii=False)
for x in G:
    print('%-24s дом %2d | покрытие с2 %4d/%d (%.0f%%) | с1 %5.2f → с2 %5.2f (полн.) | срез %5.2f → %5.2f'%(
      x['name'],x['ndom'],x['cov'],x['core'],100*x['cov']/x['core'],
      x['snaps'][0]['agg']['mean'],x['snaps'][1]['agg']['mean'],x['slice'][0]['mean'],x['slice'][1]['mean']))

# ---- сводка по тестам: пары веток, обе меры, оба съёма ----
GB={x['name']:x for x in G}
def pair(a,b,test,title,note):
    A,B=GB[a],GB[b]
    return {'test':test,'title':title,'note':note,'a':a,'b':b,
      'cov':min(A['cov'],B['cov']),'core':A['core'],
      's1':{'a':A['snaps'][0]['agg'],'b':B['snaps'][0]['agg']},
      'sl':{'a1':A['slice'][0],'a2':A['slice'][1],'b1':B['slice'][0],'b2':B['slice'][1]}}
PAIRS=[
 pair('ТЕСТ A · без дат','ТЕСТ A · с датами','A','Тест A — даты',
      'Пара из одного прогона генерации, id 938-953 сплошным блоком, создание в 16:04 и 16:05, по 8 доменов .team. Двигается только наличие дат.'),
 pair('ТЕСТ B · без картинок','ТЕСТ B · с картинками','B','Тест B — картинки',
      'Ветки вышли из разных прогонов с разрывом 27 минут, размеры 7 против 5 доменов .team после исключения 2535.team. Пара собрана менее чисто, чем 24.08.'),
 pair('ТЕСТ D · старые аккаунты','ТЕСТ D · новые аккаунты','D','Тест D — возраст аккаунта',
      'Наборы, по 5 доменов .team. Запущены вместе, зона одна, картинки внутри блоков зеркальны.'),
]
CTRL=GB['КОНТРОЛЬ']
json.dump({'g':G,'excl':sorted(EXCL_DOM),'pairs':PAIRS,
  'ctrl':{'s1':CTRL['snaps'][0]['agg'],'sl1':CTRL['slice'][0],'sl2':CTRL['slice'][1],
          'cov':CTRL['cov'],'core':CTRL['core']}},
  open('snap.json','w',encoding='utf-8'),ensure_ascii=False)
print('пар:',len(PAIRS))
