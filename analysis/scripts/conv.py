import openpyxl,io,collections,json,re,datetime
wb=openpyxl.load_workbook(io.BytesIO(open('conv.xlsx','rb').read()),data_only=True)
rows=[r for r in wb['Sheet1'].iter_rows(values_only=True) if r[0]]
D=json.load(open('flat.json',encoding='utf-8'))
G={d['d']:d for d in D['doms']}
def split(h):
    h=str(h).strip().lower(); p=h.split('.')
    return ('.'.join(p[:-2]), '.'.join(p[-2:]))
ev=[]
for r in rows:
    br,dom=split(r[5])
    ev.append({'t':r[0],'k':r[1],'cid':r[3],'c':r[4],'br':br,'dom':dom,'ref':r[6]})
doms=collections.Counter(e['dom'] for e in ev)
print('уникальных доменов',len(doms))
known=[d for d in doms if d in G]
print('из них в реестре групп',len(known),'| событий по ним',sum(doms[d] for d in known))
print('не в реестре',len(doms)-len(known),'| событий',sum(v for d,v in doms.items() if d not in G))
print()
print('--- ПО ГРУППАМ ---')
gg=collections.defaultdict(lambda: {'reg':0,'dep':0,'doms':set(),'brands':collections.Counter(),'first':None,'last':None})
for e in ev:
    g=G[e['dom']]['gname'] if e['dom'] in G else 'НЕ В РЕЕСТРЕ'
    a=gg[g]; a[e['k']]+=1; a['doms'].add(e['dom']); a['brands'][e['br']]+=1
    a['first']=min(a['first'],e['t']) if a['first'] else e['t']
    a['last']=max(a['last'],e['t']) if a['last'] else e['t']
tot={k:len([d for d in D['doms'] if d['gname']==k]) for k in set(d['gname'] for d in D['doms'])}
out=sorted(gg.items(), key=lambda x:-(x[1]['reg']+x[1]['dep']))
print('%-38s %4s %4s %5s %6s %8s  %s'%('группа','рег','деп','дом','всего','рег/дом','период'))
for g,a in out:
    n=tot.get(g,0)
    print('%-38s %4d %4d %3d/%-3d %5d %8s  %s → %s'%(g,a['reg'],a['dep'],len(a['doms']),n,a['reg']+a['dep'],
        ('%.1f'%(a['reg']/n)) if n else '—',a['first'].strftime('%d.%m'),a['last'].strftime('%d.%m')))

print()
print('--- ДОМЕНЫ ИЗ РЕЕСТРА ---')
dd=collections.defaultdict(lambda: collections.Counter())
dbr=collections.defaultdict(collections.Counter)
for e in ev:
    dd[e['dom']][e['k']]+=1; dbr[e['dom']][e['br']]+=1
kn=[(d,c) for d,c in dd.items() if d in G]
kn.sort(key=lambda x:-(x[1]['reg']+x[1]['dep']))
print('%-14s %-32s %4s %4s %5s %5s %5s  %s'%('домен','группа','рег','деп','Т10','Т3','ВЧ+СЧ','бренды'))
for d,c in kn:
    g=G[d]
    print('%-14s %-32s %4d %4d %5d %5d %5d  %s'%(d,g['gname'][:32],c['reg'],c['dep'],g['t10'],g['t3'],g['vch']+g['sch'],
      ', '.join('%s×%d'%(b,n) for b,n in dbr[d].most_common(5))))
print()
print('--- ДОМЕНЫ ВНЕ РЕЕСТРА (старые запуски) ---')
un=[(d,c) for d,c in dd.items() if d not in G]
un.sort(key=lambda x:-(x[1]['reg']+x[1]['dep']))
print('%-16s %4s %4s  %-22s %s'%('домен','рег','деп','период','бренды'))
for d,c in un[:30]:
    ts=[e['t'] for e in ev if e['dom']==d]
    print('%-16s %4d %4d  %-22s %s'%(d,c['reg'],c['dep'],
      min(ts).strftime('%d.%m')+' → '+max(ts).strftime('%d.%m'),
      ', '.join('%s×%d'%(b,n) for b,n in dbr[d].most_common(4))))
print('... всего вне реестра доменов:',len(un))
print()
print('--- ЗОНЫ (по всем конверсиям) ---')
zc=collections.defaultdict(collections.Counter)
for e in ev: zc['.'+e['dom'].split('.')[-1]][e['k']]+=1
for z,c in sorted(zc.items(),key=lambda x:-(x[1]['reg']+x[1]['dep'])):
    print('  %-8s рег %3d деп %3d'%(z,c['reg'],c['dep']))
print()
print('--- БРЕНДЫ ---')
bc=collections.defaultdict(collections.Counter)
for e in ev: bc[e['br']][e['k']]+=1
for b,c in sorted(bc.items(),key=lambda x:-(x[1]['reg']+x[1]['dep']))[:20]:
    print('  %-16s рег %3d деп %3d'%(b,c['reg'],c['dep']))
