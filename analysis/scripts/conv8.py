# Седьмая выгрузка: CSV с полной историей и новыми полями (clickid, движок, referer).
# clickid — идентификатор пользователя: по нему регистрация и депозит связываются точно,
# а не по паре домен+бренд, как приходилось раньше.
import csv,json,collections,re,datetime as dt
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
BADHOST={'yandex.ru','','ru.search.yahoo.com','alice.yandex.ru','youtube.com','—'}
NEW=[]
for r in csv.DictReader(open(SP+'conv8.csv',encoding='utf-8-sig')):
    if not r.get('datetime'): continue
    host=(r['source'] or '').strip().lower()
    p=host.split('.')
    dom='.'.join(p[-2:]) if len(p)>=2 else host
    NEW.append(dict(t=r['datetime'][:16],type=r['event'],dom=dom,
                    sub='.'.join(p[:-2]) if len(p)>2 else '',
                    geo=r['country'],eng=r['campaign'],cid=r['clickid'],
                    ref=r['referer'],ip=r['user_ip'],src='7'))
# внутри самой выгрузки бывают буквальные дубли строк
seen=set(); U=[]
for e in NEW:
    k=(e['t'],e['type'],e['cid'],e['dom'])
    if k in seen: continue
    seen.add(k); U.append(e)
print(f"строк в файле {len(NEW)}, после снятия дублей внутри файла {len(U)}")
json.dump(U,open(SP+'conv8.json','w'),ensure_ascii=False)

OLD=json.load(open(SP+'convall.json'))
have={(e['t'],e['type'],e['dom'],e['sub']) for e in OLD}
fresh=[e for e in U if (e['t'],e['type'],e['dom'],e['sub']) not in have]
ALL=OLD+[{k:e[k] for k in ('t','type','dom','sub','geo','src')} for e in fresh]
ALL.sort(key=lambda e:e['t'])
json.dump(ALL,open(SP+'convall.json','w'),ensure_ascii=False)
print(f"новых для истории {len(fresh)}; история {len(OLD)} → {len(ALL)}")
d=collections.Counter(e['t'][:10] for e in fresh)
print("новые события по дням:", {k:d[k] for k in sorted(d)})
print("движки в выгрузке:", dict(collections.Counter(e['eng'] for e in U)))
print("без нашего домена:", [e['dom'] or '(пусто)' for e in U if e['dom'] in BADHOST])
