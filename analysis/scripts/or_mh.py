#!/usr/bin/env python3
"""Odds ratio по одиночному срезу: сырой и объединённый по Мантелю-Хенцелю.

Дизайн — случай-контроль (правило 1 мануала): случаи — сабдомены с конверсией,
фон — остальные с закрытым окном. Объединение страт — Мантель-Хенцель
(правило 2): около одной конверсии на бренд в неделю, поэтому логистическая
регрессия с дамми по 206 брендам смещена.

Страта по умолчанию — бренд. Вторая страта, `launch_day`, закрывает правило 9:
возраст — главный конфаундер, и сравнивать надо запущенное вместе.

Внешних зависимостей нет: math.comb и statistics.NormalDist, как велит мануал.
"""
import sys, json, math, collections
from statistics import NormalDist

N = NormalDist()


def mh(tbl):
    """tbl: список страт (a, b, c, d) — случаи/фон × есть признак/нет.

    Возвращает MH OR, 95% ДИ по Robins-Breslow-Greenland и p МН-хи-квадрат.
    """
    num = den = 0.0
    s_p = s_r = s_q = s_s = s_pr = s_qs = 0.0
    e = v = obs = 0.0
    for a, b, c, d in tbl:
        n = a + b + c + d
        if n == 0:
            continue
        r = a * d / n
        s = b * c / n
        num += r
        den += s
        p = (a + d) / n
        q = (b + c) / n
        s_p += p * r; s_r += r; s_q += q * s; s_s += s
        s_pr += p * s + q * r
        obs += a
        e += (a + b) * (a + c) / n
        if n > 1:
            v += (a + b) * (c + d) * (a + c) * (b + d) / (n * n * (n - 1))
    if den == 0 or num == 0:
        return None, None, None, None
    orv = num / den
    # RBG-дисперсия логарифма
    var = s_p / (2 * s_r ** 2) + s_pr / (2 * s_r * s_s) + s_q / (2 * s_s ** 2)
    lo = orv * math.exp(-1.96 * math.sqrt(var))
    hi = orv * math.exp(1.96 * math.sqrt(var))
    chi = (abs(obs - e) - 0.5) ** 2 / v if v > 0 else 0.0
    p = 2 * (1 - N.cdf(math.sqrt(chi))) if chi > 0 else 1.0
    return orv, lo, hi, p


def crude(a, b, c, d):
    if 0 in (b, c):
        return None, None, None
    orv = (a * d) / (b * c)
    if 0 in (a, d):
        return orv, None, None
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    return orv, orv * math.exp(-1.96 * se), orv * math.exp(1.96 * se)


def cut(rows, field, value, strata):
    """Разрез: признак = (field == value). Возвращает 2x2 и по набору страт."""
    A = B = C = D = 0
    by = [collections.defaultdict(lambda: [0, 0, 0, 0]) for _ in strata]
    for r in rows:
        has = r.get(field) == value
        case = r['case']
        i = 0 if (case and has) else 1 if (case and not has) else 2 if (not case and has) else 3
        if i == 0: A += 1
        elif i == 1: B += 1
        elif i == 2: C += 1
        else: D += 1
        for k, sf in enumerate(strata):
            by[k][tuple(r.get(x) for x in sf)][i] += 1
    return (A, B, C, D), [list(map(tuple, d.values())) for d in by]


def fmt(orv, lo, hi, p=None):
    if orv is None:
        return "—"
    s = f"{orv:.2f}"
    if lo:
        s += f" [{lo:.2f}–{hi:.2f}]"
    if p is not None:
        s += f" p={p:.2g}"
    return s


DEFAULT_STRATA = (('brand_id',), ('launch_day',))


def report(rows, field, strata=DEFAULT_STRATA, top=12, min_cases=3):
    vals = collections.Counter(r.get(field) for r in rows if r.get(field) is not None)
    cases = collections.Counter(r.get(field) for r in rows if r['case'])
    print(f"\n{'='*78}\nСРЕЗ: {field}   (случаев {sum(1 for r in rows if r['case'])} "
          f"из {len(rows)} сабдоменов с закрытым окном)")
    head = f"{'значение':<40}{'саб':>8}{'случ':>6}   {'сырой OR':<22}"
    for sf in strata:
        head += f"{'MH: ' + '+'.join(sf):<26}"
    print(head)
    for v, n in vals.most_common(top):
        if cases[v] < min_cases:
            continue
        (A, B, C, D), by = cut(rows, field, v, strata)
        line = f"{str(v)[:38]:<40}{n:>8}{cases[v]:>6}   {fmt(*crude(A, B, C, D)):<22}"
        for tb in by:
            line += f"{fmt(*mh(tb)):<26}"
        print(line)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit("or_mh.py <панель.jsonl> <поле> [<поле> …]")
    rows = [json.loads(l) for l in open(sys.argv[1], encoding='utf-8')]
    rows = [r for r in rows if r.get('window_closed')]
    for f in sys.argv[2:]:
        # синтаксис «поле@страта1+страта2» задаёт свои страты вместо умолчания
        if '@' in f:
            f, st = f.split('@', 1)
            report(rows, f, strata=tuple((x,) for x in st.split(',')) if ',' in st
                   else (tuple(st.split('+')),))
        else:
            report(rows, f)
