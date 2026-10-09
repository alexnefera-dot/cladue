import csv, json, glob, collections, datetime as dt
T=dt.datetime.fromisoformat
pairs=list(csv.DictReader(open('export/povtory_29-30.09.csv',encoding='utf-8')))
rep={r['rep'] for r in pairs}; orig={r['orig'] for r in pairs}
site={}
with open('api/reestr_kesh.tsv',encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        if (r['base'] in rep or r['base'] in orig) and r['recrawl']:
            site[r['subdomain']]=(r['base'], T(r['recrawl']+'+03:00'))
C=collections.Counter(); seen=set()
for p in sorted(glob.glob('api/tracker_clicks_2026-09-2*.jsonl')+glob.glob('api/tracker_clicks_2026-10-*.jsonl')):
    for line in open(p,encoding='utf-8'):
        r=json.loads(line)
        if r.get('is_bot'): continue
        h=r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h: continue
        s=(r.get('subdomain') or '').lower()
        if s not in site: continue
        k=(r.get('clickid'), r['at'])
        if k in seen: continue
        seen.add(k)
        C['повторы' if site[s][0] in rep else 'первые']+=1
print('Накопленные живые поисковые клики 29.09–09.10 (без дублей):')
for k in ('повторы','первые'): print(f'   {k:<10} {C[k]:>8}')
REG={'повторы':0,'первые':44}
print(f'\n{"":<10} {"кликов":>9} {"рег":>5} {"рег на 10тыс кликов":>21}')
for k in ('повторы','первые'):
    print(f'{k:<10} {C[k]:>9} {REG[k]:>5} {(10000*REG[k]/C[k] if C[k] else 0):>21.2f}')
