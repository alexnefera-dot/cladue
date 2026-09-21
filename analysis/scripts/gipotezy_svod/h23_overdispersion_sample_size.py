#!/usr/bin/env python3
"""
Гипотеза №23. Разброс выхода между доменами одного набора одинаков во всех
семействах (сверхдисперсия φ ≈ 6–10 биномиальной) и не зависит от среднего
выхода набора; для оценки нового набора нужно ≥12–15 доменов, проба на
5 доменах различает только разницу ≥10 пунктов выхода.

Что проверяем.
  Известно (реестр): разброс доменов внутри пула «контент + день» реален
  (116 из 122 пулов — сверхдисперсия) и ничем записанным не объясняется.
  Не установлено: одинакова ли ВЕЛИЧИНА сверхдисперсии у всех наборов и
  семейств, зависит ли она от среднего выхода, и сколько доменов нужно,
  чтобы оценить набор. Это в основном знание, но оно даёт правило объёма
  пробы и правило «один провальный домен — не приговор набору».

Как проверяем (только стандартная библиотека Python 3).
  Данные: analysis/export/svod_domenov_21.09.csv, единица — домен.
  Фильтры (число исключённых печатается): окно закрыто = да; дней ≠ 1;
  «КОНТЕНТ НЕ ЗАПИСАН» исключён (не набор, сцеплен с датой); выбросы
  3615.team и 3286.team исключены; «прочие» зоны (19 доменов по одному)
  страту из ≥5 доменов образовать не могут и отпадают сами.
  Страта = «набор контента × день запуска × зона» с ≥5 доменами, чтобы
  ни день, ни зона не раздували разброс. .buzz оставлен как отдельная
  зона-страта (там только archive), его низкий средний выход внутри
  страты ничего не раздувает.
  Выход домена: O_i = «вышли за 3 суток», n_i = «сайтов в окне».
  p = ΣO_i / Σn_i страты. Стандартизованный остаток домена
  z_i = (O_i − p·n_i) / sqrt(p(1−p)·n_i);  φ = Σz_i² / (k−1).
  φ = 1 — чистый биномиал; φ = 8 — разброс доменов в 8 раз больше
  биномиального по дисперсии (в √8 ≈ 2,8 раза по отклонению).

  (1) Семейства. По каждой страте φ; по семействам (колонка «семейство»,
      семейства с ≥3 стратами) — медиана φ, квартили, min–max, бутстреп-
      интервал медианы (2000 выборок страт), объединённое φ = Σz²/Σ(k−1).
      Статистика: размах и дисперсия медиан φ по семействам.
      Нуль «сверхдисперсия одинакова везде»: остатки z_i² обмениваемы
      между доменами. 10 000 перестановок z² между доменами (а) внутри
      группы «день × зона» (день и зона удерживаются, страты-одиночки
      в своей группе не меняются), (б) глобально; random.seed(1);
      p = доля перестановок с размахом (дисперсией) ≥ наблюдённого.
      Почему не перестановка МЕТОК набора, как в постановке: наборы
      различаются средним выходом (реестр: χ² 4447), и перемешанный
      «набор» получает φ, раздутое разницей средних, — нуль сдвинут в
      сторону «однородности». Эта перестановка всё же выполнена как
      контроль с печатью того, насколько раздувается φ под нулём.
      Тот же нуль — для «все наборы одинаковы»: дисперсия ln φ по
      стратам и число страт вне 95 %-полосы ожидаемого разброса φ̂ при
      общем φ (полоса — пересэмплирование z² из общего пула при данном
      k; для справки — нормальная теория χ²(k−1)/(k−1)).
      Чувствительность: без страт с выходом < 3 %.
  (2) Зависимость от среднего выхода. Спирмен между φ страты и её p
      (страты с p ≥ 3 %; ниже φ занижен механически — при 1–3 вышедших
      сайтах на домен разбросу негде проявиться), перестановочный p
      (10 000). Две конкурирующие модели: «φ постоянна» (ρ(φ,p) ≈ 0) и
      «постоянен относительный разброс качества доменов c = CV»,
      при котором φ ≈ 1 + n·p·c²/(1−p) растёт с p (ρ(φ,p) > 0, ρ(c,p) ≈ 0).
      c для страты = sqrt((φ−1)(1−p)/(n̄·p)). Таблица по корзинам p с
      эмпирическим разбросом одного домена σ₁ и предсказаниями обеих
      моделей. Семейства с поправкой на выход: остаток ln φ после прямой
      ln φ ~ ln p по стратам, нуль — перестановка метки семейства между
      стратами (единица — страта).
  (3) Деньги: «регистраций в окне 3 суток» R_i на домен; пуассоновская
      сверхдисперсия φ_R = Σ(R_i − μ·n_i)²/(μ·n_i)/(k−1), μ = ΣR/Σn.
      Страты «набор × день × зона» с ≥5 доменами и ≥5 регистрациями;
      нуль «нет сверхдисперсии» — 10 000 раскладок ΣR регистраций по
      доменам пропорционально n_i. Дополнительно: «набор × день» с
      объединением зон (оговорка: разные средние зон раздувают φ_R) и
      корни имён content-2026-09-14c-7str-oform-1/-2 (каждый домен там —
      свой набор «_N»; корень — приближение, не набор, и так помечен).
  (4) Рабочие числа: разброс одного домена σ₁ (эмпирический по корзинам
      выхода; справочно — по моделям σ₁ = sqrt(φ·p(1−p)/n) и
      sqrt(p(1−p)/n + (c·p)²)); для m доменов на группу — ±2σ одного
      среднего и различимая на 2σ разница двух групп Δ = 2·σ₁·sqrt(2/m);
      таблица «m доменов → различимая разница в пунктах». Прямая проверка
      на уже запущенных данных: в стратах с k ≥ 2m случайные m доменов
      как «проба» против остальных k−m той же страты (2000 выборок на
      страту) — как часто проба ошибается на ≥5 и ≥10 пунктов, когда
      разницы нет. И эмпирически: как часто у набора с выходом ≥10 %
      один домен выходит хуже половины среднего набора.

  Критерии из постановки: однородность — медианы семейств в 5–11,
  p > 0,2, |ρ| < 0,3; неоднородность — p < 0,05, назвать семейства с
  большим φ и поднять для них объём пробы.
"""
import collections
import csv
import math
import os
import random

CSV_PATH = "analysis/export/svod_domenov_21.09.csv"
OUT_PATH = "analysis/export/gipotezy_svod/h23_overdispersion_sample_size.txt"
N_PERM = 10000
N_BOOT = 2000
MIN_K = 5
P_LOW = 0.03
OUTLIERS = {"3615.team", "3286.team"}
MAIN_ZONES = ("team", "lol", "casino", "buzz")

rng = random.Random(1)
_lines = []


def say(s=""):
    print(s)
    _lines.append(s)


def to_int(x):
    x = (x or "").strip()
    return int(float(x)) if x else 0


def fmt_p(p):
    return "<0.0001" if p < 1e-4 else f"{p:.4f}"


def median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return float("nan")
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def quantile(xs, q):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return float("nan")
    pos = (n - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def variance(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


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


def spearman(xs, ys):
    rx, ry = ranks(xs), ranks(ys)
    mx, my = mean(rx), mean(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else 0.0


def spearman_perm(xs, ys, n_perm=N_PERM):
    rho = spearman(xs, ys)
    ys2 = list(ys)
    cnt = 0
    for _ in range(n_perm):
        rng.shuffle(ys2)
        if abs(spearman(xs, ys2)) >= abs(rho) - 1e-12:
            cnt += 1
    return rho, (cnt + 1) / (n_perm + 1)


# ---------------------------------------------------------------- данные
def load():
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8")))
    say(f"Прочитано строк (доменов): {len(rows)}")
    n0 = len(rows)
    rows = [r for r in rows if r["окно закрыто"] == "да"]
    say(f"  исключено «окно закрыто = нет»: {n0 - len(rows)} (осталось {len(rows)})")
    n0 = len(rows)
    rows = [r for r in rows if r["дней"] != "1"]
    say(f"  исключено «дней = 1» (день 2 ещё не был): {n0 - len(rows)} (осталось {len(rows)})")
    n0 = len(rows)
    rows = [r for r in rows if r["набор контента"] != "КОНТЕНТ НЕ ЗАПИСАН"]
    say(f"  исключено «КОНТЕНТ НЕ ЗАПИСАН»: {n0 - len(rows)} (осталось {len(rows)})")
    n0 = len(rows)
    rows = [r for r in rows if r["домен"] not in OUTLIERS]
    say(f"  исключено выбросов 3615.team / 3286.team: {n0 - len(rows)} (осталось {len(rows)})")
    n0 = len(rows)
    rows = [r for r in rows if r["зона"] in MAIN_ZONES]
    say(f"  исключено «прочих» зон (по одному домену, страты не образуют): {n0 - len(rows)} (осталось {len(rows)})")
    return rows


class Stratum:
    __slots__ = ("key", "family", "doms", "k", "n", "O", "p", "z2", "phi", "regs", "cv", "c", "idx")

    def __init__(self, key, family, doms):
        self.key = key
        self.family = family
        self.doms = doms
        self.k = len(doms)
        self.n = sum(d["n"] for d in doms)
        self.O = sum(d["O"] for d in doms)
        self.p = self.O / self.n
        self.regs = sum(d["R"] for d in doms)
        p = self.p
        if 0 < p < 1:
            self.z2 = [(d["O"] - p * d["n"]) ** 2 / (p * (1 - p) * d["n"]) for d in doms]
            self.phi = sum(self.z2) / (self.k - 1)
            shares = [d["O"] / d["n"] for d in doms]
            sd = math.sqrt(variance(shares))
            self.cv = sd / p
            nbar = self.n / self.k
            self.c = math.sqrt(max(self.phi - 1, 0) * (1 - p) / (nbar * p))
        else:
            self.z2 = [0.0] * self.k
            self.phi = float("nan")
            self.cv = float("nan")
            self.c = float("nan")
        self.idx = []


def build_strata(rows):
    by = collections.defaultdict(list)
    for r in rows:
        d = {
            "dom": r["домен"],
            "n": to_int(r["сайтов в окне"]),
            "O": to_int(r["вышли за 3 суток"]),
            "R": to_int(r["регистраций в окне 3 суток"]),
        }
        by[(r["набор контента"], r["день запуска"], r["зона"])].append((r["семейство"], d))
    strata = []
    small = 0
    small_doms = 0
    for key, lst in by.items():
        if len(lst) >= MIN_K:
            strata.append(Stratum(key, lst[0][0], [d for _, d in lst]))
        else:
            small += 1
            small_doms += len(lst)
    strata.sort(key=lambda s: (s.family, s.key[0], s.key[1], s.key[2]))
    say(f"Страт «набор × день × зона» всего: {len(by)}; с ≥{MIN_K} доменами: {len(strata)} "
        f"(доменов {sum(s.k for s in strata)}, сайтов {sum(s.n for s in strata)}); "
        f"отброшено страт с <{MIN_K} доменами: {small} ({small_doms} доменов)")
    bad = [s for s in strata if not (0 < s.p < 1)]
    if bad:
        say(f"  страт с p = 0 или 1 (φ не определено): {len(bad)} — исключены")
        strata = [s for s in strata if 0 < s.p < 1]
    # индексы доменов в общем массиве z²
    pos = 0
    for s in strata:
        s.idx = list(range(pos, pos + s.k))
        pos += s.k
    return strata


# ------------------------------------------------- перестановочная машина
def family_stats(phis_by_family, min_strata=3):
    meds = [median(v) for f, v in phis_by_family.items() if len(v) >= min_strata]
    return (max(meds) - min(meds), variance(meds)) if len(meds) >= 2 else (0.0, 0.0)


def residual_permutation(strata, group_of, n_perm, families_ok, label):
    """Перестановка z² между доменами внутри групп group_of (dict: индекс домена → группа).
    Возвращает наблюдённые и перестановочные p для размаха/дисперсии медиан по семействам
    и дисперсии ln φ по стратам."""
    z2 = []
    for s in strata:
        z2.extend(s.z2)
    groups = collections.defaultdict(list)
    for i in range(len(z2)):
        groups[group_of[i]].append(i)
    group_lists = [g for g in groups.values() if len(g) > 1]

    def stats_from(z2v):
        fam = collections.defaultdict(list)
        lnphi = []
        for s in strata:
            phi = sum(z2v[i] for i in s.idx) / (s.k - 1)
            fam[s.family].append(phi)
            lnphi.append(math.log(max(phi, 1e-9)))
        rng_, var_ = family_stats({f: v for f, v in fam.items() if f in families_ok})
        return rng_, var_, variance(lnphi), median([m for f, v in fam.items() if f in families_ok for m in [median(v)]])

    obs = stats_from(z2)
    cnt = [0, 0, 0]
    null_med = []
    z2p = list(z2)
    for _ in range(n_perm):
        for g in group_lists:
            vals = [z2p[i] for i in g]
            rng.shuffle(vals)
            for i, v in zip(g, vals):
                z2p[i] = v
        st = stats_from(z2p)
        for j in range(3):
            if st[j] >= obs[j] - 1e-12:
                cnt[j] += 1
        null_med.append(st[3])
    ps = [(c + 1) / (n_perm + 1) for c in cnt]
    say(f"  [{label}] размах медиан φ по семействам: наблюдено {obs[0]:.2f}, p = {fmt_p(ps[0])}; "
        f"дисперсия медиан: {obs[1]:.2f}, p = {fmt_p(ps[1])}; "
        f"дисперсия ln φ по стратам: {obs[2]:.3f}, p = {fmt_p(ps[2])}; "
        f"медиана медиан семейств под нулём: {median(null_med):.2f} (наблюдено {obs[3]:.2f})")
    return obs, ps


def label_permutation(strata, n_perm, families_ok):
    """Как в постановке: перестановка МЕТОК набора между доменами внутри «день × зона»
    с сохранением размеров наборов; φ пересчитывается от p перемешанного «набора»."""
    groups = collections.defaultdict(list)  # (день, зона) -> список страт
    for s in strata:
        groups[(s.key[1], s.key[2])].append(s)

    def phi_of(doms):
        n = sum(d["n"] for d in doms)
        O = sum(d["O"] for d in doms)
        p = O / n
        if not (0 < p < 1):
            return None
        return sum((d["O"] - p * d["n"]) ** 2 / (p * (1 - p) * d["n"]) for d in doms) / (len(doms) - 1)

    def stats(assign):
        fam = collections.defaultdict(list)
        allphi = []
        for s, doms in assign:
            ph = phi_of(doms)
            if ph is not None:
                fam[s.family].append(ph)
                allphi.append(ph)
        r, v = family_stats({f: x for f, x in fam.items() if f in families_ok})
        return r, v, median(allphi)

    obs = stats([(s, s.doms) for s in strata])
    cnt = [0, 0]
    null_med = []
    for _ in range(n_perm):
        assign = []
        for (day, zone), ss in groups.items():
            if len(ss) == 1:
                assign.append((ss[0], ss[0].doms))
                continue
            pool = [d for s in ss for d in s.doms]
            rng.shuffle(pool)
            pos = 0
            for s in ss:
                assign.append((s, pool[pos:pos + s.k]))
                pos += s.k
        st = stats(assign)
        for j in range(2):
            if st[j] >= obs[j] - 1e-12:
                cnt[j] += 1
        null_med.append(st[2])
    ps = [(c + 1) / (n_perm + 1) for c in cnt]
    say(f"  [метки набора внутри «день × зона», как в постановке] размах медиан: {obs[0]:.2f}, p = {fmt_p(ps[0])}; "
        f"дисперсия медиан: {obs[1]:.2f}, p = {fmt_p(ps[1])}")
    say(f"    медиана φ по всем стратам: наблюдено {obs[2]:.2f}, под этим нулём в среднем {mean(null_med):.2f} "
        f"(перемешанные «наборы» несут разницу средних выходов, φ раздувается — нуль сдвинут к «однородности»; см. докстринг)")
    return obs, ps


def poisson_phi(doms, key="R"):
    n = sum(d["n"] for d in doms)
    R = sum(d[key] for d in doms)
    mu = R / n
    if mu <= 0:
        return float("nan"), R, n
    return sum((d[key] - mu * d["n"]) ** 2 / (mu * d["n"]) for d in doms) / (len(doms) - 1), R, n


def poisson_sim_p(doms, phi_obs, n_sim=N_PERM):
    """Нуль: ΣR регистраций раскладываются по доменам с вероятностями n_i/N."""
    n_list = [d["n"] for d in doms]
    N = sum(n_list)
    R = sum(d["R"] for d in doms)
    cum = []
    acc = 0
    for n in n_list:
        acc += n
        cum.append(acc / N)
    k = len(doms)
    mu = R / N
    cnt = 0
    for _ in range(n_sim):
        counts = [0] * k
        for _ in range(R):
            u = rng.random()
            j = 0
            while cum[j] < u:
                j += 1
            counts[j] += 1
        phi = sum((counts[i] - mu * n_list[i]) ** 2 / (mu * n_list[i]) for i in range(k)) / (k - 1)
        if phi >= phi_obs - 1e-12:
            cnt += 1
    return (cnt + 1) / (n_sim + 1)


# ------------------------------------------------------------------ main
def main():
    say("=" * 100)
    say("Гипотеза №23. Сверхдисперсия выхода между доменами набора: одинакова ли по семействам, зависит ли от")
    say("среднего выхода, сколько доменов нужно для оценки набора")
    say("=" * 100)
    say()
    say("0. ДАННЫЕ И ФИЛЬТРЫ")
    rows = load()
    strata = build_strata(rows)
    all_z2 = [z for s in strata for z in s.z2]
    n_dom = len(all_z2)
    sum_df = sum(s.k - 1 for s in strata)
    phi_pooled = sum(all_z2) / sum_df
    say(f"Объединённое φ по всем {len(strata)} стратам (Σz²/Σ(k−1), {n_dom} доменов, {sum_df} степеней свободы): {phi_pooled:.2f}")
    say()

    # ---------------------------------------------------------------- 1. таблица по стратам
    say("=" * 100)
    say("1. φ ПО СТРАТАМ «НАБОР × ДЕНЬ × ЗОНА» (≥5 доменов)")
    say("=" * 100)
    say("  φ = Σ(O_i − p·n_i)²/(p(1−p)·n_i)/(k−1); CV = станд. отклонение долей выхода доменов / p; "
        "c = относительный разброс качества доменов, подразумеваемый φ (см. докстринг)")
    say(f"  {'семейство':13s} {'набор контента':46s} {'день':10s} {'зона':6s} {'k':>3s} {'сайтов':>6s} {'вышли':>5s} {'выход':>6s} "
        f"{'φ':>6s} {'CV':>5s} {'c':>5s} {'рег':>3s}")
    for s in strata:
        say(f"  {s.family:13s} {s.key[0][:46]:46s} {s.key[1]:10s} {s.key[2]:6s} {s.k:3d} {s.n:6d} {s.O:5d} {s.p*100:5.1f}% "
            f"{s.phi:6.2f} {s.cv:5.2f} {s.c:5.2f} {s.regs:3d}")
    say()
    phis = [s.phi for s in strata]
    say(f"  Все страты: n = {len(phis)}; φ медиана {median(phis):.2f}, квартили {quantile(phis, .25):.2f}–{quantile(phis, .75):.2f}, "
        f"min {min(phis):.2f}, max {max(phis):.2f}; объединённое φ {phi_pooled:.2f}")
    n_over = sum(1 for s in strata if s.phi > 1)
    say(f"  Страт с φ > 1 (сверхдисперсия): {n_over} из {len(strata)}")
    say()

    # по наборам (агрегат страт)
    say("  По наборам контента (объединение страт набора: φ_набора = Σz²/Σ(k−1)):")
    by_set = collections.defaultdict(list)
    for s in strata:
        by_set[s.key[0]].append(s)
    say(f"  {'семейство':13s} {'набор контента':46s} {'страт':>5s} {'k':>3s} {'сайтов':>6s} {'выход':>6s} {'φ':>6s} {'φ по стратам':>24s} {'рег':>3s}")
    set_rows = []
    for name, ss in sorted(by_set.items(), key=lambda kv: (kv[1][0].family, kv[0])):
        z2 = [z for s in ss for z in s.z2]
        df = sum(s.k - 1 for s in ss)
        phi = sum(z2) / df
        k = sum(s.k for s in ss)
        n = sum(s.n for s in ss)
        O = sum(s.O for s in ss)
        regs = sum(s.regs for s in ss)
        rng_txt = ", ".join(f"{s.phi:.1f}" for s in ss)
        say(f"  {ss[0].family:13s} {name[:46]:46s} {len(ss):5d} {k:3d} {n:6d} {O/n*100:5.1f}% {phi:6.2f} {rng_txt[:24]:>24s} {regs:3d}")
        set_rows.append((name, ss[0].family, phi, O / n, k, n, regs))
    say()

    # ожидаемый разброс φ̂ при общем φ
    say("  Ожидаемый разброс оценки φ̂ при ОДНОМ общем φ (пересэмплирование z² из общего пула; в скобках — нормальная теория χ²(k−1)/(k−1)):")
    ks = sorted(set(s.k for s in strata))
    band = {}
    say(f"  {'k':>3s} {'2.5%':>7s} {'50%':>7s} {'97.5%':>7s}   (φ̂/φ_общ по нормальной теории: 2.5% / 97.5%)")
    for k in ks:
        sims = []
        for _ in range(N_PERM):
            sims.append(sum(rng.choice(all_z2) for _ in range(k)) / (k - 1))
        sims.sort()
        lo, md, hi = quantile(sims, .025), quantile(sims, .5), quantile(sims, .975)
        band[k] = (lo, hi)
        chi = []
        for _ in range(4000):
            chi.append(sum(rng.gauss(0, 1) ** 2 for _ in range(k - 1)) / (k - 1))
        chi.sort()
        say(f"  {k:3d} {lo:7.2f} {md:7.2f} {hi:7.2f}   ({quantile(chi, .025):.2f} / {quantile(chi, .975):.2f})")
    outside = [s for s in strata if s.phi < band[s.k][0] or s.phi > band[s.k][1]]
    say(f"  Страт вне своей 95 %-полосы: {len(outside)} из {len(strata)} (при общем φ ожидается ≈ {0.05*len(strata):.1f}):")
    for s in outside:
        side = "ниже" if s.phi < band[s.k][0] else "выше"
        say(f"    {s.family:13s} {s.key[0][:40]:40s} {s.key[1]} {s.key[2]:6s} k={s.k:2d} выход {s.p*100:4.1f}% φ={s.phi:.2f} ({side}; полоса {band[s.k][0]:.2f}–{band[s.k][1]:.2f})")
    say()

    # ---------------------------------------------------------------- 2. семейства
    say("=" * 100)
    say("2. СЕМЕЙСТВА: ОДИНАКОВА ЛИ СВЕРХДИСПЕРСИЯ")
    say("=" * 100)
    fam = collections.defaultdict(list)
    for s in strata:
        fam[s.family].append(s)
    families_ok = sorted(f for f, v in fam.items() if len(v) >= 3)
    say(f"  Семейства с ≥3 стратами (участвуют в тесте): {', '.join(families_ok)}; "
        f"остальные ({', '.join(sorted(f for f in fam if f not in families_ok)) or '—'}) только в таблице")
    say(f"  {'семейство':13s} {'страт':>5s} {'домен':>5s} {'сайтов':>6s} {'выход':>6s} {'медиана φ':>9s} {'бутстреп 95%':>14s} {'кварт.':>12s} {'min–max':>12s} {'объед. φ':>8s} {'без p<3%':>9s}")
    fam_med = {}
    for f, ss in sorted(fam.items(), key=lambda kv: -len(kv[1])):
        ph = [s.phi for s in ss]
        boots = []
        for _ in range(N_BOOT):
            boots.append(median([rng.choice(ph) for _ in ph]))
        z2 = [z for s in ss for z in s.z2]
        df = sum(s.k - 1 for s in ss)
        n = sum(s.n for s in ss)
        O = sum(s.O for s in ss)
        ph_hi = [s.phi for s in ss if s.p >= P_LOW]
        fam_med[f] = median(ph)
        say(f"  {f:13s} {len(ss):5d} {sum(s.k for s in ss):5d} {n:6d} {O/n*100:5.1f}% {median(ph):9.2f} "
            f"{quantile(boots,.025):6.2f}–{quantile(boots,.975):<6.2f} {quantile(ph,.25):5.2f}–{quantile(ph,.75):<5.2f} "
            f"{min(ph):5.2f}–{max(ph):<5.2f} {sum(z2)/df:8.2f} {median(ph_hi) if ph_hi else float('nan'):9.2f}")
    meds_ok = {f: fam_med[f] for f in families_ok}
    say(f"  Размах медиан по семействам с ≥3 стратами: {max(meds_ok.values()) - min(meds_ok.values()):.2f} "
        f"(min {min(meds_ok, key=meds_ok.get)} {min(meds_ok.values()):.2f}, max {max(meds_ok, key=meds_ok.get)} {max(meds_ok.values()):.2f})")
    say()
    say("  Перестановочные тесты (10 000 перестановок, random.seed(1)):")
    group_dz = {}
    group_all = {}
    for s in strata:
        for i in s.idx:
            group_dz[i] = (s.key[1], s.key[2])
            group_all[i] = 0
    obs_dz, p_dz = residual_permutation(strata, group_dz, N_PERM, families_ok, "остатки z² внутри «день × зона»")
    obs_g, p_g = residual_permutation(strata, group_all, N_PERM, families_ok, "остатки z² глобально")
    obs_lab, p_lab = label_permutation(strata, N_PERM, families_ok)
    say()
    # чувствительность: без низкого выхода
    strata_hi = [s for s in strata if s.p >= P_LOW]
    low = [s for s in strata if s.p < P_LOW]
    say(f"  Чувствительность: без {len(low)} страт с выходом < {P_LOW*100:.0f} % "
        f"({'; '.join(f'{s.key[0][:30]} {s.key[1]} {s.key[2]} p={s.p*100:.1f}% φ={s.phi:.1f}' for s in low)}):")
    pos = 0
    for s in strata_hi:
        s.idx = list(range(pos, pos + s.k))
        pos += s.k
    fam_hi = collections.defaultdict(list)
    for s in strata_hi:
        fam_hi[s.family].append(s)
    families_ok_hi = sorted(f for f, v in fam_hi.items() if len(v) >= 3)
    g_dz_hi = {}
    g_all_hi = {}
    for s in strata_hi:
        for i in s.idx:
            g_dz_hi[i] = (s.key[1], s.key[2])
            g_all_hi[i] = 0
    say("    медианы: " + "; ".join(f"{f} {median([s.phi for s in v]):.2f} (n={len(v)})" for f, v in sorted(fam_hi.items(), key=lambda kv: -len(kv[1])) if f in families_ok_hi))
    obs_dz_hi, p_dz_hi = residual_permutation(strata_hi, g_dz_hi, N_PERM, families_ok_hi, "без p<3%: остатки внутри «день × зона»")
    obs_g_hi, p_g_hi = residual_permutation(strata_hi, g_all_hi, N_PERM, families_ok_hi, "без p<3%: остатки глобально")
    # восстановить индексы
    pos = 0
    for s in strata:
        s.idx = list(range(pos, pos + s.k))
        pos += s.k
    say()

    # ---------------------------------------------------------------- 3. зависимость от среднего выхода
    say("=" * 100)
    say("3. ЗАВИСИТ ЛИ φ ОТ СРЕДНЕГО ВЫХОДА НАБОРА")
    say("=" * 100)
    xs = [s.p for s in strata_hi]
    ys = [s.phi for s in strata_hi]
    cs = [s.c for s in strata_hi]
    cvs = [s.cv for s in strata_hi]
    rho_phi, p_rho_phi = spearman_perm(xs, ys)
    rho_c, p_rho_c = spearman_perm(xs, cs)
    rho_cv, p_rho_cv = spearman_perm(xs, cvs)
    say(f"  Страты с выходом ≥ {P_LOW*100:.0f} %: n = {len(strata_hi)} ({sum(s.k for s in strata_hi)} доменов)")
    say(f"  Спирмен ρ(φ, выход) = {rho_phi:+.3f}, перестановочный двусторонний p = {fmt_p(p_rho_phi)}")
    say(f"  Спирмен ρ(c, выход) = {rho_c:+.3f}, p = {fmt_p(p_rho_c)}   (c — относительный разброс качества доменов; при «постоянном φ» ρ(c,p) < 0, при «постоянном c» ρ(φ,p) > 0)")
    say(f"  Спирмен ρ(CV, выход) = {rho_cv:+.3f}, p = {fmt_p(p_rho_cv)}   (CV — сырой коэффициент вариации долей выхода доменов)")
    xs_all = [s.p for s in strata]
    ys_all = [s.phi for s in strata]
    rho_all, p_all = spearman_perm(xs_all, ys_all)
    say(f"  Для справки, со всеми стратами (включая p < 3 %): ρ(φ, выход) = {rho_all:+.3f}, p = {fmt_p(p_all)}")
    # по наборам
    sr = [r for r in set_rows if r[3] >= P_LOW]
    rho_set, p_set = spearman_perm([r[3] for r in sr], [r[2] for r in sr])
    say(f"  По наборам (объединённое φ набора, {len(sr)} наборов с выходом ≥ 3 %): ρ = {rho_set:+.3f}, p = {fmt_p(p_set)}")
    say()
    say("  По корзинам среднего выхода страты (все страты):")
    bins = [(0, .03), (.03, .06), (.06, .10), (.10, .15), (.15, .20), (.20, .45)]
    say(f"  {'выход':>10s} {'страт':>5s} {'домен':>5s} {'медиана φ':>9s} {'объед. φ':>8s} {'медиана c':>9s} {'медиана CV':>10s} {'σ₁ эмпир.':>10s} {'σ₁ при φ_общ':>12s} {'σ₁ при c_общ':>12s}")
    c_hi = median(cs)
    bin_rows = []
    for lo, hi in bins:
        ss = [s for s in strata if lo <= s.p < hi]
        if not ss:
            continue
        z2 = [z for s in ss for z in s.z2]
        df = sum(s.k - 1 for s in ss)
        # эмпирическое σ₁: корень из средней квадратичной ошибки долей выхода вокруг p страты
        resid = [(d["O"] / d["n"] - s.p) ** 2 for s in ss for d in s.doms]
        sd_emp = math.sqrt(sum(resid) / df)
        pbar = sum(s.O for s in ss) / sum(s.n for s in ss)
        sd_phi = math.sqrt(phi_pooled * pbar * (1 - pbar) / 206)
        sd_c = math.sqrt(pbar * (1 - pbar) / 206 + (c_hi * pbar) ** 2)
        say(f"  {lo*100:4.0f}–{hi*100:<4.0f}% {len(ss):5d} {sum(s.k for s in ss):5d} {median([s.phi for s in ss]):9.2f} {sum(z2)/df:8.2f} "
            f"{median([s.c for s in ss]):9.3f} {median([s.cv for s in ss]):10.2f} {sd_emp*100:9.2f}п {sd_phi*100:11.2f}п {sd_c*100:11.2f}п")
        bin_rows.append((lo, hi, len(ss), pbar, sd_emp, sd_phi, sd_c))
    say(f"  (σ₁ — разброс выхода одного домена в пунктах; «при φ_общ» = sqrt({phi_pooled:.2f}·p(1−p)/206); "
        f"«при c_общ» = sqrt(p(1−p)/206 + (c·p)²) с c = {c_hi:.3f} — медиана c по стратам с p ≥ 3 %)")
    # какая модель ближе: сумма |log(σ_emp/σ_model)| по корзинам с ≥3 стратами
    err_phi = sum(abs(math.log(r[4] / r[5])) for r in bin_rows if r[2] >= 3)
    err_c = sum(abs(math.log(r[4] / r[6])) for r in bin_rows if r[2] >= 3)
    if abs(err_phi - err_c) < 0.2 * max(err_phi, err_c):
        model_txt = "обе модели одинаково грубы: разброс растёт с выходом, но медленнее, чем при постоянном c; рабочие числа брать из эмпирических σ₁ по корзинам"
        model_c = None
    else:
        model_c = err_c < err_phi
        model_txt = f"ближе модель «{'постоянный относительный разброс c' if model_c else 'постоянное φ'}»"
    say(f"  Сумма |ln(σ₁ эмпир./σ₁ модели)| по корзинам с ≥3 стратами: постоянное φ — {err_phi:.2f}, постоянное c — {err_c:.2f} → {model_txt}")
    say()
    # семейства с поправкой на выход: остаток ln φ после прямой ln φ ~ ln p по стратам,
    # нуль — перестановка метки семейства между стратами (страта — единица)
    say("  Семейства с поправкой на средний выход (страты с p ≥ 3 %): остаток ln φ после прямой ln φ = a + b·ln p по стратам;")
    say("  нуль — 10 000 перестановок метки семейства между стратами (единица — страта; k страты не учитывается, тест грубее остаточного):")
    lx = [math.log(s.p) for s in strata_hi]
    ly = [math.log(max(s.phi, 1e-9)) for s in strata_hi]
    mx, my = mean(lx), mean(ly)
    b = sum((a - mx) * (c - my) for a, c in zip(lx, ly)) / sum((a - mx) ** 2 for a in lx)
    a0 = my - b * mx
    resid = [c - (a0 + b * x) for x, c in zip(lx, ly)]
    say(f"    прямая: ln φ = {a0:.2f} + {b:.2f}·ln p (наклон {b:.2f}: при постоянном φ ≈ 0, при постоянном c ≈ 1)")
    fams_hi = [s.family for s in strata_hi]
    fam_res = collections.defaultdict(list)
    for f, r in zip(fams_hi, resid):
        fam_res[f].append(r)
    fam_ok_res = [f for f, v in fam_res.items() if len(v) >= 3]
    meds_res = {f: median(fam_res[f]) for f in fam_ok_res}
    say("    медианы остатка по семействам (exp = во сколько раз φ выше/ниже ожидаемого при этом выходе): "
        + "; ".join(f"{f} ×{math.exp(meds_res[f]):.2f} (n={len(fam_res[f])})" for f in sorted(fam_ok_res, key=lambda f: -meds_res[f])))
    obs_r = max(meds_res.values()) - min(meds_res.values())
    cnt = 0
    labs = list(fams_hi)
    for _ in range(N_PERM):
        rng.shuffle(labs)
        fr = collections.defaultdict(list)
        for f, r in zip(labs, resid):
            fr[f].append(r)
        m = [median(v) for f, v in fr.items() if f in fam_ok_res]
        if max(m) - min(m) >= obs_r - 1e-12:
            cnt += 1
    p_fam_adj = (cnt + 1) / (N_PERM + 1)
    say(f"    размах медиан остатка {obs_r:.2f} (×{math.exp(obs_r):.2f}), перестановочный p = {fmt_p(p_fam_adj)}")
    say()

    # ---------------------------------------------------------------- 4. регистрации
    say("=" * 100)
    say("4. ДЕНЬГИ: ПУАССОНОВСКАЯ СВЕРХДИСПЕРСИЯ РЕГИСТРАЦИЙ В ОКНЕ 3 СУТОК")
    say("=" * 100)
    say("  φ_R = Σ(R_i − μ·n_i)²/(μ·n_i)/(k−1); нуль «регистрации ложатся на домены случайно, пропорционально сайтам» — "
        "10 000 раскладок; p = доля с φ_R ≥ наблюдённого.")
    say("  φ_R с φ выхода напрямую НЕ сравнимо: при 0,5–2 регистрациях на домен φ_R ≈ 1 + (регистраций на домен)·c_R², то есть даже большой")
    say("  относительный разброс доменов c_R даёт φ_R лишь ≈1,5–3. Поэтому рядом — c_R = sqrt((φ_R − 1)/(рег на домен)), сравнимый с c выхода.")
    say("  (а) Страты «набор × день × зона» с ≥5 доменами и ≥5 регистрациями:")
    reg_strata = [s for s in strata if s.regs >= 5]
    say(f"  {'набор контента':40s} {'день':10s} {'зона':6s} {'k':>3s} {'сайтов':>6s} {'рег':>3s} {'рег/дом':>18s} {'φ_R':>6s} {'p':>8s} {'c_R':>5s} {'φ вых':>6s} {'c вых':>5s}")
    phiR_list = []
    cR_list = []
    for s in reg_strata:
        phiR, R, n = poisson_phi(s.doms)
        pv = poisson_sim_p(s.doms, phiR)
        per = sorted((d["R"] for d in s.doms), reverse=True)
        mu_dom = R / s.k
        cR = math.sqrt(max(phiR - 1, 0) / mu_dom)
        phiR_list.append((phiR, s.k))
        cR_list.append(cR)
        say(f"  {s.key[0][:40]:40s} {s.key[1]:10s} {s.key[2]:6s} {s.k:3d} {s.n:6d} {R:3d} {str(per)[:18]:>18s} {phiR:6.2f} {fmt_p(pv):>8s} {cR:5.2f} {s.phi:6.2f} {s.c:5.2f}")
    pooled_R = float("nan")
    if phiR_list:
        pooled_R = sum(ph * (k - 1) for ph, k in phiR_list) / sum(k - 1 for _, k in phiR_list)
        say(f"  Медиана φ_R по {len(phiR_list)} стратам: {median([ph for ph, _ in phiR_list]):.2f}; объединённое: {pooled_R:.2f}; медиана c_R: {median(cR_list):.2f} "
            f"(c выхода в тех же стратах: медиана {median([s.c for s in reg_strata]):.2f})")
    say()
    say("  (б) «Набор × день» с объединением зон (оговорка: разные средние зон могут раздувать φ_R):")
    sd_groups = collections.defaultdict(list)
    for r in rows:
        sd_groups[(r["набор контента"], r["день запуска"])].append({
            "n": to_int(r["сайтов в окне"]), "O": to_int(r["вышли за 3 суток"]),
            "R": to_int(r["регистраций в окне 3 суток"]), "zone": r["зона"]})
    say(f"  {'набор контента':40s} {'день':10s} {'зоны':22s} {'k':>3s} {'рег':>3s} {'рег/дом':>22s} {'φ_R':>6s} {'p':>8s} {'c_R':>5s}")
    phiR_b = []
    cR_b = []
    for (name, day), doms in sorted(sd_groups.items(), key=lambda kv: -sum(d["R"] for d in kv[1])):
        R = sum(d["R"] for d in doms)
        if len(doms) < MIN_K or R < 5:
            continue
        phiR, R, n = poisson_phi(doms)
        pv = poisson_sim_p(doms, phiR)
        zones = collections.Counter(d["zone"] for d in doms)
        per = sorted((d["R"] for d in doms), reverse=True)
        cR = math.sqrt(max(phiR - 1, 0) / (R / len(doms)))
        phiR_b.append((phiR, len(doms)))
        cR_b.append(cR)
        say(f"  {name[:40]:40s} {day:10s} {str(dict(zones))[:22]:22s} {len(doms):3d} {R:3d} {str(per)[:22]:>22s} {phiR:6.2f} {fmt_p(pv):>8s} {cR:5.2f}")
    if phiR_b:
        say(f"  Медиана φ_R: {median([ph for ph, _ in phiR_b]):.2f}; объединённое: {sum(ph*(k-1) for ph,k in phiR_b)/sum(k-1 for _,k in phiR_b):.2f}; медиана c_R: {median(cR_b):.2f}")
    say()
    say("  (в) content-2026-09-14c-…: каждый домен там записан своим набором «…_N» (наборов из ≥5 доменов нет). "
        "Приближение по КОРНЮ имени (без суффикса _N) — это не набор контента, а группа вариантов одного корня; помечено как приближение:")
    roots = collections.defaultdict(list)
    for r in rows:
        name = r["набор контента"]
        if name.startswith("content-2026-09-14c-"):
            root = name.rsplit("_", 1)[0]
            roots[(root, r["день запуска"], r["зона"])].append({
                "n": to_int(r["сайтов в окне"]), "O": to_int(r["вышли за 3 суток"]),
                "R": to_int(r["регистраций в окне 3 суток"])})
    say(f"  {'корень (приближение)':40s} {'день':10s} {'зона':6s} {'k':>3s} {'рег':>3s} {'рег/дом':>22s} {'φ_R':>6s} {'p':>8s} {'c_R':>5s} {'φ вых':>6s}")
    for (root, day, zone), doms in sorted(roots.items()):
        R = sum(d["R"] for d in doms)
        if len(doms) < MIN_K:
            continue
        st = Stratum((root, day, zone), "content-дата", doms)
        if R >= 5:
            phiR, R, n = poisson_phi(doms)
            pv = poisson_sim_p(doms, phiR)
            per = sorted((d["R"] for d in doms), reverse=True)
            cR = math.sqrt(max(phiR - 1, 0) / (R / len(doms)))
            say(f"  {root[:40]:40s} {day:10s} {zone:6s} {len(doms):3d} {R:3d} {str(per)[:22]:>22s} {phiR:6.2f} {fmt_p(pv):>8s} {cR:5.2f} {st.phi:6.2f}")
        else:
            say(f"  {root[:40]:40s} {day:10s} {zone:6s} {len(doms):3d} {R:3d} {'(рег < 5)':>22s} {'—':>6s} {'—':>8s} {'—':>5s} {st.phi:6.2f}")
    say()

    # ---------------------------------------------------------------- 5. рабочие числа
    say("=" * 100)
    say("5. РАБОЧИЕ ЧИСЛА: СКОЛЬКО ДОМЕНОВ НУЖНО, ЧТОБЫ ОЦЕНИТЬ НАБОР")
    say("=" * 100)
    say("  Разброс одного домена σ₁ (в пунктах выхода). Разница двух групп по m доменов различима на 2σ, если Δ ≥ 2·σ₁·sqrt(2/m);")
    say("  один набор из m доменов оценивается с точностью ±2·σ₁/sqrt(m); для разницы Δ нужно m = 8·σ₁²/Δ² доменов на группу.")
    ms = [3, 5, 8, 10, 13, 15, 20, 30, 50]
    say()
    say("  (а) По ЭМПИРИЧЕСКОМУ σ₁ корзины выхода (раздел 3, корень средней квадратичной ошибки долей выхода доменов вокруг p страты):")
    say(f"  {'выход':>9s} {'страт':>5s} {'σ₁':>5s} | Δ 2 групп на 2σ, п, при m = " + " ".join(f"{m:>5d}" for m in ms) + " | m для Δ=5п  m для Δ=10п")
    emp_rows = {}
    for lo, hi, ns, pbar, sd_emp, sd_phi, sd_c in bin_rows:
        if ns < 3:
            continue
        emp_rows[(lo, hi)] = sd_emp
        say(f"  {lo*100:3.0f}–{hi*100:<3.0f}% {ns:5d} {sd_emp*100:4.1f}п | " + " " * 30
            + " ".join(f"{2*sd_emp*math.sqrt(2/m)*100:5.1f}" for m in ms)
            + f" | {8*sd_emp**2/0.05**2:9.1f} {8*sd_emp**2/0.10**2:11.1f}")
    say()
    say(f"  (б) По модели «постоянное φ» с φ = {phi_pooled:.2f} (объединённое; медиана по стратам {median(phis):.2f}), n = 206: σ₁ = sqrt(φ·p(1−p)/206);")
    say(f"      и по модели «постоянный относительный разброс» с c = {c_hi:.3f}: σ₁ = sqrt(p(1−p)/206 + (c·p)²). Обе — справочно, см. раздел 3.")
    for p0 in (0.06, 0.12, 0.20):
        s1_phi = math.sqrt(phi_pooled * p0 * (1 - p0) / 206)
        s1_c = math.sqrt(p0 * (1 - p0) / 206 + (c_hi * p0) ** 2)
        say(f"  Выход набора p = {p0*100:.0f} %: σ₁ по φ = {s1_phi*100:.1f} п, по c = {s1_c*100:.1f} п")
        say(f"    {'m доменов':>16s} " + " ".join(f"{m:>6d}" for m in ms))
        say(f"    {'±2σ, п (φ)':>16s} " + " ".join(f"{2*s1_phi/math.sqrt(m)*100:6.1f}" for m in ms))
        say(f"    {'Δ 2 гр., п (φ)':>16s} " + " ".join(f"{2*s1_phi*math.sqrt(2/m)*100:6.1f}" for m in ms))
        say(f"    {'Δ 2 гр., п (c)':>16s} " + " ".join(f"{2*s1_c*math.sqrt(2/m)*100:6.1f}" for m in ms))
    say()
    # прямая эмпирическая проверка «пробы на m доменах» на стратах с k ≥ 2m
    say("  (в) Прямая проверка на уже запущенных данных: в стратах с k ≥ 2m берём случайные m доменов как «пробу» и сравниваем её выход")
    say("      с выходом остальных k−m доменов той же страты (2000 выборок на страту). Это разброс, который проба показывает, когда")
    say("      на самом деле разницы нет (обе половины — один набор, день, зона):")
    say(f"  {'выход страты':14s} {'m':>3s} {'страт':>5s} {'домен':>5s} {'|Δ| медиана':>11s} {'|Δ| 90%':>8s} {'|Δ| 95%':>8s} {'доля |Δ|≥5п':>12s} {'доля |Δ|≥10п':>13s}")
    probe = {}
    for band, lo_p, hi_p in (("3–10 %", P_LOW, 0.10), ("≥ 10 %", 0.10, 1.0)):
        for m in (5, 8, 13):
            ss = [s for s in strata if s.k >= 2 * m and lo_p <= s.p < hi_p]
            if not ss:
                say(f"  {band:14s} {m:3d}     — (нет страт с k ≥ {2*m})")
                continue
            diffs = []
            for s in ss:
                idxs = list(range(s.k))
                for _ in range(2000):
                    rng.shuffle(idxs)
                    a = idxs[:m]
                    bset = idxs[m:]
                    pa = sum(s.doms[i]["O"] for i in a) / sum(s.doms[i]["n"] for i in a)
                    pb = sum(s.doms[i]["O"] for i in bset) / sum(s.doms[i]["n"] for i in bset)
                    diffs.append(abs(pa - pb))
            probe[(band, m)] = (len(ss), sum(s.k for s in ss), median(diffs), quantile(diffs, .9), quantile(diffs, .95),
                                sum(1 for d in diffs if d >= 0.05) / len(diffs), sum(1 for d in diffs if d >= 0.10) / len(diffs),
                                ", ".join(sorted(set(s.key[0][:22] for s in ss))))
            pr = probe[(band, m)]
            say(f"  {band:14s} {m:3d} {pr[0]:5d} {pr[1]:5d} {pr[2]*100:10.1f}п {pr[3]*100:7.1f}п {pr[4]*100:7.1f}п {pr[5]*100:11.1f}% {pr[6]*100:12.1f}%   [{pr[7][:70]}]")
    say("  (оговорка: остаток k−m доменов при m = 13 — это 3–13 доменов, сам не точен; |Δ| включает шум обеих половин, как и формула Δ 2 групп)")
    say()
    # эмпирика: как часто домен «хорошего» набора проваливается
    good = [s for s in strata if s.p >= 0.10]
    doms_good = [(d["O"] / d["n"], s.p) for s in good for d in s.doms]
    n_half = sum(1 for sh, p in doms_good if sh < 0.5 * p)
    n_quart = sum(1 for sh, p in doms_good if sh < 0.25 * p)
    n_5 = sum(1 for sh, p in doms_good if sh < 0.05)
    n_dbl = sum(1 for sh, p in doms_good if sh > 2 * p)
    shares_rel = sorted(sh / p for sh, p in doms_good)
    say(f"  (г) Эмпирически, страты с выходом ≥ 10 % ({len(good)} страт, {len(doms_good)} доменов): "
        f"домен хуже половины среднего своего набора — {n_half} ({n_half/len(doms_good)*100:.1f} %), "
        f"хуже четверти — {n_quart} ({n_quart/len(doms_good)*100:.1f} %), "
        f"ниже 5 % выхода — {n_5} ({n_5/len(doms_good)*100:.1f} %), лучше двойного среднего — {n_dbl} ({n_dbl/len(doms_good)*100:.1f} %).")
    say(f"      Отношение выхода домена к среднему своего набора: 5 % доменов ниже {quantile(shares_rel,.05):.2f}, "
        f"25 % ниже {quantile(shares_rel,.25):.2f}, медиана {quantile(shares_rel,.5):.2f}, 75 % ниже {quantile(shares_rel,.75):.2f}, 95 % ниже {quantile(shares_rel,.95):.2f}.")
    say()

    # ---------------------------------------------------------------- ВЫВОД
    say("=" * 100)
    say("ВЫВОД")
    say("=" * 100)
    lo_ok, hi_ok = 5, 11
    in_band = [f for f in families_ok if lo_ok <= meds_ok[f] <= hi_ok]
    out_band = [f for f in families_ok if not (lo_ok <= meds_ok[f] <= hi_ok)]
    med_txt = "; ".join(f"{f} {meds_ok[f]:.1f} ({len(fam[f])} страт)" for f in sorted(families_ok, key=lambda f: -meds_ok[f]))
    say(f"1. Сверхдисперсия есть везде: φ > 1 в {n_over} из {len(strata)} страт «набор × день × зона» ({n_dom} доменов, "
        f"{sum(s.n for s in strata)} сайтов); объединённое φ = {phi_pooled:.2f}, медиана {median(phis):.2f}, квартили "
        f"{quantile(phis,.25):.1f}–{quantile(phis,.75):.1f}. Разброс домена по дисперсии в {phi_pooled:.0f} раз больше биномиального, "
        f"по отклонению — в {math.sqrt(phi_pooled):.1f} раза.")
    say(f"   Медианы φ по семействам: {med_txt}. В коридоре 5–11: {', '.join(in_band) or '—'}; вне: {', '.join(out_band) or '—'}"
        + (f" (nabory без страт с выходом < 3 %: {median([s.phi for s in fam_hi['nabory']]):.1f}; объединённое φ nabory {sum(z for s in fam['nabory'] for z in s.z2)/sum(s.k-1 for s in fam['nabory']):.1f} — "
           f"один пул nabory411420_styled_img 06.09 .team даёт φ = 26)." if "nabory" in fam_hi else "."))
    say(f"   Размах медиан {obs_dz[0]:.2f}: перестановочный p = {fmt_p(p_dz[0])} (остатки внутри «день × зона»), {fmt_p(p_g[0])} (глобально); "
        f"дисперсия медиан p = {fmt_p(p_dz[1])} / {fmt_p(p_g[1])}. Без страт с выходом < 3 %: p = {fmt_p(p_dz_hi[0])} / {fmt_p(p_g_hi[0])}. "
        f"С поправкой на средний выход (перестановка метки семейства между стратами): p = {fmt_p(p_fam_adj)}. "
        f"Перестановка меток набора, как в постановке (нуль сдвинут к однородности): p = {fmt_p(p_lab[0])}.")
    p_fam_min = min(p_dz[0], p_g[0], p_fam_adj)
    p_fam_max = max(p_dz[0], p_g[0], p_fam_adj)
    homog = p_fam_min > 0.2
    heter = p_fam_max < 0.05
    if homog:
        say("   Разница медиан между семействами не больше того, что даёт случайная раздача тех же остатков между наборами: "
            "ни одно семейство не «стабильнее» другого сверх выборочного шума φ̂.")
    elif heter:
        big = sorted(families_ok, key=lambda f: -meds_ok[f])[:2]
        say(f"   Семейства различаются по φ сверх шума; наибольшее φ у {', '.join(big)} — для них объём пробы надо поднимать.")
    else:
        say(f"   Различие семейств не доказано и не исключено (p от {fmt_p(p_fam_min)} до {fmt_p(p_fam_max)} в зависимости от нуля): "
            f"{len(in_band)} из {len(families_ok)} семейств в коридоре 5–11, единственный кандидат на «стабильнее» — nabory "
            f"({len(fam['nabory'])} страт по 5–7 доменов, выход 1–16 %): после поправки на средний выход его φ "
            + (f"остаётся ×{math.exp(meds_res['nabory']):.2f} от ожидаемого" if 'nabory' in meds_res else "не пересчитано")
            + f", но на {len(fam_hi.get('nabory', []))} стратах это не отличимо от шума (p = {fmt_p(p_fam_adj)}); "
            f"content-дата, наоборот, ×{math.exp(meds_res.get('content-дата', 0)):.2f}.")
    say(f"   Все ли наборы одинаковы: дисперсия ln φ по стратам p = {fmt_p(p_dz[2])} / {fmt_p(p_g[2])}; страт вне 95 %-полосы общего φ: "
        f"{len(outside)} из {len(strata)} при ожидаемых ≈{0.05*len(strata):.0f} "
        f"({', '.join(sorted(set(s.key[0][:28] for s in outside)))}). "
        "Разброс φ между стратами чуть больше, чем при одном общем φ, и большая часть этого — зависимость φ от выхода, а не семейства.")
    say(f"2. Зависимость от среднего выхода: Спирмен ρ(φ, выход) = {rho_phi:+.2f}, перестановочный p = {fmt_p(p_rho_phi)} ({len(strata_hi)} страт с выходом ≥ 3 %); "
        f"по наборам ρ = {rho_set:+.2f}, p = {fmt_p(p_set)}; наклон ln φ по ln p = {b:.2f} (0 — постоянное φ, 1 — постоянный относительный разброс).")
    if p_rho_phi < 0.05:
        say(f"   Утверждение «φ не зависит от среднего выхода» опровергается: |ρ| {'<' if abs(rho_phi) < 0.3 else '≥'} 0,3, но ρ отличим от нуля (p = {fmt_p(p_rho_phi)}), и по корзинам "
            f"φ растёт: " + "; ".join(f"{r[0]*100:.0f}–{r[1]*100:.0f} % → медиана φ {median([s.phi for s in strata if r[0] <= s.p < r[1]]):.1f}" for r in bin_rows if r[2] >= 3)
            + f". Это значит: у наборов с высоким выходом домены разбросаны сильнее в пунктах (σ₁ {emp_rows[(0.03,0.06)]*100:.1f} п при 3–6 % против {emp_rows[(0.15,0.20)]*100:.1f} п при 15–20 %), "
            f"хотя относительный разброс c = сдвиг/среднее, наоборот, падает (ρ(c, выход) = {rho_c:+.2f}). Ни «постоянное φ», ни «постоянный c» точно не описывают данные.")
    else:
        say("   Зависимость φ от среднего выхода не обнаружена.")
    if phiR_list:
        say(f"3. Деньги: в {len(phiR_list)} стратах с ≥5 регистрациями φ_R медиана {median([ph for ph,_ in phiR_list]):.2f}, объединённое {pooled_R:.2f} "
            f"(«набор × день» с объединением зон, {len(phiR_b)} страт: медиана {median([ph for ph,_ in phiR_b]):.2f}). Это НЕ «ниже, чем по выходу»: при 0,4–2 регистрациях "
            f"на домен φ_R не может быть большим; относительный разброс доменов по деньгам c_R медиана {median(cR_list):.2f} (по (б) {median(cR_b):.2f}) против c по выходу "
            f"{median([s.c for s in reg_strata]):.2f} в тех же стратах — по деньгам домены разбросаны сильнее относительно среднего, как и ожидалось. "
            f"В 2 стратах из 7 (NEW102оформленосдатой 11.09 .casino и .team) сверхдисперсия регистраций значима (один домен собрал 5 из 5–7); "
            f"в остальных на 5–13 регистрациях она не отличима от пуассона. Оценивать набор по деньгам на 5–10 доменах нельзя: нужны десятки регистраций на группу.")
    sd12 = emp_rows.get((0.10, 0.15), math.sqrt(phi_pooled * 0.12 * 0.88 / 206))
    pr5 = probe.get(("≥ 10 %", 5))
    pr5lo = probe.get(("3–10 %", 5))
    say(f"4. Правило объёма (эмпирическое σ₁ при выходе 10–15 % = {sd12*100:.1f} п, при 6–10 % = {emp_rows[(0.06,0.10)]*100:.1f} п, при 15–20 % = {emp_rows[(0.15,0.20)]*100:.1f} п): "
        f"один домен даёт ±{2*sd12*100:.0f} п; 5 доменов на группу различают разницу ≥{2*sd12*math.sqrt(2/5)*100:.0f} п, 8 — ≥{2*sd12*math.sqrt(2/8)*100:.0f} п, "
        f"13 — ≥{2*sd12*math.sqrt(2/13)*100:.0f} п, 20 — ≥{2*sd12*math.sqrt(2/20)*100:.0f} п; для разницы 5 п нужно ≈{8*sd12**2/0.05**2:.0f} доменов на группу, "
        f"для 10 п — ≈{8*sd12**2/0.10**2:.0f}. У наборов с выходом 15–20 % — соответственно ≈{8*emp_rows[(0.15,0.20)]**2/0.05**2:.0f} и ≈{8*emp_rows[(0.15,0.20)]**2/0.10**2:.0f}.")
    if pr5:
        say(f"   Прямая проверка на {pr5[0]} стратах с выходом ≥ 10 % и k ≥ 10 ({pr5[1]} доменов): проба из 5 доменов расходится с остальными доменами ТОГО ЖЕ набора "
            f"на ≥5 п в {pr5[5]*100:.0f} % выборок, на ≥10 п — в {pr5[6]*100:.0f} %; медиана расхождения {pr5[2]*100:.1f} п, 95-й процентиль {pr5[4]*100:.1f} п. "
            + (f"Проба из 8: ≥5 п в {probe[('≥ 10 %', 8)][5]*100:.0f} %, 95-й процентиль {probe[('≥ 10 %', 8)][4]*100:.1f} п ({probe[('≥ 10 %', 8)][0]} страт). " if ("≥ 10 %", 8) in probe else "")
            + (f"У наборов с выходом 3–10 % ({pr5lo[0]} страт) проба из 5 ошибается на ≥5 п в {pr5lo[5]*100:.0f} % (95-й процентиль {pr5lo[4]*100:.1f} п) — "
               f"там пунктов мало, но и разницы между наборами меньше." if pr5lo else ""))
    say(f"   Провал одного домена — обычное дело: у наборов с выходом ≥ 10 % {n_half/len(doms_good)*100:.0f} % доменов выходят хуже половины среднего своего набора, "
        f"{n_quart/len(doms_good)*100:.0f} % — хуже четверти; четверть доменов любого набора — ниже {quantile(shares_rel,.25):.2f} его среднего, 5 % — ниже {quantile(shares_rel,.05):.2f}.")
    say()
    v1 = "подтверждается" if homog else ("опровергается" if heter else "не решена (p между 0,05 и 0,2; nabory ниже, но не доказано)")
    v2 = "опровергается" if p_rho_phi < 0.05 else "подтверждается"
    say(f"Итог: «φ одинакова у всех семейств» — {v1}; «φ не зависит от среднего выхода» — {v2} (ρ = {rho_phi:+.2f}, p = {fmt_p(p_rho_phi)}: "
        f"φ растёт с выходом, разброс в пунктах у сильных наборов больше); «для оценки набора нужно ≥12–15 доменов, проба на 5 различает только ≥10 п» — "
        f"подтверждается по порядку величины при выходе ≈10–15 % (≈{8*sd12**2/0.05**2:.0f} доменов на группу для 5 п; 5 доменов → ≥{2*sd12*math.sqrt(2/5)*100:.0f} п"
        + (f", прямая проверка на наборах с выходом ≥ 10 %: {pr5[5]*100:.0f} % проб из 5 расходятся с остальным набором на ≥5 п, 95-й процентиль {pr5[4]*100:.0f} п" if pr5 else "") + "); у наборов с выходом 15–20 % нужно ещё больше.")
    say("Что с этим делать: это знание, а не рычаг. (а) Оценивать новый набор не раньше, чем по 12–15 доменам в одной зоне и одном дне; по 5 доменам "
        "принимать решение только при разнице ≥10 пунктов выхода, а у наборов с выходом выше 15 % — при ещё большей. "
        f"(б) Один провальный домен у набора с нормальным средним не браковать: {n_half/len(doms_good)*100:.0f} % доменов любого набора выходят хуже половины его среднего. "
        "(в) Проверяемо на уже запущенных данных: взять наборы, которые сочли «провальными» или «удачными» по ≤5 доменам, и пересчитать по всем их доменам того же дня и зоны — "
        "если разница с семейством меньше 8–10 пунктов, решение было шумом; таблица (в) раздела 5 показывает, как часто это бывает. "
        "(г) По деньгам набор по 5–10 доменам не оценивается совсем: 0–2 регистрации на домен, один домен собирает половину; нужны десятки регистраций на группу.")
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(_lines) + "\n")
    print(f"\n[записано: {OUT_PATH}]")


if __name__ == "__main__":
    main()
