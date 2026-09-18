#!/usr/bin/env python3
"""Суточный ряд кликов по старым базам — тем, что созданы до начала выгрузки.

Треть привязанных конверсий приходит с баз, которых нет в реестре `/v1/subdomains`
(он отдаёт созданные с 01.08). Это наши же базы — та же форма `бренд.база.зона`, —
просто старше. Для вопроса «сколько живёт домен» они и есть ответ: их возраст
больше всего окна наблюдения.

Ряд строится по имени базы (два последних уровня хоста), потому что реестра для
них нет и связать сабдомен с базой иначе нечем.

    python3 starye_bazy.py <старые_базы.txt> <days_old.json> <clicks.jsonl> [ещё...]
"""
import sys, json, collections

want = {l.strip() for l in open(sys.argv[1], encoding='utf-8') if l.strip()}
out_path, clicks = sys.argv[2], sys.argv[3:]
days = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
seen = 0

for p in clicks:
    with open(p, encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            s = (r.get('subdomain') or '').lower()
            if s.count('.') < 2:
                continue
            b = '.'.join(s.split('.')[-2:])
            if b not in want:
                continue
            at = r.get('at')
            if not at:
                continue
            seen += 1
            h = r.get('referer') or ''
            d = days[b][at[:10]]
            d[0] += 1
            d[1] += 1 if ('yandex' in h or '//ya.ru' in h) else 0
    print(f'  {p}: накоплено {seen} кликов по {len(days)} старым базам', flush=True)

json.dump({b: dict(v) for b, v in days.items()}, open(out_path, 'w', encoding='utf-8'),
          ensure_ascii=False)
print(f'ГОТОВО: {seen} кликов, {len(days)} баз -> {out_path}')
