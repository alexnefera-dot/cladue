#!/usr/bin/env python3
"""Прогноз регистраций на два дня вперёд по индексу первых суток.

Идея: деньги дня = старый сток (сайты 4+ суток) + свежие когорты 0–3 суток.
Свежая когорта принесёт примерно k1 × (сайтов, вышедших в поиск за сутки 0–1),
распределив это по возрасту по долям P[0..3]. Коэффициенты берутся только из
прошлого (скользящее окно), проверка вне выборки против двух простых правил:
«как вчера» и «среднее за 7 дней».

    python3 prognoz.py <panel.jsonl> <kliki_dni.jsonl> <out.txt> <конверсии...>
"""
import sys, json, collections, datetime as dt

panel_p, kliki_p, out_p = sys.argv[1:4]
conv_ps = sys.argv[4:]
D0 = dt.date(2026, 7, 1)
END = (dt.date(2026, 9, 22) - D0).days


def dn(s):
    return (dt.date.fromisoformat(s[:10]) - D0).days


def ds(n):
    return (D0 + dt.timedelta(n)).strftime('%d.%m')


out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


L = {}
for line in open(panel_p, encoding='utf-8'):
    r = json.loads(line)
    if r.get('recrawl_sent_at'):
        L[r['subdomain'].lower()] = dn(r['recrawl_sent_at'])
sites = collections.Counter(L.values())
i1 = collections.Counter()       # день запуска -> сайтов с кликом на сутках 0–1
for line in open(kliki_p, encoding='utf-8'):
    s, dd = json.loads(line)
    if s in L and any(0 <= dn(d) - L[s] <= 1 for d in dd):
        i1[L[s]] += 1
seen = set()
reg_new = collections.Counter()  # день -> рег с сайтов 0–3 суток
reg_old = collections.Counter()  # день -> рег со старого стока
reg_age = collections.defaultdict(collections.Counter)  # день запуска -> возраст -> рег
for p in conv_ps:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        k = (r['clickid'], r['event'], r['at'])
        if k in seen or r['event'] != 'reg':
            continue
        seen.add(k)
        s = (r.get('subdomain') or '').lower()
        d = dn(r['at'])
        if s in L and 0 <= d - L[s] <= 3:
            reg_new[d] += 1; reg_age[L[s]][d - L[s]] += 1
        else:
            reg_old[d] += 1
total = {d: reg_new[d] + reg_old[d] for d in range(dn('2026-08-18'), END + 1)}

P('=== Сигнал на уровне когорты: рег за 0–3 сутки ~ сайтов, вышедших за сутки ===')
P(f'{"запуск":>7} {"сайтов":>7} {"вышло ≤1 сут.":>14} {"рег 0–3":>8}')
for d in range(dn('2026-08-18'), END - 3):
    if sites[d]:
        P(f'{ds(d):>7} {sites[d]:>7} {i1[d]:>14} {sum(reg_age[d].values()):>8}')

P('\n=== Бэктест: прогноз итога дня на завтра и послезавтра, коэффициенты только из прошлого ===')
start = dn('2026-09-01')
err = collections.defaultdict(list)
rows = []
for t in range(start, END - 1):         # t = последний известный день, прогноз на t+1 и t+2
    past = [d for d in range(dn('2026-08-18'), t - 3) if sites[d]]  # когорты с закрытым окном
    k1 = sum(sum(reg_age[d].values()) for d in past) / max(1, sum(i1[d] for d in past))
    Pa = [sum(reg_age[d][a] for d in past) for a in range(4)]
    Pa = [x / max(1, sum(Pa)) for x in Pa]
    base = sum(reg_old[d] for d in range(t - 6, t + 1)) / 7
    for h in (1, 2):
        T = t + h
        if T > END:
            continue
        # когорта, запущенная в сам прогнозный день, ещё не видна: берём среднее i1 за 7 дней
        est_i1 = lambda d: i1[d] if d <= t - 1 else sum(i1[x] for x in range(t - 7, t)) / 7
        fresh = sum(k1 * est_i1(T - a) * Pa[a] for a in range(4))
        f_model = base + fresh
        f_mean = sum(total[d] for d in range(t - 6, t + 1)) / 7
        f_yday = total[t]
        y = total[T]
        err[('индекс', h)].append(abs(f_model - y))
        err[('среднее 7 дн.', h)].append(abs(f_mean - y))
        err[('как вчера', h)].append(abs(f_yday - y))
        err[('смесь', h)].append(abs((f_model + f_mean) / 2 - y))
        rows.append((ds(T), h, y, f_model, f_mean, f_yday))
P(f'{"день":>6} {"гориз.":>6} {"факт":>5} {"по индексу":>11} {"среднее 7":>10} {"как вчера":>10}')
for r in rows:
    P(f'{r[0]:>6} {r[1]:>6} {r[2]:>5} {r[3]:>11.1f} {r[4]:>10.1f} {r[5]:>10}')
P('\nСредняя ошибка, рег в день (меньше — лучше):')
for m in ('индекс', 'среднее 7 дн.', 'смесь', 'как вчера'):
    P(f'   {m:<14} завтра {sum(err[(m,1)])/len(err[(m,1)]):5.2f}   послезавтра {sum(err[(m,2)])/len(err[(m,2)]):5.2f}')
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
