# -*- coding: utf-8 -*-
import io, os, re
DST='vyhod'
TYPES=['main','app','bonus','registracia','slots','vhod','zerkalo']
NAME={'app':'клиент на телефоне','bonus':'бонусы и промокоды','registracia':'анкета игрока',
      'slots':'каталог автоматов','vhod':'вход в кабинет','zerkalo':'запасное имя','main':'разобранная площадка'}
# зачин перечня — свой у каждого типа (правило «разводить каждую повторяющуюся конструкцию»)
OPENER={
 'app':   ('<p>Рядом: {}.</p>', ' ; '),
 'bonus': ('<p>Мой замер по соседним разделам простой — {}.</p>', ', '),
 'registracia': ('<p>Что читать следом? {}.</p>', '. '),
 'slots': ('<p>Куда смотреть дальше: {}.</p>', '; '),
 'vhod':  ('<p>Соседние разборы — {} — лежат каждый на своей странице.</p>', ', '),
 'zerkalo': ('<p>Остальное разложено по соседям: {}.</p>', '; '),
}
ORDER={'app':['zerkalo','registracia','slots','vhod'],
       'bonus':['vhod','app','slots','registracia'],
       'registracia':['slots','vhod','zerkalo','app'],
       'slots':['app','vhod','registracia','zerkalo'],
       'vhod':['registracia','zerkalo','app','slots'],
       'zerkalo':['app','slots','registracia','vhod']}

for site in sorted(os.listdir(DST)):
    sp=os.path.join(DST,site)
    if not os.path.isdir(sp): continue
    have=[t for t in TYPES if os.path.isfile(os.path.join(sp,t+'.html'))]
    # 1. срезать лишние ссылки на / с внутренних: оставить максимум 2 на комплект
    left=2
    for t in have:
        if t=='main': continue
        p=os.path.join(sp,t+'.html'); s=io.open(p,encoding='utf-8').read()
        def cut(m):
            global left
            if left>0:
                left-=1; return m.group(0)
            return m.group(1)
        s=re.sub(r'<a href="/">(.*?)</a>', cut, s, flags=re.S)
        io.open(p,'w',encoding='utf-8').write(s)
    # 2. перечень ссылок в конец каждой внутренней (перед FAQ-H2)
    for t in have:
        if t=='main': continue
        p=os.path.join(sp,t+'.html'); s=io.open(p,encoding='utf-8').read()
        tgt=[x for x in ORDER[t] if x in have and x!=t]
        if not tgt: continue
        tpl,sep=OPENER[t]
        items=[]
        for x in tgt:
            if t=='registracia': items.append('Про «%s» — <a href="/%s">%s</a>' % (NAME[x],x,NAME[x]))
            else: items.append('<a href="/%s">%s</a>' % (x,NAME[x]))
        block=tpl.format(sep.join(items))
        m=re.search(r'\n<h2>Ответы', s)
        if m: s=s[:m.start()]+'\n'+block+s[m.start():]
        else: s=s.rstrip()+'\n'+block+'\n'
        io.open(p,'w',encoding='utf-8').write(s)
print('готово')
