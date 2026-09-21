#!/usr/bin/env python3
"""Полный прогон по месяцам: август, сентябрь, затем вся сеть.

Один проход по панели, дальше все разрезы считаются на одном и том же наборе
строк — чтобы август и сентябрь нельзя было случайно посчитать разными
способами.

Две метрики, и они отвечают на разные вопросы:

* **выход в поиск за K суток** — доля сайтов, получивших первый поисковый клик
  в первые K суток после переобхода. Окно фиксировано, и в расчёт идут только
  дни, у которых эти сутки успели пройти до конца данных. Это про видимость.
* **регистраций на десять тысяч поисковых кликов** — это про деньги. Конверсия
  приходит позже клика, поэтому у последних трёх-четырёх дней она недосчитана
  по построению; такие дни помечены.

Везде, где сравниваются уровни фактора, показаны два числа: отношение к ставке
дня и отношение к ставке «пак + день». Если эффект держится в первом и исчезает
во втором — это была тень контента, а не сам фактор.

    python3 svodka_mesyacy.py <панель.jsonl> <клики-по-сабдоменам.jsonl>
                              <свежие-клики.jsonl> <последний-день-кликов>
"""
import sys, json, re, math, collections, datetime

K = 3
KF = 1          # короткое окно для самых свежих дней


def fam(name):
    return re.sub(r'[_\-]\d+$', '', name)


def dsub(day, k):
    return str(datetime.date.fromisoformat(day) - datetime.timedelta(days=k))


def between(a, b):
    return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days


def chi2_p(x, df):
    if x <= 0:
        return 1.0
    if df == 1:
        from statistics import NormalDist
        return 2 * (1 - NormalDist().cdf(math.sqrt(x)))
    if df == 2:
        return math.exp(-x / 2)
    return chi2_p(x, df - 2) + (x / 2) ** (df / 2 - 1) * math.exp(-x / 2) / math.gamma(df / 2)


def h1(t):
    print('\n\n' + '#' * 100 + '\n# ' + t + '\n' + '#' * 100)


def h2(t):
    print('\n' + '=' * 100 + '\n' + t + '\n' + '=' * 100)


def load(panel, subsclicks, fresh, last):
    yaf = {}
    for line in open(subsclicks, encoding='utf-8'):
        s, n, ya, f, l, yf, yl = json.loads(line)
        if yf:
            yaf[s] = yf[:10]
    rows, bd = [], collections.defaultdict(set)
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        b = r.get('content_domain_url')
        if not d or not b:
            continue
        bd[b].add(d)
        rows.append({
            'sub': r['subdomain'], 'base': b, 'day': d, 'tld': r.get('tld'),
            'pack': fam(r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН'),
            'brand': r.get('brand_label'), 'block': r.get('recrawl_block'),
            'night': r.get('is_night_kiev'), 'ya': r.get('ya_account_id'),
            'kw': r.get('keywords_len'), 'tpl': r.get('template'),
            'cl': r.get('ya_clicks') or 0, 'reg': r.get('reg', 0), 'fd': r.get('fd', 0),
        })
    for line in open(fresh, encoding='utf-8'):
        r = json.loads(line)
        s = (r.get('subdomain') or '').lower()
        hh = r.get('referer') or ''
        if not ('yandex' in hh or '//ya.ru' in hh):
            continue
        at = (r.get('at') or '')[:10]
        if at and (s not in yaf or at < yaf[s]):
            yaf[s] = at
    order = {b: {d: i for i, d in enumerate(sorted(ds))} for b, ds in bd.items()}
    for r in rows:
        f = yaf.get(r['sub'])
        lag = between(r['day'], f) if f else None
        r['lag'] = lag
        r['hit'] = 1 if (lag is not None and 0 <= lag <= K) else 0
        r['hit1'] = 1 if (lag is not None and 0 <= lag <= KF) else 0
        r['wave'] = min(order[r['base']][r['day']], 1)
        r['ok'] = r['day'] <= dsub(last, K)        # окно выхода досмотрено
        r['ok1'] = r['day'] <= dsub(last, KF)
    # сколько раз аккаунт взят в работу
    first = {b: min(ds) for b, ds in bd.items()}
    acc = collections.defaultdict(set)
    for r in rows:
        if r['ya'] is not None:
            acc[r['ya']].add(r['base'])
    seq = {}
    for a, bs in acc.items():
        for i, b in enumerate(sorted(bs, key=lambda x: (first[x], x))):
            seq[b] = i + 1
    for r in rows:
        r['seq'] = seq.get(r['base'])
    return rows


def reach(rs):
    e = [r for r in rs if r['ok']]
    return (sum(r['hit'] for r in e), len(e))


def money(rs):
    cl = sum(r['cl'] for r in rs)
    return sum(r['reg'] for r in rs), sum(r['fd'] for r in rs), cl


def strat(rs, level, stratum, title, minn=1000, minstrat=60, money_too=True):
    """Уровни фактора: доля выхода в поиск и отношение к ставке страты."""
    e = [r for r in rs if r['ok']]
    sp = collections.defaultdict(lambda: [0, 0])
    for r in e:
        k = stratum(r)
        if k is None:
            continue
        t = sp[k]
        t[0] += r['hit']
        t[1] += 1
    g = collections.defaultdict(lambda: [0, 0, 0.0, 0, 0, 0, set()])
    for r in e:
        k, v = stratum(r), level(r)
        if k is None or v is None:
            continue
        hh, nn = sp[k]
        if nn < minstrat:
            continue
        t = g[v]
        t[0] += r['hit']
        t[1] += 1
        t[2] += hh / nn
        t[3] += r['reg']
        t[4] += r['fd']
        t[5] += r['cl']
        t[6].add(r['base'])
    o = [(v, t) for v, t in g.items() if t[1] >= minn]
    o.sort(key=lambda x: -(x[1][0] / x[1][2] if x[1][2] else 0))
    print('\n' + title)
    if len(o) < 2:
        print('  уровней с достаточным объёмом нет')
        return
    print('  %-26s %5s %8s %8s %8s %7s %6s %4s %8s'
          % ('уровень', 'баз', 'сайтов', 'выход3', 'к страте', 'кликов', 'рег', 'ФД', 'рег/10т'))
    for v, t in o:
        print('  %-26s %5d %8d %7.1f%% %8.2f %7d %6d %4d %8s'
              % (str(v)[:26], len(t[6]), t[1], 100 * t[0] / t[1],
                 t[0] / t[2] if t[2] else 0, t[5], t[3], t[4],
                 '%.1f' % (10000 * t[3] / t[5]) if t[5] else '—'))


def obzor(rs, name, last):
    h2(name)
    n = len(rs)
    b = len({r['base'] for r in rs})
    hh, nn = reach(rs)
    reg, fd, cl = money(rs)
    print('баз %d, сайтов %d, поисковых кликов %d' % (b, n, cl))
    print('выход в поиск за 3 суток: %.1f%% (досмотрено %d сайтов из %d)'
          % (100 * hh / nn if nn else 0, nn, n))
    print('регистраций %d, ФД %d; на десять тысяч кликов %.1f рег, %.1f ФД'
          % (reg, fd, 10000 * reg / cl if cl else 0, 10000 * fd / cl if cl else 0))
    print('кликов на регистрацию %s' % ('%d' % (cl // reg) if reg else '—'))
    print('\nпо дням')
    print('день        баз  сайтов   выход3   кликов   рег  ФД  рег/10т')
    byday = collections.defaultdict(list)
    for r in rs:
        byday[r['day']].append(r)
    for d in sorted(byday):
        v = byday[d]
        hh, nn = reach(v)
        reg, fd, cl = money(v)
        mark = ''
        if d > dsub(last, K):
            mark = '   окно выхода не закрыто'
        if d > dsub(last, 4):
            mark += '; конверсии недосчитаны'
        print('%s %4d %7d %8s %8d %5d %3d %8s%s'
              % (d, len({x['base'] for x in v}), len(v),
                 '%.1f%%' % (100 * hh / nn) if nn else '—',
                 cl, reg, fd, '%.1f' % (10000 * reg / cl) if cl else '—', mark))


def razrezy(rs, name, last):
    pd = lambda r: (r['pack'], r['day']) if r['pack'] != 'КОНТЕНТ НЕ ЗАПИСАН' else None
    h2(name + ' · ФАКТОРЫ: ДЕНЬ ПРОТИВ ПАКА+ДНЯ')
    for t, f in (('ЗОНА', lambda r: r['tld']),
                 ('ЧАС ПЕРЕОБХОДА', lambda r: r['block']),
                 ('НОЧЬ ПО КИЕВУ', lambda r: 'ночь' if r['night'] else 'день'),
                 ('ВОЛНА ПЕРЕОБХОДА', lambda r: 'первая' if r['wave'] == 0 else 'вторая'),
                 ('КОТОРЫЙ РАЗ АККАУНТ', lambda r: r['seq'] if r['seq'] and r['seq'] <= 3 else None),
                 ('СТРАНИЦ В САЙТЕ', lambda r: '12 страниц'
                  if re.search(r'12(page|str|стр)', r['pack'], re.I) else '7 страниц'
                  if re.search(r'7(page|str|стр)', r['pack'], re.I) else None),
                 ('ДЛИНА СПИСКА КЛЮЧЕЙ', lambda r: '<4k' if (r['kw'] or 0) < 4000
                  else '4-8k' if r['kw'] < 8000 else '8k+')):
        strat(rs, f, lambda r: r['day'], '  %s | страта: день' % t)
        strat(rs, f, pd, '  %s | страта: пак + день' % t)


def brendy(rs, name):
    h2(name + ' · БРЕНДЫ')
    e = [r for r in rs if r['ok']]
    g = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
    for r in e:
        t = g[r['brand']]
        t[0] += r['hit']
        t[1] += 1
        t[2] += r['cl']
        t[3] += r['reg']
        t[4] += r['fd']
    o = sorted(g.items(), key=lambda x: -(x[1][0] / x[1][1] if x[1][1] else 0))
    print('брендов %d' % len(o))
    print('\nлучшие по выходу в поиск')
    print('  %-22s %8s %8s %9s %5s %4s %9s' % ('бренд', 'сайтов', 'выход3', 'кликов', 'рег', 'ФД', 'кл/рег'))
    for b, t in o[:12]:
        print('  %-22s %8d %7.1f%% %9d %5d %4d %9s'
              % (str(b)[:22], t[1], 100 * t[0] / t[1], t[2], t[3], t[4],
                 '%d' % (t[2] // t[3]) if t[3] else '—'))
    print('\nхудшие по выходу в поиск')
    for b, t in o[-8:]:
        print('  %-22s %8d %7.1f%% %9d %5d %4d %9s'
              % (str(b)[:22], t[1], 100 * t[0] / t[1], t[2], t[3], t[4],
                 '%d' % (t[2] // t[3]) if t[3] else '—'))
    m = sorted(g.items(), key=lambda x: -(10000 * x[1][3] / x[1][2] if x[1][2] else 0))
    print('\nлучшие по деньгам (от 3000 кликов)')
    print('  %-22s %9s %5s %4s %9s %9s' % ('бренд', 'кликов', 'рег', 'ФД', 'кл/рег', 'выход3'))
    for b, t in [x for x in m if x[1][2] >= 3000][:12]:
        print('  %-22s %9d %5d %4d %9d %8.1f%%'
              % (str(b)[:22], t[2], t[3], t[4], t[2] // t[3], 100 * t[0] / t[1]))
    zero = [(b, t) for b, t in g.items() if t[3] == 0]
    print('\nбрендов без единой регистрации: %d, на них кликов %d'
          % (len(zero), sum(t[2] for _, t in zero)))
    for b, t in sorted(zero, key=lambda x: -x[1][2])[:10]:
        print('  %-22s кликов %8d, выход %.1f%%' % (str(b)[:22], t[2], 100 * t[0] / t[1]))


def paki(rs, name, minsites=1000):
    h2(name + ' · КОНТЕНТЫ')
    e = [r for r in rs if r['ok']]
    g = collections.defaultdict(lambda: [0, 0, 0, 0, 0, set(), set()])
    for r in e:
        t = g[r['pack']]
        t[0] += r['hit']
        t[1] += 1
        t[2] += r['cl']
        t[3] += r['reg']
        t[4] += r['fd']
        t[5].add(r['base'])
        t[6].add(r['day'])
    o = sorted(g.items(), key=lambda x: -(x[1][0] / x[1][1] if x[1][1] else 0))
    big = [(p, t) for p, t in o if t[1] >= minsites]
    print('паков %d, из них от %d сайтов — %d' % (len(o), minsites, len(big)))
    print('  %-42s %5s %8s %8s %9s %5s %4s %8s'
          % ('пак', 'баз', 'сайтов', 'выход3', 'кликов', 'рег', 'ФД', 'рег/10т'))
    for p, t in big:
        print('  %-42s %5d %8d %7.1f%% %9d %5d %4d %8s'
              % (str(p)[:42], len(t[5]), t[1], 100 * t[0] / t[1], t[2], t[3], t[4],
                 '%.1f' % (10000 * t[3] / t[2]) if t[2] else '—'))
    # перестановочная проверка: управляет ли пак выходом в поиск
    dayrate = collections.defaultdict(lambda: [0, 0])
    for r in e:
        t = dayrate[r['day']]
        t[0] += r['hit']
        t[1] += 1
    import random
    def stat(labels):
        gg = collections.defaultdict(lambda: [0, 0.0])
        for r, lb in zip(e, labels):
            hh, nn = dayrate[r['day']]
            t = gg[lb]
            t[0] += r['hit']
            t[1] += hh / nn if nn else 0
        return sum((k - x) ** 2 / x for k, x in gg.values() if x >= 5)
    obs = stat([r['pack'] for r in e])
    byday = collections.defaultdict(list)
    for i, r in enumerate(e):
        byday[r['day']].append(i)
    random.seed(3)
    mx = 0
    for _ in range(60):
        lab = [None] * len(e)
        for d, idx in byday.items():
            src = [e[i]['pack'] for i in idx]
            random.shuffle(src)
            for i, s in zip(idx, src):
                lab[i] = s
        mx = max(mx, stat(lab))
    print('\nуправляет ли пак выходом в поиск: хи-квадрат %.0f, '
          'максимум за 60 перестановок ярлыка внутри дня %.0f' % (obs, mx))


def domeny(rs, name):
    h2(name + ' · ДОМЕНЫ ВНУТРИ ПУЛОВ')
    e = [r for r in rs if r['ok']]
    pool = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for r in e:
        if r['pack'] == 'КОНТЕНТ НЕ ЗАПИСАН':
            continue
        t = pool[(r['pack'], r['day'])][r['base']]
        t[0] += r['hit']
        t[1] += 1
    tot = sig = 0
    worst = []
    for (p, d), doms in pool.items():
        if len(doms) < 5:
            continue
        v = list(doms.values())
        tn = sum(x[1] for x in v)
        tk = sum(x[0] for x in v)
        if tn < 500 or tk < 5:
            continue
        q = tk / tn
        x = sum((k - n * q) ** 2 / (n * q * (1 - q)) for k, n in v if n)
        tot += 1
        pv = chi2_p(x, len(v) - 1)
        sig += pv < 0.05
        worst.append((p, d, len(v), tn, 100 * q,
                      min(100 * k / n for k, n in v), max(100 * k / n for k, n in v), pv))
    print('пулов «пак + день» по 5+ баз: %d, разброс между доменами значим в %d' % (tot, sig))
    worst.sort(key=lambda t: -(t[6] - t[5]))
    print('\nгде разрыв между лучшим и худшим доменом больше всего')
    print('  %-38s %-11s %4s %7s %7s %16s' % ('пак', 'день', 'баз', 'сайтов', 'выход3', 'разброс'))
    for t in worst[:14]:
        print('  %-38s %-11s %4d %7d %6.1f%% %6.1f%% - %6.1f%%'
              % (t[0][:38], t[1], t[2], t[3], t[4], t[5], t[6]))
    # повторяемость: первая волна против второй
    g = collections.defaultdict(lambda: [[0, 0], [0, 0]])
    for r in e:
        t = g[r['base']][r['wave']]
        t[0] += r['hit']
        t[1] += 1
    use = [(a[0][0] / a[0][1], a[1][0] / a[1][1])
           for a in g.values() if a[0][1] >= 100 and a[1][1] >= 30]
    if len(use) > 30:
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
        a = [x[0] for x in use]
        b = [x[1] for x in use]
        ra, rb = rk(a), rk(b)
        n = len(a)
        ma, mb = sum(ra) / n, sum(rb) / n
        num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
        den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((x - mb) ** 2 for x in rb))
        use.sort(key=lambda x: -x[0])
        k = len(use) // 4
        print('\nповторяемость домена: доменов %d, ранговая связь волн %.2f' % (n, num / den))
        print('  верхняя четверть по первой волне -> вторая волна %.1f%%'
              % (100 * sum(x[1] for x in use[:k]) / k))
        print('  нижняя четверть по первой волне -> вторая волна %.1f%%'
              % (100 * sum(x[1] for x in use[-k:]) / k))


def main(panel, subsclicks, fresh, last):
    rows = load(panel, subsclicks, fresh, last)
    aug = [r for r in rows if r['day'][:7] == '2026-08']
    sep = [r for r in rows if r['day'][:7] == '2026-09']
    for rs, nm in ((aug, 'АВГУСТ'), (sep, 'СЕНТЯБРЬ'), (rows, 'ВСЯ СЕТЬ')):
        h1(nm)
        obzor(rs, nm + ' · ОБЗОР', last)
        razrezy(rs, nm, last)
        brendy(rs, nm)
        paki(rs, nm)
        domeny(rs, nm)


if __name__ == '__main__':
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
