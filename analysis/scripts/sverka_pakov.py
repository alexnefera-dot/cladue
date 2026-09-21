#!/usr/bin/env python3
"""Сверка: у скольких баз пак известен из журнала запусков, но пуст в API.

Журнал запусков (`analysis/launch_*.txt`) — это выгрузка из интерфейса: секция
названа паком, под ней перечислены домены баз. API отдаёт `content_label` по
сабдомену. Вопрос — насколько одно расходится с другим.

Единица — база (домен). База считается «есть в API», если метка стоит хотя бы
у одного её сабдомена, и «есть в журнале», если домен упомянут хоть в одном
файле журнала.

    python3 sverka_pakov.py <панель.jsonl> <submeta.jsonl>
"""
import sys, os, json, collections, importlib.util

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
FIELDS = ['content_label', 'content_id', 'pack_kind', 'oform_version',
          'generation_runs_count', 'ya_account_id', 'cf_account_id', 'title_ru_len',
          'description_ru_len', 'additional_text_ru_len', 'additional_text_2_ru_len',
          'keywords_word_count', 'keywords_len', 'pipeline_started', 'recrawl_sent_at',
          'content_domain_url', 'schedule_trigger_mode']
IX = {k: n for n, k in enumerate(FIELDS)}


def journal():
    """Домен базы -> (имя пака, день) из журнала запусков."""
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
                for d in doms:
                    out.setdefault(d, (main, day))
    return out


def main(panel, metapath):
    meta = {}
    for line in open(metapath, encoding='utf-8'):
        a = json.loads(line)
        s, v = a[0], a[1:]
        meta[s] = [b if b is not None else c for b, c in zip(meta[s], v)] if s in meta else v

    jr = journal()
    base = collections.defaultdict(lambda: {'n': 0, 'api': 0, 'days': set(),
                                            'cl': 0, 'reg': 0, 'fd': 0})
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        b = r.get('content_domain_url')
        if not d or not b:
            continue
        a = base[b]
        a['n'] += 1
        a['days'].add(d)
        a['cl'] += r.get('ya_clicks') or 0
        a['reg'] += r.get('reg', 0)
        a['fd'] += r.get('fd', 0)
        v = meta.get(r['subdomain'])
        if v and v[IX['content_label']]:
            a['api'] += 1

    g = collections.defaultdict(lambda: {'b': 0, 'n': 0, 'cl': 0, 'reg': 0, 'fd': 0, 'list': []})
    for b, a in base.items():
        inapi = a['api'] > 0
        injr = b in jr
        k = ('в API и в журнале' if inapi and injr else
             'только в API' if inapi else
             'ТОЛЬКО В ЖУРНАЛЕ' if injr else
             'нигде')
        t = g[k]
        t['b'] += 1
        t['n'] += a['n']
        t['cl'] += a['cl']
        t['reg'] += a['reg']
        t['fd'] += a['fd']
        t['list'].append((b, min(a['days']), jr.get(b, (None, None))[0], a['n'], a['reg'], a['fd']))

    print('баз всего: %d, из них упомянуто в журнале запусков: %d'
          % (len(base), sum(1 for b in base if b in jr)))
    print('доменов в журнале, которых нет в панели: %d\n'
          % sum(1 for d in jr if d not in base))
    print('%-22s %6s %8s %11s %6s %5s' % ('', 'баз', 'сайтов', 'кликов', 'рег', 'ФД'))
    for k in ('в API и в журнале', 'только в API', 'ТОЛЬКО В ЖУРНАЛЕ', 'нигде'):
        t = g[k]
        if not t['b']:
            continue
        print('%-22s %6d %8d %11d %6d %5d' % (k, t['b'], t['n'], t['cl'], t['reg'], t['fd']))

    t = g['ТОЛЬКО В ЖУРНАЛЕ']
    if t['b']:
        print('\nБАЗЫ, У КОТОРЫХ ПАК ЕСТЬ В ЖУРНАЛЕ, НО МЕТКИ В API НЕТ')
        byday = collections.Counter(x[1] for x in t['list'])
        print('  по дням первого переобхода:')
        for d in sorted(byday):
            print('    %s  %3d баз' % (d, byday[d]))
        bypack = collections.Counter(x[2] for x in t['list'])
        print('  по пакам (сверху крупные):')
        for p, n in bypack.most_common(20):
            print('    %-44s %3d баз' % (str(p)[:43], n))

    t = g['нигде']
    if t['b']:
        print('\nБАЗЫ БЕЗ ИМЕНИ ВООБЩЕ: %d, сайтов %d, кликов %d, рег %d'
              % (t['b'], t['n'], t['cl'], t['reg']))
        byday = collections.Counter(x[1] for x in t['list'])
        for d in sorted(byday):
            print('    %s  %3d баз' % (d, byday[d]))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
