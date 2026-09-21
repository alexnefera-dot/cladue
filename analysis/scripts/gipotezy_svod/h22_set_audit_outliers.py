#!/usr/bin/env python3
"""
Гипотеза №22. Отдельные наборы контента систематически выбиваются из базы
своего дня и зоны сверх обычного разброса наборов.

Названы: Generator_NNNNNN_styled_img (346353…392396) и Generator_A_staryy_stil /
Generator_B_novyy_bez_img — примерно 0,45 от выхода соседей (мёртвая ветка
генератора, а не styled_img как оформление); script_yandex_12page — ≈0,7 выхода и
≈0,4 регистраций; Content_script_12page_08.09 — ≈1,4 выхода и ≈2,4 регистраций.

Что считаем.
  Единица — домен. Выход = «вышли за 3 суток» / «сайтов в окне». Деньги —
  «регистраций в окне 3 суток». Страта — день запуска × зона (team / lol /
  casino / buzz / прочие).
  Фильтры: окно закрыто = да; дней ≠ 1; без выбросов 3615.team и 3286.team;
  «КОНТЕНТ НЕ ЗАПИСАН» исключён и из наборов, и из базы (это не набор, а
  отсутствие записи); число исключённых строк печатается.

Как считаем.
  1. Общий каркас (защита от выбора худших задним числом). Для каждого набора
     с ≥5 доменами в страте при ≥5 чужих доменах в той же страте:
       E = доля выхода остальных доменов страты × сайтов набора,
       O = вышли за 3 суток, O/E.
     Перестановочный тест на весь набор наборов: 10 000 раз перемешиваем метку
     набора между доменами внутри страты (домен уносит с собой свои сайты и
     свои выходы), пересчитываем O/E каждого набора. Из этого: 95%-коридор
     каждого набора, двусторонний p, распределение минимального и
     максимального O/E по наборам, сколько наборов выходит за коридор при
     случайности (против наблюдаемого числа), поправка Бенджамини–Хохберга.
  2. Контраст (а): наборы Generator_* от 04–06.09 против не-Generator соседей
     тех же страт (так считал автор гипотезы): суммарный O/E, p по
     перестановке метки «Generator» внутри страты (10 000). Контроли —
     styled_img-наборы тех же страт (nabory…_styled_img, NEW20/NEW21…) и
     Generator_11page_* в страте 25.08 .team. Деньги — точный биномиальный
     дележ регистраций страты пропорционально сайтам, свёртка по стратам.
  3. Контраст (б): Content_script_12page_08.09 (08.09 .lol и .team) и
     script_yandex_12page (11.09 .casino/.lol/.team; 12.09 .casino отдельно):
     O/E выхода с перестановкой метки набора внутри страты, регистрации —
     тот же биномиальный дележ.
  random.seed(1). Только стандартная библиотека.
"""
import collections
import csv
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h22_set_audit_outliers.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
NPERM = 10000
MIN_SET = 5      # доменов в наборе внутри страты
MIN_OTHERS = 5   # чужих доменов в страте
GEN_DAYS = ('2026-09-04', '2026-09-05', '2026-09-06')
CONTENT_SCRIPT = 'Content_script_12page_08.09'
SCRIPT_YANDEX = 'script_yandex_12page'


class Tee:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def __call__(self, *a):
        s = ' '.join(str(x) for x in a)
        print(s)
        self.f.write(s + '\n')

    def close(self):
        self.f.close()


def num(s, default=0.0):
    s = (s or '').strip()
    return float(s) if s else default


def zone_group(z):
    return z if z in ('team', 'lol', 'casino', 'buzz') else 'прочие'


def dm(day):
    return day[8:10] + '.' + day[5:7]


def skey(key):
    return dm(key[0]) + ' .' + key[1]


def ratio(a, b):
    return a / b if b else float('nan')


def fmt(x, nd=2):
    return 'н/д' if x != x else f'{x:.{nd}f}'


def perm_p(null, obs, side):
    """p = (число перестановок не менее крайних + 1) / (N + 1)."""
    if side == 'low':
        k = sum(1 for v in null if v <= obs)
    else:
        k = sum(1 for v in null if v >= obs)
    return (k + 1) / (len(null) + 1)


def quantiles(vals, lo=0.025, hi=0.975):
    s = sorted(vals)
    n = len(s)
    return s[max(0, min(n - 1, int(round(lo * (n - 1)))))], s[max(0, min(n - 1, int(round(hi * (n - 1)))))]


def binom_pmf(n, p):
    out = []
    for k in range(n + 1):
        out.append(math.comb(n, k) * p ** k * (1 - p) ** (n - k))
    return out


def convolve_binomials(parts):
    """parts: список (n_s, p_s). Возвращает распределение суммы независимых биномиальных."""
    dist = [1.0]
    for n, p in parts:
        pm = binom_pmf(n, p)
        new = [0.0] * (len(dist) + n)
        for i, a in enumerate(dist):
            if a == 0:
                continue
            for k, b in enumerate(pm):
                new[i + k] += a * b
        dist = new
    return dist


def bh_reject(pvals, q):
    """Бенджамини–Хохберг: возвращает множество индексов отвергнутых гипотез."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    kmax = 0
    for rank, i in enumerate(order, 1):
        if pvals[i] <= q * rank / m:
            kmax = rank
    return set(order[:kmax])


def main():
    random.seed(1)
    log = Tee(OUT)
    with open(SRC, encoding='utf-8') as f:
        raw = list(csv.DictReader(f))

    rows, nz_rows = [], []
    excl = collections.Counter()
    for r in raw:
        if r['домен'] in OUTLIERS:
            excl['выбросы 3615.team / 3286.team'] += 1
            continue
        if r['окно закрыто'] != 'да':
            excl['окно не закрыто'] += 1
            continue
        if r['дней'] == '1':
            excl['дней = 1 (день 2 ещё не наступил)'] += 1
            continue
        rec = dict(dom=r['домен'], day=r['день запуска'], zone=zone_group(r['зона']),
                   set=r['набор контента'], sites=num(r['сайтов в окне']),
                   out=num(r['вышли за 3 суток']), reg=num(r['регистраций в окне 3 суток']),
                   fd=num(r['ФД в окне 3 суток']))
        if rec['set'] == NOCONTENT:
            excl['КОНТЕНТ НЕ ЗАПИСАН'] += 1
            nz_rows.append(rec)
            continue
        rows.append(rec)

    log('ГИПОТЕЗА №22. Наборы, которые выбиваются из базы своего дня и зоны')
    log('=' * 78)
    log(f'Строк в своде: {len(raw)}. Исключено:')
    for k, v in excl.items():
        log(f'  {k}: {v}')
    log(f'Осталось доменов: {len(rows)}, сайтов: {sum(r["sites"] for r in rows):.0f}, '
        f'регистраций в окне: {sum(r["reg"] for r in rows):.0f}')
    log('Страта = день запуска × зона (team / lol / casino / buzz / прочие).')
    log('Выход = вышли за 3 суток / сайтов в окне. О/E: O = вышли, E = доля выхода '
        'остальных доменов страты × сайтов набора.')
    log('«КОНТЕНТ НЕ ЗАПИСАН» исключён и из наборов, и из базы страт (это касается 13 доменов 04.09 .team '
        'и 15 доменов 04.09 .lol — ниже есть проверка чувствительности с ними).')

    strata = collections.defaultdict(list)
    for i, r in enumerate(rows):
        strata[(r['day'], r['zone'])].append(i)

    # ------------------------------------------------------------------
    # 1. Общий каркас: все наборы с >=5 доменами при >=5 чужих в страте
    # ------------------------------------------------------------------
    log('\n' + '=' * 78)
    log('1. ОБЩИЙ КАРКАС: КАЖДЫЙ НАБОР ПРОТИВ ОСТАЛЬНЫХ ДОМЕНОВ СВОЕЙ СТРАТЫ')
    log('=' * 78)
    log(f'Берём наборы с ≥{MIN_SET} доменами в страте при ≥{MIN_OTHERS} чужих доменах той же страты.')
    log(f'Перестановок: {NPERM}, метка набора перемешивается между доменами внутри страты.')

    sets_in = {}   # key -> [(set, count)] fixed order
    qual = []      # (key, set)
    for key in sorted(strata):
        idx = strata[key]
        cnt = collections.Counter(rows[i]['set'] for i in idx)
        lst = [(s, c) for s, c in sorted(cnt.items()) if c >= MIN_SET and len(idx) - c >= MIN_OTHERS]
        if lst:
            sets_in[key] = lst
            qual.extend((key, s) for s, _ in lst)
    log(f'Наборов в проверке: {len(qual)} в {len(sets_in)} стратах.')

    obs = {}
    for key, s in qual:
        idx = strata[key]
        o = sum(rows[i]['out'] for i in idx if rows[i]['set'] == s)
        st = sum(rows[i]['sites'] for i in idx if rows[i]['set'] == s)
        rg = sum(rows[i]['reg'] for i in idx if rows[i]['set'] == s)
        nd = sum(1 for i in idx if rows[i]['set'] == s)
        to = sum(rows[i]['out'] for i in idx)
        ts = sum(rows[i]['sites'] for i in idx)
        base = ratio(to - o, ts - st)
        e = base * st
        obs[(key, s)] = dict(n=nd, sites=st, out=o, reg=rg, rate=ratio(o, st), base=base, e=e,
                             oe=ratio(o, e), others=len(idx) - nd)

    null = {q: [] for q in qual}
    for _ in range(NPERM):
        for key, lst in sets_in.items():
            idx = strata[key][:]
            random.shuffle(idx)
            to = sum(rows[i]['out'] for i in idx)
            ts = sum(rows[i]['sites'] for i in idx)
            pos = 0
            for s, c in lst:
                block = idx[pos:pos + c]
                pos += c
                o = sum(rows[i]['out'] for i in block)
                st = sum(rows[i]['sites'] for i in block)
                e = ratio(to - o, ts - st) * st
                null[(key, s)].append(o / e if e > 0 else float('nan'))

    stats = {}
    for q in qual:
        nv = null[q]
        ob = obs[q]['oe']
        lo, hi = quantiles(nv)
        p_low = perm_p(nv, ob, 'low')
        p_high = perm_p(nv, ob, 'high')
        p2 = min(1.0, 2 * min(p_low, p_high))
        stats[q] = dict(lo=lo, hi=hi, p_low=p_low, p_high=p_high, p2=p2,
                        outside=(ob < lo or ob > hi))

    # семейный тест: число наборов вне коридора, минимум и максимум O/E
    n_out_null = []
    min_null, max_null = [], []
    for j in range(NPERM):
        c = 0
        mn, mx = float('inf'), float('-inf')
        for q in qual:
            v = null[q][j]
            if v != v:
                continue
            if v < stats[q]['lo'] or v > stats[q]['hi']:
                c += 1
            mn = min(mn, v)
            mx = max(mx, v)
        n_out_null.append(c)
        min_null.append(mn)
        max_null.append(mx)
    n_out_obs = sum(1 for q in qual if stats[q]['outside'])
    n_low_obs = sum(1 for q in qual if obs[q]['oe'] < stats[q]['lo'])
    n_high_obs = sum(1 for q in qual if obs[q]['oe'] > stats[q]['hi'])
    obs_min_q = min(qual, key=lambda q: obs[q]['oe'])
    obs_max_q = max(qual, key=lambda q: obs[q]['oe'])
    pvals = [stats[q]['p2'] for q in qual]
    bh05 = bh_reject(pvals, 0.05)
    bh10 = bh_reject(pvals, 0.10)

    named = set()
    for key, s in qual:
        if (s.startswith('Generator_') and key[0] in GEN_DAYS) or s in (CONTENT_SCRIPT, SCRIPT_YANDEX):
            named.add((key, s))

    log('\nТаблица всех наборов (по возрастанию O/E). Коридор — 95% перестановочный интервал O/E '
        'для этого набора при случайной метке; p — двусторонний перестановочный; '
        'BH — прошёл поправку Бенджамини–Хохберга (q=0,05 / q=0,10); ◄ — набор, названный в гипотезе.')
    hdr = f'{"страта":<15}{"набор":<40}{"дом":>4}{"сайтов":>7}{"вышли":>6}{"выход%":>8}{"база%":>7}' \
          f'{"O/E":>6}  {"коридор":<12}{"p":>7}  {"вне":<4}{"BH":<6}'
    log(hdr)
    log('-' * len(hdr))
    order = sorted(qual, key=lambda q: obs[q]['oe'])
    for rank, q in enumerate(order):
        key, s = q
        ob, stt = obs[q], stats[q]
        flag = ('ниже' if ob['oe'] < stt['lo'] else 'выше') if stt['outside'] else ''
        bh = ('0,05' if rank_in(bh05, qual, q) else ('0,10' if rank_in(bh10, qual, q) else ''))
        mark = ' ◄' if q in named else ''
        log(f'{skey(key):<15}{s[:39]:<40}{ob["n"]:>4}{ob["sites"]:>7.0f}{ob["out"]:>6.0f}'
            f'{ob["rate"] * 100:>8.1f}{ob["base"] * 100:>7.1f}{ob["oe"]:>6.2f}  '
            f'{fmt(stt["lo"]) + "–" + fmt(stt["hi"]):<12}{stt["p2"]:>7.4f}  {flag:<4}{bh:<6}{mark}')

    log('\nСемейный итог (все наборы разом):')
    exp_out = sum(n_out_null) / NPERM
    q95 = sorted(n_out_null)[int(round(0.95 * (NPERM - 1)))]
    log(f'  Наборов вне своего 95%-коридора: {n_out_obs} из {len(qual)} '
        f'(ниже коридора {n_low_obs}, выше {n_high_obs}); при случайности в среднем {exp_out:.1f}, '
        f'95-й процентиль {q95}; P(случайно ≥ {n_out_obs}) = {perm_p(n_out_null, n_out_obs, "high"):.4f}.')
    mn_lo, mn_hi = quantiles(min_null)
    mx_lo, mx_hi = quantiles(max_null)
    log(f'  Минимальный O/E: {obs[obs_min_q]["oe"]:.2f} ({skey(obs_min_q[0])} {obs_min_q[1]}); '
        f'при случайности минимум по наборам лежит в {mn_lo:.2f}–{mn_hi:.2f}, '
        f'P(случайный минимум ≤ наблюдённого) = {perm_p(min_null, obs[obs_min_q]["oe"], "low"):.4f}.')
    log(f'  Максимальный O/E: {obs[obs_max_q]["oe"]:.2f} ({skey(obs_max_q[0])} {obs_max_q[1]}); '
        f'при случайности максимум лежит в {mx_lo:.2f}–{mx_hi:.2f}, '
        f'P(случайный максимум ≥ наблюдённого) = {perm_p(max_null, obs[obs_max_q]["oe"], "high"):.4f}.')
    log(f'  Поправка Бенджамини–Хохберга: при q=0,05 остаются {len(bh05)} наборов, при q=0,10 — {len(bh10)}.')
    for lab, sel in (('q=0,05', bh05), ('q=0,10', bh10)):
        names = [f'{skey(qual[i][0])} {qual[i][1]} ({obs[qual[i]]["oe"]:.2f})'
                 for i in sorted(sel, key=lambda i: obs[qual[i]]['oe'])]
        log(f'    {lab}: ' + ('; '.join(names) if names else '—'))
    log('  Из названных в гипотезе наборов:')
    for q in sorted(named, key=lambda q: obs[q]['oe']):
        stt = stats[q]
        log(f'    {skey(q[0])} {q[1]}: O/E {obs[q]["oe"]:.2f}, коридор {stt["lo"]:.2f}–{stt["hi"]:.2f}, '
            f'p={stt["p2"]:.4f}, {"ВНЕ коридора" if stt["outside"] else "внутри коридора"}'
            f'{", BH 0,05" if rank_in(bh05, qual, q) else (", BH 0,10" if rank_in(bh10, qual, q) else "")}')
    log('  Оговорка: коридоры и счёт «вне коридора» взяты из одних и тех же перестановок; '
        'при 10 000 перестановках смещение ничтожно.')

    # ------------------------------------------------------------------
    # 2. Контраст (а): Generator_* 04–06.09 против не-Generator соседей
    # ------------------------------------------------------------------
    log('\n' + '=' * 78)
    log('2. КОНТРАСТ (а): НАБОРЫ Generator_* ОТ 04–06.09 ПРОТИВ НЕ-Generator СОСЕДЕЙ')
    log('=' * 78)

    def is_gen(r):
        return r['set'].startswith('Generator_') and r['day'] in GEN_DAYS

    gen_keys = sorted({(r['day'], r['zone']) for r in rows if is_gen(r)})
    log('Страты с Generator: ' + ', '.join(skey(k) for k in gen_keys))
    log('База — все не-Generator домены той же страты (без «КОНТЕНТ НЕ ЗАПИСАН»).')

    def group_oe(keys, pick, sens_extra=None):
        """Суммарный O/E группы pick(row) против остальных доменов тех же страт."""
        O = E = 0.0
        parts = []
        for key in keys:
            idx = strata[key]
            g = [rows[i] for i in idx if pick(rows[i])]
            o = [rows[i] for i in idx if not pick(rows[i])]
            if sens_extra:
                o = o + [r for r in sens_extra if (r['day'], r['zone']) == key]
            go = sum(r['out'] for r in g)
            gs = sum(r['sites'] for r in g)
            oo = sum(r['out'] for r in o)
            os_ = sum(r['sites'] for r in o)
            e = ratio(oo, os_) * gs
            O += go
            E += e
            parts.append((key, len(g), gs, go, len(o), os_, oo, e))
        return O, E, parts

    def group_perm(keys, pick, side):
        """Перестановка метки группы внутри каждой страты; суммарный O/E."""
        pre = []
        for key in keys:
            idx = strata[key]
            ng = sum(1 for i in idx if pick(rows[i]))
            to = sum(rows[i]['out'] for i in idx)
            ts = sum(rows[i]['sites'] for i in idx)
            pre.append((idx[:], ng, to, ts))
        vals = []
        for _ in range(NPERM):
            O = E = 0.0
            for idx, ng, to, ts in pre:
                random.shuffle(idx)
                block = idx[:ng]
                go = sum(rows[i]['out'] for i in block)
                gs = sum(rows[i]['sites'] for i in block)
                O += go
                E += ratio(to - go, ts - gs) * gs
            vals.append(ratio(O, E))
        return vals

    def reg_split(keys, pick):
        """Биномиальный дележ регистраций страты пропорционально сайтам; свёртка по стратам."""
        parts, obs_r, lines = [], 0.0, []
        for key in keys:
            idx = strata[key]
            g = [rows[i] for i in idx if pick(rows[i])]
            o = [rows[i] for i in idx if not pick(rows[i])]
            gs = sum(r['sites'] for r in g)
            ts = gs + sum(r['sites'] for r in o)
            gr = sum(r['reg'] for r in g)
            tr = gr + sum(r['reg'] for r in o)
            p = ratio(gs, ts)
            parts.append((int(tr), p))
            obs_r += gr
            lines.append(f'    {skey(key)}: у набора {gr:.0f} рег на {gs:.0f} сайтах, у остальных '
                         f'{tr - gr:.0f} на {ts - gs:.0f}; доля сайтов набора {p * 100:.1f}%, ожидание {tr * p:.2f}')
        dist = convolve_binomials(parts)
        e = sum(n * p for n, p in parts)
        k = int(obs_r)
        p_le = sum(dist[:k + 1])
        p_ge = sum(dist[k:])
        return obs_r, e, p_le, p_ge, lines

    O, E, parts = group_oe(gen_keys, is_gen)
    log('\nПо стратам (Generator против не-Generator):')
    log(f'{"страта":<15}{"Gen дом":>8}{"сайтов":>7}{"вышли":>6}{"выход%":>8}{"чуж.дом":>8}{"сайтов":>7}{"вышли":>6}{"выход%":>8}{"E":>7}{"O/E":>6}')
    for key, ng, gs, go, no, os_, oo, e in parts:
        log(f'{skey(key):<15}{ng:>8}{gs:>7.0f}{go:>6.0f}{ratio(go, gs) * 100:>8.1f}{no:>8}{os_:>7.0f}{oo:>6.0f}'
            f'{ratio(oo, os_) * 100:>8.1f}{e:>7.1f}{ratio(go, e):>6.2f}')
    gen_null = group_perm(gen_keys, is_gen, 'low')
    g_lo, g_hi = quantiles(gen_null)
    p_gen = perm_p(gen_null, ratio(O, E), 'low')
    n_gen = sum(1 for r in rows if is_gen(r))
    log(f'СУММАРНО Generator: {n_gen} доменов, O = {O:.0f}, E = {E:.1f}, O/E = {ratio(O, E):.2f}; '
        f'при случайной метке O/E лежит в {g_lo:.2f}–{g_hi:.2f}; P(перестановка ≤ наблюдённого) = {p_gen:.4f}.')
    O2, E2, _ = group_oe(gen_keys, is_gen, sens_extra=nz_rows)
    log(f'Чувствительность: если вернуть «КОНТЕНТ НЕ ЗАПИСАН» в базу (04.09 .team +13 доменов), '
        f'O/E = {ratio(O2, E2):.2f} (E = {E2:.1f}).')

    log('\nПо наборам в стратах с Generator. Два О/E: «против не-Gen» — база = не-Generator домены страты '
        '(для не-Gen набора — без него самого); «против всех» — база = все остальные домены страты '
        '(общий каркас). p и коридор — из раздела 1 (только для наборов с ≥5 доменами).')
    hdr = f'{"страта":<15}{"набор":<40}{"дом":>4}{"сайтов":>7}{"вышли":>6}{"выход%":>8}{"рег":>4}{"O/E не-Gen":>11}{"O/E все":>9}  {"p / коридор":<20}'
    log(hdr)
    log('-' * len(hdr))
    ctrl_styled = []
    numbered = {}
    for key in gen_keys:
        idx = strata[key]
        nongen = [rows[i] for i in idx if not is_gen(rows[i])]
        ng_out = sum(r['out'] for r in nongen)
        ng_sites = sum(r['sites'] for r in nongen)
        tot_out = sum(rows[i]['out'] for i in idx)
        tot_sites = sum(rows[i]['sites'] for i in idx)
        cnt = collections.OrderedDict()
        for i in idx:
            cnt.setdefault(rows[i]['set'], []).append(rows[i])
        items = sorted(cnt.items(), key=lambda kv: (not kv[1][0]['set'].startswith('Generator_'), kv[0]))
        for s, rs in items:
            o = sum(r['out'] for r in rs)
            st = sum(r['sites'] for r in rs)
            rg = sum(r['reg'] for r in rs)
            gen = rs[0]['set'].startswith('Generator_')
            if gen:
                base1 = ratio(ng_out, ng_sites)
            else:
                base1 = ratio(ng_out - o, ng_sites - st)
            oe1 = ratio(o, base1 * st)
            oe2 = ratio(o, ratio(tot_out - o, tot_sites - st) * st)
            q = (key, s)
            extra = ''
            if q in stats:
                extra = f'p={stats[q]["p2"]:.3f} [{stats[q]["lo"]:.2f}–{stats[q]["hi"]:.2f}]'
            elif len(rs) < MIN_SET:
                extra = f'<{MIN_SET} дом'
            log(f'{skey(key):<15}{s[:39]:<40}{len(rs):>4}{st:>7.0f}{o:>6.0f}{ratio(o, st) * 100:>8.1f}{rg:>4.0f}'
                f'{fmt(oe1):>11}{fmt(oe2):>9}  {extra:<20}')
            if gen:
                numbered[(key, s)] = dict(oe1=oe1, oe2=oe2, n=len(rs))
            elif 'styled_img' in s:
                ctrl_styled.append((key, s, len(rs), oe1, oe2))

    log('\nКонтроли styled_img в тех же стратах (ожидание гипотезы ≈1,0 / критерий ≥0,9):')
    n_ok = 0
    for key, s, n, oe1, oe2 in ctrl_styled:
        ok = oe1 >= 0.9
        n_ok += ok
        log(f'  {skey(key)} {s}: {n} дом, O/E против не-Gen соседей {fmt(oe1)}, против всех {fmt(oe2)} '
            f'{"✓" if ok else "✗ ниже 0,9"}')
    log(f'  ≥0,9 у {n_ok} из {len(ctrl_styled)} контролей.')

    # 06.09 .lol — nabory_styled_img без Generator рядом
    key_lol = ('2026-09-06', 'lol')
    if key_lol in strata:
        log('\nДополнительно 06.09 .lol (Generator там нет; nabory…_styled_img против NEW20_3…_styled_img и прочих):')
        idx = strata[key_lol]
        tot_out = sum(rows[i]['out'] for i in idx)
        tot_sites = sum(rows[i]['sites'] for i in idx)
        cnt = collections.defaultdict(list)
        for i in idx:
            cnt[rows[i]['set']].append(rows[i])
        for s, rs in sorted(cnt.items()):
            o = sum(r['out'] for r in rs)
            st = sum(r['sites'] for r in rs)
            oe2 = ratio(o, ratio(tot_out - o, tot_sites - st) * st)
            q = (key_lol, s)
            extra = f'p={stats[q]["p2"]:.3f}' if q in stats else ''
            log(f'  {s[:44]:<45}{len(rs):>3} дом {st:>5.0f} сайтов, выход {ratio(o, st) * 100:5.1f}%, O/E против всех {oe2:.2f} {extra}')

    # Generator_11page_* 25.08 .team
    key25 = ('2026-08-25', 'team')
    log('\nGenerator_11page_* в страте 25.08 .team (ожидание гипотезы ≈0,85–0,90):')
    idx = strata[key25]
    ng = [rows[i] for i in idx if not rows[i]['set'].startswith('Generator_')]
    base = ratio(sum(r['out'] for r in ng), sum(r['sites'] for r in ng))
    log(f'  база (не-Generator наборы: {", ".join(sorted({r["set"] for r in ng}))}): '
        f'{len(ng)} дом, выход {base * 100:.1f}%')
    g25 = collections.defaultdict(list)
    for i in idx:
        if rows[i]['set'].startswith('Generator_'):
            g25[rows[i]['set']].append(rows[i])
    for s, rs in sorted(g25.items()):
        o = sum(r['out'] for r in rs)
        st = sum(r['sites'] for r in rs)
        q = (key25, s)
        extra = f'; общий каркас: O/E {obs[q]["oe"]:.2f}, p={stats[q]["p2"]:.3f}' if q in stats else ''
        log(f'  {s}: {len(rs)} дом, выход {ratio(o, st) * 100:.1f}%, O/E против не-Gen {ratio(o, base * st):.2f}{extra}')
    g25_keys = [key25]
    O25, E25, _ = group_oe(g25_keys, lambda r: r['set'].startswith('Generator_'))
    n25 = group_perm(g25_keys, lambda r: r['set'].startswith('Generator_'), 'low')
    log(f'  оба вместе: O/E {ratio(O25, E25):.2f}, P(перестановка ≤) = {perm_p(n25, ratio(O25, E25), "low"):.4f}')

    # 24.08 и 31.08 — только для сведения
    log('\nДля сведения (оценить нельзя: единственный сосед в страте — «КОНТЕНТ НЕ ЗАПИСАН»):')
    for day, s in (('2026-08-24', 'ТЕСТ B Generator_11page_NOimg_24.08'),
                   ('2026-08-31', 'Generator_11page_test_1…_9 (dorgen com')):
        for zone in ('team', 'lol'):
            rs = [r for r in rows if r['day'] == day and r['zone'] == zone and r['set'] == s]
            nz = [r for r in nz_rows if r['day'] == day and r['zone'] == zone]
            if not rs:
                continue
            o = sum(r['out'] for r in rs)
            st = sum(r['sites'] for r in rs)
            nzo = sum(r['out'] for r in nz)
            nzs = sum(r['sites'] for r in nz)
            log(f'  {dm(day)} .{zone} {s}: {len(rs)} дом, выход {ratio(o, st) * 100:.1f}%; '
                f'рядом «КОНТЕНТ НЕ ЗАПИСАН» {len(nz)} дом, выход {ratio(nzo, nzs) * 100:.1f}%')

    # деньги Generator
    r_obs, r_e, p_le, p_ge, lines = reg_split(gen_keys, is_gen)
    log('\nДеньги Generator 04–06.09 (регистрации в окне 3 суток, биномиальный дележ по сайтам):')
    for ln in lines:
        log(ln)
    gen_fd = sum(r['fd'] for r in rows if is_gen(r))
    log(f'  Итого у Generator {r_obs:.0f} регистраций при ожидании {r_e:.2f}; P(≤{r_obs:.0f}) = {p_le:.3f}, '
        f'P(≥{r_obs:.0f}) = {p_ge:.3f}; ФД в окне: {gen_fd:.0f}. '
        + ('Не различимо.' if min(p_le, p_ge) > 0.05 else 'Различимо.'))

    log('\nПо доменам Generator 04–06.09 (домен: сайтов / вышли / выход% / рег):')
    for key in gen_keys:
        for i in strata[key]:
            r = rows[i]
            if is_gen(r):
                log(f'  {skey(key)} {r["set"]:<32} {r["dom"]:<14} {r["sites"]:.0f} / {r["out"]:.0f} / '
                    f'{ratio(r["out"], r["sites"]) * 100:.1f}% / {r["reg"]:.0f}')

    # по наборам Generator суммарно по стратам (против не-Gen базы)
    log('\nНаборы Generator суммарно по всем своим стратам (O/E против не-Gen соседей):')
    gen_pooled = collections.OrderedDict()
    for key in gen_keys:
        idx = strata[key]
        nongen = [rows[i] for i in idx if not is_gen(rows[i])]
        base = ratio(sum(r['out'] for r in nongen), sum(r['sites'] for r in nongen))
        for i in idx:
            r = rows[i]
            if is_gen(r):
                d = gen_pooled.setdefault(r['set'], dict(n=0, sites=0.0, out=0.0, e=0.0, reg=0.0))
                d['n'] += 1
                d['sites'] += r['sites']
                d['out'] += r['out']
                d['e'] += base * r['sites']
                d['reg'] += r['reg']
    gen_pooled_oe = {}
    for s_, d in sorted(gen_pooled.items(), key=lambda kv: ratio(kv[1]['out'], kv[1]['e'])):
        gen_pooled_oe[s_] = ratio(d['out'], d['e'])
        log(f'  {s_:<32}{d["n"]:>3} дом {d["sites"]:>5.0f} сайтов, вышли {d["out"]:>4.0f} при E {d["e"]:>6.1f} → O/E {gen_pooled_oe[s_]:.2f}, рег {d["reg"]:.0f}')
    n_le045 = sum(1 for v in gen_pooled_oe.values() if v <= 0.45)
    log(f'  ≤0,45 у {n_le045} из {len(gen_pooled_oe)} наборов (ожидание гипотезы: 5 из 8).')

    # критерии (а)
    gen_oe = ratio(O, E)
    crit_a1 = gen_oe <= 0.5 and p_gen < 0.001
    bad_numbered = [(s_, v) for s_, v in gen_pooled_oe.items() if s_ != 'Generator_346353_styled_img' and v > 0.75]
    crit_a2 = not bad_numbered
    crit_a3 = (n_ok == len(ctrl_styled)) if ctrl_styled else False
    log('\nКритерии (а):')
    log(f'  суммарный O/E ≤ 0,5 при p < 0,001: O/E = {gen_oe:.2f}, p = {p_gen:.4f} → {"да" if crit_a1 else "нет"}')
    log(f'  ни один набор Generator кроме 346353 не выше 0,75 (против не-Gen, суммарно по стратам): '
        f'{"да" if crit_a2 else "нет: " + "; ".join(f"{s_} {v:.2f}" for s_, v in bad_numbered)}')
    log(f'  styled_img-контроли ≥ 0,9: {n_ok} из {len(ctrl_styled)} → {"да" if crit_a3 else "нет"}')

    # один и тот же набор в разных стратах: насколько O/E зависит от соседей
    log('\nОдин и тот же набор в разных стратах общего каркаса (O/E зависит от того, кто рядом):')
    by_name = collections.defaultdict(list)
    for key, s_ in qual:
        by_name[s_].append((key, obs[(key, s_)]['oe'], obs[(key, s_)]['base']))
    for s_, lst in sorted(by_name.items()):
        if len(lst) < 2:
            continue
        vals = [v for _, v, _ in lst]
        spread = ratio(max(vals), min(vals))
        log(f'  {s_[:44]:<45} ' + '; '.join(f'{skey(k)} O/E {v:.2f} (база {b * 100:.1f}%)' for k, v, b in lst)
            + f'  → разброс {spread:.1f}×')

    # ------------------------------------------------------------------
    # 3. Контраст (б): Content_script_12page_08.09 и script_yandex_12page
    # ------------------------------------------------------------------
    log('\n' + '=' * 78)
    log('3. КОНТРАСТ (б): Content_script_12page_08.09 И script_yandex_12page')
    log('=' * 78)

    def set_block(name, keys, side, label):
        pick = lambda r: r['set'] == name
        O, E, parts = group_oe(keys, pick)
        log(f'\n{name} — {label}. База — все остальные домены страты.')
        log(f'{"страта":<15}{"дом":>4}{"сайтов":>7}{"вышли":>6}{"выход%":>8}{"чуж.дом":>8}{"сайтов":>7}{"вышли":>6}{"выход%":>8}{"E":>7}{"O/E":>6}')
        for key, ng, gs, go, no, os_, oo, e in parts:
            log(f'{skey(key):<15}{ng:>4}{gs:>7.0f}{go:>6.0f}{ratio(go, gs) * 100:>8.1f}{no:>8}{os_:>7.0f}{oo:>6.0f}'
                f'{ratio(oo, os_) * 100:>8.1f}{e:>7.1f}{ratio(go, e):>6.2f}')
        nv = group_perm(keys, pick, side)
        lo, hi = quantiles(nv)
        p = perm_p(nv, ratio(O, E), side)
        nd = sum(p_[1] for p_ in parts)
        log(f'  СУММАРНО: {nd} доменов, O = {O:.0f}, E = {E:.1f}, O/E = {ratio(O, E):.2f}; '
            f'при случайной метке {lo:.2f}–{hi:.2f}; P(перестановка {"≥" if side == "high" else "≤"} наблюдённого) = {p:.4f}.')
        r_obs, r_e, p_le, p_ge, lines = reg_split(keys, pick)
        log('  Регистрации в окне 3 суток (биномиальный дележ по сайтам):')
        for ln in lines:
            log(ln)
        log(f'    итого {r_obs:.0f} при ожидании {r_e:.2f} ({fmt(ratio(r_obs, r_e))}×); '
            f'P(≥{r_obs:.0f}) = {p_ge:.3f}, P(≤{r_obs:.0f}) = {p_le:.3f}.')
        return dict(oe=ratio(O, E), p=p, lo=lo, hi=hi, reg=r_obs, reg_e=r_e, p_ge=p_ge, p_le=p_le, n=nd, O=O, E=E)

    cs_keys = sorted({(r['day'], r['zone']) for r in rows if r['set'] == CONTENT_SCRIPT})
    cs = set_block(CONTENT_SCRIPT, cs_keys, 'high', 'страты ' + ', '.join(skey(k) for k in cs_keys))
    # состав базы 08.09 .lol и сравнение только с clean7
    log('  Состав базы по наборам (что именно стоит за «остальными»):')
    for key in cs_keys:
        idx = strata[key]
        cnt = collections.defaultdict(list)
        for i in idx:
            if rows[i]['set'] != CONTENT_SCRIPT:
                cnt[rows[i]['set']].append(rows[i])
        for s, rs in sorted(cnt.items(), key=lambda kv: -len(kv[1])):
            o = sum(r['out'] for r in rs)
            st = sum(r['sites'] for r in rs)
            log(f'    {skey(key)} {s[:44]:<45}{len(rs):>3} дом, выход {ratio(o, st) * 100:5.1f}%, рег {sum(r["reg"] for r in rs):.0f}')
    O_c = E_c = 0.0
    for key in cs_keys:
        idx = strata[key]
        g = [rows[i] for i in idx if rows[i]['set'] == CONTENT_SCRIPT]
        c7 = [rows[i] for i in idx if rows[i]['set'] == 'clean7_part1_50оформлено']
        if c7:
            O_c += sum(r['out'] for r in g)
            E_c += ratio(sum(r['out'] for r in c7), sum(r['sites'] for r in c7)) * sum(r['sites'] for r in g)
    log(f'  Только против clean7_part1_50оформлено в тех же стратах: O/E = {ratio(O_c, E_c):.2f} '
        f'(O = {O_c:.0f}, E = {E_c:.1f}). Против archive37…v2 в 08.09 .lol база слабая (archive — известно худшее семейство).')

    sy_keys11 = sorted({(r['day'], r['zone']) for r in rows if r['set'] == SCRIPT_YANDEX and r['day'] == '2026-09-11'})
    sy_keys12 = sorted({(r['day'], r['zone']) for r in rows if r['set'] == SCRIPT_YANDEX and r['day'] == '2026-09-12'})
    sy11 = set_block(SCRIPT_YANDEX, sy_keys11, 'low', '11.09: ' + ', '.join(skey(k) for k in sy_keys11))
    sy12 = set_block(SCRIPT_YANDEX, sy_keys12, 'low', '12.09 отдельно (слабый день): ' + ', '.join(skey(k) for k in sy_keys12))
    sy_all = set_block(SCRIPT_YANDEX, sy_keys11 + sy_keys12, 'low', 'все страты вместе')

    log('\nscript_yandex_12page против NEW102 напрямую в 11.09 .casino:')
    key = ('2026-09-11', 'casino')
    idx = strata[key]
    g = [rows[i] for i in idx if rows[i]['set'] == SCRIPT_YANDEX]
    go, gs = sum(r['out'] for r in g), sum(r['sites'] for r in g)
    for nm in ('NEW102оформленобездаты', 'NEW102оформленосдатой', 'оба NEW102'):
        if nm == 'оба NEW102':
            rs = [rows[i] for i in idx if rows[i]['set'].startswith('NEW102')]
        else:
            rs = [rows[i] for i in idx if rows[i]['set'] == nm]
        o, st = sum(r['out'] for r in rs), sum(r['sites'] for r in rs)
        log(f'  {nm}: {len(rs)} дом, выход {ratio(o, st) * 100:.1f}%, рег {sum(r["reg"] for r in rs):.0f}; '
            f'script_yandex ({len(g)} дом) выход {ratio(go, gs) * 100:.1f}%, рег {sum(r["reg"] for r in g):.0f} → '
            f'отношение выходов {ratio(ratio(go, gs), ratio(o, st)):.2f}')

    log('\nПо доменам (домен: сайтов / вышли / выход% / рег):')
    for nm, keys in ((CONTENT_SCRIPT, cs_keys), (SCRIPT_YANDEX, sy_keys11 + sy_keys12)):
        for key in keys:
            for i in strata[key]:
                r = rows[i]
                if r['set'] == nm:
                    log(f'  {skey(key)} {nm:<28} {r["dom"]:<14} {r["sites"]:.0f} / {r["out"]:.0f} / '
                        f'{ratio(r["out"], r["sites"]) * 100:.1f}% / {r["reg"]:.0f}')

    # критерии (б)
    crit_b1 = cs['oe'] >= 1.25 and cs['p'] < 0.05
    crit_b1r = cs['reg'] >= 2 * cs['reg_e']
    crit_b2 = sy11['oe'] <= 0.8 and sy11['p'] < 0.05
    named_out = {q: stats[q]['outside'] for q in named}
    log('\nКритерии (б):')
    log(f'  Content_script O/E ≥ 1,25 при p < 0,05: O/E = {cs["oe"]:.2f}, p = {cs["p"]:.4f} → {"да" if crit_b1 else "нет"}; '
        f'регистраций ≥ 2× ожидания: {cs["reg"]:.0f} против {cs["reg_e"]:.2f} ({fmt(ratio(cs["reg"], cs["reg_e"]))}×, '
        f'P = {cs["p_ge"]:.3f}) → {"да" if crit_b1r else "нет"}')
    log(f'  script_yandex O/E ≤ 0,8 при p < 0,05 в страте 11.09: O/E = {sy11["oe"]:.2f}, p = {sy11["p"]:.4f} → '
        f'{"да" if crit_b2 else "нет"}; 12.09 .casino: O/E = {sy12["oe"]:.2f}, p = {sy12["p"]:.4f}; '
        f'все вместе: O/E = {sy_all["oe"]:.2f}, p = {sy_all["p"]:.4f}; регистраций {sy_all["reg"]:.0f} при ожидании '
        f'{sy_all["reg_e"]:.2f}, P(≤) = {sy_all["p_le"]:.3f}')
    log('  Названные наборы за коридором общего теста:')
    for q in sorted(named, key=lambda q: obs[q]['oe']):
        log(f'    {skey(q[0])} {q[1]}: {"ВНЕ" if named_out[q] else "внутри"} (O/E {obs[q]["oe"]:.2f}, коридор '
            f'{stats[q]["lo"]:.2f}–{stats[q]["hi"]:.2f})')
    n_named_out = sum(named_out.values())
    log(f'    итого вне коридора {n_named_out} из {len(named)} названных, прошедших порог ≥5 доменов.')

    # ------------------------------------------------------------------
    # ВЫВОД
    # ------------------------------------------------------------------
    log('\n' + '=' * 78)
    log('ВЫВОД')
    log('=' * 78)
    gen_low = [f'{s_.replace("Generator_", "")} {v:.2f}' for s_, v in gen_pooled_oe.items()]
    cs_top_dom = max((rows[i] for key in cs_keys for i in strata[key] if rows[i]['set'] == CONTENT_SCRIPT),
                     key=lambda r: r['reg'])
    k14 = ('2026-09-14', 'team')
    log(f'1. Общий тест на все {len(qual)} наборов (≥5 доменов и ≥5 чужих в страте день × зона): вне своего '
        f'95%-коридора {n_out_obs} наборов ({n_low_obs} ниже, {n_high_obs} выше) при {exp_out:.1f} ожидаемых по случайности '
        f'(P = {perm_p(n_out_null, n_out_obs, "high"):.4f}); после поправки Бенджамини–Хохберга при q=0,05 остаётся {len(bh05)}. '
        f'То есть наборы расходятся с соседями сильнее обычного разброса доменов — это подтверждает известное «набор '
        f'управляет выходом». Худшие два набора всего каркаса гипотеза не называла: 14.09 .team nabory-510-514_styled_img '
        f'({obs[(k14, "nabory-510-514_styled_img")]["oe"]:.2f}) и nabory-500-509_styled_img '
        f'({obs[(k14, "nabory-500-509_styled_img")]["oe"]:.2f}).')
    log(f'2. Generator_* от 04–06.09 — подтверждено: {n_gen} доменов ({sum(d["sites"] for d in gen_pooled.values()):.0f} сайтов), '
        f'вышло {O:.0f} сайтов при ожидании {E:.0f} по не-Generator соседям тех же дней и зон — O/E {gen_oe:.2f}, то есть '
        f'в {1 / gen_oe:.1f} раза ниже; перестановочный p = {p_gen:.4f} (при случайной метке O/E {g_lo:.2f}–{g_hi:.2f}). '
        f'По наборам: {"; ".join(gen_low)} — ≤0,45 у {n_le045} из {len(gen_pooled_oe)}. С «КОНТЕНТ НЕ ЗАПИСАН» в базе O/E '
        f'{ratio(O2, E2):.2f}. В общем каркасе (против всех соседей, включая другие Generator) за коридор выходят 370382 и 354359; '
        f'346353 ({obs[(("2026-09-04", "team"), "Generator_346353_styled_img")]["oe"]:.2f}) — нет. Регистраций {r_obs:.0f} при '
        f'ожидании {r_e:.2f} (P = {p_le:.2f}) — не различимо. Generator_11page_* от 25.08: {ratio(O25, E25):.2f}, '
        f'внутри коридора — старый генератор не мёртв.')
    log(f'3. «Плох генератор, а не styled_img» — только наполовину. Контроли styled_img в тех же стратах: ≥0,9 у {n_ok} из '
        f'{len(ctrl_styled)}; NEW20/NEW21/NEW20_3…styled_img держатся у 1,0–1,5, но nabory400410_styled_img проваливается '
        f'и в .team (0,51, 4 дом), и в .lol (0,59, 7 дом, p = {stats[(("2026-09-06", "lol"), "nabory400410_styled_img")]["p2"]:.3f}), '
        f'а nabory-500-509/510-514_styled_img от 14.09 — худшие во всём каркасе. Провал сцеплен не со styled_img как '
        f'оформлением, а с нумерованными генерированными наборами (Generator_NNNNNN и часть nabory-NNN), что согласуется '
        f'с известным «NEW 0,147 против nabory 0,032».')
    log(f'4. Content_script_12page_08.09 — частично. Выход: суммарно O/E {cs["oe"]:.2f}, но p = {cs["p"]:.4f}, потому что '
        f'в .lol 2,61 (вне коридора, BH 0,05), а в .team 0,68 при двух соседях; база в 08.09 .lol на 51 из 61 '
        f'доменов — archive37…v2 с выходом ≈5%, а против clean7 тех же страт O/E всего {ratio(O_c, E_c):.2f}. '
        f'Деньги: {cs["reg"]:.0f} регистраций при ожидании {cs["reg_e"]:.2f} ({ratio(cs["reg"], cs["reg_e"]):.1f}×, P = {cs["p_ge"]:.3f}), '
        f'но {cs_top_dom["reg"]:.0f} из них — один домен {cs_top_dom["dom"]}; на 11 доменах это не рецепт, а один удачный домен.')
    log(f'5. script_yandex_12page — не подтверждено. 11.09: O/E {sy11["oe"]:.2f}, p = {sy11["p"]:.4f} (в .casino 0,74, в .team 1,29); '
        f'12.09 .casino: {sy12["oe"]:.2f}, p = {sy12["p"]:.4f}; все 21 домен: {sy_all["oe"]:.2f}, p = {sy_all["p"]:.4f}. Везде внутри '
        f'коридора. Регистраций {sy_all["reg"]:.0f} при ожидании {sy_all["reg_e"]:.2f} (P(≤) = {sy_all["p_le"]:.2f}). Против NEW102 в '
        f'11.09 .casino — 0,74, не «вдвое».')
    log('6. Оговорка ко всему: O/E набора — относительно соседей по дню и зоне. archive37строформленоv2часть1 даёт 2,54 в 10.09 .team '
        '(рядом archive47 с 3–5%) и 0,44 в 11.09 .team (рядом NEW102 и clean7 с 11–12%). «Выбивается» — не свойство набора, '
        'а свойство пары «набор — соседи»; поэтому 11–21 домен script-наборов в стратах со случайным составом мало что доказывают.')
    log('Что с этим делать: (1) нумерованные Generator_NNNNNN_styled_img 04–06.09 и Generator_A/B больше не ставить — это '
        'проверяемо уже сейчас: у 44 доменов выход вдвое ниже соседей (p = 0,0001) и ни одной пользы по деньгам; чинить надо '
        'контент генератора, потому что NEW…styled_img тех же дней в порядке. (2) Прежде чем повторять «рецепт» '
        'Content_script_12page_08.09, поставить его рядом с NEW102/clean7 в одну страту: против archive он выигрывает, против '
        'clean7 — только 1,10. (3) script_yandex_12page не запрещать по этим данным: 21 домен внутри коридора; если ставить ещё — '
        'только в одной страте с NEW102, чтобы был чистый контраст. (4) Отдельно разобрать nabory-500-509 и nabory-510-514_styled_img '
        'от 14.09 .team (O/E 0,21 и 0,09) — они хуже любого Generator, и гипотеза их не заметила.')

    log.close()


def rank_in(sel, qual, q):
    return qual.index(q) in sel


if __name__ == '__main__':
    main()
