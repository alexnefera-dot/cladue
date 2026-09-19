#!/usr/bin/env python3
"""Четыре вопроса, которые ни разу не считались.

1. **Разложение по уровням.** Сколько разброса исхода сидит на уровне бренда,
   сколько на уровне базы, сколько не объясняется ничем. До сих пор мерились
   отдельные факторы, но не доли — а именно доли говорят, где рычаг.
2. **Конверсия при условии выхода в выдачу.** Воронка показала, что вся потеря
   на входе в выдачу. Если после выхода факторы уже ничего не меняют, значит
   вся настройка сети сводится к охвату — и это надо проверить, а не
   предположить.
3. **Интенсивность вместо доли.** Везде исходом было «вышел или нет». Сколько
   кликов получает вышедший — другой вопрос, ближе к позиции в выдаче.
4. **Возраст: деньги против кликов.** Клики оседают к восьмым суткам. Оседают
   ли конверсии так же быстро — от этого зависит, верно ли выбрано окно.

    python3 nedochet.py <панель.jsonl> <days.json> <карта.jsonl> <конец>
"""
import sys, json, math, collections, statistics
from datetime import date, timedelta

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from or_mh import mh


def h(t):
    print('\n' + '=' * 92)
    print(t)
    print('=' * 92)


def between_share(groups, p_all):
    """Доля разброса, объяснённая уровнем.

    Наблюдаемая дисперсия групповых долей завышена на шум выборки, поэтому из
    неё вычитается средний p(1-p)/n. Иначе уровень с мелкими группами всегда
    «объясняет» больше — ровно та ошибка, из-за которой мелкие паки казались
    выдающимися.
    """
    gs = [(k, v) for k, v in groups.items() if v[1] >= 30]
    if len(gs) < 5:
        return None
    rates = [v[0] / v[1] for _, v in gs]
    w = sum(v[1] for _, v in gs)
    mean = sum(v[0] for _, v in gs) / w
    obs = sum(v[1] * (v[0] / v[1] - mean) ** 2 for _, v in gs) / w
    noise = sum(v[1] * (v[0] / v[1]) * (1 - v[0] / v[1]) / v[1]
                for _, v in gs) / w
    true = max(obs - noise, 0.0)
    return true / (p_all * (1 - p_all)), len(gs)


def main(panel, days_path, map_path, obs_to):
    rows = []
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        if not r.get('window_closed'):
            continue
        d = (r.get('recrawl_sent_at') or '')[:10]
        if not d:
            continue
        rows.append({
            'brand': r.get('brand_label'), 'base': r.get('content_domain_url'),
            'day': d, 'y': 1 if r.get('ya_clicks') else 0,
            'clicks': r.get('ya_clicks') or 0,
            'cv': r.get('reg', 0) + r.get('fd', 0),
            'tld': r.get('tld'), 'pattern': r.get('base_name_pattern'),
            'content': r.get('content'),
            'pages': ('12' if any(x in (r.get('content') or '').lower()
                                  for x in ('12page', '12стр', '12str')) else
                      '7' if any(x in (r.get('content') or '').lower()
                                 for x in ('7page', '7стр', '7str')) else None),
        })
    p_all = sum(r['y'] for r in rows) / len(rows)
    print(f'сабдоменов {len(rows)}, доля вышедших {100*p_all:.1f}%')

    # ---------- 1 ----------
    h('1 · РАЗЛОЖЕНИЕ РАЗБРОСА ПО УРОВНЯМ')
    print('доля дисперсии исхода «вышел в поиск», объяснённая уровнем,')
    print('после вычета шума выборки')
    levels = {
        'бренд': lambda r: r['brand'],
        'база': lambda r: r['base'],
        'день переобхода': lambda r: r['day'],
        'пак контента': lambda r: r['content'],
        'зона': lambda r: r['tld'],
        'тип имени базы': lambda r: r['pattern'],
    }
    print(f"{'уровень':<20}{'групп':>8}{'доля разброса':>16}")
    for name, key in levels.items():
        g = collections.defaultdict(lambda: [0, 0])
        for r in rows:
            k = key(r)
            if k is None:
                continue
            c = g[k]
            c[0] += r['y']; c[1] += 1
        res = between_share(g, p_all)
        if res:
            share, n = res
            print(f'{name:<20}{n:>8}{100*share:>15.1f}%')
    print('\nуровни не складываются в 100%: они вложены друг в друга')
    print('(база несёт зону, пак и день), поэтому читать надо порядок, а не сумму')

    # ---------- 2 ----------
    h('2 · КОНВЕРСИЯ ПРИ УСЛОВИИ, ЧТО САБДОМЕН УЖЕ ВЫШЕЛ В ВЫДАЧУ')
    got = [r for r in rows if r['y']]
    print(f'вышедших сабдоменов {len(got)}, конверсий на них {sum(r["cv"] for r in got)}')
    print(f'конверсия среди вышедших: {100.0*sum(1 for r in got if r["cv"])/len(got):.3f}%')
    print('\nесли факторы тут ничего не меняют — вся настройка сети сводится к охвату')
    print(f"{'срез':<16}{'значение':<18}{'вышедших':>10}{'конверсий':>11}{'OR по дню':>22}")
    for field, vals in (('pages', ('12', '7')),
                        ('tld', ('team', 'lol', 'casino')),
                        ('pattern', ('numeric', 'alpha_other', 'casino_prefix'))):
        for v in vals:
            sel = [r for r in got if r.get(field) == v]
            if len(sel) < 300:
                continue
            tbl = collections.defaultdict(lambda: [0, 0, 0, 0])
            for r in got:
                c = tbl[r['day']]
                y = 1 if r['cv'] else 0
                if r.get(field) == v:
                    c[0] += y; c[2] += 1 - y
                else:
                    c[1] += y; c[3] += 1 - y
            orv, lo, hi, p = mh([tuple(x) for x in tbl.values()])
            print(f'{field:<16}{str(v):<18}{len(sel):>10}'
                  f'{sum(r["cv"] for r in sel):>11}'
                  f'{(f"{orv:.2f} [{lo:.2f}-{hi:.2f}]" if orv else "—"):>22}')

    # ---------- 3 ----------
    h('3 · ИНТЕНСИВНОСТЬ: сколько кликов получает вышедший сабдомен')
    print('медиана, а не среднее: распределение с длинным хвостом')
    print(f"{'срез':<16}{'значение':<18}{'вышедших':>10}{'медиана кликов':>16}{'среднее':>10}")
    for field, vals in (('pages', ('12', '7')),
                        ('tld', ('team', 'lol', 'casino', 'buzz')),
                        ('pattern', ('numeric', 'alpha_other', 'casino_prefix'))):
        for v in vals:
            sel = [r['clicks'] for r in got if r.get(field) == v]
            if len(sel) < 300:
                continue
            print(f'{field:<16}{str(v):<18}{len(sel):>10}'
                  f'{statistics.median(sel):>16.0f}{statistics.mean(sel):>10.0f}')

    # ---------- 4 ----------
    h('4 · ВОЗРАСТ: КЛИКИ ПРОТИВ ДЕНЕГ')
    days = json.load(open(days_path, encoding='utf-8'))
    rec = {}
    for line in open(map_path, encoding='utf-8'):
        sub, b, cd, brand, r_, st, pg, tld, stage = json.loads(line)
        t = (r_ or st or '')[:10]
        if b and t and (b not in rec or t < rec[b]):
            rec[b] = t
    end = date.fromisoformat(obs_to)
    cl_age = collections.Counter()
    risk = collections.Counter()
    for b, ser in days.items():
        t = rec.get(b)
        if not t:
            continue
        r0 = date.fromisoformat(t)
        obs = (end - r0).days
        for a in range(0, 22):
            if a <= obs:
                risk[a] += 1
        for k, v in ser.items():
            a = (date.fromisoformat(k) - r0).days
            if 0 <= a <= 21:
                cl_age[a] += v[1]
    cv_age = collections.Counter()
    for line in open('analysis/export/tracker_conversions.jsonl', encoding='utf-8'):
        c = json.loads(line)
        s = (c.get('subdomain') or '').lower()
        if s.count('.') < 2:
            continue
        b = '.'.join(s.split('.')[-2:])
        t = rec.get(b)
        if not t:
            continue
        a = (date.fromisoformat(c['at'][:10]) - date.fromisoformat(t)).days
        if 0 <= a <= 21:
            cv_age[a] += 1
    tot_c = sum(cl_age.values())
    tot_v = sum(cv_age.values())
    print(f'кликов в окне 22 суток {tot_c}, конверсий {tot_v}')
    print(f"{'сутки':>6}{'баз в риске':>13}{'кликов на базу':>16}{'доля кликов':>13}"
          f"{'конверсий':>11}{'доля конверсий':>16}")
    ccl = ccv = 0.0
    for a in range(0, 22):
        if not risk[a]:
            continue
        ccl += 100.0 * cl_age[a] / tot_c
        ccv += 100.0 * cv_age[a] / max(tot_v, 1)
        print(f'{a:>6}{risk[a]:>13}{cl_age[a]/risk[a]:>16.0f}'
              f'{100.0*cl_age[a]/tot_c:>12.1f}%{cv_age[a]:>11}'
              f'{100.0*cv_age[a]/max(tot_v,1):>15.1f}%')
    print(f'\nнакоплено к 6-м суткам: кликов {sum(100.0*cl_age[a]/tot_c for a in range(7)):.1f}%, '
          f'конверсий {sum(100.0*cv_age[a]/max(tot_v,1) for a in range(7)):.1f}%')


if __name__ == '__main__':
    if len(sys.argv) < 5:
        raise SystemExit(__doc__)
    main(*sys.argv[1:5])
