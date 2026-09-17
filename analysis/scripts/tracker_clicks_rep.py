#!/usr/bin/env python3
"""Разбор выгрузки кликов трекера: ключ соединения, боты, кампании.

Аудит по странице отвечает на вопросы TRACKER_PREFLIGHT §3 только для первой
страницы — а она отсортирована по времени и потому смещена. Здесь те же числа
по всей выгрузке, и отдельно по нашей кампании: /v1/clicks отдаёт трафик всех
кампаний трекера, фильтр `campaign=` в запросе игнорируется.

Ключ классифицируется по реестру доменов, а не по совпадению с реферером.
На кликах совпадение `subdomain` с хостом реферера — обычное дело: дор
редиректит со своего же сабдомена, и реферером оказывается он сам. Признак
отравления — ключ, которого нет в `domains_flat.txt`.

Отдельно считается **краулерная ловушка**: клики, у которых хвост `exit_path`
состоит из повторов одного сегмента (`/promo/ru/ru/ru/…`). Это не бот и не
человек, а обход бесконечного дерева URL, которое порождает относительная
ссылка на странице дора. Трекер засчитывает каждый шаг как клик, `is_bot` при
этом не срабатывает. Из объёмов такие клики выбрасывать, но числом показывать.

По тому же поводу — правило мануала «один домен держит среднее»: если сабдомен
даёт больше LEAD_MIN кликов кампании, он выносится в лидеры и все доли
показываются ещё раз без него.

    python3 tracker_clicks_rep.py analysis/api/tracker_clicks_<from>_<to>.jsonl
"""
import os, sys, json, collections
from urllib.parse import urlsplit

OURS     = 'dorgen_engine'
TLD      = ('casino', 'team', 'lol', 'buzz')  # зоны, в которых работает сеть
TRAP_RUN = 4        # столько одинаковых сегментов подряд в хвосте пути = ловушка
LEAD_MIN = 0.05     # доля кликов кампании, с которой сабдомен считается лидером
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def host(url):
    if not url:
        return None
    h = (urlsplit(url).hostname or '').lower()
    return h[4:] if h.startswith('www.') else h or None


def is_trap(path):
    """Путь вида `/promo/ru/ru/ru/…` — обход бесконечного дерева URL.

    Берём хвост: если последние TRAP_RUN сегментов одинаковы, это не навигация,
    а рекурсивная ссылка, по которой краулер уходит вглубь. На выгрузке 11–17.09
    таких кликов 199 275, и 99.9% из них на одном сабдомене.
    """
    segs = [x for x in (path or '').split('/') if x]
    return len(segs) >= TRAP_RUN and len(set(segs[-TRAP_RUN:])) == 1


def registry():
    """Домены реестра: сабдомен наш, если его хвост — домен из domains_flat.txt."""
    with open(os.path.join(ROOT, 'domains_flat.txt'), encoding='utf-8') as f:
        return {l.strip().lower() for l in f if l.strip()}


def our_shape(sub):
    """Похож ли ключ на наш сабдомен: `бренд.домен.зона` в наших зонах.

    Нужно там, где реестр молчит. Ключ нашей формы вне реестра — почти всегда
    запуск старше реестра (проверено: 38 из 40 крупнейших таких доменов система
    запусков знает). Ключ чужой формы — либо поисковик, подставленный вместо
    сабдомена, либо чужая сетка.
    """
    p = (sub or '').lower().split('.')
    return len(p) >= 3 and p[-1] in TLD


def is_ours(sub, doms):
    """Сабдомен наш, если любой его хвост — домен реестра.

    Реестр ведётся с 24.08 и полным не является: выборочная проверка через
    /v1/events показала запуски, которых в нём нет, а система запусков их знает.
    Поэтому False означает «не подтверждён реестром», а не «точно чужой».
    """
    p = (sub or '').lower().split('.')
    return any('.'.join(p[i:]) in doms for i in range(1, len(p) - 1))


def pct(a, b):
    return f"{100.0 * a / b:.2f}%" if b else "—"


def main(path):
    doms = registry()
    camp = collections.Counter()
    refs = collections.Counter()
    st = collections.defaultdict(collections.Counter)   # кампания -> счётчики
    days = collections.Counter()
    poisoned_ex = collections.Counter()
    unknown_ex = collections.Counter()
    subs = collections.defaultdict(set)
    sub_clicks = collections.Counter()      # только наша кампания: клики на сабдомен
    sub_bots = collections.Counter()
    sub_traps = collections.Counter()
    trap_paths = collections.Counter()

    n = 0
    with open(path, encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            n += 1
            c = r.get('campaign') or '(нет)'
            camp[c] += 1
            s = (r.get('subdomain') or '').lower()
            h = host(r.get('referer'))
            k = st[c]
            k['всего'] += 1
            if r.get('is_bot'):
                k['боты'] += 1
            if not s:
                k['без ключа'] += 1
            else:
                subs[c].add(s)
                if is_ours(s, doms):
                    k['в реестре'] += 1
                    # реферер — сам дор: нормально, а не отравление
                    k['самореферер' if s == h else 'внешний реферер'] += 1
                elif our_shape(s):
                    k['наша форма, вне реестра'] += 1
                    if c == OURS:
                        unknown_ex[s] += 1
                else:
                    k['чужая форма'] += 1
                    k['из них взят из реферера' if s == h else 'из них чужая сетка'] += 1
                    if c == OURS:
                        poisoned_ex[s] += 1
            if not r.get('referer'):
                k['без реферера'] += 1
            elif 'yandex' in (h or '') or h in ('ya.ru', 'dzen.ru'):
                k['яндекс-реферер'] += 1
            if r.get('landing_path'):
                k['landing_path'] += 1
            trap = is_trap(r.get('exit_path'))
            if trap:
                k['краулерная ловушка'] += 1
            if c == OURS:
                days[(r.get('at') or '')[:10]] += 1
                refs[h or '(пусто)'] += 1
                sub_clicks[s or '(пусто)'] += 1
                if r.get('is_bot'):
                    sub_bots[s or '(пусто)'] += 1
                if trap:
                    sub_traps[s or '(пусто)'] += 1
                    trap_paths[(r.get('exit_path') or '')[:60]] += 1

    print(f"ВСЕГО КЛИКОВ В ВЫГРУЗКЕ: {n}\n")
    print("КАМПАНИИ (клики трекера, не только наши):")
    for c, v in camp.most_common():
        print(f"  {c:<22} {v:>8}  {pct(v, n)}")

    for c in [OURS] + [x for x in camp if x != OURS]:
        k = st[c]
        t = k['всего']
        if not t:
            continue
        mark = '  <-- НАША' if c == OURS else ''
        print(f"\n{'='*60}\n{c}{mark}: {t} кликов, {len(subs[c])} уникальных ключей")
        for name in ('без ключа', 'в реестре', 'самореферер', 'внешний реферер',
                     'наша форма, вне реестра', 'чужая форма',
                     'из них взят из реферера', 'из них чужая сетка', 'боты',
                     'краулерная ловушка',
                     'яндекс-реферер', 'без реферера', 'landing_path'):
            print(f"  {name:<18} {k[name]:>8}  {pct(k[name], t)}")
        if c != OURS:
            break   # чужие кампании подробно не нужны, хватает верхней таблицы

    t = st[OURS]['всего']
    lead = [(x, v) for x, v in sub_clicks.most_common() if v >= LEAD_MIN * t]
    print(f"\n{'='*60}\nКОНЦЕНТРАЦИЯ {OURS}")
    half, k2 = 0, 0
    for _, v in sub_clicks.most_common():
        half += v; k2 += 1
        if half >= t / 2:
            break
    print(f"  половину кликов дают {k2} сабдоменов из {len(sub_clicks)}")
    print("  топ-5:")
    for x, v in sub_clicks.most_common(5):
        print(f"    {x:<38} {v:>8}  {pct(v, t)}  боты {pct(sub_bots[x], v)}"
              f"  ловушка {pct(sub_traps[x], v)}")

    if lead:
        # правило мануала: один домен держит среднее — показать и без него
        drop = {x for x, _ in lead}
        t2 = t - sum(v for _, v in lead)
        b2 = st[OURS]['боты'] - sum(sub_bots[x] for x in drop)
        p2 = st[OURS]['краулерная ловушка'] - sum(sub_traps[x] for x in drop)
        print(f"\n  ЛИДЕРЫ (≥{LEAD_MIN:.0%} кликов кампании) — доли пересчитаны без них:")
        for x, v in lead:
            print(f"    {x:<38} {v:>8}  {pct(v, t)}")
        print(f"    {'клики':<38} {t:>8} -> {t2}")
        print(f"    {'боты':<38} {pct(st[OURS]['боты'], t):>8} -> {pct(b2, t2)}")
        print(f"    {'краулерная ловушка':<38} {pct(st[OURS]['краулерная ловушка'], t):>8} -> {pct(p2, t2)}")
    else:
        print(f"  сабдоменов с долей ≥{LEAD_MIN:.0%} нет — пересчитывать без лидера нечего")

    if trap_paths:
        print(f"\nКРАУЛЕРНАЯ ЛОВУШКА {OURS}: {st[OURS]['краулерная ловушка']} кликов "
              f"на {len(sub_traps)} сабдоменах")
        for x, v in sub_traps.most_common(5):
            print(f"    {x:<38} {v:>8}  {pct(v, sub_clicks[x])} кликов этого сабдомена")
        print("  пути:")
        for x, v in trap_paths.most_common(3):
            print(f"    {x:<60} {v:>8}")

    print(f"\nКЛИКИ {OURS} ПО ДНЯМ:")
    for d, v in sorted(days.items()):
        print(f"  {d}  {v:>7}")

    print(f"\nТОП РЕФЕРЕРОВ {OURS}:")
    for h, v in refs.most_common(15):
        print(f"  {h:<40} {v:>7}  {pct(v, camp[OURS])}")

    if poisoned_ex:
        print(f"\nКЛЮЧИ {OURS} ЧУЖОЙ ФОРМЫ — отравление и чужие сетки, топ:")
        for s, v in poisoned_ex.most_common(15):
            print(f"  {s:<40} {v:>7}")
    if unknown_ex:
        print(f"\nКЛЮЧИ {OURS} НАШЕЙ ФОРМЫ ВНЕ РЕЕСТРА, топ (уникальных {len(unknown_ex)}):")
        for s, v in unknown_ex.most_common(15):
            print(f"  {s:<40} {v:>7}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
