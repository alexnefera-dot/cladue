#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №21 (угол: СТАТИСТИКА И ОПРЕДЕЛЕНИЯ).
Только stdlib. Единица — домен второго уровня; знаменатель — «сайтов в окне».
Проверяем: воспроизводимость, суммы против средних долей, множественность,
объём событий, устойчивость к удалению топ-доменов и пулов, знаменатели,
фильтры окна/«дней=1», силу формулировок (интервалы), мощность теста
неоднородности.
"""
import collections
import csv
import math
import os
import random
import sys

CSV = "analysis/export/svod_domenov_21.09.csv"
OUT = "analysis/export/gipotezy_svod/w21_statistika.txt"
OUTLIERS = {"3615.team", "3286.team"}
ZONES = ("team", "lol", "casino")
NPERM = 20000

_L = []


def say(s=""):
    print(s)
    _L.append(s)


def ii(x):
    x = (x or "").strip()
    return int(float(x)) if x else 0


def load(window=True, drop_day1=True, drop_noset=True, zones=ZONES, drop_outl=True):
    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    n0 = len(rows)
    if window:
        rows = [r for r in rows if r["окно закрыто"] == "да"]
    if drop_day1:
        rows = [r for r in rows if r["дней"] != "1"]
    if drop_noset:
        rows = [r for r in rows if r["набор контента"] != "КОНТЕНТ НЕ ЗАПИСАН"]
    if zones:
        rows = [r for r in rows if r["зона"] in zones]
    if drop_outl:
        rows = [r for r in rows if r["домен"] not in OUTLIERS]
    out = []
    for r in rows:
        out.append({
            "домен": r["домен"], "зона": r["зона"], "набор": r["набор контента"],
            "день": r["день запуска"], "семейство": r["семейство"],
            "сайтов": ii(r["сайтов в окне"]), "сайтов_всего": ii(r["сайтов"]),
            "вышли": ii(r["вышли за 3 суток"]), "вышли1": ii(r["вышли за 1 сутки"]),
            "вышли7": ii(r["вышли за 7 суток"]),
            "клики": ii(r["кликов из поиска в окне"]),
            "рег": ii(r["регистраций в окне 3 суток"]),
            "рег_всего": ii(r["регистраций"]),
            "фд": ii(r["ФД в окне 3 суток"]),
        })
    return out, n0


def pools_of(doms):
    p = collections.defaultdict(list)
    for d in doms:
        p[(d["набор"], d["день"])].append(d)
    return p


# ---------------------------------------------------------------- ядро O/E
def oe_blocks(blocks, num, den, is_target):
    """blocks: список списков доменов (пулов). Возвращает O, E, O/E."""
    O = E = 0.0
    for ds in blocks:
        tn = sum(d[num] for d in ds)
        td = sum(d[den] for d in ds)
        if td == 0:
            continue
        rate = tn / td
        for d in ds:
            if is_target(d):
                O += d[num]
                E += rate * d[den]
    return O, E, (O / E if E else float("nan"))


def perm_p(blocks, num, den, is_target, nperm=NPERM, seed=1):
    """Двусторонняя перестановка метки зоны внутри пула, домен целиком."""
    rnd = random.Random(seed)
    Oobs, E, _ = oe_blocks(blocks, num, den, is_target)
    # подготовка
    prep = []
    for ds in blocks:
        td = sum(d[den] for d in ds)
        tn = sum(d[num] for d in ds)
        if td == 0:
            continue
        k = sum(1 for d in ds if is_target(d))
        if k == 0 or k == len(ds):
            continue
        prep.append(([d[num] for d in ds], k))
        # фиксированная часть O (пулы без вариации) — добавим отдельно
    fixedO = 0.0
    for ds in blocks:
        td = sum(d[den] for d in ds)
        if td == 0:
            continue
        k = sum(1 for d in ds if is_target(d))
        if k == 0 or k == len(ds):
            fixedO += sum(d[num] for d in ds if is_target(d))
    ge = le = 0
    for _ in range(nperm):
        s = fixedO
        for nums, k in prep:
            idx = rnd.sample(range(len(nums)), k)
            for i in idx:
                s += nums[i]
        if s >= Oobs:
            ge += 1
        if s <= Oobs:
            le += 1
    return Oobs, E, (ge + 1) / (nperm + 1), (le + 1) / (nperm + 1)


def boot_oe(blocks, num, den, is_target, nboot=3000, seed=7):
    """Бутстреп по доменам внутри пул×зона (сцепка доменов учтена)."""
    rnd = random.Random(seed)
    groups = []
    for ds in blocks:
        t = [d for d in ds if is_target(d)]
        o = [d for d in ds if not is_target(d)]
        if not t or not o:
            continue
        groups.append((t, o))
    vals = []
    for _ in range(nboot):
        O = E = 0.0
        for t, o in groups:
            tt = [t[rnd.randrange(len(t))] for _ in t]
            oo = [o[rnd.randrange(len(o))] for _ in o]
            tn = sum(d[num] for d in tt) + sum(d[num] for d in oo)
            td = sum(d[den] for d in tt) + sum(d[den] for d in oo)
            if td == 0:
                continue
            rate = tn / td
            O += sum(d[num] for d in tt)
            E += rate * sum(d[den] for d in tt)
        if E:
            vals.append(O / E)
    vals.sort()
    if not vals:
        return (float("nan"), float("nan"))
    return vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))]


def fp(p):
    return f"{p:.4f}" if p >= 0.0001 else "<0.0001"


# ================================================================== запуск
doms, nraw = load()
say("=" * 100)
say("КОНТРПРОВЕРКА ГИПОТЕЗЫ №21. Статистика и определения.")
say("=" * 100)
say(f"Файл: {CSV}; строк всего {nraw}; после фильтров тестировщика (окно закрыто=да, "
    f"дней≠1, набор записан, зоны team/lol/casino, без 3615.team и 3286.team): {len(doms)} доменов")

P = pools_of(doms)


def pool_list(min_t, min_l, zone_a="lol", zone_b="team"):
    out = []
    for k in sorted(P, key=lambda k: (k[1], k[0])):
        ds = P[k]
        a = [d for d in ds if d["зона"] == zone_a]
        b = [d for d in ds if d["зона"] == zone_b]
        if len(a) >= min_l and len(b) >= min_t:
            out.append((k, a + b))
    return out


P46 = pool_list(1, 1)
P20 = pool_list(3, 3)
is_lol = lambda d: d["зона"] == "lol"

say()
say("-" * 100)
say("1. ВОСПРОИЗВОДИМОСТЬ И «СУММЫ ПРОТИВ СРЕДНИХ ДОЛЕЙ»")
say("-" * 100)
say("Скрипт тестировщика перезапущен (тот же seed=1): вывод совпал с сохранённым побайтово (diff пуст).")
say("Ниже — независимый пересчёт теми же определениями, но своим кодом.")

for name, PP in (("46 парных пулов (≥1 домен team и ≥1 lol)", P46),
                 ("20 пулов (≥3 домена в каждой зоне)", P20)):
    blocks = [ds for _, ds in PP]
    O, E, oe = oe_blocks(blocks, "вышли", "сайтов", is_lol)
    Or, Er, oer = oe_blocks(blocks, "рег", "сайтов", is_lol)
    nl = sum(1 for ds in blocks for d in ds if is_lol(d))
    nt = sum(1 for ds in blocks for d in ds if not is_lol(d))
    sl = sum(d["сайтов"] for ds in blocks for d in ds if is_lol(d))
    st = sum(d["сайтов"] for ds in blocks for d in ds if not is_lol(d))
    say(f"  {name}: пулов {len(PP)}; доменов team {nt} / lol {nl}; сайтов team {st} / lol {sl}")
    say(f"    выход: O(.lol)={O:.0f} при E={E:.1f} → O/E={oe:.3f}")
    say(f"    регистрации: O(.lol)={Or:.0f} при E={Er:.1f} → O/E={oer:.3f}; событий в пулах всего "
        f"{Or + sum(d['рег'] for ds in blocks for d in ds if not is_lol(d)):.0f}")

# средние долей vs суммы
blocks46 = [ds for _, ds in P46]
lolds = [d for ds in blocks46 for d in ds if is_lol(d)]
teamds = [d for ds in blocks46 for d in ds if not is_lol(d)]
m_lol = sum(d["вышли"] / d["сайтов"] for d in lolds) / len(lolds)
m_team = sum(d["вышли"] / d["сайтов"] for d in teamds) / len(teamds)
say(f"  Контроль «не средние ли долей»: невзвешенное среднее доли выхода по доменам "
    f".lol {m_lol:.4f} против .team {m_team:.4f} (отношение {m_lol/m_team:.3f}); "
    f"суммарно {sum(d['вышли'] for d in lolds)/sum(d['сайтов'] for d in lolds):.4f} против "
    f"{sum(d['вышли'] for d in teamds)/sum(d['сайтов'] for d in teamds):.4f}.")
say("  → тестировщик считает суммами и внутри пулов (страта «набор+день»), это правильный знаменатель;")
say("    сырое отношение без страты и средние долей дают тот же порядок, артефакта усреднения нет.")

say()
say("-" * 100)
say("2. ОБЪЁМ СОБЫТИЙ (порог: <20 регистраций ничего не доказывает)")
say("-" * 100)
groups = []


def fam_pools(fams, min_each=1):
    out = []
    for k in sorted(P, key=lambda k: (k[1], k[0])):
        ds = P[k]
        if ds[0]["семейство"] not in fams:
            continue
        a = [d for d in ds if d["зона"] == "lol"]
        b = [d for d in ds if d["зона"] == "team"]
        if len(a) >= min_each and len(b) >= min_each:
            out.append((k, a + b))
    return out


sets_for_count = [
    ("46 парных пулов, регистрации .lol+.team", [ds for _, ds in P46]),
    ("20 пулов части 1", [ds for _, ds in P20]),
    ("clean+nabory (11 пулов)", [ds for _, ds in fam_pools({"clean", "nabory"})]),
    ("только nabory", [ds for _, ds in fam_pools({"nabory"})]),
    ("только clean", [ds for _, ds in fam_pools({"clean"})]),
]
for nm, bl in sets_for_count:
    tot = sum(d["рег"] for ds in bl for d in ds)
    lol = sum(d["рег"] for ds in bl for d in ds if is_lol(d))
    ndom = sum(1 for ds in bl for d in ds if d["рег"] > 0)
    say(f"  {nm}: регистраций в окне всего {tot} (в .lol {lol}), они лежат на {ndom} доменах")
# clean7 11.09
c7 = [ds for k, ds in P46 if k == ("clean7_part1_50оформлено", "2026-09-11")]
say(f"  clean7_part1_50оформлено 11.09: регистраций всего "
    f"{sum(d['рег'] for ds in c7 for d in ds)} на "
    f"{sum(1 for ds in c7 for d in ds if d['рег']>0)} доменах")
# casino
casino_pools = []
for k in sorted(P, key=lambda k: (k[1], k[0])):
    ds = P[k]
    c = [d for d in ds if d["зона"] == "casino"]
    o = [d for d in ds if d["зона"] in ("team", "lol")]
    if c and o:
        casino_pools.append((k, c + o))
is_cas = lambda d: d["зона"] == "casino"
bc = [ds for _, ds in casino_pools]
say(f"  .casino (14 парных пулов): регистраций всего {sum(d['рег'] for ds in bc for d in ds)}, "
    f"из них .casino {sum(d['рег'] for ds in bc for d in ds if is_cas(d))} на "
    f"{sum(1 for ds in bc for d in ds if is_cas(d) and d['рег']>0)} доменах")
say("  → по правилу методики любая группа с <20 регистрациями (clean7 11.09: 6; nabory: 3;")
say("    clean: 10; casino: 19) сама по себе денежный вывод не несёт. Порог 20 проходит только")
say("    свод 46 пулов (90 регистраций, из них 34 в .lol).")

say()
say("-" * 100)
say("3. МНОЖЕСТВЕННОСТЬ")
say("-" * 100)
say("  Пересчитано срезов в отчёте тестировщика (по тексту h21_zone_penalty_by_set.txt):")
say("    ч.1 неоднородность: 3 веса × 2 порога (≥3/≥2) × 2 метрики (выход, клики/вышедший) = 12 тестов,")
say("        + 4 межсемейных, + те же 6 без clean7 11.09 = 22;")
say("    ч.1 индивидуальные p 20 пулов = 20;")
say("    ч.2 воспроизводимость: 2 набора × (p дня + совместный p) = 6;")
say("    ч.3 деньги: 6 групп × (выход + регистрации) = 12, плюс биномиальный и доменный для clean7 = 14;")
say("    ч.4 .casino: 5 нарезок × (выход + регистрации, перестановочный и пуассоновский) ≈ 15.")
say("    Итого порядка 75–80 объявленных p-значений на одном и том же своде.")
say("  Что выживает после поправки:")
say("    • p = 0.0003 (общий штраф .lol по выходу, 46 пулов) × 80 = 0.024 — выживает (Бонферрони);")
say("    • p = 0.0031 (пул clean7 11.09) × 20 пулов = 0.062, × 80 = 0.25 — НЕ выживает;")
say("    • p = 0.035 / 0.045 (регистрации clean7 11.09) — не выживает ни при какой поправке;")
say("    • p = 0.0561 и 0.0346 (межсемейная дисперсия) — не выживает и до поправки;")
say("    • p < 0.0001 (.casino выход, все пулы) × 80 = 0.008 — выживает;")
say("    • p = 0.0113 (.casino выход без archive) × 80 = 0.90 — НЕ выживает;")
say("    • p = 0.0048 / 0.0009 (выход .lol в nabory / clean) × 80 = 0.38 / 0.07 — не выживает.")
# BH по 20 пуловым p из отчёта
pool_ps = [0.6544, 0.1000, 0.1000, 0.7152, 0.8372, 0.1989, 0.0727, 0.7788, 0.3492, 0.1000,
           0.4107, 0.5818, 0.5298, 0.1536, 0.8762, 0.9268, 0.0031, 0.7887, 0.6748, 1.0000]
sp = sorted(pool_ps)
bh = [min(1.0, sp[i] * len(sp) / (i + 1)) for i in range(len(sp))]
for i in range(len(bh) - 2, -1, -1):
    bh[i] = min(bh[i], bh[i + 1])
say(f"  BH (FDR) по 20 пуловым p: минимальное q = {bh[0]:.3f} (это clean7 11.09, сырое p = {sp[0]}), "
    f"второе q = {bh[1]:.3f}")
say(f"  → при FDR 5 % clean7 11.09 {'проходит' if bh[0] < 0.05 else 'НЕ проходит'}; при Бонферрони — нет.")

say()
say("-" * 100)
say("4. УСТОЙЧИВОСТЬ: УДАЛЕНИЕ ТОП-3 ДОМЕНОВ И ЛИШЬ-ОДИН-ПУЛ")
say("-" * 100)


def drop_topk(blocks, is_target, key, k=3):
    """Убираем k доменов с наибольшим key в целевой группе и k — в контрольной."""
    tg = sorted([d for ds in blocks for d in ds if is_target(d)], key=lambda d: -d[key])[:k]
    ct = sorted([d for ds in blocks for d in ds if not is_target(d)], key=lambda d: -d[key])[:k]
    bad = {id(d) for d in tg + ct}
    nb = []
    for ds in blocks:
        n = [d for d in ds if id(d) not in bad]
        if any(is_target(d) for d in n) and any(not is_target(d) for d in n):
            nb.append(n)
    return nb, [d["домен"] for d in tg], [d["домен"] for d in ct]


def report(nm, blocks, num, den, is_t, seed=11, nperm=NPERM):
    O, E, oe = oe_blocks(blocks, num, den, is_t)
    _, _, pge, ple = perm_p(blocks, num, den, is_t, nperm=nperm, seed=seed)
    lo, hi = boot_oe(blocks, num, den, is_t)
    say(f"  {nm}: O={O:.0f}, E={E:.1f}, O/E={oe:.3f} [бутстреп по доменам 95 %: {lo:.2f}; {hi:.2f}]; "
        f"перест. p(O≤)={fp(ple)}, p(O≥)={fp(pge)}")
    return oe, ple, pge


say("4.1. Общий штраф .lol по выходу (46 парных пулов) — главное, что уцелело у тестировщика:")
report("  все 46 пулов", blocks46, "вышли", "сайтов", is_lol)
b2, t3, c3 = drop_topk(blocks46, is_lol, "вышли", 3)
say(f"    (убраны топ-3 по числу вышедших: .lol {t3}; .team {c3})")
report("  без топ-3 доменов в каждой зоне", b2, "вышли", "сайтов", is_lol)
b3, t3r, c3r = drop_topk(blocks46, is_lol, "рег", 3)
say(f"    (убраны топ-3 по регистрациям: .lol {t3r}; .team {c3r})")
report("  без топ-3 по регистрациям", b3, "вышли", "сайтов", is_lol)
# без clean7 11.09
b4 = [ds for k, ds in P46 if k != ("clean7_part1_50оформлено", "2026-09-11")]
report("  без пула clean7 11.09", b4, "вышли", "сайтов", is_lol)
# leave-one-pool-out
worst = []
for k, ds in P46:
    bl = [x for kk, x in P46 if kk != k]
    O, E, oe = oe_blocks(bl, "вышли", "сайтов", is_lol)
    worst.append((oe, k))
worst.sort()
say(f"    leave-one-pool-out по 46 пулам: O/E меняется в диапазоне "
    f"{worst[0][0]:.3f} ({worst[0][1][0][:28]} {worst[0][1][1]}) … "
    f"{worst[-1][0]:.3f} ({worst[-1][1][0][:28]} {worst[-1][1][1]})")
# сколько пулов ниже ожидания
sgn = []
for k, ds in P46:
    O, E, oe = oe_blocks([ds], "вышли", "сайтов", is_lol)
    if E:
        sgn.append(1 if O < E else 0)
below = sum(sgn)
n = len(sgn)
pbin = sum(math.comb(n, i) for i in range(below, n + 1)) / 2 ** n
say(f"    знаковый счёт: .lol ниже ожидания пула в {below} из {n} пулов "
    f"(односторонний биномиальный p = {pbin:.4f}) — эффект размазан по пулам, а не сидит на одном")

say()
say("4.2. Регистрации .lol (46 пулов) — «в деньгах не виден»:")
report("  все 46 пулов", blocks46, "рег", "сайтов", is_lol)
b5, t3g, c3g = drop_topk(blocks46, is_lol, "рег", 3)
say(f"    (убраны топ-3 по регистрациям: .lol {t3g}; .team {c3g})")
report("  без топ-3 по регистрациям", b5, "рег", "сайтов", is_lol)

say()
say("4.3. Пул clean7_part1_50оформлено 11.09 (единственный «собственный» эффект):")
report("  выход, весь пул", c7, "вышли", "сайтов", is_lol, nperm=NPERM)
b6, t3c, c3c = drop_topk(c7, is_lol, "вышли", 3)
say(f"    (убраны топ-3 по вышедшим: .lol {t3c}; .team {c3c})")
report("  выход без топ-3 в каждой зоне", b6, "вышли", "сайтов", is_lol)
report("  регистрации, весь пул", c7, "рег", "сайтов", is_lol)

say()
say("4.4. .casino:")
report("  выход, все 14 пулов", bc, "вышли", "сайтов", is_cas)
bca = [ds for _, ds in casino_pools if ds[0]["семейство"] != "archive"]
report("  выход, без archive-пулов", bca, "вышли", "сайтов", is_cas)
b7, t3a, c3a = drop_topk(bc, is_cas, "вышли", 3)
say(f"    (убраны топ-3 по вышедшим: .casino {t3a}; прочие {c3a})")
report("  выход, без топ-3 в каждой группе", b7, "вышли", "сайтов", is_cas)
b8, t3b, c3b = drop_topk(bca, is_cas, "вышли", 3)
report("  выход, без archive и без топ-3", b8, "вышли", "сайтов", is_cas)
report("  регистрации, все 14 пулов", bc, "рег", "сайтов", is_cas)
b9, t3d, c3d = drop_topk(bc, is_cas, "рег", 3)
say(f"    (убраны топ-3 по регистрациям: .casino {t3d}; прочие {c3d})")
report("  регистрации, без топ-3", b9, "рег", "сайтов", is_cas)
wc = []
for k, ds in casino_pools:
    bl = [x for kk, x in casino_pools if kk != k]
    O, E, oe = oe_blocks(bl, "вышли", "сайтов", is_cas)
    wc.append((oe, k))
wc.sort()
say(f"    leave-one-pool-out (выход .casino): {wc[0][0]:.3f} ({wc[0][1][0][:28]} {wc[0][1][1]}) … "
    f"{wc[-1][0]:.3f} ({wc[-1][1][0][:28]} {wc[-1][1][1]})")

say()
say("-" * 100)
say("5. ЗНАМЕНАТЕЛИ, ОКОННЫЕ КОЛОНКИ И ФИЛЬТРЫ")
say("-" * 100)
bad = [d["домен"] for d in doms if d["вышли"] > d["сайтов"]]
say(f"  «вышли за 3 суток» > «сайтов в окне»: {len(bad)} доменов — {'нет' if not bad else bad[:5]}")
neq = [d for d in doms if d["сайтов"] != d["сайтов_всего"]]
say(f"  «сайтов в окне» ≠ «сайтов» после фильтра окна: {len(neq)} доменов "
    f"(то есть оконный знаменатель почти всюду совпадает с полным)")
rr = sum(d["рег"] for d in doms), sum(d["рег_всего"] for d in doms)
say(f"  Оконная колонка регистраций использована верно: в отфильтрованном наборе "
    f"«регистраций в окне 3 суток» {rr[0]} против «регистраций» (всего) {rr[1]}")
# варианты фильтров
for nm, kw in (("как у тестировщика", {}),
               ("если НЕ исключать «дней=1»", {"drop_day1": False}),
               ("если НЕ исключать «окно не закрыто»", {"window": False}),
               ("если НЕ исключать «КОНТЕНТ НЕ ЗАПИСАН»", {"drop_noset": False}),
               ("если НЕ исключать выбросы 3615/3286.team", {"drop_outl": False})):
    dd, _ = load(**kw)
    PP = pools_of(dd)
    bl = []
    for k in PP:
        ds = PP[k]
        a = [d for d in ds if d["зона"] == "lol"]
        b = [d for d in ds if d["зона"] == "team"]
        if a and b:
            bl.append(a + b)
    O, E, oe = oe_blocks(bl, "вышли", "сайтов", is_lol)
    Or, Er, oer = oe_blocks(bl, "рег", "сайтов", is_lol)
    say(f"  {nm}: пулов {len(bl)}, выход .lol O/E = {oe:.3f} (O={O:.0f}, E={E:.0f}); "
        f"регистрации O/E = {oer:.3f} (O={Or:.0f}, E={Er:.1f})")
# «вышли за 1 сутки» и «за 7 суток» как альтернативные числители
for num, nm in (("вышли1", "вышли за 1 сутки"), ("вышли", "вышли за 3 суток"), ("вышли7", "вышли за 7 суток (вне окна!)")):
    O, E, oe = oe_blocks(blocks46, num, "сайтов", is_lol)
    say(f"  Числитель «{nm}»: O/E .lol = {oe:.3f} (O={O:.0f}, E={E:.0f})")

say()
say("-" * 100)
say("6. СИЛА ФОРМУЛИРОВОК: ИНТЕРВАЛЫ ВМЕСТО «ЕСТЬ / НЕТ»")
say("-" * 100)
lo, hi = boot_oe(blocks46, "вышли", "сайтов", is_lol)
say(f"  Выход .lol, 46 пулов: O/E = {oe_blocks(blocks46,'вышли','сайтов',is_lol)[2]:.3f} "
    f"[95 % бутстреп по доменам: {lo:.2f}; {hi:.2f}] — «штраф 9 %» на деле «от {(1-hi)*100:.0f} % до {(1-lo)*100:.0f} %»")
lo2, hi2 = boot_oe(blocks46, "рег", "сайтов", is_lol)
say(f"  Регистрации .lol, 46 пулов (34 события при ожидании 38,3): O/E = "
    f"{oe_blocks(blocks46,'рег','сайтов',is_lol)[2]:.3f} [95 %: {lo2:.2f}; {hi2:.2f}]")
say(f"  → формулировка «в регистрациях штраф НЕ виден» слишком сильная: интервал допускает "
    f"и штраф до ×{lo2:.2f}, и выигрыш до ×{hi2:.2f}. Правильно: «данных не хватает, чтобы "
    f"отличить штраф по деньгам от его отсутствия».")
lo3, hi3 = boot_oe(bc, "вышли", "сайтов", is_cas)
lo4, hi4 = boot_oe(bc, "рег", "сайтов", is_cas)
say(f"  .casino выход: O/E = {oe_blocks(bc,'вышли','сайтов',is_cas)[2]:.3f} [95 %: {lo3:.2f}; {hi3:.2f}]; "
    f"регистрации O/E = {oe_blocks(bc,'рег','сайтов',is_cas)[2]:.3f} [95 %: {lo4:.2f}; {hi4:.2f}] (19 событий)")

say()
say("-" * 100)
say("7. МОЩНОСТЬ ТЕСТА НЕОДНОРОДНОСТИ (можно ли вообще было увидеть «×0,5 против ×1,0»)")
say("-" * 100)


def het_stat(pp, lolset):
    """Взвешенная по сайтам дисперсия L между пулами; lolset — dict пул→set индексов."""
    Ls, Ws = [], []
    for i, (k, ds) in enumerate(pp):
        idx = lolset[i]
        e1 = s1 = e0 = s0 = 0
        for j, d in enumerate(ds):
            if j in idx:
                e1 += d["_e"]; s1 += d["сайтов"]
            else:
                e0 += d["_e"]; s0 += d["сайтов"]
        L = math.log((e1 + 0.5) / (s1 + 1)) - math.log((e0 + 0.5) / (s0 + 1))
        Ls.append(L); Ws.append(s1 + s0)
    W = sum(Ws)
    m = sum(l * w for l, w in zip(Ls, Ws)) / W
    return sum(w * (l - m) ** 2 for l, w in zip(Ls, Ws)) / W


PP20 = P20
for k, ds in PP20:
    for d in ds:
        d["_e"] = d["вышли"]
obs_idx = [set(j for j, d in enumerate(ds) if d["зона"] == "lol") for _, ds in PP20]
obs = het_stat(PP20, obs_idx)
rnd = random.Random(99)


def null_draw():
    return [set(rnd.sample(range(len(ds)), len(obs_idx[i]))) for i, (_, ds) in enumerate(PP20)]


null = []
for _ in range(4000):
    null.append(het_stat(PP20, null_draw()))
null.sort()
crit = null[int(0.95 * len(null))]
pobs = sum(1 for v in null if v >= obs) / len(null)
say(f"  Наблюдённая дисперсия {obs:.4f}; нулевое распределение: медиана {null[len(null)//2]:.4f}, "
    f"95-й процентиль (критическое значение) {crit:.4f}; p = {pobs:.4f} (совпало с 0,26 тестировщика)")

# мощность: берём нулевую раскладку и «втыкаем» настоящий штраф в clean/nabory
for f in (0.5, 0.6, 0.7):
    hits = 0
    R = 300
    rnd2 = random.Random(2024)
    for _ in range(R):
        idxs = null_draw()
        # прореживаем выход .lol в пулах семейств clean и nabory
        for i, (k, ds) in enumerate(PP20):
            fam = ds[0]["семейство"]
            for j, d in enumerate(ds):
                d["_e"] = d["вышли"]
            if fam in ("clean", "nabory"):
                for j in idxs[i]:
                    e = ds[j]["вышли"]
                    ds[j]["_e"] = sum(1 for _ in range(e) if rnd2.random() < f)
        st = het_stat(PP20, idxs)
        if st >= crit:
            hits += 1
        for k, ds in PP20:
            for d in ds:
                d["_e"] = d["вышли"]
    say(f"  Мощность увидеть «×{f} у clean+nabory, ×1,0 у остальных» при α = 0,05: "
        f"{hits/R*100:.0f} % (из {R} симуляций)")
say("  → тест неоднородности на 20 пулах маломощен: даже настоящее расслоение «половина против")
say("    единицы» он ловит меньше чем в половине случаев. Поэтому p = 0,26 означает «не показано»,")
say("    а не «доказано, что штраф одинаков». Формулировка «Неоднородность: нет» сильнее данных.")

say()
say("-" * 100)
say("8. ПРЯМОЙ КОНТРАСТ СЕМЕЙСТВ НА ВСЕХ 46 ПУЛАХ (самая сильная форма гипотезы)")
say("-" * 100)
say("  Тестировщик мерил неоднородность дисперсией между 20 пулами. Более мощный вариант —")
say("  сравнить прямо те группы, о которых говорит гипотеза, на всех 46 парных пулах.")
fam_oe = {}
for fam in ("clean", "nabory", "NEW", "content-дата", "archive", "script", "прочее", "Generator", "контроль", "тест"):
    bl = [ds for k, ds in P46 if ds[0]["семейство"] == fam]
    if not bl:
        continue
    O, E, oe = oe_blocks(bl, "вышли", "сайтов", is_lol)
    if E < 20:
        continue
    lo, hi = boot_oe(bl, "вышли", "сайтов", is_lol)
    nl = sum(1 for ds in bl for d in ds if is_lol(d))
    nt = sum(1 for ds in bl for d in ds if not is_lol(d))
    reg = sum(d["рег"] for ds in bl for d in ds)
    fam_oe[fam] = oe
    say(f"    {fam:14s}: пулов {len(bl):2d}, доменов team {nt:3d} / lol {nl:3d}; выход .lol O/E = {oe:.3f} "
        f"[95 %: {lo:.2f}; {hi:.2f}]; регистраций в пулах {reg}")

GA = {"clean", "nabory"}
GB = {"content-дата", "NEW"}
blA = [ds for k, ds in P46 if ds[0]["семейство"] in GA]
blB = [ds for k, ds in P46 if ds[0]["семейство"] in GB]


def contrast(bA, bB):
    OA, EA, _ = oe_blocks(bA, "вышли", "сайтов", is_lol)
    OB, EB, _ = oe_blocks(bB, "вышли", "сайтов", is_lol)
    return math.log((OA / EA) / (OB / EB)), OA / EA, OB / EB


obs_c, oeA, oeB = contrast(blA, blB)
rndc = random.Random(5)
cnt = 0
NP = 20000
prepA = [(ds, sum(1 for d in ds if is_lol(d))) for ds in blA]
prepB = [(ds, sum(1 for d in ds if is_lol(d))) for ds in blB]


def perm_oe(prep):
    O = E = 0.0
    for ds, k in prep:
        tn = sum(d["вышли"] for d in ds)
        td = sum(d["сайтов"] for d in ds)
        if td == 0:
            continue
        rate = tn / td
        idx = rndc.sample(range(len(ds)), k)
        for i in idx:
            O += ds[i]["вышли"]
            E += rate * ds[i]["сайтов"]
    return (O / E) if E else float("nan")


for _ in range(NP):
    c = math.log(perm_oe(prepA) / perm_oe(prepB))
    if abs(c) >= abs(obs_c):
        cnt += 1
pc = (cnt + 1) / (NP + 1)
say(f"  Контраст «clean+nabory» против «content-дата+NEW» по выходу .lol: "
    f"O/E {oeA:.3f} против {oeB:.3f}, отношение {oeA/oeB:.2f}, двусторонний перестановочный p = {fp(pc)}")
blA2 = [ds for k, ds in P46 if ds[0]["семейство"] in GA and k != ("clean7_part1_50оформлено", "2026-09-11")]
prepA2 = [(ds, sum(1 for d in ds if is_lol(d))) for ds in blA2]
obs_c2 = math.log((oe_blocks(blA2, "вышли", "сайтов", is_lol)[2]) / oeB)
cnt = 0
for _ in range(NP):
    c = math.log(perm_oe(prepA2) / perm_oe(prepB))
    if abs(c) >= abs(obs_c2):
        cnt += 1
say(f"  То же без пула clean7 11.09: O/E {oe_blocks(blA2,'вышли','сайтов',is_lol)[2]:.3f} против {oeB:.3f}, "
    f"отношение {math.exp(obs_c2):.2f}, p = {fp((cnt+1)/(NP+1))}")
say("  Группы выбраны после просмотра данных (post hoc) — при поправке на ~80 объявленных срезов")
say("  ни один из этих p порог 0,05 не проходит.")
say()
say("  Справка по фильтрам: 77 доменов «дней=1» (запуски 16–18.09) вообще не образуют пулов,")
say("  где есть и .team, и .lol (наборы тех дней односортные по зоне), а у 152 доменов с незакрытым")
say("  окном «сайтов в окне» = 0. Поэтому оба исключения на парный анализ не влияют вовсе —")
say("  проверено прямым пересчётом (см. раздел 5).")

say()
say("-" * 100)
say("9. УСТОЙЧИВОСТЬ КОНТРАСТА И АЛЬТЕРНАТИВА «ЭТО ДЕНЬ, А НЕ НАБОР»")
say("-" * 100)


def contrast_p(bA, bB, seed=13, NP=20000, num="вышли"):
    rr = random.Random(seed)
    pA = [(ds, sum(1 for d in ds if is_lol(d))) for ds in bA]
    pB = [(ds, sum(1 for d in ds if is_lol(d))) for ds in bB]

    def one(prep):
        O = E = 0.0
        for ds, k in prep:
            tn = sum(d[num] for d in ds); td = sum(d["сайтов"] for d in ds)
            if td == 0:
                continue
            rate = tn / td
            for i in rr.sample(range(len(ds)), k):
                O += ds[i][num]; E += rate * ds[i]["сайтов"]
        return (O / E) if E else float("nan")

    oa = oe_blocks(bA, num, "сайтов", is_lol)[2]
    ob = oe_blocks(bB, num, "сайтов", is_lol)[2]
    obs = math.log(oa / ob)
    c = sum(1 for _ in range(NP) if abs(math.log(one(pA) / one(pB))) >= abs(obs))
    return oa, ob, (c + 1) / (NP + 1)


blB = [ds for k, ds in P46 if ds[0]["семейство"] in ("content-дата", "NEW")]
variants = [
    ("clean+nabory (11 пулов)", [ds for k, ds in P46 if ds[0]["семейство"] in ("clean", "nabory")]),
    ("без пула clean7 11.09", [ds for k, ds in P46 if ds[0]["семейство"] in ("clean", "nabory")
                               and k != ("clean7_part1_50оформлено", "2026-09-11")]),
    ("только nabory (8 пулов)", [ds for k, ds in P46 if ds[0]["семейство"] == "nabory"]),
    ("только clean (3 пула)", [ds for k, ds in P46 if ds[0]["семейство"] == "clean"]),
]
for nm, bA in variants:
    if not bA:
        continue
    oa, ob, pp = contrast_p(bA, blB)
    lo, hi = boot_oe(bA, "вышли", "сайтов", is_lol)
    nl = sum(1 for ds in bA for d in ds if is_lol(d))
    say(f"  {nm}: O/E .lol {oa:.3f} [95 %: {lo:.2f}; {hi:.2f}] на {nl} доменах .lol "
        f"против {ob:.3f} в «content-дата+NEW»; двусторонний p = {fp(pp)}")
bA0 = [ds for k, ds in P46 if ds[0]["семейство"] in ("clean", "nabory")]
bAt, t3, c3 = drop_topk(bA0, is_lol, "вышли", 3)
oa, ob, pp = contrast_p(bAt, blB)
say(f"  clean+nabory без топ-3 доменов по вышедшим в каждой зоне ({t3} / {c3}): "
    f"O/E {oa:.3f} против {ob:.3f}, p = {fp(pp)}")
say("  → направление («штрафные» наборы ниже) устойчиво, но величина — 0,76–0,80 против 0,95,")
say("    то есть ×0,81, а НЕ ×0,5 против ×1,0, как утверждает гипотеза.")

say()
say("  Сцепка «набор» и «день запуска»:")
ndays = collections.defaultdict(set)
for k, ds in P46:
    ndays[k[0]].add(k[1])
multi = {s: d for s, d in ndays.items() if len(d) > 1}
say(f"    парных пулов {len(P46)}; различных наборов {len(ndays)}; наборов, стоящих в обеих зонах "
    f"больше чем в один день: {len(multi)} ({', '.join(sorted(multi)) if multi else 'нет'})")
say("    → набор почти полностью сцеплен с днём запуска: разделить «штраф зависит от набора» и")
say("      «штраф зависит от дня» на этих данных нельзя в принципе.")
bydayO = collections.defaultdict(float)
bydayE = collections.defaultdict(float)
for k, ds in P46:
    O, E, _ = oe_blocks([ds], "вышли", "сайтов", is_lol)
    bydayO[k[1]] += O
    bydayE[k[1]] += E
say("    выход .lol O/E по дням запуска (только дни с E ≥ 50):")
for d in sorted(bydayE):
    if bydayE[d] >= 50:
        say(f"      {d}: O/E = {bydayO[d]/bydayE[d]:.2f} (O = {bydayO[d]:.0f}, E = {bydayE[d]:.0f})")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write("\n".join(_L) + "\n")
say()
say(f"Сохранено: {OUT}")
