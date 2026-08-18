#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сверка очищенного корпуса с оригиналами доноров по написанию бренда.

    python3 engine/sverka-brenda.py <папка-с-оригиналами> [--json]

Очищенный донор — это текст, в котором редактор заменил имя площадки на
%brand_name_ru% / %brand_name_en%. Вопрос, ради которого написан скрипт: не
переврал ли редактор письменность. Считать вхождения по обе стороны бесполезно —
в оригинале бренд стоит ещё и в шапке, подвале, лицензии и облаке запросов,
которых в очищенном тексте нет.

Поэтому здесь выравнивание, а не подсчёт. Очищенный текст режется по
плейсхолдерам на сегменты, каждый сегмент ищется в оригинале последовательно, и
промежуток между соседними сегментами — ровно то, что плейсхолдер заменил. Так
видно не «сколько», а «что именно» стояло на каждом месте.

Дополнительно считаются упоминания в зоне статьи (от начала первого сегмента до
конца последнего) — это ловит пропуски редактора, если они есть.
"""
import os
import re
import sys
import json
import html
import collections

PAGES = ["main", "app", "bonus", "registracia", "slots", "vhod", "zerkalo"]
CLEAN = "samples/v4-donors"
PH = re.compile(r"%brand_name_(ru|en)%")
CYR = re.compile(r"[А-Яа-яЁё]")
LAT = re.compile(r"[A-Za-z]")


def plain(h):
    """Текст без разметки. Голый `<` экранируется: иначе strip съедает полфайла."""
    h = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", h)
    h = re.sub(r"(?s)<!--.*?-->", " ", h)
    h = re.sub(r"<(?![a-zA-Z/!?])", "&lt;", h)
    h = re.sub(r"(?s)<[^>]*>", " ", h)
    h = html.unescape(h).replace(" ", " ").replace("‑", "-")
    return re.sub(r"\s+", " ", h).strip()


def align(cleaned, original):
    """[(письменность_плейсхолдера, что_стояло)], зона статьи. (None, None) если не сошлось."""
    ct, ot = plain(cleaned), plain(original)
    parts, kinds, last = [], [], 0
    for m in PH.finditer(ct):
        parts.append(ct[last:m.start()])
        kinds.append(m.group(1))
        last = m.end()
    parts.append(ct[last:])

    pos, starts, ends = 0, [], []
    for seg in parts:
        s = seg.strip()
        if not s:
            starts.append(pos)
            ends.append(pos)
            continue
        j = ot.find(s[:60], pos)
        if j < 0:
            return None, None
        starts.append(j)
        if ot.startswith(s, j):
            e = j + len(s)
        else:
            k = ot.find(s[-60:], j)
            e = k + 60 if k >= 0 else j + 60
        ends.append(e)
        pos = e

    gaps = [(kinds[i], ot[ends[i]:starts[i + 1]].strip()) for i in range(len(kinds))]
    return gaps, ot[starts[0]:ends[-1]]


def pismo(w):
    if len(w) > 30:
        return "не разобрано"
    if CYR.search(w) and LAT.search(w):
        return "смесь"
    if CYR.search(w):
        return "кириллица"
    if LAT.search(w):
        return "латиница"
    return "пусто"


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    kak_json = "--json" in sys.argv
    if not args or not os.path.isdir(args[0]):
        sys.exit("usage: python3 engine/sverka-brenda.py <папка-с-оригиналами> [--json]")
    orig = args[0]

    sites = sorted(d for d in os.listdir(orig)
                   if os.path.isdir(f"{orig}/{d}") and not d.startswith("__")
                   and os.path.isdir(f"{CLEAN}/{d}"))
    res, svod = {}, collections.Counter()
    for s in sites:
        res[s] = {}
        for p in PAGES:
            fo, fc = f"{orig}/{s}/{p}.html", f"{CLEAN}/{s}/{p}.html"
            if not (os.path.isfile(fo) and os.path.isfile(fc)):
                continue
            cc = open(fc, encoding="utf-8", errors="replace").read()
            co = open(fo, encoding="utf-8", errors="replace").read()
            gaps, zona = align(cc, co)
            e = {"ph_en": len(re.findall(r"%brand_name_en%", cc)),
                 "ph_ru": len(re.findall(r"%brand_name_ru%", cc)),
                 "сошлось": zona is not None}
            if zona is not None:
                e["замены"] = [{"плейсхолдер": k, "стояло": w, "письменность": pismo(w)}
                               for k, w in gaps]
                for k, w in gaps:
                    svod[(k, pismo(w))] += 1
            res[s][p] = e

    if kak_json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return

    print(f"{'сайт':12}{'страница':13}{'ph_en':>6}{'ph_ru':>6}   замены")
    for s, pp in res.items():
        for p, v in pp.items():
            if not v["сошлось"]:
                print(f"{s:12}{p:13}{'':>6}{'':>6}   — выравнивание не сошлось")
                continue
            c = collections.Counter(z["письменность"] for z in v["замены"])
            hvost = ", ".join(f"{k} {n}" for k, n in c.most_common()) or "—"
            print(f"{s:12}{p:13}{v['ph_en']:>6}{v['ph_ru']:>6}   {hvost}")

    print("\n── чем на деле был каждый плейсхолдер ──")
    for (k, cls), n in sorted(svod.items()):
        print(f"  %brand_name_{k}% → {cls:14} {n}")


main()
