# Итоговые цифры для отчёта: цена безубыточности домена и вклад .casino в убыток.
import json,collections,math,re,glob,datetime as dt
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
BAD={'yandex.ru','','—','ru.search.yahoo.com','alice.yandex.ru','youtube.com','ya.ru',
     'google.com','yahoo.com','yandex.kz','yandex.by','yandex.uz'}
PRICE={'casino':7.0,'team':2.0,'lol':1.0,'buzz':1.0}
DEP=40.0; TODAY=dt.date(2026,9,12)
EV=[e for e in json.load(open(SP+'convall.json')) if e['dom'] not in BAD]
reg=collections.Counter(); dp=collections.Counter()
for e in EV: (reg if e['type']=='reg' else dp)[e['dom']]+=1
def dat(s):
    m=re.match(r'(\d\d)\.(\d\d)',s)
    return dt.date(2026,int(m.group(2)),int(m.group(1))) if m else None
D={}
for f in sorted(glob.glob('/home/user/cladue/analysis/launch_*.txt')):
    if '_flat' in f: continue
    md=re.search(r'launch_(\d\d\.\d\d)',f)
    if not md: continue
    day=md.group(1); main=None; prev=False
    for l in open(f):
        l=l.rstrip(); s2=l.strip(); h=None
        if l.startswith('## '): h=l[3:].strip()
        elif s2.startswith('===') and s2.endswith('==='): h=s2.strip('= ').strip()
        elif s2 and not re.match(r'^[a-z0-9\-]+\.[a-z]+$',s2) and not l.startswith('#'): h=s2
        if h is not None:
            if not (prev and main): main=h
            prev=True
        elif re.match(r'^[a-z0-9\-]+\.[a-z]+$',s2):
            prev=False
            if 'ОДНИМ СПИСКОМ' in (main or '').upper(): continue
            D[s2]=(day,main or '')
CLOSED={d:v for d,v in D.items() if dat(v[0]) and (TODAY-dat(v[0])).days>=6}
zone=lambda d:d.split('.')[-1]
ALL=set(x.strip() for x in open('/home/user/cladue/analysis/domains_flat.txt') if x.strip())|set(D)

def sm(ds,label):
    n=len(ds); c=sum(PRICE.get(zone(d),1.0) for d in ds)
    r=sum(reg[d] for d in ds); p=sum(dp[d] for d in ds); rv=p*DEP
    print(f"{label:<34}{n:>6} дом  ${c:>6.0f}  {r:>4} рег  {p:>3} деп  ${rv:>6.0f}  итог ${rv-c:>+7.0f}  ROI {rv/c if c else 0:>4.2f}x")
    return n,c,r,p

print("=== ГЛАВНОЕ ЧИСЛО: сколько приносит один домен ===")
n,c,r,p=sm(CLOSED,'закрытые окна, как есть')
per=p*DEP/n
print(f"\nодин домен приносит ${per:.2f} выручки (при {p/n:.4f} деп/домен и ${DEP:.0f} за депозит)")
print(f"=> ЛЮБОЙ домен дороже ${per:.2f} убыточен при текущей конверсии")
for z in ('casino','team','lol'):
    print(f"   .{z:<8} ${PRICE[z]:.0f}  {'убыток' if PRICE[z]>per else 'прибыль'} ${per-PRICE[z]:+.2f}/домен")

print("\n=== ВКЛАД .casino В УБЫТОК ===")
sm(CLOSED,'все закрытые окна')
sm({d:v for d,v in CLOSED.items() if zone(d)=='casino'},'  из них .casino')
sm({d:v for d,v in CLOSED.items() if zone(d)!='casino'},'  всё кроме .casino')
print()
sm(ALL,'весь реестр (окна частью открыты)')
sm({d for d in ALL if zone(d)=='casino'},'  из них .casino')
sm({d for d in ALL if zone(d)!='casino'},'  всё кроме .casino')

print("\n=== ВОРОНКА: где теряется ===")
nn=len(CLOSED); rr=sum(reg[d] for d in CLOSED); pp=sum(dp[d] for d in CLOSED)
w=sum(1 for d in CLOSED if reg[d])
print(f"запущено домены        {nn:>6}")
print(f"дали хоть 1 рег        {w:>6}   {100*w/nn:>5.1f}% от запущенных")
print(f"регистраций всего      {rr:>6}   {rr/nn:>5.2f} на домен, {rr/w:.2f} на сработавший")
print(f"депозитов              {pp:>6}   {100*pp/rr:>5.1f}% от регистраций")
print(f"выручка                ${pp*DEP:>5.0f}")
print("\nчтобы выйти в плюс при текущих ценах, надо поднять ЛЮБОЕ из трёх:")
need=c/DEP
print(f"  заход {100*w/nn:.1f}% -> {100*w/nn*need/pp:.1f}%   (в {need/pp:.2f}x)")
print(f"  рег на сработавший домен {rr/w:.2f} -> {rr/w*need/pp:.2f}")
print(f"  рег->деп {100*pp/rr:.1f}% -> {100*need/rr:.1f}%")
print(f"  ...или снизить среднюю цену домена ${c/nn:.2f} -> ${pp*DEP/nn:.2f}")
