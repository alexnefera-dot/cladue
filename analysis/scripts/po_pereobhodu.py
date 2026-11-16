#!/usr/bin/env python3
"""Клики и конверсии в разрезе «был переобход / не было».

Переобход — отправка сайта в Яндекс (recrawl_sent_at). Без него сайт в индекс
не входит, живых поисковых кликов у него быть не может, а бот-клики и редиректы
на него идут всё равно — поэтому «клики» без этого разреза обманывают.

Группы:
  переобход был      — recrawl_sent_at заполнен
  переобхода не было — сайт в реестре, recrawl_sent_at пуст
  нет в реестре      — запуск старше 01.08.2026, API таких не отдаёт

Выгрузки трекера перекрываются по датам, поэтому каждый день считается ровно
одним файлом — тем, который его покрывает целиком и выгружен последним.
Окно одно и то же для кликов и конверсий, цифры сопоставимы.

Использование:
    python3 -I scripts/po_pereobhodu.py [ОТ YYYY-MM-DD] [ДО YYYY-MM-DD]
"""
import collections
import glob
import json
import os
import sys

OT = sys.argv[1] if len(sys.argv) > 1 else '2026-10-11'
DO = sys.argv[2] if len(sys.argv) > 2 else '2026-11-16'
ZONY = {'lol', 'team', 'buzz', 'casino'}

# какой файл кликов «владеет» какими датами: перекрытия считать нельзя
VLADEET = [
    ('tracker_clicks_2026-10-11_2026-10-21.jsonl', '2026-10-11', '2026-10-21'),
    ('tracker_clicks_2026-10-22_2026-10-23.jsonl', '2026-10-22', '2026-10-23'),
    ('tracker_clicks_2026-10-24_2026-10-24.jsonl', '2026-10-24', '2026-10-24'),
    ('tracker_clicks_2026-10-25_2026-10-30.jsonl', '2026-10-25', '2026-10-30'),
    ('tracker_clicks_2026-10-31_2026-11-09.jsonl', '2026-10-31', '2026-11-07'),
    ('tracker_clicks_2026-11-08_2026-11-09.jsonl', '2026-11-08', '2026-11-09'),
    ('tracker_clicks_2026-11-10_2026-11-10.jsonl', '2026-11-10', '2026-11-10'),
    ('tracker_clicks_2026-11-11_2026-11-12.jsonl', '2026-11-11', '2026-11-11'),
    ('tracker_clicks_2026-11-12_2026-11-16.jsonl', '2026-11-12', '2026-11-16'),
]


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


# 1. реестр: сайт -> был ли переобход
rec = {}
for put in sorted(glob.glob('api/dorgen_subdomains_*.jsonl')):
    if not os.path.getsize(put):
        continue
    for ln in open(put):
        s = pole(ln, 'subdomain')
        if not s:
            continue
        b = pole(ln, 'recrawl_sent_at')[:1].isdigit()
        rec[s] = rec.get(s, False) or b        # переобход хоть раз — значит был

vsego_s = collections.Counter()
for s, b in rec.items():
    vsego_s['переобход был' if b else 'переобхода не было'] += 1
print(f'Реестр: {len(rec)} сайтов — {dict(vsego_s)}')
print(f'Окно: {OT}..{DO}')
print()


def gruppa(s):
    if s in rec:
        return 'переобход был' if rec[s] else 'переобхода не было'
    return 'нет в реестре'


# 2. клики
kl = collections.defaultdict(collections.Counter)
zhivye_sajty = collections.defaultdict(set)
sajty_s_klikom = collections.defaultdict(set)
for f, o, d in VLADEET:
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
        g = gruppa(s)
        kl[g]['vse'] += 1
        sajty_s_klikom[g].add(s)
        if '"is_bot": true' in ln:
            kl[g]['bot'] += 1
            continue
        rk = ln.find('"referer": "')
        if rk < 0 or 'yandex.' not in ln[rk + 12:ln.find('"', rk + 12)]:
            continue
        kl[g]['zhiv'] += 1
        zhivye_sajty[g].add(s)

# 3. конверсии
kv = collections.defaultdict(collections.Counter)
konv_sajty = collections.defaultdict(set)
vid = set()
for put in glob.glob('api/tracker_conversions_*.jsonl'):
    for ln in open(put):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        dt = str(r.get('at'))[:10]
        if not (OT <= dt <= DO):
            continue
        k = (r.get('clickid'), r.get('event'), r.get('at'))
        if k in vid:
            continue
        vid.add(k)
        s = (r.get('subdomain') or '').lower()
        p = s.split('.')
        if not s or len(p) < 3 or p[-1] not in ZONY:
            kv['ключ не наш/пуст'][r.get('event')] += 1
            continue
        g = gruppa(s)
        kv[g][r.get('event')] += 1
        konv_sajty[g].add(s)

GR = ['переобход был', 'переобхода не было', 'нет в реестре']
print(f'{"группа":<22} {"сайтов":>9} {"кликов":>10} {"боты":>9} {"живых":>8} '
      f'{"сайтов с живым":>15} {"рег":>5} {"фд":>4}')
for g in GR:
    n = vsego_s.get(g, 0) if g != 'нет в реестре' else len(sajty_s_klikom[g])
    print(f'{g:<22} {n:>9} {kl[g]["vse"]:>10} {kl[g]["bot"]:>9} {kl[g]["zhiv"]:>8} '
          f'{len(zhivye_sajty[g]):>15} {kv[g]["reg"]:>5} {kv[g]["fd"]:>4}')
print()
print('Доля живых поисковых кликов от всех кликов группы:')
for g in GR:
    v = kl[g]['vse']
    print(f'  {g:<22} {kl[g]["zhiv"]}/{v} = {100.0 * kl[g]["zhiv"] / v if v else 0:.3f}%')
print()
print('Рег на 1000 живых поисковых кликов:')
for g in GR:
    z = kl[g]['zhiv']
    print(f'  {g:<22} {1000.0 * kv[g]["reg"] / z if z else 0:.2f}' + ('' if z else '  (живых кликов нет)'))
print()
pr = kv['ключ не наш/пуст']
print(f'Конверсии с чужим/пустым ключом (к сайту не привязать): рег {pr["reg"]}, фд {pr["fd"]}')
print()
print('Сайты с конверсиями в группе «переобхода не было»:',
      ', '.join(sorted(konv_sajty['переобхода не было'])) or 'нет')
