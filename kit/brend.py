#!/usr/bin/env python3
"""Где живёт бренд: все поверхности, не только видимый текст.

    python3 brend.py <папка-наборов> [--pages main,slots,...]
"""
import sys, os, re
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import obshee
from bs4 import BeautifulSoup

ORDER = ["<title>","meta content","JSON-LD","видимый текст","img alt","img src (имя файла)",
         "href (URL)","<link href>","title= у ссылок","title= прочее","aria-label","class=","id="]

def scan(setdir, only=None):
    brands = obshee.detect_brand(setdir)
    if not brands: return brands, {}
    rx = re.compile("|".join(re.escape(b) for b in brands), re.I)
    S = defaultdict(int)
    for f in obshee.pages(setdir, only):
        raw = open(f, encoding="utf-8", errors="ignore").read()
        s = BeautifulSoup(raw, "lxml")
        t = s.find("title")
        if t: S["<title>"] += len(rx.findall(t.get_text()))
        for m in s.find_all("meta"):
            S["meta content"] += len(rx.findall(m.get("content") or ""))
        for sc in s.find_all("script", type="application/ld+json"):
            S["JSON-LD"] += len(rx.findall(sc.string or sc.get_text() or ""))
        for a in s.find_all("a"):
            S["href (URL)"] += len(rx.findall(a.get("href") or ""))
            S["title= у ссылок"] += len(rx.findall(a.get("title") or ""))
        for l in s.find_all("link"):
            S["<link href>"] += len(rx.findall(l.get("href") or ""))
        for i in s.find_all("img"):
            S["img src (имя файла)"] += len(rx.findall(i.get("src") or ""))
            S["img alt"] += len(rx.findall(i.get("alt") or ""))
        for el in s.find_all(attrs={"aria-label": True}):
            S["aria-label"] += len(rx.findall(el.get("aria-label")))
        for el in s.find_all(attrs={"title": True}):
            if el.name in ("a", "img"): continue
            S["title= прочее"] += len(rx.findall(el.get("title") or ""))
        for el in s.find_all(class_=True):
            S["class="] += len(rx.findall(" ".join(el.get("class"))))
        for el in s.find_all(id=True):
            S["id="] += len(rx.findall(el.get("id") or ""))
        s2 = BeautifulSoup(raw, "lxml")
        for x in s2(["script", "style"]): x.decompose()
        body = s2.body or s2
        S["видимый текст"] += len(rx.findall(body.get_text(" ", strip=True)))
    return brands, S

def main():
    args, opts = obshee.split_args(sys.argv[1:])
    only = set(opts["--pages"][0].split(",")) if "--pages" in opts else None
    if not args: print(__doc__); sys.exit(1)
    sets = obshee.sets_from(args[0], opts)
    res = {}
    for p in sets:
        b, S = scan(p, only)
        res[os.path.basename(p.rstrip("/"))] = (b, S)
    cols = list(res)
    keys = [k for k in ORDER if any(res[c][1].get(k) for c in cols)]
    print("| поверхность | " + " | ".join(cols) + " |")
    print("|---|" + "---|" * len(cols))
    for k in keys:
        print(f"| {k} | " + " | ".join(str(res[c][1].get(k, 0)) for c in cols) + " |")
    tot = {c: sum(res[c][1].values()) for c in cols}
    print("| **ИТОГО** | " + " | ".join(f"**{tot[c]}**" for c in cols) + " |")
    print("| вне видимого текста, % | " + " | ".join(
        f"{(tot[c]-res[c][1].get('видимый текст',0))/tot[c]*100:.0f}%" if tot[c] else "—" for c in cols) + " |")
    print()
    for c in cols: print(f"  {c}: бренд опознан как {res[c][0]}")

if __name__ == "__main__":
    main()
