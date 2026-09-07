# Разбор последней выгрузки конверсий: только её события, три разреза и полный список.
import json,collections,re,datetime as dt
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
BAD={'yandex.ru','—','ru.search.yahoo.com','alice.yandex.ru'}
RAW=json.load(open(SP+'conv7.json'))
M=json.load(open(SP+'dommap.json'))
# реестр запусков точнее общей карты: там ветка названа полностью (7/12 стр, даты).
# Форматы заголовков разные: где-то одна строка "## NEW50_3_7pages...", где-то основная
# строка и под ней уточнение "## 12 стр, С ДАТАМИ, семейство NEW50", где-то только "# ...".
import glob
def hdr(h):
    h=re.split(r'\s+—\s+',h.strip())[0]                      # всё после тире — это id/время/зоны
    h=re.sub(r',\s*(id\s*\d|создан)[^,)]*','',h)             # хвосты внутри скобок
    return h.strip(' ,')
BRANCH=re.compile(r'NEW|Generator|nabor|Набор|Выдача|troyka|struktura|trikomplekt|kruzhevn|'
                  r'degtyarn|tesemochn|shponn|drobiln|bortnich|solodovn|7page|12page|11page')
for f in sorted(glob.glob('/home/user/cladue/analysis/launch_*.txt')):
    if '_flat' in f: continue
    md=re.search(r'launch_(\d\d\.\d\d)',f)
    if not md: continue
    day=md.group(1); main=None; extra=None; prev_was_hdr=False
    for l in open(f):
        l=l.rstrip()
        if l.startswith('## '):
            h=hdr(l[3:])
            # заголовок сразу за заголовком (без доменов между) — это уточнение к нему,
            # а не новая ветка; иначе начинается новая ветка
            if prev_was_hdr and main: extra=h
            else: main=h; extra=None
            prev_was_hdr=True
        elif l.startswith('# ') and main is None:
            h=hdr(l[2:])
            if BRANCH.search(h): main=h
        elif re.match(r'^[a-z0-9\-]+\.[a-z]+$',l.strip()):
            prev_was_hdr=False
            name=main if main else extra
            if not name: continue                      # заголовков нет — оставляем старую карту
            # уточнение дописываем, только если в самом имени ветки нет страниц/дат
            if main and extra and not re.search(r'\d+\s*(pages|page|стр)',main): name=main+' · '+extra
            M[l.strip()]=dict(g=name,day=day)

def clean(g):
    g=re.sub(r'\s*[—,(]\s*(id|создан|\d+\s*дом)[^,)]*\)?','',g or '')
    return re.sub(r'_?\d*…_\d+','',g).strip(' _·,')
def pages(g):
    m=re.search(r'(\d+)\s*(?:pages|стр|page)',g); return m.group(1) if m else None
def dates(g):
    if 'withdate' in g or 'с датами' in g: return 'с датами'
    if 'nodate' in g or 'без дат' in g: return 'без дат'
    return None
def src(g):
    if g.startswith('Generator'): return 'генератор'
    if 'NEW' in g: return 'готовый пак'
    if 'nabor' in g.lower() or 'Набор' in g: return 'наборы'
    if 'Выдача' in g: return 'выдача'
    return None
EV=[]
for e in RAW:
    if e['dom'] in BAD: continue
    m=M.get(e['dom']); g=clean(m['g']) if m else None
    EV.append(dict(t=e['t'],type=e['type'],dom=e['dom'],br=e['sub'],geo=e['geo'],
                   zone='.'+e['dom'].split('.')[-1],g=g,day=m['day'] if m else None,
                   pg=pages(g) if g else None,dt=dates(g) if g else None,src=src(g) if g else None))
EV.sort(key=lambda x:x['t'],reverse=True)
skip=[e for e in RAW if e['dom'] in BAD]

def cut(key,label):
    a=collections.defaultdict(lambda:{'r':0,'d':0,'doms':set()})
    for e in EV:
        k=key(e); x=a[k if k is not None else '— не заведено —']
        x['r']+= e['type']=='reg'; x['d']+= e['type']=='dep'; x['doms'].add(e['dom'])
    return dict(label=label,rows=sorted([dict(k=k,r=v['r'],d=v['d'],n=len(v['doms']))
        for k,v in a.items()],key=lambda x:(-(x['r']+x['d']),-x['n'])))

D=dict(ev=EV,n=len(RAW),reg=sum(1 for e in EV if e['type']=='reg'),
       dep=sum(1 for e in EV if e['type']=='dep'),doms=len({e['dom'] for e in EV}),
       skip=[dict(dom=e['dom'],type=e['type'],t=e['t'],eng=e['eng']) for e in skip],
       days=sorted({e['t'][:10] for e in EV}),
       cuts=[cut(lambda e:e['g'],'Группа контента'),
             cut(lambda e:e['zone'],'Доменная зона'),
             cut(lambda e:e['day'],'День запуска домена'),
             cut(lambda e:e['pg'] and e['pg']+' страниц','Число страниц'),
             cut(lambda e:e['dt'],'Даты в имени'),
             cut(lambda e:e['src'],'Откуда контент'),
             cut(lambda e:e['geo'],'Гео'),
             cut(lambda e:e['br'],'Бренд')],
       built=dt.datetime.now().strftime('%d.%m %H:%M'))
json.dump(D,open(SP+'e50.json','w'),ensure_ascii=False)
print(f"{D['n']} строк → {len(EV)} привязано ({D['reg']} рег, {D['dep']} деп) на {D['doms']} доменах")
for c in D['cuts'][:3]:
    print(f"\n{c['label']}:")
    for r in c['rows']: print(f"   {str(r['k'])[:44]:<46} рег {r['r']:>2} деп {r['d']:>2}  доменов {r['n']}")
