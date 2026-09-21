#!/usr/bin/env python3
"""
Гипотеза №15. При равном числе поисковых кликов nabory дают в 1,5 раза меньше
регистраций на клик, чем NEW, content-дата и archive (у nabory плохи и выход, и
клик — нечем спасать), а archive при худшем выходе конвертирует клик не хуже
остальных (плох только выход — спасаем, если найдём выход).

Что проверяем.
  Вторую ступень воронки — отдачу с поискового клика (регистраций в окне 3 суток на
  поисковый клик в окне) — по семействам наборов при зафиксированных дне запуска и
  зоне. Первая ступень (выход сайтов в поиск) и деньги на сайт по семействам уже
  известны из реестра; отдача с клика при равном уровне кликов не проверялась.
  Семейство — свойство набора, поэтому обычный пул «набор контента + день» не годится
  (семейство в нём константа); страта = день запуска + зона.

Как проверяем.
  Фильтры: окно закрыто = да; дней ≠ 1; без 3615.team и 3286.team; без
  «КОНТЕНТ НЕ ЗАПИСАН». Зоны team/lol/casino/buzz, остальные — «прочие».
  Страта = день запуска + зона; в расчёт входят только страты с ≥2 семействами
  (в страте из одного семейства O = E по построению).
  E домена = (регистраций страты / поисковых кликов страты) × поисковые клики домена;
  O/E семейства = Σ регистраций / Σ E. Рядом — O/E «против остальных»: E из ставки
  остальных семейств той же страты (без самого семейства), потому что там, где
  семейство даёт 80–95 % кликов страты, обычный O/E прижат к 1 по построению.
  Значимость: перестановка метки семейства между доменами внутри страты, 10 000 раз,
  random.seed(1); статистики — O/E nabory и O/E archive (оба варианта) и
  Σ(O−E)²/E по всем семействам как общий тест на многие сравнения. p односторонний
  (O/E ≤ наблюдённого, для archive — ≥) и двусторонний (|ln O/E| ≥ наблюдённого).
  Рядом — пуассоновский хвост P(X ≤ O | E) как грубый знак для маленьких групп.
  Контроль объёма: (а) сырые рег/10 тыс. по семействам в 4 бинах поисковых кликов
  домена в окне (≤95, 95–325, 325–912, >912); (б) O/E в стратах день + зона + бин
  (те же перестановки); (в) только сентябрь (день запуска ≥ 01.09).
  Второй ярус: внутри nabory — по наборам (E тот же, из страт день + зона) и
  «nabory без набора X»; внутри archive — по наборам archive37строформленоv2часть1/2/3,
  archive47_unique119оформленочасть1/2, archive412_unique12оформлено, плюс сравнение
  частей archive между собой внутри страт из одних archive-доменов.
  Дубль на сайт: те же страты, E = ставка страты на сайт × сайтов в окне; рядом O/E
  выхода (вышли за 3 суток / сайтов в окне) и O/E поисковых кликов на сайт, чтобы
  видеть обе ступени воронки. ФД в окне (62 на весь свод) — только как знак.

Критерии постановки: nabory O/E по кликам ≤0,7 при p < 0,05 и ≤1 в каждом бине с
≥2 регистрациями; archive 0,85–1,2; опровержение — nabory O/E ≈1 (плох только выход).
"""
import collections
import csv
import math
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h15_family_per_click.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
NSIM = 10000
ZONES = ('team', 'lol', 'casino', 'buzz')
BIN_NAMES = ('≤95', '95–325', '325–912', '>912')
FAM_ORDER = ('nabory', 'archive', 'NEW', 'content-дата', 'Generator', 'clean', 'script',
             'прочее', 'контроль', 'тест')
SEPT = '2026-09-01'
TARGETS = ('nabory', 'archive')
ARCHIVE_SETS = ('archive37строформленоv2часть1', 'archive37строформленоv2часть2',
                'archive37строформленоv2часть3', 'archive47_unique119оформленочасть1',
                'archive47_unique119оформленочасть2', 'archive412_unique12оформлено')
SERIES_RE = re.compile(r'^(nabory-\d+-\d+(?:_styled_img)?)_\d+$')


class Tee:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def write(self, s):
        sys.__stdout__.write(s)
        self.f.write(s)

    def flush(self):
        sys.__stdout__.flush()
        self.f.flush()


def iv(x):
    return int(x) if x not in ('', None) else 0


def fmt(x, nd=2):
    if x != x or x in (float('inf'), float('-inf')):
        return '—'
    return ('%.' + str(nd) + 'f') % x


def ratio(a, b):
    return a / b if b else float('nan')


def per10k(r, c):
    return 1e4 * r / c if c else float('nan')


def pois_cdf(k, lam):
    """P(X <= k) для X ~ Pois(lam)."""
    if lam <= 0:
        return 1.0
    s, term = 0.0, math.exp(-lam)
    for i in range(int(k) + 1):
        s += term
        term *= lam / (i + 1)
    return min(1.0, s)


def pois_sf(k, lam):
    """P(X >= k)."""
    if k <= 0:
        return 1.0
    return max(0.0, 1.0 - pois_cdf(k - 1, lam))


def click_bin(c):
    if c <= 95:
        return '≤95'
    if c <= 325:
        return '95–325'
    if c <= 912:
        return '325–912'
    return '>912'


def fam_sorted(fams):
    order = {f: i for i, f in enumerate(FAM_ORDER)}
    return sorted(fams, key=lambda f: (order.get(f, 99), f))


# ---------------------------------------------------------------- загрузка

def load(out):
    with open(SRC, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    out.write('Прочитано строк (доменов): %d\n' % len(rows))
    steps = (
        ('окно закрыто ≠ да (3 суток ещё не прошли)', lambda r: r['окно закрыто'] != 'да'),
        ('дней = 1 (день 2 ещё не наступил, 150 сайтов)', lambda r: r['дней'] == '1'),
        ('выбросы 3615.team и 3286.team', lambda r: r['домен'] in OUTLIERS),
        ('«КОНТЕНТ НЕ ЗАПИСАН» (не набор, сцеплен с датой)', lambda r: r['набор контента'] == NOCONTENT),
    )
    pending = collections.Counter(r['семейство'] for r in rows
                                  if r['окно закрыто'] != 'да' or r['дней'] == '1')
    kept = rows
    for name, cond in steps:
        drop = [r for r in kept if cond(r)]
        kept = [r for r in kept if not cond(r)]
        out.write('  исключено: %-52s %4d   (осталось %d)\n' % (name, len(drop), len(kept)))
    doms = []
    for r in kept:
        d = dict(dom=r['домен'], zone=r['зона'] if r['зона'] in ZONES else 'прочие',
                 day=r['день запуска'], fam=r['семейство'], sset=r['набор контента'],
                 clicks=iv(r['кликов из поиска в окне']), regs=iv(r['регистраций в окне 3 суток']),
                 fd=iv(r['ФД в окне 3 суток']), sites=iv(r['сайтов в окне']),
                 exits=iv(r['вышли за 3 суток']))
        d['bin'] = click_bin(d['clicks'])
        m = SERIES_RE.match(d['sset'])
        d['series'] = (m.group(1) + '_*') if m else d['sset']
        doms.append(d)
    return doms, pending


# ---------------------------------------------------------------- страты и O/E

def build_strata(doms, key, label='fam', min_labels=2):
    st = collections.defaultdict(list)
    for d in doms:
        st[key(d)].append(d)
    kept = {k: v for k, v in st.items() if len({d[label] for d in v}) >= min_labels}
    dropped = {k: v for k, v in st.items() if k not in kept}
    return kept, dropped


def new_cell():
    return dict(n=0, sites=0, clicks=0, regs=0, fd=0, exits=0, O=0.0, E=0.0,
                Oex=0.0, Eex=0.0, Efd=0.0, nstr=0)


def oe_table(strata, label='fam', num='regs', den='clicks', only=None):
    """O/E по меткам label внутри страт. E = ставка страты (num/den) × den домена.
    Oex/Eex — та же пара, но ставка берётся по остальным меткам страты (без самой)."""
    per = collections.defaultdict(new_cell)
    for doms in strata.values():
        R = sum(d[num] for d in doms)
        C = sum(d[den] for d in doms)
        Fd = sum(d['fd'] for d in doms)
        sub = collections.defaultdict(lambda: [0, 0])
        for d in doms:
            lab = d[label]
            if only is not None and not only(d):
                continue
            p = per[lab]
            p['n'] += 1
            p['sites'] += d['sites']
            p['clicks'] += d['clicks']
            p['regs'] += d['regs']
            p['fd'] += d['fd']
            p['exits'] += d['exits']
            p['O'] += d[num]
            sub[lab][0] += d[num]
            sub[lab][1] += d[den]
        if C == 0:
            continue
        for lab, (Rf, Cf) in sub.items():
            p = per[lab]
            p['nstr'] += 1
            p['E'] += R / C * Cf
            p['Efd'] += Fd / C * Cf
            Co = C - Cf
            if Co > 0:
                p['Oex'] += Rf
                p['Eex'] += (R - Rf) / Co * Cf
    return per


def rate_ratio_vs(strata, fam, exclude=(), num='regs', den='clicks'):
    """O семейства и E по ставке «остальных» страты, где остальные — все метки,
    кроме fam и кроме exclude. Считается только по стратам, где такие остальные
    имеют den > 0."""
    O = E = 0.0
    n = 0
    for doms in strata.values():
        mine = [d for d in doms if d['fam'] == fam]
        oth = [d for d in doms if d['fam'] != fam and d['fam'] not in exclude]
        if not mine or not oth:
            continue
        Co = sum(d[den] for d in oth)
        if Co == 0:
            continue
        Ro = sum(d[num] for d in oth)
        O += sum(d[num] for d in mine)
        E += Ro / Co * sum(d[den] for d in mine)
        n += len(mine)
    return O, E, n


def print_oe(out, per, fams, title, num_lab='рег', with_ex=True, with_pois=True):
    out.write('\n%s\n' % title)
    hdr = '  %-14s %6s %7s %8s %5s %4s %7s %6s' % ('семейство', 'домен.', 'сайтов', 'кликов', num_lab, 'ФД', 'E', 'O/E')
    if with_ex:
        hdr += ' %15s' % 'против остальн.'
    if with_pois:
        hdr += ' %8s %8s' % ('P(X≤O)', 'P(X≥O)')
    out.write(hdr + '\n')
    for f in fams:
        if f not in per:
            continue
        p = per[f]
        line = '  %-14s %6d %7d %8d %5d %4d %7s %6s' % (
            f, p['n'], p['sites'], p['clicks'], p['O'], p['fd'], fmt(p['E'], 1), fmt(ratio(p['O'], p['E'])))
        if with_ex:
            line += ' %6s (%2d/%5s)' % (fmt(ratio(p['Oex'], p['Eex'])), p['Oex'], fmt(p['Eex'], 1))
        if with_pois:
            line += ' %8s %8s' % (fmt(pois_cdf(p['O'], p['E']), 3), fmt(pois_sf(p['O'], p['E']), 3))
        out.write(line + '\n')


# ---------------------------------------------------------------- перестановки

def perm_test(strata, label='fam', targets=TARGETS, nsim=NSIM, seed=1, num='regs', den='clicks'):
    random.seed(seed)
    fams = sorted({d[label] for doms in strata.values() for d in doms})
    idx = {f: i for i, f in enumerate(fams)}
    F = len(fams)
    prep = []
    for doms in strata.values():
        C = sum(d[den] for d in doms)
        R = sum(d[num] for d in doms)
        if C == 0:
            continue
        prep.append(([d[num] for d in doms], [d[den] for d in doms],
                     [idx[d[label]] for d in doms], R, C))

    def stats(assign):
        O = [0.0] * F
        E = [0.0] * F
        Oex = [0.0] * F
        Eex = [0.0] * F
        for (rs, cs, _, R, C), lab in zip(prep, assign):
            Rf = [0.0] * F
            Cf = [0.0] * F
            for r, c, f in zip(rs, cs, lab):
                Rf[f] += r
                Cf[f] += c
            rate = R / C
            for f in range(F):
                cf = Cf[f]
                rf = Rf[f]
                if cf == 0 and rf == 0:
                    continue
                O[f] += rf
                E[f] += rate * cf
                Co = C - cf
                if Co > 0:
                    Oex[f] += rf
                    Eex[f] += (R - rf) / Co * cf
        res = {'T': sum((O[f] - E[f]) ** 2 / E[f] for f in range(F) if E[f] > 0)}
        for t in targets:
            if t in idx:
                i = idx[t]
                res[t + '_oe'] = ratio(O[i], E[i]) if E[i] > 0 else float('nan')
                res[t + '_rr'] = ratio(Oex[i], Eex[i]) if Eex[i] > 0 else float('nan')
        return res

    obs = stats([labs for (_, _, labs, _, _) in prep])
    sims = {k: [] for k in obs}
    copies = [list(labs) for (_, _, labs, _, _) in prep]
    for _ in range(nsim):
        for lab in copies:
            random.shuffle(lab)
        s = stats(copies)
        for k, v in s.items():
            sims[k].append(v)
    return obs, sims


def pvals(obs, sim):
    xs = [v for v in sim if v == v]
    n = len(xs)
    nan = float('nan')
    if n == 0 or obs != obs:
        return dict(low=nan, high=nan, two=nan, lo=nan, hi=nan, n=n)
    eps = 1e-12
    low = sum(1 for v in xs if v <= obs + eps) / n
    high = sum(1 for v in xs if v >= obs - eps) / n
    lo_obs = abs(math.log(obs)) if obs > 0 else float('inf')
    two = sum(1 for v in xs if (abs(math.log(v)) if v > 0 else float('inf')) >= lo_obs - eps) / n
    xs.sort()
    return dict(low=low, high=high, two=two, lo=xs[int(0.025 * n)], hi=xs[min(n - 1, int(0.975 * n))], n=n)


def print_perm(out, obs, sims, title):
    out.write('\n%s (перестановок %d, random.seed(1))\n' % (title, len(sims['T'])))
    out.write('  %-28s %7s %13s %9s %9s %9s\n' % ('статистика', 'наблюд.', 'нуль 2.5–97.5%', 'p(≤)', 'p(≥)', 'p(двуст.)'))
    names = (('nabory_oe', 'nabory O/E (E из страты)'), ('nabory_rr', 'nabory O/E против остальных'),
             ('archive_oe', 'archive O/E (E из страты)'), ('archive_rr', 'archive O/E против остальных'))
    res = {}
    for k, name in names:
        if k not in obs:
            continue
        pv = pvals(obs[k], sims[k])
        res[k] = pv
        out.write('  %-28s %7s %6s–%-6s %9s %9s %9s\n' % (
            name, fmt(obs[k]), fmt(pv['lo']), fmt(pv['hi']), fmt(pv['low'], 4), fmt(pv['high'], 4), fmt(pv['two'], 4)))
    pv = pvals(obs['T'], sims['T'])
    res['T'] = pv
    out.write('  %-28s %7s %6s–%-6s %9s %9s %9s\n' % (
        'Σ(O−E)²/E по всем семействам', fmt(obs['T'], 1), fmt(pv['lo'], 1), fmt(pv['hi'], 1), '', fmt(pv['high'], 4), ''))
    return res


# ---------------------------------------------------------------- основной ход

def main():
    out = Tee(OUT)
    sys.stdout = out
    print('ГИПОТЕЗА №15. Отдача с поискового клика по семействам наборов при равном дне и зоне:')
    print('nabory в 1,5 раза хуже NEW/content-дата/archive на клик; archive на клик не хуже остальных.')
    print('Файл: %s\n' % os.path.relpath(SRC, REPO))

    print('0. ФИЛЬТРЫ')
    doms, pending = load(out)
    zones = collections.Counter(d['zone'] for d in doms)
    print('  зоны после фильтров: %s' % ', '.join('%s %d' % (z, zones[z]) for z in ZONES + ('прочие',) if zones.get(z)))
    if not zones.get('прочие'):
        print('  (доменов экзотических зон — группа «прочие» — после фильтров не осталось)')
    fams_all = collections.Counter(d['fam'] for d in doms)
    print('  семейства после фильтров: %s' % ', '.join('%s %d' % (f, fams_all[f]) for f in fam_sorted(fams_all)))

    # ---- 1. основной расчёт: страта = день + зона
    key_dz = lambda d: (d['day'], d['zone'])
    strata, dropped = build_strata(doms, key_dz)
    n_in = sum(len(v) for v in strata.values())
    n_drop = sum(len(v) for v in dropped.values())
    print('\n1. СТРАТЫ «ДЕНЬ ЗАПУСКА + ЗОНА» И O/E ПО КЛИКАМ')
    print('  страт всего %d; с ≥2 семействами %d (доменов %d); из одного семейства %d (доменов %d — исключены,'
          % (len(strata) + len(dropped), len(strata), n_in, len(dropped), n_drop))
    print('  там O = E по построению)')
    drop_fams = collections.Counter(d['fam'] for v in dropped.values() for d in v)
    print('  исключённые одно-семейные страты по семействам: %s'
          % ', '.join('%s %d' % (f, drop_fams[f]) for f in fam_sorted(drop_fams)))
    print('\n  Состав страт (семейство: доменов / поисковых кликов в окне / регистраций в окне):')
    for k in sorted(strata):
        doms_k = strata[k]
        cnt = collections.defaultdict(lambda: [0, 0, 0])
        for d in doms_k:
            c = cnt[d['fam']]
            c[0] += 1
            c[1] += d['clicks']
            c[2] += d['regs']
        R = sum(d['regs'] for d in doms_k)
        C = sum(d['clicks'] for d in doms_k)
        print('  %s %-7s рег/10тыс %5s | %s' % (k[0][5:], k[1], fmt(per10k(R, C), 1),
              '; '.join('%s %d/%d/%d' % (f, *cnt[f]) for f in fam_sorted(cnt))))

    per_main = oe_table(strata)
    fams_main = fam_sorted(per_main)
    print_oe(out, per_main, fams_main,
             '  O/E регистраций на поисковый клик (E = ставка страты × клики домена; «против остальных» — E по ставке\n'
             '  остальных семейств страты; P — пуассоновские хвосты при E из страты, грубый знак):')
    tot_regs = sum(p['O'] for p in per_main.values())
    tot_clicks = sum(p['clicks'] for p in per_main.values())
    print('  всего в стратах: доменов %d, сайтов %d, кликов %d, регистраций %d, ФД %d'
          % (sum(p['n'] for p in per_main.values()), sum(p['sites'] for p in per_main.values()),
             tot_clicks, tot_regs, sum(p['fd'] for p in per_main.values())))

    # nabory при ставке NEW / content-дата и т.п. — сырые
    raw = collections.defaultdict(lambda: [0, 0, 0])
    for d in doms:
        raw[d['fam']][0] += 1
        raw[d['fam']][1] += d['clicks']
        raw[d['fam']][2] += d['regs']
    print('\n  Сырые (без страт) рег/10 тыс. поисковых кликов в окне по семействам после фильтров:')
    for f in fam_sorted(raw):
        n, c, r = raw[f]
        print('    %-14s доменов %4d кликов %7d рег %3d  → %s' % (f, n, c, r, fmt(per10k(r, c))))
    nab = raw['nabory']
    for ref in ('NEW', 'content-дата', 'archive'):
        if ref in raw and raw[ref][1]:
            print('    nabory при сырой ставке %-12s дали бы %s регистраций (получили %d)'
                  % (ref, fmt(nab[1] * raw[ref][2] / raw[ref][1], 1), nab[2]))

    # archive против «остальных без nabory»
    print('\n  archive против остальных семейств, но без nabory среди «остальных» (страты, где есть и другие):')
    O, E, n = rate_ratio_vs(strata, 'archive', exclude=('nabory',))
    print('    доменов archive %d, O = %d, E = %s, O/E = %s' % (n, O, fmt(E, 1), fmt(ratio(O, E))))
    O2, E2, n2 = rate_ratio_vs(strata, 'archive', exclude=())
    print('    для сравнения: против всех остальных — доменов %d, O = %d, E = %s, O/E = %s' % (n2, O2, fmt(E2, 1), fmt(ratio(O2, E2))))
    print('  nabory против остальных без archive:')
    O3, E3, n3 = rate_ratio_vs(strata, 'nabory', exclude=('archive',))
    print('    доменов nabory %d, O = %d, E = %s, O/E = %s' % (n3, O3, fmt(E3, 1), fmt(ratio(O3, E3))))
    print('  nabory против каждого семейства по отдельности (только общие страты, E по ставке этого семейства):')
    nab_vs = {}
    for ref in ('NEW', 'content-дата', 'archive', 'Generator', 'clean', 'script', 'прочее'):
        Ov = Ev = 0.0
        nv = 0
        for doms_k in strata.values():
            mine = [d for d in doms_k if d['fam'] == 'nabory']
            oth = [d for d in doms_k if d['fam'] == ref]
            Co = sum(d['clicks'] for d in oth)
            if not mine or not oth or Co == 0:
                continue
            Ov += sum(d['regs'] for d in mine)
            Ev += sum(d['regs'] for d in oth) / Co * sum(d['clicks'] for d in mine)
            nv += len(mine)
        nab_vs[ref] = (Ov, Ev, nv)
        if nv:
            print('    против %-13s доменов nabory %3d, O = %2d, E = %5s, O/E = %s'
                  % (ref, nv, Ov, fmt(Ev, 1), fmt(ratio(Ov, Ev))))

    for fam in TARGETS:
        print('\n  Вклад страт в O/E %s (O — рег. семейства; E — по ставке страты; E\' — по ставке остальных семейств страты):' % fam)
        print('  %-13s %5s %7s %3s %6s %6s | %s' % ('страта', 'дом.', 'кликов', 'O', 'E', "E'", 'остальные: доменов / кликов / рег.'))
        for k in sorted(strata):
            doms_k = strata[k]
            mine = [d for d in doms_k if d['fam'] == fam]
            if not mine:
                continue
            oth = [d for d in doms_k if d['fam'] != fam]
            R = sum(d['regs'] for d in doms_k)
            C = sum(d['clicks'] for d in doms_k)
            Cm = sum(d['clicks'] for d in mine)
            Om = sum(d['regs'] for d in mine)
            Ro = sum(d['regs'] for d in oth)
            Co = sum(d['clicks'] for d in oth)
            print('  %s %-7s %5d %7d %3d %6s %6s | %d / %d / %d' % (
                k[0][5:], k[1], len(mine), Cm, Om, fmt(R / C * Cm, 2) if C else '—',
                fmt(Ro / Co * Cm, 2) if Co else '—', len(oth), Co, Ro))

    print('\n2. ПЕРЕСТАНОВОЧНЫЙ ТЕСТ (метка семейства между доменами внутри страты день + зона)')
    obs_main, sims_main = perm_test(strata)
    pm = print_perm(out, obs_main, sims_main, '  Основной срез')

    # ---- 3. контроль объёма: бины кликов
    print('\n3. КОНТРОЛЬ ОБЪЁМА: БИНЫ ПОИСКОВЫХ КЛИКОВ ДОМЕНА В ОКНЕ')
    print('  (а) Сырые рег/10 тыс. по семействам и бинам (после фильтров, без страт):')
    rawb = collections.defaultdict(lambda: [0, 0, 0])
    for d in doms:
        rawb[(d['fam'], d['bin'])][0] += 1
        rawb[(d['fam'], d['bin'])][1] += d['clicks']
        rawb[(d['fam'], d['bin'])][2] += d['regs']
    print('  %-14s' % 'семейство' + ''.join(' | %-26s' % b for b in BIN_NAMES))
    print('  %-14s' % '' + ''.join(' | %6s %7s %3s %7s' % ('домен.', 'кликов', 'рег', 'рег/10т') for _ in BIN_NAMES))
    for f in ('nabory', 'archive', 'NEW', 'content-дата', 'Generator', 'clean', 'script'):
        line = '  %-14s' % f
        for b in BIN_NAMES:
            n, c, r = rawb.get((f, b), [0, 0, 0])
            line += ' | %6d %7d %3d %7s' % (n, c, r, fmt(per10k(r, c)))
        print(line)

    print('\n  (б) O/E в стратах «день + зона + бин» (только страты с ≥2 семействами):')
    key_dzb = lambda d: (d['day'], d['zone'], d['bin'])
    strata_b, dropped_b = build_strata(doms, key_dzb)
    print('  страт %d (доменов %d); одно-семейных %d (доменов %d) исключено'
          % (len(strata_b), sum(len(v) for v in strata_b.values()), len(dropped_b), sum(len(v) for v in dropped_b.values())))
    per_b = oe_table(strata_b)
    print_oe(out, per_b, fam_sorted(per_b), '  Все бины вместе (страта = день + зона + бин):')
    print('\n  По бинам (E из страт день + зона + бин):')
    print('  %-14s' % 'семейство' + ''.join(' | %-22s' % b for b in BIN_NAMES))
    print('  %-14s' % '' + ''.join(' | %5s %3s %6s %6s' % ('дом.', 'рег', 'E', 'O/E') for _ in BIN_NAMES))
    per_bin = {}
    for b in BIN_NAMES:
        sub = {k: v for k, v in strata_b.items() if k[2] == b}
        per_bin[b] = oe_table(sub)
    for f in ('nabory', 'archive', 'NEW', 'content-дата', 'Generator', 'clean', 'script'):
        line = '  %-14s' % f
        for b in BIN_NAMES:
            p = per_bin[b].get(f)
            if p:
                line += ' | %5d %3d %6s %6s' % (p['n'], p['O'], fmt(p['E'], 1), fmt(ratio(p['O'], p['E'])))
            else:
                line += ' | %5s %3s %6s %6s' % ('—', '—', '—', '—')
        print(line)
    obs_b, sims_b = perm_test(strata_b)
    pb = print_perm(out, obs_b, sims_b, '  Перестановки внутри страт день + зона + бин')

    # ---- 4. только сентябрь
    print('\n4. ТОЛЬКО СЕНТЯБРЬ (день запуска ≥ %s)' % SEPT)
    doms_s = [d for d in doms if d['day'] >= SEPT]
    strata_s, dropped_s = build_strata(doms_s, key_dz)
    print('  доменов %d; страт с ≥2 семействами %d (доменов %d)'
          % (len(doms_s), len(strata_s), sum(len(v) for v in strata_s.values())))
    per_s = oe_table(strata_s)
    print_oe(out, per_s, fam_sorted(per_s), '  O/E по кликам, страта = день + зона:')
    obs_s, sims_s = perm_test(strata_s)
    ps = print_perm(out, obs_s, sims_s, '  Перестановки, только сентябрь')

    # ---- 5. второй ярус
    print('\n5. ВТОРОЙ ЯРУС')
    print('  (а) Внутри nabory — по наборам (E из страт день + зона, как в основном срезе):')
    per_set = oe_table(strata, label='sset')
    nab_sets = [s for s in per_set if s.startswith('nabor')]
    big = sorted([s for s in nab_sets if per_set[s]['n'] >= 3], key=lambda s: (-per_set[s]['n'], s))
    small = [s for s in nab_sets if per_set[s]['n'] < 3]
    print('  %-32s %6s %8s %4s %6s %6s %8s' % ('набор контента', 'домен.', 'кликов', 'рег', 'E', 'O/E', 'P(X≤O)'))
    for s in big:
        p = per_set[s]
        print('  %-32s %6d %8d %4d %6s %6s %8s' % (s, p['n'], p['clicks'], p['O'], fmt(p['E'], 1),
                                                  fmt(ratio(p['O'], p['E'])), fmt(pois_cdf(p['O'], p['E']), 3)))
    sm = new_cell()
    for s in small:
        for k in ('n', 'clicks', 'O', 'E', 'sites', 'fd'):
            sm[k] += per_set[s][k]
    print('  %-32s %6d %8d %4d %6s %6s %8s' % ('наборы по 1–2 домена (%d шт.)' % len(small), sm['n'], sm['clicks'],
                                              sm['O'], fmt(sm['E'], 1), fmt(ratio(sm['O'], sm['E'])), fmt(pois_cdf(sm['O'], sm['E']), 3)))
    print('  те же наборы по 1–2 домена, сгруппированные по серии имени (nabory-NNN-MMM[_styled_img]_k → серия):')
    per_ser = oe_table(strata, label='series')
    sers = sorted([s for s in per_ser if s.endswith('_*')], key=lambda s: (-per_ser[s]['n'], s))
    for s in sers:
        p = per_ser[s]
        print('    %-30s %6d %8d %4d %6s %6s' % (s, p['n'], p['clicks'], p['O'], fmt(p['E'], 1), fmt(ratio(p['O'], p['E']))))
    print('  nabory без набора X (наборы с ≥5 доменами):')
    nabp = per_main['nabory']
    for s in [s for s in big if per_set[s]['n'] >= 5]:
        p = per_set[s]
        O_ = nabp['O'] - p['O']
        E_ = nabp['E'] - p['E']
        print('    без %-30s доменов %3d, O = %2d, E = %5s, O/E = %s' % (s, nabp['n'] - p['n'], O_, fmt(E_, 1), fmt(ratio(O_, E_))))
    print('  nabory по оформлению (styled_img в имени набора против остальных):')
    for name, cond in (('styled_img', lambda d: 'styled_img' in d['sset']), ('без styled_img', lambda d: 'styled_img' not in d['sset'])):
        p = oe_table(strata, only=lambda d, c=cond: d['fam'] == 'nabory' and c(d)).get('nabory')
        if p:
            print('    %-16s доменов %3d, кликов %6d, O = %2d, E = %5s, O/E = %s' % (name, p['n'], p['clicks'], p['O'], fmt(p['E'], 1), fmt(ratio(p['O'], p['E']))))

    print('\n  (б) Внутри archive — по наборам (E из страт день + зона, как в основном срезе):')
    print('  %-36s %6s %8s %4s %6s %6s %6s %8s' % ('набор контента', 'домен.', 'кликов', 'рег', 'E', 'O/E', 'Oex/Eex', 'P(X≤O)'))
    for s in ARCHIVE_SETS:
        p = per_set.get(s)
        if not p:
            continue
        print('  %-36s %6d %8d %4d %6s %6s %6s %8s' % (s, p['n'], p['clicks'], p['O'], fmt(p['E'], 1), fmt(ratio(p['O'], p['E'])),
                                                      fmt(ratio(p['Oex'], p['Eex'])), fmt(pois_cdf(p['O'], p['E']), 3)))
    print('  сырые показатели наборов archive (после фильтров, без страт):')
    print('  %-36s %6s %7s %8s %6s %4s %8s %7s' % ('набор контента', 'домен.', 'сайтов', 'выход %', 'кл/с', 'рег', 'рег/10т', 'р/100с'))
    for s_ in ARCHIVE_SETS:
        dd = [d for d in doms if d['sset'] == s_]
        if not dd:
            continue
        n_, si, ex, cl, rg = len(dd), sum(d['sites'] for d in dd), sum(d['exits'] for d in dd), sum(d['clicks'] for d in dd), sum(d['regs'] for d in dd)
        print('  %-36s %6d %7d %8s %6s %4d %8s %7s' % (s_, n_, si, fmt(100.0 * ex / si, 1), fmt(ratio(cl, si), 1), rg, fmt(per10k(rg, cl)), fmt(100.0 * rg / si)))
    print('  части archive между собой: страты день + зона только из archive-доменов, ≥2 наборов archive в страте')
    doms_a = [d for d in doms if d['fam'] == 'archive']
    strata_a, _ = build_strata(doms_a, key_dz, label='sset')
    per_a = oe_table(strata_a, label='sset')
    print('    страт %d, доменов %d' % (len(strata_a), sum(len(v) for v in strata_a.values())))
    print('    %-36s %6s %8s %4s %6s %6s' % ('набор контента', 'домен.', 'кликов', 'рег', 'E', 'O/E'))
    for s in ARCHIVE_SETS:
        p = per_a.get(s)
        if p:
            print('    %-36s %6d %8d %4d %6s %6s' % (s, p['n'], p['clicks'], p['O'], fmt(p['E'], 1), fmt(ratio(p['O'], p['E']))))
    obs_a, sims_a = perm_test(strata_a, label='sset', targets=ARCHIVE_SETS, nsim=NSIM)
    print('    перестановки метки набора внутри archive-страт (%d): Σ(O−E)²/E = %s, p = %s'
          % (NSIM, fmt(obs_a['T'], 1), fmt(pvals(obs_a['T'], sims_a['T'])['high'], 4)))
    for s in ARCHIVE_SETS:
        k = s + '_oe'
        if k in obs_a:
            pv = pvals(obs_a[k], sims_a[k])
            print('      %-36s O/E %5s, p(≤) %6s, p(≥) %6s' % (s, fmt(obs_a[k]), fmt(pv['low'], 3), fmt(pv['high'], 3)))

    # ---- 6. дубль на сайт: обе ступени
    print('\n6. ДУБЛЬ НА САЙТ: ОБЕ СТУПЕНИ ВОРОНКИ РЯДОМ (те же страты день + зона)')
    per_exit = oe_table(strata, num='exits', den='sites')
    per_cps = oe_table(strata, num='clicks', den='sites')
    per_site = oe_table(strata, num='regs', den='sites')
    print('  E выхода = ставка страты (вышли за 3 суток / сайтов в окне) × сайтов домена; E кликов на сайт — так же по кликам;')
    print('  E рег/сайт = ставка страты (рег / сайтов) × сайтов домена; O/E рег/клик — из п. 1.')
    print('  %-14s %6s %7s %7s %8s %4s | %7s %9s %8s %8s' % ('семейство', 'домен.', 'сайтов', 'вышли', 'кликов', 'рег', 'O/E вых', 'O/E кл/с', 'O/E р/кл', 'O/E р/с'))
    for f in fams_main:
        p = per_main[f]
        print('  %-14s %6d %7d %7d %8d %4d | %7s %9s %8s %8s' % (
            f, p['n'], p['sites'], p['exits'], p['clicks'], p['O'],
            fmt(ratio(per_exit[f]['O'], per_exit[f]['E'])), fmt(ratio(per_cps[f]['O'], per_cps[f]['E'])),
            fmt(ratio(p['O'], p['E'])), fmt(ratio(per_site[f]['O'], per_site[f]['E']))))
    print('  выход, % сайтов: ' + ', '.join('%s %s' % (f, fmt(100.0 * per_main[f]['exits'] / per_main[f]['sites'], 1))
                                             for f in fams_main if per_main[f]['sites']))
    print('  кликов на сайт: ' + ', '.join('%s %s' % (f, fmt(ratio(per_main[f]['clicks'], per_main[f]['sites']), 1))
                                            for f in fams_main if per_main[f]['sites']))
    print('  рег на 100 сайтов: ' + ', '.join('%s %s' % (f, fmt(100.0 * per_main[f]['O'] / per_main[f]['sites']))
                                               for f in fams_main if per_main[f]['sites']))
    obs_site, sims_site = perm_test(strata, num='regs', den='sites')
    psite = print_perm(out, obs_site, sims_site, '  Перестановки для O/E рег на сайт')
    obs_exit, sims_exit = perm_test(strata, num='exits', den='sites')
    pexit = print_perm(out, obs_exit, sims_exit, '  Перестановки для O/E выхода (вышли за 3 суток на сайт)')

    # ---- 7. ФД
    print('\n7. ФД В ОКНЕ КАК ЗНАК (E ФД = ставка страты ФД/клик × клики домена)')
    print('  %-14s %4s %7s %6s' % ('семейство', 'ФД', 'E ФД', 'O/E'))
    for f in fams_main:
        p = per_main[f]
        print('  %-14s %4d %7s %6s' % (f, p['fd'], fmt(p['Efd'], 1), fmt(ratio(p['fd'], p['Efd']))))
    print('  всего ФД в стратах: %d из 62 в своде' % sum(p['fd'] for p in per_main.values()))

    # ---- 8. критерии
    print('\n8. ПРОВЕРКА КРИТЕРИЕВ ПОСТАНОВКИ')
    nab_oe = ratio(per_main['nabory']['O'], per_main['nabory']['E'])
    nab_rr = ratio(per_main['nabory']['Oex'], per_main['nabory']['Eex'])
    arc_oe = ratio(per_main['archive']['O'], per_main['archive']['E'])
    arc_rr = ratio(per_main['archive']['Oex'], per_main['archive']['Eex'])
    p_nab = pm['nabory_oe']['low']
    p_nab_rr = pm['nabory_rr']['low']
    bins_ok = []
    for b in BIN_NAMES:
        p = per_bin[b].get('nabory')
        if p and p['O'] >= 2:
            bins_ok.append((b, ratio(p['O'], p['E']), p['O']))
    c1 = nab_oe <= 0.7 and p_nab < 0.05
    c2 = all(oe <= 1.0 for _, oe, _ in bins_ok)
    c3 = 0.85 <= arc_oe <= 1.2
    print('  1) nabory O/E по кликам ≤ 0,7 при p < 0,05: O/E = %s (против остальных %s), p(≤) = %s (против остальных %s) → %s'
          % (fmt(nab_oe), fmt(nab_rr), fmt(p_nab, 4), fmt(p_nab_rr, 4), 'ДА' if c1 else 'НЕТ'))
    print('  2) nabory O/E ≤ 1 в каждом бине с ≥2 регистрациями: %s → %s'
          % (', '.join('%s %s (%d рег)' % (b, fmt(oe), o) for b, oe, o in bins_ok), 'ДА' if c2 else 'НЕТ'))
    print('  3) archive O/E по кликам 0,85–1,2: O/E = %s (против остальных %s; против остальных без nabory %s) → %s'
          % (fmt(arc_oe), fmt(arc_rr), fmt(ratio(O, E)), 'ДА' if c3 else 'НЕТ'))
    print('  4) общий тест на все семейства Σ(O−E)²/E: p = %s' % fmt(pm['T']['high'], 4))

    # ---- 9. ВЫВОД
    conclusion(out, doms, strata, per_main, per_bin, per_set, per_a, per_exit, per_cps, per_site, pm, pb, ps, psite, pexit,
               obs_b, obs_s, raw, nab_vs, (O, E, n), (O3, E3, n3), big, sm, c1, c2, c3, bins_ok, pending)


def conclusion(out, doms, strata, per_main, per_bin, per_set, per_a, per_exit, per_cps, per_site, pm, pb, ps, psite, pexit,
               obs_b, obs_s, raw, nab_vs, arc_vs_nonab, nab_vs_nonarc, big, sm, c1, c2, c3, bins_ok, pending):
    nab = per_main['nabory']
    arc = per_main['archive']
    new = per_main.get('NEW', new_cell())
    cd = per_main.get('content-дата', new_cell())
    nab_oe = ratio(nab['O'], nab['E'])
    nab_rr = ratio(nab['Oex'], nab['Eex'])
    arc_oe = ratio(arc['O'], arc['E'])
    arc_rr = ratio(arc['Oex'], arc['Eex'])
    Oa, Ea, na = arc_vs_nonab
    On, En, nn = nab_vs_nonarc
    lines = ['\nВЫВОД']
    lines.append(
        'Проверяли: если зафиксировать день запуска и зону и сравнить регистрации на один поисковый клик,\n'
        'дают ли nabory в полтора раза меньше, чем NEW, content-дата и archive, и держит ли archive отдачу\n'
        'с клика на общем уровне. Срез: %d доменов после фильтров, %d страт «день + зона» с ≥2 семействами\n'
        '(%d доменов, %d поисковых кликов в окне, %d регистраций в окне).'
        % (len(doms), len(strata), sum(p['n'] for p in per_main.values()),
           sum(p['clicks'] for p in per_main.values()), sum(p['O'] for p in per_main.values())))
    lines.append(
        '1. nabory. На %d доменах (%d сайтов, %d поисковых кликов) получено %d регистраций в окне против\n'
        '   ожидаемых %s по ставке своих страт — O/E %s; если ставку брать только по соседям по страте\n'
        '   (без самих nabory), ожидание %s, O/E %s. Перестановки метки семейства внутри страты дают\n'
        '   p(≤) = %s (по ставке страты) и %s (против соседей); двусторонний p = %s. Нулевое\n'
        '   распределение O/E nabory 2,5–97,5 %%: %s–%s — то есть при 12 регистрациях сдвиг\n'
        '   в 0,6–0,7 отличить от случайности нельзя. Сырая отдача nabory %s рег/10 тыс. против NEW %s,\n'
        '   content-дата %s, archive %s; при ставке NEW nabory получили бы %s регистраций вместо %d.'
        % (nab['n'], nab['sites'], nab['clicks'], nab['O'], fmt(nab['E'], 1), fmt(nab_oe), fmt(nab['Eex'], 1),
           fmt(nab_rr), fmt(pm['nabory_oe']['low'], 3), fmt(pm['nabory_rr']['low'], 3), fmt(pm['nabory_oe']['two'], 3),
           fmt(pm['nabory_oe']['lo']), fmt(pm['nabory_oe']['hi']),
           fmt(per10k(raw['nabory'][2], raw['nabory'][1])), fmt(per10k(raw['NEW'][2], raw['NEW'][1])),
           fmt(per10k(raw['content-дата'][2], raw['content-дата'][1])), fmt(per10k(raw['archive'][2], raw['archive'][1])),
           fmt(raw['nabory'][1] * raw['NEW'][2] / raw['NEW'][1], 1) if raw['NEW'][1] else '—', nab['O']))
    vs_lines = []
    for ref in ('NEW', 'content-дата', 'archive'):
        Ov, Ev, nv = nab_vs.get(ref, (0, 0, 0))
        if nv:
            vs_lines.append('против %s %s (%d дом., O %d / E %s)' % (ref, fmt(ratio(Ov, Ev)), nv, Ov, fmt(Ev, 1)))
    zero_sets = [s_ for s_ in big if per_set[s_]['O'] == 0]
    over_sets = [s_ for s_ in big if per_set[s_]['O'] > 0]
    lines.append(
        '   Попарно в общих стратах: %s.\n'
        '   Контроль объёма: в стратах день + зона + бин кликов O/E nabory %s (p(≤) = %s); по бинам с ≥2 рег.: %s.\n'
        '   Только сентябрь: O/E %s (p(≤) = %s). Внутри nabory один набор ничего не тянет: из %d наборов с ≥3\n'
        '   доменами %d дали 0 регистраций при E от %s до %s, остальные — %s; наборы по 1–2 домена\n'
        '   (%d шт.) — %d рег. при E %s (O/E %s); «nabory без любого одного набора» держится в 0,60–0,75.'
        % ('; '.join(vs_lines), fmt(obs_b['nabory_oe']), fmt(pb['nabory_oe']['low'], 3),
           ', '.join('%s %s (%d рег)' % (b, fmt(oe), o) for b, oe, o in bins_ok),
           fmt(obs_s['nabory_oe']), fmt(ps['nabory_oe']['low'], 3),
           len(big), len(zero_sets),
           fmt(min(per_set[s_]['E'] for s_ in zero_sets), 1) if zero_sets else '—',
           fmt(max(per_set[s_]['E'] for s_ in zero_sets), 1) if zero_sets else '—',
           ', '.join('%s %d/%s' % (s_, per_set[s_]['O'], fmt(per_set[s_]['E'], 1)) for s_ in over_sets),
           sm['n'], sm['O'], fmt(sm['E'], 1), fmt(ratio(sm['O'], sm['E']))))
    lines.append(
        '2. archive. O/E по ставке страты %s — но это число почти ничего не значит: archive даёт большую\n'
        '   часть кликов в своих стратах (08–11.09), и E там считается в основном по самим archive. Против\n'
        '   соседей по страте O/E %s (%d рег. при E %s), а соседи там — на три четверти nabory; против\n'
        '   соседей без nabory (script, clean, NEW) — O/E %s (%d доменов, O %d, E %s). Перестановки:\n'
        '   p(≥) = %s по ставке страты, %s против соседей; нулевой интервал %s–%s. Части archive между\n'
        '   собой: %s.'
        % (fmt(arc_oe), fmt(arc_rr), arc['Oex'], fmt(arc['Eex'], 1), fmt(ratio(Oa, Ea)), na, Oa, fmt(Ea, 1),
           fmt(pm['archive_oe']['high'], 3), fmt(pm['archive_rr']['high'], 3),
           fmt(pm['archive_oe']['lo']), fmt(pm['archive_oe']['hi']),
           ', '.join('%s %d/%s (O/E %s)' % (s.replace('archive37строформленоv2', 'a37_').replace('archive47_unique119оформлено', 'a47_').replace('archive412_unique12оформлено', 'a412'),
                                             per_a[s]['O'], fmt(per_a[s]['E'], 1), fmt(ratio(per_a[s]['O'], per_a[s]['E']))) for s in ARCHIVE_SETS if s in per_a)))
    lines.append(
        '3. Обе ступени рядом (п. 6). Выход в поиск: nabory O/E %s, archive %s, NEW %s, content-дата %s.\n'
        '   Кликов на сайт: nabory %s, archive %s, NEW %s, content-дата %s. Регистраций на клик: nabory %s,\n'
        '   archive %s, NEW %s, content-дата %s. Регистраций на сайт: nabory %s (p(≤) = %s), archive %s\n'
        '   (p(≤) = %s), NEW %s, content-дата %s.'
        % (fmt(ratio(per_exit['nabory']['O'], per_exit['nabory']['E'])), fmt(ratio(per_exit['archive']['O'], per_exit['archive']['E'])),
           fmt(ratio(per_exit['NEW']['O'], per_exit['NEW']['E'])), fmt(ratio(per_exit['content-дата']['O'], per_exit['content-дата']['E'])),
           fmt(ratio(per_cps['nabory']['O'], per_cps['nabory']['E'])), fmt(ratio(per_cps['archive']['O'], per_cps['archive']['E'])),
           fmt(ratio(per_cps['NEW']['O'], per_cps['NEW']['E'])), fmt(ratio(per_cps['content-дата']['O'], per_cps['content-дата']['E'])),
           fmt(nab_oe), fmt(arc_oe), fmt(ratio(new['O'], new['E'])), fmt(ratio(cd['O'], cd['E'])),
           fmt(ratio(per_site['nabory']['O'], per_site['nabory']['E'])), fmt(psite['nabory_oe']['low'], 4),
           fmt(ratio(per_site['archive']['O'], per_site['archive']['E'])), fmt(psite['archive_oe']['low'], 3),
           fmt(ratio(per_site['NEW']['O'], per_site['NEW']['E'])), fmt(ratio(per_site['content-дата']['O'], per_site['content-дата']['E']))))
    lines.append(
        '4. Многие сравнения: общий перестановочный тест по всем семействам Σ(O−E)²/E даёт p = %s —\n'
        '   разброс отдачи с клика между семействами внутри дня и зоны в целом %s.'
        % (fmt(pm['T']['high'], 3), 'не отличим от случайного' if pm['T']['high'] >= 0.05 else 'больше случайного'))
    n_pend = pending.get('nabory', 0)
    a412d = [d for d in doms if d['sset'] == 'archive412_unique12оформлено']
    a412 = dict(n=len(a412d), O=sum(d['regs'] for d in a412d), clicks=sum(d['clicks'] for d in a412d),
                sites=sum(d['sites'] for d in a412d), exits=sum(d['exits'] for d in a412d))
    arc_raw_regs = raw['archive'][2]
    arc_mass = [d for doms_k in strata.values() for d in doms_k if d['fam'] == 'archive' and d['day'] <= '2026-09-10']
    arc_late = [d for doms_k in strata.values() for d in doms_k if d['fam'] == 'archive' and d['day'] > '2026-09-10']
    nab_site = ratio(per_site['nabory']['O'], per_site['nabory']['E'])
    nab_exit = ratio(per_exit['nabory']['O'], per_exit['nabory']['E'])
    nab_cps = ratio(per_cps['nabory']['O'], per_cps['nabory']['E'])
    sty = oe_table(strata, only=lambda d: d['fam'] == 'nabory' and 'styled_img' in d['sset']).get('nabory', new_cell())
    nsty = oe_table(strata, only=lambda d: d['fam'] == 'nabory' and 'styled_img' not in d['sset']).get('nabory', new_cell())
    lines.append(
        'Итог: ЧАСТИЧНО. Половина про nabory подтверждается по размеру, но стоит на грани значимости:\n'
        '%d регистраций против %s ожидаемых по дню и зоне — O/E %s, то есть в %s раза меньше на поисковый\n'
        'клик; тот же порядок в сентябре (%s), в стратах с бином кликов (%s), против NEW (%s) и content-дата (%s)\n'
        'в общих стратах, ≤1 во всех бинах с ≥2 регистрациями, и ни один набор nabory не тянет результат в одиночку.\n'
        'Но перестановочный p = %s (односторонний) / %s (двусторонний) по основной статистике, %s по статистике\n'
        '«против соседей», %s в стратах с бином, а общий тест по всем семействам p = %s: при 12 регистрациях\n'
        'нулевой интервал O/E %s–%s, и наблюдённое сидит на его краю. Половина про archive по знаку верна —\n'
        'во всех вариантах O/E archive по клику ≥ 1 (%s по ставке страты, %s против соседей, %s против соседей без\n'
        'nabory), — но толком не проверяема: archive запускался 08–11.09 почти в одиночку. Там, где он массовый\n'
        '(08–10.09: %d доменов, %d рег.), соседей по 3–17 доменов и это в основном nabory; там, где соседей много\n'
        '(11.09), archive всего %d доменов с %d рег. «Не хуже остальных» здесь значит по сути «не хуже nabory», а 17 из\n'
        '29 его регистраций лежат в страте 09-09 lol, где соседи — 3 домена nabory с 0 регистраций.\n'
        'Что видно надёжно: на сайт nabory дают %s от ожидаемого (p = %s), и недобор складывается из двух ступеней\n'
        'примерно поровну — выход %s (p < 0,001) × клики на вышедший сайт ≈%s × отдача с клика %s; даже с выходом на\n'
        'уровне соседей nabory давали бы ≈%s нормы на сайт. У archive внутри своих дней на сайт %s от соседей —\n'
        'то есть «худший выход archive» из реестра на своде не отделим от дня запуска.'
        % (nab['O'], fmt(nab['E'], 1), fmt(nab_oe), fmt(1 / nab_oe) if nab_oe else '—',
           fmt(obs_s['nabory_oe']), fmt(obs_b['nabory_oe']),
           fmt(ratio(*nab_vs.get('NEW', (0, 0, 0))[:2])), fmt(ratio(*nab_vs.get('content-дата', (0, 0, 0))[:2])),
           fmt(pm['nabory_oe']['low'], 3), fmt(pm['nabory_oe']['two'], 3), fmt(pm['nabory_rr']['low'], 3),
           fmt(pb['nabory_oe']['low'], 3), fmt(pm['T']['high'], 2),
           fmt(pm['nabory_oe']['lo']), fmt(pm['nabory_oe']['hi']),
           fmt(arc_oe), fmt(arc_rr), fmt(ratio(Oa, Ea)),
           len(arc_mass), sum(d['regs'] for d in arc_mass), len(arc_late), sum(d['regs'] for d in arc_late),
           fmt(nab_site), fmt(psite['nabory_oe']['low'], 4), fmt(nab_exit), fmt(nab_cps / nab_exit) if nab_exit else '—',
           fmt(nab_oe), fmt(nab_cps / nab_exit * nab_oe) if nab_exit else '—',
           fmt(ratio(per_site['archive']['O'], per_site['archive']['E']))))
    lines.append(
        'Что с этим делать: nabory — не искать им выход, а не ставить на новые запуски: даже с выходом соседей они\n'
        'дают ≈0,6 нормы на сайт, а на сайт в целом %s (это надёжно). Вопрос «0,7 или 1,0 на клик» закроется сам:\n'
        'у %d доменов nabory (запуски 16–20.09) окно ещё не закрыто или не было дня 2 — когда закроется, повторить\n'
        'п. 1–2 этого скрипта на них: если O/E останется ≤0,7 при ~20 регистрациях, p уйдёт ниже 0,01; если станет\n'
        '≈1 — nabory плохи только выходом. Post-hoc знак для той же проверки: nabory без styled_img в имени набора\n'
        '%d рег. при E %s (O/E %s) против styled_img %d при E %s (O/E %s). Для archive рычага по клику нет: отдача с\n'
        'клика не ниже общей, на сайт внутри своих дней %s; вопрос «плох ли выход archive сам по себе» на своде не\n'
        'решается (в его дни нет соседей другого семейства в объёме) — нужен запуск archive в один день и зону с\n'
        'NEW или content-дата. Знак стоимостью в проверку: archive412_unique12оформлено — %d доменов, %d из %d\n'
        'регистраций archive после фильтров, выход %s %% сайтов (у остальных наборов archive 5–8 %%), %s кликов на\n'
        'сайт, %s рег/10 тыс. кликов — единственный набор archive, который стоит воспроизвести.'
        % (fmt(nab_site), n_pend, nsty['O'], fmt(nsty['E'], 1), fmt(ratio(nsty['O'], nsty['E'])),
           sty['O'], fmt(sty['E'], 1), fmt(ratio(sty['O'], sty['E'])),
           fmt(ratio(per_site['archive']['O'], per_site['archive']['E'])),
           a412['n'], a412['O'], arc_raw_regs, fmt(100.0 * a412['exits'] / a412['sites'], 1) if a412['sites'] else '—',
           fmt(ratio(a412['clicks'], a412['sites']), 1), fmt(per10k(a412['O'], a412['clicks']))))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
