# -*- coding: utf-8 -*-
"""Откуда берётся пересечение страницы bonus: разбор совпавших шинглов по
зонам страницы. Зоны — зачин до первого h2, каждый раздел по своему h2,
блок FAQ. Считаем по той же чистке и тем же шестисловным шинглам, что
приёмка (engine/instrumenty/shingle.php), иначе проценты несравнимы.
"""
import glob, html, os, re, sys, collections

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

def зоны(html_текст):
    """Возвращает список (имя зоны, текст). Разрез по h2."""
    части = re.split(r'(<h2\b)', html_текст)
    собрано, буфер = [], части[0]
    i = 1
    куски = [буфер]
    while i < len(части):
        куски.append(части[i] + части[i + 1]); i += 2
    out = []
    for n, к in enumerate(куски):
        m = re.search(r'<h2[^>]*>(.*?)</h2>', к, re.S)
        if m:
            имя = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            имя = re.sub(r'^%brand_name_ru% Казино:\s*', '', имя)
        else:
            имя = 'зачин до первого h2'
        out.append((имя, к))
    return out

папки = sorted(glob.glob('samples/v5-final/nabor-*'),
               key=lambda p: int(p.rsplit('-', 1)[1]))[-40:]
страницы = {}
for п in папки:
    f = os.path.join(п, 'bonus.html')
    if os.path.isfile(f):
        страницы[os.path.basename(п)] = open(f, encoding='utf-8').read()

ш = {k: шинглы(чисто(v)) for k, v in страницы.items()}
пары = []
for a in ш:
    for b in ш:
        if a >= b: continue
        общ = len(ш[a] & ш[b])
        p = общ / min(len(ш[a]), len(ш[b])) * 100
        пары.append((p, a, b, общ))
пары.sort(reverse=True)
print('страниц bonus:', len(ш))
print('\nсамые похожие пары (доля от меньшей, как считает приёмка):')
for p, a, b, общ in пары[:6]:
    print('  %5.1f %%  %s ↔ %s  (%d общих шинглов)' % (p, a, b, общ))

print('\nразбор верхней пары по зонам страницы %s:' % пары[0][1])
a, b = пары[0][1], пары[0][2]
общие = ш[a] & ш[b]
свои_новые = {'Фриспины', 'Турниры и лидерборды', 'Бездепозитный бонус'}
итог = []
for имя, кусок in зоны(страницы[a]):
    зш = шинглы(чисто(кусок))
    если = len(зш & общие)
    итог.append((имя, len(зш), если))
всего_зон = sum(x[2] for x in итог)
print('%-58s %7s %7s %7s' % ('зона', 'шинглов', 'общих', 'доля'))
for имя, всего, если in итог:
    print('%-58s %7d %7d %6.1f %%' % (имя[:56], всего, если, если / max(1, len(общие)) * 100))
print('%-58s %7s %7d %6.1f %%' % ('— сумма по зонам', '', всего_зон, всего_зон / max(1, len(общие)) * 100))
print('общих шинглов всего: %d (пересечение %.1f %%)' % (len(общие), пары[0][0]))

# Сколько пар делят каждый конкретный раздел — и как это связано с процентом.
print('\nобщие H2 против процента пересечения (верхние двадцать пар):')
h2 = {k: {re.sub(r'^%brand_name_ru% Казино:\s*', '', re.sub(r'<[^>]+>', '', m).strip())
          for m in re.findall(r'<h2[^>]*>(.*?)</h2>', v, re.S)} for k, v in страницы.items()}
for p, a, b, общ in пары[:20]:
    делят = len(h2[a] & h2[b])
    print('  %5.1f %%  общих H2 %d  %s ↔ %s' % (p, делят, a, b))
import statistics
хи = [(len(h2[a] & h2[b]), p) for p, a, b, _ in пары]
for k in sorted({x for x, _ in хи}):
    зн = [p for x, p in хи if x == k]
    print('общих H2 = %d: пар %4d, пересечение медиана %.1f %%, максимум %.1f %%'
          % (k, len(зн), statistics.median(зн), max(зн)))
