# Домены, заходящие в ТОП по ВЧ-брендам, с вложенностью «от и до» по каждому съёму.
# Накрученные домены исключены.
import json,re,csv,collections,statistics as st,os
NAKRUTKA={'2679.team','gjtz.team'}      # лист «Накрутка leebet banda»
def depth(u):
    if not isinstance(u,str): return None
    p=u.split('://',1)[-1]; p='/'+p.split('/',1)[1] if '/' in p else '/'
    return len(re.findall(r'/ru(?=/|$)',p))
TIER={}
with open('/home/user/cladue/analysis/keys/keys_stats.csv',encoding='utf-8-sig') as f:
    for r in csv.DictReader(f,delimiter=';'): TIER.setdefault(r['ключ'].strip(),(r['бренд'],r['тир']))
SN=collections.defaultdict(dict)   # dom -> lab -> {keys}
POOL={}
for fn in ['p21','p22','p23','p24','p31b','p01']:
    if not os.path.exists(fn+'.json'): continue
    for sheet,snaps in json.load(open(fn+'.json')).items():
        if 'акрутк' in sheet: continue
        for s in snaps:
            for d,ks in s['per'].items():
                if d in NAKRUTKA: continue
                POOL.setdefault(d,sheet.strip())
                SN[d].setdefault(s['lab'],[])
                have={(k['q'],k['p']) for k in SN[d][s['lab']]}
                for k in ks:
                    if (k['q'],k['p']) not in have: SN[d][s['lab']].append(k)
ROWS=[]
for d,labs in SN.items():
    per=[]
    vmax=0; best=999; brands=collections.Counter(); vs30=0
    def ord_(l):
        d,m=l[:2],l[3:5]; return (int(m),int(d),l[6:])
    for lab in sorted(labs,key=ord_):
        ks=labs[lab]
        vch=[k for k in ks if TIER.get(k['q'],(None,''))[1]=='ВЧ']
        sch=[k for k in ks if TIER.get(k['q'],(None,''))[1]=='СЧ']
        v10=sum(1 for k in vch if k['p']<=10)
        ds=[k['d'] if 'd' in k else depth(k.get('u')) for k in ks]
        ds=[x for x in ds if x is not None]
        dsv=[ (k['d'] if 'd' in k else depth(k.get('u'))) for k in vch if k['p']<=10]
        dsv=[x for x in dsv if x is not None]
        per.append(dict(lab=lab,vch10=v10,vch30=sum(1 for k in vch if k['p']<=30),
            sch10=sum(1 for k in sch if k['p']<=10),
            dmin=min(ds) if ds else None,dmax=max(ds) if ds else None,
            dmed=round(st.median(ds)) if ds else None,
            vdmin=min(dsv) if dsv else None,vdmax=max(dsv) if dsv else None))
        vmax=max(vmax,v10); vs30=max(vs30,per[-1]['vch30'])
        for k in vch:
            if k['p']<=10:
                best=min(best,k['p']); brands[TIER[k['q']][0]]+=1
    if vmax==0 and vs30==0: continue
    ROWS.append(dict(dom=d,pool=POOL.get(d,'?'),vch10=vmax,vch30=vs30,
        best=(best if best!=999 else None),brands=brands.most_common(8),snaps=per))
ROWS.sort(key=lambda r:(-r['vch10'],-r['vch30'],r['best'] or 999))
json.dump(ROWS,open('vchdom.json','w'),ensure_ascii=False)
print(f"доменов с ВЧ в ТОП-30: {len(ROWS)}, из них с ВЧ в ТОП-10: {sum(1 for r in ROWS if r['vch10'])}")
print()
for r in ROWS:
    if not r['vch10'] and r['vch30']<2: continue
    print(f"{r['dom']:<13} пул {r['pool'][:34]:<36} ВЧ в Т10 макс {r['vch10']:>2}  в Т30 {r['vch30']:>2}  лучшая {r['best']}")
    print(f"   бренды: {', '.join(f'{b}·{c}' for b,c in r['brands']) or '—'}")
    for s in r['snaps']:
        rng=f"{s['dmin']}–{s['dmax']}" if s['dmin'] is not None else '—'
        vr=f"{s['vdmin']}–{s['vdmax']}" if s['vdmin'] is not None else '—'
        print(f"   {s['lab']:<14} ВЧ Т10={s['vch10']:>2} Т30={s['vch30']:>2} СЧ Т10={s['sch10']:>2} | "
              f"вложенность всего {rng:<8} медиана {str(s['dmed']):<4} | у ВЧ в Т10 {vr}")
    print()
