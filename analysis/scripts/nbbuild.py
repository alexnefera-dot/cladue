import json
head=open('/home/user/cladue/analysis/scripts/head_keys.html',encoding='utf-8').read()
head=head.replace('<title>Ключи по брендам</title>','<title>Глубина адреса и позиция</title>',1)
head=head.replace('</style>','''
.bar{display:inline-block;width:96px;height:7px;background:var(--raise);border:1px solid var(--line);
 border-radius:2px;vertical-align:middle;overflow:hidden}
.bar i{display:block;height:100%;background:var(--teal)}
.bar.g i{background:var(--good)} .bar.b i{background:var(--bad)}
</style>''',1)
D=json.load(open('nestbig.json'))
app=open('/home/user/cladue/analysis/scripts/nbapp.js',encoding='utf-8').read()
M=D['meta']
body=f'''
<header><div class="wrap">
  <div class="eyebrow">27 августа — 1 сентября · {M['n']} пар ключ × домен · {M['doms']} доменов · {len(M['pairs'])} переходов между съёмами</div>
  <h1>Глубина адреса и позиция</h1>
  <p class="sub">Даёт ли рост числа повторов <code>/ru</code> в адресе более высокую позицию.
  Разбор по всем соседним съёмам за неделю, с контролем стартовой позиции, домена
  и направления изменения.</p>
  <nav>
    <button data-s="a" aria-selected="true">Ответ</button>
    <button data-s="b">Порог и контроли</button>
    <button data-s="c">Уровень глубины</button>
    <button data-s="d">Выводы</button>
  </nav>
</div></header>
<main class="wrap">
  <section id="a"></section>
  <section id="b" hidden></section>
  <section id="c" hidden></section>
  <section id="d" hidden></section>
</main>
<footer><div class="wrap">Данные: launches*.xlsx за 27.08–01.09.
Расчёт — analysis/scripts/nestbig.py</div></footer>
<script>const D={json.dumps(D,ensure_ascii=False)};</script>
<script>{app}</script>
'''
open('nest.html','w',encoding='utf-8').write(head+body)
print('nest.html',len(head+body))
