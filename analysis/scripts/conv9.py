# Восьмая выгрузка: полная история 12.08–11.09. Начинается на девять дней раньше
# всех предыдущих, поэтому снимает усечение слева для партий 19–20 августа.
import csv,json,collections,re,datetime as dt
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
BADHOST={'yandex.ru','','—','ru.search.yahoo.com','alice.yandex.ru','youtube.com','ya.ru','google.com','yahoo.com','yandex.kz','yandex.by','yandex.uz'}
NEW=[]
for r in csv.DictReader(open(SP+'conv9.csv',encoding='utf-8-sig')):
    if not r.get('datetime'): continue
    host=(r['source'] or '').strip().lower(); p=host.split('.')
    dom='.'.join(p[-2:]) if len(p)>=2 else host
    NEW.append(dict(t=r['datetime'][:16],type=r['event'],dom=dom,
                    sub='.'.join(p[:-2]) if len(p)>2 else '',
                    geo=r['country'],eng=r['campaign'],cid=r['clickid'],src='9'))
seen=set(); U=[]
for e in NEW:
    k=(e['t'],e['type'],e['cid'],e['dom'])
    if k in seen: continue
    seen.add(k); U.append(e)
json.dump(U,open(SP+'conv9.json','w'),ensure_ascii=False)
print(f"строк {len(NEW)} → после дедупа внутри файла {len(U)}")

OLD=json.load(open(SP+'convall.json'))
have={(e['t'],e['type'],e['dom'],e['sub']) for e in OLD}
fresh=[e for e in U if (e['t'],e['type'],e['dom'],e['sub']) not in have]
ALL=OLD+[{k:e[k] for k in ('t','type','dom','sub','geo','src')} for e in fresh]
ALL.sort(key=lambda e:e['t'])
json.dump(ALL,open(SP+'convall.json','w'),ensure_ascii=False)
print(f"новых для истории {len(fresh)}; история {len(OLD)} → {len(ALL)}")
d=collections.Counter(e['t'][:10] for e in fresh)
print("новые по дням:",{k:d[k] for k in sorted(d)})
ok=[e for e in U if e['dom'] not in BADHOST]
print(f"\nпривязываемых в выгрузке {len(ok)}: рег {sum(1 for e in ok if e['type']=='reg')}, "
      f"деп {sum(1 for e in ok if e['type']=='dep')}, доменов {len({e['dom'] for e in ok})}")
print("выброшено:",dict(collections.Counter(e['dom'] or '(пусто)' for e in U if e['dom'] in BADHOST)))
