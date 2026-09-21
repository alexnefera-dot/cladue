#!/usr/bin/env python3
"""Повторный аккаунт против свежего — только на днях, где ставились обе группы.

Доля ботов на повторно взятых аккаунтах вдвое выше, но базы второго захода
запускались позже, а в сентябре ботов в сети больше вообще. Разделить одно от
другого можно только внутри дня: берём дни, где в переобход ушли и свежие
аккаунты, и повторные, и сравниваем там.

Единица — домен базы. Внутри дня считается среднее по доменам, а не сумма
кликов, иначе один многотрафиковый домен перетянет день на себя.

    python3 akkaunt_boty.py <панель.jsonl> <профиль-кликов.jsonl> <аккаунты.jsonl>
"""
import sys, json, collections, statistics


def main(panel, prof, accpath):
    P = {}
    for line in open(prof, encoding='utf-8'):
        a = json.loads(line)
        P[a[0]] = a[1:]
    acc = {}
    for line in open(accpath, encoding='utf-8'):
        a = json.loads(line)
        acc[a[0]] = a[1]

    b = collections.defaultdict(lambda: {'n': 0, 'bot': 0, 'ya': 0, 'sites': 0,
                                         'day': None, 'ya_acc': None, 'tld': None,
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
        t['day'] = d if t['day'] is None or d < t['day'] else t['day']
        a = r.get('ya_account_id')
        if a is None:
            a = acc.get(r['subdomain'])
        if a is not None:
            t['ya_acc'] = a

    seq = collections.defaultdict(list)
    for dom, t in b.items():
        if t['ya_acc'] is not None:
            seq[t['ya_acc']].append((t['day'], dom))
    order = {}
    for a, v in seq.items():
        for i, (d, dom) in enumerate(sorted(v)):
            order[dom] = i + 1
    for dom, t in b.items():
        k = order.get(dom)
        t['grp'] = None if k is None else ('свежий' if k == 1 else 'повторный')

    use = [t for t in b.values() if t['grp'] and t['n'] >= 300]
    print('доменов в расчёте: %d (свежих %d, повторных %d)'
          % (len(use), sum(1 for t in use if t['grp'] == 'свежий'),
             sum(1 for t in use if t['grp'] == 'повторный')))

    byday = collections.defaultdict(lambda: collections.defaultdict(list))
    for t in use:
        byday[t['day']][t['grp']].append(t)
    both = {d: g for d, g in byday.items()
            if len(g) == 2 and min(len(v) for v in g.values()) >= 5}
    print('дней, где ставились обе группы (по 5+ доменов): %d из %d\n'
          % (len(both), len(byday)))

    print('%-12s %22s %22s' % ('день', 'свежий аккаунт', 'повторный аккаунт'))
    print('%-12s %8s %6s %6s %8s %6s %6s'
          % ('', 'доменов', 'ботов', 'поиск', 'доменов', 'ботов', 'поиск'))
    agg = {'свежий': [0, 0, 0, 0, 0], 'повторный': [0, 0, 0, 0, 0]}
    for d in sorted(both):
        row = []
        for g in ('свежий', 'повторный'):
            v = both[d][g]
            n = sum(t['n'] for t in v)
            bt = sum(t['bot'] for t in v)
            ya = sum(t['ya'] for t in v)
            a = agg[g]
            a[0] += len(v)
            a[1] += n
            a[2] += bt
            a[3] += ya
            a[4] += sum(t['reg'] for t in v)
            row += [len(v), 100 * bt / n if n else 0, 100 * ya / n if n else 0]
        print('%-12s %8d %5.1f%% %5.1f%% %8d %5.1f%% %5.1f%%'
              % (d, row[0], row[1], row[2], row[3], row[4], row[5]))
    print('\n%-12s %8s %6s %6s %8s %6s %6s'
          % ('ИТОГО', 'доменов', 'ботов', 'поиск', 'доменов', 'ботов', 'поиск'))
    print('%-12s %8d %5.1f%% %5.1f%% %8d %5.1f%% %5.1f%%'
          % ('общие дни', agg['свежий'][0], 100 * agg['свежий'][2] / agg['свежий'][1],
             100 * agg['свежий'][3] / agg['свежий'][1], agg['повторный'][0],
             100 * agg['повторный'][2] / agg['повторный'][1],
             100 * agg['повторный'][3] / agg['повторный'][1]))

    # медиана доли ботов по домену внутри общих дней — устойчивее к выбросам
    md = {g: statistics.median([100 * t['bot'] / t['n'] for d in both for t in both[d][g]])
          for g in ('свежий', 'повторный')}
    print('\nмедианная доля ботов по домену: свежий %.1f%%, повторный %.1f%%'
          % (md['свежий'], md['повторный']))
    # знаковый критерий по дням
    w = l = 0
    for d in both:
        f = sum(t['bot'] for t in both[d]['свежий']) / sum(t['n'] for t in both[d]['свежий'])
        p = sum(t['bot'] for t in both[d]['повторный']) / sum(t['n'] for t in both[d]['повторный'])
        if p > f:
            w += 1
        elif p < f:
            l += 1
    import math
    n = w + l
    pv = sum(math.comb(n, i) for i in range(w, n + 1)) / 2 ** n if n else 1
    print('дней, где у повторных ботов больше: %d из %d; знаковый критерий p = %.3f'
          % (w, n, pv))
    print('\nрегистраций: свежие %d, повторные %d' % (agg['свежий'][4], agg['повторный'][4]))


if __name__ == '__main__':
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
