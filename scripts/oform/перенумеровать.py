#!/usr/bin/env python3
"""Нумерация картинок подряд с единицы: после чистки неиспользованных остаются дыры."""
import os, re, sys

def перенумеровать(kit: str) -> int:
    imgs = os.path.join(kit, 'images')
    if not os.path.isdir(imgs): return 0
    переименовано = 0
    for f in sorted(os.listdir(kit)):
        if not f.endswith('.html'): continue
        стр = f[:-5]
        путь = os.path.join(kit, f)
        html = open(путь, encoding='utf-8').read()
        порядок = []
        for m in re.finditer(r'images/(%s_img_\d+\.webp)' % re.escape(стр), html):
            if m.group(1) not in порядок: порядок.append(m.group(1))
        карта = {}
        for i, старое in enumerate(порядок, 1):
            новое = '%s_img_%d.webp' % (стр, i)
            if старое != новое: карта[старое] = новое
        if not карта: continue
        врем = {}
        for старое, новое in карта.items():
            t = os.path.join(imgs, старое + '.tmp')
            os.rename(os.path.join(imgs, старое), t); врем[t] = новое
        for t, новое in врем.items():
            os.rename(t, os.path.join(imgs, новое)); переименовано += 1
        for k, (старое, _) in enumerate(карта.items()):
            html = html.replace('images/' + старое, 'images/@%d@' % k)
        for k, (_, новое) in enumerate(карта.items()):
            html = html.replace('images/@%d@' % k, 'images/' + новое)
        open(путь, 'w', encoding='utf-8').write(html)
    return переименовано

if __name__ == '__main__':
    корень = sys.argv[1]
    n = sum(перенумеровать(os.path.join(корень, d)) for d in sorted(os.listdir(корень))
            if os.path.isdir(os.path.join(корень, d)))
    print('переименовано картинок:', n)
