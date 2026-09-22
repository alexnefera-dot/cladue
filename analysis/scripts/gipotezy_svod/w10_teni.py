#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
W10. Контрпроверка гипотезы №10 («правило первого дня»): тени.
Вопрос: не является ли «v1<=5 -> пусто» просто другим именем для «домен не вышел
в поиск» (уровень выхода / поисковые клики), т.е. тенью набора+дня+зоны, которые
уже доказанно управляют выходом? Проверяем, переопределив ожидание E:
  E1 (как у тестировщика): ставка пула на САЙТ x сайты домена;
  E2: ставка пула на ВЫШЕДШИЙ САЙТ x «вышли за 3 суток» домена;
  E3: ставка пула на ПОИСКОВЫЙ КЛИК В ОКНЕ x «кликов из поиска в окне» домена.
Плюс: жёсткая страта набор+день+зона(+блок часа), парные сравнения при равном
уровне выхода, период (август/сентябрь, «КОНТЕНТ НЕ ЗАПИСАН»), выбросы,
объём дня, и информативность нулей.
Только stdlib.
"""
import csv, os, random, math
from collections import defaultdict

SRC = "/home/user/cladue/analysis/export/svod_domenov_21.09.csv"
OUT = "/home/user/cladue/analysis/export/gipotezy_svod/w10_teni.txt"
random.seed(20260922)

buf = []
def p(s=""):
    buf.append(s)
    print(s)

def num(s):
    s = (s or "").strip().replace(" ", "").replace(" ", "").replace(",", ".")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None

def i(s):
    v = num(s)
    return 0 if v is None else int(round(v))

rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
p("W10. ТЕНИ: правило первого дня — это счётчик или пересказ «домен не вышел в поиск»?")
p("Файл: %s; строк (доменов): %d" % (SRC, len(rows)))
p("")

OUTL = {"3615.team", "3286.team"}
full = []
for r in rows:
    r["_v1"] = i(r["вышли за 1 сутки"]); r["_v3"] = i(r["вышли за 3 суток"]); r["_v7"] = i(r["вышли за 7 суток"])
    r["_sites"] = i(r["сайтов"]); r["_sw"] = i(r["сайтов в окне"])
    r["_reg"] = i(r["регистраций в окне 3 суток"]); r["_fd"] = i(r["ФД в окне 3 суток"])
    r["_regall"] = i(r["регистраций"]); r["_fdall"] = i(r["ФД"])
    r["_clk"] = i(r["кликов из поиска в окне"])
    r["_set"] = r["набор контента"].strip(); r["_day"] = r["день запуска"].strip()
    r["_zone"] = r["зона"].strip(); r["_hb"] = r["блок часа"].strip()
    r["_closed"] = r["окно закрыто"].strip() == "да"
    r["_days"] = i(r["дней"])
    full.append(r)

# основной набор — как у тестировщика
base = [r for r in full if r["_closed"] and r["_days"] == 2 and r["домен"] not in OUTL
        and r["_set"] != "КОНТЕНТ НЕ ЗАПИСАН"]
p("Основной набор (окно закрыто, дней=2, без выбросов 3615/3286, без «КОНТЕНТ НЕ ЗАПИСАН»): %d доменов" % len(base))

def pools(data, keyf):
    d = defaultdict(list)
    for r in data:
        d[keyf(r)].append(r)
    return d

def oe(data, keyf, wkey, mark):
    """O, E, доменов по метке; ожидание = ставка страты на единицу wkey."""
    O = E = 0.0
    n = 0; W = 0.0
    for k, g in pools(data, keyf).items():
        sw = sum(x[wkey] for x in g)
        so = sum(x["_reg"] for x in g)
        if sw <= 0 or so <= 0:
            continue
        rate = so / sw
        for x in g:
            if mark(x):
                O += x["_reg"]; E += rate * x[wkey]; n += 1; W += x[wkey]
    return O, E, n, W

KP  = lambda r: (r["_set"], r["_day"])
KPZ = lambda r: (r["_set"], r["_day"], r["_zone"])
KPZH= lambda r: (r["_set"], r["_day"], r["_zone"], r["_hb"])
KDZ = lambda r: (r["_day"], r["_zone"])

M5 = lambda r: r["_v1"] <= 5

p("")
p("="*110)
p("1. ЧТО ИМЕННО ИЗМЕРЯЕТ O/E = 0,09: ожидание на САЙТ против ожидания на ВЫШЕДШИЙ САЙТ и на ПОИСКОВЫЙ КЛИК")
p("="*110)
p("Оговорка: у v1<=5 в среднем вышло ~4%% сайтов, у v1>=6 ~17%% — ожидание «на сайт» приписывает")
p("помеченным доменам регистрации за сайты, которые в поиск не вышли и кликов не дали.")
p("")
p("  страта                         вес ожидания            доменов v1<=5   вес группы      O       E     O/E")
for kname, kf in (("набор+день", KP), ("набор+день+зона", KPZ), ("набор+день+зона+час", KPZH), ("день+зона", KDZ)):
    for wname, wk in (("сайты (тестировщик)", "_sites"), ("вышли за 3 суток", "_v3"), ("поисковые клики в окне", "_clk")):
        O, E, n, W = oe(base, kf, wk, M5)
        p("  %-30s %-22s %10d %14.0f %6.0f %7.1f %7.2f" % (kname, wname, n, W, O, E, (O/E if E > 0 else float('nan'))))
p("")
tot_clk = sum(r["_clk"] for r in base); tot_reg = sum(r["_reg"] for r in base)
g5 = [r for r in base if M5(r)]; g6 = [r for r in base if not M5(r)]
p("  Без страты, на поисковый клик в окне: всего %d рег на %d кликов = %.4f рег/клик." % (tot_reg, tot_clk, tot_reg/tot_clk))
for nm, g in (("v1<=5", g5), ("v1>=6", g6)):
    c = sum(r["_clk"] for r in g); o = sum(r["_reg"] for r in g)
    p("    %-6s доменов %4d, сайтов %6d, вышло за 3 сут %6d, поисковых кликов в окне %7d, рег %3d; рег/клик %.4f; ожидание по общей ставке %.1f"
      % (nm, len(g), sum(r["_sites"] for r in g), sum(r["_v3"] for r in g), c, o, (o/c if c else 0), c*tot_reg/tot_clk))
p("")
p("  Доля кликов: v1<=5 держат %.1f%% сайтов набора, но лишь %.1f%% вышедших сайтов и %.1f%% поисковых кликов в окне."
  % (100*sum(r["_sites"] for r in g5)/sum(r["_sites"] for r in base),
     100*sum(r["_v3"] for r in g5)/sum(r["_v3"] for r in base),
     100*sum(r["_clk"] for r in g5)/tot_clk))

p("")
p("="*110)
p("2. ЕСТЬ ЛИ ОБРЫВ НА ПЯТИ? O/E по узким группам v1 при ожидании на вышедший сайт и на клик (страта набор+день)")
p("="*110)
bins = [(0,0,"0"),(1,3,"1-3"),(4,5,"4-5"),(6,10,"6-10"),(11,20,"11-20"),(21,50,"21-50"),(51,206,">50")]
p("  группа v1   доменов   сайтов   вышли3   клики окна    O   E(сайты) O/E   E(вышли) O/E   E(клики) O/E")
for lo, hi, nm in bins:
    mk = lambda r, lo=lo, hi=hi: lo <= r["_v1"] <= hi
    g = [r for r in base if mk(r)]
    O1,E1,_,_ = oe(base, KP, "_sites", mk)
    O2,E2,_,_ = oe(base, KP, "_v3", mk)
    O3,E3,_,_ = oe(base, KP, "_clk", mk)
    f = lambda O,E: (O/E if E>0 else float('nan'))
    p("  %-10s %8d %8d %8d %11d %4.0f %8.1f %5.2f %9.1f %5.2f %9.1f %5.2f"
      % (nm, len(g), sum(r["_sites"] for r in g), sum(r["_v3"] for r in g), sum(r["_clk"] for r in g),
         O1, E1, f(O1,E1), E2, f(O2,E2), E3, f(O3,E3)))

p("")
p("="*110)
p("3. ПЕРЕСТАНОВКА ПРИ ПРАВИЛЬНОМ ВЕСЕ: тасуем метку v1<=5 внутри страты, ожидание — на вышедший сайт / на клик")
p("="*110)
def perm_test(data, keyf, wkey, mark, nperm=10000):
    groups = []
    for k, g in pools(data, keyf).items():
        sw = sum(x[wkey] for x in g); so = sum(x["_reg"] for x in g)
        if sw <= 0 or so <= 0 or len(g) < 2:
            continue
        groups.append(g)
    obsO = 0.0; obsE = 0.0; nm = 0
    for g in groups:
        for x in g:
            if mark(x):
                obsO += x["_reg"]; nm += 1
    if nm == 0:
        return None
    # ожидание и распределение под перестановкой метки (метки тасуются, вес идёт с доменом)
    sims = []
    for _ in range(nperm):
        s = 0.0
        for g in groups:
            k = sum(1 for x in g if mark(x))
            if k == 0 or k == len(g):
                s += sum(x["_reg"] for x in g if mark(x))
                continue
            idx = random.sample(range(len(g)), k)
            s += sum(g[j]["_reg"] for j in idx)
        sims.append(s)
    sims.sort()
    le = sum(1 for s in sims if s <= obsO)
    mean = sum(sims)/len(sims)
    lo = sims[int(0.025*len(sims))]; hi = sims[int(0.975*len(sims))-1]
    return obsO, mean, lo, hi, (le+1)/(nperm+1), nm, len(groups)

p("  Перестановка метки внутри страты — тест «есть ли у помеченных дефицит регистраций СВЕРХ их доли группы»")
p("  (это тест тестировщика: он тасует метку, не учитывая, что метка тождественна низкому выходу).")
for kname, kf in (("набор+день", KP), ("набор+день+зона", KPZ), ("набор+день+зона+час", KPZH)):
    res = perm_test(base, kf, "_sites", M5)
    if res:
        O, mean, lo, hi, pv, nm, ng = res
        p("    %-22s страт>=2 дом. %3d, помечено %3d: O=%.0f, под случайностью в среднем %.1f [%.0f;%.0f], p(O<=набл)=%.4f"
          % (kname, ng, nm, O, mean, lo, hi, pv))
p("")
p("  То же, но тасуем метку ТОЛЬКО среди доменов со схожим уровнем выхода (страта + корзина «вышли за 3 суток»),")
p("  т.е. спрашиваем: добавляет ли счётчик первого дня хоть что-то при равном уровне выхода?")
def v3bin(v):
    for b in (0,1,3,6,11,21,41,81):
        pass
    if v == 0: return "0"
    if v <= 5: return "1-5"
    if v <= 10: return "6-10"
    if v <= 20: return "11-20"
    if v <= 40: return "21-40"
    if v <= 80: return "41-80"
    return ">80"
for kname, kf in (("день + корзина v3", lambda r: (r["_day"], v3bin(r["_v3"]))),
                  ("день+зона + корзина v3", lambda r: (r["_day"], r["_zone"], v3bin(r["_v3"]))),
                  ("набор+день + корзина v3", lambda r: (r["_set"], r["_day"], v3bin(r["_v3"])))):
    res = perm_test(base, kf, "_sites", M5)
    if res:
        O, mean, lo, hi, pv, nm, ng = res
        p("    %-26s страт>=2 дом. %3d, помечено %3d: O=%.0f, под случайностью %.2f [%.0f;%.0f], p(O<=набл)=%.4f"
          % (kname, ng, nm, O, mean, lo, hi, pv))
    else:
        p("    %-26s объёма нет" % kname)

p("")
p("="*110)
p("4. ПАРНЫЕ СРАВНЕНИЯ ПРИ РАВНОМ УРОВНЕ ВЫХОДА: v1<=5 против соседей по пулу с таким же v3")
p("="*110)
p("  Сопоставляем домены внутри пула «набор+день» так, чтобы «вышли за 3 суток» отличались не более чем на 20%% (и не более 3 сайтов).")
pairs = []
for k, g in pools(base, KP).items():
    a = [x for x in g if M5(x)]; b = [x for x in g if not M5(x)]
    used = set()
    for x in a:
        best = None
        for j, y in enumerate(b):
            if j in used: continue
            d = abs(y["_v3"] - x["_v3"])
            if d <= max(3, 0.2*max(1, x["_v3"])):
                if best is None or d < best[0]:
                    best = (d, j, y)
        if best:
            used.add(best[1]); pairs.append((x, best[2]))
p("  Пар найдено: %d (из %d доменов v1<=5 в основном наборе)" % (len(pairs), len(g5)))
if pairs:
    ao = sum(x["_reg"] for x, y in pairs); bo = sum(y["_reg"] for x, y in pairs)
    av3 = sum(x["_v3"] for x, y in pairs); bv3 = sum(y["_v3"] for x, y in pairs)
    ac = sum(x["_clk"] for x, y in pairs); bc = sum(y["_clk"] for x, y in pairs)
    p("  v1<=5:  рег %d, вышли за 3 сут %d, поисковых кликов в окне %d" % (ao, av3, ac))
    p("  пара (v1>=6, тот же пул, тот же уровень выхода): рег %d, вышли за 3 сут %d, поисковых кликов %d" % (bo, bv3, bc))
    n = ao + bo
    if n:
        # точный биномиальный при p=0.5 (равные веса) — двусторонний
        pv = sum(math.comb(n, k) for k in range(0, min(ao, bo)+1)) / 2**n * 2
        p("  Точный биномиальный (рег делятся между парами поровну при H0): %d против %d, двусторонний p = %.3f" % (ao, bo, min(1.0, pv)))
    else:
        p("  Регистраций нет ни у одной стороны пар — сравнение пустое, различить нечего.")

p("")
p("="*110)
p("5. ПЕРИОД, ЗОНА, ДЕНЬ, ОБЪЁМ ДНЯ, ВЫБРОСЫ")
p("="*110)
aug = [r for r in full if r["_closed"] and r["_days"] == 2 and r["домен"] not in OUTL and r["_day"] < "2026-09-01"]
sep = [r for r in full if r["_closed"] and r["_days"] == 2 and r["домен"] not in OUTL and r["_day"] >= "2026-09-01"]
nz  = [r for r in full if r["_closed"] and r["_days"] == 2 and r["домен"] not in OUTL and r["_set"] == "КОНТЕНТ НЕ ЗАПИСАН"]
for nm, g in (("август (все)", aug), ("сентябрь (все)", sep), ("«КОНТЕНТ НЕ ЗАПИСАН»", nz)):
    a = [r for r in g if M5(r)]
    p("  %-24s доменов %4d, из них v1<=5 %4d (%.1f%%), рег в окне всего %3d, у v1<=5 %d; вышли3 у v1<=5 %d из %d"
      % (nm, len(g), len(a), 100*len(a)/max(1,len(g)), sum(r["_reg"] for r in g), sum(r["_reg"] for r in a),
         sum(r["_v3"] for r in a), sum(r["_v3"] for r in g)))
p("  Замечание: 335 доменов «КОНТЕНТ НЕ ЗАПИСАН» сцеплены с датой (до 24.08) и выброшены из основного теста;")
p("  правило на них не проверяемо внутри набора, а только внутри дня.")
p("")
p("  Выбросы 3615.team / 3286.team:")
for r in full:
    if r["домен"] in OUTL:
        p("    %-12s v1=%d v3=%d сайтов=%d рег окно=%d — %s" % (r["домен"], r["_v1"], r["_v3"], r["_sites"], r["_reg"],
          "попал бы в v1<=5" if M5(r) else "в v1>=6, на правило не влияет"))
p("")
p("  Концентрация помеченных по дням (основной набор):")
byday = pools(base, lambda r: r["_day"])
rows_d = []
for d, g in sorted(byday.items()):
    a = [r for r in g if M5(r)]
    rows_d.append((d, len(g), len(a), sum(r["_reg"] for r in g), sum(r["_reg"] for r in a)))
rows_d.sort(key=lambda t: -t[2])
p("    день        доменов  v1<=5  доля    рег дня  рег у v1<=5")
for d, n, a, rg, ra in rows_d[:12]:
    p("    %-10s %8d %6d %5.1f%% %8d %9d" % (d, n, a, 100*a/n, rg, ra))
top = rows_d[:5]
p("    Пять дней с наибольшим числом помеченных дают %d из %d помеченных (%.0f%%) при %d из %d доменов набора (%.0f%%)."
  % (sum(t[2] for t in top), len(g5), 100*sum(t[2] for t in top)/len(g5),
     sum(t[1] for t in top), len(base), 100*sum(t[1] for t in top)/len(base)))

p("")
p("="*110)
p("6. НУЛИ: сколько регистраций им вообще «полагалось»")
p("="*110)
closed = [r for r in full if r["_closed"] and r["домен"] not in OUTL]
zeros = [r for r in closed if r["_v3"] == 0]
rate_clk = tot_reg / tot_clk
rate_v3 = sum(r["_reg"] for r in base) / sum(r["_v3"] for r in base)
p("  Нулей (вышли за 3 суток = 0, окно закрыто): %d; сайтов %d; вышли за 7 суток суммарно %d; поисковых кликов в окне %d."
  % (len(zeros), sum(r["_sites"] for r in zeros), sum(r["_v7"] for r in zeros), sum(r["_clk"] for r in zeros)))
p("  Ожидание регистраций по общей ставке на вышедший сайт (%.4f рег на вышедший сайт): за 3 суток %.2f, за 7 суток %.2f."
  % (rate_v3, 0.0, rate_v3*sum(r["_v7"] for r in zeros)))
p("  Ожидание по ставке на поисковый клик (%.5f): %.2f регистраций." % (rate_clk, rate_clk*sum(r["_clk"] for r in zeros)))
p("  Наблюдено регистраций за всё время: %d, ФД %d." % (sum(r["_regall"] for r in zeros), sum(r["_fdall"] for r in zeros)))
p("  То есть «нули не оживают и не дают регистраций» — утверждение, которое нельзя было опровергнуть:")
p("  при их выходе им полагалось <1 регистрации, наблюдение 0 неотличимо от ожидания 0.")

p("")
p("="*110)
p("7. МОЩНОСТЬ НА ПРАВИЛЬНОМ ВЕСЕ: какой дефицит вообще различим у v1<=5 при ожидании на вышедший сайт/клик")
p("="*110)
for wname, wk in (("вышли за 3 суток", "_v3"), ("поисковые клики в окне", "_clk")):
    for kname, kf in (("набор+день", KP), ("набор+день+зона", KPZ)):
        O, E, n, W = oe(base, kf, wk, M5)
        if E <= 0: continue
        # точный пуассоновский двусторонний ориентир
        pl = sum(math.exp(-E)*E**k/math.factorial(k) for k in range(0, int(O)+1))
        p("  %-16s / %-18s: O=%.0f, E=%.2f, O/E=%.2f; P(O<=набл|E)=%.3f; верхняя граница O/E (95%%, пуассон) ~%.2f"
          % (wname, kname, O, E, O/E, pl, (O+1.92+1.96*math.sqrt(O+1))/E))

p("")
p("="*110)
p("8. ПРОВЕРКА «ЭТО НЕ ТЕНЬ ЗОНЫ»: в каждой зоне при правильном весе ожидание меньше единицы")
p("="*110)
p("  зона     вес                     помечено      O       E     O/E    P(O<=набл|E)")
for z in ("team", "lol", "casino", "buzz"):
    for wname, wk in (("сайты (тестировщик)", "_sites"), ("вышли за 3 суток", "_v3"), ("поисковые клики в окне", "_clk")):
        mk = lambda r, z=z: M5(r) and r["_zone"] == z
        O, E, n, W = oe(base, KPZ, wk, mk)
        pl = sum(math.exp(-E)*E**k/math.factorial(k) for k in range(0, int(O)+1)) if E > 0 else float("nan")
        p("  %-8s %-22s %8d %6.0f %7.2f %7.2f %12.3f" % (z, wname, n, O, E, (O/E if E > 0 else float("nan")), pl))
p("  Вывод раздела: «одинаково в team и lol» — не проверка, а отсутствие мощности: при ожидании на поисковый клик")
p("  зонам полагалось 0.25 (team), 0.58 (lol), 0.24 (buzz), 0.01 (casino) регистрации. Ноль там ничего не доказывает.")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(buf) + "\n")
print("\n[сохранено: %s]" % OUT)
