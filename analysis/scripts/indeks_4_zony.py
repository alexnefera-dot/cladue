import json, glob, collections, datetime as dt
T=dt.datetime.fromisoformat
site={}
for p in sorted(glob.glob('api/dorgen_subdomains_*.jsonl')):
    for line in open(p,encoding='utf-8'):
        r=json.loads(line); s=r['subdomain'].lower()
        if s in site: continue
        rc=r.get('recrawl_sent_at'); z=r.get('tld')
        if rc and rc[:10]>='2026-09-01' and z in ('lol','team','casino','buzz'):
            site[s]=(T(rc), z)
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
zones=('casino','buzz','team','lol')
print('ИНДЕКС 24 ч по зонам, периоды')
print(f'{"период":<16} ' + ' '.join(f'{"."+z:>22}' for z in zones))
print(f'{"":<16} ' + ' '.join(f'{"сайтов":>10}{"индекс":>12}' for _ in zones))
PER=[('01–07.09','2026-09-01','2026-09-07'),('08–14.09','2026-09-08','2026-09-14'),
     ('15–21.09','2026-09-15','2026-09-21'),('22–28.09','2026-09-22','2026-09-28'),
     ('29.09–05.10','2026-09-29','2026-10-05'),('04–09.10','2026-10-04','2026-10-09')]
for nm,lo,hi in PER:
    line=f'{nm:<16} '
    for z in zones:
        n=sum(Z[z][d][1] for d in Z[z] if lo<=d<=hi); h=sum(Z[z][d][0] for d in Z[z] if lo<=d<=hi)
        line += (f'{n:>10}{100*h/n:>11.2f}%' if n>=1500 else f'{"—":>22}')
    print(line)
print('\nПо дням, где зона была:')
print(f'{"день":<12} ' + ' '.join(f'{"."+z:>20}' for z in zones))
for d in sorted({d for z in zones for d in Z[z]}):
    line=f'{d:<12} '
    for z in zones:
        g=Z[z].get(d)
        line += (f'{g[1]:>9}{100*g[0]/g[1]:>10.2f}%' if g and g[1]>=1000 else f'{"—":>20}')
    print(line)
