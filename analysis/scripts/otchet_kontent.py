"""Отчёт: регистрации по дням и контентам."""
import csv,collections,re,glob,json
AN='/home/user/cladue/analysis/'
rows=[r for r in csv.DictReader(open(AN+'konversii_7dney.csv',encoding='utf-8-sig'))]
for r in rows:
    r['base']='.'.join(r['source'].split('.')[1:]); r['day']=r['datetime'][8:10]+'.09'

grp={}; size=collections.Counter(); gday={}
for f in sorted(glob.glob(AN+'launch_*.txt')):
    if '_flat' in f: continue
    m=re.search(r'launch_(\d\d\.\d\d)',f)
    if not m: continue
    cur=None
    for l in open(f):
        l=l.rstrip()
        if l.startswith('## '):
            name=l[3:].split(' — ')[0]; cur=name; gday[name]=m.group(1)
        elif re.fullmatch(r'[a-z0-9][a-z0-9.-]*\.[a-z]+', l.strip()) and cur:
            if l.strip() not in grp: grp[l.strip()]=cur; size[cur]+=1

DAYS=[f'{d:02d}.09' for d in range(9,17)]
reg=collections.defaultdict(collections.Counter); dep=collections.Counter()
domhit=collections.defaultdict(set)
for r in rows:
    g=grp.get(r['base'])
    if not g: g='— вне списков'
    if r['event']=='reg': reg[g][r['day']]+=1
    else: dep[g]+=1
    domhit[g].add(r['base'])

out=[]
for g in set(list(reg)+list(dep)):
    tot=sum(reg[g].values())
    out.append(dict(group=g, day=gday.get(g,'—'), size=size.get(g,0),
                    reg=tot, dep=dep[g], doms=len(domhit[g]),
                    by_day={d:reg[g][d] for d in DAYS if reg[g][d]}))
out.sort(key=lambda x:(-x['reg'],-x['dep']))

print(f"{'группа контента':<44}{'зап':<7}{'дом':>4}{'с конв':>7}{'рег':>5}{'ФД':>4}{'рег/дом':>9}")
print('-'*82)
for o in out:
    rpd=f"{o['reg']/o['size']:.3f}" if o['size'] else '—'
    print(f"{o['group'][:42]:<44}{o['day']:<7}{o['size']:>4}{o['doms']:>7}{o['reg']:>5}{o['dep']:>4}{rpd:>9}")
print('-'*82)
print(f"{'ИТОГО':<44}{'':<7}{sum(o['size'] for o in out):>4}"
      f"{sum(o['doms'] for o in out):>7}{sum(o['reg'] for o in out):>5}{sum(o['dep'] for o in out):>4}")

print("\n\nРЕГИСТРАЦИИ ПО ДНЯМ")
print(f"{'группа':<44}"+''.join(f"{d[:2]:>4}" for d in DAYS)+f"{'всего':>7}")
print('-'*82)
for o in out:
    if not o['reg']: continue
    print(f"{o['group'][:42]:<44}"+''.join(f"{o['by_day'].get(d,'·'):>4}" for d in DAYS)+f"{o['reg']:>7}")
print('-'*82)
tot={d:sum(reg[g][d] for g in reg) for d in DAYS}
print(f"{'ВСЕГО':<44}"+''.join(f"{tot[d]:>4}" for d in DAYS)+f"{sum(tot.values()):>7}")
json.dump(out,open(AN+'otchet_kontent.json','w'),ensure_ascii=False,indent=1)
