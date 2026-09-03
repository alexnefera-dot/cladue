import json,os,csv,collections,statistics as st,datetime as dt
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
S='/home/user/cladue/analysis/scripts/'
AN='/home/user/cladue/analysis/'
OUT=json.load(open(SP+'convrep.json'))
EV=json.load(open(SP+'conv4.json'))
# добить поля у неопознанных доменов
_sub=collections.defaultdict(collections.Counter); _geo=collections.defaultdict(collections.Counter)
for e in EV:
    if e['type']=='reg': _sub[e['dom']][e['sub']]+=1
    _geo[e['dom']][e['geo']]+=1
for o in OUT:
    o.setdefault('subs',_sub[o['dom']].most_common())
    o.setdefault('brpos',{}); o.setdefault('geo',_geo[o['dom']].most_common(3))
    for k in ('group','cfg','zone','day','lab'): o.setdefault(k,None)
    for k in ('t3','t10','t30','t100','best'): o.setdefault(k,None)
TIER={}
for r in csv.DictReader(open(AN+'keys/keys_stats.csv',encoding='utf-8-sig'),delimiter=';'):
    TIER.setdefault(r['бренд'],r['тир'])
NKEYS=sum(1 for _ in csv.DictReader(open(AN+'keys/keys_stats.csv',encoding='utf-8-sig'),delimiter=';'))
mb=collections.Counter(); md=collections.defaultdict(set)
for e in EV:
    if e['type']=='reg': mb[e['sub']]+=1; md[e['sub']].add(e['dom'])
brands=[dict(b=b,t=TIER.get(b,'нет в ядре'),n=n,d=len(md[b])) for b,n in mb.most_common()]
outcore=sum(n for b,n in mb.items() if b not in TIER)
noutb=sum(1 for b in mb if b not in TIER)
hit=miss=0; pos=[]
for o in OUT:
    if not o.get('known') or o.get('nopos'): continue
    for b,n in o['subs']:
        p=(o.get('brpos') or {}).get(b)
        if p is None or p==999: miss+=n
        else: hit+=n; pos+=[p]*n
geo=collections.Counter(e['geo'] for e in EV if e['type']=='reg').most_common()
DATA=dict(rows=OUT,reg=sum(o['reg'] for o in OUT),dep=sum(o['dep'] for o in OUT),
          ndom=len(OUT),ndep=sum(1 for o in OUT if o['dep']),
          nknown=sum(1 for o in OUT if o.get('known')),
          brands=brands,outcore=outcore,noutbrands=noutb,geo=geo,nkeys=NKEYS,
          vs=dict(hit=hit,miss=miss,med=round(st.median(pos)) if pos else None,
                  t10=sum(1 for x in pos if x<=10)),
          built=dt.datetime.now().strftime('%d.%m %H:%M'))
head=open(S+'head_keys.html',encoding='utf-8').read()
head=head.replace('<title>Ключи по брендам</title>','<title>Деньги за неделю</title>')
app=open(S+'mapp.js',encoding='utf-8').read()
extra='''
<style>
select{font-family:var(--body);font-size:13px;background:var(--raise);color:var(--tx);
  border:1px solid var(--line2);border-radius:2px;padding:5px 9px;margin-right:8px}
nav button:focus-visible{outline:2px solid var(--teal);outline-offset:-2px}
tr.hasdep td{background:#141d18}
.bch.ok{border-color:#24492f;background:#12241a;color:var(--tx)}
.bch.ok b{color:var(--good)}
.bch.no{color:var(--dim)}
.bch.no b{color:var(--bad);font-weight:500}
h3.vt{margin-top:26px}
.tr-нет{color:var(--bad);border-color:#522a2d;background:#2e1518}
</style>
'''
body=f'''
<header><div class="wrap">
 <div class="eyebrow">Дорвеи · выгрузка конверсий 27 августа — 3 сентября</div>
 <h1>Деньги за неделю</h1>
 <p class="sub">{DATA['reg']} регистраций и {DATA['dep']} депозитов на {DATA['ndom']} доменах.
 Для каждого домена — его группа контента, день запуска и позиции, чтобы видеть,
 какие конфигурации реально платят, а не только набирают ключи.</p>
 <nav id="nav"></nav>
</div></header>
<main class="wrap" id="main"></main>
<footer><div class="wrap">Собрано {DATA['built']} из выгрузки конверсий, реестра запусков
и последних замеров позиций. У восьми доменов группу установить не удалось — они, вероятно,
из базы, запущенной до 19 августа.</div></footer>
<script>window.DATA={json.dumps(DATA,ensure_ascii=False,separators=(',',':'))};</script>
<script>{app}</script>
'''
open(SP+'money.html','w',encoding='utf-8').write(head+extra+body)
print('ok',round(os.path.getsize(SP+'money.html')/1024),'КБ',
      '| рег',DATA['reg'],'деп',DATA['dep'],'| вне ядра',outcore,'| совпало',hit,'не совпало',miss)
