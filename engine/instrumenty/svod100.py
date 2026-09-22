import os, sys, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ryadom import metriki

def nabor(d):
    m = [metriki(os.path.join(d,f)) for f in sorted(os.listdir(d)) if f.endswith('.html')]
    if not m: return None
    return {k: st.median([x[k] for x in m]) for k in m[0]}

def svod(base, otbor=None, imya=''):
    rows=[]
    for n in sorted(os.listdir(base)):
        d=os.path.join(base,n)
        if not os.path.isdir(d): continue
        if otbor and not otbor(n): continue
        r=nabor(d)
        if r: rows.append(r)
    if not rows: return
    print('%s (%d наборов)' % (imya, len(rows)))
    for k in rows[0]:
        v=[r[k] for r in rows]
        print('  %-12s медиана %8.1f   полоса %.1f–%.1f' % (k, st.median(v), min(v), max(v)))

KON='/tmp/claude-0/-home-user-cladue/ea580ece-89cc-5463-b9fe-78c4a0a08b0d/scratchpad/new100x'
svod(KON, imya='NEW100 весь')
