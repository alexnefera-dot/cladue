# Отчёт по выгрузке конверсий: домены с регистрациями и депозитами,
# их группа контента, день запуска и позиции на последнем известном замере.
import json,collections,os,statistics as st
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
EV=json.load(open(SP+'conv4.json'))
db=json.load(open(SP+'db.json'))
SN=json.load(open(SP+'snapr.json')); QD=SN['qd']

# --- новые пулы (31.08-02.09) из snapr
NEW={}
for p in SN['pools']:
    if p.get('excl'): continue
    s=p['snaps'][-1]
    for i,d in enumerate(p['doms']):
        rows=[r for r in s['rows'] if r[1]==i]
        brs=collections.defaultdict(lambda:[999,0,0])   # best,t10,t100
        for r in rows:
            b=QD[r[0]][1]
            if not b: continue
            e=brs[b]; e[0]=min(e[0],r[2]); e[1]+=r[2]<=10; e[2]+=1
        NEW[d]=dict(group=p['name'],cfg=f"{p['pages']} стр, {p['dates']}",zone=p['zone'],
            day=p['ltx'][:5],lab=s['lab'],
            t3=sum(1 for r in rows if r[2]<=3),t10=sum(1 for r in rows if r[2]<=10),
            t30=sum(1 for r in rows if r[2]<=30),t100=len(rows),
            best=min([r[2] for r in rows],default=None),brs=dict(brs))
def old(d):
    v=db.get(d)
    if not v: return None
    bs=v['b']
    brs={b:[x['best'],x['t10'],x['t100']] for b,x in bs.items()}
    return dict(group=v.get('group') or v.get('sheet',''),
        cfg=f"{v.get('pages','?')} стр, {v.get('dates','?')}"+(', '+v['img'] if v.get('img') else ''),
        zone=v.get('zone','?'),day=v.get('coh','?'),lab=v.get('lab','?'),
        t3=sum(x['t3'] for x in bs.values()),t10=sum(x['t10'] for x in bs.values()),
        t30=sum(x['t30'] for x in bs.values()),t100=sum(x['t100'] for x in bs.values()),
        best=min([x['best'] for x in bs.values() if x['best']],default=None),brs=brs)
# домены, опознанные вручную по реестру launches.md
MAN={
 '1893.team':('7page_1…_11 (партия 27.08)','7 стр, ?','27.08'),
 '4328.team':('7page_1…_11 (партия 27.08)','7 стр, ?','27.08'),
 'dprz.team':('7page_1…_11 (партия 27.08)','7 стр, ?','27.08'),
 'glhd.team':('7page_1…_11 (партия 27.08)','7 стр, ?','27.08'),
 'hjsf.team':('7page_1…_11 (партия 27.08)','7 стр, ?','27.08'),
 'ogax.team':('7page_3_1 (id 1006)','7 стр, ?','27.08'),
 'c5vt.team':('Generator_11page_old_27.08','11 стр, ?','27.08'),
 'k6m.team':('Generator_11page_old_27.08','11 стр, ?','27.08'),
 '3592.team':('старая база (до 19.08)','?','до 19.08'),
 'rtnm.team':('старая база (до 19.08)','?','до 19.08'),
 'bqvr.team':('старая база (до 19.08)','?','до 19.08'),
}
def info(d):
    v=NEW.get(d) or old(d)
    if v: return v
    m=MAN.get(d)
    if m: return dict(group=m[0],cfg=m[1],zone='.'+d.split('.')[-1],day=m[2],lab='—',
                      t3=None,t10=None,t30=None,t100=None,best=None,brs={},nopos=True)
    return None

reg=collections.Counter(); dep=collections.Counter(); subs=collections.defaultdict(collections.Counter)
first={}; geo=collections.defaultdict(collections.Counter)
for e in EV:
    d=e['dom']
    if e['type']=='reg': reg[d]+=1; subs[d][e['sub']]+=1
    else: dep[d]+=1
    geo[d][e['geo']]+=1
    first.setdefault(d,e['t']); first[d]=min(first[d],e['t'])

DOMS=sorted(set(reg)|set(dep),key=lambda d:(-reg[d],-dep[d],d))
print(f"Доменов с событиями: {len(DOMS)} | регистраций {sum(reg.values())} | депозитов {sum(dep.values())}")
kn=[d for d in DOMS if info(d)]
print(f"Из них опознано (есть группа и позиции): {len(kn)} | не опознано: {len(DOMS)-len(kn)}\n")

print(f"{'Домен':<16}{'рег':>4}{'деп':>4}  {'группа контента':<40}{'конфиг':<22}{'запуск':<12}"
      f"{'Т3':>4}{'Т10':>5}{'Т30':>5}{'сотня':>7}{'лучш':>6}  бренды с деньгами (позиция бренда)")
OUT=[]
for d in DOMS:
    v=info(d)
    if not v:
        print(f"{d:<16}{reg[d]:>4}{dep[d]:>4}  {'— не опознан, позиций нет —':<40}{'':<22}{'':<12}"
              f"{'':>4}{'':>5}{'':>5}{'':>7}{'':>6}  "
              +', '.join(f'{k} ({n})' for k,n in subs[d].most_common(4)))
        OUT.append(dict(dom=d,reg=reg[d],dep=dep[d],known=False)); continue
    if v.get('nopos'):
        print(f"{d:<16}{reg[d]:>4}{dep[d]:>4}  {v['group'][:40]:<40}{v['cfg'][:22]:<22}{str(v['day'])[:12]:<12}"
              f"{'—':>4}{'нет замеров':>12}{'':>10}  "+', '.join(f'{k} x{n}' for k,n in subs[d].most_common(4)))
        OUT.append(dict(dom=d,reg=reg[d],dep=dep[d],known=True,nopos=True,
            group=v['group'],cfg=v['cfg'],zone=v['zone'],day=v['day'],lab='—',
            t3=None,t10=None,t30=None,t100=None,best=None,
            subs=subs[d].most_common(),brpos={},geo=geo[d].most_common(3),first=first[d]))
        continue
    bb=[]
    for b,n in subs[d].most_common(5):
        e=v['brs'].get(b)
        bb.append(f"{b} x{n} [{'поз '+str(e[0]) if e and e[0]<999 else 'позиций нет'}]")
    print(f"{d:<16}{reg[d]:>4}{dep[d]:>4}  {v['group'][:40]:<40}{v['cfg'][:22]:<22}{str(v['day'])[:12]:<12}"
          f"{v['t3']:>4}{v['t10']:>5}{v['t30']:>5}{v['t100']:>7}{str(v['best'] or '—'):>6}  "+'; '.join(bb))
    OUT.append(dict(dom=d,reg=reg[d],dep=dep[d],known=True,**{k:v[k] for k in
        ('group','cfg','zone','day','lab','t3','t10','t30','t100','best')},
        subs=subs[d].most_common(),brpos={b:v['brs'].get(b,[None])[0] for b in subs[d]},
        geo=geo[d].most_common(3),first=first[d]))

print('\n=== Совпал ли бренд, который принёс деньги, с брендом, по которому домен стоит ===')
hit=miss=nopos=0; hitpos=[]
for o in OUT:
    if not o.get('known') or o.get('nopos'): continue
    for b,n in o['subs']:
        p=o['brpos'].get(b)
        if p is None or p==999: miss+=n
        else: hit+=n; hitpos.append(p)
print(f'  регистраций, у бренда которых на этом домене ЕСТЬ позиция в сотне: {hit}')
print(f'  регистраций, у бренда которых позиции нет вообще: {miss}')
if hitpos:
    print(f'  медиана позиции такого бренда: {st.median(hitpos):.0f}; '
          f'из них в десятке: {sum(1 for x in hitpos if x<=10)}, в тридцатке: {sum(1 for x in hitpos if x<=30)}')

print('\n=== Сводка по группам контента ===')
G=collections.defaultdict(lambda:[0,0,set()])
for o in OUT:
    g=o.get('group','— не опознано —')
    G[g][0]+=o['reg']; G[g][1]+=o['dep']; G[g][2].add(o['dom'])
print(f"{'Группа':<48}{'рег':>5}{'деп':>5}{'доменов':>9}")
for g,(r,dp,ds) in sorted(G.items(),key=lambda x:-x[1][0]):
    print(f"{g[:48]:<48}{r:>5}{dp:>5}{len(ds):>9}")

print('\n=== Сводка по дню запуска ===')
Dd=collections.defaultdict(lambda:[0,0,set()])
for o in OUT:
    k=str(o.get('day','— не опознано —'))
    Dd[k][0]+=o['reg']; Dd[k][1]+=o['dep']; Dd[k][2].add(o['dom'])
for k,(r,dp,ds) in sorted(Dd.items()):
    print(f"  {k:<22} рег {r:>3}  деп {dp:>2}  доменов {len(ds):>3}")

print('\n=== Депозиты поимённо ===')
for o in OUT:
    if o['dep']:
        v=info(o['dom']) or {}
        print(f"  {o['dom']:<16} деп {o['dep']}  рег {o['reg']}  "
              f"{str(v.get('group','—'))[:40]:<40} запуск {str(v.get('day','?'))}")
json.dump(OUT,open(SP+'convrep.json','w'),ensure_ascii=False)
