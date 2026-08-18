# -*- coding: utf-8 -*-
import io
def pravka(path, pairs):
    s = io.open(path, encoding='utf-8').read()
    ok, miss = 0, []
    for a, b in pairs:
        n = s.count(a)
        if n == 1:
            s = s.replace(a, b); ok += 1
        else:
            miss.append((a[:60], n))
    io.open(path, 'w', encoding='utf-8').write(s)
    print('применено %d, пропущено %d' % (ok, len(miss)))
    for a, n in miss:
        print('  · не найдено (%d): %s' % (n, a))
