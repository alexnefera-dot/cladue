# Заход по группам: доля доменов, давших хотя бы одну регистрацию, + разрезы по конфигурации.
# Дописывает в wk.json ключи ghit (группы), cut (разрезы), cross (страницы x даты), scen (сценарии).
import json,collections,datetime as dt
db=json.load(open('db.json')); C=json.load(open('conv2.json')); A=json.load(open('age.json')); L=A['launch']
import os
E3=json.load(open('conv3.json')) if os.path.exists('conv3.json') else []
regs=[e for e in C['ev']+E3 if e['type']=='reg']; deps=[e for e in C['ev']+E3 if e['type']=='dep']
rd=collections.Counter(e['dom'] for e in regs); dp=collections.Counter(e['dom'] for e in deps)
P1=['2139.team','2483.team','ogax.team','byai.team','7186.team','4087.team','2084.team','2304.team','7440.team','0302.team']
P2=['bmtq.team','cnwv.team','dprz.team','fkxb.team','glhd.team','hjsf.team','1524.team','1893.team','2367.team','2745.team','4328.team']
OL=['3596.team','b8rn.team','c5vt.team','d3mw.team','f9kq.team','f9pb.team','h7nd.team','j2t.team','k6m.team','r9v.team']
CFG27={'7page_27.08 · партия 1':dict(src='7page, автор не указан',pages='7',dates='—',img='—',acc='—'),
       '7page_27.08 · партия 2':dict(src='7page, автор не указан',pages='7',dates='—',img='—',acc='—'),
       'Generator_11page_old_27.08':dict(src='наш генератор',pages='11',dates='—',img='старый стиль',acc='—')}
def info(d):
    if d in db and d!='базовый домен':
        v=db[d]; return v['group'],dict(src=v['src'],pages=v['pages'],dates=v['dates'],img=v['img'],acc=v['acc'])
    for g,ds in [('7page_27.08 · партия 1',P1),('7page_27.08 · партия 2',P2),('Generator_11page_old_27.08',OL)]:
        if d in ds: return g,CFG27[g]
    return None,None
def dd(s): return dt.date(2026,int(s[3:5]),int(s[:2]))
today=dt.date(2026,8,31)
G=collections.defaultdict(lambda:dict(n=0,w=0,reg=0,dep=0,ld=None,cfg=None))
for d in L:
    g,c=info(d)
    if not g: continue
    x=G[g]; x['n']+=1; x['reg']+=rd.get(d,0); x['dep']+=dp.get(d,0); x['ld']=L[d]; x['cfg']=c
    if rd.get(d,0): x['w']+=1
GH=[]
for g,v in G.items():
    age=(today-dd(v['ld'])).days
    GH.append(dict(g=g,ld=v['ld'],age=age,closed=age>=6,n=v['n'],w=v['w'],z=v['n']-v['w'],
        hit=round(100*v['w']/v['n']),Y=round(v['reg']/v['n'],2),reg=v['reg'],dep=v['dep'],
        per=round(v['reg']/v['w'],2) if v['w'] else 0,**v['cfg']))
GH.sort(key=lambda r:(-r['hit'],-r['Y']))
CL=[r for r in GH if r['closed'] and r['ld'] not in ('19.08','20.08')]
def cut(key,title):
    B=collections.defaultdict(lambda:[0,0,0])
    for r in CL:
        k=key(r)
        if k is None: continue
        B[k][0]+=r['n']; B[k][1]+=r['w']; B[k][2]+=round(r['Y']*r['n'])
    return dict(t=title,rows=[dict(k=k,n=n,w=w,hit=round(100*w/n),Y=round(rg/n,2))
        for k,(n,w,rg) in sorted(B.items(),key=lambda x:-x[1][1]/max(x[1][0],1))])
CUT=[cut(lambda r: r['pages']+' страниц' if r['pages'] in ('7','11','12') else None,'Объём текста'),
     cut(lambda r: r['dates'] if r['dates'] in ('с датами','без дат') else None,'Даты в тексте'),
     cut(lambda r: r['img'] if r['img'] in ('с картинками','без картинок') else None,'Картинки'),
     cut(lambda r: 'наш генератор' if 'генератор' in r['src'] else ('чужой контент' if 'чужой' in r['src']
         else ('наборы' if 'набор' in r['src'] else None)),'Источник контента')]
CROSS=cut(lambda r: (r['pages']+' стр · '+r['dates']) if r['pages'] in ('7','11','12')
          and r['dates'] in ('с датами','без дат') else None,'Объём × даты')
best=[r for r in CL if r['pages']=='12' and r['dates']=='без дат']
bn=sum(r['n'] for r in best); bw=sum(r['w'] for r in best); br=sum(round(r['Y']*r['n']) for r in best)
SCEN=[dict(k='текущая смесь',Y=0.42,need=95,live=571,hit=27),
      dict(k='только 12 страниц без дат',Y=round(br/bn,2),need=round(40/(br/bn)),
           live=round(40/(br/bn)*6),hit=round(100*bw/bn)),
      dict(k='только 7 страниц',Y=0.31,need=129,live=773,hit=24)]
W=json.load(open('wk.json'))
W.update(ghit=GH,cut=CUT,cross=CROSS,scen=SCEN,
         best=dict(n=bn,w=bw,reg=br,hit=round(100*bw/bn),Y=round(br/bn,2)))
json.dump(W,open('wk.json','w'),ensure_ascii=False)
print('групп',len(GH),'| лучшая конфигурация 12стр без дат:',W['best'])
for c in CUT: print(c['t'],[(r['k'],r['hit'],r['Y']) for r in c['rows']])
print('cross',[(r['k'],r['n'],r['hit'],r['Y']) for r in CROSS['rows']])
