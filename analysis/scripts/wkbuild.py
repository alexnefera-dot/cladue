# Пересобирает week.html: шапка из старого файла + свежий wk.json + wapp.js
import json,io,sys,re
def pl(n,one,few,many):
    n=abs(n)%100
    if 11<=n<=14: return many
    n%=10
    return one if n==1 else (few if 2<=n<=4 else many)
old=open('week.html',encoding='utf-8').read()
i=old.index('<script>const D=')
head=old[:i]
D=json.load(open('wk.json'))
app=open('/home/user/cladue/analysis/scripts/wapp.js',encoding='utf-8').read()
import re as _re
head=_re.sub(r'<div class="eyebrow">[^<]*</div>',
  '<div class="eyebrow">21 — 31 августа · 942 домена · %d %s · %d %s</div>'%(
     D['tot']['reg'],pl(D['tot']['reg'],'регистрация','регистрации','регистраций'),
     D['tot']['dep'],pl(D['tot']['dep'],'депозит','депозита','депозитов')),head,count=1)
head=_re.sub(r'<p class="sub">.*?</p>',
  '<p class="sub">Главное: домен приносит регистрации около шести суток после выкладки и дальше\n  замолкает; русский трафик почти не конвертит; мы занимаем не те бренды, которые платят.\n  Ниже разбор по каждому бренду, домену, группе и тесту.</p>',head,count=1,flags=_re.S)
out=head+'<script>const D='+json.dumps(D,ensure_ascii=False)+';</script>\n<script>'+app+'</script>\n'
open('week.html','w',encoding='utf-8').write(out)
print('week.html',len(out))
