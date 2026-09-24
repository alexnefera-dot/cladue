#!/usr/bin/env python3
"""Наши сайты в снимке выдачи (xlsx из парсера SERP).

Наш = базовый домен (последние две метки хоста) есть в реестре запусков dorgen.
Хосты Яндекса и прочие чужие базы в выдаче не считаются нашими.

    python3 serp_nashi.py <serp.xlsx> <out.json> <реестр1.jsonl> [реестр2.jsonl ...]
      --bases-extra <файл со списком баз>  --tracker-bases <файл>
"""
import sys, re, json, html, zipfile, collections
from urllib.parse import urlparse

args = sys.argv[1:]
xlsx, out_p = args[0], args[1]
regs, extra, trk = [], [], []
i = 2
while i < len(args):
    if args[i] == '--bases-extra':
        extra.append(args[i + 1]); i += 2
    elif args[i] == '--tracker-bases':
        trk.append(args[i + 1]); i += 2
    else:
        regs.append(args[i]); i += 1


def sheet_rows(z, name):
    x = z.read(name).decode()
    out = []
    for r in re.findall(r'<row[^>]*>(.*?)</row>', x, re.S):
        row = {}
        for col, body in re.findall(r'<c r="([A-Z]+)\d+"[^>]*>(.*?)</c>', r, re.S):
            m = re.search(r'<t[^>]*>(.*?)</t>', body, re.S) or re.search(r'<v>(.*?)</v>', body, re.S)
            row[col] = html.unescape(m.group(1)) if m else ''
        out.append(row)
    head = out[0]
    return [{head[k]: v for k, v in r.items() if k in head} for r in out[1:]]


z = zipfile.ZipFile(xlsx)
res = sheet_rows(z, 'xl/worksheets/sheet1.xml')

base = {}   # база -> сведения о запуске
for p in regs:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        b = r.get('content_domain_url')
        if not b:
            continue
        when = (r.get('recrawl_sent_at') or r.get('pipeline_started') or r.get('created_at') or '')[:10]
        cur = base.get(b)
        if cur is None or (when and (not cur['launch'] or when < cur['launch'])):
            base[b] = dict(launch=when, content=r.get('content_label') or r.get('content') or '')
for p in extra:
    for b in open(p, encoding='utf-8').read().split():
        base.setdefault(b, dict(launch='', content=''))
tb = set()
for p in trk:
    tb |= set(open(p, encoding='utf-8').read().split())

found = []
Q = collections.OrderedDict()
for r in res:
    url = r.get('url', '')
    host = (urlparse(url).hostname or '').lower()
    b = '.'.join(host.split('.')[-2:])
    who = 'наш' if b in base else ''
    item = dict(query=r['query'], pos=int(float(r['position'])), url=url, host=host, base=b,
                title=r.get('title', ''), who=who, whois=r.get('whois_created', ''))
    if who:
        item.update(base.get(b, {}))
    Q.setdefault(r['query'], []).append(item)
    if who:
        found.append(item)
json.dump(dict(scrape=res[0].get('scrape_ts', '') if res else '', queries=Q, bases=len(base)),
          open(out_p, 'w', encoding='utf-8'), ensure_ascii=False)
print(f'запросов {len(Q)}, строк {len(res)}, баз в реестре {len(base)}, наших позиций {sum(f["who"]=="наш" for f in found)}, '
      f'сайтов {len({f["host"] for f in found})}')
