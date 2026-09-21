#!/usr/bin/env python3
"""Каждый домен поимённо: сколько у него ботов, поиска и прочего трафика.

Прежняя таблица делила домены на четверти по доле ботов и показывала средние.
Здесь — сами домены, строкой на домен, без группировки.

Колонки: всяких кликов, из них ботов, из поиска, прочих (не бот и не поиск),
и конверсии. Доля ботов считается от всяких кликов домена.

    python3 boty_po_domenam.py <панель.jsonl> <профиль-кликов.jsonl> <выход.csv>
"""
import sys, json, csv, collections


def main(panel, prof, out):
    P = {}
    for line in open(prof, encoding='utf-8'):
        a = json.loads(line)
        P[a[0]] = a[1:]
    b = collections.defaultdict(lambda: {'n': 0, 'bot': 0, 'ya': 0, 'sites': 0,
                                         'day': None, 'tld': None,
                                         'content': collections.Counter(),
                                         'reg': 0, 'fd': 0})
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        dom = r.get('content_domain_url')
        d = (r.get('recrawl_sent_at') or '')[:10]
        if not dom or not d:
            continue
        n, bot, ya, yah, yaf = P.get(r['subdomain'], [0, 0, 0, 0, None])
        t = b[dom]
        t['n'] += n
        t['bot'] += bot
        t['ya'] += ya
        t['sites'] += 1
        t['reg'] += r.get('reg', 0)
        t['fd'] += r.get('fd', 0)
        t['tld'] = r.get('tld')
        t['content'][r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН'] += 1
        t['day'] = d if t['day'] is None or d < t['day'] else t['day']

    rows = []
    for dom, t in b.items():
        n = t['n']
        rows.append({
            'домен': dom, 'зона': t['tld'], 'день': t['day'],
            'набор контента': t['content'].most_common(1)[0][0],
            'сайтов': t['sites'], 'кликов всего': n,
            'ботов': t['bot'], 'ботов %': round(100 * t['bot'] / n, 1) if n else '',
            'из поиска': t['ya'], 'из поиска %': round(100 * t['ya'] / n, 1) if n else '',
            'прочих': n - t['bot'] - t['ya'],
            'регистраций': t['reg'], 'ФД': t['fd'],
            'рег на 10 тыс. поисковых': round(10000 * t['reg'] / t['ya'], 1) if t['ya'] else '',
        })
    rows.sort(key=lambda r: (-(r['ботов %'] if r['ботов %'] != '' else -1), r['домен']))
    with open(out, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    big = [r for r in rows if r['кликов всего'] >= 500]
    print('доменов всего %d, с 500+ кликами %d' % (len(rows), len(big)))
    w = '  {:<20}{:<8}{:<12}{:>8}{:>9}{:>9}{:>9}{:>8}{:>5}'
    print('\nБОЛЬШЕ ВСЕГО БОТОВ')
    print(w.format('домен', 'зона', 'день', 'кликов', 'ботов %', 'поиск %', 'прочих', 'рег', 'ФД'))
    for r in big[:15]:
        print(w.format(r['домен'][:20], r['зона'], r['день'], r['кликов всего'],
                       r['ботов %'], r['из поиска %'], r['прочих'], r['регистраций'], r['ФД']))
    print('\nМЕНЬШЕ ВСЕГО БОТОВ')
    print(w.format('домен', 'зона', 'день', 'кликов', 'ботов %', 'поиск %', 'прочих', 'рег', 'ФД'))
    for r in big[-15:]:
        print(w.format(r['домен'][:20], r['зона'], r['день'], r['кликов всего'],
                       r['ботов %'], r['из поиска %'], r['прочих'], r['регистраций'], r['ФД']))
    print('\nБОЛЬШЕ ВСЕГО РЕГИСТРАЦИЙ')
    top = sorted(big, key=lambda r: (-r['регистраций'], -r['ФД']))[:15]
    print(w.format('домен', 'зона', 'день', 'кликов', 'ботов %', 'поиск %', 'прочих', 'рег', 'ФД'))
    for r in top:
        print(w.format(r['домен'][:20], r['зона'], r['день'], r['кликов всего'],
                       r['ботов %'], r['из поиска %'], r['прочих'], r['регистраций'], r['ФД']))
    print('\n-> %s' % out)


if __name__ == '__main__':
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
