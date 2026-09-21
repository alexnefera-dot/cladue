#!/usr/bin/env python3
"""Все прежние сравнения, пересчитанные в окне первых трёх суток.

Раньше знаменателем стояли все клики домена за всю его жизнь. Домен живёт
кликами месяц, а платит в первые двое суток, поэтому долгоживущие домены
получали завышенный знаменатель и выглядели хуже, чем есть.

Здесь и клики, и конверсии берутся только из окна: сутки переобхода плюс трое
следующих. Рядом — те же величины за всё время, чтобы видеть, что изменилось.

    python3 v_okne.py <панель.jsonl> <окно.jsonl> <профиль-кликов.jsonl>
                      <аккаунты.jsonl>
"""
import sys, json, re, collections


def fam(n):
    return re.sub(r'[_\-]\d+$', '', n)


def main(panel, oknopath, prof, accpath):
    W = {}
    for line in open(oknopath, encoding='utf-8'):
        a = json.loads(line)
        W[a[0]] = a[1:]
    P = {}
    for line in open(prof, encoding='utf-8'):
        a = json.loads(line)
        P[a[0]] = a[1:]
    acc = {}
    for line in open(accpath, encoding='utf-8'):
        a = json.loads(line)
        acc[a[0]] = a[1]

    rows, bd = [], collections.defaultdict(set)
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        b = r.get('content_domain_url')
        if not d or not b:
            continue
        bd[b].add(d)
        w = W.get(r['subdomain'], [0, 0, 0, 0, 0])
        p = P.get(r['subdomain'], [0, 0, 0, 0, None, None, None, None])
        rows.append({
            'base': b, 'day': d, 'tld': r.get('tld'),
            'content': fam(r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН'),
            'brand': r.get('brand_label'),
            'ya': r.get('ya_account_id') if r.get('ya_account_id') is not None
                  else acc.get(r['subdomain']),
            'wcl': w[2], 'wbot': w[1], 'wall': w[0], 'wreg': w[3], 'wfd': w[4],
            'acl': p[2], 'areg': r.get('reg', 0), 'afd': r.get('fd', 0),
            'hit': 1 if w[2] else 0,
        })
    order = {b: {d: i for i, d in enumerate(sorted(ds))} for b, ds in bd.items()}
    first = {b: min(ds) for b, ds in bd.items()}
    byacc = collections.defaultdict(set)
    for r in rows:
        if r['ya'] is not None:
            byacc[r['ya']].add(r['base'])
    seq = {}
    for a, bs in byacc.items():
        for i, b in enumerate(sorted(bs, key=lambda x: (first[x], x))):
            seq[b] = i + 1
    for r in rows:
        r['wave'] = min(order[r['base']][r['day']], 1)
        r['seq'] = seq.get(r['base'])

    tw = sum(r['wcl'] for r in rows)
    ta = sum(r['acl'] for r in rows)
    print('поисковых кликов: в окне %d, за всё время %d (%.0f%%)'
          % (tw, ta, 100 * tw / ta))
    print('регистраций: в окне %d, за всё время %d' %
          (sum(r['wreg'] for r in rows), sum(r['areg'] for r in rows)))
    print('ФД: в окне %d, за всё время %d\n' %
          (sum(r['wfd'] for r in rows), sum(r['afd'] for r in rows)))

    def cut(f, title, minn=800, mincl=0):
        g = collections.defaultdict(lambda: [0, 0, 0, 0, 0, 0, 0, set()])
        for r in rows:
            v = f(r)
            if v is None:
                continue
            t = g[v]
            t[0] += 1
            t[1] += r['wcl']
            t[2] += r['wreg']
            t[3] += r['wfd']
            t[4] += r['acl']
            t[5] += r['areg']
            t[6] += r['hit']
            t[7].add(r['base'])
        o = [(v, t) for v, t in g.items() if t[0] >= minn and t[1] >= mincl]
        if len(o) < 2:
            return
        o.sort(key=lambda x: -(10000 * x[1][2] / x[1][1] if x[1][1] else 0))
        print(title)
        print('  %-28s %5s %7s %10s %6s %4s %9s %11s %8s'
              % ('уровень', 'баз', 'сайтов', 'кликов в окне', 'рег', 'ФД',
                 'рег/10т в окне', 'было за всё', 'разница'))
        for v, t in o:
            a = 10000 * t[2] / t[1] if t[1] else 0
            b = 10000 * t[5] / t[4] if t[4] else 0
            print('  %-28s %5d %7d %10d %6d %4d %9.1f %11.1f %+8.0f%%'
                  % (str(v)[:28], len(t[7]), t[0], t[1], t[2], t[3], a, b,
                     100 * (a / b - 1) if b else 0))
        print()

    cut(lambda r: r['tld'], 'ЗОНА')
    cut(lambda r: 'первая волна' if r['wave'] == 0 else 'вторая волна', 'ВОЛНА')
    cut(lambda r: '12 страниц' if re.search(r'12(page|str|стр)', r['content'], re.I)
        else '7 страниц' if re.search(r'7(page|str|стр)', r['content'], re.I) else None,
        'СТРАНИЦ В САЙТЕ')
    cut(lambda r: ('впервые' if r['seq'] == 1 else 'повторно') if r['seq'] else None,
        'АККАУНТ ВЕБМАСТЕРА')
    cut(lambda r: r['day'][:7], 'МЕСЯЦ')
    cut(lambda r: r['content'] if r['content'] != 'КОНТЕНТ НЕ ЗАПИСАН' else None,
        'НАБОРЫ КОНТЕНТА (от 2000 сайтов и 2000 кликов в окне)', minn=2000, mincl=2000)
    cut(lambda r: r['brand'], 'БРЕНДЫ (от 1200 сайтов и 3000 кликов в окне)',
        minn=1200, mincl=3000)


if __name__ == '__main__':
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
