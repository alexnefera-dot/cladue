#!/usr/bin/env python3
"""Подтипы сайтов выдачи: какие форматы проектов вообще встречаются.

Широкая таблица: сколько сайтов, сколько показов, сколько мест в топ-3,
сколько мест приходится на один сайт формата и сколько брендов он покрывает.
Колонка «топ-3 на сайт» и есть ответ на вопрос «что эффективнее доров».

    python3 -I scripts/serp_podtipy.py <csv> [json]
"""
import collections
import contextlib
import csv
import io
import json
import re
import sys

sys.path.insert(0, 'scripts')
with contextlib.redirect_stdout(io.StringIO()):     # serp_tipy печатает при импорте
    import serp_tipy as S

CSV = sys.argv[1]
JSON_OUT = sys.argv[2] if len(sys.argv) > 2 else None
rows = list(csv.DictReader(open(CSV, encoding='utf-8-sig'), delimiter=';'))

TELEGA = ('t.me', 'telegram.me', 'telegram.org', 'tgstat.ru', 'telegra.ph', 'teletype.in')
VIDEO = ('youtube.com', 'youtu.be', 'rutube.ru', 'tiktok.com', 'twitch.tv', 'likee.video')
SOCSET = ('vk.com', 'vk.ru', 'vk.link', 'vkvideo.ru', 'ok.ru', 'dzen.ru', 'x.com', 'twitter.com',
          'pinterest.com', 'pinterest.ru', 'viber.com', 'instagram.com', 'facebook.com', 'my.mail.ru')
PLATFORMY = ('vercel.app', 'github.io', 'notion.site', 'blogspot.com', 'wixsite.com', 'tilda.ws',
             'ucoz.ru', 'livejournal.com', 'medium.com', 'substack.com', 'netlify.app',
             'pages.dev', 'wordpress.com', 'sites.google.com', 'carrd.co', 'gitbook.io')
OTZYVY = ('otvet.mail.ru', 'otzovik.com', 'irecommend.ru', 'otzyvru.com', 'gipsyteam.ru',
          'pikabu.ru', 'reddit.com', 'quora.com', 'forum', 'otzyv')
VIKI = ('wikipedia.org', 'ruwiki.ru', 'wikimedia.org', 'wiki')
SMI = ('sports.ru', 'championat.com', 'vedomosti.ru', 'rbc.ru', 'ria.ru', 'tass.ru', 'lenta.ru',
       'kommersant.ru', 'gazeta.ru', 'iz.ru', 'kp.ru', 'mk.ru', 'vc.ru', 'dtf.ru', 'cbr.ru',
       'news.mail.ru', 'e1.ru', 'sovsport.ru', 'metaratings.ru', 'metaratings.by')
SERVISY = ('avito.ru', 'ozon.ru', 'wildberries.ru', '2gis.ru', 'hh.ru', 'kinopoisk.ru', 'okko.tv',
           'gosuslugi.ru', 'play.google.com', 'apps.apple.com', 'archive.org', 'github.com',
           'yandex.ru', 'ya.ru', 'rustore.ru', 'drom.ru', 'banki.ru', 'vbr.ru', 'list-org.com',
           'rutracker.org', 'afisha.yandex.ru', 'tr-page.yandex.ru', 'companies.rbc.ru',
           'apple.com', 'music.apple.com', 'itunes.apple.com')
PRILOZH = ('android', 'apk', 'softportal', 'trashbox', '4pda', 'droid', 'freesoft', 'skachat')
# «app» и «mobi» ловим отдельно: как приставку или через разделитель, иначе в формат
# попадают apple.com и sapphiretech.com — там «app» внутри чужого слова
PRILOZH_RE = __import__('re').compile(r'(app|^mobi|-mobi|mobile)')
# слова, внутри которых «app» ничего не значит
NE_APP = ('apple', 'sapphir', 'happy', 'apparel', 'append', 'support', 'appeal', 'apprais')
BONUS = ('bonus', 'promokod', 'promocode', 'bezdep', 'cashback', 'fribet', 'freebet', 'frispin',
         'freespin', 'podarok', 'akcii')
PROGNOZ = ('prognoz', 'stavk', 'bet-', 'betting', 'liveresult', 'legalbet', 'score', 'match',
           'sport', 'tipster')
ZERKALO = ('zerkalo', 'zercalo', 'mirror', 'vhod', 'vxod', 'login', 'oficialn', 'official')

GRUPPY = {
    'Телеграм': 'Платформы и UGC', 'Видеоплощадки': 'Платформы и UGC',
    'Соцсети': 'Платформы и UGC', 'Бесплатные платформы': 'Платформы и UGC',
    'Отзывы, вопросы, форумы': 'Платформы и UGC', 'Вики и справочники': 'Платформы и UGC',
    'СМИ и спортивные медиа': 'Платформы и UGC', 'Маркетплейсы и сервисы': 'Платформы и UGC',
    'Порталы и рейтинги казино': 'Тематические проекты',
    'Каталоги APK и приложений': 'Тематические проекты',
    'Бонусы и промокоды': 'Тематические проекты',
    'Прогнозы и ставки': 'Тематические проекты',
    'Тематические общие': 'Тематические проекты',
    'Зеркала и «вход»': 'Дорвейные форматы',
    'Доры (поддомены)': 'Дорвейные форматы',
    'Дорвейные голые домены': 'Дорвейные форматы',
    'Брендовые домены (зеркала и клоны)': 'Под имя бренда',
    'Нетематические домены': 'Чужая тематика',
    'Прочее': 'Чужая тематика',
}


def hvost(h, spisok):
    return any(h == s or h.endswith('.' + s) for s in spisok)


def podtip(r):
    h = r['Сайт'].lower()
    d = r['Домен'].lower()
    zona, imya, est_pod = S.razbor(h, d)
    chisto = re.sub(r'[^a-z]', '', imya)
    bazovyy = S.tip(r)

    if hvost(h, TELEGA):
        return 'Телеграм'
    if hvost(h, VIDEO):
        return 'Видеоплощадки'
    if hvost(h, SOCSET):
        return 'Соцсети'
    if hvost(h, PLATFORMY):
        return 'Бесплатные платформы'
    if hvost(h, VIKI) or 'wiki' in chisto:
        return 'Вики и справочники'
    if hvost(h, OTZYVY) or 'forum' in chisto or 'otzyv' in chisto:
        return 'Отзывы, вопросы, форумы'
    if hvost(h, SMI):
        return 'СМИ и спортивные медиа'
    if hvost(h, SERVISY):
        return 'Маркетплейсы и сервисы'
    if bazovyy == 'каталоги приложений и APK':
        return 'Каталоги APK и приложений'
    if bazovyy == 'порталы и рейтинги казино':
        return 'Порталы и рейтинги казино'
    if bazovyy == 'доры (поддомены)':
        return 'Доры (поддомены)'
    if bazovyy == 'брендовые домены (зеркала и клоны)':
        return 'Брендовые домены (зеркала и клоны)'

    polnoe = re.sub(r'[^a-z0-9]', '', imya)
    if any(k in polnoe for k in BONUS):
        return 'Бонусы и промокоды'
    if any(k in polnoe for k in ZERKALO):
        return 'Зеркала и «вход»'
    if any(k in polnoe for k in PRILOZH) or (PRILOZH_RE.search(imya)
                                             and not any(w in imya for w in NE_APP)):
        return 'Каталоги APK и приложений'
    if any(k in polnoe for k in PROGNOZ):
        return 'Прогнозы и ставки'
    if bazovyy == 'партнёрские и дорвейные домены':
        return 'Дорвейные голые домены'
    if bazovyy == 'тематические сайты':
        return 'Тематические общие'
    if bazovyy in ('прочие домены',):
        return 'Нетематические домены'
    return 'Прочее'


for r in rows:
    r['_pod'] = podtip(r)

VS = len(rows)
VSTR = sum(int(r['Строк выдачи'] or 0) for r in rows)
VT = sum(int(r['В топ-3'] or 0) for r in rows)

VSE_BRENDY = set()
for r in rows:
    for x in (r['Бренды'] or '').split(','):
        x = x.strip()
        if x and not x.startswith('…') and not x.startswith('ещё'):
            VSE_BRENDY.add(x)

svod = collections.defaultdict(lambda: dict(n=0, strok=0, top3=0, s_top3=0, brendov_sum=0,
                                            brendy=set(), luchshie=[]))
for r in rows:
    g = svod[r['_pod']]
    g['n'] += 1
    g['strok'] += int(r['Строк выдачи'] or 0)
    t3 = int(r['В топ-3'] or 0)
    g['top3'] += t3
    if t3:
        g['s_top3'] += 1
    g['brendov_sum'] += int(r['Брендов'] or 0)
    for x in (r['Бренды'] or '').split(','):
        x = x.strip()
        if x and not x.startswith('…') and not x.startswith('ещё'):
            g['brendy'].add(x)
    g['luchshie'].append((t3, int(r['Брендов'] or 0), r['Сайт']))

tabl = []
for p, g in svod.items():
    tabl.append({
        'imya': p, 'gruppa': GRUPPY.get(p, 'Чужая тематика'),
        'n': g['n'], 'dolya': round(100.0 * g['n'] / VS, 1),
        'strok': g['strok'], 'dolya_strok': round(100.0 * g['strok'] / VSTR, 1),
        'top3': g['top3'], 'dolya_top3': round(100.0 * g['top3'] / VT, 1),
        'top3_na_sajt': round(g['top3'] / g['n'], 2),
        'strok_na_sajt': round(g['strok'] / g['n'], 1),
        'brendov': len(g['brendy']),
        'ohvat': round(100.0 * len(g['brendy']) / len(VSE_BRENDY), 1),
        'brendov_na_sajt': round(g['brendov_sum'] / g['n'], 1),
        'top3_na_brend': round(g['top3'] / len(g['brendy']), 2) if g['brendy'] else 0,
        'dolya_s_top3': round(100.0 * g['s_top3'] / g['n'], 1),
        'primery': [x[2] for x in sorted(g['luchshie'], reverse=True)[:6]],
    })
tabl.sort(key=lambda x: -x['top3_na_sajt'])

print(f'Сайтов {VS}, строк {VSTR}, мест в топ-3 {VT}, брендов {len(VSE_BRENDY)}')
print()
print(f'{"подтип":<36} {"группа":<22} {"сайтов":>6} {"%":>5} {"строк":>6} {"%":>5} '
      f'{"топ-3":>6} {"%":>5} {"т3/сайт":>8} {"брендов":>8} {"охват":>6} {"бр/сайт":>8} '
      f'{"т3/бренд":>9} {"сайтов с т3":>12}')
for x in tabl:
    print(f'{x["imya"]:<36} {x["gruppa"]:<22} {x["n"]:>6} {x["dolya"]:>4}% {x["strok"]:>6} '
          f'{x["dolya_strok"]:>4}% {x["top3"]:>6} {x["dolya_top3"]:>4}% {x["top3_na_sajt"]:>8} '
          f'{x["brendov"]:>8} {x["ohvat"]:>5}% {x["brendov_na_sajt"]:>8} {x["top3_na_brend"]:>9} '
          f'{x["dolya_s_top3"]:>11}%')
print()
for x in tabl:
    print(f'  {x["imya"]:<36} {", ".join(x["primery"][:4])}')

if JSON_OUT:
    json.dump({'vsego_sajtov': VS, 'vsego_strok': VSTR, 'vsego_top3': VT,
               'vsego_brendov': len(VSE_BRENDY), 'podtipy': tabl},
              open(JSON_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n-> {JSON_OUT}')
