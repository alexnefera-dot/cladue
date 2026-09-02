# Данные для отчёта «Последние запуски по съёмам»: пулы 31.08 и 01.09,
# все съёмы каждого пула, бренды/ключи/вложенность/страницы на каждом съёме.
import json,re,csv,collections,statistics as st,datetime as dt,sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import p01

SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
FILES=['L31.xlsx','L01.xlsx','L02.xlsx','L03.xlsx','L04.xlsx']
AN='/home/user/cladue/analysis/'

# ---- ключи: бренд, тир, частотность
TIER={}; VOL={}
with open(AN+'keys/keys_stats.csv',encoding='utf-8-sig') as f:
    for r in csv.DictReader(f,delimiter=';'):
        TIER[r['ключ'].strip()]=(r['бренд'],r['тир'])
        try: VOL[r['бренд']]=int(r['частотность'])
        except: pass

# ---- сбор всех съёмов по листам (поздний файл перекрывает ранний)
SH=collections.OrderedDict()
for fn in FILES:
    O,_=p01.parse(SP+fn)
    for sn,snaps in O.items():
        d=SH.setdefault(sn.strip(),{})
        for s in snaps: d[s['lab']]=s

def ts(lab):
    m=re.match(r'(\d\d)\.(\d\d)\s+(\d\d):(\d\d)',lab)
    return dt.datetime(2026,int(m.group(2)),int(m.group(1)),int(m.group(3)),int(m.group(4))) if m else None

# ---- пулы
def L(s): return dt.datetime.strptime('2026.'+s,'%Y.%d.%m %H:%M')
POOLS=[
 dict(id='com', sheet='Generator_11page_test .com (ru', name='Generator_11page_test · .com',
      plat='dorgen com', ids='1055-1063', pages='11', dates='?', cap='потолок 20',
      lt=L('31.08 16:39'), ltx='31.08 16:39 (запуск)', zone='.team',
      note='Первый пул с ограничением вложенности до 20. Домены в зоне .team, платформа dorgen com.'),
 dict(id='net', sheet='Generator_11page_test .net (ru', name='nabor-244…253 · .net',
      plat='dorgen.net', ids='nabor-244…253', pages='не прислано', dates='?', cap='без потолка',
      lt=L('31.08 21:00'), ltx='31.08 вечер, точное время не прислано', zone='.team',
      note='Пул без ограничения вложенности, другая платформа. Время запуска известно приблизительно — возраст на съёмах условный.'),
 dict(id='p12nd', sheet='01.09#1', name='NEW50_12pages_nodate_01.09 · .casino',
      plat='dorgen com', ids='1110-1117', pages='12', dates='без дат', cap='потолок 20',
      lt=L('01.09 17:07'), ltx='01.09 17:07 (создан)', zone='.casino',
      doms=['tghc.casino','lrwo.casino','u9y.casino','vgti.casino','quu.casino','tfys.casino','stma.casino','baiu.casino'],
      note='Единственная ветка без дат в тексте. Прямой контроль к ветке 12 страниц с датами в той же зоне.'),
 dict(id='p12wd', sheet='01.09#1', name='NEW50_12pages_withdate_01.09_11…_17 · .casino',
      plat='dorgen com', ids='1103-1109', pages='12', dates='с датами', cap='потолок 20',
      lt=L('01.09 17:06'), ltx='01.09 17:06 (создан)', zone='.casino',
      doms=['rodl.casino','j1j.casino','x9d7.casino','w0w3.casino','unxn.casino','llvm.casino','gwrl.casino'],
      note='Контроль к ветке без дат: та же зона, те же 12 страниц, разница только в датах.'),
 dict(id='nab', sheet='01.09#1', name='nabory264268_01.09 · .team',
      plat='dorgen com', ids='1144-1147', pages='не прислано', dates='?', cap='потолок 20',
      lt=L('01.09 17:33'), ltx='01.09 17:33 (создан)', zone='.team',
      doms=['32gf.team','k3u.team','m8t.team','p2v.team'],
      note='Наборы. Число страниц и наличие дат не присланы.'),
 dict(id='p12wt', sheet='01.09#2', name='NEW50_12pages_withdate_01.09_1…_6 · .team/.lol',
      plat='dorgen com', ids='1093-1098', pages='12', dates='с датами', cap='потолок 20',
      lt=L('01.09 17:06'), ltx='01.09 17:06 (создан)', zone='.team/.lol',
      doms=['l5n.team','0403.lol','1185.lol','6348.team','7612.team','7925.team'],
      note='Та же конфигурация, что и .casino-ветка с датами, но другая зона — парный тест зоны.'),
 dict(id='p7wt', sheet='01.09#2', name='NEW50_7pages_withdate_01.09_1…_6 · .team/.lol',
      plat='dorgen com', ids='1118-1123', pages='7', dates='с датами', cap='потолок 20',
      lt=L('01.09 17:07'), ltx='01.09 17:07 (создан)', zone='.team/.lol',
      doms=['0864.team','pbfj.team','rvue.team','mmbr.team','q7a.lol','rvue.lol'],
      note='Та же зона и даты, что у ветки выше, но 7 страниц вместо 12 — парный тест числа страниц.'),
 dict(id='apex', sheet='apex, banda', name='apex/banda · узкое ядро 70 ключей',
      plat='dorgen com', ids='1055-1063', pages='11', dates='?', cap='потолок 20',
      lt=L('31.08 16:39'), ltx='31.08 16:39 (запуск)', zone='.team', excl=True,
      note='Не отдельный запуск: те же 9 доменов пула .com, но снятые по узкому ядру из 70 ключей двух брендов. В общие итоги не входит.'),
]

def parts(u):
    if not isinstance(u,str): return None,None,None
    rest=u.split('://',1)[-1]; host=rest.split('/',1)[0]
    path='/'+rest.split('/',1)[1] if '/' in rest else '/'
    segs=[s for s in path.split('/') if s]
    pg=[s for s in segs if s!='ru']
    return host,('/'+'/'.join(pg) if pg else '/'),len([s for s in segs if s=='ru'])

QD={}; PD={}
def qi(q):
    if q not in QD:
        b,t=TIER.get(q,(None,None))
        QD[q]=dict(i=len(QD),q=q,b=b,t=t,v=VOL.get(b,0))
    return QD[q]['i']
def pgi(p):
    p=p or '/'
    if p not in PD: PD[p]=len(PD)
    return PD[p]

OUT=[]
for cfg in POOLS:
    sh=SH.get(cfg['sheet'])
    if not sh: continue
    labs=sorted(sh,key=lambda l:ts(l))
    doms=cfg.get('doms') or sh[labs[0]]['doms']
    snaps=[]
    for lab in labs:
        s=sh[lab]
        age=round((ts(lab)-cfg['lt']).total_seconds()/3600,1)
        dd={}; rows=[]; brc=collections.defaultdict(lambda:[0,0,0,set()]); tic=collections.defaultdict(lambda:[0,0])
        for d in doms:
            ks=s['per'].get(d,[])
            deps=[k['d'] for k in ks if k['d'] is not None]
            pgs=set(); subs=set()
            for k in ks:
                ho,pg,dp=parts(k['u'])
                if pg: pgs.add(pg)
                if ho: subs.add(ho.split('.')[0])
                j=qi(k['q']); m=QD[k['q']]
                rows.append([j,doms.index(d),k['p'],(dp if dp is not None else -1),pgi(pg)])
                if m['b']:
                    e=brc[m['b']]
                    if k['p']<=10: e[0]+=1
                    if k['p']<=30: e[1]+=1
                    e[2]+=1; e[3].add(d)
                if m['t']:
                    tic[m['t']][1]+=1
                    if k['p']<=10: tic[m['t']][0]+=1
            f=lambda n: sum(1 for k in ks if k['p']<=n)
            bk=min(ks,key=lambda k:k['p']) if ks else None
            dd[d]=dict(t3=f(3),t10=f(10),t30=f(30),t100=len(ks),
                       bu=(bk['u'] if bk else None),
                       best=min([k['p'] for k in ks],default=None),
                       dmin=min(deps) if deps else None,
                       dmed=round(st.median(deps)) if deps else None,
                       dmax=max(deps) if deps else None,
                       npg=len(pgs),nsub=len(subs))
        t10s=[dd[d]['t10'] for d in doms]
        tot=dict(t3=sum(dd[d]['t3'] for d in doms),t10=sum(t10s),
                 t30=sum(dd[d]['t30'] for d in doms),t100=sum(dd[d]['t100'] for d in doms),
                 med=st.median(t10s) if t10s else 0,
                 hit=sum(1 for x in t10s if x>0),
                 nolead=(round((sum(t10s)-max(t10s))/(len(t10s)-1),2) if len(t10s)>1 else None))
        alld=[k['d'] for d in doms for k in s['per'].get(d,[]) if k['d'] is not None]
        tot['dmed']=round(st.median(alld)) if alld else None
        tot['dmax']=max(alld) if alld else None
        br=sorted(([b,v[0],v[1],v[2],len(v[3])] for b,v in brc.items()),key=lambda r:(-r[1],-r[2],-r[3]))
        snaps.append(dict(lab=lab,age=age,tot=tot,dom=dd,br=br,
                          tier=[[t,v[0],v[1]] for t,v in sorted(tic.items())],
                          rows=rows))
    OUT.append(dict(**{k:v for k,v in cfg.items() if k not in ('lt','sheet','doms')},
                    doms=doms,snaps=snaps,nmax=max(len(p['snaps']) for p in [dict(snaps=snaps)])))

DATA=dict(pools=OUT,
          qd=[[QD[q]['q'],QD[q]['b'],QD[q]['t'],QD[q]['v']] for q in sorted(QD,key=lambda x:QD[x]['i'])],
          pd=[p for p,_ in sorted(PD.items(),key=lambda x:x[1])],
          built=dt.datetime.now().strftime('%d.%m %H:%M'),
          nsnap=max(len(p['snaps']) for p in OUT))
json.dump(DATA,open(SP+'snapr.json','w'),ensure_ascii=False,separators=(',',':'))
print('пулов',len(OUT),'ключей',len(QD),'страниц',len(PD),
      'размер',round(os.path.getsize(SP+'snapr.json')/1024),'КБ')
for p in OUT:
    print(f"  {p['name'][:46]:<46} дом {len(p['doms']):>2}  съёмов {len(p['snaps'])}  "
          +' | '.join(f"{s['lab']} +{s['age']}ч Т10={s['tot']['t10']}" for s in p['snaps']))
