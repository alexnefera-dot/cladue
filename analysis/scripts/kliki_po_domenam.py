#!/usr/bin/env python3
"""Профиль кликов по каждому сабдомену за весь период: боты, люди, поиск.

Один проход по всем выгрузкам кликов. Окна выгрузок перекрываются, поэтому у
последнего файла берётся только хвост после 17.09 — так дедупликация не нужна
и память не тратится на 17 миллионов идентификаторов.

На выходе строка на сабдомен:
    [сабдомен, всего, ботов, из поиска, из поиска не бот, первый поисковый клик]

«Из поиска» — реферер Яндекса. Бот — флаг трекера `is_bot`.

    python3 kliki_po_domenam.py <выход.jsonl> <файл кликов>[:<от YYYY-MM-DD>] ...
"""
import sys, json


def main(out, specs):
    agg = {}
    seen = 0
    for spec in specs:
        path, _, since = spec.partition(':')
        for line in open(path, encoding='utf-8'):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            at = (r.get('at') or '')[:10]
            if since and (not at or at <= since):
                continue
            s = (r.get('subdomain') or '').lower()
            if not s:
                continue
            seen += 1
            h = r.get('referer') or ''
            ya = 1 if ('yandex' in h or '//ya.ru' in h) else 0
            bot = 1 if r.get('is_bot') else 0
            a = agg.get(s)
            if a is None:
                agg[s] = a = [0, 0, 0, 0, None]
            a[0] += 1
            a[1] += bot
            if ya:
                a[2] += 1
                if not bot:
                    a[3] += 1
                if at and (a[4] is None or at < a[4]):
                    a[4] = at
        print('  %s: накоплено %d кликов, сабдоменов %d' % (path.split('/')[-1], seen, len(agg)),
              flush=True)
    with open(out, 'w', encoding='utf-8') as f:
        for s, a in agg.items():
            f.write(json.dumps([s] + a, ensure_ascii=False) + '\n')
    tot = sum(a[0] for a in agg.values())
    bot = sum(a[1] for a in agg.values())
    ya = sum(a[2] for a in agg.values())
    yah = sum(a[3] for a in agg.values())
    print('кликов %d, ботов %d (%.1f%%), из поиска %d, из поиска живых %d (%.1f%% поиска)'
          % (tot, bot, 100 * bot / tot, ya, yah, 100 * yah / ya if ya else 0))
    print('-> %s' % out)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
