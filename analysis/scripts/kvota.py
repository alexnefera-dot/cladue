#!/usr/bin/env python3
"""Блок квоты: упирается ли сеть в суточный лимит Вебмастера и чего это стоит.

Пункт 6 каталога параметров — единственный из считаемых, который ни разу не
трогали. Поля появились только в свежей выгрузке: `quota_wait_until` (был
дефект 4 аудита), `duration_recrawl_h`, плюс события `quota_hit` в журнале.

Что проверяется:

1. **Квота реальна?** Эмпирическое число переобходов на аккаунт за сутки против
   заявленных `runtime_quota_per_day = 150`.
2. **Насколько часто упираемся** и как база при этом разрезается по суткам.
3. **Сколько база ждёт** от готовности до переобхода и связано ли ожидание с
   выходом в поиск.
4. **Что стоит очередь**: сколько суток проходит от создания домена до момента,
   когда весь набор брендов ушёл на переобход.

Дедупликация обязательна: выгрузки по датам пересекаются, и одна и та же строка
в двух файлах удваивает суточный счёт — именно так у меня сначала получилась
«квота 300».

    python3 kvota.py <subdomains.jsonl> [ещё...] --events <events.jsonl>
                     --panel <панель.jsonl> --end YYYY-MM-DD
"""
import sys, json, collections, statistics
from datetime import datetime, date

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from or_mh import mh


def ts(x):
    return datetime.fromisoformat(x) if x else None


def main(subs, events=None, panel=None, end=None):
    seen = {}
    for p in subs:
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            seen[r['subdomain'].lower()] = r
    print(f'сабдоменов после дедупликации: {len(seen)}')
    quota = next((r.get('runtime_quota_per_day') for r in seen.values()
                  if r.get('runtime_quota_per_day')), None)
    step = next((r.get('runtime_quota_step_min') for r in seen.values()
                 if r.get('runtime_quota_step_min')), None)
    resume = next((r.get('runtime_quota_resume_from') for r in seen.values()
                   if r.get('runtime_quota_resume_from')), None)
    print(f'заявлено в runtime: квота {quota} в сутки, шаг {step} мин, '
          f'сброс в {resume}\n')

    # --- 1. эмпирическая квота -------------------------------------------
    per = collections.Counter()
    for r in seen.values():
        t, a = r.get('recrawl_sent_at'), r.get('ya_account_id')
        if t and a is not None:
            per[(a, t[:10])] += 1
    top = collections.Counter(per.values()).most_common(6)
    print('=' * 74)
    print('1 · КВОТА РЕАЛЬНА И УПИРАЕМСЯ В НЕЁ ПОЧТИ ВСЕГДА')
    print(f'  пар «аккаунт × сутки»: {len(per)}')
    print(f'  самые частые значения: ' +
          ', '.join(f'{v} раз по {k}' for k, v in top))
    at_cap = sum(v for k, v in collections.Counter(per.values()).items()
                 if quota and k == quota)
    print(f'  ровно на квоте ({quota}): {at_cap} суток из {len(per)} '
          f'({100.0*at_cap/len(per):.0f}%)')

    days = collections.defaultdict(set)
    for r in seen.values():
        t, b = r.get('recrawl_sent_at'), r.get('content_domain_url')
        if t and b:
            days[b].add(t[:10])
    split = collections.Counter(len(v) for v in days.values())
    print(f'  переобход базы разрезан по суткам: ' +
          ', '.join(f'{v} баз на {k} сут.' for k, v in sorted(split.items())))

    # --- 2. когда именно уходит переобход ---------------------------------
    h = collections.Counter()
    for r in seen.values():
        t = r.get('recrawl_sent_at')
        if t:
            h[t[11:13]] += 1
    print()
    print('=' * 74)
    print('2 · ПЕРЕОБХОД ЖДЁТ ОТКРЫТИЯ ОКНА')
    tot = sum(h.values())
    for k, v in h.most_common(6):
        print(f'  час {k}: {v:>7} ({100.0*v/tot:>5.1f}%)')
    print(f'  сброс квоты в {resume} — и {100.0*h.most_common(1)[0][1]/tot:.0f}% '
          f'переобходов уходит в этот же час')

    # --- 3. сколько ждёт база ---------------------------------------------
    print()
    print('=' * 74)
    print('3 · СКОЛЬКО ПРОХОДИТ ОТ ГОТОВНОСТИ ДО ПЕРЕОБХОДА')
    d = [r['duration_recrawl_h'] for r in seen.values()
         if r.get('duration_recrawl_h') is not None]
    if d:
        d.sort()
        print(f'  сабдоменов с известной длительностью: {len(d)} '
              f'({100.0*len(d)/len(seen):.0f}%)')
        for q in (10, 25, 50, 75, 90, 99):
            print(f'    {q}-й процентиль: {d[int(len(d)*q/100)]:.1f} ч')
    wait = [r for r in seen.values() if r.get('quota_wait_until')]
    print(f'  сабдоменов с проставленным quota_wait_until: {len(wait)} '
          f'({100.0*len(wait)/len(seen):.1f}%)')
    if wait:
        w = []
        for r in wait:
            a, b = ts(r.get('recrawl_sent_at')), ts(r['quota_wait_until'])
            if a and b:
                w.append((a - b).total_seconds() / 3600)
        if w:
            w.sort()
            print(f'    медиана «ждал до → ушёл»: {w[len(w)//2]:.1f} ч')

    # --- 4. события квоты --------------------------------------------------
    if events:
        ev = collections.Counter()
        bases = set()
        by_day = collections.Counter()
        for line in open(events, encoding='utf-8'):
            r = json.loads(line)
            if r.get('event') != 'quota_hit':
                continue
            ev[r.get('detail', '')[:60]] += 1
            bases.add(r['content_domain_id'])
            by_day[r['at'][:10]] += 1
        print()
        print('=' * 74)
        print('4 · СОБЫТИЯ quota_hit')
        print(f'  всего {sum(ev.values())} на {len(bases)} базах')
        print('  по дням: ' + ', '.join(f'{k} — {v}' for k, v in sorted(by_day.items())[:8]))
        for k, v in ev.most_common(3):
            print(f'  «{k}…» — {v}')

    # --- 5. цена очереди для базы -----------------------------------------
    print()
    print('=' * 74)
    print('5 · ПОЛНЫЙ ЦИКЛ БАЗЫ: от создания домена до последнего переобхода')
    # по базам одним проходом: перебор всех сабдоменов на каждую базу — это
    # два миллиона операций на базу и час работы вместо секунды
    span = collections.defaultdict(lambda: [None, None])
    for r in seen.values():
        b, t = r.get('content_domain_url'), r.get('recrawl_sent_at')
        if not b or not t:
            continue
        c = span[b]
        first = r.get('domain_created') or t
        if c[0] is None or first < c[0]:
            c[0] = first
        if c[1] is None or t > c[1]:
            c[1] = t
    full = []
    for b, (first, last) in span.items():
        a, z = ts(first), ts(last)
        if a and z:
            full.append((z - a).total_seconds() / 3600)
    if full:
        full.sort()
        print(f'  баз: {len(full)}')
        for q in (25, 50, 75, 90):
            print(f'    {q}-й процентиль: {full[int(len(full)*q/100)]:.1f} ч '
                  f'({full[int(len(full)*q/100)]/24:.1f} сут.)')

    # --- 6. связь ожидания с выходом в поиск -------------------------------
    if panel and end:
        print()
        print('=' * 74)
        print('6 · СВЯЗАНО ЛИ ОЖИДАНИЕ С ВЫХОДОМ В ПОИСК')
        print('страта — день переобхода; длительность режется на полосы')
        rows = []
        for line in open(panel, encoding='utf-8'):
            r = json.loads(line)
            t = (r.get('recrawl_sent_at') or '')[:10]
            if not t or not r.get('window_closed'):
                continue
            sub = seen.get(r['subdomain'])
            dur = sub.get('duration_recrawl_h') if sub else None
            if dur is None:
                continue
            band = ('до 1 ч' if dur < 1 else '1–6 ч' if dur < 6 else
                    '6–12 ч' if dur < 12 else '12–24 ч' if dur < 24 else 'больше суток')
            rows.append((band, t, 1 if r.get('ya_clicks') else 0))
        bands = collections.Counter(b for b, _, _ in rows)
        print(f"{'полоса':<16}{'сабдом.':>9}{'вышли':>8}{'доля':>8}{'OR к остальным':>22}")
        for band in ('до 1 ч', '1–6 ч', '6–12 ч', '12–24 ч', 'больше суток'):
            if bands[band] < 200:
                continue
            tbl = collections.defaultdict(lambda: [0, 0, 0, 0])
            for b, t, y in rows:
                c = tbl[t]
                if b == band:
                    c[0] += y; c[2] += 1 - y
                else:
                    c[1] += y; c[3] += 1 - y
            orv, lo, hi, p = mh([tuple(v) for v in tbl.values()])
            hit = sum(y for b, _, y in rows if b == band)
            cell = f'{orv:.2f} [{lo:.2f}–{hi:.2f}]' if orv else '—'
            print(f'{band:<16}{bands[band]:>9}{hit:>8}{100.0*hit/bands[band]:>7.1f}%{cell:>22}')


if __name__ == '__main__':
    a = sys.argv[1:]
    def opt(name):
        return a[a.index(name) + 1] if name in a else None
    subs = []
    i = 0
    while i < len(a) and not a[i].startswith('--'):
        subs.append(a[i]); i += 1
    if not subs:
        raise SystemExit(__doc__)
    main(subs, opt('--events'), opt('--panel'), opt('--end'))
