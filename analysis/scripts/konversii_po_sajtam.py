#!/usr/bin/env python3
"""Конверсии по заданным сайтам: сколько и в какие даты.

Часть строк трекера приходит без поля subdomain — такие привязываются
к сайту через clickid из выгрузок кликов. Дубли снимаются по
(clickid, event, at).

    python3 -I scripts/konversii_po_sajtam.py <сайт> [сайт ...]
"""
import collections
import glob
import json
import os
import sys

# аргумент-файл: строки «дата<TAB>сайт» — дата постановки на отслеживание
CELI, kogda = set(), {}
for a in sys.argv[1:]:
    if os.path.exists(a):
        for ln in open(a, encoding='utf-8'):
            ln = ln.strip()
            if not ln:
                continue
            ch = ln.split('\t') if '\t' in ln else ln.split(None, 1)
            if len(ch) == 2 and ch[0][:1].isdigit():
                d, site = ch[0], ch[1].strip().lower()
            else:
                d, site = '', ln.lower()
            CELI.add(site)
            if d and (site not in kogda or d < kogda[site]):
                kogda[site] = d
    else:
        CELI.add(a.strip().lower().rstrip('/'))
ZONY = {'lol', 'team', 'buzz', 'casino'}

nashi = {s for s in CELI if s.count('.') >= 2 and s.rsplit('.', 1)[-1] in ZONY}
chuzhie = CELI - nashi

# clickid -> сайт, по кликам
ck = {}
for put in sorted(glob.glob('api/tracker_clicks_*.jsonl')):
    if put.endswith('.state'):
        continue
    for ln in open(put):
        k = ln.find('"subdomain": "')
        if k < 0:
            continue
        s = ln[k + 14:ln.find('"', k + 14)]
        if s.lower() in nashi:
            i = ln.find('"clickid": "')
            if i >= 0:
                ck[ln[i + 12:ln.find('"', i + 12)]] = s.lower()

sob = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
vid = set()
bez_privyazki = collections.Counter()
for put in sorted(glob.glob('api/tracker_conversions_*.jsonl')):
    for ln in open(put):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        k = (r.get('clickid'), r.get('event'), r.get('at'))
        if k in vid:
            continue
        s = (r.get('subdomain') or '').lower()
        if s not in nashi:
            s2 = ck.get(r.get('clickid'))
            if not s2:
                if not s:
                    bez_privyazki[str(r.get('at'))[:10]] += 1
                continue
            s = s2
        vid.add(k)
        sob[s][str(r.get('at'))[:10]][r.get('event')] += 1

print(f'Сайтов в запросе: {len(CELI)}; наших поддоменов {len(nashi)}, чужих доменов {len(chuzhie)}')
if chuzhie:
    print(f'  чужие (в нашем трекере их быть не может): {", ".join(sorted(chuzhie))}')
print()
vsego = collections.Counter()
for s in sorted(nashi):
    dni = sob.get(s)
    if not dni:
        k = kogda.get(s, '')
        print(f'{s:<26} конверсий нет' + (f'  (на отслеживании с {k[5:]})' if k else ''))
        continue
    reg = sum(c["reg"] for c in dni.values())
    fd = sum(c["fd"] for c in dni.values())
    vsego['reg'] += reg
    vsego['fd'] += fd
    k = kogda.get(s, '')
    do = sum(v for d2, c in dni.items() if k and d2 < k for v in c.values())
    print(f'{s:<26} рег {reg}, фд {fd}' + (f'  (на отслеживании с {k[5:]}'
          + (f', из них до постановки {do}' if do else '') + ')' if k else ''))
    for d in sorted(dni):
        c = dni[d]
        print(f'    {d}  ' + ', '.join(f'{k} {v}' for k, v in sorted(c.items())))
print()
print(f'ИТОГО по списку: рег {vsego["reg"]}, фд {vsego["fd"]}')
if bez_privyazki:
    print(f'Строк конверсий без поддомена и без совпадения по clickid: '
          f'{sum(bez_privyazki.values())} (к этим сайтам они не относятся, '
          f'но и ни к какому другому не привязались)')
