#!/usr/bin/env python3
"""Пары признаков: OR каждого сочетания против «ни того, ни другого».

Мануал разрешает пары только среди сработавших одиночных срезов и требует для
пары эффекта покрупнее: при OR 1.5 нужно ~495 конверсий, при OR 2.0 — 144.
Поэтому пары считаются и на исходе «попал в выдачу», где событий на два порядка
больше, и на конверсии.

    python3 pairs.py <панель.jsonl>
"""
import json, math, collections, sys
from statistics import NormalDist

FEAT = {
    '12 страниц':     lambda r: r.get('pages_grp') == '12 страниц',
    'зона casino':    lambda r: r.get('tld') == 'casino',
    'имя numeric':    lambda r: r.get('base_name_pattern') == 'numeric',
    'префикс casino': lambda r: r.get('base_name_pattern') == 'casino_prefix',
}


def orv(a, b, c, d):
    if 0 in (a, b, c, d):
        return None
    o = (a * d) / (b * c)
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    p = 2 * (1 - NormalDist().cdf(abs(math.log(o) / se)))
    return o, o * math.exp(-1.96 * se), o * math.exp(1.96 * se), p


def run(rows, case_fn, title):
    n = sum(1 for r in rows if case_fn(r))
    print(f"\n{'='*86}\n{title} — {n} событий")
    names = list(FEAT)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            A, B = names[i], names[j]
            fa, fb = FEAT[A], FEAT[B]
            cell = collections.defaultdict(lambda: [0, 0])
            for r in rows:
                cell[(fa(r), fb(r))][0 if case_fn(r) else 1] += 1
            base = cell[(False, False)]
            print(f"\n  {A} × {B}   (эталон: ни того, ни другого — {base[0]} из {sum(base)})")
            for k, lbl in (((True, False), f'только {A}'), ((False, True), f'только {B}'),
                           ((True, True), 'оба')):
                c = cell[k]
                if sum(c) == 0:
                    print(f"    {lbl:<28} — сочетания нет")
                    continue
                res = orv(c[0], base[0], c[1], base[1])
                s = (f"{res[0]:.2f} [{res[1]:.2f}–{res[2]:.2f}] p={res[3]:.2g}"
                     if res else "событий мало")
                print(f"    {lbl:<28} {c[0]:>5} из {sum(c):>7}   OR {s}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    rows = [json.loads(l) for l in open(sys.argv[1], encoding='utf-8') if l.strip()]
    rows = [r for r in rows if r.get('window_closed')]
    run(rows, lambda r: bool(r.get('ya_clicks', 0)), "ПАРЫ, исход: попал в выдачу")
    run(rows, lambda r: r['case'], "ПАРЫ, исход: конверсия")
