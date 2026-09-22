# -*- coding: utf-8 -*-
"""Собирает файл для вычитки: слева страница конкурента, справа наша."""
import os, re, sys, html as H
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tekst import bloki

STRANICY = ['main','obzor','bonus','slots','zerkalo','registracia','vhod',
            'app','promo','news','info','partnery']

def metriki(path):
    s = open(path, encoding='utf-8', errors='replace').read()
    s = re.sub(r'(?is)<(script|style|svg)\b.*?</\1>', ' ', s)
    bl = bloki(path)
    txt = ' '.join(t for _, t in bl)
    slova = re.findall(r'[А-Яа-яЁёA-Za-z%]+', txt)
    abz = [t for tag, t in bl if tag == 'p']
    dlinyАбз = [len(re.findall(r'[А-Яа-яЁёA-Za-z]+', t)) for t in abz]
    brend = len(re.findall(r'%brand_name_(?:ru|en)%', txt))
    ssylki = len(re.findall(r'(?i)<a\s[^>]*href', s))
    predl = len(re.findall(r'[.!?]+(?=\s|$)', txt))
    return {
        'слов': len(slova),
        'абзацев': len(abz),
        'слов/абзац': round(sum(dlinyАбз)/len(dlinyАбз), 1) if dlinyАбз else 0,
        'предложений': predl,
        'слов/предл': round(len(slova)/predl, 1) if predl else 0,
        'бренд': brend,
        'ссылок': ssylki,
        'h2': sum(1 for tag,_ in bl if tag=='h2'),
        'h3': sum(1 for tag,_ in bl if tag=='h3'),
        'блоков': len(bl),
    }

def kolonka(path):
    out = []
    for tag, t in bloki(path):
        t = H.escape(t)
        t = re.sub(r'(%brand_name_(?:ru|en)%)', r'<mark class="br">\1</mark>', t)
        t = t.replace('\x01', '<span class="a">').replace('\x02', '</span>')
        out.append('<div class="b %s">%s</div>' % (tag, t))
    return '\n'.join(out)

def para(nazvanie, kon_dir, nash_dir, kon_imya, nash_imya):
    chasti = []
    for p in STRANICY:
        a = os.path.join(kon_dir, p + '.html')
        b = os.path.join(nash_dir, p + '.html')
        if not (os.path.exists(a) and os.path.exists(b)):
            continue
        ma, mb = metriki(a), metriki(b)
        stroki = []
        for k in ma:
            va, vb = ma[k], mb[k]
            stroki.append('<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (k, va, vb))
        chasti.append('''
<section class="page" id="%s-%s">
  <h3 class="ph">%s.html</h3>
  <details class="met"><summary>метрики страницы</summary>
    <table><thead><tr><th></th><th>%s</th><th>%s</th></tr></thead><tbody>%s</tbody></table>
  </details>
  <div class="dual">
    <div class="col left"><div class="colhead">%s · %s.html</div>%s</div>
    <div class="col right"><div class="colhead">%s · %s.html</div>%s</div>
  </div>
</section>''' % (nazvanie, p, p, H.escape(kon_imya), H.escape(nash_imya),
                 ''.join(stroki),
                 H.escape(kon_imya), p, kolonka(a),
                 H.escape(nash_imya), p, kolonka(b)))
    return '\n'.join(chasti)
