#!/usr/bin/env python3
"""Отдача по генераторам, а не по именам файлов.

Правило заказчика: разные названия — разные генераторы; если меняются только
числа — генератор один; внутри генератора бывают варианты (с датой и без,
оформленные и нет, с картинками и без).

Поэтому имя набора режется на две части:
  • **генератор** — то, что остаётся после удаления чисел, дат и названий
    вариантов;
  • **вариант** — набор признаков, которые внутри генератора меняются.

Ниже печатается и сама разбивка, чтобы её можно было поправить: если какой-то
набор попал не к тому генератору, это видно по списку имён под каждым.

    python3 generatory.py <панель.jsonl> <окно3.jsonl>
"""
import sys, json, re, collections

VAR = [
    (r'withdate|сдатой|с\s*датой', 'с датой'),
    (r'nodate|бездаты|без\s*даты', 'без даты'),
    (r'styled_img', 'styled_img'),
    (r'noimg', 'без картинок'),
    (r'(?<![a-z])img', 'с картинками'),
    (r'oform-2', 'оформление-2'),
    (r'oform|оформлен', 'оформлено'),
    (r'dark', 'тёмное'),
    (r'styled', 'styled'),
    (r'unique', 'unique'),
    (r'часть|part', 'часть'),
    (r'test|тест', 'тест'),
]


def split(name):
    s = name
    var = [lab for pat, lab in VAR if re.search(pat, s, re.I)]
    # убрать варианты, даты и числа — останется генератор
    for pat, _ in VAR:
        s = re.sub(pat, ' ', s, flags=re.I)
    s = re.sub(r'\d{4}-\d{2}-\d{2}[a-z]?', ' ', s)     # 2026-09-14c
    s = re.sub(r'\d{1,2}\.\d{2}', ' ', s)              # 01.09
    s = re.sub(r'\d+\s*(page|pages|str|стр)', ' ', s, flags=re.I)
    s = re.sub(r'\d+', ' ', s)
    s = re.sub(r'\(.*?\)|…|\.{2,}', ' ', s)                 # «(dorgen com», многоточия
    s = re.sub(r'[_\-\s]+', ' ', s).strip(' _-')
    # после вырезания вариантов остаются огрызки вроде «о», «s», «v» — их убираем
    s = ' '.join(w for w in s.split() if len(w) > 2)
    s = re.sub(r'\s+', ' ', s).strip()
    return (s or 'без имени'), (', '.join(var) if var else 'без признаков')


def main(panel, oknopath):
    W = {}
    for line in open(oknopath, encoding='utf-8'):
        a = json.loads(line)
        W[a[0]] = a[1:]
    gen = collections.defaultdict(lambda: [0, 0, 0, 0, set(), set()])
    var = collections.defaultdict(lambda: [0, 0, 0])
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        b = r.get('content_domain_url')
        if not d or not b:
            continue
        name = re.sub(r'[_\-]\d+$', '', r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН')
        g, v = split(name)
        w = W.get(r['subdomain'], [0, 0, 0, 0, 0])
        t = gen[g]
        t[0] += 1
        t[1] += w[3]
        t[2] += w[4]
        t[3] += w[2]
        t[4].add(b)
        t[5].add(name)
        t2 = var[(g, v)]
        t2[0] += 1
        t2[1] += w[3]
        t2[2] += w[2]

    print('ОТДАЧА ПО ГЕНЕРАТОРАМ (окно трёх суток)')
    print('%-24s %6s %8s %6s %5s %14s %16s'
          % ('генератор', 'баз', 'сайтов', 'рег', 'ФД', 'рег на 100', 'рег на 10 тыс. кл'))
    o = sorted(gen.items(), key=lambda x: -(x[1][1] / x[1][0]))
    for g, t in o:
        if t[0] < 1000:
            continue
        print('%-24s %6d %8d %6d %5d %14.3f %16.1f'
              % (g[:24], len(t[4]), t[0], t[1], t[2], 100 * t[1] / t[0],
                 10000 * t[1] / t[3] if t[3] else 0))
    small = [(g, t) for g, t in gen.items() if t[0] < 1000]
    if small:
        n = sum(t[0] for _, t in small)
        print('%-24s %6s %8d %6d %5d %14.3f'
              % ('прочие мельче 1000', '', n, sum(t[1] for _, t in small),
                 sum(t[2] for _, t in small),
                 100 * sum(t[1] for _, t in small) / n))

    print('\nЧТО ВО ЧТО ПОПАЛО — проверьте, не склеилось ли лишнее')
    for g, t in o:
        if t[0] < 1000:
            continue
        names = sorted(t[5])
        print('\n  %s  (%d сайтов, %d наборов)' % (g, t[0], len(names)))
        for n in names[:8]:
            print('      %s' % n[:70])
        if len(names) > 8:
            print('      … ещё %d' % (len(names) - 8))

    print('\n\nВАРИАНТЫ ВНУТРИ ГЕНЕРАТОРА (только там, где вариантов несколько)')
    bygen = collections.defaultdict(list)
    for (g, v), t in var.items():
        bygen[g].append((v, t))
    for g, vs in sorted(bygen.items(), key=lambda x: -sum(t[0] for _, t in x[1])):
        vs = [(v, t) for v, t in vs if t[0] >= 800]
        if len(vs) < 2:
            continue
        print('\n  %s' % g)
        print('    %-36s %8s %6s %13s'
              % ('вариант', 'сайтов', 'рег', 'рег на 100'))
        for v, t in sorted(vs, key=lambda x: -(x[1][1] / x[1][0])):
            print('    %-36s %8d %6d %13.3f' % (v[:36], t[0], t[1], 100 * t[1] / t[0]))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
