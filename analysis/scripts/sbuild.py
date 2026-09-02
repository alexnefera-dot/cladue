import json,io,os
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
S='/home/user/cladue/analysis/scripts/'
head=open(S+'head_keys.html',encoding='utf-8').read()
head=head.replace('<title>Ключи по брендам</title>','<title>Последние запуски по съёмам</title>')
data=open(SP+'snapr.json',encoding='utf-8').read()
app=open(S+'sapp.js',encoding='utf-8').read()
D=json.loads(data)
extra='''
<style>
.swbar{position:sticky;top:0;z-index:20;background:var(--surf);border-bottom:1px solid var(--line);padding:10px 0}
.swbar .wrap{display:flex;flex-wrap:wrap;align-items:center;gap:10px}
.swl{font-family:var(--cond);text-transform:uppercase;letter-spacing:.1em;font-size:10.5px;color:var(--gold);font-weight:600}
#sw{display:flex;gap:2px;flex-wrap:wrap}
#sw button{font-family:var(--cond);font-size:13.5px;font-weight:600;background:var(--raise);border:1px solid var(--line2);
  color:var(--mut);padding:5px 13px;border-radius:2px;cursor:pointer}
#sw button:hover{color:var(--tx)}
#sw button[aria-pressed="true"]{background:#241d0f;border-color:#5c4a24;color:var(--gold)}
select,input#kq{font-family:var(--body);font-size:13px;background:var(--raise);color:var(--tx);
  border:1px solid var(--line2);border-radius:2px;padding:4px 8px}
input#kq{min-width:230px;font-family:var(--mono)}
.brow select,.brow input{margin-right:8px}
.swhint{color:var(--dim);font-size:12px}
</style>
'''
body=f'''
<header>
 <div class="wrap">
  <div class="eyebrow">Дорвеи · пулы 31.08 и 01.09</div>
  <h1>Последние запуски по съёмам</h1>
  <p class="sub">Восемь пулов, {sum(len(p['doms']) for p in D['pools'] if not p.get('excl'))} доменов, {len(D['qd'])} ключей.
  Переключатель сверху меняет съём: первый показывает, кто быстрее проиндексировался, последний — кто реально стоит.
  Сравнивать пулы между собой по первому и второму съёму нельзя — это уже пять раз разворачивало выводы.</p>
  <nav id="nav"></nav>
 </div>
</header>
<div class="swbar"><div class="wrap">
  <span class="swl">Съём</span><div id="sw"></div>
  <span class="swhint">у пулов разное число съёмов — если выбранного нет, показывается последний</span>
</div></div>
<main class="wrap" id="main"></main>
<footer><div class="wrap">Собрано {D['built']} из выгрузок L31/L01/L02/L03/L04.
Возраст считается от времени запуска, для пулов 01.09 — от времени создания контента.</div></footer>
<script>window.DATA={data};</script>
<script>{app}</script>
'''
open(SP+'snapr.html','w',encoding='utf-8').write(head+extra+body)
print('ok',round(os.path.getsize(SP+'snapr.html')/1024),'КБ')
