#!/usr/bin/env python3
"""Определение бренда по поисковому запросу.

В снимках выдачи запрос приходит и латиницей (`kent casino`), и кириллицей
(`кент казино зеркало`), а в реестре бренд записан только латиницей. Прямое
сравнение теряет почти половину запросов, поэтому из запроса сначала убираются
слова намерения, остаток переводится в латиницу и сравнивается с именами
брендов по близости написания.
"""
import re
import unicodedata

NAMERENIE = {
    'казино', 'casino', 'официальный', 'официальное', 'официально', 'сайт', 'site',
    'зеркало', 'зеркала', 'вход', 'войти', 'регистрация', 'зарегистрироваться',
    'играть', 'игра', 'игры', 'промокод', 'промокоды', 'бонус', 'бонусы', 'онлайн',
    'online', 'скачать', 'приложение', 'апп', 'app', 'слоты', 'слот', 'клуб',
    'рабочее', 'рабочий', 'новое', 'новый', 'на', 'деньги', 'бк', 'ставки',
    'отзывы', 'бездепозитный', 'фриспины', 'мобильная', 'версия', 'личный',
    'кабинет', 'ru', 'рф', 'com', 'бет', 'bet', 'и', 'в', 'для', 'с',
}

KIR_LAT = [
    ('дж', 'j'),
    ('щ', 'sch'), ('ш', 'sh'), ('ч', 'ch'), ('ж', 'j'), ('ю', 'yu'), ('я', 'ya'),
    ('ц', 'ts'), ('х', 'h'), ('ё', 'e'), ('э', 'e'), ('ы', 'y'), ('й', 'y'),
    ('а', 'a'), ('б', 'b'), ('в', 'v'), ('г', 'g'), ('д', 'd'), ('е', 'e'),
    ('з', 'z'), ('и', 'i'), ('к', 'k'), ('л', 'l'), ('м', 'm'), ('н', 'n'),
    ('о', 'o'), ('п', 'p'), ('р', 'r'), ('с', 's'), ('т', 't'), ('у', 'u'),
    ('ф', 'f'), ('ь', ''), ('ъ', ''),
]


def v_latinicu(s):
    s = s.lower()
    for k, l in KIR_LAT:
        s = s.replace(k, l)
    return re.sub(r'[^a-z0-9]', '', s)


def svernut(s):
    """Написание, устойчивое к разнице транслитераций: vulkan/volcano, zooma/zuma."""
    s = v_latinicu(s)
    s = s.replace('ck', 'k').replace('ph', 'f').replace('qu', 'kv').replace('x', 'ks')
    s = s.replace('dzh', 'j').replace('zh', 'j').replace('kh', 'h')
    s = s.replace('w', 'v').replace('c', 'k')
    s = re.sub(r'(.)\1+', r'\1', s)          # двойные буквы: mellstroy -> melstroy
    s = re.sub(r'(?<=.)[aeiouy]$', '', s)    # хвостовая гласная: zooma -> zum
    return s


def skelet(s):
    """Согласный скелет: гласные выброшены, двойные схлопнуты.

    Транслитерации расходятся именно на гласных: zooma/зума, beef/биф,
    stake/стейк, daddy/дэдди. На согласных они совпадают.
    """
    s = svernut(s)
    s = re.sub(r'[aeiouy]', '', s)
    return re.sub(r'(.)\1+', r'\1', s)


def blizost(a, b):
    """Доля совпадения по Левенштейну, 0..1."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    pred = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        tek = [i]
        for j, cb in enumerate(b, 1):
            tek.append(min(pred[j] + 1, tek[j - 1] + 1, pred[j - 1] + (ca != cb)))
        pred = tek
    return 1 - pred[-1] / max(len(a), len(b))


# Остаток, который не берут ни близость, ни скелет: короткие имена и те, где
# русское написание расходится с латинским сильнее обычного.
RUCHNYE = {
    'дэдди': 'Daddy', 'нью ретро': 'New Retro', 'ретро нью': 'New Retro',
    'буй': 'Booi', 'марафон': 'Marathon', 'битц': 'Bitz', 'спейсвин': 'Spacewin',
    'джекпокер': 'Jackpoker', 'вай': 'Why', 'джет': 'Jet', 'мостбет': 'MostBet Bookmaker',
    'голдфишка': 'Goldfishka', 'покерок': 'Pokerok', 'иззи': 'Izzi', 'лаки берд': 'Lucky Bird',
}


class Opredelitel:
    """Строит индекс по именам брендов и отвечает, какой бренд в запросе."""

    def __init__(self, imena, porog=0.78):
        self.porog = porog
        self.imena = set(imena)
        self.tochno = {}
        self.svernutye = []
        self.skelety = {}
        for imya in imena:
            for v in (imya, imya.replace(' ', '')):
                self.tochno.setdefault(v_latinicu(v), imya)
            self.svernutye.append((svernut(imya), imya))
            sk = skelet(imya)
            if len(sk) >= 2:
                self.skelety.setdefault(sk, set()).add(imya)
        self.svernutye.sort(key=lambda kv: -len(kv[0]))

    def ostatok(self, zapros):
        slova = [w for w in re.split(r'[^0-9A-Za-zА-Яа-яЁё]+', zapros.lower()) if w]
        return [w for w in slova if w not in NAMERENIE and len(w) > 1]

    def __call__(self, zapros):
        # 1. имя бренда целиком внутри запроса — самое длинное совпадение
        z = ' ' + unicodedata.normalize('NFKC', zapros.lower()).replace('ё', 'е') + ' '
        nayden, dlina = None, 0
        for lat, imya in self.tochno.items():
            if len(lat) < 3:
                continue
            for kus in (lat,):
                if kus in v_latinicu(z) and len(kus) > dlina:
                    nayden, dlina = imya, len(kus)
        if nayden:
            return nayden
        # 2. остаток запроса после слов намерения, по близости написания
        slova = self.ostatok(zapros)
        if not slova:
            return None
        for kandidat in (' '.join(slova), *slova):
            if kandidat in RUCHNYE and RUCHNYE[kandidat] in self.imena:
                return RUCHNYE[kandidat]
        for kandidat in (''.join(slova), *slova):
            k = svernut(kandidat)
            if not k:
                continue
            luchshiy, ocenka = None, 0.0
            for sv, imya in self.svernutye:
                b = blizost(k, sv)
                if b > ocenka:
                    luchshiy, ocenka = imya, b
            if ocenka >= self.porog:
                return luchshiy
        # 3. согласный скелет — берём только когда он указывает на один бренд
        for kandidat in (''.join(slova), *slova):
            sk = skelet(kandidat)
            if len(sk) >= 2 and len(self.skelety.get(sk, ())) == 1:
                return next(iter(self.skelety[sk]))
        # 4. скелет запроса — начало ровно одного скелета бренда (адмирал -> admiralx)
        for kandidat in (''.join(slova), *slova):
            sk = skelet(kandidat)
            if len(sk) < 3:
                continue
            podhodyat = {imya for s2, imena2 in self.skelety.items() if s2.startswith(sk)
                         for imya in imena2}
            if len(podhodyat) == 1:
                return next(iter(podhodyat))
        return None
