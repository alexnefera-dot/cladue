import json,os
SP='/tmp/claude-0/-home-user-cladue/7a7c5bac-d634-59c6-bc3f-c4e28ea7944c/scratchpad/'
S='/home/user/cladue/analysis/scripts/'
D=json.load(open(SP+'e50.json'))
head=open(S+'head_keys.html',encoding='utf-8').read().replace(
    '<title>Ключи по брендам</title>','<title>Последняя выгрузка конверсий</title>')
app=open(S+'eapp.js',encoding='utf-8').read()
extra='''
<style>
.cuts{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px}
.cuts.two{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
.cut{background:var(--surf);border:1px solid var(--line);border-radius:3px;padding:14px 16px}
.cut h3{font-size:14px;margin:0 0 9px;color:var(--tx)}
table.ct{width:100%;border-collapse:collapse}
table.ct td{padding:3px 0;border:0;font-size:12.5px;vertical-align:middle}
table.ct td.k{font-family:var(--mono);font-size:11.5px;color:var(--tx);
  max-width:230px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-right:10px}
table.ct td.bar{width:34%;padding-right:10px}
table.ct td.n{font-family:var(--mono);font-size:12px;text-align:right;
  white-space:nowrap;padding-left:8px;color:var(--tx)}
table.ct td.n .u{color:var(--mut);font-size:10.5px}
.bt{display:flex;height:11px;background:var(--raise);border-radius:2px;overflow:hidden}
.bf{background:var(--teal);min-width:2px}
.bf.dep{background:var(--gold)}
.lg{display:flex;gap:14px;font-size:11px;color:var(--mut);margin:0 0 10px;align-items:center}
.lg i{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.gold{color:var(--gold)}
.nw{white-space:nowrap}
.tag.ok{color:var(--good);border-color:#24492f;background:#12241a}
.tag.gd{color:var(--gold);border-color:#5c4a24;background:#241d0f}
tr.dep td{background:#1c1a12}
</style>
'''
body=f'''
<header><div class="wrap">
 <div class="eyebrow">Дорвеи · выгрузка {D['days'][0][8:10]}.{D['days'][0][5:7]}–{D['days'][-1][8:10]}.{D['days'][-1][5:7]}</div>
 <h1>Последняя выгрузка конверсий</h1>
 <p class="sub">{D['n']} строк из файла: {D['reg']} регистраций и {D['dep']} депозитов
 на {D['doms']} доменах. Каждое событие привязано к группе контента, доменной зоне
 и дню запуска домена. Только эта выгрузка — истории и сравнений здесь нет.</p>
</div></header>
<main class="wrap" id="main"></main>
<footer><div class="wrap">Собрано {D['built']}. День запуска и группа взяты из реестра
запусков; там, где список не присылали, стоит прочерк.</div></footer>
<script>window.DATA={json.dumps(D,ensure_ascii=False,separators=(',',':'))};</script>
<script>{app}</script>
'''
open(SP+'e50.html','w',encoding='utf-8').write(head+extra+body)
print('ok',round(os.path.getsize(SP+'e50.html')/1024),'КБ')
