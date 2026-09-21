#!/usr/bin/env python3
"""Добор новых дней в панель без полной перевыгрузки.

Панель строилась по реестру `/v1/subdomains`, досмотренному по 18.09, а клики
и конверсии тянулись до 21.09. Из-за этого запуски 19–21.09 в анализе
отсутствовали вовсе — не «ноль результатов», а ни одной строки.

Здесь новые сабдомены из свежей выгрузки реестра достраиваются в панель:
клики берутся из свежей выгрузки трекера, конверсии — из накопительного
архива, имя пака — из `content_label`, иначе из журнала запусков.

    python3 dobrat_dni.py <панель.jsonl> <новая-выгрузка-реестра.jsonl>
                          <свежие-клики.jsonl> <архив-конверсий.jsonl>
                          <новая-панель.jsonl>
"""
import sys, os, json, collections, importlib.util

SCRIPTS = os.path.dirname(os.path.abspath(__file__))

KEEP = ('subdomain', 'content_domain_id', 'content_domain_url', 'brand_id', 'brand_label',
        'tld', 'base_name_pattern', 'base_label_len', 'content_label', 'oform_version',
        'pack_kind', 'pages_count', 'template', 'start_hour', 'start_dow', 'is_weekend',
        'is_night_kiev', 'pipeline_started', 'recrawl_sent_at', 'yandex_pipeline_stage',
        'verification_status', 'verification_fail_count', 'keywords_len', 'sub_len',
        'ref_link_host', 'cf_account_id', 'ya_account_id', 'css_palette_hash',
        'css_bg_luminance', 'css_button_luminance', 'contrast_body_text',
        'contrast_button_text', 'contrast_link', 'first_click_at', 'clicks_sum',
        'views_sum', 'days_to_first_click_after_recrawl')


def journal():
    spec = importlib.util.spec_from_file_location('panelmod', os.path.join(SCRIPTS, 'panel.py'))
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    return m.content_by_domain()


def block(day, hour):
    if hour is None:
        return None
    return '00-05' if hour < 6 else '06-11' if hour < 12 else '12-17' if hour < 18 else '18-23'


def main(panel, regpath, clickpath, convpath, out):
    have = set()
    n_old = 0
    with open(panel, encoding='utf-8') as f, open(out, 'w', encoding='utf-8') as fo:
        for line in f:
            r = json.loads(line)
            have.add(r['subdomain'])
            n_old += 1
            fo.write(line if line.endswith('\n') else line + '\n')

        new = {}
        for line in open(regpath, encoding='utf-8'):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not isinstance(r, dict) or not r.get('subdomain'):
                continue
            s = r['subdomain'].lower()
            if s in have or s in new:
                continue
            new[s] = {k: r.get(k) for k in KEEP}
        print('в панели было %d строк; новых сабдоменов в реестре: %d' % (n_old, len(new)))
        if not new:
            print('добавлять нечего')
            return

        cl = collections.defaultdict(lambda: [0, 0])
        for line in open(clickpath, encoding='utf-8'):
            r = json.loads(line)
            s = (r.get('subdomain') or '').lower()
            if s not in new:
                continue
            h = r.get('referer') or ''
            cl[s][0] += 1
            if 'yandex' in h or '//ya.ru' in h:
                cl[s][1] += 1

        conv = collections.defaultdict(lambda: [0, 0])
        for line in open(convpath, encoding='utf-8'):
            r = json.loads(line)
            s = (r.get('subdomain') or '').lower()
            conv[s][0 if r.get('event') == 'reg' else 1] += 1

        jr = journal()
        days = collections.Counter()
        for s, r in new.items():
            d = (r.get('recrawl_sent_at') or '')[:10]
            days[d] += 1
            r['subdomain'] = s
            r['recrawl_hour'] = (int(r['recrawl_sent_at'][11:13])
                                 if r.get('recrawl_sent_at') else None)
            r['recrawl_block'] = block(d, r['recrawl_hour'])
            r['recrawl_dow'] = r.get('start_dow')
            r['content'] = r.get('content_label') or jr.get(r.get('content_domain_url'),
                                                            (None, None))[0]
            r['clicks_sum'], r['ya_clicks'] = cl[s]
            r['reg'], r['fd'] = conv.get(s, [0, 0])
            r['case'] = bool(r['reg'] or r['fd'])
            r['window_closed'] = False
            fo.write(json.dumps(r, ensure_ascii=False) + '\n')

    print('добавлено по дням переобхода:')
    for d in sorted(days):
        print('  %-12s %6d сайтов' % (d or '(без даты)', days[d]))
    print('-> %s' % out)


if __name__ == '__main__':
    if len(sys.argv) < 6:
        sys.exit(__doc__)
    main(*sys.argv[1:6])
