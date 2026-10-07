#!/usr/bin/env python3
"""Проверка папки перед замером: какие наборы найдены, сколько страниц, какой бренд.

    python3 proverka.py <папка-с-шаблонами>

Запускать ПЕРВЫМ. Если наборов 0 — структура глубже, чем ожидают скрипты:
посмотрите подсказку в конце вывода.
"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import obshee
from collections import Counter

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    args, opts = obshee.split_args(sys.argv[1:])
    root = args[0]
    if not os.path.isdir(root):
        print(f"Нет такой папки: {root}"); sys.exit(1)
    sets = obshee.sets_from(root, opts)
    print(f"Папка: {os.path.abspath(root)}")
    print(f"Наборов найдено: {len(sets)}\n")
    if not sets:
        print("Страницы не найдены на ожидаемой глубине (корень / +1 / +2 уровня).")
        print("Проверьте, как разложены файлы:")
        for p in sorted(glob.glob(os.path.join(root, "*")))[:10]:
            print("   ", p)
        print("\nЕсли наборы лежат глубже — передайте подпапку напрямую, например:")
        print(f"   python3 -I proverka.py {os.path.join(root,'<подпапка>')}")
        sys.exit(2)
    allpages = Counter()
    print(f"{'набор':34s} {'стр.':>5s}  бренд")
    rows = []
    for p in sets:
        pg = obshee.pages(p)
        names = [os.path.splitext(os.path.basename(f))[0] for f in pg]
        allpages.update(names)
        b = obshee.detect_brand(p)
        rows.append((os.path.basename(p.rstrip("/")), len(pg), b))
    for name, n, b in rows[:40]:
        print(f"{name[:34]:34s} {n:>5d}  {'/'.join(b) if b else '— не опознан, нужен brand.txt'}")
    if len(rows) > 40:
        print(f"... и ещё {len(rows)-40} наборов")
    sizes = [n for _, n, _ in rows]
    print(f"\nСтраниц в наборе: мин {min(sizes)}, медиана {sorted(sizes)[len(sizes)//2]}, макс {max(sizes)}")
    nob = [n for n, _, b in ((r[0], r[1], r[2]) for r in rows) if not b]
    if nob:
        print(f"Бренд не опознан у {len(nob)} наборов — положите в их папки brand.txt")
    print("\nСамые частые типы страниц (для --pages):")
    common = [p for p, c in allpages.most_common(14)]
    for p, c in allpages.most_common(14):
        print(f"   {p:18s} есть в {c} из {len(sets)} наборов")
    full = [p for p, c in allpages.items() if c == len(sets)]
    if full:
        print("\nЕсть во ВСЕХ наборах (можно брать как общий состав):")
        print("   --pages " + ",".join(sorted(full)))

if __name__ == "__main__":
    main()
