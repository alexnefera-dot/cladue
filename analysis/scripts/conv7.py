# Шестая выгрузка конверсий (05-07.09). Парсит, дедуплицирует с историей,
# привязывает каждое событие к группе запуска и дню.
import openpyxl,json,collections,re,datetime as dt
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
AN='/home/user/cladue/analysis/'
TYPE={'рега':'reg','деп':'dep'}
wb=openpyxl.load_workbook(SP+'conv7.xlsx',data_only=True)
NEW=[]
for r in wb['Sheet1'].iter_rows(values_only=True):
    if not r[0] or not isinstance(r[0],dt.datetime): continue
    host=str(r[5]).strip().lower(); p=host.split('.')
    NEW.append(dict(t=r[0].strftime('%Y-%m-%d %H:%M'),type=TYPE.get(str(r[1]).strip(),str(r[1])),
                    dom='.'.join(p[-2:]),sub='.'.join(p[:-2]),geo=str(r[4]),
                    eng=str(r[3]),uid=str(r[2]),src='6'))
json.dump(NEW,open(SP+'conv7.json','w'),ensure_ascii=False)

OLD=json.load(open(SP+'convall.json'))
seen={(e['t'],e['type'],e['dom'],e['sub']) for e in OLD}
fresh=[e for e in NEW if (e['t'],e['type'],e['dom'],e['sub']) not in seen]
ALL=OLD+[{k:e[k] for k in ('t','type','dom','sub','geo','src')} for e in fresh]
ALL.sort(key=lambda e:e['t'])
json.dump(ALL,open(SP+'convall.json','w'),ensure_ascii=False)
print(f"выгрузка: {len(NEW)} событий, из них новых (не было в истории) {len(fresh)}")
print(f"история: {len(OLD)} → {len(ALL)}")

# --- карта домен → группа/день: дополняем реестром запусков
M=json.load(open(SP+'dommap.json'))
import glob
for f in sorted(glob.glob(AN+'launch_*.txt')):
    if '_flat' in f: continue
    md=re.search(r'launch_(\d\d\.\d\d)',f)
    if not md: continue
    day=md.group(1); cur=None
    for l in open(f):
        l=l.rstrip()
        if l.startswith('## '): cur=l[3:].strip()
        elif re.match(r'^[a-z0-9\-]+\.[a-z]+$',l.strip()):
            d=l.strip()
            if d not in M: M[d]=dict(g=cur or day,day=day,cfg='')
json.dump(M,open(SP+'dommap.json','w'),ensure_ascii=False)
print(f"карта доменов: {len(M)}")
