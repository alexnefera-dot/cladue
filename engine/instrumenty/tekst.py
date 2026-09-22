import re, sys, html

def bloki(path):
    """Возвращает список (tag, text) по порядку: h1..h4, p, li."""
    s = open(path, encoding='utf-8', errors='replace').read()
    s = re.sub(r'(?is)<(script|style|svg)\b.*?</\1>', ' ', s)
    out = []
    for m in re.finditer(r'(?is)<(h1|h2|h3|h4|p|li|figcaption|blockquote)\b[^>]*>(.*?)</\1>', s):
        tag, body = m.group(1).lower(), m.group(2)
        if re.search(r'(?is)<(p|li|h[1-4])\b', body):   # контейнер, возьмём вложенные
            continue
        t = re.sub(r'(?is)<a\s[^>]*>', '\x01', body)
        t = re.sub(r'(?i)</a>', '\x02', t)
        t = re.sub(r'(?s)<[^>]+>', ' ', t)
        t = html.unescape(t)
        t = re.sub(r'\s+', ' ', t).strip()
        t = re.sub(r'\s+([,.;:!?%)\u00bb])', r'\1', t)
        t = re.sub(r'([(\u00ab])\s+', r'\1', t)
        t = re.sub(r'\x01\s+', '\x01', t)      # пробел внутри анкера, а не перед ним
        t = re.sub(r'\s+\x02', '\x02', t)
        if t:
            out.append((tag, t))
    return out

if __name__ == '__main__':
    for tag, t in bloki(sys.argv[1]):
        print(tag, '|', t[:200])
