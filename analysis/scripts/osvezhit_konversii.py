#!/usr/bin/env python3
"""Пересчёт `reg` и `fd` в панели по свежему архиву конверсий.

Клики я обновляю отдельной выгрузкой, а конверсии до 21.09 брались из архива,
досмотренного по 18.09. Конверсия приходит позже клика — от нескольких часов
до нескольких суток, — поэтому у сентябрьских запусков регистрации были
недосчитаны, и чем свежее запуск, тем сильнее.

Здесь `reg` и `fd` каждой строки панели переписываются заново из архива, без
перевыгрузки кликов и сабдоменов. Привязка та же, что в `panel.py`: по полю
`subdomain` конверсии.

    python3 osvezhit_konversii.py <старая-панель.jsonl> <архив-конверсий.jsonl>
                                  <новая-панель.jsonl>
"""
import sys, json, collections


def main(old, convpath, new):
    conv = collections.defaultdict(lambda: [0, 0])
    total = collections.Counter()
    for line in open(convpath, encoding='utf-8'):
        r = json.loads(line)
        s = (r.get('subdomain') or '').lower()
        ev = r.get('event')
        total[ev] += 1
        conv[s][0 if ev == 'reg' else 1] += 1
    print('архив конверсий: %s' % dict(total))

    ch = collections.Counter()
    before = after = beforefd = afterfd = 0
    byday = collections.defaultdict(lambda: [0, 0, 0, 0])
    with open(old, encoding='utf-8') as fi, open(new, 'w', encoding='utf-8') as fo:
        for line in fi:
            r = json.loads(line)
            s = r['subdomain']
            b, bf = r.get('reg', 0), r.get('fd', 0)
            a, af = conv.get(s, [0, 0])
            before += b
            beforefd += bf
            after += a
            afterfd += af
            d = (r.get('recrawl_sent_at') or '')[:10]
            if d:
                t = byday[d]
                t[0] += b
                t[1] += a
                t[2] += bf
                t[3] += af
            if (a, af) != (b, bf):
                ch['строк изменилось'] += 1
            r['reg'], r['fd'] = a, af
            r['case'] = bool(a or af)
            fo.write(json.dumps(r, ensure_ascii=False) + '\n')

    print('регистраций было %d, стало %d (%+d)' % (before, after, after - before))
    print('ФД было %d, стало %d (%+d)' % (beforefd, afterfd, afterfd - beforefd))
    print('%s' % dict(ch))
    print('\nгде прибавилось — по дню переобхода')
    print('день        рег было  рег стало  разница   ФД было  ФД стало  разница')
    for d in sorted(byday):
        t = byday[d]
        if t[0] == t[1] and t[2] == t[3]:
            continue
        print('%s %9d %10d %+8d %9d %9d %+8d'
              % (d, t[0], t[1], t[1] - t[0], t[2], t[3], t[3] - t[2]))


if __name__ == '__main__':
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
