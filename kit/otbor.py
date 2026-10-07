"""Отбор наборов по сигнатуре движка.

Отделяет наборы нашего разбираемого конструктора от любых посторонних шаблонов,
сколько бы у тех ни было страниц. Признак — характерные классы блоков в разметке,
а не число страниц: набор того же движка может приехать неполным, а чужой сайт
может случайно иметь ровно 12 страниц.

  python3 otbor.py <папка> [--out otchet/nabory.txt] [--porog 6]
"""
import os, sys, re, collections
import obshee

# Классы блоков, которые есть у конструктора и практически не встречаются больше нигде.
SIGN = [
    "hero-value", "value-pillars", "slots-dashboard", "recent-payouts-block",
    "promo-timer-widget", "yandex-index-only", "page-thematic-block",
    "related-sections", "keywords-block", "win-notifications-root",
    "support-widget", "layout-block",
]
POROG = 6           # сколько признаков из 12 достаточно, чтобы счесть набор своим


def probe(setdir):
    """Сигнатура набора: какие блоки встретились, есть ли variant/theme, состав страниц."""
    ps = obshee.pages(setdir)
    names = sorted(os.path.splitext(os.path.basename(f))[0] for f in ps)
    found, variant, theme, layout = set(), 0, set(), set()
    for f in ps:
        try:
            raw = open(f, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for s in SIGN:
            if re.search(r'class="[^"]*\b' + re.escape(s) + r'\b', raw):
                found.add(s)
        variant += len(re.findall(r"\bvariant-v\d", raw))
        theme |= set(re.findall(r"\btheme-(t\d)", raw))
        layout |= set(re.findall(r"\blayout-structure-([a-z]+)", raw))
    return {"set": os.path.basename(setdir), "path": setdir, "pages": len(ps),
            "names": names, "hits": sorted(found), "n": len(found),
            "variant": variant, "theme": sorted(theme), "layout": sorted(layout)}


def main():
    args, opts = obshee.split_args(sys.argv[1:])
    if not args:
        print(__doc__); return
    root = args[0]
    porog = int(opts["--porog"][0]) if "--porog" in opts else POROG
    out = opts["--out"][0] if "--out" in opts else None

    rows = [probe(p) for p in obshee.find_sets(root)]
    rows.sort(key=lambda r: (-r["n"], r["set"]))
    nash = [r for r in rows if r["n"] >= porog]
    chuzh = [r for r in rows if r["n"] < porog]

    print("Папка: %s" % os.path.abspath(root))
    print("Наборов найдено: %d   ·   порог сигнатуры: %d из %d\n" % (len(rows), porog, len(SIGN)))

    print("## Наш конструктор — %d наборов\n" % len(nash))
    print("%-28s %5s %8s %8s %-10s %s" % ("набор", "стр.", "призн.", "variant", "темы", "раскладка"))
    for r in nash:
        print("%-28s %5d %5d/%-2d %8d %-10s %s" % (
            r["set"][:28], r["pages"], r["n"], len(SIGN), r["variant"],
            ",".join(r["theme"]) or "—", ",".join(r["layout"]) or "—"))

    if chuzh:
        print("\n## Посторонние — %d наборов (в замер не идут)\n" % len(chuzh))
        print("%-28s %5s %8s  %s" % ("набор", "стр.", "призн.", "какие признаки нашлись"))
        for r in chuzh:
            print("%-28s %5d %5d/%-2d  %s" % (
                r["set"][:28], r["pages"], r["n"], len(SIGN), ", ".join(r["hits"]) or "ни одного"))

    if nash:
        cnt = collections.Counter(tuple(r["names"]) for r in nash)
        print("\n## Состав страниц у своих наборов\n")
        for names, k in cnt.most_common():
            print("  %2d набор(ов), %d стр.: %s" % (k, len(names), ",".join(names)))
        common = set(nash[0]["names"])
        for r in nash[1:]:
            common &= set(r["names"])
        print("\nЕсть во ВСЕХ своих наборах:")
        print("   --pages %s" % ",".join(sorted(common)) if common else "   (общих страниц нет)")

    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("# наборы нашего конструктора, отобраны по сигнатуре (порог %d из %d)\n" % (porog, len(SIGN)))
            for r in nash:
                fh.write(r["set"] + "\n")
        print("\nСписок своих наборов записан: %s" % out)


if __name__ == "__main__":
    main()
