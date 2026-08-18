# -*- coding: utf-8 -*-
import sys, os
R='%brand_name_ru%'; B='%brand_name_en%'
OUT='/home/user/cladue/samples/v3-final/ruchnoy-232/'

def build(blocks, faq, faq_h2, hero=None):
    out=[]; A=out.append
    if hero:
        A('<section class="hero"><h2>%s</h2>' % hero[0])
        A('<p>%s</p>' % hero[1])
        A('<ul>'); [A('<li>%s</li>' % i) for i in hero[2]]; A('</ul>')
        A('</section>')
    for title, secs in blocks:
        A('<h2>%s</h2>' % title)
        first=True
        for sec in secs:
            h, paras, items = sec[0], sec[1], (sec[2] if len(sec)>2 else [])
            if first:
                for piece in paras[0].split('§'): A('<p>%s</p>' % piece.strip())
                paras=paras[1:]; first=False
            A('<h3>%s</h3>' % h)
            for x in paras:
                for piece in x.split('§'): A('<p>%s</p>' % piece.strip())
            if items:
                A('<ul>'); [A('<li>%s</li>' % i) for i in items]; A('</ul>')
    A('<h2>%s</h2>' % faq_h2)
    for q,a in faq:
        A('<div itemprop="hasPart" itemscope itemtype="https://schema.org/Question">')
        A('<details><summary itemprop="name">%s</summary>' % q)
        A('<div itemprop="acceptedAnswer" itemscope itemtype="https://schema.org/Answer"><div itemprop="text"><p>%s</p></div></div>' % a)
        A('</details></div>')
    return "\n\n".join(out)+"\n"

def save(name, txt): open(OUT+name+'.html','w').write(txt)
