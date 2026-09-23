#!/usr/bin/env python3
"""Факторы не в среднем, а внутри каждого набора контента отдельно.

Для каждого набора (корень имени, от 10 доменов, окно закрыто) сравниваются
группы признака: индекс за трое суток и регистрации на сто сайтов. Затем по
наборам считается знаковый счёт — в скольких наборах группа A выше группы B.
Так видно, общий это эффект или его создают два-три набора.

    python3 faktory_po_naboram.py <свод.csv> <out.txt>
"""
import sys, csv, re, math, collections

svod_p, out_p = sys.argv[1], sys.argv[2]
I = lambda r, k: int(r[k]) if r[k] not in ('', 'None') else 0
root = lambda n: re.sub(r'_\d+$', '', n)

R = [r for r in csv.DictReader(open(svod_p, encoding='utf-8'))
     if r['окно закрыто'] == 'да' and I(r, 'сайтов в окне') > 0
     and r['набор контента'] != 'КОНТЕНТ НЕ ЗАПИСАН']
for r in R:
    r['_set'] = root(r['набор контента'])

def binom(k, n):
    if not n: return 1.0
    return min(1.0, 2 * sum(math.comb(n, x) for x in range(k, n + 1)) / 2 ** n)

FACTORS = [
    ('ЧАС: день (06–17) против вечера и ночи (18–05)',
     lambda r: 'день' if r['блок часа'] in ('06-11', '12-17') else 'вечер/ночь', 'день', 'вечер/ночь'),
    ('АККАУНТ: первый раз против повторного',
     lambda r: 'первый' if r['который раз аккаунт'] == '1' else 'повторный', 'первый', 'повторный'),
    ('ДЛИНА МЕТКИ: 3 символа против остальных',
     lambda r: '3 символа' if r['длина метки'] == '3' else 'длиннее', '3 символа', 'длиннее'),
    ('ИМЯ: цифровое против буквенного',
     lambda r: 'цифровое' if r['паттерн имени'] == 'numeric' else ('буквенное' if r['паттерн имени'] == 'alpha_other' else 'прочее'),
     'цифровое', 'буквенное'),
    ('ИМЯ: цифровое против casino-приставки',
     lambda r: 'цифровое' if r['паттерн имени'] == 'numeric' else ('casino' if r['паттерн имени'] in ('casino_prefix', 'casino_infix') else 'прочее'),
     'цифровое', 'casino'),
]

L = []
P = L.append
sets = collections.defaultdict(list)
for r in R:
    sets[r['_set']].append(r)
big = {k: v for k, v in sets.items() if len(v) >= 10}
P(f'наборов от 10 доменов: {len(big)}; доменов в них {sum(len(v) for v in big.values())}')
P('В каждом наборе сравниваются только те домены, что стоят в нём же. Знаковый счёт — по наборам.')

for title, key, A, B in FACTORS:
    P(''); P('=' * 96); P(title)
    rows = []
    for name, v in sorted(big.items()):
        ga = [r for r in v if key(r) == A]
        gb = [r for r in v if key(r) == B]
        if len(ga) < 3 or len(gb) < 3:
            continue
        f = lambda g, m: sum(I(r, m) for r in g)
        sa, sb = f(ga, 'сайтов в окне'), f(gb, 'сайтов в окне')
        ia, ib = 100 * f(ga, 'вышли за 3 суток') / sa, 100 * f(gb, 'вышли за 3 суток') / sb
        ra, rb = f(ga, 'регистраций в окне 3 суток'), f(gb, 'регистраций в окне 3 суток')
        rows.append((name, len(ga), len(gb), ia, ib, ra, rb, sa, sb))
    if not rows:
        P('   наборов, где обе группы есть хотя бы по 3 домена, нет'); continue
    P(f'   наборов с обеими группами: {len(rows)}')
    P(f'   {"набор":<40}{"дом A/B":>10}{"индекс A":>10}{"индекс B":>10}{"A/B":>7}{"рег A/B":>10}{"рег/100 A":>11}{"рег/100 B":>11}')
    for n, na, nb, ia, ib, ra, rb, sa, sb in sorted(rows, key=lambda x: -(x[3] / max(x[4], 1e-9))):
        P(f'   {n[:39]:<40}{f"{na}/{nb}":>10}{ia:>9.1f}%{ib:>9.1f}%{ia/max(ib,1e-9):>7.2f}'
          f'{f"{ra}/{rb}":>10}{100*ra/sa:>11.3f}{100*rb/sb:>11.3f}')
    wa = sum(1 for x in rows if x[3] > x[4]); wb = sum(1 for x in rows if x[4] > x[3])
    P(f'   ИНДЕКС: «{A}» выше в {wa} наборах, «{B}» в {wb} — знаковый p = {binom(max(wa,wb), wa+wb):.3f}')
    SA = sum(x[7] for x in rows); SB = sum(x[8] for x in rows)
    IA = sum(x[3] * x[7] for x in rows) / SA; IB = sum(x[4] * x[8] for x in rows) / SB
    P(f'   ИНДЕКС суммарно: {A} {IA:.1f}% против {B} {IB:.1f}% — отношение {IA/max(IB,1e-9):.2f}')
    ma = sum(1 for x in rows if x[5] / x[7] > x[6] / x[8]); mb = sum(1 for x in rows if x[6] / x[8] > x[5] / x[7])
    RA = sum(x[5] for x in rows); RB = sum(x[6] for x in rows)
    P(f'   ДЕНЬГИ: «{A}» выше в {ma} наборах, «{B}» в {mb}, поровну (обычно нули) в {len(rows)-ma-mb}'
      f' — знаковый p = {binom(max(ma,mb), ma+mb):.3f}')
    P(f'   ДЕНЬГИ суммарно: {A} {RA} рег на {SA} сайтов ({100*RA/SA:.3f} на 100) против '
      f'{B} {RB} на {SB} ({100*RB/SB:.3f}) — отношение {(RA/SA)/max(RB/SB,1e-12):.2f}')
open(out_p, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
