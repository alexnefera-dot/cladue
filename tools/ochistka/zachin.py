# -*- coding: utf-8 -*-
import io, os, re
DST='vyhod'
TYPES=['app','bonus','registracia','slots','vhod','zerkalo']
EM={'app':'📱','bonus':'🎁','registracia':'📝','slots':'🎰','vhod':'🔑','zerkalo':'🔁'}
TXT={'app':'клиент на телефоне','bonus':'бонусы и промокоды','registracia':'анкета игрока',
     'slots':'игровые автоматы','vhod':'вход в кабинет','zerkalo':'запасное имя'}
TAIL={'app':'сборка и её вес','bonus':'условия акций','registracia':'документы и анкета',
      'slots':'зал и его механики','vhod':'пароль и сеанс','zerkalo':'свежий адрес'}

for site in sorted(os.listdir(DST)):
    sp=os.path.join(DST,site)
    if not os.path.isdir(sp): continue
    have=[t for t in TYPES if os.path.isfile(os.path.join(sp,t+'.html'))]
    p=os.path.join(sp,'main.html')
    if not os.path.isfile(p): continue
    s=io.open(p,encoding='utf-8').read()
    # список-оглавление после первого блока
    ul='<ul>\n'+'\n'.join('<li>%s <strong><a href="/%s">%s</a></strong> — %s</li>'
        % (EM[t],t,TXT[t],TAIL[t]) for t in have)+'\n</ul>'
    m=re.search(r'</(p|h2|h3|table|blockquote|ul|ol)>', s)
    if m: s=s[:m.end()]+'\n'+ul+s[m.end():]
    else: s=ul+'\n'+s
    # хвостовой перечень перед FAQ
    tail='<p>Соседние разделы этой площадки: '+'; '.join(
        '<a href="/%s">%s</a>' % (t,TXT[t]) for t in have)+'.</p>'
    m=re.search(r'\n<h2>Ответы', s)
    if m: s=s[:m.start()]+'\n'+tail+s[m.start():]
    else: s=s.rstrip()+'\n'+tail+'\n'
    io.open(p,'w',encoding='utf-8').write(s)

# у внутренних lead_list должен быть 0: если ul/ol попал в первую четвёрку — подвинуть ниже
for site in sorted(os.listdir(DST)):
    sp=os.path.join(DST,site)
    if not os.path.isdir(sp): continue
    for f in sorted(os.listdir(sp)):
        if not f.endswith('.html') or f=='main.html': continue
        p=os.path.join(sp,f); s=io.open(p,encoding='utf-8').read()
        blocks=re.findall(r'<(h2|h3|p|ul|ol|table|blockquote|dl)\b', s, flags=re.I)
        if not any(b.lower() in ('ul','ol') for b in blocks[:4]): continue
        m=re.search(r'<(ul|ol)\b.*?</\1>', s, flags=re.S)
        if not m: continue
        blk=m.group(0); s=s[:m.start()]+s[m.end():]
        mm=None
        for mm2 in re.finditer(r'</(p|h3|table|blockquote)>', s):
            mm=mm2
            if len(re.findall(r'<(h2|h3|p|ul|ol|table|blockquote|dl)\b', s[:mm2.end()], flags=re.I))>=4: break
        if mm: s=s[:mm.end()]+'\n'+blk+s[mm.end():]
        else: s=s+'\n'+blk
        io.open(p,'w',encoding='utf-8').write(s)
print('готово')
