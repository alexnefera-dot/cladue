#!/usr/bin/env python3
"""Разбор сети по согласованному плану. Успех — регистрации и ФД.

Прежние расчёты мерили промежуточный исход «сайт получил клик из поиска».
Здесь успехом считается только то, что названо успехом: регистрация и первый
депозит. Клики остаются, но как описание пути, а не как цель.

Пять блоков:
  1. Картина: сколько запущено, сколько ожило, сколько заработало — по зонам и месяцам.
  2. Бренды: полная таблица, потом бренд на зонах, потом бренд на контентах.
  3. Аккаунты Вебмастера: свежесть = сколько раз использовался и чистился ли.
  4. Контент и зона порознь.
  5. Что из этого следует проверять.

    python3 razbor.py <панель.jsonl> <subdomains.jsonl>[,…] <события.jsonl>
"""
import sys, json, collections, statistics


def h(t):
    print('\n' + '=' * 100)
    print(t)
    print('=' * 100)


def pct(a, b):
    return f'{100.0*a/b:.2f}%' if b else '—'


def main(panel, subs_paths, events):
    reg = {}
    for p in subs_paths:
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            reg[r['subdomain'].lower()] = r

    rows = []
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        s = reg.get(r['subdomain'], {})
        rec = (r.get('recrawl_sent_at') or '')[:10]
        rows.append({
            'sub': r['subdomain'], 'base': r.get('content_domain_url'),
            'brand': r.get('brand_label'), 'tld': r.get('tld'),
            'content': r.get('content'), 'month': rec[:7], 'day': rec,
            'closed': bool(r.get('window_closed')),
            'clicks': r.get('clicks') or 0, 'ya': r.get('ya_clicks') or 0,
            'reg': r.get('reg', 0), 'fd': r.get('fd', 0),
            'ya_acc': s.get('ya_account_id'), 'cd_id': r.get('content_domain_id'),
        })
    closed = [r for r in rows if r['closed']]

    h('БЛОК 1 · КАРТИНА: КТО ЗАПУЩЕН, КТО ОЖИЛ, КТО ЗАРАБОТАЛ')
    print(f'всего сайтов в реестре: {len(rows)}, из них с закрытым окном: {len(closed)}')
    print(f'баз: {len({r["base"] for r in rows if r["base"]})}, '
          f'брендов: {len({r["brand"] for r in rows if r["brand"]})}\n')

    def picture(sel, label):
        n = len(sel)
        c = sum(1 for r in sel if r['clicks'])
        y = sum(1 for r in sel if r['ya'])
        g = sum(1 for r in sel if r['reg'])
        f = sum(1 for r in sel if r['fd'])
        return (label, n, c, y, g, f,
                sum(r['reg'] for r in sel), sum(r['fd'] for r in sel))

    print('по зонам (только закрытые окна):')
    print(f"{'зона':<10}{'сайтов':>9}{'с кликами':>11}{'из поиска':>11}"
          f"{'с рег.':>8}{'с ФД':>7}{'рег':>6}{'ФД':>5}{'рег на 1000 сайтов':>20}")
    byz = collections.defaultdict(list)
    for r in closed:
        byz[r['tld']].append(r)
    for z, sel in sorted(byz.items(), key=lambda kv: -len(kv[1])):
        if len(sel) < 1000:
            continue
        lb, n, c, y, g, f, R, F = picture(sel, z)
        print(f'{str(z):<10}{n:>9}{c:>11}{y:>11}{g:>8}{f:>7}{R:>6}{F:>5}'
              f'{1000.0*R/n:>20.2f}')

    print('\nпо месяцам переобхода:')
    print(f"{'месяц':<10}{'сайтов':>9}{'с кликами':>11}{'из поиска':>11}"
          f"{'с рег.':>8}{'с ФД':>7}{'рег':>6}{'ФД':>5}{'рег на 1000 сайтов':>20}")
    bym = collections.defaultdict(list)
    for r in closed:
        bym[r['month']].append(r)
    for m, sel in sorted(bym.items()):
        if len(sel) < 1000:
            continue
        lb, n, c, y, g, f, R, F = picture(sel, m)
        print(f'{m:<10}{n:>9}{c:>11}{y:>11}{g:>8}{f:>7}{R:>6}{F:>5}'
              f'{1000.0*R/n:>20.2f}')

    print('\nзона × месяц, регистраций на 1000 сайтов:')
    zs = [z for z, s in byz.items() if len(s) >= 5000]
    ms = sorted(m for m, s in bym.items() if len(s) >= 1000)
    print(f"{'зона':<10}" + ''.join(f'{m:>16}' for m in ms))
    for z in zs:
        line = f'{str(z):<10}'
        for m in ms:
            sel = [r for r in closed if r['tld'] == z and r['month'] == m]
            line += (f'{1000.0*sum(r["reg"] for r in sel)/len(sel):>10.2f}'
                     f' ({len(sel)//1000}k)' if len(sel) >= 500 else f'{"—":>16}')
        print(line)

    h('БЛОК 2 · БРЕНДЫ')
    br = collections.defaultdict(lambda: [0, 0, 0, 0, 0, 0, 0])
    for r in closed:
        b = r['brand']
        if not b:
            continue
        t = br[b]
        t[0] += 1
        t[1] += 1 if r['clicks'] else 0
        t[2] += 1 if r['ya'] else 0
        t[3] += 1 if r['reg'] else 0
        t[4] += r['reg']
        t[5] += r['fd']
        t[6] += r['ya']
    tot_r = sum(v[4] for v in br.values())
    tot_f = sum(v[5] for v in br.values())
    print(f'брендов {len(br)}, регистраций {tot_r}, ФД {tot_f}')
    print(f'\nбренды с конверсиями (отсортированы по регистрациям):')
    print(f"{'бренд':<22}{'сайтов':>8}{'из поиска':>11}{'доля':>7}"
          f"{'рег':>5}{'ФД':>4}{'рег на 1000 сайтов':>20}{'поисковых кликов':>18}")
    withconv = [(b, v) for b, v in br.items() if v[4] or v[5]]
    for b, v in sorted(withconv, key=lambda kv: (-kv[1][4], -kv[1][5])):
        print(f'{b[:21]:<22}{v[0]:>8}{v[2]:>11}{100.0*v[2]/v[0]:>6.1f}%'
              f'{v[4]:>5}{v[5]:>4}{1000.0*v[4]/v[0]:>20.2f}{v[6]:>18}')
    zero = [b for b, v in br.items() if not v[4] and not v[5]]
    print(f'\nбрендов без единой регистрации: {len(zero)} из {len(br)}')
    zero_clicks = sum(br[b][6] for b in zero)
    print(f'  на них пришлось {zero_clicks} поисковых кликов '
          f'({100.0*zero_clicks/sum(v[6] for v in br.values()):.1f}% всех)')
    print(f'  примеры: {", ".join(sorted(zero)[:10])}')

    print('\nБРЕНД × ЗОНА — регистраций на 1000 сайтов (только пары с 1000+ сайтов)')
    zs2 = [z for z, s in byz.items() if len(s) >= 10000]
    print(f"{'бренд':<22}" + ''.join(f'{str(z):>14}' for z in zs2) + f"{'всего рег':>11}")
    for b, v in sorted(withconv, key=lambda kv: -kv[1][4])[:25]:
        line = f'{b[:21]:<22}'
        for z in zs2:
            sel = [r for r in closed if r['brand'] == b and r['tld'] == z]
            if len(sel) < 100:
                line += f'{"—":>14}'
            else:
                line += f'{1000.0*sum(r["reg"] for r in sel)/len(sel):>14.1f}'
        line += f'{v[4]:>11}'
        print(line)

    h('БЛОК 3 · АККАУНТЫ ВЕБМАСТЕРА: СВЕЖЕСТЬ')
    purge = {}
    for line in open(events, encoding='utf-8'):
        e = json.loads(line)
        if e.get('event') != 'hosts_purge':
            continue
        purge.setdefault(e['content_domain_id'],
                         'чистился' if 'Удалено' in (e.get('detail') or '')
                         else 'первый раз')
    use = collections.defaultdict(set)
    for r in closed:
        if r['ya_acc'] is not None and r['base']:
            use[r['ya_acc']].add(r['base'])
    order = {}
    day_of = {}
    for r in closed:
        if r['base'] and r['day']:
            day_of.setdefault(r['base'], r['day'])
            if r['day'] < day_of[r['base']]:
                day_of[r['base']] = r['day']
    for a, bs in use.items():
        for i, b in enumerate(sorted(bs, key=lambda b: day_of.get(b, ''))):
            order[b] = i + 1

    g = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
    for r in closed:
        b = r['base']
        k1 = purge.get(r['cd_id'])
        k2 = order.get(b)
        if k1 is None and k2 is None:
            continue
        key = (k1 or 'неизвестно',
               'первая база' if k2 == 1 else f'{k2}-я база' if k2 else '?')
        t = g[key]
        t[0] += 1; t[1] += 1 if r['ya'] else 0
        t[2] += r['reg']; t[3] += r['fd']; t[4] += 1 if r['reg'] else 0
    print('свежесть по журналу (что нашла зачистка при постановке)')
    print('  × которая по счёту база на этом аккаунте в нашем реестре\n')
    print(f"{'аккаунт':<14}{'порядок':<14}{'сайтов':>9}{'из поиска':>11}"
          f"{'рег':>6}{'ФД':>5}{'рег на 1000 сайтов':>20}")
    for k, t in sorted(g.items(), key=lambda kv: -kv[1][0]):
        if t[0] < 1000:
            continue
        print(f'{k[0]:<14}{k[1]:<14}{t[0]:>9}{t[1]:>11}{t[2]:>6}{t[3]:>5}'
              f'{1000.0*t[2]/t[0]:>20.2f}')

    h('БЛОК 4 · КОНТЕНТ И ЗОНА ПОРОЗНЬ')
    pairs = collections.defaultdict(lambda: collections.Counter())
    for r in closed:
        if r['content'] and r['tld']:
            pairs[r['content']][r['tld']] += 1
    multi = {c: z for c, z in pairs.items()
             if sum(1 for v in z.values() if v >= 400) >= 2}
    print(f'паков, стоявших хотя бы на двух зонах: {len(multi)} из {len(pairs)}')
    print('только на них можно отделить зону от контента\n')
    print(f"{'пак':<40}{'зона':<10}{'сайтов':>8}{'из поиска':>11}{'рег':>5}{'ФД':>4}")
    shown = 0
    for c, zc in sorted(multi.items(), key=lambda kv: -sum(kv[1].values())):
        if shown >= 10:
            break
        shown += 1
        for z, n in sorted(zc.items(), key=lambda kv: -kv[1]):
            if n < 400:
                continue
            sel = [r for r in closed if r['content'] == c and r['tld'] == z]
            print(f'{c[:39]:<40}{str(z):<10}{len(sel):>8}'
                  f'{sum(1 for r in sel if r["ya"]):>11}'
                  f'{sum(r["reg"] for r in sel):>5}{sum(r["fd"] for r in sel):>4}')
    print('\nсводно по парам «один пак, две зоны»: регистраций на 1000 сайтов')
    agg = collections.defaultdict(lambda: [0, 0])
    for c, zc in multi.items():
        for z, n in zc.items():
            if n < 400:
                continue
            sel = [r for r in closed if r['content'] == c and r['tld'] == z]
            a = agg[z]
            a[0] += len(sel); a[1] += sum(r['reg'] for r in sel)
    for z, a in sorted(agg.items(), key=lambda kv: -kv[1][0]):
        print(f'  {str(z):<10}{a[0]:>8} сайтов{a[1]:>5} рег'
              f'{1000.0*a[1]/a[0]:>10.2f} на 1000')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2].split(','), sys.argv[3])
