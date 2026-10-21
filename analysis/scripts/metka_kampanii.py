#!/usr/bin/env python3
"""Сверка двух меток кампании в реф-ссылках и пересчёт конверсий по обеим.

С 08.10.2026 генератор ставит на новые сайты слаг /go/dorgne_fenix вместо
/go/dorgen_engine. Хост реф-ссылки прежний (sitegoratorr2.top), сменился только
слаг, и трекер пишет его в поле campaign. Все прежние отчёты фильтровали
campaign == 'dorgen_engine' и теряли всё, что запущено с 08.10.

Запуск:
    python3 metka_kampanii.py            # свод по меткам и когортам
"""
import collections
import json
import os

API = os.path.join(os.path.dirname(__file__), '..', 'api')
OURS = {'dorgen_engine', 'dorgne_fenix'}

REESTRY = [
    'dorgen_subdomains_2026-09-01_2026-09-30.jsonl',
    'dorgen_subdomains_2026-10-01_2026-10-10.jsonl',
    'dorgen_subdomains_2026-10-11_2026-10-22.jsonl',
]
KONVERSII = 'tracker_conversions_2026-10-10_2026-10-21.jsonl'
KLIKI = 'tracker_clicks_2026-10-11_2026-10-21.jsonl'


def pervoe_pole(stroka):
    """Значение subdomain без разбора всей строки — реестры весят под гигабайт."""
    i = stroka.find('"', 13)
    j = stroka.find('"', i + 1)
    return stroka[i + 1:j] if j > 0 else ''


def reestr(nuzhnye):
    karta = {}
    for imya in REESTRY:
        put = os.path.join(API, imya)
        if not os.path.exists(put):
            continue
        with open(put) as f:
            for stroka in f:
                sub = pervoe_pole(stroka)
                if sub not in nuzhnye:
                    continue
                r = json.loads(stroka)
                karta[sub] = {
                    'pereobhod': (r.get('recrawl_sent_at') or '')[:10],
                    'tld': r.get('tld'),
                    'slug': r.get('ref_link_slug'),
                }
    return karta


def konversii():
    vidennye, rows = set(), []
    with open(os.path.join(API, KONVERSII)) as f:
        for stroka in f:
            r = json.loads(stroka)
            if r.get('campaign') not in OURS:
                continue
            klyuch = (r['clickid'], r['event'], r['at'])
            if klyuch in vidennye:
                continue
            vidennye.add(klyuch)
            rows.append(r)
    return rows


def kogorta(data):
    if not data:
        return 'не опознан (до сентября)'
    if data >= '2026-10-11':
        return 'окт 11+'
    if data >= '2026-10-08':
        return 'окт 08-10'
    if data >= '2026-10-01':
        return 'окт 01-07'
    return 'сентябрь'


PORYADOK = ['не опознан (до сентября)', 'сентябрь', 'окт 01-07', 'окт 08-10', 'окт 11+']


def main():
    # 1. когда сменился слаг
    po_dnyam = collections.defaultdict(collections.Counter)
    for imya in REESTRY[1:]:
        put = os.path.join(API, imya)
        if not os.path.exists(put):
            continue
        with open(put) as f:
            for stroka in f:
                r = json.loads(stroka)
                data = (r.get('recrawl_sent_at') or '')[:10]
                if data >= '2026-10-01':
                    po_dnyam[data][r.get('ref_link_slug')] += 1
    print('слаг реф-ссылки по дате переобхода')
    for data in sorted(po_dnyam):
        vsego = sum(po_dnyam[data].values())
        doli = ', '.join(f'{k} {v} ({v / vsego:.0%})' for k, v in po_dnyam[data].most_common())
        print(f'  {data}  {vsego:>6}  {doli}')

    # 2. конверсии по обеим меткам
    rows = konversii()
    karta = reestr({r['subdomain'] for r in rows if r.get('subdomain')})
    reg = collections.Counter()
    fd = collections.Counter()
    for r in rows:
        k = kogorta(karta.get(r['subdomain'], {}).get('pereobhod'))
        (reg if r['event'] == 'reg' else fd)[k] += 1
    print('\nконверсии 10-21.10 по когорте запуска (обе метки)')
    print('  когорта                   рег   ФД')
    for k in PORYADOK:
        print(f'  {k:<24} {reg.get(k, 0):>4} {fd.get(k, 0):>4}')
    print(f'  {"ИТОГО":<24} {sum(reg.values()):>4} {sum(fd.values()):>4}')
    print('  по метке:', dict(collections.Counter(r['campaign'] for r in rows)))

    # 3. индекс свежих когорт — доля сайтов с живым поисковым кликом
    put_klikov = os.path.join(API, KLIKI)
    if not os.path.exists(put_klikov):
        return
    sait_data, razmer = {}, collections.Counter()
    for imya in REESTRY[1:]:
        put = os.path.join(API, imya)
        if not os.path.exists(put):
            continue
        with open(put) as f:
            for stroka in f:
                r = json.loads(stroka)
                data = (r.get('recrawl_sent_at') or '')[:10]
                if data >= '2026-10-08':
                    sait_data[r['subdomain']] = data
                    razmer[data] += 1
    zhivye = collections.defaultdict(set)
    with open(put_klikov) as f:
        for stroka in f:
            r = json.loads(stroka)
            sub = r.get('subdomain')
            if sub not in sait_data or r.get('campaign') not in OURS:
                continue
            if r.get('is_bot') or 'yandex.' not in (r.get('referer') or ''):
                continue
            zhivye[sait_data[sub]].add(sub)
    print('\nиндекс свежих когорт (живой поисковый клик за 11-21.10)')
    print('  переобход   сайтов   с живым кликом   индекс')
    for data in sorted(razmer):
        n = razmer[data]
        print(f'  {data}  {n:>7}  {len(zhivye[data]):>14}  {len(zhivye[data]) / n:>7.2%}')


if __name__ == '__main__':
    main()
