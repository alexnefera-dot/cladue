import openpyxl,io,collections,core,json
wb=openpyxl.load_workbook(io.BytesIO(open('book1.xlsx','rb').read()),data_only=True)
b=[list(r) for r in wb['Sheet1'].iter_rows(values_only=True)]
DOMS=['9928.team','f6zn.team','w2yn.team','4150.team','qluj.team','sblv.team','6574.team','5803.team','4814.team','3677.lol','c3c.lol','3286.team','w4g.team','i5x.team','xabd.team','mkuk.team','4733.team','2824.team','1750.team','w4lv.team','7216.lol','8573.lol','2058.team','zfmn.team','bgqt.team','chrv.team','t8nv.team','2428.team','7672.team','y8db.team','5367.team','khbr.team','1625.team','1857.team','5385.team','nchg.team','2764.team','4757.team','8304.team','8300.team','7039.team','nwcs.team']
GRP={}
for d in '9928.team f6zn.team w2yn.team 4150.team qluj.team sblv.team 6574.team 5803.team 4814.team 3677.lol c3c.lol'.split(): GRP[d]=('Тест B','с картинками')
for d in '3286.team w4g.team i5x.team xabd.team mkuk.team 4733.team 2824.team 1750.team w4lv.team 7216.lol 8573.lol'.split(): GRP[d]=('Тест B','без картинок')
for d in '2058.team zfmn.team bgqt.team chrv.team t8nv.team'.split(): GRP[d]=('Тест C · блок 1','без картинок')
for d in '2428.team 7672.team y8db.team 5367.team khbr.team'.split(): GRP[d]=('Тест C · блок 1','с картинками')
for d in '1625.team 1857.team 5385.team nchg.team 2764.team'.split(): GRP[d]=('Тест C · блок 2','без картинок')
for d in '4757.team 8304.team 8300.team 7039.team nwcs.team'.split(): GRP[d]=('Тест C · блок 2','с картинками')
def val(x):
    try:
        v=int(x); return v if 1<=v<=100 else None
    except: return None
APEX='apex'
rows=[]
for r in b:
    q=str(r[0]).strip().lower()
    m=core.KW.get(q)
    br,vol=(m[0],m[1]) if m else (APEX,None)
    hits=[(DOMS[i],val(r[1+i])) for i in range(len(DOMS)) if val(r[1+i])]
    rows.append({'q':q,'br':br,'vol':vol,'hits':sorted(hits,key=lambda x:x[1])})
B={}
for x in rows:
    e=B.setdefault(x['br'],{'b':x['br'],'vol':x['vol'],'keys':[],'nk':0,'hits':0})
    e['nk']+=1; e['keys'].append(x); e['hits']+=len(x['hits'])
out=[]
for br,e in B.items():
    per=collections.defaultdict(list)
    for k in e['keys']:
        for d,p in k['hits']: per[d].append((k['q'],p))
    doms=[]
    for d,ks in per.items():
        ks.sort(key=lambda x:x[1])
        doms.append({'d':d,'grp':GRP[d][0],'arm':GRP[d][1],'zone':'.'+d.split('.')[-1],
                     'n':len(ks),'best':ks[0][1],'keys':[{'q':q,'p':p} for q,p in ks]})
    doms.sort(key=lambda x:(x['best'],-x['n']))
    out.append({'b':br,'vol':e['vol'],'nk':e['nk'],'hits':e['hits'],
                'ndom':len(doms),'doms':doms,
                'allkeys':[k['q'] for k in e['keys']],
                'dead':[k['q'] for k in e['keys'] if not k['hits']]})
out.sort(key=lambda x:(-(x['vol'] or 0)))
D={'brands':out,'ndoms':len(DOMS),'nkeys':len(rows),
   'hits':sum(x['hits'] for x in out),
   'withpos':len({d for x in out for d in [dd['d'] for dd in x['doms']]}),
   'src':'Book1.xlsx · узкое ядро 70 ключей по 7 брендам · 42 домена запуска 24.08'}
json.dump(D,open('brand.json','w',encoding='utf-8'),ensure_ascii=False)
print('брендов',len(out),'| позиций',D['hits'],'| доменов с позицией',D['withpos'])
for x in out:
    print('  %-8s %-11s ключей %2d | попаданий %2d | доменов %d | лучший: %s'%(
        x['b'],('%.1fM'%(x['vol']/1e6)) if x['vol'] else 'нет в ядре',x['nk'],x['hits'],x['ndom'],
        ('%s поз.%d по %d кл.'%(x['doms'][0]['d'],x['doms'][0]['best'],x['doms'][0]['n'])) if x['doms'] else '—'))
