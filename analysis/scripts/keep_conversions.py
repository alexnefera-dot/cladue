#!/usr/bin/env python3
"""Накопительный архив конверсий: единственный источник цели, который может пропасть.

Клики и сабдомены восстанавливаются из API в любой момент, а конверсии — нет:
их мало, они и есть исход, и если у трекера скользящее хранение, старые месяцы
однажды перестанут отдаваться. Поэтому каждая выгрузка вливается в
`analysis/export/tracker_conversions.jsonl`, который лежит в репозитории.

Дедупликация — по строке целиком: у одного `clickid` бывает и `reg`, и `fd`,
а иногда и два `reg` с разным временем, так что более узкий ключ склеил бы
разные события.

    python3 keep_conversions.py analysis/api/tracker_conversions_<from>_<to>.jsonl [ещё…]
"""
import os, sys, json

ARCHIVE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..', 'export', 'tracker_conversions.jsonl')


def load(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def key(r):
    return json.dumps(r, sort_keys=True, ensure_ascii=False)


def main(paths):
    have = load(ARCHIVE)
    seen = {key(r) for r in have}
    added = 0
    for p in paths:
        for r in load(p):
            k = key(r)
            if k not in seen:
                seen.add(k); have.append(r); added += 1
    have.sort(key=lambda r: (r.get('at') or '', r.get('clickid') or ''))
    os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
    with open(ARCHIVE, 'w', encoding='utf-8') as f:
        for r in have:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    span = (have[0]['at'][:10], have[-1]['at'][:10]) if have else ('—', '—')
    fd = sum(1 for r in have if r.get('event') == 'fd')
    print(f"архив: {len(have)} строк ({added} новых), {span[0]} … {span[1]}, ФД {fd}")
    print(f"-> {os.path.normpath(ARCHIVE)}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1:])
