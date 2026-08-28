# Пересобирает week.html: шапка из старого файла + свежий wk.json + wapp.js
import json,io,sys,re
old=open('week.html',encoding='utf-8').read()
i=old.index('<script>const D=')
head=old[:i]
D=json.load(open('wk.json'))
app=open('/home/user/cladue/analysis/scripts/wapp.js',encoding='utf-8').read()
head=head.replace('Три главных вывода: русский трафик почти не приносит регистраций,\n  мы занимаем не те бренды, которые платят, и позиции всё-таки работают —\n  но только по правильным брендам.',
  'Главное: домен приносит регистрации примерно четверо суток после выкладки и дальше\n  почти замолкает; русский трафик почти не конвертит; мы занимаем не те бренды, которые платят.')
out=head+'<script>const D='+json.dumps(D,ensure_ascii=False)+';</script>\n<script>'+app+'</script>\n'
open('week.html','w',encoding='utf-8').write(out)
print('week.html',len(out))
