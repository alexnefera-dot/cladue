#!/usr/bin/env python3
"""Проверка архива с HTML-фрагментами сайтов по планам из checks/.

Использование:
    python3 scripts/check_archive.py <архив.zip | папка> [-o отчёт.md] [--sort ПАПКА]

Архив должен иметь структуру  <N>-стр/<домен>/<страница>.html .
Коды проверок (A*, B*, C*, D*) соответствуют checks/00-common.md.
--sort ПАПКА  раскладывает сайты по типам: ПАПКА/годные/<тип>/<домен>/ и
              ПАПКА/на-доработку/<тип>/<домен>/, плюс ПАПКА/сводка.md.
Код возврата: 1, если найдена хотя бы одна ошибка (ERROR), иначе 0.
"""
import argparse
import hashlib
import html
import itertools
import os
import re
import shutil
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from html.parser import HTMLParser

# ---------------------------------------------------------------- шаблоны ---
SET_7 = ["app", "bonus", "main", "registracia", "slots", "vhod", "zerkalo"]
SET_12 = SET_7 + ["info", "news", "obzor", "partnery", "promo"]

# pages: эталонный набор; min_words: минимум слов; min_h2: минимум <h2>.
TEMPLATES = {
    1:  {"pages": ["main"], "min_words": 300, "min_h2": 3},
    7:  {"pages": SET_7, "min_words": 150, "min_h2": 1},
    8:  {"pages": SET_7 + ["privacy"], "min_words": 150, "min_h2": 1},
    9:  {"pages": SET_7 + ["contacts", "privacy"], "min_words": 150, "min_h2": 1},
    10: {"pages": SET_7 + ["about", "contacts", "privacy"], "min_words": 150, "min_h2": 1},
    12: {"pages": SET_12, "min_words": 400, "min_h2": 2},
    # 13-я страница при выкачке отсутствует — шаблон без неё, те же 12 страниц.
    13: {"pages": SET_12, "min_words": 400, "min_h2": 2},
}
# Группа -> (тип, страницы, которые выбрасываются). Сайты 9-стр и 10-стр
# собираются в шаблон 7-стр без служебных страниц; ссылки на убранные
# страницы ловит C1.
СЛУЖЕБНЫЕ = ["privacy", "contacts", "about"]
CONVERT = {8: (7, СЛУЖЕБНЫЕ), 9: (7, СЛУЖЕБНЫЕ), 10: (7, СЛУЖЕБНЫЕ)}
# Сайт убирается из выдачи (а не отправляется на доработку), если в нём
# есть заглушки или дубли файлов, а для типов из DISCARD_INCOMPLETE — ещё
# и если не хватает страниц. Причина пишется в отчёт и сводку.
DISCARD_INCOMPLETE = {7}

ALLOWED_PLACEHOLDERS = {"%brand_name_ru%", "%brand_name_en%",
                        "%domain_name%", "%date%"}
ALLOWED_TAGS = {"p", "h2", "h3", "h4", "ul", "ol", "li", "strong", "em", "b", "i", "a",
                "table", "thead", "tbody", "tr", "th", "td", "details", "summary",
                "blockquote", "br", "hr", "pre", "code", "dl", "dt", "dd", "section",
                "aside", "nav", "time", "figure", "figcaption", "small", "sup", "sub", "mark"}
VOID_TAGS = {"br", "hr", "img", "meta", "link", "input"}
JUNK_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}

# Ключевые слова раздела: страница должна подтверждать свою тему.
TOPIC = {
    "main": r"официальн|казино",
    "vhod": r"вход|войти|авториз|логин|парол",
    "registracia": r"регистрац|зарегистр|аккаунт|анкет",
    "zerkalo": r"зеркал|блокировк",
    "bonus": r"бонус|вейджер|кэшбэк|фриспин",
    "slots": r"слот|автомат|провайдер|rtp|джекпот",
    "app": r"приложен|apk|android|ios|скача|мобильн",
    "promo": r"промокод|акци|промо|турнир",
    "partnery": r"партн[её]р|вебмастер|реферал|аффилиат|revshare|cpa",
    "obzor": r"обзор|отзыв|рейтинг|плюсы|минусы",
    "news": r"новост|обновлен|анонс",
    "info": r"информац|правил|услови|лиценз|верификац|платеж|faq|вопрос",
    "about": r"о нас|о компании|кто мы|команд|мисси",
    "contacts": r"контакт|поддержк|email|телефон|чат|связ",
    "privacy": r"конфиденциальн|персональн|cookie|политик",
}
# Слово в тексте ссылки -> страница, на которую она могла бы вести (C2, справочно).
ANCHOR_TARGET = [
    (r"промокод|промо|акци", "promo"), (r"обзор", "obzor"),
    (r"новост", "news"), (r"информац|справ|правил", "info"),
    (r"партн[её]р", "partnery"), (r"бонус", "bonus"),
    (r"приложен|скача", "app"), (r"зеркал", "zerkalo"),
    (r"регистр", "registracia"), (r"вход|войти|логин|кабинет", "vhod"),
    (r"слот|автомат|играть|демо", "slots"), (r"контакт|поддержк", "contacts"),
    (r"конфиденц", "privacy"), (r"о нас", "about"),
]
# Бренд ищем только в строгом контексте: «казино X», «X Casino», «зеркало X»,
# «сайт X», «вход в X», строка бренда «<p>X.</p>» в начале страницы. Слово,
# которое чаще стоит в контексте слота или провайдера («от X», «слот X»,
# «X — популярный слот»), брендом не считается.
BRAND_BEFORE = re.compile(
    r"(?:казино|casino|зеркал(?:о|а|у|е|ом)?|сайт(?:а|е|у|ом)?|официальн\w+\s+сайт\w*|бренд\w*|поддержк\w*|"
    r"приложени[еяю]|вход(?:а|е)?\s+в|регистраци[яию]\s+в|аккаунт(?:а|е)?\s+в|кабинет(?:а|е)?\s+в|войти\s+в|"
    r"зайти\s+в|доступ\s+к|платформ[аеу]|букмекер\w*)\s+[«\"']?$", re.I)
BRAND_AFTER = re.compile(r"^[»\"']?[\s-]*(?:казино|casino|club|bet|mirror|официальн)", re.I)
SLOT_BEFORE = re.compile(r"(?:\bот|слот(?:а|е|ы|ов)?|автомат\w*|провайдер\w*|играйте\s+в|играть\s+в|игр[аыеу]\s+в|разработчик\w*|студи[яи])\s+[«\"']?$", re.I)
SLOT_AFTER = re.compile(r"^[»\"']?\s*(?:[-—–]\s*популярн|\(RTP|\(\d{4}\)|от\s+[A-Z]|с\s+RTP|—\s*слот|-\s*слот)")
PROVIDER_AFTER = re.compile(r"^\s+(?:Gaming|Games|Studios?|Lab|Labs|Play|Soft|Interactive|Entertainment|Authenticator|Aurora|Cloud)\b")
BRAND_LINE = re.compile(r"^\s*<p>(?:Казино\s+|Casino\s+)?([A-Z][A-Za-z0-9]+(?:[ -](?!Casino\b|casino\b)[A-Z][A-Za-z0-9]+)?)(?:\s+(?:Casino|casino|казино|Казино))?\.\s*</p>")
LATIN_WHITELIST = {
    "rtp", "vpn", "ios", "android", "app", "store", "google", "play", "pwa",
    "ssl", "live", "faq", "usdt", "bitcoin", "btc", "eth", "visa",
    "mastercard", "mir", "skrill", "neteller", "trustly", "telegram",
    "messenger", "whatsapp", "email", "e-mail", "id", "ip", "url", "html",
    "apk", "wild", "fast", "expanding", "high", "medium", "low", "megaways",
    "jackpot", "ok", "top", "vip", "cpa", "revshare", "hybrid", "kyc", "aml",
    "curacao", "ukgc", "mga", "gmt", "chat", "sms", "push", "pin", "2fa",
    "casino", "name", "face", "touch", "apple", "samsung", "huawei", "xiaomi",
    "windows", "chrome", "safari", "firefox", "opera", "yandex", "mail",
    "gmail", "wifi", "mac", "pc", "tv", "qr", "gdpr", "cookies", "cookie",
    # провайдеры и игры — не бренды казино
    "netent", "novomatic", "playtech", "pragmatic", "microgaming", "evolution",
    "yggdrasil", "quickspin", "endorphina", "bgaming", "betsoft", "amatic",
    "igrosoft", "belatra", "spinomenal", "hacksaw", "relax", "nolimit",
    "thunderkick", "wazdan", "habanero", "booongo", "playson", "egt", "merkur",
    "blueprint", "kalamba", "gamzix", "evoplay", "spribe", "smartsoft",
    "platipus", "swintt", "amusnet", "gaming", "games", "studios", "play'n",
    "sweet", "bonanza", "gates", "olympus", "book", "dead", "big", "bass",
    "starburst", "sugar", "rush", "money", "train", "the", "dog", "house",
    "wanted", "starlight", "princess", "razor", "shark", "fruit", "party",
    "fire", "joker", "buffalo", "king", "reactoonz", "lucky", "blue",
    "christmas", "catch", "asalto", "al", "banco", "crazy", "time", "monopoly",
    "lightning", "roulette", "blackjack", "baccarat", "poker", "aviator",
    "plinko", "mines", "crash", "keno", "dragon", "tiger", "mega", "moolah",
    "gonzo", "quest", "alive", "wolf", "gold", "bonus", "buy", "free", "spins",
    "hold", "win", "cash", "coin", "volcano", "cocktail", "monkey", "resident",
    "garage", "keks", "island", "pirate", "rock", "climber", "lady", "charm",
    "sizzling", "hot", "deluxe", "dolphin", "pearl", "beetle", "mania",
    "columbus", "lord", "ocean", "ramses", "thunder", "bird", "pharaoh",
    "cleopatra", "zeus", "hercules", "thor", "viking", "valhalla", "odin",
    "ra", "of", "and", "or", "in", "on", "for", "with", "to", "new", "best",
    "welcome", "extra", "max", "min", "pro", "plus", "premium", "ultra",
    # валюты, протоколы, термины, слова из названий игр
    "usd", "rub", "eur", "uah", "kzt", "https", "http", "dns", "txid", "wagering",
    "mirror", "pay", "scatter", "spin", "spins", "how", "what", "double",
    "happy", "night", "city", "dice", "ok", "wi-fi", "cdn", "kraken", "binance",
    "coinbase", "crush", "mystic", "flame", "calavera", "werewolf", "monte",
    "carlo", "amusnet", "spadegaming", "rake", "red", "wolf", "book", "sweet",
    "ios", "tor", "sim", "esim", "kyc", "vip", "rtp", "id", "pin", "otp", "qr",
    # провайдеры, техника, английские слова из инструкций
    "true", "lab", "mancala", "aspect", "thunderspin", "stars", "burning",
    "aurora", "amazon", "ram", "redis", "docker", "linux", "cloudflare", "nginx",
    "diamonds", "sapphires", "rubies", "authenticator", "settings", "oauth",
    "workers", "testflight", "tls", "sha", "rng", "protect", "points", "norm",
    "normal", "math", "malta", "jaz", "install", "get", "turbo", "service",
    "xxx", "okhand", "gaming", "api", "sdk", "json", "waf", "ddos", "imei",
    "apps", "update", "account", "login", "password", "support", "help",
    "center", "team", "player", "players", "game", "slot", "slots", "bank",
    "card", "cards",
}


# ------------------------------------------------------------- утилиты ---
class TagChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.errors, self.tags = [], [], Counter()

    def handle_starttag(self, tag, attrs):
        self.tags[tag] += 1
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.errors.append("незакрытый <%s>" % self.stack.pop())
            self.stack.pop()
        else:
            self.errors.append("лишний </%s>" % tag)

    def finish(self):
        self.errors += ["незакрытый <%s>" % t for t in self.stack]
        return self.errors


def strip_tags(raw):
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def shingles(words, n=6):
    return {" ".join(words[i:i + n]) for i in range(max(0, len(words) - n + 1))}


class Findings:
    def __init__(self):
        self.items = defaultdict(list)   # ключ сайта -> [(уровень, код, текст)]

    def add(self, key, level, code, msg):
        self.items[key].append((level, code, msg))

    def count(self, key, level):
        return sum(1 for l, _, _ in self.items[key] if l == level)


# ---------------------------------------------------------------- разбор ---
def unpack(path):
    if os.path.isdir(path):
        return path
    tmp = tempfile.mkdtemp(prefix="check_archive_")
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            # Архивы с macOS/Windows без флага UTF-8: имена читаются как cp437.
            if not info.flag_bits & 0x800:
                try:
                    info.filename = info.filename.encode("cp437").decode("utf-8")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
            z.extract(info, tmp)
    return tmp


def find_groups(root):
    groups = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__MACOSX"]
        for d in dirnames:
            m = re.fullmatch(r"(\d+)-стр", d)
            if m:
                groups.append((int(m.group(1)), os.path.join(dirpath, d)))
    return sorted(groups)


def analyze_page(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    text = strip_tags(raw)
    words = re.findall(r"\w+", text)
    tc = TagChecker()
    tc.feed(raw)
    anchors = re.findall(r'<a\s[^>]*href="([^"]*)"[^>]*>(.*?)</a>', raw, re.S)
    h2 = [re.sub(r"<[^>]+>", "", h).strip()
          for h in re.findall(r"<h2[^>]*>(.*?)</h2>", raw, re.S)]
    return {
        "path": path, "raw": raw, "text": text, "words": words, "nwords": len(words),
        "tag_errors": tc.finish(), "tags": tc.tags,
        "anchors": anchors, "h2": h2,
        "placeholders": Counter(re.findall(r"%[A-Za-z_]+%", raw)),
        "md5": hashlib.md5(raw.encode("utf-8")).hexdigest(),
        "utf8_ok": _utf8_ok(path),
    }


def _utf8_ok(path):
    data = open(path, "rb").read()
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return "не UTF-8"
    if data.startswith(b"\xef\xbb\xbf"):
        return "BOM"
    if b"\r" in data:
        return "CRLF"
    return ""


GENERIC_DOMAINS = re.compile(r"^(?:[\w.-]+@)?(?:mirror\d*|proxy\d*|example|domain|site|casino|mail|test|"
                             r"google|gmail|yandex|mail|apple|speedtest|whatismyip|github|wikipedia|"
                             r"youtube|telegram|t|vk|ok|play|facebook|instagram|twitter|x|yahoo|yopmail|"
                             r"dnschecker|ssllabs|vpn|protonmail|outlook|hotmail|icloud|cloudflare|whatsapp|"
                             r"viber|skype|paypal|qiwi|webmoney|sber|tinkoff|uk|letsencrypt|apkmirror|apkpure|"
                             r"googleapis|ntp|pool\.ntp|time|w3|mozilla|chrome|android|microsoft|windows)"
                             r"\.(?:com|net|org|ru|io)$", re.I)


def brand_hits(text):
    """По тексту страницы: Counter брендовых контекстов, Counter пар (слово перед, токен), Counter слотовых контекстов."""
    hits, prev, slot = Counter(), Counter(), Counter()
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9]{2,})\b", text):
        tok = m.group(1)
        if tok.lower() in LATIN_WHITELIST or (tok.isupper() and len(tok) <= 4):
            continue
        before = text[max(0, m.start() - 30): m.start()]
        after = text[m.end(): m.end() + 24]
        if PROVIDER_AFTER.match(after) or SLOT_BEFORE.search(before) or SLOT_AFTER.match(after):
            slot[tok] += 1
            continue
        if BRAND_BEFORE.search(before) or BRAND_AFTER.match(after):
            hits[tok] += 1
            pm = re.search(r"([A-Z][A-Za-z0-9]{2,})\s+$", before)
            if pm and pm.group(1).lower() not in LATIN_WHITELIST:
                prev[(pm.group(1), tok)] += 1
    return hits, prev, slot


def brand_candidates(raws):
    """Бренды сайта по всем страницам: [(имя, упоминаний, страниц)], сильные первыми."""
    total, pages, prev, slot, line = Counter(), Counter(), Counter(), Counter(), Counter()
    for raw in raws:
        m = BRAND_LINE.match(raw)
        if m and m.group(1).split()[0].lower() not in LATIN_WHITELIST:
            line[m.group(1)] += 1
        hits, pr, sl = brand_hits(strip_tags(raw))
        for tok, c in hits.items():
            total[tok] += c
            pages[tok] += 1
        prev.update(pr)
        slot.update(sl)
    out = []
    for tok in set(total) | set(line):
        first = tok.split()[0]
        strong = line[tok] >= 2
        ok = (pages[first] >= 2 and total[first] >= 3) or total[first] >= 5
        if not (strong or ok):
            continue
        if not strong and slot[first] >= total[first]:
            continue
        name = tok
        if " " not in tok:
            pair = max(((w, n) for (w, t), n in prev.items() if t == tok), key=lambda x: x[1], default=None)
            if pair and pair[1] >= total[tok] * 0.5:
                name = pair[0] + " " + tok
        out.append((name, total[first] + line[tok], max(pages[first], line[tok]), strong))
    out.sort(key=lambda x: (-x[3], -x[1]))
    seen, res = set(), []
    for name, c, pg, strong in out:
        if name.split()[0] in seen:
            continue
        seen.add(name.split()[0])
        res.append((name, c, pg))
    return res


def brand_leaks(text):
    """Контакты и телефоны на странице (бренды считаются по сайту, см. check_site)."""
    hits = Counter()
    contacts = Counter()
    for tok in re.findall(r"[\w.-]+@[\w.-]+\.[a-z]{2,}|\b[A-Za-z0-9-]+\.(?:com|net|org|ru|io)\b", text):
        if not GENERIC_DOMAINS.match(tok):
            contacts[tok] += 1
    phones = Counter(re.findall(r"\+\d[\d ()-]{7,}\d", text))
    return hits, contacts, phones


# ------------------------------------------------------------- проверки ---
def check_site(n, tpl, key, pages, F):
    names = sorted(pages)
    exp = tpl["pages"]
    # A3 / A4: количество и набор страниц
    if len(names) != len(exp):
        F.add(key, "ERROR", "A3", "страниц %d, по шаблону %d-стр ожидается %d" % (len(names), n, len(exp)))
    missing = sorted(set(exp) - set(names))
    extra = sorted(set(names) - set(exp))
    if missing:
        F.add(key, "ERROR", "A4", "нет страниц: " + ", ".join(missing))
    if extra:
        F.add(key, "ERROR", "A4", "лишние страницы: " + ", ".join(extra))
    for p in names:
        if not re.fullmatch(r"[a-z0-9-]+", p):
            F.add(key, "WARN", "A5", "имя файла не в нижнем регистре латиницей: %s.html" % p)

    no_brand, misrouted_all, misrouted_pages = [], Counter(), 0
    for p in names:
        d = pages[p]
        loc = "%s.html" % p
        if d["utf8_ok"]:
            F.add(key, "ERROR", "A6", "%s: %s" % (loc, d["utf8_ok"]))
        # B1 объём
        if d["nwords"] < tpl["min_words"]:
            lvl = "ERROR" if d["nwords"] < 60 else "WARN"
            F.add(key, lvl, "B1", "%s: %d слов (минимум %d)%s" % (
                loc, d["nwords"], tpl["min_words"],
                " — заглушка" if d["nwords"] < 60 else ""))
        # B2 заголовки
        if len(d["h2"]) < tpl["min_h2"] and d["nwords"] >= 60:
            F.add(key, "WARN", "B2", "%s: заголовков h2 — %d (минимум %d)" % (
                loc, len(d["h2"]), tpl["min_h2"]))
        # B3 тема страницы
        low = d["text"].lower()
        hits = {sec: len(re.findall(rx, low)) for sec, rx in TOPIC.items()}
        own = hits.get(p, 0)
        if p in TOPIC and own < 2 and d["nwords"] >= 60:
            F.add(key, "WARN", "B3", "%s: тема раздела не подтверждается (%d совпадений); первый h2: «%s»" % (
                loc, own, (d["h2"][0][:60] if d["h2"] else "—")))
        for sec in ("privacy", "contacts", "about", "partnery", "news"):
            if sec != p and hits[sec] >= 8 and hits[sec] >= 2 * max(own, 1) and d["nwords"] >= 60:
                F.add(key, "WARN", "B3", "%s: содержимое похоже на раздел «%s» (%d совпадений против %d своих); первый h2: «%s»" % (
                    loc, sec, hits[sec], own, (d["h2"][0][:60] if d["h2"] else "—")))
        # B4 чужие бренды и контакты
        _, contacts, phones = brand_leaks(d["text"])
        for tok, c in contacts.items():
            if "%" in tok:
                continue
            F.add(key, "ERROR", "B4", "%s: контакт/домен в тексте: %s" % (loc, tok))
        for tok in phones:
            F.add(key, "WARN", "B4", "%s: телефон в тексте: %s" % (loc, tok))
        # B5 плейсхолдеры
        bad = [ph for ph in d["placeholders"] if ph not in ALLOWED_PLACEHOLDERS]
        if bad:
            F.add(key, "ERROR", "B5", "%s: неизвестные плейсхолдеры: %s" % (loc, ", ".join(bad)))
        if re.search(r"\{\{.*?\}\}|\[\[.*?\]\]|\{[^{}\n]*\|[^{}\n]*\}", d["raw"]):
            F.add(key, "ERROR", "B5", "%s: остатки шаблонизатора {{ }} / [[ ]] / {a|b}" % loc)
        unfilled = Counter(re.findall(r"\{[A-Z_]{2,}\}", d["raw"]))
        if unfilled:
            F.add(key, "ERROR", "B5", "%s: незаполненные переменные: %s" % (
                loc, ", ".join("%s (%d)" % kv for kv in unfilled.items())))
        if not any(ph.startswith("%brand_name") for ph in d["placeholders"]) and d["nwords"] >= 60:
            no_brand.append(p)
        # B6 разметка
        if d["tag_errors"]:
            F.add(key, "ERROR", "B6", "%s: %s" % (loc, "; ".join(d["tag_errors"][:3])))
        bad_tags = sorted(set(d["tags"]) - ALLOWED_TAGS)
        if bad_tags:
            F.add(key, "ERROR", "B6", "%s: недопустимые теги: %s" % (loc, ", ".join(bad_tags)))
        # B7 пустые элементы
        empties = 0
        for tag in ("h2", "h3", "p", "li"):
            for m in re.findall(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), d["raw"], re.S):
                if not re.sub(r"<[^>]+>|&nbsp;|\s", "", m):
                    empties += 1
        empties += sum(1 for _, t in d["anchors"] if not re.sub(r"<[^>]+>|\s", "", t))
        if empties:
            F.add(key, "WARN", "B7", "%s: пустых элементов — %d" % (loc, empties))
        # B8 повтор h2
        dup = [h for h, c in Counter(d["h2"]).items() if c > 1 and h]
        if dup:
            F.add(key, "WARN", "B8", "%s: повтор h2: «%s»" % (loc, dup[0][:60]))
        # B9 FAQ первым блоком
        if d["h2"] and d["h2"][0].startswith("❓"):
            F.add(key, "INFO", "B9", "%s: FAQ стоит первым блоком" % loc)
        # B10 склейка слов
        glue = re.findall(r"[а-яё][А-ЯЁ]|[а-яёА-ЯЁ]\d", d["text"])
        if len(glue) > 5:
            F.add(key, "INFO", "B10", "%s: склеек слов/чисел без пробела — %d" % (loc, len(glue)))
        # C1–C4 ссылки
        broken, misrouted, external = Counter(), Counter(), 0
        for href, txt in d["anchors"]:
            t = re.sub(r"<[^>]+>", "", txt).strip().lower()
            if re.match(r"(https?:|//|mailto:|tel:)", href):
                external += 1
                continue
            tgt = href.strip("/").split("/")[0].split("?")[0]
            if tgt and tgt not in pages:
                broken[href] += 1
                continue
            for rx, sec in ANCHOR_TARGET:
                if re.search(rx, t):
                    if sec in pages and tgt != sec:
                        misrouted[(t[:40], href)] += 1
                    break
        for href, c in broken.items():
            F.add(key, "ERROR", "C1", "%s: ссылка на отсутствующую страницу %s (%d)" % (loc, href, c))
        if misrouted:
            misrouted_pages += 1
            misrouted_all.update(misrouted)
        if external:
            F.add(key, "WARN", "C3", "%s: внешних ссылок — %d" % (loc, external))
        if not d["anchors"] and len(exp) > 1:
            F.add(key, "INFO", "C4", "%s: нет внутренних ссылок" % loc)
    for name, c, pg in brand_candidates([pages[p]["raw"] for p in names]):
        F.add(key, "ERROR", "B4", "возможный чужой бренд «%s»: %d упоминаний на %d страницах" % (name, c, pg))
    if no_brand:
        F.add(key, "INFO", "B5", "нет плейсхолдера бренда на страницах: " + ", ".join(no_brand))
    if misrouted_all:
        ex = "; ".join("«%s» → %s (%d)" % (t, h, c) for (t, h), c in misrouted_all.most_common(4))
        F.add(key, "INFO", "C2", "ссылок не на свой раздел — %d на %d страницах, чаще всего: %s" % (
            sum(misrouted_all.values()), misrouted_pages, ex))
    # D3 дубли внутри сайта
    sh = {p: shingles(pages[p]["words"]) for p in names}
    for a, b in itertools.combinations(names, 2):
        A, B = sh[a], sh[b]
        if len(A) < 30 or len(B) < 30:
            continue
        cont = len(A & B) / min(len(A), len(B))
        if cont >= 0.5:
            F.add(key, "WARN", "D3", "%s.html и %s.html: общий текст %d%% меньшей страницы" % (a, b, round(cont * 100)))
    # B11 разброс бонусных процентов
    pct = set()
    for p in names:
        for m in re.findall(r"(?:бонус|депозит)[^%<]{0,30}?(?<!\d)(?<!\d )(\d{2,3}) ?%", pages[p]["text"], re.I):
            pct.add(int(m))
    if len(pct) > 5:
        F.add(key, "INFO", "B11", "разных процентов бонуса по сайту — %d: %s" % (
            len(pct), ", ".join("%d%%" % v for v in sorted(pct))))


def check_cross(all_pages, F):
    """D1 точные дубли и D2 почти-дубли между сайтами."""
    by_md5 = defaultdict(list)
    for key, d in all_pages.items():
        by_md5[d["md5"]].append(key)
    for keys in by_md5.values():
        if len(keys) > 1:
            for k in keys:
                site = k.rsplit("/", 1)[0]
                F.add(site, "ERROR", "D1", "%s: файл байт в байт совпадает с %s" % (
                    k.rsplit("/", 1)[1], ", ".join(x for x in keys if x != k)))
    sh = {k: shingles(d["words"]) for k, d in all_pages.items() if d["nwords"] >= 60}
    # Кандидаты через обратный индекс: общие для многих сайтов цепочки (шаблонные
    # фразы) не считаются, пары с малым числом общих цепочек не сравниваются.
    index = defaultdict(list)
    for k, A in sh.items():
        for g in A:
            index[g].append(k)
    shared = Counter()
    for g, keys in index.items():
        if len(keys) > 50:
            continue
        for a, b in itertools.combinations(sorted(keys), 2):
            shared[(a, b)] += 1
    for (a, b), n in shared.items():
        if n < 20:
            continue
        sa, sb = a.rsplit("/", 1)[0], b.rsplit("/", 1)[0]
        if sa == sb:
            continue
        A, B = sh[a], sh[b]
        inter = len(A & B)
        j = inter / len(A | B)
        cont = inter / min(len(A), len(B))
        if j >= 0.3 or cont >= 0.5:
            msg = "%s ≈ %s (Жаккар %.2f, вложенность %.2f)" % (a, b, j, cont)
            F.add(sa, "WARN", "D2", msg)
            F.add(sb, "WARN", "D2", msg)


# ---------------------------------------------------------------- отчёт ---
LEVEL_ORDER = {"ERROR": 0, "WARN": 1, "INFO": 2}
REASON = {  # короткая причина брака для сводки, по коду ошибки
    "A3": "не то количество страниц", "A4": "не тот набор страниц",
    "A6": "кодировка", "B1": "заглушки", "B4": "чужой бренд или контакты",
    "B5": "незаполненные переменные", "B6": "разметка",
    "C1": "ссылки в никуда", "D1": "дубль файла",
}


def discard_reason(F, s):
    """Почему сайт убран из выдачи; None — не убран."""
    items = F.items[s["key"]]
    why = []
    if any(lvl == "ERROR" and code == "B1" and "заглушка" in msg for lvl, code, msg in items):
        why.append("контент из заглушек")
    if any(lvl == "ERROR" and code == "D1" for lvl, code, _ in items):
        why.append("контент дублированный")
    if s["n"] in DISCARD_INCOMPLETE and any(lvl == "ERROR" and code in ("A3", "A4") for lvl, code, _ in items):
        why.append("неполный набор")
    return " и ".join(why) if why else None


def discarded(F, s):
    return discard_reason(F, s) is not None


def verdict(F, s):
    if discarded(F, s):
        return "🗑 убран: " + discard_reason(F, s)
    e, w = F.count(s["key"], "ERROR"), F.count(s["key"], "WARN")
    return "❌ брак" if e else ("⚠️ проверить" if w else "✅ годен")


def reasons(F, key):
    codes = Counter(code for lvl, code, _ in F.items[key] if lvl == "ERROR")
    return "; ".join("%s (%d)" % (REASON.get(c, c), n) for c, n in sorted(codes.items()))


def render(F, sites, archive_name, junk, unknown_groups):
    out = ["# Отчёт проверки: %s" % archive_name, ""]
    tot = Counter()
    for s in sites:
        for lvl in ("ERROR", "WARN"):
            tot[lvl] += F.count(s["key"], lvl)
    good = sum(1 for s in sites if not F.count(s["key"], "ERROR"))
    gone = sum(1 for s in sites if discarded(F, s))
    out += ["**Сайтов:** %d, годных %d, убрано %d. **Ошибок:** %d. **Предупреждений:** %d." % (
        len(sites), good, gone, tot["ERROR"], tot["WARN"]), ""]
    if junk:
        out += ["- A1 WARN: мусорные файлы в архиве — %s" % ", ".join(
            "%s (%d)" % kv for kv in junk.items())]
    if unknown_groups:
        out += ["- A2 WARN: папки групп без шаблона: %s" % ", ".join(unknown_groups)]
    out += ["", "## Сводка", "", "| Тип | Сайт | Страниц | Ошибок | Предупр. | Итог |",
            "|---|---|---:|---:|---:|---|"]
    for s in sites:
        k = s["key"]
        out.append("| %s | %s | %d | %d | %d | %s |" % (
            s["type"], s["site"] + s["note"], s["npages"], F.count(k, "ERROR"), F.count(k, "WARN"), verdict(F, s)))
    out += ["", "## Подробно", ""]
    for s in sites:
        k = s["key"]
        out.append("### %s" % k)
        items = sorted(F.items[k], key=lambda x: (LEVEL_ORDER[x[0]], x[1]))
        if not items:
            out.append("- замечаний нет")
        for lvl, code, msg in items:
            out.append("- %s %s: %s" % (code, lvl, msg))
        out.append("")
    return "\n".join(out)


def sort_output(F, sites, out_dir, archive_name):
    """Разложить сайты: годные/<тип>/<домен>, на-доработку/<тип>/<домен>, сводка.md."""
    by_type = defaultdict(lambda: {"good": [], "bad": [], "gone": []})
    for s in sites:
        k = s["key"]
        if discarded(F, s):
            by_type[s["type"]]["gone"].append(s)
            continue
        bucket = "на-доработку" if F.count(k, "ERROR") else "годные"
        dst = os.path.join(out_dir, bucket, s["type"], s["site"])
        os.makedirs(dst, exist_ok=True)
        for p, d in s["pages"].items():
            shutil.copyfile(d["path"], os.path.join(dst, p + ".html"))
        by_type[s["type"]]["good" if bucket == "годные" else "bad"].append(s)
    lines = ["# Сводка по типам: %s" % archive_name, ""]
    for t in sorted(by_type, key=lambda x: int(x.split("-")[0])):
        g, b, x = by_type[t]["good"], by_type[t]["bad"], by_type[t]["gone"]
        lines += ["## %s — годных %d, на доработку %d, убрано %d" % (t, len(g), len(b), len(x)), ""]
        for s in g:
            lines.append("- ✅ %s%s" % (s["site"], s["note"]))
        for s in b:
            lines.append("- ❌ %s%s — %s" % (s["site"], s["note"], reasons(F, s["key"])))
        for s in x:
            lines.append("- 🗑 %s%s — убран: %s (%s)" % (s["site"], s["note"], discard_reason(F, s), reasons(F, s["key"])))
        lines.append("")
    open(os.path.join(out_dir, "сводка.md"), "w", encoding="utf-8").write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("-o", "--output", help="файл отчёта (Markdown)")
    ap.add_argument("--sort", metavar="ПАПКА", help="разложить сайты по типам в эту папку")
    args = ap.parse_args()
    root = unpack(args.path)
    F = Findings()
    junk = Counter()
    for dirpath, dirnames, filenames in os.walk(root):
        if "__MACOSX" in dirpath.split(os.sep):
            junk["__MACOSX"] += len(filenames)
            continue
        for fn in filenames:
            if fn in JUNK_NAMES or fn.startswith("._"):
                junk[fn] += 1
    all_pages, sites, unknown = {}, [], []
    for n, gdir in find_groups(root):
        gname = os.path.basename(gdir)
        if n not in TEMPLATES:
            unknown.append(gname)
            continue
        target, drop = CONVERT.get(n, (n, []))
        tpl = TEMPLATES[target]
        for site in sorted(os.listdir(gdir)):
            sdir = os.path.join(gdir, site)
            if not os.path.isdir(sdir):
                continue
            tname = "%d-стр" % target
            key = "%s/%s" % (tname, site)
            pages, dropped = {}, []
            for fn in sorted(os.listdir(sdir)):
                fp = os.path.join(sdir, fn)
                if fn.endswith(".html"):
                    if fn[:-5] in drop:
                        dropped.append(fn[:-5])
                    else:
                        pages[fn[:-5]] = analyze_page(fp)
                elif os.path.isfile(fp) and fn not in JUNK_NAMES and not fn.startswith("._"):
                    F.add(key, "WARN", "A5", "посторонний файл: %s" % fn)
                elif os.path.isdir(fp):
                    F.add(key, "WARN", "A5", "вложенная папка: %s" % fn)
            note = ""
            if target != n:
                note = " (из %s)" % gname
                F.add(key, "INFO", "A2", "собрано из %s: убраны %s" % (
                    gname, ", ".join(dropped) if dropped else "ничего"))
            sites.append({"key": key, "type": tname, "site": site, "note": note, "n": target,
                          "pages": pages, "npages": len(pages)})
            check_site(target, tpl, key, pages, F)
            for p, d in pages.items():
                all_pages["%s/%s.html" % (key, p)] = d
    check_cross(all_pages, F)
    name = os.path.basename(args.path.rstrip("/"))
    report = render(F, sites, name, junk, unknown)
    if args.output:
        open(args.output, "w", encoding="utf-8").write(report + "\n")
        print("отчёт записан: %s" % args.output)
    else:
        print(report)
    if args.sort:
        sort_output(F, sites, args.sort, name)
        print("сайты разложены в: %s" % args.sort)
    errors = sum(F.count(s["key"], "ERROR") for s in sites)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
