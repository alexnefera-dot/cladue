#!/usr/bin/env python3
"""Точные имена контента — с номером экземпляра, по одному на домен.

Имя экземпляра берётся из реестра запусков (поле content_label), где оно есть
целиком: `content-2026-09-17-7str-oform-2_42`. Для дней, где реестр его не
отдаёт, имя восстанавливается из журнала: заголовок секции даёт имя набора и
диапазон экземпляров, домены под ним идут по порядку. Там, где журнал сам
предупреждает о сбитой нумерации, экземпляр помечается как ненадёжный.

    python3 tochnye_kontenty.py <свод.csv> <out.csv> <out.txt>
"""
import sys, csv, re, json, glob, collections

svod_p, out_csv, out_txt = sys.argv[1:4]

# 1. реестр: точное имя экземпляра
REG = {}
for p in ('analysis/api/dorgen_subdomains_2026-08-25_2026-09-17.jsonl',
          'analysis/api/dorgen_subdomains_2026-09-18_2026-09-22.jsonl'):
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        s = (r.get('subdomain') or '').lower()
        c = r.get('content_label')
        if s and c:
            REG.setdefault(s.split('.', 1)[1], c)

# 2. журнал: имя набора + порядковый номер домена в секции
RANGE = re.compile(r'_\d+\s*(?:…|\.{2,3})\s*_?\d*(?:\s*,\s*_\d+\s*(?:…|\.{2,3})\s*_?\d*)*$')
JOURNAL, SHAKY = {}, set()
for p in sorted(glob.glob('analysis/launch_*.txt')):
    name = None; idx = 0; shaky = False
    for line in open(p, encoding='utf-8'):
        t = line.strip()
        if t.startswith('## '):
            head = t[3:].split(' — ')[0].split(' - ')[0].strip()
            base = RANGE.sub('', head).rstrip('_ ,')
            name = base if len(base) >= 4 and not re.match(r'^[А-ЯЁа-яё\s\d,.\-–—]+$', base) else None
            idx = 0; shaky = False
            continue
        if t.startswith('# ВНИМАНИЕ') and 'нумерация' in t:
            shaky = True
            continue
        if t.startswith('#') or not t or ' ' in t or '.' not in t:
            continue
        if name:
            idx += 1
            JOURNAL.setdefault(t.lower(), f'{name}_{idx}')
            if shaky:
                SHAKY.add(t.lower())

I = lambda r, k: int(r[k]) if r[k] not in ('', 'None') else 0
R = [r for r in csv.DictReader(open(svod_p, encoding='utf-8'))
     if r['день запуска'] >= '2026-09-01' and r['окно закрыто'] == 'да']

rows = []
for r in R:
    b = r['домен']
    exact = REG.get(b)
    src = 'реестр'
    if not exact:
        exact = JOURNAL.get(b)
        src = 'журнал (ненадёжный номер)' if b in SHAKY else 'журнал'
    s = I(r, 'сайтов в окне')
    rows.append({'точное имя контента': exact or 'имя не восстановлено',
                 'источник имени': src if exact else '—',
                 'домен': b, 'зона': r['зона'], 'день запуска': r['день запуска'],
                 'сайтов': s, 'вышли за 3 суток': I(r, 'вышли за 3 суток'),
                 'индекс %': round(100 * I(r, 'вышли за 3 суток') / s, 1) if s else '',
                 'кликов из поиска': I(r, 'кликов из поиска в окне'),
                 'регистраций': I(r, 'регистраций в окне 3 суток'), 'ФД': I(r, 'ФД в окне 3 суток'),
                 'набор (без номера)': re.sub(r'_\d+$', '', exact) if exact else ''})
rows.sort(key=lambda x: -(x['индекс %'] if x['индекс %'] != '' else -1))
with open(out_csv, 'w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

L = []; P = L.append
src = collections.Counter(x['источник имени'] for x in rows)
P(f'доменов сентября с закрытым окном: {len(rows)}')
P('откуда взято точное имя: ' + ', '.join(f'{k} — {v}' for k, v in src.most_common()))
P(f'уникальных точных имён: {len({x["точное имя контента"] for x in rows if x["точное имя контента"] != "имя не восстановлено"})}')
P(f'на одно имя приходится доменов: {len(rows) / max(len({x["точное имя контента"] for x in rows}), 1):.2f}')
P('')
P('ТОП-30 ТОЧНЫХ ИМЁН ПО ИНДЕКСУ (у каждого имени один домен, 150–206 сайтов)')
P(f'   {"точное имя контента":<46}{"домен":<18}{"зона":>7}{"день":>7}{"сайтов":>7}{"индекс":>8}{"клики":>8}{"рег":>5}{"ФД":>4}')
for x in rows[:30]:
    P(f'   {x["точное имя контента"][:45]:<46}{x["домен"][:17]:<18}{x["зона"]:>7}{x["день запуска"][5:]:>7}'
      f'{x["сайтов"]:>7}{x["индекс %"]:>7}%{x["кликов из поиска"]:>8}{x["регистраций"]:>5}{x["ФД"]:>4}')
P('')
P('ТОП-20 ТОЧНЫХ ИМЁН ПО РЕГИСТРАЦИЯМ (для сравнения — видно, что событий единицы)')
P(f'   {"точное имя контента":<46}{"домен":<18}{"сайтов":>7}{"индекс":>8}{"рег":>5}{"ФД":>4}')
for x in sorted(rows, key=lambda x: (-x['регистраций'], -x['ФД']))[:20]:
    P(f'   {x["точное имя контента"][:45]:<46}{x["домен"][:17]:<18}{x["сайтов"]:>7}{x["индекс %"]:>7}%{x["регистраций"]:>5}{x["ФД"]:>4}')
open(out_txt, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
