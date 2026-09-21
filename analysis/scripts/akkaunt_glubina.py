#!/usr/bin/env python3
"""Глубина использования аккаунта Вебмастера: который раз он взят в работу.

Раньше я писал, что глубину узнать нельзя — есть только «первый раз / уже
использовался» из события чистки хостов. Это было неверно: поле
`ya_account_id` приходит в выгрузке сабдоменов по каждому сайту и за весь
период. Порядковый номер использования считается из него напрямую: базы
аккаунта упорядочиваются по дню переобхода, и каждая получает свой номер.

Метрика — выход в поиск за трое суток. Страты: день переобхода, затем
«пак + день», чтобы отделить глубину от того, какой контент в этот день шёл.

    python3 akkaunt_glubina.py <панель.jsonl> <submeta.jsonl>
                               <клики-по-сабдоменам.jsonl> <свежие-клики.jsonl>
"""
import sys, json, re, collections, datetime

K = 3
LAST = '2026-09-18'
FIELDS = ['content_label', 'content_id', 'pack_kind', 'oform_version',
          'generation_runs_count', 'ya_account_id', 'cf_account_id', 'title_ru_len',
          'description_ru_len', 'additional_text_ru_len', 'additional_text_2_ru_len',
          'keywords_word_count', 'keywords_len', 'pipeline_started', 'recrawl_sent_at',
          'content_domain_url', 'schedule_trigger_mode']
IX = {k: n for n, k in enumerate(FIELDS)}


def load_meta(path):
    """Окна выгрузок перекрываются: берём непустое значение из любого вхождения."""
    m = {}
    for line in open(path, encoding='utf-8'):
        a = json.loads(line)
        s, v = a[0], a[1:]
        m[s] = [b if b is not None else c for b, c in zip(m[s], v)] if s in m else v
    return m


def strat(rows, level, stratum, title, minn=1500, minstrat=80):
    sp = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        k = stratum(r)
        if k is None:
            continue
        t = sp[k]
        t[0] += r['hit']
        t[1] += 1
    g = collections.defaultdict(lambda: [0, 0, 0.0, 0, set()])
    for r in rows:
        k, v = stratum(r), level(r)
        if k is None or v is None:
            continue
        h, n = sp[k]
        if n < minstrat:
            continue
        t = g[v]
        t[0] += r['hit']
        t[1] += 1
        t[2] += h / n
        t[3] += r['reg']
        t[4].add(r['base'])
    o = [(v, t[0], t[1], 100 * t[0] / t[1], t[0] / t[2] if t[2] else 0, t[3], len(t[4]))
         for v, t in g.items() if t[1] >= minn]
    o.sort(key=lambda x: x[0] if isinstance(x[0], (int, float)) else 0)
    print('\n' + title)
    print('  %-14s %7s %8s %8s %8s %9s %5s' % (
        'уровень', 'баз', 'сайтов', 'выход3', 'доля', 'к страте', 'рег'))
    for v, h, n, p, k, reg, b in o:
        print('  %-14s %7d %8d %8d %7.1f%% %9.2f %5d' % (str(v)[:14], b, n, h, p, k, reg))


def main(panel, metapath, subsclicks, freshclicks):
    meta = load_meta(metapath)
    yaf = {}
    for line in open(subsclicks, encoding='utf-8'):
        s, n, ya, f, l, yf, yl = json.loads(line)
        if yf:
            yaf[s] = yf[:10]

    rows, bd = [], collections.defaultdict(set)
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        b = r.get('content_domain_url')
        if not d or not b:
            continue
        v = meta.get(r['subdomain']) or [None] * len(FIELDS)
        bd[b].add(d)
        rows.append({
            'sub': r['subdomain'], 'base': b, 'day': d, 'tld': r.get('tld'),
            'pack': re.sub(r'[_\-]\d+$', '',
                           v[IX['content_label']] or r.get('content') or 'ПАК НЕИЗВЕСТЕН'),
            'ya': v[IX['ya_account_id']], 'reg': r.get('reg', 0), 'fd': r.get('fd', 0),
        })

    for line in open(freshclicks, encoding='utf-8'):
        r = json.loads(line)
        s = (r.get('subdomain') or '').lower()
        h = r.get('referer') or ''
        if not ('yandex' in h or '//ya.ru' in h):
            continue
        at = (r.get('at') or '')[:10]
        if at and (s not in yaf or at < yaf[s]):
            yaf[s] = at

    # порядковый номер базы на аккаунте: базы аккаунта по дню первого переобхода
    first = {b: min(ds) for b, ds in bd.items()}
    acc = collections.defaultdict(set)
    for r in rows:
        if r['ya'] is not None:
            acc[r['ya']].add(r['base'])
    seq = {}
    for a, bs in acc.items():
        for i, b in enumerate(sorted(bs, key=lambda x: (first[x], x))):
            seq[b] = i + 1

    sel = [r for r in rows if r['day'] <= LAST]
    for r in sel:
        f = yaf.get(r['sub'])
        r['hit'] = 1 if (f and 0 <= (datetime.date.fromisoformat(f)
                                     - datetime.date.fromisoformat(r['day'])).days <= K) else 0
        r['seq'] = seq.get(r['base'])

    print('аккаунтов Вебмастера: %d, баз: %d, сайтов в расчёте: %d'
          % (len(acc), len(bd), len(sel)))
    c = collections.Counter(len(bs) for bs in acc.values())
    print('баз на аккаунт:', dict(sorted(c.items())))

    def lvl(r):
        if r['seq'] is None:
            return None
        return r['seq'] if r['seq'] <= 4 else '5+'

    strat(sel, lvl, lambda r: r['day'], 'КОТОРЫЙ РАЗ АККАУНТ ВЗЯТ В РАБОТУ | страта: день')
    strat(sel, lvl, lambda r: (r['pack'], r['day']),
          'КОТОРЫЙ РАЗ АККАУНТ ВЗЯТ В РАБОТУ | страта: пак + день')


if __name__ == '__main__':
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
