#!/usr/bin/env python3
"""
Гипотеза №18. Зона и семейство контента «выбирают» бренды.

Что проверяем.
  Таблицы «бренд × зона» (Martin 22 из 24 в .team при ожидании 15,6;
  Shuffle 12 из 12; Селектор 6 из 9 в .lol при 2,3; Money X 5 из 9 в .lol)
  и «бренд × семейство» (R7 8 из 11 в NEW и 0 в content-дата при 2,5;
  Селектор 7 из 9 в content-дата при 2) — неоднородны ли они ПОСЛЕ
  стратификации по пулу «набор контента + день» (зона) / дню запуска
  (семейство). Ожидание в формулировке гипотезы — наивное (доля зоны среди
  всех конверсий), а зона и семейство сцеплены с днём и контентом, поэтому
  наивные сдвиги могут быть тенью дня/контента. Наивные числа здесь
  воспроизводятся («как в гипотезе»), а решает стратифицированный расчёт.

Как проверяем.
  Источник — колонка «какие бренды конвертили» вида «Martin (5), Twin (2)»:
  N = регистраций + ФД бренда на домене за всё время (сумма сверяется с
  колонками «регистраций» и «ФД» по каждой строке). Оконной разбивки по
  брендам в своде нет, поэтому события — за всё время; это оговаривается.
  Фильтр: окно закрыто = да и дней ≠ 1 (число исключённых печатается).
  Выбросы 3615.team и 3286.team клики не дают, здесь клики не используются —
  они оставлены, их вклад в события печатается.

  Единица перестановки — домен (все события домена идут вместе с его
  меткой, как в данных). Бренды — с ≥7 конверсиями в анализируемом наборе.

  (а) Зона. Зоны team / lol / casino; buzz и «прочие» (по 3 конверсии)
      исключены — клетку на 3 событиях не проверить. Страта — пул
      «набор контента + день запуска» («КОНТЕНТ НЕ ЗАПИСАН» + день здесь
      работает как дневная страта, это оговорено; есть контрольный прогон
      без него). Ожидание клетки бренд × зона считается внутри каждого
      пула: E = Σ по пулам (событий бренда в пуле × доля зоны среди всех
      конверсий пула) — это взвешенный по событиям бренда вариант формулы
      из постановки («доля зоны среди конверсий тех же пулов, где бренд
      конвертировал»). Пул, где все домены в одной зоне, даёт O = E и
      ничего не вносит; вклад дают только «смешанные» пулы (домены ≥2 зон,
      ≥1 событие) — их число печатается; если их <15, страта не тянет, и
      решает уровень дня (он считается в любом случае).
      Статистика — χ² = Σ (O − E)² / E по клеткам таблицы на смешанных
      пулах (плюс Σ|O − E| как устойчивая к маленьким E проверка). Нуль —
      10 000 перестановок метки зоны между доменами внутри пула
      (random.seed(1)), O и E пересчитываются в каждой перестановке.
      Дополнительные нули: без страты (чтобы понять, была ли наивная
      таблица вообще необычной) и перестановка имени бренда между записями
      «домен × бренд × n» одного пула (сохраняет объёмы зон и доменов,
      но не число событий бренда).
      На бренд: (1) точный тест доли .team против ожидания пулов
      (пуассон-биномиальное распределение: каждое событие бренда в
      смешанном пуле — испытание с вероятностью «доля .team в пуле»;
      это тест из постановки, он считает события независимыми, хотя
      события одного домена сцеплены); (2) перестановочный p по χ² бренда
      по трём зонам (сцепку событий домена учитывает). Поправка
      Бенджамини–Хохберга по числу брендов. Число брендов «одной зоны»
      при ≥5 конверсиях — против того же нуля, и для каждого такого
      бренда — как часто он «одной зоны» на перестановках.
  (б) Семейство. content-дата / NEW / archive / nabory / прочие (Generator,
      clean, script, контроль, тест, прочее); «не записан» — отдельный
      прогон как шестое семейство (оно сцеплено с датой, дни до 24.08
      однородны и вклада не дают). Страта — день запуска (семейство
      вложено в набор, поэтому стратифицировать по пулу нельзя: на пару
      бренд × набор ≤2 домена — уровень отдельного набора недостижим, это
      надо сказать прямо). Ожидание, статистика и перестановки — как в (а),
      но метка — семейство, страта — день. Три нуля: перестановка семейства
      между доменами одного дня (по постановке); строже — между наборами
      контента одного дня (все домены набора несут одно семейство, поэтому
      честная единица — набор); и перестановка имени бренда между записями
      одного дня (семейство меняет число конверсий на домен, перестановка
      метки это ломает, а перестановка бренда сохраняет). Если нули
      расходятся, решает строгий.
  Контроль: те же глобальные тесты без фильтра окна (все 2077 строк —
  цифры постановки считались на них).

  Критерии из постановки. Зона: p < 0,05 и 3–5 брендов со сдвигом ×1,4–2;
  семейство: p < 0,05, 2–4 бренда ×2 и 1–3 бренда одного семейства.
  Альтернатива: p > 0,2 и ни один бренд не проходит FDR — зона/семейство
  меняют число конверсий, но не их брендовый состав.
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
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h18_brand_zone_family.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
NPERM = 10000
MIN_BRAND = 7      # бренды с ≥7 конверсиями — в таблицу и тест
MIN_SINGLE = 5     # «бренд одной зоны / одного семейства» при ≥5 конверсиях
MIN_MIXED = 15     # столько смешанных пулов нужно, чтобы страта «тянула»
ZONES = ['team', 'lol', 'casino']
FAM_MAIN = ['content-дата', 'NEW', 'archive', 'nabory', 'прочие']
FAM_OTHER = {'Generator', 'clean', 'script', 'контроль', 'тест', 'прочее'}
NAMED_ZONE = ['Martin', 'Shuffle', 'Селектор', 'Money X']
NAMED_FAM = ['R7', 'Селектор']
BRAND_RE = re.compile(r'^\s*(.+?)\s*\((\d+)\)\s*$')


class Tee:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def __call__(self, *args):
        s = ' '.join(str(a) for a in args)
        print(s)
        self.f.write(s + '\n')

    def close(self):
        self.f.close()


def toint(s):
    s = (s or '').strip()
    return int(s) if s else 0


def parse_brands(s):
    out = []
    for part in (s or '').split(','):
        part = part.strip()
        if not part:
            continue
        m = BRAND_RE.match(part)
        if not m:
            raise ValueError('не разобрано: %r' % part)
        out.append((m.group(1), int(m.group(2))))
    return out


def fam_of(f):
    return 'прочие' if f in FAM_OTHER else f


# ---------------------------------------------------------------- статистика
def bh_fdr(pvals):
    """Поправка Бенджамини–Хохберга: список q того же порядка, что p."""
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    q = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        val = min(prev, pvals[i] * m / rank)
        q[i] = val
        prev = val
    return q


def poisson_binomial_p(ps, k):
    """Точный двусторонний p: X = сумма независимых испытаний с вероятностями ps;
    p = сумма вероятностей исходов, не более вероятных, чем наблюдённый k
    (как в binom.test R)."""
    dist = [1.0]
    for p in ps:
        new = [0.0] * (len(dist) + 1)
        for j, v in enumerate(dist):
            new[j] += v * (1.0 - p)
            new[j + 1] += v * p
        dist = new
    if k < 0 or k >= len(dist):
        return 1.0
    pk = dist[k]
    return min(1.0, sum(v for v in dist if v <= pk * (1.0 + 1e-9)))


def ratio(o, e):
    if e <= 0:
        return '   —'
    return '%5.2f' % (o / e)


def fp(p):
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return '    —'
    return '%.4f' % p if p >= 0.0001 else '<1e-4'


# ---------------------------------------------------------------- анализ
def analyze(doms, labels, title, log, mode='label', unit=None, nperm=NPERM, named=(), brief=False):
    """doms: список словарей {name, label (индекс в labels), stratum, unit, recs [(brand, n)]}.
    mode='label': перестановка метки между доменами страты (unit=None) или между
                  группами доменов с одинаковым doms[i]['unit'] внутри страты;
    mode='brand': перестановка имени бренда между записями (домен, бренд, n) страты.
    Возвращает словарь итогов."""
    L = len(labels)
    n_dom = len(doms)
    tot = [sum(n for _, n in d['recs']) for d in doms]
    tot_b = collections.Counter()
    for d in doms:
        for b, n in d['recs']:
            tot_b[b] += n
    n_ev = sum(tot)
    brands = sorted(tot_b, key=lambda b: (-tot_b[b], b))
    bidx = {b: i for i, b in enumerate(brands)}
    nb = len(brands)
    recs0 = [[(bidx[b], n) for b, n in d['recs']] for d in doms]
    B5_0 = [bi for bi in range(nb) if tot_b[brands[bi]] >= MIN_SINGLE]
    B7_0 = [bi for bi in range(nb) if tot_b[brands[bi]] >= MIN_BRAND]

    # наивная таблица (как в гипотезе): E = N бренда × доля метки среди всех событий
    ev_lab = [0] * L
    for i, d in enumerate(doms):
        ev_lab[d['label']] += tot[i]
    Ofull = [[0] * L for _ in range(nb)]
    dom_b = [set() for _ in range(nb)]
    for i, d in enumerate(doms):
        for bi, n in recs0[i]:
            Ofull[bi][d['label']] += n
            dom_b[bi].add(i)

    # страты
    strata = collections.OrderedDict()
    for i, d in enumerate(doms):
        strata.setdefault(d['stratum'], []).append(i)
    mixed = []          # смешанные страты (списки индексов доменов): метки ≥2 и события ≥1
    mixed_units = []    # единицы перестановки метки внутри смешанной страты
    fixed_idx = []      # домены вне смешанных страт (их вклад постоянен)
    n_str_ev = 0
    for s, idx in strata.items():
        labs = set(doms[i]['label'] for i in idx)
        ev = sum(tot[i] for i in idx)
        if ev > 0:
            n_str_ev += 1
        if len(labs) >= 2 and ev > 0:
            mixed.append(idx)
            if unit is None:
                mixed_units.append([[i] for i in idx])
            else:
                g = collections.OrderedDict()
                for i in idx:
                    g.setdefault(doms[i]['unit'], []).append(i)
                mixed_units.append(list(g.values()))
        else:
            fixed_idx.extend(idx)
    mixed_dom = sum(len(idx) for idx in mixed)
    mixed_ev = sum(tot[i] for idx in mixed for i in idx)
    n_units_mixed = sum(len(u) for u in mixed_units)
    slots = [[(i, k) for i in idx for k in range(len(recs0[i]))] for idx in mixed]
    # события брендов в смешанных стратах
    mix_ev_b = [0] * nb
    mix_dom_b = [set() for _ in range(nb)]
    mix_str_b = [set() for _ in range(nb)]
    for k, idx in enumerate(mixed):
        for i in idx:
            for bi, n in recs0[i]:
                mix_ev_b[bi] += n
                mix_dom_b[bi].add(i)
                mix_str_b[bi].add(k)
    # постоянная часть счётчиков «по всем стратам» (для брендов одной метки и итогов)
    fixed_cnt = [[0] * L for _ in range(nb)]
    for i in fixed_idx:
        for bi, n in recs0[i]:
            fixed_cnt[bi][doms[i]['label']] += n

    lab0 = [d['label'] for d in doms]

    def compute(lab, recs):
        O = [[0] * L for _ in range(nb)]
        E = [[0.0] * L for _ in range(nb)]
        cnt = [row[:] for row in fixed_cnt]
        for idx in mixed:
            ev = [0] * L
            for i in idx:
                ev[lab[i]] += tot[i]
            S = float(sum(ev))
            share = [e / S for e in ev]
            for i in idx:
                r = recs[i]
                if not r:
                    continue
                li = lab[i]
                for bi, n in r:
                    O[bi][li] += n
                    cnt[bi][li] += n
                    Ei = E[bi]
                    for l in range(L):
                        Ei[l] += n * share[l]
        return O, E, cnt

    def stats(O, E, cnt):
        totc = [sum(row) for row in cnt]
        B7 = [bi for bi in range(nb) if totc[bi] >= MIN_BRAND]
        chi_b = [0.0] * nb
        l1 = 0.0
        for bi in B7:
            s = 0.0
            for l in range(L):
                e = E[bi][l]
                if e > 0:
                    s += (O[bi][l] - e) ** 2 / e
                    l1 += abs(O[bi][l] - e)
            chi_b[bi] = s
        chi = sum(chi_b[bi] for bi in B7)
        single_b = [totc[bi] >= MIN_SINGLE and sum(1 for l in range(L) if cnt[bi][l] > 0) == 1 for bi in range(nb)]
        d0 = [O[bi][0] - E[bi][0] for bi in range(nb)]
        return chi, l1, chi_b, sum(single_b), single_b, d0

    O0, E0, cnt0 = compute(lab0, recs0)
    chi0, l10, chi_b0, single0, single_b0, d00 = stats(O0, E0, cnt0)

    # перестановки
    rng = random.Random(1)
    ge_chi = ge_l1 = ge_single = 0
    ge_chi_b = [0] * nb
    ge_d0 = [0] * nb
    single_freq = [0] * nb
    sum_chi = 0.0
    sum_single = 0.0
    labp = list(lab0)
    recsp = [list(r) for r in recs0]
    for _ in range(nperm):
        if mode == 'label':
            for units in mixed_units:
                ul = [labp[u[0]] for u in units]
                rng.shuffle(ul)
                for u, v in zip(units, ul):
                    for i in u:
                        labp[i] = v
        else:
            for sl in slots:
                names = [recsp[i][k][0] for i, k in sl]
                rng.shuffle(names)
                for (i, k), bi in zip(sl, names):
                    recsp[i][k] = (bi, recsp[i][k][1])
        O, E, cnt = compute(labp, recsp)
        chi, l1, chi_b, single, single_b, d0 = stats(O, E, cnt)
        sum_chi += chi
        sum_single += single
        if chi >= chi0 - 1e-12:
            ge_chi += 1
        if l1 >= l10 - 1e-12:
            ge_l1 += 1
        if single >= single0:
            ge_single += 1
        for bi in B7_0:
            if chi_b[bi] >= chi_b0[bi] - 1e-12:
                ge_chi_b[bi] += 1
            if abs(d0[bi]) >= abs(d00[bi]) - 1e-12:
                ge_d0[bi] += 1
        for bi in B5_0:
            if single_b[bi]:
                single_freq[bi] += 1
    p_chi = (ge_chi + 1.0) / (nperm + 1)
    p_l1 = (ge_l1 + 1.0) / (nperm + 1)
    p_single = (ge_single + 1.0) / (nperm + 1)
    p_chi_b = {bi: (ge_chi_b[bi] + 1.0) / (nperm + 1) for bi in B7_0}
    p_d0 = {bi: (ge_d0[bi] + 1.0) / (nperm + 1) for bi in B7_0}

    # точный тест доли первой метки (пуассон-биномиальный) на бренд
    share_str = []
    for idx in mixed:
        ev = [0] * L
        for i in idx:
            ev[lab0[i]] += tot[i]
        S = float(sum(ev))
        share_str.append([e / S for e in ev])
    p_bin = {}
    for bi in B7_0:
        ps = []
        for k, idx in enumerate(mixed):
            for i in idx:
                for bj, n in recs0[i]:
                    if bj == bi:
                        ps.extend([share_str[k][0]] * n)
        p_bin[bi] = poisson_binomial_p(ps, int(O0[bi][0])) if ps else float('nan')
    q_bin = dict(zip(B7_0, bh_fdr([p_bin[bi] for bi in B7_0])))
    q_chi = dict(zip(B7_0, bh_fdr([p_chi_b[bi] for bi in B7_0])))

    null_desc = {('label', None): 'метки между доменами', ('label', 'unit'): 'метки между наборами контента',
                 ('brand', None): 'имени бренда между записями (домен × бренд × n)'}[(mode, unit)]

    # ---------------------------------------------------------------- печать
    log('')
    log('=' * 100)
    log(title)
    log('=' * 100)
    log('Доменов %d, событий (рег + ФД) %d; по меткам: %s' % (
        n_dom, n_ev, ', '.join('%s %d (%.0f%%)' % (labels[l], ev_lab[l], 100.0 * ev_lab[l] / n_ev) for l in range(L))))
    log('Страт всего %d, страт с событиями %d; смешанных страт (метки ≥2, событий ≥1): %d — в них доменов %d, событий %d (%.0f%% всех)%s' % (
        len(strata), n_str_ev, len(mixed), mixed_dom, mixed_ev, 100.0 * mixed_ev / n_ev if n_ev else 0,
        '' if unit is None else '; единиц перестановки (наборов) в смешанных стратах %d' % n_units_mixed))
    log('Брендов с ≥%d конверсиями: %d (%s)' % (MIN_BRAND, len(B7_0), ', '.join('%s %d' % (brands[bi], tot_b[brands[bi]]) for bi in B7_0)))
    if len(mixed) < MIN_MIXED and len(strata) > 1:
        log('!! Смешанных страт меньше %d — страта не тянет, этот прогон только для сведения.' % MIN_MIXED)

    w = max(len(brands[bi]) for bi in B7_0) + 1 if B7_0 else 10
    if not brief:
        log('')
        log('Таблица 1 (наивная, «как в гипотезе»): все события бренда, E = N × доля метки среди всех событий набора.')
        head = 'бренд'.ljust(w) + '  N дом' + ''.join(' | %s O   E   O/E' % labels[l][:7].rjust(7) for l in range(L))
        log(head)
        for bi in B7_0:
            b = brands[bi]
            N = tot_b[b]
            row = b.ljust(w) + '%3d %3d' % (N, len(dom_b[bi]))
            for l in range(L):
                e = N * ev_lab[l] / float(n_ev)
                row += ' | %9d %5.1f %s' % (Ofull[bi][l], e, ratio(Ofull[bi][l], e))
            log(row)

        log('')
        log('Таблица 2 (стратифицированная): только смешанные страты; E = Σ по стратам (событий бренда × доля метки в страте).')
        log('  N — все события бренда; Nсм/домсм/стрсм — события, домены и страты бренда в смешанных стратах;')
        log('  p-бин — точный тест доли «%s» (события как независимые); p-пер — перестановочный по χ² бренда по всем меткам; q — BH по %d брендам.' % (labels[0], len(B7_0)))
        head = 'бренд'.ljust(w) + '  N Nсм домсм стрсм' + ''.join(' | %s O    E   O/E' % labels[l][:7].rjust(7) for l in range(L)) + ' | p-бин  q-бин | p-пер  q-пер'
        log(head)
        for bi in B7_0:
            b = brands[bi]
            row = b.ljust(w) + '%3d %3d %5d %5d' % (tot_b[b], mix_ev_b[bi], len(mix_dom_b[bi]), len(mix_str_b[bi]))
            for l in range(L):
                row += ' | %9d %5.1f %s' % (O0[bi][l], E0[bi][l], ratio(O0[bi][l], E0[bi][l]))
            row += ' | %s %s | %s %s' % (fp(p_bin[bi]), fp(q_bin[bi]), fp(p_chi_b[bi]), fp(q_chi[bi]))
            log(row)
        log('Итого по %d брендам в смешанных стратах: O по меткам %s; E %s' % (
            len(B7_0), ' / '.join('%d' % sum(O0[bi][l] for bi in B7_0) for l in range(L)),
            ' / '.join('%.1f' % sum(E0[bi][l] for bi in B7_0) for l in range(L))))

    # именованные бренды из формулировки
    if named:
        log('')
        log('Бренды из формулировки гипотезы (в этом наборе; наивное O/E и O/E по смешанным стратам):')
        for b in named:
            if b not in bidx:
                log('  %-10s — в этом наборе конверсий нет' % b)
                continue
            bi = bidx[b]
            N = tot_b[b]
            naive = ', '.join('%s %d/%.1f' % (labels[l], Ofull[bi][l], N * ev_lab[l] / float(n_ev)) for l in range(L))
            strat = ', '.join('%s %d/%.1f' % (labels[l], O0[bi][l], E0[bi][l]) for l in range(L))
            extra = ''
            if bi in p_chi_b:
                extra = '; p-пер %s (q %s), p-бин %s' % (fp(p_chi_b[bi]), fp(q_chi[bi]), fp(p_bin[bi]))
            elif N < MIN_BRAND:
                extra = ' (<%d конверсий, в тест не входит)' % MIN_BRAND
            log('  %-10s N=%d: наивно [%s]; в смешанных стратах (%d событий) [%s]%s' % (b, N, naive, mix_ev_b[bi], strat, extra))

    log('')
    log('Глобальный тест (нуль — %d перестановок %s внутри страты):' % (nperm, null_desc))
    log('  χ² (O−E)²/E по таблице: наблюдённое %.1f, среднее на перестановках %.1f, p = %s' % (chi0, sum_chi / nperm, fp(p_chi)))
    log('  Σ|O−E|: наблюдённое %.1f, p = %s' % (l10, fp(p_l1)))
    log('  Брендов «одной метки» при ≥%d конверсиях: %d из %d (среднее на перестановках %.2f), p = %s' % (
        MIN_SINGLE, single0, len(B5_0), sum_single / nperm, fp(p_single)))
    singles = [bi for bi in B5_0 if single_b0[bi]]
    if singles:
        parts = []
        for bi in singles:
            l = [l for l in range(L) if cnt0[bi][l] > 0][0]
            s = '%s (%d в %s' % (brands[bi], tot_b[brands[bi]], labels[l])
            if mode == 'label':
                s += '; на перестановках так же в %.0f%% случаев' % (100.0 * single_freq[bi] / nperm)
            parts.append(s + ')')
        log('    это: %s' % '; '.join(parts))
    n_p05 = sum(1 for bi in B7_0 if p_chi_b[bi] < 0.05)
    n_q = sum(1 for bi in B7_0 if q_chi[bi] < 0.05)
    n_q10 = sum(1 for bi in B7_0 if q_chi[bi] < 0.10)
    n_bin05 = sum(1 for bi in B7_0 if p_bin[bi] < 0.05)
    n_binq = sum(1 for bi in B7_0 if q_bin[bi] < 0.05)
    log('  На бренд: перестановочный p < 0,05 у %d из %d; после BH q < 0,05 у %d, q < 0,10 у %d. Точный тест доли «%s»: p < 0,05 у %d, q < 0,05 у %d.' % (
        n_p05, len(B7_0), n_q, n_q10, labels[0], n_bin05, n_binq))
    shifted = []
    for bi in B7_0:
        for l in range(L):
            if E0[bi][l] >= 3 and O0[bi][l] / E0[bi][l] >= 1.4:
                shifted.append('%s → %s ×%.2f (%d/%.1f, p-пер %s)' % (brands[bi], labels[l], O0[bi][l] / E0[bi][l], O0[bi][l], E0[bi][l], fp(p_chi_b[bi])))
    log('  Клетки со сдвигом ×1,4 и больше при E ≥ 3 (в смешанных стратах): %d%s' % (len(shifted), (' — ' + '; '.join(shifted)) if shifted else ''))
    return {
        'p_chi': p_chi, 'p_l1': p_l1, 'chi0': chi0, 'chi_null': sum_chi / nperm, 'n_mixed': len(mixed),
        'mixed_ev': mixed_ev, 'n_ev': n_ev, 'n_dom': n_dom, 'nB': len(B7_0), 'n_p05': n_p05, 'n_q': n_q, 'n_q10': n_q10,
        'n_bin05': n_bin05, 'n_binq': n_binq, 'single': single0, 'single_null': sum_single / nperm, 'p_single': p_single,
        'singles': [brands[bi] for bi in singles], 'single_freq': {brands[bi]: single_freq[bi] / float(nperm) for bi in singles},
        'shifted': shifted, 'brands': brands, 'bidx': bidx, 'tot_b': tot_b, 'O0': O0, 'E0': E0, 'B7': B7_0,
        'p_chi_b': p_chi_b, 'q_chi': q_chi, 'p_bin': p_bin, 'Ofull': Ofull, 'ev_lab': ev_lab, 'mix_ev_b': mix_ev_b,
    }


def main():
    log = Tee(OUT)
    log('Гипотеза №18: зона и семейство контента «выбирают» бренды? Источник: %s' % os.path.relpath(SRC, REPO))
    with open(SRC, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    log('Строк (доменов) всего: %d' % len(rows))

    # разбор брендов и сверка
    all_ev = 0
    for r in rows:
        r['_recs'] = parse_brands(r['какие бренды конвертили'])
        n = sum(x[1] for x in r['_recs'])
        if n != toint(r['регистраций']) + toint(r['ФД']):
            raise SystemExit('не сходится сумма брендов у %s' % r['домен'])
        all_ev += n
    log('Событий (регистраций + ФД за всё время) во всех строках: %d — совпадает с суммой колонок «регистраций» и «ФД» построчно.' % all_ev)
    log('ВАЖНО: разбивка конверсий по брендам есть только за всё время, не в окне 3 суток; события здесь — за всё время.')

    # фильтр
    excl_open = [r for r in rows if r['окно закрыто'] != 'да']
    excl_day1 = [r for r in rows if r['окно закрыто'] == 'да' and r['дней'] == '1']
    base = [r for r in rows if r['окно закрыто'] == 'да' and r['дней'] != '1']
    log('Исключено: окно не закрыто — %d доменов (%d событий); дней = 1 при закрытом окне — %d доменов (%d событий). Осталось %d доменов, %d событий.' % (
        len(excl_open), sum(sum(n for _, n in r['_recs']) for r in excl_open),
        len(excl_day1), sum(sum(n for _, n in r['_recs']) for r in excl_day1),
        len(base), sum(sum(n for _, n in r['_recs']) for r in base)))
    out_ev = sum(sum(n for _, n in r['_recs']) for r in base if r['домен'] in OUTLIERS)
    log('Выбросы по кликам %s оставлены (клики не используются); их событий: %d.' % (', '.join(OUTLIERS), out_ev))
    n_noc = sum(1 for r in base if r['набор контента'] == NOCONTENT)
    log('«%s»: %d доменов (%d событий) — в части (а) это дневные страты (оговорено, есть контроль без них); в части (б) — отдельный прогон.' % (
        NOCONTENT, n_noc, sum(sum(n for _, n in r['_recs']) for r in base if r['набор контента'] == NOCONTENT)))

    def zone_doms(src, stratum, drop_nocontent=False):
        out = []
        for r in src:
            if r['зона'] not in ZONES:
                continue
            if drop_nocontent and r['набор контента'] == NOCONTENT:
                continue
            if stratum == 'pool':
                s = (r['набор контента'], r['день запуска'])
            elif stratum == 'day':
                s = r['день запуска']
            else:
                s = 'все'
            out.append({'name': r['домен'], 'label': ZONES.index(r['зона']), 'stratum': s, 'unit': None, 'recs': r['_recs']})
        return out

    def fam_doms(src, labels, stratum='day'):
        out = []
        for r in src:
            fam = fam_of(r['семейство'])
            if fam not in labels:
                continue
            out.append({'name': r['домен'], 'label': labels.index(fam), 'stratum': r['день запуска'] if stratum == 'day' else 'все',
                        'unit': r['набор контента'], 'recs': r['_recs']})
        return out

    # ---------------------------------------------------------------- (а) зона
    log('')
    log('#' * 100)
    log('ЧАСТЬ (а). БРЕНД × ЗОНА')
    log('#' * 100)
    zc = collections.Counter()
    ze = collections.Counter()
    for r in base:
        z = r['зона'] if r['зона'] in ('team', 'lol', 'casino', 'buzz') else 'прочие'
        zc[z] += 1
        ze[z] += sum(n for _, n in r['_recs'])
    log('Зоны после фильтра: %s.' % ', '.join('%s %d доменов / %d событий' % (z, zc[z], ze[z]) for z in ('team', 'lol', 'casino', 'buzz', 'прочие')))
    log('buzz и «прочие» исключены из части (а): %d доменов, %d событий — на 3 событиях клетку не проверить.' % (
        zc['buzz'] + zc['прочие'], ze['buzz'] + ze['прочие']))

    dz = zone_doms(base, 'pool')
    pools = collections.OrderedDict()
    for d in dz:
        p = pools.setdefault(d['stratum'], {'dom': [0] * 3, 'ev': [0] * 3})
        p['dom'][d['label']] += 1
        p['ev'][d['label']] += sum(n for _, n in d['recs'])
    mixed_pools = [(k, v) for k, v in pools.items() if sum(1 for x in v['dom'] if x) >= 2 and sum(v['ev']) > 0]
    log('')
    log('Смешанные пулы «набор контента + день» (домены ≥2 зон, ≥1 событие): %d. Домены team/lol/casino и события team/lol/casino:' % len(mixed_pools))
    for (nabor, day), v in sorted(mixed_pools, key=lambda kv: -sum(kv[1]['ev'])):
        log('  %s  %-32s домены %3d/%3d/%3d  события %3d/%3d/%3d' % (day, nabor[:32], v['dom'][0], v['dom'][1], v['dom'][2], v['ev'][0], v['ev'][1], v['ev'][2]))
    resA0 = analyze(zone_doms(base, 'none'), ZONES, '(а0) Зона БЕЗ страты — была ли наивная таблица вообще необычной (перестановка зоны между всеми доменами)', log, brief=True)
    resA = analyze(dz, ZONES, '(а1) Зона, страта — пул «набор контента + день», перестановка зоны между доменами пула (главный прогон)', log, named=NAMED_ZONE)
    resA_day = analyze(zone_doms(base, 'day'), ZONES, '(а2) Зона, страта — день запуска (запасной уровень, контроль контента слабее)', log, named=NAMED_ZONE)
    resA_noc = analyze(zone_doms(base, 'pool', drop_nocontent=True), ZONES,
                       '(а3) Контроль: зона по пулам без «%s»' % NOCONTENT, log, brief=True)
    resA_br = analyze(dz, ZONES, '(а4) Контроль: зона по пулам, нуль — перестановка имени бренда между записями пула (объёмы зон сохранены)', log, mode='brand', brief=True)

    # ---------------------------------------------------------------- (б) семейство
    log('')
    log('#' * 100)
    log('ЧАСТЬ (б). БРЕНД × СЕМЕЙСТВО КОНТЕНТА')
    log('#' * 100)
    fc = collections.Counter()
    fe = collections.Counter()
    for r in base:
        fc[r['семейство']] += 1
        fe[r['семейство']] += sum(n for _, n in r['_recs'])
    log('Семейства после фильтра (доменов/событий): %s.' % ', '.join('%s %d/%d' % (k, fc[k], fe[k]) for k, _ in fc.most_common()))
    log('«прочие» = %s.' % ', '.join(sorted(FAM_OTHER)))
    pair = collections.Counter()
    for r in base:
        for b, n in r['_recs']:
            pair[(b, r['набор контента'])] += 1
    log('Пар бренд × набор контента с конверсиями: %d; из них с ≥3 доменами %d, с 2 — %d, с 1 — %d → уровень отдельного набора недостижим, только семейство.' % (
        len(pair), sum(1 for v in pair.values() if v >= 3), sum(1 for v in pair.values() if v == 2), sum(1 for v in pair.values() if v == 1)))
    df = fam_doms(base, FAM_MAIN)
    resB0 = analyze(fam_doms(base, FAM_MAIN, 'none'), FAM_MAIN, '(б0) Семейство БЕЗ страты (без «не записан») — была ли наивная таблица необычной', log, brief=True)
    resB = analyze(df, FAM_MAIN, '(б1) Семейство без «не записан», страта — день, перестановка семейства между доменами дня (по постановке)', log, named=NAMED_FAM)
    resB_u = analyze(df, FAM_MAIN, '(б2) То же, строгий нуль: перестановка семейства между наборами контента одного дня', log, unit='unit', named=NAMED_FAM)
    resB_br = analyze(df, FAM_MAIN, '(б3) То же, нуль — перестановка имени бренда между записями одного дня (объёмы семейств и доменов сохранены)', log, mode='brand', brief=True)
    FAM6 = FAM_MAIN + ['не записан']
    df6 = fam_doms(base, FAM6)
    resB6 = analyze(df6, FAM6, '(б4) Семейство с «не записан» шестым, страта — день, перестановка между доменами дня', log, named=NAMED_FAM)
    resB6_u = analyze(df6, FAM6, '(б5) То же, строгий нуль: между наборами контента одного дня («не записан» + день = один набор)', log, unit='unit', brief=True)

    # ---------------------------------------------------------------- контроль без фильтра окна
    log('')
    log('#' * 100)
    log('КОНТРОЛЬ: ВСЕ %d СТРОК БЕЗ ФИЛЬТРА ОКНА (цифры постановки считались на них)' % len(rows))
    log('#' * 100)
    resA_all = analyze(zone_doms(rows, 'pool'), ZONES, '(к1) Зона по пулам, все строки', log, named=NAMED_ZONE, brief=True)
    resB_all = analyze(fam_doms(rows, FAM_MAIN), FAM_MAIN, '(к2) Семейство по дням, все строки, между наборами', log, unit='unit', named=NAMED_FAM, brief=True)

    # ---------------------------------------------------------------- ВЫВОД
    log('')
    log('=' * 100)
    log('ВЫВОД')
    log('=' * 100)

    def verdict_line(res, what):
        return '%s: χ² %.1f при среднем на перестановках %.1f, p = %s (Σ|O−E| p = %s); брендов с p < 0,05 — %d из %d, после BH q < 0,05 — %d; смешанных страт %d, событий в них %d из %d.' % (
            what, res['chi0'], res['chi_null'], fp(res['p_chi']), fp(res['p_l1']), res['n_p05'], res['nB'], res['n_q'], res['n_mixed'], res['mixed_ev'], res['n_ev'])

    log('Часть (а) — зона.')
    log('  ' + verdict_line(resA0, 'Без страты'))
    log('  ' + verdict_line(resA, 'Пул «набор контента + день» (главный)'))
    log('  ' + verdict_line(resA_day, 'День запуска'))
    log('  ' + verdict_line(resA_noc, 'Пул без «%s»' % NOCONTENT))
    log('  ' + verdict_line(resA_br, 'Пул, перестановка бренда'))
    log('  ' + verdict_line(resA_all, 'Все строки без фильтра окна, пул'))
    log('  Брендов «одной зоны» при ≥5 конверсиях: %d (на перестановках %.2f, p = %s)%s.' % (
        resA['single'], resA['single_null'], fp(resA['p_single']),
        (' — ' + ', '.join('%s (так же в %.0f%% перестановок)' % (b, 100 * resA['single_freq'][b]) for b in resA['singles'])) if resA['singles'] else ''))
    log('Часть (б) — семейство.')
    log('  ' + verdict_line(resB0, 'Без страты'))
    log('  ' + verdict_line(resB, 'День, перестановка между доменами (по постановке)'))
    log('  ' + verdict_line(resB_u, 'День, перестановка между наборами (строгий нуль)'))
    log('  ' + verdict_line(resB_br, 'День, перестановка бренда'))
    log('  ' + verdict_line(resB6, 'С «не записан», между доменами'))
    log('  ' + verdict_line(resB6_u, 'С «не записан», между наборами'))
    log('  ' + verdict_line(resB_all, 'Все строки без фильтра окна, между наборами'))
    log('  Брендов «одного семейства» при ≥5 конверсиях (без «не записан»): %d при ожидании %.2f — p = %s (между доменами), %s (между наборами), %s (перестановка бренда)%s.' % (
        resB['single'], resB['single_null'], fp(resB['p_single']), fp(resB_u['p_single']), fp(resB_br['p_single']),
        (' — ' + ', '.join('%s (так же в %.0f%% перестановок)' % (b, 100 * resB_u['single_freq'][b]) for b in resB_u['singles'])) if resB_u['singles'] else ''))
    log('  С «не записан» шестым семейством: %d при ожидании %.2f, p = %s%s.' % (
        resB6['single'], resB6['single_null'], fp(resB6['p_single']), (' — ' + ', '.join(resB6['singles'])) if resB6['singles'] else ''))

    def naive_vs_strat(res, labels, b):
        if b not in res['bidx']:
            return '%s: в наборе конверсий нет' % b
        bi = res['bidx'][b]
        N = res['tot_b'][b]
        parts = []
        for l in range(len(labels)):
            e_n = N * res['ev_lab'][l] / float(res['n_ev'])
            parts.append('%s наивно %d/%.1f → в страте %d/%.1f' % (labels[l], res['Ofull'][bi][l], e_n, res['O0'][bi][l], res['E0'][bi][l]))
        p = res['p_chi_b'].get(bi)
        tail = ('; p-пер %s, q %s' % (fp(p), fp(res['q_chi'][bi]))) if p is not None else ' (<%d конверсий, в тест не входит)' % MIN_BRAND
        return '%s (N=%d, в смешанных стратах %d): %s%s' % (b, N, res['mix_ev_b'][bi], '; '.join(parts), tail)

    log('Бренды из формулировки после стратификации:')
    for b in NAMED_ZONE:
        log('  ' + naive_vs_strat(resA, ZONES, b))
    for b in NAMED_FAM:
        log('  ' + naive_vs_strat(resB_u, FAM_MAIN, b))

    # итоговая словесная оценка — по числам
    a_p = [resA['p_chi'], resA_day['p_chi'], resA_noc['p_chi'], resA_br['p_chi']]
    b_p = [resB['p_chi'], resB_u['p_chi'], resB_br['p_chi'], resB6['p_chi'], resB6_u['p_chi']]
    a_sig = min(a_p) < 0.05
    a_null = min(a_p) > 0.2 and resA['n_q'] == 0 and resA_day['n_q'] == 0
    b_sig = resB_u['p_chi'] < 0.05 and resB['p_chi'] < 0.05
    b_null = min(b_p) > 0.2 and resB['n_q'] == 0 and resB_u['n_q'] == 0
    log('')
    log('Простыми словами.')
    if a_sig:
        log('  Зона: хотя бы в одном прогоне таблица бренд × зона неоднородна (p < 0,05): %s — см. таблицы, нужно смотреть, устойчив ли сдвиг.' % (
            '; '.join(resA['shifted']) if resA['shifted'] else 'см. таблицу 2'))
    elif a_null:
        log('  Зона: после стратификации по пулу «набор контента + день» таблица бренд × зона не отличается от случайной (p = %s; по дню %s; без «%s» %s; при перестановке бренда %s), ни один из %d брендов не проходит поправку на множественность.' % (
            fp(resA['p_chi']), fp(resA_day['p_chi']), NOCONTENT, fp(resA_noc['p_chi']), fp(resA_br['p_chi']), resA['nB']))
        if resA0['p_chi'] > 0.2:
            log('  Даже без страты наивная таблица не необычна (p = %s): сдвиги из формулировки (Martin, Shuffle → .team; Селектор, Money X → .lol) — обычный разброс при 5–25 событиях на бренд, а не скрытый эффект зоны.' % fp(resA0['p_chi']))
        else:
            log('  Без страты наивная таблица выглядела необычной (p = %s), но внутри пулов сдвиг исчезает — это была тень дня и контента.' % fp(resA0['p_chi']))
        log('  Зона меняет число конверсий, а не их брендовый состав; общего коэффициента зоны достаточно. .lol сокращать можно, не теряя «своих» брендов.')
    else:
        log('  Зона: результат промежуточный (p = %s по пулу, %s по дню; после BH q < 0,05 у %d брендов) — см. таблицы, эффект слабый или нестабильный.' % (
            fp(resA['p_chi']), fp(resA_day['p_chi']), resA['n_q']))
    if b_sig:
        log('  Семейство: после стратификации по дню таблица бренд × семейство неоднородна и по мягкому, и по строгому нулю (p = %s / %s): %s.' % (
            fp(resB['p_chi']), fp(resB_u['p_chi']), '; '.join(resB_u['shifted']) if resB_u['shifted'] else 'см. таблицу 2'))
    elif b_null:
        log('  Семейство: после стратификации по дню таблица бренд × семейство не отличается от случайной (p = %s между доменами, %s между наборами, %s при перестановке бренда; с «не записан» %s / %s), ни один бренд не проходит поправку.' % (
            fp(resB['p_chi']), fp(resB_u['p_chi']), fp(resB_br['p_chi']), fp(resB6['p_chi']), fp(resB6_u['p_chi'])))
        log('  Семейство контента меняет число конверсий, а не то, какие бренды их приносят; известного коэффициента семейства достаточно.')
    else:
        log('  Семейство: результат промежуточный (p = %s между доменами, %s между наборами, %s при перестановке бренда; q < 0,05 у %d брендов) — см. таблицы.' % (
            fp(resB['p_chi']), fp(resB_u['p_chi']), fp(resB_br['p_chi']), resB_u['n_q']))
    if resB['singles']:
        label_sig = resB['p_single'] < 0.05 or resB_u['p_single'] < 0.05
        brand_sig = resB_br['p_single'] < 0.05
        log('  Единственный намёк — бренды «одного семейства»: %s. Таких %d.' % (
            ', '.join('%s (%d из %d в %s)' % (b, resB['tot_b'][b], resB['tot_b'][b], FAM_MAIN[[l for l in range(len(FAM_MAIN)) if resB['Ofull'][resB['bidx'][b]][l] > 0][0]]) for b in resB['singles']),
            resB['single']))
        log('    По нулю «перестановка семейства» ожидается %.1f (p = %s между доменами, %s между наборами); по нулю «перестановка бренда» — %.1f (p = %s).' % (
            resB['single_null'], fp(resB['p_single']), fp(resB_u['p_single']), resB_br['single_null'], fp(resB_br['p_single'])))
        if label_sig and not brand_sig:
            log('    Расхождение нулей объяснимо: NEW даёт больше конверсий на домен (известный эффект объёма), поэтому перестановка метки семейства')
            log('    занижает шанс, что все 5–8 конверсий бренда лягут на NEW-домены; нуль, сохраняющий объёмы доменов и семейств, этого не делает — и намёк исчезает.')
        elif label_sig and brand_sig:
            log('    Намёк держится по обоим нулям — это единственное, что стоит проверить новыми запусками.')
        else:
            log('    На перестановках столько же выходит регулярно — совпадение.')
        log('    С «не записан» шестым семейством: %d при ожидании %.1f, p = %s%s.' % (
            resB6['single'], resB6['single_null'], fp(resB6['p_single']),
            ' — R7 и Fenix конвертили и на августовском незаписанном контенте, «только NEW» и в этом смысле неверно' if not any(b in ('R7', 'Fenix') for b in resB6['singles']) else ''))
        log('    По стратифицированной таблице R7 в NEW %d при ожидании %.1f (×%.2f, p-пер %s) — 4 домена по 2 конверсии; на таком объёме «все в NEW» от совпадения не отличить.' % (
            resB['O0'][resB['bidx']['R7']][1], resB['E0'][resB['bidx']['R7']][1],
            resB['O0'][resB['bidx']['R7']][1] / resB['E0'][resB['bidx']['R7']][1], fp(resB['p_chi_b'].get(resB['bidx']['R7']))) if 'R7' in resB['bidx'] and resB['E0'][resB['bidx']['R7']][1] > 0 else '')
    log('  Оговорки: события — за всё время (оконной разбивки по брендам нет); тест слабый — %d событий на %d брендов, в смешанных пулах лишь %d;' % (resA['n_ev'], resA['nB'], resA['mixed_ev']))
    log('  уровень отдельного набора контента недостижим (≤2 домена на пару бренд × набор), проверено только семейство; buzz с 3 событиями не проверялся.')
    log.close()


if __name__ == '__main__':
    main()
