#!/usr/bin/env python3
"""Сохранённая страница -> обычная статика: index.html, css/, img/.

    python3 scripts/lending.py <папка с выкачкой> -o <папка выдачи> [--обрезать-с "<строка>"]

Что делает:
- берёт HTML и его папку `<имя>_files`;
- `--обрезать-с` режет разметку начиная с первого вхождения строки и до `</body>`:
  так из главной страницы сайта остаётся только лендинг оферов;
- собирает CSS, который к странице относится, в `css/styles.css` (нужен Node с Playwright:
  правила проверяются по живому документу, иначе от 500 КБ чужих стилей не отличить нужные);
- переносит картинки в `img/` и чинит пути: выкачка оставляет абсолютные (`/img/splash/x.webp`),
  из-за них фон и логотипы не грузятся нигде, кроме исходного домена;
- оставляет в голове только charset, viewport, title, description и ссылку на стили;
  счётчики, prefetch чужих доменов и блоки `ld+json` удаляются.
"""
import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile

ПУСТЫЕ = {"br", "img", "meta", "link", "input", "hr", "source", "path", "use",
          "circle", "rect", "ellipse", "line", "polygon", "stop", "area", "col",
          "embed", "track", "wbr"}
КАРТИНКИ = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".ico", ".avif")
СБОРЩИК = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oform", "собрать-css.js")
# Признаки чужой аналитики в скрипте: по ним он не переносится в шаблон.
СЧЁТЧИК = re.compile(r"(?i)mc\.yandex\.ru|metrika|googletagmanager|google-analytics|gtag\(|dataLayer")


def найти_страницу(папка):
    """HTML и его папка с файлами. Служебное от macOS не в счёт."""
    for корень, папки, файлы in os.walk(папка):
        папки[:] = [p for p in папки if p != "__MACOSX"]
        for f in sorted(файлы):
            if f.lower().endswith((".html", ".htm")) and not f.startswith("._"):
                рядом = os.path.join(корень, os.path.splitext(f)[0] + "_files")
                return os.path.join(корень, f), (рядом if os.path.isdir(рядом) else None)
    raise SystemExit("в папке нет html")


def обрезать(t, метка):
    """Всё от метки и до конца тела — долой."""
    рез = t.find(метка)
    if рез < 0:
        raise SystemExit("метка обрезки не найдена: " + метка)
    конец = t.rfind("</body>")
    return t[:рез] + "\n" + t[конец:]


def чистая_голова(t, заголовок, описание):
    """Голова с нуля: от выкачки там счётчики, prefetch чужих доменов и гора ld+json."""
    тело = t[t.find("<body"):]
    return (
        "<!doctype html>\n<html lang=\"ru\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
        "<title>%s</title>\n"
        "<meta name=\"description\" content=\"%s\">\n"
        "<link rel=\"stylesheet\" href=\"css/styles.css\">\n"
        "</head>\n%s" % (html.escape(заголовок), html.escape(описание), тело)
    )


def имя_картинки(путь):
    """Имя для img/: только строчная латиница, цифры и дефис. «brand(1).png» -> «brand-1.png»."""
    основа, расш = os.path.splitext(os.path.basename(путь))
    основа = re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9-]+", "-", основа)).strip("-").lower()
    return (основа or "img") + расш.lower()


def разобрать_css(текст):
    """CSS на правила верхнего уровня: [(селекторы или None, целый кусок текста)].

    Разбираем сами, а не через браузер: CSSOM теряет сокращения с var() внутри
    (`background: linear-gradient(…, var(--gold))` читается пустым), и собранный
    из него файл делает текст невидимым.
    """
    текст = re.sub(r"/\*.*?\*/", "", текст, flags=re.S)
    куски, глубина, начало = [], 0, 0
    i = 0
    while i < len(текст):
        з = текст[i]
        if з in "\"'":
            кавычка = з
            i += 1
            while i < len(текст) and текст[i] != кавычка:
                i += 2 if текст[i] == "\\" else 1
        elif з == "{":
            глубина += 1
        elif з == "}":
            глубина -= 1
            if глубина == 0:
                куски.append(текст[начало:i + 1].strip())
                начало = i + 1
        i += 1
    хвост = текст[начало:].strip()
    if хвост:
        куски.append(хвост)
    правила = []
    for к in куски:
        if not к or "{" not in к:
            continue
        голова = к[:к.index("{")].strip()
        правила.append((None if голова.startswith("@") else голова, к, голова))
    return правила


def отсеять(текст, нужные):
    """Оставить правила, чьи селекторы браузер признал нужными. @-блоки — рекурсивно."""
    вышло = []
    for селекторы, кусок, голова in разобрать_css(текст):
        if селекторы is None:
            if re.match(r"@(media|supports|layer|container)\b", голова):
                внутри = кусок[кусок.index("{") + 1:кусок.rindex("}")]
                ядро = отсеять(внутри, нужные)
                if ядро.strip():
                    вышло.append("%s{%s}" % (голова, ядро))
            else:
                вышло.append(кусок)        # @font-face, @keyframes, @import — как есть
            continue
        оставить = [s.strip() for s in разделить_селекторы(селекторы) if s.strip() in нужные]
        if оставить:
            тело = кусок[кусок.index("{") + 1:кусок.rindex("}")]
            вышло.append("%s{%s}" % (",".join(оставить), тело))
    return "\n".join(вышло)


def разделить_селекторы(голова):
    """Запятые верхнего уровня: внутри :is(…), :not(…) они не разделяют."""
    части, глубина, начало = [], 0, 0
    for i, з in enumerate(голова):
        if з == "(":
            глубина += 1
        elif з == ")":
            глубина -= 1
        elif з == "," and глубина == 0:
            части.append(голова[начало:i]); начало = i + 1
    части.append(голова[начало:])
    return части


def нужные_селекторы(страница, селекторы):
    """Спросить браузер, какие селекторы к странице относятся."""
    if not os.path.isfile(СБОРЩИК):
        raise SystemExit("нет сборщика CSS: " + СБОРЩИК)
    среда = dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/opt/node22/lib/node_modules"))
    узел = os.environ.get("NODE", "/opt/node22/bin/node")
    import json
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as вх:
        json.dump(селекторы, вх)
        путь_вх = вх.name
    путь_вых = путь_вх + ".out"
    try:
        r = subprocess.run([узел, СБОРЩИК, страница, путь_вх, путь_вых],
                           capture_output=True, text=True, env=среда)
        if r.returncode != 0:
            raise SystemExit("сборщик CSS упал:\n" + r.stdout + r.stderr)
        print("   " + r.stdout.strip())
        return set(json.load(open(путь_вых, encoding="utf-8")))
    finally:
        for f in (путь_вх, путь_вых):
            if os.path.exists(f):
                os.unlink(f)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("папка")
    p.add_argument("-o", "--выход", required=True)
    p.add_argument("--обрезать-с", default=None,
                   help="строка, начиная с которой разметка удаляется до конца тела")
    p.add_argument("--заголовок", default=None)
    p.add_argument("--описание", default="")
    арг = p.parse_args()

    страница, файлы = найти_страницу(арг.папка)
    t = open(страница, encoding="utf-8", errors="replace").read()
    print("страница: %s, %d КБ" % (os.path.basename(страница), len(t) // 1024))

    if арг.обрезать_с:
        было = len(t)
        t = обрезать(t, арг.обрезать_с)
        print("   обрезано %d КБ разметки" % ((было - len(t)) // 1024))

    заголовок = арг.заголовок
    if заголовок is None:
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", open(страница, encoding="utf-8",
                                                              errors="replace").read())
        заголовок = html.unescape(re.sub(r"\s+", " ", m.group(1)).strip()) if m else "Офферы"

    выход = арг.выход
    shutil.rmtree(выход, ignore_errors=True)
    os.makedirs(os.path.join(выход, "css"))
    os.makedirs(os.path.join(выход, "img"))

    # Картинки: и те, что лежат рядом в <имя>_files, и те, на которые остались абсолютные пути.
    карта = {}
    if файлы:
        for f in sorted(os.listdir(файлы)):
            if f.startswith(".") or not f.lower().endswith(КАРТИНКИ):
                continue
            новое = имя_картинки(f)
            shutil.copy2(os.path.join(файлы, f), os.path.join(выход, "img", новое))
            карта[f] = новое
    print("   картинок перенесено: %d" % len(карта))

    # Локальные <link rel=stylesheet> втягиваем прямо в страницу: на file:// браузер
    # не отдаёт правила подключённого файла (чужое происхождение), и сборщик их не видит.
    def втянуть(m):
        путь = m.group(1)
        полный = os.path.normpath(os.path.join(os.path.dirname(страница), путь.lstrip("./")))
        if not os.path.isfile(полный):
            return m.group(0)
        return "<style>\n%s\n</style>" % open(полный, encoding="utf-8", errors="replace").read()

    t = re.sub(r'<link[^>]*rel="stylesheet"[^>]*href="(\./[^"]+)"[^>]*>', втянуть, t)

    # Скрипты из папки выкачки переезжают в js/ рядом со страницей. Счётчики не берём:
    # это чужая аналитика (Метрика, GA, GTM), в шаблоне ей делать нечего.
    скрипты = {}
    if файлы:
        for f in sorted(os.listdir(файлы)):
            if f.lower().endswith(".js") and not f.startswith("."):
                тело = open(os.path.join(файлы, f), encoding="utf-8", errors="replace").read(4000)
                if СЧЁТЧИК.search(тело):
                    print("   счётчик выброшен: %s" % f)
                    continue
                os.makedirs(os.path.join(выход, "js"), exist_ok=True)
                новое_имя = имя_картинки(f)
                shutil.copy2(os.path.join(файлы, f), os.path.join(выход, "js", новое_имя))
                скрипты[f] = новое_имя
    if скрипты:
        print("   скриптов перенесено: %d" % len(скрипты))

    # Весь CSS страницы одним текстом, в порядке документа: позже объявленное перебивает раннее.
    исходный_css = "\n".join(re.findall(r"(?is)<style[^>]*>(.*?)</style>", t))
    селекторы = []
    def собрать_селекторы(текст):
        for сел, кусок, голова in разобрать_css(текст):
            if сел is None:
                if re.match(r"@(media|supports|layer|container)\b", голова):
                    собрать_селекторы(кусок[кусок.index("{") + 1:кусок.rindex("}")])
            else:
                селекторы.extend(s.strip() for s in разделить_селекторы(сел) if s.strip())
    собрать_селекторы(исходный_css)

    # Промежуточная страница рядом с исходником: по ней браузер и решит, что из CSS нужно.
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=os.path.dirname(страница),
                                     encoding="utf-8", delete=False) as вр:
        вр.write(t)
        временная = вр.name
    try:
        нужные = нужные_селекторы(временная, sorted(set(селекторы)))
    finally:
        os.unlink(временная)
    open(os.path.join(выход, "css", "styles.css"), "w", encoding="utf-8").write(
        отсеять(исходный_css, нужные))

    # Пути в HTML и CSS: папка выкачки -> img/, абсолютные пути сайта -> тот же img/.
    def чинить(текст, префикс):
        if файлы:
            корень = os.path.basename(файлы)
            for старое, новое in скрипты.items():
                текст = текст.replace("./%s/%s" % (корень, старое), "js/" + новое)
                текст = текст.replace("%s/%s" % (корень, старое), "js/" + новое)
            for старое, новое in карта.items():
                текст = текст.replace("./%s/%s" % (корень, старое), префикс + новое)
                текст = текст.replace("%s/%s" % (корень, старое), префикс + новое)
        # «/img/splash/stage-hero.webp» и подобное: имя файла у нас уже есть
        def абсолютный(m):
            имя = имя_картинки(m.group(0))
            return префикс + имя if имя in карта.values() else m.group(0)
        текст = re.sub(r"/[\w./-]*?/[\w.-]+(?:%s)" % "|".join(re.escape(e) for e in КАРТИНКИ),
                       абсолютный, текст)
        # Путь, который скрипт достраивает на ходу: `/img/partners/${partner.image}`.
        # Имя файла тут появляется только в браузере, поэтому правилом выше не ловится.
        return re.sub(r"/img(?:/[\w-]+)*/(?=\$\{)", префикс, текст)

    t = чинить(t, "img/")
    css_путь = os.path.join(выход, "css", "styles.css")
    css = чинить(open(css_путь, encoding="utf-8").read(), "../img/")
    open(css_путь, "w", encoding="utf-8").write(css)
    # Перенесённые скрипты тоже держат пути: браузер считает их от страницы, значит «img/».
    for новое_имя in скрипты.values():
        путь = os.path.join(выход, "js", новое_имя)
        open(путь, "w", encoding="utf-8").write(
            чинить(open(путь, encoding="utf-8", errors="replace").read(), "img/"))

    # Ссылки на невзятые скрипты и инлайновые счётчики из разметки убираем.
    if файлы:
        корень = os.path.basename(файлы)
        t = re.sub(r'<script[^>]*src="\.?/?%s/[^"]+"[^>]*>\s*</script>' % re.escape(корень), "", t)
    t = re.sub(r"(?is)<script\b[^>]*>(?:(?!</script>).)*?(?:mc\.yandex\.ru|googletagmanager|"
               r"google-analytics|gtag\()(?:(?!</script>).)*?</script>", "", t)

    t = чистая_голова(t, заголовок, арг.описание)
    # Инлайновые <style> уже уехали в styles.css — в теле они больше не нужны.
    t = re.sub(r"(?is)<style[^>]*>.*?</style>", "", t)
    open(os.path.join(выход, "index.html"), "w", encoding="utf-8").write(t)

    # Картинки, на которые в итоге никто не ссылается, в шаблоне не нужны.
    весь = t + css + "".join(open(os.path.join(выход, "js", f), encoding="utf-8",
                                  errors="replace").read() for f in скрипты.values())
    лишние = [f for f in sorted(os.listdir(os.path.join(выход, "img"))) if f not in весь]
    for f in лишние:
        os.remove(os.path.join(выход, "img", f))
    if лишние:
        print("   неиспользуемых картинок удалено: %d" % len(лишние))

    итог = sum(os.path.getsize(os.path.join(r, f))
               for r, _, fs in os.walk(выход) for f in fs)
    print("готово: %s — index.html %d КБ, css/styles.css %d КБ, img/ %d файлов, всего %d КБ"
          % (выход, len(t) // 1024, len(css) // 1024, len(карта), итог // 1024))


if __name__ == "__main__":
    main()
