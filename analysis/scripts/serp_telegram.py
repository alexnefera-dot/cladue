#!/usr/bin/env python3
"""Телеграм в выдаче: охват брендов, лидерство, доля видимости.

Важное ограничение: посайтовая выгрузка сворачивает весь телеграм в хосты
t.me / telegram.me / tgstat.ru — имён каналов в ней нет, поэтому «сколько
забирает канал» посчитать нельзя. Считаем то, что данные позволяют:
охват брендов, лидерство в выдаче бренда и долю видимости соцсетей.

Список брендов у t.me в выгрузке обрезан, поэтому принадлежность бренда
к телеграму выводится так: бренд точно с телеграмом, если он виден в
необрезанном списке t.me/telegram.me/tgstat.ru; точно без телеграма,
если все его соцсайты опознаны и телеграма среди них нет.

    python3 -I scripts/serp_telegram.py <сайты.csv> <бренды.csv> [json]
"""
import collections
import contextlib
import csv
import importlib.util
import io
import json
import sys

SAJTY, BRENDY = sys.argv[1], sys.argv[2]
JSON_OUT = sys.argv[3] if len(sys.argv) > 3 else None

sys.path.insert(0, 'scripts')
sys.argv = ['serp_podtipy', SAJTY]
spec = importlib.util.spec_from_file_location('sp', 'scripts/serp_podtipy.py')
with contextlib.redirect_stdout(io.StringIO()):
    sp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sp)

TG = {'t.me', 'telegram.me', 'tgstat.ru'}
soc = [r for r in sp.rows if r['_pod'] in ('Телеграм', 'Соцсети', 'Видеоплощадки')]
tg = [r for r in soc if r['Сайт'] in TG]
br = list(csv.DictReader(open(BRENDY, encoding='utf-8-sig'), delimiter=';'))
VSEGO = len(br)


def chislo(x):
    return float((x or '0').replace(',', '.'))


def spisok(r):
    out, obrez = [], 0
    for x in (r['Бренды'] or '').split(','):
        x = x.strip()
        if not x:
            continue
        if x.startswith('…') or x.startswith('ещё'):
            obrez = int(''.join(c for c in x if c.isdigit()) or 0)
        else:
            out.append(x)
    return out, obrez


# что известно про каждый бренд из необрезанных списков
izvestno = collections.defaultdict(set)
sajty = []
for r in sorted(soc, key=lambda r: -int(r['В топ-3'] or 0)):
    bl, ob = spisok(r)
    for b in bl:
        izvestno[b].add(r['Сайт'])
    sajty.append({'imya': r['Сайт'], 'telegram': r['Сайт'] in TG,
                  'brendov': int(r['Брендов'] or 0), 'strok': int(r['Строк выдачи'] or 0),
                  'top3': int(r['В топ-3'] or 0), 'poziciya': int(r['Лучшая позиция'] or 0),
                  'obrezano': ob, 'vidno': bl})

brendy = []
tochno_s, tochno_bez, neyasno = [], [], []
for r in br:
    b = r['Бренд']
    n_soc = int(r['соцсети и видео'] or 0)
    izv = izvestno.get(b, set())
    if r['Лидер'] in TG:                      # лидер выдачи — прямое свидетельство
        izv = izv | {r['Лидер']}
    est_tg = bool(izv & TG)
    if est_tg:
        status = 'точно есть'
        tochno_s.append(b)
    elif len(izv) >= n_soc:
        status = 'точно нет'
        tochno_bez.append(b)
    else:
        status = 'не видно в выгрузке'
        neyasno.append(b)
    brendy.append({
        'imya': b, 'soc': n_soc, 'vsego_sajtov': int(r['Всего сайtov'] or 0) if 'Всего сайtov' in r
        else int(r['Всего сайтов'] or 0),
        'strok': int(r['Строк выдачи'] or 0),
        'dolya_soc': chislo(r['Доля видимости: соцсети и видео %']),
        'lider': r['Лидер'], 'lider_tg': r['Лидер'] in TG,
        'status_tg': status, 'izvestnye': sorted(izv),
    })
brendy.sort(key=lambda x: -x['dolya_soc'])

tg_strok = sum(x['strok'] for x in sajty if x['telegram'])
soc_strok = sum(x['strok'] for x in sajty)
tg_top3 = sum(x['top3'] for x in sajty if x['telegram'])
soc_top3 = sum(x['top3'] for x in sajty)
lidery = [x for x in brendy if x['lider_tg']]
vse_lidery = collections.Counter(r['Лидер'] for r in br)

otchet = {
    'hostov': len(tg), 'brendov_vsego': VSEGO,
    'tg_strok': tg_strok, 'tg_top3': tg_top3,
    'soc_strok': soc_strok, 'soc_top3': soc_top3,
    'dolya_tg_v_soc_strok': round(100.0 * tg_strok / soc_strok, 1),
    'dolya_tg_v_soc_top3': round(100.0 * tg_top3 / soc_top3, 1),
    'vsego_strok_vydachi': sp.VSTR, 'vsego_top3_vydachi': sp.VT, 'vsego_sajtov': sp.VS,
    'dolya_strok': round(100.0 * tg_strok / sp.VSTR, 1),
    'dolya_top3': round(100.0 * tg_top3 / sp.VT, 1),
    'sajty': sajty,
    'ohvat_tme': next(x['brendov'] for x in sajty if x['imya'] == 't.me'),
    'liderov': len(lidery), 'lidery': [x['imya'] for x in lidery],
    'liderstvo_ryad': [{'imya': k, 'n': v} for k, v in vse_lidery.most_common(8)],
    'tochno_s': len(tochno_s), 'tochno_bez': sorted(tochno_bez), 'neyasno': len(neyasno),
    'bez_soc': [x['imya'] for x in brendy if x['soc'] == 0],
    'brendy': brendy,
    'raspred_soc': [{'imya': f'{k} соцсайт' + ('' if k == 1 else 'а' if k < 5 else 'ов'), 'n': v,
                     'dolya': round(100.0 * v / VSEGO, 1)}
                    for k, v in sorted(collections.Counter(x['soc'] for x in brendy).items())],
}

print(f"Телеграм: {len(tg)} хоста, {tg_strok} строк ({otchet['dolya_strok']}% всей выдачи), "
      f"{tg_top3} мест в топ-3 ({otchet['dolya_top3']}%)")
print(f"Внутри соцсетей телеграм — {otchet['dolya_tg_v_soc_strok']}% строк и "
      f"{otchet['dolya_tg_v_soc_top3']}% мест в топ-3")
print(f"t.me встречается в выдаче {otchet['ohvat_tme']} брендов из {VSEGO} = "
      f"{round(100.0 * otchet['ohvat_tme'] / VSEGO, 1)}%")
print(f"t.me — лидер выдачи у {len(lidery)} брендов: {', '.join(otchet['lidery'])}")
print(f"Самые частые лидеры вообще: {otchet['liderstvo_ryad']}")
print(f"Брендов точно с телеграмом по необрезанным спискам: {len(tochno_s)}; "
      f"точно без: {len(tochno_bez)}; не видно: {neyasno and len(neyasno)}")
print(f"Брендов без соцсетей вовсе: {len(otchet['bez_soc'])} — {', '.join(otchet['bez_soc'])}")
print()
print(f'{"сайт":<20} {"брендов":>7} {"строк":>6} {"топ-3":>6} {"поз":>4}')
for x in sajty:
    print(f'{x["imya"]:<20} {x["brendov"]:>7} {x["strok"]:>6} {x["top3"]:>6} {x["poziciya"]:>4}')
print()
print(f'{"бренд":<20} {"соцсайтов":>10} {"доля соцсетей":>14} {"всего сайтов":>13} {"лидер":<26} {"телеграм"}')
for x in brendy[:40]:
    print(f'{x["imya"]:<20} {x["soc"]:>10} {x["dolya_soc"]:>13}% {x["vsego_sajtov"]:>13} '
          f'{x["lider"]:<26} {x["status_tg"]}')

if JSON_OUT:
    json.dump(otchet, open(JSON_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n-> {JSON_OUT}')
