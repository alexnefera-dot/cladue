import json
head=open('/home/user/cladue/analysis/scripts/head_keys.html',encoding='utf-8').read()
head=head.replace('<title>Ключи по брендам</title>','<title>Пулы 31 августа</title>',1)
head=head.replace('</style>','''
.bar{display:inline-block;width:88px;height:7px;background:var(--raise);border:1px solid var(--line);
 border-radius:2px;vertical-align:middle;margin-right:7px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--teal)}
.bar.g i{background:var(--good)} .bar.b i{background:var(--warn)}
.ctl{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
.ctl input,.ctl select{font-family:var(--body);font-size:13px;background:var(--surf);
 color:var(--tx);border:1px solid var(--line2);border-radius:3px;padding:6px 9px}
.ctl input{min-width:260px}
.ctl input:focus-visible,.ctl select:focus-visible{outline:2px solid var(--teal);outline-offset:-1px}
#kt thead th[data-s]:hover{color:var(--gold)}
.ok{color:var(--teal)}
</style>''',1)
D=json.load(open('pools_rep.json'))
app=open('/home/user/cladue/analysis/scripts/papp.js',encoding='utf-8').read()
A,B=D['pools'][0],D['pools'][1]
body=f'''
<header><div class="wrap">
  <div class="eyebrow">Запуски 31 августа · {A['n']+B['n']} доменов · ядро 1 049 ключей · три съёма</div>
  <h1>Пулы 31 августа</h1>
  <p class="sub">Два пула, выложенных в один вечер с разным потолком повторов <code>/ru</code>
  в адресе. Здесь видно, чем именно каждый домен ранжируется: по каким брендам,
  по каким ключам, какими страницами и с какой вложенностью.</p>
  <nav>
    <button data-s="p" aria-selected="true">Пулы и домены</button>
    <button data-s="e">Заход</button>
    <button data-s="d">Вложенность</button>
    <button data-s="pg">Страницы</button>
    <button data-s="b">Бренды</button>
    <button data-s="k">Ключи</button>
  </nav>
</div></header>
<main class="wrap">
  <section id="p"></section>
  <section id="e" hidden></section>
  <section id="d" hidden></section>
  <section id="pg" hidden></section>
  <section id="b" hidden></section>
  <section id="k" hidden></section>
</main>
<footer><div class="wrap">Данные: launches_20260831_211207.xlsx, launches_20260901_005250.xlsx,
launches_20260901_102608.xlsx. Расчёт — analysis/scripts/p01.py и pools.py</div></footer>
<script>const D={json.dumps(D,ensure_ascii=False)};</script>
<script>{app}</script>
'''
open('pools31.html','w',encoding='utf-8').write(head+body)
print('pools31.html',len(head+body))
