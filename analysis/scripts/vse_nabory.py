#!/usr/bin/env python3
"""Все наборы контента без исключений — и удачные, и пустые, и мелкие.

Прежние таблицы резались порогом по числу сайтов, и из-за этого выпадали
как раз те наборы, про которые важно знать, что они не сработали. Здесь
выводятся **все**, включая те, где данных заведомо мало, — но с явной пометкой,
сколько регистраций следовало ожидать.

Ожидание считается по ставке **дня запуска** каждой базы: в августе сеть давала
вдвое больше регистраций на сайт, чем в сентябре, и без этой поправки старые
наборы выглядят лучше просто потому, что старые.

Ноль регистраций при ожидаемых 0.4 и ноль при ожидаемых 8.6 — разные вещи.
Первое ничего не значит, второе значит.

Свежие запуски идут в расчёт наравне с остальными: в колонке «свежих» видно,
у скольких сайтов окно ещё не закрылось. Поправка на день делает их сравнимыми
с прочими — ставка их собственного дня уже низкая именно потому, что они свежие.

    python3 vse_nabory.py <панель.jsonl> <subdomains.jsonl>[,…] <выход.csv>
"""
import sys, json, re, csv, collections


def family(inst, fallback):
    if inst:
        return re.sub(r'[_\-]\d+$', '', inst)
    return fallback


def main(panel, subs_paths, out_csv):
    api = {}
    for p in subs_paths:
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            if r.get('content_label'):
                api[r['subdomain'].lower()] = r['content_label']

    rows = []
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        b = r.get('content_domain_url')
        if not d or not b:
            continue
        rows.append({
            'fam': family(api.get(r['subdomain']), r.get('content')) or 'ПАК НЕИЗВЕСТЕН',
            'base': b, 'day': d, 'tld': r.get('tld'),
            'ya': 1 if r.get('ya_clicks') else 0, 'clicks': r.get('ya_clicks') or 0,
            'reg': r.get('reg', 0), 'fd': r.get('fd', 0),
            'fresh': 0 if r.get('window_closed') else 1,
        })

    day = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        t = day[r['day']]
        t[0] += 1
        t[1] += r['reg']

    g = collections.defaultdict(lambda: {'bases': set(), 'n': 0, 'ya': 0, 'cl': 0,
                                         'reg': 0, 'fd': 0, 'exp': 0.0, 'fresh': 0,
                                         'days': set(), 'tld': collections.Counter()})
    for r in rows:
        t = g[r['fam']]
        t['bases'].add(r['base']); t['n'] += 1; t['ya'] += r['ya']
        t['cl'] += r['clicks']; t['reg'] += r['reg']; t['fd'] += r['fd']
        t['days'].add(r['day']); t['tld'][r['tld']] += 1; t['fresh'] += r['fresh']
        d = day[r['day']]
        t['exp'] += (d[1] / d[0]) if d[0] else 0

    def verdict(t):
        if t['reg'] == 0:
            if t['exp'] >= 3:
                return 'ПУСТОЙ: ноль при ожидаемых %.1f' % t['exp']
            return 'мало данных'
        if t['exp'] < 2:
            return 'мало данных'
        k = t['reg'] / t['exp']
        if k >= 1.8:
            return 'лучше ожидаемого в %.1f раза' % k
        if k <= 0.55:
            return 'хуже ожидаемого в %.1f раза' % (1 / k)
        return 'как ожидалось'

    order = sorted(g.items(), key=lambda kv: (-kv[1]['reg'], -kv[1]['n']))
    with open(out_csv, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['набор', 'баз', 'сайтов', 'свежих', 'дней', 'зоны', 'вышли в поиск',
                    'поисковых кликов', 'регистраций', 'ФД',
                    'кликов на регистрацию', 'ожидалось регистраций', 'вердикт'])
        for name, t in order:
            w.writerow([name, len(t['bases']), t['n'], t['fresh'], len(t['days']),
                        '/'.join(f'{z}:{n}' for z, n in t['tld'].most_common(3)),
                        t['ya'], t['cl'], t['reg'], t['fd'],
                        round(t['cl'] / t['reg']) if t['reg'] else '',
                        round(t['exp'], 1), verdict(t)])

    print(f'наборов всего: {len(g)}')
    print(f'сайтов в расчёте: {len(rows)}, регистраций {sum(t["reg"] for t in g.values())}')
    print(f'-> {out_csv}\n')
    print(f"{'набор':<40}{'баз':>4}{'сайтов':>8}{'свеж':>6}{'поиск':>7}{'кликов':>8}"
          f"{'рег':>4}{'ФД':>3}{'кл/рег':>8}{'ожид':>6}  вердикт")
    for name, t in order:
        print(f'{name[:39]:<40}{len(t["bases"]):>4}{t["n"]:>8}{t["fresh"]:>6}{t["ya"]:>7}{t["cl"]:>8}'
              f'{t["reg"]:>4}{t["fd"]:>3}'
              f'{(str(round(t["cl"]/t["reg"])) if t["reg"] else "—"):>8}'
              f'{t["exp"]:>6.1f}  {verdict(t)}')

    print()
    pust = [(n, t) for n, t in order if t['reg'] == 0 and t['exp'] >= 3]
    print(f'НАБОРЫ, НЕ ДАВШИЕ НИ ОДНОЙ РЕГИСТРАЦИИ ПРИ ОЖИДАЕМЫХ ТРЁХ И БОЛЬШЕ: {len(pust)}')
    print(f'  сайтов на них {sum(t["n"] for _, t in pust)}, '
          f'поисковых кликов {sum(t["cl"] for _, t in pust)}, '
          f'ожидалось регистраций {sum(t["exp"] for _, t in pust):.0f}')
    malo = [(n, t) for n, t in order if verdict(t) == 'мало данных']
    print(f'НАБОРОВ, ПО КОТОРЫМ СУДИТЬ НЕЛЬЗЯ (ожидалось меньше двух регистраций): {len(malo)}')
    print(f'  сайтов на них {sum(t["n"] for _, t in malo)}')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2].split(','), sys.argv[3])
