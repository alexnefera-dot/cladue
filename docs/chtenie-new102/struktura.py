# -*- coding: utf-8 -*-
"""Структура страниц по семействам: последовательность верхних блоков, пул h2, перестановки, сквозные факты набора."""
import sys,os,re,glob,json,statistics as st
from html.parser import HTMLParser
from collections import Counter,defaultdict
sys.path.insert(0,'/tmp/p27/formula'); from fakty import facts,NAMES
ROOT='/tmp/p27/new102/a8961923-NEW102'
PAGES=['main','obzor','promo','news','info','partnery','app','bonus','registracia','slots','vhod','zerkalo']
fp=json.load(open('/tmp/p27/formula/fp.json'))
def family(s):
    if 'faq-item' in fp[s]['cls']:
        return 'F1b' if s in ('betwinner','ezcash-2','martin') else 'F1'
    return 'F2'
class T(HTMLParser):
    """верхние блоки: (тег, класс/сигнатура, h2-текст, счётчики)"""
    VOID={'meta','img','br','input','link','hr'}
    def __init__(s): super().__init__(); s.depth=0; s.top=[]; s.cur=None; s.h2=False; s.h2buf=[]
    def handle_starttag(s,t,a):
        a=dict(a)
        if s.depth==0:
            s.cur={'tag':t,'cls':(a.get('class','') or '').split()[0] if a.get('class') else '','h2':'','n':Counter()}
            s.top.append(s.cur)
        elif s.cur: s.cur['n'][t]+=1
        if t=='h2': s.h2=True; s.h2buf=[]
        if t not in s.VOID: s.depth+=1
    def handle_endtag(s,t):
        if t=='h2' and s.cur: s.h2=False; s.cur['h2']=s.cur['h2'] or re.sub(r'\s+',' ',''.join(s.h2buf)).strip()
        if t not in s.VOID: s.depth=max(0,s.depth-1)
        if s.depth==0: s.cur=None
    def handle_data(s,d):
        if s.h2: s.h2buf.append(d)
def blocks(html):
    p=T(); p.feed(html); out=[]
    for b in p.top:
        n=b['n']; t=b['tag']
        if t in ('h2','h3','p','ul','ol','img','figure'): kind=t
        elif b['cls'] and not re.match(r'^[a-z]{2}-[a-z]{6}$',b['cls']): kind=t+'.'+b['cls']
        else:
            if n['table'] or n['tr']: kind=t+'[table]'
            elif n['h2'] and n['td']==0 and (n['p'] or n['li']): kind=t+'[раздел]'
            elif n['a']>=5 and n['p']==0: kind=t+'[ссылки]'
            elif n['h3']>=3 and n['p']==0: kind=t+'[плитки]'
            else: kind=t+'[div]'
        out.append((kind,b['h2'],dict(n)))
    return out
if __name__=='__main__':
    fam=defaultdict(list)
    for s in fp: fam[family(s)].append(s)
    R={}
    for F,sets in fam.items():
        print(f'\n############ {F}: {len(sets)} наборов')
        for pg in PAGES:
            sigs=Counter(); h2pool=Counter(); nsec=[]; kinds_pos=defaultdict(list)
            for s in sets:
                f=f'{ROOT}/{s}/{pg}.html'
                if not os.path.exists(f): continue
                bl=blocks(open(f,encoding='utf-8',errors='ignore').read())
                sig=' '.join(k for k,_,_ in bl); sigs[sig]+=1
                secs=[h for k,h,_ in bl if h]; nsec.append(len(secs))
                for h in secs: h2pool[re.sub(r'\d[\d\s.,]*','N',h)]+=1
                for i,(k,_,_) in enumerate(bl): kinds_pos[k].append(i)
            if not nsec: continue
            print(f'\n--- {pg}: разных сигнатур {len(sigs)} из {sum(sigs.values())}; h2 на страницу {min(nsec)}–{max(nsec)} (медиана {st.median(nsec)}); разных h2 {len(h2pool)}')
            top=sigs.most_common(2)
            for sig,c in top: print(f'   {c}× {sig[:260]}')
            print('   h2 пул (топ-8):', '; '.join(f'{h[:60]} ({c})' for h,c in h2pool.most_common(8)))
