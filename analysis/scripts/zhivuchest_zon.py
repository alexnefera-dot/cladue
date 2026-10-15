import csv, json, glob, collections, datetime as dt
T=dt.date.fromisoformat
site={}
with open('api/reestr_kesh.tsv',encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        d=r['recrawl'][:10]
        if d in ('2026-10-02','2026-10-03') and r['tld'] in ('lol','team'):
            site[r['subdomain']]=(T(d), r['tld'], d)
N=collections.Counter()
for s,(rc,z,d) in site.items(): N[(z,d)]+=1
print('Когорты, запущенные в одни и те же дни (календарь одинаков у обеих зон):')
for k in sorted(N): print(f'   {k[1]} .{k[0]:<5} {N[k]:>7} сайтов')
A=collections.defaultdict(int)
for p in sorted(glob.glob('api/tracker_clicks_2026-10-*.jsonl')):
    for line in open(p,encoding='utf-8'):
        r=json.loads(line)
        if r.get('is_bot'): continue
        h=r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h: continue
        v=site.get((r.get('subdomain') or '').lower())
        if not v: continue
        age=(T(r['at'][:10])-v[0]).days
        if 0<=age<=13: A[(v[1],age)]+=1
tot={z:sum(A[(z,a)] for a in range(14)) for z in ('lol','team')}
nn={z:sum(N[(z,d)] for d in ('2026-10-02','2026-10-03')) for z in ('lol','team')}
print(f'\nвсего кликов за 14 суток жизни: .lol {tot["lol"]} на {nn["lol"]} сайтах, '
      f'.team {tot["team"]} на {nn["team"]} сайтах')
print(f'на сайт: .lol {tot["lol"]/nn["lol"]:.2f}, .team {tot["team"]/nn["team"]:.2f}\n')
print(f'{"возраст":<9} {".lol кл/сайт":>14} {".team кл/сайт":>14} {"lol/team":>9} | {"накоплено .lol":>15} {"накоплено .team":>16}')
cl=ct=0
for a in range(0,14):
    x=A[('lol',a)]/nn['lol']; y=A[('team',a)]/nn['team']
    cl+=A[('lol',a)]; ct+=A[('team',a)]
    r=x/y if y else 0
    print(f'{a:<9} {x:>14.3f} {y:>14.3f} {r:>9.2f} | {100*cl/max(1,tot["lol"]):>14.0f}% {100*ct/max(1,tot["team"]):>15.0f}%')
