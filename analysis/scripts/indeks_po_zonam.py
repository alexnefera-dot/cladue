import json, glob, collections, datetime as dt
T=dt.datetime.fromisoformat
site={}
for p in sorted(glob.glob('api/dorgen_subdomains_*.jsonl')):
    for line in open(p,encoding='utf-8'):
        r=json.loads(line); s=r['subdomain'].lower()
        if s in site: continue
        rc=r.get('recrawl_sent_at')
        if rc and rc[:10]>='2026-09-01' and r.get('tld') in ('lol','team'):
            site[s]=(T(rc), r['tld'])
first={}
for s,f in json.load(open('api/boty_sentyabr.json',encoding='utf-8'))['first'].items():
    if f[1] and s in site: first[s]=f[1]
for p in sorted(glob.glob('api/tracker_clicks_2026-09-*.jsonl')+glob.glob('api/tracker_clicks_2026-10-*.jsonl')):
    for line in open(p,encoding='utf-8'):
        r=json.loads(line)
        if r.get('is_bot'): continue
        h=r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h: continue
        s=(r.get('subdomain') or '').lower()
        if s in site and (s not in first or r['at']<first[s]): first[s]=r['at']
Z=collections.defaultdict(lambda: collections.defaultdict(lambda:[0,0]))
for s,(rc,z) in site.items():
    d=rc.strftime('%Y-%m-%d'); g=Z[z][d]; g[1]+=1
    f=first.get(s)
    if f and rc-dt.timedelta(hours=1)<=T(f)<rc+dt.timedelta(hours=24): g[0]+=1
print(f'ИНДЕКС 24 ч по зонам (доля сайтов с живым поисковым кликом)')
print(f'{"день":<12} ' + ' '.join(f'{".%s"%z:>24}' for z in ('lol','team')) + f' {"lol/team":>9}')
print(f'{"":<12} ' + ' '.join(f'{"сайтов":>10}{"индекс":>14}' for _ in range(2)))
for d in sorted(set(Z['lol'])|set(Z['team'])):
    a,b=Z['lol'].get(d),Z['team'].get(d)
    sa=f'{a[1]:>10}{100*a[0]/a[1]:>13.2f}%' if a and a[1]>=1500 else f'{"—":>24}'
    sb=f'{b[1]:>10}{100*b[0]/b[1]:>13.2f}%' if b and b[1]>=1500 else f'{"—":>24}'
    rat=''
    if a and b and a[1]>=1500 and b[1]>=1500 and b[0]:
        rat=f'{(a[0]/a[1])/(b[0]/b[1]):>9.2f}'
    print(f'{d:<12} {sa} {sb} {rat}')
print()
for nm,lo,hi in (('01–12.09','2026-09-01','2026-09-12'),('13–22.09','2026-09-13','2026-09-22'),
                 ('23–25.09','2026-09-23','2026-09-25'),('26.09–01.10','2026-09-26','2026-10-01'),
                 ('02–03.10','2026-10-02','2026-10-03'),('04–07.10','2026-10-04','2026-10-07')):
    o=[]
    for z in ('lol','team'):
        n=sum(Z[z][d][1] for d in Z[z] if lo<=d<=hi); h=sum(Z[z][d][0] for d in Z[z] if lo<=d<=hi)
        o.append((n,h,100*h/n if n else 0))
    r=(o[0][2]/o[1][2]) if o[1][2] else 0
    print(f'{nm:<12} .lol {o[0][0]:>7} сайтов {o[0][2]:>6.2f}%   .team {o[1][0]:>7} сайтов {o[1][2]:>6.2f}%   lol/team {r:>5.2f}')
