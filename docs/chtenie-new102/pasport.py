# -*- coding: utf-8 -*-
"""Сквозной паспорт набора: сколько разных значений каждого факта на набор и на страницу, на скольких страницах живёт самое частое; имена; дословные повторы предложений между страницами и между наборами семейства."""
import sys,os,re,glob,json,statistics as st
from collections import Counter,defaultdict
sys.path.insert(0,'/tmp/p27/formula'); from fakty import facts,NAMES
ROOT='/tmp/p27/new102/a8961923-NEW102'
fp=json.load(open('/tmp/p27/formula/fp.json'))
def family(s):
    if s.startswith('/'): return 'наши'
    if 'faq-item' in fp[s]['cls']: return 'F1b' if s in ('betwinner','ezcash-2','martin') else 'F1'
    return 'F2'
def text(html):
    html=re.sub(r'<(style|script)[^>]*>.*?</\1>','',html,flags=re.S)
    t=re.sub(r'<[^>]+>',' ',html); return re.sub(r'\s+',' ',t)
def sents(t):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+',t) if len(s.split())>=8]
sets=[(s,f'{ROOT}/{s}') for s in fp]+[(f'/наш-{n}',f'/home/user/cladue/samples/v5-final/nabor-{n}') for n in (478,479,480,481,482,483)]
fam=defaultdict(list); famsents=defaultdict(lambda: defaultdict(set))
for s,d in sets:
    F=family(s); per={}; allf=defaultdict(Counter); names=Counter(); pagesents={}
    for f in sorted(glob.glob(d+'/*.html')):
        pg=os.path.basename(f)[:-5]; t=text(open(f,encoding='utf-8',errors='ignore').read())
        fx=facts(t); per[pg]=fx
        for k in ('rtp','проц','джекпот','время'):
            for v in fx[k]: allf[k][v]+=1
        for m in re.finditer(r'(?<![А-ЯЁа-яё-])('+'|'.join(NAMES)+r')(?![а-яё])',t): names[m.group(1)]+=1
        pagesents[pg]=set(sents(t))
    rec={'наборов':1}
    for k in ('rtp','проц','джекпот','время'):
        c=allf[k]; rec['разн_'+k]=len(c); rec['страниц_топ_'+k]=(c.most_common(1)[0][1] if c else 0)
        rec['на_стр_'+k]=st.mean(len(per[p][k]) for p in per) if per else 0
    rec['разн_имён']=len(names); rec['имён_упом']=sum(names.values()); rec['топ_имя_доля']=(names.most_common(1)[0][1]/max(1,sum(names.values())))
    # дословные повторы между страницами набора
    cnt=Counter(x for p in pagesents for x in pagesents[p]); rec['предл_всего']=sum(len(v) for v in pagesents.values()); rec['предл_на_2+стр']=sum(1 for x,c in cnt.items() if c>=2)
    for p in pagesents:
        for x in pagesents[p]: famsents[F][x].add(s)
    fam[F].append(rec)
print('| семейство | наборов | RTP: разных/набор, на стр, страниц у топа | процент: разных, на стр, топ | джекпот: разных, на стр, топ | время: разных, на стр, топ | имён разных / упоминаний / доля топ-имени | предложений на 2+ страницах набора |')
print('|---|---|---|---|---|---|---|---|')
for F,rs in fam.items():
    m=lambda k: round(st.mean(r[k] for r in rs),1)
    print(f"| {F} | {len(rs)} | {m('разн_rtp')} / {m('на_стр_rtp')} / {m('страниц_топ_rtp')} | {m('разн_проц')} / {m('на_стр_проц')} / {m('страниц_топ_проц')} | {m('разн_джекпот')} / {m('на_стр_джекпот')} / {m('страниц_топ_джекпот')} | {m('разн_время')} / {m('на_стр_время')} / {m('страниц_топ_время')} | {m('разн_имён')} / {m('имён_упом')} / {round(st.mean(r['топ_имя_доля'] for r in rs),2)} | {m('предл_на_2+стр')} из {m('предл_всего')} |")
print('\nДословные предложения (≥8 слов), общие для наборов одного семейства:')
for F,d in famsents.items():
    n=len(fam[F]); shared=[(x,len(v)) for x,v in d.items() if len(v)>=2]
    shared.sort(key=lambda x:-x[1])
    print(f'\n{F}: всего разных предложений {len(d)}, встречаются в ≥2 наборах: {len(shared)} ({round(100*len(shared)/len(d))}%), в ≥половине наборов: {sum(1 for x,c in shared if c>=n/2)}')
    for x,c in shared[:8]: print(f'   {c}× {x[:150]}')
