# -*- coding: utf-8 -*-
import io, os, re
DST='vyhod'
TYPES=['app','bonus','registracia','slots','vhod','zerkalo']
NAME={'app':'клиент на телефоне','bonus':'бонусы и промокоды','registracia':'анкета игрока',
      'slots':'каталог автоматов','vhod':'вход в кабинет','zerkalo':'запасное имя'}
OPENER={'app':'<p>Рядом: {}.</p>','bonus':'<p>Мой замер по соседним разделам простой — {}.</p>',
        'registracia':'<p>Что читать следом? {}.</p>','slots':'<p>Куда смотреть дальше: {}.</p>',
        'vhod':'<p>Соседние разборы — {} — лежат каждый на своей странице.</p>',
        'zerkalo':'<p>Остальное разложено по соседям: {}.</p>'}
SEP={'app':'; ','bonus':', ','registracia':'. ','slots':'; ','vhod':', ','zerkalo':'; '}
ORDER={'app':['zerkalo','registracia','slots','vhod'],'bonus':['vhod','app','slots','registracia'],
       'registracia':['slots','vhod','zerkalo','app'],'slots':['app','vhod','registracia','zerkalo'],
       'vhod':['registracia','zerkalo','app','slots'],'zerkalo':['app','slots','registracia','vhod']}
for site in sorted(os.listdir(DST)):
    sp=os.path.join(DST,site)
    if not os.path.isdir(sp): continue
    have=[t for t in TYPES if os.path.isfile(os.path.join(sp,t+'.html'))]
    for t in have:
        p=os.path.join(sp,t+'.html'); s=io.open(p,encoding='utf-8').read()
        if len(re.findall(r'href="', s))>=3: continue
        tgt=[x for x in ORDER[t] if x in have and x!=t]
        items=['<a href="/%s">%s</a>' % (x,NAME[x]) for x in tgt]
        if t=='registracia': items=['Про «%s» — <a href="/%s">%s</a>' % (NAME[x],x,NAME[x]) for x in tgt]
        block=OPENER[t].format(SEP[t].join(items))
        m=re.search(r'\n<h2>Ответы', s)
        s = (s[:m.start()]+'\n'+block+s[m.start():]) if m else (s.rstrip()+'\n'+block+'\n')
        io.open(p,'w',encoding='utf-8').write(s)
    # главная: добить до 26+
    p=os.path.join(sp,'main.html'); s=io.open(p,encoding='utf-8').read()
    n=len(re.findall(r'href="', s))
    if n<26:
        need=26-n
        extra=[]
        pool=[x for x in have]
        i=0
        while len(extra)<need:
            extra.append(pool[i%len(pool)]); i+=1
        block='<p>Коротко по остальным узлам площадки: '+', '.join(
            '<a href="/%s">%s</a>' % (x,NAME[x]) for x in extra)+' — каждый разобран отдельной страницей.</p>'
        m=re.search(r'\n<h2>Ответы', s)
        s = (s[:m.start()]+'\n'+block+s[m.start():]) if m else (s.rstrip()+'\n'+block+'\n')
        io.open(p,'w',encoding='utf-8').write(s)
print('готово')
