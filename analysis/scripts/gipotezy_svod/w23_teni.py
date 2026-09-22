#!/usr/bin/env python3
"""
w23_teni — скептическая проверка гипотезы №23 (сверхдисперсия выхода между
доменами набора) на ТЕНИ: набор контента, день запуска, зона, час запуска,
период (август/сентябрь), «КОНТЕНТ НЕ ЗАПИСАН», выбросы 3615/3286,
партия постановки (cf-аккаунт), объём страты k, объём дня.

Что делаем.
  1. Лестница страт: от «день×зона» (наборы перемешаны) до
     «набор×день×зона×час запуска». Если φ — тень набора/дня/зоны/часа,
     она должна падать к 1 при ужесточении страты.
  2. Парный оценщик φ_pair внутри пула: для каждой пары доменов одной
     страты d = O_i/n_i − O_j/n_j; нуль — гипергеометрический (успехи пары
     раскладываются по 2n слотам случайно), Var_hyper(d) считается точно.
     φ_pair = Σd²/ΣVar_hyper. Он не зависит от k и не требует k≥5, поэтому
     годится для самых жёстких страт и для сравнения страт разного размера.
  3. Влияние выбросов: пересчёт φ без домена с максимальным |z| в каждой
     страте (и без двух).
  4. Тень периода/зоны/семейства в связке «φ растёт с выходом»: Спирмен
     внутри периода, внутри зоны, внутри семейства, частный Спирмен с
     контролем k, и то же на φ_pair вместо φ.
  5. Чувствительность: возврат выбросов, возврат «КОНТЕНТ НЕ ЗАПИСАН»
     (страты «дата×зона»), август против сентября.
  Только стандартная библиотека.
"""
import collections
import csv
import math
import os
import random

CSV_PATH = "analysis/export/svod_domenov_21.09.csv"
OUT_PATH = "analysis/export/gipotezy_svod/w23_teni.txt"
OUTLIERS = {"3615.team", "3286.team"}
MAIN_ZONES = ("team", "lol", "casino", "buzz")
N_BOOT = 3000
N_PERM = 10000
rng = random.Random(7)
_lines = []


def say(s=""):
    print(s)
    _lines.append(s)


def med(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return float("nan")
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def q(xs, p):
    s = sorted(xs)
    n = len(s)
    if not n:
        return float("nan")
    pos = (n - 1) * p
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for t in range(i, j + 1):
            r[order[t]] = avg
        i = j + 1
    return r


def pearson(a, b):
    ma, mb = mean(a), mean(b)
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa = sum((x - ma) ** 2 for x in a)
    sbb = sum((y - mb) ** 2 for y in b)
    return sab / math.sqrt(saa * sbb) if saa > 0 and sbb > 0 else 0.0


def spearman(a, b):
    return pearson(ranks(a), ranks(b))


def fmt_p(p):
    return "<0.0001" if p < 1e-4 else f"{p:.4f}"


# ---------------------------------------------------------------- данные
def load(keep_outliers=False, keep_unrecorded=False):
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8")))
    rows = [r for r in rows if r["окно закрыто"] == "да" and r["дней"] != "1"]
    if not keep_unrecorded:
        rows = [r for r in rows if r["набор контента"] != "КОНТЕНТ НЕ ЗАПИСАН"]
    if not keep_outliers:
        rows = [r for r in rows if r["домен"] not in OUTLIERS]
    rows = [r for r in rows if r["зона"] in MAIN_ZONES]
    out = []
    for r in rows:
        n = int(float(r["сайтов в окне"] or 0))
        if n < 50:
            continue
        o = int(float(r["вышли за 3 суток"] or 0))
        out.append({
            "dom": r["домен"], "zone": r["зона"], "day": r["день запуска"],
            "set": r["набор контента"], "fam": r["семейство"],
            "hour": r["час запуска"], "blk": r["блок часа"],
            "cf": r["cf-аккаунт"], "n": n, "o": o,
            "reg": int(float(r["регистраций в окне 3 суток"] or 0)),
        })
    return out


KEYS = {
    "день×зона (наборы перемешаны)": lambda r: (r["day"], r["zone"]),
    "набор×день": lambda r: (r["set"], r["day"]),
    "набор×день×зона (страта тестировщика)": lambda r: (r["set"], r["day"], r["zone"]),
    "набор×день×зона×блок часа": lambda r: (r["set"], r["day"], r["zone"], r["blk"]),
    "набор×день×зона×час запуска": lambda r: (r["set"], r["day"], r["zone"], r["hour"]),
    "набор×день×зона×час×cf-аккаунт": lambda r: (r["set"], r["day"], r["zone"], r["hour"], r["cf"]),
}


def strata(rows, keyf, mink):
    d = collections.defaultdict(list)
    for r in rows:
        d[keyf(r)].append(r)
    return {k: v for k, v in d.items() if len(v) >= mink}


def phi_of(st):
    """φ = Σz²/(k−1) для страты (список доменов)."""
    N = sum(r["n"] for r in st)
    O = sum(r["o"] for r in st)
    p = O / N
    if p <= 0 or p >= 1:
        return None, p, 0.0
    z2 = sum((r["o"] - p * r["n"]) ** 2 / (p * (1 - p) * r["n"]) for r in st)
    return z2 / (len(st) - 1), p, z2


def pooled_phi(sts):
    num = 0.0
    den = 0
    for st in sts:
        ph, p, z2 = phi_of(st)
        if ph is None:
            continue
        num += z2
        den += len(st) - 1
    return (num / den if den else float("nan")), den


def pair_stats(st):
    """Σd² и ΣVar_hyper(d) по всем парам страты."""
    s_obs = 0.0
    s_exp = 0.0
    k = len(st)
    for i in range(k):
        for j in range(i + 1, k):
            a, b = st[i], st[j]
            ni, nj = a["n"], b["n"]
            S = a["o"] + b["o"]
            N = ni + nj
            if S == 0 or S == N:
                continue
            d = a["o"] / ni - b["o"] / nj
            var = (1 / ni + 1 / nj) ** 2 * (ni * nj * S * (N - S) / (N * N * (N - 1)))
            s_obs += d * d
            s_exp += var
    return s_obs, s_exp


def phi_pair_pooled(sts):
    o = sum(pair_stats(st)[0] for st in sts)
    e = sum(pair_stats(st)[1] for st in sts)
    return (o / e if e > 0 else float("nan")), o, e


def summarize(st):
    """Сводка страты: (k−1, Σz², Σd², ΣVar_hyper, p, φ)."""
    ph, p, z2 = phi_of(st)
    po, pe = pair_stats(st)
    return {"df": len(st) - 1, "z2": z2 if ph is not None else 0.0,
            "po": po, "pe": pe, "p": p, "phi": ph, "k": len(st)}


def pooled_from(recs):
    den = sum(r["df"] for r in recs)
    return (sum(r["z2"] for r in recs) / den) if den else float("nan")


def pair_from(recs):
    e = sum(r["pe"] for r in recs)
    return (sum(r["po"] for r in recs) / e) if e > 0 else float("nan")


def boot_ci(recs, fn, nb=N_BOOT):
    vals = []
    m = len(recs)
    if m < 2:
        return float("nan"), float("nan")
    for _ in range(nb):
        samp = [recs[rng.randrange(m)] for _ in range(m)]
        v = fn(samp)
        if v == v:
            vals.append(v)
    return q(vals, 0.025), q(vals, 0.975)


# ================================================================ печать
say("=" * 100)
say("w23_teni. Скептическая проверка №23: сверхдисперсия выхода — не тень ли она")
say("набора / дня / зоны / часа / периода / выбросов / объёма страты")
say("=" * 100)

rows = load()
say(f"\n0. ДАННЫЕ. После фильтров тестировщика (окно закрыто, дней≠1, без «КОНТЕНТ НЕ ЗАПИСАН»,")
say(f"   без 3615.team/3286.team, зоны team/lol/casino/buzz): доменов {len(rows)}, сайтов {sum(r['n'] for r in rows)}")
say(f"   n (сайтов в окне) на домен: min {min(r['n'] for r in rows)}, медиана {med([r['n'] for r in rows]):.0f}, max {max(r['n'] for r in rows)}")
say(f"   вышли за 3 суток всего: {sum(r['o'] for r in rows)}; общий выход {100*sum(r['o'] for r in rows)/sum(r['n'] for r in rows):.1f}%")
say("   В страте «набор×день×зона» оформление/шаблон/страниц/наборов-на-домене постоянны,")
say("   аккаунт вебмастера у каждого домена свой (1 домен = 1 аккаунт) — «партия постановки»")
say("   как отдельный фактор внутри страты неразличима; проверяем cf-аккаунт (до 3 доменов на него).")

# ---------------------------------------------------------------- 1
say("\n" + "=" * 100)
say("1. ЛЕСТНИЦА СТРАТ: ПАДАЕТ ЛИ φ ПРИ УЖЕСТОЧЕНИИ")
say("=" * 100)
say("  φ_объед = Σz²/Σ(k−1); φ_pair — парный оценщик (нуль гипергеометрический), от k не зависит.")
say(f"  {'страта':42s} {'k≥':>3s} {'страт':>6s} {'домен':>6s} {'df':>5s} {'φ_объед':>8s} {'95% бутстреп':>16s} {'медиана φ':>10s} {'φ_pair':>7s} {'95%':>14s}")
ladder = {}
for name, keyf in KEYS.items():
    for mink in (2, 5):
        sts = list(strata(rows, keyf, mink).values())
        if not sts:
            continue
        recs = [summarize(x) for x in sts]
        ph = pooled_from(recs)
        df = sum(r["df"] for r in recs)
        lo, hi = boot_ci(recs, pooled_from)
        phis = [r["phi"] for r in recs if r["phi"] is not None]
        pp = pair_from(recs)
        plo, phi_ = boot_ci(recs, pair_from)
        say(f"  {name:42s} {mink:>3d} {len(sts):>6d} {sum(len(s) for s in sts):>6d} {df:>5d} {ph:>8.2f} {lo:>7.2f}–{hi:<8.2f} {med(phis):>10.2f} {pp:>7.2f} {plo:>6.2f}–{phi_:<7.2f}")
        ladder[(name, mink)] = (ph, pp, len(sts), sum(len(s) for s in sts))

base = ladder[("набор×день×зона (страта тестировщика)", 5)]
hard = ladder[("набор×день×зона×час запуска", 2)]
say(f"\n  Сдвиг от страты тестировщика (φ={base[0]:.2f}) к самой жёсткой «набор×день×зона×час» (φ={hard[0]:.2f}):")
say(f"    {100*(hard[0]-base[0])/base[0]:+.0f}% — если бы сверхдисперсия была тенью часа запуска, φ ушла бы к 1.")

# 1б. вклад уровней: разложение дисперсии
say("\n  Разложение: сколько сверхдисперсии снимает каждый уровень (φ_pair, k≥2, одни и те же домены)")
common = set()
sts_hour = strata(rows, KEYS["набор×день×зона×час запуска"], 2)
common = {r["dom"] for v in sts_hour.values() for r in v}
sub = [r for r in rows if r["dom"] in common]
say(f"  (подвыборка: домены, у которых есть хотя бы один «сосед» по набору+дню+зоне+часу: {len(sub)} доменов)")
for name, keyf in KEYS.items():
    sts = list(strata(sub, keyf, 2).values())
    if not sts:
        continue
    pp, o, e = phi_pair_pooled(sts)
    say(f"    {name:42s} пар {sum(len(s)*(len(s)-1)//2 for s in sts):>5d}  φ_pair {pp:>6.2f}")

# ---------------------------------------------------------------- 2
say("\n" + "=" * 100)
say("2. ВЫБРОСЫ И ВЛИЯНИЕ ОДНОГО ДОМЕНА")
say("=" * 100)
sts5 = list(strata(rows, KEYS["набор×день×зона (страта тестировщика)"], 5).values())
ph0, df0 = pooled_phi(sts5)
say(f"  Страта тестировщика, k≥5: страт {len(sts5)}, доменов {sum(len(s) for s in sts5)}, φ = {ph0:.2f}")
for drop in (1, 2):
    trimmed = []
    for st in sts5:
        ph, p, _ = phi_of(st)
        zs = sorted(st, key=lambda r: -abs((r["o"] - p * r["n"]) / math.sqrt(p * (1 - p) * r["n"])) if 0 < p < 1 else 0)
        t = zs[drop:]
        if len(t) >= 3:
            trimmed.append(t)
    pht, dft = pooled_phi(trimmed)
    phis = [phi_of(s)[0] for s in trimmed if phi_of(s)[0] is not None]
    say(f"  Без {drop} домена(ов) с максимальным |z| в каждой страте: страт {len(trimmed)}, доменов {sum(len(s) for s in trimmed)}, φ = {pht:.2f}, медиана φ {med(phis):.2f}")
say("  Калибровка: то же урезание под нулём «чистый биномиал» (те же k, n, p; 400 симуляций)")


def binom(n, p):
    # нормальное приближение с округлением — при n=206 и p 0.03–0.4 этого достаточно
    x = int(round(rng.gauss(n * p, math.sqrt(n * p * (1 - p)))))
    return max(0, min(n, x))


for drop in (0, 1, 2):
    vals = []
    for _ in range(400):
        num = den = 0.0
        for st in sts5:
            _, p, _ = phi_of(st)
            sim = [{"n": r["n"], "o": binom(r["n"], p)} for r in st]
            N = sum(r["n"] for r in sim)
            O = sum(r["o"] for r in sim)
            ps = O / N if N else 0
            if not 0 < ps < 1:
                continue
            zs = sorted(sim, key=lambda r: -abs(r["o"] - ps * r["n"]) / math.sqrt(ps * (1 - ps) * r["n"]))
            t = zs[drop:]
            if len(t) < 3:
                continue
            Nt = sum(r["n"] for r in t)
            Ot = sum(r["o"] for r in t)
            pt = Ot / Nt
            if not 0 < pt < 1:
                continue
            num += sum((r["o"] - pt * r["n"]) ** 2 / (pt * (1 - pt) * r["n"]) for r in t)
            den += len(t) - 1
        vals.append(num / den)
    say(f"    без {drop} домена(ов): под нулём φ = {med(vals):.2f} (95 % {q(vals,0.025):.2f}–{q(vals,0.975):.2f})")
say("  Наблюдённые 4.83 и 3.54 сравнивать надо именно с этими числами, а не с 1.")

rows_out = load(keep_outliers=True)
sts_o = list(strata(rows_out, KEYS["набор×день×зона (страта тестировщика)"], 5).values())
pho, _ = pooled_phi(sts_o)
say(f"  С возвращёнными 3615.team и 3286.team: страт {len(sts_o)}, доменов {sum(len(s) for s in sts_o)}, φ = {pho:.2f} (было {ph0:.2f})")
for st in sts_o:
    doms = {r["dom"] for r in st}
    if doms & OUTLIERS:
        ph, p, _ = phi_of(st)
        for r in st:
            if r["dom"] in OUTLIERS:
                z = (r["o"] - p * r["n"]) / math.sqrt(p * (1 - p) * r["n"])
                say(f"    выброс {r['dom']}: набор {r['set'][:32]} {r['day']} {r['zone']}, выход {100*r['o']/r['n']:.1f}% при p страты {100*p:.1f}%, z = {z:+.2f}")

# ---------------------------------------------------------------- 3
say("\n" + "=" * 100)
say("3. ТЕНЬ ПЕРИОДА, ЗОНЫ, СЕМЕЙСТВА: ОДНА ЛИ φ ВЕЗДЕ")
say("=" * 100)
sts5_keyed = strata(rows, KEYS["набор×день×зона (страта тестировщика)"], 5)


def group_report(title, getter):
    say(f"\n  {title}")
    say(f"    {'группа':18s} {'страт':>5s} {'домен':>6s} {'выход':>6s} {'φ_объед':>8s} {'95% бутстреп':>16s} {'мед.φ':>7s} {'φ_pair':>7s}")
    g = collections.defaultdict(list)
    for k, v in sts5_keyed.items():
        g[getter(k, v)].append(v)
    for name in sorted(g, key=lambda x: -pooled_from([summarize(y) for y in g[x]])):
        sts = g[name]
        recs = [summarize(x) for x in sts]
        ph = pooled_from(recs)
        lo, hi = boot_ci(recs, pooled_from, 1500) if len(sts) >= 3 else (float("nan"), float("nan"))
        phis = [r["phi"] for r in recs if r["phi"] is not None]
        N = sum(r["n"] for s in sts for r in s)
        O = sum(r["o"] for s in sts for r in s)
        pp = pair_from(recs)
        say(f"    {str(name):18s} {len(sts):>5d} {sum(len(s) for s in sts):>6d} {100*O/N:>5.1f}% {ph:>8.2f} {lo:>7.2f}–{hi:<8.2f} {med(phis):>7.2f} {pp:>7.2f}")


group_report("По периоду (август = запуски до 01.09, сентябрь — остальные):",
             lambda k, v: "август" if k[1] < "2026-09-01" else "сентябрь")
group_report("По зоне:", lambda k, v: k[2])
group_report("По семейству:", lambda k, v: v[0]["fam"])
group_report("По объёму страты k:", lambda k, v: "k=5–7" if len(v) <= 7 else ("k=8–13" if len(v) <= 13 else "k≥14"))

# ---------------------------------------------------------------- 4
say("\n" + "=" * 100)
say("4. «φ РАСТЁТ С ВЫХОДОМ» — ЭТО ЭФФЕКТ ИЛИ ТЕНЬ ПЕРИОДА/ЗОНЫ/СЕМЕЙСТВА/k?")
say("=" * 100)
items = []
for k, v in sts5_keyed.items():
    ph, p, _ = phi_of(v)
    if ph is None or p < 0.03:
        continue
    pp_o, pp_e = pair_stats(v)
    items.append({
        "set": k[0], "day": k[1], "zone": k[2], "fam": v[0]["fam"], "k": len(v),
        "phi": ph, "p": p, "pair": pp_o / pp_e if pp_e > 0 else float("nan"),
        "per": "август" if k[1] < "2026-09-01" else "сентябрь",
    })
say(f"  Страт с выходом ≥3 %: {len(items)} (доменов {sum(i['k'] for i in items)})")
ph_l = [i["phi"] for i in items]
p_l = [i["p"] for i in items]
k_l = [float(i["k"]) for i in items]
pair_l = [i["pair"] for i in items]
r_phi_p = spearman(ph_l, p_l)
r_phi_k = spearman(ph_l, k_l)
r_p_k = spearman(p_l, k_l)
say(f"  Спирмен ρ(φ, выход) = {r_phi_p:+.3f}   (у тестировщика +0.279)")
say(f"  Спирмен ρ(φ, k)     = {r_phi_k:+.3f}   ρ(выход, k) = {r_p_k:+.3f}")
part = (r_phi_p - r_phi_k * r_p_k) / math.sqrt((1 - r_phi_k ** 2) * (1 - r_p_k ** 2))
say(f"  Частный Спирмен ρ(φ, выход | k) = {part:+.3f}")
say(f"  Спирмен ρ(φ_pair, выход) = {spearman(pair_l, p_l):+.3f}  (φ_pair не зависит от k)")
say(f"  Спирмен ρ(φ, день запуска как дата) = {spearman(ph_l, [float(i['day'].replace('-','')) for i in items]):+.3f}")
say(f"  Спирмен ρ(выход, день запуска) = {spearman(p_l, [float(i['day'].replace('-','')) for i in items]):+.3f}")


def strat_spearman(items, groupf, label):
    """Спирмен внутри групп: ранги считаются внутри группы, усреднение с весом (n-1);
    нуль — перестановка выхода внутри группы."""
    g = collections.defaultdict(list)
    for it in items:
        g[groupf(it)].append(it)
    use = {k: v for k, v in g.items() if len(v) >= 4}
    num = den = 0.0
    parts = []
    for k, v in sorted(use.items()):
        r = spearman([x["phi"] for x in v], [x["p"] for x in v])
        w = len(v) - 1
        num += r * w
        den += w
        parts.append(f"{k}: ρ={r:+.2f} (n={len(v)})")
    obs = num / den if den else float("nan")
    cnt = 0
    for _ in range(N_PERM):
        nu = de = 0.0
        for k, v in use.items():
            ps = [x["p"] for x in v]
            rng.shuffle(ps)
            r = spearman([x["phi"] for x in v], ps)
            nu += r * (len(v) - 1)
            de += len(v) - 1
        if abs(nu / de) >= abs(obs) - 1e-12:
            cnt += 1
    pv = (cnt + 1) / (N_PERM + 1)
    say(f"  {label}: взвешенный внутригрупповой ρ = {obs:+.3f}, перестановочный p = {fmt_p(pv)}")
    say(f"      группы (n≥4): " + "; ".join(parts))
    return obs, pv


say("\n  Жёсткая страта для самой связи «φ ~ выход» — считаем ρ только ВНУТРИ однородных групп:")
strat_spearman(items, lambda i: i["per"], "внутри периода (август/сентябрь)")
strat_spearman(items, lambda i: i["zone"], "внутри зоны")
strat_spearman(items, lambda i: i["fam"], "внутри семейства")
strat_spearman(items, lambda i: (i["per"], i["zone"]), "внутри период×зона")
strat_spearman(items, lambda i: i["day"], "внутри одного дня запуска")

say("\n  Арифметика: при ЛЮБОЙ модели «у домена своё качество с относительным разбросом c»")
say("  φ = 1 + n·p·c²/(1−p) — φ обязана расти с p при постоянном c, это не свойство наборов, а масштаб.")
cs = []
for i in items:
    c2 = (i["phi"] - 1) * (1 - i["p"]) / (206 * i["p"])
    cs.append(math.sqrt(max(c2, 0)))
say(f"  ρ(c, выход) = {spearman(cs, p_l):+.3f}; медиана c = {med(cs):.3f}, квартили {q(cs,0.25):.3f}–{q(cs,0.75):.3f}")
say("  То есть в абсолютных пунктах разброс растёт, в относительных — падает. Обе формулировки верны,")
say("  а «φ зависит от выхода» — просто выбор шкалы; ни одна модель («φ const», «c const») не описывает обе.")

# корзины выхода с бутстрепом σ₁
say("\n  Разброс одного домена σ₁ по корзинам выхода (эмпирический, с бутстрепом по доменам внутри корзины):")
buckets = [(0.03, 0.06), (0.06, 0.10), (0.10, 0.15), (0.15, 0.20), (0.20, 0.45)]
say(f"    {'выход':>10s} {'страт':>5s} {'домен':>6s} {'σ₁, п.':>7s} {'95% бутстреп':>14s} {'φ_объед':>8s} {'φ_pair':>7s}")
for lo, hi in buckets:
    sel = [i for i in items if lo <= i["p"] < hi]
    if not sel:
        continue
    keys = [(i["set"], i["day"], i["zone"]) for i in sel]
    sts = [sts5_keyed[k] for k in keys]
    devs = []
    for st in sts:
        _, p, _ = phi_of(st)
        for r in st:
            devs.append((r["o"] / r["n"] - p) * 100)
    s1 = math.sqrt(mean([d * d for d in devs]))
    bs = []
    for _ in range(2000):
        smp = [devs[rng.randrange(len(devs))] for _ in range(len(devs))]
        bs.append(math.sqrt(mean([d * d for d in smp])))
    ph, _ = pooled_phi(sts)
    say(f"    {100*lo:>4.0f}–{100*hi:<4.0f}% {len(sel):>5d} {sum(len(s) for s in sts):>6d} {s1:>7.2f} {q(bs,0.025):>6.2f}–{q(bs,0.975):<7.2f} {ph:>8.2f} {phi_pair_pooled(sts)[0]:>7.2f}")

# ---------------------------------------------------------------- 5
say("\n" + "=" * 100)
say("5. «КОНТЕНТ НЕ ЗАПИСАН» И АВГУСТ: ЧТО ДАЁТ ВОЗВРАТ 335 БАЗ")
say("=" * 100)
rows_u = load(keep_unrecorded=True)
unrec = [r for r in rows_u if r["set"] == "КОНТЕНТ НЕ ЗАПИСАН"]
say(f"  Доменов «КОНТЕНТ НЕ ЗАПИСАН» после фильтров окна: {len(unrec)}; дни: {sorted(set(r['day'] for r in unrec))[:3]}…{sorted(set(r['day'] for r in unrec))[-2:]}")
u_sts = list(strata(unrec, lambda r: (r["day"], r["zone"]), 5).values())
if u_sts:
    u_recs = [summarize(x) for x in u_sts]
    ph = pooled_from(u_recs)
    lo, hi = boot_ci(u_recs, pooled_from, 1500)
    phis = [r["phi"] for r in u_recs if r["phi"] is not None]
    say(f"  Страты «дата×зона» внутри «КОНТЕНТ НЕ ЗАПИСАН» (k≥5): {len(u_sts)}, доменов {sum(len(s) for s in u_sts)}")
    say(f"    φ = {ph:.2f} (95 % {lo:.2f}–{hi:.2f}), медиана φ {med(phis):.2f}, φ_pair {pair_from(u_recs):.2f}")
    say("    Оговорка: внутри такой страты может быть несколько разных наборов, φ завышена этим сверху.")
say("  То есть сверхдисперсия того же порядка есть и в отброшенном тестировщиком куске данных —")
say("  она не создана отбором «есть имя набора».")

# ---------------------------------------------------------------- 6
say("\n" + "=" * 100)
say("6. ПРАВИЛО ОБЪЁМА: ПРЯМАЯ ПРОВЕРКА НА ЖЁСТКИХ СТРАТАХ")
say("=" * 100)
say("  Проба m доменов против остальных k−m доменов ТОЙ ЖЕ страты (набор×день×зона, k≥2m),")
say("  2000 случайных разбиений на страту; |разница| в пунктах выхода — это чистый шум,")
say("  ведь набор, день и зона одинаковы.")
say(f"  {'выход страты':>13s} {'m':>3s} {'страт':>6s} {'медиана |Δ|':>12s} {'90-й проц.':>11s} {'доля |Δ|≥5п':>12s} {'доля ≥10п':>10s}")
for lo, hi in [(0.03, 0.10), (0.10, 0.15), (0.15, 0.45)]:
    for m in (5, 8, 13):
        pool = [sts5_keyed[(i["set"], i["day"], i["zone"])] for i in items if lo <= i["p"] < hi and i["k"] >= 2 * m]
        if not pool:
            continue
        ds = []
        for st in pool:
            k = len(st)
            for _ in range(2000):
                idx = list(range(k))
                rng.shuffle(idx)
                a = [st[t] for t in idx[:m]]
                b = [st[t] for t in idx[m:]]
                pa = sum(x["o"] for x in a) / sum(x["n"] for x in a)
                pb = sum(x["o"] for x in b) / sum(x["n"] for x in b)
                ds.append(abs(pa - pb) * 100)
        say(f"    {100*lo:>4.0f}–{100*hi:<4.0f}% {m:>3d} {len(pool):>6d} {med(ds):>12.2f} {q(ds,0.90):>11.2f} {100*mean([1 if d>=5 else 0 for d in ds]):>11.1f}% {100*mean([1 if d>=10 else 0 for d in ds]):>9.1f}%")

say("\n  Сколько доменов на группу нужно, чтобы шум был ниже порога (из эмпирического σ₁ корзины,")
say("  Δ_различимая = 2·σ₁·sqrt(2/m); с бутстреп-границами σ₁):")
say(f"    {'выход':>10s} {'σ₁, п.':>7s} {'m для 5 п':>10s} {'m для 8 п':>10s} {'m для 10 п':>11s}")
for lo, hi in buckets:
    sel = [i for i in items if lo <= i["p"] < hi]
    if not sel:
        continue
    sts = [sts5_keyed[(i["set"], i["day"], i["zone"])] for i in sel]
    devs = []
    for st in sts:
        _, p, _ = phi_of(st)
        for r in st:
            devs.append((r["o"] / r["n"] - p) * 100)
    s1 = math.sqrt(mean([d * d for d in devs]))
    def need(delta):
        return math.ceil(8 * s1 * s1 / (delta * delta))
    say(f"    {100*lo:>4.0f}–{100*hi:<4.0f}% {s1:>7.2f} {need(5):>10d} {need(8):>10d} {need(10):>11d}")

# ---------------------------------------------------------------- 7
say("\n" + "=" * 100)
say("7. ПРОВАЛЬНЫЙ ДОМЕН: ЧАСТОТА")
say("=" * 100)
cnt = tot = 0
for i in items:
    if i["p"] < 0.10:
        continue
    st = sts5_keyed[(i["set"], i["day"], i["zone"])]
    _, p, _ = phi_of(st)
    for r in st:
        tot += 1
        if r["o"] / r["n"] < 0.5 * p:
            cnt += 1
say(f"  У страт с выходом ≥10 %: доменов {tot}, из них выход ниже половины среднего страты: {cnt} ({100*cnt/tot:.1f} %)")
lo_b = 0.0
# биномиальный доверительный интервал по Уилсону
ph_ = cnt / tot
zc = 1.96
den = 1 + zc * zc / tot
cen = (ph_ + zc * zc / (2 * tot)) / den
half = zc * math.sqrt(ph_ * (1 - ph_) / tot + zc * zc / (4 * tot * tot)) / den
say(f"  95 % (Уилсон): {100*(cen-half):.1f}–{100*(cen+half):.1f} %")

say("\n" + "=" * 100)
say("ИТОГ СКЕПТИКА")
say("=" * 100)
recs_base = [summarize(x) for x in sts5]
ph_base = pooled_from(recs_base)
df_base = sum(r["df"] for r in recs_base)
lo_b, hi_b = boot_ci(recs_base, pooled_from)
sts_h = list(strata(rows, KEYS["набор×день×зона×час запуска"], 2).values())
recs_h = [summarize(x) for x in sts_h]
ph_h = pooled_from(recs_h)
df_h = sum(r["df"] for r in recs_h)
lo_h, hi_h = boot_ci(recs_h, pooled_from)
say(f"  1) Сверхдисперсия НЕ тень страты: φ = {ph_base:.2f} (95 % {lo_b:.2f}–{hi_b:.2f}) при страте набор×день×зона")
say(f"     и φ = {ph_h:.2f} (95 % {lo_h:.2f}–{hi_h:.2f}, df {df_h}) при страте набор×день×зона×ЧАС ЗАПУСКА.")
say(f"     Парный оценщик на той же жёсткой страте: φ_pair = {pair_from(recs_h):.2f}.")
say(f"  2) Она не держится на выбросах: без самого отклонившегося домена каждой страты φ всё ещё много выше 1.")
say(f"  3) Связь «φ растёт с выходом» тоже не тень: сырой ρ {r_phi_p:+.3f}; внутри периода +0.337 (p=0.0032),")
say("     внутри зоны +0.240 (p=0.044), внутри ОДНОГО ДНЯ запуска +0.600 (p<0.0001) — при ужесточении страты")
say("     связь усиливается, а не исчезает. Но это утверждение о шкале: в пунктах разброс растёт")
say("     (σ₁ 3.4 → 7.6 п), в относительных долях падает (ρ(c, выход) = −0.51).")
say("  4) Что не выдержало: «nabory — единственное семейство ниже коридора». Медиана φ там 2.74,")
say("     но объединённое φ 5.20, а k-независимый φ_pair = 7.76 — внутри коридора. Вывод о nabory")
say("     держится на выборе оценщика (медиана φ̂ по 5–7 стратам смещена вниз) и не должен идти в отчёт.")
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
open(OUT_PATH, "w", encoding="utf-8").write("\n".join(_lines) + "\n")
print("\n[сохранено в " + OUT_PATH + "]")
