#!/usr/bin/env python3
"""Остальные пункты каталога: то, что ни разу не считалось.

Поля, появившиеся в выгрузке только сейчас (`pack_kind`, `oform_version`,
`generation_runs_count`, `pipeline_error`), плюс те, до которых не доходили руки
(`base_label_len`, возраст домена, вложенность, суточный профиль, оффер).

Уровень каждого разреза берётся из каталога `PLAN_PARAMETROV.md`:
база чистится стратой по дню переобхода, сабдомен — стратой по бренду.
Признаки, привязанные к бренду один в один (`api_form`, `popup`,
`established_year`, `ref_link_slug`), отдельно не считаются — это бренд.

    python3 ostalnoe.py <панель.jsonl> <subdomains.jsonl>[,…] [клики.jsonl]
"""
import sys, json, collections
from datetime import datetime

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from or_mh import mh


def cut(rows, field, strata_key, title, min_n=500):
    """Каждое значение против остальных, страта — strata_key."""
    vals = collections.Counter(r[field] for r in rows if r.get(field) is not None)
    print(f'\n{title}')
    print(f"{'значение':<26}{'сабдом.':>9}{'вышли':>8}{'доля':>8}"
          f"{'OR к остальным':>22}{'конв':>6}")
    for v, n in vals.most_common(10):
        if n < min_n:
            continue
        tbl = collections.defaultdict(lambda: [0, 0, 0, 0])
        hit = cv = 0
        for r in rows:
            c = tbl[r[strata_key]]
            y = r['y']
            if r.get(field) == v:
                c[0] += y
                c[2] += 1 - y
                hit += y
                cv += r['cv']
            else:
                c[1] += y
                c[3] += 1 - y
        orv, lo, hi, p = mh([tuple(x) for x in tbl.values()])
        cell = f'{orv:.2f} [{lo:.2f}–{hi:.2f}]' if orv else '—'
        print(f'{str(v)[:25]:<26}{n:>9}{hit:>8}{100.0*hit/n:>7.1f}%{cell:>22}{cv:>6}')


def main(panel, subs_paths, clicks=None):
    extra = {}
    for p in subs_paths:
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            extra[r['subdomain'].lower()] = (
                r.get('generation_runs_count'), r.get('pipeline_error'),
                r.get('domain_created'), r.get('pack_kind'), r.get('oform_version'))

    rows = []
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        if not r.get('window_closed'):
            continue
        day = (r.get('recrawl_sent_at') or '')[:10]
        if not day:
            continue
        g, err, dcre, pk, ofv = extra.get(r['subdomain'], (None, None, None, None, None))
        age = None
        if dcre and r.get('recrawl_sent_at'):
            h = (datetime.fromisoformat(r['recrawl_sent_at'])
                 - datetime.fromisoformat(dcre)).total_seconds() / 3600
            age = ('до 6 ч' if h < 6 else '6–12 ч' if h < 12 else
                   '12–24 ч' if h < 24 else 'больше суток')
        rows.append({
            'y': 1 if r.get('ya_clicks') else 0,
            'cv': r.get('reg', 0) + r.get('fd', 0),
            'day': day, 'brand': r.get('brand_label'),
            'pack_kind': pk or r.get('pack_kind'),
            'oform_version': ofv or r.get('oform_version'),
            'generation_runs_count': g,
            'base_label_len': r.get('base_label_len'),
            'domain_age': age,
            'err_class': (None if not err else
                          'квота' if 'квота' in err else
                          'верификация' if 'VERIFICATION' in err else
                          'ошибки в партии' if err.startswith('Ошибки') else 'прочее'),
        })
    print(f'сабдоменов с закрытым окном: {len(rows)}, '
          f'вышли в поиск: {sum(r["y"] for r in rows)}')

    print('\n' + '=' * 78)
    print('УРОВЕНЬ БАЗЫ — страта по дню переобхода')
    for f, t in (('pack_kind', 'ВИД ПАКА (поле API, а не разбор имени)'),
                 ('oform_version', 'ВЕРСИЯ ОФОРМЛЕНИЯ'),
                 ('generation_runs_count', 'СКОЛЬКО РАЗ ГЕНЕРИРОВАЛСЯ ПАК'),
                 ('base_label_len', 'ДЛИНА ИМЕНИ БАЗЫ'),
                 ('domain_age', 'ВОЗРАСТ ДОМЕНА К МОМЕНТУ ПЕРЕОБХОДА'),
                 ('err_class', 'КЛАСС pipeline_error')):
        cut(rows, f, 'day', t)

    if clicks:
        print('\n' + '=' * 78)
        print('КЛИКИ: вложенность, суточный профиль, источник')
        nest = collections.Counter()
        hour = collections.Counter()
        hour_ya = collections.Counter()
        alice = collections.Counter()
        n = 0
        for line in open(clicks, encoding='utf-8'):
            r = json.loads(line)
            n += 1
            ref = r.get('referer') or ''
            path = r.get('exit_path') or ''
            lvl = sum(1 for x in path.split('/') if x == 'ru')
            ya = 'yandex' in ref or '//ya.ru' in ref
            if ya:
                nest[min(lvl, 6)] += 1
                hour_ya[r['at'][11:13]] += 1
                if 'alice.' in ref:
                    alice[r.get('subdomain', '')[:40]] += 1
            hour[r['at'][11:13]] += 1
        print(f'\nвложенность /ru у поисковых кликов (всего кликов в файле {n}):')
        for k in sorted(nest):
            print(f'  уровней {k}: {nest[k]:>8} ({100.0*nest[k]/max(sum(nest.values()),1):>5.1f}%)')
        print('\nсуточный профиль, доля кликов по часам:')
        t1, t2 = sum(hour.values()), sum(hour_ya.values())
        for h in sorted(hour):
            a, b = 100.0 * hour[h] / t1, 100.0 * hour_ya[h] / max(t2, 1)
            print(f'  {h}: все {a:>5.2f}%  поиск {b:>5.2f}%  {"#" * int(b * 4)}')
        if alice:
            print(f'\nклики с alice.yandex.ru: {sum(alice.values())} '
                  f'на {len(alice)} сабдоменах')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2].split(','),
         sys.argv[3] if len(sys.argv) > 3 else None)
