#!/usr/bin/env python3
"""Срок жизни домена: §4 программы тестов, расчёт на уже собранном.

Новых запусков не нужно. Вопрос: домен выходит в поиск, работает, выпадает —
сколько это длится и какой формы кривая. Ответ меняет экономику: порог
окупаемости $1.94 посчитан на шестисуточном окне, и если база отдаёт дольше,
порог занижен.

Считается по **кликам с реферером поиска**, а не по всем. Всего кликов у базы
вдвое-втрое больше, но остальное — прямые заходы, боты и возвраты; они идут и
тогда, когда в выдаче база уже не стоит, и маскируют выпадение. Оговорка та же,
что и везде: поисковый клик означает «стоит в выдаче и по ней кликают», а не
«в индексе» — про индекс мы по-прежнему знаем только со слов переобхода.

Три вещи, которые ломают наивный счёт, и что с ними сделано:

1. **Усечение справа.** База, запущенная 15.09, к 17.09 прожила два дня — это
   длина наблюдения, а не срок жизни. Возрастной профиль считается с риск-сетом:
   в знаменателе дня N только базы, чьё наблюдение доросло до возраста N.
2. **Возраст против календаря.** В хвосте профиля остаются только августовские
   базы, и «подъём на 17-й день» может оказаться просто августом. Поэтому тот
   же профиль печатается отдельно по когортам недели запуска.
3. **Обрыв против паузы.** Трафик прерывистый, один пустой день — не смерть.
   Смертью считается хвостовой разрыв не меньше GAP суток, дотянувшийся до
   конца наблюдения; иначе база жива и цензурируется.

    python3 srok_zhizni.py <карта.jsonl> <days.json> <конец YYYY-MM-DD>
"""
import sys, json, collections, statistics
from datetime import date, timedelta

GAP = 3                  # суток тишины в хвосте = трафик прекратился
WINDOW = 6               # окно, по которому сейчас считается экономика
DUMP_FROM = date(2026, 7, 28)   # с какой даты в выгрузке вообще есть клики


def main(map_path, days_path, obs_to):
    end = date.fromisoformat(obs_to)
    days = json.load(open(days_path, encoding='utf-8'))

    attr = {}
    for line in open(map_path, encoding='utf-8'):
        sub, base, cd_id, brand, recrawl, started, pages, tld, stage = json.loads(line)
        if not base:
            continue
        a = attr.setdefault(base, {'subs': 0, 'recrawl': None, 'tld': collections.Counter()})
        a['subs'] += 1
        t = (recrawl or started or '')[:10]
        if t and (a['recrawl'] is None or t < a['recrawl']):
            a['recrawl'] = t
        if tld:
            a['tld'][tld] += 1

    earliest = min(day for s in days.values() for day in s)
    print(f'баз в реестре: {len(attr)}, из них с хотя бы одним кликом: {len(days)}')
    print(f'выгрузка кликов ведётся с {DUMP_FROM}, первый клик по нашим базам {earliest} —')
    print(f'усечения слева нет: ни одна база не начала работать до начала выгрузки')
    print(f'наблюдение до {obs_to}\n')

    rows = []
    for base, series in days.items():
        a = attr.get(base)
        if a is None:
            continue
        ya = {date.fromisoformat(k): v[1] for k, v in series.items() if v[1]}
        allc = {date.fromisoformat(k): v[0] for k, v in series.items()}
        if not ya:
            continue                       # ни одного поискового клика: в выдачу не вышла
        f, l = min(ya), max(ya)
        rows.append({
            'base': base, 'first': f, 'last': l,
            'life': (l - f).days,
            'obs': (end - f).days,
            'alive': (end - l).days < GAP,
            'ya': ya, 'all': allc,
            'ya_sum': sum(ya.values()), 'all_sum': sum(allc.values()),
            'cohort': f - timedelta(days=f.weekday()),
            'tld': a['tld'].most_common(1)[0][0] if a['tld'] else None,
            'subs': a['subs'],
        })
    rows.sort(key=lambda r: r['first'])
    noya = len(days) - len(rows)
    print(f'баз с поисковыми кликами: {len(rows)}; без единого поискового клика: {noya}\n')

    def profile(sel, maxage=31, minrisk=20):
        out = []
        for age in range(maxage):
            risk = [r for r in sel if r['obs'] >= age]
            if len(risk) < minrisk:
                break
            c = sum(r['ya'].get(r['first'] + timedelta(days=age), 0) for r in risk)
            withc = sum(1 for r in risk
                        if r['ya'].get(r['first'] + timedelta(days=age), 0) > 0)
            out.append((age, len(risk), c / len(risk), withc / len(risk)))
        return out

    print('=' * 72)
    print('КРИВАЯ ПОИСКОВЫХ КЛИКОВ ПО ВОЗРАСТУ БАЗЫ')
    print('день 0 — первый день, когда база получила клик из поиска')
    print(f"{'день':>5} {'баз в риске':>12} {'поисковых/базу':>15} {'доля баз с кликом':>18}")
    for age, n, c, w in profile(rows):
        print(f'{age:>5} {n:>12} {c:>15.1f} {100.0*w:>17.1f}%')

    print()
    print('=' * 72)
    print('ТОТ ЖЕ ПРОФИЛЬ ПО КОГОРТАМ (неделя первого поискового клика)')
    print('если форма кривой повторяется в каждой когорте — это возраст, а не календарь')
    coh = collections.defaultdict(list)
    for r in rows:
        coh[r['cohort']].append(r)
    ages = [0, 1, 2, 3, 4, 5, 6, 8, 10, 14, 20]
    print(f"{'когорта':<12} {'баз':>5} " + ' '.join(f'{("д"+str(a)):>7}' for a in ages))
    for c, sel in sorted(coh.items()):
        if len(sel) < 30:
            continue
        p = {a: v for a, n, v, w in profile(sel, maxage=31, minrisk=10)}
        cells = ' '.join((f'{p[a]:>7.0f}' if a in p else f'{"—":>7}') for a in ages)
        print(f'{c.isoformat():<12} {len(sel):>5} {cells}')

    print()
    print('=' * 72)
    print(f'ЧТО ОСТАЁТСЯ ЗА ОКНОМ В {WINDOW} СУТОК')
    print('доли считаются только по базам, у которых наблюдение длиннее окна —')
    print('иначе «за окном ничего нет» выйдет просто потому, что туда не досмотрели')
    for span in (WINDOW, 13, 20):
        sel = [r for r in rows if r['obs'] > span]
        if len(sel) < 20:
            continue
        for what, key in (('поисковые', 'ya'), ('все клики', 'all')):
            inside = sum(v for r in sel for day, v in r[key].items()
                         if (day - r['first']).days <= span)
            tot = sum(sum(r[key].values()) for r in sel)
            print(f'  окно {span+1:>2} суток, {what:<10} баз {len(sel):>4}  '
                  f'внутри {100.0*inside/tot:>5.1f}%  за окном {100.0*(tot-inside)/tot:>5.1f}%')

    print()
    print('=' * 72)
    print('КОГДА ПОИСКОВЫЙ ТРАФИК ПРЕКРАЩАЕТСЯ')
    print(f'смерть = хвостовая тишина не меньше {GAP} суток до конца наблюдения;')
    print('живые на конец наблюдения цензурируются, а не считаются короткоживущими')
    dead = [r for r in rows if not r['alive']]
    print(f'  прекратили: {len(dead)} из {len(rows)} ({100.0*len(dead)/len(rows):.1f}%)')
    print(f'  ещё идут:   {len(rows) - len(dead)}')
    s = 1.0
    km = []
    print(f"\n{'день':>5} {'в риске':>9} {'обрывов':>9} {'доля живых':>12}")
    for t in sorted({r['life'] for r in rows}):
        n = sum(1 for r in rows if r['life'] >= t)
        dd = sum(1 for r in dead if r['life'] == t)
        if not n:
            break
        s *= (1 - dd / n)
        km.append((t, s))
        if t <= 25:
            print(f'{t:>5} {n:>9} {dd:>9} {100.0*s:>11.1f}%')
    half = next((t for t, v in km if v <= 0.5), None)
    print(f'\n  медианный срок жизни: '
          f'{str(half) + " суток" if half is not None else "не достигнут за наблюдение"}')

    print()
    print('=' * 72)
    print('СРОК ЖИЗНИ ПРОТИВ ЗОНЫ')
    print('сравнение честно только при одинаковой длине наблюдения: берутся базы,')
    print('прожившие под наблюдением не меньше 14 суток')
    sel = [r for r in rows if r['obs'] >= 14]
    print(f'  таких баз: {len(sel)}')
    print(f"    {'зона':<10} {'баз':>5} {'мед. срок':>10} {'доля мёртвых':>14} "
          f"{'поисковых/базу':>15}")
    g = collections.defaultdict(list)
    for r in sel:
        g[r['tld']].append(r)
    for k, v in sorted(g.items(), key=lambda kv: -len(kv[1])):
        if len(v) < 10:
            continue
        print(f'    {str(k):<10} {len(v):>5} {statistics.median(r["life"] for r in v):>10.1f} '
              f'{100.0*sum(1 for r in v if not r["alive"])/len(v):>13.1f}% '
              f'{sum(r["ya_sum"] for r in v)/len(v):>15.1f}')

    tot_ya = sum(r['ya_sum'] for r in rows)
    tot_all = sum(r['all_sum'] for r in rows)
    print(f'\nвсего кликов по этим базам {tot_all}, из поиска {tot_ya} '
          f'({100.0*tot_ya/tot_all:.1f}%)')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
