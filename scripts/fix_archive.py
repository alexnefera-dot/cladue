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
from check_archive import GENERIC_DOMAINS, LATIN_WHITELIST, brand_candidates  # noqa: E402

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
    rows = []
    for rx, rep, how in rules:
        raw, n = re.subn(rx, rep, raw)
        if n:
            rows.append((brand, how, n))
    return raw, rows


def strip_text(raw):
    return re.sub(r"<[^>]+>", " ", raw)


def site_brands(files):
    """Бренды сайта — те же кандидаты, что находит проверка (check_archive.brand_candidates), не больше двух."""
    raws = [open(p, encoding="utf-8").read() for p in files]
    return [name for name, c, pg in brand_candidates(raws)][:2]


def fix_generic(raw):
    rows = []
    raw, n = re.subn(r"\{YYYYMMDD\}", "%date%", raw)
    if n:
        rows.append(("{YYYYMMDD}", "%date%", "дата"))
    raw, n = re.subn(r"\{\{(.*?)\}\}", r"\1", raw)
    if n:
        rows.append(("{{ }}", "снято", "скобки шаблонизатора (%d)" % n))
    def email(m):
        return m.group(1) + "@%domain_name%"
    raw, n = re.subn(r"(?<![\w@%])([\w.-]+)@(?!%domain_name%)[A-Za-z0-9.-]+\.[a-z]{2,}\b", email, raw)
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
        files = [os.path.join(dp, f) for f in sorted(fn) if f.endswith(".html")]
        if not files:
            continue
        brands = list(args.brand)
        if args.auto_brand:
            auto = site_brands(files)
            if auto:
                found[os.path.relpath(dp, args.path)] = auto
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
            for brand in brands:
                raw, brows = fix_brand(raw, brand)
                for bname, how, n in brows:
                    rows.append(how)
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
