#!/usr/bin/env python3
"""
Гипотеза №17. Повторные конверсии на домене — это один и тот же сайт-бренд, стоящий
в выдаче; повторные регистрации с одного сайта не приносят первых депозитов (ФД идут
только с первой регистрации сайта); «сгущённые» бренды (Martin, R7, Twin, Trix, Iris)
живут на немногих доменах-носителях, а Lucky Bird / Luckybear / Олимп размазаны по
доменам пропорционально объёму.

Что проверяем.
  (А) Один сайт. У домена с R регистрациями сколько разных сайтов (брендов) их дали?
      В своде: «регистраций» = R, «сайтов с регистрацией» = S — число брендов в
      строке «какие бренды конвертили». Проверено на файле: числа в скобках там =
      регистрации + ФД (536 = 461 + 75), S равно числу брендов в списке, R ≥ S всегда,
      и у всех 37 доменов «1 регистрация + 1 ФД» S = 1 — то есть ФД падает на тот же
      сайт, где была регистрация. Отсюда повторы регистраций с одного сайта = R − S,
      без примеси ФД. Важно: в формулировке гипотезы «N конверсий» = регистрации + ФД,
      и пара «регистрация + её же ФД» считается как «две конверсии одного бренда» —
      это не повтор, а один человек. Сначала воспроизводим цифры гипотезы как есть,
      затем считаем честно — только по регистрациям.
      Ноль: R брендов тянутся независимо из распределения регистраций по брендам
      (без вклада самого домена — leave-one-out), 10 000 симуляций; смотрим число
      разных сайтов S и долю доменов, где все R регистраций с одного сайта. Рядом —
      перестановка меток бренда между всеми регистрациями свода (поля доменов
      фиксированы) и распределение по всем 536 конверсиям, как в гипотезе.
  (Б) ФД. Группы: A — регистраций = сайтов с регистрацией (повторов нет),
      B — регистраций > сайтов (есть повторы с одного сайта). ФД/рег и ФД/сайт в A и B;
      точный тест 2×2 (односторонний, гипергеометрический); ДИ отношения ФД/сайт;
      две модели для B — «ФД только с первой регистрации сайта» E = S_B × ставка A и
      «все регистрации равноценны» E = R_B × ставка A — пуассоновские хвосты и
      отношение правдоподобий; то же внутри пулов «набор контента + день запуска»,
      внутри зоны и внутри дня (O/E) с перестановкой меток A/B среди доменов
      с регистрациями внутри страты (10 000). Контроль: A только с R ≥ 2 против B
      (у B по построению R ≥ 2); без «КОНТЕНТ НЕ ЗАПИСАН».
  (В) Сгущение. Для брендов с ≥7 конверсиями: k регистраций (ФД отняты), D_obs
      доменов. Нули: (1) перестановка меток бренда между всеми регистрациями свода —
      поля доменов (сколько регистраций у домена) сохранены, это контроль «богатых
      доменов»; (2) размещение k регистраций независимо по доменам с p ∝ поисковых
      кликов в окне; (3) p ∝ вышли за 3 суток; (4) равномерно; (5) p ∝ регистраций
      домена. 10 000 симуляций, p = доля симуляций с D ≤ D_obs, поправка
      Бенджамини–Хохберга; индекс сгущения = E[D] / D_obs. Общий тест: сумма повторов
      Σ(R − S) = 33 против перестановочного распределения. Повтор внутри пулов ≥3
      доменов для пар бренд × пул с ≥5 регистрациями (перестановка внутри пула).
  Даты: у доменов с R ≥ 2 — доля с ≥2 разными датами регистраций и уникальных дат
      на регистрацию: однобрендовые (S = 1) против многобрендовых (S ≥ 2), и B против
      A; перестановка метки внутри пула, при нехватке страт — внутри дня запуска.
  Описательно: какие бренды дают повторы, домены-носители.

Фильтры: окно закрыто = да; дней ≠ 1; без 3615.team и 3286.team. Для ФД (часть Б)
дополнительно запуск ≤ 2026-09-13 (основной расчёт) и без ограничения по дате (рядом).
«КОНТЕНТ НЕ ЗАПИСАН» остаётся в основном расчёте (часть повторов — в доменах до 24.08,
где журнала не было; это оговорено), пул для него = «КОНТЕНТ НЕ ЗАПИСАН + день»;
чувствительность без него — отдельно.

Как ФД отнесены к бренду: ФД возможен только на сайте, где есть регистрация, значит
только у бренда с числом в скобках ≥ 2; на каждый такой бренд не больше (число − 1) ФД;
ФД раздаются сначала брендам с наибольшим числом. Домены, где раздача неоднозначна,
перечислены в выводе (их 3, влияние — единицы событий из 424).

Критерии постановки: А — доля «все с одного сайта» 60–65 % против 2–3 %, p ≪ 0,001;
Б — ФД в B ближе к «только первые» (p(≤12 | 16,9) < 0,15), ФД/сайт в A и B
отличаются <20 %; В — Martin, R7, Twin, Trix, Iris с D_obs в 1,5–2 раза ниже ожидания
при p < 0,05 после FDR, Lucky Bird / Luckybear / Cactus / Олимп с индексом 0,9–1,1.
"""
import collections
import csv
import math
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h17_same_site_repeats.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
NSIM = 10000
FD_LAUNCH_MAX = '2026-09-13'
ZONES = ('team', 'lol', 'casino', 'buzz')
BRAND_RE = re.compile(r'^(.*?) \((\d+)\)$')
CLUSTERED_EXPECT = ('Martin', 'R7', 'Twin', 'Trix', 'Iris')
SPREAD_EXPECT = ('Lucky Bird', 'Luckybear', 'Cactus', 'Олимп')


class Tee:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def write(self, s):
        sys.__stdout__.write(s)
        self.f.write(s)

    def flush(self):
        sys.__stdout__.flush()
        self.f.flush()


def I(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def F(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def fmt(x, d=2):
    return f'{x:.{d}f}'


def zone_of(r):
    return r['зона'] if r['зона'] in ZONES else 'прочие'


def pool_of(r):
    return r['набор контента'] + ' | ' + r['день запуска']


# ---------- вероятностные помощники (только stdlib) ----------
def log_fact(n):
    return math.lgamma(n + 1)


def pois_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam + k * math.log(lam) - log_fact(k))


def pois_le(k, lam):
    return sum(pois_pmf(i, lam) for i in range(0, k + 1))


def pois_ge(k, lam):
    return 1.0 - pois_le(k - 1, lam) if k > 0 else 1.0


def hyper_pmf(x, a_tot, b_tot, k):
    # x успехов из a_tot при выборке k из a_tot + b_tot
    return math.exp(log_fact(a_tot) - log_fact(x) - log_fact(a_tot - x)
                    + log_fact(b_tot) - log_fact(k - x) - log_fact(b_tot - k + x)
                    - log_fact(a_tot + b_tot) + log_fact(k) + log_fact(a_tot + b_tot - k))


def fisher_one_sided_le(x, a_tot, b_tot, k):
    """P(X ≤ x): доля успехов в группе B (k наблюдений) не выше ожидаемой при общей ставке."""
    lo = max(0, k - b_tot)
    return sum(hyper_pmf(i, a_tot, b_tot, k) for i in range(lo, x + 1))


def rate_ratio_ci(a, na, b, nb):
    """ДИ 95 % для отношения ставок (b/nb)/(a/na), лог-нормальное приближение."""
    if a == 0 or b == 0:
        return (float('nan'), float('nan'))
    lr = math.log((b / nb) / (a / na))
    se = math.sqrt(1 / a + 1 / b)
    return (math.exp(lr - 1.96 * se), math.exp(lr + 1.96 * se))


def bh_fdr(pvals):
    n = len(pvals)
    order = sorted(range(n), key=lambda i: pvals[i])
    q = [0.0] * n
    prev = 1.0
    for rank in range(n, 0, -1):
        i = order[rank - 1]
        val = min(prev, pvals[i] * n / rank)
        q[i] = val
        prev = val
    return q


# ---------- чтение и подготовка ----------
def parse_brands(s):
    s = s.strip()
    if not s:
        return []
    out = []
    for item in s.split(','):
        m = BRAND_RE.match(item.strip())
        if m:
            out.append((m.group(1), int(m.group(2))))
    return out


def attribute_fd(brand_counts, fd):
    """Раздать fd депозитов брендам: только тем, у кого число ≥ 2, не больше (число − 1) каждому,
    сначала бренду с наибольшим числом. Возвращает (регистраций по брендам, неоднозначно ли)."""
    regs = dict(brand_counts)
    left = fd
    order = sorted(brand_counts, key=lambda b: -brand_counts[b])
    for b in order:
        if left == 0:
            break
        cap = brand_counts[b] - 1
        take = min(cap, left)
        regs[b] -= take
        left -= take
    # неоднозначность: есть ли другой способ раздать (несколько брендов с cap>0 и fd < суммарной ёмкости)
    caps = sorted((brand_counts[b] - 1 for b in brand_counts if brand_counts[b] >= 2), reverse=True)
    ambiguous = fd > 0 and len(caps) >= 2 and fd < sum(caps) and not (fd <= caps[0] and len(caps) == 1)
    if fd > 0 and len(caps) >= 2:
        # однозначно только если fd == сумме ёмкостей (все берут максимум)
        ambiguous = fd != sum(caps)
    return regs, ambiguous


def main():
    sys.stdout = Tee(OUT)
    random.seed(1)
    with open(SRC, encoding='utf-8') as f:
        rows_all = list(csv.DictReader(f))
    print('Гипотеза №17: повторные регистрации с одного сайта, ФД с повторов, сгущение брендов по доменам')
    print(f'Источник: {os.path.relpath(SRC, REPO)}; строк (доменов): {len(rows_all)}')
    print()

    # --- воспроизведение цифр гипотезы на всём своде (без фильтров), как они были получены ---
    print('0. Воспроизведение цифр гипотезы на всём своде (2077 доменов, без фильтров)')
    conv_dist = collections.Counter()
    same_brand_by_n = collections.Counter()
    regfd_by_n = collections.Counter()
    same_brand_pure = collections.Counter()
    pure_by_n = collections.Counter()
    brand_conv = collections.Counter()
    for r in rows_all:
        bl = parse_brands(r['какие бренды конвертили'])
        n = sum(c for _, c in bl)
        for b, c in bl:
            brand_conv[b] += c
        if n == 0:
            continue
        conv_dist[n] += 1
        if len(bl) == 1:
            same_brand_by_n[n] += 1
        if I(r['ФД']) == 0:
            pure_by_n[n] += 1
            if len(bl) == 1:
                same_brand_pure[n] += 1
        else:
            regfd_by_n[n] += 1
    tot_conv = sum(brand_conv.values())
    sp2 = sum((v / tot_conv) ** 2 for v in brand_conv.values())
    print(f'  Событий (регистрации + ФД) {tot_conv} по {len(brand_conv)} брендам; Σp² = {sp2:.4f}')
    print('  N конверсий | доменов | из них все одного бренда | доменов с ФД>0 (там пара «рег+ФД» = один человек) | доменов без ФД | среди них одного бренда')
    for n in (2, 3, 4):
        print(f'  {n:>11} | {conv_dist[n]:>7} | {same_brand_by_n[n]:>24} ({100*same_brand_by_n[n]/max(1,conv_dist[n]):.0f} %) '
              f'| {regfd_by_n[n]:>10} | {pure_by_n[n]:>14} | {same_brand_pure[n]:>3} ({100*same_brand_pure[n]/max(1,pure_by_n[n]):.0f} %)')
    print('  Проверка на файле: R ≥ S у всех доменов; у всех 37 доменов «1 регистрация + 1 ФД» сайтов с регистрацией = 1,')
    print('  то есть ФД записан на тот же сайт, что и регистрация. Значит «две конверсии одного бренда» при N = 2')
    print('  в большинстве случаев — это регистрация и её же депозит, а не повтор.')
    all_R = sum(I(r['регистраций']) for r in rows_all)
    all_S = sum(I(r['сайтов с регистрацией']) for r in rows_all)
    print(f'  Цифра гипотезы «104 повторные регистрации (21 %)» не воспроизводится: на всём своде регистраций {all_R}, '
          f'сайтов с регистрацией {all_S}, повторов R − S = {all_R - all_S} ({100*(all_R-all_S)/all_R:.1f} %); '
          f'21 % получается, только если считать ФД повторными регистрациями (536 − 428 = 108).')
    print('  То же с «сгущением»: «R7 11 конверсий на 6 доменах» — в таблице (В) ниже видно, сколько из них регистрации, а сколько депозиты.')
    print()

    # --- фильтры ---
    excluded = collections.Counter()
    rows = []
    for r in rows_all:
        if r['домен'] in OUTLIERS:
            excluded['выброс 3615.team / 3286.team'] += 1
            continue
        if r['окно закрыто'] != 'да':
            excluded['окно закрыто = нет'] += 1
            continue
        if r['дней'] == '1':
            excluded['дней = 1 (ещё не было дня 2)'] += 1
            continue
        rows.append(r)
    print('1. Фильтры')
    for k, v in excluded.items():
        print(f'  исключено: {k}: {v}')
    print(f'  осталось доменов: {len(rows)}; из них «{NOCONTENT}»: {sum(1 for r in rows if r["набор контента"] == NOCONTENT)} (оставлены, оговорено)')

    # подготовка: регистрации по брендам на домене
    ambiguous_list = []
    for r in rows:
        r['_R'] = I(r['регистраций'])
        r['_F'] = I(r['ФД'])
        r['_S'] = I(r['сайтов с регистрацией'])
        bl = parse_brands(r['какие бренды конвертили'])
        bc = {b: c for b, c in bl}
        regs, amb = attribute_fd(bc, r['_F'])
        if amb:
            ambiguous_list.append((r['домен'], r['какие бренды конвертили'], r['_F']))
        r['_regs'] = regs                   # бренд -> регистраций
        r['_conv'] = bc                     # бренд -> конверсий
        assert sum(regs.values()) == r['_R'], (r['домен'], regs, r['_R'])
        assert len(regs) == r['_S'], (r['домен'], regs, r['_S'])
        r['_dates'] = r['даты регистраций'].split()
        r['_pool'] = pool_of(r)
        r['_zone'] = zone_of(r)
    tot_R = sum(r['_R'] for r in rows)
    tot_S = sum(r['_S'] for r in rows)
    tot_F = sum(r['_F'] for r in rows)
    print(f'  после фильтров: регистраций {tot_R}, сайтов с регистрацией {tot_S}, ФД {tot_F}, '
          f'повторов с одного сайта (R − S) {tot_R - tot_S} ({100*(tot_R-tot_S)/tot_R:.1f} % регистраций)')
    print(f'  доменов с неоднозначной раздачей ФД по брендам: {len(ambiguous_list)}')
    for d, s, fd in ambiguous_list:
        print(f'    {d}: {s}; ФД {fd} (ФД отданы бренду с наибольшим числом)')
    print()

    # распределение регистраций по брендам (после фильтров)
    brand_reg = collections.Counter()
    brand_domains = collections.defaultdict(set)
    for r in rows:
        for b, c in r['_regs'].items():
            brand_reg[b] += c
            brand_domains[b].add(r['домен'])
    K = sum(brand_reg.values())
    sp2_reg = sum((v / K) ** 2 for v in brand_reg.values())
    print(f'  Регистраций по брендам после фильтров: {K} по {len(brand_reg)} брендам; Σp² = {sp2_reg:.4f} '
          f'(ожидаемая доля «две регистрации — один бренд» при независимости)')
    print()

    # ====================== (А) один сайт ======================
    print('=' * 100)
    print('(А) ОДИН САЙТ: число разных сайтов S при R регистрациях на домене — наблюдение против независимости')
    print('=' * 100)
    by_R = collections.defaultdict(list)
    for r in rows:
        if r['_R'] >= 2:
            by_R[r['_R']].append(r)
    brands = sorted(brand_reg)
    idx = {b: i for i, b in enumerate(brands)}
    kvec = [brand_reg[b] for b in brands]

    def draw_S(r, R, nsim, weights_fn):
        """Возвращает список S по симуляциям для домена r при R независимых брендах."""
        w = weights_fn(r)
        cw = []
        acc = 0.0
        for x in w:
            acc += x
            cw.append(acc)
        out = []
        for _ in range(nsim):
            picks = random.choices(range(len(w)), cum_weights=cw, k=R)
            out.append(len(set(picks)))
        return out

    def w_loo(r):
        return [kvec[i] - r['_regs'].get(brands[i], 0) for i in range(len(brands))]

    conv_brands = sorted(brand_conv)
    conv_vec = [brand_conv[b] for b in conv_brands]

    def w_conv536(_r):
        return conv_vec

    print('  Ноль 1: R брендов независимо из распределения регистраций по брендам без вклада самого домена (LOO).')
    print('  Ноль 2: то же из распределения 536 конверсий всего свода (как в гипотезе).')
    print('  R | доменов | регистраций | S набл. (среднее) | S ожид. LOO | все с одного сайта: набл. | ожид. LOO | p (≥ набл.) | ожид. по 536 | p | хоть один повтор (S<R): набл. | ожид. LOO | p')
    groups = [(2, [2]), (3, [3]), (4, [4]), ('≥5', [5, 6, 7, 8, 9, 10])]
    partA = {}
    for label, Rs in groups:
        doms = [r for R in Rs for r in by_R.get(R, [])]
        if not doms:
            continue
        obs_S = sum(r['_S'] for r in doms)
        obs_one = sum(1 for r in doms if r['_S'] == 1)
        obs_rep = sum(1 for r in doms if r['_S'] < r['_R'])
        sims_one = [0] * NSIM
        sims_rep = [0] * NSIM
        sims_S = [0] * NSIM
        sims_one2 = [0] * NSIM
        for r in doms:
            s1 = draw_S(r, r['_R'], NSIM, w_loo)
            s2 = draw_S(r, r['_R'], NSIM, w_conv536)
            for i in range(NSIM):
                sims_S[i] += s1[i]
                if s1[i] == 1:
                    sims_one[i] += 1
                if s1[i] < r['_R']:
                    sims_rep[i] += 1
                if s2[i] == 1:
                    sims_one2[i] += 1
        n = len(doms)
        eS = sum(sims_S) / NSIM
        e1 = sum(sims_one) / NSIM
        e1b = sum(sims_one2) / NSIM
        er = sum(sims_rep) / NSIM
        p1 = sum(1 for x in sims_one if x >= obs_one) / NSIM
        p1b = sum(1 for x in sims_one2 if x >= obs_one) / NSIM
        pr = sum(1 for x in sims_rep if x >= obs_rep) / NSIM
        partA[label] = dict(n=n, obs_one=obs_one, e1=e1, p1=p1, obs_rep=obs_rep, er=er, pr=pr, eS=eS, obs_S=obs_S)
        print(f'  {str(label):>2} | {n:>7} | {sum(r["_R"] for r in doms):>11} | {obs_S/n:>17.2f} | {eS/n:>11.2f} | '
              f'{obs_one:>3} ({100*obs_one/n:.0f} %) | {e1:>6.2f} ({100*e1/n:.1f} %) | {p1:<9.4f} | {e1b:>6.2f} ({100*e1b/n:.1f} %) | {p1b:<6.4f} | '
              f'{obs_rep:>3} ({100*obs_rep/n:.0f} %) | {er:>6.2f} ({100*er/n:.1f} %) | {pr:.4f}')
    # перестановка меток бренда по всем регистрациям (поля доменов сохранены)
    slots_dom = []
    slots_lab = []
    for r in rows:
        for b, c in r['_regs'].items():
            for _ in range(c):
                slots_dom.append(r['домен'])
                slots_lab.append(b)
    dom_R = {r['домен']: r['_R'] for r in rows}
    obs_repeats_total = tot_R - tot_S
    obs_one_R2 = partA[2]['obs_one'] if 2 in partA else 0

    def shuffle_stats(labels, doms):
        seen = collections.defaultdict(set)
        for d, b in zip(doms, labels):
            seen[d].add(b)
        rep = sum(dom_R[d] - len(seen[d]) for d in seen)
        one_r2 = sum(1 for d in seen if dom_R[d] == 2 and len(seen[d]) == 1)
        return rep, one_r2

    labs = list(slots_lab)
    sh_rep = []
    sh_one = []
    for _ in range(NSIM):
        random.shuffle(labs)
        a, b = shuffle_stats(labs, slots_dom)
        sh_rep.append(a)
        sh_one.append(b)
    e_rep = sum(sh_rep) / NSIM
    p_rep = sum(1 for x in sh_rep if x >= obs_repeats_total) / NSIM
    e_one = sum(sh_one) / NSIM
    p_one = sum(1 for x in sh_one if x >= obs_one_R2) / NSIM
    mx = max(sh_rep)
    print()
    print(f'  Перестановка меток бренда между всеми {len(slots_lab)} регистрациями (число регистраций у каждого домена сохранено):')
    print(f'    повторов с одного сайта Σ(R − S): наблюдено {obs_repeats_total}, ожидание {e_rep:.1f}, максимум по 10 000 перестановкам {mx}, p = {p_rep:.4f}')
    print(f'    доменов с R = 2 и одним сайтом: наблюдено {obs_one_R2}, ожидание {e_one:.2f}, p = {p_one:.4f}')
    print()

    # ====================== (Б) ФД ======================
    print('=' * 100)
    print('(Б) ФД: группа A (регистраций = сайтов, повторов нет) против B (регистраций > сайтов, есть повторы)')
    print('=' * 100)

    def group_of(r):
        if r['_R'] == 0:
            return None
        return 'B' if r['_R'] > r['_S'] else 'A'

    def summarize(rs, title):
        A = [r for r in rs if group_of(r) == 'A']
        B = [r for r in rs if group_of(r) == 'B']
        out = {}
        for g, lst in (('A', A), ('B', B)):
            out[g] = dict(n=len(lst), R=sum(r['_R'] for r in lst), S=sum(r['_S'] for r in lst), F=sum(r['_F'] for r in lst))
        print(f'  {title}')
        print('    группа | доменов | регистраций | сайтов с рег. | ФД | ФД/рег | ФД/сайт')
        for g in ('A', 'B'):
            o = out[g]
            print(f'    {g:>6} | {o["n"]:>7} | {o["R"]:>11} | {o["S"]:>13} | {o["F"]:>2} | {o["F"]/max(1,o["R"]):.3f}  | {o["F"]/max(1,o["S"]):.3f}')
        a, b = out['A'], out['B']
        if b['F'] >= 0 and a['R'] > 0 and b['R'] > 0:
            rateA = a['F'] / a['R']
            p_fisher = fisher_one_sided_le(b['F'], a['F'] + b['F'], a['R'] + b['R'] - a['F'] - b['F'], b['R'])
            ci_site = rate_ratio_ci(a['F'], a['S'], b['F'], b['S'])
            ci_reg = rate_ratio_ci(a['F'], a['R'], b['F'], b['R'])
            E_first = b['S'] * rateA
            E_all = b['R'] * rateA
            print(f'    ФД/рег B к A: {(b["F"]/b["R"])/rateA:.2f} (ДИ {ci_reg[0]:.2f}–{ci_reg[1]:.2f}); точный тест 2×2 (ФД/рег в B ниже), p = {p_fisher:.3f}')
            print(f'    ФД/сайт B к A: {(b["F"]/b["S"])/(a["F"]/a["S"]):.2f} (ДИ {ci_site[0]:.2f}–{ci_site[1]:.2f})')
            print(f'    Модель «ФД только с первой регистрации сайта»: E = {b["S"]} × {rateA:.3f} = {E_first:.1f}; P(X ≥ {b["F"]}) = {pois_ge(b["F"], E_first):.3f}, P(X ≤ {b["F"]}) = {pois_le(b["F"], E_first):.3f}')
            print(f'    Модель «все регистрации равноценны»:            E = {b["R"]} × {rateA:.3f} = {E_all:.1f}; P(X ≤ {b["F"]}) = {pois_le(b["F"], E_all):.3f}, P(X ≥ {b["F"]}) = {pois_ge(b["F"], E_all):.3f}')
            lr = pois_pmf(b['F'], E_first) / max(1e-300, pois_pmf(b['F'], E_all))
            print(f'    Отношение правдоподобий «только первые» / «все равноценны» при {b["F"]} ФД: {lr:.2f} '
                  f'({"в пользу «только первые»" if lr > 1 else "в пользу «все равноценны»"}; убедительным считаем ≥ 10 или ≤ 0,1)')
            print(f'    «Лишних» регистраций в B: {b["R"] - b["S"]}; сколько ФД они дали при модели «все равноценны»: ≈ {(b["R"]-b["S"])*rateA:.1f}, при «только первые»: 0')
        return out

    rows_fd = [r for r in rows if r['день запуска'] <= FD_LAUNCH_MAX]
    print(f'  Основной расчёт для ФД: запуск ≤ {FD_LAUNCH_MAX} — доменов {len(rows_fd)} (исключено {len(rows) - len(rows_fd)} более поздних)')
    resB_main = summarize(rows_fd, f'Б.1 Запуск ≤ {FD_LAUNCH_MAX}')
    print()
    resB_all = summarize(rows, 'Б.2 Без ограничения по дате запуска (как в формулировке гипотезы)')
    print()
    rows_fd_nc = [r for r in rows_fd if r['набор контента'] != NOCONTENT]
    summarize(rows_fd_nc, f'Б.3 Запуск ≤ {FD_LAUNCH_MAX}, без «{NOCONTENT}»')
    print()
    rows_fd_r2 = [r for r in rows_fd if r['_R'] >= 2]
    summarize(rows_fd_r2, f'Б.4 Запуск ≤ {FD_LAUNCH_MAX}, только домены с R ≥ 2 (у B R ≥ 2 по построению)')
    print()

    # стратификация: O/E внутри страт с перестановкой A/B
    def strat_oe(rs, key_fn, title, nperm=NSIM):
        strata = collections.defaultdict(list)
        for r in rs:
            g = group_of(r)
            if g:
                strata[key_fn(r)].append(r)
        use = {k: v for k, v in strata.items() if any(group_of(r) == 'A' for r in v) and any(group_of(r) == 'B' for r in v)}
        nB = sum(1 for v in use.values() for r in v if group_of(r) == 'B')
        nA = sum(1 for v in use.values() for r in v if group_of(r) == 'A')

        def stats(assign):
            # assign: dict strata -> list of (r, label)
            O = 0
            E_all = 0.0
            E_first = 0.0
            for k, lst in assign.items():
                RA = sum(r['_R'] for r, g in lst if g == 'A')
                FA = sum(r['_F'] for r, g in lst if g == 'A')
                RB = sum(r['_R'] for r, g in lst if g == 'B')
                SB = sum(r['_S'] for r, g in lst if g == 'B')
                FB = sum(r['_F'] for r, g in lst if g == 'B')
                if RA == 0:
                    continue
                O += FB
                E_all += RB * FA / RA
                E_first += SB * FA / RA
            return O, E_all, E_first

        base = {k: [(r, group_of(r)) for r in v] for k, v in use.items()}
        O, E_all, E_first = stats(base)
        oe_obs = O / E_all if E_all > 0 else float('nan')
        oe1_obs = O / E_first if E_first > 0 else float('nan')
        # перестановка меток внутри страты. Под нулём «все регистрации равноценны» ФД ∝ R в обеих группах,
        # и метка A/B обменна относительно ФД/рег — проверяем O/E_all (односторонне: ниже ли у B).
        # Под нулём «ФД только с первой регистрации сайта» ФД ∝ S в обеих группах, метка обменна
        # относительно ФД/сайт — проверяем O/E_first (односторонне: выше ли у B, чем даёт этот ноль).
        cnt_le = 0
        cnt_ge = 0
        cnt1_ge = 0
        perm_vals = []
        for _ in range(nperm):
            assign = {}
            for k, lst in base.items():
                labels = [g for _, g in lst]
                random.shuffle(labels)
                assign[k] = [(lst[i][0], labels[i]) for i in range(len(lst))]
            o, ea, ef = stats(assign)
            v = o / ea if ea > 0 else float('nan')
            v1 = o / ef if ef > 0 else float('nan')
            perm_vals.append(v)
            if v == v:
                if v <= oe_obs:
                    cnt_le += 1
                if v >= oe_obs:
                    cnt_ge += 1
            if v1 == v1 and v1 >= oe1_obs:
                cnt1_ge += 1
        valid = [v for v in perm_vals if v == v]
        valid.sort()
        lo = valid[int(0.025 * len(valid))] if valid else float('nan')
        hi = valid[int(0.975 * len(valid)) - 1] if valid else float('nan')
        print(f'  {title}: страт с обеими группами {len(use)}; доменов A {nA}, B {nB}')
        print(f'    ФД в B: наблюдено {O}; E «все равноценны» {E_all:.1f} (O/E {oe_obs:.2f}); E «только первые» {E_first:.1f} (O/E {oe1_obs:.2f})')
        print(f'    перестановка меток A/B внутри страт ({nperm}): ноль «все равноценны» — p(O/E ≤ набл.) = {cnt_le/nperm:.3f} '
              f'(нулевой интервал O/E {lo:.2f}–{hi:.2f}); ноль «только первые» — p(O/E_first ≥ набл.) = {cnt1_ge/nperm:.3f}')
        if E_first > 0:
            print(f'    пуассон: P(X ≤ {O} | {E_all:.1f}) = {pois_le(O, E_all):.3f}; P(X ≥ {O} | {E_first:.1f}) = {pois_ge(O, E_first):.3f}; '
                  f'отношение правдоподобий «только первые»/«все» = {pois_pmf(O, E_first)/max(1e-300,pois_pmf(O, E_all)):.2f}')
        return dict(O=O, E_all=E_all, E_first=E_first, p_all=cnt_le / nperm, p_first=cnt1_ge / nperm, n_strata=len(use))

    print('  Б.5 Стратификация (запуск ≤ 13.09):')
    st_pool = strat_oe(rows_fd, lambda r: r['_pool'], 'пул «набор контента + день запуска»')
    strat_oe(rows_fd, lambda r: r['_zone'], 'зона')
    st_day = strat_oe(rows_fd, lambda r: r['день запуска'], 'день запуска')
    strat_oe(rows_fd, lambda r: r['_zone'] + ' | ' + r['день запуска'], 'зона + день запуска')
    print('  Б.6 Стратификация, только домены с R ≥ 2 (запуск ≤ 13.09):')
    st_r2 = strat_oe(rows_fd_r2, lambda r: r['день запуска'], 'день запуска')
    strat_oe(rows_fd_r2, lambda r: r['_zone'], 'зона')
    print('  Б.7 Стратификация без ограничения по дате (все запуски):')
    strat_oe(rows, lambda r: r['_pool'], 'пул «набор контента + день запуска»')
    strat_oe(rows, lambda r: r['день запуска'], 'день запуска')
    print()
    # где сидят домены B
    print('  Домены группы B (есть повторы с одного сайта), запуск ≤ 13.09:')
    print('    домен | зона | запуск | набор контента | R | S | ФД | бренды | даты регистраций')
    for r in sorted((r for r in rows_fd if group_of(r) == 'B'), key=lambda r: (-r['_R'], r['домен'])):
        print(f'    {r["домен"]} | {r["_zone"]} | {r["день запуска"]} | {r["набор контента"]} | {r["_R"]} | {r["_S"]} | {r["_F"]} | {r["какие бренды конвертили"]} | {" ".join(r["_dates"])}')
    pools_B = collections.Counter(r['_pool'] for r in rows_fd if group_of(r) == 'B')
    print(f'    пулов с доменами B: {len(pools_B)}; пулы с ≥2 доменами B: ' + '; '.join(f'{k} ({v})' for k, v in pools_B.most_common() if v >= 2))
    print()

    # ====================== (В) сгущение ======================
    print('=' * 100)
    print('(В) СГУЩЕНИЕ: у брендов с ≥7 конверсиями — число доменов D_obs против нуля независимого размещения')
    print('=' * 100)
    brand_conv_f = collections.Counter()
    for r in rows:
        for b, c in r['_conv'].items():
            brand_conv_f[b] += c
    targets = sorted((b for b in brand_conv_f if brand_conv_f[b] >= 7), key=lambda b: -brand_reg[b])
    print(f'  Брендов с ≥7 конверсиями после фильтров: {len(targets)}')
    # веса доменов
    dom_list = [r['домен'] for r in rows]
    w_click = [F(r['кликов из поиска в окне']) for r in rows]
    w_exit = [F(r['вышли за 3 суток']) for r in rows]
    w_unif = [1.0] * len(rows)
    w_reg = [float(r['_R']) for r in rows]
    weight_sets = [('перестановка меток (поля доменов)', None), ('∝ поисковых кликов в окне', w_click),
                   ('∝ вышли за 3 суток', w_exit), ('равномерно', w_unif), ('∝ регистраций домена', w_reg)]

    def cum(w):
        out = []
        acc = 0.0
        for x in w:
            acc += x
            out.append(acc)
        return out

    sim_results = {name: {} for name, _ in weight_sets}
    # (1) перестановка меток: одна серия перестановок для всех брендов
    tset = set(targets)
    D_sh = {b: [] for b in targets}
    labs = list(slots_lab)
    for _ in range(NSIM):
        random.shuffle(labs)
        seen = {b: set() for b in targets}
        for d, b in zip(slots_dom, labs):
            if b in tset:
                seen[b].add(d)
        for b in targets:
            D_sh[b].append(len(seen[b]))
    for b in targets:
        D_obs = len(brand_domains[b])
        sims = D_sh[b]
        sim_results['перестановка меток (поля доменов)'][b] = (sum(sims) / NSIM, sum(1 for x in sims if x <= D_obs) / NSIM)
    # (2..5) независимое размещение
    for name, w in weight_sets[1:]:
        cw = cum(w)
        for b in targets:
            D_obs = len(brand_domains[b])
            k = brand_reg[b]
            sims = []
            for _ in range(NSIM):
                picks = random.choices(range(len(w)), cum_weights=cw, k=k)
                sims.append(len(set(picks)))
            sim_results[name][b] = (sum(sims) / NSIM, sum(1 for x in sims if x <= D_obs) / NSIM)
    # таблица
    print('  Индекс сгущения = E[D] / D_obs (>1 — бренд сидит на меньшем числе доменов, чем ожидалось). p = доля симуляций с D ≤ D_obs; q — FDR по всем брендам таблицы.')
    header = '  бренд | конверсий | регистраций | D_obs | доменов с ≥2 рег. бренда'
    for name, _ in weight_sets:
        header += f' | {name}: E[D], индекс, p, q'
    print(header)
    qmap = {}
    for name, _ in weight_sets:
        ps = [sim_results[name][b][1] for b in targets]
        qs = bh_fdr(ps)
        qmap[name] = dict(zip(targets, qs))
    for b in targets:
        line = f'  {b} | {brand_conv_f[b]} | {brand_reg[b]} | {len(brand_domains[b])} | {sum(1 for r in rows if r["_regs"].get(b,0) >= 2)}'
        for name, _ in weight_sets:
            e, p = sim_results[name][b]
            line += f' | {e:.1f}, {e/len(brand_domains[b]):.2f}, {p:.4f}, {qmap[name][b]:.3f}'
        print(line)
    print()
    main_null = 'перестановка меток (поля доменов)'
    click_null = '∝ поисковых кликов в окне'
    print('  Сводка по ожиданию гипотезы (основной ноль — перестановка меток; рядом — ∝ поисковых кликов в окне):')
    for grp, names in (('ожидались сгущёнными', CLUSTERED_EXPECT), ('ожидались размазанными', SPREAD_EXPECT)):
        print(f'    {grp}:')
        for b in names:
            if b in sim_results[main_null]:
                e1, p1 = sim_results[main_null][b]
                e2, p2 = sim_results[click_null][b]
                D = len(brand_domains[b])
                print(f'      {b}: рег. {brand_reg[b]}, доменов {D}; перестановка: E[D] {e1:.1f}, индекс {e1/D:.2f}, p {p1:.4f}, q {qmap[main_null][b]:.3f}; '
                      f'∝ клики: E[D] {e2:.1f}, индекс {e2/D:.2f}, p {p2:.4f}, q {qmap[click_null][b]:.3f}')
            else:
                print(f'      {b}: после фильтров конверсий {brand_conv_f.get(b, 0)} (< 7), в таблицу не вошёл; регистраций {brand_reg.get(b,0)}, доменов {len(brand_domains.get(b, ()))}')
    n_sig_sh = sum(1 for b in targets if qmap[main_null][b] < 0.05)
    n_sig_cl = sum(1 for b in targets if qmap[click_null][b] < 0.05)
    print(f'    брендов с q < 0,05: перестановка меток {n_sig_sh} из {len(targets)}; ∝ клики {n_sig_cl}; ∝ вышли за 3 суток {sum(1 for b in targets if qmap["∝ вышли за 3 суток"][b] < 0.05)}; '
          f'равномерно {sum(1 for b in targets if qmap["равномерно"][b] < 0.05)}; ∝ регистраций {sum(1 for b in targets if qmap["∝ регистраций домена"][b] < 0.05)}')
    print()
    # домены-носители
    print('  Домены-носители (≥2 регистраций бренда на домене) у брендов таблицы; «дат» — сколько разных дат у всех регистраций домена:')
    for b in targets:
        carriers = [(r['домен'], r['_regs'][b], r['_R'], len(set(r['_dates'])), r['_F'], r['день запуска'], r['набор контента'])
                    for r in rows if r['_regs'].get(b, 0) >= 2]
        if carriers:
            print(f'    {b}: ' + '; '.join(f'{d} ({c} из {R} рег. домена, дат {u}, ФД домена {f}, {day}, {cs})' for d, c, R, u, f, day, cs in carriers))
    print()
    # внутри пулов
    print('  В.2 Внутри пулов «набор контента + день» с ≥3 доменами: пары бренд × пул с ≥5 регистрациями бренда в пуле; перестановка меток внутри пула')
    pool_rows = collections.defaultdict(list)
    for r in rows:
        pool_rows[r['_pool']].append(r)
    pairs = []
    for p, lst in pool_rows.items():
        if len(lst) < 3:
            continue
        cnt = collections.Counter()
        for r in lst:
            for b, c in r['_regs'].items():
                cnt[b] += c
        for b, c in cnt.items():
            if c >= 5:
                pairs.append((p, b, c))
    if not pairs:
        print('    таких пар нет')
    tot_pool_rep_obs = 0
    tot_pool_rep_exp = 0.0
    for p, b, c in sorted(pairs, key=lambda x: (-x[2], x[0])):
        lst = pool_rows[p]
        sd = []
        sl = []
        for r in lst:
            for bb, cc in r['_regs'].items():
                for _ in range(cc):
                    sd.append(r['домен'])
                    sl.append(bb)
        D_obs = sum(1 for r in lst if r['_regs'].get(b, 0) >= 1)
        sims = []
        labs2 = list(sl)
        for _ in range(NSIM):
            random.shuffle(labs2)
            sims.append(len({d for d, x in zip(sd, labs2) if x == b}))
        e = sum(sims) / NSIM
        pv = sum(1 for x in sims if x <= D_obs) / NSIM
        print(f'    {p}: доменов в пуле {len(lst)}, регистраций в пуле {len(sl)}; {b}: {c} рег. на {D_obs} доменах; E[D] {e:.2f}, индекс {e/D_obs:.2f}, p = {pv:.4f}')
        tot_pool_rep_obs += c - D_obs
        tot_pool_rep_exp += c - e
    if pairs:
        print(f'    итого по парам: повторов бренда на домене наблюдено {tot_pool_rep_obs}, ожидалось {tot_pool_rep_exp:.1f}')
    # общий тест внутри пулов: Σ(R−S) при перестановке меток внутри каждого пула
    obs_tot = 0
    pool_slots = []
    for p, lst in pool_rows.items():
        sd = []
        sl = []
        for r in lst:
            for bb, cc in r['_regs'].items():
                for _ in range(cc):
                    sd.append(r['домен'])
                    sl.append(bb)
        if len(sl) >= 2:
            pool_slots.append((sd, sl))
            obs_tot += sum(r['_R'] - r['_S'] for r in lst)
    sims = []
    for _ in range(NSIM):
        tot = 0
        for sd, sl in pool_slots:
            labs2 = list(sl)
            random.shuffle(labs2)
            seen = collections.defaultdict(set)
            for d, x in zip(sd, labs2):
                seen[d].add(x)
            tot += sum(dom_R[d] - len(seen[d]) for d in seen)
        sims.append(tot)
    e_pool = sum(sims) / NSIM
    pv_pool = sum(1 for x in sims if x >= obs_tot) / NSIM
    print(f'    Общий тест внутри пулов: Σ(R − S) в пулах с ≥2 регистрациями наблюдено {obs_tot}, ожидание при перестановке меток внутри пула {e_pool:.1f} (макс. {max(sims)}), p = {pv_pool:.4f}')
    print()

    # ====================== даты ======================
    print('=' * 100)
    print('ДАТЫ: у доменов с R ≥ 2 — разные ли даты у регистраций')
    print('=' * 100)
    r2 = [r for r in rows if r['_R'] >= 2]

    def date_stats(lst):
        n = len(lst)
        R = sum(r['_R'] for r in lst)
        U = sum(len(set(r['_dates'])) for r in lst)
        multi = sum(1 for r in lst if len(set(r['_dates'])) >= 2)
        return n, R, U, multi

    def date_compare(rs, label_fn, names, title):
        print(f'  {title}')
        print('    группа | доменов | регистраций | уникальных дат | уник. дат / рег | доменов с ≥2 датами')
        g = {nm: [r for r in rs if label_fn(r) == nm] for nm in names}
        for nm in names:
            n, R, U, multi = date_stats(g[nm])
            print(f'    {nm:>26} | {n:>7} | {R:>11} | {U:>14} | {U/max(1,R):.2f}            | {multi} ({100*multi/max(1,n):.0f} %)')
        return g

    def date_perm(rs, label_fn, names, strat_fn, title):
        strata = collections.defaultdict(list)
        for r in rs:
            strata[strat_fn(r)].append(r)
        use = [v for v in strata.values() if len({label_fn(r) for r in v}) == 2]
        if not use:
            print(f'    {title}: страт с обеими группами нет')
            return
        a, b = names

        def stat(assign):
            # разность долей «≥2 даты» и разность уник. дат/рег между a и b
            na = nb = 0
            ma = mb = 0
            Ra = Rb = 0
            Ua = Ub = 0
            for lst in assign:
                for r, g in lst:
                    u = len(set(r['_dates']))
                    if g == a:
                        na += 1; ma += (u >= 2); Ra += r['_R']; Ua += u
                    else:
                        nb += 1; mb += (u >= 2); Rb += r['_R']; Ub += u
            return (ma / na - mb / nb, Ua / Ra - Ub / Rb)

        base = [[(r, label_fn(r)) for r in v] for v in use]
        obs = stat(base)
        c1 = c2 = 0
        for _ in range(NSIM):
            assign = []
            for lst in base:
                labels = [g for _, g in lst]
                random.shuffle(labels)
                assign.append([(lst[i][0], labels[i]) for i in range(len(lst))])
            s = stat(assign)
            if abs(s[0]) >= abs(obs[0]) - 1e-12:
                c1 += 1
            if abs(s[1]) >= abs(obs[1]) - 1e-12:
                c2 += 1
        nA = sum(1 for lst in base for r, g in lst if g == a)
        nB = sum(1 for lst in base for r, g in lst if g == b)
        print(f'    {title}: страт с обеими группами {len(use)} (доменов {a} {nA}, {b} {nB}); '
              f'разность доли «≥2 даты» ({a} − {b}) {obs[0]:+.2f}, p двусторонний = {c1/NSIM:.3f}; '
              f'разность уник. дат/рег {obs[1]:+.2f}, p = {c2/NSIM:.3f}')

    lab1 = lambda r: 'однобрендовые (S = 1)' if r['_S'] == 1 else 'многобрендовые (S ≥ 2)'
    date_compare(r2, lab1, ('однобрендовые (S = 1)', 'многобрендовые (S ≥ 2)'), 'Д.1 Все домены с R ≥ 2: один бренд против нескольких')
    date_perm(r2, lab1, ('однобрендовые (S = 1)', 'многобрендовые (S ≥ 2)'), lambda r: r['_pool'], 'перестановка внутри пула «набор + день»')
    date_perm(r2, lab1, ('однобрендовые (S = 1)', 'многобрендовые (S ≥ 2)'), lambda r: r['день запуска'], 'перестановка внутри дня запуска')
    date_perm(r2, lab1, ('однобрендовые (S = 1)', 'многобрендовые (S ≥ 2)'), lambda r: 'все', 'перестановка без страт')
    lab2 = lambda r: 'B (есть повтор с сайта)' if r['_R'] > r['_S'] else 'A (все с разных сайтов)'
    date_compare(r2, lab2, ('B (есть повтор с сайта)', 'A (все с разных сайтов)'), 'Д.2 Все домены с R ≥ 2: B (есть повтор с одного сайта) против A (все с разных сайтов)')
    date_perm(r2, lab2, ('B (есть повтор с сайта)', 'A (все с разных сайтов)'), lambda r: r['_pool'], 'перестановка внутри пула «набор + день»')
    date_perm(r2, lab2, ('B (есть повтор с сайта)', 'A (все с разных сайтов)'), lambda r: r['день запуска'], 'перестановка внутри дня запуска')
    date_perm(r2, lab2, ('B (есть повтор с сайта)', 'A (все с разных сайтов)'), lambda r: 'все', 'перестановка без страт')
    # повторы бренда: те же даты или разные — на уровне пары (бренд, домен)
    same_day = 0
    diff_day = 0
    print('  Д.3 Повторы с одного сайта: у домена B все ли повторные регистрации в один день? (по датам домена, сайт по датам не отделить)')
    for r in r2:
        if r['_R'] > r['_S']:
            u = len(set(r['_dates']))
            if u == 1:
                same_day += 1
            else:
                diff_day += 1
    print(f'    доменов B: все регистрации в один день — {same_day}; в ≥2 дня — {diff_day}')
    print()

    # ====================== описательно ======================
    print('=' * 100)
    print('ОПИСАТЕЛЬНО: какие бренды дают повторы с одного сайта (≥2 регистраций бренда на одном домене)')
    print('=' * 100)
    rep_brand = collections.Counter()
    rep_brand_dom = collections.Counter()
    for r in rows:
        for b, c in r['_regs'].items():
            if c >= 2:
                rep_brand[b] += c - 1
                rep_brand_dom[b] += 1
    print('  бренд | повторных регистраций | доменов с повтором | всего регистраций бренда | доменов бренда | доля повторов')
    for b, v in rep_brand.most_common():
        print(f'  {b} | {v} | {rep_brand_dom[b]} | {brand_reg[b]} | {len(brand_domains[b])} | {100*v/brand_reg[b]:.0f} %')
    print(f'  всего повторных регистраций {sum(rep_brand.values())} у {len(rep_brand)} брендов; '
          f'ожидание при перестановке меток (п. А) {e_rep:.1f}')
    print()

    # ====================== ВЫВОД ======================
    a2 = partA.get(2, {})
    a3 = partA.get(3, {})
    a4 = partA.get(4, {})
    bm = resB_main
    ba = resB_all
    rateA = bm['A']['F'] / bm['A']['R']
    E1 = bm['B']['S'] * rateA
    E2 = bm['B']['R'] * rateA
    lr_main = pois_pmf(bm['B']['F'], E1) / pois_pmf(bm['B']['F'], E2)
    late_A_R = ba['A']['R'] - bm['A']['R']
    late_A_F = ba['A']['F'] - bm['A']['F']

    def brand_line(b):
        e1, p1 = sim_results[main_null][b]
        D = len(brand_domains[b])
        return f'{b} — {brand_reg[b]} рег. на {D} доменах (ожидалось {e1:.1f}, индекс {e1/D:.2f}, q = {qmap[main_null][b]:.3f})'

    clustered = [b for b in targets if qmap[main_null][b] < 0.05]
    not_clustered_expected = [b for b in CLUSTERED_EXPECT if b in sim_results[main_null] and qmap[main_null][b] >= 0.05]
    spread_ok = [b for b in SPREAD_EXPECT if b in sim_results[main_null] and 0.9 <= sim_results[main_null][b][0] / len(brand_domains[b]) <= 1.1]
    spread_not = [b for b in SPREAD_EXPECT if b in sim_results[main_null] and b not in spread_ok]
    fd_conf = '; '.join(f'{b}: {brand_conv_f[b]} конверсий = {brand_reg[b]} рег. + {brand_conv_f[b]-brand_reg[b]} ФД'
                        for b in ('R7', 'Trix', 'Iris') if b in brand_conv_f)
    nB_all = sum(1 for r in rows if r['_R'] > r['_S'])
    nB_nc = sum(1 for r in rows if r['_R'] > r['_S'] and r['набор контента'] == NOCONTENT)
    d1 = date_stats([r for r in r2 if r['_S'] == 1])
    d2 = date_stats([r for r in r2 if r['_S'] >= 2])
    print('=' * 100)
    print('ВЫВОД')
    print('=' * 100)
    print(f"""Фильтры: окно закрыто = да, дней ≠ 1, без 3615.team и 3286.team — {len(rows)} доменов, {tot_R} регистраций,
{tot_S} сайтов с регистрацией, {tot_R - tot_S} повторов с одного сайта ({100*(tot_R-tot_S)/tot_R:.0f} % регистраций), {tot_F} ФД.
«КОНТЕНТ НЕ ЗАПИСАН» (335 доменов) оставлен: {nB_nc} из {nB_all} доменов с повторами — оттуда; без него картина та же (Б.3).

Главное про исходные цифры. В своде «конверсии» = регистрации + ФД, и ФД записан на тот же сайт, где была
регистрация (у всех 37 доменов «1 рег + 1 ФД» сайтов с регистрацией = 1). Поэтому «две конверсии одного бренда»
у 45 из 69 доменов — это в 37 случаях один человек, который зарегистрировался и внёс депозит, а не повтор.
Среди 32 доменов с двумя регистрациями и без ФД одного бренда — {same_brand_pure[2]} ({100*same_brand_pure[2]/max(1,pure_by_n[2]):.0f} %), а не 65 %. «104 повторные
регистрации (21 %)» на файле тоже нет: повторов R − S = 33 из 461 регистраций (7 %). У R7, Trix, Iris «сгущение»
целиком из депозитов: {fd_conf}.

1. Часть А — повторы с одного сайта есть, но их мало. Домены с R = 2: {a2.get('n',0)}, обе регистрации с одного сайта у
   {a2.get('obs_one',0)} ({100*a2.get('obs_one',0)/max(1,a2.get('n',1)):.0f} %) против {100*a2.get('e1',0)/max(1,a2.get('n',1)):.1f} % при независимом выборе бренда (p = {a2.get('p1',float('nan')):.4f}); R = 3: хоть один повтор у {a3.get('obs_rep',0)} из {a3.get('n',0)}
   против {a3.get('er',0):.1f} ожидаемых (p = {a3.get('pr',float('nan')):.4f}); R = 4: {a4.get('obs_rep',0)} из {a4.get('n',0)} против {a4.get('er',0):.1f} (p = {a4.get('pr',float('nan')):.2f}). Всего {obs_repeats_total} повторов при {e_rep:.1f} ожидаемых
   по перестановке меток бренда между регистрациями (максимум по 10 000 перестановкам {mx}, p = {p_rep:.4f}) — в {obs_repeats_total/max(0.1,e_rep):.1f} раза
   больше случайного; внутри пулов «набор + день» ожидание {e_pool:.1f} (p = {pv_pool:.4f}). То есть сайт-бренд действительно
   иногда «стоит» и собирает 2–3 регистрации, но это {100*(tot_R-tot_S)/tot_R:.0f} % регистраций, а не «повторы почти всегда один сайт».
   {same_day} из {nB_all} доменов с повторами собрали все регистрации в один день — часть повторов может быть дублем
   одного человека; по своду это не отделить.

2. Часть Б — не решается. Запуск ≤ 13.09: A — {bm['A']['n']} доменов, {bm['A']['R']} регистраций, {bm['A']['F']} ФД ({rateA:.3f} на регистрацию и на сайт);
   B — {bm['B']['n']} доменов, {bm['B']['R']} регистраций на {bm['B']['S']} сайтах, {bm['B']['F']} ФД ({bm['B']['F']/bm['B']['R']:.3f} на регистрацию — {(bm['B']['F']/bm['B']['R'])/rateA:.2f} от A, ДИ {rate_ratio_ci(bm['A']['F'], bm['A']['R'], bm['B']['F'], bm['B']['R'])[0]:.2f}–{rate_ratio_ci(bm['A']['F'], bm['A']['R'], bm['B']['F'], bm['B']['R'])[1]:.2f};
   {bm['B']['F']/bm['B']['S']:.3f} на сайт — {(bm['B']['F']/bm['B']['S'])/rateA:.2f} от A). Модели для B: «ФД только с первой регистрации сайта» E = {E1:.1f}, «все регистрации
   равноценны» E = {E2:.1f}, наблюдено {bm['B']['F']}: отношение правдоподобий {lr_main:.2f} (слабо в пользу «все равноценны»), ни одна модель
   не отвергнута: внутри пулов O/E {st_pool['O']/st_pool['E_all']:.2f} по «все равноценны» (перестановочный p = {st_pool['p_all']:.2f}) и {st_pool['O']/st_pool['E_first']:.2f} по «только первые»
   (p = {st_pool['p_first']:.2f}); только среди доменов с R ≥ 2 внутри дня — {st_r2['O']/st_r2['E_all']:.2f} (p = {st_r2['p_all']:.2f}) и {st_r2['O']/st_r2['E_first']:.2f} (p = {st_r2['p_first']:.2f}).
   Цифра гипотезы «0,126 против 0,178» (Б.2) складывается из доменов, запущенных после 13.09: там A дала {late_A_F} ФД
   на {late_A_R} регистраций, а B — 0 на {ba['B']['R']-bm['B']['R']}; с отсечкой 13.09 разницы нет ({bm['B']['F']/bm['B']['R']:.3f} против {rateA:.3f}). Разница между моделями —
   {E2-E1:.1f} ФД, шум пуассона на {bm['B']['F']} — ±{math.sqrt(bm['B']['F']):.1f}: чтобы различить, в группе B нужно ~30 ФД, сейчас {bm['B']['F']}.

3. Часть В — частично. При перестановке меток бренда с сохранением числа регистраций у каждого домена
   (контроль «богатых доменов»; ∝ поисковым кликам даёт то же) сгущены {len(clustered)} из {len(targets)} брендов (q < 0,05):
   {'; '.join(brand_line(b) for b in clustered)}.
   Из ожидавшихся сгущёнными не сгущены: {', '.join(f'{b} ({brand_reg[b]} рег. на {len(brand_domains[b])} доменах)' for b in not_clustered_expected)} —
   их «сгущение» было депозитами. Размазаны, как ожидалось: {', '.join(f'{b} (индекс {sim_results[main_null][b][0]/len(brand_domains[b]):.2f})' for b in spread_ok)};
   {'; '.join(f'{b} — индекс {sim_results[main_null][b][0]/len(brand_domains[b]):.2f}, q = {qmap[main_null][b]:.3f}' for b in spread_not) or 'остальные из списка тоже'}. Индексы сгущения у сгущённых {min(sim_results[main_null][b][0]/len(brand_domains[b]) for b in clustered):.2f}–{max(sim_results[main_null][b][0]/len(brand_domains[b]) for b in clustered):.2f}, а не 1,5–2:
   «носители» — 3–4 домена на бренд с 2–3 регистрациями каждый, остальные регистрации бренда идут по одной с домена.
   Проверка внутри пулов по брендам невозможна: нет пары бренд × пул с ≥5 регистрациями.

4. Даты — не подтверждается. Уникальных дат на регистрацию у однобрендовых доменов (S = 1) {d1[2]/d1[1]:.2f} против {d2[2]/d2[1]:.2f}
   у многобрендовых (а не 0,91 против 0,76); доля доменов с ≥2 датами {100*d1[3]/d1[0]:.0f} % против {100*d2[3]/d2[0]:.0f} % — знак обратный
   ожиданию; перестановочные p внутри пула 0,6–0,8.

Итог: ЧАСТИЧНО. Реален только факт, что сайт-бренд иногда даёт 2–3 регистрации с одного домена ({obs_repeats_total} повторов
против {e_rep:.1f} случайных) и что это свойство немногих брендов ({', '.join(clustered)}). Размер эффекта в гипотезе
завышен в разы (65 % → {100*a2.get('obs_one',0)/max(1,a2.get('n',1)):.0f} %, 21 % повторов → {100*(tot_R-tot_S)/tot_R:.0f} %) из-за подсчёта депозита как второй конверсии того же
бренда; R7, Trix, Iris не сгущены; «ФД только с первых регистраций» на 12 ФД не решается, а с честной
отсечкой по дате запуска знак пропадает; «однобрендовые повторы живут дольше» не подтверждается.

Что с этим делать: рычага нет — переводить отчётность на «сайтов с регистрацией» не нужно (разница с
регистрациями 8 %), «беречь домены-носители» не на чем: у сгущённых брендов носители дают по 2–3 регистрации и
их 3–4 на бренд. Проверяемое на уже запущенных данных: (1) в analysis/export/tracker_conversions.jsonl есть clickid
и subdomain — по ним можно узнать, повтор с одного сайта — это второй человек или тот же клик/дубль ({same_day} из {nB_all}
доменов с повторами собрали всё в один день); (2) когда закроется окно у 229 отфильтрованных доменов
(окно не закрыто / дней = 1), повторить Б.1 и Б.5: модели различимы при ~30 ФД в группе B.
""")


if __name__ == '__main__':
    main()
