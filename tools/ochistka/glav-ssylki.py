# -*- coding: utf-8 -*-
import io, os, re
DST='vyhod'
TYPES=['app','registracia','slots','vhod','zerkalo']
PAT={
 'slots': [r'игровы\w+ автомат\w*', r'каталог\w*', r'слот\w+', r'зал\w*', r'провайдер\w*', r'демо-режим\w*', r'барабан\w+'],
 'app':   [r'приложени\w+', r'мобильн\w+ клиент\w*', r'сборк\w+', r'мобильн\w+ верси\w+'],
 'vhod':  [r'вход\w* в (?:личный )?кабинет', r'личн\w+ кабинет\w*', r'авторизаци\w+', r'сеанс\w*'],
 'registracia': [r'регистраци\w+', r'анкет\w+', r'верификаци\w+'],
 'zerkalo': [r'зеркал\w+', r'домен\w*', r'запасн\w+ адрес\w*'],
}
LIMIT=28
def outside(s):
    """список (start,end) кусков текста вне тегов и вне уже существующих <a>"""
    spans=[]; pos=0
    for m in re.finditer(r'<a\b.*?</a>|<[^>]+>', s, flags=re.S):
        if m.start()>pos: spans.append((pos,m.start()))
        pos=m.end()
    if pos<len(s): spans.append((pos,len(s)))
    return spans

for site in sorted(os.listdir(DST)):
    p=os.path.join(DST,site,'main.html')
    if not os.path.isfile(p): continue
    s=io.open(p,encoding='utf-8').read()
    have=[t for t in TYPES if os.path.isfile(os.path.join(DST,site,t+'.html'))]
    cur=len(re.findall(r'href="', s))
    # ходим по кругу типам, чтобы ссылки распределились
    changed=True
    while cur<LIMIT and changed:
        changed=False
        for t in have:
            if cur>=LIMIT: break
            for pat in PAT[t]:
                if cur>=LIMIT: break
                done=False
                for a,b in outside(s):
                    m=re.search(pat, s[a:b], flags=re.I)
                    if not m: continue
                    i,j=a+m.start(), a+m.end()
                    s=s[:i]+'<a href="/%s">%s</a>' % (t, s[i:j])+s[j:]
                    cur+=1; changed=True; done=True; break
                if done: continue
    io.open(p,'w',encoding='utf-8').write(s)

# обрезать внутренние страницы, где ссылок больше 11
for site in sorted(os.listdir(DST)):
    sp=os.path.join(DST,site)
    if not os.path.isdir(sp): continue
    for f in sorted(os.listdir(sp)):
        if not f.endswith('.html') or f=='main.html': continue
        p=os.path.join(sp,f); s=io.open(p,encoding='utf-8').read()
        n=len(re.findall(r'href="', s))
        if n<=11: continue
        need=n-11
        def cut(m):
            global need
            if need>0:
                need-=1; return m.group(1)
            return m.group(0)
        s=re.sub(r'<a href="/[a-z]*">(.*?)</a>', cut, s, count=0, flags=re.S)
        io.open(p,'w',encoding='utf-8').write(s)
print('готово')
