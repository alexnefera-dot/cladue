# Как менялись позиции у ключей, у которых менялась вложенность /ru в ранжирующем URL.
# Запускать в папке с p21..p24.json (снимки 27-28.08 в новом формате).
import json,re,collections,statistics as st
S={}
for f in ['p21','p22','p23','p24']:
    for sheet,snaps in json.load(open(f+'.json')).items():
        for s in snaps: S.setdefault((sheet,s['lab']),s)
def depth(u):
    if not u: return None
    p=u.split('://',1)[-1]; p='/'+p.split('/',1)[1] if '/' in p else '/'
    return len(re.findall(r'/ru(?=/|$)',p))
def pairs(prev,last):
    out=[]
    for sh in {k[0] for k in S}:
        a,b=S.get((sh,prev)),S.get((sh,last))
        if not a or not b: continue
        for dom in b.get('per',{}):
            A={(k['b'],k['q']):k for k in a['per'].get(dom,[])}
            B={(k['b'],k['q']):k for k in b['per'].get(dom,[])}
            for kk in set(A)&set(B):
                d0,d1=depth(A[kk].get('u')),depth(B[kk].get('u'))
                if d0 is None or d1 is None: continue
                out.append(dict(dom=dom,b=kk[0],q=kk[1],p0=A[kk]['p'],p1=B[kk]['p'],d0=d0,d1=d1,
                                u0=A[kk].get('u'),u1=B[kk].get('u')))
    return out
def med(v): return st.median(v) if v else None
def report(rows,title):
    ch=[r for r in rows if r['d1']!=r['d0']]; sm=[r for r in rows if r['d1']==r['d0']]
    g=lambda v:[r['p1']-r['p0'] for r in v]
    print(f"== {title}: пар {len(rows)}")
    for lab,v in [('вложенность менялась',ch),('вложенность та же',sm)]:
        d=g(v); print(f"   {lab:<22} n={len(d):>3} медиана {med(d):+.0f} "
                      f"вверх {sum(1 for x in d if x<0)} вниз {sum(1 for x in d if x>0)}")
    for lo,hi,lab in [(1,10,'старт 1–10'),(11,30,'11–30'),(31,60,'31–60'),(61,100,'61–100')]:
        a=g([r for r in ch if lo<=r['p0']<=hi]); b=g([r for r in sm if lo<=r['p0']<=hi])
        print(f"   {lab:<12} менялась n={len(a):>3} мед {med(a) if a else '—'}"
              f"   та же n={len(b):>3} мед {med(b) if b else '—'}")
def survival(prev,last):
    per=collections.defaultdict(lambda:collections.defaultdict(lambda:[0,0]))
    for sh in {k[0] for k in S}:
        a,b=S.get((sh,prev)),S.get((sh,last))
        if not a or not b: continue
        for dom in a.get('per',{}):
            B={(k['b'],k['q']) for k in b['per'].get(dom,[])}
            for k in a['per'][dom]:
                dp=depth(k.get('u'))
                if dp is None: continue
                lab='чистый' if dp==0 else ('1–9' if dp<10 else ('10–19' if dp<20 else '20+'))
                per[dom][lab][0]+=1
                if (k['b'],k['q']) in B: per[dom][lab][1]+=1
    return per
if __name__=='__main__':
    for a,b in [('28.08 00:30','28.08 12:43'),('27.08 21:47','28.08 00:30')]:
        report(pairs(a,b),f'{a} → {b}'); print()
    for dom,v in survival('28.08 00:30','28.08 12:43').items():
        print(dom, {l:f"{s}/{t}" for l,(t,s) in v.items() if t})
