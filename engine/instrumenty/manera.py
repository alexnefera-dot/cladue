import os, re, sys, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tekst import bloki

BASE = sys.argv[1]
rows = []
for nabor in sorted(os.listdir(BASE)):
    d = os.path.join(BASE, nabor)
    if not os.path.isdir(d): continue
    ru = en = h2b = h2all = 0
    stranicy = 0; slova = []
    for f in sorted(os.listdir(d)):
        if not f.endswith('.html'): continue
        bl = bloki(os.path.join(d, f))
        txt = ' '.join(t for _, t in bl)
        ru += len(re.findall(r'%brand_name_ru%', txt))
        en += len(re.findall(r'%brand_name_en%', txt))
        for tag, t in bl:
            if tag == 'h2':
                h2all += 1
                if '%brand_name' in t: h2b += 1
        slova.append(len(re.findall(r'[А-Яа-яЁёA-Za-z]+', txt)))
        stranicy += 1
    vsego = ru + en
    rows.append((nabor, stranicy, vsego / max(stranicy,1), en / max(vsego,1) * 100,
                 h2b / max(h2all,1) * 100, st.median(slova) if slova else 0))
rows.sort(key=lambda r: -r[2])
print('%-16s %3s %7s %7s %7s %7s' % ('набор','стр','бренд/с','лат%','h2-бр%','слов'))
for r in rows:
    print('%-16s %3d %7.1f %7.1f %7.1f %7.0f' % r)
