#!/usr/bin/env python3
"""Панель для анализа: строка = сабдомен, атрибуты запуска + клики + конверсии.

Шаг 0 плана (`analysis/spec/PLAN_ANALIZA.md`). Соединяет две системы по ключу
`subdomain` и режет по правилу окна: в выборку идут только сабдомены с закрытым
окном — не меньше WINDOW_DAYS суток от `recrawl_sent_at` до конца наблюдения.

Принадлежность сети определяется **ключом**, а не полем `campaign` трекера:
кампания там — это бренд или оффер (`apex_engine`, `kush_engine`, `leebet`…),
и наши сабдомены расходятся по многим кампаниям. Источник истины — выгрузка
`/v1/subdomains`.

    python3 panel.py <subdomains.jsonl> <clicks.jsonl>[,<clicks2.jsonl>] \\
                     <conversions.jsonl> <наблюдение_до YYYY-MM-DD> [панель.jsonl]
"""
import os, re, sys, json, collections, importlib.util
from datetime import date, datetime, timedelta

WINDOW_DAYS = 6          # правило мануала: окно закрыто через 6 суток от recrawl

# что тянем из /v1/subdomains: только то, что идёт в анализ
KEEP = ('subdomain', 'content_domain_id', 'content_domain_url', 'brand_id', 'brand_label',
        'tld', 'base_name_pattern', 'base_label_len', 'content_label', 'oform_version',
        'pack_kind', 'pages_count', 'template', 'start_hour', 'start_dow', 'is_weekend',
        'is_night_kiev', 'pipeline_started', 'recrawl_sent_at', 'yandex_pipeline_stage',
        'verification_status', 'verification_fail_count', 'cf_account_id',
        'css_bg_luminance', 'css_button_luminance', 'contrast_body_text',
        'contrast_button_text', 'contrast_link', 'css_palette_hash', 'clicks_sum',
        'views_sum', 'first_click_at', 'days_to_first_click_after_recrawl',
        'ref_link_host', 'sub_len', 'keywords_len')


SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def content_by_domain():
    """Имя пака по домену базы — из реестра запусков.

    `content_label` в API пуст у 99.7% строк (заполнен у трёх имён из 226 000),
    поэтому имя берётся из `analysis/launch_*.txt`: заголовок секции и есть имя
    контента. Хвосты заголовка («_1…_50», «— id 1557-1606, создан 21:51»)
    срезаются: по мануалу контент — одно значение, имя целиком, но без номера
    экземпляра пака.
    """
    spec = importlib.util.spec_from_file_location('alltxt', os.path.join(SCRIPTS, 'alltxt.py'))
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    out = {}
    for day, files in m.FILES.items():
        for f in files:
            for main, _extra, doms in m.parse(f):
                name = _norm_content(main)
                for d in doms:
                    out[d] = (name, day)
    return out


def _norm_content(h):
    if not h:
        return None
    s = h.split(' — ')[0].split(' - ')[0].split(',')[0].strip()
    s = re.sub(r'\s*\(.*?\)\s*$', '', s)
    s = re.sub(r'[_\s]*\d+\s*[…\.]{1,3}\s*_?\d*$', '', s)   # _1…_50
    s = re.sub(r'_\d+$', '', s)                                # _44
    s = s.strip(' ,;')
    if not s or len(s) < 4 or re.match(r'^[А-ЯЁ\s\d]+$', s):
        return None
    return s


def ts(x):
    return datetime.fromisoformat(x) if x else None


def nesting(path):
    return sum(1 for x in (path or '').split('/') if x == 'ru')


def load_subdomains(path):
    rows = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            rows[r['subdomain'].lower()] = {k: r.get(k) for k in KEEP}
    return rows


def add_clicks(rows, paths, stat):
    """Клики всех кампаний: наши строки отбираются по ключу."""
    for p in paths:
        with open(p, encoding='utf-8') as f:
            for line in f:
                r = json.loads(line)
                s = (r.get('subdomain') or '').lower()
                stat['клики всего'] += 1
                row = rows.get(s)
                if row is None:
                    stat['клики не нашей сети'] += 1
                    continue
                stat['клики наши'] += 1
                row['clicks'] = row.get('clicks', 0) + 1
                if r.get('is_bot'):
                    row['bots'] = row.get('bots', 0) + 1
                if nesting(r.get('exit_path')):
                    row['deep'] = row.get('deep', 0) + 1
                h = (r.get('referer') or '')
                if 'yandex' in h or '//ya.ru' in h:
                    row['ya_clicks'] = row.get('ya_clicks', 0) + 1
                at = r.get('at')
                if at and (row.get('first_click') is None or at < row['first_click']):
                    row['first_click'] = at
                row.setdefault('campaigns', set()).add(r.get('campaign'))


def add_conversions(rows, path, stat):
    for line in open(path, encoding='utf-8'):
        r = json.loads(line)
        s = (r.get('subdomain') or '').lower()
        stat['конверсии всего'] += 1
        row = rows.get(s)
        if row is None:
            stat['конверсии не нашей сети'] += 1
            continue
        stat['конверсии наши'] += 1
        row['reg' if r.get('event') == 'reg' else 'fd'] = \
            row.get('reg' if r.get('event') == 'reg' else 'fd', 0) + 1


def main(subs_path, clicks_paths, conv_path, obs_to, out=None):
    stat = collections.Counter()
    rows = load_subdomains(subs_path)
    print(f"сабдоменов в выгрузке запусков: {len(rows)}")

    reg = content_by_domain()
    named = 0
    for r in rows.values():
        name, day = reg.get(r.get('content_domain_url'), (None, None))
        r['content'] = r.get('content_label') or name
        r['launch_day'] = day
        named += bool(r['content'])
    print(f"имя контента известно у {named} ({100.0*named/len(rows):.1f}%), "
          f"из них из API {sum(1 for r in rows.values() if r.get('content_label'))}")

    add_clicks(rows, clicks_paths, stat)
    add_conversions(rows, conv_path, stat)

    # производные: часы. Мануал требует блоки по 6 часов — 24 категории разом
    # дают «значимые» часы случайно, а час цикличен (23 и 0 соседние).
    for r in rows.values():
        t = ts(r.get('recrawl_sent_at'))
        r['recrawl_hour'] = t.hour if t else None
        r['recrawl_block'] = f"{t.hour // 6 * 6:02d}-{t.hour // 6 * 6 + 5:02d}" if t else None
        r['recrawl_dow'] = t.weekday() if t else None
        h = r.get('start_hour')
        r['start_block'] = f"{h // 6 * 6:02d}-{h // 6 * 6 + 5:02d}" if h is not None else None

    # окно: закрыто, если от recrawl_sent_at прошло WINDOW_DAYS до конца наблюдения
    end = datetime.fromisoformat(obs_to + 'T23:59:59+03:00')
    closed = 0
    for r in rows.values():
        t = ts(r.get('recrawl_sent_at'))
        r['window_closed'] = bool(t and (end - t) >= timedelta(days=WINDOW_DAYS))
        r['case'] = bool(r.get('reg') or r.get('fd'))
        r['campaigns'] = sorted(x for x in r.pop('campaigns', ()) if x)
        closed += r['window_closed']

    cases = sum(1 for r in rows.values() if r['case'] and r['window_closed'])
    print(f"\nсоединение по ключу:")
    for k in ('клики всего', 'клики наши', 'клики не нашей сети',
              'конверсии всего', 'конверсии наши', 'конверсии не нашей сети'):
        print(f"  {k:<26} {stat[k]:>9}")
    print(f"\nокно {WINDOW_DAYS} суток от recrawl_sent_at, наблюдение до {obs_to}:")
    print(f"  сабдоменов с закрытым окном {closed}  ({100.0*closed/len(rows):.1f}%)")
    print(f"  из них случаев (есть конверсия) {cases}")

    if out:
        with open(out, 'w', encoding='utf-8') as f:
            for r in rows.values():
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        print(f"\n-> {out}")


if __name__ == '__main__':
    if len(sys.argv) < 5:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2].split(','), sys.argv[3], sys.argv[4],
         sys.argv[5] if len(sys.argv) > 5 else None)
