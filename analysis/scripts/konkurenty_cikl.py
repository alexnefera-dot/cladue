#!/usr/bin/env python3
"""Жизненный цикл чужих сайтов в выдаче: кто держится, кто сменяется.

На вход — снимки SERP (xlsx парсера) с метками времени. Считается только по
запросам, которые есть во всех сравниваемых снимках, иначе «пропал» будет путаться
с «не спрашивали».

Домены делятся на четыре вида:
  наши        — базовый домен есть в реестре запусков dorgen
  дорвей      — чужой сайт той же техники: либо хост вида бренд.база.зона в наших
                зонах, либо путь с повторами /ru/ru/ru, либо дешёвая зона из списка
  площадка    — телеграм, ютуб, вк, сам Яндекс и прочие чужие площадки
  сайт        — всё остальное: обычные домены, похожие на собственные сайты брендов

    python3 konkurenty_cikl.py <out.txt> --snaps <метка>=<файл.xlsx> ... --subs <реестр.jsonl ...>
"""
import sys, re, json, html, zipfile, collections
from urllib.parse import urlparse

out_p = sys.argv[1]
opt = collections.defaultdict(list); cur = None
for a in sys.argv[2:]:
    if a.startswith('--'):
        cur = a[2:]
    else:
        opt[cur].append(a)
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


def sheet(p):
    z = zipfile.ZipFile(p); x = z.read('xl/worksheets/sheet1.xml').decode(); rows = []
    for r in re.findall(r'<row[^>]*>(.*?)</row>', x, re.S):
        row = {}
        for col, body in re.findall(r'<c r="([A-Z]+)\d+"[^>]*>(.*?)</c>', r, re.S):
            m = re.search(r'<t[^>]*>(.*?)</t>', body, re.S) or re.search(r'<v>(.*?)</v>', body, re.S)
            row[col] = html.unescape(m.group(1)) if m else ''
        rows.append(row)
    if not rows:
        return []
    head = rows[0]
    return [{head[k]: v for k, v in r.items() if k in head} for r in rows[1:]]


ours = set()
for p in opt['subs']:
    for line in open(p, encoding='utf-8'):
        ours.add(json.loads(line)['content_domain_url'].lower())

DOR_TLD = {'team', 'lol', 'casino', 'buzz', 'top', 'sbs', 'icu', 'cfd', 'bond', 'rest', 'makeup', 'skin'}
SITES = ('telegram', 't.me', 'youtube', 'vk.com', 'yandex', 'ya.ru', 'dzen', 'ok.ru',
         'facebook', 'instagram', 'twitter', 'x.com', 'wikipedia', 'otzovik', 'irecommend')


def kind(host, url):
    h = host.lower()
    base = '.'.join(h.split('.')[-2:])
    if base in ours:
        return 'наши'
    if any(s in h for s in SITES):
        return 'площадка'
    tld = h.rsplit('.', 1)[-1]
    path = urlparse(url).path or ''
    if h.count('.') >= 2 and tld in DOR_TLD:
        return 'дорвей'
    if re.search(r'(/(ru|RU-ru|ru_RU)){4,}', path):
        return 'дорвей'
    if tld in DOR_TLD - {'casino'}:
        return 'дорвей'
    return 'сайт'


snaps = []
for s in opt['snaps']:
    tag, p = s.split('=', 1)
    snaps.append((tag, sheet(p)))
qsets = [{r['query'] for r in rs} for _, rs in snaps]
common = set.intersection(*qsets) if qsets else set()
P(f'Снимков {len(snaps)}, общих запросов {len(common)}.')
P('Снимки: ' + ', '.join(t for t, _ in snaps))

# домен -> снимок -> лучшая позиция
seen = collections.defaultdict(dict)
KIND = {}
for i, (tag, rs) in enumerate(snaps):
    for r in rs:
        if r['query'] not in common:
            continue
        hostv = (r.get('domain') or urlparse(r.get('url') or '').hostname or '').lower()
        if not hostv:
            continue
        pos = int(r.get('position') or 99)
        d = seen[hostv]
        d[i] = min(d.get(i, 99), pos)
        KIND[hostv] = kind(hostv, r.get('url') or '')
n = len(snaps)
P(f'\nРазных хостов в выдаче по общим запросам: {len(seen)}')
P(f'\n{"вид":<12} {"хостов":>7} {"доля":>6} {"в первом снимке":>16} {"в последнем":>12} {"дожили":>8} {"новых":>7}')
for k in ('наши', 'дорвей', 'сайт', 'площадка'):
    hs = [h for h in seen if KIND[h] == k]
    if not hs:
        continue
    first = [h for h in hs if 0 in seen[h]]
    last = [h for h in hs if n - 1 in seen[h]]
    surv = [h for h in first if n - 1 in seen[h]]
    new = [h for h in last if 0 not in seen[h]]
    P(f'{k:<12} {len(hs):>7} {100*len(hs)/len(seen):>5.1f}% {len(first):>16} {len(last):>12} '
      f'{(100*len(surv)/len(first) if first else 0):>7.0f}% {(100*len(new)/len(last) if last else 0):>6.0f}%')
# сколько снимков держится хост
P(f'\nВ скольких снимках из {n} встречается хост:')
P(f'{"вид":<12} ' + ' '.join(f'{i:>5}' for i in range(1, n + 1)) + f' {"медиана":>8}')
import statistics
for k in ('наши', 'дорвей', 'сайт', 'площадка'):
    hs = [h for h in seen if KIND[h] == k]
    if not hs:
        continue
    c = collections.Counter(len(seen[h]) for h in hs)
    med = statistics.median([len(seen[h]) for h in hs])
    P(f'{k:<12} ' + ' '.join(f'{c.get(i,0):>5}' for i in range(1, n + 1)) + f' {med:>8.0f}')
# форма домена: голый против поддомена
P(f'\nФорма домена у чужих дорвеев (первый снимок против последнего):')
P(f'{"форма":<30} {"в первом":>9} {"дожили":>8} {"выживаемость":>13} {"средняя позиция в конце":>24}')
first_s = {h for h in seen if 0 in seen[h]}
last_s = {h for h in seen if n - 1 in seen[h]}
for nm, test in (('голый домен (бренд в имени)', lambda h: h.count('.') == 1),
                 ('поддомен бренд.база.зона', lambda h: h.count('.') >= 2)):
    a = [h for h in first_s if KIND[h] == 'дорвей' and test(h)]
    su = [h for h in a if h in last_s]
    b = [h for h in last_s if KIND[h] == 'дорвей' and test(h)]
    pos = [seen[h][n - 1] for h in b]
    P(f'{nm:<30} {len(a):>9} {len(su):>8} {(100*len(su)/len(a) if a else 0):>12.0f}% '
      f'{(sum(pos)/len(pos) if pos else 0):>24.1f}')
for nm, k in (('наши (все поддоменные)', 'наши'), ('брендовые сайты', 'сайт')):
    a = [h for h in first_s if KIND[h] == k]
    su = [h for h in a if h in last_s]
    P(f'{nm:<30} {len(a):>9} {len(su):>8} {(100*len(su)/len(a) if a else 0):>12.0f}%')
P('\nЧужие дорвеи, дожившие до конца окна:')
for h in sorted(h for h in first_s & last_s if KIND[h] == 'дорвей'):
    P(f'   {h:<34} позиция {seen[h][0]} -> {seen[h][n-1]}   '
      f'{"голый" if h.count(".") == 1 else "поддомен"}')

# ВАЖНО: плотность (доров на базу) по выдаче не измеряется. Контроль: у наших баз
# в выдаче тоже медиана 1 хост на базу, хотя на каждой стоит 206 сайтов. Запросов
# мало и они про десяток брендов, поэтому в топ-10 попадает один-два хоста с базы.

# состав топ-10 по снимкам
P(f'\nИз чего состоит выдача (доля строк в топ-10 по общим запросам):')
P(f'{"снимок":<14} {"строк":>7} ' + ' '.join(f'{k:>10}' for k in ('наши', 'дорвей', 'сайт', 'площадка')))
for i, (tag, rs) in enumerate(snaps):
    rr = [r for r in rs if r['query'] in common]
    c = collections.Counter()
    for r in rr:
        hostv = (r.get('domain') or urlparse(r.get('url') or '').hostname or '').lower()
        if hostv:
            c[KIND.get(hostv, 'сайт')] += 1
    t = sum(c.values()) or 1
    P(f'{tag:<14} {t:>7} ' + ' '.join(f'{c[k]:>5}{100*c[k]/t:>4.0f}%' for k in ('наши', 'дорвей', 'сайт', 'площадка')))
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
