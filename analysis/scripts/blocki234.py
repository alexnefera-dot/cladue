#!/usr/bin/env python3
"""Блоки 2–4 на всех запусках, включая свежие, с поправкой на день.

Свежие не выбрасываются. Но и сравнивать их с дозревшими напрямую нельзя:
у свежего сайта было меньше времени на конверсию. Поэтому для каждой группы
считается **ожидаемое** число регистраций — сумма по её сайтам ставки того дня,
в который сайт ушёл на переобход. Свежий день даёт низкую ставку именно потому,
что он свежий, и поправка снимается сама собой.

Ставка пересчитывается на каждом прогоне: по мере дозревания чисел она растёт,
и вместе с ней ожидание. Числа поэтому слегка плавают от отчёта к отчёту — это
нормально и честнее фиксированной ставки.

    python3 blocki234.py <панель.jsonl> <subdomains.jsonl>[,…] <события.jsonl>
"""
import sys, json, collections, statistics


def h(t):
    print('\n' + '=' * 104)
    print(t)
    print('=' * 104)


def main(panel, subs_paths, events):
    reg = {}
    for p in subs_paths:
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            reg[r['subdomain'].lower()] = r

    rows = []
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('recrawl_sent_at') or '')[:10]
        if not d:
            continue                      # ещё не отправлен, считать нечего
        s = reg.get(r['subdomain'], {})
        rows.append({
            'brand': r.get('brand_label'), 'tld': r.get('tld'),
            'content': r.get('content'), 'base': r.get('content_domain_url'),
            'cd': r.get('content_domain_id'), 'day': d,
            'fresh': 0 if r.get('window_closed') else 1,
            'ya': 1 if r.get('ya_clicks') else 0, 'cl': r.get('ya_clicks') or 0,
            'reg': r.get('reg', 0), 'fd': r.get('fd', 0),
            'acc': s.get('ya_account_id'),
        })
    day = collections.defaultdict(lambda: [0, 0, 0])
    for r in rows:
        t = day[r['day']]
        t[0] += 1; t[1] += r['reg']; t[2] += r['fd']
    for r in rows:
        t = day[r['day']]
        r['exp'] = t[1] / t[0] if t[0] else 0
        r['expfd'] = t[2] / t[0] if t[0] else 0

    print(f'сайтов в расчёте {len(rows)}, свежих {sum(r["fresh"] for r in rows)} '
          f'({100.0*sum(r["fresh"] for r in rows)/len(rows):.0f}%)')
    print(f'регистраций {sum(r["reg"] for r in rows)}, ФД {sum(r["fd"] for r in rows)}')

    def agg(sel):
        n = len(sel)
        return {'n': n, 'fresh': sum(r['fresh'] for r in sel),
                'ya': sum(r['ya'] for r in sel), 'cl': sum(r['cl'] for r in sel),
                'reg': sum(r['reg'] for r in sel), 'fd': sum(r['fd'] for r in sel),
                'exp': sum(r['exp'] for r in sel), 'expfd': sum(r['expfd'] for r in sel)}

    h('БЛОК 2 · БРЕНДЫ, все запуски')
    byb = collections.defaultdict(list)
    for r in rows:
        if r['brand']:
            byb[r['brand']].append(r)
    res = [(b, agg(v)) for b, v in byb.items()]
    print(f"{'бренд':<20}{'сайтов':>8}{'свеж':>7}{'поиск':>7}{'кликов':>8}"
          f"{'рег':>5}{'ожид':>6}{'отнош':>7}{'ФД':>4}{'кл/рег':>8}")
    for b, t in sorted(res, key=lambda kv: -kv[1]['reg'])[:30]:
        k = t['reg'] / t['exp'] if t['exp'] else 0
        print(f'{b[:19]:<20}{t["n"]:>8}{t["fresh"]:>7}{t["ya"]:>7}{t["cl"]:>8}'
              f'{t["reg"]:>5}{t["exp"]:>6.1f}{k:>7.2f}{t["fd"]:>4}'
              f'{(str(round(t["cl"]/t["reg"])) if t["reg"] else "—"):>8}')
    zero = [(b, t) for b, t in res if t['reg'] == 0]
    print(f'\nбрендов без единой регистрации: {len(zero)} из {len(res)}')
    zz = sorted(zero, key=lambda kv: -kv[1]['exp'])[:10]
    print('  те из них, где регистраций ждали больше всего:')
    for b, t in zz:
        print(f'    {b[:24]:<26} сайтов {t["n"]:>6}, кликов {t["cl"]:>7}, '
              f'ожидалось {t["exp"]:.1f}')
    print(f'  всего на бесплодных брендах {sum(t["cl"] for _, t in zero)} поисковых кликов '
          f'и {sum(t["exp"] for _, t in zero):.0f} ожидавшихся регистраций')

    h('БЛОК 3 · АККАУНТЫ ВЕБМАСТЕРА, все запуски')
    purge = {}
    for line in open(events, encoding='utf-8'):
        e = json.loads(line)
        if e.get('event') != 'hosts_purge':
            continue
        purge.setdefault(e['content_domain_id'],
                         'уже использовался' if 'Удалено' in (e.get('detail') or '')
                         else 'первый раз')
    for r in rows:
        r['fresh_acc'] = purge.get(r['cd'])
    byd = collections.defaultdict(collections.Counter)
    for r in rows:
        if r['fresh_acc']:
            byd[r['day']][r['fresh_acc']] += 1
    both = {d for d, c in byd.items() if len(c) == 2 and min(c.values()) >= 200}
    print(f'дней, где ставились обе группы: {len(both)} из {len(byd)}')
    for scope, name in ((None, 'ВСЕ ДНИ'), (both, 'ТОЛЬКО ОБЩИЕ ДНИ')):
        sel = [r for r in rows if r['fresh_acc'] and (scope is None or r['day'] in scope)]
        print(f'\n{name}')
        print(f"{'аккаунт':<20}{'сайтов':>8}{'свеж':>7}{'поиск':>7}{'кликов':>9}"
              f"{'рег':>5}{'ожид':>6}{'отнош':>7}{'ФД':>4}")
        for k in ('первый раз', 'уже использовался'):
            s = [r for r in sel if r['fresh_acc'] == k]
            if not s:
                continue
            t = agg(s)
            kk = t['reg'] / t['exp'] if t['exp'] else 0
            print(f'{k:<20}{t["n"]:>8}{t["fresh"]:>7}{t["ya"]:>7}{t["cl"]:>9}'
                  f'{t["reg"]:>5}{t["exp"]:>6.1f}{kk:>7.2f}{t["fd"]:>4}')

    h('БЛОК 4 · КОНТЕНТ И ЗОНА ПОРОЗНЬ, все запуски')
    pz = collections.defaultdict(collections.Counter)
    for r in rows:
        if r['content'] and r['tld']:
            pz[r['content']][r['tld']] += 1
    multi = {c for c, z in pz.items() if sum(1 for v in z.values() if v >= 400) >= 2}
    sel = [r for r in rows if r['content'] in multi and pz[r['content']][r['tld']] >= 400]
    print(f'паков хотя бы на двух зонах: {len(multi)}; сайтов в сравнении {len(sel)}')
    print('внутри такого пака зона отделима от контента по построению\n')
    print(f"{'зона':<10}{'сайтов':>9}{'свеж':>7}{'поиск':>8}{'кликов':>9}"
          f"{'рег':>5}{'ожид':>6}{'отнош':>7}{'ФД':>4}")
    for z in ('team', 'lol', 'casino', 'buzz'):
        s = [r for r in sel if r['tld'] == z]
        if len(s) < 1000:
            continue
        t = agg(s)
        k = t['reg'] / t['exp'] if t['exp'] else 0
        print(f'{z:<10}{t["n"]:>9}{t["fresh"]:>7}{t["ya"]:>8}{t["cl"]:>9}'
              f'{t["reg"]:>5}{t["exp"]:>6.1f}{k:>7.2f}{t["fd"]:>4}')

    print('\nКОНТЕНТЫ ВНУТРИ ЗОНЫ .team — все с 1000+ сайтов')
    tm = [r for r in rows if r['tld'] == 'team' and r['content']]
    byc = collections.defaultdict(list)
    for r in tm:
        byc[r['content']].append(r)
    print(f"{'пак':<42}{'сайтов':>8}{'свеж':>7}{'поиск':>7}{'кликов':>9}"
          f"{'рег':>5}{'ожид':>6}{'отнош':>7}")
    for c, v in sorted(byc.items(), key=lambda kv: -len(kv[1])):
        if len(v) < 1000:
            continue
        t = agg(v)
        k = t['reg'] / t['exp'] if t['exp'] else 0
        print(f'{c[:41]:<42}{t["n"]:>8}{t["fresh"]:>7}{t["ya"]:>7}{t["cl"]:>9}'
              f'{t["reg"]:>5}{t["exp"]:>6.1f}{k:>7.2f}')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2].split(','), sys.argv[3])
