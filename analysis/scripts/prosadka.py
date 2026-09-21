#!/usr/bin/env python3
"""Почему просели сентябрьские запуски: разброс внутри пачки, дни, причины.

Метрика — **выход в поиск за 3 суток**: доля сайтов, получивших первый
поисковый клик в течение трёх суток после переобхода. Момент первого
поискового клика берётся из потока кликов (`ya_first` в выгрузке сабдоменов),
а не из поля панели `days_to_first_click_after_recrawl`: то поле заполнено
лишь у 5% сайтов и по дням заполнено неровно, сравнивать по нему нельзя.

Окно фиксировано, и в расчёт идут только дни, у которых эти трое суток успели
пройти до конца данных. Иначе свежие дни проигрывают не по качеству, а по
недосмотренности. По регистрациям такой разбор не сделать: их 412 на всю сеть,
а выходов в поиск — 41 тысяча, и только на них хватает разрешения, чтобы
отделить один фактор от другого.

Главный приём — страты. Один и тот же фактор проверяется при разных стратах:
если эффект есть при страте «день» и исчезает при страте «пак+день», значит
это была тень пака, а не самостоятельная причина.

    python3 prosadka.py <панель.jsonl> <subdomains.jsonl>[,…] <база-аккаунт.json>
                        <клики-по-сабдоменам.jsonl> <события.jsonl или ->
"""
import sys, json, math, re, glob, datetime, collections

LAST = '2026-09-18'
K = 3


def dsub(day, k):
    y, m, d = map(int, day.split('-'))
    return str(datetime.date(y, m, d) - datetime.timedelta(days=k))


def days_between(a, b):
    return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days


def week(d):
    dt = datetime.date.fromisoformat(d)
    return str(dt - datetime.timedelta(days=dt.weekday()))


def fam(name):
    return re.sub(r'[_\-]\d+$', '', name)


def chi2_p(x, df):
    """Правый хвост хи-квадрат."""
    if x <= 0:
        return 1.0
    if df == 1:
        from statistics import NormalDist
        return 2 * (1 - NormalDist().cdf(math.sqrt(x)))
    if df == 2:
        return math.exp(-x / 2)
    return chi2_p(x, df - 2) + (x / 2) ** (df / 2 - 1) * math.exp(-x / 2) / math.gamma(df / 2)


def h(t):
    print('\n' + '=' * 96 + '\n' + t + '\n' + '=' * 96)


def load(panel, subs_paths, accpath, clickpath):
    api = {}
    for p in subs_paths:
        for line in open(p, encoding='utf-8'):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get('content_label'):
                api[r['subdomain'].lower()] = r['content_label']
    acc = json.load(open(accpath, encoding='utf-8'))
    yafirst = {}
    for line in open(clickpath, encoding='utf-8'):
        s, n, ya, f, l, yf, yl = json.loads(line)
        if yf:
            yafirst[s] = yf[:10]

    rows, cdid = [], {}
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        b = r.get('content_domain_url')
        if not d or not b:
            continue
        cdid[r.get('content_domain_id')] = b
        a = acc.get(b) or {}
        rows.append({
            'inst': api.get(r['subdomain']) or r.get('content') or 'БЕЗ ИМЕНИ',
            'brand': r.get('brand_label'), 'base': b, 'day': d, 'tld': r.get('tld'),
            'block': r.get('recrawl_block'), 'night': r.get('is_night_kiev'),
            'tpl': r.get('template'), 'cf': a.get('cf'), 'pat': r.get('base_name_pattern'),
            'kw': r.get('keywords_len'), 'yaf': yafirst.get(r['subdomain']),
            'cl': r.get('clicks_sum') or 0, 'reg': r.get('reg', 0), 'fd': r.get('fd', 0),
        })
    return rows, cdid


def prepare(rows):
    """Волна переобхода внутри базы и отметка выхода в поиск за K суток."""
    bd = collections.defaultdict(set)
    for r in rows:
        bd[r['base']].add(r['day'])
    order = {b: {d: i for i, d in enumerate(sorted(ds))} for b, ds in bd.items()}
    sel = [r for r in rows if r['day'] <= dsub(LAST, K)]
    for r in sel:
        r['hit'] = 1 if (r['yaf'] and 0 <= days_between(r['day'], r['yaf']) <= K) else 0
        r['wave'] = min(order[r['base']][r['day']], 1)
    return sel, order


def strat(rows, level, stratum, minn=1500, minstrat=100, title=''):
    """Доля выхода в поиск по уровням фактора, приведённая к ставке страты."""
    sp = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        s = stratum(r)
        if s is None:
            continue
        t = sp[s]
        t[0] += r['hit']
        t[1] += 1
    g = collections.defaultdict(lambda: [0, 0, 0.0])
    for r in rows:
        s, v = stratum(r), level(r)
        if s is None or v is None:
            continue
        hh, nn = sp[s]
        if nn < minstrat:
            continue
        t = g[v]
        t[0] += r['hit']
        t[1] += 1
        t[2] += hh / nn
    o = [(v, t[0], t[1], 100 * t[0] / t[1], t[0] / t[2] if t[2] else 0)
         for v, t in g.items() if t[1] >= minn]
    o.sort(key=lambda x: -x[4])
    print('\n' + title)
    if len(o) < 2:
        print('  уровней с достаточным объёмом нет')
        return
    print('  %-24s %8s %8s %8s %9s' % ('уровень', 'сайтов', 'выход3', 'доля', 'к страте'))
    for v, hh, nn, p, k in o:
        print('  %-24s %8d %8d %7.1f%% %9.2f' % (str(v)[:24], nn, hh, p, k))


def main(panel, subs_paths, accpath, clickpath, eventsglob):
    rows, cdid = load(panel, subs_paths, accpath, clickpath)
    E, order = prepare(rows)
    print('сайтов всего %d, баз %d; в расчёте выхода за %d суток — %d сайтов'
          % (len(rows), len({r['base'] for r in rows}), K, len(E)))

    h('1 · ЧТО ПРОИСХОДИЛО ПО ДНЯМ')
    byday = collections.defaultdict(list)
    for r in E:
        byday[r['day']].append(r)
    print('день        сайтов  баз  выход3   рег   рег на 10 тыс. кликов')
    for d in sorted(byday):
        rs = byday[d]
        hh = sum(r['hit'] for r in rs)
        cl = sum(r['cl'] for r in rs)
        g = sum(r['reg'] for r in rs)
        print('%s %7d %4d  %5.1f%% %5d %12s' % (
            d, len(rs), len({r['base'] for r in rs}), 100 * hh / len(rs), g,
            '%.1f' % (10000 * g / cl) if cl else '—'))

    h('2 · РАЗБРОС ВНУТРИ ПАЧКИ, ЗАПУЩЕННОЙ В ОДИН ДЕНЬ')
    print('Пачка — семейство генераций, ушедшее в переобход в один день.')
    print('Экземпляр внутри пачки — одна генерация, она же одна база.')
    print('Хи-квадрат проверяет, больше ли разброс между экземплярами, чем даёт случай.\n')
    batch = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for r in E:
        if r['inst'] == 'БЕЗ ИМЕНИ':
            continue
        t = batch[(fam(r['inst']), r['day'])][r['inst']]
        t[0] += r['hit']
        t[1] += 1
    print('%-38s %-11s %3s %6s %6s %13s %7s %4s %8s'
          % ('пачка', 'день', 'экз', 'сайтов', 'выход3', 'разброс', 'хи2', 'df', 'p'))
    nsig = ntot = 0
    for (f, d), inst in sorted(batch.items()):
        g = [tuple(v) for v in inst.values()]
        tn, tk = sum(x[1] for x in g), sum(x[0] for x in g)
        if len(g) < 5 or tn < 500 or tk < 5:
            continue
        p = tk / tn
        x = sum((k - n * p) ** 2 / (n * p * (1 - p)) for k, n in g if n)
        df = len(g) - 1
        pv = chi2_p(x, df)
        ntot += 1
        nsig += pv < 0.05
        print('%-38s %-11s %3d %6d %5.1f%% %6.1f%%-%5.1f%% %7.1f %4d %8.4f' % (
            f[:37], d, len(g), tn, 100 * p,
            min(100 * k / n for k, n in g if n), max(100 * k / n for k, n in g if n),
            x, df, pv))
    print('\nпачек проверено %d, разброс значимо больше случайного у %d' % (ntot, nsig))

    S = [r for r in E if r['inst'] != 'БЕЗ ИМЕНИ'
         and len(batch[(fam(r['inst']), r['day'])]) >= 5]
    print('\nЧем объясняется разброс внутри пачки (страта — сама пачка):')
    for name, f in (('час переобхода', lambda r: r['block']),
                    ('зона', lambda r: r['tld']),
                    ('длина списка ключей', lambda r: '<4k' if (r['kw'] or 0) < 4000
                     else '4-8k' if r['kw'] < 8000 else '8k+'),
                    ('паттерн имени базы', lambda r: r['pat'])):
        strat(S, f, lambda r: (fam(r['inst']), r['day']), minn=400, minstrat=50,
              title='  ' + name.upper())

    h('3 · ОДИН И ТОТ ЖЕ ПАК В РАЗНЫЕ ДНИ')
    print('Только первая волна базы: вторая волна — это другие бренды (см. блок 5).\n')
    g = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for r in E:
        if r['inst'] == 'БЕЗ ИМЕНИ' or r['wave']:
            continue
        t = g[fam(r['inst'])][r['day']]
        t[0] += r['hit']
        t[1] += 1
    dd = collections.defaultdict(lambda: [0, 0.0])
    for f in sorted(g):
        ds = {d: v for d, v in g[f].items() if v[1] >= 400}
        tk = sum(v[0] for v in ds.values())
        tn = sum(v[1] for v in ds.values())
        if len(ds) < 2 or tk < 20:
            continue
        p = tk / tn
        print('%-42s %6d сайтов, выход3 %.1f%%' % (f[:41], tn, 100 * p))
        for d in sorted(ds):
            k, n = ds[d]
            print('    %s  сайтов %6d  выход3 %5.1f%%  к паку %.2f'
                  % (d, n, 100 * k / n, (k / n) / p))
            t = dd[d]
            t[0] += n
            t[1] += (k / n) / p * n
    print('\nдень относительно своих паков, первая волна:')
    for d in sorted(dd):
        n, s = dd[d]
        print('  %s сайтов %6d  %.2f' % (d, n, s / n))

    h('4 · ФАКТОРЫ: ДЕНЬ ПРОТИВ ПАКА+ДНЯ')
    print('Если эффект держится при страте «день», но исчезает при «пак+день»,')
    print('это был не фактор, а тень того, какой контент в этот час отправляли.')
    pd = lambda r: (fam(r['inst']), r['day']) if r['inst'] != 'БЕЗ ИМЕНИ' else None
    for name, f in (('ЧАС ПЕРЕОБХОДА', lambda r: r['block']),
                    ('ЗОНА', lambda r: r['tld']),
                    ('НОЧЬ ПО КИЕВУ', lambda r: 'ночь' if r['night'] else 'день'),
                    ('ШАБЛОН', lambda r: r['tpl']),
                    ('ДЛИНА СПИСКА КЛЮЧЕЙ', lambda r: '<4k' if (r['kw'] or 0) < 4000
                     else '4-8k' if r['kw'] < 8000 else '8k+')):
        strat(E, f, lambda r: r['day'], title=name + ' | страта: день')
        strat(E, f, pd, title=name + ' | страта: пак + день')

    if eventsglob != '-':
        purge = {}
        for p in glob.glob(eventsglob):
            for line in open(p, encoding='utf-8'):
                e = json.loads(line)
                if e.get('event') != 'hosts_purge':
                    continue
                b = cdid.get(e.get('content_domain_id'))
                if b:
                    purge.setdefault(b, 'уже использовался'
                                     if 'Удалено' in (e.get('detail') or '') else 'первый раз')
        for r in E:
            r['acc'] = purge.get(r['base'])
        strat(E, lambda r: r.get('acc'), lambda r: r['day'],
              title='СВЕЖЕСТЬ АККАУНТА | страта: день')
        strat(E, lambda r: r.get('acc'), pd,
              title='СВЕЖЕСТЬ АККАУНТА | страта: пак + день')

    h('5 · ВОЛНА ПЕРЕОБХОДА И БРЕНДЫ')
    print('База уходит в переобход за два дня: сначала одни бренды, на следующий')
    print('день остальные. Вопрос — вторая волна хуже из-за задержки или из-за брендов.\n')
    w2 = collections.defaultdict(lambda: [0, 0])
    for r in E:
        t = w2[r['brand']]
        t[0] += r['wave']
        t[1] += 1
    share = {b: t[0] / t[1] for b, t in w2.items()}
    print('брендов, уходящих во вторую волну больше чем в 90%% случаев: %d'
          % sum(1 for v in share.values() if v > 0.9))
    print('брендов, уходящих во вторую волну меньше чем в 10%% случаев: %d'
          % sum(1 for v in share.values() if v < 0.1))
    for name, st in (('день', lambda r: r['day']),
                     ('бренд', lambda r: r['brand']),
                     ('бренд + день', lambda r: (r['brand'], r['day']))):
        strat(E, lambda r: 'первая волна' if r['wave'] == 0 else 'вторая волна', st,
              title='ВОЛНА | страта: ' + name)

    h('6 · НЕДЕЛИ: ФАКТ ПРОТИВ ОЖИДАНИЯ ПО БРЕНДАМ И ПО ПАКАМ')
    brate = collections.defaultdict(lambda: [0, 0])
    prate = collections.defaultdict(lambda: [0, 0])
    for r in E:
        t = brate[r['brand']]
        t[0] += r['hit']
        t[1] += 1
        t = prate[fam(r['inst'])]
        t[0] += r['hit']
        t[1] += 1
    wk = collections.defaultdict(lambda: [0, 0, 0.0, 0.0])
    for r in E:
        if r['wave']:
            continue
        t = wk[week(r['day'])]
        t[0] += r['hit']
        t[1] += 1
        hh, nn = brate[r['brand']]
        t[2] += hh / nn if nn else 0
        hh, nn = prate[fam(r['inst'])]
        t[3] += hh / nn if nn else 0
    print('неделя        сайтов  выход3   ожид по брендам  к брендам   ожид по пакам  к пакам')
    for w in sorted(wk):
        hh, n, eb, ep = wk[w]
        if n < 1000:
            continue
        print('%s %7d %6.1f%% %14.1f%% %10.2f %14.1f%% %8.2f' % (
            w, n, 100 * hh / n, 100 * eb / n, hh / eb if eb else 0,
            100 * ep / n, hh / ep if ep else 0))

    h('7 · ЧЕМ ГРУЗИЛИ КАЖДУЮ НЕДЕЛЮ')
    wp = collections.defaultdict(collections.Counter)
    for r in E:
        if r['wave']:
            continue
        wp[week(r['day'])][fam(r['inst'])] += 1
    for w in sorted(wp):
        tot = sum(wp[w].values())
        if tot < 1000:
            continue
        print('\nнеделя %s, первая волна, %d сайтов' % (w, tot))
        print('  %-42s %7s %7s %11s' % ('пак', 'сайтов', 'доля', 'выход3 пака'))
        for p, n in wp[w].most_common(8):
            hh, nn = prate[p]
            print('  %-42s %7d %6.1f%% %10.1f%%'
                  % (p[:41], n, 100 * n / tot, 100 * hh / nn if nn else 0))


if __name__ == '__main__':
    if len(sys.argv) < 6:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2].split(','), sys.argv[3], sys.argv[4], sys.argv[5])
