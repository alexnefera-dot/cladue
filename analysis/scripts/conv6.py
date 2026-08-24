import openpyxl,io,collections,json,datetime,math
wb=openpyxl.load_workbook(io.BytesIO(open('conv.xlsx','rb').read()),data_only=True)
rows=[r for r in wb['Sheet1'].iter_rows(values_only=True) if r[0]]
D=json.load(open('flat.json',encoding='utf-8'))
GN={d['d']:d['gname'] for d in D['doms']}
FMT={d['gname']:d['fmt'] for d in D['doms']}
PG={d['gname']:d['pages'] for d in D['doms']}
ev=[]
for r in rows:
    h=str(r[5]).strip().lower(); p=h.split('.')
    if h in ('yandex.ru','ru.search.yahoo.com','alice.yandex.ru'): continue
    ev.append({'t':r[0],'k':r[1],'dom':'.'.join(p[-2:]),'br':'.'.join(p[:-2])})
LAUNCH={'Generator_11page':'20.08 01:25','7page_yandex':'20.08 01:25','Generator_11page_2':'20.08 01:25',
 'Generator_v5':'20.08 01:25','Generator_v4_2':'20.08 01:25','generator v4':'20.08 01:25',
 '12pages_withdate · Theme1':'20.08 17:00','12pages_withdate · Theme2':'20.08 17:00',
 '12pages_nodate':'20.08 17:00','7pages_nodate':'20.08 17:00','kostoreznaya1 · имена':'20.08 17:00',
 'nabor28gotovyi · наборы':'20.08 17:00','Generation 50':'20.08 22:00',
 'Generator_11page_21.08 (обе партии)':'22.08 01:18','nabor-53 · наборы':'22.08 01:18',
 'NEW50_5_12pages_withdate':'22.08 01:18','NEW50_5_7pages_withdate':'22.08 01:18',
 'Generator_11page_img':'22.08 23:30','NEW50_5_12pages_nodate':'22.08 23:04','NEW50_5_7pages_nodate':'22.08 23:04'}
END=datetime.datetime(2026,8,24,12,15)
def dt(s):
    d,t=s.split(); dd,mm=d.split('.'); hh,mi=t.split(':')
    return datetime.datetime(2026,int(mm),int(dd),int(hh),int(mi))
# группировка по формату
BUCK={}
for g in LAUNCH:
    p=PG[g]
    if p.startswith('12'): b='12 страниц'
    elif p.startswith('11'): b='11 страниц'
    elif p.startswith('7'): b='7 страниц'
    else: b='неизвестно (Generation 50)'
    BUCK[g]=b
agg=collections.defaultdict(lambda: {'reg':0,'dep':0,'domdays':0,'n':0,'groups':[]})
for g,L in LAUNCH.items():
    n=len([d for d in D['doms'] if d['gname']==g]); days=(END-dt(L)).total_seconds()/86400
    a=agg[BUCK[g]]; a['domdays']+=n*days; a['n']+=n; a['groups'].append(g)
for e in ev:
    g=GN.get(e['dom'])
    if not g: continue
    agg[BUCK[g]][e['k']]+=1
print('%-26s %4s %8s %5s %5s %11s'%('формат','дом','дом·дней','рег','деп','рег/дом/дн'))
for b,a in sorted(agg.items(),key=lambda x:-x[1]['reg']/x[1]['domdays']):
    print('%-26s %4d %8.1f %5d %5d %11.3f'%(b,a['n'],a['domdays'],a['reg'],a['dep'],a['reg']/a['domdays']))
print()
# даты vs без дат в 12-страничных
for nm,gs in [('12 стр С датами',['12pages_withdate · Theme1','12pages_withdate · Theme2','NEW50_5_12pages_withdate']),
              ('12 стр БЕЗ дат',['12pages_nodate','NEW50_5_12pages_nodate']),
              ('12 стр наборы',['nabor28gotovyi · наборы','nabor-53 · наборы'])]:
    n=sum(len([d for d in D['doms'] if d['gname']==g]) for g in gs)
    dd=sum(len([d for d in D['doms'] if d['gname']==g])*(END-dt(LAUNCH[g])).total_seconds()/86400 for g in gs)
    reg=sum(1 for e in ev if GN.get(e['dom']) in gs and e['k']=='reg')
    dep=sum(1 for e in ev if GN.get(e['dom']) in gs and e['k']=='dep')
    print('%-18s дом %2d | дом·дней %5.1f | рег %2d | деп %d | рег/дом/дн %.3f'%(nm,n,dd,reg,dep,reg/dd))
