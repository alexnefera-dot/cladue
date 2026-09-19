#!/usr/bin/env python3
"""Размер базы и аккаунт Cloudflare — два последних непосчитанных фактора.

**Размер базы** интересен не сам по себе. Если 206 брендов на одном домене
конкурируют между собой, у базы с меньшим числом сабдоменов отдача **на
сабдомен** должна быть выше. Это самая дешёвая проверка самоконкуренции из
возможных: она не требует ни запуска, ни съёма выдачи.

**Аккаунт Cloudflare** ни разу не рассматривался: смотрели только яндексовый.
Сначала надо выяснить, не идут ли они один в один — тогда это одна переменная,
а не две.

Сабдомены с незакрытым окном отброшены: у базы, которая ещё разворачивается,
маленький размер означает «не доделана», а не «маленькая».

    python3 razmer_i_cf.py <панель.jsonl> <subdomains.jsonl>[,…]
"""
import sys, json, collections, statistics

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from or_mh import mh


def h(t):
    print('\n' + '=' * 90)
    print(t)
    print('=' * 90)


def cut(rows, key, title, strata='day', min_n=500):
    vals = collections.Counter(r[key] for r in rows if r.get(key) is not None)
    print(f'\n{title}')
    print(f"{'значение':<22}{'сабдом.':>9}{'вышли':>8}{'доля':>8}{'OR к остальным':>24}")
    for v, n in sorted(vals.items(), key=lambda kv: str(kv[0])):
        if n < min_n:
            continue
        tbl = collections.defaultdict(lambda: [0, 0, 0, 0])
        hit = 0
        for r in rows:
            c = tbl[r[strata]]
            y = r['y']
            if r.get(key) == v:
                c[0] += y; c[2] += 1 - y; hit += y
            else:
                c[1] += y; c[3] += 1 - y
        orv, lo, hi, p = mh([tuple(x) for x in tbl.values()])
        print(f'{str(v):<22}{n:>9}{hit:>8}{100.0*hit/n:>7.1f}%'
              f'{(f"{orv:.2f} [{lo:.2f}-{hi:.2f}]" if orv else "—"):>24}')


def main(panel, subs_paths):
    reg = {}
    for p in subs_paths:
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            reg[r['subdomain'].lower()] = r

    rows = []
    base_size = collections.Counter()
    base_day = {}
    base_cf = {}
    base_ya = {}
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        if not r.get('window_closed'):
            continue
        b = r.get('content_domain_url')
        d = (r.get('recrawl_sent_at') or '')[:10]
        if not b or not d:
            continue
        base_size[b] += 1
        base_day.setdefault(b, d)
        s = reg.get(r['subdomain'], {})
        if s.get('cf_account_id') is not None:
            base_cf[b] = s['cf_account_id']
        if s.get('ya_account_id') is not None:
            base_ya[b] = s['ya_account_id']
        rows.append({'base': b, 'day': d, 'y': 1 if r.get('ya_clicks') else 0,
                     'clicks': r.get('ya_clicks') or 0,
                     'cv': r.get('reg', 0) + r.get('fd', 0),
                     'stage': r.get('yandex_pipeline_stage')})

    for r in rows:
        n = base_size[r['base']]
        r['size'] = ('до 100' if n < 100 else '100–159' if n < 160 else
                     '160–199' if n < 200 else '200–206' if n <= 206 else 'больше 206')

    h('1 · РАЗМЕР БАЗЫ')
    sizes = sorted(base_size.values())
    print(f'баз с закрытым окном: {len(base_size)}')
    print(f'  сабдоменов на базу: медиана {statistics.median(sizes):.0f}, '
          f'минимум {min(sizes)}, максимум {max(sizes)}')
    dist = collections.Counter()
    for n in sizes:
        dist['206' if n == 206 else 'меньше 206' if n < 206 else 'больше 206'] += 1
    print(f'  ровно 206: {dist["206"]}, меньше: {dist["меньше 206"]}, '
          f'больше: {dist["больше 206"]}')

    small = [b for b, n in base_size.items() if n < 200]
    if small:
        st = collections.Counter(r['stage'] for r in rows if r['base'] in small)
        print(f'\n  у неполных баз стадия пайплайна: {dict(st.most_common(3))}')

    cut(rows, 'size', 'ОТДАЧА НА САБДОМЕН ПО РАЗМЕРУ БАЗЫ (страта — день)')

    print('\n  проверка самоконкуренции: растут ли клики базы пропорционально размеру')
    byb = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        c = byb[r['base']]
        c[0] += r['clicks']; c[1] += 1
    bands = collections.defaultdict(lambda: [0, 0, 0])
    for b, c in byb.items():
        n = c[1]
        k = ('до 100' if n < 100 else '100–159' if n < 160 else
             '160–199' if n < 200 else '200–206')
        z = bands[k]
        z[0] += 1; z[1] += c[0]; z[2] += n
    print(f"{'размер':<14}{'баз':>6}{'кликов на базу':>17}{'кликов на сабдомен':>21}")
    for k in ('до 100', '100–159', '160–199', '200–206'):
        z = bands[k]
        if z[0] < 5:
            continue
        print(f'{k:<14}{z[0]:>6}{z[1]/z[0]:>17.0f}{z[1]/z[2]:>21.1f}')

    h('2 · АККАУНТ CLOUDFLARE')
    common = [b for b in base_cf if b in base_ya]
    pairs = {(base_cf[b], base_ya[b]) for b in common}
    print(f'баз с обоими аккаунтами: {len(common)}')
    print(f'  различных аккаунтов CF: {len(set(base_cf.values()))}, '
          f'яндекса: {len(set(base_ya.values()))}')
    print(f'  различных пар (CF, яндекс): {len(pairs)}')
    cf_many = collections.Counter(base_cf[b] for b in common)
    ya_per_cf = collections.defaultdict(set)
    for b in common:
        ya_per_cf[base_cf[b]].add(base_ya[b])
    multi = sum(1 for v in ya_per_cf.values() if len(v) > 1)
    print(f'  аккаунтов CF, работавших больше чем с одним яндексовым: {multi}')
    print(f'  баз на аккаунт CF: медиана '
          f'{statistics.median(cf_many.values()):.0f}, максимум {max(cf_many.values())}')

    order = collections.defaultdict(list)
    for b in common:
        order[base_cf[b]].append((base_day[b], b))
    seq = {}
    for a, lst in order.items():
        for i, (d, b) in enumerate(sorted(lst)):
            seq[b] = i + 1
    for r in rows:
        s = seq.get(r['base'])
        r['cf_seq'] = None if s is None else ('1-я база аккаунта' if s == 1 else
                                              '2-я' if s == 2 else '3-я и дальше')
    cut(rows, 'cf_seq', 'КОТОРАЯ ПО СЧЁТУ БАЗА НА АККАУНТЕ CLOUDFLARE (страта — день)')

    load = collections.Counter()
    for b in common:
        load[(base_cf[b], base_day[b])] += 1
    print(f'\n  баз на один аккаунт CF в сутки: '
          f'{dict(collections.Counter(load.values()).most_common(5))}')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2].split(','))
