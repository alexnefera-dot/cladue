#!/usr/bin/env python3
"""Наши домены, которые видно по кликам, но переобхода у них не было ни одного.

Домен берётся из реестра; «без переобхода» — recrawl_sent_at пуст у всех 206
его сайтов. Клики считаются в окне, каждый день ровно одним файлом выгрузки:
выгрузки трекера перекрываются по датам.

Использование:
    python3 -I scripts/domeny_bez_pereobhoda.py [ОТ] [ДО]
"""
import collections
import glob
import os
import sys

OT = sys.argv[1] if len(sys.argv) > 1 else '2026-10-11'
DO = sys.argv[2] if len(sys.argv) > 2 else '2026-11-16'
ZONY = {'lol', 'team', 'buzz', 'casino'}
VLAD = [('tracker_clicks_2026-10-11_2026-10-21.jsonl', '2026-10-11', '2026-10-21'),
        ('tracker_clicks_2026-10-22_2026-10-23.jsonl', '2026-10-22', '2026-10-23'),
        ('tracker_clicks_2026-10-24_2026-10-24.jsonl', '2026-10-24', '2026-10-24'),
        ('tracker_clicks_2026-10-25_2026-10-30.jsonl', '2026-10-25', '2026-10-30'),
        ('tracker_clicks_2026-10-31_2026-11-09.jsonl', '2026-10-31', '2026-11-07'),
        ('tracker_clicks_2026-11-08_2026-11-09.jsonl', '2026-11-08', '2026-11-09'),
        ('tracker_clicks_2026-11-10_2026-11-10.jsonl', '2026-11-10', '2026-11-10'),
        ('tracker_clicks_2026-11-11_2026-11-12.jsonl', '2026-11-11', '2026-11-11'),
        ('tracker_clicks_2026-11-12_2026-11-16.jsonl', '2026-11-12', '2026-11-16')]


def pole(ln, imya):
    k = ln.find('"' + imya + '":')
    if k < 0:
        return ''
    j = k + len(imya) + 3
    while j < len(ln) and ln[j] == ' ':
        j += 1
    if ln[j:j + 1] == '"':
        return ln[j + 1:ln.find('"', j + 1)]
    return ln[j:min(x for x in (ln.find(',', j), ln.find('}', j), len(ln)) if x > 0)].strip()


dom = collections.defaultdict(lambda: dict(saitov=0, rec=0, sozdan='',
                                           st=collections.Counter()))
vid = set()
for put in sorted(glob.glob('api/dorgen_subdomains_*.jsonl')):
    if not os.path.getsize(put):
        continue
    for ln in open(put):
        s = pole(ln, 'subdomain')
        b = pole(ln, 'content_domain_url')
        if not s or not b:
            continue
        g = dom[b]
        r = pole(ln, 'recrawl_sent_at')[:1].isdigit()
        if s in vid:
            if r:
                g['rec'] += 1            # переобход мог появиться в поздней выгрузке
                vid.add((s, 'r'))
            continue
        vid.add(s)
        g['saitov'] += 1
        if r:
            g['rec'] += 1
        d = pole(ln, 'domain_created')[:10]
        if d[:1].isdigit():
            g['sozdan'] = min(g['sozdan'] or '9999', d)
        g['st'][pole(ln, 'yandex_pipeline_stage')] += 1

bez = {b for b, g in dom.items() if g['rec'] == 0}
print(f'Доменов в реестре: {len(dom)}; без единого переобхода: {len(bez)}')

kl = collections.defaultdict(collections.Counter)
sajty = collections.defaultdict(set)
for f, o, d in VLAD:
    put = 'api/' + f
    if not os.path.exists(put) or d < OT or o > DO:
        continue
    for ln in open(put):
        k = ln.find('"subdomain": "')
        if k < 0:
            continue
        dt = ln[8:18]
        if not (max(o, OT) <= dt <= min(d, DO)):
            continue
        s = ln[k + 14:ln.find('"', k + 14)]
        p = s.split('.')
        if len(p) < 3 or p[-1] not in ZONY:
            continue
        b = '.'.join(p[-2:])
        if b not in bez:
            continue
        kl[b]['vse'] += 1
        sajty[b].add(s)
        if '"is_bot": true' in ln:
            kl[b]['bot'] += 1
            continue
        rk = ln.find('"referer": "')
        if rk >= 0 and 'yandex.' in ln[rk + 12:ln.find('"', rk + 12)]:
            kl[b]['zhiv'] += 1

vidno = sorted(kl, key=lambda b: -kl[b]['vse'])
print(f'Из них видно по кликам за {OT}..{DO}: {len(vidno)}')
print(f'Суммарно: кликов {sum(kl[b]["vse"] for b in vidno)}, '
      f'живых поисковых {sum(kl[b]["zhiv"] for b in vidno)}')
print()
print(f'{"домен":<12} {"создан":<12} {"сайтов":>6} {"с кликами":>10} {"кликов":>8} '
      f'{"боты":>7} {"живых":>6}  стадии')
for b in vidno:
    g = dom[b]
    st = ', '.join(f'{k} {v}' for k, v in g['st'].most_common(3))
    print(f'{b:<12} {g["sozdan"] or "—":<12} {g["saitov"]:>6} {len(sajty[b]):>10} '
          f'{kl[b]["vse"]:>8} {kl[b]["bot"]:>7} {kl[b]["zhiv"]:>6}  {st}')
print()
print('# Список в столбик')
for b in vidno:
    print(b)
tihie = sorted(bez - set(vidno))
print()
print(f'# Без переобхода и ни одного клика: {len(tihie)}')
for b in tihie:
    print(b)
