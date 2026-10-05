#!/usr/bin/env python3
"""Какие группы контента заходят из свежих запусков.

Контент в системе стоит ровно на одном домене, поэтому отдельный текст от своего
домена не отделить — сравнивать можно только группы. Мешают ещё две вещи: день
переобхода (чем позже, тем меньше успел набрать) и доменная зона (.lol вдвое
сильнее .team). Обе снимаются делением на средний сайт того же дня и той же зоны.

Устойчивость проверяется выбрасыванием лучшего текста группы и двух лучших: если
группа держится без них, дело в группе, если проседает — в одном удачном тексте.

    python3 kontenty_svezhie.py <день кликов> <с какого переобхода> <out.txt>
        --subs ... --clicks ...
"""
import sys, json, re, collections, statistics

day, since, out_p = sys.argv[1:4]
opt = collections.defaultdict(list); cur = None
for a in sys.argv[4:]:
    if a.startswith('--'):
        cur = a[2:]
    else:
        opt[cur].append(a)
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


site = {}
for p in opt['subs']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        s = r['subdomain'].lower(); rc = r.get('recrawl_sent_at')
        if not rc or s in site or rc[:10] < since:
            continue
        site[s] = dict(c=r.get('content_label') or '?', d=rc[:10], z=r.get('tld'))
clicks = collections.Counter()
for p in opt['clicks']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        if r.get('is_bot') or r['at'][:10] != day:
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        s = (r.get('subdomain') or '').lower()
        if s in site:
            clicks[s] += 1


def fam(c):
    m = re.match(r'content-\d{4}-\d{2}-\d{2}-(.+?)_\d+$', c) or re.match(r'content-\d{4}-\d{2}-\d{2}-(.+)$', c)
    if m:
        return m.group(1)
    m = re.match(r'(nabory-[\d-]+-[^_]+)_\d+$', c)
    if m:
        return 'nabory: ' + m.group(1).split('-', 3)[-1]
    return re.sub(r'_\d+$', '', c)


# фон: средний сайт того же дня в той же зоне
cell = collections.defaultdict(lambda: [0, 0])
for s, v in site.items():
    k = (v['d'], v['z']); cell[k][0] += clicks.get(s, 0); cell[k][1] += 1
base = {k: a / b for k, (a, b) in cell.items() if b}
# текст -> сайты, клики, прорыв
T = collections.defaultdict(lambda: dict(n=0, c=0, hit=0, d='', z=None))
for s, v in site.items():
    g = T[v['c']]; g['n'] += 1; g['c'] += clicks.get(s, 0); g['d'] = v['d']; g['z'] = v['z']
    if clicks.get(s, 0):
        g['hit'] += 1
F = collections.defaultdict(list)
for c, g in T.items():
    F[fam(c)].append((c, g))


def norm(v):
    c = sum(g['c'] for _, g in v)
    wb = sum(g['n'] * base.get((g['d'], g['z']), 0) for _, g in v)
    return c / wb if wb else 0


P(f'Клики за {day}. Запуски с переобходом от {since}. Текстов {len(T)}, сайтов {sum(g["n"] for g in T.values())}, '
  f'кликов {sum(g["c"] for g in T.values())}.')
P(f'Фон = средний сайт того же дня в той же зоне. 1,00× — как у всех.\n')
P(f'{"группа контента":<24} {"текстов":>8} {"сайтов":>7} {".lol":>6} {"к фону":>8} {"без топ-1":>10} '
  f'{"без топ-2":>10} {"медиана текста":>15} {"с нулём":>9}')
rows = []
for f, v in F.items():
    if len(v) < 10:
        continue
    v2 = sorted(v, key=lambda x: -x[1]['c'])
    n = sum(g['n'] for _, g in v)
    lol = 100 * sum(g['n'] for _, g in v if g['z'] == 'lol') / n
    med = statistics.median([(g['c'] / g['n']) / base.get((g['d'], g['z']), 1) or 0 for _, g in v])
    rows.append((norm(v), f, len(v), n, lol, norm(v2[1:]), norm(v2[2:]), med,
                 sum(1 for _, g in v if g['c'] == 0)))
for k, f, t, n, lol, b1, b2, med, zero in sorted(rows, reverse=True):
    P(f'{f[:24]:<24} {t:>8} {n:>7} {lol:>5.0f}% {k:>7.2f}× {b1:>9.2f}× {b2:>9.2f}× {med:>15.2f} {zero:>4}/{t:<4}')
P('\nЛучшие тексты (полные имена), к фону своего дня и зоны:')
P(f'{"текст":<44} {"день":<11} {"зона":<6} {"кликов":>8} {"прорыв":>8} {"к фону":>8}')
for c, g in sorted(T.items(), key=lambda x: -x[1]['c'])[:15]:
    b = base.get((g['d'], g['z']), 0)
    P(f'{c:<44} {g["d"]:<11} {g["z"]:<6} {g["c"]:>8} {100*g["hit"]/g["n"]:>7.1f}% '
      f'{((g["c"]/g["n"])/b if b else 0):>7.1f}×')
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
