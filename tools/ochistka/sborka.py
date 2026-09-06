# -*- coding: utf-8 -*-
import io, os, re, sys
sys.path.insert(0,'.')
from normalize import normalize, FAQ_TPL

SRC='vhod-arch'; DST='vyhod'
BRAND={'3fe.casino':['Eva'],'53d.casino':['Eva'],'9h2.casino':['Eva'],'9q5.casino':['Eva'],
       'djn.casino':[],'e8x.casino':[],'xjr.casino':[],'yhl.casino':[]}
TYPES=['main','app','bonus','registracia','slots','vhod','zerkalo']
FAQ_H2={'main':'Ответы на частые вопросы','app':'Ответы на вопросы о приложении',
        'bonus':'Ответы на вопросы о бонусах','registracia':'Ответы на вопросы о регистрации',
        'slots':'Ответы на вопросы об автоматах','vhod':'Ответы на вопросы о входе',
        'zerkalo':'Ответы на вопросы о зеркале'}
# сколько пар FAQ держит профиль
FAQ_N={'main':9,'app':10,'bonus':4,'registracia':10,'slots':8,'vhod':8,'zerkalo':4}

os.makedirs(DST, exist_ok=True)
for site in sorted(BRAND):
    os.makedirs(os.path.join(DST,site), exist_ok=True)
    for f in sorted(os.listdir(os.path.join(SRC,site))):
        t = f[:-5]
        raw = io.open(os.path.join(SRC,site,f), encoding='utf-8').read()
        body, faqs = normalize(raw, BRAND[site])
        if t in TYPES:
            n = FAQ_N[t]
            keep = faqs[:n]
            if keep:
                body += '\n\n<h2>%s %%brand_name_en%%</h2>\n' % FAQ_H2[t]
                body += '\n'.join(FAQ_TPL.format(q=q, a=a) for q, a in keep)
            io.open(os.path.join(DST,site,f),'w',encoding='utf-8').write(body+'\n')
        # служебные страницы (about/contacts/privacy) в состав не входят
print('готово')
