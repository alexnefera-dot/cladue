#!/usr/bin/env python3
"""Клики по доменам, созданным в заданном окне: живые или боты.

Живой поисковый клик — не бот и в referer есть yandex. Всё остальное
разбираем по реферерам, меткам и странам, чтобы было видно, что это за трафик.

    python3 -I scripts/kliki_novyh.py <реестр.jsonl> <клики.jsonl> [ещё клики...]
"""
import collections
import json
import os
import sys


def pole(ln, imya):
    k = ln.find('"' + imya + '":')
    if k < 0:
        return ''
    j = k + len(imya) + 3
    while j < len(ln) and ln[j] == ' ':
        j += 1
    if ln[j:j + 1] == '"':
        return ln[j + 1:ln.find('"', j + 1)]
    return ln[j:min(x for x in (ln.find(',', j), ln.find('}', j), len(ln)) if x > 0)].strip()


REESTR, KLIKI = sys.argv[1], sys.argv[2:]
sait_baza, bazy = {}, collections.Counter()
for ln in open(REESTR):
    s = pole(ln, 'subdomain')
    if s and s not in sait_baza:
        sait_baza[s] = pole(ln, 'content_domain_url')
        bazy[sait_baza[s]] += 1
print(f'Домены: {len(bazy)}, сайтов {len(sait_baza)}')

vsego = collections.Counter()
po_baze = collections.defaultdict(collections.Counter)
ref = collections.Counter()
ref_zhivye = collections.Counter()
sobytie = collections.Counter()
strana = collections.Counter()
metka = collections.Counter()
chasy = collections.Counter()
sajty_s_klikom = set()
sajty_zhivye = set()
primery = []
for put in KLIKI:
    for ln in open(put):
        k = ln.find('"subdomain": "')
        if k < 0:
            continue
        s = ln[k + 14:ln.find('"', k + 14)]
        if s not in sait_baza:
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        b = sait_baza[s]
        vsego['kliki'] += 1
        sajty_s_klikom.add(s)
        po_baze[b]['kliki'] += 1
        bot = bool(r.get('is_bot'))
        rf = (r.get('referer') or '')
        hvost = rf.split('/')[2] if rf.startswith('http') and len(rf.split('/')) > 2 else (rf or 'пусто')
        ref[hvost] += 1
        sobytie[r.get('event')] += 1
        strana[r.get('country') or '—'] += 1
        metka[r.get('campaign') or '—'] += 1
        chasy[str(r.get('at'))[:13]] += 1
        if bot:
            vsego['bot'] += 1
            po_baze[b]['bot'] += 1
            continue
        if 'yandex.' in rf or 'ya.ru' in rf:
            vsego['zhivye'] += 1
            po_baze[b]['zhivye'] += 1
            sajty_zhivye.add(s)
            ref_zhivye[hvost] += 1
            if len(primery) < 10:
                primery.append({'at': r.get('at'), 'subdomain': s, 'referer': rf,
                                'country': r.get('country'), 'campaign': r.get('campaign'),
                                'event': r.get('event')})
        else:
            vsego['prochee'] += 1
            po_baze[b]['prochee'] += 1

print(f'Кликов всего: {vsego["kliki"]}')
print(f'  помечены ботами:        {vsego["bot"]}')
print(f'  живые поисковые:        {vsego["zhivye"]}')
print(f'  не бот и не из поиска:  {vsego["prochee"]}')
print(f'Сайтов с кликами: {len(sajty_s_klikom)} из {len(sait_baza)}; '
      f'с живым поисковым: {len(sajty_zhivye)}')
print()
print(f'{"домен":<12} {"кликов":>8} {"боты":>7} {"живые":>6} {"прочее":>8}')
for b, c in sorted(po_baze.items(), key=lambda x: -x[1]['kliki']):
    print(f'{b:<12} {c["kliki"]:>8} {c["bot"]:>7} {c["zhivye"]:>6} {c["prochee"]:>8}')
print()
print('Рефереры (топ-12):')
for k, v in ref.most_common(12):
    print(f'  {k:<40} {v:>8}  {100.0 * v / vsego["kliki"]:.1f}%')
print()
print('События:', dict(sobytie.most_common(6)))
print('Метки кампаний:', dict(metka.most_common(6)))
print('Страны (топ-8):', dict(strana.most_common(8)))
print('По часам (топ-10):', dict(chasy.most_common(10)))
if primery:
    print()
    print('Примеры живых поисковых кликов:')
    for p in primery:
        print(f'  {p["at"][:19]}  {p["subdomain"]:<30} ref {p["referer"][:40]}  '
              f'{p["country"]}  {p["campaign"]}  {p["event"]}')
