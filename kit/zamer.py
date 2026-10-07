#!/usr/bin/env python3
"""Замер шаблона: медиана, полоса и CV по наборам.

    python3 zamer.py <папка-наборов> [<вторая-папка> --labels наши их] [--pages main,slots,...]

Единица — НАБОР (папка со страницами). Показатель сначала считается внутри набора,
потом по наборам берётся медиана, полоса (min–max) и CV = σ/среднее.
CV требует минимум 2 набора на сторону; при одном выводится n/a.
"""
import sys, os, re, statistics as st
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import obshee

SENT = re.compile(r"[.!?]+")
WORD = re.compile(r"[А-Яа-яЁёA-Za-z0-9\-]+")
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")
KEYS = {
 "казино":r"казино","слот":r"слот","бонус":r"бонус","джекпот":r"джекпот","зеркало":r"зеркал",
 "промокод":r"промокод","регистрация":r"регистрац","вход":r"\bвход","фриспин":r"фриспин|free ?spin",
 "вейджер":r"вейджер|отыгрыш","лицензия":r"лицензи","кэшбэк":r"кэшб[эе]к|кешб[эе]к",
 "депозит":r"депозит","вывод":r"вывод","поддержка":r"поддержк","турнир":r"турнир",
 "RTP":r"\bRTP\b|отдач","провайдер":r"провайдер|студи","приложение":r"приложени",
 "верификация":r"верификац","лимит":r"лимит","кабинет":r"кабинет",
}
TY = r"\bты\b|\bтебе\b|\bтебя\b|\bтвой\b|\bтвоя\b|\bтвои\b"
VY = r"\bвы\b|\bвам\b|\bвас\b|\bваш\b|\bваша\b|\bваши\b"
POVEL = r"\b\w+(?:ай|яй|ей|уй|и)те\b|\bскачай\b|\bиграй\b|\bзаходи\b|\bзабирай\b|\bжми\b"

def med(x): return round(st.median(x), 2) if x else 0.0
def cv(x):
    if len(x) < 2: return None
    m = st.mean(x)
    return round(st.pstdev(x) / m, 2) if m else 0.0

def measure(setdir, only=None):
    files = obshee.pages(setdir, only)
    if not files: return None
    brands = obshee.detect_brand(setdir)
    br = re.compile("|".join(re.escape(b) for b in brands), re.I) if brands else None
    n = len(files)
    W = sents = links = strong = em = emo = btn = imgs = faq = tbl = 0
    divs = spans = classes = styles = inputs = selfl = 0
    paras, h2s, lists, anchors, hrefs = [], [], [], [], set()
    items = 0
    h3n = brand_cnt = brand_lat = h2_brand = digits = 0
    pcts, sums, rtps, names = set(), set(), set(), set()
    ty = vy = povel = 0
    keyhits = Counter()
    for f in files:
        slug = os.path.splitext(os.path.basename(f))[0]
        s = obshee.soup_of(f)
        body = s.body or s
        txt = body.get_text(" ", strip=True)
        W += len(WORD.findall(txt)); sents += len(SENT.findall(txt))
        for p in body.find_all("p"):
            w = len(WORD.findall(p.get_text(" ", strip=True)))
            if w: paras.append(w)
        for h in body.find_all("h2"):
            t = h.get_text(" ", strip=True); h2s.append(t)
            if br and br.search(t): h2_brand += 1
        h3n += len(body.find_all("h3"))
        for l in body.find_all(["ul", "ol"]):
            li = l.find_all("li", recursive=False)
            if li:
                lists.append(len(li))
                items += sum(len(WORD.findall(x.get_text(" ", strip=True))) for x in li)
        for t in body.find_all("table"): tbl += 1
        for a in body.find_all("a"):
            links += 1; anchors.append(a.get_text(" ", strip=True))
            h = a.get("href") or ""; hrefs.add(h)
            if re.search(r"/" + re.escape(slug) + r"/?($|[?#])", h): selfl += 1
        strong += len(body.find_all(["strong", "b"])); em += len(body.find_all(["em", "i"]))
        emo += len(EMOJI.findall(txt)); btn += len(body.find_all("button"))
        imgs += len(body.find_all("img")); faq += len(body.find_all(["summary", "details"]))
        divs += len(body.find_all("div")); spans += len(body.find_all("span"))
        classes += len(body.find_all(class_=True)); styles += len(body.find_all(style=True))
        inputs += len(body.find_all(["input", "select", "textarea"]))
        digits += len(re.findall(r"\d", txt))
        pcts |= set(re.findall(r"\d{1,3}(?:[.,]\d+)?%", txt))
        sums |= set(re.findall(r"\d[\d\s  ]{2,}(?:₽|руб|RUB|EUR|USD)", txt))
        rtps |= set(re.findall(r"\b9\d[.,]\d{1,2}", txt))
        names |= set(re.findall(r"\b([А-ЯЁ][а-яё]{2,})(?:,?\s+\d{2}\s*(?:лет|год))", txt))
        ty += len(re.findall(TY, txt, re.I)); vy += len(re.findall(VY, txt, re.I))
        povel += len(re.findall(POVEL, txt, re.I))
        if br:
            hits = br.findall(txt); brand_cnt += len(hits)
            brand_lat += sum(1 for h in hits if re.match(r"[A-Za-z]", h))
        for k, rx in KEYS.items(): keyhits[k] += len(re.findall(rx, txt, re.I))
    k1000 = lambda v: round(v / W * 1000, 2) if W else 0.0
    per = lambda v: round(v / n, 2)
    R = {
      "_имя": os.path.basename(setdir.rstrip("/")), "_бренд": brands,
      "страниц": n, "слов в наборе": W, "слов на страницу": per(W),
      "абзацев на страницу": per(len(paras)), "слов в абзаце": med(paras),
      "предложений на 100 слов": round(sents / W * 100, 2) if W else 0,
      "коротких абзацев <25 слов, %": round(sum(1 for p in paras if p < 25) / len(paras) * 100, 1) if paras else 0,
      "σ длины абзаца": round(st.pstdev(paras), 1) if len(paras) > 1 else 0,
      "h2 на страницу": per(len(h2s)), "h3 на h2": round(h3n / len(h2s), 2) if h2s else 0,
      "длина h2, знаков": med([len(x) for x in h2s]),
      "h2 с двоеточием, %": round(sum(1 for x in h2s if ":" in x) / len(h2s) * 100, 1) if h2s else 0,
      "h2 с тире, %": round(sum(1 for x in h2s if re.search(r"[-–—‑]", x)) / len(h2s) * 100, 1) if h2s else 0,
      "h2 с брендом, %": round(h2_brand / len(h2s) * 100, 1) if h2s else 0,
      "списков на страницу": per(len(lists)), "пунктов в списке": med(lists),
      "слов в пункте": round(items / sum(lists), 1) if sum(lists) else 0,
      "таблиц на набор": tbl,
      "ссылок на страницу": per(links), "ссылок на 1000 слов": k1000(links),
      "уникальных адресов": len(hrefs),
      "уникальных анкоров, %": round(len(set(anchors)) / len(anchors) * 100, 1) if anchors else 0,
      "ссылок на себя": selfl,
      "бренд на 1000 слов": k1000(brand_cnt),
      "бренд латиницей, %": round(brand_lat / brand_cnt * 100, 1) if brand_cnt else 0,
      "написаний бренда": len(brands),
      "цифр на 100 слов": round(digits / W * 100, 2) if W else 0,
      "разных процентов": len(pcts), "разных сумм": len(sums), "разных RTP": len(rtps),
      "имён-героев": len(names),
      "ты-форм на 1000": k1000(ty), "вы-форм на 1000": k1000(vy),
      "доля вы, %": round(vy / (ty + vy) * 100, 1) if (ty + vy) else 0,
      "повелительных на 1000": k1000(povel),
      "strong на 1000 слов": k1000(strong), "em на 1000 слов": k1000(em),
      "эмодзи на страницу": per(emo), "кнопок на набор": btn,
      "картинок на страницу": per(imgs), "FAQ-меток на набор": faq,
      "div на страницу": per(divs), "span на страницу": per(spans),
      "class на страницу": per(classes), "инлайн style= на страницу": per(styles),
      "полей ввода на набор": inputs,
    }
    for k in KEYS: R[f"кл. «{k}» на 1000"] = k1000(keyhits[k])
    return R

def main():
    args, opts = obshee.split_args(sys.argv[1:])
    only = set(opts["--pages"][0].split(",")) if "--pages" in opts else None
    labels = opts.get("--labels", ["A", "B"])
    if len(labels) < 2: labels = labels + ["B"]
    if not args:
        print(__doc__); sys.exit(1)
    groups = []
    for root, lab in zip(args, labels):
        ms = [m for m in (measure(p, only) for p in obshee.sets_from(root, opts)) if m]
        groups.append((lab, ms))
        print(f"{lab}: наборов {len(ms)} — " + ", ".join(f"{m['_имя']}({'/'.join(m['_бренд']) or '?'})" for m in ms), file=sys.stderr)
    keys = [k for k in groups[0][1][0] if not k.startswith("_")]
    hdr = "| параметр |" + "".join(f" {l}: медиана | {l}: полоса | {l} CV |" for l, _ in groups)
    print(hdr); print("|---|" + "---|" * (3 * len(groups)))
    f = lambda v: f"{v:g}" if isinstance(v, float) else str(v)
    for k in keys:
        row = f"| {k} |"
        for _, ms in groups:
            v = [m[k] for m in ms if isinstance(m[k], (int, float))]
            if not v: row += " — | — | — |"; continue
            c = cv(v)
            row += f" {f(med(v))} | {f(min(v))}–{f(max(v))} | {c if c is not None else 'n/a'} |"
        print(row)

if __name__ == "__main__":
    main()
