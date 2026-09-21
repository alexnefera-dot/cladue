#!/usr/bin/env python3
"""Каждая группа контента отдельно, под своим настоящим именем.

Никаких придуманных семейств: строка — это набор ровно так, как он назван в
журнале запусков, без склейки и без переименования. Номер экземпляра
(«_1…_50», «_44») срезан, потому что это один и тот же набор, разложенный по
базам.

Зона показана составом, а не одним значением: один и тот же набор часто лежит
в двух зонах сразу, и его общая отдача — среднее двух разных чисел. Поэтому
рядом отдельные колонки по `.team` и по `.lol`.

Метрика — регистрации в окне трёх суток от переобхода.

    python3 gruppy_kontenta.py <панель.jsonl> <окно3.jsonl> <выход.csv>
"""
import sys, json, re, csv, collections


def main(panel, oknopath, out):
    W = {}
    for line in open(oknopath, encoding='utf-8'):
        a = json.loads(line)
        W[a[0]] = a[1:]
    g = collections.defaultdict(lambda: {
        'bases': set(), 'days': set(), 'n': 0, 'cl': 0, 'reg': 0, 'fd': 0,
        'z': collections.Counter(),
        'byz': collections.defaultdict(lambda: [0, 0, 0])})
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        b = r.get('content_domain_url')
        if not d or not b:
            continue
        name = re.sub(r'[_\-]\d+$', '', r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН')
        w = W.get(r['subdomain'], [0, 0, 0, 0, 0])
        t = g[name]
        t['bases'].add(b)
        t['days'].add(d)
        t['n'] += 1
        t['cl'] += w[2]
        t['reg'] += w[3]
        t['fd'] += w[4]
        z = r.get('tld')
        t['z'][z] += 1
        tz = t['byz'][z]
        tz[0] += 1
        tz[1] += w[3]
        tz[2] += w[2]

    rows = []
    for name, t in g.items():
        row = {
            'группа контента': name,
            'баз': len(t['bases']), 'сайтов': t['n'],
            'первый день': min(t['days']), 'дней': len(t['days']),
            'зоны': ' '.join('.%s %d%%' % (k, round(100 * v / t['n']))
                             for k, v in t['z'].most_common(3)),
            'кликов из поиска в окне': t['cl'],
            'регистраций': t['reg'], 'ФД': t['fd'],
            'рег на 100 сайтов': round(100 * t['reg'] / t['n'], 3),
            'рег на 10 тыс. кликов': round(10000 * t['reg'] / t['cl'], 1) if t['cl'] else '',
        }
        for z in ('team', 'lol', 'casino', 'buzz'):
            a = t['byz'].get(z)
            row['сайтов .%s' % z] = a[0] if a else 0
            row['рег .%s' % z] = a[1] if a else 0
            row['на 100 в .%s' % z] = round(100 * a[1] / a[0], 3) if a and a[0] else ''
        rows.append(row)
    rows.sort(key=lambda r: -r['рег на 100 сайтов'])
    with open(out, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    tot = sum(r['сайтов'] for r in rows)
    treg = sum(r['регистраций'] for r in rows)
    print('групп контента: %d, сайтов %d, регистраций в окне %d, в среднем %.3f на 100'
          % (len(rows), tot, treg, 100 * treg / tot))

    def table(sel, title, key='рег на 100 сайтов'):
        print('\n' + title)
        print('  %-40s %5s %7s %8s %5s %4s %11s %10s  %s'
              % ('группа контента', 'баз', 'сайтов', 'кликов', 'рег', 'ФД',
                 'рег на 100', 'рег/10т кл', 'зоны'))
        for r in sel:
            print('  %-40s %5d %7d %8d %5d %4d %11.3f %10s  %s'
                  % (r['группа контента'][:40], r['баз'], r['сайтов'],
                     r['кликов из поиска в окне'], r['регистраций'], r['ФД'],
                     r[key], r['рег на 10 тыс. кликов'], r['зоны']))

    big = [r for r in rows if r['сайтов'] >= 1500]
    table([r for r in big if r['регистраций'] > 0],
          'ГРУППЫ ОТ 1500 САЙТОВ, ДАВШИЕ ХОТЬ ОДНУ РЕГИСТРАЦИЮ')
    zero = [r for r in big if r['регистраций'] == 0]
    table(zero, 'ГРУППЫ ОТ 1500 САЙТОВ БЕЗ ЕДИНОЙ РЕГИСТРАЦИИ')
    print('\n  на них сайтов %d (%.0f%% сети), поисковых кликов в окне %d'
          % (sum(r['сайтов'] for r in zero),
             100 * sum(r['сайтов'] for r in zero) / tot,
             sum(r['кликов из поиска в окне'] for r in zero)))

    print('\n\nОДНА И ТА ЖЕ ГРУППА В РАЗНЫХ ЗОНАХ (от 1000 сайтов в каждой)')
    print('  %-40s %9s %7s %9s %9s %7s %9s'
          % ('группа контента', 'сайтов .team', 'рег', 'на 100', 'сайтов .lol', 'рег', 'на 100'))
    for r in rows:
        if r['сайтов .team'] >= 1000 and r['сайтов .lol'] >= 1000:
            print('  %-40s %9d %7d %9.3f %9d %7d %9.3f'
                  % (r['группа контента'][:40], r['сайтов .team'], r['рег .team'],
                     r['на 100 в .team'], r['сайтов .lol'], r['рег .lol'],
                     r['на 100 в .lol']))
    print('\n-> %s' % out)


if __name__ == '__main__':
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
