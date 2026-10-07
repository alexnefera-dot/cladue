#!/usr/bin/env python3
"""Блоки и их варианты: состав страницы, матрица variant, проверка «ярлык или реальный рескин».

    python3 bloki.py <папка-наборов> [--page main] [--seq]

--seq  дополнительно печатает последовательность блоков по каждому набору.
Ищет CSS и в <style>, и в локальных файлах *_files/ (css/php), чтобы понять,
есть ли под variant-класс хоть одно правило.
"""
import sys, os, re, glob
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import obshee
from bs4 import BeautifulSoup

BLOCKISH = re.compile(r"(-section|-block|-widget|-dashboard|-root|-value|-pillars|-only|-nav|-sections)$|^(header|footer|main-nav)$")

def css_of(setdir, page_file):
    """Весь CSS набора: инлайн <style> + локальные файлы рядом."""
    css = []
    raw = open(page_file, encoding="utf-8", errors="ignore").read()
    css += re.findall(r"<style[^>]*>(.*?)</style>", raw, re.S)
    base = os.path.splitext(page_file)[0] + "_files"
    for pat in ("*.css", "*.php", "css*"):
        for f in glob.glob(os.path.join(base, pat)):
            try: css.append(open(f, encoding="utf-8", errors="ignore").read())
            except Exception: pass
    return "\n".join(css)

def analyse(setdir, page="main"):
    fs = obshee.pages(setdir, {page}) or obshee.pages(setdir)[:1]
    if not fs: return None
    f = fs[0]
    s = obshee.soup_of(f)
    css = css_of(setdir, f)
    blocks = {}        # block-class -> variant (или "")
    seq = []
    for el in s.find_all(class_=True):
        cls = el.get("class")
        var = next((c for c in cls if re.match(r"variant-v\d", c)), "")
        base = next((c for c in cls if BLOCKISH.search(c)), "")
        if not base:
            continue
        if base not in blocks or (var and not blocks[base]):
            blocks[base] = var
        if not seq or seq[-1] != base:
            seq.append(base)
    body = s.find("body")
    bc = " ".join(body.get("class") or []) if body else ""
    meta = {
        "тема": (re.search(r"theme-(\w+)", bc) or [None, "—"])[1],
        "раскладка": (re.search(r"layout-structure-(\w+)", bc) or [None, "—"])[1],
        "тип": (re.search(r"page-(\w+)", bc) or [None, "—"])[1],
    }
    return {"блоки": blocks, "seq": seq, "meta": meta, "css": css}

def main():
    args, opts = obshee.split_args(sys.argv[1:])
    page = opts["--page"][0] if "--page" in opts else "main"
    if not args: print(__doc__); sys.exit(1)
    sets = obshee.sets_from(args[0], opts)
    data = {}
    for p in sets:
        r = analyse(p, page)
        if r: data[os.path.basename(p.rstrip("/"))] = r
    if not data: print("наборы не найдены"); sys.exit(1)
    names = list(data)
    allblocks = sorted({b for d in data.values() for b in d["блоки"]})
    # правила считаем по одному набору: CSS у сайтов почти идентичны,
    # суммирование по всем множило бы счёт на их число
    css_one = max((d["css"] for d in data.values()), key=len)
    css_all = css_one
    print(f"Страница: {page}.  Наборов: {len(names)}.  Разных блоков: {len(allblocks)}\n")
    print("| блок | " + " | ".join(names) + " | CSS-правил под variant | вердикт |")
    print("|---|" + "---|" * (len(names) + 2))
    real = fake = 0
    for b in allblocks:
        cells = [data[n]["блоки"].get(b, "—").replace("variant-", "") or "—" for n in names]
        if not any(c.startswith("v") for c in cells):
            continue
        nrules = len(re.findall(r"\." + re.escape(b) + r"\.variant-v\d", css_all))
        verdict = "рескин" if nrules else "ярлык (вид не меняется)"
        real += 1 if nrules else 0; fake += 0 if nrules else 1
        print(f"| `{b}` | " + " | ".join(cells) + f" | {nrules} | {verdict} |")
    print(f"\nБлоков с variant: {real+fake} — из них реально перерисовываются **{real}**, пустых ярлыков **{fake}**.")
    print("\n| ручка | " + " | ".join(names) + " |")
    print("|---|" + "---|" * len(names))
    for k in ("тема", "раскладка", "тип"):
        print(f"| {k} | " + " | ".join(data[n]["meta"][k] for n in names) + " |")
    for k, sel in (("раскладка", "layout-structure"),):
        rules = re.findall(r"[^{};]{0,80}layout-structure-\w+[^{]{0,60}\{", css_all)
        print(f"\nCSS-селекторов под `{sel}`: {len(rules)}" + ("" if rules else "  → ярлык без эффекта"))
        for r in rules[:4]:
            print("    " + re.sub(r"\s+", " ", r).strip()[-80:])
    if "--seq" in opts:
        print("\n## Последовательность блоков")
        for n in names:
            print(f"\n**{n}**\n\n`" + " → ".join(data[n]["seq"]) + "`")

if __name__ == "__main__":
    main()
