import sys, os, struct

def vint(b, p):
    v = 0; s = 0
    while True:
        x = b[p]; p += 1
        v |= (x & 0x7f) << s; s += 7
        if not x & 0x80: return v, p

def unpack(path, out):
    b = open(path,'rb').read()
    sig = b'Rar!\x1a\x07\x01\x00'
    assert b[:8] == sig, b[:8]
    p = 8
    files = []
    while p < len(b) - 8:
        p += 4                      # header CRC32
        hsize, q = vint(b, p)
        hstart = q
        htype, q = vint(b, q)
        hflags, q = vint(b, q)
        extra = data = 0
        if hflags & 0x0001: extra, q = vint(b, q)
        if hflags & 0x0002: data, q = vint(b, q)
        hend = hstart + hsize
        if htype in (2, 3):
            fflags, q = vint(b, q)
            usize, q = vint(b, q)
            attr, q = vint(b, q)
            if fflags & 0x0002: q += 4
            if fflags & 0x0004: q += 4
            comp, q = vint(b, q)
            host, q = vint(b, q)
            nlen, q = vint(b, q)
            name = b[q:q+nlen].decode('utf-8','replace')
            method = (comp >> 7) & 7
            if htype == 2:
                files.append((name, method, hend, data, usize, bool(fflags & 1)))
        p = hend + data
        if htype == 5: break        # end of archive
    for name, method, off, dsize, usize, isdir in files:
        if isdir: continue
        dst = os.path.join(out, name.replace('\\','/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if method == 0:
            open(dst,'wb').write(b[off:off+dsize])
        else:
            print('COMPRESSED(method %d): %s' % (method, name))
    print('entries:', len(files))

unpack(sys.argv[1], sys.argv[2])
