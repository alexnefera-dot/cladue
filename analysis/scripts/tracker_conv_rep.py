#!/usr/bin/env python3
"""Разбор конверсий трекера против выгрузки кликов.

Отвечает на то, чего не видно по одной странице аудита: доля чужих кампаний,
состоятельность ключа по реестру, и главное — находится ли клик конверсии
в выгрузке кликов по `clickid`. Без этого связка «клик → регистрация» не
считается, сколько бы ни было заполнено полей.

    python3 tracker_conv_rep.py <conversions.jsonl|json> <clicks.jsonl>
"""
import os, sys, json, collections
from urllib.parse import urlsplit

OURS = 'dorgen_engine'
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def rows(path):
    """JSONL выгрузки или сохранённый ответ API целиком — строка JSONL тоже
    начинается с '{', поэтому различаем разбором, а не первым символом."""
    text = open(path, encoding='utf-8').read()
    try:
        return json.loads(text).get('data', [])
    except json.JSONDecodeError:
        return [json.loads(l) for l in text.splitlines() if l.strip()]


def host(url):
    if not url:
        return None
    h = (urlsplit(url).hostname or '').lower()
    return h[4:] if h.startswith('www.') else h or None


def pct(a, b):
    return f"{100.0 * a / b:.2f}%" if b else "—"


def main(conv_path, clicks_path):
    doms = {l.strip().lower() for l in open(os.path.join(ROOT, 'domains_flat.txt'),
                                            encoding='utf-8') if l.strip()}
    conv = rows(conv_path)
    print(f"КОНВЕРСИЙ ВСЕГО: {len(conv)}")
    print("  кампании:", dict(collections.Counter(r.get('campaign') for r in conv).most_common()))

    ours = [r for r in conv if r.get('campaign') == OURS]
    n = len(ours)
    print(f"\n{OURS}: {n} конверсий")
    ev = collections.Counter(r.get('event') for r in ours)
    print("  события:", dict(ev))

    nosub = [r for r in ours if not r.get('subdomain')]
    inreg, outreg = [], []
    for r in ours:
        s = (r.get('subdomain') or '').lower()
        if not s:
            continue
        p = s.split('.')
        (inreg if any('.'.join(p[i:]) in doms for i in range(1, len(p) - 1)) else outreg).append(r)
    print(f"  без ключа       {len(nosub):>5}  {pct(len(nosub), n)}")
    print(f"  ключ в реестре  {len(inreg):>5}  {pct(len(inreg), n)}")
    print(f"  ключ вне реестра{len(outreg):>5}  {pct(len(outreg), n)}")
    for r in outreg:
        s = (r.get('subdomain') or '').lower()
        mark = 'ОТРАВЛЕН (= хост реферера)' if s == host(r.get('referer')) else 'не опознан'
        print(f"      {s:<34} {mark}  <- {(r.get('referer') or '')[:60]}")

    # главное: есть ли клик конверсии в выгрузке кликов
    ids = set()
    for line in open(clicks_path, encoding='utf-8'):
        c = json.loads(line)
        if c.get('campaign') == OURS:
            ids.add(c.get('clickid'))
    hit = [r for r in ours if r.get('clickid') in ids]
    print(f"\n  clickid найден среди кликов {OURS}: {len(hit)} из {n}  {pct(len(hit), n)}")
    miss = [r for r in ours if r.get('clickid') not in ids]
    if miss:
        print(f"  не найдено {len(miss)} — клик раньше окна выгрузки или отфильтрован:")
        for r in miss[:10]:
            print(f"      {r.get('at')}  {r.get('subdomain')}  {r.get('clickid')}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
