import json
D=json.load(open('flat.json',encoding='utf-8'))
tpl=open('tpl3.html',encoding='utf-8').read()
js=open('app4.js',encoding='utf-8').read()
dj=json.dumps(D,ensure_ascii=False).replace('</','<\\/')
html=tpl.replace('__DATA__',dj).replace('<script src="app4.js"></script>','<script>\n'+js+'\n</script>')
open('report3.html','w',encoding='utf-8').write(html)
print('report3.html', len(html))
