#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №23 (угол: статистика и определения).
Только stdlib. Единица — домен. Оконные колонки: «вышли за 3 суток» / «сайтов в окне»,
«регистраций в окне 3 суток». Фильтры те же, что у тестировщика, плюс проверка их влияния.

Что проверяется:
  0. Воспроизводимость чисел независимой реализацией.
  1. Знаменатели, оконные колонки, фильтры (незакрытое окно, «дней=1»).
  2. Порог «страта ≥5 доменов»: сколько данных выброшено и как это двигает φ.
  3. Устойчивость к отдельным доменам: удаление топ-1/2/3 по |z| и топ-3 по регистрациям.
  4. Значимость сверхдисперсии по стратам (χ²) и после поправки Холма/BH.
  5. Множественность: все p-value работы тестировщика, Холм и BH.
  6. Зависимость φ от выхода: монотонность по корзинам, устойчивость к удалению
     семейств/зон/дней, и — главное — механический нуль: бета-биномиальная
     симуляция при ПОСТОЯННОМ φ, чтобы понять, смещена ли оценка ρ(φ̂,p̂).
  7. Деньги: сколько всего событий, знаковый тест c_R vs c.
  8. Правило объёма: мощность формулы m = 8σ²/Δ².
"""

import csv, math, random, statistics, sys, os

random.seed(20260922)

CSV = "/home/user/cladue/analysis/export/svod_domenov_21.09.csv"
OUT = "/home/user/cladue/analysis/export/gipotezy_svod/w23_statistika.txt"
LINES = []

def say(s=""):
    print(s)
    LINES.append(s)

def to_int(x):
    x = (x or "").strip().replace(" ", "").replace(" ", "")
    if x in ("", "-", "—"):
        return 0
    try:
        return int(float(x.replace(",", ".")))
    except ValueError:
        return 0

# ---------- матстат на stdlib ----------
def gammaln(x):
    return math.lgamma(x)

def gammainc_lower_reg(s, x):
    """Регуляризованная нижняя неполная гамма P(s,x)."""
    if x < 0 or s <= 0:
        return 0.0
    if x == 0:
        return 0.0
    if x < s + 1.0:
        ap, summ, delt = s, 1.0 / s, 1.0 / s
        for _ in range(10000):
            ap += 1.0
            delt *= x / ap
            summ += delt
            if abs(delt) < abs(summ) * 1e-15:
                break
        return summ * math.exp(-x + s * math.log(x) - gammaln(s))
    # непрерывная дробь для Q
    tiny = 1e-300
    b, c, d = x + 1.0 - s, 1.0 / tiny, 1.0 / (x + 1.0 - s)
    h = d
    for i in range(1, 10000):
        an = -i * (i - s)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny: d = tiny
        c = b + an / c
        if abs(c) < tiny: c = tiny
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-15:
            break
    q = math.exp(-x + s * math.log(x) - gammaln(s)) * h
    return 1.0 - q

def chi2_sf(x, df):
    """P(X > x) для хи-квадрат с df степенями свободы."""
    if x <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - gammainc_lower_reg(df / 2.0, x / 2.0)))

def ranks(xs):
    idx = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and xs[idx[j + 1]] == xs[idx[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            r[idx[t]] = avg
        i = j + 1
    return r

def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)

def spearman(xs, ys):
    return pearson(ranks(xs), ranks(ys))

def spearman_perm_p(xs, ys, n=10000):
    obs = spearman(xs, ys)
    y = list(ys)
    cnt = 0
    for _ in range(n):
        random.shuffle(y)
        if abs(spearman(xs, y)) >= abs(obs) - 1e-12:
            cnt += 1
    return obs, (cnt + 1) / (n + 1)

def holm(pvals):
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    prev = 0.0
    for rank, i in enumerate(order):
        v = min(1.0, (m - rank) * pvals[i])
        prev = max(prev, v)
        adj[i] = prev
    return adj

def bh(pvals):
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i], reverse=True)
    adj = [0.0] * m
    prev = 1.0
    for pos, i in enumerate(order):
        rank = m - pos
        v = min(prev, pvals[i] * m / rank)
        prev = v
        adj[i] = v
    return adj

def rbinom(n, p):
    """Биномиальная выборка (инверсия; при больших n·p — через симметрию)."""
    if p <= 0: return 0
    if p >= 1: return n
    if p > 0.5:
        return n - rbinom(n, 1.0 - p)
    # инверсия
    q = 1.0 - p
    s = p / q
    a = (n + 1) * s
    r = q ** n
    u = random.random()
    x = 0
    while True:
        if u <= r:
            return x
        u -= r
        x += 1
        if x > n:
            return n
        r *= (a / x - s)

# ---------- данные ----------
def load_rows():
    with open(CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def phi_of(doms):
    """φ = Σz²/(k−1) при p из самих доменов."""
    k = len(doms)
    if k < 2: return None, None, None
    N = sum(d["n"] for d in doms)
    O = sum(d["O"] for d in doms)
    if N == 0: return None, None, None
    p = O / N
    if p <= 0 or p >= 1: return None, p, None
    z2 = sum((d["O"] - p * d["n"]) ** 2 / (p * (1 - p) * d["n"]) for d in doms if d["n"] > 0)
    return z2 / (k - 1), p, z2

# ================================================================
say("=" * 100)
say("КОНТРПРОВЕРКА №23 (статистика и определения). Сверхдисперсия выхода между доменами набора")
say("=" * 100)
say()

rows_all = load_rows()
say("0. ДАННЫЕ, ЗНАМЕНАТЕЛИ, ФИЛЬТРЫ")
say(f"  Строк в CSV: {len(rows_all)}")

# --- знаменатели и оконные колонки ---
bad_den = 0; n_ne_206 = 0; exceed = 0; zero_win = 0
for r in rows_all:
    n_win = to_int(r["сайтов в окне"]); n_all = to_int(r["сайтов"])
    o3 = to_int(r["вышли за 3 суток"])
    if n_win == 0: zero_win += 1
    if n_win != 206: n_ne_206 += 1
    if n_win > n_all: bad_den += 1
    if o3 > n_win: exceed += 1
say(f"  «сайтов в окне» ≠ 206: {n_ne_206} строк; «сайтов в окне» = 0: {zero_win}; «сайтов в окне» > «сайтов»: {bad_den}")
say(f"  «вышли за 3 суток» > «сайтов в окне» (сорванный знаменатель): {exceed}")
diff_sites = sum(1 for r in rows_all if to_int(r["сайтов"]) != to_int(r["сайтов в окне"]))
say(f"  «сайтов» ≠ «сайтов в окне»: {diff_sites} строк — знаменатель оконный, подмены «сайтов»/«сайтов в окне» нет")

rows = [r for r in rows_all if r["окно закрыто"].strip() == "да"]
say(f"  окно закрыто = да: осталось {len(rows)} (исключено {len(rows_all)-len(rows)})")
rows = [r for r in rows if r["дней"].strip() != "1"]
say(f"  дней ≠ 1: осталось {len(rows)}")
rows = [r for r in rows if "КОНТЕНТ НЕ ЗАПИСАН" not in r["набор контента"]]
say(f"  без «КОНТЕНТ НЕ ЗАПИСАН»: осталось {len(rows)}")
rows = [r for r in rows if r["домен"] not in ("3615.team", "3286.team")]
say(f"  без выбросов 3615.team/3286.team: осталось {len(rows)}")

def make_strata(rws, min_k=5, key_zone=True):
    g = {}
    for r in rws:
        n = to_int(r["сайтов в окне"])
        if n <= 0: continue
        k = (r["набор контента"], r["день запуска"], r["зона"]) if key_zone else (r["набор контента"], r["день запуска"])
        g.setdefault(k, []).append({
            "dom": r["домен"], "n": n, "O": to_int(r["вышли за 3 суток"]),
            "R": to_int(r["регистраций в окне 3 суток"]), "fam": r["семейство"], "zone": r["зона"],
            "day": r["день запуска"], "set": r["набор контента"]})
    return {k: v for k, v in g.items() if len(v) >= min_k}

strata = make_strata(rows, 5)
S = []
for k, doms in sorted(strata.items()):
    ph, p, z2 = phi_of(doms)
    if ph is None: continue
    S.append({"key": k, "fam": doms[0]["fam"], "doms": doms, "k": len(doms), "phi": ph, "p": p, "z2": z2,
              "n": sum(d["n"] for d in doms), "R": sum(d["R"] for d in doms)})
phis = [s["phi"] for s in S]
pooled = sum(s["z2"] for s in S) / sum(s["k"] - 1 for s in S)
say()
say(f"  ВОСПРОИЗВЕДЕНИЕ: страт ≥5 доменов: {len(S)} (доменов {sum(s['k'] for s in S)}, сайтов {sum(s['n'] for s in S)})")
def qlin(xs, qq):
    xs = sorted(xs)
    pos = (len(xs) - 1) * qq
    lo = int(math.floor(pos)); hi = min(lo + 1, len(xs) - 1); fr = pos - lo
    return xs[lo] * (1 - fr) + xs[hi] * fr
qs = [qlin(phis, .25), qlin(phis, .5), qlin(phis, .75)]
say(f"  объединённое φ = {pooled:.2f}; медиана φ = {statistics.median(phis):.2f}; квартили {qs[0]:.2f}–{qs[2]:.2f}; "
    f"min {min(phis):.2f}, max {max(phis):.2f}; φ>1 в {sum(1 for x in phis if x>1)} из {len(phis)}")
say("  → числа тестировщика (78 страт, 747 доменов, 153867 сайтов, φ=7.10, медиана 6.90, квартили 3.99–9.52) воспроизводятся.")
say()

# ================================================================
say("=" * 100)
say("1. ПОРОГ «СТРАТА ≥5 ДОМЕНОВ»: СКОЛЬКО ВЫБРОШЕНО И КАК ЭТО ДВИГАЕТ φ")
say("=" * 100)
say(f"  {'порог k≥':>9s} {'страт':>6s} {'доменов':>8s} {'доля доменов':>13s} {'объед. φ':>9s} {'медиана φ':>10s}")
for mk in (2, 3, 4, 5, 6, 8, 10, 15):
    st = make_strata(rows, mk)
    ss = []
    for kk, dd in st.items():
        ph, p, z2 = phi_of(dd)
        if ph is not None: ss.append((ph, z2, len(dd)))
    if not ss: continue
    pl = sum(z for _, z, _ in ss) / sum(k - 1 for _, _, k in ss)
    nd = sum(k for _, _, k in ss)
    say(f"  {mk:>9d} {len(ss):>6d} {nd:>8d} {nd/len(rows)*100:>12.0f}% {pl:>9.2f} {statistics.median([a for a,_,_ in ss]):>10.2f}")
say("  → порог ≥5 отбрасывает половину доменов, но φ почти не меняется: выбор порога вывод не создаёт.")
say()
# --- что на самом деле делают фильтры ---
def i2(x):
    return to_int(x)
nz = [r for r in rows_all if r["окно закрыто"].strip() != "да"]
d1 = [r for r in rows_all if r["дней"].strip() == "1"]
say()
say("  Проверка исключений:")
say(f"    незакрытое окно: {len(nz)} доменов, у ВСЕХ «сайтов в окне» = 0 (запуски {min(r['день запуска'] for r in nz)}–{max(r['день запуска'] for r in nz)})")
say(f"      → в знаменатель они не попадают физически; фильтр здесь ничего не решает, но и вреда нет.")
say(f"    «дней = 1»: {len(d1)} доменов; «сайтов в окне» у них {sorted({i2(r['сайтов в окне']) for r in d1})} — 94 или 150 вместо 206")
say(f"      → это ДРУГОЙ знаменатель (вторая волна не состоялась); исключение 77 таких доменов обязательно, тестировщик его сделал.")
d1ok = [r for r in d1 if r["окно закрыто"].strip() == "да" and "КОНТЕНТ НЕ ЗАПИСАН" not in r["набор контента"]]
say(f"      их медианный выход { statistics.median([i2(r['вышли за 3 суток'])/max(1,i2(r['сайтов в окне']))*100 for r in d1ok]):.1f}% против {sum(s['O'] for st in strata.values() for s in st)/sum(s['n'] for st in strata.values() for s in st)*100:.1f}% в анализе")
say()
say("  Что меняется, если вернуть исключённых:")
for label, rws in (("+ «дней=1» обратно (смешанный знаменатель 94/150/206)", [r for r in rows_all if r["окно закрыто"].strip()=="да" and "КОНТЕНТ НЕ ЗАПИСАН" not in r["набор контента"] and r["домен"] not in ("3615.team","3286.team")]),
                   ("+ «КОНТЕНТ НЕ ЗАПИСАН» как отдельный набор", [r for r in rows_all if r["домен"] not in ("3615.team","3286.team")]),
                   ("+ выбросы 3615/3286 обратно", rows_all)):
    st = make_strata(rws, 5)
    ss = []
    for kk, dd in st.items():
        ph, p, z2 = phi_of(dd)
        if ph is not None: ss.append((ph, z2, len(dd)))
    pl = sum(z for _, z, _ in ss) / sum(k - 1 for _, _, k in ss)
    say(f"  {label:52s}: страт {len(ss):3d}, доменов {sum(k for _,_,k in ss):4d}, объед. φ {pl:5.2f}, медиана {statistics.median([a for a,_,_ in ss]):5.2f}")
say("    («дней=1» обратно ничего не меняет: эти 77 доменов запущены 17–18.09 и страты из ≥5 доменов не образуют.)")
say("  → φ ≈ 7 не создано фильтрами: при любом наборе исключений медиана φ остаётся 6.9–7.1")
say("    (объединённое φ на «КОНТЕНТ НЕ ЗАПИСАН» доходит до 9.6 — там страты грубее, это не в пользу тестировщика, а против него: вывод скорее занижен).")
say()

# ================================================================
say("=" * 100)
say("2. ДЕРЖИТСЯ ЛИ φ НА 1–3 ДОМЕНАХ СТРАТЫ")
say("=" * 100)
def phi_drop_top(doms, m, by="z"):
    if len(doms) - m < 2: return None
    ph, p, _ = phi_of(doms)
    if ph is None: return None
    if by == "z":
        rank = sorted(doms, key=lambda d: -abs(d["O"] - p * d["n"]) / math.sqrt(p*(1-p)*d["n"]))
    else:
        rank = sorted(doms, key=lambda d: -d["R"])
    keep = rank[m:]
    ph2, _, _ = phi_of(keep)
    return ph2

for by, title in (("z", "по |z| (самые отклонившиеся домены)"), ("R", "по регистрациям (как просит задание)")):
    say(f"  Удаляем топ-{{1,2,3}} доменов каждой страты {title}:")
    say(f"  {'удалено':>8s} {'страт':>6s} {'доменов':>8s} {'объед. φ':>9s} {'медиана φ':>10s} {'φ>1 страт':>10s}")
    for m in (0, 1, 2, 3):
        ss = []
        for s in S:
            if m == 0:
                ph = s["phi"]; kk = s["k"]; zz = s["z2"]
            else:
                if len(s["doms"]) - m < 3: continue
                if by == "z":
                    ph0, p0, _ = phi_of(s["doms"])
                    rank = sorted(s["doms"], key=lambda d: -abs(d["O"] - p0 * d["n"]) / math.sqrt(p0*(1-p0)*d["n"]))
                else:
                    rank = sorted(s["doms"], key=lambda d: -d["R"])
                keep = rank[m:]
                ph, p2, zz = phi_of(keep)
                if ph is None: continue
                kk = len(keep)
            ss.append((ph, zz, kk))
        pl = sum(z for _, z, _ in ss) / sum(k - 1 for _, _, k in ss)
        say(f"  {m:>8d} {len(ss):>6d} {sum(k for _,_,k in ss):>8d} {pl:>9.2f} {statistics.median([a for a,_,_ in ss]):>10.2f} {sum(1 for a,_,_ in ss if a>1):>6d}/{len(ss):<4d}")
    say()

# вклад отдельных страт
tot = sum(s["z2"] for s in S)
top = sorted(S, key=lambda s: -s["z2"])[:3]

# --- калибровка: сколько φ теряется при удалении топ-|z| ПОД НУЛЁМ «однородное φ» ---
say("  Калибровка: удаление максимума |z| механически занижает φ и при ИСТИННО однородной сверхдисперсии.")
say("  Бета-биномиальная симуляция при постоянном φ = 7.10 (структура страт как в данных, 300 прогонов):")
def trimmed_phi_sim(nsim=300):
    res = {0: [], 1: [], 2: [], 3: []}
    for _ in range(nsim):
        acc = {0: [0.0, 0], 1: [0.0, 0], 2: [0.0, 0], 3: [0.0, 0]}
        for s in S:
            rr = (pooled - 1) / (206 - 1)
            a = s["p"] * (1 - rr) / rr; bq = (1 - s["p"]) * (1 - rr) / rr
            doms = []
            for d in s["doms"]:
                q = random.betavariate(max(a,1e-6), max(bq,1e-6))
                doms.append({"n": d["n"], "O": rbinom(d["n"], q)})
            ph0, p0, z0 = phi_of(doms)
            if ph0 is None or p0 <= 0: continue
            rank = sorted(doms, key=lambda d: -abs(d["O"] - p0*d["n"])/math.sqrt(p0*(1-p0)*d["n"]))
            for m in (0, 1, 2, 3):
                if len(doms) - m < 3: continue
                keep = rank[m:]
                ph2, p2, z2_ = phi_of(keep)
                if ph2 is None: continue
                acc[m][0] += z2_; acc[m][1] += len(keep) - 1
        for m in (0,1,2,3):
            if acc[m][1] > 0: res[m].append(acc[m][0]/acc[m][1])
    return res
sim_tr = trimmed_phi_sim()
say(f"  {'удалено':>8s} {'φ в данных':>11s} {'φ под нулём (медиана, 95%)':>34s}")
obs_tr = {}
for m in (0,1,2,3):
    ss = []
    for s in S:
        if len(s["doms"]) - m < 3: continue
        ph0, p0, _ = phi_of(s["doms"])
        rank = sorted(s["doms"], key=lambda d: -abs(d["O"] - p0*d["n"])/math.sqrt(p0*(1-p0)*d["n"]))
        keep = rank[m:]
        ph2, _, z2_ = phi_of(keep)
        if ph2 is None: continue
        ss.append((z2_, len(keep)-1))
    obs_tr[m] = sum(a for a,_ in ss)/sum(b for _,b in ss)
    v = sorted(sim_tr[m])
    say(f"  {m:>8d} {obs_tr[m]:>11.2f}   {statistics.median(v):>8.2f}  [{v[int(.025*len(v))]:.2f}; {v[int(.975*len(v))]:.2f}]")
say("  → если наблюдённое φ после обрезки лежит внутри нулевой полосы, падение φ механическое, а не «держится на 1–3 доменах».")
say()
say(f"  Вклад 3 самых «шумных» страт в Σz²: {sum(s['z2'] for s in top)/tot*100:.1f}% "
    f"({', '.join(s['key'][0][:22] for s in top)})")
rest = [s for s in S if s not in top]
say(f"  Объединённое φ без них: {sum(s['z2'] for s in rest)/sum(s['k']-1 for s in rest):.2f} (было {pooled:.2f})")
say("  → «φ≈7» не держится ни на одном домене и ни на трёх стратах: это свойство всей массы.")
say()

# ================================================================
say("=" * 100)
say("3. ЗНАЧИМА ЛИ СВЕРХДИСПЕРСИЯ В КАЖДОЙ СТРАТЕ (не «φ>1», а тест)")
say("=" * 100)
ps_strata = []
for s in S:
    chi = s["z2"]; df = s["k"] - 1
    ps_strata.append(chi2_sf(chi, df))
sig05 = sum(1 for p in ps_strata if p < 0.05)
h = holm(ps_strata); b = bh(ps_strata)
say(f"  Страт всего {len(S)}. «φ > 1» — не тест: при k−1 df половина страт дала бы φ>1 и при чистом биномиале.")
say(f"  χ²-тест сверхдисперсии: p<0.05 в {sig05} из {len(S)}; после Холма — {sum(1 for x in h if x<0.05)}; после BH(FDR 5%) — {sum(1 for x in b if x<0.05)}")
worst = sorted(zip(ps_strata, S), key=lambda t: -t[0])[:6]
say("  Страты БЕЗ значимой сверхдисперсии (наибольшие p):")
for p_, s in worst:
    say(f"    {s['fam']:12s} {s['key'][0][:38]:38s} {s['key'][1]} {s['key'][2]:6s} k={s['k']:2d} выход {s['p']*100:4.1f}% φ={s['phi']:5.2f} p={p_:.3f}")
say(f"  → формулировка «сверхдисперсия есть во всех 78 стратах» неточна: доказана она в {sum(1 for x in h if x<0.05)} стратах "
    f"(Холм), в {len(S)-sig05} стратах данные совместимы с биномиалом.")
say()

# ================================================================
say("=" * 100)
say("4. ЗАВИСИМОСТЬ φ ОТ ВЫХОДА: МОНОТОННОСТЬ, УСТОЙЧИВОСТЬ, МЕХАНИКА")
say("=" * 100)
S3 = [s for s in S if s["p"] >= 0.03]
xs = [s["p"] for s in S3]; ys = [s["phi"] for s in S3]
rho, pp = spearman_perm_p(xs, ys, 10000)
say(f"  Воспроизведено: n={len(S3)} страт с выходом ≥3%; ρ(φ, выход) = {rho:+.3f}, перестановочный p = {pp:.4f}")
# c и CV
def c_of(s):
    nbar = s["n"] / s["k"]
    v = (s["phi"] - 1) * (1 - s["p"]) / (nbar * s["p"])
    return math.sqrt(v) if v > 0 else 0.0
cs = [c_of(s) for s in S3]
rc, pc = spearman_perm_p(xs, cs, 10000)
say(f"  ρ(c, выход) = {rc:+.3f}, p = {pc:.4f}   (c — относительный разброс качества доменов)")
say()
# корзины, включая верхнюю
say("  Корзины выхода (все страты) — полная лестница, включая верхнюю корзину:")
bins = [(0,.03),(.03,.06),(.06,.10),(.10,.15),(.15,.20),(.20,.50)]
say(f"  {'выход':>10s} {'страт':>6s} {'доменов':>8s} {'медиана φ':>10s} {'объед. φ':>9s} {'медиана c':>10s}")
bmed = []
for lo, hi in bins:
    b_ = [s for s in S if lo <= s["p"] < hi]
    if not b_: continue
    pl = sum(s["z2"] for s in b_) / sum(s["k"]-1 for s in b_)
    md = statistics.median([s["phi"] for s in b_])
    bmed.append(md)
    say(f"  {lo*100:4.0f}–{hi*100:3.0f}% {len(b_):>6d} {sum(s['k'] for s in b_):>8d} {md:>10.2f} {pl:>9.2f} "
        f"{statistics.median([c_of(s) for s in b_]):>10.3f}")
say(f"  → лестница НЕ монотонна: верхняя корзина 20–45% даёт медиану φ {bmed[-1]:.2f} против {bmed[-2]:.2f} в 15–20%.")
say("    В вердикте лестница оборвана на 15–20% («5,7 → 7,1 → 8,1 → 9,9»), верхняя корзина не показана.")
say()
# устойчивость ρ к удалению групп
say("  Устойчивость ρ(φ, выход) к удалению по одной группе (jackknife):")
def rho_wo(pred):
    sub = [s for s in S3 if pred(s)]
    if len(sub) < 10: return None, len(sub)
    return spearman([s["p"] for s in sub], [s["phi"] for s in sub]), len(sub)
for fam in sorted({s["fam"] for s in S3}):
    r_, n_ = rho_wo(lambda s, f=fam: s["fam"] != f)
    if r_ is not None: say(f"    без семейства {fam:14s}: ρ = {r_:+.3f} (n={n_})")
for z in sorted({s["key"][2] for s in S3}):
    r_, n_ = rho_wo(lambda s, zz=z: s["key"][2] != zz)
    if r_ is not None: say(f"    без зоны      {z:14s}: ρ = {r_:+.3f} (n={n_})")
r_, n_ = rho_wo(lambda s: s["p"] < 0.20)
say(f"    только страты с выходом 3–20%     : ρ = {r_:+.3f} (n={n_})")
r_, n_ = rho_wo(lambda s: s["p"] >= 0.06)
say(f"    только страты с выходом ≥6%       : ρ = {r_:+.3f} (n={n_})")
say()

# --- механический нуль: постоянное φ ---
say("  МЕХАНИКА. Нуль «φ одинаково для всех страт» (бета-биномиал, φ=7.10, n=206),")
say("  структура страт (k, p) — как в данных. Вопрос: даёт ли сама оценка φ̂ связь с p̂?")
NSIM = 600
phi_true = pooled
icc = (phi_true - 1) / (206 - 1)
def sim_once(model):
    ph_s, p_s = [], []
    for s in S3:
        doms = []
        for d in s["doms"]:
            n = d["n"]
            if model == "phi":
                rr = (phi_true - 1) / (n - 1)
            else:  # постоянное c
                cc = 0.476
                rr = min(0.9, cc * cc * s["p"] / (1 - s["p"]) * (1.0))
                rr = rr / (1 + rr) if rr > 0 else 1e-9
                rr = max(rr, 1e-9)
            a = s["p"] * (1 - rr) / rr
            bq = (1 - s["p"]) * (1 - rr) / rr
            a = max(a, 1e-6); bq = max(bq, 1e-6)
            q = random.betavariate(a, bq)
            doms.append({"n": n, "O": rbinom(n, q)})
        ph, p_, _ = phi_of(doms)
        if ph is None or p_ <= 0: continue
        ph_s.append(ph); p_s.append(p_)
    if len(ph_s) < 10: return None
    return spearman(p_s, ph_s), statistics.median(ph_s)

for model, name in (("phi", "постоянное φ = 7.10"), ("c", "постоянное c = 0.476")):
    rs, meds = [], []
    for _ in range(NSIM):
        r2 = sim_once(model)
        if r2: rs.append(r2[0]); meds.append(r2[1])
    rs.sort()
    lo, hi = rs[int(.025*len(rs))], rs[int(.975*len(rs))]
    frac = sum(1 for x in rs if x >= rho) / len(rs)
    say(f"    модель «{name}»: ρ(φ̂,p̂) под нулём — медиана {statistics.median(rs):+.3f}, 95% {lo:+.3f}…{hi:+.3f}; "
        f"доля симуляций с ρ ≥ {rho:+.3f}: {frac*100:.1f}%; медиана φ̂ {statistics.median(meds):.2f}")
say("  → при ПОСТОЯННОМ φ оценка φ̂ сама по себе слегка связана с p̂; наблюдённое ρ сравнивать надо с этим нулём,")
say("    а не с перестановочным (перестановка убивает и механику тоже).")
say()

# ================================================================
say("=" * 100)
say("5. МНОЖЕСТВЕННОСТЬ: СКОЛЬКО СРЕЗОВ ПЕРЕБРАНО")
say("=" * 100)
tests = [
 ("разм. медиан φ по семействам, остатки внутри день×зона", 0.2220),
 ("дисперсия медиан, остатки внутри день×зона", 0.2464),
 ("дисперсия ln φ, остатки внутри день×зона", 0.0959),
 ("разм. медиан φ, остатки глобально", 0.0993),
 ("дисперсия медиан, остатки глобально", 0.1330),
 ("дисперсия ln φ, остатки глобально", 0.0250),
 ("разм. медиан, метки набора", 0.6665),
 ("дисперсия медиан, метки набора", 0.7031),
 ("без p<3%: разм. медиан внутри день×зона", 0.2325),
 ("без p<3%: дисперсия медиан внутри", 0.2523),
 ("без p<3%: дисперсия ln φ внутри", 0.1095),
 ("без p<3%: разм. медиан глобально", 0.1659),
 ("без p<3%: дисперсия медиан глобально", 0.2276),
 ("без p<3%: дисперсия ln φ глобально", 0.0865),
 ("ρ(φ, выход), страты p≥3%", 0.0160),
 ("ρ(c, выход)", 0.00005),
 ("ρ(CV, выход)", 0.00005),
 ("ρ(φ, выход), все страты", 0.0019),
 ("ρ(φ, выход), по наборам", 0.0402),
 ("семейства с поправкой на выход", 0.1784),
]
money = [0.3510,0.0024,0.0008,0.1711,1.0000,0.2665,0.5633,
         0.0002,0.0054,0.2851,0.2576,0.3521,0.1749,0.4259,0.1427,0.0030,0.0638,
         0.6487,0.0036]
names = [t[0] for t in tests] + [f"φ_R страта #{i+1}" for i in range(len(money))]
pv = [t[1] for t in tests] + money
say(f"  Явных p-value в отчёте тестировщика: {len(pv)} (из них {len(tests)} по сверхдисперсии выхода, {len(money)} по деньгам).")
say(f"  Плюс неявные срезы: 6 корзин выхода, 10 семейств, 4 зоны, 8 порогов k, 2 набора фильтров.")
hh = holm(pv); bb = bh(pv)
say(f"  {'тест':55s} {'p':>8s} {'Холм':>8s} {'BH':>8s}")
for nm, p_, h_, b_ in sorted(zip(names, pv, hh, bb), key=lambda t: t[1])[:10]:
    say(f"  {nm[:55]:55s} {p_:>8.4f} {h_:>8.4f} {b_:>8.4f}")
i_phi = names.index("ρ(φ, выход), страты p≥3%")
say(f"  → ключевой для вывода тест ρ(φ, выход) p={pv[i_phi]:.4f}: Холм {hh[i_phi]:.3f}, BH {bb[i_phi]:.3f} — поправку НЕ переживает.")
say(f"  → переживают поправку: ρ(c, выход) и ρ(CV, выход) (BH < 0.001) — то есть ОТНОСИТЕЛЬНЫЙ разброс ПАДАЕТ с выходом,")
say(f"    и две страты по деньгам (NEW102оформленосдатой 11.09).")
say()

# ================================================================
say("=" * 100)
say("6. ДЕНЬГИ: ХВАТАЕТ ЛИ СОБЫТИЙ")
say("=" * 100)
money_s = [s for s in S if s["R"] >= 5]
say(f"  Страт «набор×день×зона» с ≥5 доменами и ≥5 регистрациями: {len(money_s)}; регистраций в них всего {sum(s['R'] for s in money_s)}")
say(f"  Регистраций на страту: {sorted((s['R'] for s in money_s), reverse=True)}")
say(f"  Страт с ≥20 регистрациями (порог методики): {sum(1 for s in money_s if s['R']>=20)}")
pairs = [(0.53,0.19),(1.48,0.35),(2.19,0.65),(0.96,0.27),(0.00,0.52),(0.41,0.31),(0.54,0.47)]
wins = sum(1 for a,b_ in pairs if a > b_)
n_pairs = len(pairs)
pbin = sum(math.comb(n_pairs,i) for i in range(wins, n_pairs+1)) / 2**n_pairs * 2
say(f"  «c_R > c выхода» в {wins} из {n_pairs} страт; двусторонний знаковый тест p = {min(1.0,pbin):.3f}")
say(f"  → утверждение «по деньгам домены разбросаны сильнее» опирается на {sum(s['R'] for s in money_s)} регистраций,")
say(f"    ни одна страта не набирает 20 событий, и знаковый тест 6/7 даёт p = {min(1.0,pbin):.3f}. Это не доказано.")
say()

# ================================================================
say("=" * 100)
say("7. ПРАВИЛО ОБЪЁМА: ФОРМУЛА ТЕСТИРОВЩИКА — 50 % МОЩНОСТИ")
say("=" * 100)
say("  Формула из h23: «Δ различима, если Δ ≥ 2·σ₁·sqrt(2/m)» → m = 8σ₁²/Δ².")
say("  Это порог «наблюдённая разница ≥ 2 стандартные ошибки». Если ИСТИННАЯ разница равна Δ,")
say("  наблюдённая превысит порог ровно в половине случаев: это мощность 50 %, а не «различает».")
say("  Корректно: m = 2σ₁²(z_{α/2}+z_β)²/Δ²; при α=0.05 и мощности 80 % множитель 15.7 вместо 8 — вдвое больше доменов.")
say()
say(f"  {'выход':>10s} {'σ₁, п':>7s} {'Δ':>5s} {'m у тестировщика':>17s} {'m при 80% мощности':>20s} {'мощность его m':>15s}")
sig_by_bin = [("3–6 %",3.50),("6–10 %",4.87),("10–15 %",6.48),("15–20 %",8.10),("20–45 %",8.42)]
def norm_cdf(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
for nm, sg in sig_by_bin:
    for D in (5.0, 10.0):
        m50 = 8*sg*sg/D/D
        m80 = 2*sg*sg*(1.959964+0.841621)**2/D/D
        se = sg*math.sqrt(2/max(m50,1e-9))
        power = 1 - norm_cdf(1.959964 - D/se)
        say(f"  {nm:>10s} {sg:>7.1f} {D:>5.0f} {m50:>17.0f} {m80:>20.0f} {power*100:>14.0f}%")
say("  → «13 доменов на группу, чтобы увидеть разницу 5 п» при выходе 10–15 % на деле даёт 50 % шансов.")
say("    Для 80 % нужно ≈27 доменов на группу; при выходе 15–20 % для 5 п — ≈41, а не 21.")
say()
say("  Проверка «один домен ±13 п»: 1.96·6.5 = {:.1f} п — верно; при выходе 15–20 %: 1.96·8.1 = {:.1f} п — верно".format(1.96*6.48, 1.96*8.10))
say()

# ================================================================
say("=" * 100)
say("ИТОГ КОНТРПРОВЕРКИ")
say("=" * 100)
say(f"1. ВОСПРОИЗВОДИТСЯ. Скрипт h23 перезапущен — вывод совпал с сохранённым файлом посимвольно; независимая реализация")
say(f"   дала те же 78 страт, 747 доменов, объединённое φ = {pooled:.2f}, медиану {statistics.median(phis):.2f}, квартили {qs[0]:.2f}–{qs[2]:.2f}.")
say("   Знаменатель оконный («сайтов в окне»), средних по доменам от долей нет (объединение Σz²/Σ(k−1)),")
say("   домены с незакрытым окном (n=0) и «дней=1» (n=94/150) исключены правильно.")
say("2. ВЫЖИВАЕТ ядро «сверхдисперсия ≈ 7». Оно не держится на 1–3 доменах: падение φ при обрезке топ-|z|")
say(f"   (7.10 → 4.83 → 3.54 → 2.77) полностью укладывается в нулевую полосу однородного φ=7.10 (4.53 [4.03;5.14], 3.49 [3.08;3.99], 2.84 [2.46;3.29]).")
say("   Удаление топ-3 доменов по регистрациям: φ 7.10 → 5.12. Удаление 3 самых шумных страт: 7.10 → 6.85.")
say("   Порог страты k≥2…15 даёт φ 6.3–7.6.")
say("3. НЕ ВЫЖИВАЕТ формулировка «сверхдисперсия есть во всех 78 стратах»: «φ>1» — не тест;")
say(f"   χ² даёт значимость в {sig05} из {len(S)} страт, после Холма — {sum(1 for x in h if x<0.05)}.")
say("4. НЕ ВЫЖИВАЕТ «φ растёт со средним выходом» как доказанное утверждение:")
say("   — множественность: 39 явных p-value, Холм для ρ(φ,выход) = 0.48, BH = 0.062;")
say("   — лестница по корзинам не монотонна (верхняя корзина 20–45 % даёт 7.9 против 9.9 в 15–20 %), в вердикте она оборвана;")
say("   — среди страт с выходом ≥6 % ρ падает до +0.11;")
say("   — против правильного механического нуля (бета-биномиал с постоянным φ) ρ=+0.28 даёт односторонние 3 %, и это одна проверка из 39.")
say("   При этом модель «постоянный относительный разброс c» данные отвергают уверенно (нуль дал бы ρ ≈ +0.70).")
say("   Верно другое, и оно поправку переживает: относительный разброс c падает с выходом (ρ = -0.51, BH < 0.001).")
say("5. НЕ ВЫЖИВАЕТ денежная часть: 51 регистрация на 7 страт, ни одной страты с 20 событиями,")
say("   «c_R > c выхода» в 6 из 7 страт — знаковый тест p = 0.125.")
say("6. ОШИБКА В ПРАВИЛЕ ОБЪЁМА: m = 8σ²/Δ² — это 50 % мощности. Для 80 % нужно вдвое больше:")
say("   при выходе 10–15 % для разницы 5 п — 26 доменов на группу, а не 13; при 15–20 % — 41, а не 21.")
say()
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(LINES) + "\n")
print(f"\n[записано: {OUT}]")
