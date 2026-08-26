import openpyxl,io,collections,statistics as st,core,json,re
KW=core.KW; EXCL=core.EXCL_BRAND
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
PAT=[("зеркало",r"зеркал|mirror"),("вход",r"\bвход\b|войти|log ?in"),
     ("регистрация",r"регистрац|\bреги\b|sign ?up|создать аккаунт"),
     ("офиц. сайт",r"официальн|\bофиц\b|official"),
     ("бонус/промокод",r"бонус|промокод|промо|фриспин|freespin|бездеп|no ?deposit"),
     ("играть/деньги",r"играть|на деньги|на реальные|игровые автоматы|слоты|игра\b"),
     ("приложение",r"приложени|скачать|apk|андроид|android|\bios\b|мобильн|download|app\b"),
     ("отзывы",r"отзыв|review|развод|вывод"),("личный кабинет",r"кабинет|личный|аккаунт|account|профил"),
     ("бренд + казино",r"казино|casino|kazino")]
def cls(q):
    for n,rx in PAT:
        if re.search(rx,q): return n
    return "бренд без добавок" if len(q.split())<=3 else "прочее"
SRC=[('launches13.xlsx',[
  ('ТЕСТ B · Generator_11page_img_2','24.08 · картинки','B1','с картинками','наш','11 стр'),
  ('ТЕСТ B · Generator_11page_NOimg','24.08 · без картинок','B1','без картинок','наш','11 стр'),
  ('ТЕСТ C · вебмастера, блок 1 (10','24.08 · старые аккаунты','C1','смешанная','наш','11 стр'),
  ('ТЕСТ C · вебмастера, блок 2 (10','24.08 · новые аккаунты','C2','смешанная','наш','11 стр')]),
 ('launches14.xlsx',[
  ('NEW33_12pages_withdate_25.08 (8','25.08 · 12 стр + даты','A','с датами','чужой','12 стр'),
  ('NEW33_12pages_nodate_25.08 (8)','25.08 · 12 стр без дат','A','без дат','чужой','12 стр'),
  ('Generator_11page_NOimg_25.08 (1','25.08 · без картинок','B2','без картинок','наш','11 стр'),
  ('Generator_11page_img_25.08 (5)','25.08 · с картинками','B2','с картинками','наш','11 стр'),
  ('NEW50_5_7pages_nodate_21.08 (11','25.08 · контроль (контент 21.08)','CTRL','контроль','чужой','7 стр')]),
 ('launches15.xlsx',[
  ('Старые аккаунты (nabor-149…153)','26.08 · наборы, старые акк.','D_old','наборы','наборы','12 стр'),
  ('Новые аккаунты (nabor-144…148)','26.08 · наборы, новые акк.','D_new','наборы','наборы','12 стр')])]
EXCL_DOM={'5374.team','2535.team'}   # исключены по просьбе
C_img=set('2428.team 7672.team y8db.team 5367.team khbr.team 4757.team 8304.team 8300.team 7039.team nwcs.team'.split())
DOMS=[]
for fn,sheets in SRC:
    wb=openpyxl.load_workbook(io.BytesIO(open(fn,'rb').read()),data_only=True)
    for sn,gname,tag,arm,author,fmt in sheets:
        ws=wb[sn]; rows=list(ws.iter_rows(values_only=True))
        idx=[i for i,r in enumerate(rows) if r[0] and isinstance(r[0],str) and r[0].startswith('Ключ')]
        snaps=[i for i in idx if 'Снимок' in str(rows[i-1][0])]
        labs=[str(rows[i-1][0]).replace('Снимок ','').replace(' XML','') for i in snaps]
        hdr=[str(c).strip().lower() for c in rows[snaps[0]][1:] if c not in (None,'')]
        per={d:[dict() for _ in snaps] for d in hdr}
        for j,h in enumerate(snaps):
            nxt=[i for i in idx if i>h]; end=(nxt[0]-1) if nxt else len(rows)
            for r in rows[h+1:end]:
                q=r[0]
                if not isinstance(q,str): continue
                q=q.strip().lower(); mm=KW.get(q)
                if not mm: continue
                br,vol,_=mm
                if br in EXCL: continue
                for i,d in enumerate(hdr):
                    try: p=int(r[1+i])
                    except: continue
                    if 1<=p<=100: per[d][j][q]=(p,br,vol,tier(vol))
        for d in hdr:
            if d in EXCL_DOM: continue
            a = arm if arm!='смешанная' else ('с картинками' if d in C_img else 'без картинок')
            S=per[d]; L=S[-1]; cnt=lambda s,t:sum(1 for p,*_ in s.values() if p<=t)
            keys=[]
            for q,(p,br,vol,t) in L.items():
                if p<=10: keys.append({'q':q,'b':br,'v':vol,'t':t,'c':cls(q),'p':p,
                                       'h':[(S[j].get(q) or (None,))[0] for j in range(len(S))]})
            keys.sort(key=lambda k:k['p'])
            brs={}
            for k in keys:
                e=brs.setdefault(k['b'],{'b':k['b'],'v':k['v'],'t':k['t'],'best':999,'n':0,'t3':0})
                e['best']=min(e['best'],k['p']); e['n']+=1
                if k['p']<=3: e['t3']+=1
            DOMS.append({'d':d,'zone':'.'+d.split('.')[-1],'g':gname,'test':tag,'arm':a,
                'author':author,'fmt':fmt,'day':gname[:5],
                'tr':[cnt(s,10) for s in S],'tr30':[cnt(s,30) for s in S],'tr100':[len(s) for s in S],
                't10':cnt(L,10),'t30':cnt(L,30),'t100':len(L),'t3':cnt(L,3),
                'vch':sum(1 for p,b,v,t in L.values() if p<=10 and t=='ВЧ'),
                'sch':sum(1 for p,b,v,t in L.values() if p<=10 and t=='СЧ'),
                'nch':sum(1 for p,b,v,t in L.values() if p<=10 and t=='НЧ'),
                'best':min([p for p,*_ in L.values()],default=None),
                'nb':len(brs),'brands':sorted(brs.values(),key=lambda x:(x['best'],-x['n'])),
                'keys':keys,'labels':labs})
def grp(ds,name,cfg):
    tm=[x for x in ds if x['zone']=='.team'] or ds
    v=sorted((x['t10'] for x in tm),reverse=True); n=len(tm); tot=sum(v)
    L=max(len(x['tr']) for x in tm)
    ser=[sum(x['tr'][j] for x in tm if len(x['tr'])>j)/sum(1 for x in tm if len(x['tr'])>j) for j in range(L)]
    return {'name':name,'cfg':cfg,'n':len(ds),'ntm':n,'t10':sum(v)/n,'med':st.median(v),
      'wo':sum(v[1:])/(n-1) if n>1 else 0,'vals':v,'ser':ser,
      'vch':sum(x['vch'] for x in tm),'sch':sum(x['sch'] for x in tm),
      't3':sum(x['t3'] for x in tm),'t30':sum(x['t30'] for x in tm),'t100':sum(x['t100'] for x in tm),
      'z100':sum(1 for x in ds if x['t100']==0),
      'brands':len({b['b'] for x in tm for b in x['brands']}),
      'lead':v[0]/tot if tot else 0}
ORD=['25.08 · контроль (контент 21.08)','26.08 · наборы, старые акк.','26.08 · наборы, новые акк.','25.08 · 12 стр без дат','25.08 · 12 стр + даты',
     '25.08 · без картинок','25.08 · с картинками','24.08 · новые аккаунты','24.08 · старые аккаунты',
     '24.08 · без картинок','24.08 · картинки']
G=[grp([x for x in DOMS if x['g']==nm],nm,
       {'25.08 · контроль (контент 21.08)':'7 стр, контенты 21.08, чужой',
        '25.08 · 12 стр без дат':'тест A, чужой контент','25.08 · 12 стр + даты':'тест A, чужой контент',
        '25.08 · без картинок':'тест B день 2, наш','25.08 · с картинками':'тест B день 2, наш',
        '24.08 · новые аккаунты':'тест C, наш','24.08 · старые аккаунты':'тест C, наш',
        '24.08 · без картинок':'тест B день 1, наш','24.08 · картинки':'тест B день 1, наш',
        '26.08 · наборы, старые акк.':'тест D, наборы','26.08 · наборы, новые акк.':'тест D, наборы'}[nm]) for nm in ORD]
IMG=[grp([x for x in DOMS if x['arm']==a and x['author']=='наш'],'Картинки: '+a,'тест B, оба дня, .team') for a in ('без картинок','с картинками')]
DAT=[grp([x for x in DOMS if x['arm']==a],'Даты: '+a,'тест A, 25.08') for a in ('без дат','с датами')]
AUT=[grp([x for x in DOMS if x['author']==a and x['day']=='25.08'],'Автор: '+a+' контент','25.08, один съём') for a in ('чужой','наш')]
ACC=[grp([x for x in DOMS if x['test'] in t],'Аккаунты: '+n,'тесты C и D, .team') for t,n in ((('C1','D_old'),'старые'),(('C2','D_new'),'новые'))]
BR={}
for x in DOMS:
    for b in x['brands']:
        e=BR.setdefault(b['b'],{'b':b['b'],'v':b['v'],'t':b['t'],'doms':[],'keys':0,'best':999})
        e['doms'].append({'d':x['d'],'g':x['g'],'arm':x['arm'],'best':b['best'],'n':b['n'],'t3':b['t3']})
        e['keys']+=b['n']; e['best']=min(e['best'],b['best'])
for e in BR.values(): e['doms'].sort(key=lambda x:(x['best'],-x['n']))
CAT=collections.Counter()
for x in DOMS:
    for k in x['keys']: CAT[k['c']]+=1
D={'labs':['24.08 22:24','25.08 11:09','25.08 23:21'],
   'doms':sorted(DOMS,key=lambda x:-x['t10']),'groups':G,'img':IMG,'dat':DAT,'aut':AUT,'acc':ACC,
   'brands':sorted(BR.values(),key=lambda x:(-x['keys'],x['best'])),
   'cats':sorted(({'c':c,'n':n} for c,n in CAT.items()),key=lambda x:-x['n']),
   'tot':{'doms':len(DOMS),'t10':sum(x['t10'] for x in DOMS),'t3':sum(x['t3'] for x in DOMS),
          'hs':sum(x['vch']+x['sch'] for x in DOMS),'brands':len(BR),
          'z100':sum(1 for x in DOMS if x['t100']==0)}}
json.dump(D,open('flatall.json','w',encoding='utf-8'),ensure_ascii=False)
print('доменов',len(DOMS),'групп',len(G),'брендов',len(BR),'Т10',D['tot']['t10'])
for g in G+IMG+DAT+AUT:
    print('  %-34s n=%2d/%2d Т10/дом %6.2f мед %5.1f б/лид %6.2f лид %2.0f%% ВЧ %2d СЧ %2d Т3 %3d'%(
        g['name'][:34],g['ntm'],g['n'],g['t10'],g['med'],g['wo'],100*g['lead'],g['vch'],g['sch'],g['t3']))
