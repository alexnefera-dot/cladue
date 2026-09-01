# Живучесть и результативность по зонам. Главное — парное сравнение внутри групп:
# в одной группе один контент и один день, поэтому зона там единственное отличие.
import json,collections
db=json.load(open('db.json')); C=json.load(open('conv2.json'))
import os
E3=json.load(open('conv3.json')) if os.path.exists('conv3.json') else []
rd=collections.Counter(e['dom'] for e in C['ev']+E3 if e['type']=='reg')
dp=collections.Counter(e['dom'] for e in C['ev']+E3 if e['type']=='dep')
TR={d:v for d,v in C['tr'].items() if v['is_dom']}
def zone(d): return '.'+d.split('.')[-1]
Z=collections.defaultdict(lambda:dict(n=0,pos=0,t10=0,t10sum=0,w=0,reg=0,dep=0,sub=0,doms=[]))
for d,v in db.items():
    if d=='базовый домен': continue
    bs=v['b'].values(); t10=sum(x['t10'] for x in bs); t100=sum(x['t100'] for x in bs)
    x=Z[zone(d)]; x['n']+=1; x['t10sum']+=t10; x['doms'].append(d)
    if t10: x['t10']+=1
    if t100: x['pos']+=1
    if rd.get(d,0): x['w']+=1
    x['reg']+=rd.get(d,0); x['dep']+=dp.get(d,0); x['sub']+=TR.get(d,{}).get('sub',0)
# парное сравнение внутри групп
G=collections.defaultdict(lambda:collections.defaultdict(list))
for d,v in db.items():
    if d=='базовый домен': continue
    G[v['group']][zone(d)].append((d,sum(x['t10'] for x in v['b'].values()),
        sum(x['t100'] for x in v['b'].values()),rd.get(d,0)))
def roll(sel):
    n=t10=pos=reg=0
    for g,zs in G.items():
        if '.team' not in zs or len(zs)<2: continue
        for z,v in zs.items():
            if not sel(z): continue
            n+=len(v); t10+=sum(x[1] for x in v); pos+=sum(1 for x in v if x[2]); reg+=sum(x[3] for x in v)
    return dict(n=n,t10=round(t10/n,1) if n else None,pos=round(100*pos/n) if n else None,
                reg=round(reg/n,2) if n else None)
PAIR=dict(team=roll(lambda z:z=='.team'),other=roll(lambda z:z!='.team'),
          lol=roll(lambda z:z=='.lol'))
teamlol=[0,0,0,0]
for g,zs in G.items():
    if '.team' in zs and '.lol' in zs:
        for i,z in ((0,'.team'),(2,'.lol')):
            teamlol[i]+=len(zs[z]); teamlol[i+1]+=sum(x[1] for x in zs[z])
json.dump(dict(zones={z:{k:v for k,v in x.items() if k!='doms'} for z,x in Z.items()},
               zonedoms={z:x['doms'] for z,x in Z.items()},pair=PAIR),
          open('zones.json','w'),ensure_ascii=False)
print(f"{'зона':<9}{'дом':>5}{'с позиц':>8}{'%':>5}{'с Т10':>7}{'%':>5}{'Т10/дом':>9}{'рег':>5}{'рег/дом':>9}")
for z,x in sorted(Z.items(),key=lambda k:-k[1]['n']):
    print(f"{z:<9}{x['n']:>5}{x['pos']:>8}{100*x['pos']/x['n']:>4.0f}%{x['t10']:>7}{100*x['t10']/x['n']:>4.0f}%"
          f"{x['t10sum']/x['n']:>9.1f}{x['reg']:>5}{x['reg']/x['n']:>9.2f}")
print('\nпарное сравнение внутри смешанных групп:',PAIR)
