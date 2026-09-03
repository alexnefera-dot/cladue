import json,os
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
S='/home/user/cladue/analysis/scripts/'
head=open(S+'head_keys.html',encoding='utf-8').read()
head=head.replace('<title>Ключи по брендам</title>','<title>Домены последних запусков</title>')
data=open(SP+'snapr.json',encoding='utf-8').read()
app=open(S+'sapp.js',encoding='utf-8').read()
D=json.loads(data)
ND=sum(len(p['doms']) for p in D['pools'] if not p.get('excl'))
extra='''
<style>
.swbar{position:sticky;top:0;z-index:20;background:var(--surf);border-bottom:1px solid var(--line);padding:11px 0}
.swbar .wrap{display:flex;flex-wrap:wrap;align-items:center;gap:11px}
.swl{font-family:var(--cond);text-transform:uppercase;letter-spacing:.1em;font-size:10.5px;color:var(--gold);font-weight:600}
#sw{display:flex;gap:3px;flex-wrap:wrap}
#sw button{font-family:var(--cond);font-size:13.5px;font-weight:600;background:var(--raise);border:1px solid var(--line2);
  color:var(--mut);padding:6px 14px;border-radius:2px;cursor:pointer}
#sw button:hover{color:var(--tx)}
#sw button[aria-pressed="true"]{background:#241d0f;border-color:#5c4a24;color:var(--gold)}
#sw button:focus-visible,nav button:focus-visible,.more:focus-visible{outline:2px solid var(--teal);outline-offset:2px}
.swhint{color:var(--dim);font-size:12px}
select,input#kq{font-family:var(--body);font-size:13px;background:var(--raise);color:var(--tx);
  border:1px solid var(--line2);border-radius:2px;padding:5px 9px}
input#kq{min-width:240px;font-family:var(--mono)}
.brow select,.brow input{margin-right:8px}
.pill.p-money{background:#12241a;color:var(--good);border:1px solid #24492f}
.tag.ok{color:var(--good);border-color:#24492f;background:#12241a}
h3.vt{margin-top:26px}
.bch.warnc{color:var(--mut);border-color:#5c4a24;background:#241d0f;font-family:var(--body);font-size:12px}

.gsec{margin-bottom:34px}
.ghead{border-left:2px solid var(--gold);padding:2px 0 2px 13px;margin-bottom:14px}
.ghead h3{font-size:19px;font-family:var(--cond);font-weight:600;margin:0}
.gd{margin:3px 0 0;font-size:13.5px;color:var(--gold)}
.gd2{margin:4px 0 0;font-size:13.5px;color:var(--mut);max-width:100ch}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(430px,1fr));gap:13px;align-items:start}
.dcard{background:var(--surf);border:1px solid var(--line);border-radius:3px;padding:14px 16px 12px}
.dcard.empty{background:#191a1e;border-color:#2a2229}
.dh{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:11px}
.dn{font-family:var(--mono);font-size:16px;font-weight:600;color:var(--tx)}
.p-up{background:#12241a;color:var(--good);border:1px solid #24492f}
.p-dn{background:#2e1518;color:var(--bad);border:1px solid #522a2d}
.dstats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:10px 0;
  border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin-bottom:11px}
.dstats>div{display:flex;flex-direction:column;gap:1px}
.sv{font-family:var(--mono);font-size:21px;font-weight:600;line-height:1.1}
.sl{font-family:var(--cond);font-size:10px;text-transform:uppercase;letter-spacing:.07em;color:var(--dim);
  font-weight:600;line-height:1.25}
.drow{display:flex;gap:9px;margin-bottom:9px;align-items:baseline}
.drow .mk{flex:0 0 96px;line-height:1.35}
.dv{flex:1;min-width:0;font-size:13px}
.dnote{margin:0;font-size:13px;color:var(--mut)}
.klist{border:1px solid var(--line);border-radius:2px;margin-bottom:10px;overflow:hidden}
.kr{display:grid;grid-template-columns:34px 1fr auto auto auto;gap:8px;align-items:baseline;
  padding:5px 9px;border-bottom:1px solid var(--line);font-size:12.5px}
.kr:last-child{border-bottom:0}
.kr:nth-child(odd){background:#1c1f29}
.kp{font-family:var(--mono);font-weight:600;text-align:right}
.kq2{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.kb{font-size:11.5px;color:var(--mut)}
.kpg{font-family:var(--mono);font-size:11px;color:var(--dim);max-width:14ch;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.more{display:block;width:100%;background:var(--raise);border:0;border-top:1px solid var(--line);
  color:var(--teal);font-family:var(--cond);font-size:12px;font-weight:600;padding:6px;cursor:pointer}
.more:hover{color:var(--tx)}
.uex{font-family:var(--mono);font-size:11px;color:var(--dim);margin-top:3px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(max-width:700px){.cards{grid-template-columns:1fr}.dstats{grid-template-columns:repeat(2,1fr)}}
</style>
'''
body=f'''
<header>
 <div class="wrap">
  <div class="eyebrow">Дорвеи · замер 3 сентября, 12:03</div>
  <h1>Домены последних запусков</h1>
  <p class="sub">{ND} доменов из шестнадцати групп, запущенных 31 августа, 1 и 2 сентября.
  Вкладка «Сравнения» показывает, что с чем поставлено рядом и что из этого вышло;
  остальные — сами домены, бренды и ключи. Переключатель сверху меняет замер позиций:
  первый замер показывает, кто быстрее проиндексировался, а не кто лучше, поэтому сравнивать
  группы можно только на возрасте около двадцати часов.</p>
  <nav id="nav"></nav>
 </div>
</header>
<div class="swbar"><div class="wrap">
  <span class="swl">Замер позиций</span><div id="sw"></div>
  <span class="swhint">у некоторых групп замеров меньше — тогда показан самый свежий, это подписано</span>
</div></div>
<main class="wrap" id="main"></main>
<footer><div class="wrap">Собрано {D['built']}. Возраст домена считается от запуска;
для группы <code>nabor-244…253</code> и всех групп 1 сентября точное время запуска не присылали,
там считается от времени создания контента.</div></footer>
<script>window.DATA={data};</script>
<script>{app}</script>
'''
open(SP+'snapr.html','w',encoding='utf-8').write(head+extra+body)
print('ok',round(os.path.getsize(SP+'snapr.html')/1024),'КБ')
