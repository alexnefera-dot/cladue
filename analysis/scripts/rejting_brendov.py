#!/usr/bin/env python3
"""Рейтинг брендов — самый чистый эксперимент, который в сети уже идёт.

Каждая база несёт **все 206 брендов**. Значит сравнение брендов между собой
сбалансировано по базе, дню, зоне, аккаунту, IP, шаблону и контенту **по
построению**, а не поправками. Это ровно та рандомизация внутри домена, которую
методика называет главным рычагом, — и она уже существует, её не надо заводить.

Страта — база. Исход — сабдомен получил клик из поиска.

Почему это важнее всех прежних разрезов: контент даёт разброс в 18 раз, зона в
1.7, «12 страниц» 1.88 — а бренд в тысячи. Всё остальное считалось поверх
фактора, который сильнее их всех и ни разу не был измерен.

    python3 rejting_brendov.py <панель.jsonl> [квота_в_сутки]
"""
import sys, json, collections

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from or_mh import mh


def main(panel, quota='150'):
    quota = int(quota)
    rows = []
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        b, d = r.get('brand_label'), r.get('content_domain_id')
        if not b or d is None:
            continue
        rows.append((b, d, 1 if r.get('ya_clicks') else 0,
                     r.get('ya_clicks') or 0, r.get('reg', 0) + r.get('fd', 0)))

    byd = collections.defaultdict(lambda: [0, 0])
    for b, d, y, cl, cv in rows:
        t = byd[d]
        t[0] += y
        t[1] += 1 - y

    agg = collections.defaultdict(lambda: [0, 0, 0, 0])   # вышли, всего, кликов, конверсий
    for b, d, y, cl, cv in rows:
        t = agg[b]
        t[0] += y
        t[1] += 1
        t[2] += cl
        t[3] += cv

    out = []
    for brand in agg:
        tbl = collections.defaultdict(lambda: [0, 0, 0, 0])
        for b, d, y, cl, cv in rows:
            if b != brand:
                continue
            c = tbl[d]
            c[0] += y
            c[2] += 1 - y
            c[1] += byd[d][0] - y
            c[3] += byd[d][1] - (1 - y)
        orv, lo, hi, p = mh([tuple(v) for v in tbl.values()])
        if orv is not None:
            out.append((orv, lo, hi, brand, agg[brand]))
    out.sort(key=lambda x: -x[0])

    print(f'брендов {len(out)}, сабдоменов {len(rows)}')
    print('страта — база; каждая база несёт весь набор брендов\n')
    print(f"{'бренд':<24}{'сабдом.':>9}{'вышли':>8}{'кликов':>9}"
          f"{'OR к остальным':>24}{'конв':>6}")
    for i, (orv, lo, hi, b, s) in enumerate(out):
        if i == 15:
            print(f"{'…':<24}{'':>9}{'':>8}{'':>9}{'':>24}")
        if 15 <= i < len(out) - 10:
            continue
        print(f'{b[:23]:<24}{s[1]:>9}{100.0*s[0]/s[1]:>7.1f}%{s[2]:>9}'
              f'{f"{orv:.2f} [{lo:.2f}–{hi:.2f}]":>24}{s[3]:>6}')

    tot_out = sum(s[0] for _, _, _, _, s in out)
    tot_cl = sum(s[2] for _, _, _, _, s in out)
    tot_cv = sum(s[3] for _, _, _, _, s in out)
    print(f'\n{"верхние N":<12}{"доля выходов":>14}{"доля кликов":>13}{"доля конверсий":>16}')
    for n in (10, 25, 50, 75, 100, 150, len(out)):
        s = out[:n]
        print(f'{n:<12}{100.0*sum(x[4][0] for x in s)/tot_out:>13.1f}%'
              f'{100.0*sum(x[4][2] for x in s)/tot_cl:>12.1f}%'
              f'{100.0*sum(x[4][3] for x in s)/max(tot_cv,1):>15.1f}%')

    tail = out[quota:]
    if tail:
        print(f'\nБРЕНДЫ ЗА ПРЕДЕЛАМИ СУТОЧНОЙ КВОТЫ ({quota} URL в сутки на аккаунт)')
        print('квота — дефицитный ресурс, и она делится между брендами поровну,')
        print('хотя отдача у них различается на три порядка')
        print(f'  брендов в хвосте: {len(tail)}')
        print(f'  сабдоменов на них: {sum(x[4][1] for x in tail)} '
              f'({100.0*sum(x[4][1] for x in tail)/len(rows):.0f}% всей квоты)')
        print(f'  выходов в поиск: {sum(x[4][0] for x in tail)} '
              f'({100.0*sum(x[4][0] for x in tail)/tot_out:.1f}% всех)')
        print(f'  конверсий: {sum(x[4][3] for x in tail)} из {tot_cv}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(*sys.argv[1:3])
