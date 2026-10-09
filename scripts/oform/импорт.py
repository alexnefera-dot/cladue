#!/usr/bin/env python3
"""Проверка комплектов под формат импорта (см. templates/README.md).

    python3 scripts/oform/импорт.py <папка с комплектами>

Ошибка в любой папке отменяет весь импорт, поэтому проверяем до отдачи.
Код возврата 1, если что-то не так.
"""
import os
import re
import sys

СТРАНИЦА = re.compile(r"^[a-z][a-z0-9_-]*$")
КАРТИНКА = re.compile(r"^([a-z][a-z0-9_-]*)_img_\d+\.[a-z0-9]+$")
СТИЛЬ = re.compile(r'(?is)<style[^>]*>.*?</style>|style="[^"]*"')
# url() ищем только в стилях: в тексте страницы попадается и обычная проза
# («base64url(sha256(секрет))»), и проверка принимала её за ссылку на картинку.
ССЫЛКА_СТИЛЯ = re.compile(r'url\((?:\'|")?([^\'")]*)(?:\'|")?\)')
ИСТОЧНИК = re.compile(r'src="([^"]*)"')


def проверить(kit):
    беды = []
    файлы = sorted(os.listdir(kit))
    страницы = {f[:-5] for f in файлы if f.endswith(".html")}
    if "main" not in страницы:
        беды.append("нет main.html")
    for f in файлы:
        if f.endswith(".html"):
            if not СТРАНИЦА.match(f[:-5]):
                беды.append("имя страницы не по правилу: " + f)
        elif f != "images":
            беды.append("лишний файл: " + f)
    картинки = set()
    if "images" in файлы:
        for k in sorted(os.listdir(os.path.join(kit, "images"))):
            картинки.add(k)
            m = КАРТИНКА.match(k)
            if not m:
                беды.append("имя картинки не по правилу: " + k)
            elif m.group(1) not in страницы:
                беды.append("картинка не от страницы комплекта: " + k)
            if os.path.getsize(os.path.join(kit, "images", k)) == 0:
                беды.append("пустая картинка: " + k)
    for f in файлы:
        if not f.endswith(".html"):
            continue
        html = open(os.path.join(kit, f), encoding="utf-8").read()
        ссылки = [m.group(1) for m in ИСТОЧНИК.finditer(html)]
        for кусок in СТИЛЬ.findall(html):
            ссылки += ССЫЛКА_СТИЛЯ.findall(кусок)
        for ссылка in ссылки:
            if not ссылка or ссылка.startswith(("http", "data:", "/", "#")):
                continue
            # в HTML должно стоять голое имя файла: путь подставляет импорт
            if "/" in ссылка:
                беды.append("%s: путь вместо имени файла: %s" % (f, ссылка))
            elif ссылка not in картинки:
                беды.append("%s: картинки нет в images/: %s" % (f, ссылка))
    return беды


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    корень = sys.argv[1]
    комплекты = sorted(d for d in os.listdir(корень)
                       if os.path.isdir(os.path.join(корень, d)))
    всего = 0
    for d in комплекты:
        беды = проверить(os.path.join(корень, d))
        всего += len(беды)
        for б in беды:
            print("%-22s %s" % (d, б))
    print("комплектов %d, ошибок %d" % (len(комплекты), всего))
    return 1 if всего else 0


if __name__ == "__main__":
    sys.exit(main())
