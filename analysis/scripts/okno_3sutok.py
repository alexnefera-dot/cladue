#!/usr/bin/env python3
"""Клики и конверсии в окне первых трёх суток от переобхода, по каждому сайту.

Зачем. Домен живёт кликами месяц, а платит в первые двое суток: 84.5%
регистраций приходит за трое суток, 95% за неделю. Если делить регистрации на
все клики домена, долгоживущий домен выглядит хуже умершего просто потому,
что у него знаменатель больше. Окно уравнивает.

Окно — сутки переобхода плюс трое следующих, включительно.

На выходе строка на сабдомен:
    [сабдомен, кликов в окне, ботов в окне, из поиска в окне, регистраций в окне,
     ФД в окне]

    python3 okno_3sutok.py <панель.jsonl> <конверсии.jsonl> <выход.jsonl>
                           <файл кликов>[:<от YYYY-MM-DD>] ...
"""
import sys, json, collections, datetime

K = 3


def main(panel, convpath, out, specs):
    rec = {}
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        if d:
            rec[r['subdomain']] = d
    print('сайтов с датой переобхода: %d' % len(rec))

    edge = {s: str(datetime.date.fromisoformat(d) + datetime.timedelta(days=K))
            for s, d in rec.items()}

    agg = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
    seen = 0
    for spec in specs:
        path, _, since = spec.partition(':')
        for line in open(path, encoding='utf-8'):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            at = (r.get('at') or '')[:10]
            if not at or (since and at <= since):
                continue
            s = (r.get('subdomain') or '').lower()
            d = rec.get(s)
            if d is None or at < d or at > edge[s]:
                continue
            seen += 1
            a = agg[s]
            a[0] += 1
            if r.get('is_bot'):
                a[1] += 1
            h = r.get('referer') or ''
            if 'yandex' in h or '//ya.ru' in h:
                a[2] += 1
        print('  %s: в окне накоплено %d кликов' % (path.split('/')[-1], seen), flush=True)

    nreg = 0
    for line in open(convpath, encoding='utf-8'):
        r = json.loads(line)
        s = (r.get('subdomain') or '').lower()
        at = (r.get('at') or '')[:10]
        d = rec.get(s)
        if d is None or not at or at < d or at > edge[s]:
            continue
        nreg += 1
        agg[s][4 if r.get('event') == 'fd' else 3] += 1

    with open(out, 'w', encoding='utf-8') as f:
        for s, a in agg.items():
            f.write(json.dumps([s] + a) + '\n')
    print('сабдоменов с активностью в окне: %d' % len(agg))
    print('кликов в окне %d, из них ботов %d (%.1f%%), из поиска %d'
          % (sum(a[0] for a in agg.values()), sum(a[1] for a in agg.values()),
             100 * sum(a[1] for a in agg.values()) / max(1, sum(a[0] for a in agg.values())),
             sum(a[2] for a in agg.values())))
    print('конверсий в окне: %d (регистраций %d, ФД %d)'
          % (nreg, sum(a[3] for a in agg.values()), sum(a[4] for a in agg.values())))
    print('-> %s' % out)


if __name__ == '__main__':
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
