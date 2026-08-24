import openpyxl,io,collections,json,datetime
wb=openpyxl.load_workbook(io.BytesIO(open('conv.xlsx','rb').read()),data_only=True)
rows=[r for r in wb['Sheet1'].iter_rows(values_only=True) if r[0]]
D=json.load(open('flat.json',encoding='utf-8'))
KNOWN={d['d'] for d in D['doms']}
GN={d['d']:d['gname'] for d in D['doms']}
ev=[]
for r in rows:
    h=str(r[5]).strip().lower(); p=h.split('.')
    if h in ('yandex.ru','ru.search.yahoo.com','alice.yandex.ru'): continue
    ev.append({'t':r[0],'k':r[1],'br':'.'.join(p[:-2]),'dom':'.'.join(p[-2:]),'cid':r[3]})
new=[e for e in ev if e['dom'] in KNOWN]; old=[e for e in ev if e['dom'] not in KNOWN]
def st(x,nm):
    reg=sum(1 for e in x if e['k']=='reg'); dep=sum(1 for e in x if e['k']=='dep')
    doms={e['dom'] for e in x}
    print('%-22s событий %3d | рег %3d | деп %3d | деп/рег %5.1f%% | доменов %3d'%(nm,len(x),reg,dep,100*dep/reg if reg else 0,len(doms)))
st(ev,'ВСЕГО'); st(new,'новые (реестр)'); st(old,'старые запуски')
print()
print('--- ДЕПОЗИТЫ (26) ---')
for e in sorted([e for e in ev if e['k']=='dep'],key=lambda x:x['t']):
    g=GN.get(e['dom'],'старый запуск')
    print('  %s  %-16s %-14s %s'%(e['t'].strftime('%d.%m %H:%M'),e['dom'],e['br'],g))
print()
print('--- деп по когортам старых доменов (по дате первой конверсии) ---')
first={}
for e in old: first.setdefault(e['dom'],e['t'])
for d,t in first.items(): first[d]=min(t,min(x['t'] for x in old if x['dom']==d))
coh=collections.defaultdict(lambda: collections.Counter())
for e in old:
    k=first[e['dom']].strftime('%d.%m')
    coh[k][e['k']]+=1; coh[k]['d_'+e['dom']]=1
for k in sorted(coh,key=lambda s:(s[3:],s[:2])):
    c=coh[k]; nd=sum(1 for x in c if x.startswith('d_'))
    print('  первая конв. %s: доменов %2d, рег %2d, деп %2d'%(k,nd,c['reg'],c['dep']))
