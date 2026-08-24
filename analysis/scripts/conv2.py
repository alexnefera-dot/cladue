import openpyxl,io,collections,json,datetime
wb=openpyxl.load_workbook(io.BytesIO(open('conv.xlsx','rb').read()),data_only=True)
rows=[r for r in wb['Sheet1'].iter_rows(values_only=True) if r[0]]
D=json.load(open('flat.json',encoding='utf-8'))
G={d['d']:d for d in D['doms']}
SE=('yandex.ru','yahoo.com','yandex.kz','ya.ru')
ev=[]
for r in rows:
    h=str(r[5]).strip().lower(); p=h.split('.')
    dom='.'.join(p[-2:])
    if any(h.endswith(s) for s in SE) and len(p)<=3 and p[0] in ('','alice','ru') or h in ('yandex.ru','ru.search.yahoo.com','alice.yandex.ru'): continue
    ev.append({'t':r[0],'k':r[1],'br':'.'.join(p[:-2]),'dom':dom})
print('привязанных событий',len(ev))
LAUNCH={
 'Generator_11page':'20.08 01:25','7page_yandex':'20.08 01:25','Generator_11page_2':'20.08 01:25',
 'Generator_v5':'20.08 01:25','Generator_v4_2':'20.08 01:25','generator v4':'20.08 01:25',
 '12pages_withdate · Theme1':'20.08 17:00','12pages_withdate · Theme2':'20.08 17:00',
 '12pages_nodate':'20.08 17:00','7pages_nodate':'20.08 17:00',
 'kostoreznaya1 · имена':'20.08 17:00','nabor28gotovyi · наборы':'20.08 17:00',
 'Generation 50':'20.08 22:00','Generator_11page_21.08 (обе партии)':'22.08 01:18',
 'nabor-53 · наборы':'22.08 01:18','NEW50_5_12pages_withdate':'22.08 01:18',
 'NEW50_5_7pages_withdate':'22.08 01:18','Generator_11page_img':'22.08 23:30',
 'NEW50_5_12pages_nodate':'22.08 23:04','NEW50_5_7pages_nodate':'22.08 23:04'}
END=datetime.datetime(2026,8,24,12,15)
def dt(s):
    d,t=s.split(); dd,mm=d.split('.'); hh,mi=t.split(':')
    return datetime.datetime(2026,int(mm),int(dd),int(hh),int(mi))
gg=collections.defaultdict(lambda: collections.Counter())
gdom=collections.defaultdict(set)
for e in ev:
    if e['dom'] not in G: continue
    g=G[e['dom']]['gname']; gg[g][e['k']]+=1; gdom[g].add(e['dom'])
gstats={}
for k,Gr in D['groups'].items(): gstats[Gr['name']]=Gr
res=[]
for g,L in LAUNCH.items():
    n=len([d for d in D['doms'] if d['gname']==g])
    days=(END-dt(L)).total_seconds()/86400
    c=gg[g]; reg=c['reg']; dep=c['dep']
    S=gstats[g]
    t10=sum(d['t10'] for d in D['doms'] if d['gname']==g)
    res.append((g,n,round(days,1),reg,dep,len(gdom[g]),reg/n/days,t10, (reg/t10*100) if t10 else None))
res.sort(key=lambda x:-x[6])
print()
print('%-38s %3s %5s %4s %4s %6s %9s %6s %8s'%('группа','дом','дней','рег','деп','с конв','рег/дом/дн','Т10','рег/100Т10'))
for g,n,days,reg,dep,nd,rpd,t10,r100 in res:
    print('%-38s %3d %5.1f %4d %4d %3d/%-3d %9.3f %6d %8s'%(g,n,days,reg,dep,nd,n,rpd,t10,('%.1f'%r100) if r100 is not None else '—'))
