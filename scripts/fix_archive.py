#!/usr/bin/env python3
"""Правка типовых дефектов в распакованном архиве (файлы меняются на месте).

Использование:
    python3 scripts/fix_archive.py ПАПКА [--brand Motor --brand Daddy]

Что делает:
- {NAME} -> мужское русское имя: берётся из текста раздела (герой истории),
  иначе из списка; в брендовом контексте («казино {NAME}», «приложение {NAME}»,
  «В {NAME}») подставляется %brand_name_ru%.
- {AMOUNT} -> сумма в рублях из текста раздела, иначе типовая.
- {YYYYMMDD} -> %date%. Примерные адреса вида user@example.com -> user@%domain_name%.
  Два плейсхолдера бренда подряд схлопываются в один.
  Голый домен после собаки («whitelist для @yourcompany.com») — тоже.
- {PROTOCOL}, {SERVER}, {PORT}, {DOMAIN}, {HOST}, {URL}, {ID}, {NNN}, {IP},
  {MIN_WITHDRAWAL}, {UUID}, {DDMMYY} -> техническое значение.
- ru.html -> main.html, если main.html в наборе нет: главная скачана под языковой приставкой.
- Мусор после чистки: склейки <strongслово>, теги meter/font/center, битые <h2:, остатки [[ ]] и {a|b}.
- --auto-brand -> бренд каждого сайта определяется сам: самое частое латинское
  слово рядом с «казино/зеркало/приложение/бонус» не из белого списка, если оно
  есть минимум на двух страницах сайта. Найденные бренды печатаются.
- --brand X -> чужой бренд X заменяется на плейсхолдеры:
  «X Casino», «X App», промокоды вида XFREE -> %brand_name_en%;
  адреса @X.com и @X-casino.com -> @%domain_name%; сайт X.com -> %domain_name%;
  «(например, Xmirror.com)» убирается; телефон «+… X» -> «по номеру из личного
  кабинета»; остальные упоминания X -> %brand_name_ru%.
Печатает таблицу замен. Принимает только папку (распакованный архив).
"""
import argparse
import hashlib
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_archive import (ALLOWED_TAGS, CYR_WHITELIST, GENERIC_DOMAINS,  # noqa: E402
                           LATIN_WHITELIST, VOID_TAGS, brand_candidates,
                           вырезать_карточки)

NAMES = ("Олег Пётр Петр Дмитрий Марат Георгий Юрий Эдуард Евгений Роман Михаил Валерий Фёдор Федор Иван "
         "Андрей Сергей Алексей Николай Павел Максим Артём Артем Кирилл Виктор Илья Денис Антон Станислав "
         "Егор Тимур Руслан Константин Владислав Григорий Игорь Владимир Александр Василий Борис Аркадий "
         "Анатолий Леонид Семён Семен Степан Захар Матвей Никита Даниил Данил Ярослав Вадим Глеб Марк Тарас "
         "Богдан Всеволод Геннадий Герман Ефим Родион Савелий Тихон Филипп Ринат Рустам Артур Ильдар Дамир "
         "Азат Айрат Радик Ильяс").split()
NAME_RX = re.compile(r"\b(%s)(а|у|ом|е|ем|я|ю|ей)?\b" % "|".join(NAMES))
POOL = ["Андрей", "Сергей", "Алексей", "Николай", "Иван", "Павел", "Максим", "Кирилл", "Виктор", "Илья",
        "Денис", "Антон", "Егор", "Тимур", "Руслан", "Константин", "Владислав", "Григорий", "Игорь", "Никита"]
AMOUNT_RX = re.compile(r"(\d{1,3}(?:[  ]\d{3})+|\d{4,6})\s*(?:₽|руб)")
DEFAULT_AMOUNT = {"promo": "42 000 ₽", "partnery": "156 000 ₽"}
BRAND_CTX = re.compile(r"(казино|приложение|платформ\w*|сайт\w*|\bВ|\bв|\bна)\s*$")


def strip(s):
    return re.sub(r"<[^>]+>", " ", s)


def fill_vars(raw, page, seed):
    """Подставить {NAME} и {AMOUNT}; вернуть новый текст и список замен."""
    out, pos, rows = [], 0, []
    for m in re.finditer(r"\{(NAME|AMOUNT)\}", raw):
        out.append(raw[pos:m.start()])
        pos = m.end()
        before = strip(raw[max(0, m.start() - 40):m.start()])
        nxt = raw.find("<h2", m.end())
        section = strip(raw[m.end(): nxt if nxt > 0 else m.end() + 3000])
        if m.group(1) == "NAME":
            if BRAND_CTX.search(before):
                rep, how = "%brand_name_ru%", "бренд по контексту"
            else:
                found = NAME_RX.search(section)
                if found:
                    rep, how = found.group(1), "имя из раздела"
                else:
                    rep, how = POOL[seed % len(POOL)], "имя из списка"
                    seed //= 7
        else:
            # Берём из раздела только правдоподобную сумму выигрыша или заработка:
            # мелкие числа рядом обычно про депозит или ставку.
            rep = how = None
            for m2 in AMOUNT_RX.finditer(section):
                if int(re.sub(r"\D", "", m2.group(1))) >= 10000:
                    rep, how = m2.group(0).replace("руб", "₽"), "сумма из раздела"
                    break
            if rep is None:
                rep, how = DEFAULT_AMOUNT.get(page, "42 000 ₽"), "сумма по умолчанию"
        out.append(rep)
        rows.append(("{%s}" % m.group(1), rep, how))
    out.append(raw[pos:])
    return "".join(out), rows


ХВОСТ_БРЕНДА = re.compile(r'(%brand_name_(?:ru|en)%)\s+([A-Z][A-Za-z]{2,}|[А-ЯЁ][А-Яа-яЁё]{2,})\b')


def site_khvost(исходные):
    """Второе слово чужого бренда, оставшееся словом: «%brand_name_ru% Икс», «… Prestige».

    Генератор пишет первое слово названия плейсхолдером, второе оставляет как есть.
    Берём слово только тогда, когда в текстах сайта оно нигде не стоит само — тот же
    предохранитель, что у зачина. Иначе под нож идут обычные слова из фразы-двойника:
    «%brand_name_ru% Фактология Blitz Red» — здесь имя это «Blitz Red», а «Фактология»
    просто слово. Имена слотов не считаются: «Cats Royal» — слот, а не бренд.
    """
    текст = " ".join(исходные)
    хвосты = Counter(ХВОСТ_БРЕНДА.findall(текст))
    if not хвосты:
        return set()
    # имена слотов вычитаем целиком: карточка снимает заголовок «<h3>Royal Golden
    # Dragon</h3>», но строка «Играйте в Royal Golden Dragon от Swintt» остаётся,
    # и слово из имени слота проходило бы за самостоятельное
    без_карточек, имена = вырезать_карточки(текст)
    for имя in set(имена):
        без_карточек = без_карточек.replace(имя, " ")
    вышло = set()
    for (_, слово), n in хвосты.items():
        if n < 5:
            continue
        свой = LATIN_WHITELIST if слово[0] < "А" else CYR_WHITELIST
        if слово.lower() in свой:
            continue
        один = r"(?<![\w%%])%s(?![\w])" % re.escape(слово)
        if len(re.findall(один, без_карточек)) == n:
            вышло.add(слово)
    return вышло


def fix_brand_tail(raw, хвосты):
    """Снять хвосты названия, отобранные по сайту в site_khvost."""
    счёт = [0]

    def снять(m):
        if m.group(2) not in хвосты:
            return m.group(0)
        счёт[0] += 1
        return m.group(1)

    raw = ХВОСТ_БРЕНДА.sub(снять, raw)
    return raw, ([("хвост бренда", "снят", "%d" % счёт[0])] if счёт[0] else [])


ДВА_ПЛЕЙСХОЛДЕРА = re.compile(r"(%brand_name_(?:ru|en)%)\s+%brand_name_(?:ru|en)%")


def fix_double_brand(raw):
    """Два плейсхолдера подряд — остаток от замены слова, стоявшего сразу за первым.

    «%brand_name_ru% Prestige» превращается в «%brand_name_ru% %brand_name_en%»:
    название целиком, а выглядит как сказанное дважды. Оставляем первый.
    """
    всего = 0
    while True:
        raw, n = ДВА_ПЛЕЙСХОЛДЕРА.subn(r"\1", raw)
        всего += n
        if not n:
            break
    return raw, ([("два плейсхолдера", "схлопнуты", "%d" % всего)] if всего else [])


def fix_brand(raw, brand):
    rows = []
    if " " in brand:   # двухсловный бренд: сначала целиком, потом каждое неслужебное слово отдельно
        raw, rows = fix_brand_one(raw, brand)
        for word in brand.split():
            if word.lower() not in LATIN_WHITELIST:
                raw, more = fix_brand_one(raw, word)
                rows += more
        return raw, rows
    return fix_brand_one(raw, brand)


def fix_brand_one(raw, brand):
    b = re.escape(brand)
    rules = [
        (r"([A-Za-z0-9._-]+)@%s(?:-casino)?\.com\b" % b, r"\1@%domain_name%", "адрес → @%domain_name%"),
        (r"\b%s(?:mirror|proxy|casino|mobile|bet|app|club)\d*\.(?:com|net|org|ru|io)\b" % b, "%domain_name%", "склейка-домен → %domain_name%"),
        (r"\b%s(?=(?:mirror|proxy|casino|mobile|bet|app|club|games?)\b)" % b, "%brand_name_en%", "склейка → %brand_name_en%"),
        (r"\s*\(например,\s*%s[a-z]*\.com\)" % b, "", "пример зеркала убран"),
        (r"\b%s[a-z]*\.com\b" % b, "%domain_name%", "сайт → %domain_name%"),
        (r"\+\d[\d\s]{3,}%s\b" % b, "по номеру из личного кабинета", "телефон с брендом"),
        (r"\b%s([A-Z]{3,})\b" % b, r"%brand_name_en%\1", "промокод → %brand_name_en%"),
        (r"\b%s\s+(Casino|App|Club|Bet|Play|Online)\b" % b, r"%brand_name_en% \1", "латинская связка → %brand_name_en%"),
        (r"\b%s\b" % b, "%brand_name_ru%", "бренд → %brand_name_ru%"),
    ]
    if brand[0] >= "А":   # русское название склоняется: «в Хайпе», «бонусы Хайпа»
        rules.insert(-1, (r"\b%s(?:а|е|у|ом|ы|ов|ам|ах|ами|ой|ою)\b" % b,
                          "%brand_name_ru%", "бренд со склонением → %brand_name_ru%"))
    rows = []
    for rx, rep, how in rules:
        raw, n = re.subn(rx, rep, raw)
        if n:
            rows.append((brand, how, n))
    return raw, rows


def strip_text(raw):
    return re.sub(r"<[^>]+>", " ", raw)


# Между зачином и названием бывает дефис: «Мани-Икс» — детектор берёт «Икс»,
# и перед плейсхолдером остаётся висеть «Мани-».
ЗАЧИН_БРЕНДА = re.compile(r"([A-Z][A-Za-z]{2,}|[А-ЯЁ][А-Яа-яЁё]{2,})(?:\s+|-)%brand_name_(?:ru|en)%")


def site_zachin(исходные, заменённые, бренды):
    """Первое слово двухсловного названия, если оно словарное: «Новое Ретро», «Casino Royale».

    Такое слово детектор пропускает (оно в словаре), и после замены второго
    остаётся висеть: «Новое %brand_name_ru%». Забираем его только тогда, когда
    название без него в текстах не встречается ни разу: «Казино Лекс» рядом с
    74 отдельными «Лекс» — обычное слово перед брендом, а не часть имени.
    """
    зачины = Counter(ЗАЧИН_БРЕНДА.findall(" ".join(заменённые)))
    if not зачины:
        return None
    слово, n = зачины.most_common(1)[0]
    if n < 5:
        return None
    исходный = " ".join(исходные)
    for бренд in бренды:
        имя = re.escape(бренд)
        всего = len(re.findall(r"\b%s\b" % имя, исходный))
        рядом = len(re.findall(r"%s(?:\s+|-)%s\b" % (re.escape(слово), имя), исходный))
        if всего == n and рядом == n:
            return слово
    return None


def site_hvost_posle(исходные, бренды):
    """Слово, которое всегда стоит сразу за названием: «Изи Кэш» — детектор взял «Изи».

    Зеркало site_zachin: там слово перед названием, здесь после. Такой хвост нельзя
    отобрать до детекции (site_khvost), потому что плейсхолдера на его месте ещё нет:
    он появляется только после замены самого названия. Берём слово лишь тогда, когда
    название одно, без слова за ним, не встречается ни разу — иначе это обычное слово
    из фразы. Редкий вариант («Изи Кэш» 162 раза и «Изи Кэшинг» один — искажённое
    генератором название) порога в 5 упоминаний не берёт и остаётся словом.
    """
    текст = " ".join(исходные)
    вышло = set()
    for бренд in бренды:
        имя = re.escape(бренд)
        всего = len(re.findall(r"\b%s\b" % имя, текст))
        if всего < 5:
            continue
        за = Counter(re.findall(
            r"\b%s\s+([A-Z][A-Za-z]{2,}|[А-ЯЁ][А-Яа-яЁё]{2,})\b" % имя, текст))
        if sum(за.values()) == всего:
            вышло |= {с for с, n in за.items() if n >= 5}
    return вышло


def fix_brand_head(raw, зачин):
    raw, n = re.subn(r"\b%s(?:\s+|-)(%%brand_name_(?:ru|en)%%)" % re.escape(зачин), r"\1", raw)
    return raw, ([("зачин бренда", "снят", "%d" % n)] if n else [])


def fix_glavnaya(dp, fn):
    """Главная, скачанная под языковой приставкой: «ru.html» вместо «main.html».

    Переименовываем только когда main.html в наборе нет. Если лежат оба, ru.html —
    побайтовая копия главной, и её ловит D1 как дубль файла. Без переименования набор
    считается неполным (A4) и сайт убирается из выдачи целиком.
    """
    if "ru.html" not in fn or "main.html" in fn:
        return fn
    os.rename(os.path.join(dp, "ru.html"), os.path.join(dp, "main.html"))
    print("%-45s %-9s -> %-16s %s" % (os.path.basename(dp), "ru.html", "main.html",
                                      "главная под приставкой"))
    return [f for f in fn if f != "ru.html"] + ["main.html"]


def site_brands(files):
    """Бренды сайта — те же кандидаты, что находит проверка (check_archive.brand_candidates).

    Ищем в два захода: второе написание названия видно только после того, как
    первое ушло в плейсхолдер. На сайте с «Лаки Бир» латинское «Lucky Bear»
    до замены не набирает порога, а после — набирает.

    Хвост названия снимается до детекции: генератор пишет «%brand_name_ru% Икс»,
    и само «Икс» стоит в брендовом контексте, поэтому проходит за отдельный бренд
    и на его месте встаёт второй плейсхолдер («%brand_name_ru% %brand_name_ru%»).
    """
    исходные = [open(p, encoding="utf-8").read() for p in files]
    хвосты = site_khvost(исходные)
    raws = [fix_brand_tail(raw, хвосты)[0] for raw in исходные]
    найдено = []
    for _ in range(2):
        новые = [name for name, c, pg in brand_candidates(raws) if name not in найдено][:2]
        if not новые:
            break
        найдено += новые
        for brand in новые:
            raws = [fix_brand(raw, brand)[0] for raw in raws]
    if найдено:
        хвосты |= site_hvost_posle(исходные, найдено)
    return найдено, (site_zachin(исходные, raws, найдено) if найдено else None), хвосты


# Имена, которые вообще бывают в HTML. Всё остальное в угловых скобках — не тег, а текст
# выкачки («<http>», «<country_code>», «<d.morikova>»): скобки снимаем, текст оставляем.
ИЗВЕСТНЫЕ_ТЕГИ = ALLOWED_TAGS | VOID_TAGS | {
    "div", "span", "html", "head", "body", "script", "style", "iframe", "caption", "colgroup",
    "col", "tfoot", "noscript", "main", "header", "footer", "form", "input", "button", "label",
    "select", "option", "textarea", "picture", "source", "video", "audio", "svg", "path", "canvas",
    "template", "slot", "object", "embed", "map", "area", "output", "progress", "meter", "ins", "del"}
ЧУЖОЙ_ТЕГ = re.compile(r"</?([A-Za-z][\w.:-]*)\b[^>]*>")


def fix_markup(raw):
    """Мусор после чистки: склейки <strongслово>, теги вне списка, остатки [[ ]] и {a|b}."""
    rows = []
    известные = {"a", "abbr", "article", "aside", "b", "blockquote", "body", "br", "button", "canvas",
                 "caption", "cite", "code", "col", "colgroup", "data", "dd", "del", "details", "dfn",
                 "div", "dl", "dt", "em", "embed", "fieldset", "figcaption", "figure", "footer", "form",
                 "h1", "h2", "h3", "h4", "h5", "h6", "head", "header", "hgroup", "hr", "html", "i",
                 "iframe", "img", "input", "ins", "kbd", "label", "legend", "li", "link", "main", "map",
                 "mark", "menu", "meta", "meter", "nav", "noscript", "object", "ol", "optgroup", "option",
                 "output", "p", "param", "picture", "pre", "progress", "q", "rp", "rt", "ruby", "s",
                 "samp", "script", "section", "select", "small", "source", "span", "strong", "style",
                 "sub", "summary", "sup", "table", "tbody", "td", "template", "textarea", "tfoot", "th",
                 "thead", "time", "title", "tr", "track", "u", "ul", "var", "video", "wbr"}

    def разделить(m):  # noqa: E306
        if (m.group(1) + m.group(2)).lower() in известные:
            return m.group(0)      # это обычный тег, не склейка
        return "<%s>%s" % (m.group(1), m.group(2))

    def разделить_закрывающий(m):
        if (m.group(1) + m.group(2)).lower() in известные:
            return m.group(0)
        return "</%s>%s" % (m.group(1), m.group(2))

    # Потерян открывающий <section>: фрагмент начинается сразу с текста, а в конце
    # остаётся лишний </section>. Возвращаем тег с классом соседних секций.
    if len(re.findall(r"(?i)</section>", raw)) == len(re.findall(r"(?i)<section\b", raw)) + 1:
        m = re.search(r'(?i)<section[^>]*class="([^"]+)"', raw)
        тег = '<section class="%s">' % m.group(1) if m else "<section>"
        raw = тег + "\n" + raw
        rows.append(("потерян <section>", тег, "восстановлен в начале"))
    raw, n = re.subn(r"<(strong|em|b|i)([A-Za-zА-Яа-яЁё][\w-]*)>", разделить, raw)
    raw, n2 = re.subn(r"</(strong|em|b|i)([A-Za-zА-Яа-яЁё][\w-]*)>", разделить_закрывающий, raw)
    if n + n2:
        rows.append(("склейка тега", "<strong>слово", "разделено (%d)" % (n + n2)))
    # Закрывающий тег, которому нечего закрывать (остаток вырезанного блока).
    for тег in ("ul", "ol", "li", "div", "table"):
        глуб, лишние = 0, []
        for m in re.finditer(r"(?i)<(/?)%s\b[^>]*>" % тег, raw):
            if m.group(1):
                глуб -= 1
                if глуб < 0:
                    лишние.append(m.span())
                    глуб = 0
            else:
                глуб += 1
        for a, b in reversed(лишние):
            raw = raw[:a] + raw[b:]
        if лишние:
            rows.append(("лишний </%s>" % тег, "снят", "%d" % len(лишние)))
    # Кнопка закрытия поп-апа из выкачки: «<button>×</button>» перед баннером.
    # Снимаем вместе с содержимым, иначе в тексте остаётся голый крестик. Кнопку
    # с настоящей подписью («Получить») так не трогаем — у неё содержимое словесное.
    raw, n = re.subn(r"<button\b[^>]*>[^\w<]{0,3}</button>", "", raw)
    if n:
        rows.append(("кнопка закрытия", "снята", "%d" % n))
    raw, n = re.subn(r"</?(?:meter|progress|output|option|font|center|marquee|blink|spoiler|title|felt)[^>]*>", "", raw)
    if n:
        rows.append(("лишний тег", "снят", "%d" % n))
    снято = [0]

    def _снять(m):
        if m.group(1).lower() in ИЗВЕСТНЫЕ_ТЕГИ:
            return m.group(0)
        снято[0] += 1
        return ""

    raw = ЧУЖОЙ_ТЕГ.sub(_снять, raw)
    if снято[0]:
        rows.append(("тег не из HTML", "снят", "%d" % снято[0]))
    raw, n = re.subn(r"<h([1-6]):\s*", r"<h\1>", raw)
    if n:
        rows.append(("битый h", "исправлен", "%d" % n))
    raw, n = re.subn(r"\[\[(.*?)\]\]", r"\1", raw)
    if n:
        rows.append(("[[ ]]", "снято", "%d" % n))
    raw, n = re.subn(r"\{([^{}|\n]{1,60})\|[^{}\n]{1,60}\}", r"\1", raw)
    if n:
        rows.append(("{a|b}", "первый вариант", "%d" % n))
    return raw, rows


# Технические переменные, которые встречаются в текстах про доступ и установку.
ТЕХ_ПЕРЕМЕННЫЕ = {"{PROTOCOL}": "HTTPS", "{SERVER}": "%domain_name%", "{PORT}": "443",
                  "{DOMAIN}": "%domain_name%", "{HOST}": "%domain_name%", "{URL}": "%domain_name%",
                  # номер обращения в поддержку: «#502-{ID}», «/ticket {ID} {Текст}»
                  "{ID}": "4187",
                  # хвост тикет-ида: «автоматический тикет-ид #WIN-%date%-{NNN}»
                  "{NNN}": "317",
                  # адрес зеркала в обход блокировки: «вставьте в браузер https://{IP}/{path}»
                  "{IP}": "%domain_name%",
                  # минимальная сумма вывода: «Минимальная сумма вывода составляет {MIN_WITHDRAWAL}»
                  "{MIN_WITHDRAWAL}": "1 000 ₽",
                  # id запроса в примере обращения к API: «X-Request-ID: {UUID}»
                  "{UUID}": "7c1f4ae0-9b2d-4e13-8a57-16f0c3d2b985",
                  # дата внутри номера обращения: «Reference ID: CB-{DDMMYY}-001». Не %date%:
                  # тот подставляется прописью («Обновление 2 октября»), а здесь нужны шесть цифр.
                  "{DDMMYY}": "021026"}


def fix_generic(raw):
    rows = []
    for var, знач in ТЕХ_ПЕРЕМЕННЫЕ.items():
        raw, n = re.subn(r"(?<![$\\])" + re.escape(var), знач, raw)
        if n:
            rows.append((var, знач, "техническая переменная (%d)" % n))
    raw, n = re.subn(r"\{YYYYMMDD\}", "%date%", raw)
    if n:
        rows.append(("{YYYYMMDD}", "%date%", "дата"))
    raw, n = re.subn(r"\{\{(.*?)\}\}", r"\1", raw)
    if n:
        rows.append(("{{ }}", "снято", "скобки шаблонизатора (%d)" % n))
    def email(m):
        return m.group(1) + "@%domain_name%"
    # локальная часть необязательна: бывает голое «whitelist для @yourcompany.com»,
    # а правило ниже про домен отсекает всё, перед чем стоит @
    raw, n = re.subn(r"(?<![\w@%])([\w.-]*)@(?!%domain_name%)[A-Za-z0-9.-]+\.[a-z]{2,}\b", email, raw)
    if n:
        rows.append(("email", "@%domain_name%", "адрес-пример (%d)" % n))
    def domain(m):
        return m.group(0) if GENERIC_DOMAINS.match(m.group(2)) else m.group(1) + "%domain_name%"
    raw, n = re.subn(r"(?<![\w@%.])((?:https?://)?(?:[a-z0-9-]+\.)*)([A-Za-z0-9-]+\.(?:com|net|org|ru|io))\b(?!\w)", domain, raw)
    if n:
        rows.append(("домен", "%domain_name%", "чужой домен (%d)" % n))
    return raw, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="распакованный архив")
    ap.add_argument("--brand", action="append", default=[], help="чужой бренд для замены (можно несколько раз)")
    ap.add_argument("--auto-brand", action="store_true", help="определять бренд каждого сайта автоматически")
    args = ap.parse_args()
    if not os.path.isdir(args.path):
        raise SystemExit("нужна папка с распакованным архивом")
    total = 0
    found = {}
    for dp, dn, fn in os.walk(args.path):
        dn[:] = [d for d in dn if d != "__MACOSX"]
        fn = fix_glavnaya(dp, fn)
        files = [os.path.join(dp, f) for f in sorted(fn) if f.endswith(".html")]
        if not files:
            continue
        brands = list(args.brand)
        зачин = None
        хвосты = set()
        if args.auto_brand:
            auto, зачин, хвосты = site_brands(files)
            if auto:
                found[os.path.relpath(dp, args.path)] = auto + ([зачин + " …"] if зачин else [])
            brands += auto
        for p in files:
            f = os.path.basename(p)
            raw = open(p, encoding="utf-8").read()
            orig = raw
            rel = os.path.relpath(p, args.path)
            seed = int(hashlib.md5(rel.encode()).hexdigest(), 16)
            raw, rows = fill_vars(raw, f[:-5], seed)
            for what, rep, how in rows:
                print("%-45s %-9s -> %-16s %s" % (rel, what, rep, how))
            raw, grows = fix_generic(raw)
            rows += grows
            raw, mrows = fix_markup(raw)
            rows += mrows
            for brand in brands:
                raw, brows = fix_brand(raw, brand)
                for bname, how, n in brows:
                    rows.append(how)
            raw, trows = fix_brand_tail(raw, хвосты)
            rows += trows
            if зачин:
                raw, hrows = fix_brand_head(raw, зачин)
                rows += hrows
            raw, drows = fix_double_brand(raw)
            rows += drows
            if raw != orig:
                open(p, "w", encoding="utf-8").write(raw)
                total += len(rows)
    if found:
        print("\nбренды по сайтам:")
        for site, b in sorted(found.items()):
            print("  %-40s %s" % (site, ", ".join(b)))
    print("\nвсего замен:", total)


if __name__ == "__main__":
    main()
