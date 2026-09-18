#!/usr/bin/env python3
"""Раскладка конверсий по контенту: сколько регистраций и ФД дал каждый пак.

Единица — база: пак назначается домену целиком, поэтому «баз» — честный
знаменатель, а «сабдоменов» показывает вес базы (обычно 206 брендов).

Имя пака известно у 80% сабдоменов: `content_label` API отдаёт пустым почти
везде, и имя берётся из заголовков реестра запусков `analysis/launch_*.txt`.
Остальные 20% — базы, которых в реестре запусков нет; они идут отдельной
строкой «пак неизвестен», а не растворяются в среднем.

    python3 kontenty_fd.py <панель.jsonl> [<от YYYY-MM-DD>]
"""
import sys, json, math, collections
from datetime import date, timedelta
from statistics import NormalDist

N = NormalDist()


def poisson_upper(k, n):
    """Верхняя граница 95% для частоты событий на базу.

    Считается как пуассоновская, а не биномиальная: на одной базе бывает
    несколько ФД, и доля тут не годится. Ищется такое λ, при котором вероятность
    увидеть k или меньше равна 0.025.
    """
    if not n:
        return 0.0

    def cdf(lam):
        s = t = math.exp(-lam)
        for i in range(1, k + 1):
            t *= lam / i
            s += t
        return s

    lo, hi = 0.0, max(k * 3.0, 10.0)
    while cdf(hi) > 0.025:
        hi *= 2
    for _ in range(80):
        mid = (lo + hi) / 2
        if cdf(mid) > 0.025:
            lo = mid
        else:
            hi = mid
    return hi / n


def family(name):
    """Семейство пака: всё до номера партии и до описания страниц."""
    if not name:
        return 'пак неизвестен'
    for f in ('NEW50_3', 'NEW50_2', 'NEW50_5', 'NEW50', 'NEW33', 'NEW20_4', 'NEW20_3',
              'NEW20', 'NEW102', 'Content_script', 'script_yandex', 'clean', 'archive',
              'content-2026', 'nabor', 'КОНТРОЛЬ'):
        if name.startswith(f) or name.startswith('КОНТРОЛЬ ' + f):
            return f
    return name.split('_')[0][:18]


def pages(name):
    if not name:
        return '?'
    n = name.lower()
    if '12page' in n or '12стр' in n or '12str' in n:
        return '12'
    if '11page' in n:
        return '11'
    if '7page' in n or '7str' in n or '7стр' in n:
        return '7'
    return '?'


def mh_rate(strata):
    """МН-отношение частот со стратой: [(событий1, баз1, событий0, баз0), …].

    Частота, а не доля: на одной базе бывает несколько конверсий. Дисперсия —
    стандартная для МН-отношения частот, база играет роль единицы экспозиции.
    """
    num = den = v = 0.0
    for a, n1, b, n0 in strata:
        N = n1 + n0
        if not N:
            continue
        num += a * n0 / N
        den += b * n1 / N
        v += (a + b) * n1 * n0 / N ** 2
    if not num or not den:
        return None, None, None
    rr = num / den
    se = math.sqrt(v / (num * den))
    return rr, rr * math.exp(-1.96 * se), rr * math.exp(1.96 * se)


def main(panel, since=None):
    bases = {}
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        if since and (r.get('recrawl_sent_at') or '')[:10] < since:
            continue
        b = r.get('content_domain_url')
        if not b:
            continue
        a = bases.setdefault(b, {'content': r.get('content'), 'tld': r.get('tld'),
                                 'rec': None, 'subs': 0, 'reg': 0, 'fd': 0})
        t = (r.get('recrawl_sent_at') or '')[:10]
        if t and (a['rec'] is None or t < a['rec']):
            a['rec'] = t
        a['subs'] += 1
        a['reg'] += r.get('reg', 0)
        a['fd'] += r.get('fd', 0)

    print(f'баз в расчёте: {len(bases)}'
          + (f', отбор: переобход с {since}' if since else ', вся история реестра'))
    tot_reg = sum(a['reg'] for a in bases.values())
    tot_fd = sum(a['fd'] for a in bases.values())
    print(f'регистраций {tot_reg}, ФД {tot_fd}\n')

    for level, keyf in (('ПО ПАКАМ', lambda a: a['content'] or 'пак неизвестен'),
                        ('ПО СЕМЕЙСТВАМ', lambda a: family(a['content'])),
                        ('ПО ЧИСЛУ СТРАНИЦ В ИМЕНИ', lambda a: pages(a['content']))):
        g = collections.defaultdict(lambda: {'baz': 0, 'subs': 0, 'reg': 0, 'fd': 0})
        for a in bases.values():
            c = g[keyf(a)]
            c['baz'] += 1
            c['subs'] += a['subs']
            c['reg'] += a['reg']
            c['fd'] += a['fd']
        print('=' * 88)
        print(level)
        print(f"{'':<44}{'баз':>5}{'сабдом.':>9}{'рег':>5}{'ФД':>4}"
              f"{'рег/база':>10}{'ФД/база':>9}{'ФД: 95% сверху':>16}")
        rows = sorted(g.items(), key=lambda kv: (-kv[1]['fd'], -kv[1]['reg']))
        shown = 0
        for k, c in rows:
            if level == 'ПО ПАКАМ' and c['fd'] == 0 and shown > 14:
                continue
            shown += 1
            hi = poisson_upper(c['fd'], c['baz'])
            print(f"{k[:43]:<44}{c['baz']:>5}{c['subs']:>9}{c['reg']:>5}{c['fd']:>4}"
                  f"{c['reg']/c['baz']:>10.2f}{c['fd']/c['baz']:>9.2f}"
                  f"{hi:>15.2f}")
        if level == 'ПО ПАКАМ':
            zero = sum(1 for k, c in rows if c['fd'] == 0)
            print(f'\n  паков всего {len(rows)}, из них с нулём ФД — {zero}')
            one = sum(1 for k, c in rows if c['fd'] == 1)
            print(f'  ровно с одним ФД — {one}')
            print('  на уровне пака контенты по ФД не различаются: данных нет и')
            print('  не может быть, пока ФД считаются десятками, а паков сотни')
        print()

    # 12 против 7 со стратой по неделе: единственное сравнение, где есть мощность
    print('=' * 88)
    print('12 СТРАНИЦ ПРОТИВ 7, СТРАТА — НЕДЕЛЯ ПЕРЕОБХОДА')
    print('без страты сравнение врёт: 12-страничные паки шли в конце августа,')
    print('когда и ставка ФД, и регистрации на базу были выше, а 7-страничные —')
    print('в середине сентября')
    w = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0]))
    for a in bases.values():
        p = pages(a['content'])
        if p not in ('12', '7') or not a['rec']:
            continue
        d = date.fromisoformat(a['rec'])
        c = w[(d - timedelta(days=d.weekday())).isoformat()][p]
        c[0] += 1
        c[1] += a['reg']
        c[2] += a['fd']
    print(f"\n{'неделя':<12}{'12: баз':>9}{'рег':>6}{'ФД':>5}{'рег/база':>11}"
          f"{'  |':>3}{'7: баз':>8}{'рег':>6}{'ФД':>5}{'рег/база':>11}")
    sreg, sfd = [], []
    for wk in sorted(w):
        a, b = w[wk].get('12', [0, 0, 0]), w[wk].get('7', [0, 0, 0])
        if not a[0] or not b[0]:
            continue
        sreg.append((a[1], a[0], b[1], b[0]))
        sfd.append((a[2], a[0], b[2], b[0]))
        print(f'{wk:<12}{a[0]:>9}{a[1]:>6}{a[2]:>5}{a[1]/a[0]:>11.2f}{"  |":>3}'
              f'{b[0]:>8}{b[1]:>6}{b[2]:>5}{b[1]/b[0]:>11.2f}')
    for name, st in (('регистрации', sreg), ('ФД', sfd)):
        rr, lo, hi = mh_rate(st)
        if rr:
            mark = '' if lo > 1 else '   — интервал накрывает единицу'
            print(f'\n  {name}: 12 страниц дают в {rr:.2f} раза больше '
                  f'[{lo:.2f}–{hi:.2f}]{mark}')
    print()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1], *(sys.argv[2:3]))
