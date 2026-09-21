#!/usr/bin/env python3
"""Список баз, по которым нет пака ни в API, ни в журнале запусков.

Журнал (`analysis/launch_*.txt`) начинается с 24.08, а в выгрузке
`/v1/subdomains` поля контента появились только после 24.08. Пересечение этих
двух дыр — базы, про которые не известно ничего, кроме домена и дня.

Файл сделан под заполнение: строка = база, столбец «пак» пустой. Достаточно
вписать имя пака напротив домена и вернуть файл — я подставлю его в панель
тем же механизмом, что и журнал.

    python3 zapros_zhurnala.py <панель.jsonl> <клики-по-сабдоменам.jsonl>
                               <свежие-клики.jsonl> <выход.csv> <выход.txt>
"""
import sys, json, collections, datetime

K = 3


def main(panel, subsclicks, fresh, out_csv, out_txt):
    yaf = {}
    for line in open(subsclicks, encoding='utf-8'):
        s, n, ya, f, l, yf, yl = json.loads(line)
        if yf:
            yaf[s] = yf[:10]

    sites = {}
    base = collections.defaultdict(lambda: {
        'days': set(), 'tld': collections.Counter(), 'n': 0, 'hit': 0,
        'cl': 0, 'reg': 0, 'fd': 0, 'ya': set(), 'brands': set()})
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        b = r.get('content_domain_url')
        if not d or not b or r.get('content'):
            continue
        sites[r['subdomain']] = (b, d)
        a = base[b]
        a['days'].add(d)
        a['tld'][r.get('tld')] += 1
        a['n'] += 1
        a['cl'] += r.get('ya_clicks') or 0
        a['reg'] += r.get('reg', 0)
        a['fd'] += r.get('fd', 0)
        a['brands'].add(r.get('brand_label'))

    for line in open(fresh, encoding='utf-8'):
        r = json.loads(line)
        s = (r.get('subdomain') or '').lower()
        h = r.get('referer') or ''
        if s not in sites or not ('yandex' in h or '//ya.ru' in h):
            continue
        at = (r.get('at') or '')[:10]
        if at and (s not in yaf or at < yaf[s]):
            yaf[s] = at
    for s, (b, d) in sites.items():
        f = yaf.get(s)
        if f and 0 <= (datetime.date.fromisoformat(f)
                       - datetime.date.fromisoformat(d)).days <= K:
            base[b]['hit'] += 1

    rows = sorted(base.items(), key=lambda kv: (min(kv[1]['days']), kv[0]))
    import csv
    with open(out_csv, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['пак (заполнить)', 'домен базы', 'день переобхода', 'зона',
                    'сайтов', 'брендов', 'вышли в поиск за 3 суток', 'выход3 %',
                    'поисковых кликов', 'регистраций', 'ФД'])
        for b, a in rows:
            w.writerow(['', b, min(a['days']), a['tld'].most_common(1)[0][0],
                        a['n'], len(a['brands']), a['hit'],
                        round(100 * a['hit'] / a['n'], 1), a['cl'], a['reg'], a['fd']])

    byday = collections.defaultdict(list)
    for b, a in rows:
        byday[min(a['days'])].append((b, a))
    L = ['ЗАПРОС: ПАКИ ПО БАЗАМ, ПРО КОТОРЫЕ НЕТ НИ МЕТКИ В API, НИ СТРОКИ В ЖУРНАЛЕ',
         '=' * 78, '',
         'Формат под заполнение: над группой доменов впишите имя пака — так же,',
         'как в launch_*.txt. Порядок доменов внутри дня произвольный.', '']
    tot = [0, 0, 0, 0]
    for d in sorted(byday):
        v = byday[d]
        n = sum(a['n'] for _, a in v)
        cl = sum(a['cl'] for _, a in v)
        reg = sum(a['reg'] for _, a in v)
        fd = sum(a['fd'] for _, a in v)
        tot = [tot[0] + n, tot[1] + cl, tot[2] + reg, tot[3] + fd]
        z = collections.Counter()
        for _, a in v:
            z.update(a['tld'])
        L += ['=' * 78,
              '%s — %d баз, %d сайтов, %d поисковых кликов, %d регистраций, %d ФД'
              % (d, len(v), n, cl, reg, fd),
              '   зоны: ' + '  '.join('.%s %d' % (k, x) for k, x in z.most_common()),
              '=' * 78, '', '--- (впишите имя пака)', '']
        for b, a in sorted(v, key=lambda kv: -kv[1]['cl']):
            L.append('    %-22s  сайтов %4d  выход %5.1f%%  кликов %7d  рег %2d  ФД %d'
                     % (b, a['n'], 100 * a['hit'] / a['n'], a['cl'], a['reg'], a['fd']))
        L.append('')
    L += ['=' * 78,
          'ИТОГО: %d баз, %d сайтов, %d поисковых кликов, %d регистраций, %d ФД'
          % (len(rows), tot[0], tot[1], tot[2], tot[3]), '=' * 78]
    open(out_txt, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('\n'.join(L[-3:]))
    print('дней:', len(byday), '| файлы:', out_csv, out_txt)


if __name__ == '__main__':
    if len(sys.argv) < 6:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
