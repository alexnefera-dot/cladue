import openpyxl,io,re,json,collections,datetime
wb=openpyxl.load_workbook(io.BytesIO(open('conv2.xlsx','rb').read()),data_only=True)
rows=list(wb['Sheet1'].iter_rows(values_only=True))
TR={}; GEO=[]; EV=[]
mode='traffic'
for i,r in enumerate(rows):
    a=str(r[0]) if r[0] is not None else ''
    if a.startswith('Гео'): mode='geo'; continue
    if a.startswith('Конверсии'): mode='ev'; continue
    if a.startswith('Реферер'): continue
    if mode=='traffic':
        nm=str(r[1] or '')
        m=re.match(r'^([^\s\xa0]+)(?:\xa0· (\d+) подд\.)?$',nm.strip())
        if not m: continue
        d=m.group(1); sub=int(m.group(2)) if m.group(2) else 0
        try: hits=int(r[2]); uniq=int(r[3]); reg=int(r[4]); dep=int(r[5])
        except: continue
        TR[d]={'sub':sub,'hits':hits,'uniq':uniq,'reg':reg,'dep':dep,'is_dom':a.strip()=='▶'}
    elif mode=='geo':
        if r[1] is None: continue
        try: GEO.append({'geo':a,'uniq':int(r[1]),'hits':int(r[2])})
        except: pass
    elif mode=='ev':
        if not a or 'T' not in a and '-' not in a: continue
        try: ts=datetime.datetime.fromisoformat(a)
        except: continue
        host=str(r[5] or '')
        parts=host.split('.')
        brand=parts[0] if len(parts)>2 else None
        dom='.'.join(parts[1:]) if len(parts)>2 else host
        EV.append({'ts':a,'d':ts.strftime('%d.%m'),'h':ts.hour,'type':str(r[1]),'uid':str(r[3]),
                   'geo':str(r[4] or ''),'host':host,'brand':brand,'dom':dom,'ref':str(r[6] or ''),'ua':str(r[7] or '')})
json.dump({'tr':TR,'geo':GEO,'ev':EV},open('conv2.json','w'),ensure_ascii=False)
print(f"доменов трафика: {len(TR)}  гео: {len(GEO)}  событий: {len(EV)}")
regs=[e for e in EV if e['type']=='reg']; deps=[e for e in EV if e['type']=='dep']
print(f"регистраций: {len(regs)}  депозитов: {len(deps)}")
print(f"период: {min(e['ts'] for e in EV)} … {max(e['ts'] for e in EV)}")
print("\nсумма по трафику:", sum(v['hits'] for v in TR.values()), "хитов,", sum(v['uniq'] for v in TR.values()), "уников,",
      sum(v['reg'] for v in TR.values()), "рег,", sum(v['dep'] for v in TR.values()), "деп")
print("\nтоп гео:", [(g['geo'],g['uniq']) for g in GEO[:6]])
