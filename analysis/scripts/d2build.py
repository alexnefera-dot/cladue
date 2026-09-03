import json,os,statistics as st,datetime as dt
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
S='/home/user/cladue/analysis/scripts/'
A=json.load(open(SP+'snapr.json')); QD=A['qd']
P={p['id']:p for p in A['pools']}
DAY=[p for p in A['pools'] if p['ltx'].startswith('02.09')]
for p in DAY: p['snaps']=p['snaps'][-1:]          # один замер

def per(pid,doms,tf=None):
    p=P[pid]; s=p['snaps'][-1]; idx={d:p['doms'].index(d) for d in doms}
    R=[r for r in s['rows'] if not tf or QD[r[0]][2] in tf]
    t10=[sum(1 for r in R if r[1]==idx[d] and r[2]<=10) for d in doms]
    return sum(t10)/len(doms),sum(1 for x in t10 if x>0),len(doms)
tm=lambda pid:[d for d in P[pid]['doms'] if d.endswith('.team')]
DC=[]
for nm,ya,yb,verd in [
  ('12 страниц с датами NEW50','p12wt','n1_12wd','совпало до цифры'),
  ('7 страниц с датами NEW50','p7wt','n1_7wd','разошлось, но по дорогим ключам в обратную сторону')]:
    a,ah,an=per(ya,tm(ya)); b,bh,bn=per(yb,P[yb]['doms'])
    DC.append(dict(name=nm,a=a,ah=ah,an=an,b=b,bh=bh,bn=bn,v=verd))

ND=sum(len(p['doms']) for p in DAY)
REG=sum(p['snaps'][0]['tot']['reg'] for p in DAY)
T10=sum(p['snaps'][0]['tot']['t10'] for p in DAY)
HIT=sum(sum(1 for d in p['doms'] if p['snaps'][0]['dom'][d]['t10']) for p in DAY)
keep=set()
for p in DAY:
    for r in p['snaps'][0]['rows']: keep.add(r[0])
D=dict(pools=DAY,qd=A['qd'],pd=A['pd'],sd=A['sd'],nsnap=1,built=A['built'],dayCut=DC)
data=json.dumps(D,ensure_ascii=False,separators=(',',':'))
head=open(S+'head_keys.html',encoding='utf-8').read().replace(
    '<title>Ключи по брендам</title>','<title>Запуск 2 сентября</title>')
app=open(S+'d2app.js',encoding='utf-8').read()
extra=open(S+'sbuild.py',encoding='utf-8').read().split("extra='''",1)[1].split("'''",1)[0]
extra=extra.replace('.swbar{','.swbar{display:none;')
body=f'''
{extra}
<header><div class="wrap">
 <div class="eyebrow">Дорвеи · запуск 2 сентября, замер 3 сентября 12:03</div>
 <h1>Запуск 2 сентября</h1>
 <p class="sub">{ND} доменов в девяти ветках, запущены в один час — с 16:19 до 16:21.
 На замере им около двадцати часов, и это тот возраст, на котором ветки уже разошлись
 и их можно сравнивать. Всего {T10} ключей в десятке, зашли {HIT} доменов,
 первые {REG} регистрации уже пришли.</p>
 <nav id="nav"></nav>
</div></header>
<main class="wrap" id="main"></main>
<footer><div class="wrap">Собрано {D['built']} из выгрузки позиций за 3 сентября 12:03,
реестра запусков и выгрузки конверсий. Конфигурация трёх веток наборов не прислана:
число страниц и наличие дат неизвестны.</div></footer>
<script>window.DATA={data};</script>
<script>{app}</script>
'''
open(SP+'day02.html','w',encoding='utf-8').write(head+body)
print('ok',round(os.path.getsize(SP+'day02.html')/1024),'КБ | доменов',ND,
      '| Т10',T10,'| зашло',HIT,'| рег',REG)
