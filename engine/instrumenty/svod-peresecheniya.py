# -*- coding: utf-8 -*-
"""Сводка: откуда берётся пересечение наших наборов, по всем типам."""
import glob, html, itertools, os, re, statistics

def чисто(h):
    h = re.sub(r'<(script|style)\b.*?</\1>', ' ', h, flags=re.S | re.I)
    h = re.sub(r'%[a-z_]+%', ' бренд ', h)
    h = re.sub(r'<[^>]+>', ' ', h)
    h = html.unescape(h).lower()
    h = re.sub(r'[^а-яёa-z0-9 ]+', ' ', h)
    return re.sub(r'\s+', ' ', h).strip()

def шинглы(t, n=6):
    w = t.split()
    return {' '.join(w[i:i + n]) for i in range(len(w) - n + 1)}

def куски(h):
    ч = re.split(r'(<h2\b)', h)
    out, i = [ч[0]], 1
    while i < len(ч):
        out.append(ч[i] + ч[i + 1]); i += 2
    res = []
    for к in out:
        m = re.search(r'<h2[^>]*>(.*?)</h2>', к, re.S)
        имя = re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else '§зачин'
        res.append((имя, к))
    return res

ТИПЫ = ['main', 'obzor', 'promo', 'news', 'info', 'partnery',
        'app', 'bonus', 'registracia', 'slots', 'vhod', 'zerkalo']
папки = sorted(glob.glob('samples/v5-final/nabor-*'), key=lambda p: int(p.rsplit('-', 1)[1]))[-40:]
print('наборов в разборе: %d (%s … %s)' % (len(папки), os.path.basename(папки[0]), os.path.basename(папки[-1])))
print('\n%-12s %8s %8s %9s %9s %9s %8s' % ('тип', 'перес.', 'худшее', 'FAQ', 'разделы', 'зачин', 'вопр.'))
for т in ТИПЫ:
    стр = {os.path.basename(p): open(os.path.join(p, т + '.html'), encoding='utf-8').read()
           for p in папки if os.path.isfile(os.path.join(p, т + '.html'))}
    if len(стр) < 5: continue
    ш = {k: шинглы(чисто(v)) for k, v in стр.items()}
    пары = sorted(((len(ш[a] & ш[b]) / min(len(ш[a]), len(ш[b])) * 100, a, b)
                   for a, b in itertools.combinations(ш, 2)), reverse=True)
    доли = {'faq': [], 'разделы': [], 'зачин': []}
    общвопр = []
    for p, a, b in пары[:12]:
        общие = ш[a] & ш[b]
        счёт = {'faq': 0, 'разделы': 0, 'зачин': 0}
        for имя, к in куски(стр[a]):
            n = len(шинглы(чисто(к)) & общие)
            ключ = 'faq' if re.search(r'ответы на вопросы|частые вопросы|faq', имя, re.I) else (
                'зачин' if имя == '§зачин' else 'разделы')
            счёт[ключ] += n
        в = max(1, len(общие))
        for k in доли: доли[k].append(счёт[k] / в * 100)
        va = set(re.findall(r'<h3 class="faq-question"[^>]*>(.*?)</h3>', стр[a], re.S))
        vb = set(re.findall(r'<h3 class="faq-question"[^>]*>(.*?)</h3>', стр[b], re.S))
        общвопр.append(len(va & vb))
    print('%-12s %7.1f %% %7.1f %% %7.1f %% %7.1f %% %7.1f %% %8.1f'
          % (т, statistics.median(p for p, _, _ in пары), пары[0][0],
             statistics.median(доли['faq']), statistics.median(доли['разделы']),
             statistics.median(доли['зачин']), statistics.mean(общвопр)))
print('\nперес. — медиана по всем парам, худшее — верхняя пара;')
print('доли FAQ/разделы/зачин — медиана по двенадцати худшим парам;')
print('вопр. — сколько вопросов FAQ в среднем общие у худших пар.')
