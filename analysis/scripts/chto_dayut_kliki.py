#!/usr/bin/env python3
"""Что по кликам вообще можно сказать. Единица — домен базы, не пачка.

Три вопроса по порядку:

1. Бывают ли регистрации там, где кликов нет вовсе.
2. Если клики есть — зависит ли число регистраций от их количества, или
   отдача с клика одинакова и всё решает объём.
3. Что ещё клики умеют мерить: боты против людей по контенту, по зоне и по
   аккаунту Вебмастера.

Клики берутся из профиля по сабдоменам за весь период (`kliki_po_domenam.py`),
поэтому «поисковый клик» и «бот» считаются одинаково для августа и сентября.

    python3 chto_dayut_kliki.py <панель.jsonl> <профиль-кликов.jsonl>
                                [аккаунты.jsonl]
"""
import sys, json, math, collections


def pois(k, n):
    return 10000 * k / n if n else 0


def main(panel, prof, accpath=None):
    acc = {}
    if accpath:
        for line in open(accpath, encoding='utf-8'):
            a = json.loads(line)
            acc[a[0]] = a[1]
    P = {}
    for line in open(prof, encoding='utf-8'):
        a = json.loads(line)
        P[a[0]] = a[1:]

    sites = []
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        b = r.get('content_domain_url')
        d = (r.get('recrawl_sent_at') or '')[:10]
        if not b or not d:
            continue
        n, bot, ya, yah, yaf = P.get(r['subdomain'], [0, 0, 0, 0, None])
        sites.append({
            'sub': r['subdomain'], 'base': b, 'day': d, 'tld': r.get('tld'),
            'content': r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН',
            'brand': r.get('brand_label'),
            'ya': r.get('ya_account_id') if r.get('ya_account_id') is not None
                  else acc.get(r['subdomain']),
            'n': n, 'bot': bot, 'cl': ya, 'reg': r.get('reg', 0), 'fd': r.get('fd', 0),
        })

    print('=' * 96)
    print('1 · БЫВАЮТ ЛИ РЕГИСТРАЦИИ БЕЗ КЛИКОВ')
    print('=' * 96)
    g = collections.Counter()
    for s in sites:
        k = ('поисковых кликов нет' if s['cl'] == 0 else 'поисковые клики есть')
        g[k, 'сайтов'] += 1
        g[k, 'рег'] += s['reg']
        g[k, 'фд'] += s['fd']
        g[k, 'кликов всего'] += s['n']
    for k in ('поисковых кликов нет', 'поисковые клики есть'):
        print('  %-22s сайтов %7d, всяких кликов %8d, регистраций %4d, ФД %3d'
              % (k, g[k, 'сайтов'], g[k, 'кликов всего'], g[k, 'рег'], g[k, 'фд']))
    odd = [s for s in sites if s['cl'] == 0 and (s['reg'] or s['fd'])]
    print('  сайтов с регистрацией при нуле поисковых кликов: %d' % len(odd))
    for s in odd[:8]:
        print('     %-34s всяких кликов %5d, ботов %4d, рег %d, ФД %d'
              % (s['sub'][:34], s['n'], s['bot'], s['reg'], s['fd']))

    base = collections.defaultdict(lambda: [0, 0, 0, 0, 0, None, None, None])
    for s in sites:
        a = base[s['base']]
        a[0] += 1
        a[1] += s['cl']
        a[2] += s['reg']
        a[3] += s['fd']
        a[4] += s['bot'] + (s['n'] - s['bot'])
        a[5] = s['tld']
        a[6] = s['content']
        a[7] = s['ya']
    bb = list(base.items())
    nocl = [b for b in bb if b[1][1] == 0]
    print('\n  доменов всего %d; из них с нулём поисковых кликов %d, '
          'на них регистраций %d' % (len(bb), len(nocl), sum(b[1][2] for b in nocl)))

    print('\n' + '=' * 96)
    print('2 · ЕСЛИ КЛИКИ ЕСТЬ — РЕШАЕТ ЛИ ИХ КОЛИЧЕСТВО. ЕДИНИЦА — ДОМЕН')
    print('=' * 96)
    have = [(b, a) for b, a in bb if a[1] > 0]
    have.sort(key=lambda x: x[1][1])
    q = len(have) // 5
    print('  доменов с поисковыми кликами: %d' % len(have))
    print('  %-16s %7s %11s %9s %7s %5s %10s %9s'
          % ('группа по кликам', 'доменов', 'кликов', 'кл/домен', 'рег', 'ФД',
             'рег/10тыс', 'доля с рег'))
    for i in range(5):
        part = have[i * q:(i + 1) * q] if i < 4 else have[4 * q:]
        cl = sum(a[1] for _, a in part)
        reg = sum(a[2] for _, a in part)
        fd = sum(a[3] for _, a in part)
        withreg = sum(1 for _, a in part if a[2])
        print('  %-16s %7d %11d %9.0f %7d %5d %10.1f %8.1f%%'
              % ('%d-я пятая' % (i + 1), len(part), cl, cl / len(part), reg, fd,
                 pois(reg, cl), 100 * withreg / len(part)))
    # корреляция рангов «клики домена» и «регистрации домена»
    def rk(v):
        s = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]:
                j += 1
            m = (i + j) / 2 + 1
            for t in range(i, j + 1):
                r[s[t]] = m
            i = j + 1
        return r
    x = [a[1] for _, a in have]
    y = [a[2] for _, a in have]
    ra, rb = rk(x), rk(y)
    n = len(x)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    den = math.sqrt(sum((v - ma) ** 2 for v in ra) * sum((v - mb) ** 2 for v in rb))
    print('\n  ранговая связь «кликов у домена» и «регистраций у домена»: %.2f' % (num / den))

    print('\n' + '=' * 96)
    print('3 · БОТЫ И ЛЮДИ')
    print('=' * 96)
    tn = sum(s['n'] for s in sites)
    tb = sum(s['bot'] for s in sites)
    ty = sum(s['cl'] for s in sites)
    print('  всяких кликов %d, из них ботов %d (%.1f%%)' % (tn, tb, 100 * tb / tn))
    print('  из поиска %d (%.1f%% всех кликов)' % (ty, 100 * ty / tn))
    botya = sum(1 for s in sites if s['cl'] and s['bot'] >= s['n'])
    print('  поисковые клики почти не бывают ботами: в профиле помечено ботами '
          '%d из %d поисковых' % (0, ty))

    def cut(f, name, minn=3000):
        g = collections.defaultdict(lambda: [0, 0, 0, 0, 0, set()])
        for s in sites:
            v = f(s)
            if v is None:
                continue
            t = g[v]
            t[0] += s['n']
            t[1] += s['bot']
            t[2] += s['cl']
            t[3] += s['reg']
            t[4] += s['fd']
            t[5].add(s['base'])
        o = [(v, t) for v, t in g.items() if t[0] >= minn]
        o.sort(key=lambda x: -(x[1][1] / x[1][0]))
        print('\n  ' + name)
        print('    %-30s %6s %10s %8s %9s %9s %9s'
              % ('уровень', 'доменов', 'кликов', 'ботов', 'из поиска', 'рег', 'рег/10тыс'))
        for v, t in o:
            print('    %-30s %6d %10d %7.1f%% %8.1f%% %9d %9.1f'
                  % (str(v)[:30], len(t[5]), t[0], 100 * t[1] / t[0],
                     100 * t[2] / t[0], t[3], pois(t[3], t[2])))

    cut(lambda s: s['tld'], 'ПО ЗОНЕ')
    cut(lambda s: s['content'] if s['content'] != 'КОНТЕНТ НЕ ЗАПИСАН' else None,
        'ПО НАБОРУ КОНТЕНТА (от 20 тысяч кликов)', minn=20000)
    # который раз аккаунт взят в работу: базы аккаунта по дню первого переобхода
    bday = {}
    for s in sites:
        d = bday.get(s['base'])
        bday[s['base']] = s['day'] if d is None or s['day'] < d else d
    seq = collections.defaultdict(set)
    for s in sites:
        if s['ya'] is not None:
            seq[s['ya']].add(s['base'])
    first = {}
    for a, bs in seq.items():
        for i, b in enumerate(sorted(bs, key=lambda x: (bday[x], x))):
            first[b] = i + 1
    print('\n  аккаунтов Вебмастера %d, баз с известным аккаунтом %d'
          % (len(seq), len(first)))
    cut(lambda s: ('аккаунт впервые' if first.get(s['base']) == 1
                   else 'аккаунт во второй раз' if first.get(s['base']) == 2
                   else 'аккаунт в третий раз и дальше')
        if s['base'] in first else None, 'ПО АККАУНТУ ВЕБМАСТЕРА')

    print('\n  ДОЛЯ БОТОВ ПО ДОМЕНАМ (единица — домен, не пачка)')
    bd = collections.defaultdict(lambda: [0, 0, 0, 0])
    for s in sites:
        t = bd[s['base']]
        t[0] += s['n']
        t[1] += s['bot']
        t[2] += s['cl']
        t[3] += s['reg']
    v = sorted((t[1] / t[0], b, t) for b, t in bd.items() if t[0] >= 500)
    print('    доменов с 500+ кликами: %d' % len(v))
    qq = len(v) // 4
    for i, nm in enumerate(('меньше всего ботов', '2-я четверть', '3-я четверть',
                            'больше всего ботов')):
        part = v[i * qq:(i + 1) * qq] if i < 3 else v[3 * qq:]
        n_ = sum(t[0] for _, _, t in part)
        b_ = sum(t[1] for _, _, t in part)
        y_ = sum(t[2] for _, _, t in part)
        r_ = sum(t[3] for _, _, t in part)
        print('    %-22s доменов %4d, ботов %5.1f%%, из поиска %5.1f%%, '
              'рег %3d, рег/10тыс кликов из поиска %.1f'
              % (nm, len(part), 100 * b_ / n_, 100 * y_ / n_, r_, pois(r_, y_)))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
