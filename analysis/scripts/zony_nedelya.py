#!/usr/bin/env python3
"""Регистрации по зонам за неделю: абсолют и с поправкой на число живых сайтов.

Сайт считается живым в день D, если его переобход был не раньше чем за `окно`
суток до D. Без этой поправки сравнение зон врёт: зоны запускались в разное
время, и у одной в работе может быть втрое больше сайтов, чем у другой.

    python3 zony_nedelya.py <с> <по> <out.txt> --subs ... --conv ... [--okno 7]
"""
import sys, json, collections, datetime as dt

lo, hi, out_p = sys.argv[1:4]
opt = collections.defaultdict(list); cur = None
for a in sys.argv[4:]:
    if a.startswith('--'):
        cur = a[2:]
    else:
        opt[cur].append(a)
OKNO = int(opt['okno'][0]) if opt['okno'] else 7
T = dt.datetime.fromisoformat
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


reg = {}
for p in opt['subs']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        s = r['subdomain'].lower()
        if s in reg:
            continue
        rc = r.get('recrawl_sent_at')
        reg[s] = dict(z=r.get('tld'), rc=rc[:10] if rc else None, b=r['content_domain_url'])
seen = set(); CV = collections.defaultdict(collections.Counter); nomap = collections.Counter()
AGE = collections.defaultdict(lambda: collections.defaultdict(list))
for p in opt['conv']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        k = (r['clickid'], r['event'], r['at'])
        d = r['at'][:10]
        if k in seen or r.get('campaign') != 'dorgen_engine' or not (lo <= d <= hi):
            continue
        seen.add(k)
        s = (r.get('subdomain') or '').lower()
        v = reg.get(s)
        z = v['z'] if v and v['z'] else None
        if not z:                       # зону берём из самого хоста, если сайта нет в реестре
            z = s.rsplit('.', 1)[-1] if '.' in s else '?'
            nomap[z] += 1
        # возраст сайта на день конверсии — чтобы числитель совпал со знаменателем
        age = None
        if v and v['rc']:
            age = (T(d) - T(v['rc'])).days
        CV[d][(z, r['event'])] += 1
        AGE[d][(z, r['event'])].append(age)

days = sorted({d for d in CV} | {(T(lo) + dt.timedelta(days=i)).strftime('%Y-%m-%d')
                                 for i in range((T(hi) - T(lo)).days + 1)})
zones = ('lol', 'team')
# живые сайты каждой зоны в каждый день
live = collections.defaultdict(collections.Counter)
for s, v in reg.items():
    if not v['rc'] or v['z'] not in zones:
        continue
    r0 = T(v['rc'])
    for d in days:
        dd = T(d)
        if 0 <= (dd - r0).days < OKNO:
            live[d][v['z']] += 1

P(f'Регистрации по зонам, {lo} — {hi}. Живым считается сайт, переобойденный за последние {OKNO} суток.')
P(f'\n{"день":<12} ' + ' '.join(f'{".%s" % z:>34}' for z in zones))
P(f'{"":<12} ' + ' '.join(f'{"живых сайтов":>14}{"рег":>6}{"ФД":>5}{"рег/10тыс":>10}' for _ in zones))
TOT = collections.defaultdict(lambda: [0, 0, 0])
for d in days:
    line = f'{d:<12} '
    for z in zones:
        n = live[d][z]; rg = CV[d][(z, 'reg')]; fd = CV[d][(z, 'fd')]
        line += f'{n:>14}{rg:>6}{fd:>5}' + (f'{10000*rg/n:>10.2f}' if n else f'{"—":>10}') + ' '
        t = TOT[z]; t[0] += n; t[1] += rg; t[2] += fd
    P(line)
P(f'{"ИТОГО":<12} ' + ' '.join(
    f'{TOT[z][0]:>14}{TOT[z][1]:>6}{TOT[z][2]:>5}' + (f'{10000*TOT[z][1]/TOT[z][0]:>10.2f}' if TOT[z][0] else f'{"—":>10}') + ' '
    for z in zones))
# то же, но числитель ограничен возрастом сайта — честное сравнение
P(f'\n=== Только регистрации с сайтов моложе {OKNO} суток (числитель и знаменатель сходятся) ===')
P(f'{"день":<12} ' + ' '.join(f'{".%s" % z:>34}' for z in zones))
P(f'{"":<12} ' + ' '.join(f'{"живых сайтов":>14}{"рег":>6}{"ФД":>5}{"рег/10тыс":>10}' for _ in zones))
T2 = collections.defaultdict(lambda: [0, 0, 0])
for d in days:
    line = f'{d:<12} '
    for z in zones:
        n = live[d][z]
        rg = sum(1 for a in AGE[d][(z, 'reg')] if a is not None and 0 <= a < OKNO)
        fd = sum(1 for a in AGE[d][(z, 'fd')] if a is not None and 0 <= a < OKNO)
        line += f'{n:>14}{rg:>6}{fd:>5}' + (f'{10000*rg/n:>10.2f}' if n else f'{"—":>10}') + ' '
        t = T2[z]; t[0] += n; t[1] += rg; t[2] += fd
    P(line)
P(f'{"ИТОГО":<12} ' + ' '.join(
    f'{T2[z][0]:>14}{T2[z][1]:>6}{T2[z][2]:>5}' + (f'{10000*T2[z][1]/T2[z][0]:>10.2f}' if T2[z][0] else f'{"—":>10}') + ' '
    for z in zones))

# устойчивость: то же при других окнах
P(f'\n=== Устойчивость: та же мера при разных окнах жизни сайта ===')
P(f'{"окно, суток":<13} ' + ' '.join(f'{".%s рег" % z:>12}{"сайто-дней":>12}{"рег/10тыс":>11}' for z in zones))
for W in (3, 5, 7, 10, 14, 21, 30):
    ln = f'{W:<13} '
    for z in zones:
        n = 0
        for s2, v2 in reg.items():
            if not v2['rc'] or v2['z'] != z:
                continue
            r0 = T(v2['rc'])
            n += sum(1 for d in days if 0 <= (T(d) - r0).days < W)
        rw = sum(1 for d in days for a in AGE[d][(z, 'reg')] if a is not None and 0 <= a < W)
        ln += f'{rw:>12}{n:>12}' + (f'{10000*rw/n:>11.2f}' if n else f'{"—":>11}')
    P(ln)

share = {z: TOT[z][1] for z in zones}; tr = sum(share.values()) or 1
P(f'\nДоля регистраций (все возрасты): ' + ', '.join(f'.{z} {share[z]} ({100*share[z]/tr:.0f}%)' for z in zones))
sh2 = {z: T2[z][1] for z in zones}; tr2 = sum(sh2.values()) or 1
P(f'Доля регистраций (сайты моложе {OKNO} суток): ' + ', '.join(f'.{z} {sh2[z]} ({100*sh2[z]/tr2:.0f}%)' for z in zones))
other = sum(v for (z, e), v in ((k, v) for d in CV for k, v in CV[d].items()) if e == 'reg' and z not in zones)
if other:
    P(f'Вне двух зон: {other} рег')
if nomap:
    P(f'Сайтов не нашлось в реестре, зона взята из хоста: {dict(nomap)}')
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
