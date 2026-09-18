#!/usr/bin/env python3
"""Каталог параметров: что вообще есть в выгрузке и что с этим можно сделать.

Для каждого поля считается три вещи, и все три решают его судьбу в анализе:

1. **Заполненность.** Пустое поле — не фактор, а заявка разработчику.
2. **Число различных значений.** Константа на всю сеть — не фактор, а описание.
3. **Уровень.** Меняется ли поле внутри базы (уровень сабдомена), внутри дня
   (уровень базы), только между днями (уровень дня) или не меняется вовсе
   (уровень сети). Уровень определяет, какой стратой фактор чистится, и
   чистится ли вообще: фактор уровня дня стратой по дню не чистится — он с ней
   коллинеарен.

    python3 parametry.py <subdomains.jsonl> [ещё...] [--rows N]
"""
import sys, json, collections

SKIP_VALUES = 40          # больше этого — считаем непрерывным


def main(paths, limit=120000):
    rows = []
    for p in paths:
        with open(p, encoding='utf-8') as f:
            for line in f:
                rows.append(json.loads(line))
                if len(rows) >= limit:
                    break
        if len(rows) >= limit:
            break

    keys = sorted({k for r in rows[:2000] for k in r})
    print(f'строк в профиле: {len(rows)}, полей: {len(keys)}\n')

    by_base = collections.defaultdict(list)
    for r in rows:
        b = r.get('content_domain_url')
        if b:
            by_base[b].append(r)
    by_day = collections.defaultdict(set)
    for r in rows:
        d = (r.get('recrawl_sent_at') or r.get('pipeline_started') or '')[:10]
        b = r.get('content_domain_url')
        if d and b:
            by_day[d].add(b)

    out = []
    for k in keys:
        vals = [r.get(k) for r in rows]
        filled = sum(1 for v in vals if v is not None and v != '')
        if not filled:
            out.append((k, 0.0, 0, 'пусто', '—'))
            continue
        uniq = len({str(v) for v in vals if v is not None})

        # меняется ли внутри базы
        in_base = sum(1 for b, rs in by_base.items()
                      if len({str(r.get(k)) for r in rs}) > 1)
        share_in_base = in_base / max(len(by_base), 1)

        # меняется ли между базами одного дня
        in_day = 0
        days = 0
        for d, bases in by_day.items():
            if len(bases) < 2:
                continue
            days += 1
            per = {}
            for b in bases:
                s = {str(r.get(k)) for r in by_base[b]}
                per[b] = next(iter(s)) if len(s) == 1 else '<varies>'
            if len(set(per.values())) > 1:
                in_day += 1
        share_in_day = in_day / max(days, 1)

        if share_in_base > 0.2:
            level = 'сабдомен'
        elif share_in_day > 0.2:
            level = 'база'
        elif uniq > 1:
            level = 'день'
        else:
            level = 'сеть (константа)'

        kind = ('непрерывное' if uniq > SKIP_VALUES else
                'булево' if uniq <= 2 else 'категория')
        out.append((k, 100.0 * filled / len(rows), uniq, level, kind))

    print(f"{'поле':<38}{'заполнено':>11}{'значений':>10}{'уровень':<20}{'тип'}")
    for level in ('сабдомен', 'база', 'день', 'сеть (константа)', 'пусто'):
        sel = [x for x in out if x[3] == level]
        if not sel:
            continue
        print(f'\n--- {level.upper()} ({len(sel)}) ' + '-' * (62 - len(level)))
        for k, fill, uniq, lvl, kind in sorted(sel, key=lambda x: -x[1]):
            print(f'{k:<38}{fill:>10.1f}%{uniq:>10}  {kind}')

    print(f'\nитого: ' + ', '.join(
        f'{lvl} {sum(1 for x in out if x[3] == lvl)}'
        for lvl in ('сабдомен', 'база', 'день', 'сеть (константа)', 'пусто')))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    lim = 120000
    if '--rows' in sys.argv:
        lim = int(sys.argv[sys.argv.index('--rows') + 1])
    if not args:
        raise SystemExit(__doc__)
    main(args, lim)
