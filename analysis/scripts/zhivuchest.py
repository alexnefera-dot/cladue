#!/usr/bin/env python3
"""Живучесть запусков: сколько сайтов доходит до поискового клика.

Живучесть домена = доля его сайтов, получивших первый клик из поиска в течение
K суток от переобхода. По сети 74% первых кликов приходят за сутки и 86% за трое,
поэтому на четвёртый день запуск уже оценён.

    python3 zhivuchest.py <реестр.jsonl> <окно K> <out.txt> <клики.jsonl> [ещё клики...]

Реестр — выгрузка /v1/subdomains (в ней есть recrawl_sent_at и content_label).
Клики — выгрузки трекера; берём только строки с поисковым реферером и не ботов.
"""
import sys, json, re, collections, datetime

reg_p, K, out_p = sys.argv[1], int(sys.argv[2]), sys.argv[3]
click_paths = sys.argv[4:]

SUB = {}
for line in open(reg_p, encoding='utf-8'):
    r = json.loads(line)
    s = (r.get('subdomain') or '').lower()
    rc = (r.get('recrawl_sent_at') or '')[:10]
    if s and rc:
        name = r.get('content_label') or 'не записан'
        # в реестре имя набора несёт хвост с номером домена: …-oform-1_28 — это
        # один домен, а не отдельный набор; для группировки хвост убираем
        root = re.sub(r'_\d+$', '', name)
        SUB[s] = {'rc': rc, 'content': root, 'full': name,
                  'base': s.split('.', 1)[1], 'brand': r.get('brand_label') or ''}
print(f'реестр: {len(SUB)} сайтов', flush=True)

first = {}                                    # сайт -> дата первого поискового клика
seen = 0
for p in click_paths:
    for line in open(p, encoding='utf-8'):
        seen += 1
        r = json.loads(line)
        if r.get('is_bot'):
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        s = (r.get('subdomain') or '').lower()
        if s not in SUB:
            continue
        d = r['at'][:10]
        if s not in first or d < first[s]:
            first[s] = d
    print(f'  {p}: прочитано {seen}, сайтов с поиском {len(first)}', flush=True)

day = lambda s: datetime.date.fromisoformat(s)
BASE = collections.defaultdict(lambda: collections.Counter())
CONT = collections.defaultdict(lambda: collections.Counter())
DAY  = collections.defaultdict(lambda: collections.Counter())
LAST = max(v['rc'] for v in SUB.values())
CLOSED = (day(LAST) - datetime.timedelta(days=K)).isoformat()
dom_seen = collections.defaultdict(set)
for s, v in SUB.items():
    if v['rc'] > CLOSED:
        continue                              # окно ещё не закрылось
    dom_seen[v['content']].add(v['base'])
    lag = (day(first[s]) - day(v['rc'])).days if s in first else None
    ok = lag is not None and lag <= K
    for agg, key in ((BASE, v['base']), (CONT, v['content']), (DAY, v['rc'])):
        c = agg[key]
        c['sites'] += 1
        c['live'] += 1 if ok else 0
for k, d in dom_seen.items():
    CONT[k]['dom'] = len(d)

L = []
P = L.append
tot_s = sum(c['sites'] for c in DAY.values()); tot_l = sum(c['live'] for c in DAY.values())
P(f'ЖИВУЧЕСТЬ ЗА {K} СУТОК ОТ ПЕРЕОБХОДА')
P(f'всего сайтов {tot_s}, дошли до поискового клика {tot_l} ({100*tot_l/tot_s:.1f}%)')
P(f'учтены запуски по {CLOSED} включительно — у более поздних окно ещё не закрылось')
P('')
P('ПО ДНЯМ ПЕРЕОБХОДА')
P(f'   {"день":<12}{"сайтов":>9}{"дошли":>9}{"живучесть":>11}')
for k in sorted(DAY):
    c = DAY[k]
    P(f'   {k:<12}{c["sites"]:>9}{c["live"]:>9}{100*c["live"]/c["sites"]:>10.1f}%')
P('')
P('ПО НАБОРАМ КОНТЕНТА (от лучшего; только наборы от 10 доменов, окно закрыто)')
P(f'   {"набор":<40}{"доменов":>9}{"сайтов":>8}{"дошли":>8}{"живучесть":>11}')
for k, c in sorted(CONT.items(), key=lambda kv: -kv[1]['live'] / max(kv[1]['sites'], 1)):
    if c['dom'] < 10:
        continue
    P(f'   {k[:39]:<40}{c["dom"]:>9}{c["sites"]:>8}{c["live"]:>8}{100*c["live"]/c["sites"]:>10.1f}%')
P('')
P('ПО ДОМЕНАМ (худшие 20 и лучшие 20)')
dom = sorted(((100 * c['live'] / c['sites'], k, c) for k, c in BASE.items() if c['sites'] >= 100))
def show(rows):
    for pct, k, c in rows:
        P(f'   {k:<28}{c["sites"]:>6} сайтов{c["live"]:>6} дошли{pct:>8.1f}%')
show(dom[:20]); P('   ...'); show(dom[-20:])
open(out_p, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
