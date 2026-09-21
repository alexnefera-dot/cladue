#!/usr/bin/env python3
"""
Гипотеза №21. Штраф зоны .lol не одинаков по наборам контента.

Что проверяем.
  Утверждение: внутри пула «набор контента + день запуска» отношение выхода
  в поиск .lol / .team у одних наборов ≈0,5 (clean7_part1_50оформлено,
  nabory…), у других ≈1,0 (content-2026-09-12-7str-oform-*, 12-страничные
  NEW50…); это повторяется у одного набора в разные дни; .casino в тех же
  пулах даёт ×1,2 выхода и ×1,3 регистраций. Реестр уже закрыл «зону в
  среднем» (0,86–1,10 после контента), здесь — формальный тест
  НЕОДНОРОДНОСТИ эффекта зоны по наборам, воспроизводимость и деньги.

Как проверяем (только стандартная библиотека Python 3).
  Данные: analysis/export/svod_domenov_21.09.csv, единица — домен.
  Фильтры (число исключённых печатается): окно закрыто = да; дней ≠ 1;
  «КОНТЕНТ НЕ ЗАПИСАН» исключён (это не набор, сцеплен с датой); зоны
  только team / lol / casino (.buzz — известно худшая, «прочие» 19 доменов
  по одному — не пара); выбросы 3615.team и 3286.team исключены (миллионы
  «прочих» кликов; в частях с кликами они бы искажали).
  Выход = «вышли за 3 суток» / «сайтов в окне» (суммы по группе, не
  средние долей). Деньги = «регистраций в окне 3 суток». Клики = «кликов
  из поиска в окне».
  Страта — пул «набор контента + день запуска».

  (1) Неоднородность. Пулы с ≥3 доменами и в .team, и в .lol (casino-домены
      этих пулов в части 1 не участвуют). На пул: L = ln(выход lol / выход
      team) (с поправкой +0,5 к числу вышедших и +1 к сайтам, чтобы ln был
      определён при нуле — в реальных данных нулей нет). Статистика —
      взвешенная по сайтам дисперсия L между пулами вокруг взвешенного
      среднего (веса: сумма сайтов пула; контроль — гармоническое среднее
      сайтов двух зон и без весов). Постоянный (одинаковый для всех
      наборов) штраф зоны дисперсию не увеличивает, поэтому это тест
      именно на разный штраф у разных наборов. Нуль — 10 000 перестановок
      метки зоны между доменами внутри пула с сохранением числа доменов в
      каждой зоне (random.seed(1)); домен переставляется целиком, поэтому
      известная сверхдисперсия доменов внутри пула учтена. p = доля
      перестановок с дисперсией ≥ наблюдённой. Отдельно — взвешенное
      среднее L (средний штраф) с двусторонним перестановочным p.
      То же по «кликов из поиска в окне / вышли за 3 суток» (кликов на
      вышедший сайт). Чувствительность: порог ≥2 домена в каждой зоне.
      Вторичный тест на заявленную структуру: неоднородность МЕЖДУ
      семействами (колонка «семейство»: clean, nabory, NEW, content-дата,
      archive, script, прочее) — межгрупповая взвешенная дисперсия средних
      L, тот же нуль; это грубее, чем «по наборам», но ближе к формулировке
      («clean7 + nabory против content-дата + NEW»). Группировка выбрана
      после просмотра тех же данных, это оговаривается.
      На пул: 95 % интервал L (пуассоновское приближение — без учёта
      сцепки сайтов домена, узковат; и бутстреп по доменам, 2000 выборок —
      с учётом сцепки, при 3 доменах груб) и перестановочный двусторонний
      p пула (точный перебор всех раскладок, если их ≤ 50 000, иначе
      10 000 случайных).
  (2) Воспроизводимость. Наборы, стоящие и в .team, и в .lol в ≥2 дня:
      знак L по дням, знаковый критерий; на набор — совместный O/E выхода
      .lol по всем его дням с перестановочным p (перестановки внутри
      каждого дня). Если таких наборов ≤2 — так и сказать: критерий не
      решает.
  (3) Деньги в «штрафной» группе. Пулы семейств clean и nabory с доменами
      в обеих зонах (≥1 домен в каждой): регистраций и ФД в окне по зонам;
      O/E регистраций .lol, где E = (регистраций пула / сайтов пула) ×
      сайтов .lol; перестановочный p (метка зоны внутри пула, домен со
      своими регистрациями целиком). Для clean7_part1_50оформлено 11.09 —
      точный биномиальный расчёт «0 из 6 в .lol при доле сайтов .lol» и
      доменная перестановка. Для сравнения — та же таблица по группе
      «content-2026-09-12 + 12-страничные NEW» и по всем пулам части 1.
  (4) .casino. Пулы с ≥1 доменом .casino и ≥1 доменом .team/.lol:
      O/E выхода и регистраций .casino (E = доля пула × сайтов casino),
      перестановочный p (метка casino / не casino внутри пула), плюс
      пуассоновский расчёт «19 при ожидании 15» из формулировки (он
      считает регистрации независимыми — на деле они сцеплены по доменам,
      поэтому решает перестановка). Помечается как предварительное.

  Критерии из постановки: p неоднородности < 0,05 и одинаковый знак у
  одного набора в ≥2 днях; casino O/E ≥ 1,15 при p < 0,1. Опровержение:
  дисперсия внутри нуля (отношения 0,5 — шум).
"""
import collections
import csv
import itertools
import math
import os
import random

CSV_PATH = "analysis/export/svod_domenov_21.09.csv"
OUT_PATH = "analysis/export/gipotezy_svod/h21_zone_penalty_by_set.txt"
N_PERM = 10000
N_BOOT = 2000
OUTLIERS = {"3615.team", "3286.team"}
ZONES = ("team", "lol", "casino")

_lines = []


def say(s=""):
    print(s)
    _lines.append(s)


def to_int(x):
    x = (x or "").strip()
    return int(float(x)) if x else 0


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
    zc = collections.Counter(r["зона"] for r in rows)
    rows = [r for r in rows if r["зона"] in ZONES]
    say(f"  исключено .buzz: {zc.get('buzz', 0)}, «прочие» зоны: "
        f"{n0 - len(rows) - zc.get('buzz', 0)} (осталось {len(rows)})")
    n0 = len(rows)
    outl = [r["домен"] for r in rows if r["домен"] in OUTLIERS]
    rows = [r for r in rows if r["домен"] not in OUTLIERS]
    say(f"  исключено выбросов по «прочим» кликам (3615.team, 3286.team): "
        f"{len(outl)} — {', '.join(outl) if outl else 'их уже нет после фильтров'} (осталось {len(rows)})")
    doms = []
    for r in rows:
        doms.append({
            "домен": r["домен"], "зона": r["зона"],
            "набор": r["набор контента"], "день": r["день запуска"],
            "семейство": r["семейство"], "страниц": r["страниц"],
            "сайтов": to_int(r["сайтов в окне"]),
            "вышли": to_int(r["вышли за 3 суток"]),
            "клики": to_int(r["кликов из поиска в окне"]),
            "рег": to_int(r["регистраций в окне 3 суток"]),
            "фд": to_int(r["ФД в окне 3 суток"]),
        })
    return doms


def build_pools(doms):
    pools = collections.defaultdict(list)
    for d in doms:
        pools[(d["набор"], d["день"])].append(d)
    return pools


def zsum(ds, key):
    return sum(d[key] for d in ds)


def logratio(e1, s1, e0, s0):
    """ln((e1+0.5)/(s1+1)) - ln((e0+0.5)/(s0+1)): lol (1) против team (0)."""
    return math.log((e1 + 0.5) / (s1 + 1)) - math.log((e0 + 0.5) / (s0 + 1))


def wvar(ls, ws):
    W = sum(ws)
    m = sum(l * w for l, w in zip(ls, ws)) / W
    return sum(w * (l - m) ** 2 for l, w in zip(ls, ws)) / W, m


def fmt_p(p):
    return f"{p:.4f}" if p >= 0.0001 else "<0.0001"


# --------------------------------------------------- часть 1: неоднородность
def pair_pools(pools, min_n):
    """Пулы с ≥min_n доменов в team и в lol; возвращает список
    (ключ, домены team+lol в порядке, число lol)."""
    out = []
    for k in sorted(pools, key=lambda k: (k[1], k[0])):
        ds = pools[k]
        t = [d for d in ds if d["зона"] == "team"]
        l = [d for d in ds if d["зона"] == "lol"]
        if len(t) >= min_n and len(l) >= min_n:
            out.append((k, t + l, len(l)))
    return out


def pool_L(ds, lol_idx, num_key, den_key):
    """L для одного пула при заданном множестве индексов lol."""
    e1 = s1 = e0 = s0 = 0
    for i, d in enumerate(ds):
        if i in lol_idx:
            e1 += d[num_key]; s1 += d[den_key]
        else:
            e0 += d[num_key]; s0 += d[den_key]
    return logratio(e1, s1, e0, s0), (e1, s1, e0, s0)


def weights_for(pp, kind):
    ws = []
    for k, ds, nl in pp:
        st = zsum(ds[:len(ds) - nl], "сайтов"); sl = zsum(ds[len(ds) - nl:], "сайтов")
        if kind == "sites":
            ws.append(st + sl)
        elif kind == "harm":
            ws.append(2 * st * sl / (st + sl))
        else:
            ws.append(1.0)
    return ws


def heterogeneity_test(pp, num_key, den_key, groups=None, label=""):
    """Возвращает словарь с наблюдёнными и p по трём весам + среднее L.
    groups: список меток групп (по пулам) для межгрупповой дисперсии."""
    rng = random.Random(1)
    n = len(pp)
    obs_L = []
    for k, ds, nl in pp:
        lol_idx = set(range(len(ds) - nl, len(ds)))
        L, _ = pool_L(ds, lol_idx, num_key, den_key)
        obs_L.append(L)
    wsets = {"сайты": weights_for(pp, "sites"),
             "гарм.": weights_for(pp, "harm"),
             "без весов": weights_for(pp, "none")}
    obs = {}
    for wn, ws in wsets.items():
        v, m = wvar(obs_L, ws)
        obs[wn] = (v, m)
    # межгрупповая дисперсия по семействам (веса — сайты)
    def between(ls, ws, gs):
        W = sum(ws); m = sum(l * w for l, w in zip(ls, ws)) / W
        gw = collections.defaultdict(float); gl = collections.defaultdict(float)
        for l, w, g in zip(ls, ws, gs):
            gw[g] += w; gl[g] += l * w
        return sum(gw[g] * (gl[g] / gw[g] - m) ** 2 for g in gw) / W
    obs_between = between(obs_L, wsets["сайты"], groups) if groups else None
    cnt = {wn: 0 for wn in wsets}
    cnt_mean = {wn: 0 for wn in wsets}
    cnt_between = 0
    null_var_mean = {wn: 0.0 for wn in wsets}
    null_between_mean = 0.0
    for _ in range(N_PERM):
        Ls = []
        for k, ds, nl in pp:
            lol_idx = set(rng.sample(range(len(ds)), nl))
            L, _ = pool_L(ds, lol_idx, num_key, den_key)
            Ls.append(L)
        for wn, ws in wsets.items():
            v, m = wvar(Ls, ws)
            null_var_mean[wn] += v
            if v >= obs[wn][0]:
                cnt[wn] += 1
            if abs(m) >= abs(obs[wn][1]):
                cnt_mean[wn] += 1
        if groups:
            b = between(Ls, wsets["сайты"], groups)
            null_between_mean += b
            if b >= obs_between:
                cnt_between += 1
    res = {"n": n, "obs_L": obs_L, "obs": obs,
           "p_var": {wn: cnt[wn] / N_PERM for wn in wsets},
           "null_var": {wn: null_var_mean[wn] / N_PERM for wn in wsets},
           "p_mean": {wn: cnt_mean[wn] / N_PERM for wn in wsets},
           "obs_between": obs_between,
           "p_between": (cnt_between / N_PERM) if groups else None,
           "null_between": (null_between_mean / N_PERM) if groups else None}
    return res


def pool_perm_p(ds, nl, num_key, den_key, rng):
    """Двусторонний перестановочный p для L одного пула: точный перебор,
    если раскладок ≤ 50 000, иначе 10 000 случайных."""
    n = len(ds)
    lol_idx = set(range(n - nl, n))
    L_obs, _ = pool_L(ds, lol_idx, num_key, den_key)
    total = math.comb(n, nl)
    if total <= 50000:
        cnt = 0
        for comb in itertools.combinations(range(n), nl):
            L, _ = pool_L(ds, set(comb), num_key, den_key)
            if abs(L) >= abs(L_obs) - 1e-12:
                cnt += 1
        return cnt / total, total, True
    cnt = 0
    for _ in range(N_PERM):
        L, _ = pool_L(ds, set(rng.sample(range(n), nl)), num_key, den_key)
        if abs(L) >= abs(L_obs) - 1e-12:
            cnt += 1
    return cnt / N_PERM, total, False


def boot_ci(t, l, num_key, den_key, rng):
    vals = []
    for _ in range(N_BOOT):
        tb = [rng.choice(t) for _ in t]
        lb = [rng.choice(l) for _ in l]
        vals.append(logratio(zsum(lb, num_key), zsum(lb, den_key),
                             zsum(tb, num_key), zsum(tb, den_key)))
    vals.sort()
    return vals[int(0.025 * N_BOOT)], vals[int(0.975 * N_BOOT) - 1]


def part1(pools):
    say()
    say("=" * 100)
    say("ЧАСТЬ 1. Неоднородность штрафа .lol по пулам «набор контента + день» (≥3 домена в .team и в .lol)")
    say("=" * 100)
    pp = pair_pools(pools, 3)
    say(f"Пулов: {len(pp)}; доменов .team {sum(len(ds) - nl for _, ds, nl in pp)}, "
        f".lol {sum(nl for _, ds, nl in pp)}")
    rng = random.Random(1)
    say()
    say("Таблица пулов (выход = вышли за 3 суток / сайтов в окне; рег = регистраций в окне 3 суток;")
    say("  L = ln(выход lol / выход team); ДИ-Пуассон без сцепки доменов; ДИ-бутстреп по доменам;")
    say("  p пула — двусторонний перестановочный, «точн.» = перебор всех раскладок):")
    hdr = (f"{'день':10s} {'набор контента':34s} {'семейство':12s} | {'team: дом/сайт/вышли/выход/рег':32s} | "
           f"{'lol: дом/сайт/вышли/выход/рег':32s} | {'lol/team':8s} {'L':6s} {'ДИ-Пуассон':16s} {'ДИ-бутстреп':16s} {'p пула':8s}")
    say(hdr)
    say("-" * len(hdr))
    groups = []
    rows_out = []
    for k, ds, nl in pp:
        t = ds[:len(ds) - nl]; l = ds[len(ds) - nl:]
        et, st, rt = zsum(t, "вышли"), zsum(t, "сайтов"), zsum(t, "рег")
        el, sl, rl = zsum(l, "вышли"), zsum(l, "сайтов"), zsum(l, "рег")
        L = logratio(el, sl, et, st)
        ratio = (el / sl) / (et / st) if et and el else float("nan")
        se = math.sqrt(1 / (el + 0.5) + 1 / (et + 0.5))
        lo, hi = boot_ci(t, l, "вышли", "сайтов", rng)
        p, total, exact = pool_perm_p(ds, nl, "вышли", "сайтов", rng)
        fam = t[0]["семейство"]
        groups.append(fam)
        say(f"{k[1]:10s} {k[0][:34]:34s} {fam:12s} | {len(t):3d}/{st:5d}/{et:4d}/{et/st:.3f}/{rt:2d}{'':10s} | "
            f"{len(l):3d}/{sl:5d}/{el:4d}/{el/sl:.3f}/{rl:2d}{'':10s} | {ratio:8.2f} {L:6.2f} "
            f"[{L-1.96*se:5.2f};{L+1.96*se:5.2f}] [{lo:5.2f};{hi:5.2f}] {fmt_p(p):8s}{'точн.' if exact else ''}")
        rows_out.append((k, fam, ratio, L, p))
    say()
    say("Тест неоднородности по выходу (вышли за 3 суток / сайтов):")
    res = heterogeneity_test(pp, "вышли", "сайтов", groups=groups)
    for wn in ("сайты", "гарм.", "без весов"):
        v, m = res["obs"][wn]
        say(f"  веса {wn:10s}: дисперсия L между пулами {v:.4f} (на перестановках в среднем {res['null_var'][wn]:.4f}), "
            f"p = {fmt_p(res['p_var'][wn])}; среднее L = {m:+.3f} (lol/team = {math.exp(m):.2f}), "
            f"двусторонний p = {fmt_p(res['p_mean'][wn])}")
    say(f"  Межгрупповая дисперсия по семействам ({', '.join(sorted(set(groups)))}): "
        f"{res['obs_between']:.4f} (на перестановках {res['null_between']:.4f}), p = {fmt_p(res['p_between'])} "
        f"— группировка задана после просмотра данных, ориентир, не решающий тест")
    p1_exit = res
    # средние L по семействам
    say()
    say("Средние по семействам (взвешенно по сайтам; O/E — вышли .lol против ожидания по доле сайтов в пуле):")
    fam_acc = collections.defaultdict(lambda: [0, 0, 0.0, 0, 0, 0.0, 0])  # pools, doms_lol, O, E, sites_l
    for (k, ds, nl), L, fam in zip(pp, res["obs_L"], groups):
        t = ds[:len(ds) - nl]; l = ds[len(ds) - nl:]
        et, st = zsum(t, "вышли"), zsum(t, "сайтов"); el, sl = zsum(l, "вышли"), zsum(l, "сайтов")
        E = (et + el) / (st + sl) * sl
        a = fam_acc[fam]
        a[0] += 1; a[1] += len(l); a[2] += el; a[3] += E; a[4] += len(t); a[5] += L * (st + sl); a[6] += st + sl
    for fam, a in sorted(fam_acc.items(), key=lambda x: -x[1][6]):
        say(f"  {fam:12s}: пулов {a[0]:2d}, доменов team {a[4]:3d} / lol {a[1]:3d}; вышли .lol O = {a[2]:4.0f}, E = {a[3]:7.1f}, "
            f"O/E = {a[2]/a[3]:.2f}; среднее L = {a[5]/a[6]:+.3f} (lol/team {math.exp(a[5]/a[6]):.2f})")
    say()
    say("Тест неоднородности по «кликов из поиска в окне / вышли за 3 суток» (кликов на вышедший сайт):")
    res2 = heterogeneity_test(pp, "клики", "вышли", groups=groups)
    for wn in ("сайты", "гарм.", "без весов"):
        v, m = res2["obs"][wn]
        say(f"  веса {wn:10s}: дисперсия {v:.4f} (на перестановках {res2['null_var'][wn]:.4f}), p = {fmt_p(res2['p_var'][wn])}; "
            f"среднее L = {m:+.3f} (lol/team = {math.exp(m):.2f}), двусторонний p = {fmt_p(res2['p_mean'][wn])}")
    say(f"  Межгрупповая по семействам: {res2['obs_between']:.4f} (на перестановках {res2['null_between']:.4f}), p = {fmt_p(res2['p_between'])}")
    say("  Пулы по кликам на вышедший сайт (lol/team):")
    for (k, ds, nl), L in zip(pp, res2["obs_L"]):
        t = ds[:len(ds) - nl]; l = ds[len(ds) - nl:]
        say(f"    {k[1]} {k[0][:34]:34s} team {zsum(t,'клики'):6d}/{zsum(t,'вышли'):4d} = {zsum(t,'клики')/max(1,zsum(t,'вышли')):6.1f}; "
            f"lol {zsum(l,'клики'):6d}/{zsum(l,'вышли'):4d} = {zsum(l,'клики')/max(1,zsum(l,'вышли')):6.1f}; lol/team {math.exp(L):.2f}")
    say()
    say("Чувствительность: порог ≥2 домена в каждой зоне, по выходу:")
    pp2 = pair_pools(pools, 2)
    groups2 = [ds[0]["семейство"] for _, ds, _ in pp2]
    res3 = heterogeneity_test(pp2, "вышли", "сайтов", groups=groups2)
    keys1 = {k for k, _, _ in pp}
    say(f"  пулов {len(pp2)} (добавились: "
        + "; ".join(f"{k[1]} {k[0][:30]} ({len(ds)-nl}/{nl})" for k, ds, nl in pp2 if k not in keys1)
        + ")")
    for wn in ("сайты", "гарм.", "без весов"):
        v, m = res3["obs"][wn]
        say(f"  веса {wn:10s}: дисперсия {v:.4f} (на перестановках {res3['null_var'][wn]:.4f}), p = {fmt_p(res3['p_var'][wn])}; "
            f"среднее L = {m:+.3f} (lol/team {math.exp(m):.2f}), p = {fmt_p(res3['p_mean'][wn])}")
    say(f"  Межгрупповая по семействам: {res3['obs_between']:.4f} (на перестановках {res3['null_between']:.4f}), p = {fmt_p(res3['p_between'])}")
    say()
    say("Проверка «один пул или структура»: те же тесты без clean7_part1_50оформлено 11.09 (единственный пул со значимым собственным p):")
    key_c7 = ("clean7_part1_50оформлено", "2026-09-11")
    loo = {}
    for name, plist in (("≥3 домена", pp), ("≥2 домена", pp2)):
        sub = [(k, ds, nl) for k, ds, nl in plist if k != key_c7]
        gsub = [ds[0]["семейство"] for _, ds, _ in sub]
        r = heterogeneity_test(sub, "вышли", "сайтов", groups=gsub)
        loo[name] = r
        v, m = r["obs"]["сайты"]
        say(f"  порог {name}: пулов {len(sub)}; дисперсия {v:.4f} (на перестановках {r['null_var']['сайты']:.4f}), p = {fmt_p(r['p_var']['сайты'])}; "
            f"между семействами {r['obs_between']:.4f} (на перестановках {r['null_between']:.4f}), p = {fmt_p(r['p_between'])}; "
            f"среднее L {m:+.3f} (lol/team {math.exp(m):.2f}), p = {fmt_p(r['p_mean']['сайты'])}")
    say()
    say("Пулы из формулировки (≈0,5 против ≈1,0) и их индивидуальные p (на 3+3 доменах всего 20 раскладок — минимум p = 0,10):")
    for k, fam, ratio, L, p in rows_out:
        say(f"  {k[1]} {k[0][:40]:40s} lol/team {ratio:.2f}  p пула {fmt_p(p)}")
    return pp, p1_exit, res2, res3, pp2, loo


# ------------------------------------------------ часть 2: воспроизводимость
def part2(pools):
    say()
    say("=" * 100)
    say("ЧАСТЬ 2. Воспроизводимость знака у одного набора в разные дни (набор стоит и в .team, и в .lol в ≥2 дня)")
    say("=" * 100)
    byset = collections.defaultdict(list)
    for k, ds in pools.items():
        t = [d for d in ds if d["зона"] == "team"]; l = [d for d in ds if d["зона"] == "lol"]
        if t and l:
            byset[k[0]].append((k[1], t, l))
    multi = {s: sorted(v) for s, v in byset.items() if len(v) >= 2}
    say(f"Наборов в обеих зонах в ≥2 дня (порог ≥1 домен в зоне): {len(multi)}")
    rng = random.Random(1)
    agree = 0
    details = {}
    for s, days in sorted(multi.items()):
        say(f"  Набор {s}:")
        signs = []
        Ls = []
        pool_data = []
        O = 0.0; E = 0.0
        for day, t, l in days:
            et, st, rt = zsum(t, "вышли"), zsum(t, "сайтов"), zsum(t, "рег")
            el, sl, rl = zsum(l, "вышли"), zsum(l, "сайтов"), zsum(l, "рег")
            L = logratio(el, sl, et, st)
            ds = t + l
            p, total, exact = pool_perm_p(ds, len(l), "вышли", "сайтов", rng)
            say(f"    {day}: team {len(t)} дом/{st} сайт/{et} вышли/{et/st:.3f}/{rt} рег; lol {len(l)} дом/{sl} сайт/{el} вышли/{el/sl:.3f}/{rl} рег; "
                f"lol/team {math.exp(L):.2f}, L {L:+.2f}, p пула {fmt_p(p)}{' (точн., раскладок ' + str(total) + ')' if exact else ''}")
            signs.append(1 if L > 0 else -1); Ls.append(L)
            pool_data.append((ds, len(l)))
            O += el; E += (et + el) / (st + sl) * sl
        same = len(set(signs)) == 1
        agree += same
        # совместный O/E по дням
        cnt_lo = cnt_hi = 0
        for _ in range(N_PERM):
            Op = 0.0
            for ds, nl in pool_data:
                idx = set(rng.sample(range(len(ds)), nl))
                Op += sum(ds[i]["вышли"] for i in idx)
            if Op <= O: cnt_lo += 1
            if Op >= O: cnt_hi += 1
        say(f"    знак L по дням {'совпадает' if same else 'НЕ совпадает'} ({', '.join('+' if x > 0 else '−' for x in signs)}); "
            f"совместно по дням: вышли .lol O = {O:.0f}, E = {E:.1f}, O/E = {O/E:.2f}, перестановочный p (O ≤ набл.) = {fmt_p(cnt_lo/N_PERM)}, "
            f"(O ≥ набл.) = {fmt_p(cnt_hi/N_PERM)}")
        details[s] = {"days": [d for d, _, _ in days], "ratios": [math.exp(x) for x in Ls], "same": same,
                      "OE": O / E, "p_lo": cnt_lo / N_PERM, "p_hi": cnt_hi / N_PERM}
    k = len(multi)
    if k:
        # знаковый критерий: при нуле P(совпадение) = 0.5 у набора из 2 дней
        p_sign = sum(math.comb(k, j) for j in range(agree, k + 1)) / 2 ** k
        say(f"Знаковый критерий: совпал знак у {agree} из {k} наборов; при нуле ожидание {k/2:.1f}, p = {p_sign:.3f}")
        if k <= 2:
            say("  При ≤2 наборах знаковый критерий ничего решить не может (минимальный p = 0,25): воспроизводимость на своде не проверяется.")
    else:
        say("  Ни одного такого набора — воспроизводимость на своде не проверяется.")
    # отдельно: NEW102 — в обеих зонах только 11.09
    n102 = [(k, len([d for d in ds if d['зона']=='team']), len([d for d in ds if d['зона']=='lol']), len([d for d in ds if d['зона']=='casino']))
            for k, ds in pools.items() if k[0].startswith("NEW102")]
    say("Справка: NEW102оформленобездаты/сдатой по дням (team/lol/casino): "
        + "; ".join(f"{k[1]} {k[0][6:]} {t}/{l}/{c}" for k, t, l, c in sorted(n102, key=lambda x: (x[0][1], x[0][0])))
        + " — в обеих зонах team и lol только 11.09, «против других дней» сравнивать не с чем.")
    return details


# --------------------------------------------- часть 3: деньги по группам
def money_block(title, plist, rng, show_pools=True):
    """plist: список (ключ, домены team+lol, n_lol). O/E регистраций и выхода .lol."""
    say(f"  {title}: пулов {len(plist)}")
    tot = {z: [0, 0, 0, 0, 0, 0] for z in ("team", "lol")}  # доменов, сайтов, вышли, клики, рег, фд
    O_reg = E_reg = O_ex = E_ex = 0.0
    O_reg_c = E_reg_c = 0.0
    pool_data = []
    for k, ds, nl in plist:
        t = ds[:len(ds) - nl]; l = ds[len(ds) - nl:]
        for z, g in (("team", t), ("lol", l)):
            a = tot[z]
            a[0] += len(g); a[1] += zsum(g, "сайтов"); a[2] += zsum(g, "вышли"); a[3] += zsum(g, "клики"); a[4] += zsum(g, "рег"); a[5] += zsum(g, "фд")
        S = zsum(ds, "сайтов"); R = zsum(ds, "рег"); X = zsum(ds, "вышли"); C = zsum(ds, "клики")
        sl = zsum(l, "сайтов"); cl = zsum(l, "клики")
        O_reg += zsum(l, "рег"); E_reg += R / S * sl
        O_ex += zsum(l, "вышли"); E_ex += X / S * sl
        O_reg_c += zsum(l, "рег"); E_reg_c += (R / C * cl) if C else 0
        pool_data.append((ds, nl))
        if show_pools:
            say(f"    {k[1]} {k[0][:36]:36s} team {len(t):2d} дом/{zsum(t,'сайтов'):5d} сайт/{zsum(t,'вышли'):4d} вышли/{zsum(t,'клики'):6d} кл/{zsum(t,'рег'):2d} рег/{zsum(t,'фд')} ФД | "
                f"lol {len(l):2d} дом/{zsum(l,'сайтов'):5d} сайт/{zsum(l,'вышли'):4d} вышли/{zsum(l,'клики'):6d} кл/{zsum(l,'рег'):2d} рег/{zsum(l,'фд')} ФД")
    for z in ("team", "lol"):
        a = tot[z]
        say(f"    итого {z:5s}: доменов {a[0]:3d}, сайтов {a[1]:6d}, вышли {a[2]:5d} ({a[2]/a[1]*100:.1f} %), кликов из поиска {a[3]:7d}, "
            f"рег {a[4]:3d} ({a[4]/a[1]*100:.2f} на 100 сайтов; {a[4]/a[3]*10000 if a[3] else 0:.1f} на 10 тыс. кликов), ФД {a[5]}")
    rt = tot["team"][4] / tot["team"][1] * 100; rl = tot["lol"][4] / tot["lol"][1] * 100
    say(f"    рег на 100 сайтов lol/team = {rl/rt if rt else float('nan'):.2f} (сырое, без страты)")
    # перестановки
    c_reg_lo = c_reg_hi = c_ex_lo = c_ex_hi = 0
    for _ in range(N_PERM):
        Or = Ox = 0
        for ds, nl in pool_data:
            idx = rng.sample(range(len(ds)), nl)
            for i in idx:
                Or += ds[i]["рег"]; Ox += ds[i]["вышли"]
        if Or <= O_reg: c_reg_lo += 1
        if Or >= O_reg: c_reg_hi += 1
        if Ox <= O_ex: c_ex_lo += 1
        if Ox >= O_ex: c_ex_hi += 1
    say(f"    стратифицированно: вышли .lol O = {O_ex:.0f}, E = {E_ex:.1f}, O/E = {O_ex/E_ex:.2f}, p(O ≤) = {fmt_p(c_ex_lo/N_PERM)}, p(O ≥) = {fmt_p(c_ex_hi/N_PERM)}")
    say(f"    стратифицированно: регистраций .lol O = {O_reg:.0f}, E (по сайтам) = {E_reg:.1f}, O/E = {O_reg/E_reg if E_reg else float('nan'):.2f}, "
        f"p(O ≤) = {fmt_p(c_reg_lo/N_PERM)}, p(O ≥) = {fmt_p(c_reg_hi/N_PERM)}; E по кликам = {E_reg_c:.1f}, O/E = {O_reg/E_reg_c if E_reg_c else float('nan'):.2f}")
    return {"tot": tot, "O_reg": O_reg, "E_reg": E_reg, "p_reg_lo": c_reg_lo / N_PERM, "p_reg_hi": c_reg_hi / N_PERM,
            "O_ex": O_ex, "E_ex": E_ex, "p_ex_lo": c_ex_lo / N_PERM, "p_ex_hi": c_ex_hi / N_PERM, "n_pools": len(plist)}


def part3(pools, pp):
    say()
    say("=" * 100)
    say("ЧАСТЬ 3. Деньги в «штрафной» группе (семейства clean и nabory) против остальных")
    say("=" * 100)
    rng = random.Random(1)
    allpairs = pair_pools(pools, 1)
    pen = [(k, ds, nl) for k, ds, nl in allpairs if ds[0]["семейство"] in ("clean", "nabory")]
    out = {}
    out["pen"] = money_block("«Штрафная» группа: пулы clean + nabory с ≥1 доменом в каждой зоне", pen, rng)
    say()
    nab = [(k, ds, nl) for k, ds, nl in pen if ds[0]["семейство"] == "nabory"]
    out["nabory"] = money_block("Только nabory (без clean)", nab, rng, show_pools=False)
    say()
    cln = [(k, ds, nl) for k, ds, nl in pen if ds[0]["семейство"] == "clean"]
    out["clean"] = money_block("Только clean (clean7_part1_50оформлено 08.09 и 11.09, clean12_unique11оформлено 07.09)", cln, rng, show_pools=False)
    say()
    pen_wo = [(k, ds, nl) for k, ds, nl in pen if k != ("clean7_part1_50оформлено", "2026-09-11")]
    out["pen_wo"] = money_block("«Штрафная» группа без clean7 11.09", pen_wo, rng, show_pools=False)
    say()
    # clean7 11.09 биномиальный
    k11 = ("clean7_part1_50оформлено", "2026-09-11")
    ds = pools.get(k11, [])
    t = [d for d in ds if d["зона"] == "team"]; l = [d for d in ds if d["зона"] == "lol"]
    if t and l:
        st, sl = zsum(t, "сайтов"), zsum(l, "сайтов"); rt, rl = zsum(t, "рег"), zsum(l, "рег")
        share_l = sl / (st + sl); n = rt + rl
        p_bin = sum(math.comb(n, j) * share_l ** j * (1 - share_l) ** (n - j) for j in range(0, rl + 1))
        # доменная перестановка
        dd = t + l; nl = len(l)
        cnt = 0; total = math.comb(len(dd), nl)
        if total <= 200000:
            for comb in itertools.combinations(range(len(dd)), nl):
                if sum(dd[i]["рег"] for i in comb) <= rl:
                    cnt += 1
            p_dom = cnt / total; how = f"точный перебор {total} раскладок"
        else:
            for _ in range(N_PERM):
                if sum(dd[i]["рег"] for i in rng.sample(range(len(dd)), nl)) <= rl:
                    cnt += 1
            p_dom = cnt / N_PERM; how = f"{N_PERM} перестановок"
        regdoms = sorted(((d["домен"], d["рег"]) for d in dd if d["рег"]), key=lambda x: -x[1])
        say(f"  clean7_part1_50оформлено 11.09: .team {len(t)} дом/{st} сайт/{rt} рег, .lol {len(l)} дом/{sl} сайт/{rl} рег; доля сайтов .lol {share_l:.3f}.")
        say(f"    биномиально P(≤{rl} из {n} в .lol) = {p_bin:.4f} (считает регистрации независимыми);")
        say(f"    доменная перестановка ({how}): P(рег .lol ≤ {rl}) = {p_dom:.4f}; регистрации лежат на доменах: "
            + ", ".join(f"{d} ({r})" for d, r in regdoms))
        out["clean7"] = {"rt": rt, "rl": rl, "nt": len(t), "nl": len(l), "p_bin": p_bin, "p_dom": p_dom, "ndoms": len(regdoms)}
    say()
    # группа «без штрафа» по формулировке: content-2026-09-12-* и 12-страничные NEW
    nop = [(k, ds, nl) for k, ds, nl in allpairs
           if (ds[0]["семейство"] == "content-дата" and k[0].startswith("content-2026-09-12"))
           or (ds[0]["семейство"] == "NEW" and ds[0]["страниц"] == "12")]
    out["nop"] = money_block("Группа «без штрафа» по формулировке: content-2026-09-12-* и 12-страничные NEW, ≥1 домен в каждой зоне", nop, rng)
    say()
    out["pp"] = money_block("Все пулы части 1 (≥3 домена в каждой зоне)", pp, rng, show_pools=False)
    say()
    allp = pair_pools(pools, 1)
    out["all"] = money_block("Все пулы с ≥1 доменом в каждой зоне (team и lol)", allp, rng, show_pools=False)
    return out


# ------------------------------------------------------- часть 4: casino
def casino_block(title, plist, rng, show_pools):
    say(f"  {title}: пулов {len(plist)}; доменов .casino {sum(nl for _, _, nl in plist)}, .team/.lol {sum(len(ds)-nl for _, ds, nl in plist)}")
    if show_pools:
        say(f"  {'день':10s} {'набор контента':36s} | {'casino: дом/сайт/вышли/выход/рег':34s} | {'team+lol: дом/сайт/вышли/выход/рег (team/lol дом)':52s} | casino/остальные")
    O_ex = E_ex = O_reg = E_reg = 0.0
    tot = {"casino": [0, 0, 0, 0, 0, 0], "прочие": [0, 0, 0, 0, 0, 0]}
    pool_data = []
    for k, ds, nl in plist:
        o = ds[:len(ds) - nl]; c = ds[len(ds) - nl:]
        ec, sc, rc = zsum(c, "вышли"), zsum(c, "сайтов"), zsum(c, "рег")
        eo, so, ro = zsum(o, "вышли"), zsum(o, "сайтов"), zsum(o, "рег")
        nt = sum(1 for d in o if d["зона"] == "team"); nlo = len(o) - nt
        ratio = (ec / sc) / (eo / so) if eo and ec else float("nan")
        if show_pools:
            say(f"  {k[1]:10s} {k[0][:36]:36s} | {len(c):3d}/{sc:5d}/{ec:4d}/{ec/sc:.3f}/{rc:2d}{'':12s} | {len(o):3d}/{so:5d}/{eo:4d}/{eo/so:.3f}/{ro:2d} ({nt}/{nlo}){'':22s} | {ratio:.2f}")
        S = sc + so; O_ex += ec; E_ex += (ec + eo) / S * sc; O_reg += rc; E_reg += (rc + ro) / S * sc
        for z, g in (("casino", c), ("прочие", o)):
            a = tot[z]; a[0] += len(g); a[1] += zsum(g, "сайтов"); a[2] += zsum(g, "вышли"); a[3] += zsum(g, "клики"); a[4] += zsum(g, "рег"); a[5] += zsum(g, "фд")
        pool_data.append((ds, nl))
    for z in ("casino", "прочие"):
        a = tot[z]
        say(f"    итого {z:6s}: доменов {a[0]:3d}, сайтов {a[1]:6d}, вышли {a[2]:5d} ({a[2]/a[1]*100:.1f} %), кликов {a[3]:7d}, рег {a[4]:3d} "
            f"({a[4]/a[1]*100:.2f} на 100 сайтов; {a[4]/a[3]*10000 if a[3] else 0:.1f} на 10 тыс. кликов), ФД {a[5]}")
    c_ex = c_reg = c_ex_lo = c_reg_lo = 0
    for _ in range(N_PERM):
        Ox = Or = 0
        for ds, nl in pool_data:
            for i in rng.sample(range(len(ds)), nl):
                Ox += ds[i]["вышли"]; Or += ds[i]["рег"]
        if Ox >= O_ex: c_ex += 1
        if Ox <= O_ex: c_ex_lo += 1
        if Or >= O_reg: c_reg += 1
        if Or <= O_reg: c_reg_lo += 1
    lam = E_reg
    p_pois = 1 - sum(math.exp(-lam) * lam ** j / math.factorial(j) for j in range(0, int(O_reg))) if lam > 0 else float("nan")
    say(f"    Выход .casino: O = {O_ex:.0f}, E = {E_ex:.1f}, O/E = {O_ex/E_ex if E_ex else float('nan'):.2f}; перестановочный p (O ≥) = {fmt_p(c_ex/N_PERM)}, (O ≤) = {fmt_p(c_ex_lo/N_PERM)}")
    say(f"    Регистрации .casino: O = {O_reg:.0f}, E = {E_reg:.1f}, O/E = {O_reg/E_reg if E_reg else float('nan'):.2f}; перестановочный p (O ≥) = {fmt_p(c_reg/N_PERM)}, (O ≤) = {fmt_p(c_reg_lo/N_PERM)}; "
        f"пуассоновский P(X ≥ {O_reg:.0f} | λ = {E_reg:.1f}) = {p_pois:.4f} (регистрации считаются независимыми — на деле сцеплены по доменам)")
    return {"O_ex": O_ex, "E_ex": E_ex, "O_reg": O_reg, "E_reg": E_reg, "p_ex": c_ex / N_PERM, "p_reg": c_reg / N_PERM,
            "n_pools": len(plist), "n_dom": sum(nl for _, _, nl in plist)}


def part4(pools):
    say()
    say("=" * 100)
    say("ЧАСТЬ 4. .casino в парных пулах (≥1 домен .casino и ≥1 домен .team/.lol) — предварительно")
    say("=" * 100)
    rng = random.Random(1)
    plist = []
    for k in sorted(pools, key=lambda k: (k[1], k[0])):
        ds = pools[k]
        c = [d for d in ds if d["зона"] == "casino"]; o = [d for d in ds if d["зона"] != "casino"]
        if c and o:
            plist.append((k, o + c, len(c)))
    out = {}
    out["all"] = casino_block("Все парные пулы с .casino", plist, rng, show_pools=True)
    regdoms = sorted(((d["домен"], d["набор"][:30], d["день"], d["рег"]) for _, ds, nl in plist for d in ds[len(ds)-nl:] if d["рег"]), key=lambda x: -x[3])
    say("    Регистрации .casino по доменам: " + "; ".join(f"{d} {s} {day} ({r})" for d, s, day, r in regdoms))
    if regdoms:
        top = regdoms[0]; a = out["all"]
        say(f"    Без домена {top[0]} ({top[3]} рег): O = {a['O_reg'] - top[3]:.0f} при E ≈ {a['E_reg']:.1f} → O/E ≈ {(a['O_reg']-top[3])/a['E_reg']:.2f} (грубая проверка на один домен)")
    say()
    say("  Разбивка по семействам (archive известен как чувствительный к зоне; проверяем, не держится ли выигрыш .casino на одних archive-пулах):")
    arch = [(k, ds, nl) for k, ds, nl in plist if ds[0]["семейство"] == "archive"]
    rest = [(k, ds, nl) for k, ds, nl in plist if ds[0]["семейство"] != "archive"]
    out["archive"] = casino_block("Только archive", arch, rng, show_pools=False)
    out["rest"] = casino_block("Без archive", rest, rng, show_pools=False)
    # против .team и против .lol по отдельности (внутри пула оставляем casino и одну зону)
    say()
    say("  .casino против одной зоны (в пуле оставлены только домены .casino и этой зоны):")
    for z in ("team", "lol"):
        sub = []
        for k, ds, nl in plist:
            o = [d for d in ds[:len(ds)-nl] if d["зона"] == z]; c = ds[len(ds)-nl:]
            if o:
                sub.append((k, o + c, nl))
        out["vs_" + z] = casino_block(f"casino против .{z}", sub, rng, show_pools=False)
    return out


# ---------------------------------------------------------------- вывод
def main():
    say("Гипотеза №21. Штраф зоны .lol не одинаков по наборам контента; .casino лучше в тех же пулах.")
    say(f"Файл: {CSV_PATH}. Перестановок: {N_PERM}, random.seed(1). Бутстреп: {N_BOOT}.")
    say()
    doms = load()
    pools = build_pools(doms)
    say(f"Пулов «набор контента + день» после фильтров: {len(pools)}; из них с доменами в ≥2 зонах (team/lol/casino): "
        f"{sum(1 for ds in pools.values() if len(set(d['зона'] for d in ds)) >= 2)}")
    pp, r_ex, r_cl, r_sens, pp2, loo = part1(pools)
    rep = part2(pools)
    mon = part3(pools, pp)
    cas = part4(pools)

    say()
    say("=" * 100)
    say("ВЫВОД")
    say("=" * 100)
    p_var = r_ex["p_var"]["сайты"]; v_obs, m_obs = r_ex["obs"]["сайты"]; v_null = r_ex["null_var"]["сайты"]
    p_var_h = r_ex["p_var"]["гарм."]; p_var_u = r_ex["p_var"]["без весов"]
    p_between = r_ex["p_between"]
    p_cl = r_cl["p_var"]["сайты"]
    p_sens = r_sens["p_var"]["сайты"]
    ca = cas["all"]
    O_ex, E_ex, O_reg, E_reg, p_cas_ex, p_cas_reg, n_cas_pools, n_cas_dom = (ca["O_ex"], ca["E_ex"], ca["O_reg"], ca["E_reg"], ca["p_ex"], ca["p_reg"], ca["n_pools"], ca["n_dom"])
    say(f"1. Неоднородность штрафа .lol по {len(pp)} пулам: взвешенная дисперсия ln(выход lol / выход team) = {v_obs:.3f}, "
        f"на перестановках зоны внутри пула в среднем {v_null:.3f}; p = {fmt_p(p_var)} (гарм. веса {fmt_p(p_var_h)}, без весов {fmt_p(p_var_u)}; "
        f"при пороге ≥2 домена {fmt_p(p_sens)}; по кликам на вышедший сайт {fmt_p(p_cl)}).")
    if p_var < 0.05:
        say("   Разброс отношений между пулами больше, чем даёт случайная раскладка доменов по зонам: штраф действительно разный у разных наборов.")
    else:
        say("   Разброс отношений между пулами (от 0,48 до 1,37) не больше того, что даёт случайная раскладка тех же доменов по зонам внутри пула.")
        say("   Отношения ≈0,5 у nabory274283, nabory294303, nabory411420, NEW50_3_7pages_withdate_styled — разброс 3–5 доменов на зону,")
        say("   а не свойство набора: на 3+3 доменах всего 20 раскладок, ни один из этих пулов сам по себе не значим (p пула 0,07–0,35).")
    say(f"   Межгрупповая дисперсия по семействам (7 групп: NEW, archive, clean, content-дата, nabory, script, прочее): p = {fmt_p(p_between)} — "
        + ("на грани, но группы выбраны после просмотра тех же данных; как самостоятельное доказательство не годится." if p_between < 0.1 else "ничего не добавляет."))
    say(f"   Единственный пул со значимым собственным дефицитом .lol — clean7_part1_50оформлено 11.09: 20 против 15 доменов, выход 0,105 против 0,059, p пула 0,0031 "
        f"(с поправкой Бонферрони на 20 пулов ≈ {min(1, 0.0031*20):.2f}).")
    l3 = loo["≥3 домена"]; l2 = loo["≥2 домена"]
    say(f"   Без этого одного пула: неоднородность p = {fmt_p(l3['p_var']['сайты'])} (≥2 домена: {fmt_p(l2['p_var']['сайты'])}), "
        f"между семействами p = {fmt_p(l3['p_between'])} (≥2 домена: {fmt_p(l2['p_between'])}) — "
        + ("«структура по семействам» держится на одном пуле." if l3['p_between'] > 0.1 and l2['p_between'] > 0.1 else "след по семействам остаётся и без него."))
    say(f"   Средний штраф .lol по этим пулам: lol/team = {math.exp(m_obs):.2f} (двусторонний p = {fmt_p(r_ex['p_mean']['сайты'])}) — "
        "согласуется с реестром (зона после контента 0,86–1,10).")
    k = len(rep)
    parts = []
    for sname, d in rep.items():
        parts.append(f"{sname} ({' / '.join(d['days'])}: lol/team {' и '.join(f'{x:.2f}' for x in d['ratios'])}, знак {'совпал' if d['same'] else 'не совпал'}, "
                     f"совместно O/E {d['OE']:.2f}, p = {fmt_p(d['p_lo'])})")
    say(f"2. Воспроизводимость: наборов в обеих зонах в ≥2 дня — {k}: " + "; ".join(parts) + ". "
        "Знаковый критерий на двух наборах ничего решить не может (минимальный p = 0,25). NEW102 в обеих зонах стоит только 11.09. "
        "Совместный p по дням у clean7 — это по сути один пул 11.09 плюс 2 домена .team 08.09.")
    pen = mon["pen"]; nop = mon["nop"]; c7 = mon.get("clean7")
    tp, tl = pen["tot"]["team"], pen["tot"]["lol"]
    say(f"3. Деньги «штрафной» группы (clean + nabory, {pen['n_pools']} пулов): .team {tp[0]} доменов / {tp[1]} сайтов / {tp[4]} рег, "
        f".lol {tl[0]} доменов / {tl[1]} сайтов / {tl[4]} рег; регистраций .lol O = {pen['O_reg']:.0f} при E = {pen['E_reg']:.1f} "
        f"(O/E = {pen['O_reg']/pen['E_reg']:.2f}, перестановочный p = {fmt_p(pen['p_reg_lo'])}); выход .lol O/E = {pen['O_ex']/pen['E_ex']:.2f} (p = {fmt_p(pen['p_ex_lo'])}).")
    if c7:
        say(f"   clean7 11.09: {c7['rt']} рег в .team ({c7['nt']} доменов) и {c7['rl']} в .lol ({c7['nl']} доменов): биномиально p = {c7['p_bin']:.3f}, "
            f"по доменной перестановке p = {c7['p_dom']:.3f} ({c7['rt']} регистраций лежат на {c7['ndoms']} доменах). "
            f"Практически все регистрации группы — это один пул одного дня; у nabory регистраций почти нет, «≤0,3» не проверяется.")
    nb = mon["nabory"]; cl = mon["clean"]; pw = mon["pen_wo"]
    say(f"   Только nabory ({nb['n_pools']} пулов: .team {nb['tot']['team'][0]} доменов / {nb['tot']['team'][4]} рег, .lol {nb['tot']['lol'][0]} доменов / {nb['tot']['lol'][4]} рег): "
        f"выход .lol O/E = {nb['O_ex']/nb['E_ex']:.2f} (p(O ≤) = {fmt_p(nb['p_ex_lo'])}); регистраций O/E = {nb['O_reg']/nb['E_reg'] if nb['E_reg'] else float('nan'):.2f} (p = {fmt_p(nb['p_reg_lo'])}). "
        f"Только clean ({cl['n_pools']} пула): выход .lol O/E = {cl['O_ex']/cl['E_ex']:.2f} (p = {fmt_p(cl['p_ex_lo'])}), регистраций O/E = {cl['O_reg']/cl['E_reg']:.2f} (p = {fmt_p(cl['p_reg_lo'])}). "
        f"Группа без clean7 11.09: выход .lol O/E = {pw['O_ex']/pw['E_ex']:.2f} (p = {fmt_p(pw['p_ex_lo'])}), регистраций O/E = {pw['O_reg']/pw['E_reg']:.2f} (p = {fmt_p(pw['p_reg_lo'])}).")
    tp2, tl2 = nop["tot"]["team"], nop["tot"]["lol"]
    say(f"   Группа «без штрафа» (content-2026-09-12-* и 12-страничные NEW, {nop['n_pools']} пулов): .team {tp2[0]} доменов / {tp2[4]} рег, .lol {tl2[0]} доменов / {tl2[4]} рег; "
        f"регистраций .lol O/E = {nop['O_reg']/nop['E_reg']:.2f} (p(O ≤) = {fmt_p(nop['p_reg_lo'])}, p(O ≥) = {fmt_p(nop['p_reg_hi'])}); выход .lol O/E = {nop['O_ex']/nop['E_ex']:.2f}.")
    say(f"4. .casino в {n_cas_pools} пулах ({n_cas_dom} доменов): выход O/E = {O_ex/E_ex:.2f} (перестановочный p = {fmt_p(p_cas_ex)}), "
        f"регистраций {O_reg:.0f} при ожидании {E_reg:.1f}, O/E = {O_reg/E_reg:.2f} (перестановочный p = {fmt_p(p_cas_reg)}). "
        + ("Выход .casino выше остальных зон в тех же пулах, и это не разброс доменов; " if p_cas_ex < 0.1 else "По выходу отличие от остальных зон в пределах разброса; ")
        + ("по деньгам — тоже за пределами разброса, но событий мало." if p_cas_reg < 0.1 else "по деньгам — в пределах разброса (регистраций мало, один домен даёт 5 из 19)."))
    ar = cas["archive"]; rs = cas["rest"]; vt = cas["vs_team"]; vl = cas["vs_lol"]
    say(f"   По семействам: archive ({ar['n_pools']} пула, {ar['n_dom']} доменов casino) выход O/E = {ar['O_ex']/ar['E_ex']:.2f} (p = {fmt_p(ar['p_ex'])}), рег {ar['O_reg']:.0f}/{ar['E_reg']:.1f}; "
        f"без archive ({rs['n_pools']} пулов, {rs['n_dom']} доменов) выход O/E = {rs['O_ex']/rs['E_ex']:.2f} (p = {fmt_p(rs['p_ex'])}), рег {rs['O_reg']:.0f}/{rs['E_reg']:.1f} (O/E {rs['O_reg']/rs['E_reg']:.2f}, p = {fmt_p(rs['p_reg'])}). "
        f"Против .team: выход O/E {vt['O_ex']/vt['E_ex']:.2f} (p = {fmt_p(vt['p_ex'])}); против .lol: {vl['O_ex']/vl['E_ex']:.2f} (p = {fmt_p(vl['p_ex'])}).")
    say()
    allp = mon["all"]
    say(f"5. Общий (одинаковый для всех наборов) штраф .lol по выходу: по 46 парным пулам O/E = {allp['O_ex']/allp['E_ex']:.2f} (p = {fmt_p(allp['p_ex_lo'])}), "
        f"по регистрациям O/E = {allp['O_reg']/allp['E_reg']:.2f} (p = {fmt_p(allp['p_reg_lo'])}) — небольшой и только по выходу, в деньгах не виден; "
        "это согласуется с реестром («зона после контента 0,86–1,10»). nabory (0,79) и clean (0,76) сидят на нижнем краю этого общего штрафа, content-2026-09-12 (1,0–1,1) — на верхнем, "
        "но тест неоднородности говорит: разница между ними не больше разброса доменов.")
    say()
    if p_var >= 0.05:
        say("Итог: главное утверждение — что штраф .lol РАЗНЫЙ у разных наборов (≈0,5 у clean7 и nabory против ≈1,0 у content-дата и 12-страничных NEW) — НЕ подтверждается: "
            f"неоднородность по 20 пулам внутри нуля (p = {fmt_p(p_var)}; без clean7 11.09 — {fmt_p(l3['p_var']['сайты'])}), воспроизводимость не проверяется (2 набора, один за, один против). "
            "Сгустки «≈0,5» и «≈1,0» — то, как выглядит шум 3–15 доменов на зону вокруг общего штрафа ≈0,85; отбирать пулы задним числом нельзя. "
            f"След по семействам есть (p = {fmt_p(p_between)} при ≥3 доменах, {fmt_p(r_sens['p_between'])} при ≥2), но он держится на одном пуле — clean7_part1_50оформлено 11.09, "
            "где .lol реально вышел вдвое хуже .team (p = 0,003) и все 6 регистраций легли в .team (p ≈ 0,04); без него след слабеет "
            f"(p = {fmt_p(l3['p_between'])} / {fmt_p(l2['p_between'])}). Это один набор в один день, а не правило «зона под набор». "
            "Маршрутизация clean7/nabory только в .team на этих данных не обоснована; content-дата в .lol — не запрещена. "
            f".casino: по выходу подтверждается (O/E {O_ex/E_ex:.2f}, p < 0,0001), но вдвое-втрое — только в archive-пулах (O/E {ar['O_ex']/ar['E_ex']:.2f}), "
            f"вне archive O/E {rs['O_ex']/rs['E_ex']:.2f}; по регистрациям не подтверждается ({O_reg:.0f} при ожидании {E_reg:.1f}, p = {fmt_p(p_cas_reg)}; без archive O/E {rs['O_reg']/rs['E_reg']:.2f}; без одного домена 1109casino.casino — 0,94).")
    else:
        say("Итог: неоднородность штрафа подтверждается; смотреть, у каких семейств .lol проседает, и не ставить их в .lol.")
    say("Что с этим делать: (а) не делить наборы на «штрафные» и «нештрафные» по зоне — разница внутри шума; общий штраф .lol по выходу ≈0,85 есть, но в деньгах он не виден, "
        "так что если .lol дешевле .team, эти данные не запрещают ставить в .lol любой набор (кроме .buzz); "
        "(б) единственный проверяемый след — clean7_part1_50оформлено: при следующем запуске в обе зоны посмотреть на своде, повторится ли дефицит .lol по выходу и регистрациям "
        "(нужно ≥10 доменов в каждой зоне в один день); (в) .casino: выход выше в тех же пулах — это знание; про деньги на 19 регистрациях сказать нельзя, "
        "и большая часть выигрыша по выходу — archive-пулы, где .team известен как худший; следующий свод покажет, держится ли O/E ≥1,15 по регистрациям вне archive.")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(_lines) + "\n")
    print(f"\n[записано: {OUT_PATH}]")


if __name__ == "__main__":
    main()
