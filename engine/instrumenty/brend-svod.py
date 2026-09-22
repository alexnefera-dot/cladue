# -*- coding: utf-8 -*-
import re, sys, os, glob, statistics as st
def text(h): return re.sub(r'\s+',' ',re.sub(r'(?is)<(script|style)\b.*?</\1>',' ',h))
def nabor(d):
    ff=sorted(glob.glob(d+'/*.html'))
    if not ff: return None
    ru=en=0; h2b=h2a=0; pervT=0; str_=0; vlozh=0; na_str=[]
    bezBrenda=0
    for f in ff:
        h=open(f,encoding='utf-8',errors='ignore').read()
        t=re.sub(r'<[^>]+>',' ',text(h))
        r=len(re.findall(r'%brand_name_ru%',t)); e=len(re.findall(r'%brand_name_en%',t))
        ru+=r; en+=e; na_str.append(r+e); str_+=1
        if r+e==0: bezBrenda+=1
        for m in re.findall(r'(?is)<h2\b[^>]*>(.*?)</h2>',h):
            h2a+=1
            if '%brand_name' in m: h2b+=1
        slova=re.findall(r'[А-Яа-яЁёA-Za-z%_]+', t)
        tret=' '.join(slova[:max(1,len(slova)//3)])
        if '%brand_name_ru%' in tret or '%brand_name_en%' in tret: pervT+=1
        vlozh+=len(re.findall(r'(?is)<a\b[^>]*>(?:(?!</a>).)*<a\b',h))
    vsego=ru+en
    return {
      'бренд на страницу': round(vsego/str_,2),
      'бренд: медиана по страницам': st.median(na_str),
      'бренд: макс на странице': max(na_str),
      'страниц без бренда': bezBrenda,
      'доля латиницы в бренде, %': round(en*100/max(1,vsego),1),
      'бренд в h2, %': round(h2b*100/max(1,h2a),1),
      'страниц с брендом в первой трети, %': round(pervT*100/str_,1),
      'вложенных ссылок на набор': vlozh,
    }
def svod(uzor):
    rows=[nabor(d) for d in sorted(glob.glob(uzor))]
    rows=[r for r in rows if r]
    return {k:(round(st.median([r[k] for r in rows]),2), round(min(r[k] for r in rows),2), round(max(r[k] for r in rows),2)) for k in rows[0]}, len(rows)
a,na=svod(sys.argv[1]); b,nb=svod(sys.argv[2])
print('наборов: %d и %d'%(na,nb))
for k in a:
    x,y=a[k],b[k]
    print('| %s | %s | %s–%s | %s | %s–%s |'%(k,x[0],x[1],x[2],y[0],y[1],y[2]))
