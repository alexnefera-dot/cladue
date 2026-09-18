#!/usr/bin/env python3
"""Аккаунт Вебмастера с историей против пустого: отдача и конверсии.

Все поля про возраст аккаунта (`ya_account_age_days_at_start`, `ya_prior_launches`,
`ya_hosts_before`, `hours_since_ya_last_used`) API отдаёт пустыми. Единственный
уцелевший признак истории — событие `hosts_purge` при постановке базы:
«Удалено 166 из 166» означает, что аккаунт уже был занят, «На аккаунте не было
хостов» — что он чистый.

Единица — база. Окно — 7 суток от переобхода, досмотренное до конца. Страта —
день переобхода: пустые аккаунты раздавались не равномерно по календарю, а
возраст базы и день запуска — главные конфаундеры.

    python3 akkaunty.py <снимок.jsonl> <события.jsonl> <карта.jsonl>
                        <конверсии.jsonl> <клики-конверсий.jsonl> <конец YYYY-MM-DD>
"""
import sys, json, math, collections, statistics
from datetime import date, timedelta
from statistics import NormalDist

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from or_mh import mh

WINDOW = 6
N = NormalDist()


def rate_ratio(k1, n1, k2, n2):
    """Отношение частот с 95% ДИ: пуассоновская модель, лог-нормальное приближение.

    Годится для редких событий — конверсий. Для кликов не годится: они
    переразбросаны на порядок (одна база даёт тысячи, соседняя ноль), и
    пуассоновский интервал вышел бы обманчиво узким. Клики сравниваются рангами.
    """
    if not k1 or not k2:
        return None, None, None
    rr = (k1 / n1) / (k2 / n2)
    se = math.sqrt(1 / k1 + 1 / k2)
    return rr, rr * math.exp(-1.96 * se), rr * math.exp(1.96 * se)


def mannwhitney(x, y):
    """U-критерий с нормальным приближением и поправкой на связки.

    Возвращает вероятность того, что случайная база из x даст больше, чем из y,
    и двустороннее p. Медианы сравнивать честнее, чем средние: распределение
    кликов на базу — с длинным хвостом.
    """
    z = sorted([(v, 0) for v in x] + [(v, 1) for v in y])
    ranks = {}
    i = 0
    rsum = 0.0
    ties = 0.0
    while i < len(z):
        j = i
        while j + 1 < len(z) and z[j + 1][0] == z[i][0]:
            j += 1
        r = (i + j) / 2 + 1
        t = j - i + 1
        ties += t ** 3 - t
        for k in range(i, j + 1):
            if z[k][1] == 0:
                rsum += r
        i = j + 1
    n1, n2 = len(x), len(y)
    u = rsum - n1 * (n1 + 1) / 2
    n = n1 + n2
    mu = n1 * n2 / 2
    var = n1 * n2 / 12 * ((n + 1) - ties / (n * (n - 1))) if n > 1 else 0
    if var <= 0:
        return u / (n1 * n2), 1.0
    zval = (u - mu) / math.sqrt(var)
    return u / (n1 * n2), 2 * (1 - N.cdf(abs(zval)))


def main(snap_path, ev_path, map_path, conv_path, convclicks_path, obs_to):
    end = date.fromisoformat(obs_to)
    snap = {}
    for line in open(snap_path, encoding='utf-8'):
        r = json.loads(line)
        snap[r['base']] = r

    url = {}
    for line in open(map_path, encoding='utf-8'):
        sub, b, cd, brand, rec, st, pg, tld, stage = json.loads(line)
        if cd is not None and b:
            url[cd] = b

    kind = {}
    for line in open(ev_path, encoding='utf-8'):
        r = json.loads(line)
        if r.get('event') != 'hosts_purge':
            continue
        b = url.get(r['content_domain_id'])
        if not b:
            continue
        kind.setdefault(b, 'с историей' if 'Удалено' in (r.get('detail') or '') else 'пустой')

    click = {}
    for line in open(convclicks_path, encoding='utf-8'):
        r = json.loads(line)
        click[r['clickid']] = r
    conv, fd = collections.Counter(), collections.Counter()
    for line in open(conv_path, encoding='utf-8'):
        c = json.loads(line)
        k = click.get(c['clickid'])
        if not k:
            continue
        s = (k.get('subdomain') or '').lower()
        if s.count('.') < 2:
            continue
        b = '.'.join(s.split('.')[-2:])
        conv[b] += 1
        if c.get('event') != 'reg':
            fd[b] += 1

    rows = []
    for b, k in kind.items():
        r = snap.get(b)
        if not r or not r.get('recrawl'):
            continue
        d = date.fromisoformat(r['recrawl'])
        if (end - d).days < WINDOW + 1:
            continue                       # окно не досмотрено
        ya = sum(v[1] for day, v in r['days'].items()
                 if 0 <= (date.fromisoformat(day) - d).days <= WINDOW)
        rows.append({'base': b, 'kind': k, 'day': d, 'ya': ya,
                     'conv': conv[b], 'fd': fd[b], 'subs': r.get('subs') or 0})

    print(f'баз с известным типом аккаунта и досмотренным окном: {len(rows)}')
    print(collections.Counter(r['kind'] for r in rows))

    print()
    print('=' * 74)
    print('ПО ДНЯМ ПЕРЕОБХОДА — только те дни, где есть обе группы')
    print(f"{'день':<12} {'пустых':>7} {'поиск/базу':>11} {'конв':>5} | "
          f"{'с историей':>11} {'поиск/базу':>11} {'конв':>5}")
    byday = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        byday[r['day']][r['kind']].append(r)
    both = []
    for d in sorted(byday):
        a, b = byday[d].get('пустой', []), byday[d].get('с историей', [])
        if not a or not b:
            continue
        both.append(d)
        print(f'{d.isoformat():<12} {len(a):>7} {sum(x["ya"] for x in a)/len(a):>11.0f} '
              f'{sum(x["conv"] for x in a):>5} | {len(b):>11} '
              f'{sum(x["ya"] for x in b)/len(b):>11.0f} {sum(x["conv"] for x in b):>5}')

    sel = [r for r in rows if r['day'] in both]
    print(f'\nв сравнении остаётся {len(sel)} баз за {len(both)} дней, '
          f'где обе группы раздавались в один день')

    print()
    print('=' * 74)
    print('ИТОГ ПО СРАВНИМЫМ ДНЯМ')
    print(f"{'аккаунт':<12} {'баз':>5} {'поиск/базу':>11} {'медиана':>9} "
          f"{'конверсий':>10} {'на 100 баз':>11} {'ФД':>4} {'ФД на 100':>10}")
    agg = {}
    for k in ('пустой', 'с историей'):
        v = [r for r in sel if r['kind'] == k]
        if not v:
            continue
        agg[k] = v
        print(f'{k:<12} {len(v):>5} {sum(x["ya"] for x in v)/len(v):>11.0f} '
              f'{statistics.median(x["ya"] for x in v):>9.0f} '
              f'{sum(x["conv"] for x in v):>10} {100.0*sum(x["conv"] for x in v)/len(v):>11.1f} '
              f'{sum(x["fd"] for x in v):>4} {100.0*sum(x["fd"] for x in v)/len(v):>10.1f}')

    if len(agg) == 2:
        a, b = agg['с историей'], agg['пустой']
        for name, key in (('конверсии', 'conv'), ('ФД', 'fd')):
            rr, lo, hi = rate_ratio(sum(x[key] for x in a), len(a),
                                    sum(x[key] for x in b), len(b))
            if rr:
                print(f'\n  {name}: аккаунт с историей даёт в {rr:.2f} раза больше '
                      f'(95% ДИ {lo:.2f}–{hi:.2f})')
            else:
                print(f'\n  {name}: в одной из групп ноль, отношение не считается '
                      f'({sum(x[key] for x in a)} против {sum(x[key] for x in b)})')

        p_gt, pv = mannwhitney([x['ya'] for x in a], [x['ya'] for x in b])
        print(f'\n  поисковые клики: база на аккаунте с историей обгоняет базу на пустом '
              f'в {100*p_gt:.0f}% пар (U-критерий, p = {pv:.3f})')

        # доля баз, у которых есть хоть одна конверсия — МН со стратой по дню
        tbl = []
        for d in both:
            g = byday[d]
            a_ = sum(1 for x in g.get('с историей', []) if x['conv'])
            b_ = len(g.get('с историей', [])) - a_
            c_ = sum(1 for x in g.get('пустой', []) if x['conv'])
            d_ = len(g.get('пустой', [])) - c_
            tbl.append((a_, c_, b_, d_))
        orv, lo, hi, p = mh(tbl)
        if orv:
            print(f'\n  доля баз с конверсией, OR по Мантелю-Хенцелю со стратой по дню: '
                  f'{orv:.2f} (95% ДИ {lo:.2f}–{hi:.2f}, p = {p:.4f})')

    print()
    print('=' * 74)
    print('ОГОВОРКИ')
    print('· «Пустой» означает только, что зачистке нечего было удалять. Аккаунт мог')
    print('  быть новым, а мог быть старым и уже вычищенным — различить нечем.')
    print('· Сравнение наблюдательное: кому достаётся пустой аккаунт, решает раздача,')
    print('  а не жребий. Страта по дню снимает календарь, но не порядок раздачи.')
    print('· Конверсий мало, доверительные интервалы широкие — это направление, а не')
    print('  точная величина.')


if __name__ == '__main__':
    if len(sys.argv) < 7:
        raise SystemExit(__doc__)
    main(*sys.argv[1:7])
