import json
head=open('head_keys.html',encoding='utf-8').read()
D=json.load(open('keys28.json'))
app=open('/home/user/cladue/analysis/scripts/kapp.js',encoding='utf-8').read()
T=D['tot']
body=f'''
<header><div class="wrap">
  <div class="eyebrow">Съём 28.08 12:43 против 28.08 00:30 · 31 домен · {T['brands']} брендов · {T['rows']} строк</div>
  <h1>Ключи по брендам</h1>
  <p class="sub">Позиции разобраны не по пулам доменов, а по отдельным ключам и брендам.
  Отдельно — проверка ограничения вложенности <code>/ru</code> до 20: меняет ли потолок
  то, как ведут себя ключи, у которых Яндекс сменил ранжирующий адрес.</p>
  <nav>
    <button data-s="a" aria-selected="true">Партии 7page</button>
    <button data-s="c">Ограничение /ru</button>
    <button data-s="b">Бренды и ключи</button>
  </nav>
</div></header>
<main class="wrap">
  <section id="a"></section>
  <section id="c" hidden></section>
  <section id="b" hidden></section>
</main>
<footer><div class="wrap">Данные: launches_20260828_004911.xlsx и launches_20260828_124455.xlsx,
группы 27 августа. Расчёт — analysis/scripts/keys28.py</div></footer>
<script>const D={json.dumps(D,ensure_ascii=False)};</script>
<script>{app}</script>
'''
open('keys28.html','w',encoding='utf-8').write(head+body)
print('keys28.html',len(head+body))
