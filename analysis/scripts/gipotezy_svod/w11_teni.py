# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №11 (ТЕНИ / конфаундинг).
Угол: эффект «хвост не приходит на домены без поздних выходов» — тень
выбора нуля (E ∝ ранним выходам), набора/дня/зоны/часа, периода
(август против сентября, «КОНТЕНТ НЕ ЗАПИСАН»), выбросов и объёма дня.

Только stdlib. Единица — домен. Тесты — перестановочные (метки внутри страты,
счётчики домена не разбиваются) и точные пуассоновские.
"""
import csv, os, sys, math, random, collections, datetime

REPO = '/home/user/cladue'
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w11_teni.txt')
REF = datetime.date(2026, 9, 21)
OUTLIERS = {'3615.team', '3286.team'}
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
ZONES = ('team', 'lol', 'casino', 'buzz')
NSIM = 10000

class Tee:
    def __init__(self, path):
        self.f = open(path, 'w', encoding='utf-8'); self.o = sys.stdout
    def write(self, s):
        self.f.write(s); self.o.write(s)
    def flush(self):
        self.f.flush(); self.o.flush()

def I(x):
    x = (x or '').strip()
    return int(float(x)) if x else 0

def F(x):
    x = (x or '').strip()
    return float(x) if x else 0.0

def D(s):
    return datetime.date(*map(int, s.split('-')))

def r2(a, b, nd=2):
    return ('%.'+str(nd)+'f') % (a / b) if b else 'н/д'

def ratio(a, b):
    return a / b if b else float('nan')

def fmt(x, nd=2):
    try:
        if x != x: return 'н/д'
    except Exception: return 'н/д'
    return ('%.'+str(nd)+'f') % x

# --- точные пуассоновские границы для O при данном E ---
def pois_cdf(k, mu):
    if k < 0: return 0.0
    t = math.exp(-mu); s = t
    for i in range(1, k+1):
        t *= mu/i; s += t
    return min(1.0, s)

def pois_sf_ge(k, mu):   # P(X >= k)
    return 1.0 - pois_cdf(k-1, mu) if k > 0 else 1.0

def pois_ci(k, alpha=0.05):
    """точный ДИ для среднего пуассона при наблюдённых k."""
    lo = 0.0 if k == 0 else _bis(lambda m: pois_sf_ge(k, m) - alpha/2, 1e-9, 1e6)
    hi = _bis(lambda m: pois_cdf(k, m) - alpha/2, 1e-9, 1e6)
    return lo, hi

def _bis(f, lo, hi, it=200):
    flo = f(lo)
    for _ in range(it):
        mid = (lo+hi)/2
        if (f(mid) > 0) == (flo > 0): lo = mid
        else: hi = mid
    return (lo+hi)/2

def log_choose(n, k):
    return math.lgamma(n+1) - math.lgamma(k+1) - math.lgamma(n-k+1)

def binom_sf(k, n, p):   # P(X >= k)
    if k <= 0: return 1.0
    if k > n: return 0.0
    return sum(math.exp(log_choose(n, i) + i*math.log(p) + (n-i)*math.log1p(-p))
               for i in range(k, n+1)) if p > 0 else 0.0

def binom_cdf(k, n, p):
    if k < 0: return 0.0
    if k >= n: return 1.0
    return sum(math.exp(log_choose(n, i) + i*math.log(p) + (n-i)*math.log1p(-p))
               for i in range(0, k+1)) if p > 0 else 1.0

# ---------------- загрузка ----------------
def make(r):
    age = (REF - D(r['день запуска'])).days
    age2 = (REF - D(r['последний день'])).days if r['последний день'] else age
    sites = I(r['сайтов']); w1 = I(r['сайтов в 1-й волне']); w2 = I(r['сайтов во 2-й волне'])
    if w1 + w2 != sites: w1, w2 = sites, 0
    early = I(r['вышли за 3 суток']); out7 = I(r['вышли за 7 суток']); ss = I(r['сайтов с поиском'])
    offs = [(D(s) - D(r['день запуска'])).days for s in r['даты регистраций'].split()]
    d = {
        'домен': r['домен'], 'зона': r['зона'] if r['зона'] in ZONES else 'прочие',
        'день': r['день запуска'], 'набор': r['набор контента'], 'семейство': r['семейство'],
        'час': r['блок часа'], 'возраст': age, 'сайтов': sites,
        'early': early, 'late47': out7 - early, 'late8': ss - out7, 'late_alt': ss - early,
        'reg': I(r['регистраций']), 'reg_w': I(r['регистраций в окне 3 суток']),
        'fd': I(r['ФД']), 'fd_w': I(r['ФД в окне 3 суток']),
        'search': I(r['из поиска']), 'search_w': I(r['кликов из поиска в окне']),
        'exp_w': sites*3, 'exp_after': w1*max(0, age-3) + w2*max(0, age2-3),
        'tail_d5': sum(1 for o in offs if o >= 5),
    }
    d['tail'] = d['reg'] - d['reg_w']
    d['search_after'] = d['search'] - d['search_w']
    d['late_group'] = '0' if d['late47'] == 0 else ('1-3' if d['late47'] <= 3 else '>=4')
    d['bin'] = '0' if d['late47'] == 0 else '>=1'
    d['месяц'] = 'авг' if d['день'] < '2026-09-01' else 'сен'
    return d

def load(keep_nocontent=False, keep_outliers=False, keep_d1=False):
    rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
    a = [r for r in rows if r['окно закрыто'] == 'да']
    if not keep_d1: a = [r for r in a if r['дней'] != '1']
    if not keep_outliers: a = [r for r in a if r['домен'] not in OUTLIERS]
    if not keep_nocontent: a = [r for r in a if r['набор контента'] != NOCONTENT]
    return [make(r) for r in a]

def age_ge(doms, k): return [d for d in doms if d['возраст'] >= k]

# ---------------- стратифицированное O/E ----------------
KEYS = {
    'набор+день':            lambda d: (d['набор'], d['день']),
    'набор+день+зона':       lambda d: (d['набор'], d['день'], d['зона']),
    'набор+день+зона+час':   lambda d: (d['набор'], d['день'], d['зона'], d['час']),
}

def strat(doms, key, num, exp, group_of, groups, nsim=0, seed=7):
    pools = [v for v in _by(doms, key).values() if len(v) >= 2 and sum(d[exp] for d in v) > 0]
    used = [d for v in pools for d in v]
    lost = sum(d[num] for d in doms) - sum(d[num] for d in used)
    O = collections.Counter(); E = collections.Counter(); N = collections.Counter(); EX = collections.Counter()
    for v in pools:
        tn = sum(d[num] for d in v); te = sum(d[exp] for d in v)
        for d in v:
            g = group_of(d); O[g] += d[num]; E[g] += tn*d[exp]/te; N[g] += 1; EX[g] += d[exp]
    res = {'tab': {g: (N[g], EX[g], O[g], E[g], ratio(O[g], E[g])) for g in groups},
           'pools': len(pools), 'dom': len(used), 'lost': lost, 'num': sum(d[num] for d in used)}
    if nsim:
        rng = random.Random(seed)
        lo_obs = ratio(O[groups[0]], E[groups[0]]); hi_obs = ratio(O[groups[-1]], E[groups[-1]])
        chi_obs = sum((O[g]-E[g])**2/E[g] for g in groups if E[g] > 0)
        prep = [(v, sum(d[num] for d in v), sum(d[exp] for d in v), [group_of(d) for d in v]) for v in pools]
        c_lo = c_hi = c_chi = 0
        for _ in range(nsim):
            Op = collections.Counter(); Ep = collections.Counter()
            for v, tn, te, labs in prep:
                l = labs[:]; rng.shuffle(l)
                for d, g in zip(v, l):
                    Op[g] += d[num]; Ep[g] += tn*d[exp]/te
            if ratio(Op[groups[0]], Ep[groups[0]]) <= lo_obs + 1e-12: c_lo += 1
            if ratio(Op[groups[-1]], Ep[groups[-1]]) >= hi_obs - 1e-12: c_hi += 1
            if sum((Op[g]-Ep[g])**2/Ep[g] for g in groups if Ep[g] > 0) >= chi_obs - 1e-12: c_chi += 1
        res['p'] = {'lo': (c_lo+1)/(nsim+1), 'hi': (c_hi+1)/(nsim+1), 'chi': (c_chi+1)/(nsim+1)}
    return res

def _by(doms, key):
    p = collections.defaultdict(list)
    for d in doms: p[key(d)].append(d)
    return p

def show(out, res, groups, expname, gname, title):
    out.write(f'  {title}\n')
    out.write(f'    страт {res["pools"]}, доменов {res["dom"]}, событий в страте {res["num"]} (вне страты {res["lost"]})\n')
    out.write(f'    {gname:10s} {"доменов":>8s} {expname:>14s} {"O":>5s} {"E":>8s} {"O/E":>6s} {"95% ДИ O/E":>16s}\n')
    for g in groups:
        n, ex, o, e, oe = res['tab'][g]
        if o <= 500:
            lo, hi = pois_ci(int(o))
            ci = f'{fmt(lo/e if e else float("nan"))}–{fmt(hi/e if e else float("nan"))}'
        else:
            ci = 'н/д (клики)'
        out.write(f'    {g:10s} {n:8d} {ex:14.0f} {o:5d} {e:8.2f} {fmt(oe):>6s} {ci:>16s}\n')
    if 'p' in res:
        out.write(f'    p (перестановка меток в страте): O/E({groups[0]}) ≤ набл. {fmt(res["p"]["lo"],4)}; '
                  f'O/E({groups[-1]}) ≥ набл. {fmt(res["p"]["hi"],4)}; χ² {fmt(res["p"]["chi"],4)}\n')

# ================================================================
out = Tee(OUT)
G3 = ('0', '1-3', '>=4')
G2 = ('0', '>=1')

out.write('='*110 + '\n')
out.write('КОНТРПРОВЕРКА №11 — ТЕНИ. Хвост регистраций после окна 3 суток и поздние выходы.\n')
out.write(f'Источник: analysis/export/svod_domenov_21.09.csv; срез {REF}; перестановок {NSIM}, seed 7.\n')
out.write('='*110 + '\n\n')

base = age_ge(load(), 10)
out.write(f'База сравнения (как у тестировщика): возраст ≥10, без «{NOCONTENT}», без выбросов, дней≠1 — '
          f'{len(base)} доменов, {sum(d["сайтов"] for d in base)} сайтов, '
          f'хвост {sum(d["tail"] for d in base)}, рег в окне {sum(d["reg_w"] for d in base)}.\n\n')

# ---------- 1. Состав групп: чем late47=0 отличается ПОМИМО поздних выходов ----------
out.write('='*110 + '\n1. ЧТО ЕЩЁ РАЗЛИЧАЕТ ГРУППЫ (кандидаты в конфаундеры)\n' + '='*110 + '\n')
out.write(f'  {"группа":8s} {"доменов":>8s} {"сайтов":>8s} {"early/сайт":>11s} {"выход3%":>8s} {"поиск%":>7s} '
          f'{"авг%":>6s} {"team%":>6s} {"lol%":>6s} {"casino%":>7s} {"buzz%":>6s} {"возраст":>8s} {"кл/сайт окно":>12s}\n')
for g in G3:
    v = [d for d in base if d['late_group'] == g]
    s = sum(d['сайтов'] for d in v); e = sum(d['early'] for d in v)
    ss = sum(d['early']+d['late47']+d['late8'] for d in v)
    out.write(f'  {g:8s} {len(v):8d} {s:8d} {r2(e,s,3):>11s} {r2(100*e,s,1):>8s} {r2(100*ss,s,1):>7s} '
              f'{r2(100*sum(1 for d in v if d["месяц"]=="авг"),len(v),1):>6s} ')
    for z in ZONES:
        out.write(f'{r2(100*sum(1 for d in v if d["зона"]==z),len(v),1):>6s} ' if z != 'casino'
                  else f'{r2(100*sum(1 for d in v if d["зона"]==z),len(v),1):>7s} ')
    out.write(f'{r2(sum(d["возраст"] for d in v),len(v),1):>8s} {r2(sum(d["search_w"] for d in v),s,1):>12s}\n')

out.write('\n  Распределение групп по месяцу запуска (доменов / хвост / рег в окне):\n')
for m in ('авг', 'сен'):
    for g in G3:
        v = [d for d in base if d['месяц'] == m and d['late_group'] == g]
        out.write(f'    {m} {g:5s}: доменов {len(v):4d}, хвост {sum(d["tail"] for d in v):3d}, '
                  f'окно {sum(d["reg_w"] for d in v):3d}, early {sum(d["early"] for d in v):6d}, '
                  f'кликов после окна {sum(d["search_after"] for d in v):7d}\n')

# ---------- 2. Лестница страт: E ∝ early ----------
out.write('\n' + '='*110 + '\n2. ЛЕСТНИЦА СТРАТ, НУЛЬ «E ∝ ранним выходам» (нуль тестировщика)\n' + '='*110 + '\n')
for kname, key in KEYS.items():
    out.write(f'\n--- страта: {kname} ---\n')
    show(out, strat(base, key, 'tail', 'early', lambda d: d['late_group'], G3, NSIM), G3, 'early', 'late47', 'ХВОСТ')
    show(out, strat(base, key, 'reg_w', 'early', lambda d: d['late_group'], G3, NSIM), G3, 'early', 'late47', 'КОНТРОЛЬ: рег в окне')

# ---------- 3. Тот же эффект под НУЛЁМ ПО МЕХАНИЗМУ: E ∝ кликам после окна ----------
out.write('\n' + '='*110 + '\n3. ТОТ ЖЕ ЭФФЕКТ ПОД НУЛЁМ ПО МЕХАНИЗМУ: E ∝ поисковым кликам ПОСЛЕ ОКНА\n')
out.write('   (нуль «хвост идёт за трафиком после окна, кто бы его ни дал»)\n' + '='*110 + '\n')
for kname, key in KEYS.items():
    out.write(f'\n--- страта: {kname} ---\n')
    show(out, strat(base, key, 'tail', 'search_after', lambda d: d['late_group'], G3, NSIM),
         G3, 'кл.после', 'late47', 'ХВОСТ')

# ---------- 4. Почему нуль «E ∝ early» встроенно занижает late=0 ----------
out.write('\n' + '='*110 + '\n4. ПОЧЕМУ НУЛЬ «E ∝ early» ВСТРОЕННО ДАЁТ O/E<1 У late=0\n' + '='*110 + '\n')
out.write('  Нуль раздаёт ВЕСЬ хвост пула пропорционально ранним выходам. Но хвост пула частью\n'
          '  порождён поздними сайтами (это и есть гипотеза), поэтому у домена без поздних выходов\n'
          '  O/E<1 получается тавтологически. Оценим величину встроенного смещения.\n')
tot_t = sum(d['tail'] for d in base); tot_e = sum(d['early'] for d in base)
tot_l = sum(d['late47']+d['late8'] for d in base)
out.write(f'  Доля сайтов, вышедших после 3 суток, среди всех вышедших: '
          f'{r2(100*tot_l, tot_e+tot_l, 1)} % ({tot_l} из {tot_e+tot_l}).\n')
for theta in (0.0, 0.3, 0.5, 0.7, 1.0):
    # имитация: хвост домена ~ (1-theta)*early + theta*(late47+late8), нормируем внутри пула,
    # считаем ожидаемое O/E группы 0 под нулём E ∝ early
    num = collections.Counter(); den = collections.Counter()
    for v in _by(base, KEYS['набор+день']).values():
        if len(v) < 2: continue
        te = sum(d['early'] for d in v)
        w = [(1-theta)*d['early'] + theta*(d['late47']+d['late8']) for d in v]
        tw = sum(w)
        if te <= 0 or tw <= 0: continue
        tn = sum(d['tail'] for d in v)
        for d, wi in zip(v, w):
            g = d['late_group']
            num[g] += tn*wi/tw        # «истинный» хвост по модели
            den[g] += tn*d['early']/te  # ожидание нуля E ∝ early
    out.write(f'  θ (доля хвоста с поздних сайтов) = {theta:.1f}: ожидаемое O/E(0) = '
              f'{fmt(ratio(num["0"], den["0"]))}, O/E(1-3) = {fmt(ratio(num["1-3"], den["1-3"]))}, '
              f'O/E(>=4) = {fmt(ratio(num[">=4"], den[">=4"]))}\n')
out.write('  Наблюдалось 0.35 / 1.28 / 1.10.\n')

# ---------- 5. Устойчивость: джекнайф по доменам и по стратам ----------
out.write('\n' + '='*110 + '\n5. УСТОЙЧИВОСТЬ: ДЖЕКНАЙФ ПО ДОМЕНАМ И ПО СТРАТАМ (страта набор+день)\n' + '='*110 + '\n')
key = KEYS['набор+день']
def oe_of(doms, g='0', num='tail', exp='early', k=key):
    r = strat(doms, k, num, exp, lambda d: d['late_group'], G3)
    return r['tab'][g][4], r['tab'][g][2], r['tab'][g][3]
b0, bo, be = oe_of(base)
out.write(f'  Базовое O/E(late=0) = {fmt(b0)} (O={bo}, E={fmt(be)}).\n')
# домены с хвостом — влияют
cand = sorted([d for d in base if d['tail'] > 0], key=lambda d: -d['tail'])
out.write(f'  Доменов с хвостом >0: {len(cand)}; максимум хвоста на домене: {cand[0]["tail"]} ({cand[0]["домен"]}).\n')
worst = []
for d in cand[:40]:
    v = [x for x in base if x['домен'] != d['домен']]
    worst.append((oe_of(v)[0], d['домен'], d['tail'], d['late_group'], d['зона']))
worst.sort()
out.write('  Худшие/лучшие 5 по влиянию одного домена на O/E(0):\n')
for oe, dom, t, g, z in worst[:5] + worst[-5:]:
    out.write(f'    без {dom:14s} (хвост {t}, late47 {g:4s}, {z:7s}): O/E(0) = {fmt(oe)}\n')
# джекнайф по стратам
pl = list(_by(base, key).items())
js = []
for pk, v in pl:
    if len(v) < 2: continue
    rest = [d for d in base if key(d) != pk]
    js.append((oe_of(rest)[0], pk, len(v), sum(d['tail'] for d in v)))
js.sort()
out.write(f'  Джекнайф по стратам ({len(js)} страт): O/E(0) от {fmt(js[0][0])} до {fmt(js[-1][0])}.\n')
for oe, pk, n, t in js[:3] + js[-3:]:
    out.write(f'    без страты {str(pk):55s} (доменов {n:3d}, хвост {t:3d}): O/E(0) = {fmt(oe)}\n')
# топ-3 домена вон
drop = {w[1] for w in worst[-3:]}
v = [d for d in base if d['домен'] not in drop]
r = strat(v, key, 'tail', 'early', lambda d: d['late_group'], G3, NSIM)
show(out, r, G3, 'early', 'late47', f'Без 3 самых влиятельных доменов ({", ".join(sorted(drop))}):')

# ---------- 6. Период и «КОНТЕНТ НЕ ЗАПИСАН» ----------
out.write('\n' + '='*110 + '\n6. ПЕРИОД: АВГУСТ ПРОТИВ СЕНТЯБРЯ И «КОНТЕНТ НЕ ЗАПИСАН»\n' + '='*110 + '\n')
for m in ('авг', 'сен'):
    v = [d for d in base if d['месяц'] == m]
    out.write(f'\n--- запуски {m} ({len(v)} доменов, хвост {sum(d["tail"] for d in v)}) ---\n')
    show(out, strat(v, key, 'tail', 'early', lambda d: d['late_group'], G3, NSIM), G3, 'early', 'late47', 'ХВОСТ, страта набор+день')
    show(out, strat(v, KEYS['набор+день+зона'], 'tail', 'early', lambda d: d['late_group'], G3, NSIM),
         G3, 'early', 'late47', 'ХВОСТ, страта набор+день+зона')
nc = age_ge(load(keep_nocontent=True), 10)
ncz = [d for d in nc if d['набор'] == NOCONTENT]
out.write(f'\n--- только «{NOCONTENT}» ({len(ncz)} доменов, хвост {sum(d["tail"] for d in ncz)}; страта = день[+зона]) ---\n')
show(out, strat(ncz, lambda d: (d['набор'], d['день']), 'tail', 'early', lambda d: d['late_group'], G3, NSIM),
     G3, 'early', 'late47', 'ХВОСТ, страта день')
show(out, strat(ncz, lambda d: (d['набор'], d['день'], d['зона']), 'tail', 'early', lambda d: d['late_group'], G3, NSIM),
     G3, 'early', 'late47', 'ХВОСТ, страта день+зона')

# ---------- 7. Выбросы и дней=1 обратно ----------
out.write('\n' + '='*110 + '\n7. ВЫБРОСЫ 3615/3286 И ДОМЕНЫ С ОДНИМ ДНЁМ — ОБРАТНО В НАБОР\n' + '='*110 + '\n')
for lbl, doms in (('с выбросами 3615/3286', age_ge(load(keep_outliers=True), 10)),
                  ('с дней=1', age_ge(load(keep_d1=True), 10)),
                  ('с выбросами и дней=1 и «не записан»', age_ge(load(True, True, True), 10))):
    out.write(f'\n--- {lbl}: {len(doms)} доменов, хвост {sum(d["tail"] for d in doms)} ---\n')
    show(out, strat(doms, key, 'tail', 'early', lambda d: d['late_group'], G3, NSIM), G3, 'early', 'late47', 'ХВОСТ')

# ---------- 8. Парные сравнения внутри страты ----------
out.write('\n' + '='*110 + '\n8. ПАРНЫЕ СРАВНЕНИЯ ВНУТРИ СТРАТЫ (late=0 против late≥1)\n' + '='*110 + '\n')
for kname, key2 in KEYS.items():
    tot0t = tot0e = tot1t = tot1e = 0; nstr = 0; sgn_lo = sgn_hi = sgn_tie = 0
    tot0c = tot1c = 0
    for pk, v in _by(base, key2).items():
        a = [d for d in v if d['late47'] == 0]; b = [d for d in v if d['late47'] > 0]
        if not a or not b: continue
        nstr += 1
        t0 = sum(d['tail'] for d in a); e0 = sum(d['early'] for d in a)
        t1 = sum(d['tail'] for d in b); e1 = sum(d['early'] for d in b)
        c0 = sum(d['search_after'] for d in a); c1 = sum(d['search_after'] for d in b)
        tot0t += t0; tot0e += e0; tot1t += t1; tot1e += e1; tot0c += c0; tot1c += c1
        if e0 and e1:
            x, y = t0/e0, t1/e1
            if x < y: sgn_lo += 1
            elif x > y: sgn_hi += 1
            else: sgn_tie += 1
    rr = ratio(ratio(tot0t, tot0e), ratio(tot1t, tot1e))
    rrc = ratio(ratio(tot0t, tot0c), ratio(tot1t, tot1c))
    p_sign = 2*min(binom_cdf(sgn_lo, sgn_lo+sgn_hi, 0.5), binom_sf(sgn_lo, sgn_lo+sgn_hi, 0.5)) if sgn_lo+sgn_hi else float('nan')
    out.write(f'  {kname:22s}: страт с обеими группами {nstr:3d}; '
              f'хвост late=0 {tot0t:3d} на {tot0e:6d} ранних, late≥1 {tot1t:3d} на {tot1e:6d}; '
              f'отношение ставок {fmt(rr)}\n')
    out.write(f'  {"":22s}  на кликах после окна: {tot0t} на {tot0c} против {tot1t} на {tot1c} — отношение {fmt(rrc)}\n')
    out.write(f'  {"":22s}  знаковый тест по стратам: ниже {sgn_lo}, выше {sgn_hi}, ничьих {sgn_tie}, p = {fmt(p_sign,4)}\n')

# ---------- 9. Дозовость и шаг 0 -> 1 ----------
out.write('\n' + '='*110 + '\n9. «ЕСТЬ/НЕТ» ИЛИ ШУМ: ДИ НА ГРУППЫ И СРАВНЕНИЕ 1-3 ПРОТИВ >=4\n' + '='*110 + '\n')
r = strat(base, key, 'tail', 'early', lambda d: d['late_group'], G3)
n1, e1_, o1, ee1, _ = r['tab']['1-3']; n2, e2_, o2, ee2, _ = r['tab']['>=4']
p = ee1/(ee1+ee2)
pv = 2*min(binom_cdf(o1, o1+o2, p), binom_sf(o1, o1+o2, p))
out.write(f'  1-3 против >=4 (биномиальный при E-долях): O {o1} и {o2}, E {fmt(ee1)} и {fmt(ee2)}, '
          f'двусторонний p = {fmt(min(1.0,pv),4)} — различия нет.\n')
n0, e0_, o0, ee0, _ = r['tab']['0']
pv0 = binom_cdf(o0, o0+o1+o2, ee0/(ee0+ee1+ee2))
out.write(f'  0 против всех (биномиальный): O(0) {o0} из {o0+o1+o2} при доле E {fmt(ee0/(ee0+ee1+ee2),3)}, '
          f'односторонний p = {fmt(pv0,4)}.\n')
out.write(f'  Абсолютный дефицит: {fmt(ee0-o0,1)} регистрации хвоста на {n0} доменах и '
          f'{sum(d["сайтов"] for d in base if d["late_group"]=="0")} сайтах.\n')

# ---------- 10. Трафик после окна: 5x и 14.6x под стратой ----------
out.write('\n' + '='*110 + '\n10. ТРАФИК ПОСЛЕ ОКНА: «в 5 раз» и «в 14,6 раза» под стратой\n' + '='*110 + '\n')
out.write('  Плотность = поисковых кликов на 100 сайто-суток.\n')
out.write(f'  {"группа":8s} {"доменов":>8s} {"пл.окно":>9s} {"пл.после":>9s} {"после/окно":>11s}\n')
for g in G3:
    v = [d for d in base if d['late_group'] == g]
    out.write(f'  {g:8s} {len(v):8d} {r2(100*sum(d["search_w"] for d in v), sum(d["exp_w"] for d in v),1):>9s} '
              f'{r2(100*sum(d["search_after"] for d in v), sum(d["exp_after"] for d in v),1):>9s} '
              f'{r2(sum(d["search_after"] for d in v)/max(1,sum(d["exp_after"] for d in v)), sum(d["search_w"] for d in v)/max(1,sum(d["exp_w"] for d in v)),3):>11s}\n')
# стратифицированное O/E плотности после окна
r = strat(base, KEYS['набор+день+зона'], 'search_after', 'exp_after', lambda d: d['late_group'], G3, 0)
show(out, r, G3, 'сайто-сут', 'late47', 'Клики после окна, E ∝ сайто-суткам после окна, страта набор+день+зона:')
oe0 = r['tab']['0'][4]; oe4 = r['tab']['>=4'][4]
out.write(f'  Отношение плотности >=4 к 0: сырое {r2(27.8,5.5,2)} раза; ВНУТРИ СТРАТЫ набор+день+зона '
          f'{fmt(ratio(oe4,oe0))} раза (O/E {fmt(oe0)} против {fmt(oe4)}) — «в 5 раз» сжимается вдвое.\n')

# ---------- 11. Конверсия клика после окна: 0.76 / 0.68 ----------
out.write('\n' + '='*110 + '\n11. КОНВЕРСИЯ КЛИКА ПОСЛЕ ОКНА (0,76 в страте; 0,68 с «не записан»)\n' + '='*110 + '\n')
def conv_block(doms, lbl, k):
    tw = sum(d['reg_w'] for d in doms); cw = sum(d['search_w'] for d in doms)
    tt = sum(d['tail'] for d in doms); ct = sum(d['search_after'] for d in doms)
    raw = ratio(ratio(tt, ct), ratio(tw, cw))
    # страта: E хвоста ∝ кликам после окна с оконной ставкой пула
    O = 0.0; E = 0.0; np_ = 0
    for pk, v in _by(doms, k).items():
        if len(v) < 2: continue
        cw_ = sum(d['search_w'] for d in v); rw_ = sum(d['reg_w'] for d in v)
        ca_ = sum(d['search_after'] for d in v)
        if cw_ <= 0 or ca_ <= 0: continue
        np_ += 1; O += sum(d['tail'] for d in v); E += ca_*rw_/cw_
    lo, hi = pois_ci(int(O))
    out.write(f'  {lbl}: сырое хвост/окно = {fmt(raw)} ({tt} на {ct} против {tw} на {cw}); '
              f'в страте O/E = {fmt(ratio(O,E))} (O={int(O)}, E={fmt(E)}, страт {np_}, '
              f'95% ДИ {fmt(lo/E)}–{fmt(hi/E)})\n')
for lbl, doms, k in (
    ('возраст ≥14, без «не записан», страта набор+день', age_ge(load(), 14), KEYS['набор+день']),
    ('возраст ≥14, без «не записан», страта набор+день+зона', age_ge(load(), 14), KEYS['набор+день+зона']),
    ('возраст ≥14, С «не записан», страта набор+день', age_ge(load(keep_nocontent=True), 14), KEYS['набор+день']),
    ('возраст ≥14, ТОЛЬКО «не записан», страта день', [d for d in age_ge(load(keep_nocontent=True), 14) if d['набор'] == NOCONTENT], KEYS['набор+день']),
    ('возраст ≥10, без «не записан», страта набор+день', base, KEYS['набор+день']),
):
    conv_block(doms, lbl, k)

# ---------- 12. tail_d5 (наверняка после окна) под жёсткой стратой ----------
out.write('\n' + '='*110 + '\n12. ХВОСТ ПО ДАТАМ С 5-го ДНЯ (наверняка вне окна обеих волн), жёсткая страта\n' + '='*110 + '\n')
for kname, key2 in KEYS.items():
    out.write(f'\n--- страта: {kname} ---\n')
    show(out, strat(base, key2, 'tail_d5', 'early', lambda d: d['late_group'], G3, NSIM), G3, 'early', 'late47', 'ХВОСТ d5')

# ---------- 13. Возраст ----------
out.write('\n' + '='*110 + '\n13. ВОЗРАСТ: ≥14 и ≥21 под жёсткой стратой\n' + '='*110 + '\n')
for a in (14, 21):
    v = age_ge(load(), a)
    out.write(f'\n--- возраст ≥{a}: {len(v)} доменов, хвост {sum(d["tail"] for d in v)} ---\n')
    show(out, strat(v, KEYS['набор+день+зона'], 'tail', 'early', lambda d: d['late_group'], G3, NSIM),
         G3, 'early', 'late47', 'ХВОСТ, страта набор+день+зона')
    show(out, strat(v, KEYS['набор+день+зона'], 'tail', 'search_after', lambda d: d['late_group'], G3, NSIM),
         G3, 'кл.после', 'late47', 'ХВОСТ, E ∝ кликам после окна')

out.flush()
print('\nГОТОВО ->', OUT)
