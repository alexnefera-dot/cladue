#!/usr/bin/env python3
"""Досчёт кликов за 19–21.09 в старых строках панели.

Панель строилась с кликами, досмотренными по 18.09. Строки, добранные за
19–21.09, считались по свежей выгрузке. Из-за этого `ya_clicks` у разных дней
означал разное, и «регистраций на десять тысяч кликов» у последних дней
выходило втрое завышенным.

Здесь к каждой старой строке добавляются клики строго после 18.09 — период,
которого в панели не было, так что двойного счёта нет. Новые строки не
трогаются: у них клики уже посчитаны по всему свежему окну.

    python3 dobrat_kliki.py <панель.jsonl> <свежие-клики.jsonl> <новая-панель.jsonl>
                            [граница YYYY-MM-DD]
"""
import sys, json, collections

def main(panel, fresh, out, edge='2026-09-18'):
    add = collections.defaultdict(lambda: [0, 0])
    for line in open(fresh, encoding='utf-8'):
        r = json.loads(line)
        at = (r.get('at') or '')[:10]
        if not at or at <= edge:
            continue
        s = (r.get('subdomain') or '').lower()
        h = r.get('referer') or ''
        add[s][0] += 1
        if 'yandex' in h or '//ya.ru' in h:
            add[s][1] += 1
    print('сабдоменов с кликами после %s: %d' % (edge, len(add)))

    before = after = 0
    touched = 0
    byday = collections.defaultdict(lambda: [0, 0])
    with open(panel, encoding='utf-8') as fi, open(out, 'w', encoding='utf-8') as fo:
        for line in fi:
            r = json.loads(line)
            d = (r.get('recrawl_sent_at') or '')[:10]
            b = r.get('ya_clicks') or 0
            before += b
            # строки, добранные из свежего реестра, уже содержат эти клики
            if d and d <= edge:
                c, y = add.get(r['subdomain'], [0, 0])
                if y or c:
                    touched += 1
                    r['ya_clicks'] = b + y
                    r['clicks_sum'] = (r.get('clicks_sum') or 0) + c
            after += r.get('ya_clicks') or 0
            if d:
                t = byday[d]
                t[0] += b
                t[1] += r.get('ya_clicks') or 0
            fo.write(json.dumps(r, ensure_ascii=False) + '\n')
    print('поисковых кликов было %d, стало %d (+%d); строк дополнено %d'
          % (before, after, after - before, touched))
    print('\nдень        кликов было  стало   прибавка')
    for d in sorted(byday):
        t = byday[d]
        if t[0] == t[1]:
            continue
        print('%s %12d %8d %+9d' % (d, t[0], t[1], t[1] - t[0]))


if __name__ == '__main__':
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(*sys.argv[1:5])
