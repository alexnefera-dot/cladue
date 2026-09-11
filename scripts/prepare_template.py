#!/usr/bin/env python3
"""Подготовка скачанного сайта под наш шаблонизатор: подстановка переменных и разбор остатков.

Использование:
    python3 scripts/prepare_template.py <папка со страницами> [-o папка] [--домен X]
        [--бренд-ру X] [--бренд-ен X] [--картинки X] [--метрика %переменная%] [--слоты ПУТЬ]

Что делает:
  1. Находит в страницах домен, бренд (русский и латиницей), папку картинок и номер
     счётчика Яндекс.Метрики — или берёт их из ключей.
  2. Меняет их на переменные: %domain_name%, %brand_name_ru%, %brand_name_en%,
     %directory_img% и переменную счётчика (по умолчанию %yandex_metrika_id%).
  3. Чинит мусор выкачки: путь вида /ru/ru/ru/… в ссылках, canonical и hreflang.
  4. Пишет отчёт: что осталось от чужого проекта, какие ссылки ведут не на страницы
     набора и какие файлы движка страницы просят (styles.php, manifest.json и т. п.).

Контакты (телефон, почта, мессенджеры) не трогаются: это наши же данные.
"""
import argparse
import collections
import os
import re
import shutil
import sys

НАБОР = ["app", "bonus", "info", "main", "news", "obzor", "partnery", "promo",
         "registracia", "slots", "vhod", "zerkalo"]
СЛУЖЕБНЫЕ = ["styles.php", "manifest.json", "rss.xml", "atom.xml", "tableau.json",
             "xmlrpc.php", "sitemap.xml", "robots.txt", "search"]
RU_ПУТЬ = re.compile(r'(?:/ru){2,}/?', re.I)
RU_ПУТЬ_ESC = re.compile(r'(?:\\/ru){2,}\\/?', re.I)


def найти(тексты):
    """Домен, бренд, папка картинок и счётчик метрики — по самим страницам."""
    всё = "\n".join(тексты)
    домен = collections.Counter(re.findall(r'https?://([a-z0-9][a-z0-9.-]+\.[a-z]{2,})', всё, re.I))
    свои = {"schema.org", "ogp.me", "fonts.googleapis.com", "fonts.gstatic.com", "mc.yandex.ru",
            "www.google-analytics.com", "www.googletagmanager.com", "t.me", "vk.com",
            "www.googleadservices.com", "yandex.ru", "www.w3.org"}
    домены = [d for d, _ in домен.most_common() if d.lower() not in свои]
    return {
        "домен": домены[0] if домены else "",
        "бренд_ру": (collections.Counter(re.findall(r'([А-ЯЁ][а-яё]{2,})\s+Казино', всё)).most_common(1) or [("", 0)])[0][0],
        "бренд_ен": (collections.Counter(re.findall(r'([A-Z][A-Za-z]{2,})\s+Casino', всё)).most_common(1) or [("", 0)])[0][0],
        "картинки": (collections.Counter(re.findall(r'/img/([\w.-]+)/', всё)).most_common(1) or [("", 0)])[0][0],
        "метрика": (collections.Counter(re.findall(r'mc\.yandex\.ru/(?:watch|metrika/tag\.js\?id=)(\d+)', всё)).most_common(1) or [("", 0)])[0][0],
    }


def подставить(html, к, метка):
    счёт = collections.Counter()

    def замена(шаблон, чем, имя):
        nonlocal html
        html, n = re.subn(шаблон, чем, html)
        счёт[имя] += n

    if к["домен"]:
        д = re.escape(к["домен"])
        замена(r'(?i)https?://' + д, "https://%domain_name%", "домен")
        замена(r'(?i)(?<![\w.])' + д + r'(?![\w-])', "%domain_name%", "домен")
        замена(r'(?i)https?:\\/\\/' + re.escape(к["домен"].replace('/', '\\/')), r"https:\/\/%domain_name%", "домен")
    if к["картинки"]:
        замена(r'/img/' + re.escape(к["картинки"]) + r'/', "/img/%directory_img%/", "папка картинок")
        замена(r'\\/img\\/' + re.escape(к["картинки"]) + r'\\/', r"\/img\/%directory_img%\/", "папка картинок")
    if к["бренд_ру"]:
        замена(r'(?<![А-Яа-яЁё])' + re.escape(к["бренд_ру"]) + r'(?![А-Яа-яЁё])', "%brand_name_ru%", "бренд (рус)")
    if к["бренд_ен"]:
        замена(r'(?<![A-Za-z])' + re.escape(к["бренд_ен"]) + r'(?![A-Za-z])', "%brand_name_en%", "бренд (лат)")
        замена(r'(?<![A-Za-z])' + re.escape(к["бренд_ен"].lower()) + r'(?![A-Za-z])', "%brand_name_en%", "бренд (лат)")
    if к["метрика"]:
        замена(r'(?<!\d)' + re.escape(к["метрика"]) + r'(?!\d)', метка, "счётчик метрики")
    # мусор выкачки: /ru/ru/ru/… вместо корня
    html, n = RU_ПУТЬ.subn("/", html)
    счёт["путь /ru/ru/…"] += n
    html, n = RU_ПУТЬ_ESC.subn(r"\/", html)
    счёт["путь /ru/ru/…"] += n
    return html, счёт


МЕТРИКА_БЛОКИ = [
    r'(?is)<script[^>]*mc\.yandex\.ru/metrika/[^>]*>.*?</script>',
    r'(?is)<script[^>]*>\s*\(function\(m,e,t,r,i,k,a\).*?</script>',
    r'(?is)<noscript>\s*<div>\s*<img[^>]*mc\.yandex\.ru/watch/[^>]*>\s*</div>\s*</noscript>',
    r'(?is)<link[^>]*(?:preconnect|dns-prefetch)[^>]*mc\.yandex\.ru[^>]*>',
]


def правила(html, счёт, слоты, вход):
    """Правки под наш движок: метрика прочь, свои пути, регистрация и вход — одна страница."""
    for шаблон in МЕТРИКА_БЛОКИ:
        html, n = re.subn(шаблон, "", html)
        счёт["метрика снята"] += n
    # картинки слотов лежат в общей папке картинок
    html, n = re.subn(r'(?<=["\'])/slots/(\d+\.jpg)', slots_путь(слоты) + r"\1", html)
    счёт["картинки слотов"] += n
    html, n = re.subn(r'\\/slots\\/(\d+\.jpg)', slots_путь(слоты).replace("/", "\\/") + r"\1", html)
    счёт["картинки слотов"] += n
    # utm-хвосты — метки чужой кампании, внутренним ссылкам они не нужны
    html, n = re.subn(r'\?utm_[^"\'<>\s\\]*', "", html)
    счёт["utm-хвосты сняты"] += n
    html, n = re.subn(r'\?utm_[^"\\]*(?=")', "", html)
    счёт["utm-хвосты сняты"] += n
    # регистрация и вход ведут на одну страницу движка; canonical, hreflang и @id
    # не трогаем — они называют саму страницу, а не цель ссылки
    цель = r'/(?:registracia|vhod)(?:/|#[\w-]*)?'
    html, n = re.subn(r'(<a\b[^>]*?\shref=")(?:https?://%domain_name%)?' + цель + r'(?=")', r"\1" + вход, html)
    счёт["ссылки регистрации и входа"] += n
    html, n = re.subn(r'(<link\b[^>]*?rel="(?:prefetch|preload)"[^>]*?href=")(?:https?://%domain_name%)?' + цель + r'(?=")',
                      r"\1" + вход, html)
    счёт["ссылки регистрации и входа"] += n
    html, n = re.subn(r'("(?:url|target|urlTemplate)"\s*:\s*")(https?:\\?/\\?/%domain_name%)?'
                      + цель.replace("/", r"\\?/") + r'(?=")',
                      lambda m: m.group(1) + (m.group(2) or "") + (вход.replace("/", r"\/") if m.group(2) and "\\" in m.group(2) else вход),
                      html)
    счёт["ссылки регистрации и входа"] += n
    html, n = re.subn(r'(property="og:see_also" content="(?:https?://%domain_name%)?)' + цель + r'(?=")',
                      r"\1" + вход, html)
    счёт["ссылки регистрации и входа"] += n
    # карта сайта — без расширения
    html, n = re.subn(r'/htmlmap\.html', "/htmlmap", html)
    html2, n2 = re.subn(r'\\/htmlmap\.html', r"\\/htmlmap", html)
    html, n = html2, n + n2
    счёт["карта сайта"] += n
    # в обычных ссылках путь с доменом не нужен: canonical, hreflang и схемы его сохраняют
    html, n = re.subn(r'(<a\b[^>]*?\shref=")https?://%domain_name%(/)', r"\1\2", html)
    счёт["ссылки без домена"] += n
    return html, счёт


def slots_путь(слоты):
    return (слоты or "/img/%directory_img%").rstrip("/") + "/"


def остатки(html, к, метка):
    из = collections.Counter()
    for имя, шаблон in (("домен", к["домен"]), ("бренд (рус)", к["бренд_ру"]),
                        ("бренд (лат)", к["бренд_ен"]), ("счётчик", к["метрика"])):
        if шаблон:
            из[имя] = len(re.findall(re.escape(шаблон), html, re.I))
    чужие = collections.Counter()
    for u in re.findall(r'(?:href|src|action)="(https?://[^"]+)"', html):
        d = re.sub(r'^https?://([^/]+).*$', r'\1', u)
        if "%domain_name%" not in d:
            чужие[d] += 1
    пути = collections.Counter()
    for u in re.findall(r'(?:href|src)="(?:https?://%domain_name%)?(/[^"#?]*)"', html):
        первый = u.strip("/").split("/")[0]
        if первый and первый not in НАБОР and not u.startswith("/img/"):
            пути[u] += 1
    файлы = collections.Counter(f for f in СЛУЖЕБНЫЕ if f in html)
    return из, чужие, пути, файлы


def main():
    p = argparse.ArgumentParser(description="Подготовка скачанного шаблона под шаблонизатор")
    p.add_argument("path")
    p.add_argument("-o", "--out", help="куда положить подготовленные страницы")
    p.add_argument("--домен", dest="домен")
    p.add_argument("--бренд-ру", dest="бренд_ру")
    p.add_argument("--бренд-ен", dest="бренд_ен")
    p.add_argument("--картинки", dest="картинки")
    p.add_argument("--метрика", dest="метрика", default="%yandex_metrika_id%",
                   help="на что менять номер счётчика, если блок метрики оставляют (по умолчанию %%yandex_metrika_id%%)")
    p.add_argument("--слоты", dest="слоты", default="/img/%directory_img%",
                   help="куда переносить картинки слотов (по умолчанию /img/%%directory_img%%)")
    p.add_argument("--вход", dest="вход", default="/singup",
                   help="страница регистрации и входа нашего движка (по умолчанию /singup)")
    args = p.parse_args()

    файлы = sorted(f for f in os.listdir(args.path) if f.endswith(".html"))
    if not файлы:
        sys.exit("в папке нет .html")
    тексты = [open(os.path.join(args.path, f), encoding="utf-8", errors="replace").read() for f in файлы]
    к = найти(тексты)
    for ключ, знач in (("домен", args.домен), ("бренд_ру", args.бренд_ру),
                       ("бренд_ен", args.бренд_ен), ("картинки", args.картинки)):
        if знач:
            к[ключ] = знач

    print("# Подготовка шаблона: %s" % os.path.basename(args.path.rstrip("/")))
    print()
    print("Найдено в страницах: домен `%s`, бренд «%s» / `%s`, папка картинок `%s`, счётчик метрики `%s`."
          % (к["домен"], к["бренд_ру"], к["бренд_ен"], к["картинки"], к["метрика"] or "—"))
    print()
    if args.out:
        os.makedirs(args.out, exist_ok=True)

    итог = collections.Counter()
    таблица, хвосты = [], collections.Counter()
    чужие_все, пути_все, файлы_все = collections.Counter(), collections.Counter(), collections.Counter()
    for f, html in zip(файлы, тексты):
        новый, счёт = подставить(html, к, args.метрика)
        новый, счёт = правила(новый, счёт, args.слоты, args.вход)
        из, чужие, пути, служебные = остатки(новый, к, args.метрика)
        итог.update(счёт)
        хвосты.update(из)
        чужие_все.update(чужие)
        пути_все.update(пути)
        файлы_все.update(служебные)
        таблица.append((f, sum(счёт.values()), sum(из.values())))
        if args.out:
            open(os.path.join(args.out, f), "w", encoding="utf-8").write(новый)
    if args.out:
        for f in os.listdir(args.path):
            if not f.endswith(".html") and os.path.isfile(os.path.join(args.path, f)):
                shutil.copy2(os.path.join(args.path, f), os.path.join(args.out, f))

    print("## Замены")
    print()
    print("| Что | Замен |")
    print("|---|---:|")
    for имя, n in итог.most_common():
        if n:
            print("| %s | %d |" % (имя, n))
    print()
    print("## По страницам")
    print()
    print("| Страница | Замен | Осталось от чужого |")
    print("|---|---:|---:|")
    for f, n, o in таблица:
        print("| %s | %d | %d |" % (f, n, o))
    if sum(хвосты.values()):
        print()
        print("**Осталось после замен:** " + ", ".join("%s — %d" % (k, v) for k, v in хвосты.items() if v))
    if чужие_все:
        print()
        print("## Ссылки на чужие домены")
        print()
        for d, n in чужие_все.most_common(20):
            print("- `%s` — %d" % (d, n))
    if пути_все:
        print()
        print("## Ссылки не на страницы набора")
        print()
        for u, n in пути_все.most_common(20):
            print("- `%s` — %d" % (u, n))
    if файлы_все:
        print()
        print("## Файлы движка, которые просят страницы")
        print()
        for f, n in файлы_все.most_common():
            print("- `%s`" % f)


if __name__ == "__main__":
    main()
