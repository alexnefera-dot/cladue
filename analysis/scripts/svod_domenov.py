#!/usr/bin/env python3
"""Одна широкая строка на домен: всё, что считалось по сети, в одном месте.

Единица — домен базы. Никаких пачек, четвертей и средних по группе: группировку
и фильтры делает тот, кто смотрит таблицу.

Источники: панель (сайты, конверсии, атрибуты запуска), профиль кликов по
сабдоменам за весь период (боты, поиск, первый поисковый клик), карта аккаунтов
Вебмастера.

Что в строке:
  • кто это          — домен, зона, дни переобхода, волны
  • чем запускали    — набор контента, страниц, оформление, шаблон
  • на чём           — аккаунт Вебмастера и который раз взят, CF-аккаунт
  • когда            — час, блок, ночь, выходной, день недели
  • трафик           — клики, боты, поиск, прочее
  • индексация       — сколько сайтов вышло в поиск за 1, 3 и 7 суток, задержка
  • деньги           — регистрации, ФД, отдача с клика, какие бренды сконвертили

Колонка «окно закрыто» отмечает домены, у которых трёхсуточное окно ещё не
прошло: у них выход в поиск занижен по построению, и их надо отфильтровывать
перед сравнением.

    python3 svod_domenov.py <панель.jsonl> <профиль-кликов.jsonl>
                            <аккаунты.jsonl> <выход.csv> [последний день кликов]
"""
import sys, json, csv, re, collections, datetime, statistics

BLOCKS = ((6, '00-05'), (12, '06-11'), (18, '12-17'), (24, '18-23'))


def block(h):
    if h is None:
        return None
    for edge, name in BLOCKS:
        if h < edge:
            return name
    return None


def pages(name):
    if re.search(r'12\s*(page|str|стр)', name, re.I):
        return 12
    if re.search(r'11\s*(page|str|стр)', name, re.I):
        return 11
    if re.search(r'7\s*(page|str|стр)', name, re.I):
        return 7
    return None


def oform(name):
    n = name.lower()
    if 'styled_img' in n:
        return 'styled_img'
    if 'oform-2' in n or 'оформлено' in n or 'oform' in n:
        return 'оформлено'
    if 'nodate' in n or 'withdate' in n:
        return 'без оформления'
    return None


def семейство(name):
    for pref, lab in (('nabory', 'nabory'), ('nabor', 'nabory'),
                      ('content-', 'content-дата'), ('NEW', 'NEW'),
                      ('archive', 'archive'), ('clean', 'clean'),
                      ('Generator', 'Generator'), ('КОНТРОЛЬ', 'контроль'),
                      ('ТЕСТ', 'тест'), ('script', 'script'), ('Content_script', 'script')):
        if name.startswith(pref):
            return lab
    return 'прочее' if name != 'КОНТЕНТ НЕ ЗАПИСАН' else 'не записан'


def main(panel, prof, accpath, out, last='2026-09-21'):
    P = {}
    for line in open(prof, encoding='utf-8'):
        a = json.loads(line)
        P[a[0]] = a[1:]
    acc = {}
    for line in open(accpath, encoding='utf-8'):
        a = json.loads(line)
        acc[a[0]] = a[1]

    D = collections.defaultdict(lambda: {
        'days': set(), 'tld': None, 'content': collections.Counter(),
        'tpl': collections.Counter(), 'pat': collections.Counter(),
        'cf': collections.Counter(), 'ya': collections.Counter(),
        'hour': collections.Counter(), 'dow': collections.Counter(),
        'night': 0, 'weekend': 0, 'sites': 0, 'brands': set(),
        'n': 0, 'bot': 0, 'cl': 0, 'other': 0,
        'lags': [], 'hit1': 0, 'hit3': 0, 'hit7': 0, 'cl_hit': 0,
        'reg': 0, 'fd': 0, 'regbrands': collections.Counter(), 'byday': collections.Counter(),
        'sites_ya': 0, 'label_len': None, 'vfail': 0, 'stage': collections.Counter()})

    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        dom = r.get('content_domain_url')
        d = (r.get('recrawl_sent_at') or '')[:10]
        if not dom or not d:
            continue
        t = D[dom]
        t['days'].add(d)
        t['tld'] = r.get('tld')
        t['content'][r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН'] += 1
        t['tpl'][r.get('template')] += 1
        t['pat'][r.get('base_name_pattern')] += 1
        t['cf'][r.get('cf_account_id')] += 1
        a = r.get('ya_account_id')
        if a is None:
            a = acc.get(r['subdomain'])
        if a is not None:
            t['ya'][a] += 1
        h = r.get('recrawl_hour')
        if h is None and r.get('recrawl_sent_at'):
            h = int(r['recrawl_sent_at'][11:13])
        t['hour'][h] += 1
        t['dow'][r.get('start_dow')] += 1
        t['night'] += 1 if r.get('is_night_kiev') else 0
        t['weekend'] += 1 if r.get('is_weekend') else 0
        t['sites'] += 1
        t['byday'][d] += 1
        t['brands'].add(r.get('brand_label'))
        t['label_len'] = r.get('base_label_len')
        t['vfail'] += r.get('verification_fail_count') or 0
        t['stage'][r.get('yandex_pipeline_stage')] += 1
        n, bot, ya, yah, yaf = P.get(r['subdomain'], [0, 0, 0, 0, None])
        t['n'] += n
        t['bot'] += bot
        t['cl'] += ya
        t['other'] += n - bot - ya
        if ya:
            t['sites_ya'] += 1
        if yaf:
            lag = (datetime.date.fromisoformat(yaf) - datetime.date.fromisoformat(d)).days
            if lag >= 0:
                t['lags'].append(lag)
                if lag <= 1:
                    t['hit1'] += 1
                if lag <= 3:
                    t['hit3'] += 1
                    t['cl_hit'] += ya
                if lag <= 7:
                    t['hit7'] += 1
        t['reg'] += r.get('reg', 0)
        t['fd'] += r.get('fd', 0)
        if r.get('reg') or r.get('fd'):
            t['regbrands'][r.get('brand_label')] += (r.get('reg', 0) + r.get('fd', 0))

    # который раз аккаунт взят в работу и сколько баз на нём всего
    first = {dom: min(t['days']) for dom, t in D.items()}
    byacc = collections.defaultdict(set)
    for dom, t in D.items():
        if t['ya']:
            byacc[t['ya'].most_common(1)[0][0]].add(dom)
    seq, accsize = {}, {}
    for a, doms in byacc.items():
        for i, dom in enumerate(sorted(doms, key=lambda x: (first[x], x))):
            seq[dom] = i + 1
            accsize[dom] = len(doms)

    def pc(k, n, nd=1):
        return round(100 * k / n, nd) if n else ''

    rows = []
    for dom, t in D.items():
        cname = t['content'].most_common(1)[0][0]
        d0 = min(t['days'])
        closed = d0 <= str(datetime.date.fromisoformat(last) - datetime.timedelta(days=3))
        nd = t['sites'] if closed else 0
        rows.append({
            'домен': dom, 'зона': t['tld'],
            'день запуска': d0, 'последний день': max(t['days']), 'дней': len(t['days']),
            'окно закрыто': 'да' if closed else 'нет',
            'набор контента': cname, 'семейство': семейство(cname),
            'наборов на домене': len(t['content']),
            'страниц': pages(cname) or '', 'оформление': oform(cname) or '',
            'шаблон': t['tpl'].most_common(1)[0][0],
            'паттерн имени': t['pat'].most_common(1)[0][0],
            'длина метки': t['label_len'],
            'аккаунт вебмастера': t['ya'].most_common(1)[0][0] if t['ya'] else '',
            'который раз аккаунт': seq.get(dom, ''),
            'аккаунт: баз всего': accsize.get(dom, ''),
            'аккаунт свежий': ('да' if seq.get(dom) == 1 else 'нет') if dom in seq else '',
            'cf-аккаунт': t['cf'].most_common(1)[0][0] if t['cf'] else '',
            'час запуска': t['hour'].most_common(1)[0][0] if t['hour'] else '',
            'блок часа': block(t['hour'].most_common(1)[0][0]) if t['hour'] else '',
            'день недели': t['dow'].most_common(1)[0][0] if t['dow'] else '',
            'ночью, сайтов': t['night'], 'в выходной, сайтов': t['weekend'],
            'сайтов': t['sites'], 'сайтов в окне': nd, 'брендов': len(t['brands']),
            'сайтов в 1-й волне': t['byday'][d0],
            'сайтов во 2-й волне': t['sites'] - t['byday'][d0],
            'ошибок верификации': t['vfail'],
            'кликов всего': t['n'], 'ботов': t['bot'], 'ботов %': pc(t['bot'], t['n']),
            'из поиска': t['cl'], 'из поиска %': pc(t['cl'], t['n']),
            'прочих': t['other'], 'прочих %': pc(t['other'], t['n']),
            'сайтов с поиском': t['sites_ya'],
            'доля сайтов с поиском %': pc(t['sites_ya'], t['sites']),
            'вышли за 1 сутки': t['hit1'] if closed else '',
            'вышли за 3 суток': t['hit3'] if closed else '',
            'вышли за 7 суток': t['hit7'] if closed else '',
            'выход 3 суток %': pc(t['hit3'], nd) if closed else '',
            'задержка до поиска, медиана': (round(statistics.median(t['lags']), 1)
                                            if t['lags'] else ''),
            'кликов на сайт с поиском': (round(t['cl'] / t['sites_ya'], 1)
                                         if t['sites_ya'] else ''),
            'регистраций': t['reg'], 'ФД': t['fd'],
            'рег на 10 тыс. поисковых': (round(10000 * t['reg'] / t['cl'], 1)
                                         if t['cl'] else ''),
            'кликов на регистрацию': (t['cl'] // t['reg']) if t['reg'] else '',
            'брендов с конверсией': len(t['regbrands']),
            'какие бренды конвертили': ', '.join(
                '%s (%d)' % (b, n) for b, n in t['regbrands'].most_common()),
        })
    rows.sort(key=lambda r: (-r['регистраций'], -r['из поиска']))
    with open(out, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print('доменов %d, колонок %d' % (len(rows), len(rows[0])))
    print('с закрытым окном %d' % sum(1 for r in rows if r['окно закрыто'] == 'да'))
    print('-> %s' % out)
    return rows


if __name__ == '__main__':
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    main(*sys.argv[1:6])
