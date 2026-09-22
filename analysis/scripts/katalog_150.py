#!/usr/bin/env python3
"""Каталог из 150 брендов: что даёт урезание.

Считает три вещи, из которых складывается ответ:
  1. вклад второго дня базы (56 брендов остатка) в сайты, клики, регистрации и ФД;
  2. цикл аккаунта Вебмастера (занятость + отдых) и ёмкость пула;
  3. сколько денег остаётся при отборе 150 брендов — по очереди и по деньгам
     (отбор по августу, замер по сентябрю — вне выборки).

    python3 katalog_150.py <panel.jsonl> <okno3.jsonl> <svod.csv>
"""
import sys, json, csv, collections, datetime, statistics

panel, okno, svod = sys.argv[1], sys.argv[2], sys.argv[3]

W = {}
for line in open(okno, encoding='utf-8'):
    r = json.loads(line)
    W[r[0]] = r[1:]                                   # всего, боты, из поиска, рег, ФД

rows = []
for line in open(panel, encoding='utf-8'):
    r = json.loads(line)
    rows.append((r['subdomain'], r.get('brand_label') or '—', r.get('recrawl_sent_at') or ''))

base_min = {}                                          # первый день переобхода базы
for sub, b, rc in rows:
    if not rc:
        continue
    base = sub.split('.', 1)[1]
    d = rc[:10]
    if base not in base_min or d < base_min[base]:
        base_min[base] = d

B = collections.defaultdict(collections.Counter)
w1 = collections.Counter()
w2 = collections.Counter()
wave = collections.defaultdict(collections.Counter)
for sub, b, rc in rows:
    if not rc:
        continue
    d0 = base_min[sub.split('.', 1)[1]]
    w = 1 if rc[:10] == d0 else 2
    o = W.get(sub) or [0, 0, 0, 0, 0]
    mon = 'авг' if d0 < '2026-09-01' else 'сен'
    x = B[b]
    x['sites'] += 1; x['ya'] += o[2]; x['reg'] += o[3]; x['fd'] += o[4]
    x['reg_' + mon] += o[3]; x['sites_' + mon] += 1
    v = wave[w]
    v['sites'] += 1; v['ya'] += o[2]; v['reg'] += o[3]; v['fd'] += o[4]
    (w1 if w == 1 else w2)[b] += 1

print('1. ВКЛАД ВТОРОГО ДНЯ БАЗЫ')
for k, name in [('sites', 'сайтов'), ('ya', 'кликов из поиска'), ('reg', 'регистраций'), ('fd', 'ФД')]:
    a, b_ = wave[1][k], wave[2][k]
    print(f'   {name:<18} день 1 {a:>9}   день 2 {b_:>7}   доля дня 2 {100*b_/(a+b_):5.1f}%')

rem = {b for b in B if w2[b] > w1[b]}
tot = sum(B[b]['reg'] for b in B)
print(f'\n   брендов в остатке: {len(rem)}; их регистраций {sum(B[b]["reg"] for b in rem)} '
      f'({100*sum(B[b]["reg"] for b in rem)/tot:.1f}% всех), сайтов '
      f'{100*sum(B[b]["sites"] for b in rem)/sum(B[b]["sites"] for b in B):.1f}%')

print('\n2. ЦИКЛ АККАУНТА ВЕБМАСТЕРА')
R = list(csv.DictReader(open(svod, encoding='utf-8')))
acc = collections.defaultdict(list)
for r in R:
    acc[r['аккаунт вебмастера']].append(datetime.date.fromisoformat(r['день запуска']))
gaps = sorted((v[i] - v[i-1]).days for v in (sorted(x) for x in acc.values()) for i in range(1, len(v)))
by_day = collections.Counter(r['день запуска'] for r in R)
cycle = statistics.median(gaps)
print(f'   аккаунтов {len(acc)}, повторных использований {len(gaps)}')
print(f'   интервал: медиана {cycle:.0f} дней, 10-й процентиль {gaps[len(gaps)//10]}, '
      f'быстрее 14 дней {sum(1 for g in gaps if g < 14)} случаев')
print(f'   ёмкость пула при цикле {cycle:.0f} дней: {len(acc)/cycle:.0f} баз в день; '
      f'фактически {len(R)/len(by_day):.0f} (максимум {max(by_day.values())})')
print(f'   при каталоге в 150 брендов цикл {cycle-1:.0f} дней: {len(acc)/(cycle-1):.0f} баз в день '
      f'(+{100*(cycle/(cycle-1)-1):.1f}%)')

print('\n3. СКОЛЬКО ДЕНЕГ ОСТАЁТСЯ ПРИ КАТАЛОГЕ В 150 БРЕНДОВ')
keep_queue = set(B) - rem
print(f'   режем хвост очереди:      остаётся {100*sum(B[b]["reg"] for b in keep_queue)/tot:.1f}% регистраций')
ranked = sorted(B, key=lambda b: (-(B[b]['reg_авг'] / max(B[b]['sites_авг'], 1)), -B[b]['reg_авг']))
keep_money = set(ranked[:150])
sep = sum(B[b]['reg_сен'] for b in B)
print(f'   отбор 150 лучших по августу → сентябрь: удержано '
      f'{sum(B[b]["reg_сен"] for b in keep_money)}/{sep} = '
      f'{100*sum(B[b]["reg_сен"] for b in keep_money)/sep:.1f}% (вне выборки)')
zero = [b for b in B if B[b]['reg'] == 0]
print(f'   брендов с нулём регистраций: {len(zero)}, на них '
      f'{100*sum(B[b]["sites"] for b in zero)/sum(B[b]["sites"] for b in B):.1f}% сайтов')

print('\n4. ИТОГ: множитель регистраций в сутки')
for name, speed in [('упираемся в пул аккаунтов', cycle/(cycle-1)), ('упираемся в домены/контент', 1.0),
                    ('упираемся в сутки переобхода', 2.0)]:
    for cut, share in [('хвост очереди', sum(B[b]['reg'] for b in keep_queue)/tot),
                       ('худшие по деньгам', sum(B[b]['reg_сен'] for b in keep_money)/sep)]:
        print(f'   {name:<30} {cut:<20} {speed*share:.2f}')
