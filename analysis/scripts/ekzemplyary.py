#!/usr/bin/env python3
"""Каждый экземпляр генерации — отдельной строкой, без склейки в семейства.

Прежняя таблица наборов сводила `nabory-515-524_styled_img_1 … _10` в одну
строку «семейство». Это скрывало ровно то, что нужно видеть: каждый экземпляр
генерился отдельно, и внутри одного семейства экземпляры могут расходиться.

Здесь строка = экземпляр. Имя берётся из `content_label` выгрузки API, а если
его нет — из поля `content` панели (оно тоже поэкземплярное: 574 из 662 его
значений приходятся ровно на одну базу).

Ожидание считается по ставке дня запуска, пересчитывается каждый прогон.
Свежие запуски (окно ещё не закрылось) не выбрасываются, а помечаются.

    python3 ekzemplyary.py <панель.jsonl> <subdomains.jsonl>[,…] <выход.csv>
"""
import sys, json, re, csv, collections


def main(panel, subs_paths, out_csv):
    api = {}
    for p in subs_paths:
        for line in open(p, encoding='utf-8'):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get('content_label'):
                api[r['subdomain'].lower()] = r['content_label']

    rows = []
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        b = r.get('content_domain_url')
        if not d or not b:
            continue
        name = api.get(r['subdomain']) or r.get('content') or 'ПАК НЕИЗВЕСТЕН'
        rows.append({
            'inst': name,
            'fam': re.sub(r'[_\-]\d+$', '', name),
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

    g = collections.defaultdict(lambda: {
        'bases': set(), 'days': set(), 'fams': set(), 'tld': collections.Counter(),
        'n': 0, 'fresh': 0, 'ya': 0, 'cl': 0, 'reg': 0, 'fd': 0, 'exp': 0.0})
    for r in rows:
        a = g[r['inst']]
        a['bases'].add(r['base']); a['days'].add(r['day']); a['fams'].add(r['fam'])
        a['tld'][r['tld']] += 1
        a['n'] += 1; a['fresh'] += r['fresh']; a['ya'] += r['ya']
        a['cl'] += r['clicks']; a['reg'] += r['reg']; a['fd'] += r['fd']
        t = day[r['day']]
        a['exp'] += t[1] / t[0] if t[0] else 0

    out = []
    for name, a in g.items():
        exp = a['exp']
        if exp < 2:
            v = 'мало данных'
        elif a['reg'] == 0:
            v = 'ПУСТОЙ: ноль при ожидаемых %.1f' % exp
        else:
            k = a['reg'] / exp
            v = ('лучше ожидаемого в %.1f раза' % k) if k >= 1.5 else \
                ('хуже ожидаемого в %.1f раза' % (1 / k)) if k <= 1 / 1.5 else 'как ожидалось'
        out.append({
            'экземпляр': name,
            'семейство': sorted(a['fams'])[0],
            'баз': len(a['bases']),
            'сайтов': a['n'],
            'свежих': a['fresh'],
            'дней': len(a['days']),
            'первый день': min(a['days']),
            'зоны': '/'.join('%s:%d' % kv for kv in a['tld'].most_common()),
            'вышли в поиск': a['ya'],
            'поисковых кликов': a['cl'],
            'регистраций': a['reg'],
            'ФД': a['fd'],
            'кликов на регистрацию': a['cl'] // a['reg'] if a['reg'] else '',
            'ожидалось регистраций': round(exp, 1),
            'вердикт': v,
        })
    out.sort(key=lambda r: (r['семейство'], r['экземпляр']))
    with open(out_csv, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    print('экземпляров всего:', len(out))
    print('семейств:', len(set(r['семейство'] for r in out)))
    print('сайтов:', sum(r['сайтов'] for r in out),
          'свежих:', sum(r['свежих'] for r in out),
          'регистраций:', sum(r['регистраций'] for r in out))
    c = collections.Counter(re.sub(r' .*', '', r['вердикт']) for r in out)
    for k, n in c.most_common():
        print('  %-14s %4d экземпляров, сайтов %7d' % (
            k, n, sum(r['сайтов'] for r in out if r['вердикт'].startswith(k))))


if __name__ == '__main__':
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2].split(','), sys.argv[3])
