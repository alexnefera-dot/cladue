# -*- coding: utf-8 -*-
import re, io, sys, os, unicodedata

FAQ_TPL = ('<details itemscope itemtype="https://schema.org/Question">\n'
           '  <summary itemprop="name">{q}</summary>\n'
           '  <div itemprop="acceptedAnswer" itemscope itemtype="https://schema.org/Answer">\n'
           '    <div itemprop="text"><p>{a}</p></div>\n'
           '  </div>\n'
           '</details>')

EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿⬀-⯿️←-⇿✀-➿]')

def strip_tags(t):
    return re.sub(r'<[^>]+>', '', t)

def clean_text(t):
    t = t.replace('­','').replace('‑','-').replace('⁠','')
    t = t.replace(' ',' ').replace(' ',' ').replace(' ',' ')
    return t

def normalize(raw, brand_words):
    s = raw
    # 1. вырезать FAQ-блоки чужой разметки и переписать в каноническую
    faqs = []
    def grab(m):
        blk = m.group(0)
        q = re.search(r'itemprop="name"[^>]*>(.*?)</summary>', blk, re.S)
        a = re.search(r'itemprop="text"[^>]*>(.*?)</div>', blk, re.S)
        if not q or not a: return ''
        qq = clean_text(strip_tags(q.group(1))).strip()
        aa = clean_text(strip_tags(a.group(1))).strip()
        aa = re.sub(r'\s+',' ',aa); qq = re.sub(r'\s+',' ',qq)
        faqs.append((qq,aa))
        return '\x00FAQ\x00'
    s = re.sub(r'<div[^>]*itemprop="hasPart"[^>]*>.*?</div>\s*</div>', grab, s, flags=re.S)
    # уцелевшие одиночные details -> в обычный абзац
    def det(m):
        blk = m.group(0)
        summ = re.search(r'<summary[^>]*>(.*?)</summary>', blk, re.S)
        body = re.sub(r'<summary[^>]*>.*?</summary>', '', blk, flags=re.S)
        body = re.sub(r'</?details[^>]*>', '', body)
        head = strip_tags(summ.group(1)).strip() if summ else ''
        return ('<h3>%s</h3>\n' % head if head else '') + body
    s = re.sub(r'<details[^>]*>.*?</details>', det, s, flags=re.S)
    # 2. служебное — вон
    s = re.sub(r'<(script|style|meta|link|noscript)[^>]*>.*?</\1>', '', s, flags=re.S|re.I)
    s = re.sub(r'<(meta|link|img|hr|br)[^>]*/?>', '', s, flags=re.I)
    s = re.sub(r'<caption[^>]*>.*?</caption>', '', s, flags=re.S|re.I)
    # 3. развернуть контейнеры
    for tag in ('div','section','article','aside','footer','header','main','span','thead','tbody','tfoot','figure','figcaption','small','q','abbr','time','cite','code','kbd','samp','var','sup','sub','u','s','mark','ins','del','dfn'):
        s = re.sub(r'</?%s(?=[\s>/])[^>]*>' % tag, '', s, flags=re.I)
    # 4. em/i -> обычный текст, b -> strong
    s = re.sub(r'</?(em|i)(?=[\s>/])[^>]*>', '', s, flags=re.I)
    s = re.sub(r'<b(?=[\s>])[^>]*>', '<strong>', s, flags=re.I); s = re.sub(r'</b>(?!lockquote)', '</strong>', s, flags=re.I)
    # 5. заголовки
    s = re.sub(r'<h1[^>]*>(.*?)</h1>', r'<h2>\1</h2>', s, flags=re.S|re.I)
    s = re.sub(r'<h4[^>]*>(.*?)</h4>', r'<h3>\1</h3>', s, flags=re.S|re.I)
    s = re.sub(r'<h5[^>]*>(.*?)</h5>', r'<h3>\1</h3>', s, flags=re.S|re.I)
    s = re.sub(r'<h6[^>]*>(.*?)</h6>', r'<h3>\1</h3>', s, flags=re.S|re.I)
    # 6. атрибуты долой (кроме href и schema.org)
    s = re.sub(r'<(p|h2|h3|ul|ol|li|table|tr|td|th|blockquote|strong|dl|dt|dd)\b[^>]*>', r'<\1>', s, flags=re.I)
    s = re.sub(r'<a\b[^>]*href="([^"]*)"[^>]*>', lambda m: '<a href="%s">' % m.group(1), s, flags=re.I)
    # 7. ссылки: /main -> /, внешние -> текст
    s = s.replace('href="/main"', 'href="/"')
    s = re.sub(r'<a href="(?!/)[^"]*">(.*?)</a>', r'\1', s, flags=re.S)
    # 8. бренд
    for w in brand_words:
        s = re.sub(r'\b%s\b' % re.escape(w), '%brand_name_en%', s)
    s = re.sub(r'(%brand_name_en%)\s+Casino\b', r'\1', s)
    s = re.sub(r'(%brand_name_en%)(\s+%brand_name_en%)+', r'\1', s)
    s = re.sub(r'(%brand_name_ru%)(\s+%brand_name_ru%)+', r'\1', s)
    # 9. эмодзи: в <p>, <h2>, <h3>, <td>, <th> — вон; в <li> оставить только ведущий
    def clean_p(m):
        return '<%s>%s</%s>' % (m.group(1), EMOJI.sub('', m.group(2)), m.group(1))
    s = re.sub(r'<(p|h2|h3|td|th|blockquote|summary)>(.*?)</\1>', clean_p, s, flags=re.S)
    def clean_li(m):
        body = m.group(1)
        lead = ''
        mm = re.match(r'\s*(%s(?:️)?)\s*' % EMOJI.pattern, body)
        if mm:
            lead = mm.group(1) + ' '
            body = body[mm.end():]
        return '<li>' + lead + EMOJI.sub('', body) + '</li>'
    s = re.sub(r'<li>(.*?)</li>', clean_li, s, flags=re.S)
    # 10. типографика и мусор
    s = clean_text(s)
    s = re.sub(r'<p>\s*</p>', '', s)
    s = re.sub(r'<(ul|ol)>\s*</\1>', '', s)
    s = re.sub(r'<blockquote>\s*<p>(.*?)</p>\s*</blockquote>', r'<blockquote>\1</blockquote>', s, flags=re.S)
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = re.sub(r'>\s+<', '>\n<', s)
    # 10a. осиротевшие <li> (у исходного генератора встречаются) — обернуть
    def wrap(m):
        return '<ul>\n' + m.group(0).strip() + '\n</ul>'
    parts = re.split(r'(<(?:ul|ol)\b.*?</(?:ul|ol)>)', s, flags=re.S)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r'(?:\s*<li>.*?</li>)+', wrap, parts[i], flags=re.S)
    s = ''.join(parts)
    # 11. вернуть FAQ единым блоком в конец
    s = s.replace('\x00FAQ\x00', '')
    # титульная заглушка вида «Казино %brand_name_ru%.» в первой строке — вон
    s = re.sub(r'\A\s*<p>[^<]{0,60}%brand_name_ru%\.?</p>\s*', '', s)
    # схлопнуть пустые/битые blockquote
    s = re.sub(r'<blockquote>\s*</blockquote>', '', s)
    s = s.strip()
    return s, faqs

if __name__ == '__main__':
    src = sys.argv[1]
    raw = io.open(src, encoding='utf-8').read()
    brands = sys.argv[2].split(',') if len(sys.argv) > 2 and sys.argv[2] else []
    out, faqs = normalize(raw, brands)
    sys.stdout.write(out + '\n\x01\n' + '\n'.join('%s\t%s' % f for f in faqs))
