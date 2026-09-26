#!/usr/bin/env python3
"""Повторы старых контентов: тот же экземпляр текста на новом домене против первого запуска.

Пара = домен-повтор и домен первого запуска с тем же content_label (с номером экземпляра).
Выход в поиск: доля сайтов домена с живым поисковым кликом за 24 и 48 часов от переобхода.
Чтобы убрать эффект дня, каждый домен сравнивается со своим днём: индекс домена делится
на индекс всех запусков той же зоны в тот же день (контроль). Итог — отношение
«повтор к своему дню» / «первый запуск к своему дню».

    python3 povtory.py <день повторов> <out.txt> <out.csv> --subs <реестр ...> --panel <panel.jsonl>
        --first <boty.json> --clicks <клики.jsonl ...> --conv <конверсии.jsonl ...>
"""
import sys, re, csv, json, collections, datetime as dt

day, out_p, csv_p = sys.argv[1:4]
opt = collections.defaultdict(list); cur = None
for a in sys.argv[4:]:
    if a.startswith('--'):
        cur = a[2:]
    else:
        opt[cur].append(a)
T = dt.datetime.fromisoformat
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


# сайты: из панели (до 21.09) и свежего реестра
site = {}
for line in open(opt['panel'][0], encoding='utf-8'):
    r = json.loads(line)
    site[r['subdomain'].lower()] = dict(base=r['content_domain_url'], zone=r['tld'], rc=r.get('recrawl_sent_at'),
                                        content=r.get('content_label') or '',
                                        day=(r.get('recrawl_sent_at') or '')[:10])
for p in opt['subs']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        s = r['subdomain'].lower()
        b = r['content_domain_url']
        site[s] = dict(base=b, zone=b.rsplit('.', 1)[1], rc=r.get('recrawl_sent_at'),
                       content=r.get('content_label') or '', day=(r.get('recrawl_sent_at') or '')[:10])
# первые поисковые клики (не боты, реферер Яндекса)
first = {}
for s, f in json.load(open(opt['first'][0]))['first'].items():
    if f[1]:
        first[s] = f[1]
end = '2026-09-22T23:59:59+03:00'
for p in opt['clicks']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        if r['at'] > end:
            end = r['at']
        if r.get('is_bot'):
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        s = (r.get('subdomain') or '').lower()
        if s in site and (s not in first or r['at'] < first[s]):
            first[s] = r['at']
END = T(end)
seen = set(); conv = collections.defaultdict(list)
for p in opt['conv']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        k = (r['clickid'], r['event'], r['at'])
        if k in seen or r['event'] not in ('reg', 'fd') or r.get('campaign') != 'dorgen_engine':
            continue
        seen.add(k); conv[(r.get('subdomain') or '').lower()].append((r['at'], r['event']))


def dom_stats(sites, hours):
    n = hit = 0
    for s in sites:
        v = site[s]
        if not v['rc']:
            continue
        rc = T(v['rc'])
        if rc + dt.timedelta(hours=hours) > END:
            return None
        n += 1
        f = first.get(s)
        if f and rc - dt.timedelta(hours=1) <= T(f) < rc + dt.timedelta(hours=hours):
            hit += 1
    return (hit, n) if n else None


def money(sites, hours):
    reg = fd = 0
    for s in sites:
        rc = site[s]['rc']
        if not rc:
            continue
        for at, e in conv.get(s, []):
            if T(at) < T(rc) + dt.timedelta(hours=hours):
                if e == 'reg': reg += 1
                else: fd += 1
    return reg, fd


by_base = collections.defaultdict(list)
for s, v in site.items():
    by_base[v['base']].append(s)
by_label = collections.defaultdict(set)
for b, ss in by_base.items():
    c = site[ss[0]]['content']
    if c:
        by_label[c].add(b)
# контроль: все домены той же зоны, переобход в тот же день
ctrl_sites = collections.defaultdict(list)
for s, v in site.items():
    if v['day']:
        ctrl_sites[(v['day'], v['zone'])].append(s)
ctrl_cache = {}


def ctrl(dd, zone, hours):
    k = (dd, zone, hours)
    if k not in ctrl_cache:
        st = dom_stats(ctrl_sites[(dd, zone)], hours)
        ctrl_cache[k] = st[0] / st[1] if st and st[1] else None
    return ctrl_cache[k]


def base_day(b):
    days = sorted(site[s]['day'] for s in by_base[b] if site[s]['day'])
    return days[len(days) // 2] if days else ''


reps = sorted({site[s]['base'] for s, v in site.items() if v['day'] == day and re.match(r'content-2026-09-1[4-7]', v['content'])})
rows = []
for b in reps:
    c = site[by_base[b][0]]['content']
    origs = sorted(x for x in by_label[c] if x != b and base_day(x) < day)
    if not origs:
        continue
    o = origs[0]
    r = dict(content=c, rep=b, rep_zone=b.rsplit('.', 1)[1], rep_day=base_day(b), orig=o, orig_zone=o.rsplit('.', 1)[1],
             orig_day=base_day(o))
    for h in (24, 48, 72):
        for who, bb in (('rep', b), ('orig', o)):
            st = dom_stats(by_base[bb], h)
            r[f'{who}_i{h}'] = round(100 * st[0] / st[1], 1) if st else ''
            cc = ctrl(r[f'{who}_day'], r[f'{who}_zone'], h)
            r[f'{who}_ctl{h}'] = round(100 * cc, 1) if cc else ''
    for who, bb in (('rep', b), ('orig', o)):
        r[f'{who}_reg'], r[f'{who}_fd'] = money(by_base[bb], 72)
    # весь набор (все экземпляры того же корня) при первом запуске: индекс к своему дню
    root = re.sub(r'_\d+$', '', c)
    rel = []
    for x, ss in by_base.items():
        cx = site[ss[0]]['content']
        if x != b and re.sub(r'_\d+$', '', cx) == root and base_day(x) < day:
            st = dom_stats(ss, 24); cc = ctrl(base_day(x), x.rsplit('.', 1)[1], 24)
            if st and cc:
                rel.append(st[0] / st[1] / cc)
    r['set_n'] = len(rel)
    r['set_rel24'] = round(sum(rel) / len(rel), 2) if rel else ''
    rows.append(r)

P(f'Повторы {day}: доменов {len(rows)}. Клики до {END:%d.%m %H:%M}. Индекс = доля сайтов домена с поисковым кликом.')
P('Контроль дня = индекс всех доменов той же зоны с переобходом в тот же день.')
P(f'\n{"контент (экземпляр)":<38} {"повтор":<15} {"за 24ч":>7} {"день":>6} {"за 48ч":>7} | {"первый":<14} {"за 24ч":>7} {"день":>6} {"за 72ч":>7} {"рег/ФД 3д":>9}')
for r in rows:
    P(f'{r["content"]:<38} {r["rep"]:<15} {str(r["rep_i24"]):>6}% {str(r["rep_ctl24"]):>5}% {str(r["rep_i48"]):>6}% | '
      f'{r["orig"]:<14} {str(r["orig_i24"]):>6}% {str(r["orig_ctl24"]):>5}% {str(r["orig_i72"]):>6}% {r["orig_reg"]:>5}/{r["orig_fd"]}')


def agg(h):
    ok = [r for r in rows if r[f'rep_i{h}'] != '' and r[f'orig_i{h}'] != '' and r[f'rep_ctl{h}'] and r[f'orig_ctl{h}']]
    if not ok:
        return None
    ri = sum(r[f'rep_i{h}'] for r in ok) / len(ok); oi = sum(r[f'orig_i{h}'] for r in ok) / len(ok)
    rc = sum(r[f'rep_ctl{h}'] for r in ok) / len(ok); oc = sum(r[f'orig_ctl{h}'] for r in ok) / len(ok)
    worse = sum(1 for r in ok if r[f'rep_i{h}'] / r[f'rep_ctl{h}'] < r[f'orig_i{h}'] / r[f'orig_ctl{h}'])
    return len(ok), ri, oi, rc, oc, worse


P('\nИтог по парам (среднее по доменам):')
for h in (24, 48):
    a = agg(h)
    if not a:
        P(f'   за {h}ч: окно повторов ещё не закрыто'); continue
    n, ri, oi, rc, oc, worse = a
    sr = [r['set_rel24'] for r in rows if r['set_rel24'] != '' and r[f'rep_i{h}'] != '' and r[f'rep_ctl{h}']]
    rr = [r[f'rep_i{h}'] / r[f'rep_ctl{h}'] for r in rows if r['set_rel24'] != '' and r[f'rep_i{h}'] != '' and r[f'rep_ctl{h}']]
    if h == 24 and sr:
        P(f'   за 24ч, против всего набора: повтор ×{sum(rr)/len(rr):.2f} к своему дню, набор при первом запуске ×{sum(sr)/len(sr):.2f} '
          f'(в среднем по наборам своих пар)')
    P(f'   за {h}ч: пар {n}; повтор {ri:.1f}% при дне {rc:.1f}% (×{ri/rc:.2f}); первый {oi:.1f}% при дне {oc:.1f}% (×{oi/oc:.2f}); '
      f'повтор/первый с поправкой на день ×{(ri/rc)/(oi/oc):.2f}; повтор хуже первого в {worse} из {n}')
tr = sum(r['rep_reg'] for r in rows); tf = sum(r['rep_fd'] for r in rows)
P(f'   деньги повторов на сейчас: рег {tr}, ФД {tf}; у первых запусков за 3 суток: рег {sum(r["orig_reg"] for r in rows)}, '
  f'ФД {sum(r["orig_fd"] for r in rows)}')
with open(csv_p, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
