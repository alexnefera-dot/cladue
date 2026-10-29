#!/usr/bin/env python3
"""Сравнивает присланные сайты конкурентов между собой (без нашего генератора)."""
import re, os, itertools, collections

BASE = '/home/user/cladue/samples/konkurenty'
ПОРЯДОК = ['main', 'bonus', 'registracia', 'app', 'zerkalo', 'vhod', 'slots',
           'novosti', 'info', 'promo', 'obzor', 'partnery']
ТИП_А = ПОРЯДОК[:7]
ТИП_Б = ПОРЯДОК[7:]

def текст(html):
    t = re.sub(r'<[^>]*>', ' ', html)
    t = t.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')
    return re.sub(r'\s+', ' ', t).strip()

def слова(t):
    return re.findall(r'[0-9A-Za-zЀ-ӿ%‑-]+', t.lower())

def шинглы(t, n=6):
    w = слова(t)
    return {' '.join(w[i:i+n]) for i in range(max(0, len(w)-n+1))}

сайты = sorted(d for d in os.listdir(BASE) if d.startswith('sayt-'))
данные = {}
for с in сайты:
    данные[с] = {}
    for p in ПОРЯДОК:
        f = os.path.join(BASE, с, p + '.html')
        if os.path.isfile(f):
            h = open(f, encoding='utf-8').read()
            данные[с][p] = (h, текст(h))

print('=== объём и каркас по сайтам ===')
print(f"{'сайт':8} {'слов':>7} {'h2':>4} {'h3':>4} {'<p>':>5} {'табл':>5} {'ul':>4} {'ol':>4} {'li':>5} {'ссыл':>5} {'details':>8} {'цитат':>6} {'img':>4}")
for с in сайты:
    агг = collections.Counter()
    for h, t in данные[с].values():
        агг['слов'] += len(слова(t))
        for тег in ('h2', 'h3', 'p', 'table', 'ul', 'ol', 'li', 'a', 'details', 'blockquote', 'img'):
            агг[тег] += len(re.findall(r'<' + тег + r'\b', h, re.I))
    print(f"{с:8} {агг['слов']:7} {агг['h2']:4} {агг['h3']:4} {агг['p']:5} {агг['table']:5} "
          f"{агг['ul']:4} {агг['ol']:4} {агг['li']:5} {агг['a']:5} {агг['details']:8} "
          f"{агг['blockquote']:6} {агг['img']:4}")

print('\n=== объём по страницам (слов) ===')
print(f"{'стр':12} " + ' '.join(f'{с:>8}' for с in сайты))
for p in ПОРЯДОК:
    строка = f'{p:12} '
    for с in сайты:
        строка += f"{len(слова(данные[с][p][1])) if p in данные[с] else 0:>8} "
    print(строка)

print('\n=== совпадение текста между сайтами (6-словные шинглы, %) ===')
for p in ПОРЯДОК:
    пары = []
    for a, b in itertools.combinations(сайты, 2):
        if p in данные[a] and p in данные[b]:
            sa, sb = шинглы(данные[a][p][1]), шинглы(данные[b][p][1])
            if sa and sb:
                общ = len(sa & sb) / min(len(sa), len(sb)) * 100
                пары.append(f'{a[-1]}~{b[-1]}: {общ:5.1f}')
    print(f'{p:12} ' + '  '.join(пары))

print('\n=== внутренняя каннибализация (между страницами одного сайта, макс. пара) ===')
for с in сайты:
    худшие = []
    for a, b in itertools.combinations([p for p in ПОРЯДОК if p in данные[с]], 2):
        sa, sb = шинглы(данные[с][a][1]), шинглы(данные[с][b][1])
        if sa and sb:
            худшие.append((len(sa & sb) / min(len(sa), len(sb)) * 100, a, b))
    худшие.sort(reverse=True)
    print(f'{с}: ' + ', '.join(f'{a}~{b} {v:.1f}%' for v, a, b in худшие[:3]))

print('\n=== маркеры стиля ===')
маркеры = {
    'метафора «камень/каменолом»': r'камен|каменолом|кирка|гранит',
    'метафора «фарфор»': r'фарфор|сервиз|скол|чашк',
    'метафора «пинбол»': r'пинбол|pinball|флиппер',
    '«мы» (мы предлагаем/наш)': r'\bмы \w+|наш[аиеу]?\w*\b',
    '«вы/ваш»': r'\bвы\b|\bваш',
    'лицензии (MGA/UKGC/Curacao)': r'MGA|UKGC|Gambling Commission|Curacao|Кюрасао',
    'KYC/AML': r'KYC|AML',
    'CTA «НЕ ЗАХОДИ»': r'НЕ ЗАХОДИ',
    'незаменённые {плейсхолдеры}': r'\{(?:slots|vhod|info|news|promo)\}|CASINO_NAME',
    'эмодзи': r'[\U0001F300-\U0001FAFF☀-➿]',
    'суммы в ₽': r'₽',
    'суммы в €/$/£': r'[€$£]',
    'RTP': r'\bRTP\b',
}
print(f"{'маркер':32} " + ' '.join(f'{с:>8}' for с in сайты))
for имя, рег in маркеры.items():
    строка = f'{имя:32} '
    for с in сайты:
        n = sum(len(re.findall(рег, t, re.I)) for _, t in данные[с].values())
        строка += f'{n:>8} '
    print(строка)

print('\n=== числовая фактура (одни и те же показатели у разных сайтов) ===')
for шаблон, подпись in [
    (r'минимальн\w*[^.]{0,40}?(\d[\d  ]*)\s*₽', 'мин. вывод, ₽'),
    (r'(?:предел|предельн\w*)[^.]{0,60}?(\d[\d  ]*)\s*₽', 'лимит операции, ₽'),
    (r'(\d[\d  ]*)\s*(?:выпусков|слотов|игр)\b', 'размер каталога'),
    (r'(\d+)\s*студи', 'студий-поставщиков'),
    (r'(\d+)\s*турнир', 'турниров в месяц'),
    (r'(\d+)\s*%\s*на первый депозит', '% на первый депозит'),
]:
    print(f'\n{подпись}:')
    for с in сайты:
        найдено = []
        for p, (_, t) in данные[с].items():
            for m in re.findall(шаблон, t, re.I):
                найдено.append(f'{m.strip()} ({p})')
        print(f'  {с}: ' + (', '.join(dict.fromkeys(найдено)) or '—'))
