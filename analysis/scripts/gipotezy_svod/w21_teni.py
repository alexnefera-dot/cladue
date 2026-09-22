# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №21 (угол: ТЕНИ / конфаундинг).
Проверяем, не является ли то, что выжило у тестировщика, тенью:
  - периода (август против сентября, «КОНТЕНТ НЕ ЗАПИСАН»),
  - дня запуска и объёма дня,
  - партии постановки (аккаунт вебмастера / cf-аккаунт / час запуска),
  - имени домена (паттерн имени, длина метки),
  - отдельных пулов и отдельных доменов (выбросы).
Только stdlib.
"""
import csv, collections, math, random, os, itertools

CSV_PATH = "analysis/export/svod_domenov_21.09.csv"
OUT_PATH = "analysis/export/gipotezy_svod/w21_teni.txt"
N_PERM = 20000
ZONES = {"team", "lol", "casino"}
OUTLIERS = {"3615.team", "3286.team"}

_lines = []
def say(s=""):
    print(s); _lines.append(s)

def ti(x):
    x = (x or "").strip()
    return int(float(x)) if x else 0

def fmt_p(p):
    return f"{p:.4f}" if p >= 0.0001 else "<0.0001"

# ------------------------------------------------------------------ данные
def load(drop_unrecorded=True, closed_only=True, drop_day1=True, drop_outliers=True):
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8")))
    n0 = len(rows)
    if closed_only:
        rows = [r for r in rows if r["окно закрыто"] == "да"]
    if drop_day1:
        rows = [r for r in rows if r["дней"] != "1"]
    if drop_unrecorded:
        rows = [r for r in rows if r["набор контента"] != "КОНТЕНТ НЕ ЗАПИСАН"]
    rows = [r for r in rows if r["зона"] in ZONES]
    if drop_outliers:
        rows = [r for r in rows if r["домен"] not in OUTLIERS]
    return rows, n0

# ------------------------------------------------------------ страты и O/E
def blocks(recs, keyf, target, others):
    """Страты, в которых есть и целевая зона, и зоны сравнения."""
    P = collections.defaultdict(list)
    for r in recs:
        P[keyf(r)].append(r)
    out = []
    for k in sorted(P, key=lambda k: tuple(str(x) for x in k)):
        v = P[k]
        c = [r for r in v if r["зона"] == target]
        o = [r for r in v if r["зона"] in others]
        if c and o:
            out.append((k, c, o))
    return out

def oe(pp, num, den):
    O = E = 0.0
    for _, c, o in pp:
        g = c + o
        s = sum(ti(r[den]) for r in g)
        if not s:
            continue
        x = sum(ti(r[num]) for r in g)
        sc = sum(ti(r[den]) for r in c)
        O += sum(ti(r[num]) for r in c)
        E += x / s * sc
    return O, E

def permp(pp, num, den="сайтов в окне", nperm=N_PERM, seed=1):
    """Перестановка ярлыка зоны МЕЖДУ ДОМЕНАМИ внутри страты (сцепка по домену сохранена)."""
    O, E = oe(pp, num, den)
    rng = random.Random(seed)
    data = [([ti(r[num]) for r in c + o], len(c)) for _, c, o in pp]
    lo = hi = 0
    for _ in range(nperm):
        s = 0
        for xs, nc in data:
            s += sum(xs[i] for i in rng.sample(range(len(xs)), nc))
        if s <= O: lo += 1
        if s >= O: hi += 1
    return O, E, lo / nperm, hi / nperm

def line(nm, pp, num="вышли за 3 суток", den="сайтов в окне", side="lo"):
    if not pp:
        say(f"  {nm:52s} страт нет"); return None
    O, E, lo, hi = permp(pp, num, den)
    nz = sum(len(c) for _, c, _ in pp); no = sum(len(o) for _, _, o in pp)
    p = lo if side == "lo" else hi
    say(f"  {nm:52s} страт {len(pp):3d} цель {nz:3d} / сравн {no:3d} | O = {O:7.0f}, E = {E:8.1f}, O/E = {O/E if E else float('nan'):.3f}, "
        f"p({'O ≤' if side=='lo' else 'O ≥'}) = {fmt_p(p)}")
    return {"O": O, "E": E, "p": p, "n": len(pp), "nz": nz, "no": no}

# ключи страт
K_SET_DAY   = lambda r: (r["набор контента"], r["день запуска"])
K_HOUR      = lambda r: (r["набор контента"], r["день запуска"], r["час запуска"])
K_BLOCK     = lambda r: (r["набор контента"], r["день запуска"], r["блок часа"])
K_PAT       = lambda r: (r["набор контента"], r["день запуска"], r["паттерн имени"])
K_PAT_HOUR  = lambda r: (r["набор контента"], r["день запуска"], r["паттерн имени"], r["час запуска"])
K_LEN       = lambda r: (r["набор контента"], r["день запуска"], r["длина метки"])
K_DAY       = lambda r: (r["день запуска"],)


def main():
    say("Контрпроверка гипотезы №21. Угол: ТЕНИ (конфаундинг).")
    say(f"Файл: {CSV_PATH}. Перестановок: {N_PERM}, доменная перестановка внутри страты, random.seed(1).")
    say("Единица — домен. Числитель по умолчанию «вышли за 3 суток», знаменатель «сайтов в окне».")
    say()

    rows, n0 = load()
    say(f"Прочитано доменов: {n0}; после фильтров тестировщика (окно закрыто, дней≠1, контент записан, зоны team/lol/casino, без 3615.team/3286.team): {len(rows)}")
    say(f"  зоны: " + ", ".join(f"{z} {n}" for z, n in collections.Counter(r['зона'] for r in rows).most_common()))
    say()

    # ============================================================ БЛОК 1
    say("=" * 100)
    say("БЛОК 1. Что вообще можно наложить: какие конфаундеры варьируют внутри пула «набор+день»")
    say("=" * 100)
    acc = collections.defaultdict(collections.Counter)
    cfa = collections.defaultdict(collections.Counter)
    for r in rows:
        acc[r["аккаунт вебмастера"]][r["зона"]] += 1
        cfa[r["cf-аккаунт"]][r["зона"]] += 1
    say(f"  Аккаунт вебмастера: {len(acc)} аккаунтов на {len(rows)} доменов "
        f"(доменов на аккаунт: " + ", ".join(f"{k}→{v}" for k, v in sorted(collections.Counter(sum(c.values()) for c in acc.values()).items())) + ")")
    say(f"  cf-аккаунт: {len(cfa)} аккаунтов (доменов на cf: " +
        ", ".join(f"{k}→{v}" for k, v in sorted(collections.Counter(sum(c.values()) for c in cfa.values()).items())) + ")")
    for nm, kf in (("набор+день+аккаунт вебмастера", lambda r: (r["набор контента"], r["день запуска"], r["аккаунт вебмастера"])),
                   ("набор+день+cf-аккаунт", lambda r: (r["набор контента"], r["день запуска"], r["cf-аккаунт"]))):
        b = blocks(rows, kf, "lol", ("team",))
        say(f"  Страт «{nm}» с обеими зонами: {len(b)} — страту наложить НЕЛЬЗЯ (аккаунт почти всегда свой на домен).")
    P = collections.defaultdict(list)
    for r in rows:
        P[K_SET_DAY(r)].append(r)
    pairs = [(k, [r for r in v if r["зона"] == "team"], [r for r in v if r["зона"] == "lol"]) for k, v in sorted(P.items())]
    pairs = [(k, t, l) for k, t, l in pairs if t and l]
    nh = sum(1 for k, t, l in pairs
             if set(r["час запуска"] for r in t) != set(r["час запуска"] for r in l)
             or len(set(r["час запуска"] for r in t)) > 1)
    say(f"  Час запуска варьирует/не совпадает между зонами в {nh} из {len(pairs)} парных пулов team/lol — страту по часу наложить МОЖНО (с потерей объёма).")
    for z in ("team", "lol", "casino"):
        v = [r for r in rows if r["зона"] == z]
        c = collections.Counter(r["паттерн имени"] for r in v)
        say(f"  Паттерн имени, .{z} ({len(v)} доменов): " + ", ".join(f"{k} {n} ({n/len(v)*100:.0f} %)" for k, n in c.most_common()))
    say("  → .casino составлен почти целиком из «словесных» меток (alpha_other 82 %), .team/.lol — наполовину numeric: зона сцеплена с именем домена.")
    say()
    # есть ли собственный эффект паттерна внутри набор+день+зона (team/lol)
    Pz = collections.defaultdict(list)
    for r in rows:
        if r["зона"] in ("team", "lol"):
            Pz[(r["набор контента"], r["день запуска"], r["зона"])].append(r)
    pp = []
    for k, v in sorted(Pz.items()):
        a = [r for r in v if r["паттерн имени"] == "alpha_other"]
        b = [r for r in v if r["паттерн имени"] != "alpha_other"]
        if a and b:
            pp.append((k, a, b))
    say("  Контроль: собственный эффект «словесного» имени внутри страты набор+день+зона (только .team/.lol):")
    line("alpha_other против остальных имён, выход", pp, side="hi")
    say("  → сам по себе паттерн имени выход не двигает (O/E ≈ 1,0); значит он работает как метка партии, а не как причина.")
    say()

    # ============================================================ БЛОК 2
    say("=" * 100)
    say("БЛОК 2. Штраф .lol по выходу под всё более жёсткой стратой (сравнение только с .team)")
    say("=" * 100)
    res = {}
    for nm, kf in (("набор + день (страта тестировщика)", K_SET_DAY),
                   ("набор + день + блок часа", K_BLOCK),
                   ("набор + день + час запуска", K_HOUR),
                   ("набор + день + паттерн имени", K_PAT),
                   ("набор + день + длина метки", K_LEN),
                   ("набор + день + паттерн имени + час", K_PAT_HOUR)):
        res[nm] = line(nm, blocks(rows, kf, "lol", ("team",)))
    say("  → штраф .lol не растворяется ни в часе, ни в имени домена: O/E держится в коридоре 0,86–0,91.")
    say()

    # ============================================================ БЛОК 3
    say("=" * 100)
    say("БЛОК 3. Период, день, объём дня, отдельные пулы — где на самом деле сидит дефицит .lol")
    say("=" * 100)
    pp_all = blocks(rows, K_SET_DAY, "lol", ("team",))
    tot = []
    for k, l, t in pp_all:
        g = t + l
        s = sum(ti(r["сайтов в окне"]) for r in g); x = sum(ti(r["вышли за 3 суток"]) for r in g)
        sl = sum(ti(r["сайтов в окне"]) for r in l)
        O = sum(ti(r["вышли за 3 суток"]) for r in l); E = x / s * sl
        tot.append((O - E, k, O, E, len(t), len(l)))
    tot.sort()
    say("  Топ-8 пулов по вкладу в дефицит (O − E):")
    for a in tot[:8]:
        say(f"    {a[1][1]} {a[1][0][:34]:34s} O = {a[2]:4.0f}, E = {a[3]:6.1f}, O−E = {a[0]:+7.1f}, .team {a[4]:2d} дом / .lol {a[5]:2d} дом")
    say("  Топ-3 пула по избытку:")
    for a in tot[-3:]:
        say(f"    {a[1][1]} {a[1][0][:34]:34s} O = {a[2]:4.0f}, E = {a[3]:6.1f}, O−E = {a[0]:+7.1f}, .team {a[4]:2d} дом / .lol {a[5]:2d} дом")
    Oa = sum(a[2] for a in tot); Ea = sum(a[3] for a in tot)
    say(f"  Всего: O = {Oa:.0f}, E = {Ea:.1f}, O/E = {Oa/Ea:.3f}, суммарный дефицит {Oa-Ea:+.1f} вышедших сайтов.")
    for k in (1, 2, 3, 4):
        rest = tot[k:]
        o = sum(a[2] for a in rest); e = sum(a[3] for a in rest)
        say(f"    без {k} самых дефицитных пулов: пулов {len(rest)}, O/E = {o/e:.3f}")
    say()
    say("  Разрез по периоду (август — это первые записанные наборы, .lol там почти нет):")
    aug = [(k, l, t) for k, l, t in pp_all if k[1] < "2026-09-01"]
    sep = [(k, l, t) for k, l, t in pp_all if k[1] >= "2026-09-01"]
    line("август (24–26.08)", aug)
    line("сентябрь", sep)
    line("сентябрь без clean7_part1 11.09", [x for x in sep if x[0] != ("clean7_part1_50оформлено", "2026-09-11")])
    bal = [(k, l, t) for k, l, t in pp_all if min(len(t), len(l)) >= 3 and max(len(t), len(l)) / min(len(t), len(l)) <= 3]
    line("сбалансированные пулы (≥3 домена в зоне, перекос ≤3×)", bal)
    line("сбаланс. пулы без clean7 11.09", [x for x in bal if x[0] != ("clean7_part1_50оформлено", "2026-09-11")])
    say()
    say("  По дням запуска (O/E .lol против .team внутри пулов этого дня):")
    byday = collections.defaultdict(lambda: [0.0, 0.0, 0, 0])
    for a in tot:
        day = a[1][1]; byday[day][0] += a[2]; byday[day][1] += a[3]; byday[day][2] += a[4]; byday[day][3] += a[5]
    for day in sorted(byday):
        o, e, nt, nl = byday[day]
        say(f"    {day}: O = {o:5.0f}, E = {e:7.1f}, O/E = {o/e:.3f}; доменов .team {nt:3d} / .lol {nl:3d}")
    days = sorted(byday)
    worst = min(days, key=lambda dd: byday[dd][0] / byday[dd][1])
    say(f"  Leave-one-day-out (убираем по одному дню целиком):")
    for dd in days:
        o = Oa - byday[dd][0]; e = Ea - byday[dd][1]
        if e > 0:
            say(f"    без {dd}: O/E = {o/e:.3f}")
    say()
    # знаковый тест по пулам (без весов — один пул = один голос)
    signs = []
    for k, l, t in pp_all:
        st = sum(ti(r["сайтов в окне"]) for r in t); sl = sum(ti(r["сайтов в окне"]) for r in l)
        xt = sum(ti(r["вышли за 3 суток"]) for r in t); xl = sum(ti(r["вышли за 3 суток"]) for r in l)
        signs.append(xl / sl - xt / st)
    neg = sum(1 for s in signs if s < 0); pos = sum(1 for s in signs if s > 0); n = neg + pos
    pbin = min(1.0, 2 * sum(math.comb(n, j) for j in range(0, min(neg, pos) + 1)) / 2 ** n)
    say(f"  Знаковый тест (один пул = один голос, без весов): .lol хуже в {neg} пулах, лучше в {pos} из {n}; двусторонний p = {pbin:.4f}")
    say("  → дефицит .lol не сидит в одном пуле и не держится на объёме: он виден и как простое большинство пулов.")
    say()

    # ============================================================ БЛОК 4
    say("=" * 100)
    say("БЛОК 4. Тот же штраф .lol на других исходах и при других фильтрах (тень окна, тень фильтров)")
    say("=" * 100)
    for num, den, side in (("вышли за 1 сутки", "сайтов в окне", "lo"),
                           ("вышли за 3 суток", "сайтов в окне", "lo"),
                           ("вышли за 7 суток", "сайтов", "lo"),
                           ("кликов из поиска в окне", "сайтов в окне", "lo"),
                           ("регистраций в окне 3 суток", "сайтов в окне", "lo"),
                           ("регистраций в окне 3 суток", "вышли за 3 суток", "lo"),
                           ("ФД в окне 3 суток", "сайтов в окне", "lo")):
        line(f"{num} / {den}", pp_all, num, den, side)
    say("  → срез окна ни при чём: 1, 3 и 7 суток дают одно и то же (0,90–0,91). В регистрациях штрафа нет ни на сайт, ни на вышедший сайт.")
    say()
    say("  Чувствительность к фильтрам тестировщика:")
    r2, _ = load(drop_unrecorded=False)
    say(f"    с «КОНТЕНТ НЕ ЗАПИСАН» (страта только по дню запуска), доменов {len(r2)}:")
    line("страта «день запуска», .lol против .team", blocks(r2, K_DAY, "lol", ("team",)))
    line("страта «день+час», .lol против .team", blocks(r2, lambda r: (r["день запуска"], r["час запуска"]), "lol", ("team",)))
    r3, _ = load(closed_only=False, drop_day1=False)
    say(f"    без отсева «окно не закрыто» и «дней = 1», доменов {len(r3)}:")
    line("набор+день, .lol против .team", blocks(r3, K_SET_DAY, "lol", ("team",)))
    say("      (числа те же: все 229 добавленных доменов — запуски 17–21.09, у 152 «сайтов в окне» = 0, "
        "их пулы «набор+день» не пересекаются с прежними и парных страт не дают)")
    r4, _ = load(drop_outliers=False)
    line("с выбросами 3615.team/3286.team (набор+день)", blocks(r4, K_SET_DAY, "lol", ("team",)))
    say()

    # ============================================================ БЛОК 5
    say("=" * 100)
    say("БЛОК 5. Единственный «свой» пул — clean7_part1_50оформлено 11.09: тень часа/партии/имени?")
    say("=" * 100)
    cl = [r for r in rows if r["набор контента"] == "clean7_part1_50оформлено" and r["день запуска"] == "2026-09-11"]
    t = [r for r in cl if r["зона"] == "team"]; l = [r for r in cl if r["зона"] == "lol"]; c = [r for r in cl if r["зона"] == "casino"]
    say(f"  Доменов в пуле: .team {len(t)}, .lol {len(l)}, .casino {len(c)}; у всех «сайтов в окне» = 206, «дней» = 2, последний день 12.09.")
    say(f"  Аккаунты вебмастера идут подряд ({min(ti(r['аккаунт вебмастера']) for r in cl)}–{max(ti(r['аккаунт вебмастера']) for r in cl)}) — одна партия постановки.")
    say("  Разбивка по часу запуска внутри пула (выход = вышли за 3 суток / сайтов в окне):")
    hrs = sorted(set(r["час запуска"] for r in cl), key=lambda h: int(h))
    nsame = nlolworse = 0
    for h in hrs:
        th = [r for r in t if r["час запуска"] == h]; lh = [r for r in l if r["час запуска"] == h]
        if not th or not lh:
            continue
        xt = sum(ti(r["вышли за 3 суток"]) for r in th); st = sum(ti(r["сайтов в окне"]) for r in th)
        xl = sum(ti(r["вышли за 3 суток"]) for r in lh); sl = sum(ti(r["сайтов в окне"]) for r in lh)
        nsame += 1
        if xl / sl < xt / st: nlolworse += 1
        say(f"    час {h:>2s}: .team {len(th)} дом {xt:3d}/{st:4d} = {xt/st:.3f} | .lol {len(lh)} дом {xl:3d}/{sl:4d} = {xl/sl:.3f} | lol/team = {(xl/sl)/(xt/st):.2f}")
    say(f"  Часов, где обе зоны есть: {nsame}; .lol хуже в {nlolworse} из них.")
    tn = [r for r in t if r["паттерн имени"] == "numeric"]; ln = [r for r in l if r["паттерн имени"] == "numeric"]
    xt = sum(ti(r["вышли за 3 суток"]) for r in tn); st = sum(ti(r["сайтов в окне"]) for r in tn)
    xl = sum(ti(r["вышли за 3 суток"]) for r in ln); sl = sum(ti(r["сайтов в окне"]) for r in ln)
    say(f"  Только numeric-имена: .team {len(tn)} дом {xt}/{st} = {xt/st:.3f}; .lol {len(ln)} дом {xl}/{sl} = {xl/sl:.3f}; lol/team = {(xl/sl)/(xt/st):.2f}")
    # регистрации: точный гипергеометрический тест по доменам с регистрацией
    regd_t = sum(1 for r in t if ti(r["регистраций в окне 3 суток"]) > 0)
    regd_l = sum(1 for r in l if ti(r["регистраций в окне 3 суток"]) > 0)
    K = regd_t + regd_l; N = len(t) + len(l)
    p_hyp = math.comb(len(t), K) / math.comb(N, K) if K <= len(t) else float("nan")
    say(f"  Регистрации: доменов с регистрацией .team {regd_t} из {len(t)}, .lol {regd_l} из {len(l)}; "
        f"точный гипергеометрический P(все {K} конвертивших домена в .team) = {p_hyp:.4f}")
    say(f"  Поправка на множественность: пул выбран как лучший из 20 → p·20 ≈ {p_hyp*20:.2f} по регистрациям; по выходу 0,0031·20 ≈ 0,06.")
    say()

    # ============================================================ БЛОК 6
    say("=" * 100)
    say("БЛОК 6. .casino: сколько от «×1,23» остаётся после жёсткой страты и без archive-пулов")
    say("=" * 100)
    noarch = [r for r in rows if r["семейство"] != "archive"]
    say("  Выход:")
    c_base = line("набор+день, .casino против .team+.lol (тестировщик)", blocks(rows, K_SET_DAY, "casino", ("team", "lol")), side="hi")
    line("набор+день, только .team в сравнении", blocks(rows, K_SET_DAY, "casino", ("team",)), side="hi")
    line("набор+день, без archive-пулов", blocks(noarch, K_SET_DAY, "casino", ("team", "lol")), side="hi")
    line("набор+день, без archive, только .team", blocks(noarch, K_SET_DAY, "casino", ("team",)), side="hi")
    line("набор+день+паттерн имени", blocks(rows, K_PAT, "casino", ("team", "lol")), side="hi")
    line("набор+день+паттерн, без archive", blocks(noarch, K_PAT, "casino", ("team", "lol")), side="hi")
    line("набор+день+паттерн, без archive, только .team", blocks(noarch, K_PAT, "casino", ("team",)), side="hi")
    line("набор+день+блок часа", blocks(rows, K_BLOCK, "casino", ("team", "lol")), side="hi")
    line("набор+день+блок часа, без archive", blocks(noarch, K_BLOCK, "casino", ("team", "lol")), side="hi")
    line("набор+день+блок часа, без archive, только .team", blocks(noarch, K_BLOCK, "casino", ("team",)), side="hi")
    line("набор+день+час", blocks(rows, K_HOUR, "casino", ("team", "lol")), side="hi")
    line("набор+день+час, без archive", blocks(noarch, K_HOUR, "casino", ("team", "lol")), side="hi")
    say("  Регистрации:")
    line("набор+день (тестировщик)", blocks(rows, K_SET_DAY, "casino", ("team", "lol")), "регистраций в окне 3 суток", "сайтов в окне", "hi")
    line("набор+день, без archive", blocks(noarch, K_SET_DAY, "casino", ("team", "lol")), "регистраций в окне 3 суток", "сайтов в окне", "hi")
    line("набор+день+блок часа, без archive", blocks(noarch, K_BLOCK, "casino", ("team", "lol")), "регистраций в окне 3 суток", "сайтов в окне", "hi")
    say()
    say("  Вклад пулов в избыток .casino (без archive):")
    ppc = blocks(noarch, K_SET_DAY, "casino", ("team", "lol"))
    tt = []
    for k, c2, o2 in ppc:
        g = c2 + o2
        s = sum(ti(r["сайтов в окне"]) for r in g); x = sum(ti(r["вышли за 3 суток"]) for r in g)
        sc = sum(ti(r["сайтов в окне"]) for r in c2)
        O = sum(ti(r["вышли за 3 суток"]) for r in c2); E = x / s * sc
        tt.append((O - E, k, O, E, len(c2), len(o2)))
    tt.sort(reverse=True)
    for a in tt:
        say(f"    {a[1][1]} {a[1][0][:34]:34s} O = {a[2]:5.0f}, E = {a[3]:7.1f}, O−E = {a[0]:+7.1f}, .casino {a[4]:2d} дом / прочие {a[5]:2d} дом, O/E = {a[2]/a[3]:.2f}")
    Oc = sum(a[2] for a in tt); Ec = sum(a[3] for a in tt)
    say(f"    итого без archive: O/E = {Oc/Ec:.3f}")
    for k in (1, 2, 3):
        rest = tt[k:]
        o = sum(a[2] for a in rest); e = sum(a[3] for a in rest)
        say(f"      без {k} самых «выигрышных» пулов: пулов {len(rest)}, O/E = {o/e:.3f}")
    say("  Внутрипуловой сдвиг часа: в NEW50_12pages_withdate_01.09 .casino поставлен в 17–18 ч, .team/.lol в 22–23 ч;")
    say("  в script_yandex_12page 11.09 .casino в 0–20 ч, все .team/.lol ровно в 19 ч — зона сцеплена с партией постановки.")
    say()

    # ============================================================ ВЫВОД
    say("=" * 100)
    say("ВЫВОД КОНТРПРОВЕРКИ")
    say("=" * 100)
    say("1. Неоднородность штрафа .lol по наборам — как и у тестировщика, ничего нет; добавлять нечего.")
    say("2. Общий штраф .lol по выходу — тенью НЕ объясняется. Он переживает все жёсткие страты:")
    say("   набор+день 0,906 (p = 0,0004), +блок часа 0,906, +час 0,862, +паттерн имени 0,904, +паттерн+час — тот же порядок;")
    say("   переживает 1/3/7-суточное окно (0,900 / 0,906 / 0,913), удаление августа (сентябрь 0,925, p = 0,0034),")
    say("   удаление clean7 11.09 (0,939, p = 0,017), ограничение сбалансированными пулами (0,920),")
    say("   удаление любого одного дня и любых 4 самых дефицитных пулов (0,94), и виден как простое большинство пулов (31 из 46, p = 0,026).")
    say("   Но величина у тестировщика завышена краем: 5 августовских пулов (8 доменов .lol) дают четверть всего дефицита.")
    say("   Честный коридор — O/E 0,92–0,94 по сентябрю, а не 0,91; в регистрациях по-прежнему пусто (0,89 на сайт, 0,94 на вышедший сайт).")
    say("3. clean7 11.09 — не тень часа и не тень имени: .lol хуже .team внутри 6 из 7 часов, и на одних numeric-именах lol/team = 0,47.")
    say("   Но это один пул одного дня, выбранный как лучший из 20: Бонферрони ≈ 0,06 по выходу и ≈ 0,9 по регистрациям.")
    say("4. .casino «лучше по выходу ×1,23» — ОПРОВЕРГНУТО как самостоятельный эффект зоны: это тень archive-пулов,")
    say("   сравнения с просевшим .lol и партии постановки. Без archive и против одного .team: 1,08 (p = 0,068);")
    say("   при страте по блоку часа без archive против .team: 1,07 (p = 0,14); при страте по имени без archive: 1,02 (p = 0,33).")
    say("   По регистрациям без archive O/E 0,93–1,00 — никакого выигрыша.")
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    open(OUT_PATH, "w", encoding="utf-8").write("\n".join(_lines) + "\n")
    print(f"\n[сохранено: {OUT_PATH}]")


if __name__ == "__main__":
    main()
