import re, zlib, sys
PDF=sys.argv[1]
pdf=open(PDF,'rb').read()
objs={}
for m in re.finditer(rb'(\d+)\s+(\d+)\s+obj(.*?)endobj', pdf, re.S):
    objs[int(m.group(1))]=m.group(3)
def stream(body):
    m=re.search(rb'stream\r?\n', body)
    if not m: return None
    s=body[m.end():body.find(b'endstream')]
    try: return zlib.decompress(s)
    except Exception: return s
def parse(d):
    mp={}
    for blk in re.findall(rb'beginbfchar(.*?)endbfchar', d, re.S):
        for a,b in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk):
            mp[int(a,16)]=bytes.fromhex(b.decode()).decode('utf-16-be','ignore')
    for blk in re.findall(rb'beginbfrange(.*?)endbfrange', d, re.S):
        for a,b,c in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk):
            lo,hi,st=int(a,16),int(b,16),int(c,16)
            for k in range(lo,hi+1): mp[k]=chr(st+(k-lo))
    return mp
fonts={}
for n,b in objs.items():
    if b'/Font' in b and b'/ToUnicode' in b:
        m=re.search(rb'/ToUnicode\s+(\d+)\s+0\s+R', b)
        if m and int(m.group(1)) in objs:
            d=stream(objs[int(m.group(1))])
            if d: fonts[n]=parse(d)
namemap={}
for n,b in objs.items():
    for nm,fo in re.findall(rb'/(F\d+)\s+(\d+)\s+0\s+R', b):
        fo=int(fo)
        if fo in fonts: namemap.setdefault(nm.decode(), fonts[fo])
out=[]
for n,b in sorted(objs.items()):
    d=stream(b)
    if not d or b'BT' not in d: continue
    cur=None
    for m in re.finditer(rb'/(F\d+)\s+[\d.]+\s+Tf|<([0-9A-Fa-f]+)>\s*Tj|\bET\b', d):
        if m.group(1): cur=namemap.get(m.group(1).decode(), {})
        elif m.group(2): out.append((cur or {}).get(int(m.group(2),16),'?'))
        else: out.append('')
s=''.join(out)
open('raw.txt','w').write(s)
print(len(s))
