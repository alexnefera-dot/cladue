#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №13 («валюта» домена: ширина охвата при равных кликах + излишек выхода).
Угол: ТЕНИ (конфаундинг). Проверяем, не является ли эффект тенью
  (1) объёма кликов (регистрации на клик нелинейно падают с кликами — E ∝ кликам заведомо
      занижает ожидание у малокликовых «широких» и завышает у многокликовых «магнитов»);
  (2) зоны (40 из 58 пулов смешаны по зонам; .buzz почти без денег, .casino — наоборот);
  (3) периода / набора («КОНТЕНТ НЕ ЗАПИСАН» = август, сцеплен с датой);
  (4) выбросов и нескольких доменов-рекордсменов (джекнайф);
  (5) бота/«прочих» кликов как эффекта знаменателя.
Жёсткая страта: набор контента + день запуска + зона (при возможности + блок часа),
плюс узкие бины кликов (×1.25 по логарифму) и парные сравнения с жёстким допуском по кликам.
Только stdlib.
"""
import csv, os, sys, math, random, collections

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod')
OUT = os.path.join(OUT_DIR, 'w13_teni.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
NPERM = 5000
SEED = 1
TNAME = ('нижний T1 (широкий)', 'средний T2', 'верхний T3 (магниты)')


class Tee:
    def __init__(self, path):
        self.f = open(path, 'w', encoding='utf-8')
    def write(self, s):
        sys.__stdout__.write(s); self.f.write(s)
    def flush(self):
        sys.__stdout__.flush(); self.f.flush()


def p(*a): print(*a)
def line(ch='=', n=112): p(ch * n)
def to_int(x):
    try: return int(float(x))
    except (TypeError, ValueError): return 0
def to_float(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0
def fr(x, d=2):
    if x is None: return 'н/д'
    if x == float('inf'): return '∞'
    return f'{x:.{d}f}'


class Dom:
    __slots__ = ('domain','zone','day','month','content','hour','hb','sites','exits','sws',
                 'clicks','allclicks','bots','other','regs','fd','exitpct')
    def __init__(self, r):
        self.domain = r['домен']; self.zone = r['зона']; self.day = r['день запуска']
        self.month = 'август' if r['день запуска'] < '2026-09' else 'сентябрь'
        self.content = r['набор контента']
        self.hour = to_int(r['час запуска']); self.hb = r['блок часа']
        self.sites = to_int(r['сайтов в окне']); self.exits = to_int(r['вышли за 3 суток'])
        self.sws = to_int(r['сайтов с поиском'])
        self.clicks = to_int(r['кликов из поиска в окне'])
        self.allclicks = to_int(r['кликов всего в окне']); self.bots = to_int(r['ботов в окне'])
        self.other = max(0, self.allclicks - self.clicks - self.bots)
        self.regs = to_int(r['регистраций в окне 3 суток']); self.fd = to_int(r['ФД в окне 3 суток'])
        self.exitpct = self.exits / self.sites * 100 if self.sites else 0.0
    @property
    def conc(self):
        return self.clicks / self.exits if self.exits else None


def load():
    rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
    ex = collections.Counter(); keep = []; noc = []; outl = []
    for r in rows:
        if r['окно закрыто'] != 'да': ex['окно не закрыто'] += 1; continue
        if r['дней'] == '1': ex['дней = 1'] += 1; continue
        d = Dom(r)
        if d.domain in OUTLIERS: outl.append(d); ex['выбросы 3615/3286'] += 1; continue
        (noc if d.content == NOCONTENT else keep).append(d)
    return len(rows), ex, keep, noc, outl


def make_pools(doms, keyfn, min_n=4, min_reg=1):
    pl = collections.defaultdict(list)
    for d in doms: pl[keyfn(d)].append(d)
    n_all = len(pl)
    out = {k: v for k, v in pl.items() if len(v) >= min_n and sum(x.regs for x in v) >= min_reg}
    return out, n_all


def terciles(doms, key):
    """Конвенция тестировщика: метка = i*3//n по возрастанию key (ничьи — по вышедшим, затем имя)."""
    s = sorted(doms, key=lambda d: (key(d), d.exits, d.domain))
    n = len(s)
    return {d.domain: i * 3 // n for i, d in enumerate(s)}


def terciles_alt(doms, key):
    """Альтернативная развёрстка остатка (остаток — верхнему терцилю)."""
    s = sorted(doms, key=lambda d: (key(d), d.exits, d.domain))
    n = len(s); c1 = n // 3; c2 = 2 * n // 3
    return {d.domain: (0 if i < c1 else (1 if i < c2 else 2)) for i, d in enumerate(s)}


# ---------------------------------------------------------------------------------------------
# O/E по терцилям внутри страты с произвольным весом; перестановка меток внутри страты
# ---------------------------------------------------------------------------------------------
def oe_terciles(pools, keyfn, wfn, title, note='', nperm=NPERM, stat='low/high',
                keep_zero=True, tfn=None, ofn=None):
    tfn = tfn or terciles
    ofn = ofn or (lambda d: d.regs)
    recs = []
    for k, doms in pools.items():
        use = [d for d in doms if d.exits > 0 and (keep_zero or d.clicks > 0)]
        if len(use) < 3: continue
        W = sum(wfn(d) for d in use); O = sum(ofn(d) for d in use)
        if W <= 0 or O <= 0: continue
        lab = tfn(use, keyfn)
        recs.append([(d, lab[d.domain], wfn(d), ofn(d), O / W) for d in use])
    if not recs:
        p(f'  {title}: данных нет.'); return None
    agg = [collections.Counter() for _ in range(3)]
    for cell in recs:
        for d, l, w, y, rate in cell:
            a = agg[l]; a['n'] += 1; a['O'] += y; a['E'] += w * rate
            a['cl'] += d.clicks; a['ex'] += d.exits; a['fd'] += d.fd; a['st'] += d.sites
    p(f'\n  {title}')
    if note: p(f'  {note}')
    p('  терциль                доменов   вышли     кликов   рег   ФД   рег/10т.кл  рег/100выш      O       E    O/E')
    for i in range(3):
        a = agg[i]
        r10 = a['O'] / a['cl'] * 10000 if a['cl'] else 0
        r100 = a['O'] / a['ex'] * 100 if a['ex'] else 0
        oe = a['O'] / a['E'] if a['E'] > 0 else float('nan')
        p(f"  {TNAME[i]:<22}{a['n']:>5}{a['ex']:>8}{a['cl']:>11}{a['O']:>6}{a['fd']:>5}{r10:>12.2f}{r100:>12.2f}"
          f"{a['O']:>8}{a['E']:>8.1f}{oe:>7.2f}")
    def st(A):
        o = [A[i]['O'] for i in range(3)]; e = [A[i]['E'] for i in range(3)]
        if stat == 'low/high':
            if e[0] <= 0 or e[2] <= 0 or o[2] == 0: return None
            return (o[0] / e[0]) / (o[2] / e[2])
        else:
            return o[2] / e[2] if e[2] > 0 else None
    obs = st(agg)
    random.seed(SEED); ge = 0; ok = 0
    for _ in range(nperm):
        A = [collections.Counter() for _ in range(3)]
        for cell in recs:
            labs = [c[1] for c in cell]; random.shuffle(labs)
            for (d, _l, w, y, rate), nl in zip(cell, labs):
                A[nl]['O'] += y; A[nl]['E'] += w * rate
        v = st(A)
        if v is not None:
            ok += 1
            if v >= obs: ge += 1
    pv = ge / ok if ok else float('nan')
    nm = 'O/E(T1)/O/E(T3)' if stat == 'low/high' else 'O/E(T3)'
    p(f'  {nm} = {fr(obs)}; перестановка меток внутри страты {nperm}: p(≥) = {pv:.4f}, двусторонний p = {min(1.0, 2*min(pv,1-pv)):.4f}')
    return obs, pv, agg


# ---------------------------------------------------------------------------------------------
# Пуассоновская модель λ = c_страта × кликов^α × вышедших^β
# ---------------------------------------------------------------------------------------------
def fit_ab(pools, fix_alpha=None, fix_beta=None, grid=None):
    cells = []
    for k, doms in pools.items():
        use = [d for d in doms if d.exits > 0 and d.clicks > 0]
        O = sum(d.regs for d in use)
        if len(use) < 3 or O == 0: continue
        cells.append(use)
    if grid is None:
        grid = [i / 40 for i in range(-20, 81)]   # -0.50 .. 2.00 шагом 0.025
    def ll(a, b):
        s = 0.0
        for use in cells:
            W = 0.0
            for d in use: W += (d.clicks ** a) * (d.exits ** b)
            if W <= 0: continue
            O = 0
            for d in use:
                if d.regs:
                    s += d.regs * (a * math.log(d.clicks) + b * math.log(d.exits))
                    O += d.regs
            s -= O * math.log(W)
        return s
    best = None
    A = [fix_alpha] if fix_alpha is not None else grid
    B = [fix_beta] if fix_beta is not None else grid
    for a in A:
        for b in B:
            v = ll(a, b)
            if best is None or v > best[0]: best = (v, a, b)
    return best, ll, cells


def profile_ci(ll, ahat, bhat, llmax, grid, which='b'):
    lo = hi = None
    for x in grid:
        if which == 'b':
            v = max(ll(a, x) for a in [ahat - .2, ahat - .1, ahat, ahat + .1, ahat + .2, ahat + .4])
        else:
            v = max(ll(x, b) for b in [bhat - .2, bhat - .1, bhat, bhat + .1, bhat + .2, bhat + .4])
        if v >= llmax - 1.92:
            if lo is None: lo = x
            hi = x
    return lo, hi


# ---------------------------------------------------------------------------------------------
# Пары внутри страты
# ---------------------------------------------------------------------------------------------
def pairs_of(pools, cr, xr):
    pairs = []
    for k, doms in pools.items():
        s = sorted([d for d in doms if d.exits > 0 and d.clicks > 0], key=lambda d: (d.clicks, d.domain))
        i = 0
        while i < len(s) - 1:
            a, b = s[i], s[i + 1]
            if b.clicks / a.clicks <= cr and max(a.exits, b.exits) / min(a.exits, b.exits) >= xr:
                pairs.append(((a, b) if a.exits > b.exits else (b, a), k)); i += 2
            else: i += 1
    return pairs


def pair_report(pairs, label, show=True, nperm=NPERM):
    n = len(pairs)
    if n == 0:
        if show: p(f'  {label}: пар нет.')
        return None
    ow = sum(w.regs for (w, _), _ in pairs); on = sum(nw.regs for (_, nw), _ in pairs)
    cw = sum(w.clicks for (w, _), _ in pairs); cn = sum(nw.clicks for (_, nw), _ in pairs)
    xw = sum(w.exits for (w, _), _ in pairs); xn = sum(nw.exits for (_, nw), _ in pairs)
    wins = sum(1 for (w, nw), _ in pairs if w.regs > nw.regs)
    los = sum(1 for (w, nw), _ in pairs if w.regs < nw.regs)
    anyreg = sum(1 for (w, nw), _ in pairs if w.regs + nw.regs > 0)
    def rr(o1, c1, o2, c2):
        if c1 <= 0 or c2 <= 0: return None
        if o2 == 0: return float('inf') if o1 > 0 else 1.0
        return (o1 / c1) / (o2 / c2)
    obs = rr(ow, cw, on, cn)
    random.seed(SEED); ge = 0
    for _ in range(nperm):
        o1 = c1 = o2 = c2 = 0
        for (w, nw), _ in pairs:
            if random.random() < .5: w, nw = nw, w
            o1 += w.regs; c1 += w.clicks; o2 += nw.regs; c2 += nw.clicks
        v = rr(o1, c1, o2, c2)
        if v is not None and v >= obs: ge += 1
    m = wins + los
    ps = min(1.0, 2 * sum(math.comb(m, j) for j in range(min(wins, los) + 1)) / 2 ** m) if m else None
    if show:
        p(f'  {label}: пар {n} (доменов {2*n}), с ≥1 рег. {anyreg}; вышли {xw} vs {xn}, кликов {cw} vs {cn}; '
          f'рег {ow} vs {on} ({ow/cw*10000 if cw else 0:.2f} vs {on/cn*10000 if cn else 0:.2f} на 10 тыс.); '
          f'отношение {fr(obs)}; p(перест.) = {ge/nperm:.4f}; знаки {wins}:{los}, знаковый p = {fr(ps,4) if ps is not None else "н/д"}')
    return dict(n=n, ow=ow, on=on, cw=cw, cn=cn, obs=obs, pperm=ge / nperm, wins=wins, los=los, ps=ps)



def fit_block(name, P, out=True):
    """Оценка λ = c(страта) × кликов^α × вышедших^β + профильный интервал для β."""
    grid = [i / 40 for i in range(-20, 81)]
    (llmax, a, b), ll, cells = fit_ab(P)
    (ll0, a0, _), _, _ = fit_ab(P, fix_beta=0.0)
    lo, hi = profile_ci(ll, a, b, llmax, grid, 'b')
    ndom = sum(len(c) for c in cells); nreg = sum(d.regs for c in cells for d in c)
    if out:
        p(f'  {name:<46} доменов {ndom:>4}, рег {nreg:>4} | α(β=0) {a0:5.2f} | α {a:5.2f}, β {b:5.2f} '
          f'[{lo:5.2f}; {hi:5.2f}] | χ²(β=0) {2*(llmax-ll0):6.2f}')
    return a0, a, b, lo, hi, 2 * (llmax - ll0), ndom, nreg


def main():
    total, ex, keep, noc, outl = load()
    line()
    p('Контрпроверка гипотезы №13. ТЕНИ: объём кликов, зона, период/набор, час, выбросы, знаменатель.')
    p(f'Источник: analysis/export/svod_domenov_21.09.csv; перестановок {NPERM}, random.seed({SEED}).')
    line()
    p(f'Строк: {total}. Исключено: ' + ', '.join(f'{k} {v}' for k, v in ex.items()) +
      f'. Основной набор {len(keep)}, «{NOCONTENT}» {len(noc)}.')

    key_pool = lambda d: (d.content, d.day)
    key_hard = lambda d: (d.content, d.day, d.zone)
    key_hard_h = lambda d: (d.content, d.day, d.zone, d.hb)

    P_pool, n_pool_all = make_pools(keep, key_pool)
    P_hard, n_hard_all = make_pools(keep, key_hard)
    P_hardh, n_hardh_all = make_pools(keep, key_hard_h)
    P_noc, _ = make_pools(noc, lambda d: (d.day,))
    P_noc_hard, _ = make_pools(noc, lambda d: (d.day, d.zone))
    P_all, _ = make_pools(keep + noc, lambda d: (d.content, d.day, d.zone))

    def descr(nm, P, nall):
        dd = [d for v in P.values() for d in v]
        p(f'  {nm}: пулов {len(P)} (до отбора {nall}), доменов {len(dd)}, кликов {sum(d.clicks for d in dd)}, '
          f'вышедших {sum(d.exits for d in dd)}, регистраций {sum(d.regs for d in dd)}, ФД {sum(d.fd for d in dd)}')
    p('\nСтраты (≥4 доменов и ≥1 регистрации):')
    descr('мягкая тестировщика: набор+день', P_pool, n_pool_all)
    descr('ЖЁСТКАЯ: набор+день+зона', P_hard, n_hard_all)
    descr('ЖЁСТЧЕ: набор+день+зона+блок часа', P_hardh, n_hardh_all)
    descr('«КОНТЕНТ НЕ ЗАПИСАН»: день', P_noc, 0)
    descr('«КОНТЕНТ НЕ ЗАПИСАН»: день+зона', P_noc_hard, 0)
    mixed = sum(1 for v in P_pool.values() if len(set(d.zone for d in v)) > 1)
    p(f'  Пулов «набор+день» со смесью зон: {mixed} из {len(P_pool)} — зона в мягкой страте НЕ зафиксирована.')
    dd = [d for v in P_pool.values() for d in v]
    z0 = [d for d in dd if d.exits > 0 and d.clicks == 0]
    p(f'  В мягкой страте доменов с вышедшими > 0, но БЕЗ поисковых кликов в окне: {len(z0)} '
      f'(регистраций у них {sum(d.regs for d in z0)}). У них «концентрация» = 0, и тестировщик кладёт их')
    p('  в нижний (широкий) терциль с нулевым ожиданием — они бесплатно занимают места в T1.')

    line()
    p('ТЕНЬ 1. НЕЛИНЕЙНОСТЬ ПО КЛИКАМ: E ∝ кликам смещает O/E против «магнитов»')
    line()
    s2 = sorted([d for d in dd if d.clicks > 0 and d.exits > 0], key=lambda d: d.clicks)
    q = len(s2) // 5
    p(f'  Квинтили доменов по кликам в окне (мягкая страта, {len(s2)} доменов с кликами):')
    p('  квинтиль   доменов  медиана кликов      кликов      рег   рег/10 тыс. кликов   вышедших   кликов/вышедший')
    for i in range(5):
        part = s2[i*q:(i+1)*q] if i < 4 else s2[4*q:]
        cl = sum(d.clicks for d in part); rg = sum(d.regs for d in part); xx = sum(d.exits for d in part)
        p(f'  Q{i+1:<9}{len(part):>7}{part[len(part)//2].clicks:>17}{cl:>13}{rg:>9}{rg/cl*10000:>20.2f}{xx:>12}{cl/xx:>18.1f}')
    p('  Отдача на клик падает от Q1 к Q5 в ~4,6 раза, а концентрация (кликов/вышедший) монотонно растёт:')
    p('  «терциль концентрации» — это в значительной мере «терциль объёма кликов» в маске.')

    line()
    p('ГЛАВНЫЙ ТЕСТ ГИПОТЕЗЫ А БЕЗ ТЕРЦИЛЕЙ: λ = c(страта) × кликов^α × вышедших^β')
    p('Гипотеза А («при равных кликах регистрации ∝ числу вышедших») требует β ≈ 1 и устойчиво > 0.')
    line()
    a0, ahat, bhat, blo, bhi, chi, _, _ = fit_block('мягкая страта набор+день (как у тестировщика)', P_pool)
    fit_block('ЖЁСТКАЯ страта набор+день+зона', P_hard)
    fit_block('ЖЁСТЧЕ: набор+день+зона+блок часа', P_hardh)
    fit_block('«КОНТЕНТ НЕ ЗАПИСАН» (август), пул = день', P_noc)
    fit_block('«КОНТЕНТ НЕ ЗАПИСАН», пул = день+зона', P_noc_hard)
    fit_block('всё вместе, набор+день+зона', P_all)
    for mn in ('август', 'сентябрь'):
        Pm, _ = make_pools([d for d in keep if d.month == mn], key_hard)
        if Pm: fit_block(f'{mn}: набор+день+зона', Pm)
    for z in ('team', 'lol', 'casino'):
        Pz, _ = make_pools([d for d in keep if d.zone == z], key_pool)
        if Pz: fit_block(f'только зона {z} (набор+день)', Pz)
    Pfd, _ = make_pools(keep, key_hard)
    p('')
    # ФД: тот же тест на депозитах
    for d in keep + noc: d.__class__ = Dom
    class DomFD:  # обёртка не нужна: считаем β для ФД вручную
        pass
    def fit_fd(name, P):
        grid = [i / 40 for i in range(-20, 81)]
        cells = []
        for k, doms in P.items():
            use = [d for d in doms if d.exits > 0 and d.clicks > 0]
            if len(use) < 3 or sum(d.fd for d in use) == 0: continue
            cells.append(use)
        def ll(a, b):
            s = 0.0
            for use in cells:
                W = sum((d.clicks ** a) * (d.exits ** b) for d in use); O = 0
                for d in use:
                    if d.fd:
                        s += d.fd * (a * math.log(d.clicks) + b * math.log(d.exits)); O += d.fd
                s -= O * math.log(W)
            return s
        best = max(((ll(a, b), a, b) for a in grid for b in grid))
        ll0 = max(ll(a, 0.0) for a in grid)
        lo = hi = None
        for x in grid:
            v = max(ll(a, x) for a in grid[::4])
            if v >= best[0] - 1.92:
                if lo is None: lo = x
                hi = x
        nfd = sum(d.fd for c in cells for d in c)
        p(f'  {name:<46} ФД {nfd:>4} | α {best[1]:5.2f}, β {best[2]:5.2f} [{lo:5.2f}; {hi:5.2f}] | χ²(β=0) {2*(best[0]-ll0):6.2f}')
    p('  То же на ПЕРВЫХ ДЕПОЗИТАХ (деньги, а не регистрации):')
    fit_fd('мягкая страта набор+день', P_pool)
    fit_fd('ЖЁСТКАЯ страта набор+день+зона', P_hard)

    line()
    p('ТЕНЬ 2. ТЕРЦИЛИ КОНЦЕНТРАЦИИ: зона, час, период, конвенция терцилей, нулевые клики')
    line()
    zz = collections.defaultdict(collections.Counter)
    for d in dd:
        if d.exits <= 0 or d.clicks <= 0: continue
        c = zz[d.zone]; c['n'] += 1; c['reg'] += d.regs; c['cl'] += d.clicks; c['ex'] += d.exits
    p('  зона     доменов   кликов    рег   рег/10т.кл   кликов/вышедший')
    for z, c in sorted(zz.items(), key=lambda kv: -kv[1]['n']):
        p(f'  {z:<9}{c["n"]:>6}{c["cl"]:>10}{c["reg"]:>7}{c["reg"]/c["cl"]*10000:>13.2f}{c["cl"]/c["ex"]:>18.1f}')
    oe_terciles(P_pool, lambda d: (d.clicks / d.exits) if d.exits else 0, lambda d: d.clicks,
                'Воспроизведение тестировщика: мягкая страта, E ∝ кликам (ожидается 1.85)')
    oe_terciles(P_pool, lambda d: (d.clicks / d.exits) if d.exits else 0, lambda d: d.clicks,
                'То же, но остаток пула отдан ВЕРХНЕМУ терцилю (иная развёрстка ничьих)', tfn=terciles_alt)
    oe_terciles(P_pool, lambda d: d.conc, lambda d: d.clicks,
                'То же, но выброшены домены без поисковых кликов в окне', keep_zero=False)
    oe_terciles(P_pool, lambda d: (d.clicks / d.exits) if d.exits else 0, lambda d: d.clicks ** a0,
                f'Мягкая страта, E ∝ кликов^{a0:.2f} (учтена нелинейность отдачи на клик)')
    oe_terciles(P_hard, lambda d: (d.clicks / d.exits) if d.exits else 0, lambda d: d.clicks,
                'ЖЁСТКАЯ страта набор+день+ЗОНА, E ∝ кликам')
    oe_terciles(P_hard, lambda d: (d.clicks / d.exits) if d.exits else 0, lambda d: d.clicks ** a0,
                f'ЖЁСТКАЯ страта набор+день+зона, E ∝ кликов^{a0:.2f}')
    oe_terciles(P_hardh, lambda d: (d.clicks / d.exits) if d.exits else 0, lambda d: d.clicks ** a0,
                f'ЖЁСТЧЕ: набор+день+зона+блок часа, E ∝ кликов^{a0:.2f}')
    oe_terciles(P_noc_hard, lambda d: (d.clicks / d.exits) if d.exits else 0, lambda d: d.clicks ** a0,
                f'«КОНТЕНТ НЕ ЗАПИСАН», пул = день+зона, E ∝ кликов^{a0:.2f}')
    for mn in ('август', 'сентябрь'):
        Pm, _ = make_pools([d for d in keep if d.month == mn], key_hard)
        if Pm:
            oe_terciles(Pm, lambda d: (d.clicks / d.exits) if d.exits else 0, lambda d: d.clicks ** a0,
                        f'{mn}: набор+день+зона, E ∝ кликов^{a0:.2f}')
    oe_terciles(P_pool, lambda d: (d.clicks / d.exits) if d.exits else 0, lambda d: d.clicks,
                'ФД вместо регистраций: мягкая страта, E ∝ кликам', ofn=lambda d: d.fd)
    oe_terciles(P_hard, lambda d: (d.clicks / d.exits) if d.exits else 0, lambda d: d.clicks,
                'ФД вместо регистраций: ЖЁСТКАЯ страта набор+день+зона, E ∝ кликам', ofn=lambda d: d.fd)

    line()
    p('ТЕНЬ 3. УЗКИЕ БИНЫ КЛИКОВ вместо бина шириной ×3 у тестировщика')
    line()
    for width, wname in ((1.6, '×1.6'), (2.5, '×2.5')):
        def binkey(d, w=width): return int(math.log(max(d.clicks, 1)) / math.log(w))
        for base, bname in ((key_pool, 'набор+день'), (key_hard, 'набор+день+зона')):
            P2, _ = make_pools([d for d in keep if d.clicks > 0], lambda d, b=base, bk=binkey: b(d) + (bk(d),),
                               min_n=3, min_reg=1)
            dd2 = [d for v in P2.values() for d in v]
            if not dd2: continue
            spread = sorted(max(d.clicks for d in v) / max(1, min(d.clicks for d in v)) for v in P2.values())
            p(f'\n  Страта {bname} × бин кликов {wname}: ячеек {len(P2)}, доменов {len(dd2)}, '
              f'регистраций {sum(d.regs for d in dd2)}; медиана разброса кликов в ячейке ×{spread[len(spread)//2]:.2f}')
            oe_terciles(P2, lambda d: d.conc, lambda d: d.clicks,
                        f'терцили концентрации внутри ячейки ({bname} × {wname}), E ∝ кликам', keep_zero=False)

    line()
    p('ТЕНЬ 4. ПАРЫ: ужесточение допуска по кликам, фиксация зоны и часа, джекнайф')
    line()
    base_pairs = pairs_of(P_pool, 1.25, 1.5)
    pair_report(base_pairs, 'мягкая страта набор+день, клики ≤×1.25, вышедших ≥×1.5 (тест тестировщика)')
    for cr in (1.15, 1.10, 1.05):
        pair_report(pairs_of(P_pool, cr, 1.5), f'та же страта, клики ≤×{cr}, вышедших ≥×1.5')
    p('')
    for cr in (1.25, 1.10):
        pair_report(pairs_of(P_hard, cr, 1.5), f'ЖЁСТКАЯ страта набор+день+ЗОНА, клики ≤×{cr}, вышедших ≥×1.5')
    pair_report(pairs_of(P_hardh, 1.25, 1.5), 'ЖЁСТЧЕ: набор+день+зона+блок часа, клики ≤×1.25, вышедших ≥×1.5')
    pair_report(pairs_of(P_noc, 1.25, 1.5), '«КОНТЕНТ НЕ ЗАПИСАН» (август), пул = день')
    pair_report(pairs_of(P_noc_hard, 1.25, 1.5), '«КОНТЕНТ НЕ ЗАПИСАН», пул = день+зона')

    p('\n  Где сидит эффект: базовые пары по объёму кликов широкого домена')
    B = ((0, 95, '≤95'), (95, 325, '95–325'), (325, 912, '325–912'), (912, 10**9, '>912'))
    for lo_, hi_, nm in B:
        sub = [x for x in base_pairs if lo_ < x[0][0].clicks <= hi_ or (lo_ == 0 and x[0][0].clicks <= hi_)]
        r = pair_report(sub, '', show=False)
        if r: p(f'    бин {nm:<9} пар {r["n"]:>3}: рег {r["ow"]:>2} vs {r["on"]:>2}, отношение {fr(r["obs"])}, знаки {r["wins"]}:{r["los"]}')
    pair_report([x for x in base_pairs if x[0][0].clicks <= 912], '  базовые пары БЕЗ крупнейшего бина (>912 кликов)')
    pair_report([x for x in base_pairs if x[0][0].zone == x[0][1].zone], '  базовые пары, где оба домена ОДНОЙ зоны')
    pair_report([x for x in base_pairs if x[0][0].zone != x[0][1].zone], '  базовые пары РАЗНЫХ зон')

    p('\n  Интервал для эффекта пар: бутстрэп по пулам (1000), отношение ставок «широкий/узкий» на клик')
    for nm, P_, cr_ in (('мягкая набор+день, ≤×1.25', P_pool, 1.25),
                        ('ЖЁСТКАЯ набор+день+зона, ≤×1.25', P_hard, 1.25),
                        ('ЖЁСТЧЕ набор+день+зона+час, ≤×1.25', P_hardh, 1.25)):
        prs = pairs_of(P_, cr_, 1.5)
        if not prs: continue
        bypool = collections.defaultdict(list)
        for pr, k in prs: bypool[k].append(pr)
        ks = list(bypool.keys()); random.seed(SEED); vals = []
        for _ in range(1000):
            samp = [random.choice(ks) for _ in ks]
            ow = on = cw = cn = 0
            for k in samp:
                for w, x in bypool[k]:
                    ow += w.regs; cw += w.clicks; on += x.regs; cn += x.clicks
            if cw > 0 and cn > 0 and on > 0: vals.append((ow / cw) / (on / cn))
            elif cw > 0 and on == 0 and ow > 0: vals.append(float('inf'))
        fin = sorted(v for v in vals if v != float('inf'))
        ninf = len(vals) - len(fin)
        if fin:
            p(f'    {nm:<36} медиана {fin[len(fin)//2]:.2f}, 95% интервал [{fin[int(.025*len(fin))]:.2f}; '
              f'{fin[min(len(fin)-1,int(.975*len(fin)))]:.2f}] (+{ninf} бутстрэпов с нулём у узкого из {len(vals)}); '
              f'доля бутстрэпов с отношением < 1: {sum(1 for v in vals if v != float("inf") and v < 1)/max(1,len(vals))*100:.1f}%')

    p('\n  ОТРИЦАТЕЛЬНЫЕ КОНТРОЛИ (та же машинка пар, но роль назначена не по вышедшим):')
    for nm, kf in (('роль по алфавиту имени домена', lambda a, b: (a, b) if a.domain < b.domain else (b, a)),
                   ('роль по чётности часа запуска', lambda a, b: (a, b) if (a.hour % 2) >= (b.hour % 2) else (b, a)),
                   ('роль по числу сайтов в окне', lambda a, b: (a, b) if a.sites >= b.sites else (b, a))):
        prs = []
        for k, doms in P_pool.items():
            ss = sorted([d for d in doms if d.exits > 0 and d.clicks > 0], key=lambda d: (d.clicks, d.domain))
            i = 0
            while i < len(ss) - 1:
                a_, b_ = ss[i], ss[i + 1]
                if b_.clicks / a_.clicks <= 1.25 and max(a_.exits, b_.exits) / min(a_.exits, b_.exits) >= 1.5:
                    prs.append((kf(a_, b_), k)); i += 2
                else: i += 1
        r = pair_report(prs, '', show=False)
        p(f'    {nm:<34} рег {r["ow"]:>2} vs {r["on"]:>2}, отношение {fr(r["obs"])}, знаки {r["wins"]}:{r["los"]}, p(перест.) {r["pperm"]:.4f}')
    prs = []
    for k, doms in P_pool.items():
        ss = sorted([d for d in doms if d.exits > 0 and d.clicks > 0], key=lambda d: (d.clicks, d.domain))
        i = 0
        while i < len(ss) - 1:
            a_, b_ = ss[i], ss[i + 1]
            if b_.clicks / a_.clicks <= 1.25 and max(a_.exits, b_.exits) / min(a_.exits, b_.exits) <= 1.1:
                prs.append(((b_, a_), k)); i += 2   # «роль» = больше кликов
            else: i += 1
    r = pair_report(prs, '', show=False)
    if r: p(f'    пары с РАВНЫМИ вышедшими (≤×1.1), роль = больше кликов: пар {r["n"]}, рег {r["ow"]} vs {r["on"]}, '
            f'отношение {fr(r["obs"])}, знаки {r["wins"]}:{r["los"]}, p(перест.) {r["pperm"]:.4f}')
    sv = sorted(set(d.sites for v in P_pool.values() for d in v))
    p(f'    справка: различных значений «сайтов в окне» среди доменов страты {len(sv)} '
      f'(мин {min(sv)}, макс {max(sv)}) — число сайтов практически константа, вышедшие различаются только долей выхода.')

    p('\n  Знаменатель внутри пар: боты и «прочие» клики у широкого и узкого домена')
    for nm, P_, lab in (('мягкая', P_pool, 'набор+день'), ('жёсткая', P_hard, 'набор+день+зона')):
        prs = pairs_of(P_, 1.25, 1.5)
        if not prs: continue
        w_all = sum(w.allclicks for (w, _), _ in prs); n_all = sum(x.allclicks for (_, x), _ in prs)
        w_b = sum(w.bots for (w, _), _ in prs); n_b = sum(x.bots for (_, x), _ in prs)
        w_o = sum(w.other for (w, _), _ in prs); n_o = sum(x.other for (_, x), _ in prs)
        w_s = sum(w.sws for (w, _), _ in prs); n_s = sum(x.sws for (_, x), _ in prs)
        p(f'    {lab}: ботов% широкий {w_b/max(1,w_all)*100:.1f} vs узкий {n_b/max(1,n_all)*100:.1f}; '
          f'прочих% {w_o/max(1,w_all)*100:.1f} vs {n_o/max(1,n_all)*100:.1f}; '
          f'сайтов с поиском {w_s} vs {n_s}')

    p('\n  Джекнайф по пулам (базовые пары): выбрасываем по одному пулу целиком')
    byk = collections.defaultdict(list)
    for pr, k in base_pairs: byk[k].append(pr)
    rows = []
    for k in byk:
        r = pair_report([x for x in base_pairs if x[1] != k], '', show=False)
        if r: rows.append(((r['obs'] if r['obs'] != float('inf') else 99), k, r))
    rows.sort()
    for v, k, r in rows[:4]:
        p(f'    без пула {str(k):<46} отношение {fr(r["obs"])}, рег {r["ow"]} vs {r["on"]}, p(перест.) {r["pperm"]:.4f}, знаки {r["wins"]}:{r["los"]}')
    p(f'    всего пулов с парами {len(byk)}; после выброса одного пула отношение колеблется '
      f'{fr(rows[0][2]["obs"])}–{fr(rows[-1][2]["obs"])}, худший p(перест.) {max(r["pperm"] for _,_,r in rows):.4f}')
    p('  Джекнайф по доменам: выбрасываем пары с самыми «денежными» широкими доменами')
    ws = sorted(base_pairs, key=lambda x: -x[0][0].regs)
    for kk in (1, 2, 3):
        drop = set(id(x) for x in ws[:kk])
        r = pair_report([x for x in base_pairs if id(x) not in drop], '', show=False)
        top = ', '.join(f'{x[0][0].domain}({x[0][0].regs} рег)' for x in ws[:kk])
        p(f'    без {kk} пар(ы) [{top}]: рег {r["ow"]} vs {r["on"]}, отношение {fr(r["obs"])}, '
          f'p(перест.) {r["pperm"]:.4f}, знаки {r["wins"]}:{r["los"]}')

    line()
    p('ТЕНЬ 5. ЗНАМЕНАТЕЛЬ ПО ТЕРЦИЛЯМ КОНЦЕНТРАЦИИ (мягкая страта)')
    line()
    agg = [collections.Counter() for _ in range(3)]
    for k, doms in P_pool.items():
        use = [d for d in doms if d.exits > 0]
        if len(use) < 3: continue
        lab = terciles(use, lambda d: (d.clicks / d.exits) if d.exits else 0)
        for d in use:
            a = agg[lab[d.domain]]
            a['n'] += 1; a['cl'] += d.clicks; a['bot'] += d.bots; a['oth'] += d.other
            a['all'] += d.allclicks; a['reg'] += d.regs; a['fd'] += d.fd; a['ex'] += d.exits; a['sws'] += d.sws
    p('  терциль                доменов   поиск.кликов   ботов   прочих   ботов%   прочих%   вышедших   сайтов с поиском')
    for i in range(3):
        a = agg[i]
        p(f'  {TNAME[i]:<22}{a["n"]:>6}{a["cl"]:>15}{a["bot"]:>9}{a["oth"]:>9}'
          f'{a["bot"]/max(1,a["all"])*100:>9.1f}{a["oth"]/max(1,a["all"])*100:>10.1f}{a["ex"]:>12}{a["sws"]:>17}')
    p('  ФД по терцилям: ' + '; '.join(f'{TNAME[i]} {agg[i]["fd"]}' for i in range(3)) +
      ' — при E ∝ кликам депозиты почти не отличают терцили, хотя регистрации отличают.')

    p('\n  Регистрации на 10 тыс. КЛИКОВ ВСЕГО в окне (а не только «из поиска») по тем же терцилям:')
    for i in range(3):
        a = agg[i]
        p(f'    {TNAME[i]:<22} рег {a["reg"]:>3}, кликов всего {a["all"]:>8}, '
          f'рег/10 тыс. всего {a["reg"]/max(1,a["all"])*10000:>5.2f}, рег/10 тыс. поисковых {a["reg"]/max(1,a["cl"])*10000:>5.2f}')
    oe_terciles(P_pool, lambda d: (d.clicks / d.exits) if d.exits else 0, lambda d: float(d.allclicks),
                'Терцили концентрации, E ∝ КЛИКАМ ВСЕГО в окне (боты+поиск+прочие) — мягкая страта')
    oe_terciles(P_hard, lambda d: (d.clicks / d.exits) if d.exits else 0, lambda d: float(d.allclicks),
                'Терцили концентрации, E ∝ КЛИКАМ ВСЕГО в окне — ЖЁСТКАЯ страта набор+день+зона')
    oe_terciles(P_pool, lambda d: (d.allclicks / d.exits) if d.exits else 0, lambda d: float(d.allclicks),
                'Концентрация СЧИТАЕТСЯ по кликам всего, E ∝ кликам всего — мягкая страта')
    p('\n  Пары, подобранные по КЛИКАМ ВСЕГО в окне (а не по поисковым), вышедших ≥×1.5:')
    for nm, P_ in (('мягкая набор+день', P_pool), ('ЖЁСТКАЯ набор+день+зона', P_hard)):
        prs = []
        for k, doms in P_.items():
            ss = sorted([d for d in doms if d.exits > 0 and d.allclicks > 0], key=lambda d: (d.allclicks, d.domain))
            i = 0
            while i < len(ss) - 1:
                a_, b_ = ss[i], ss[i + 1]
                if b_.allclicks / a_.allclicks <= 1.25 and max(a_.exits, b_.exits) / min(a_.exits, b_.exits) >= 1.5:
                    prs.append(((a_, b_) if a_.exits > b_.exits else (b_, a_), k)); i += 2
                else: i += 1
        if not prs: continue
        ow = sum(w.regs for (w, _), _ in prs); on = sum(x.regs for (_, x), _ in prs)
        cw = sum(w.allclicks for (w, _), _ in prs); cn = sum(x.allclicks for (_, x), _ in prs)
        sw_ = sum(w.clicks for (w, _), _ in prs); sn = sum(x.clicks for (_, x), _ in prs)
        wins = sum(1 for (w, x), _ in prs if w.regs > x.regs); los = sum(1 for (w, x), _ in prs if w.regs < x.regs)
        m = wins + los
        ps = min(1.0, 2 * sum(math.comb(m, j) for j in range(min(wins, los) + 1)) / 2 ** m) if m else None
        rr = (ow / cw) / (on / cn) if on and cn else float('inf') if ow else 1.0
        p(f'    {nm}: пар {len(prs)}; кликов всего {cw} vs {cn} (из них поисковых {sw_} vs {sn}); '
          f'рег {ow} vs {on}; отношение на клик всего {fr(rr)}; знаки {wins}:{los}, знаковый p = {fr(ps,4) if ps is not None else "н/д"}')

    line()
    p('ЧАСТЬ Б ПОД ЖЁСТКОЙ СТРАТОЙ: терцили «выход 3 суток %»')
    line()
    for nm, P_ in (('мягкая набор+день', P_pool), ('ЖЁСТКАЯ набор+день+зона', P_hard),
                   ('ЖЁСТЧЕ набор+день+зона+час', P_hardh)):
        oe_terciles(P_, lambda d: d.exitpct, lambda d: d.clicks, f'{nm}, E ∝ кликам', stat='high')
        oe_terciles(P_, lambda d: d.exitpct, lambda d: float(d.exits), f'{nm}, E ∝ вышедшим', stat='high')
        oe_terciles(P_, lambda d: d.exitpct, lambda d: d.clicks ** a0, f'{nm}, E ∝ кликов^{a0:.2f}', stat='high')

    line()
    p('ВЕСА: «вышедших × √кликов» против чистых кликов — различимы ли?')
    line()
    def dev(pools, wfn):
        s = 0.0; n = 0
        for k, doms in pools.items():
            use = [d for d in doms if d.exits > 0 and d.clicks > 0]
            O = sum(d.regs for d in use); W = sum(wfn(d) for d in use)
            if not use or W <= 0 or O == 0: continue
            for d in use:
                e = wfn(d) * O / W; y = d.regs
                s += 2 * ((y * math.log(y / e) if y > 0 else 0) - (y - e)); n += 1
        return s, n
    cand = [('клики', lambda d: float(d.clicks)), ('вышедшие', lambda d: float(d.exits)),
            ('вышедшие×√кликов', lambda d: d.exits * math.sqrt(d.clicks)),
            (f'кликов^{a0:.2f}', lambda d: d.clicks ** a0),
            (f'кликов^{ahat:.2f}×вышедших^{bhat:.2f}', lambda d: (d.clicks ** ahat) * (d.exits ** bhat)),
            ('сайты (плоский)', lambda d: float(d.sites))]
    p('  Пуассоновская девианса внутри пула (меньше = лучше), мягкая страта набор+день:')
    for nm, f in cand:
        D, n = dev(P_pool, f); p(f'    {nm:<34} девианса {D:8.1f} при {n} доменах')
    keys = list(P_pool.keys())
    random.seed(SEED); diffs = []
    for _ in range(400):
        samp = [random.choice(keys) for _ in keys]
        sub = {(k, i): P_pool[k] for i, k in enumerate(samp)}
        d1, _ = dev(sub, lambda d: d.exits * math.sqrt(d.clicks)); d2, _ = dev(sub, lambda d: float(d.clicks))
        diffs.append(d2 - d1)
    diffs.sort()
    p(f'  Бутстрэп по пулам (400): выигрыш «вышедшие×√кликов» перед «кликами» по девиансе: '
      f'медиана {diffs[len(diffs)//2]:.1f}, 95% интервал [{diffs[int(.025*len(diffs))]:.1f}; {diffs[int(.975*len(diffs))-1]:.1f}], '
      f'доля бутстрэпов с выигрышем {sum(1 for x in diffs if x > 0)/len(diffs)*100:.0f}%.')
    line()
    p('ИТОГ КОНТРПРОВЕРКИ')
    line()
    p('  ОПРОВЕРГНУТО (тени):')
    p('   1. Терцильный аргумент «1,85 (32 при 21,0 против 89 при 108,3), p=0,002» — тень объёма кликов')
    p('      и знаменателя. Отдача на клик падает в 4,6 раза (10,52 → 2,28 рег на 10 тыс. от Q1 к Q5),')
    p('      а концентрация растёт с кликами (4,0 → 66,6 клика на вышедший): терциль концентрации почти')
    p('      совпадает с терцилем объёма. При E ∝ кликов^0,82 отношение падает до 1,40 (двуст. p=0,09),')
    p('      в страте набор+день+зона 1,48 (p=0,085), +блок часа 1,42 (p=0,12). При счёте по кликам ВСЕГО')
    p('      в окне (ботов 50,7% в T1 против 18,3% в T3) отношение 0,82 (p=0,38) и 1,04 (p=0,83) — знак исчезает.')
    p('      Смена развёрстки остатка терцилей одна меняет 1,85 на 1,72.')
    p('   2. «Знак тот же везде» — нет. В «КОНТЕНТ НЕ ЗАПИСАН» при фиксированной зоне пары дают 9 против 8')
    p('      (1,12; p=0,40), терцили 1,23 (p=0,44); в зоне casino β = −0,07 (χ²=0,00), в lol β=0,85 [−0,07; 1,85].')
    p('   3. Деньги эффекта не видят: на ФД β=0,55 [−0,42; 1,75], χ²=1,1; терцили ФД 1,20 (p=0,62) и 1,15 (p=0,73).')
    p('   4. «В 3,3 раза» — неустойчивая точка: без бина >912 кликов 2,02 (p=0,12); минус три «денежных»')
    p('      широких домена 2,00 (p=0,09); бутстрэп по пулам 95% интервал [1,6; 9,8] и [0,9; 9,5] в жёсткой страте.')
    p('  ВЫЖИЛО:')
    p('   5. Направление А при равных кликах: β (эластичность по вышедшим) 1,18 [0,68; 1,77], χ²=19,3;')
    p('      в страте набор+день+зона 1,18 [0,57; 1,82], χ²=15,2; +блок часа 0,97 [0,30; 1,68], χ²=8,0.')
    p('   6. Пары в страте набор+день+зона+блок часа: 12 против 3 (4,17; p=0,002; знаки 8:1);')
    p('      при подборе пар по кликам ВСЕГО — 22 против 8 (2,74; знаки 14:4, знаковый p=0,031).')
    p('   7. Отрицательные контроли чисты: роль по алфавиту 1,02, по чётности часа 0,78, по числу сайтов 0,57;')
    p('      при равных вышедших лишние клики дают 0,75 — машинка пар сама по себе эффекта не создаёт.')
    p('   8. Часть Б выживает с меньшими числами: O/E(T3) ∝ вышедшим 1,41 → 1,34 (p=0,013) и 1,35 (p=0,012);')
    p('      ∝ кликам 1,15 → 1,13 (p=0,34) — от 1 не отличается. Вес вышедшие×√кликов: девианса 383,4')
    p('      против 406,7 (клики) и 421,3 (вышедшие), выигрыш по бутстрэпу 23,2 [5,4; 43,6], 99% бутстрэпов.')
    line()


if __name__ == '__main__':
    tee = Tee(OUT); sys.stdout = tee
    try: main()
    finally:
        sys.stdout = sys.__stdout__; tee.flush(); tee.f.close()
