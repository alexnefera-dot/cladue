#!/usr/bin/env python3
"""Полный прогон: весь план анализа за один раз, один отчёт.

Не выборочные разрезы, а вся батарея из `PLAN_ANALIZA.md` и каталога
`PLAN_PARAMETROV.md` подряд: приёмка, воронка, все срезы уровня базы и уровня
сабдомена, пары, сцепка охвата с деньгами, экономика по ячейкам и холдаут по
периодам для всего, что вышло значимым.

Каждый срез считается **двумя стратами сразу** — по дню и по бренду. Расхождение
между ними и есть проверка на тень бренда: если срез силён по дню и исчезает по
бренду, это бренд, а не срез. Именно так рассыпались волна, позиция, палитра.

    python3 polnyy_analiz.py <панель.jsonl> <subdomains.jsonl>[,…] <конец YYYY-MM-DD>
"""
import sys, json, math, collections, statistics
from datetime import datetime, date

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from or_mh import mh

WINDOW = 6
FD_PAYOUT = 40.0
TLD_PRICE = {'lol': 1, 'team': 2, 'buzz': 3, 'casino': 7, 'top': 2, 'online': 3}


def h1(t):
    print('\n' + '=' * 96)
    print(t)
    print('=' * 96)


def cut(rows, field, outcome, strata, title, min_n=400, top=12):
    """Каждое значение против остальных по каждой из страт."""
    vals = collections.Counter(r.get(field) for r in rows if r.get(field) is not None)
    if not vals:
        return []
    print(f'\n{title}   (поле {field}, {len(vals)} значений)')
    head = f"{'значение':<30}{'n':>8}{'исход':>8}{'доля':>8}"
    for s in strata:
        head += f'{"MH: " + s:>24}'
    print(head)
    out = []
    for v, n in vals.most_common(top):
        if n < min_n:
            continue
        line = f'{str(v)[:29]:<30}{n:>8}'
        hit = sum(r[outcome] for r in rows if r.get(field) == v)
        line += f'{hit:>8}{100.0*hit/n:>7.1f}%'
        res = {}
        for s in strata:
            tbl = collections.defaultdict(lambda: [0, 0, 0, 0])
            for r in rows:
                c = tbl[r[s]]
                y = r[outcome]
                if r.get(field) == v:
                    c[0] += y; c[2] += 1 - y
                else:
                    c[1] += y; c[3] += 1 - y
            orv, lo, hi, p = mh([tuple(x) for x in tbl.values()])
            res[s] = (orv, lo, hi, p)
            line += f'{(f"{orv:.2f} [{lo:.2f}-{hi:.2f}]" if orv else "—"):>24}'
        print(line)
        out.append((field, v, n, hit, res))
    return out


def main(panel, subs_paths, obs_to):
    end = date.fromisoformat(obs_to)
    reg = {}
    for p in subs_paths:
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            reg[r['subdomain'].lower()] = r

    rows = []
    allrows = []
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        s = reg.get(r['subdomain'], {})
        rec = (r.get('recrawl_sent_at') or '')[:10]
        dur = s.get('duration_recrawl_h')
        dc = s.get('domain_created')
        age = None
        if dc and r.get('recrawl_sent_at'):
            hh = (datetime.fromisoformat(r['recrawl_sent_at'])
                  - datetime.fromisoformat(dc)).total_seconds() / 3600
            age = 'до 6 ч' if hh < 6 else '6–24 ч' if hh < 24 else 'больше суток'
        row = {
            'sub': r['subdomain'], 'base': r.get('content_domain_url'),
            'brand': r.get('brand_label'), 'day': rec,
            'y': 1 if r.get('ya_clicks') else 0,
            'clicks': r.get('ya_clicks') or 0,
            'cv': r.get('reg', 0) + r.get('fd', 0),
            'fd': r.get('fd', 0), 'reg': r.get('reg', 0),
            'case': 1 if (r.get('reg') or r.get('fd')) else 0,
            'closed': bool(r.get('window_closed')),
            'stage': r.get('yandex_pipeline_stage'),
            'verif': r.get('verification_status'),
            'content': r.get('content'), 'tld': r.get('tld'),
            'pattern': r.get('base_name_pattern'),
            'label_len': r.get('base_label_len'),
            'oform': r.get('oform_version'), 'pack_kind': s.get('pack_kind'),
            'start_block': r.get('start_block'), 'night': r.get('is_night_kiev'),
            'palette': s.get('css_palette_hash'),
            'wait': (None if dur is None else
                     'до 1 ч' if dur < 1 else '1–12 ч' if dur < 12 else
                     '12–24 ч' if dur < 24 else 'больше суток'),
            'domain_age': age,
            'pages': ('12' if (r.get('content') or '').lower().count('12page')
                      or '12стр' in (r.get('content') or '').lower()
                      or '12str' in (r.get('content') or '').lower() else
                      '7' if ('7page' in (r.get('content') or '').lower()
                              or '7str' in (r.get('content') or '').lower()
                              or '7стр' in (r.get('content') or '').lower()) else None),
        }
        allrows.append(row)
        if row['closed'] and row['day']:
            rows.append(row)

    h1('1 · ПРИЁМКА И ВЫБОРКА')
    print(f'сабдоменов всего {len(allrows)}, с закрытым окном {len(rows)} '
          f'({100.0*len(rows)/len(allrows):.1f}%)')
    print(f'баз {len({r["base"] for r in allrows if r["base"]})}, '
          f'брендов {len({r["brand"] for r in allrows if r["brand"]})}')
    print(f'вышли в поиск (закрытые окна): {sum(r["y"] for r in rows)}')
    print(f'регистраций {sum(r["reg"] for r in rows)}, ФД {sum(r["fd"] for r in rows)}, '
          f'случаев (база с конверсией) {sum(r["case"] for r in rows)}')
    op = [r for r in allrows if not r['closed']]
    print(f'ОКНО НЕ ЗАКРЫТО: {len(op)} сабдоменов, в них {sum(r["case"] for r in op)} '
          f'конверсий — переснять на следующем расчёте')

    h1('2 · ВОРОНКА ОТ ЗАПУСКА ДО ДЕПОЗИТА')
    n = len(rows)
    ver = sum(1 for r in rows if r['verif'] == 'VERIFIED')
    done = sum(1 for r in rows if r['stage'] == 'done')
    got = sum(r['y'] for r in rows)
    cl = sum(r['clicks'] for r in rows)
    rg = sum(r['reg'] for r in rows)
    fd = sum(r['fd'] for r in rows)
    steps = [('сабдоменов с закрытым окном', n, None),
             ('верификация пройдена', ver, n),
             ('пайплайн done', done, ver),
             ('есть клик из поиска', got, done),
             ('поисковых кликов', cl, None),
             ('регистраций', rg, got),
             ('ФД', fd, rg)]
    print(f"{'этап':<34}{'штук':>12}{'от предыдущего':>18}")
    for name, v, base in steps:
        pct = f'{100.0*v/base:.3f}%' if base else ''
        print(f'{name:<34}{v:>12}{pct:>18}')
    print(f'\nна одну базу: кликов {cl/max(len({r["base"] for r in rows}),1):.0f}, '
          f'регистраций {rg/max(len({r["base"] for r in rows}),1):.2f}, '
          f'ФД {fd/max(len({r["base"] for r in rows}),1):.3f}')

    h1('3 · СРЕЗЫ УРОВНЯ БАЗЫ · исход «вышел в поиск» · страты: день и бренд')
    sig = []
    for f, t in (('pages', 'ЧИСЛО СТРАНИЦ В ИМЕНИ ПАКА'),
                 ('pack_kind', 'ВИД ПАКА (поле API)'),
                 ('tld', 'ЗОНА'),
                 ('pattern', 'ТИП ИМЕНИ БАЗЫ'),
                 ('label_len', 'ДЛИНА ИМЕНИ БАЗЫ'),
                 ('oform', 'ВЕРСИЯ ОФОРМЛЕНИЯ'),
                 ('start_block', 'БЛОК ЧАСА СТАРТА'),
                 ('night', 'НОЧНОЙ СТАРТ'),
                 ('domain_age', 'ВОЗРАСТ ДОМЕНА К ПЕРЕОБХОДУ')):
        sig += cut(rows, f, 'y', ['day', 'brand'], t)

    h1('4 · СРЕЗЫ УРОВНЯ САБДОМЕНА · страты: база и бренд')
    print('расхождение между стратами и есть проверка на тень бренда')
    for f, t in (('wait', 'ОЖИДАНИЕ ПЕРЕД ПЕРЕОБХОДОМ'),
                 ('palette', 'ПАЛИТРА ОФОРМЛЕНИЯ')):
        cut(rows, f, 'y', ['base', 'brand'], t, top=6)

    h1('5 · ТЕ ЖЕ СРЕЗЫ НА ИСХОДЕ «ЕСТЬ КОНВЕРСИЯ»')
    for f, t in (('pages', 'ЧИСЛО СТРАНИЦ'), ('tld', 'ЗОНА'),
                 ('pattern', 'ТИП ИМЕНИ'), ('wait', 'ОЖИДАНИЕ')):
        cut(rows, f, 'case', ['day'], t, top=8)

    h1('6 · ХОЛДАУТ ПО ПЕРИОДАМ')
    print('всё, что вышло значимым, пересчитано на трёх отрезках отдельно')
    per = [('17–31.08', '2026-08-17', '2026-08-31'),
           ('01–09.09', '2026-09-01', '2026-09-09'),
           ('10–18.09', '2026-09-10', '2026-09-18')]
    checks = [('pages', '12'), ('pattern', 'numeric'), ('pattern', 'casino_prefix'),
              ('tld', 'casino'), ('wait', 'до 1 ч'), ('wait', 'больше суток')]
    print(f"{'признак':<28}" + ''.join(f'{p[0]:>22}' for p in per))
    for f, v in checks:
        line = f'{f + " = " + str(v):<28}'
        for _, a, b in per:
            sel = [r for r in rows if a <= r['day'] <= b]
            tbl = collections.defaultdict(lambda: [0, 0, 0, 0])
            for r in sel:
                c = tbl[r['day']]
                y = r['y']
                if r.get(f) == v:
                    c[0] += y; c[2] += 1 - y
                else:
                    c[1] += y; c[3] += 1 - y
            orv, lo, hi, p = mh([tuple(x) for x in tbl.values()])
            line += f'{(f"{orv:.2f}" if orv else "—"):>22}'
        print(line)

    h1('7 · ПАРЫ ПРИЗНАКОВ')
    feats = [('12 страниц', lambda r: r['pages'] == '12'),
             ('имя numeric', lambda r: r['pattern'] == 'numeric'),
             ('зона lol', lambda r: r['tld'] == 'lol'),
             ('отправлен за час', lambda r: r['wait'] == 'до 1 ч')]
    print(f"{'сочетание':<44}{'n':>9}{'вышли':>8}{'доля':>8}{'OR к «ни того, ни другого»':>28}")
    for i in range(len(feats)):
        for j in range(i + 1, len(feats)):
            (n1, f1), (n2, f2) = feats[i], feats[j]
            both = [r for r in rows if f1(r) and f2(r)]
            none = [r for r in rows if not f1(r) and not f2(r)]
            if len(both) < 300 or len(none) < 300:
                continue
            tbl = collections.defaultdict(lambda: [0, 0, 0, 0])
            for r in both:
                c = tbl[r['day']]; c[0] += r['y']; c[2] += 1 - r['y']
            for r in none:
                c = tbl[r['day']]; c[1] += r['y']; c[3] += 1 - r['y']
            orv, lo, hi, p = mh([tuple(x) for x in tbl.values()])
            hit = sum(r['y'] for r in both)
            print(f'{n1 + " + " + n2:<44}{len(both):>9}{hit:>8}{100.0*hit/len(both):>7.1f}%'
                  f'{(f"{orv:.2f} [{lo:.2f}-{hi:.2f}]" if orv else "—"):>28}')

    h1('8 · СЦЕПКА ОХВАТА С ДЕНЬГАМИ')
    byb = collections.defaultdict(lambda: [0, 0, 0, 0])
    for r in rows:
        c = byb[r['base']]
        c[0] += 1; c[1] += r['y']; c[2] += r['reg']; c[3] += r['fd']
    bands = collections.defaultdict(lambda: [0, 0, 0, 0])
    for b, c in byb.items():
        if c[0] < 100:
            continue
        share = c[1] / c[0]
        k = ('до 5%' if share < .05 else '5–10%' if share < .10 else
             '10–20%' if share < .20 else '20–35%' if share < .35 else 'больше 35%')
        z = bands[k]
        z[0] += 1; z[1] += c[1]; z[2] += c[2]; z[3] += c[3]
    print(f"{'доля сабдоменов в выдаче':<26}{'баз':>6}{'рег/база':>11}{'ФД/база':>10}")
    for k in ('до 5%', '5–10%', '10–20%', '20–35%', 'больше 35%'):
        z = bands[k]
        if not z[0]:
            continue
        print(f'{k:<26}{z[0]:>6}{z[2]/z[0]:>11.2f}{z[3]/z[0]:>10.3f}')

    h1('9 · ЭКОНОМИКА ПО ЯЧЕЙКАМ')
    rate_r = sum(r['reg'] for r in rows)
    rate_f = sum(r['fd'] for r in rows)
    rate = rate_f / max(rate_r, 1)
    print(f'ставка ФД на выборке: {rate:.3f}; доход с регистрации {rate*FD_PAYOUT:.2f} $')
    cells = collections.defaultdict(lambda: [set(), 0, 0])
    for r in rows:
        k = (r['pages'] or 'прочее', r['tld'])
        c = cells[k]
        c[0].add(r['base']); c[1] += r['reg']; c[2] += r['fd']
    print(f"{'страниц':<10}{'зона':<9}{'баз':>6}{'рег':>6}{'ФД':>5}"
          f"{'рег/база':>11}{'цена':>7}{'маржа':>9}")
    res = []
    for (pg, tld), c in cells.items():
        nb = len(c[0])
        if nb < 15:
            continue
        rpb = c[1] / nb
        price = TLD_PRICE.get(tld, 2)
        res.append((rpb * rate * FD_PAYOUT - price, pg, tld, nb, c[1], c[2], rpb, price))
    for m, pg, tld, nb, rr, ff, rpb, price in sorted(res, reverse=True):
        print(f'{pg:<10}{str(tld):<9}{nb:>6}{rr:>6}{ff:>5}{rpb:>11.2f}${price:>6}'
              f'{m:>+9.2f}')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2].split(','), sys.argv[3])
