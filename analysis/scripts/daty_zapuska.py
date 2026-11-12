#!/usr/bin/env python3
"""Даты запуска доменов: создание контента, регистрация, конвейер, переобход.

Читает даты напрямую из выгрузок реестра (api/dorgen_subdomains_*.jsonl),
а не из kesh.tsv: кеш первый-побеждает и врёт на датах переобхода.
Конверсии цепляются к домену двумя путями: по заполненному subdomain
в самой конверсии и по clickid из выгрузок кликов.

Использование:
    python3 -I scripts/daty_zapuska.py 2280.team mazo.lol ...
"""
import collections
import glob
import json
import os
import sys

MET = {'dorgen_engine', 'dorgne_fenix'}   # метка сменилась 08.10, нужны обе


def baza(d):
    ch = (d or '').split('.')
    return '.'.join(ch[-2:]) if len(ch) >= 2 else (d or '')


def pole(ln, imya):
    """Значение строкового поля целиком: обрезать по ширине нельзя,
    имена контентов должны быть полными."""
    k = ln.find('"' + imya + '":')
    if k < 0:
        return ''
    j = k + len(imya) + 3
    while j < len(ln) and ln[j] == ' ':
        j += 1
    if ln[j:j + 1] == '"':
        return ln[j + 1:ln.find('"', j + 1)]
    return ln[j:min(x for x in (ln.find(',', j), ln.find('}', j), len(ln)) if x > 0)].strip()


def reestr(celi):
    dom = collections.defaultdict(lambda: dict(
        saitov=0, zap=0, sozdan=set(), cd=set(), rec=set(), pipe=set(),
        st=collections.Counter(), kont=collections.Counter(), zona=''))
    vid = set()
    for put in sorted(glob.glob('api/dorgen_subdomains_*.jsonl')):
        if not os.path.getsize(put):
            continue
        for ln in open(put):
            k = ln.find('"content_domain_url":')
            if k < 0:
                continue
            hv = ln[k + 21:k + 70]
            b = hv.split('"')[1] if '"' in hv else ''
            if b not in celi:
                continue
            i = ln.find('"', 13)
            s = ln[i + 1:ln.find('"', i + 1)]
            if s in vid:
                continue
            vid.add(s)
            g = dom[b]
            g['saitov'] += 1
            g['zona'] = b.rsplit('.', 1)[-1]
            for imya, klyuch in (('domain_created', 'sozdan'), ('cd_created', 'cd'),
                                 ('pipeline_started', 'pipe'), ('recrawl_sent_at', 'rec')):
                v = pole(ln, imya)[:10]
                if v[:1].isdigit():
                    g[klyuch].add(v)
                    if klyuch == 'rec':
                        g['zap'] += 1
            g['st'][pole(ln, 'yandex_pipeline_stage')] += 1
            kl = pole(ln, 'content_label')
            if kl and kl != 'null':
                g['kont'][kl] += 1
    return dom


def konversii(celi):
    pryamo = collections.defaultdict(set)
    for put in glob.glob('api/tracker_conversions_*.jsonl'):
        for ln in open(put):
            if '"subdomain": null' in ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            s = r.get('subdomain') or ''
            if baza(s) in celi:
                pryamo[baza(s)].add((str(r.get('at'))[:10], r.get('event'), s))

    ck = {}
    for put in glob.glob('api/tracker_clicks_*.jsonl'):
        for ln in open(put):
            if '"subdomain"' not in ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            s = r.get('subdomain') or ''
            if baza(s) in celi and (not r.get('campaign') or r['campaign'] in MET):
                ck[r.get('clickid')] = s
    for put in glob.glob('api/tracker_conversions_*.jsonl'):
        for ln in open(put):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            s = ck.get(r.get('clickid'))
            if s:
                pryamo[baza(s)].add((str(r.get('at'))[:10], r.get('event'), s))
    return pryamo, len(ck)


def main(argv):
    celi = set(argv)
    if not celi:
        print(__doc__)
        return 1
    dom = reestr(celi)
    konv, klikov = konversii(celi)

    def d(g, x):
        v = sorted(g[x])
        return (v[0] if len(v) == 1 else f'{v[0]}..{v[-1]}') if v else '—'

    poryadok = sorted(celi, key=lambda b: (sorted(dom[b]['rec'])[0] if dom.get(b) and dom[b]['rec'] else '9'))
    print(f'{"домен":<12} {"контент":<12} {"регистрация":<12} {"конвейер":<12} '
          f'{"переобход":<22} {"сайтов":>6} {"запущ":>6} {"конв":>5}')
    for b in poryadok:
        g = dom.get(b)
        if not g:
            print(f'{b:<12} нет в реестре (значит до 01.08.2026 — API раньше данных не отдаёт)')
            continue
        print(f'{b:<12} {d(g, "cd"):<12} {d(g, "sozdan"):<12} {d(g, "pipe"):<12} '
              f'{d(g, "rec"):<22} {g["saitov"]:>6} {g["zap"]:>6} {len(konv[b]):>5}')
    print()
    for b in poryadok:
        g = dom.get(b)
        if g and g['kont']:
            print(f'  {b:<12} контент: {", ".join(k for k, _ in g["kont"].most_common(3))}')
    print()
    print(f'  clickid-ов в выгрузках кликов по этим базам: {klikov}')
    for b in poryadok:
        for dt, ev, s in sorted(konv[b]):
            print(f'  конверсия: {dt}  {ev}  {s}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
