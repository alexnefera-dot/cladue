# Список всех запусков за неделю в один txt: по дням, по группам, плюс плоский список.
import re,collections,datetime as dt
AN='/home/user/cladue/analysis/'
DAYS=['01.09','02.09','03.09','04.09','05.09','06.09','07.09']
FILES={'01.09':['launch_01.09.txt'],'02.09':['launch_02.09.txt'],
       '03.09':['launch_03.09.txt','launch_03.09_a4.txt'],'04.09':['launch_04.09.txt'],
       '05.09':['launch_05.09.txt'],'06.09':['launch_06.09.txt'],'07.09':['launch_07.09.txt']}
def hdr(h):
    h=h.strip()
    return h
def parse(f):
    """Возвращает [(заголовок, [домены])]. Форматы разные: где-то одна строка ##,
    где-то основная и под ней уточнение, где-то только # без ##."""
    out=[]; main=None; extra=None; cur=[]; prev_hdr=False; title=None
    for l in open(AN+f):
        l=l.rstrip()
        if l.startswith('## '):
            if cur: out.append((main,extra,cur)); cur=[]
            h=hdr(l[3:])
            if prev_hdr and main: extra=h
            else: main=h; extra=None
            prev_hdr=True
        elif l.startswith('# '):
            title=l[2:].strip()
        elif re.match(r'^[a-z0-9\-]+\.[a-z]+$',l.strip()):
            prev_hdr=False; cur.append(l.strip())
    if cur: out.append((main,extra,cur))
    return title,out

def pl(n,a,b,c):
    x=abs(n)%100; y=x%10
    return f"{n} "+(c if 10<x<20 else a if y==1 else b if 1<y<5 else c)
lines=[]; allx=[]; tot=0
lines.append('СПИСОК ЗАПУСКОВ ЗА НЕДЕЛЮ  1–7 сентября 2026')
lines.append('='*72)
lines.append('')
lines.append('Собрано из реестра запусков. Дальше по дням: группа, id, время создания,')
lines.append('зоны, затем домены — по одному в строке, готовые к копированию.')
lines.append('В самом конце — общий плоский список всех доменов недели.')
lines.append('')
per={}
for d in DAYS:
    blocks=[]
    for f in FILES[d]:
        t,bl=parse(f)
        blocks+= [(m,e,doms,f) for m,e,doms in bl]
    n=sum(len(b[2]) for b in blocks); per[d]=n; tot+=n
    z=collections.Counter('.'+x.split('.')[-1] for b in blocks for x in b[2])
    lines.append('')
    lines.append('='*72)
    lines.append(f'{d}.2026 — {pl(n,"домен","домена","доменов")}, {pl(len(blocks),"группа","группы","групп")}'
                 f'   [{"  ".join(f"{a} {b}" for a,b in z.most_common())}]')
    lines.append('='*72)
    for m,e,doms,f in blocks:
        zz=collections.Counter('.'+x.split('.')[-1] for x in doms)
        lines.append('')
        lines.append(f'--- {m or "(без заголовка)"}')
        if e: lines.append(f'    {e}')
        lines.append(f'    {pl(len(doms),"домен","домена","доменов")}: {"  ".join(f"{a} {b}" for a,b in zz.most_common())}')
        lines.append('')
        lines+= ['    '+x for x in doms]
        allx+=doms
lines.append('')
lines.append('='*72)
lines.append(f'ИТОГО ЗА НЕДЕЛЮ: {pl(tot,"домен","домена","доменов")}')
lines.append('='*72)
for d in DAYS: lines.append(f'  {d}  {per[d]:>3}')
z=collections.Counter('.'+x.split('.')[-1] for x in allx)
lines.append('')
lines.append('  зоны: '+'   '.join(f'{a} {b}' for a,b in z.most_common()))
dup=[x for x,c in collections.Counter(allx).items() if c>1]
lines.append(f'  повторов домена внутри недели: {len(dup)}'+(': '+' '.join(dup) if dup else ''))
lines.append('')
lines.append('='*72)
lines.append(f'ПЛОСКИЙ СПИСОК — все {pl(len(allx),"домен","домена","доменов")} недели подряд')
lines.append('='*72)
lines+=allx
lines.append('')
open(AN+'zapuski_nedeli_01-07.09.txt','w').write('\n'.join(lines))
print(f"{tot} доменов, дни: "+', '.join(f'{d}={per[d]}' for d in DAYS))
