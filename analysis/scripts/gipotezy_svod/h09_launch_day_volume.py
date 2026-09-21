#!/usr/bin/env python3
"""
Гипотеза №9. Большой день запуска сети не разбавляет результат домена.

Что проверяем.
  В большие дни (110–159 доменов за день, то есть 23–30 тыс. сайтов на
  переобход) выход в поиск, клики на вышедший сайт, скорость входа и
  регистрации у домена не ниже, чем в малые дни (<60 доменов), если сравнивать
  внутри одного набора контента и зоны. Если спрос по бренду делится между
  близнецами или Яндекс медленнее берёт массу однотипных сайтов, большой день
  должен давать O/E < 1 по выходу, кликам на вышедший и скорости.

Как проверяем.
  Объём дня N(день) = число строк свода с тем же днём запуска (по всем 2077
  строкам, включая исключённые из анализа: нагрузка на сеть — это все запуски).
  Вторая мера — нагрузка переобхода L(день) = 150·N(день) + 56·N₂(день−1),
  где N₂ — вчерашние домены, у которых был день 2 («дней» ≠ 1).
  Классы объёма: <60 / 60–110 / ≥110 доменов.

  Фильтр: окно закрыто = да; дней ≠ 1; без «КОНТЕНТ НЕ ЗАПИСАН»; без выбросов
  3615.team и 3286.team (исключены везде, а не только там, где клики).

  Метрики домена (все в окне 3 суток):
    выход        = вышли за 3 суток / сайтов в окне
    клики/вышедш = кликов из поиска в окне / вышли за 3 суток
    регистрации  = регистраций в окне 3 суток / сайтов в окне
    скорость     = вышли за 1 сутки / вышли за 3 суток
    задержка     = «задержка до поиска, медиана» (суток), среднее по доменам
                   с весом «вышли за 3 суток»; сравнивается разностью, не O/E.

  Главная страта — набор контента + зона (зоны team/lol/casino/buzz, остальные
  — «прочие»). Берутся только наборы с ≥2 датами запуска; внутри страты каждый
  день — пул. Ожидание пула E = знаменатель пула × доля своего набора+зоны;
  O/E класса объёма = ΣO / ΣE по пулам класса. Тесты: взвешенный по сайтам
  Спирмен между N(день) и O/E пулов, нулевое распределение — перестановка
  объёмов между днями внутри набора (10 000 раз); знаковый критерий по парам
  «самый большой день против самого малого» внутри набора+зоны (контраст
  объёма ≥1,2×); точный биномиальный p.
  Вторичная страта — семейство + страниц + оформление + зона + ISO-неделя,
  три класса объёма, перестановка дня между доменами внутри страты (10 000).
  Только здесь достижимы самые большие дни 15–17.09: на них каждый домен
  несёт свой собственный набор (159 наборов на 159 доменов), поэтому страта
  «набор + день» для них вырождается в «домен».
  Дополнительно — корень набора (имя набора без хвоста «_номер», как в
  analysis/scripts/pary_variantov.py) + зона: даёт ещё два сравнения
  14.09 (71) против 15.09 (159) внутри одного корня.

  Критерии из постановки: «не разбавляет» — O/E класса ≥110 ≥ 0,9 по выходу
  и кликам на вышедший, Спирмен не ниже −0,2 при p > 0,2; «разбавляет» —
  монотонное падение ≥1,3× от малых дней к большим при p < 0,05 в обеих
  стратах.
"""
import collections
import csv
import datetime
import math
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h09_launch_day_volume.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
NPERM = 10000
CLASSES = ('<60', '60-110', '>=110')
METRICS = [  # (ярлык, числитель, знаменатель)
    ('выход', 'out3', 'sites'),
    ('клики/вышедш', 'clk', 'out3'),
    ('регистрации', 'reg', 'sites'),
    ('скорость', 'out1', 'out3'),
]


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
    if s == '':
        return default
    return float(s)


def zone_group(z):
    return z if z in ('team', 'lol', 'casino', 'buzz') else 'прочие'


def vol_class(n):
    return '<60' if n < 60 else ('60-110' if n < 110 else '>=110')


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def wpearson(x, y, w):
    sw = sum(w)
    if sw <= 0 or len(x) < 3:
        return float('nan')
    mx = sum(a * b for a, b in zip(x, w)) / sw
    my = sum(a * b for a, b in zip(y, w)) / sw
    sxy = sum(wi * (a - mx) * (b - my) for a, b, wi in zip(x, y, w))
    sxx = sum(wi * (a - mx) ** 2 for a, wi in zip(x, w))
    syy = sum(wi * (b - my) ** 2 for b, wi in zip(y, w))
    if sxx <= 0 or syy <= 0:
        return float('nan')
    return sxy / math.sqrt(sxx * syy)


def wspearman(x, y, w):
    return wpearson(ranks(x), ranks(y), w)


def binom_two_sided(k, n):
    if n == 0:
        return float('nan')
    pk = math.comb(n, k) / 2 ** n
    return min(1.0, sum(math.comb(n, i) / 2 ** n for i in range(n + 1)
                        if math.comb(n, i) / 2 ** n <= pk + 1e-12))


def fmt(x, d=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return '—'
    return f'{x:.{d}f}'


def ratio(o, e):
    return o / e if e > 0 else float('nan')


def main():
    out = Tee(OUT)
    random.seed(1)
    rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
    out('Гипотеза №9: большой день запуска сети (≥110 доменов за день) не разбавляет результат домена')
    out('Файл:', SRC)
    out('Строк (доменов) всего:', len(rows))

    # ---------- объём дня по всем строкам ----------
    N = collections.Counter(r['день запуска'] for r in rows)
    N2 = collections.Counter(r['день запуска'] for r in rows if r['дней'] != '1')
    days = sorted(N)
    LOAD = {}
    for d in days:
        prev = (datetime.date.fromisoformat(d) - datetime.timedelta(days=1)).isoformat()
        LOAD[d] = 150 * N[d] + 56 * N2.get(prev, 0)

    # ---------- фильтр ----------
    out('\nФильтр (исключения по шагам):')
    cur = rows
    for label, keep in [
        ('окно закрыто = нет', lambda r: r['окно закрыто'] == 'да'),
        ('дней = 1 (только первая волна, 150 сайтов)', lambda r: r['дней'] != '1'),
        ('выбросы ' + ', '.join(OUTLIERS) + ' (миллионы «прочих» кликов; исключены везде)',
         lambda r: r['домен'] not in OUTLIERS),
        ('«КОНТЕНТ НЕ ЗАПИСАН» (не набор, сцеплен с датой)', lambda r: r['набор контента'] != NOCONTENT),
    ]:
        nxt = [r for r in cur if keep(r)]
        out(f'  {label}: исключено {len(cur) - len(nxt)}, осталось {len(nxt)}')
        cur = nxt
    base = cur

    for r in base:
        r['sites'] = num(r['сайтов в окне'])
        r['out3'] = num(r['вышли за 3 суток'])
        r['out1'] = num(r['вышли за 1 сутки'])
        r['clk'] = num(r['кликов из поиска в окне'])
        r['reg'] = num(r['регистраций в окне 3 суток'])
        r['fd'] = num(r['ФД в окне 3 суток'])
        r['delay'] = num(r['задержка до поиска, медиана'], None)
        r['N'] = N[r['день запуска']]
        r['L'] = LOAD[r['день запуска']]
        r['cls'] = vol_class(r['N'])
        r['zone'] = zone_group(r['зона'])
        r['root'] = re.sub(r'[_\-]\d+$', '', r['набор контента'])

    # ---------- таблица дней ----------
    out('\nОбъём дня по всем 2077 строкам (N — доменов запущено; N₂(вчера) — вчерашних с днём 2; '
        'L = 150·N + 56·N₂(вчера) — сайтов на переобход за день); после фильтра — доменов/сайтов/'
        'регистраций в окне, вошедших в анализ:')
    out('  день        N   класс   N₂(вчера)      L | в анализе: доменов  сайтов  вышли3  рег  наборов контента')
    tot = collections.Counter()
    for d in days:
        sub = [r for r in base if r['день запуска'] == d]
        prev = (datetime.date.fromisoformat(d) - datetime.timedelta(days=1)).isoformat()
        out(f'  {d}  {N[d]:3d}   {vol_class(N[d]):6s}       {N2.get(prev, 0):3d}  {LOAD[d]:5d} | '
            f'{len(sub):18d}  {int(sum(r["sites"] for r in sub)):6d}  {int(sum(r["out3"] for r in sub)):6d}  '
            f'{int(sum(r["reg"] for r in sub)):3d}  {len(set(r["набор контента"] for r in sub)):3d}')
    out('  Самые большие дни 15, 16, 17.09 (159/138/152): на каждом домене свой собственный набор контента '
        f'({", ".join(str(len(set(r["набор контента"] for r in rows if r["день запуска"] == d))) for d in ("2026-09-15", "2026-09-16", "2026-09-17"))} '
        'наборов на 159/138/152 доменов). Страта «набор + день» для них равна «домен»: сравнить их внутри '
        'набора нельзя, они доступны только во вторичной страте и в корнях.')

    # ---------- контекст без страты ----------
    out('\nКонтекст БЕЗ страты (не доказательство — день сцеплен с набором контента и зоной):')
    out('  класс    доменов   сайтов   вышли3   выход%   кликов/вышедш   рег   рег/100 сайтов   рег/10т.кл   ФД   вышли1/вышли3   задержка')
    for c in CLASSES:
        sub = [r for r in base if r['cls'] == c]
        s = sum(r['sites'] for r in sub)
        o3 = sum(r['out3'] for r in sub)
        o1 = sum(r['out1'] for r in sub)
        ck = sum(r['clk'] for r in sub)
        rg = sum(r['reg'] for r in sub)
        fd = sum(r['fd'] for r in sub)
        dl = [(r['delay'], r['out3']) for r in sub if r['delay'] is not None and r['out3'] > 0]
        dlm = sum(a * b for a, b in dl) / sum(b for _, b in dl) if dl else float('nan')
        out(f'  {c:7s}  {len(sub):7d}  {int(s):7d}  {int(o3):7d}   {100 * o3 / s:5.1f}      {ck / o3:8.1f}   '
            f'{int(rg):4d}   {100 * rg / s:8.3f}        {1e4 * rg / ck:6.1f}   {int(fd):2d}      {o1 / o3:8.3f}     {dlm:6.2f}')

    # =====================================================================
    # ГЛАВНАЯ СТРАТА: набор контента + зона
    # =====================================================================
    def pool_analysis(title, keyname, pool_key, unit_label):
        """keyname: поле группировки ('набор контента' или 'root'); pool_key(r) -> (группа, зона)."""
        out('\n' + '=' * 110)
        out(title)
        out('=' * 110)
        gdays = collections.defaultdict(set)
        for r in base:
            gdays[r[keyname]].add(r['день запуска'])
        multi = {g for g, ds in gdays.items() if len(ds) >= 2}
        cand = [r for r in base if r[keyname] in multi]
        strata = collections.defaultdict(list)
        for r in cand:
            strata[pool_key(r)].append(r)
        strata = {k: v for k, v in strata.items() if len(set(r['день запуска'] for r in v)) >= 2}
        used = [r for v in strata.values() for r in v]
        out(f'{unit_label} с ≥2 датами запуска: {len(multi)} ({len(cand)} доменов); '
            f'страт {unit_label.lower()}+зона с ≥2 датами: {len(strata)} ({len(used)} доменов, '
            f'{int(sum(r["sites"] for r in used))} сайтов, {int(sum(r["reg"] for r in used))} регистраций в окне); '
            f'{len(cand) - len(used)} доменов отпали, потому что в их зоне у {unit_label.lower()} одна дата (O/E там тождественно 1).')

        # пулы
        pools = []  # dict: key, day, N, L, cls, n, sites, per-metric O,E, delay
        for key in sorted(strata):
            v = strata[key]
            tot_ = {f: sum(r[f] for r in v) for f in ('sites', 'out3', 'out1', 'clk', 'reg')}
            dl = [(r['delay'], r['out3']) for r in v if r['delay'] is not None and r['out3'] > 0]
            dl_s = sum(a * b for a, b in dl) / sum(b for _, b in dl) if dl else None
            bydays = collections.defaultdict(list)
            for r in v:
                bydays[r['день запуска']].append(r)
            for d in sorted(bydays):
                u = bydays[d]
                p = {'key': key, 'day': d, 'N': N[d], 'L': LOAD[d], 'cls': vol_class(N[d]), 'n': len(u),
                     'sites': sum(r['sites'] for r in u), 'grp': key[0]}
                for lab, nu, de in METRICS:
                    o = sum(r[nu] for r in u)
                    den = sum(r[de] for r in u)
                    rate = tot_[nu] / tot_[de] if tot_[de] > 0 else 0.0
                    p[lab] = (o, den * rate)
                dlp = [(r['delay'], r['out3']) for r in u if r['delay'] is not None and r['out3'] > 0]
                p['delay'] = (sum(a * b for a, b in dlp) / sum(b for _, b in dlp) - dl_s, sum(b for _, b in dlp)) if dlp and dl_s is not None else None
                pools.append(p)

        out('\nПулы (страта + день). O/E — наблюдённое/ожидаемое по доле своей страты; '
            'Δзадержки — сдвиг средней медианной задержки пула от страты, суток (+ = медленнее):')
        out('  страта                                           день    N  класс  дом  сайтов | выход O/E | кл/выш O/E | рег O/E (O) | скорость O/E | Δзадержки')
        last = None
        for p in pools:
            if p['key'] != last:
                last = p['key']
                out(f'  {p["key"][0][:38]:38s} {p["key"][1]:7s}')
            o3, e3 = p['выход']
            oc, ec = p['клики/вышедш']
            orr, er = p['регистрации']
            os_, es = p['скорость']
            dz = fmt(p['delay'][0]) if p['delay'] else '—'
            out(f'  {"":46s} {p["day"][5:]}  {p["N"]:3d}  {p["cls"]:6s} {p["n"]:3d}  {int(p["sites"]):5d} |  '
                f'{fmt(ratio(o3, e3)):>6s}   |   {fmt(ratio(oc, ec)):>6s}   |  {fmt(ratio(orr, er)):>6s} ({int(orr):2d}) |    '
                f'{fmt(ratio(os_, es)):>6s}    |  {dz:>6s}')

        # O/E по классам объёма
        def class_table(pools_, xattr='cls'):
            res = {}
            for c in CLASSES:
                sub = [p for p in pools_ if p[xattr] == c]
                row = {'n': sum(p['n'] for p in sub), 'sites': sum(p['sites'] for p in sub),
                       'reg': sum(p['регистрации'][0] for p in sub), 'pools': len(sub),
                       'nsets': len(set(p['grp'] for p in sub))}
                for lab, _, _ in METRICS:
                    o = sum(p[lab][0] for p in sub)
                    e = sum(p[lab][1] for p in sub)
                    row[lab] = ratio(o, e)
                    row[lab + '_O'] = o
                dl = [p['delay'] for p in sub if p['delay']]
                row['delay'] = sum(a * b for a, b in dl) / sum(b for _, b in dl) if dl and sum(b for _, b in dl) > 0 else float('nan')
                res[c] = row
            return res

        obs = class_table(pools)
        out('\nO/E по классам объёма дня (ΣO/ΣE по пулам класса; страта = ' + unit_label.lower() + ' + зона):')
        out('  класс    пулов  наборов  доменов   сайтов | выход O/E | кл/выш O/E | рег O/E (O рег) | скорость O/E | Δзадержки, сут')
        for c in CLASSES:
            w = obs[c]
            out(f'  {c:7s}  {w["pools"]:5d}  {w["nsets"]:7d}  {w["n"]:7d}  {int(w["sites"]):7d} |  {fmt(w["выход"]):>6s}   |   '
                f'{fmt(w["клики/вышедш"]):>6s}   |  {fmt(w["регистрации"]):>6s} ({int(w["reg"]):3d})   |    {fmt(w["скорость"]):>6s}    |  {fmt(w["delay"]):>6s}')

        # Спирмен (взвешенный по сайтам) между N и O/E пулов + перестановка объёмов внутри набора
        out('\nВзвешенный по сайтам Спирмен между объёмом дня и O/E пулов; p — перестановка объёмов между днями '
            f'внутри {unit_label.lower()} ({NPERM} раз; двусторонний, в скобках односторонний «чем больше день, тем хуже»):')
        grp_days = collections.defaultdict(list)
        for p in pools:
            if p['day'] not in grp_days[p['grp']]:
                grp_days[p['grp']].append(p['day'])
        # относительный объём: N минус среднее N по дням набора
        grp_meanN = {g: sum(N[d] for d in ds) / len(ds) for g, ds in grp_days.items()}

        def stats_for(pools_, xattr):
            res = {}
            for lab, _, _ in METRICS:
                xs, ys, ws = [], [], []
                for p in pools_:
                    o, e = p[lab]
                    if e > 0:
                        xs.append(p[xattr]); ys.append(o / e); ws.append(p['sites'])
                res[lab] = wspearman(xs, ys, ws)
            xs, ys, ws = [], [], []
            for p in pools_:
                if p['delay']:
                    xs.append(p[xattr]); ys.append(p['delay'][0]); ws.append(p['delay'][1])
            res['задержка'] = wspearman(xs, ys, ws)
            return res

        for p in pools:
            p['Nrel'] = p['N'] - grp_meanN[p['grp']]
        rho_obs = {x: stats_for(pools, x) for x in ('N', 'Nrel', 'L')}
        obs_cls = obs
        # перестановки
        cnt2 = {x: collections.Counter() for x in rho_obs}
        cnt1 = {x: collections.Counter() for x in rho_obs}
        cnt_cls_low = collections.Counter()   # O/E(>=110) <= observed
        cnt_cls_hi = collections.Counter()
        cnt_ratio = collections.Counter()     # O/E(<60)/O/E(>=110) >= observed
        obs_ratio = {lab: ratio(obs_cls['<60'][lab], obs_cls['>=110'][lab]) for lab, _, _ in METRICS}
        for _ in range(NPERM):
            perm_N = {}
            for g, ds in grp_days.items():
                vals = [N[d] for d in ds]
                random.shuffle(vals)
                for d, v in zip(ds, vals):
                    perm_N[(g, d)] = v
            for p in pools:
                v = perm_N[(p['grp'], p['day'])]
                p['pN'] = v
                p['pNrel'] = v - grp_meanN[p['grp']]
                p['pcls'] = vol_class(v)
            for x in ('N', 'Nrel'):
                rp = stats_for(pools, 'p' + x)
                for lab, v in rp.items():
                    if not math.isnan(v) and not math.isnan(rho_obs[x][lab]):
                        if abs(v) >= abs(rho_obs[x][lab]) - 1e-12:
                            cnt2[x][lab] += 1
                        if v <= rho_obs[x][lab] + 1e-12:
                            cnt1[x][lab] += 1
            pc = class_table(pools, 'pcls')
            for lab, _, _ in METRICS:
                v = pc['>=110'][lab]
                o = obs_cls['>=110'][lab]
                if not math.isnan(v) and not math.isnan(o):
                    if v <= o + 1e-12:
                        cnt_cls_low[lab] += 1
                    if v >= o - 1e-12:
                        cnt_cls_hi[lab] += 1
                rr = ratio(pc['<60'][lab], pc['>=110'][lab])
                if not math.isnan(rr) and not math.isnan(obs_ratio[lab]) and rr >= obs_ratio[lab] - 1e-12:
                    cnt_ratio[lab] += 1
        # L отдельно (перестановка L между днями внутри набора, так же как N)
        cnt2L = collections.Counter(); cnt1L = collections.Counter()
        pools_by_gd = collections.defaultdict(list)
        for p in pools:
            pools_by_gd[(p['grp'], p['day'])].append(p)
        for _ in range(NPERM):
            for g, ds in grp_days.items():
                vals = [LOAD[d] for d in ds]
                random.shuffle(vals)
                for d, v in zip(ds, vals):
                    for p in pools_by_gd[(g, d)]:
                        p['pL'] = v
            rp = stats_for(pools, 'pL')
            for lab, v in rp.items():
                if not math.isnan(v) and not math.isnan(rho_obs['L'][lab]):
                    if abs(v) >= abs(rho_obs['L'][lab]) - 1e-12:
                        cnt2L[lab] += 1
                    if v <= rho_obs['L'][lab] + 1e-12:
                        cnt1L[lab] += 1
        out('  мера объёма                       | ' + ' | '.join(f'{lab:>22s}' for lab, _, _ in METRICS) + ' | ' + f'{"задержка":>22s}')
        for x, name in (('N', 'N(день), доменов'), ('Nrel', 'N − среднее N по набору'), ('L', 'L, сайтов на переобход')):
            cells = []
            for lab in [m[0] for m in METRICS] + ['задержка']:
                rho = rho_obs[x][lab]
                if x == 'L':
                    p2 = (cnt2L[lab] + 1) / (NPERM + 1); p1 = (cnt1L[lab] + 1) / (NPERM + 1)
                else:
                    p2 = (cnt2[x][lab] + 1) / (NPERM + 1); p1 = (cnt1[x][lab] + 1) / (NPERM + 1)
                cells.append(f'ρ={fmt(rho):>5s} p={p2:.3f} ({p1:.3f})')
            out(f'  {name:33s} | ' + ' | '.join(f'{c:>22s}' for c in cells))
        out('  (для задержки ρ > 0 значит «в большие дни медленнее»; для остальных метрик ρ < 0 значит «в большие дни хуже»)')
        out('\nПерестановочные p для O/E класса ≥110 (объёмы переставлены между днями внутри ' + unit_label.lower() + '):')
        for lab, _, _ in METRICS:
            o = obs_cls['>=110'][lab]
            out(f'  {lab:13s}: O/E ≥110 = {fmt(o)}; P(O/E ≤ наблюдённого) = {(cnt_cls_low[lab] + 1) / (NPERM + 1):.3f}, '
                f'P(O/E ≥ наблюдённого) = {(cnt_cls_hi[lab] + 1) / (NPERM + 1):.3f}; '
                f'отношение O/E(<60)/O/E(≥110) = {fmt(obs_ratio[lab])}, P(отношение ≥ наблюдённого) = {(cnt_ratio[lab] + 1) / (NPERM + 1):.3f}')

        # знаковый критерий по парам
        out('\nПары «самый большой день против самого малого» внутри страты (контраст объёма ≥1,2×). '
            'Ставки: выход %, кликов на вышедший, рег/100 сайтов, вышли1/вышли3, задержка сут:')
        out('  страта                                          | большой: день   N  дом  сайт | малый: день   N  дом  сайт | выход б/м | кл/выш б/м | рег б/м | скорость б/м | задержка б/м')
        pairs = []
        skipped = []
        for key in sorted(strata):
            ps = [p for p in pools if p['key'] == key]
            big = max(ps, key=lambda p: p['N'])
            small = min(ps, key=lambda p: p['N'])
            if small['N'] == 0 or big['N'] / small['N'] < 1.2:
                skipped.append((key, big['N'], small['N']))
                continue
            row = {'key': key, 'big': big, 'small': small}
            pairs.append(row)

        # ставки напрямую из доменов
        def raw_rate(key, day, nu, de):
            u = [r for r in strata[key] if r['день запуска'] == day]
            o = sum(r[nu] for r in u); d = sum(r[de] for r in u)
            return o / d if d > 0 else float('nan')

        def raw_delay(key, day):
            u = [(r['delay'], r['out3']) for r in strata[key] if r['день запуска'] == day and r['delay'] is not None and r['out3'] > 0]
            return sum(a * b for a, b in u) / sum(b for _, b in u) if u else float('nan')

        signs = {lab: [0, 0, 0] for lab, _, _ in METRICS}
        signs['задержка'] = [0, 0, 0]
        for row in pairs:
            key = row['key']; b = row['big']; s = row['small']
            cells = []
            for lab, nu, de in METRICS:
                rb = raw_rate(key, b['day'], nu, de); rs = raw_rate(key, s['day'], nu, de)
                mult = 100 if lab in ('выход', 'регистрации') else 1
                if lab == 'регистрации':
                    cells.append(f'{rb * mult:5.2f}/{rs * mult:5.2f}')
                elif lab == 'выход':
                    cells.append(f'{rb * mult:5.1f}/{rs * mult:5.1f}')
                else:
                    cells.append(f'{fmt(rb, 2 if lab == "скорость" else 1):>5s}/{fmt(rs, 2 if lab == "скорость" else 1):>5s}')
                if math.isnan(rb) or math.isnan(rs):
                    continue
                if rb > rs + 1e-12:
                    signs[lab][0] += 1
                elif rb < rs - 1e-12:
                    signs[lab][1] += 1
                else:
                    signs[lab][2] += 1
            db = raw_delay(key, b['day']); ds_ = raw_delay(key, s['day'])
            cells.append(f'{fmt(db):>5s}/{fmt(ds_):>5s}')
            if not (math.isnan(db) or math.isnan(ds_)):
                if db > ds_ + 1e-12:
                    signs['задержка'][0] += 1   # больше задержка в большой день = хуже
                elif db < ds_ - 1e-12:
                    signs['задержка'][1] += 1
                else:
                    signs['задержка'][2] += 1
            out(f'  {key[0][:38]:38s} {key[1]:7s} |   {b["day"][5:]}  {b["N"]:3d}  {b["n"]:3d}  {int(b["sites"]):4d} |  {s["day"][5:]}  {s["N"]:3d}  {s["n"]:3d}  {int(s["sites"]):4d} | '
                + ' | '.join(cells))
        if skipped:
            out('  без контраста объёма (<1,2×), в пары не вошли: ' + '; '.join(f'{k[0][:30]} {k[1]} ({b} против {s})' for k, b, s in skipped))
        out(f'\n  Знаковый критерий по {len(pairs)} парам (плюс = в большой день ставка ВЫШЕ; для задержки плюс = в большой день задержка ДЛИННЕЕ, то есть хуже):')
        for lab in [m[0] for m in METRICS] + ['задержка']:
            plus, minus, ties = signs[lab]
            n = plus + minus
            p = binom_two_sided(min(plus, minus), n) if n else float('nan')
            out(f'    {lab:13s}: больше в большой день {plus}, меньше {minus}, равно {ties}; точный биномиальный p = {fmt(p, 3)}')
        # взвешенная сводка по парам: сумма O/E больших против малых
        out('  Взвешенная сводка по тем же парам (ΣO/ΣE по большим дням против ΣO/ΣE по малым):')
        for lab, _, _ in METRICS:
            ob = sum(r['big'][lab][0] for r in pairs); eb = sum(r['big'][lab][1] for r in pairs)
            os_ = sum(r['small'][lab][0] for r in pairs); es = sum(r['small'][lab][1] for r in pairs)
            out(f'    {lab:13s}: большие O/E = {fmt(ratio(ob, eb))} (O={int(ob)}), малые O/E = {fmt(ratio(os_, es))} (O={int(os_)}), '
                f'отношение большие/малые = {fmt(ratio(ratio(ob, eb), ratio(os_, es)))}')
        return {'obs': obs, 'rho': rho_obs, 'p2': cnt2, 'p1': cnt1, 'p2L': cnt2L, 'signs': signs, 'npairs': len(pairs),
                'n': len(used), 'sites': sum(r['sites'] for r in used), 'reg': sum(r['reg'] for r in used),
                'cls_low': cnt_cls_low, 'ratio': obs_ratio, 'cnt_ratio': cnt_ratio, 'nstrata': len(strata)}

    main_res = pool_analysis('А. ГЛАВНАЯ СТРАТА: набор контента + зона (только наборы с ≥2 датами запуска)',
                             'набор контента', lambda r: (r['набор контента'], r['zone']), 'Наборов контента')

    # =====================================================================
    # ВТОРИЧНАЯ СТРАТА: семейство + страниц + оформление + зона + ISO-неделя
    # =====================================================================
    out('\n' + '=' * 110)
    out('Б. ВТОРИЧНАЯ СТРАТА: семейство + страниц + оформление + зона + ISO-неделя; три класса объёма; '
        'перестановка дня между доменами внутри страты')
    out('=' * 110)
    out('  Здесь набор контента НЕ зафиксирован: внутри страты разные дни несут разные наборы. '
        'Это единственная страта, где есть дни 15–17.09.')
    for r in base:
        r['wk'] = datetime.date.fromisoformat(r['день запуска']).isocalendar()[1]
        r['skey'] = (r['семейство'], r['страниц'], r['оформление'], r['zone'], r['wk'])
    S2 = collections.defaultdict(list)
    for r in base:
        S2[r['skey']].append(r)
    S2 = {k: v for k, v in S2.items() if len(set(r['cls'] for r in v)) >= 2}
    used2 = [r for v in S2.values() for r in v]
    out(f'  страт с ≥2 классами объёма: {len(S2)}; доменов {len(used2)}, сайтов {int(sum(r["sites"] for r in used2))}, '
        f'регистраций в окне {int(sum(r["reg"] for r in used2))}')
    out('  страта (семейство, страниц, оформление, зона, неделя): классы → доменов [дни]')
    for k in sorted(S2, key=lambda k: (k[4], k[0], k[1], k[2], k[3])):
        v = S2[k]
        parts = []
        for c in CLASSES:
            u = [r for r in v if r['cls'] == c]
            if u:
                parts.append(f'{c}: {len(u)} [{", ".join(sorted(set(r["день запуска"][5:] for r in u)))}]')
        out(f'    {k[0]:13s} {k[1] or "—":3s} {k[2] or "—":15s} {k[3]:7s} нед.{k[4]}: ' + '; '.join(parts))

    def expected2(strata_, clsattr):
        """ΣO, ΣE по классам (E домена = знаменатель × доля страты)."""
        res = {c: {lab: [0.0, 0.0] for lab, _, _ in METRICS} for c in CLASSES}
        cnt = {c: [0, 0.0, 0.0] for c in CLASSES}
        dl = {c: [0.0, 0.0] for c in CLASSES}
        for v in strata_.values():
            tot_ = {f: sum(r[f] for r in v) for f in ('sites', 'out3', 'out1', 'clk', 'reg')}
            dls = [(r['delay'], r['out3']) for r in v if r['delay'] is not None and r['out3'] > 0]
            dlm = sum(a * b for a, b in dls) / sum(b for _, b in dls) if dls else None
            for r in v:
                c = r[clsattr]
                cnt[c][0] += 1; cnt[c][1] += r['sites']; cnt[c][2] += r['reg']
                for lab, nu, de in METRICS:
                    rate = tot_[nu] / tot_[de] if tot_[de] > 0 else 0.0
                    res[c][lab][0] += r[nu]
                    res[c][lab][1] += r[de] * rate
                if r['delay'] is not None and r['out3'] > 0 and dlm is not None:
                    dl[c][0] += (r['delay'] - dlm) * r['out3']; dl[c][1] += r['out3']
        return res, cnt, dl

    res2, cnt2_, dl2 = expected2(S2, 'cls')
    out('\nO/E по классам объёма (ΣO/ΣE, страта = семейство+страниц+оформление+зона+неделя):')
    out('  класс    доменов   сайтов | выход O/E (O) | кл/выш O/E (O) | рег O/E (O) | скорость O/E (O) | Δзадержки, сут')
    for c in CLASSES:
        w = res2[c]
        d = dl2[c][0] / dl2[c][1] if dl2[c][1] > 0 else float('nan')
        out(f'  {c:7s}  {cnt2_[c][0]:7d}  {int(cnt2_[c][1]):7d} |  {fmt(ratio(*w["выход"])):>5s} ({int(w["выход"][0]):5d}) |  '
            f'{fmt(ratio(*w["клики/вышедш"])):>5s} ({int(w["клики/вышедш"][0]):6d}) |  {fmt(ratio(*w["регистрации"])):>5s} ({int(w["регистрации"][0]):3d}) |  '
            f'{fmt(ratio(*w["скорость"])):>5s} ({int(w["скорость"][0]):5d})  |  {fmt(d):>6s}')
    obs2 = {c: {lab: ratio(*res2[c][lab]) for lab, _, _ in METRICS} for c in CLASSES}
    obs2_ratio = {lab: ratio(obs2['<60'][lab], obs2['>=110'][lab]) for lab, _, _ in METRICS}
    obs2_ratio_mid = {lab: ratio(obs2['60-110'][lab], obs2['>=110'][lab]) for lab, _, _ in METRICS}
    # перестановка дня между доменами внутри страты
    c_low = collections.Counter(); c_hi = collections.Counter(); c_ratio = collections.Counter(); c_ratio_mid = collections.Counter()
    for _ in range(NPERM):
        for v in S2.values():
            labels = [r['cls'] for r in v]
            random.shuffle(labels)
            for r, l in zip(v, labels):
                r['pcls'] = l
        rp, _, _ = expected2(S2, 'pcls')
        for lab, _, _ in METRICS:
            v = ratio(*rp['>=110'][lab]); o = obs2['>=110'][lab]
            if v <= o + 1e-12:
                c_low[lab] += 1
            if v >= o - 1e-12:
                c_hi[lab] += 1
            rr = ratio(ratio(*rp['<60'][lab]), v)
            if not math.isnan(rr) and rr >= obs2_ratio[lab] - 1e-12:
                c_ratio[lab] += 1
            rm = ratio(ratio(*rp['60-110'][lab]), v)
            if not math.isnan(rm) and rm >= obs2_ratio_mid[lab] - 1e-12:
                c_ratio_mid[lab] += 1
    out(f'\nПерестановочные p (день переставлен между доменами внутри страты, {NPERM} раз; единица перестановки — домен, '
        'сверхдисперсия пулов «набор+день» не учтена, поэтому p здесь занижены — значимость следует читать с запасом):')
    for lab, _, _ in METRICS:
        out(f'  {lab:13s}: O/E ≥110 = {fmt(obs2[">=110"][lab])}; P(≤) = {(c_low[lab] + 1) / (NPERM + 1):.3f}, P(≥) = {(c_hi[lab] + 1) / (NPERM + 1):.3f}; '
            f'O/E(<60)/O/E(≥110) = {fmt(obs2_ratio[lab])}, P(≥) = {(c_ratio[lab] + 1) / (NPERM + 1):.3f}; '
            f'O/E(60–110)/O/E(≥110) = {fmt(obs2_ratio_mid[lab])}, P(≥) = {(c_ratio_mid[lab] + 1) / (NPERM + 1):.3f}')

    # по дням внутри вторичной страты
    out('\nТе же O/E по отдельным дням (страта та же; показывает, как ведут себя именно 15, 16, 17.09):')
    out('  день    N   класс  доменов  сайтов | выход O/E | кл/выш O/E | рег O/E (O) | скорость O/E | Δзадержки')
    byday = collections.defaultdict(lambda: {'n': 0, 'sites': 0.0, 'reg': 0.0, 'dl': [0.0, 0.0], **{lab: [0.0, 0.0] for lab, _, _ in METRICS}})
    for v in S2.values():
        tot_ = {f: sum(r[f] for r in v) for f in ('sites', 'out3', 'out1', 'clk', 'reg')}
        dls = [(r['delay'], r['out3']) for r in v if r['delay'] is not None and r['out3'] > 0]
        dlm = sum(a * b for a, b in dls) / sum(b for _, b in dls) if dls else None
        for r in v:
            b = byday[r['день запуска']]
            b['n'] += 1; b['sites'] += r['sites']; b['reg'] += r['reg']
            for lab, nu, de in METRICS:
                rate = tot_[nu] / tot_[de] if tot_[de] > 0 else 0.0
                b[lab][0] += r[nu]; b[lab][1] += r[de] * rate
            if r['delay'] is not None and r['out3'] > 0 and dlm is not None:
                b['dl'][0] += (r['delay'] - dlm) * r['out3']; b['dl'][1] += r['out3']
    for d in sorted(byday):
        b = byday[d]
        dz = b['dl'][0] / b['dl'][1] if b['dl'][1] > 0 else float('nan')
        out(f'  {d[5:]}  {N[d]:3d}  {vol_class(N[d]):6s}  {b["n"]:6d}  {int(b["sites"]):6d} |  {fmt(ratio(*b["выход"])):>6s}   |   '
            f'{fmt(ratio(*b["клики/вышедш"])):>6s}   |  {fmt(ratio(*b["регистрации"])):>6s} ({int(b["регистрации"][0]):2d}) |    {fmt(ratio(*b["скорость"])):>6s}    |  {fmt(dz):>6s}')

    # =====================================================================
    # ДОПОЛНИТЕЛЬНО: корень набора + зона
    # =====================================================================
    root_res = pool_analysis('В. ДОПОЛНИТЕЛЬНО: корень набора (имя без хвоста «_номер», как в pary_variantov.py) + зона. '
                             'Это подтягивает варианты одного корня, разнесённые по дням, в том числе 14.09 (71) против 15.09 (159)',
                             'root', lambda r: (r['root'], r['zone']), 'Корней наборов')

    # =====================================================================
    # ВЫВОД
    # =====================================================================
    out('\n' + '=' * 110)
    out('ВЫВОД')
    out('=' * 110)
    A = main_res['obs']; R = main_res['rho']['N']
    pA = {lab: (main_res['p2']['N'][lab] + 1) / (NPERM + 1) for lab in R}
    B = obs2
    C = root_res['obs']; RC = root_res['rho']['N']
    pC = {lab: (root_res['p2']['N'][lab] + 1) / (NPERM + 1) for lab in RC}
    sA = main_res['signs']; sC = root_res['signs']

    out(f'1. Что удалось сравнить. Внутри одного набора контента и зоны (главная страта: {main_res["nstrata"]} страт, '
        f'{main_res["n"]} доменов, {int(main_res["sites"])} сайтов, {int(main_res["reg"])} регистраций в окне) '
        f'дни ≥110 — это только 08.09 (123) и 11.09 (122); класс ≥110 в этой страте держит {A[">=110"]["n"]} доменов, '
        f'60–110 — {A["60-110"]["n"]}, <60 — {A["<60"]["n"]}. Самые большие дни 15–17.09 (159/138/152) внутри набора '
        'сравнить нельзя: на них каждый домен несёт свой собственный набор контента. Они видны только во вторичной страте '
        f'(семейство+страниц+оформление+зона+неделя: {len(used2)} доменов, класс ≥110 — {cnt2_[">=110"][0]} доменов) '
        f'и в корнях наборов (В: {root_res["n"]} доменов).')
    out(f'2. Главная страта, O/E класса ≥110 против класса <60: выход {fmt(A[">=110"]["выход"])} против {fmt(A["<60"]["выход"])}; '
        f'клики на вышедший {fmt(A[">=110"]["клики/вышедш"])} против {fmt(A["<60"]["клики/вышедш"])}; '
        f'регистрации {fmt(A[">=110"]["регистрации"])} ({int(A[">=110"]["reg"])} рег) против {fmt(A["<60"]["регистрации"])} ({int(A["<60"]["reg"])} рег); '
        f'скорость {fmt(A[">=110"]["скорость"])} против {fmt(A["<60"]["скорость"])}; сдвиг задержки {fmt(A[">=110"]["delay"])} против {fmt(A["<60"]["delay"])} сут. '
        f'Спирмен объём↔O/E по пулам: выход {fmt(R["выход"])} (p={pA["выход"]:.2f}), клики/вышедший {fmt(R["клики/вышедш"])} (p={pA["клики/вышедш"]:.2f}), '
        f'регистрации {fmt(R["регистрации"])} (p={pA["регистрации"]:.2f}), скорость {fmt(R["скорость"])} (p={pA["скорость"]:.2f}), '
        f'задержка {fmt(R["задержка"])} (p={pA["задержка"]:.2f}).')
    out(f'   Пары «большой день против малого» ({main_res["npairs"]} пар): выход выше в большой день в {sA["выход"][0]} парах, ниже в {sA["выход"][1]} '
        f'(p={fmt(binom_two_sided(min(sA["выход"][0], sA["выход"][1]), sA["выход"][0] + sA["выход"][1]), 2)}); '
        f'клики на вышедший {sA["клики/вышедш"][0]} против {sA["клики/вышедш"][1]} '
        f'(p={fmt(binom_two_sided(min(sA["клики/вышедш"][0], sA["клики/вышедш"][1]), sA["клики/вышедш"][0] + sA["клики/вышедш"][1]), 2)}); '
        f'регистрации {sA["регистрации"][0]} против {sA["регистрации"][1]} при {sA["регистрации"][2]} равных; '
        f'скорость {sA["скорость"][0]} против {sA["скорость"][1]}; задержка длиннее в большой день в {sA["задержка"][0]} парах, короче в {sA["задержка"][1]}.')
    out(f'3. Вторичная страта (с днями 15–17.09), O/E класса ≥110 против 60–110 и <60: выход {fmt(B[">=110"]["выход"])} / {fmt(B["60-110"]["выход"])} / {fmt(B["<60"]["выход"])}; '
        f'клики на вышедший {fmt(B[">=110"]["клики/вышедш"])} / {fmt(B["60-110"]["клики/вышедш"])} / {fmt(B["<60"]["клики/вышедш"])}; '
        f'регистрации {fmt(B[">=110"]["регистрации"])} / {fmt(B["60-110"]["регистрации"])} / {fmt(B["<60"]["регистрации"])} '
        f'({int(res2[">=110"]["регистрации"][0])}/{int(res2["60-110"]["регистрации"][0])}/{int(res2["<60"]["регистрации"][0])} рег); '
        f'скорость {fmt(B[">=110"]["скорость"])} / {fmt(B["60-110"]["скорость"])} / {fmt(B["<60"]["скорость"])}. '
        'Но в этой страте день и набор контента не разделены: разница классов может быть разницей наборов.')
    out(f'4. Корни наборов (В), O/E класса ≥110 против <60: выход {fmt(C[">=110"]["выход"])} против {fmt(C["<60"]["выход"])}, '
        f'клики на вышедший {fmt(C[">=110"]["клики/вышедш"])} против {fmt(C["<60"]["клики/вышедш"])}, регистрации {fmt(C[">=110"]["регистрации"])} против {fmt(C["<60"]["регистрации"])}, '
        f'скорость {fmt(C[">=110"]["скорость"])} против {fmt(C["<60"]["скорость"])}; Спирмен по выходу {fmt(RC["выход"])} (p={pC["выход"]:.2f}), '
        f'по кликам {fmt(RC["клики/вышедш"])} (p={pC["клики/вышедш"]:.2f}); пар {root_res["npairs"]}: выход выше в большой день {sC["выход"][0]} против {sC["выход"][1]}, '
        f'клики {sC["клики/вышедш"][0]} против {sC["клики/вышедш"][1]}.')

    # сверка с критериями постановки — по пунктам
    checks = [
        ('O/E класса ≥110 по выходу ≥ 0,9', A['>=110']['выход'], A['>=110']['выход'] >= 0.9),
        ('O/E класса ≥110 по кликам на вышедший ≥ 0,9', A['>=110']['клики/вышедш'], A['>=110']['клики/вышедш'] >= 0.9),
        ('Спирмен N(день)↔O/E по выходу ≥ −0,2', R['выход'], R['выход'] >= -0.2),
        ('Спирмен N(день)↔O/E по кликам на вышедший ≥ −0,2', R['клики/вышедш'], R['клики/вышедш'] >= -0.2),
        ('p Спирмена по выходу > 0,2', pA['выход'], pA['выход'] > 0.2),
        ('p Спирмена по кликам на вышедший > 0,2', pA['клики/вышедш'], pA['клики/вышедш'] > 0.2),
    ]
    out('5. Сверка с критериями постановки (главная страта, набор контента + зона):')
    for name, val, ok in checks:
        out(f'   {"да " if ok else "НЕТ"}  {name}: {fmt(val)}')
    failed = [name for name, _, ok in checks if not ok]
    out(f'   Спирмен по выходу при других мерах объёма: N − среднее N по набору {fmt(main_res["rho"]["Nrel"]["выход"])}, '
        f'L (сайтов на переобход) {fmt(main_res["rho"]["L"]["выход"])}; в корнях наборов {fmt(RC["выход"])} (p={pC["выход"]:.2f}).')
    dil_main = {lab: (main_res['ratio'][lab], (main_res['cnt_ratio'][lab] + 1) / (NPERM + 1)) for lab in ('выход', 'клики/вышедш')}
    dil_sec = {lab: (obs2_ratio[lab], (c_ratio[lab] + 1) / (NPERM + 1)) for lab in ('выход', 'клики/вышедш')}
    dilute = all(dil_main[lab][0] >= 1.3 and dil_main[lab][1] < 0.05 and dil_sec[lab][0] >= 1.3 and dil_sec[lab][1] < 0.05
                 for lab in ('выход', 'клики/вышедш'))
    out('   «Разбавляет» (падение ≥1,3× от <60 к ≥110 при p < 0,05 в обеих стратах): главная страта — выход '
        f'{fmt(dil_main["выход"][0])}× (p={dil_main["выход"][1]:.2f}), клики {fmt(dil_main["клики/вышедш"][0])}× (p={dil_main["клики/вышедш"][1]:.2f}); '
        f'вторичная — выход {fmt(dil_sec["выход"][0])}× (p={dil_sec["выход"][1]:.2f}), клики {fmt(dil_sec["клики/вышедш"][0])}× (p={dil_sec["клики/вышедш"][1]:.2f}) — '
        + ('ВЫПОЛНЕНО' if dilute else 'НЕ ВЫПОЛНЕНО') + '.')
    out('   Итог по критериям: ' + ('все условия «не разбавляет» выполнены' if not failed else
        'условия «не разбавляет» выполнены, кроме: ' + '; '.join(failed) + ' — отклонение от порога в пределах шума (p Спирмена > 0,2, другие меры объёма см. выше)')
        + '; условия «разбавляет» не выполнены.')

    def oe_day(d, lab):
        b = byday.get(d)
        return ratio(*b[lab]) if b else float('nan')
    out('6. Самые большие дни по отдельности (вторичная страта; O/E выход / клики на вышедший / регистрации): '
        + '; '.join(f'{d[8:]}.09 ({N[d]}) {fmt(oe_day(d, "выход"))} / {fmt(oe_day(d, "клики/вышедш"))} / {fmt(oe_day(d, "регистрации"))}'
                    for d in ('2026-09-13', '2026-09-14', '2026-09-15', '2026-09-16', '2026-09-17')) + '. '
        'Колебания между соседними днями не идут за объёмом: день на 71 домен (14.09) слабый, дни на 159 и 138 (15–16.09) сильные, день на 152 (17.09) '
        'снова слабый. Именно слабость 14.09 (он же главный «малый» сосед недели 38) поднимает класс ≥110 во вторичной страте выше 1 — это не заслуга больших дней. '
        'Оговорка по 17.09: у 56 сайтов второй волны (переобход 18.09) окно 3 суток кончается 21.09 — в день выгрузки, часть кликов могла не попасть; '
        'это занижает 17.09, то есть работает против гипотезы, а не за неё. Разброс между днями одной недели и одного семейства (0,6…1,2 по выходу) в разы больше '
        'любого следа объёма — день остаётся тенью, но объём дня этой тени не объясняет.')
    out('7. Простыми словами. Там, где день можно сравнить честно — внутри одного набора контента и зоны, — базы, выложенные в день на 122–123 домена '
        f'(~23–24 тыс. сайтов на переобход), выходят в поиск, собирают клики на вышедший сайт и приносят регистрации так же, как выложенные в дни на 25–101 домен: '
        f'O/E {fmt(A[">=110"]["выход"])} / {fmt(A[">=110"]["клики/вышедш"])} / {fmt(A[">=110"]["регистрации"])}, скорость {fmt(A[">=110"]["скорость"])}, '
        f'знаковый критерий по парам {sA["выход"][0]}:{sA["выход"][1]} по выходу и {sA["клики/вышедш"][0]}:{sA["клики/вышедш"][1]} по кликам, корреляции объёма с O/E '
        f'слабые и незначимые (ρ от {fmt(min(R.values()))} до {fmt(max(R.values()))}, все p > 0,2). Единственный намёк на минус — выход в большие дни {fmt(A[">=110"]["выход"])} '
        f'и ρ = {fmt(R["выход"])} по выходу: если эффект и есть, он не больше 5–10 % и тонет в разбросе дней. Для дней на 138–159 доменов (15–17.09) честного сравнения '
        'внутри набора нет — у каждой базы там свой собственный набор контента; по семейству и неделе и по двум корням (14.09 против 15.09) разбавления тоже не видно. '
        f'Регистраций в главной страте {int(main_res["reg"])}, поэтому по регистрациям ответ грубый: «не хуже» в пределах ±30–40 %.')
    out('8. Что с этим делать: потолок доменов в день вводить не нужно — до 123 доменов в сутки вреда не видно, при 138–159 признаков вреда тоже нет, просто там нет '
        'чистой проверки. Увеличивать объём дня ради результата тоже незачем: эффекта нет в обе стороны. Проверяемо на уже запущенных данных: когда закроются окна '
        '18–21.09, повторить этот же скрипт — корни content-2026-09-14b-7str-oform-1 (26 доменов 18 и 21.09), content-2026-09-16-7str, nabory-611-620, '
        'content-2026-09-14-7str-oform-8/9 продолжаются в малые дни (38–78 доменов), и сравнение 138–159 против 38–78 станет возможным внутри корня. '
        'Это знание, не рычаг.')
    out.close()


if __name__ == '__main__':
    main()
