"""Общие утилиты набора инструментов: поиск наборов, чтение страниц, опознание бренда."""
import os, re, glob
from bs4 import BeautifulSoup

PAGE_EXT = ("*.html", "*.htm")

BRAND_STOP = {
 "casino","казино","онлайн","online","слоты","слот","игровые","автоматы","бонус","бонусы",
 "официальный","сайт","зеркало","вход","регистрация","играть","игры","россии","рублей",
 "деньги","реальные","лучшие","обзор","скачать","приложение","мобильное","промокод",
 "фриспины","джекпот","подробный","отзывы","новые","главная","личный","кабинет","демо",
 "поддержка","контакты","партнёрам","партнерам","новости","информация","условия","политика",
 "правила","акции","турниры","вопросы","ответы","помощь","каталог","портал","платформа",
 "выплаты","вывод","депозит","лицензия","безопасность","служба","программа","разделы",
 "сегодня","актуальный","рабочее","лучший","топ","гид","как","что","для","все","над",
}

def find_sets(root):
    """Папки-наборы: каталоги, внутри которых лежат html-страницы."""
    out = []
    if any(glob.glob(os.path.join(root, e)) for e in PAGE_EXT):
        return [root]
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d)
        if not os.path.isdir(p) or d.startswith("__") or d.startswith("."):
            continue
        if any(glob.glob(os.path.join(p, e)) for e in PAGE_EXT):
            out.append(p)
        else:  # ещё уровень вложенности
            for d2 in sorted(os.listdir(p)):
                p2 = os.path.join(p, d2)
                if os.path.isdir(p2) and any(glob.glob(os.path.join(p2, e)) for e in PAGE_EXT):
                    out.append(p2)
    return out

def pages(setdir, only=None):
    fs = []
    for e in PAGE_EXT:
        fs += glob.glob(os.path.join(setdir, e))
    fs = sorted(fs)
    if only:
        fs = [f for f in fs if os.path.splitext(os.path.basename(f))[0] in only]
    return fs

def soup_of(path, drop_scripts=True):
    s = BeautifulSoup(open(path, encoding="utf-8", errors="ignore").read(), "lxml")
    if drop_scripts:
        for t in s(["script", "style", "noscript"]):
            t.decompose()
    return s

def visible_text(path):
    s = soup_of(path)
    body = s.body or s
    return body.get_text(" ", strip=True)

def detect_brand(setdir, override=None):
    """Бренд как литерал: 1-2 слова. Возвращает список написаний (латиница + кириллица).

    override — путь к файлу brand.txt в папке набора: по одному написанию на строку.
    """
    from collections import Counter
    bf = os.path.join(setdir, "brand.txt")
    if override:
        return [x.strip() for x in override.split(",") if x.strip()]
    if os.path.exists(bf):
        return [l.strip() for l in open(bf, encoding="utf-8") if l.strip()]
    uni, bi, n = Counter(), Counter(), 0
    CAP = r"[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё]{2,}"
    for f in pages(setdir):
        s = BeautifulSoup(open(f, encoding="utf-8", errors="ignore").read(), "lxml")
        t = s.find("title")
        if not t:
            continue
        n += 1
        txt = t.get_text()
        for w in set(re.findall(CAP, txt)):
            if w.lower() not in BRAND_STOP:
                uni[w] += 1
        for a, b in set(re.findall(r"(" + CAP + r")\s+(" + CAP + r")", txt)):
            if a.lower() not in BRAND_STOP and b.lower() not in BRAND_STOP:
                bi[a + " " + b] += 1
    if not n:
        return []
    thr = max(2, n * 0.3)
    out = [w for w, k in bi.most_common() if k >= thr][:1]          # биграмма-бренд, если есть
    out += [w for w, k in uni.most_common() if k >= thr
            and not any(w in o for o in out)][:2]                   # плюс однословные написания
    if not out and uni:
        out = [uni.most_common(1)[0][0]]
    return out


OPT_ARITY = {"--pages": 1, "--page": 1, "--k": 1, "--labels": 2, "--seq": 0,
             "--only": 1, "--only-file": 1}

def split_args(argv):
    """Разбор аргументов: позиционные отдельно, опции со своими значениями отдельно."""
    pos, opts, i = [], {}, 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            n = OPT_ARITY.get(a, 1)
            opts[a] = argv[i + 1:i + 1 + n]
            i += 1 + n
        else:
            pos.append(a)
            i += 1
    return pos, opts


def sets_from(root, opts=None):
    """find_sets плюс фильтр --only / --only-file (имена папок наборов через запятую)."""
    sets = find_sets(root)
    opts = opts or {}
    names = None
    if "--only" in opts:
        names = {x.strip() for x in opts["--only"][0].split(",") if x.strip()}
    elif "--only-file" in opts:
        names = {l.strip() for l in open(opts["--only-file"][0], encoding="utf-8") if l.strip()
                 and not l.startswith("#")}
    if names is None:
        return sets
    return [p for p in sets if os.path.basename(p) in names]
