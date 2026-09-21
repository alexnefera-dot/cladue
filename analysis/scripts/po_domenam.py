#!/usr/bin/env python3
"""Каждая база отдельной строкой, сложенные в пулы по пакам.

Пул — пак плюс день переобхода: всё, что в этот день ушло на одном контенте.
Внутри пула строка = один домен базы. Именно на этом уровне сидит разброс,
который не объясняет ни один записанный признак, и увидеть его можно только
поимённо.

Метрика — выход в поиск за трое суток от переобхода. Первый поисковый клик
берётся из двух источников сразу: накопленной выгрузки по сабдоменам и свежей
выгрузки кликов, минимум из двух. Без свежей выгрузки у запусков после 15.09
окно не закрыто и все они выглядят пустыми.

Днём базы считается первый её день переобхода; вторая волна — остаток брендов,
уехавший на следующий день, он показан отдельной колонкой.

    python3 po_domenam.py <панель.jsonl> <subdomains.jsonl>[,…]
                          <клики-по-сабдоменам.jsonl> <свежие-клики.jsonl>[,…]
                          <выход.csv> [последний-полный-день]
"""
import sys, json, re, csv, collections, datetime

K = 3


def fam(name):
    return re.sub(r'[_\-]\d+$', '', name)


def main(panel, subs_paths, subsclicks, fresh_paths, out_csv, last):
    api = {}
    for p in subs_paths:
        for line in open(p, encoding='utf-8'):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get('content_label'):
                api[r['subdomain'].lower()] = r['content_label']

    yaf = {}
    for line in open(subsclicks, encoding='utf-8'):
        s, n, ya, f, l, yf, yl = json.loads(line)
        if yf:
            yaf[s] = yf[:10]

    sites = {}
    bd = collections.defaultdict(set)
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        b = r.get('content_domain_url')
        if not d or not b:
            continue
        bd[b].add(d)
        sites[r['subdomain']] = {
            'pack': fam(api.get(r['subdomain']) or r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН'),
            'day': d, 'base': b, 'tld': r.get('tld'),
            'cl': r.get('ya_clicks') or 0, 'reg': r.get('reg', 0), 'fd': r.get('fd', 0),
        }

    for p in fresh_paths:
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            s = (r.get('subdomain') or '').lower()
            if s not in sites:
                continue
            hh = r.get('referer') or ''
            if not ('yandex' in hh or '//ya.ru' in hh):
                continue
            at = (r.get('at') or '')[:10]
            if at and (s not in yaf or at < yaf[s]):
                yaf[s] = at

    order = {b: {d: i for i, d in enumerate(sorted(ds))} for b, ds in bd.items()}
    g = collections.defaultdict(lambda: {
        'tld': None, 'packs': collections.Counter(), 'days': set(),
        'n': 0, 'hit': 0, 'w2': 0, 'cl': 0, 'reg': 0, 'fd': 0})
    for s, v in sites.items():
        if v['day'] > last:
            continue
        a = g[v['base']]
        a['tld'] = v['tld']
        a['packs'][v['pack']] += 1
        a['days'].add(v['day'])
        a['n'] += 1
        a['w2'] += 1 if order[v['base']][v['day']] else 0
        a['cl'] += v['cl']
        a['reg'] += v['reg']
        a['fd'] += v['fd']
        f = yaf.get(s)
        if f and 0 <= (datetime.date.fromisoformat(f)
                       - datetime.date.fromisoformat(v['day'])).days <= K:
            a['hit'] += 1

    rows = []
    for b, a in g.items():
        rows.append({
            'домен базы': b, 'зона': a['tld'],
            'набор контента': a['packs'].most_common(1)[0][0],
            'наборов на базе': len(a['packs']),
            'первый день': min(a['days']), 'дней': len(a['days']),
            'сайтов': a['n'], 'во второй волне': a['w2'],
            'вышли в поиск за 3 суток': a['hit'],
            'выход3 %': round(100 * a['hit'] / a['n'], 1),
            'поисковых кликов': a['cl'], 'регистраций': a['reg'], 'ФД': a['fd'],
        })
    rows.sort(key=lambda r: (r['пак'], r['первый день'], -r['выход3 %']))
    with open(out_csv, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print('баз %d, сайтов %d, вышли в поиск %d (%.1f%%)' % (
        len(rows), sum(r['сайтов'] for r in rows),
        sum(r['вышли в поиск за 3 суток'] for r in rows),
        100 * sum(r['вышли в поиск за 3 суток'] for r in rows) / sum(r['сайтов'] for r in rows)))

    pool = collections.defaultdict(list)
    for r in rows:
        pool[(r['пак'], r['первый день'])].append(r)
    big = {k: v for k, v in pool.items() if len(v) >= 5}
    print('пулов «пак + день» по пять и больше баз: %d, в них баз %d'
          % (len(big), sum(len(v) for v in big.values())))
    for (p, d), v in sorted(big.items(), key=lambda x: -sum(y['сайтов'] for y in x[1])):
        n = sum(y['сайтов'] for y in v)
        hh = sum(y['вышли в поиск за 3 суток'] for y in v)
        print('\n%s · %s · баз %d · сайтов %d · выход3 %.1f%% · рег %d'
              % (p, d, len(v), n, 100 * hh / n, sum(y['регистраций'] for y in v)))
        print('  %-18s %-8s %7s %7s %8s %9s %5s' % (
            'домен', 'зона', 'сайтов', 'выход3', 'кликов', '2-я волна', 'рег'))
        for y in v:
            print('  %-18s %-8s %7d %6.1f%% %8d %9d %5d' % (
                y['домен базы'][:18], y['зона'], y['сайтов'], y['выход3 %'],
                y['поисковых кликов'], y['во второй волне'], y['регистраций']))


if __name__ == '__main__':
    if len(sys.argv) < 6:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2].split(','), sys.argv[3], sys.argv[4].split(','),
         sys.argv[5], sys.argv[6] if len(sys.argv) > 6 else '2026-09-18')
