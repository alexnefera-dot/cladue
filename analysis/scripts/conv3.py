import openpyxl,io,collections,json
wb=openpyxl.load_workbook(io.BytesIO(open('conv.xlsx','rb').read()),data_only=True)
rows=[r for r in wb['Sheet1'].iter_rows(values_only=True) if r[0]]
D=json.load(open('flat.json',encoding='utf-8'))
G={d['d']:d for d in D['doms']}
ev=[]
for r in rows:
    h=str(r[5]).strip().lower(); p=h.split('.')
    if h in ('yandex.ru','ru.search.yahoo.com','alice.yandex.ru'): continue
    ev.append({'t':r[0],'k':r[1],'br':'.'.join(p[:-2]),'dom':'.'.join(p[-2:]),'c':r[4]})
print('всего',len(ev),'| в реестре',sum(1 for e in ev if e['dom'] in G))
# бренд конверсии против брендов, по которым домен ранжируется в Т10
hit=miss=nodata=0; rows2=[]
for e in ev:
    if e['dom'] not in G: continue
    d=G[e['dom']]
    brs={b['b']:b for b in d['brands']}
    if e['br'] in brs: hit+=1; st='в Т10 (поз. %d, %d ключей)'%(brs[e['br']]['best'],brs[e['br']]['n'])
    elif d['t10']==0: nodata+=1; st='домен без Т10 вообще'
    else: miss+=1; st='бренда нет в Т10 домена'
    rows2.append((e['dom'],e['br'],e['k'],st))
print()
print('Бренд конверсии ранжируется у этого домена в ТОП-10:', hit)
print('Бренда нет в Т10, но домен ранжируется по другим:', miss)
print('Домен вообще без ключей в Т10:', nodata)
print()
for r in sorted(rows2):
    print('  %-14s %-14s %-4s %s'%r)
