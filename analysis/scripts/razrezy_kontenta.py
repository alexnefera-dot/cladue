#!/usr/bin/env python3
"""Каждая группа контента в разрезе зоны, аккаунта и часа запуска.

Общая цифра по группе — среднее нескольких разных ситуаций: один и тот же
контент лежит в двух зонах, на свежих и повторных аккаунтах, уходит в разные
часы. Здесь эти ситуации разложены.

Единица строки — сочетание «контент × зона × аккаунт × блок часа». Рядом
отдельные срезы: контент × зона, контент × аккаунт, контент × час — чтобы
каждый можно было смотреть без дробления объёма.

Успешные и неуспешные группы разбираются порознь: у первых вопрос «почему
получилось», у вторых «на чём сломалось», и смешивать их в одну таблицу
бессмысленно.

Метрики: выход в поиск за трое суток (что решает 86% потерь) и регистрации
в том же окне.

    python3 razrezy_kontenta.py <панель.jsonl> <окно3.jsonl> <аккаунты.jsonl>
                                <выход.csv>
"""
import sys, json, re, csv, collections, datetime

EDGE = '2026-09-18'          # у запусков позже окно трёх суток не закрыто


def block(h):
    if h is None:
        return None
    return '00-05' if h < 6 else '06-11' if h < 12 else '12-17' if h < 18 else '18-23'


def main(panel, oknopath, accpath, out):
    W = {}
    for line in open(oknopath, encoding='utf-8'):
        a = json.loads(line)
        W[a[0]] = a[1:]
    acc = {}
    for line in open(accpath, encoding='utf-8'):
        a = json.loads(line)
        acc[a[0]] = a[1]

    rows, bd = [], collections.defaultdict(set)
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        b = r.get('content_domain_url')
        if not d or not b or d > EDGE:
            continue
        bd[b].add(d)
        w = W.get(r['subdomain'], [0, 0, 0, 0, 0])
        h = r.get('recrawl_hour')
        if h is None and r.get('recrawl_sent_at'):
            h = int(r['recrawl_sent_at'][11:13])
        rows.append({
            'base': b, 'day': d, 'tld': r.get('tld'),
            'content': re.sub(r'[_\-]\d+$', '', r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН'),
            'blk': block(h),
            'ya': r.get('ya_account_id') if r.get('ya_account_id') is not None
                  else acc.get(r['subdomain']),
            'hit': 1 if w[2] else 0, 'cl': w[2], 'reg': w[3], 'fd': w[4],
        })
    first = {b: min(ds) for b, ds in bd.items()}
    byacc = collections.defaultdict(set)
    for r in rows:
        if r['ya'] is not None:
            byacc[r['ya']].add(r['base'])
    seq = {}
    for a, bs in byacc.items():
        for i, b in enumerate(sorted(bs, key=lambda x: (first[x], x))):
            seq[b] = i + 1
    for r in rows:
        s = seq.get(r['base'])
        r['acc'] = 'свежий' if s == 1 else 'повторный' if s else '?'

    def agg(sel):
        n = len(sel)
        h = sum(r['hit'] for r in sel)
        cl = sum(r['cl'] for r in sel)
        reg = sum(r['reg'] for r in sel)
        fd = sum(r['fd'] for r in sel)
        return n, h, cl, reg, fd

    # полная сетка в csv
    grid = collections.defaultdict(list)
    for r in rows:
        grid[(r['content'], r['tld'], r['acc'], r['blk'])].append(r)
    out_rows = []
    for (c, z, a, b), sel in grid.items():
        n, h, cl, reg, fd = agg(sel)
        out_rows.append({
            'группа контента': c, 'зона': z, 'аккаунт': a, 'блок часа': b,
            'баз': len({x['base'] for x in sel}), 'сайтов': n,
            'вышли в поиск': h, 'выход %': round(100 * h / n, 1),
            'кликов в окне': cl, 'регистраций': reg, 'ФД': fd,
            'рег на 100 сайтов': round(100 * reg / n, 3),
        })
    out_rows.sort(key=lambda r: (r['группа контента'], -r['сайтов']))
    with open(out, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    N, H, CL, REG, FD = agg(rows)
    print('сайтов в расчёте %d (запуски по %s), выход %.1f%%, регистраций %d'
          % (N, EDGE, 100 * H / N, REG))
    print('строк в сетке «контент × зона × аккаунт × час»: %d -> %s\n' % (len(out_rows), out))

    bycont = collections.defaultdict(list)
    for r in rows:
        bycont[r['content']].append(r)
    big = {c: v for c, v in bycont.items() if len(v) >= 1500}
    rate = {c: agg(v)[1] / len(v) for c, v in big.items()}
    good = sorted(big, key=lambda c: -rate[c])[:8]
    bad = [c for c in sorted(big, key=lambda c: rate[c]) if rate[c] < 0.08][:10]

    def block_table(cs, title):
        print('\n' + '=' * 104)
        print(title)
        print('=' * 104)
        for c in cs:
            v = big[c]
            n, h, cl, reg, fd = agg(v)
            print('\n%s' % c)
            print('  всего: %d баз, %d сайтов, выход %.1f%%, кликов %d, рег %d, ФД %d'
                  % (len({x['base'] for x in v}), n, 100 * h / n, cl, reg, fd))
            for keyf, nm in ((lambda r: r['tld'], 'зона'),
                             (lambda r: r['acc'], 'аккаунт'),
                             (lambda r: r['blk'], 'час')):
                g = collections.defaultdict(list)
                for r in v:
                    g[keyf(r)].append(r)
                parts = []
                for k, sel in sorted(g.items(), key=lambda x: -len(x[1])):
                    if len(sel) < 300:
                        continue
                    n2, h2, cl2, reg2, fd2 = agg(sel)
                    parts.append('%s: %d сайтов, выход %.1f%%, рег %d' % (k, n2, 100 * h2 / n2, reg2))
                if len(parts) > 1:
                    print('    %-8s %s' % (nm, '   |   '.join(parts)))

    block_table(good, 'УДАЧНЫЕ ГРУППЫ (по выходу в поиск, от 1500 сайтов)')
    block_table(bad, 'НЕУДАЧНЫЕ ГРУППЫ (выход ниже 8%, от 1500 сайтов)')


if __name__ == '__main__':
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
