#!/usr/bin/env python3
"""Окно заработка от первого клика, а не от переобхода: §6 программы тестов.

Домен, вышедший в поиск на второй день, за шестидневное окно зарабатывает
четыре дня; вышедший на пятый — один. Сейчас они сравниваются как равные, и
любая разница между конфигурациями складывает «контент лучше» и «быстрее
вышел» в одно число.

Здесь считается, где на самом деле лежат конверсии: по возрасту от переобхода
и по возрасту от первого поискового клика той же базы. Конверсии привязаны к
сабдомену через `clickid` — поле `subdomain` в выгрузке конверсий пустое.

    python3 okno_ot_klika.py <карта.jsonl> <subs.jsonl> <days.json>
                             <конверсии.jsonl> <клики-конверсий.jsonl>
"""
import sys, json, collections, statistics
from datetime import date, datetime, timedelta

WINDOW = 6


def ts(x):
    return datetime.fromisoformat(x) if x else None


def main(map_path, subs_path, days_path, conv_path, convclicks_path):
    base_of, recrawl_of = {}, {}
    for line in open(map_path, encoding='utf-8'):
        sub, base, cd_id, brand, recrawl, started, pages, tld, stage = json.loads(line)
        base_of[sub] = base
        recrawl_of[sub] = recrawl or started

    # первый поисковый клик базы — момент, с которого она реально в выдаче
    days = json.load(open(days_path, encoding='utf-8'))
    base_first_ya = {}
    for b, series in days.items():
        ya = [k for k, v in series.items() if v[1]]
        if ya:
            base_first_ya[b] = date.fromisoformat(min(ya))

    sub_first_ya = {}
    for line in open(subs_path, encoding='utf-8'):
        s, n, ya, first, last, ya_first, ya_last = json.loads(line)
        if ya_first:
            sub_first_ya[s] = ya_first

    click_of = {}
    for line in open(convclicks_path, encoding='utf-8'):
        r = json.loads(line)
        click_of[r['clickid']] = r

    conv = [json.loads(l) for l in open(conv_path, encoding='utf-8')]
    print(f'конверсий в архиве: {len(conv)}, из них с clickid: '
          f'{sum(1 for c in conv if c.get("clickid"))}')

    rows, stat = [], collections.Counter()
    for c in conv:
        cid = c.get('clickid')
        k = click_of.get(cid) if cid else None
        if k is None:
            stat['клик не найден в выгрузке'] += 1
            continue
        s = (k.get('subdomain') or '').lower()
        b = base_of.get(s)
        if b is None:
            stat['сабдомен не нашей сети'] += 1
            continue
        stat['привязано'] += 1
        rec = ts(recrawl_of.get(s))
        at = ts(c['at'])
        kat = ts(k['at'])
        rows.append({
            'event': c.get('event'), 'sub': s, 'base': b,
            'at': at, 'click_at': kat,
            'from_recrawl': (at - rec).total_seconds() / 86400 if rec else None,
            'from_first_ya': ((at.date() - base_first_ya[b]).days
                              if b in base_first_ya else None),
            'click_from_recrawl': (kat - rec).total_seconds() / 86400 if rec else None,
            'ya_click': 'yandex' in (k.get('referer') or '') or '//ya.ru' in (k.get('referer') or ''),
        })

    for k, v in stat.most_common():
        print(f'  {k:<28} {v:>5}')
    print()

    fd = [r for r in rows if r['event'] != 'reg']
    print(f'привязано конверсий {len(rows)}, из них ФД {len(fd)}\n')

    print('=' * 72)
    print('ГДЕ ЛЕЖАТ КОНВЕРСИИ: ВОЗРАСТ ОТ ПЕРЕОБХОДА ПРОТИВ ВОЗРАСТА ОТ ПЕРВОГО КЛИКА')
    print('строка — сколько суток прошло, столбцы — две системы отсчёта')
    print(f"{'сутки':>8} {'от переобхода':>14} {'от первого клика':>18}")
    a = collections.Counter()
    b = collections.Counter()
    for r in rows:
        if r['from_recrawl'] is not None:
            a[min(int(r['from_recrawl']), 30)] += 1
        if r['from_first_ya'] is not None:
            b[min(r['from_first_ya'], 30)] += 1
    for i in range(0, 31):
        if not a[i] and not b[i]:
            continue
        print(f'{i:>8} {a[i]:>14} {b[i]:>18}')
    inw_r = sum(v for k, v in a.items() if k <= WINDOW)
    inw_y = sum(v for k, v in b.items() if k <= WINDOW)
    print(f"\n  внутри окна {WINDOW} суток от переобхода:      {inw_r} из {sum(a.values())} "
          f"({100.0*inw_r/max(sum(a.values()),1):.1f}%)")
    print(f"  внутри окна {WINDOW} суток от первого клика:  {inw_y} из {sum(b.values())} "
          f"({100.0*inw_y/max(sum(b.values()),1):.1f}%)")

    print()
    print('=' * 72)
    print('СКОЛЬКО БАЗА ЖДЁТ ВЫХОДА В ПОИСК')
    print('это и есть съеденная часть окна: пока база не в выдаче, окно идёт вхолостую')
    lag = []
    for b_, f in base_first_ya.items():
        recs = [recrawl_of[s][:10] for s in ()]
    # лаг считается по сабдоменам: у каждого свой переобход
    per = []
    for s, ya_first in sub_first_ya.items():
        rec = recrawl_of.get(s)
        if not rec:
            continue
        v = (ts(ya_first) - ts(rec)).total_seconds() / 86400
        if -1 < v < 40:
            per.append(v)
    per.sort()
    if per:
        print(f'  сабдоменов с поисковым кликом и известным переобходом: {len(per)}')
        for q in (10, 25, 50, 75, 90):
            print(f'    {q}-й процентиль: {per[int(len(per)*q/100)]:.2f} суток')
        eaten = statistics.median(per)
        print(f'\n  медиана {eaten:.2f} суток — это {100.0*eaten/WINDOW:.0f}% окна в {WINDOW} суток,')
        print(f'  то есть у половины сабдоменов на заработок остаётся меньше '
              f'{WINDOW - eaten:.1f} суток из {WINDOW}')

    print()
    print('=' * 72)
    print('ЧТО ЭТО МЕНЯЕТ В СРАВНЕНИЯХ')
    print('если лаг до выхода в поиск различается между группами, окно в 6 суток')
    print('сравнивает разную экспозицию; проверяем разброс лага по зонам')
    bytld = collections.defaultdict(list)
    for s, ya_first in sub_first_ya.items():
        rec = recrawl_of.get(s)
        if not rec:
            continue
        v = (ts(ya_first) - ts(rec)).total_seconds() / 86400
        if -1 < v < 40:
            bytld[s.rsplit('.', 1)[-1]].append(v)
    print(f"    {'зона':<10} {'сабдоменов':>11} {'медиана лага':>14} {'остаток окна':>14}")
    for k, v in sorted(bytld.items(), key=lambda kv: -len(kv[1]))[:6]:
        if len(v) < 50:
            continue
        m = statistics.median(v)
        print(f'    {k:<10} {len(v):>11} {m:>14.2f} {WINDOW-m:>14.2f}')


if __name__ == '__main__':
    if len(sys.argv) < 6:
        raise SystemExit(__doc__)
    main(*sys.argv[1:6])
