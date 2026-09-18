#!/usr/bin/env python3
"""Шаг 2: первый и последний клик по каждому сабдомену + суточный ряд по базам.

Один проход по всем выгрузкам кликов (около 3 ГБ). На выходе два файла:
  subs.jsonl  — [сабдомен, всего, из_яндекса, первый, последний, первый_ya, последний_ya]
  days.json   — {база: {дата: [всего, из_яндекса]}}

Смещения часового пояса во всех строках одинаковы (+03:00), поэтому сравнение
меток идёт лексикографически, без разбора дат.

    python3 lifespan_clicks.py <карта.jsonl> <subs.jsonl> <days.json> <clicks.jsonl> [ещё...]
"""
import sys, json, collections

map_path, subs_out, days_out = sys.argv[1], sys.argv[2], sys.argv[3]
clicks = sys.argv[4:]

base = {}
with open(map_path, encoding='utf-8') as f:
    for line in f:
        r = json.loads(line)
        base[r[0]] = r[1]                      # сабдомен -> домен базы

agg = {}                                       # сабдомен -> [n, ya, first, last, ya_first, ya_last]
days = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
seen = foreign = 0

for p in clicks:
    with open(p, encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            s = (r.get('subdomain') or '').lower()
            seen += 1
            b = base.get(s)
            if b is None:
                foreign += 1
                continue
            at = r.get('at')
            if not at:
                continue
            h = r.get('referer') or ''
            ya = 1 if ('yandex' in h or '//ya.ru' in h) else 0
            a = agg.get(s)
            if a is None:
                agg[s] = a = [0, 0, at, at, None, None]
            a[0] += 1
            a[1] += ya
            if at < a[2]:
                a[2] = at
            if at > a[3]:
                a[3] = at
            if ya:
                if a[4] is None or at < a[4]:
                    a[4] = at
                if a[5] is None or at > a[5]:
                    a[5] = at
            d = days[b][at[:10]]
            d[0] += 1
            d[1] += ya
    print(f'  {p}: всего {seen}, чужих {foreign}, наших сабдоменов с кликом {len(agg)}', flush=True)

with open(subs_out, 'w', encoding='utf-8') as f:
    for s, a in agg.items():
        f.write(json.dumps([s] + a, ensure_ascii=False) + '\n')
with open(days_out, 'w', encoding='utf-8') as f:
    json.dump({b: dict(v) for b, v in days.items()}, f, ensure_ascii=False)

print(f'ГОТОВО: {seen} кликов, из них наших {seen - foreign}; '
      f'{len(agg)} сабдоменов с кликом, {len(days)} баз')
