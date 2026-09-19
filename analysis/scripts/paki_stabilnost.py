#!/usr/bin/env python3
"""Устойчив ли рейтинг паков: тот же пак на другом дне — тот же результат?

С брендами это проверялось просто: каждый бренд есть на каждой базе, и ранг
считается на одном периоде, а мерится на другом. С паками так нельзя — пак живёт
столько, сколько длится партия. Поэтому сначала надо выяснить, у скольких паков
вообще есть второй день, и только потом говорить об устойчивости.

Проверка идёт на трёх уровнях:

1. **Сколько дней живёт пак.** Если пак стоял один день, его «рейтинг» неотделим
   от всего, что было особенного в той партии.
2. **Внутри пака между днями.** Для паков, проживших два дня и больше: совпадает
   ли доля вышедших в поиск в первый и во второй день.
3. **Семейство пака.** Имена приходят поэкземплярно (`nabory-581-590_9`),
   поэтому семейство живёт дольше отдельного экземпляра и на нём проверка
   возможна там, где на экземпляре нет.

    python3 paki_stabilnost.py <панель.jsonl>
"""
import sys, re, json, collections, statistics

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from or_mh import mh

MIN_SUB = 400


def family(name):
    """Семейство: имя без номера экземпляра и без хвоста партии."""
    s = re.sub(r'[_\-]\d+$', '', name or '')
    s = re.sub(r'[_\-]part\d+.*$', '', s, flags=re.I)
    s = re.sub(r'[_\-]\d{2}\.\d{2}$', '', s)
    return s or name


def spearman(a, b):
    common = [k for k in a if k in b]
    if len(common) < 5:
        return None, len(common)
    ra = {k: i for i, k in enumerate(sorted(common, key=lambda k: a[k]))}
    rb = {k: i for i, k in enumerate(sorted(common, key=lambda k: b[k]))}
    n = len(common)
    d2 = sum((ra[k] - rb[k]) ** 2 for k in common)
    return 1 - 6 * d2 / (n * (n * n - 1)), n


def main(panel):
    rows = []
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        if not r.get('window_closed'):
            continue
        d = (r.get('recrawl_sent_at') or '')[:10]
        c = r.get('content')
        if not d or not c:
            continue
        rows.append((c, family(c), d, r.get('content_domain_url'),
                     1 if r.get('ya_clicks') else 0))
    print(f'сабдоменов с закрытым окном и известным паком: {len(rows)}')

    # ---------- 1. сколько дней живёт пак ----------
    days = collections.defaultdict(set)
    bases = collections.defaultdict(set)
    n_sub = collections.Counter()
    for c, f, d, b, y in rows:
        days[c].add(d); bases[c].add(b); n_sub[c] += 1
    big = [c for c in n_sub if n_sub[c] >= MIN_SUB]
    dist = collections.Counter(len(days[c]) for c in big)
    print(f'\nпаков с {MIN_SUB}+ сабдоменами: {len(big)}')
    print('на скольких днях стоял пак:')
    for k in sorted(dist):
        print(f'  {k} дн. — {dist[k]} паков' + ('  ← рейтинг неотделим от партии'
                                                if k == 1 else ''))
    multi = [c for c in big if len(days[c]) >= 2]
    print(f'\nпаков, проживших два дня и больше: {len(multi)} из {len(big)} '
          f'({100.0*len(multi)/len(big):.0f}%)')

    # ---------- 2. внутри пака между днями ----------
    print('\n' + '=' * 88)
    print('2 · ТОТ ЖЕ ПАК НА ДРУГОЙ ДЕНЬ')
    print('доля вышедших в первый день партии против остальных дней;')
    print('если пак — свойство контента, доли должны совпадать')
    print(f"{'пак':<40}{'дней':>6}{'1-й день':>11}{'остальные':>11}{'разница':>10}")
    pairs = []
    for c in sorted(multi, key=lambda c: -n_sub[c]):
        ds = sorted(days[c])
        first = [y for cc, f, d, b, y in rows if cc == c and d == ds[0]]
        rest = [y for cc, f, d, b, y in rows if cc == c and d != ds[0]]
        if len(first) < 150 or len(rest) < 150:
            continue
        a, b_ = statistics.mean(first), statistics.mean(rest)
        pairs.append((a, b_, c))
        if len(pairs) <= 14:
            print(f'{c[:39]:<40}{len(ds):>6}{100*a:>10.1f}%{100*b_:>10.1f}%'
                  f'{100*(b_-a):>+9.1f}')
    if len(pairs) >= 5:
        r1 = {c: a for a, b_, c in pairs}
        r2 = {c: b_ for a, b_, c in pairs}
        rho, n = spearman(r1, r2)
        print(f'\n  паков в сравнении: {len(pairs)}')
        print(f'  ранговая корреляция «первый день против остальных»: '
              f'{rho:.3f}' if rho is not None else '  мало паков')
        print(f'  средняя разница долей: '
              f'{100*statistics.mean(b_-a for a, b_, c in pairs):+.1f} п.п., '
              f'разброс {100*statistics.pstdev(b_-a for a, b_, c in pairs):.1f}')

    # ---------- 3. семейства ----------
    print('\n' + '=' * 88)
    print('3 · СЕМЕЙСТВА ПАКОВ: живут дольше экземпляра')
    fam_days = collections.defaultdict(set)
    fam_sub = collections.Counter()
    fam_hit = collections.Counter()
    for c, f, d, b, y in rows:
        fam_days[f].add(d); fam_sub[f] += 1; fam_hit[f] += y
    fbig = [f for f in fam_sub if fam_sub[f] >= MIN_SUB]
    fdist = collections.Counter(len(fam_days[f]) for f in fbig)
    print(f'семейств с {MIN_SUB}+ сабдоменами: {len(fbig)}; '
          f'из них на одном дне — {fdist[1]}')
    fmulti = [f for f in fbig if len(fam_days[f]) >= 3]
    print(f'семейств, проживших три дня и больше: {len(fmulti)}')
    print(f"\n{'семейство':<38}{'дней':>6}{'сабдом.':>9}{'доля':>8}"
          f"{'разброс по дням':>18}")
    for f in sorted(fmulti, key=lambda f: -fam_sub[f])[:12]:
        byd = collections.defaultdict(list)
        for c, ff, d, b, y in rows:
            if ff == f:
                byd[d].append(y)
        per = [statistics.mean(v) for d, v in sorted(byd.items()) if len(v) >= 100]
        if len(per) < 3:
            continue
        print(f'{f[:37]:<38}{len(per):>6}{fam_sub[f]:>9}'
              f'{100.0*fam_hit[f]/fam_sub[f]:>7.1f}%'
              f'{100*min(per):>9.1f}–{100*max(per):<8.1f}')
    print('\nразброс по дням внутри одного семейства и есть цена рейтинга:')
    print('если он шире разницы между семействами, рейтинг паков — это рейтинг дней')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
