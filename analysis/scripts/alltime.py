# Все конверсии за всю историю: три источника, дедуп, топ доменов и депозиты.
import json,collections,csv,datetime as dt,os,sys
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
AN='/home/user/cladue/analysis/'
E=[]
c2=json.load(open(SP+'conv2.json'))
for e in c2['ev']:
    E.append(dict(t=e['ts'][:16],type=e['type'],dom=e['dom'],sub=e.get('brand',''),
                  geo=e.get('geo',''),uid=e.get('uid'),src='conv2'))
for e in json.load(open(SP+'conv3.json')):
    E.append(dict(t=e['ts'][:16],type=e['type'],dom=e['dom'],sub=e.get('brand',''),
                  geo=e.get('geo',''),uid=e.get('uid'),src='conv3'))
for e in json.load(open(SP+'conv4.json')):
    E.append(dict(t=e['t'][:16],type=e['type'],dom=e['dom'],sub=e.get('sub',''),
                  geo=e.get('geo',''),uid=None,src='conv4'))
# дедуп: по (время, тип, домен, бренд) — uid есть не везде
seen=set(); EV=[]
for e in sorted(E,key=lambda x:(x['t'],x['dom'],x['type'],x['src'])):
    k=(e['t'],e['type'],e['dom'],e['sub'])
    if k in seen: continue
    seen.add(k); EV.append(e)
print(f"событий во всех источниках: {len(E)} → после дедупа: {len(EV)}")
print(f"регистраций {sum(1 for e in EV if e['type']=='reg')}, депозитов {sum(1 for e in EV if e['type']=='dep')}")
print(f"период: {min(e['t'] for e in EV)} — {max(e['t'] for e in EV)}")
json.dump(EV,open(SP+'convall.json','w'),ensure_ascii=False)

# ---- атрибуция домена к группе
db=json.load(open(SP+'db.json'))
SN=json.load(open(SP+'snapr.json')); QD=SN['qd']
NEW={}
for p in SN['pools']:
    if p.get('excl'): continue
    s=p['snaps'][-1]
    for i,d in enumerate(p['doms']):
        rows=[r for r in s['rows'] if r[1]==i]
        NEW[d]=dict(group=p['name'],cfg=f"{p['pages']} стр, {p['dates']}",day=p['ltx'][:5],
            t10=sum(1 for r in rows if r[2]<=10),t100=len(rows),
            best=min([r[2] for r in rows],default=None))
MAN={'1893.team':('7page_1…_11 (партия 27.08)','7 стр, ?','27.08'),
 '4328.team':('7page_1…_11 (партия 27.08)','7 стр, ?','27.08'),
 'dprz.team':('7page_1…_11 (партия 27.08)','7 стр, ?','27.08'),
 'glhd.team':('7page_1…_11 (партия 27.08)','7 стр, ?','27.08'),
 'hjsf.team':('7page_1…_11 (партия 27.08)','7 стр, ?','27.08'),
 'ogax.team':('7page_3_1 (id 1006)','7 стр, ?','27.08'),
 'c5vt.team':('Generator_11page_old_27.08','11 стр, ?','27.08'),
 'k6m.team':('Generator_11page_old_27.08','11 стр, ?','27.08'),
 '3592.team':('старая база (до 19.08)','?','до 19.08'),
 'rtnm.team':('старая база (до 19.08)','?','до 19.08'),
 'bqvr.team':('старая база (до 19.08)','?','до 19.08')}
def info(d):
    if d in NEW: return NEW[d]
    v=db.get(d)
    if v:
        bs=v['b']
        return dict(group=v.get('group') or v.get('sheet',''),
            cfg=f"{v.get('pages','?')} стр, {v.get('dates','?')}",day=v.get('coh','?'),
            t10=sum(x['t10'] for x in bs.values()),t100=sum(x['t100'] for x in bs.values()),
            best=min([x['best'] for x in bs.values() if x['best']],default=None))
    m=MAN.get(d)
    if m: return dict(group=m[0],cfg=m[1],day=m[2],t10=None,t100=None,best=None)
    return dict(group='не опознан',cfg='—',day='?',t10=None,t100=None,best=None)

reg=collections.Counter(); dep=collections.Counter()
subs=collections.defaultdict(collections.Counter); geo=collections.defaultdict(collections.Counter)
tt=collections.defaultdict(lambda:[None,None])
for e in EV:
    (reg if e['type']=='reg' else dep)[e['dom']]+=1
    if e['type']=='reg': subs[e['dom']][e['sub']]+=1
    geo[e['dom']][e['geo']]+=1
    a,b=tt[e['dom']]
    tt[e['dom']]=[min(a or e['t'],e['t']),max(b or e['t'],e['t'])]

ALL=sorted(set(reg)|set(dep))
print(f"\nдоменов с событиями за всю историю: {len(ALL)}")
def row(d):
    v=info(d)
    return dict(dom=d,reg=reg[d],dep=dep[d],**v,
        subs=subs[d].most_common(6),geo=geo[d].most_common(2),first=tt[d][0],last=tt[d][1])
ROWS=[row(d) for d in ALL]
json.dump(ROWS,open(SP+'alltime.json','w'),ensure_ascii=False)

def show(rows,title):
    print(f"\n=== {title} ===")
    print(f"{'Домен':<15}{'рег':>4}{'деп':>4}  {'группа':<44}{'конфиг':<20}{'запуск':<11}"
          f"{'Т10':>5}{'сотня':>7}{'лучш':>6}  бренды")
    for r in rows:
        print(f"{r['dom']:<15}{r['reg']:>4}{r['dep']:>4}  {str(r['group'])[:44]:<44}{str(r['cfg'])[:20]:<20}"
              f"{str(r['day'])[:11]:<11}{('—' if r['t10'] is None else r['t10']):>5}"
              f"{('—' if r['t100'] is None else r['t100']):>7}{str(r['best'] or '—'):>6}  "
              +', '.join(f"{b}{'×'+str(n) if n>1 else ''}" for b,n in r['subs'][:4]))
show(sorted(ROWS,key=lambda r:(-r['reg'],-r['dep']))[:25],'ТОП-25 ПО РЕГИСТРАЦИЯМ ЗА ВСЮ ИСТОРИЮ')
show(sorted([r for r in ROWS if r['dep']>=2],key=lambda r:(-r['dep'],-r['reg'])),'ДОМЕНЫ С ДВУМЯ И БОЛЕЕ ДЕПОЗИТАМИ')
d1=[r for r in ROWS if r['dep']==1]
print(f"\nдоменов ровно с одним депозитом: {len(d1)}; всего депозитов "
      f"{sum(r['dep'] for r in ROWS)} на {sum(1 for r in ROWS if r['dep'])} доменах")
print(f"\n=== Распределение доменов по числу регистраций ===")
c=collections.Counter(r['reg'] for r in ROWS)
for k in sorted(c,reverse=True): print(f"  {k} рег: {c[k]} доменов")
