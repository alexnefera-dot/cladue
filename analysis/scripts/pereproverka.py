#!/usr/bin/env python3
"""Перепроверка выводов, не попавших в полный прогон.

Полный прогон (`polnyy_analiz.py`) пересмотрел срезы уровня базы и сабдомена.
Здесь — всё остальное, что было объявлено выводом: бренды, источники трафика,
тренды, переиспользование пака, «пакет бренда», аккаунты. Проверка везде одна и
та же: **разбить на периоды и посмотреть, держится ли**, а где возможно —
ранжировать на одном периоде и мерить на другом, чтобы отбор не подгонял сам
себя.

    python3 pereproverka.py <панель.jsonl> <subdomains.jsonl>[,…]
                            <kto.json> <kto_ids.json> <days.json> <конец>
"""
import sys, json, math, collections, statistics
from datetime import date, timedelta

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from or_mh import mh

PERIODS = [('17–31.08', '2026-08-17', '2026-08-31'),
           ('01–09.09', '2026-09-01', '2026-09-09'),
           ('10–18.09', '2026-09-10', '2026-09-18')]


def h(t):
    print('\n' + '=' * 92)
    print(t)
    print('=' * 92)


def spearman(a, b):
    """Ранговая корреляция без внешних библиотек."""
    common = [k for k in a if k in b]
    if len(common) < 8:
        return None
    ra = {k: i for i, k in enumerate(sorted(common, key=lambda k: a[k]))}
    rb = {k: i for i, k in enumerate(sorted(common, key=lambda k: b[k]))}
    n = len(common)
    d2 = sum((ra[k] - rb[k]) ** 2 for k in common)
    return 1 - 6 * d2 / (n * (n * n - 1))


def main(panel, subs_paths, kto, kto_ids, days_path, obs_to):
    rows = []
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        if not r.get('window_closed'):
            continue
        d = (r.get('recrawl_sent_at') or '')[:10]
        if not d:
            continue
        rows.append({'brand': r.get('brand_label'), 'base': r.get('content_domain_url'),
                     'day': d, 'y': 1 if r.get('ya_clicks') else 0,
                     'cv': r.get('reg', 0) + r.get('fd', 0),
                     'content': r.get('content')})

    # ---------- 1. устойчив ли рейтинг брендов ----------
    h('1 · РЕЙТИНГ БРЕНДОВ: держится ли порядок между периодами')
    reach = {}
    for name, a, b in PERIODS:
        sel = [r for r in rows if a <= r['day'] <= b]
        g = collections.defaultdict(lambda: [0, 0])
        for r in sel:
            c = g[r['brand']]
            c[0] += r['y']; c[1] += 1
        reach[name] = {k: v[0] / v[1] for k, v in g.items() if v[1] >= 100}
        print(f'  {name}: брендов с ≥100 сабдоменами — {len(reach[name])}')
    ns = [p[0] for p in PERIODS]
    for i in range(len(ns) - 1):
        rho = spearman(reach[ns[i]], reach[ns[i + 1]])
        print(f'  ранговая корреляция {ns[i]} против {ns[i+1]}: '
              f'{rho:.3f}' if rho is not None else '  мало данных')
    rho = spearman(reach[ns[0]], reach[ns[-1]])
    print(f'  ранговая корреляция {ns[0]} против {ns[-1]}: {rho:.3f}')
    a1 = reach[ns[0]]
    top = sorted(a1, key=lambda k: -a1[k])[:25]
    bot = sorted(a1, key=lambda k: a1[k])[:25]
    last = reach[ns[-1]]
    print(f'  верхние 25 брендов первого периода в последнем: '
          f'{100*statistics.mean(last[k] for k in top if k in last):.1f}% выхода')
    print(f'  нижние 25 брендов первого периода в последнем: '
          f'{100*statistics.mean(last[k] for k in bot if k in last):.1f}% выхода')

    # ---------- 2. «редкие бренды конвертят лучше» ----------
    h('2 · «ЧЕМ РЕЖЕ БРЕНД ВЫХОДИТ, ТЕМ ЛУЧШЕ КОНВЕРТИТ»')
    print('ранг считается на первом периоде, конверсия меряется на последнем —')
    print('иначе отбор подгоняет сам себя')
    order = sorted(a1, key=lambda k: -a1[k])
    late = [r for r in rows if PERIODS[-1][1] <= r['day'] <= PERIODS[-1][2]]
    g = collections.defaultdict(lambda: [0, 0, 0])
    for r in late:
        if r['brand'] not in a1:
            continue
        rank = order.index(r['brand'])
        k = ('1–25' if rank < 25 else '26–75' if rank < 75 else
             '76–150' if rank < 150 else '151+')
        c = g[k]
        c[0] += 1; c[1] += r['y']; c[2] += r['cv']
    print(f"{'группа по рангу':<16}{'сабдом.':>9}{'вышли':>8}{'конв':>6}"
          f"{'конв на 1000 вышедших':>24}")
    for k in ('1–25', '26–75', '76–150', '151+'):
        c = g[k]
        if not c[0]:
            continue
        print(f'{k:<16}{c[0]:>9}{c[1]:>8}{c[2]:>6}'
              f'{1000.0*c[2]/max(c[1],1):>24.1f}')

    # ---------- 3. источники трафика по периодам ----------
    h('3 · ИСТОЧНИКИ ТРАФИКА: держатся ли доли конверсии')
    ids = json.load(open(kto_ids, encoding='utf-8'))
    conv = collections.defaultdict(lambda: collections.Counter())
    for line in open('analysis/export/tracker_conversions.jsonl', encoding='utf-8'):
        c = json.loads(line)
        k = ids.get(c['clickid'])
        if not k:
            continue
        conv[c['at'][:7]][k[0]] += 1
    print(f"{'источник':<18}" + ''.join(f'{m:>12}' for m in sorted(conv)))
    srcs = sorted({s for m in conv.values() for s in m}, key=lambda s: -sum(
        conv[m][s] for m in conv))
    for s in srcs[:9]:
        print(f'{s:<18}' + ''.join(f'{conv[m][s]:>12}' for m in sorted(conv)))
    bots = sum(1 for v in ids.values() if v[2])
    botconv = sum(1 for line in open('analysis/export/tracker_conversions.jsonl',
                                     encoding='utf-8')
                  if (lambda k: k and k[2])(ids.get(json.loads(line)['clickid'])))
    print(f'\n  кликов с флагом бота: {bots}; конверсий на них: {botconv}')

    # ---------- 4. переиспользование пака со стратой ----------
    h('4 · ПЕРЕИСПОЛЬЗОВАНИЕ ПАКА, теперь со стратой по дню')
    byc = collections.defaultdict(list)
    first = {}
    for r in rows:
        if r['content'] and r['base'] and (r['base'] not in first
                                           or r['day'] < first[r['base']]):
            first[r['base']] = r['day']
    seenb = {}
    for r in rows:
        if r['content'] and r['base']:
            seenb[r['base']] = r['content']
    for b, c in seenb.items():
        byc[c].append((first.get(b, '9999'), b))
    seq = {}
    for c, lst in byc.items():
        for i, (t, b) in enumerate(sorted(lst)):
            seq[b] = i + 1
    g = collections.defaultdict(lambda: [0, 0, 0])
    tbl_rows = []
    for r in rows:
        s = seq.get(r['base'])
        if not s:
            continue
        k = '1-я' if s == 1 else '2–3-я' if s <= 3 else '4–6-я' if s <= 6 else '7+'
        c = g[k]
        c[0] += 1; c[1] += r['y']; c[2] += r['cv']
        tbl_rows.append((k, r['day'], r['y']))
    print(f"{'какая по счёту':<16}{'сабдом.':>9}{'доля':>8}{'конв':>6}{'MH по дню':>22}")
    for k in ('1-я', '2–3-я', '4–6-я', '7+'):
        c = g[k]
        if not c[0]:
            continue
        t = collections.defaultdict(lambda: [0, 0, 0, 0])
        for kk, d, y in tbl_rows:
            z = t[d]
            if kk == k:
                z[0] += y; z[2] += 1 - y
            else:
                z[1] += y; z[3] += 1 - y
        orv, lo, hi, p = mh([tuple(x) for x in t.values()])
        print(f'{k:<16}{c[0]:>9}{100.0*c[1]/c[0]:>7.1f}%{c[2]:>6}'
              f'{(f"{orv:.2f} [{lo:.2f}-{hi:.2f}]" if orv else "—"):>22}')

    # ---------- 5. пакет бренда на всём реестре ----------
    h('5 · «ПАКЕТ БРЕНДА» на всём реестре, а не на одной выгрузке')
    reg = {}
    for p in subs_paths:
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            reg[r['subdomain'].lower()] = r
    fields = ['css_palette_hash', 'keywords_len', 'contrast_body_text', 'sub_len',
              'ref_link_slug', 'api_form', 'popup', 'established_year']
    pb = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in reg.values():
        b = r.get('brand_label')
        for f in fields:
            if r.get(f) is not None:
                pb[f][b].add(str(r.get(f)))
    print(f"{'поле':<24}{'брендов':>9}{'макс. значений внутри бренда':>32}")
    for f in fields:
        if not pb[f]:
            continue
        mx = max(len(v) for v in pb[f].values())
        print(f'{f:<24}{len(pb[f]):>9}{mx:>32}')

    # ---------- 6. тренды на свежих данных ----------
    h('6 · ТРЕНДЫ: падение отдачи и вклад свежих баз')
    days = json.load(open(days_path, encoding='utf-8'))
    recb = {}
    for r in reg.values():
        b = r.get('content_domain_url')
        t = (r.get('recrawl_sent_at') or '')[:10]
        if b and t and (b not in recb or t < recb[b]):
            recb[b] = t
    end = date.fromisoformat(obs_to)
    w = collections.defaultdict(lambda: [0, 0])
    age_share = collections.defaultdict(lambda: [0, 0])
    for b, ser in days.items():
        t = recb.get(b)
        if not t:
            continue
        rec = date.fromisoformat(t)
        if (end - rec).days >= 7:
            s7 = sum(v[1] for k, v in ser.items()
                     if 0 <= (date.fromisoformat(k) - rec).days <= 6)
            c = w[rec - timedelta(days=rec.weekday())]
            c[0] += 1; c[1] += s7
        for k, v in ser.items():
            d = date.fromisoformat(k)
            age = (d - rec).days
            z = age_share[d - timedelta(days=d.weekday())]
            z[0] += v[1]
            if 0 <= age <= 3:
                z[1] += v[1]
    print(f"{'неделя':<12}{'баз':>6}{'поисковых на базу':>20}{'доля трафика от баз 0–3 сут.':>32}")
    for k in sorted(w):
        c = w[k]
        z = age_share.get(k, [0, 0])
        share = f'{100.0*z[1]/z[0]:.1f}%' if z[0] else '—'
        print(f'{k.isoformat():<12}{c[0]:>6}{c[1]/c[0]:>20.0f}{share:>32}')


if __name__ == '__main__':
    if len(sys.argv) < 7:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2].split(','), sys.argv[3], sys.argv[4],
         sys.argv[5], sys.argv[6])
