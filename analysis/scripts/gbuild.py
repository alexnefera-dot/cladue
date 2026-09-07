import json,os
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
S='/home/user/cladue/analysis/scripts/'
D=json.load(open(SP+'groups.json'))
head=open(S+'head_keys.html',encoding='utf-8').read().replace(
    '<title>Ключи по брендам</title>','<title>Группы запуска и деньги</title>')
app=open(S+'gapp.js',encoding='utf-8').read()
T=D['tot']
extra='''
<style>
select{font-family:var(--body);font-size:13px;background:var(--raise);color:var(--tx);
  border:1px solid var(--line2);border-radius:2px;padding:5px 9px}
label{font-size:12px;color:var(--mut);display:inline-flex;align-items:center;gap:6px}
.ctl{display:flex;flex-wrap:wrap;gap:14px;align-items:center;margin:0 0 12px;
  padding:12px 14px;background:var(--surf);border:1px solid var(--line);border-radius:3px}
nav button:focus-visible,select:focus-visible,tr.grow:focus-visible{outline:2px solid var(--teal);outline-offset:-2px}

tr.grow{cursor:pointer}
tr.grow:hover td{background:var(--raise)}
tr.grow.sel td{background:#1b2130;border-bottom-color:transparent}
tr.grow.dim td:not(.l){color:var(--dim)}
.gname{font-family:var(--mono);font-size:12.5px;color:var(--tx);margin-right:6px}
.gold{color:var(--gold)}
.tag.ok{color:var(--good);border-color:#24492f;background:#12241a}
.tag.bad2{color:var(--bad);border-color:#522a2d;background:#2e1518}
.tag.warn2{color:var(--warn);border-color:#5c4a24;background:#241d0f}
.note.sm2{font-size:11.5px;margin:2px 0 0}

tr.det td{padding:0;background:#151a24}
.dbox{padding:12px 16px 14px;display:flex;flex-direction:column;gap:12px}
.dsec .dh{font-family:var(--cond);text-transform:uppercase;letter-spacing:.08em;
  font-size:10px;color:var(--mut);font-weight:600;margin-bottom:5px}
table.inner{width:auto;border-collapse:collapse}
table.inner td{padding:3px 14px 3px 0;border:0;font-size:12.5px;vertical-align:middle}
table.inner td.num{font-family:var(--mono);white-space:nowrap}
.flat{display:flex;flex-wrap:wrap;gap:2px}

.bars{display:flex;flex-direction:column;gap:3px;border:1px solid var(--line);
  border-radius:3px;background:var(--surf);padding:14px 16px}
.brow2{display:grid;grid-template-columns:82px 1fr 46px;align-items:center;gap:10px}
.blab{font-family:var(--mono);font-size:12px;color:var(--mut);text-align:right}
.btrack{height:14px;background:var(--raise);border-radius:2px;position:relative}
.bfill{position:absolute;left:0;top:0;bottom:0;background:var(--gold);border-radius:0 4px 4px 0;min-width:2px}
.bval{font-family:var(--mono);font-size:12.5px;font-weight:600;color:var(--tx)}
h3.vt{margin-top:24px}
@media(max-width:640px){.brow2{grid-template-columns:64px 1fr 40px}}
</style>
'''
body=f'''
<header><div class="wrap">
 <div class="eyebrow">Дорвеи · конверсии 21 августа — 7 сентября</div>
 <h1>Группы запуска и деньги</h1>
 <p class="sub">{T['g']} групп, {T['n']} доменов, {T['r']} регистраций и {T['dep']} депозитов.
 Для каждой группы видно, сколько её доменов дало деньги из всех запущенных,
 и какие именно домены сработали. {T['zero']} групп не дали ничего.</p>
 <nav id="nav"></nav>
</div></header>
<main class="wrap" id="main"></main>
<footer><div class="wrap">Собрано {D['built']}. Доля считается от всех доменов группы,
а не от тех, что попали в выгрузку конверсий. Группы с незакрытым окном помечены —
их доля ещё вырастет, ставить их рядом с закрытыми нельзя.</div></footer>
<script>window.DATA={json.dumps(D,ensure_ascii=False,separators=(',',':'))};</script>
<script>{app}</script>
'''
open(SP+'groups.html','w',encoding='utf-8').write(head+extra+body)
print('ok',round(os.path.getsize(SP+'groups.html')/1024),'КБ |',T['g'],'групп')
