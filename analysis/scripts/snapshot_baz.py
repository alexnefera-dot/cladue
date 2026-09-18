#!/usr/bin/env python3
"""Накопительный снимок баз — страховка от ротации реестра.

`/v1/subdomains` держит около пяти недель: запросы раньше 11.08 возвращают ноль
строк. При этом треть конверсий приходит с баз старше этой границы, и отбор идёт
строго по возрасту. Значит всё, что API однажды отдал, надо складывать у себя —
как уже делается с конверсиями (`keep_conversions.py`).

Снимок — строка на базу, а не на сабдомен: 1850 строк вместо 379 тысяч, меньше
мегабайта, и этого хватает для срока жизни, аккаунтов и суточных рядов. Новый
запуск сливается со старым: база, пропавшая из выдачи API, остаётся в файле,
суточные ряды дополняются.

    python3 snapshot_baz.py <снимок.jsonl> <карта.jsonl> <days.json>[,<days_old.json>]
                            [--acc <base_acc.json>] [--purge <events.jsonl>]
"""
import os, sys, json, collections

def load_prev(path):
    rows = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            r = json.loads(line)
            rows[r['base']] = r
    return rows


def main(argv):
    out_path, map_path = argv[0], argv[1]
    days_paths = argv[2].split(',')
    rest = argv[3:]
    acc_path = rest[rest.index('--acc') + 1] if '--acc' in rest else None
    purge_path = rest[rest.index('--purge') + 1] if '--purge' in rest else None

    rows = load_prev(out_path)
    print(f'в снимке было баз: {len(rows)}')

    reg = {}
    for line in open(map_path, encoding='utf-8'):
        sub, base, cd_id, brand, recrawl, started, pages, tld, stage = json.loads(line)
        if not base:
            continue
        a = reg.setdefault(base, {'subs': 0, 'recrawl': None, 'cd_id': cd_id,
                                  'tld': collections.Counter(), 'stage': collections.Counter()})
        a['subs'] += 1
        t = (recrawl or started or '')[:10]
        if t and (a['recrawl'] is None or t < a['recrawl']):
            a['recrawl'] = t
        if tld:
            a['tld'][tld] += 1
        if stage:
            a['stage'][stage] += 1

    acc = json.load(open(acc_path, encoding='utf-8')) if acc_path else {}

    purge = {}
    if purge_path:
        url = {v['cd_id']: b for b, v in reg.items() if v['cd_id'] is not None}
        for line in open(purge_path, encoding='utf-8'):
            r = json.loads(line)
            if r.get('event') != 'hosts_purge' or 'Удалено' not in (r.get('detail') or ''):
                continue
            b = url.get(r['content_domain_id'])
            if b and (b not in purge or r['at'][:10] < purge[b]):
                purge[b] = r['at'][:10]

    for base, a in reg.items():
        r = rows.setdefault(base, {'base': base, 'days': {}})
        r['in_registry'] = True
        r['subs'] = a['subs']
        r['recrawl'] = a['recrawl']
        r['cd_id'] = a['cd_id']
        r['tld'] = a['tld'].most_common(1)[0][0] if a['tld'] else None
        r['stage'] = a['stage'].most_common(1)[0][0] if a['stage'] else None
        if base in acc:
            r['ya_account'] = acc[base].get('ya')
            r['cf_account'] = acc[base].get('cf')
        if base in purge:
            r['hosts_purge'] = purge[base]

    added = 0
    for p in days_paths:
        for base, series in json.load(open(p, encoding='utf-8')).items():
            r = rows.get(base)
            if r is None:
                r = rows[base] = {'base': base, 'days': {}, 'in_registry': False}
                added += 1
            for day, v in series.items():
                r['days'][day] = v          # свежая выгрузка перекрывает старую

    with open(out_path, 'w', encoding='utf-8') as f:
        for base in sorted(rows):
            f.write(json.dumps(rows[base], ensure_ascii=False, sort_keys=True) + '\n')

    inreg = sum(1 for r in rows.values() if r.get('in_registry'))
    print(f'стало баз: {len(rows)} (в реестре {inreg}, вне реестра {len(rows)-inreg}; '
          f'новых вне реестра в этом проходе {added})')
    print(f'с зачисткой хостов: {sum(1 for r in rows.values() if r.get("hosts_purge"))}')
    print(f'-> {out_path}')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(sys.argv[1:])
