#!/usr/bin/env python3
"""Типы сайтов в выдаче и разбор доров.

На вход — выгрузка всех сайтов выдачи (CSV с ; и колонками
Сайт;Домен;Тип;Наш;Почему наш;Брендов;Бренды;Ключей;Строк выдачи;Лучшая позиция;
В топ-3;Лучшая доля в бренде %;Где эта доля;Лидер в брендах;Свежесть).

Колонка «Тип» в выгрузке считает дором любой поддомен — туда попадают
m.sports.ru, play.google.com и web.archive.org. Здесь тип считается заново,
правила по порядку, первое совпадение выигрывает.

Использование:
    python3 -I scripts/serp_tipy.py <csv> [--primery]
"""
import collections
import csv
import glob
import os
import re
import sys

CSV = sys.argv[1]
PRIMERY = '--primery' in sys.argv

SOCSETI = ('t.me', 'telegram.me', 'telegram.org', 'tgstat.ru', 'vk.com', 'vk.ru',
           'vkvideo.ru', 'ok.ru', 'youtube.com', 'youtu.be', 'dzen.ru', 'zen.yandex.ru',
           'tiktok.com', 'x.com', 'twitter.com', 'rutube.ru', 'pinterest.com',
           'pinterest.ru', 'instagram.com', 'facebook.com', 'twitch.tv', 'teletype.in',
           'likee.video', 'my.mail.ru', 'telegra.ph', 'viber.com', 'whatsapp.com',
           'vk.link', 'vkontakte.ru', 'ok.me', 'yappy.media')

PLOSHADKI = ('yandex.ru', 'yandex.com', 'ya.ru', 'wikipedia.org', 'ruwiki.ru',
             'wikimedia.org', 'rbc.ru', 'vedomosti.ru', 'cbr.ru', 'ria.ru', 'tass.ru',
             'kommersant.ru', 'lenta.ru', 'gazeta.ru', 'iz.ru', 'kp.ru', 'mk.ru',
             '2gis.ru', 'avito.ru', 'mail.ru', 'google.com', 'google.ru', 'apple.com',
             'archive.org', 'github.com', 'gitlab.com', 'sports.ru', 'championat.com',
             'otzovik.com', 'irecommend.ru', 'kinopoisk.ru', 'drom.ru', 'hh.ru',
             'gosuslugi.ru', 'livejournal.com', 'pikabu.ru', 'habr.com', 'dtf.ru',
             'vc.ru', 'ozon.ru', 'wildberries.ru', 'rutracker.org', 'sberbank.ru',
             'tinkoff.ru', 'banki.ru', 'vbr.ru', 'rambler.ru', 'list-org.com',
             'reddit.com', 'quora.com', 'medium.com', 'linkedin.com', 'soundcloud.com',
             'spotify.com', 'figma.com', 'notion.site', 'substack.com')

PRILOZHENIYA = ('android', 'apk', 'softportal', 'trashbox', '4pda', 'appstore',
                'app-store', 'mobile-app', 'sklad', 'softik', 'soft.', 'programmy', 'droid')

REYTINGI = ('top', 'topi', 'rating', 'rejting', 'reyting', 'reiting', 'best', 'luchshie',
            'obzor', 'review', 'otzyv', 'otziv', 'vybor', 'podborka', 'spisok', 'vse',
            'all', 'compare', 'sravn', 'guide', 'gid', 'expert', 'rank')

TEMATIKA = ('casino', 'kazino', 'casin', 'kazin', 'bet', 'slot', 'slots', 'igrov', 'igra',
            'gambl', 'azart', 'stavk', 'bookmaker', 'bukmeker', 'jackpot', 'dzhekpot',
            'bonus', 'promokod', 'promo', 'freespin', 'frispin', 'zerkalo', 'mirror',
            'play', 'win', 'luck', 'spin', 'vulkan', 'volcano', 'poker', 'ruletka',
            'roulette', 'bk', 'sport', 'bezdep', 'cashback', 'fribet', 'freebet',
            'cupis', 'prognoz', 'ludo', 'stake', 'fonbet')

DESHEVYE = {'buzz', 'top', 'team', 'lol', 'casino', 'fun', 'sbs', 'cfd', 'best', 'click',
            'site', 'xyz', 'monster', 'casa', 'cam', 'icu', 'store', 'shop', 'space',
            'live', 'bond', 'quest', 'autos', 'cyou', 'rest', 'lat', 'makeup', 'skin',
            'hair', 'mom', 'bar', 'uno', 'online', 'website', 'fyi', 'today', 'life',
            'world', 'digital', 'agency', 'cloud', 'link', 'bio', 'wiki', 'ink', 'run',
            'homes', 'boats', 'motorcycles', 'beauty', 'christmas', 'pics', 'sbs'}


SOSTAVNYE = ('co.com', 'com.ru', 'net.ru', 'org.ru', 'pp.ru', 'msk.ru', 'spb.ru',
             'co.uk', 'org.uk', 'com.ua', 'in.ua', 'kiev.ua', 'com.tr', 'co.il',
             'com.br', 'com.pl', 'com.de', 'co.in', 'com.kz', 'org.kz', 'com.cy')

OBYCHNYE = {'ru', 'com', 'net', 'org', 'by', 'kz', 'ua', 'info', 'biz', 'pro', 'me',
            'io', 'co', 'games', 'show', 'vip', 'tv', 'app', 'dev', 'su', 'рф', 'uz',
            'am', 'ge', 'md', 'kg', 'tj', 'az', 'de', 'pl', 'tr', 'il', 'br'}


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


def brendy_reestra():
    b = set()
    for put in sorted(glob.glob('api/dorgen_subdomains_*.jsonl'))[:2]:
        if not os.path.getsize(put):
            continue
        for ln in open(put):
            s = pole(ln, 'subdomain')
            if s:
                b.add(s.split('.')[0].lower())
    return b


rows = list(csv.DictReader(open(CSV, encoding='utf-8-sig'), delimiter=';'))
BR = brendy_reestra()
for r in rows:                                   # бренды выдачи тоже в словарь
    for x in (r['Бренды'] or '').split(','):
        x = re.sub(r'[^a-zа-я0-9]', '', x.strip().lower())
        if x and not x.startswith('ещё'):
            BR.add(x)
BR_DLINNYE = {b for b in BR if len(b) >= 4}

pod_bazy = collections.Counter(r['Домен'] for r in rows if r['Домен'] != r['Сайт'])


def brend_v(s):
    """Имя бренда в строке: точное совпадение, приставка (цифры спереди не мешают)
    или длинная подстрока. Подстрока короче 6 букв даёт ложные срабатывания."""
    if s in BR:
        return s
    bez = s.lstrip('0123456789')
    kand = [b for b in BR_DLINNYE if bez.startswith(b) or s.startswith(b)]
    if kand:
        return max(kand, key=len)
    kand = [b for b in BR_DLINNYE if len(b) >= 6 and b in s]
    return max(kand, key=len) if kand else ''


def razbor(h, d):
    """Хост -> (зона, имя базы, есть ли поддомен). Составная зона — не поддомен."""
    for suf in SOSTAVNYE:
        if d.endswith('.' + suf):
            return suf, d[:-(len(suf) + 1)].rsplit('.', 1)[-1], h != d
        if h.endswith('.' + suf) and d == suf:
            return suf, h[:-(len(suf) + 1)].rsplit('.', 1)[-1], h.count('.') > suf.count('.') + 1
    return d.rsplit('.', 1)[-1], d.rsplit('.', 1)[0], h != d


def tip(r):
    h = r['Сайт'].lower()
    d = r['Домен'].lower()
    zona, imya, est_pod = razbor(h, d)
    nbr = int(r['Брендов'] or 0)
    baza_polnaya = imya + '.' + zona
    pod_na_baze = pod_bazy[d] if est_pod else pod_bazy.get(baza_polnaya, 0)
    metka = h.split('.')[0] if est_pod else ''

    for s in SOCSETI:
        if h == s or h.endswith('.' + s):
            return 'соцсети и видео'
    for s in PLOSHADKI:
        if h == s or h.endswith('.' + s):
            return 'крупные площадки рунета'
    if any(k in h for k in PRILOZHENIYA) or imya in ('rustore', 'apkpure', 'apkshki'):
        return 'каталоги приложений и APK'

    chisto = re.sub(r'[^a-z]', '', imya)
    b = brend_v(re.sub(r'[^a-z0-9]', '', imya))

    # сайт самого бренда: имя базы построено на бренде, зона обычная,
    # поддоменов-доров на ней нет
    svoy_obychnaya = b and len(b) >= 4 and pod_na_baze < 6 and zona in OBYCHNYE
    svoy = b and len(b) >= 4 and nbr <= 3 and pod_na_baze < 2
    if svoy_obychnaya:
        return 'брендовые домены (зеркала и клоны)'

    # служебный поддомен обычного сайта (ru., m., blog., app.) — не дор
    SLUZHEBNYE = {'www', 'm', 'mobile', 'ru', 'en', 'kz', 'by', 'ua', 'blog', 'news',
                  'shop', 'app', 'apps', 'play', 'help', 'support', 'wiki', 'forum',
                  'web', 'lk', 'my', 'invite', 'static', 'cdn', 'api', 'account'}
    if est_pod and metka in SLUZHEBNYE and zona in OBYCHNYE and pod_na_baze < 6:
        if any(k in chisto for k in TEMATIKA):
            return 'тематические сайты'
        return 'прочие домены'
    if est_pod:
        return 'доры (поддомены)'

    # голый домен
    if svoy:
        return 'брендовые домены (зеркала и клоны)'
    if nbr >= 10:
        return 'порталы и рейтинги казино'
    if any(k in chisto for k in REYTINGI) and (any(k in chisto for k in TEMATIKA) or nbr >= 5):
        return 'порталы и рейтинги казино'
    if zona in DESHEVYE:
        return 'партнёрские и дорвейные домены'
    if any(k in chisto for k in TEMATIKA) or zona in ('casino', 'bet', 'poker'):
        return 'тематические сайты'
    return 'прочие домены'


for r in rows:
    r['_tip'] = tip(r)

itog = collections.Counter(r['_tip'] for r in rows)
strok = collections.Counter()
top3 = collections.Counter()
for r in rows:
    strok[r['_tip']] += int(r['Строк выдачи'] or 0)
    top3[r['_tip']] += int(r['В топ-3'] or 0)
VS, VSTR, VT = len(rows), sum(strok.values()), sum(top3.values())

print(f'Сайтов {VS}, строк выдачи {VSTR}, мест в топ-3 {VT}')
print()
print(f'{"тип":<28} {"сайтов":>7} {"%":>6} {"строк":>7} {"%":>6} {"топ-3":>6} {"%":>6}')
for t, n in itog.most_common():
    print(f'{t:<28} {n:>7} {100.0*n/VS:>5.1f}% {strok[t]:>7} {100.0*strok[t]/VSTR:>5.1f}% '
          f'{top3[t]:>6} {100.0*top3[t]/VT:>5.1f}%')
if '--json' in sys.argv:
    import json
    put = sys.argv[sys.argv.index('--json') + 1]
    prim = collections.defaultdict(list)
    for r in rows:
        if len(prim[r['_tip']]) < 6:
            prim[r['_tip']].append(r['Сайт'])
    json.dump({
        'vsego_sajtov': VS, 'vsego_strok': VSTR, 'vsego_top3': VT,
        'tipy': [{'imya': t, 'n': n, 'dolya': round(100.0 * n / VS, 1),
                  'strok': strok[t], 'dolya_strok': round(100.0 * strok[t] / VSTR, 1),
                  'top3': top3[t], 'dolya_top3': round(100.0 * top3[t] / VT, 1),
                  'primery': prim[t]} for t, n in itog.most_common()],
    }, open(put, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'-> {put}')

if PRIMERY:
    print()
    for t, _ in itog.most_common():
        pr = [r['Сайт'] for r in rows if r['_tip'] == t][:10]
        print(f'{t}:\n   {", ".join(pr)}')
