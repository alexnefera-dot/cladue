#!/usr/bin/env python3
"""Фильтрация архива без правок: набор страниц, заглушки, тонкие главные, точные дубли и уникальность.

Использование:
    python3 scripts/filter_archive.py <архив.zip | папка> -o <папка результата> [--порог 60] [--без-копий]

Ничего не чинит и не смотрит на бренды, переменные, ссылки и разметку: это другой этап.
Страницы могут быть как фрагментами, так и целыми документами: head, script, style,
header и footer не считаются ни текстом, ни материалом для сравнения.
Результат в папке:
  сводка.md   — итоги по типам, причины, самые похожие пары, списки убранных
  сайты.tsv   — строка на сайт: тип, сайт, группа, вердикт, причина, страниц, слов,
                главная (слов/разделов), совпадение %, с каким сайтом
  годные.txt  — годные «тип/домен», по одному в строке
  годные/<тип>/<домен>/ и убрано/<тип>/<домен>/ — копии страниц (без --без-копий);
                8/9/10-стр лежат уже как 7-стр
Уникальность: 6-словные цепочки, кандидаты по выборке 1/8 цепочек (короткие
страницы — целиком), шаблонные цепочки (на более чем 50 страницах) не считаются,
совпадение = доля общих цепочек от меньшей страницы по той же выборке; проверка
пар; сайт, у которого страница совпадает с чужой на порог и больше, убирается,
из пары остаётся сайт с бо́льшим объёмом текста. Рассчитан на сотни тысяч страниц:
страницы читаются по одной, в памяти только сводные числа и выборки.
"""
import argparse
import hashlib
import itertools
import os
import re
import shutil
import sys
import zipfile
import zlib
from array import array
from collections import Counter, defaultdict
from functools import lru_cache

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_archive import (CONVERT, JUNK_NAMES, MIN_MAIN_WORDS, TEMPLATES,  # noqa: E402
                           WIDGET_P, strip_tags)

# Страницы бывают целыми документами: служебное и обвязку не считаем ни текстом,
# ни материалом для сравнения.
CUT = re.compile(r"<head\b.*?</head>|<script\b.*?</script>|<style\b.*?</style>|"
                 r"<noscript\b.*?</noscript>|<!--.*?-->|<header\b.*?</header>|"
                 r"<footer\b.*?</footer>|<!DOCTYPE[^>]*>", re.S | re.I)


def body_html(raw):
    return CUT.sub(" ", raw)


def content_words(raw):
    """Слова видимого текста: абзацы, списки, таблицы, врезки; без карточек слотов и строк из 1–3 слов."""
    words = 0
    for tag in ("p", "li", "td", "dd", "summary", "blockquote", "figcaption", "caption"):
        for m in re.findall(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), raw, re.S | re.I):
            t = strip_tags(m).strip()
            n = len(re.findall(r"\w+", t))
            if n <= 3 or WIDGET_P.match(t):
                continue
            words += n
    return words


def sections(raw):
    """Разделы: h1/h2 плюс h3, после которых идёт не карточка слота."""
    n = len(re.findall(r"<h[12][^>]*>", raw, re.I))
    for m in re.finditer(r"<h3[^>]*>.*?</h3>", raw, re.S | re.I):
        tail = strip_tags(raw[m.end(): m.end() + 300]).strip()
        if not WIDGET_P.match(tail) and "RTP" not in tail[:120]:
            n += 1
    return n

GROUP_RX = re.compile(r"^(\d+)-стр$")
SAMPLE_MASK = 7           # выборка цепочек: hash & 7 == 0, то есть 1/8
SMALL_PAGE = 300          # у страниц короче 300 цепочек индексируются все цепочки
MAX_DF = 50               # цепочки, встречающиеся более чем на 50 страницах, — шаблонные, не улика
MIN_SHARED = 4            # минимум общих индексированных цепочек, чтобы проверять пару точно


# ---------------------------------------------------------------- источник ---
class Source:
    """Архив (zip) или папка: список сайтов и чтение страниц по одной."""

    def __init__(self, path):
        self.path = path
        self.zip = None
        self.entries = {}     # (группа, сайт, страница) -> имя записи / путь
        if os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                dirnames[:] = [d for d in dirnames if d != "__MACOSX"]
                for fn in filenames:
                    self._add(os.path.relpath(os.path.join(dirpath, fn), path), os.path.join(dirpath, fn))
        else:
            self.zip = zipfile.ZipFile(path)
            for info in self.zip.infolist():
                name = info.filename
                if not info.flag_bits & 0x800:
                    try:
                        name = name.encode("cp437").decode("utf-8")
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        pass
                if info.is_dir():
                    continue
                self._add(name, info.filename)

    def _add(self, rel, key):
        parts = rel.replace("\\", "/").split("/")
        if "__MACOSX" in parts or parts[-1] in JUNK_NAMES or parts[-1].startswith("._"):
            return
        for i, p in enumerate(parts):
            if GROUP_RX.match(p) and i + 2 < len(parts) and parts[-1].endswith(".html") and i + 2 == len(parts) - 1:
                self.entries[(p, parts[i + 1], parts[-1][:-5])] = key
                return

    def sites(self):
        by_site = defaultdict(dict)
        for (g, s, p), key in self.entries.items():
            by_site[(g, s)][p] = key
        for (g, s) in sorted(by_site, key=lambda k: (int(GROUP_RX.match(k[0]).group(1)), k[1])):
            yield g, s, by_site[(g, s)]

    def read(self, key):
        if self.zip:
            return self.zip.read(key).decode("utf-8", errors="replace")
        return open(key, encoding="utf-8", errors="replace").read()

    def read_bytes(self, key):
        return self.zip.read(key) if self.zip else open(key, "rb").read()


# ---------------------------------------------------------------- страницы ---
def shingle_hashes(words, n=6):
    """crc32 каждой 6-словной цепочки (слова в нижнем регистре)."""
    w = [x.lower() for x in words]
    return {zlib.crc32(" ".join(w[i:i + n]).encode()) for i in range(max(0, len(w) - n + 1))}


def page_stats(raw):
    raw = body_html(raw)
    words = re.findall(r"\w+", strip_tags(raw))
    sh = shingle_hashes(words)
    return {
        "nwords": len(words), "cw": content_words(raw), "sec": sections(raw),
        "md5": hashlib.md5(raw.encode("utf-8")).hexdigest(), "nsh": len(sh),
        "sampled": array("I", sorted(sh if len(sh) <= SMALL_PAGE else (h for h in sh if h & SAMPLE_MASK == 0))),
    }


# ---------------------------------------------------------------- решения ---
def structural_reasons(n, pages, stats, md5_seen, key):
    """Причины убрать сайт без сравнения с другими: набор страниц, заглушки, тонкая главная, копия своей же страницы, точный дубль."""
    tpl = TEMPLATES.get(n)
    why = []
    if tpl is None:
        return ["неизвестный тип %d-стр" % n]
    exp = set(tpl["pages"])
    missing, extra = sorted(exp - set(pages)), sorted(set(pages) - exp)
    if missing or extra:
        why.append("неполный набор" + (": нет " + ", ".join(missing) if missing else "") + (": лишние " + ", ".join(extra) if extra else ""))
    stubs = [p for p in pages if stats[p]["nwords"] < 60]
    if stubs:
        why.append("контент из заглушек: " + ", ".join(sorted(stubs)))
    if "main" in stats:
        m = stats["main"]
        if m["sec"] == 0 or m["cw"] < 150 or (m["cw"] < MIN_MAIN_WORDS and m["sec"] < 3):
            why.append("главная без текста: %d слов, %d разделов" % (m["cw"], m["sec"]))
    свои = defaultdict(list)
    for p in sorted(pages):
        свои[stats[p]["md5"]].append(p)
    сам = [" = ".join(v) for v in свои.values() if len(v) > 1]
    if сам:
        why.append("копия своей же страницы: " + "; ".join(sorted(сам)))
    dup = []
    for p in sorted(pages):
        h = stats[p]["md5"]
        if h in md5_seen and md5_seen[h][0] != key:
            dup.append("%s = %s/%s" % (p, *md5_seen[h]))
        else:
            md5_seen.setdefault(h, (key, p))
    if dup:
        why.append("контент дублированный (файл в файл): " + "; ".join(dup))
    return why


# ---------------------------------------------------------------- главное ---
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("-o", "--out", required=True, help="папка результата")
    ap.add_argument("--порог", type=int, default=60, help="совпадение в процентах, с которого сайт — дубль (по умолчанию 60)")
    ap.add_argument("--без-копий", action="store_true", help="только списки, без копирования страниц")
    args = ap.parse_args()
    src = Source(args.path)
    os.makedirs(args.out, exist_ok=True)

    sites = []                 # список словарей по сайтам
    page_meta = []             # id страницы -> (индекс сайта, имя страницы)
    sampled = []               # id страницы -> array выборочных хешей
    md5_seen = {}
    total_pages = 0
    for g, s, pages in src.sites():
        n = int(GROUP_RX.match(g).group(1))
        target, drop = CONVERT.get(n, (n, []))
        keep = {p: k for p, k in pages.items() if p not in drop}
        stats = {}
        for p, k in sorted(keep.items()):
            stats[p] = page_stats(src.read(k))
        key = "%d-стр/%s" % (target, s)
        site = {"key": key, "type": "%d-стр" % target, "group": g, "site": s, "pages": keep, "stats": stats,
                "words": sum(v["nwords"] for v in stats.values()),
                "why": structural_reasons(target, keep, stats, md5_seen, key),
                "overlap": 0.0, "partner": "", "page_ids": []}
        idx = len(sites)
        sites.append(site)
        for p in sorted(keep):
            page_meta.append((idx, p))
            sampled.append(stats[p]["sampled"])
            site["page_ids"].append(len(page_meta) - 1)
            stats[p]["sampled"] = None
        total_pages += len(keep)
        if len(sites) % 500 == 0:
            print("прочитано сайтов: %d, страниц: %d" % (len(sites), total_pages), file=sys.stderr)
    print("сайтов: %d, страниц: %d" % (len(sites), total_pages), file=sys.stderr)

    # --- уникальность среди сайтов, прошедших структурный отбор
    alive = [i for i, st in enumerate(sites) if not st["why"]]
    alive_set = set(alive)
    index = defaultdict(list)
    for i in alive:
        for pid in sites[i]["page_ids"]:
            for h in sampled[pid]:
                index[h].append(pid)
    shared = Counter()
    boiler = set()             # шаблонные цепочки: на более чем MAX_DF страницах
    for h, pids in index.items():
        if len(pids) > MAX_DF:
            boiler.add(h)
        elif len(pids) >= 2:
            for a, b in itertools.combinations(pids, 2):
                if page_meta[a][0] != page_meta[b][0]:
                    shared[(a, b) if a < b else (b, a)] += 1
    index = None

    @lru_cache(maxsize=4000)
    def exact(pid):
        """Цепочки страницы в общей выборке (hash & 7 == 0) без шаблонных — одинаково для обеих страниц пары."""
        idx, p = page_meta[pid]
        raw = body_html(src.read(sites[idx]["pages"][p]))
        return frozenset(h for h in shingle_hashes(re.findall(r"\w+", strip_tags(raw))) if h & SAMPLE_MASK == 0 and h not in boiler)

    pairs = []
    for (a, b), n in shared.items():
        if n < MIN_SHARED:
            continue
        A, B = exact(a), exact(b)
        if len(A) < 8 or len(B) < 8:
            continue
        inter = len(A & B)
        cont = inter / min(len(A), len(B))
        if cont >= 0.3:
            pairs.append((cont, a, b))
    shared = None
    for cont, a, b in pairs:
        for x, y in ((a, b), (b, a)):
            st = sites[page_meta[x][0]]
            if cont > st["overlap"]:
                st["overlap"], st["partner"] = cont, "%s (%s.html)" % (sites[page_meta[y][0]]["key"], page_meta[y][1])
    threshold = args.порог / 100
    removed = set()
    for cont, a, b in sorted(pairs, reverse=True):
        if cont < threshold:
            break
        ia, ib = page_meta[a][0], page_meta[b][0]
        if ia in removed or ib in removed:
            continue
        loser, winner = (ia, ib) if (sites[ia]["words"], sites[ia]["key"]) < (sites[ib]["words"], sites[ib]["key"]) else (ib, ia)
        removed.add(loser)
        sites[loser]["why"].append("контент дублированный: совпадение %d %% с %s (%s.html)" % (
            round(cont * 100), sites[winner]["key"], page_meta[a if loser == ib else b][1]))

    # --- выход
    good = [st for st in sites if not st["why"]]
    gone = [st for st in sites if st["why"]]
    with open(os.path.join(args.out, "сайты.tsv"), "w", encoding="utf-8") as f:
        f.write("тип\tсайт\tгруппа\tвердикт\tпричина\tстраниц\tслов\tглавная_слов\tглавная_разделов\tсовпадение_%\tс_кем\n")
        for st in sites:
            m = st["stats"].get("main", {"cw": 0, "sec": 0})
            f.write("\t".join(str(x) for x in [st["type"], st["site"], st["group"], "убран" if st["why"] else "годен",
                    "; ".join(st["why"]), len(st["pages"]), st["words"], m["cw"], m["sec"], round(st["overlap"] * 100), st["partner"]]) + "\n")
    with open(os.path.join(args.out, "годные.txt"), "w", encoding="utf-8") as f:
        f.write("".join(st["key"] + "\n" for st in good))
    reasons = Counter(w.split(":")[0] for st in gone for w in st["why"])
    by_type = defaultdict(lambda: [0, 0])
    for st in sites:
        by_type[st["type"]][0 if not st["why"] else 1] += 1
    lines = ["# Фильтрация: %s" % os.path.basename(args.path.rstrip("/")), "",
             "Сайтов %d, страниц %d. **Годных %d, убрано %d.** Порог совпадения %d %%. Совпадение — доля общих 6-словных цепочек от меньшей страницы, без шаблонных цепочек (виджеты, повторяющиеся более чем на 50 страницах). Без правок: бренды, переменные, ссылки и разметка не смотрелись." % (
                 len(sites), total_pages, len(good), len(gone), args.порог), "",
             "| Тип | Годных | Убрано |", "|---|---:|---:|"]
    for t in sorted(by_type, key=lambda x: int(x.split("-")[0])):
        lines.append("| %s | %d | %d |" % (t, by_type[t][0], by_type[t][1]))
    lines += ["", "## Причины", ""] + ["- %s: %d" % kv for kv in reasons.most_common()]
    top = sorted(((st["overlap"], st) for st in sites if st["overlap"] >= 0.3), key=lambda x: -x[0])[:30]
    if top:
        lines += ["", "## Самые похожие", "", "| Сайт | Совпадение | С кем | Итог |", "|---|---:|---|---|"]
        for cont, st in top:
            lines.append("| %s | %d %% | %s | %s |" % (st["key"], round(cont * 100), st["partner"], "убран" if st["why"] else "годен"))
    lines += ["", "## Убрано", ""]
    for st in gone:
        lines.append("- %s%s — %s" % (st["key"], " (из %s)" % st["group"] if st["group"] != st["type"] else "", "; ".join(st["why"])))
    open(os.path.join(args.out, "сводка.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    if not args.без_копий:
        for st in sites:
            dst = os.path.join(args.out, "убрано" if st["why"] else "годные", st["type"], st["site"])
            os.makedirs(dst, exist_ok=True)
            for p, k in st["pages"].items():
                with open(os.path.join(dst, p + ".html"), "wb") as f:
                    f.write(src.read_bytes(k))
    print("годных %d, убрано %d; результат в %s" % (len(good), len(gone), args.out))


if __name__ == "__main__":
    main()
