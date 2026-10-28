#!/usr/bin/env python3
"""Кто держит выдачу бренда и ротирует ли она — по построчным снимкам выдачи.

Нужен снимок со строками, а не сводка по брендам: `{"scrape": "<дата>",
"queries": {"<запрос>": [{"pos":1,"host":...,"base":...,"url":...}, ...]}}`.
Сводная выгрузка по брендам на этот вопрос не отвечает: в ней нет ни позиций,
ни того, какой именно хост стоит в топе по каждому ключу.

Держит выдачу = стоит в топ-3 не меньше чем по половине ключей бренда.
Ротация считается между соседними снимками: сколько держателей осталось теми
же и какая доля топ-3 обновилась.

    python3 serp_kto_derzhit.py снимок1.json снимок2.json ... [--kesh api/kesh.tsv]
        [--top 3] [--porog 0.5] [--out export/kto_derzhit.txt]
"""
import collections
import csv
import json
import statistics
import sys

SOCSETI = {'t.me', 'vk.com', 'vk.ru', 'youtube.com', 'm.youtube.com', 'ok.ru',
           'dzen.ru', 'rutube.ru', 'telegram.org', 'instagram.com', 'x.com', 'twitter.com'}
IZVESTNYE = {'yandex.ru', 'mail.ru', 'otvet.mail.ru', 'ru.wikipedia.org', 'wikipedia.org',
             'vc.ru', 'pikabu.ru', 'habr.com', 'avito.ru', 'ozon.ru', 'kinopoisk.ru',
             'rbc.ru', 'lenta.ru', 'championat.com', 'sports.ru', 'freesoft.ru'}

opt = collections.defaultdict(list)
klyuch = None
for a in sys.argv[1:]:
    if a.startswith('--'):
        klyuch = a[2:]
    else:
        opt[klyuch].append(a)

TOP = int((opt['top'] or [3])[0])
POROG = float((opt['porog'] or [0.5])[0])
snimki_p = opt[None]

stroki = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    stroki.append(s)


nashi_bazy = set()
if opt['kesh']:
    with open(opt['kesh'][0], encoding='utf-8') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            nashi_bazy.add(r['base'])


def tip(host, base):
    if base in nashi_bazy:
        return 'наш дор'
    if host in SOCSETI or base in SOCSETI:
        return 'соцсети и видео'
    if host in IZVESTNYE or base in IZVESTNYE:
        return 'известные рунета'
    # поддомен считаем дором: бренд.база.зона — хост длиннее базы на метку
    if host != base and host.endswith('.' + base):
        return 'чужой дор (поддомен)'
    return 'домен'


def brend_zaprosa(zapros, obrazcy):
    """Запрос -> бренд. Берём самый длинный образец, который в него входит."""
    z = ' ' + zapros.lower().replace('ё', 'е') + ' '
    nayden, dlina = None, 0
    for obr, imya in obrazcy:
        if obr in z and len(obr) > dlina:
            nayden, dlina = imya, len(obr)
    return nayden


def prochitat(put):
    d = json.load(open(put, encoding='utf-8'))
    q = d['queries']
    if isinstance(q, list):
        sgr = collections.defaultdict(list)
        for r in q:
            sgr[r['query']].append(r)
        q = sgr
    return d.get('scrape', put), q


# образцы имён брендов: из реестра и, если дана сводка, из её колонки Ключ
obrazcy = []
if opt['kesh']:
    with open(opt['kesh'][0], encoding='utf-8') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            imya = (r['brand'] or '').strip()
            if imya and len(imya) >= 3:
                obrazcy.append((imya.lower().replace('ё', 'е'), imya))
for put in opt['svodka']:
    with open(put, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f, delimiter=';'):
            imya = (r.get('Бренд') or '').strip()
            kl = (r.get('Ключ') or '').strip()
            if imya and len(imya) >= 3:
                obrazcy.append((imya.lower().replace('ё', 'е'), imya))
            if kl and len(kl) >= 4:
                obrazcy.append((kl.lower(), imya or kl))
obrazcy = sorted(set(obrazcy), key=lambda kv: -len(kv[0]))

snimki = [prochitat(p) for p in snimki_p]
P(f'снимков: {len(snimki)}')
for (dt, q), p in zip(snimki, snimki_p):
    P(f'  {dt}  запросов {len(q)}  строк {sum(len(v) for v in q.values())}  ({p.split("/")[-1]})')
P('')


def derzhateli(q):
    """запросы -> {хост: доля ключей, где он в топ-N}, и состав топ-N по ключам."""
    vsego = len(q)
    schet = collections.Counter()
    topy = {}
    for zapros, rows in q.items():
        v_tope = []
        for r in sorted(rows, key=lambda r: r.get('pos') or 99):
            if (r.get('pos') or 99) <= TOP:
                v_tope.append(r['host'])
        topy[zapros] = v_tope
        for h in set(v_tope):
            schet[h] += 1
    return {h: c / vsego for h, c in schet.items()}, topy, vsego


def po_brendam(q):
    g = collections.defaultdict(dict)
    bez = 0
    for z, rows in q.items():
        b = brend_zaprosa(z, obrazcy)
        if b is None:
            bez += 1
            continue
        g[b][z] = rows
    return g, bez


P(f'КТО ДЕРЖИТ ВЫДАЧУ БРЕНДА — хост в топ-{TOP} не меньше чем по {POROG:.0%} ключей ЭТОГО бренда')
brendy_snimkov = []
for (dt, q), p in zip(snimki, snimki_p):
    g, bez = po_brendam(q)
    brendy_snimkov.append(g)
    P(f'  {str(dt)[:19]}: брендов опознано {len(g)}, запросов без бренда {bez}')
P('')

poslednij = brendy_snimkov[-1]
P(f'  {"бренд":<18} {"ключей":>7} {"держателей":>11} {"кто держит":<54} {"чем занят топ-3"}')
for b in sorted(poslednij, key=lambda b: -len(poslednij[b]))[:40]:
    q = poslednij[b]
    doli, _, vsego = derzhateli(q)
    drzh = sorted(((h, d) for h, d in doli.items() if d >= POROG), key=lambda kv: -kv[1])
    c = collections.Counter()
    for rows in q.values():
        for r in rows:
            if (r.get('pos') or 99) <= TOP:
                c[tip(r['host'], r.get('base') or r['host'])] += 1
    n = sum(c.values()) or 1
    sostav = ', '.join(f'{t.split(" ")[0]} {c[t]/n:.0%}' for t, _ in c.most_common(3))
    kto = '; '.join(f'{h} ({d:.0%})' for h, d in drzh[:2]) or 'никто — выдача ротирует'
    P(f'  {b:<18} {vsego:>7} {len(drzh):>11} {kto:<54} {sostav}')
P('')

P(f'ЧЕМ ЗАНЯТ ТОП-{TOP} В ЦЕЛОМ (доля строк топа по типу хоста)')
P(f'  {"снимок":<22} ' + ' '.join(f'{t:>22}' for t in
                                  ('наш дор', 'чужой дор (поддомен)', 'домен', 'соцсети и видео', 'известные рунета')))
for dt, q in snimki:
    c = collections.Counter()
    for rows in q.values():
        for r in rows:
            if (r.get('pos') or 99) <= TOP:
                c[tip(r['host'], r.get('base') or r['host'])] += 1
    n = sum(c.values()) or 1
    P(f'  {str(dt)[:19]:<22} ' + ' '.join(f'{c[t]/n:>21.1%}' for t in
                                          ('наш дор', 'чужой дор (поддомен)', 'домен', 'соцсети и видео', 'известные рунета')))
P('')

if len(snimki) >= 2:
    P(f'РОТАЦИЯ ТОП-{TOP} МЕЖДУ СНИМКАМИ — по общим ключам')
    P(f'  {"пара снимков":<44} {"общих ключей":>13} {"топ не менялся":>15} '
      f'{"обновление состава":>19} {"первое место то же":>19}')
    for i in range(len(snimki) - 1):
        (d1, q1), (d2, q2) = snimki[i], snimki[i + 1]
        obshchie = set(q1) & set(q2)
        if not obshchie:
            continue
        bez_izmen = 0
        obnov = []
        pervoe = 0
        for z in obshchie:
            t1 = [r['host'] for r in sorted(q1[z], key=lambda r: r.get('pos') or 99) if (r.get('pos') or 99) <= TOP]
            t2 = [r['host'] for r in sorted(q2[z], key=lambda r: r.get('pos') or 99) if (r.get('pos') or 99) <= TOP]
            if t1 == t2:
                bez_izmen += 1
            s1, s2 = set(t1), set(t2)
            obnov.append(len(s2 - s1) / len(s2) if s2 else 0)
            if t1 and t2 and t1[0] == t2[0]:
                pervoe += 1
        P(f'  {str(d1)[:16]} -> {str(d2)[:16]:<24} {len(obshchie):>13} '
          f'{bez_izmen/len(obshchie):>14.0%} {statistics.mean(obnov):>18.0%} {pervoe/len(obshchie):>18.0%}')
    P('')

    P('УСТОЙЧИВОСТЬ ДЕРЖАТЕЛЕЙ')
    naborы = []
    for dt, q in snimki:
        doli, _, _ = derzhateli(q)
        naborы.append({h for h, d in doli.items() if d >= POROG})
    for i in range(len(snimki) - 1):
        a_, b_ = naborы[i], naborы[i + 1]
        if not (a_ or b_):
            continue
        ost = len(a_ & b_)
        P(f'  {str(snimki[i][0])[:16]} -> {str(snimki[i+1][0])[:16]}: '
          f'держателей было {len(a_)}, стало {len(b_)}, осталось тех же {ost}'
          + (f' ({ost/len(a_):.0%})' if a_ else ''))
    P('')

P(f'САМЫЕ ЧАСТЫЕ ХОСТЫ В ТОП-{TOP} ПО ВСЕМ СНИМКАМ')
vsegoc = collections.Counter()
vsego_strok = 0
for dt, q in snimki:
    for rows in q.values():
        for r in rows:
            if (r.get('pos') or 99) <= TOP:
                vsegoc[r['host']] += 1
                vsego_strok += 1
P(f'  {"хост":<40} {"строк топа":>11} {"доля":>7} {"тип":<22}')
for h, c in vsegoc.most_common(25):
    b = h.split('.', 1)[1] if h.count('.') >= 2 else h
    P(f'  {h:<40} {c:>11} {c/vsego_strok:>6.1%} {tip(h, b):<22}')

if opt['out']:
    with open(opt['out'][0], 'w', encoding='utf-8') as f:
        f.write('\n'.join(stroki) + '\n')
    print(f'\nзаписано: {opt["out"][0]}')
