#!/usr/bin/env python3
"""Живые и мёртвые бренды: разбор всех 206 брендов за всю историю запусков.

Считает по каждому бренду за весь период панели (11.08–21.09):
  сколько сайтов ему дали, сколько из них вышло в поиск, сколько собрали
  поисковых кликов, сколько пришло регистраций и первых депозитов, отдачу
  на сто сайтов и на десять тысяч кликов, отношение к сетевой ставке (O/E)
  и устойчивость между августом и сентябрём.

Делит бренды на классы: объёмные (есть и трафик, и деньги), снайперы
(трафика почти нет, но каждый клик конвертит), мёртвые по деньгам (трафик
есть, денег нет) и мёртвые по спросу (трафика нет, судить не о чем).

    python3 brendy_zhivye.py <panel.jsonl> <klikprof2.jsonl> <out.csv> <out.txt>
"""
import sys, json, csv, collections, math

panel, klik, out_csv, out_txt = sys.argv[1:5]

K = {}
for line in open(klik, encoding='utf-8'):
    q = json.loads(line)
    K[q[0]] = q                                    # sub, всего, боты, из поиска, ...

B = collections.defaultdict(collections.Counter)
zones = collections.defaultdict(collections.Counter)
for line in open(panel, encoding='utf-8'):
    x = json.loads(line)
    rc = (x.get('recrawl_sent_at') or '')[:10]
    if not rc:
        continue                                   # сайт не уходил в переобход
    b = x.get('brand_label') or '—'
    k = K.get(x['subdomain'])
    ya = k[3] if k else 0
    mon = 'авг' if rc < '2026-09-01' else 'сен'
    c = B[b]
    c['sites'] += 1; c['ya'] += ya
    c['clicks'] += k[1] if k else 0
    c['reg'] += x.get('reg') or 0
    c['fd'] += x.get('fd') or 0
    if ya:
        c['vyshli'] += 1
    c['sites_' + mon] += 1; c['ya_' + mon] += ya; c['reg_' + mon] += x.get('reg') or 0
    zones[b][x.get('tld') or '?'] += 1

TOT_YA = sum(c['ya'] for c in B.values())
TOT_REG = sum(c['reg'] for c in B.values())
RATE = TOT_REG / TOT_YA                            # сетевая ставка, рег на клик

def poisson_lo_hi(o, e):
    """Грубый 95% интервал O/E по Пуассону (Гарвудовы границы через гамму)."""
    if e <= 0:
        return None, None
    lo = 0.0 if o == 0 else _chi2_inv(0.025, 2 * o) / 2 / e
    hi = _chi2_inv(0.975, 2 * (o + 1)) / 2 / e
    return lo, hi

def _chi2_inv(p, k):
    """Квантиль хи-квадрат через поиск по функции распределения (stdlib)."""
    lo, hi = 0.0, max(10.0, k * 5)
    while _chi2_cdf(hi, k) < p:
        hi *= 2
    for _ in range(200):
        m = (lo + hi) / 2
        if _chi2_cdf(m, k) < p:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2

def _chi2_cdf(x, k):
    return _gammainc(k / 2, x / 2)

def _gammainc(s, x):
    """Нижняя неполная гамма, нормированная."""
    if x <= 0:
        return 0.0
    if x < s + 1:
        t = 1.0 / s; total = t; n = 0
        while n < 500:
            n += 1; t *= x / (s + n); total += t
            if t < total * 1e-14:
                break
        return total * math.exp(-x + s * math.log(x) - math.lgamma(s))
    f, c, d = 0.0, 1e300, 1.0 / 1e-300
    b = x + 1 - s; c = 1e300; d = 1 / b; h = d
    for i in range(1, 500):
        an = -i * (i - s)
        b += 2
        d = an * d + b
        if abs(d) < 1e-300: d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300: c = 1e-300
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-14:
            break
    return 1 - math.exp(-x + s * math.log(x) - math.lgamma(s)) * h

def klass(r):
    """Класс бренда. Порог трафика — ожидание в 3 регистрации по сетевой ставке."""
    reg, E = r['регистраций'], r['E']
    if reg >= 5 and E >= 3:
        return 'объёмный'
    if reg >= 5 and E < 3:
        return 'снайпер'
    if reg == 0 and E >= 3:
        return 'мёртвый по деньгам'
    if reg == 0 and E < 1:
        return 'мёртвый по спросу'
    return 'слабый'

rows = []
for b, c in B.items():
    E = c['ya'] * RATE
    lo, hi = poisson_lo_hi(c['reg'], E)
    r = {'бренд': b, 'сайтов': c['sites'], 'вышли в поиск': c['vyshli'],
         'выход %': round(100 * c['vyshli'] / c['sites'], 1),
         'поисковых кликов': c['ya'],
         'кликов на вышедший сайт': round(c['ya'] / c['vyshli'], 1) if c['vyshli'] else 0,
         'регистраций': c['reg'], 'ФД': c['fd'],
         'рег на 100 сайтов': round(100 * c['reg'] / c['sites'], 3),
         'рег на 10 тыс. кликов': round(1e4 * c['reg'] / c['ya'], 1) if c['ya'] else None,
         'E': round(E, 2), 'oe': round(c['reg'] / E, 2) if E > 0 else None,
         'oe_lo': round(lo, 2) if lo is not None else None,
         'oe_hi': round(hi, 2) if hi is not None else None,
         'ФД на регистрацию': round(c['fd'] / c['reg'], 2) if c['reg'] else None,
         'рег авг': c['reg_авг'], 'рег сен': c['reg_сен'],
         'кликов авг': c['ya_авг'], 'кликов сен': c['ya_сен'],
         'сайтов авг': c['sites_авг'], 'сайтов сен': c['sites_сен'],
         'зоны': ' '.join(f'{z} {n}' for z, n in zones[b].most_common(4))}
    r['класс'] = klass(r)
    rows.append(r)
rows.sort(key=lambda r: -r['регистраций'])

with open(out_csv, 'w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

def spearman(pairs):
    pairs = [p for p in pairs if p[0] is not None and p[1] is not None]
    if len(pairs) < 3:
        return None
    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i])
        rr = [0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[s[j + 1]] == v[s[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for t in range(i, j + 1):
                rr[s[t]] = avg
            i = j + 1
        return rr
    a = rank([p[0] for p in pairs]); b = rank([p[1] for p in pairs])
    n = len(a); ma = sum(a) / n; mb = sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return round(num / den, 3) if den else None

lines = []
P = lines.append
P('ЖИВЫЕ И МЁРТВЫЕ БРЕНДЫ — все 206 за историю запусков 11.08–21.09')
P(f'Сеть: {sum(r["сайтов"] for r in rows)} сайтов, {TOT_YA} поисковых кликов, '
  f'{TOT_REG} регистраций, {sum(r["ФД"] for r in rows)} первых депозитов.')
P(f'Сетевая ставка: {RATE*1e4:.2f} регистрации на 10 тысяч поисковых кликов.')
P('')
P('1. КЛАССЫ')
cl = collections.Counter(r['класс'] for r in rows)
for k in ['объёмный', 'снайпер', 'слабый', 'мёртвый по деньгам', 'мёртвый по спросу']:
    g = [r for r in rows if r['класс'] == k]
    if not g:
        continue
    P(f'   {k:<20} брендов {len(g):>3} | сайтов {sum(r["сайтов"] for r in g):>7} '
      f'| кликов {sum(r["поисковых кликов"] for r in g):>9} | рег {sum(r["регистраций"] for r in g):>4} '
      f'| ФД {sum(r["ФД"] for r in g):>3} | рег/10 тыс. {1e4*sum(r["регистраций"] for r in g)/max(sum(r["поисковых кликов"] for r in g),1):7.2f}')
P('')
P('2. СНАЙПЕРЫ — трафика почти нет, но каждый клик конвертит')
P(f'   {"бренд":<16}{"сайтов":>8}{"выход %":>9}{"клики":>9}{"рег":>5}{"ФД":>4}{"рег/10тыс":>11}{"ожидание":>10}')
for r in sorted([r for r in rows if r['класс'] == 'снайпер'], key=lambda r: -r['рег на 10 тыс. кликов']):
    P(f'   {r["бренд"]:<16}{r["сайтов"]:>8}{r["выход %"]:>9}{r["поисковых кликов"]:>9}'
      f'{r["регистраций"]:>5}{r["ФД"]:>4}{r["рег на 10 тыс. кликов"]:>11}{r["E"]:>10}')
P('')
P('3. МЁРТВЫЕ ПО ДЕНЬГАМ — трафик есть, регистраций ноль')
P(f'   {"бренд":<16}{"сайтов":>8}{"выход %":>9}{"клики":>9}{"ожидание":>10}{"верх интервала O/E":>20}')
for r in sorted([r for r in rows if r['класс'] == 'мёртвый по деньгам'], key=lambda r: -r['E']):
    P(f'   {r["бренд"]:<16}{r["сайтов"]:>8}{r["выход %"]:>9}{r["поисковых кликов"]:>9}{r["E"]:>10}{r["oe_hi"]:>20}')
P('')
P('4. ОБЪЁМНЫЕ — есть и трафик, и деньги')
P(f'   {"бренд":<16}{"сайтов":>8}{"выход %":>9}{"клики":>9}{"рег":>5}{"ФД":>4}{"рег/10тыс":>11}{"O/E":>7}')
for r in sorted([r for r in rows if r['класс'] == 'объёмный'], key=lambda r: -r['регистраций']):
    P(f'   {r["бренд"]:<16}{r["сайтов"]:>8}{r["выход %"]:>9}{r["поисковых кликов"]:>9}'
      f'{r["регистраций"]:>5}{r["ФД"]:>4}{r["рег на 10 тыс. кликов"]:>11}{r["oe"]:>7}')
P('')
P('5. САМЫЕ БОЛЬШИЕ ПО ТРАФИКУ (первая двадцатка) — и что они дают')
P(f'   {"бренд":<16}{"клики":>9}{"рег":>5}{"ожидание":>10}{"O/E":>7}{"рег/10тыс":>11}')
for r in sorted(rows, key=lambda r: -r['поисковых кликов'])[:20]:
    P(f'   {r["бренд"]:<16}{r["поисковых кликов"]:>9}{r["регистраций"]:>5}{r["E"]:>10}'
      f'{(r["oe"] if r["oe"] is not None else 0):>7}{r["рег на 10 тыс. кликов"]:>11}')
P('')
P('6. УСТОЙЧИВОСТЬ: август против сентября')
both = [r for r in rows if r['кликов авг'] > 0 and r['кликов сен'] > 0]
P(f'   брендов с трафиком в оба месяца: {len(both)}')
P('   ранговая связь выхода в поиск:      ' + str(spearman([(r['кликов авг']/max(r['сайтов авг'],1), r['кликов сен']/max(r['сайтов сен'],1)) for r in both])))
P('   ранговая связь регистраций на сайт: ' + str(spearman([(r['рег авг']/max(r['сайтов авг'],1), r['рег сен']/max(r['сайтов сен'],1)) for r in both])))
P('   ранговая связь отдачи с клика:      ' + str(spearman([(r['рег авг']/max(r['кликов авг'],1), r['рег сен']/max(r['кликов сен'],1)) for r in both])))
top_aug = sorted(both, key=lambda r: -(r['рег авг']/max(r['кликов авг'],1)))[:20]
sep_top = sum(r['рег сен'] for r in top_aug); sep_all = sum(r['рег сен'] for r in both)
P(f'   двадцатка лучших по августу дала в сентябре {sep_top} из {sep_all} регистраций '
  f'({100*sep_top/max(sep_all,1):.0f}% против 10% при случайном отборе)')
zero_aug = [r for r in both if r['рег авг'] == 0]
P(f'   брендов без регистраций в августе: {len(zero_aug)}; из них дали деньги в сентябре: '
  f'{sum(1 for r in zero_aug if r["рег сен"] > 0)} (всего {sum(r["рег сен"] for r in zero_aug)} регистраций)')
P('')
P('7. СВЯЗЬ ТРАФИКА И ОТДАЧИ')
P('   ранговая связь "поисковых кликов" и "рег на 10 тыс. кликов": ' +
  str(spearman([(r['поисковых кликов'], r['рег на 10 тыс. кликов']) for r in rows if r['поисковых кликов'] > 0])))
q = sorted([r for r in rows if r['поисковых кликов'] > 0], key=lambda r: r['поисковых кликов'])
step = len(q) // 5
P(f'   {"группа по кликам":<22}{"брендов":>9}{"клики":>10}{"рег":>6}{"рег/10тыс":>11}')
for i in range(5):
    g = q[i*step:(i+1)*step] if i < 4 else q[4*step:]
    ya = sum(r['поисковых кликов'] for r in g); rg = sum(r['регистраций'] for r in g)
    P(f'   {i+1} пятая{"":<14}{len(g):>9}{ya:>10}{rg:>6}{1e4*rg/max(ya,1):>11.2f}')
open(out_txt, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
