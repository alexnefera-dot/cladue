#!/usr/bin/env python3
"""Шаг 1 расчёта срока жизни: компактная карта сабдоменов.

Полная выгрузка `/v1/subdomains` — 1.5 ГБ, для срока жизни из неё нужно шесть
полей. Карта пишется один раз и переиспользуется всеми расчётами окна.

    python3 lifespan_map.py <карта.jsonl> <subdomains.jsonl> [ещё...]
"""
import sys, json

KEEP = ('content_domain_url', 'content_domain_id', 'brand_label', 'recrawl_sent_at',
        'pipeline_started', 'pages_count', 'tld', 'yandex_pipeline_stage')

out_path, srcs = sys.argv[1], sys.argv[2:]
rows = {}
for p in srcs:
    with open(p, encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            rows[r['subdomain'].lower()] = [r.get(k) for k in KEEP]

with open(out_path, 'w', encoding='utf-8') as f:
    for sub, vals in rows.items():
        f.write(json.dumps([sub] + vals, ensure_ascii=False) + '\n')
print(f'карта: {len(rows)} сабдоменов -> {out_path}')
