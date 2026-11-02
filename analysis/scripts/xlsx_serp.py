#!/usr/bin/env python3
"""Чтение построчной выгрузки выдачи из xlsx парсера в формат snapshot json.

Лист `results`: query, position, url, title, domain, regdom, scrape_ts,
whois_created. Выгрузка — данные со стороны, читается только как данные.

    python3 xlsx_serp.py <out.json> <serp1.xlsx> [serp2.xlsx ...]
"""
import html
import json
import os
import re
import sys
import zipfile


def list_rows(z, name):
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        sx = z.read('xl/sharedStrings.xml').decode()
        shared = [html.unescape(re.sub(r'<[^>]+>', '', m))
                  for m in re.findall(r'<si>(.*?)</si>', sx, re.S)]
    x = z.read(name).decode()
    out = []
    for r in re.findall(r'<row[^>]*>(.*?)</row>', x, re.S):
        row = {}
        for m in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*)>(.*?)</c>', r, re.S):
            col, attrs, body = m.group(1), m.group(2), m.group(3)
            v = re.search(r'<v>(.*?)</v>', body, re.S)
            t = re.search(r'<t[^>]*>(.*?)</t>', body, re.S)
            val = html.unescape(t.group(1)) if t else (v.group(1) if v else '')
            if 't="s"' in attrs and v and shared:
                val = shared[int(v.group(1))]
            row[col] = val
        out.append(row)
    return out


def prochitat(put):
    z = zipfile.ZipFile(put)
    rs = list_rows(z, 'xl/worksheets/sheet1.xml')
    if not rs:
        return None, {}
    shapka = rs[0]
    zapisi = [{shapka[k]: r.get(k, '') for k in shapka} for r in rs[1:]]
    sgr = {}
    sbor = ''
    for r in zapisi:
        q = (r.get('query') or '').strip()
        if not q:
            continue
        sbor = sbor or (r.get('scrape_ts') or '')
        try:
            poz = int(r.get('position') or 0)
        except ValueError:
            poz = 0
        sgr.setdefault(q, []).append({
            'query': q, 'pos': poz, 'url': r.get('url') or '',
            'host': (r.get('domain') or '').lower(),
            'base': (r.get('regdom') or r.get('domain') or '').lower(),
            'title': r.get('title') or '',
            'whois': r.get('whois_created') or '',
        })
    return sbor, sgr


out_p, puti = sys.argv[1], sys.argv[2:]
snimki = []
for put in puti:
    sbor, sgr = prochitat(put)
    if not sgr:
        print(f'{os.path.basename(put)}: пусто, пропускаю')
        continue
    snimki.append({'scrape': sbor, 'queries': sgr, 'istochnik': os.path.basename(put)})
    print(f'{os.path.basename(put)}: {sbor[:19]}, запросов {len(sgr)}, '
          f'строк {sum(len(v) for v in sgr.values())}')
json.dump(snimki, open(out_p, 'w', encoding='utf-8'), ensure_ascii=False)
print(f'записано: {out_p} ({len(snimki)} снимков)')
