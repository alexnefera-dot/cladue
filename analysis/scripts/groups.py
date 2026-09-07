# Данные для отчёта «Группы запуска и что они дали».
# Одна строка = одна группа (ветка) одного дня. Знаменатель — все домены группы.
import json,collections,re,glob,math,datetime as dt
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
AN='/home/user/cladue/analysis/'
BAD={'yandex.ru','','—','ru.search.yahoo.com','alice.yandex.ru','youtube.com'}
EV=[e for e in json.load(open(SP+'convall.json')) if e['dom'] not in BAD]
db=json.load(open(SP+'db.json')); SN=json.load(open(SP+'snapr.json'))
TODAY=dt.date(2026,9,7); CURVE=[0,18,49,75,90,95,99]; DATA0=dt.date(2026,8,21)

reg=collections.Counter(); dep=collections.Counter()
brands=collections.defaultdict(collections.Counter)
for e in EV:
    (reg if e['type']=='reg' else dep)[e['dom']]+=1
    if e['type']=='reg' and e['sub']: brands[e['dom']][e['sub']]+=1

def bucket(src,g=''):
    src=str(src or ''); g=str(g or '')
    if 'наш генератор' in src or g.startswith('Generator'): return 'генератор'
    if 'чужой контент' in src or 'NEW' in g: return 'готовый пак'
    if 'наборы' in src or 'nabor' in g.lower() or 'аккаунт' in g or 'Вебмастера' in g: return 'наборы'
    if 'выдач' in src or 'Выдача' in g: return 'выдача'
    return 'не указано'

DAY={}; GRP={}; POS={}; SRC={}
for d,v in db.items():
    if d=='базовый домен': continue
    DAY[d]=str(v.get('made'))[:5]; GRP[d]=v.get('group') or v.get('sheet','')
    POS[d]=sum(x['t10'] for x in v['b'].values()); SRC[d]=bucket(v.get('src'),GRP[d])
for p in SN['pools']:
    if p.get('excl'): continue
    s=p['snaps'][-1]
    for i,x in enumerate(p['doms']):
        DAY[x]=p['ltx'][:5]; GRP[x]=p['name']; SRC[x]=bucket('',p['name'])
        POS[x]=sum(1 for r in s['rows'] if r[1]==i and r[2]<=10)
for names,g in {'bmtq cnwv dprz fkxb glhd hjsf 1524 1893 2367 2745 4328':'7page_1…_11 (партия 2)',
  '2139 2483 ogax byai 7186 4087 2084 2304 7440 0302':'7page_1_1…_10_1',
  '3596 b8rn c5vt d3mw f9kq f9pb h7nd j2t k6m r9v':'Generator_11page_old_27.08'}.items():
    for x in names.split():
        DAY[x+'.team']='27.08'; GRP[x+'.team']=g; SRC[x+'.team']=bucket('',g)
for f in sorted(glob.glob(AN+'launch_*.txt')):
    if '_flat' in f: continue
    md=re.search(r'launch_(\d\d\.\d\d)',f)
    if not md: continue
    day=md.group(1); cur=None
    for l in open(f):
        l=l.rstrip()
        if l.startswith('## '): cur=l[3:].strip()
        elif re.match(r'^[a-z0-9\-]+\.[a-z]+$',l.strip()):
            x=l.strip()
            if x in DAY: continue
            DAY[x]=day; GRP[x]=cur or day; SRC[x]=bucket('',cur or '')

def dat(s):
    m=re.match(r'(\d\d)\.(\d\d)',str(s))
    return dt.date(2026,int(m.group(2)),int(m.group(1))) if m else None
def clean(g):
    g=re.sub(r'\s*[—,(]\s*(id|создан|\d+\s*дом)[^,)]*\)?','',g or '')
    return re.sub(r'_?\d*…_\d+','',g).strip(' _·,')
def pages(g):
    m=re.search(r'(\d+)\s*(?:pages|стр|page)',g)
    if m: return m.group(1)
    return None
def dates(g):
    if 'withdate' in g or 'с датами' in g: return 'с датами'
    if 'nodate' in g or 'без дат' in g: return 'без дат'
    return None

G=collections.defaultdict(list)
for d in DAY:
    if dat(DAY[d]): G[(DAY[d],clean(GRP[d]))].append(d)
# домены, у которых есть конверсии, но нет ни дня, ни группы
orph=sorted({e['dom'] for e in EV} - set(DAY))
if orph: G[('?','Списка запуска не присылали')]=orph

ROWS=[]
for (day,g),doms in G.items():
    a=dat(day); age=(TODAY-a).days if a else None
    pct=(CURVE[min(age,6)] if age<6 else 100) if a else None
    lost=max(0,(DATA0-a).days) if a else 0
    q=('усечено' if lost else ('открыто' if age<6 else 'закрыто')) if a else 'нет дня'
    npos=[d for d in doms if d in POS]
    win=[d for d in doms if reg[d]]
    ROWS.append(dict(day=day,g=g,n=len(doms),w=len(win),r=sum(reg[d] for d in doms),
        dep=sum(dep[d] for d in doms),share=100*len(win)/len(doms),
        age=age,pct=pct,q=q,
        pg=pages(g),dt=dates(g),src=collections.Counter(SRC.get(d,'не указано') for d in doms).most_common(1)[0][0],
        t10=round(sum(POS[d] for d in npos)/len(npos),1) if npos else None,
        zones=[[k,v] for k,v in collections.Counter('.'+d.split('.')[-1] for d in doms).most_common()],
        doms=sorted([dict(d=d,r=reg[d],p=dep[d],t10=POS.get(d),
                          br=[[b,n] for b,n in brands[d].most_common()]) for d in doms],
                    key=lambda x:(-x['p'],-x['r'],x['d']))))
ROWS.sort(key=lambda x:(-x['r'],-x['share'],x['day']))
assert sum(r['r'] for r in ROWS)==sum(reg.values()), 'потеряны регистрации'
TOT=dict(g=len(ROWS),n=sum(r['n'] for r in ROWS),r=sum(r['r'] for r in ROWS),
         dep=sum(r['dep'] for r in ROWS),w=sum(r['w'] for r in ROWS),
         closed=sum(1 for r in ROWS if r['q']=='закрыто'),
         zero=sum(1 for r in ROWS if r['r']==0))
json.dump(dict(rows=ROWS,tot=TOT,built=dt.datetime.now().strftime('%d.%m %H:%M')),
          open(SP+'groups.json','w'),ensure_ascii=False)
print(f"групп {TOT['g']}, доменов {TOT['n']}, регистраций {TOT['r']}, депозитов {TOT['dep']}")
print(f"групп совсем без регистраций: {TOT['zero']}")
for r in ROWS[:15]:
    print(f"  {r['day']}  {r['g'][:46]:<48}{r['n']:>3} дом  {r['w']:>2} с рег  {r['share']:>5.1f}%  рег {r['r']:>2}  деп {r['dep']}  {r['q']}")
