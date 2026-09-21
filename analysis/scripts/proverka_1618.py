#!/usr/bin/env python3
"""Проверка предсказания гипотезы 1 на запусках 16–18.09.

Гипотеза 1 (`analysis/spec/GIPOTEZY_20.09.md`) утверждала, что просадка недели
07.09 — это контент, а не инфраструктура, и что серии `content-2026-09-14c` и
`-14b` дадут 17–26% выхода в поиск за трое суток. Тогда у запусков 16–18.09
трёхсуточное окно ещё не закрылось, и проверить было нечем.

Здесь оно закрыто свежей выгрузкой кликов: 16.09 → окно до 19.09, 17.09 → до
20.09, 18.09 → до 21.09. Последний день неполный, это помечено в выводе.

    python3 proverka_1618.py <панель.jsonl> <subdomains.jsonl>[,…] <клики.jsonl>[,…]
"""
import sys, json, re, collections, datetime

K = 3
DAYS = ('2026-09-16', '2026-09-17', '2026-09-18')


def fam(name):
    return re.sub(r'[_\-]\d+$', '', name)


def main(panel, subs_paths, click_paths):
    api = {}
    for p in subs_paths:
        for line in open(p, encoding='utf-8'):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get('content_label'):
                api[r['subdomain'].lower()] = r['content_label']

    sites = {}
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        if d not in DAYS or not r.get('content_domain_url'):
            continue
        sites[r['subdomain']] = {
            'pack': fam(api.get(r['subdomain']) or r.get('content') or 'БЕЗ ИМЕНИ'),
            'day': d, 'base': r['content_domain_url'], 'tld': r.get('tld'),
            'yaf': None,
        }
    print('сайтов, ушедших в переобход 16–18.09: %d на %d базах'
          % (len(sites), len({v['base'] for v in sites.values()})))

    seen = 0
    for p in click_paths:
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            s = (r.get('subdomain') or '').lower()
            v = sites.get(s)
            if v is None:
                continue
            seen += 1
            h = r.get('referer') or ''
            if not ('yandex' in h or '//ya.ru' in h):
                continue
            at = (r.get('at') or '')[:10]
            if at and (v['yaf'] is None or at < v['yaf']):
                v['yaf'] = at
    print('кликов по этим сайтам в свежей выгрузке: %d' % seen)

    def hit(v):
        if not v['yaf']:
            return 0
        n = (datetime.date.fromisoformat(v['yaf'])
             - datetime.date.fromisoformat(v['day'])).days
        return 1 if 0 <= n <= K else 0

    for v in sites.values():
        v['hit'] = hit(v)

    print('\nПО ДНЯМ')
    print('день        сайтов   выход3')
    byday = collections.defaultdict(lambda: [0, 0])
    for v in sites.values():
        t = byday[v['day']]
        t[0] += v['hit']
        t[1] += 1
    for d in sorted(byday):
        h, n = byday[d]
        mark = '  (окно закрывается сегодня, цифра неполная)' if d == DAYS[-1] else ''
        print('%s %7d  %6.1f%%%s' % (d, n, 100 * h / n, mark))
    th = sum(v['hit'] for v in sites.values())
    print('итого %11d  %6.1f%%' % (len(sites), 100 * th / len(sites)))

    print('\nПО ПАКАМ (500+ сайтов)')
    print('%-44s %7s %7s %7s' % ('пак', 'сайтов', 'баз', 'выход3'))
    g = collections.defaultdict(lambda: [0, 0, set()])
    for v in sites.values():
        t = g[v['pack']]
        t[0] += v['hit']
        t[1] += 1
        t[2].add(v['base'])
    for p, (h, n, b) in sorted(g.items(), key=lambda x: -x[1][0] / x[1][1]):
        if n < 500:
            continue
        print('%-44s %7d %7d %6.1f%%' % (p[:43], n, len(b), 100 * h / n))
    small = [(p, t) for p, t in g.items() if t[1] < 500]
    if small:
        h = sum(t[0] for _, t in small)
        n = sum(t[1] for _, t in small)
        print('%-44s %7d %7s %6.1f%%' % ('прочие паки мельче 500 сайтов (%d шт.)' % len(small),
                                         n, '', 100 * h / n))


if __name__ == '__main__':
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2].split(','), sys.argv[3].split(','))
