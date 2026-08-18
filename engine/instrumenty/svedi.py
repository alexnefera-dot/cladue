# -*- coding: utf-8 -*-
"""Сводит часть уникальных анкорных меток в дубли — опускает anchor_once_pct."""
import io, re, collections, sys
f = sys.argv[1]; need = int(sys.argv[2]) if len(sys.argv) > 2 else 4
s = io.open(f, encoding='utf-8').read()
a = re.findall(r'<a href="([^"]*)">(.*?)</a>', s)
c = collections.Counter([(h, t.lower()) for h, t in a])
singles = [(h, t) for (h, t), n in c.items() if n == 1]
by = collections.defaultdict(list)
for h, t in singles: by[h].append(t)
done = 0
for h, lst in by.items():
    while len(lst) >= 2 and done < need:
        keep, drop = lst[0], lst.pop()
        pat = '<a href="%s">%s</a>' % (h, drop)
        i = s.rfind(pat)
        if i < 0:
            pat = '<a href="%s">%s</a>' % (h, drop[0].upper() + drop[1:])
            i = s.rfind(pat)
            if i < 0: continue
        s = s[:i] + '<a href="%s">%s</a>' % (h, keep) + s[i+len(pat):]
        done += 1
io.open(f, 'w', encoding='utf-8').write(s)
print('сведено', done)
