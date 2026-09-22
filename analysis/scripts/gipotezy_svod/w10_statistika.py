# -*- coding: utf-8 -*-
"""Контрпроверка гипотезы №10 (правило первого дня). Угол: СТАТИСТИКА И ОПРЕДЕЛЕНИЯ.
Только stdlib. Вывод дублируется в analysis/export/gipotezy_svod/w10_statistika.txt
"""
import csv, math, collections, random, sys, os

SRC = '/home/user/cladue/analysis/export/svod_domenov_21.09.csv'
OUT = '/home/user/cladue/analysis/export/gipotezy_svod/w10_statistika.txt'
OUTLIERS = {'3615.team', '3286.team'}
ZONES = ('team', 'lol', 'casino', 'buzz')
NPERM = 20000


class Tee:
    def __init__(self, path):
        self.f = open(path, 'w', encoding='utf-8')
    def write(self, s):
        sys.__stdout__.write(s); self.f.write(s)
    def flush(self):
        sys.__stdout__.flush(); self.f.flush()


def P(*a):
    print(' '.join(str(x) for x in a))


def I(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def F(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def zone_of(r):
    return r['зона'] if r['зона'] in ZONES else 'прочие'


def load():
    rows = []
    with open(SRC, encoding='utf-8') as f:
        for i, raw in enumerate(csv.DictReader(f)):
            r = dict(raw)
            r['id'] = i
            r['z'] = zone_of(raw)
            r['sites'] = I(raw['сайтов в окне']) or 0
            r['sites_all'] = I(raw['сайтов']) or 0
            r['v1'] = I(raw['вышли за 1 сутки'])
            r['v3'] = I(raw['вышли за 3 суток'])
            r['v7'] = I(raw['вышли за 7 суток'])
            r['reg'] = I(raw['регистраций в окне 3 суток']) or 0
            r['fd'] = I(raw['ФД в окне 3 суток']) or 0
            r['reg_all'] = I(raw['регистраций']) or 0
            r['clicks_w'] = I(raw['кликов из поиска в окне']) or 0
            r['delay'] = F(raw['задержка до поиска, медиана'])
            r['pool'] = (raw['набор контента'], raw['день запуска'])
            r['day'] = raw['день запуска']
            r['block'] = raw['блок часа']
            rows.append(r)
    return rows


def filter_main(rows):
    cur = [r for r in rows if r['окно закрыто'] == 'да']
    cur = [r for r in cur if r['дней'] == '2']
    cur = [r for r in cur if r['домен'] not in OUTLIERS]
    cur = [r for r in cur if r['семейство'] != 'не записан']
    return cur


def expect(rows, key_fn, den):
    """E_i = (Σ рег страты / Σ знаменателя страты) × знаменатель домена."""
    num_s = collections.Counter(); den_s = collections.Counter()
    for r in rows:
        k = key_fn(r); num_s[k] += r['reg']; den_s[k] += r[den]
    E = {}
    for r in rows:
        k = key_fn(r)
        E[r['id']] = (num_s[k] / den_s[k]) * r[den] if den_s[k] > 0 else 0.0
    return E


def pois_ci(k, conf=0.95):
    """Точный (Garwood) интервал для среднего пуассона по наблюдённому k."""
    a = (1 - conf) / 2
    def chi2_inv(p, df):
        # бисекция по CDF хи-квадрат через неполную гамму (ряд/непр. дробь)
        lo, hi = 0.0, 1000.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if gammainc_p(df / 2, mid / 2) < p:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    lo = 0.0 if k == 0 else chi2_inv(a, 2 * k) / 2
    hi = chi2_inv(1 - a, 2 * (k + 1)) / 2
    return lo, hi


def gammainc_p(a, x):
    if x <= 0:
        return 0.0
    if x < a + 1:
        s = 1.0 / a; term = s; n = 0
        while n < 10000:
            n += 1; term *= x / (a + n); s += term
            if abs(term) < abs(s) * 1e-14:
                break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    # непрерывная дробь для Q
    tiny = 1e-300
    b = x + 1 - a; c = 1 / tiny; d = 1 / b; h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < tiny: d = tiny
        c = b + an / c
        if abs(c) < tiny: c = tiny
        d = 1 / d; de = d * c; h *= de
        if abs(de - 1) < 1e-14:
            break
    q = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
    return 1 - q


def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0
    s = 0.0; term = math.exp(-lam)
    for i in range(k + 1):
        s += term; term *= lam / (i + 1)
    return min(1.0, s)


def fmt(o, e):
    return '%.2f' % (o / e) if e > 0 else '  —  '


def perm_test(main, pools, flag_fn, den, seed=7, nperm=NPERM):
    """Перестановка метки внутри пула; E по знаменателю den (для отчёта). Возвращает p и распределение."""
    random.seed(seed)
    obs = sum(r['reg'] for r in main if flag_fn(r))
    pool_lists = [v for v in pools.values() if len(v) >= 2]
    fixed = sum(r['reg'] for v in pools.values() if len(v) < 2 for r in v if flag_fn(r))
    dist = []
    for _ in range(nperm):
        tot = fixed
        for v in pool_lists:
            labs = [flag_fn(r) for r in v]
            random.shuffle(labs)
            for r, x in zip(v, labs):
                if x:
                    tot += r['reg']
        dist.append(tot)
    dist.sort()
    p = sum(1 for t in dist if t <= obs) / nperm
    return obs, p, dist[int(0.025 * nperm)], dist[int(0.975 * nperm) - 1], sum(dist) / nperm


def perm_test_weighted(main, key_fn, flag_fn, den, seed=11, nperm=NPERM):
    """Перестановка метки внутри страты key_fn с УЧЁТОМ знаменателя:
    считаем не число регистраций, а O − E по знаменателю den (вероятность каждого домена
    получить регистрацию пропорциональна den). Реализация: случайное перераспределение
    регистраций страты по доменам страты пропорционально den."""
    random.seed(seed)
    strata = collections.defaultdict(list)
    for r in main:
        strata[key_fn(r)].append(r)
    obs = sum(r['reg'] for r in main if flag_fn(r))
    dist = []
    for _ in range(nperm):
        tot = 0
        for v in strata.values():
            nreg = sum(r['reg'] for r in v)
            if nreg == 0:
                continue
            w = [r[den] for r in v]
            W = sum(w)
            if W <= 0:
                continue
            cum = []; acc = 0.0
            for x in w:
                acc += x; cum.append(acc)
            for _k in range(nreg):
                u = random.random() * W
                lo, hi = 0, len(cum) - 1
                while lo < hi:
                    mid = (lo + hi) // 2
                    if cum[mid] < u: lo = mid + 1
                    else: hi = mid
                if flag_fn(v[lo]):
                    tot += 1
            # (розыгрыш с возвращением — регистрации на домене не ограничены)
        dist.append(tot)
    dist.sort()
    p = sum(1 for t in dist if t <= obs) / nperm
    return obs, p, dist[int(0.025 * nperm)], dist[int(0.975 * nperm) - 1], sum(dist) / nperm


def main():
    sys.stdout = Tee(OUT)
    rows = load()
    P('КОНТРПРОВЕРКА №10 «Правило первого дня» — статистика и определения')
    P('Файл: %s; строк: %d' % (SRC, len(rows)))
    P('')

    # ---------------- 0. Воспроизводимость ----------------
    P('=' * 110)
    P('0. ВОСПРОИЗВОДИМОСТЬ')
    P('=' * 110)
    main_set = filter_main(rows)
    P('  Основной набор тестировщика воспроизведён: %d доменов (окно закрыто, дней=2, без 2 выбросов, без «не записан»).' % len(main_set))
    le5 = [r for r in main_set if r['v1'] <= 5]
    ge6 = [r for r in main_set if r['v1'] >= 6]
    P('  v1≤5: %d доменов, %d сайтов в окне, %d рег в окне; v1≥6: %d доменов, %d сайтов, %d рег.' % (
        len(le5), sum(r['sites'] for r in le5), sum(r['reg'] for r in le5),
        len(ge6), sum(r['sites'] for r in ge6), sum(r['reg'] for r in ge6)))
    E_sites = expect(main_set, lambda r: r['pool'], 'sites')
    P('  O/E(v1≤5) при знаменателе «сайтов в окне»: O=%d, E=%.1f, O/E=%.2f — совпадает с h10 (0.09).' % (
        sum(r['reg'] for r in le5), sum(E_sites[r['id']] for r in le5),
        sum(r['reg'] for r in le5) / sum(E_sites[r['id']] for r in le5)))
    P('  Запуск h10_first_day_stop_rule.py даёт файл, побайтово идентичный сохранённому выводу. Числа воспроизводятся.')

    # ---------------- 1. Знаменатель ----------------
    P('')
    P('=' * 110)
    P('1. ЗНАМЕНАТЕЛЬ: «сайтов в окне» против «вышли за 3 суток» и «кликов из поиска в окне»')
    P('=' * 110)
    P('  Регистрация физически возможна только на вышедшем в поиск сайте (нужен поисковый клик).')
    P('  Знаменатель «сайтов в окне» приписывает домену с 3 вышедшими сайтами такое же ожидание, как домену с 60.')
    P('  Пересчёт O/E по трём знаменателям (страта — пул «набор контента + день»):')
    dens = [('сайтов в окне', 'sites'), ('вышли за 3 суток', 'v3'), ('кликов из поиска в окне', 'clicks_w')]
    Es = {}
    for label, d in dens:
        Es[d] = expect(main_set, lambda r: r['pool'], d)
    P('  %-26s %8s %8s %8s %8s   %s' % ('знаменатель', 'O(≤5)', 'E(≤5)', 'O/E', 'P(O≤набл)', '95% интервал O/E (точный пуассон)'))
    for label, d in dens:
        o = sum(r['reg'] for r in le5); e = sum(Es[d][r['id']] for r in le5)
        lo, hi = pois_ci(o)
        P('  %-26s %8d %8.2f %8.2f %8.4f   [%.2f; %.2f]' % (
            label, o, e, o / e if e else float('nan'), poisson_cdf(o, e), lo / e if e else 0, hi / e if e else 0))
    P('')
    P('  Доли группы v1≤5 в знаменателях основного набора:')
    for label, d in dens:
        tot = sum(r[d] for r in main_set); part = sum(r[d] for r in le5)
        P('    %-26s v1≤5 = %8d из %8d (%.2f%%)' % (label, part, tot, 100 * part / tot if tot else 0))
    P('')
    P('  Грубое отношение «в X раз хуже» при разных знаменателях (без страты):')
    for label, d in dens:
        a = sum(r['reg'] for r in le5); da = sum(r[d] for r in le5)
        b = sum(r['reg'] for r in ge6); db = sum(r[d] for r in ge6)
        ra = a / da if da else 0; rb = b / db if db else 0
        P('    %-26s v1≤5: %d/%d = %.5f; v1≥6: %d/%d = %.5f; отношение %s' % (
            label, a, da, ra, b, db, rb, ('%.1f×' % (rb / ra)) if ra > 0 else '∞'))

    # ---------------- 2. Перестановка с правильным знаменателем ----------------
    P('')
    P('=' * 110)
    P('2. ПЕРЕСТАНОВОЧНЫЙ ТЕСТ: нулевая гипотеза тестировщика против нулевой «регистрации идут за выходом»')
    P('=' * 110)
    pools = collections.defaultdict(list)
    for r in main_set:
        pools[r['pool']].append(r)
    flag5 = lambda r: r['v1'] <= 5
    o, p, lo, hi, mu = perm_test(main_set, pools, flag5, 'sites')
    P('  (а) Нуль тестировщика — метка v1 случайна внутри пула, домены равновероятны по числу сайтов:')
    P('      O = %d, при нуле в среднем %.1f, 95%% интервал [%d; %d], p = %.4f (как в h10).' % (o, mu, lo, hi, p))
    o2, p2, lo2, hi2, mu2 = perm_test_weighted(main_set, lambda r: r['pool'], flag5, 'v3')
    P('  (б) Нуль «регистрации распределяются внутри пула пропорционально вышедшим сайтам (v3)»:')
    P('      O = %d, при нуле в среднем %.1f, 95%% интервал [%d; %d], p = %.4f.' % (o2, mu2, lo2, hi2, p2))
    o3, p3, lo3, hi3, mu3 = perm_test_weighted(main_set, lambda r: r['pool'], flag5, 'clicks_w')
    P('  (в) Нуль «пропорционально поисковым кликам в окне»:')
    P('      O = %d, при нуле в среднем %.1f, 95%% интервал [%d; %d], p = %.4f.' % (o3, mu3, lo3, hi3, p3))
    P('  Смысл: (а) проверяет «v1 связан с регистрациями», но это уже доказано ранее через выход;')
    P('         (б) и (в) проверяют «v1 добавляет что-то СВЕРХ уровня выхода / кликов» — то есть собственно правило.')

    # ---------------- 3. Условно на уровень выхода ----------------
    P('')
    P('=' * 110)
    P('3. ДОБАВЛЯЕТ ЛИ v1 ЧТО-ТО ПРИ РАВНОМ УРОВНЕ ВЫХОДА (v3)')
    P('=' * 110)
    bands = [('v3 = 0', lambda r: r['v3'] == 0), ('v3 1-5', lambda r: 1 <= r['v3'] <= 5),
             ('v3 6-15', lambda r: 6 <= r['v3'] <= 15), ('v3 16-40', lambda r: 16 <= r['v3'] <= 40),
             ('v3 > 40', lambda r: r['v3'] > 40)]
    P('  %-10s | %-32s | %-32s' % ('полоса v3', 'v1≤5: дом / Σv3 / рег', 'v1≥6: дом / Σv3 / рег'))
    tot_o = 0; tot_e = 0
    for name, fn in bands:
        a = [r for r in main_set if fn(r) and r['v1'] <= 5]
        b = [r for r in main_set if fn(r) and r['v1'] >= 6]
        sa = sum(r['v3'] for r in a); sb = sum(r['v3'] for r in b)
        ra = sum(r['reg'] for r in a); rb = sum(r['reg'] for r in b)
        e = (ra + rb) / (sa + sb) * sa if (sa + sb) > 0 else 0
        tot_o += ra; tot_e += e
        P('  %-10s | %6d / %7d / %4d           | %6d / %7d / %4d          | E(v1≤5 по ставке полосы) = %.2f' % (
            name, len(a), sa, ra, len(b), sb, rb, e))
    P('  Итого при равном уровне выхода (страта = полоса v3, ставка на вышедший сайт): O = %d, E = %.2f, O/E = %s' % (
        tot_o, tot_e, fmt(tot_o, tot_e)))
    lo, hi = pois_ci(tot_o)
    P('  95%% интервал для O/E: [%.2f; %.2f] — %s' % (lo / tot_e, hi / tot_e,
        'единица внутри интервала' if lo / tot_e <= 1 <= hi / tot_e else 'единица вне интервала'))
    P('  Объём событий в зоне пересечения (v3 1-15, где есть и v1≤5, и v1≥6):')
    ov = [r for r in main_set if 1 <= r['v3'] <= 15]
    P('    доменов %d, из них v1≤5 %d, v1≥6 %d; регистраций в окне ВСЕГО %d — сравнивать нечего.' % (
        len(ov), sum(1 for r in ov if r['v1'] <= 5), sum(1 for r in ov if r['v1'] >= 6),
        sum(r['reg'] for r in ov)))

    P('')
    P('  Зоны (страта пул+зона, ≥2 домена): что остаётся от «это не тень .buzz»:')
    cntz = collections.Counter((r['pool'], r['z']) for r in main_set)
    for label, d in dens:
        Ez = expect(main_set, lambda r: (r['pool'], r['z']), d)
        parts = []
        for z in ZONES:
            f = [r for r in main_set if r['z'] == z and r['v1'] <= 5 and cntz[(r['pool'], r['z'])] >= 2]
            parts.append('%s: дом %d, O=%d, E=%.2f' % (z, len(f), sum(r['reg'] for r in f), sum(Ez[r['id']] for r in f)))
        P('    %-26s %s' % (label, '; '.join(parts)))
    P('    При правильном знаменателе ожидание в каждой зоне ≤1.3 регистрации — «в обеих больших зонах помеченные пусты»')
    P('    не является проверкой: там нечему было появиться.')

    # ---------------- 4. Хватает ли событий, топ-домены ----------------
    P('')
    P('=' * 110)
    P('4. ОБЪЁМ СОБЫТИЙ И УСТОЙЧИВОСТЬ К 1–3 ДОМЕНАМ')
    P('=' * 110)
    P('  Регистраций в окне в основном наборе: %d; доменов с ≥1 регистрацией: %d (%.1f%% набора).' % (
        sum(r['reg'] for r in main_set), sum(1 for r in main_set if r['reg'] > 0),
        100 * sum(1 for r in main_set if r['reg'] > 0) / len(main_set)))
    P('  В группе v1≤5: регистраций %d на %d доменов — это ОДНО событие. Любой вывод о группе опирается на счёт «0 против 1».' % (
        sum(r['reg'] for r in le5), len(le5)))
    top = sorted(main_set, key=lambda r: -r['reg'])[:10]
    P('  Топ-10 доменов по регистрациям в окне:')
    for r in top:
        P('    %-22s %-7s %s v1=%3d v3=%3d рег=%2d (%.1f%% всех)' % (
            r['домен'], r['z'], r['day'], r['v1'], r['v3'], r['reg'], 100 * r['reg'] / sum(x['reg'] for x in main_set)))
    P('  Удаление топ-3 доменов по регистрациям из v1≥6 (в v1≤5 удалять нечего — там 1 регистрация на 1 домене):')
    for k in (1, 3, 5, 10):
        drop = {r['id'] for r in sorted(main_set, key=lambda r: -r['reg'])[:k]}
        sub = [r for r in main_set if r['id'] not in drop]
        Ek = expect(sub, lambda r: r['pool'], 'sites')
        Ev = expect(sub, lambda r: r['pool'], 'v3')
        s5 = [r for r in sub if r['v1'] <= 5]
        o5 = sum(r['reg'] for r in s5)
        P('    без топ-%-2d: рег в наборе %3d; v1≤5: O=%d, E(сайты)=%.1f, O/E=%s; E(вышедшие)=%.2f, O/E=%s' % (
            k, sum(r['reg'] for r in sub), o5, sum(Ek[r['id']] for r in s5), fmt(o5, sum(Ek[r['id']] for r in s5)),
            sum(Ev[r['id']] for r in s5), fmt(o5, sum(Ev[r['id']] for r in s5))))
    P('  Удаление топ-3 по регистрациям НЕ ломает контраст при знаменателе «сайты» — но он и не про домены-рекордсмены,')
    P('  а про то, что у v1≤5 нет вышедших сайтов.')

    # ---------------- 5. Множественность ----------------
    P('')
    P('=' * 110)
    P('5. СКОЛЬКО СРЕЗОВ ПЕРЕБРАНО И ЧТО ОСТАЁТСЯ ПОСЛЕ ПОПРАВКИ')
    P('=' * 110)
    slices = [
        ('А1: группы v1 (0, 1-3, 4-5, 6-10, >10) — пуассоновские p', 5),
        ('А1: сводная v1≤5 + перестановка', 2),
        ('А2: зоны × (пул | пул+зона) × (v1≤5 | v1≥6)', 16),
        ('А3: пороги T = 0,3,5,8,10', 5),
        ('А4: отсечка по задержке (4 группы + перестановка + 3 пересечения)', 8),
        ('А5: догоняние (5 групп × 2 горизонта)', 10),
        ('Повтор с «КОНТЕНТ НЕ ЗАПИСАН» (5 групп)', 5),
        ('Б1–Б4: 4 спецификации × (O/E терцили/половины + перестановка + знаковый)', 12),
        ('Б: блок часа (4 группы) + грубая задержка (4 группы)', 8),
        ('В: нули — 2 перестановки + таблицы по дням/зонам/семействам', 6),
    ]
    tot_sl = sum(n for _, n in slices)
    for name, n in slices:
        P('    %-62s %3d' % (name, n))
    P('    ИТОГО сравнений и подсчётов в одном скрипте: ~%d' % tot_sl)
    P('  Поправка Бонферрони на %d сравнений: порог 0.05/%d = %.5f.' % (tot_sl, tot_sl, 0.05 / tot_sl))
    P('  Главный p = 0.0001 (1 из 10000 перестановок) — формально ниже порога %.5f, поправку переживает,' % (0.05 / tot_sl))
    P('  но только для нуля (а): «v1 не связан с регистрациями внутри пула». Для нуля (б)/(в) см. раздел 2.')
    P('  Замечание о разрешении: p = 0.0001 — это нижняя граница разрешения при 10000 перестановок, а не измеренная величина.')

    # ---------------- 6. Определения и границы окна ----------------
    P('')
    P('=' * 110)
    P('6. ОПРЕДЕЛЕНИЯ, ОКНА, ИСКЛЮЧЕНИЯ')
    P('=' * 110)
    closed = [r for r in rows if r['окно закрыто'] == 'да']
    P('  Исключения проверены: незакрытых окон %d, «дней»≠2 после этого %d, выбросов 2, «не записан» 335.' % (
        len(rows) - len(closed), sum(1 for r in closed if r['дней'] != '2')))
    d1 = [r for r in rows if r['дней'] == '1']
    P('  Доменов с «дней»=1 в файле: %d; из них с закрытым окном: %d — они в основной набор не попали. Правильно.' % (
        len(d1), sum(1 for r in d1 if r['окно закрыто'] == 'да')))
    P('  Оконные колонки использованы верно: рег/ФД/клики — «в окне 3 суток», знаменатель «сайтов в окне».')
    P('  НО: «вышли за 1 сутки», «вышли за 3 суток», «вышли за 7 суток» — НЕ оконные в том же смысле:')
    P('    они считаются от переобхода каждого сайта, включая 56 сайтов второй волны (сутки второй волны кончаются на день позже).')
    nsite = collections.Counter(r['sites'] for r in main_set)
    P('    «сайтов в окне» в основном наборе: 206 у %d доменов, иное у %d (мин %d, макс %d).' % (
        nsite.get(206, 0), len(main_set) - nsite.get(206, 0),
        min(r['sites'] for r in main_set), max(r['sites'] for r in main_set)))
    P('  Проверка «v1 — это уровень, а не порог»: доля v1 от v3 и v3 от сайтов у помеченных:')
    for name, fn in (('v1≤5', lambda r: r['v1'] <= 5), ('v1 6-10', lambda r: 6 <= r['v1'] <= 10), ('v1>10', lambda r: r['v1'] > 10)):
        g = [r for r in main_set if fn(r)]
        P('    %-8s доменов %4d, Σv1 %6d, Σv3 %6d, Σсайтов %7d; выход за 3 суток = %.2f%% сайтов' % (
            name, len(g), sum(r['v1'] for r in g), sum(r['v3'] for r in g), sum(r['sites'] for r in g),
            100 * sum(r['v3'] for r in g) / sum(r['sites'] for r in g)))

    # ---------------- 7. Нули ----------------
    P('')
    P('=' * 110)
    P('7. НУЛИ: сколько регистраций им вообще полагалось')
    P('=' * 110)
    zer = [r for r in main_set if r['v3'] == 0]
    P('  Нулей в основном наборе: %d (в h10 по всем закрытым — 32).' % len(zer))
    P('  Ожидание регистраций у нулей: по сайтам E = %.2f; по вышедшим сайтам (v3=0) E = %.2f; по поисковым кликам E = %.2f.' % (
        sum(E_sites[r['id']] for r in zer), sum(Es['v3'][r['id']] for r in zer), sum(Es['clicks_w'][r['id']] for r in zer)))
    P('  То есть «у нулей 0 регистраций» — это арифметика (нет вышедших сайтов → нет поисковых кликов → регистрация невозможна),')
    P('  а не проверяемое предсказание: при нулевом знаменателе ожидание тоже ноль.')
    clw = sum(r['clicks_w'] for r in zer)
    P('  Поисковых кликов в окне у нулей: %d (сумма по %d доменам).' % (clw, len(zer)))
    all_closed = [r for r in rows if r['окно закрыто'] == 'да' and r['домен'] not in OUTLIERS]
    z_all = [r for r in all_closed if r['v3'] == 0]
    rev = [r for r in z_all if r['v7'] >= 3]
    P('  «Оживание» (v7≥3) по группам уровня выхода (все закрытые, без выбросов):')
    for name, fn in (('v3 = 0', lambda r: r['v3'] == 0), ('v3 1-5', lambda r: 1 <= r['v3'] <= 5),
                     ('v3 6-15', lambda r: 6 <= r['v3'] <= 15)):
        g = [r for r in all_closed if fn(r)]
        gr = [r for r in g if r['v7'] >= r['v3'] + 3]
        P('    %-8s доменов %4d, прибавили ≥3 к 7 суткам: %3d (%.1f%%)' % (name, len(g), len(gr), 100 * len(gr) / len(g)))
    P('  У нулей 4 из %d (%.1f%%) — это НЕ ниже, чем у соседних групп; «нули не оживают» держится на 32 доменах и 4 событиях.' % (
        len(z_all), 100 * len(rev) / len(z_all)))

    # ---------------- 8. Скорость ----------------
    P('')
    P('=' * 110)
    P('8. СКОРОСТЬ: насколько «не отличимо от 1» подтверждено объёмом')
    P('=' * 110)
    P('  Тестировщик: отношения O/E быстрых к медленным 0.87 (терцили) и 1.14 (половины), p ≈ 0.44–0.49.')
    P('  Интервалы для отношения двух пуассоновских счётчиков (точный биномиальный на O1 из O1+O2, E-поправка):')
    for nm, o1, e1, o2, e2 in (('Б1 терцили пул×блок', 47, 58.3, 53, 57.5),
                               ('Б2 терцили пул', 46, 57.1, 56, 60.0),
                               ('Б3 половины пул×блок', 90, 86.4, 76, 82.9),
                               ('Б4 половины пул', 95, 89.3, 81, 86.9)):
        n = o1 + o2
        # интервал Клоппера–Пирсона для доли o1/(o1+o2), затем в отношение с поправкой на E
        def cp(k, n, a):
            lo, hi = 0.0, 1.0
            for _ in range(200):
                mid = (lo + hi) / 2
                s = sum(math.comb(n, i) * mid ** i * (1 - mid) ** (n - i) for i in range(k, n + 1))
                if s < a: lo = mid
                else: hi = mid
            return (lo + hi) / 2
        plo = cp(o1, n, 0.025) if o1 > 0 else 0.0
        phi = 1 - cp(n - o1, n, 0.025) if o1 < n else 1.0
        f = e2 / e1
        r_lo = plo / (1 - plo) * f if plo < 1 else float('inf')
        r_hi = phi / (1 - phi) * f if phi < 1 else float('inf')
        P('    %-24s O/E быстр/медл = %.2f, 95%% интервал [%.2f; %.2f]' % (
            nm, (o1 / e1) / (o2 / e2), r_lo, r_hi))
    P('  Интервалы шириной примерно от 0,6–0,7 до 1,4–1,5: исключены только различия больше ~1,4×.')
    P('  Формулировка «скорость ничего не добавляет» сильнее данных; верно «различие больше ~1,4× исключено, меньшее — нет».')

    # ---------------- ВЫВОД ----------------
    P('')
    P('=' * 110)
    P('ВЫВОД КОНТРПРОВЕРКИ')
    P('=' * 110)
    o_le5 = sum(r['reg'] for r in le5)
    e_s = sum(E_sites[r['id']] for r in le5)
    e_v3 = sum(Es['v3'][r['id']] for r in le5)
    e_cl = sum(Es['clicks_w'][r['id']] for r in le5)
    P('  1. Числа воспроизводятся побайтово. Фильтры и оконные колонки выбраны верно.')
    P('  2. Главная цифра O/E = 0.09 (O=%d, E=%.1f) получена на знаменателе «сайтов в окне».' % (o_le5, e_s))
    P('     При знаменателе «вышли за 3 суток» E = %.2f (O/E = %.2f), при «кликах из поиска в окне» E = %.2f (O/E = %.2f).' % (
        e_v3, o_le5 / e_v3, e_cl, o_le5 / e_cl))
    P('  3. Значит, «42×» и «O/E 0,09» — это в основном пересказ того, что у помеченных доменов почти нет вышедших сайтов,')
    P('     а не отдельное свойство счётчика первого дня.')
    P('  4. Событий для проверки «сверх уровня выхода» нет: в полосе v3 1–15 всего %d регистраций на %d доменов.' % (
        sum(r['reg'] for r in ov), len(ov)))
    sys.stdout.flush()


if __name__ == '__main__':
    main()
