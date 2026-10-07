#!/usr/bin/env python3
"""Пересечение наборов по 6-словным шинглам (бренд и числа нейтрализованы).

    python3 shingly.py <папка-наборов> [--pages main,slots,...] [--k 6]
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import obshee

W = re.compile(r"[а-яёa-z0-9]+")

def norm_text(path, brands):
    t = obshee.visible_text(path)
    for b in sorted(brands, key=len, reverse=True):
        t = re.sub(re.escape(b), "BRAND", t, flags=re.I)
    t = re.sub(r"\d+", "N", t)
    return W.findall(t.lower())

def shingles(words, k):
    return {" ".join(words[i:i+k]) for i in range(len(words)-k+1)}

def main():
    args, opts = obshee.split_args(sys.argv[1:])
    only = set(opts["--pages"][0].split(",")) if "--pages" in opts else None
    k = int(opts["--k"][0]) if "--k" in opts else 6
    if not args: print(__doc__); sys.exit(1)
    SH = {}
    for p in obshee.sets_from(args[0], opts):
        brands = obshee.detect_brand(p)
        S = set()
        for f in obshee.pages(p, only):
            S |= shingles(norm_text(f, brands), k)
        SH[os.path.basename(p.rstrip("/"))] = S
    names = list(SH)
    print(f"Доля общих {k}-словных шинглов (Жаккар, %)\n")
    print("| |" + "|".join(names) + "|")
    print("|---|" + "---|" * len(names))
    for a in names:
        row = f"| **{a}** |"
        for b in names:
            u = SH[a] | SH[b]
            row += f" {len(SH[a]&SH[b])/len(u)*100:.1f} |" if u else " — |"
        print(row)

if __name__ == "__main__":
    main()
