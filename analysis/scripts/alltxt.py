# Два txt-списка запусков: за текущую неделю и за всё время.
# Форматы файлов реестра разные — заголовки бывают "## ", "=== ... ===" и просто "имя (N)".
import re,collections
AN='/home/user/cladue/analysis/'
DOM=re.compile(r'^[a-z0-9\-]+\.[a-z]+$')

def parse(path):
    out=[]; main=None; extra=None; cur=[]; prev_hdr=False
    for l in open(AN+path):
        l=l.rstrip(); s=l.strip()
        h=None
        if l.startswith('## '): h=l[3:].strip()
        elif s.startswith('===') and s.endswith('==='): h=s.strip('= ').strip()
        elif s and not DOM.match(s) and not l.startswith('#'): h=s
        if h is not None:
            if cur: out.append((main,extra,cur)); cur=[]
            if prev_hdr and main: extra=h
            else: main=h; extra=None
            prev_hdr=True
        elif DOM.match(s):
            prev_hdr=False; cur.append(s)
    if cur: out.append((main,extra,cur))
    return out

FILES=collections.OrderedDict([
 ('24.08',['launch_24.08.txt']),('25.08',['launch_25.08.txt']),
 ('26.08',['launch_26.08_groups.txt']),('27.08',['launch_27.08.txt']),
 ('31.08',['launch_31.08_all.txt']),
 ('01.09',['launch_01.09.txt']),('02.09',['launch_02.09.txt']),
 ('03.09',['launch_03.09.txt','launch_03.09_a4.txt']),('04.09',['launch_04.09.txt']),
 ('05.09',['launch_05.09.txt']),('06.09',['launch_06.09.txt']),
 ('07.09',['launch_07.09.txt']),('08.09',['launch_08.09.txt']),
 ('09.09',['launch_09.09.txt']),('10.09',['launch_10.09.txt']),('11.09',['launch_11.09.txt']),('12.09',['launch_12.09.txt']),
])
def pl(n,a,b,c):
    x=abs(n)%100; y=x%10
    return f"{n} "+(c if 10<x<20 else a if y==1 else b if 1<y<5 else c)

def build(days,title,note,path):
    L=[title,'='*72,'']+note+['']
    allx=[]; per={}
    for d in days:
        blocks=[b for f in FILES[d] for b in parse(f)]
        # в августовских файлах есть сводный блок «ВСЕ N ОДНИМ СПИСКОМ» — он дублирует
        # уже перечисленные домены, в разбивку по группам его брать нельзя
        blocks=[b for b in blocks if 'ОДНИМ СПИСКОМ' not in (b[0] or '').upper()]
        seen=set(); clean=[]
        for m,e,doms in blocks:
            uniq=[x for x in doms if x not in seen]
            seen.update(uniq)
            if uniq: clean.append((m,e,uniq))
        blocks=clean
        dd=[x for _,_,doms in blocks for x in doms]; per[d]=len(dd)
        z=collections.Counter('.'+x.split('.')[-1] for x in dd)
        L+=['','='*72,
            f'{d}.2026 — {pl(len(dd),"домен","домена","доменов")}, '
            f'{pl(len(blocks),"группа","группы","групп")}'
            f'   [{"  ".join(f"{a} {b}" for a,b in z.most_common())}]','='*72]
        for m,e,doms in blocks:
            zz=collections.Counter('.'+x.split('.')[-1] for x in doms)
            L+=['',f'--- {m or "(без заголовка)"}']
            if e: L.append(f'    {e}')
            L+=[f'    {pl(len(doms),"домен","домена","доменов")}: '
                f'{"  ".join(f"{a} {b}" for a,b in zz.most_common())}','']
            L+=['    '+x for x in doms]; allx+=doms
    L+=['','='*72,f'ИТОГО: {pl(len(allx),"домен","домена","доменов")}','='*72]
    for d in days: L.append(f'  {d}  {per[d]:>4}')
    z=collections.Counter('.'+x.split('.')[-1] for x in allx)
    L+=['','  зоны: '+'   '.join(f'{a} {b}' for a,b in z.most_common())]
    dup=[x for x,c in collections.Counter(allx).items() if c>1]
    L.append(f'  доменов встречается более одного раза: {len(dup)}'+(': '+' '.join(dup) if dup else ''))
    L+=['','='*72,f'ПЛОСКИЙ СПИСОК — {pl(len(allx),"домен","домена","доменов")} подряд','='*72]+allx+['']
    open(AN+path,'w').write('\n'.join(L))
    return allx

WEEK=['06.09','07.09','08.09','09.09','10.09','11.09','12.09']
w=build(WEEK,'СПИСОК ЗАПУСКОВ ЗА НЕДЕЛЮ  6–12 сентября 2026',
 ['По дням: группа, id, время создания, зоны, затем домены по одному в строке.',
  'В конце — общий плоский список всех доменов недели.','',
  'Неполные партии: 07.09 clean7_part1_50 — присланы 10 из 50;',
  '08.09 archive37 часть1 — 25 из 45, часть3 — 27 из 45.'],
 'zapuski_nedeli_06-12.09.txt')

a=build(list(FILES),'СПИСОК ЗАПУСКОВ ЗА ВСЁ ВРЕМЯ  24 августа — 12 сентября 2026',
 ['Все дни, по которым есть списки запуска.','',
  'Дни 19–23 и 28–30 августа списками не заведены: по ним есть домены и позиции,',
  'но нет разбивки по группам. Эти домены собраны отдельным блоком в конце файла.','',
  'По дням: группа, id, время создания, зоны, затем домены по одному в строке.'],
 'zapuski_vse_vremya.txt')

reg=[l.strip() for l in open(AN+'domains_flat.txt') if l.strip()]
inlists=set(a); rest=[d for d in reg if d not in inlists]
grp={}
for i,l in enumerate(open(AN+'domains_full.txt')):
    if i==0: continue
    p=l.rstrip('\n').split('\t')
    if len(p)>3 and p[0]: grp[p[0]]=(p[2] or '?',p[3] or '')
L=['','','='*72,f'ДОМЕНЫ БЕЗ СПИСКА ЗАПУСКА — {pl(len(rest),"домен","домена","доменов")}','='*72,
   'Запущены до 24 августа либо в дни, по которым списки не присылались.',
   'Группа известна не у всех, день запуска не установлен ни у одного.','']
by=collections.defaultdict(list)
for d in rest: by[grp.get(d,('— группа неизвестна —',''))[0]].append(d)
for g in sorted(by,key=lambda x:-len(by[x])):
    fm=grp.get(by[g][0],('',''))[1]
    z=collections.Counter('.'+x.split('.')[-1] for x in by[g])
    L+=['',f'--- {g}'+(f'   ({fm})' if fm else ''),
        f'    {pl(len(by[g]),"домен","домена","доменов")}: '
        f'{"  ".join(f"{a2} {b2}" for a2,b2 in z.most_common())}','']
    L+=['    '+x for x in by[g]]
L+=['','='*72,f'ВСЕГО В РЕЕСТРЕ: {pl(len(reg),"домен","домена","доменов")}',
    f'  со списком запуска: {len(inlists)}',f'  без списка: {len(rest)}','='*72,'',
    f'ПЛОСКИЙ СПИСОК — весь реестр, {pl(len(reg),"домен","домена","доменов")}','='*72]+reg+['']
open(AN+'zapuski_vse_vremya.txt','a').write('\n'.join(L))
print(f"неделя: {len(w)} доменов")
print(f"всё время: {len(a)} в списках + {len(rest)} без списка = {len(reg)}")
