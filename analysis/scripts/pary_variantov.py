#!/usr/bin/env python3
"""Все пары «один корень набора, один день, разные варианты» — готовые сравнения.

Ставить ничего не надо: в сети уже есть случаи, когда один и тот же набор
уходил в один день в двух-четырёх вариантах. Это и есть настоящий опыт —
контент, день, квота и каталог брендов у вариантов общие, отличается только
то, что вынесено в имя.

Корень набора получается вычёркиванием из имени всех признаков варианта:
оформления, даты, числа страниц, картинок. Что осталось — общая основа.

Сравнение парное: внутри каждого корня и дня варианты сопоставляются между
собой, и только потом результаты складываются по всем парам. Так разница в
объёме между парами не перетягивает итог на себя.

    python3 pary_variantov.py <панель.jsonl> <окно3.jsonl> <выход.csv>
"""
import sys, json, re, csv, math, collections

EDGE = '2026-09-18'
MIN = 800

AXES = [
    ('дата', [(r'withdate|сдатой', 'с датой'), (r'nodate|бездаты', 'без даты')]),
    ('страниц', [(r'12\s*(page|str|стр)', '12'), (r'11\s*(page|str|стр)', '11'),
                 (r'7\s*(page|str|стр)', '7')]),
    ('оформление', [(r'styled_img', 'styled_img'), (r'oform-2', 'оформление-2'),
                    (r'oform|оформлен', 'оформлено')]),
    ('картинки', [(r'noimg', 'без картинок'), (r'(?<![a-z])[_+]img', 'с картинками')]),
    ('нарезка', [(r'часть1|часть 1', 'часть 1'), (r'часть2|часть 2', 'часть 2'),
                 (r'часть3|часть 3', 'часть 3')]),
    ('номер варианта', [(r'oform-1(?!\d)', 'вариант 1'), (r'oform-2(?!\d)', 'вариант 2'),
                        (r'oform-8(?!\d)', 'вариант 8'), (r'oform-9(?!\d)', 'вариант 9')]),
]


def stem(name):
    s = name
    for pat in (r'styled_img', r'oform-?\d?', r'оформлен\w*', r'withdate', r'nodate',
                r'сдатой', r'бездаты', r'\d+\s*(page|pages|str|стр)s?',
                r'[_\-]img', r'\+img', r'noimg', r'часть\s*\d'):
        s = re.sub(pat, '', s, flags=re.I)
    s = re.sub(r'[_\-\s]+', ' ', s).strip(' _-')
    return s


def axis_value(name, axis):
    for pat, lab in dict(AXES)[axis]:
        if re.search(pat, name, re.I):
            return lab
    return None


def main(panel, oknopath, out):
    W = {}
    for line in open(oknopath, encoding='utf-8'):
        a = json.loads(line)
        W[a[0]] = a[1:]
    g = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0, 0, 0, set()]))
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        b = r.get('content_domain_url')
        if not d or not b or d > EDGE:
            continue
        name = re.sub(r'[_\-]\d+$', '', r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН')
        w = W.get(r['subdomain'], [0, 0, 0, 0, 0])
        t = g[(stem(name), d)][name]
        t[0] += 1
        t[1] += 1 if w[2] else 0
        t[2] += w[2]
        t[3] += w[3]
        t[4] += w[4]
        t[5].add(b)

    pairs = []
    for (st, day), d in g.items():
        big = {k: v for k, v in d.items() if v[0] >= MIN}
        if len(big) >= 2:
            pairs.append((st, day, big))
    pairs.sort(key=lambda x: -sum(v[0] for v in x[2].values()))
    print('пар «корень + день» с двумя и более вариантами по %d+ сайтов: %d' % (MIN, len(pairs)))
    print('в них наборов: %d, сайтов %d'
          % (sum(len(x[2]) for x in pairs), sum(v[0] for x in pairs for v in x[2].values())))

    rows = []
    for st, day, big in pairs:
        for k, v in big.items():
            rows.append({
                'корень': st, 'день': day, 'набор': k,
                'баз': len(v[5]), 'сайтов': v[0],
                'вышли в поиск': v[1], 'выход %': round(100 * v[1] / v[0], 1),
                'кликов в окне': v[2], 'регистраций': v[3], 'ФД': v[4],
                'рег на 100 сайтов': round(100 * v[3] / v[0], 3),
                'дата': axis_value(k, 'дата') or '', 'страниц': axis_value(k, 'страниц') or '',
                'оформление': axis_value(k, 'оформление') or '',
                'картинки': axis_value(k, 'картинки') or '',
                'нарезка': axis_value(k, 'нарезка') or '',
            })
    rows.sort(key=lambda r: (r['корень'], r['день'], -r['сайтов']))
    with open(out, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print('\n' + '=' * 100)
    print('ВСЕ ПАРЫ ПОИМЁННО')
    print('=' * 100)
    for st, day, big in pairs:
        print('\nкорень «%s», %s' % (st[:46] or '(пусто)', day))
        print('  %-46s %5s %7s %8s %6s %4s %11s'
              % ('набор', 'баз', 'сайтов', 'выход %', 'рег', 'ФД', 'рег на 100'))
        for k, v in sorted(big.items(), key=lambda x: -x[1][1] / x[1][0]):
            print('  %-46s %5d %7d %7.1f%% %6d %4d %11.3f'
                  % (k[:46], len(v[5]), v[0], 100 * v[1] / v[0], v[3], v[4], 100 * v[3] / v[0]))

    print('\n\n' + '=' * 100)
    print('СВОДКА ПО ОСЯМ: сравнение только внутри пары, потом сложение')
    print('=' * 100)
    for axis, levels in AXES:
        labs = [lab for _, lab in levels]
        acc = collections.defaultdict(lambda: [0, 0, 0, 0])
        used = wins = losses = 0
        detail = []
        for st, day, big in pairs:
            lv = {}
            for k, v in big.items():
                a = axis_value(k, axis)
                if a is None:
                    continue
                if a in lv:
                    for i in range(4):
                        lv[a][i] += [v[0], v[1], v[2], v[3]][i]
                else:
                    lv[a] = [v[0], v[1], v[2], v[3]]
            if len(lv) < 2:
                continue
            used += 1
            for a, t in lv.items():
                for i in range(4):
                    acc[a][i] += t[i]
            order = sorted(lv, key=lambda a: labs.index(a))
            best = max(lv, key=lambda a: lv[a][1] / lv[a][0])
            if best == order[0]:
                wins += 1
            else:
                losses += 1
            detail.append((st[:28], day, {a: (lv[a][0], 100 * lv[a][1] / lv[a][0],
                                              lv[a][3]) for a in lv}))
        if used < 2:
            continue
        print('\n%s — сравнимых пар: %d' % (axis.upper(), used))
        print('  %-16s %8s %8s %9s %6s %12s'
              % ('уровень', 'сайтов', 'выход %', 'кликов', 'рег', 'рег на 100'))
        for a in sorted(acc, key=lambda a: -acc[a][1] / acc[a][0]):
            t = acc[a]
            print('  %-16s %8d %7.1f%% %9d %6d %12.3f'
                  % (a, t[0], 100 * t[1] / t[0], t[2], t[3], 100 * t[3] / t[0]))
        n = wins + losses
        if n:
            p = sum(math.comb(n, i) for i in range(max(wins, losses), n + 1)) / 2 ** (n - 1)
            print('  «%s» оказался лучше по выходу в %d парах из %d; двусторонний знаковый p = %.3f'
                  % (labs[0], wins, n, min(1.0, p)))


if __name__ == '__main__':
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
