# -*- coding: utf-8 -*-
import io, re, sys
def razbei(f, porog=66, minw=18):
    s = io.open(f, encoding='utf-8').read()
    wc = lambda t: len(re.findall(r'[\w]+', re.sub(r'<[^>]+>', ' ', t), re.U))
    out, pos, n = [], 0, 0
    for m in re.finditer(r'<p>\n(.*?)\n</p>', s, re.S):
        body = m.group(1); out.append(s[pos:m.start()]); pos = m.end()
        if wc(body) < porog: out.append(m.group(0)); continue
        sent = [x.end() for x in re.finditer(r'[.!?]\s', body)]
        if not sent: out.append(m.group(0)); continue
        cut = min(sent, key=lambda x: abs(x - len(body)//2))
        a, b = body[:cut].rstrip(), body[cut:].strip()
        if wc(a) < minw or wc(b) < minw: out.append(m.group(0)); continue
        out.append('<p>\n' + a + '\n</p>\n<p>\n  ' + b + '\n</p>'); n += 1
    out.append(s[pos:])
    io.open(f, 'w', encoding='utf-8').write(''.join(out))
    print('разбито', n)
if __name__ == '__main__':
    razbei(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 66)
