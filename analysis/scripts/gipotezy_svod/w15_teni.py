# -*- coding: utf-8 -*-
"""
КОНТРПРОВЕРКА гипотезы №15 (угол: ТЕНИ / конфаундинг).

Заявлено тестировщиком: при равном дне запуска и зоне nabory дают с поискового клика
в 1,45 раза меньше регистраций (O/E 0.69: 12 против 17.4), archive — не хуже (O/E >= 1).

Задача: показать, что 0.69 — тень набора контента, дня, зоны, периода, партии постановки,
выбросов или объёма кликов; либо, если эффект выживает, вернуть ужатую формулировку с границами.

Только stdlib.
"""
import csv, collections, math, os, random, sys

SRC = 'analysis/export/svod_domenov_21.09.csv'
OUT = 'analysis/export/gipotezy_svod/w15_teni.txt'
OUTLIERS = ('3615.team', '3286.team')
NOC = 'КОНТЕНТ НЕ ЗАПИСАН'
NSIM = 10000


class Tee:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def write(self, s):
        sys.__stdout__.write(s); self.f.write(s)

    def flush(self):
        sys.__stdout__.flush(); self.f.flush()


def iv(x):
    return int(x) if x not in ('', None) else 0


def f2(x, nd=2):
    if x is None or x != x:
        return '—'
    return ('%.' + str(nd) + 'f') % x


def click_bin(c):
    return '≤95' if c <= 95 else '95–325' if c <= 325 else '325–912' if c <= 912 else '>912'


# ------------------------------------------------------------------ загрузка
def load(keep_noc=False, keep_outliers=False, keep_open=False):
    rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
    out = []
    for r in rows:
        if not keep_open and (r['окно закрыто'] != 'да' or r['дней'] == '1'):
            continue
        if not keep_outliers and r['домен'] in OUTLIERS:
            continue
        if not keep_noc and r['набор контента'] == NOC:
            continue
        d = dict(dom=r['домен'], zone=r['зона'], day=r['день запуска'], fam=r['семейство'],
                 sset=r['набор контента'], hour=r['блок часа'], acc=r['аккаунт вебмастера'],
                 cf=r['cf-аккаунт'], brands=iv(r['брендов']), nsets=r['наборов на домене'],
                 fresh=r['аккаунт свежий'], ntimes=r['который раз аккаунт'],
                 clicks=iv(r['кликов из поиска в окне']), regs=iv(r['регистраций в окне 3 суток']),
                 fd=iv(r['ФД в окне 3 суток']), sites=iv(r['сайтов в окне']),
                 exits=iv(r['вышли за 3 суток']), allregs=iv(r['регистраций']),
                 allclicks=iv(r['из поиска']))
        d['bin'] = click_bin(d['clicks'])
        d['conv'] = 1 if d['regs'] > 0 else 0
        d['allconv'] = 1 if d['allregs'] > 0 else 0
        out.append(d)
    return out


def strata(doms, key, min_labels=2):
    st = collections.defaultdict(list)
    for d in doms:
        st[key(d)].append(d)
    return {k: v for k, v in st.items() if len({x['fam'] for x in v}) >= min_labels}


def oe(st, fam='nabory', num='regs', den='clicks', assign=None):
    """O, E (ставка страты), O', E' (ставка только соседей), доменов, кликов."""
    O = E = Oe = Ee = 0.0
    n = c = 0
    for v in st.values():
        tc = sum(x[den] for x in v); tn = sum(x[num] for x in v)
        if tc <= 0:
            continue
        oc = on = 0
        for x in v:
            f = assign[x['dom']] if assign else x['fam']
            if f == fam:
                oc += x[den]; on += x[num]
        rc, rn = tc - oc, tn - on
        O += on; E += oc * tn / tc; n += sum(1 for x in v
                                             if (assign[x['dom']] if assign else x['fam']) == fam)
        c += oc
        if rc > 0:
            Oe += on; Ee += oc * rn / rc
    return O, E, Oe, Ee, n, c


def line(lab, st, fam='nabory', num='regs', den='clicks'):
    O, E, Oe, Ee, n, c = oe(st, fam, num, den)
    return ('  %-38s дом %4d  %-6s %7d   O=%3d  E=%6.2f  O/E=%s | к соседям O/E=%s (E\'=%.1f)'
            % (lab, n, den, c, O, E, f2(O / E) if E else '—',
               f2(Oe / Ee) if Ee else '—', Ee))


# ------------------------------------------------------- перестановки (домен / кластер)
def perm(st, fam='nabory', num='regs', den='clicks', nsim=NSIM, seed=1, cluster=None):
    rnd = random.Random(seed)
    obs = oe(st, fam, num, den)
    obsv = obs[0] / obs[1] if obs[1] else float('nan')
    obse = obs[2] / obs[3] if obs[3] else float('nan')
    groups = {}
    for k, v in st.items():
        if cluster:
            g = collections.defaultdict(list)
            for x in v:
                g[x[cluster]].append(x)
            groups[k] = list(g.values())
        else:
            groups[k] = [[x] for x in v]
    vals, vals_e = [], []
    for _ in range(nsim):
        assign = {}
        for k, gs in groups.items():
            labs = [g[0]['fam'] for g in gs]
            rnd.shuffle(labs)
            for g, l in zip(gs, labs):
                for x in g:
                    assign[x['dom']] = l
        o, e, oe_, ee_, _, _ = oe(st, fam, num, den, assign=assign)
        vals.append(o / e if e else 1.0)
        vals_e.append(oe_ / ee_ if ee_ else 1.0)
    vals.sort(); vals_e.sort()
    p = sum(1 for v in vals if v <= obsv + 1e-12) / nsim
    pe = sum(1 for v in vals_e if v <= obse + 1e-12) / nsim
    q = lambda a, arr: arr[min(len(arr) - 1, int(a * len(arr)))]
    return (obsv, p, q(.025, vals), q(.975, vals), obse, pe, q(.025, vals_e), q(.975, vals_e))


# ------------------------------------------------------- точный условный интервал
def cond_pmf(st, fam, theta, num='regs', den='clicks'):
    """Распределение суммы O при отношении ставок theta: O_s ~ Bin(T_s, theta*c/(theta*c+C))."""
    dist = [1.0]
    for v in st.values():
        T = sum(x[num] for x in v)
        if T <= 0:
            continue
        c = sum(x[den] for x in v if x[fam[0]] == fam[1]) if False else sum(
            x[den] for x in v if x['fam'] == fam)
        C = sum(x[den] for x in v) - c
        if c <= 0:
            continue
        p = theta * c / (theta * c + C) if (theta * c + C) > 0 else 0.0
        b = [math.comb(T, i) * p ** i * (1 - p) ** (T - i) for i in range(T + 1)]
        nd = [0.0] * (len(dist) + T)
        for i, a in enumerate(dist):
            if a == 0.0:
                continue
            for j, bb in enumerate(b):
                nd[i + j] += a * bb
        dist = nd
    return dist


def cond_p(st, fam, theta, obs, num='regs', den='clicks'):
    d = cond_pmf(st, fam, theta, num, den)
    lo = sum(d[:obs + 1]); hi = sum(d[obs:])
    return min(1.0, 2 * min(lo, hi)), lo, hi


def cond_ci(st, fam, obs, num='regs', den='clicks'):
    def pv(t):
        return cond_p(st, fam, t, obs, num, den)[0]
    lo, hi = 1e-3, 1.0
    for _ in range(40):
        m = (lo + hi) / 2
        if pv(m) < 0.05:
            lo = m
        else:
            hi = m
    left = hi
    lo, hi = 1.0, 20.0
    for _ in range(40):
        m = (lo + hi) / 2
        if pv(m) < 0.05:
            hi = m
        else:
            lo = m
    right = lo
    # точечная оценка — условный максимум правдоподобия
    best, bt = -1, 1.0
    t = 0.05
    while t < 5.0:
        d = cond_pmf(st, fam, t, num, den)
        v = d[obs] if obs < len(d) else 0.0
        if v > best:
            best, bt = v, t
        t += 0.01
    return left, right, bt, pv(1.0)


# ------------------------------------------------------------------ главное
def main():
    out = Tee(OUT)
    W = out.write
    W('КОНТРПРОВЕРКА №15 — ТЕНИ. Отдача с поискового клика: nabory 0.69, archive >= 1\n')
    W('Данные: %s\n\n' % SRC)

    D = load()
    nab = [d for d in D if d['fam'] == 'nabory']
    W('0. СРЕЗ И ЧТО ОН СТОИТ\n')
    W('  доменов после фильтров тестировщика: %d; nabory %d, archive %d\n'
      % (len(D), len(nab), sum(1 for d in D if d['fam'] == 'archive')))
    Dopen = load(keep_open=True)
    cut = [d for d in Dopen if d['dom'] not in {x['dom'] for x in D}]
    W('  отрезано фильтром «окно закрыто / дней>1»: %d доменов — %s\n'
      % (len(cut), dict(collections.Counter(d['fam'] for d in cut))))
    W('     из них nabory по дням: %s\n'
      % dict(sorted(collections.Counter(d['day'] for d in cut if d['fam'] == 'nabory').items())))
    W('  брендов на домене (должно быть одинаково у всех — тогда состав брендов не конфаундер): '
      'nabory %s; остальные %s\n'
      % (sorted({d['brands'] for d in nab}), sorted({d['brands'] for d in D if d['fam'] != 'nabory'})[:5]))
    W('  наборов на домене: %s\n'
      % dict(collections.Counter(d['nsets'] for d in D)))
    W('  nabory по дням запуска: %s\n'
      % dict(sorted(collections.Counter(d['day'] for d in nab).items())))
    W('  nabory по зонам: %s\n' % dict(collections.Counter(d['zone'] for d in nab)))
    W('  наборов nabory: %d на %d доменах (медиана доменов в наборе %d)\n'
      % (len({d['sset'] for d in nab}), len(nab),
         sorted(collections.Counter(d['sset'] for d in nab).values())[
             len({d['sset'] for d in nab}) // 2]))
    W('  в августе (до 01.09) nabory нет ни одного домена: %s; «КОНТЕНТ НЕ ЗАПИСАН» весь до 24.08 —\n'
      '  значит тень «август против сентября» и тень «нет имени набора» физически не могут\n'
      '  попасть внутрь страт с nabory (страта = день + зона).\n\n'
      % (not any(d['day'] < '2026-09-01' for d in nab)))

    ST = strata(D, lambda d: (d['day'], d['zone']))
    W('1. БАЗА ВОСПРОИЗВЕДЕНА\n')
    W(line('страта: день + зона (как у тестировщика)', ST) + '\n')
    O, E, Oe, Ee, n, c = oe(ST, 'archive')
    W('  archive: дом %d кликов %d O=%d E=%.1f O/E=%s | к соседям %s (E\'=%.1f)\n\n'
      % (n, c, O, E, f2(O / E), f2(Oe / Ee), Ee))

    W('2. ТЕНЬ ПЕРИОДА, ЗОНЫ, ДНЯ: РЕЖЕМ СРЕЗ\n')
    for lab, sub in (
            ('только 09-01..09-11', {k: v for k, v in ST.items() if k[0] <= '2026-09-11'}),
            ('только 09-12..09-17', {k: v for k, v in ST.items() if k[0] >= '2026-09-12'}),
            ('только зона team', {k: v for k, v in ST.items() if k[1] == 'team'}),
            ('только зона lol', {k: v for k, v in ST.items() if k[1] == 'lol'}),
            ('только casino+buzz', {k: v for k, v in ST.items() if k[1] in ('casino', 'buzz')}),
            ('дни, где сосед — NEW/clean/script',
             {k: v for k, v in ST.items()
              if {x['fam'] for x in v} & {'NEW', 'clean', 'script'}}),
            ('дни, где сосед — content-дата',
             {k: v for k, v in ST.items() if 'content-дата' in {x['fam'] for x in v}}),
    ):
        W(line(lab, sub) + '\n')
    Dn = load(keep_noc=True)
    W(line('вернуть «КОНТЕНТ НЕ ЗАПИСАН» в срез',
           strata(Dn, lambda d: (d['day'], d['zone']))) + '\n')
    Do = load(keep_outliers=True)
    W(line('вернуть выбросы 3615/3286.team',
           strata(Do, lambda d: (d['day'], d['zone']))) + '\n')
    Dop = load(keep_open=True)
    W(line('снять фильтр незакрытого окна (все 2077)',
           strata(Dop, lambda d: (d['day'], d['zone']))) + '\n\n')

    W('3. ЖЁСТКАЯ СТРАТА: ДЕНЬ + ЗОНА + ЧАС + БИН КЛИКОВ\n')
    ladders = (
        ('день + зона', lambda d: (d['day'], d['zone'])),
        ('день + зона + блок часа', lambda d: (d['day'], d['zone'], d['hour'])),
        ('день + зона + бин кликов', lambda d: (d['day'], d['zone'], d['bin'])),
        ('день + зона + час + бин', lambda d: (d['day'], d['zone'], d['hour'], d['bin'])),
    )
    for lab, key in ladders:
        W(line(lab, strata(D, key)) + '\n')
    ncf = len({d['cf'] for d in D}); nac = len({d['acc'] for d in D})
    W('  партия постановки в страту не кладётся: cf-аккаунтов %d и аккаунтов вебмастера %d на %d доменов\n'
      '  (почти по одному на домен) — страт «день+зона+аккаунт» с ≥2 семействами 0. Вместо страты — баланс:\n'
      % (ncf, nac, len(D)))
    oth_all = [d for v in ST.values() for d in v if d['fam'] != 'nabory']
    for lab, f in (('блок часа', lambda d: d['hour']),
                   ('бин кликов', lambda d: d['bin']),
                   ('свежий аккаунт', lambda d: d['fresh']),
                   ('который раз аккаунт', lambda d: d['ntimes'])):
        cn = collections.Counter(f(d) for d in nab)
        co = collections.Counter(f(d) for d in oth_all)
        sn = sum(cn.values()); so = sum(co.values())
        keys = sorted(set(cn) | set(co))[:6]
        W('    %-20s nabory: %s | соседи: %s\n'
          % (lab, ', '.join('%s %.0f%%' % (k, 100 * cn.get(k, 0) / sn) for k in keys),
             ', '.join('%s %.0f%%' % (k, 100 * co.get(k, 0) / so) for k in keys)))
    W('\n')

    W('4. ТЕНЬ НАБОРА И ПАРТИИ: КЛАСТЕРНАЯ ПЕРЕСТАНОВКА И ВЫБРОС СТРАТ/НАБОРОВ\n')
    o, p, lo, hi, oe_, pe, loe, hie = perm(ST)
    W('  перестановка метки по доменам  : O/E %.2f p(≤) %.4f нуль %.2f–%.2f | к соседям %.2f p(≤) %.4f нуль %.2f–%.2f\n'
      % (o, p, lo, hi, oe_, pe, loe, hie))
    o, p, lo, hi, oe_, pe, loe, hie = perm(ST, cluster='sset', nsim=4000, seed=7)
    W('  перестановка ЦЕЛЫМ НАБОРОМ     : O/E %.2f p(≤) %.4f нуль %.2f–%.2f | к соседям %.2f p(≤) %.4f нуль %.2f–%.2f\n'
      % (o, p, lo, hi, oe_, pe, loe, hie))
    for lab, key in ladders[1:4]:
        stx = strata(D, key)
        o, p, lo, hi, oe_, pe, loe, hie = perm(stx, nsim=4000, seed=5)
        W('  перестановка в страте «%s»: O/E %.2f p(≤) %.4f нуль %.2f–%.2f\n' % (lab, o, p, lo, hi))
    o, p, lo, hi, oe_, pe, loe, hie = perm(ST, cluster='cf', nsim=4000, seed=7)
    W('  перестановка целым cf-аккаунтом: O/E %.2f p(≤) %.4f нуль %.2f–%.2f\n' % (o, p, lo, hi))
    jack = []
    for k in ST:
        sub = {kk: v for kk, v in ST.items() if kk != k}
        O, E, _, _, _, _ = oe(sub)
        jack.append((O / E if E else float('nan'), k, O, E))
    jack.sort()
    W('  выброс по одной страте (36 шт.): O/E от %.2f (без %s) до %.2f (без %s); медиана %.2f\n'
      % (jack[0][0], jack[0][1], jack[-1][0], jack[-1][1], jack[len(jack) // 2][0]))
    sets = collections.Counter(d['sset'] for d in nab)
    worst = []
    for s in sets:
        sub = {k: [x for x in v if x['sset'] != s] for k, v in ST.items()}
        sub = {k: v for k, v in sub.items() if len({x['fam'] for x in v}) >= 2}
        O, E, _, _, _, _ = oe(sub)
        worst.append((O / E if E else float('nan'), s, sets[s]))
    worst.sort()
    W('  выброс по одному набору nabory (%d шт.): O/E от %.2f до %.2f\n'
      % (len(sets), worst[0][0], worst[-1][0]))
    W('     худший вариант без набора %s (%d дом.) — %.2f; лучший без %s (%d дом.) — %.2f\n'
      % (worst[0][1], worst[0][2], worst[0][0], worst[-1][1], worst[-1][2], worst[-1][0]))
    series = collections.defaultdict(list)
    for d in nab:
        import re
        m = re.match(r'^(nabory-?\d+-?\d*)', d['sset'])
        series[m.group(1) if m else d['sset']].append(d)
    big = sorted(series.items(), key=lambda kv: -len(kv[1]))[:3]
    for s, v in big:
        sub = {k: [x for x in vv if x['sset'] not in {y['sset'] for y in v}] for k, vv in ST.items()}
        sub = {k: vv for k, vv in sub.items() if len({x['fam'] for x in vv}) >= 2}
        O, E, _, _, _, _ = oe(sub)
        W('     без серии %-28s (%2d дом.): O/E %.2f\n' % (s, len(v), O / E if E else float('nan')))
    W('\n')

    W('5. ТЕНЬ ОБЪЁМА: ПАРЫ РАВНОГО РАЗМЕРА ВНУТРИ СТРАТЫ\n')
    for tol in (1.25, 1.5, 2.0):
        pairs = []
        for k, v in ST.items():
            nn = sorted([x for x in v if x['fam'] == 'nabory'], key=lambda x: -x['clicks'])
            oo = [x for x in v if x['fam'] != 'nabory']
            used = set()
            for a in nn:
                best = None
                for b in oo:
                    if b['dom'] in used:
                        continue
                    r = (max(a['clicks'], b['clicks']) + 1) / (min(a['clicks'], b['clicks']) + 1)
                    if r <= tol and (best is None or r < best[0]):
                        best = (r, b)
                if best:
                    used.add(best[1]['dom']); pairs.append((a, best[1]))
        ra = sum(p[0]['regs'] for p in pairs); rb = sum(p[1]['regs'] for p in pairs)
        ca = sum(p[0]['clicks'] for p in pairs); cb = sum(p[1]['clicks'] for p in pairs)
        disc = [(p[0]['regs'], p[1]['regs']) for p in pairs if p[0]['regs'] != p[1]['regs']]
        w = sum(1 for a, b in disc if a > b); nd = len(disc)
        pv = sum(math.comb(nd, i) for i in range(w + 1)) / 2 ** nd if nd else 1.0
        W('  пары ±%d%% по кликам: пар %3d | клики %6d против %6d | рег %2d против %2d '
          '(отношение на клик %s) | пар с разным исходом %2d, nabory выиграл %d — знак-тест p=%.3f\n'
          % (round((tol - 1) * 100), len(pairs), ca, cb, ra, rb,
             f2((ra / ca) / (rb / cb)) if ca and cb and rb else '—', nd, w, pv))
    W('\n')

    W('6. ТЕНЬ МЕТРИКИ: ПОВТОРНЫЕ РЕГИСТРАЦИИ НА ОДНОМ ДОМЕНЕ\n')
    dist_n = collections.Counter(d['regs'] for d in nab)
    oth = [d for v in ST.values() for d in v if d['fam'] != 'nabory']
    dist_o = collections.Counter(d['regs'] for d in oth)
    W('  регистраций на домен, nabory  : %s (максимум 1 — ни один домен не сконвертил дважды)\n'
      % dict(sorted(dist_n.items())))
    W('  регистраций на домен, соседи  : %s → %d рег. с %d доменов, ×%.2f на домен\n'
      % (dict(sorted(dist_o.items())), sum(d['regs'] for d in oth),
         sum(d['conv'] for d in oth),
         sum(d['regs'] for d in oth) / sum(d['conv'] for d in oth)))
    for lab, key in ladders[:4]:
        W(line('ДОМЕНЫ с ≥1 рег.: ' + lab, strata(D, key), num='conv') + '\n')
    o, p, lo, hi, oe_, pe, loe, hie = perm(ST, num='conv')
    W('  перестановка (домены с ≥1 рег.): O/E %.2f p(≤) %.4f нуль %.2f–%.2f | к соседям %.2f p(≤) %.4f\n'
      % (o, p, lo, hi, oe_, pe))
    W(line('окно снято: рег. за всё время / все поисковые клики', ST,
           num='allregs', den='allclicks') + '\n')
    W(line('окно снято, домены с ≥1 рег.', ST, num='allconv', den='allclicks') + '\n')
    W(line('знаменатель — вышедшие сайты, а не клики', ST, den='exits') + '\n')
    W(line('ФД вместо регистраций', ST, num='fd') + '\n\n')

    W('7. ТЕНЬ ОТДЕЛЬНЫХ ДОМЕНОВ-СОСЕДЕЙ\n')
    top = sorted(oth, key=lambda d: -d['regs'])[:6]
    for d in top:
        W('  топ-сосед %-18s %-12s %s %-6s рег %d кликов %6d\n'
          % (d['dom'], d['fam'], d['day'], d['zone'], d['regs'], d['clicks']))
    for k in (1, 3, 5):
        drop = {d['dom'] for d in top[:k]}
        sub = {kk: [x for x in v if x['dom'] not in drop] for kk, v in ST.items()}
        sub = {kk: v for kk, v in sub.items() if len({x['fam'] for x in v}) >= 2}
        O, E, Oe, Ee, _, _ = oe(sub)
        W('  убрать %d самых конвертящих соседей: O=%d E=%.1f O/E=%s\n' % (k, O, E, f2(O / E)))
    nabtop = sorted(nab, key=lambda d: -d['clicks'])[:5]
    drop = {d['dom'] for d in nabtop}
    sub = {kk: [x for x in v if x['dom'] not in drop] for kk, v in ST.items()}
    sub = {kk: v for kk, v in sub.items() if len({x['fam'] for x in v}) >= 2}
    O, E, _, _, n, c = oe(sub)
    W('  убрать 5 самых кликовых доменов nabory (%d кликов из %d): дом %d O=%d E=%.1f O/E=%s\n\n'
      % (sum(d['clicks'] for d in nabtop), sum(d['clicks'] for d in nab), n, O, E, f2(O / E)))

    W('8. ТОЧНЫЙ УСЛОВНЫЙ ИНТЕРВАЛ НА ОТНОШЕНИЕ СТАВОК (страты день + зона)\n')
    for fam, num, lab in (('nabory', 'regs', 'nabory, регистрации на клик'),
                          ('nabory', 'conv', 'nabory, домены с ≥1 рег. на клик'),
                          ('archive', 'regs', 'archive, регистрации на клик')):
        obs = int(oe(ST, fam, num)[0])
        l, r, pt, p1 = cond_ci(ST, fam, obs, num=num)
        _, lo_t, hi_t = cond_p(ST, fam, 1.0, obs, num=num)
        W('  %-34s O=%2d  точечно %.2f  95%% интервал %.2f–%.2f  (p при равенстве: односторонний %.3f, двусторонний %.3f)\n'
          % (lab, obs, pt, l, r, min(lo_t, hi_t), p1))
    W('\n')

    W('9. МНОЖЕСТВЕННОСТЬ\n')
    fams = [f for f in collections.Counter(d['fam'] for d in D) if f != 'тест']
    res = []
    for f in fams:
        O, E, _, _, n, c = oe(ST, f)
        if E > 0:
            res.append((O / E, f, O, E, n))
    res.sort()
    for v, f, O, E, n in res:
        W('  %-14s дом %4d O=%3d E=%6.1f O/E=%.2f\n' % (f, n, O, E, v))
    W('  семейств в сравнении: %d; nabory — самое низкое из них. Поправка Бонферрони к p=0.036:\n'
      '  0.036 × %d = %.2f. Общий перестановочный тест Σ(O−E)²/E у тестировщика p=0.80.\n\n'
      % (len(res), len(res), min(1.0, 0.036 * len(res))))

    W('10. ARCHIVE: ЧЕМ ДЕРЖИТСЯ «НЕ ХУЖЕ»\n')
    for k, v in sorted(ST.items()):
        a = [x for x in v if x['fam'] == 'archive']
        if not a:
            continue
        nb = collections.Counter(x['fam'] for x in v if x['fam'] != 'archive')
        W('  %s %-7s archive %2d дом / %6d кл / %2d рег | соседи: %s\n'
          % (k[0], k[1], len(a), sum(x['clicks'] for x in a), sum(x['regs'] for x in a),
             ', '.join('%s %d' % (f, c) for f, c in nb.most_common())))
    sub = {k: v for k, v in ST.items() if k != ('2026-09-09', 'lol')}
    O, E, Oe, Ee, n, c = oe(sub, 'archive')
    W('  без страты 09-09 lol: дом %d O=%d E=%.1f O/E=%s | к соседям %s\n'
      % (n, O, E, f2(O / E), f2(Oe / Ee) if Ee else '—'))
    sub = {k: [x for x in v if x['sset'] != 'archive412_unique12оформлено'] for k, v in ST.items()}
    sub = {k: v for k, v in sub.items() if len({x['fam'] for x in v}) >= 2}
    O, E, Oe, Ee, n, c = oe(sub, 'archive')
    W('  без набора archive412_unique12оформлено: дом %d O=%d E=%.1f O/E=%s | к соседям %s\n'
      % (n, O, E, f2(O / E), f2(Oe / Ee) if Ee else '—'))
    sub = {k: [x for x in v if x['fam'] != 'nabory'] for k, v in ST.items()}
    sub = {k: v for k, v in sub.items() if len({x['fam'] for x in v}) >= 2}
    O, E, Oe, Ee, n, c = oe(sub, 'archive')
    W('  выбросив nabory из соседей archive: дом %d O=%d E=%.1f O/E=%s | к соседям %s (E\'=%.1f)\n'
      % (n, O, E, f2(O / E), f2(Oe / Ee) if Ee else '—', Ee))
    W('\n11. ЧТО ВЫЖИЛО И ЧТО НЕ ВЫЖИЛО\n')
    W('  Тени НЕ объясняют знак: август/«КОНТЕНТ НЕ ЗАПИСАН» вне страт nabory; выбросы 3615/3286 вне срезa;\n'
      '  разрез по периоду (0.63 / 0.76), по зоне (team 0.68, lol 0.68), по типу соседа (NEW-дни 0.62,\n'
      '  content-дни 0.76), выброс любой страты (0.61–0.74), любого набора (0.61–0.75), любой серии (0.69–0.72),\n'
      '  снятие фильтра окна (0.72), пары равного объёма (0.54–0.58) — везде ниже 1.\n'
      '  НЕ выжили размер и значимость: «в 1,45 раза» держится только на регистрациях, где соседи\n'
      '  считаются повторно (190 рег. с 136 доменов, ×1.40); на доменах с ≥1 рег. это 0.84 (p 0.15),\n'
      '  точный условный интервал на отношение ставок 0.28–1.17 (точечно 0.60), знак-тест по парам p 0.32–0.40,\n'
      '  Бонферрони на 9 семейств 0.32, общий тест p 0.80.\n')
    out.flush()


if __name__ == '__main__':
    main()
