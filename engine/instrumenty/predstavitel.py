# -*- coding: utf-8 -*-
"""Кого из корпуса ставить рядом на вычитку.

Раньше сосед для вычитки выбирался руками, и это спорно: один набор можно
подобрать под любой вывод. Здесь сосед — представитель своей группы: набор с
наименьшим отклонением от медианы группы по пяти опорным величинам, каждая
поделена на межквартильный размах группы, чтобы они весили сравнимо.
"""
import os, re, sys, statistics as st

ТИПЫ = ['main','obzor','slots','bonus','promo','registracia','vhod','zerkalo','app','news','partnery','info']

def метрики(d):
    слов = абз = дл = ссыл = h3 = бренд = стр = 0
    for т in ТИПЫ:
        f = os.path.join(d, т + '.html')
        if not os.path.isfile(f): continue
        s = open(f, encoding='utf-8', errors='replace').read()
        s = re.sub(r'(?is)<(script|style|svg)\b.*?</\1>', ' ', s)
        p = re.findall(r'(?is)<p\b[^>]*>(.*?)</p>', s)
        тела = [re.sub(r'\s+', ' ', re.sub(r'(?s)<[^>]+>', ' ', x)).strip() for x in p]
        w = [len(re.findall(r'[А-Яа-яЁёA-Za-z%]+', t)) for t in тела]
        стр += 1; слов += sum(w); абз += len(w); дл += sum(w)
        ссыл += len(re.findall(r'(?i)<a\s[^>]*href', s))
        h3 += len(re.findall(r'(?i)<h3\b', s))
        бренд += len(re.findall(r'%brand_name_(?:ru|en)%', s))
    if not стр: return None
    return {'слов/стр': слов/стр, 'слов/абз': (дл/абз if абз else 0),
            'ссылок/стр': ссыл/стр, 'h3/стр': h3/стр, 'бренд/стр': бренд/стр}

def выбрать(корень):
    наборы = {}
    for н in sorted(os.listdir(корень)):
        d = os.path.join(корень, н)
        if not os.path.isdir(d): continue
        м = метрики(d)
        if м: наборы[н] = м
    ключи = list(next(iter(наборы.values())))
    мед = {k: st.median([м[k] for м in наборы.values()]) for k in ключи}
    масштаб = {}
    for k in ключи:
        v = sorted(м[k] for м in наборы.values())
        n = len(v)
        масштаб[k] = max(1e-9, v[int(n*0.75)] - v[int(n*0.25)])
    оценка = {н: sum(abs(м[k]-мед[k])/масштаб[k] for k in ключи) for н, м in наборы.items()}
    порядок = sorted(оценка, key=оценка.get)
    print('медиана группы (%d наборов): %s' % (len(наборы),
          ', '.join('%s %.1f' % (k, мед[k]) for k in ключи)))
    for н in порядок[:5]:
        print('  %-14s отклонение %.2f | %s' % (н, оценка[н],
              ', '.join('%s %.1f' % (k, наборы[н][k]) for k in ключи)))
    return порядок[0]

if __name__ == '__main__':
    print('представитель:', выбрать(sys.argv[1]))
