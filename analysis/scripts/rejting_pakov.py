#!/usr/bin/env python3
"""Рейтинг паков контента по входу в выдачу — шаг 1 плана `KAK_MERIT_KONTENT.md`.

Исход — **сабдомен получил клик из поиска в течение WINDOW суток от переобхода**.
Он выбран не потому, что интереснее денег, а потому, что на нём есть мощность:
23 тысячи событий против 399 регистраций и 61 ФД. Пак различим при семи базах
против семисот пятидесяти, которые понадобились бы на ФД.

Оговорка, которая никуда не девается: поисковый клик означает «стоит в выдаче и
по ней кликают», а не «в индексе».

Каждый пак сравнивается **с остальными паками**, страта — день переобхода: день
отбирает и партию, и погоду в выдаче. Пак, запущенный в день, когда других паков
не было, сравнивать не с чем — такие помечаются отдельно, а не выбрасываются
молча.

Окно должно быть досмотрено: сабдомены с переобходом позже, чем за WINDOW суток
до конца наблюдения, в расчёт не идут — иначе «не вышел» получится просто
потому, что не успели посмотреть.

    python3 rejting_pakov.py <панель.jsonl> <subs_life.jsonl> <конец YYYY-MM-DD>
                             [мин_сабдоменов]
"""
import sys, json, collections
from datetime import date, datetime, timedelta

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from or_mh import mh

WINDOW = 7


def main(panel, subs_path, obs_to, min_subs='400'):
    min_subs = int(min_subs)
    end = date.fromisoformat(obs_to)

    ya_first = {}
    for line in open(subs_path, encoding='utf-8'):
        s, n, y, f, l, yf, yl = json.loads(line)
        if yf:
            ya_first[s] = yf[:10]

    rows = []
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        rec = (r.get('recrawl_sent_at') or '')[:10]
        if not rec:
            continue
        d = date.fromisoformat(rec)
        if (end - d).days < WINDOW:
            continue                                  # окно не досмотрено
        yf = ya_first.get(r['subdomain'])
        hit = 1 if (yf and 0 <= (date.fromisoformat(yf) - d).days <= WINDOW) else 0
        rows.append((r.get('content') or 'пак неизвестен', rec, hit,
                     r.get('content_domain_url'), r.get('reg', 0), r.get('fd', 0)))

    print(f'сабдоменов с досмотренным окном {WINDOW} суток: {len(rows)}')
    hits = sum(r[2] for r in rows)
    print(f'вышли в поиск в окне: {hits} ({100.0*hits/len(rows):.1f}%)\n')

    packs = collections.defaultdict(lambda: {'n': 0, 'hit': 0, 'bases': set(),
                                             'reg': 0, 'fd': 0, 'days': set()})
    per_base = {}
    for c, rec, hit, base, reg, fd in rows:
        p = packs[c]
        p['n'] += 1
        p['hit'] += hit
        p['bases'].add(base)
        p['days'].add(rec)
        if base not in per_base:
            per_base[base] = True
            p['reg'] += 0
    # регистрации и ФД считаются по сабдоменам, база тут ни при чём
    for c, rec, hit, base, reg, fd in rows:
        packs[c]['reg'] += reg
        packs[c]['fd'] += fd

    # день -> (вышли, не вышли) по каждому паку, чтобы собрать страты
    byday = collections.defaultdict(lambda: collections.Counter())
    for c, rec, hit, base, reg, fd in rows:
        byday[rec][(c, hit)] += 1
    day_tot = {d: (sum(v for (c, h), v in cnt.items() if h),
                   sum(v for (c, h), v in cnt.items() if not h))
               for d, cnt in byday.items()}
    day_packs = {d: {c for (c, h) in cnt} for d, cnt in byday.items()}

    out = []
    for c, p in packs.items():
        if p['n'] < min_subs:
            continue
        tbl = []
        alone = True
        for d in p['days']:
            a = byday[d][(c, 1)]
            b = byday[d][(c, 0)]
            oth_hit = day_tot[d][0] - a
            oth_no = day_tot[d][1] - b
            if oth_hit + oth_no == 0:
                continue                              # в этот день пак был один
            alone = False
            tbl.append((a, oth_hit, b, oth_no))
        if not tbl:
            out.append((None, None, None, None, c, p, True))
            continue
        orv, lo, hi, pv = mh(tbl)
        out.append((orv, lo, hi, pv, c, p, alone))

    out.sort(key=lambda x: (x[0] is None, -(x[0] or 0)))
    print('=' * 104)
    print(f'РЕЙТИНГ ПАКОВ, исход «вышел в поиск за {WINDOW} суток», страта — день переобхода')
    print(f"{'пак':<44}{'баз':>5}{'сабдом.':>9}{'вышли':>8}{'OR к остальным':>22}"
          f"{'p':>10}{'рег':>5}{'ФД':>4}")
    for orv, lo, hi, pv, c, p, alone in out:
        share = 100.0 * p['hit'] / p['n']
        if orv is None:
            cell = 'не с чем сравнить'
            pcell = ''
        else:
            cell = f'{orv:.2f} [{lo:.2f}–{hi:.2f}]'
            pcell = f'{pv:.1e}'
        mark = ' ●' if (orv and lo > 1) else (' ○' if (orv and hi < 1) else '')
        print(f'{c[:43]:<44}{len(p["bases"]):>5}{p["n"]:>9}{share:>7.1f}%{cell:>22}'
              f'{pcell:>10}{p["reg"]:>5}{p["fd"]:>4}{mark}')

    good = [x for x in out if x[0] and x[1] > 1]
    bad = [x for x in out if x[0] and x[2] < 1]
    print(f'\n  ● заметно лучше остальных: {len(good)} паков')
    print(f'  ○ заметно хуже: {len(bad)} паков')
    print(f'  остальные {len(out) - len(good) - len(bad)} — интервал накрывает единицу')
    if good:
        print(f'\n  лучшие: ' + ', '.join(f'{x[4]} ({x[0]:.2f})' for x in good[:5]))
    if bad:
        print(f'  худшие: ' + ', '.join(f'{x[4]} ({x[0]:.2f})' for x in bad[-5:]))
    print(f'\n  паков меньше {min_subs} сабдоменов, не попали в рейтинг: '
          f'{sum(1 for p in packs.values() if p["n"] < min_subs)} из {len(packs)}')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(*sys.argv[1:5])
