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
wb=openpyxl.load_workbook(io.BytesIO(open('launches13.xlsx','rb').read()),data_only=True)
SH=[('ТЕСТ B · Generator_11page_img_2','Тест B · с картинками','B','с картинками'),
    ('ТЕСТ B · Generator_11page_NOimg','Тест B · без картинок','B','без картинок'),
    ('ТЕСТ C · вебмастера, блок 1 (10','Тест C · старые аккаунты','C1','смешанная'),
    ('ТЕСТ C · вебмастера, блок 2 (10','Тест C · новые аккаунты','C2','смешанная')]
C_img=set('2428.team 7672.team y8db.team 5367.team khbr.team 4757.team 8304.team 8300.team 7039.team nwcs.team'.split())
DOMS=[]; LABS=[]
for sn,gname,tag,arm in SH:
    ws=wb[sn]; rows=list(ws.iter_rows(values_only=True))
    idx=[i for i,r in enumerate(rows) if r[0] and isinstance(r[0],str) and r[0].startswith('Ключ')]
    snaps=[i for i in idx if 'Снимок' in str(rows[i-1][0])]
    LABS=[str(rows[i-1][0]).replace('Снимок ','').replace(' XML','') for i in snaps]
    hdr=[str(c).strip().lower() for c in rows[snaps[0]][1:] if c not in (None,'')]
    per={d:[dict() for _ in snaps] for d in hdr}
    for j,h in enumerate(snaps):
        nxt=[i for i in idx if i>h]; end=(nxt[0]-1) if nxt else len(rows)
        for r in rows[h+1:end]:
            q=r[0]
            if not isinstance(q,str): continue
            q=q.strip().lower(); m=KW.get(q)
            if not m: continue
            br,vol,_=m
            if br in EXCL: continue
            for i,d in enumerate(hdr):
                try: p=int(r[1+i])
                except: continue
                if 1<=p<=100: per[d][j][q]=(p,br,vol,tier(vol))
    for d in hdr:
        a = arm if arm!='смешанная' else ('с картинками' if d in C_img else 'без картинок')
        S=per[d]; L=S[-1]
        cnt=lambda s,t:sum(1 for p,*_ in s.values() if p<=t)
        keys=[]
        for q,(p,br,vol,t) in L.items():
            if p<=10: keys.append({'q':q,'b':br,'v':vol,'t':t,'c':cls(q),'p':p,
                                   'h':[ (S[j].get(q) or (None,))[0] for j in range(len(S))]})
        keys.sort(key=lambda k:k['p'])
        brs={}
        for k in keys:
            e=brs.setdefault(k['b'],{'b':k['b'],'v':k['v'],'t':k['t'],'best':999,'n':0,'t3':0})
            e['best']=min(e['best'],k['p']); e['n']+=1
            if k['p']<=3: e['t3']+=1
        DOMS.append({'d':d,'zone':'.'+d.split('.')[-1],'g':gname,'test':tag,'arm':a,
            'tr':[cnt(s,10) for s in S],'tr30':[cnt(s,30) for s in S],'tr100':[len(s) for s in S],
            't10':cnt(L,10),'t30':cnt(L,30),'t100':len(L),'t3':cnt(L,3),
            'vch':sum(1 for p,b,v,t in L.values() if p<=10 and t=='ВЧ'),
            'sch':sum(1 for p,b,v,t in L.values() if p<=10 and t=='СЧ'),
            'nch':sum(1 for p,b,v,t in L.values() if p<=10 and t=='НЧ'),
            'best':min([p for p,*_ in L.values()], default=None),
            'nb':len(brs),'brands':sorted(brs.values(),key=lambda x:(x['best'],-x['n'])),
            'keys':keys,'labels':LABS})
def grp(ds,name,cfg):
    tm=[x for x in ds if x['zone']=='.team'] or ds
    v=sorted((x['t10'] for x in tm),reverse=True); n=len(tm)
    ser=[sum(x['tr'][j] for x in tm)/n for j in range(len(LABS))]
    tot=sum(v)
    return {'name':name,'cfg':cfg,'n':len(ds),'ntm':n,'t10':sum(v)/n,'med':st.median(v),
            'wo':sum(v[1:])/(n-1) if n>1 else 0,'vals':v,'ser':ser,
            'serhs':[sum(1 for x in tm for p,b,vv,t in [] ) for _ in LABS],
            'vch':sum(x['vch'] for x in tm),'sch':sum(x['sch'] for x in tm),
            't3':sum(x['t3'] for x in tm),'t30':sum(x['t30'] for x in tm),
            't100':sum(x['t100'] for x in tm),
            'z100':sum(1 for x in ds if x['t100']==0),
            'brands':len({b['b'] for x in tm for b in x['brands']}),
            'lead':v[0]/tot if tot else 0,'doms':[x['d'] for x in ds]}
G=[]
for _,gname,tag,_a in SH:
    ds=[x for x in DOMS if x['g']==gname]
    G.append(grp(ds,gname,{'B':'11 стр, наш генератор','C1':'вебмастера: старые аккаунты','C2':'вебмастера: новые аккаунты'}[tag]
                 + (' · '+ds[0]['arm'] if tag=='B' else '')))
ARM=[grp([x for x in DOMS if x['arm']==a],'Все '+a,'B + C, 19 доменов .team') for a in ('с картинками','без картинок')]
BLK=[grp([x for x in DOMS if x['test']==t],'Тест C · '+n,'10 доменов, зона .team, картинки 5+5') for t,n in (('C1','старые аккаунты'),('C2','новые аккаунты'))]
BR={}
for x in DOMS:
    for b in x['brands']:
        e=BR.setdefault(b['b'],{'b':b['b'],'v':b['v'],'t':b['t'],'doms':[],'keys':0,'best':999})
        e['doms'].append({'d':x['d'],'g':x['g'],'arm':x['arm'],'best':b['best'],'n':b['n'],'t3':b['t3']})
        e['keys']+=b['n']; e['best']=min(e['best'],b['best'])
for e in BR.values(): e['doms'].sort(key=lambda x:(x['best'],-x['n']))
BRL=sorted(BR.values(),key=lambda x:(-x['keys'],x['best']))
CAT=collections.Counter()
for x in DOMS:
    for k in x['keys']: CAT[k['c']]+=1
D={'labs':LABS,'doms':sorted(DOMS,key=lambda x:-x['t10']),'groups':G,'arms':ARM,'blocks':BLK,
   'brands':BRL,'cats':sorted(({'c':c,'n':n} for c,n in CAT.items()),key=lambda x:-x['n']),
   'tot':{'doms':len(DOMS),'t10':sum(x['t10'] for x in DOMS),'t3':sum(x['t3'] for x in DOMS),
          'hs':sum(x['vch']+x['sch'] for x in DOMS),'brands':len(BR),
          'z100':sum(1 for x in DOMS if x['t100']==0)}}
json.dump(D,open('flat24.json','w',encoding='utf-8'),ensure_ascii=False)
print('доменов',len(DOMS),'| Т10',D['tot']['t10'],'| брендов',len(BR),'| замеры',LABS)
for g in G+ARM: print('  %-26s n=%2d/%2d Т10/дом %5.2f мед %4.1f б/лид %5.2f лидер %2.0f%% ВЧ %2d СЧ %2d Т3 %2d'%(
    g['name'][:26],g['ntm'],g['n'],g['t10'],g['med'],g['wo'],100*g['lead'],g['vch'],g['sch'],g['t3']))
