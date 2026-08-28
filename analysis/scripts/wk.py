import json,collections,statistics as st
C=json.load(open('conv2.json')); db=json.load(open('db.json')); full=json.load(open('full.json'))
EV=C['ev']; TR=C['tr']; regs=[e for e in EV if e['type']=='reg']; deps=[e for e in EV if e['type']=='dep']
gt={x['geo']:x['uniq'] for x in C['geo']}; TOTU=sum(gt.values())
rd=collections.Counter(e['dom'] for e in regs); dd=collections.Counter(e['dom'] for e in deps)
rb=collections.Counter(e['brand'] for e in regs if e['brand'])
# захват по брендам
cap=collections.defaultdict(lambda:{'d10':0,'d30':0,'d100':0,'k10':0,'k3':0,'best':999,'tier':None,'vol':0})
for d,v in db.items():
    for b,x in v['b'].items():
        c=cap[b]; c['d100']+=1
        if x['t10']: c['d10']+=1
        if x['t30']: c['d30']+=1
        c['k10']+=x['t10']; c['k3']+=x['t3']; c['best']=min(c['best'],x['best'] or 999)
        c['tier']=x['tier']; c['vol']=max(c['vol'],x['vol'])
BR=[]
for b in set(list(cap)+list(rb)):
    c=cap.get(b,{'d10':0,'d30':0,'d100':0,'k10':0,'k3':0,'best':999,'tier':None,'vol':0})
    geo=collections.Counter(e['geo'] for e in regs if e['brand']==b)
    doms=collections.Counter(e['dom'] for e in regs if e['brand']==b)
    BR.append(dict(b=b,tier=c['tier'],vol=c['vol'],d10=c['d10'],d30=c['d30'],d100=c['d100'],
      k10=c['k10'],k3=c['k3'],best=(c['best'] if c['best']!=999 else None),
      reg=rb.get(b,0),incore=b in cap,geo=geo.most_common(6),doms=doms.most_common(6)))
BR.sort(key=lambda x:(-x['reg'],-x['k10']))
# домены
DM=[]
for d,v in db.items():
    bs=v['b'].values(); tr=TR.get(d,{})
    top=sorted([(b,x['t10'],x['t3'],x['best']) for b,x in v['b'].items() if x['t10']],key=lambda z:-z[1])[:8]
    DM.append(dict(d=d,group=v['group'],src=v['src'],pages=v['pages'],dates=v['dates'],img=v['img'],
      acc=v['acc'],lab=v['lab'],zone=v['zone'],
      t3=sum(x['t3'] for x in bs),t10=sum(x['t10'] for x in bs),t30=sum(x['t30'] for x in bs),
      t100=sum(x['t100'] for x in bs),nb=sum(1 for x in bs if x['t10']),
      reg=rd.get(d,0),dep=dd.get(d,0),uniq=tr.get('uniq',0),hits=tr.get('hits',0),sub=tr.get('sub',0),
      top=top))
for d,v in TR.items():
    if v['is_dom'] and d not in db and (v['reg'] or v['uniq']>3000):
        DM.append(dict(d=d,group='вне наблюдения',src='?',pages='?',dates='—',img='—',acc='—',lab='—',
          zone='.'+d.split('.')[-1],t3=0,t10=0,t30=0,t100=0,nb=0,reg=rd.get(d,0),dep=dd.get(d,0),
          uniq=v['uniq'],hits=v['hits'],sub=v['sub'],top=[]))
DM.sort(key=lambda x:(-x['reg'],-x['t10']))
# группы
GR=collections.defaultdict(lambda:{'reg':0,'dep':0,'uniq':0,'hits':0,'dom':set(),'t10':0,'t3':0,'t100':0,'nd':0,'cfg':None})
for x in DM:
    g=GR[x['group']]
    g['reg']+=x['reg']; g['dep']+=x['dep']; g['uniq']+=x['uniq']; g['hits']+=x['hits']
    g['t10']+=x['t10']; g['t3']+=x['t3']; g['t100']+=x['t100']; g['nd']+=1; g['dom'].add(x['d'])
    if g['cfg'] is None: g['cfg']=dict(src=x['src'],pages=x['pages'],dates=x['dates'],img=x['img'],acc=x['acc'])
GRL=[dict(g=k,reg=v['reg'],dep=v['dep'],uniq=v['uniq'],nd=v['nd'],t10=v['t10'],t3=v['t3'],t100=v['t100'],
     rpd=round(v['reg']/v['nd'],3),t10d=round(v['t10']/v['nd'],2),cfg=v['cfg']) for k,v in GR.items()]
GRL.sort(key=lambda x:-x['reg'])
# гео
GEO=[dict(geo=x['geo'],uniq=x['uniq'],reg=sum(1 for e in regs if e['geo']==x['geo'])) for x in C['geo']]
GEO=[g for g in GEO if g['reg'] or g['uniq']>500]
GEO.sort(key=lambda x:-x['reg'])
# позиции -> конверсии
GRAD=[]
for lo,hi,lab in [(0,0,'ни одного'),(1,4,'1–4'),(5,14,'5–14'),(15,49,'15–49'),(50,999,'50 и больше')]:
    r=[x for x in DM if x['group']!='вне наблюдения' and lo<=x['t10']<=hi]
    if r: GRAD.append(dict(lab=lab,n=len(r),reg=sum(x['reg'] for x in r),rpd=round(sum(x['reg'] for x in r)/len(r),2),
                           uniq=sum(x['uniq'] for x in r)))
DAYS=[dict(d=k,reg=v) for k,v in sorted(collections.Counter(e['d'] for e in regs).items())]
json.dump({'br':BR,'dm':DM,'gr':GRL,'geo':GEO,'grad':GRAD,'days':DAYS,
  'tot':dict(reg=len(regs),dep=len(deps),uniq=TOTU,hits=sum(v['hits'] for v in TR.values() if v['is_dom']),
             dom=len([1 for v in TR.values() if v['is_dom']]),sub=sum(v['sub'] for v in TR.values() if v['is_dom']),
             brands=len(rb),nocore=sum(c for b,c in rb.items() if b not in cap),
             ru_reg=sum(1 for e in regs if e['geo']=='🇷🇺 RU'),ru_uniq=gt.get('🇷🇺 RU',0),
             cis_reg=sum(1 for e in regs if e['geo'] in {'🇰🇿 KZ','🇺🇿 UZ','🇧🇾 BY'}),
             cis_uniq=sum(gt.get(g,0) for g in {'🇰🇿 KZ','🇺🇿 UZ','🇧🇾 BY'}),
             deps=[{'ts':e['ts'],'host':e['host'],'geo':e['geo']} for e in deps])},
  open('wk.json','w'),ensure_ascii=False)
print('брендов',len(BR),'доменов',len(DM),'групп',len(GRL),'гео',len(GEO))
