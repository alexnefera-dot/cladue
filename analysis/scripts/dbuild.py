import json,os
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
S='/home/user/cladue/analysis/scripts/'
D=json.load(open(SP+'days.json'))
head=open(S+'head_keys.html',encoding='utf-8').read().replace(
    '<title>Ключи по брендам</title>','<title>Дни запуска и окна конверсий</title>')
app=open(S+'dapp.js',encoding='utf-8').read()
nd=sum(d['n'] for d in D['days'])
extra='''
<style>
select{font-family:var(--body);font-size:13px;background:var(--raise);color:var(--tx);
  border:1px solid var(--line2);border-radius:2px;padding:5px 9px;margin-right:8px}
nav button:focus-visible,select:focus-visible{outline:2px solid var(--teal);outline-offset:2px}
.dday{font-family:var(--mono);font-size:15px}
.tag.ok{color:var(--good);border-color:#24492f;background:#12241a}
.tag.bad2{color:var(--bad);border-color:#522a2d;background:#2e1518}
.tag.warn2{color:var(--warn);border-color:#5c4a24;background:#241d0f}
tr.q-cut td{background:#1d1519}
tr.q-open td{background:#1d1a12}
h3.vt{margin-top:26px}

/* мера окна: одна величина, число всегда подписано рядом */
.meter{width:96px;height:7px;background:var(--raise);border:1px solid var(--line);
  border-radius:4px;overflow:hidden}
.mfill{height:100%;background:var(--warn);border-radius:0 4px 4px 0}
.mfill.done{background:var(--line2);border-radius:4px}

/* горизонтальные столбцы: один ряд данных, значение подписано у каждого */
.bars{display:flex;flex-direction:column;gap:4px;border:1px solid var(--line);
  border-radius:3px;background:var(--surf);padding:14px 16px}
.brow2{display:grid;grid-template-columns:74px 1fr 40px;align-items:center;gap:10px}
.blab{font-family:var(--mono);font-size:12px;color:var(--mut);text-align:right}
.btrack{height:14px;background:var(--raise);border-radius:2px;position:relative}
.bfill{position:absolute;left:0;top:0;bottom:0;background:var(--gold);
  border-radius:0 4px 4px 0;min-width:2px}
.bval{font-family:var(--mono);font-size:12.5px;font-weight:600;color:var(--tx)}
@media(max-width:640px){.brow2{grid-template-columns:58px 1fr 34px}}
</style>
'''
body=f'''
<header><div class="wrap">
 <div class="eyebrow">Дорвеи · конверсии 21 августа — 3 сентября</div>
 <h1>Дни запуска и окна конверсий</h1>
 <p class="sub">{len(D['days'])} дней запуска, {nd} доменов, {D['reg']} регистраций и {D['dep']} депозитов.
 Для каждого дня видно, закрылось ли шестидневное окно заработка, попала ли вся жизнь доменов
 в выгрузку конверсий, и можно ли этот день вообще ставить рядом с другими.</p>
 <nav id="nav"></nav>
</div></header>
<main class="wrap" id="main"></main>
<footer><div class="wrap">Собрано {D['built']}. День запуска для августовских партий взят
как дата создания контента, для запусков с 31 августа — из реестра. Выгрузка конверсий
начинается 21 августа, поэтому у партий 19 и 20 августа часть жизни не покрыта.</div></footer>
<script>window.DATA={json.dumps(D,ensure_ascii=False,separators=(',',':'))};</script>
<script>{app}</script>
'''
open(SP+'days.html','w',encoding='utf-8').write(head+extra+body)
print('ok',round(os.path.getsize(SP+'days.html')/1024),'КБ | доменов',nd)
