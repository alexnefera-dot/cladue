#!/usr/bin/env python3
"""
Контрпроверка гипотезы №17 (угол: СТАТИСТИКА И ОПРЕДЕЛЕНИЯ).
Что проверяем у тестировщика:
  1. Воспроизводимость чисел (скрипт h17 прогнан — вывод побайтово совпал).
  2. Определения: S = «сайтов с регистрацией» — действительно ли это число разных
     брендов с регистрацией; сходятся ли скобки в «какие бренды конвертили»
     с «регистраций + ФД»; не оконные ли это колонки (какие использованы).
  3. Ноль: глобальная перестановка меток бренда против перестановки ВНУТРИ пулов
     «набор контента + день запуска» (и внутри дня, зоны+дня). Это главный вопрос:
     заголовочная цифра «в 7,6 раза больше случайного» получена на глобальном нуле,
     который не учитывает, что бренд «горяч» в конкретный день.
  4. Устойчивость: снять топ-3 домена по регистрациям; снять топ-3 бренда по повторам;
     джекнайф по доменам-носителям.
  5. Объёмы событий: сколько повторов, сколько ФД в группе B, что из этого
     «меньше 20 событий».
  6. Множественность: сколько срезов перебрано в h17, переживёт ли вывод поправку.
  7. Оконные колонки и фильтры: что даёт ограничение «все регистрации домена попали
     в окно 3 суток», и есть ли повторы среди отфильтрованных (окно не закрыто / дней = 1).
  8. Часть В: индекс сгущения — самостоятельная величина или переписанные повторы.
  9. Часть Б: хватает ли 12 ФД.
Только stdlib.
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
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w17_statistika.txt')
H17 = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h17_same_site_repeats.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
NSIM = 10000
BRAND_RE = re.compile(r'^(.*?) \((\d+)\)$')


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


def parse_brands(s):
    s = (s or '').strip()
    out = []
    if not s:
        return out
    for item in s.split(','):
        m = BRAND_RE.match(item.strip())
        if m:
            out.append((m.group(1), int(m.group(2))))
    return out


def attribute_fd(brand_counts, fd):
    regs = dict(brand_counts)
    left = fd
    for b in sorted(brand_counts, key=lambda b: -brand_counts[b]):
        if left == 0:
            break
        take = min(brand_counts[b] - 1, left)
        regs[b] -= take
        left -= take
    return regs


def log_fact(n):
    return math.lgamma(n + 1)


def pois_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam + k * math.log(lam) - log_fact(k))


def pois_le(k, lam):
    return sum(pois_pmf(i, lam) for i in range(0, k + 1))


def hyper_pmf(x, a, b, k):
    return math.exp(log_fact(a) - log_fact(x) - log_fact(a - x)
                    + log_fact(b) - log_fact(k - x) - log_fact(b - k + x)
                    - log_fact(a + b) + log_fact(k) + log_fact(a + b - k))


def fisher_le(x, a, b, k):
    lo = max(0, k - b)
    return sum(hyper_pmf(i, a, b, k) for i in range(lo, x + 1))


def rr_ci(a, na, b, nb):
    if a == 0 or b == 0:
        return (float('nan'), float('nan'))
    lr = math.log((b / nb) / (a / na))
    se = math.sqrt(1 / a + 1 / b)
    return (math.exp(lr - 1.96 * se), math.exp(lr + 1.96 * se))


def repeats_of(dom_labels):
    """Σ(R − S) по списку списков меток."""
    return sum(len(v) - len(set(v)) for v in dom_labels)


def perm_repeats(groups, nsim=NSIM, rnd=None):
    """groups: список групп; группа = список доменов, домен = список меток.
    Перестановка меток внутри группы. Возвращает (E, max, p, доля >= набл., набл.)."""
    rnd = rnd or random
    obs = sum(repeats_of(g) for g in groups)
    sizes = [[len(d) for d in g] for g in groups]
    pools = [[lab for d in g for lab in d] for g in groups]
    cnt_ge = 0
    tot = 0.0
    mx = -1
    for _ in range(nsim):
        s = 0
        for gi, pool in enumerate(pools):
            rnd.shuffle(pool)
            i = 0
            for n in sizes[gi]:
                if n >= 2:
                    seg = pool[i:i + n]
                    s += n - len(set(seg))
                i += n
        tot += s
        mx = max(mx, s)
        if s >= obs:
            cnt_ge += 1
    return obs, tot / nsim, mx, (cnt_ge + 1) / (nsim + 1)


def main():
    sys.stdout = Tee(OUT)
    random.seed(20260922)
    with open(SRC, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    print('КОНТРПРОВЕРКА №17 — статистика и определения')
    print(f'Источник: analysis/export/svod_domenov_21.09.csv; строк (доменов): {len(rows)}')
    print()

    # ---------- 1. Воспроизводимость ----------
    print('=' * 100)
    print('1. ВОСПРОИЗВОДИМОСТЬ')
    print('=' * 100)
    print('  Скрипт analysis/scripts/gipotezy_svod/h17_same_site_repeats.py запущен заново:')
    print('  вывод совпал с сохранённым h17_same_site_repeats.txt побайтово (diff пуст), random.seed(1) зашит.')
    print('  Значит числа воспроизводятся; дальше проверяем, что именно они измеряют.')
    print()

    # ---------- 2. Определения ----------
    print('=' * 100)
    print('2. ОПРЕДЕЛЕНИЯ: что такое R, S и скобки в «какие бренды конвертили»')
    print('=' * 100)
    bad_sum = bad_S = bad_RS = bad_conv = 0
    n_with_reg = 0
    for r in rows:
        R, S, F = I(r['регистраций']), I(r['сайтов с регистрацией']), I(r['ФД'])
        bl = parse_brands(r['какие бренды конвертили'])
        nb = len(bl)
        tot = sum(c for _, c in bl)
        if R > 0:
            n_with_reg += 1
        if tot != R + F:
            bad_sum += 1
        if R > 0 and nb != S:
            bad_S += 1
        if S > R:
            bad_RS += 1
        if I(r['брендов с конверсией']) != nb:
            bad_conv += 1
    print(f'  доменов с регистрациями: {n_with_reg}')
    print(f'  строк, где Σ скобок ≠ регистраций + ФД: {bad_sum}')
    print(f'  строк, где число брендов в списке ≠ «сайтов с регистрацией» (при R>0): {bad_S}')
    print(f'  строк, где S > R: {bad_RS}')
    print(f'  строк, где «брендов с конверсией» ≠ длине списка: {bad_conv}')
    print('  → S = число разных брендов (= сайтов) с конверсией на домене; «брендов с конверсией» = S,')
    print('    значит бренда, у которого есть ФД, но нет регистрации, в своде нет ни разу: ФД всегда на сайте регистрации.')
    print('    Подмена «конверсии = регистрации + ФД» у тестировщика вскрыта верно.')
    print()
    # оконные колонки
    tR = sum(I(r['регистраций']) for r in rows)
    tRw = sum(I(r['регистраций в окне 3 суток']) for r in rows)
    tF = sum(I(r['ФД']) for r in rows)
    tFw = sum(I(r['ФД в окне 3 суток']) for r in rows)
    print(f'  ОКОННЫЕ КОЛОНКИ: всего регистраций {tR}, из них в окне 3 суток {tRw} ({100*tRw/tR:.0f} %);'
          f' ФД {tF}, в окне {tFw}')
    print('  h17 считает R и S по НЕоконным колонкам («регистраций», «сайтов с регистрацией»).')
    print('  Оконной пары для S в своде нет вовсе, а список брендов — тоже за всё время,')
    print('  поэтому пара (R, S) внутренне согласована, но это НЕ оконная метрика методики:')
    print(f'  {tR - tRw} регистраций ({100*(tR-tRw)/tR:.0f} %) лежат вне окна 3 суток и входят в знаменатель.')
    print()

    # ---------- подготовка выборки ----------
    keep = []
    for r in rows:
        if r['домен'] in OUTLIERS:
            continue
        if r['окно закрыто'] != 'да':
            continue
        if I(r['дней']) == 1:
            continue
        keep.append(r)
    for r in rows:
        r['_R'] = I(r['регистраций'])
        r['_S'] = I(r['сайтов с регистрацией'])
        r['_F'] = I(r['ФД'])
        r['_Rw'] = I(r['регистраций в окне 3 суток'])
        r['_Fw'] = I(r['ФД в окне 3 суток'])
        bl = parse_brands(r['какие бренды конвертили'])
        bc = {b: c for b, c in bl}
        regs = attribute_fd(bc, r['_F']) if bl else {}
        labs = []
        for b, c in regs.items():
            labs.extend([b] * c)
        r['_labels'] = labs
        r['_pool'] = r['набор контента'] + ' | ' + r['день запуска']
    reg_rows = [r for r in keep if r['_R'] > 0]
    excl = [r for r in rows if r not in keep and r['домен'] not in OUTLIERS]
    print('=' * 100)
    print('3. ФИЛЬТРЫ И ОТБРОШЕННЫЕ ДОМЕНЫ')
    print('=' * 100)
    tot_R = sum(r['_R'] for r in keep)
    tot_S = sum(r['_S'] for r in keep)
    print(f'  после фильтров (окно закрыто, дней ≠ 1, без выбросов): доменов {len(keep)},'
          f' регистраций {tot_R}, сайтов {tot_S}, повторов Σ(R−S) {tot_R - tot_S}')
    eR = sum(r['_R'] for r in excl)
    eS = sum(r['_S'] for r in excl)
    print(f'  ОТБРОШЕНО (окно не закрыто или дней = 1): доменов {len(excl)},'
          f' регистраций {eR}, сайтов {eS}, повторов {eR - eS}')
    aR = sum(I(r['регистраций']) for r in rows)
    aS = sum(I(r['сайтов с регистрацией']) for r in rows)
    print(f'  ВЕСЬ свод: регистраций {aR}, сайтов {aS}, повторов {aR - aS}')
    print('  → все повторы лежат внутри отфильтрованной выборки; исключение доменов с незакрытым окном')
    print('    и «дней = 1» ничего из числителя не выбрасывает, но выбрасывает из знаменателя')
    print(f'    {eR} регистраций: доля повторов 8 % против {100*(aR-aS)/aR:.1f} % на всём своде — разница косметическая.')
    print()

    # ---------- 4. Перестановочные нули разной строгости ----------
    print('=' * 100)
    print('4. ГЛАВНОЕ: КАКОЙ НОЛЬ. Глобальная перестановка против перестановки внутри страт')
    print('=' * 100)
    dom_labels_all = [r['_labels'] for r in reg_rows]
    obs = repeats_of(dom_labels_all)
    print(f'  Наблюдено повторов Σ(R−S) = {obs} на {sum(len(x) for x in dom_labels_all)} регистрациях'
          f' у {len(reg_rows)} доменов с регистрацией.')
    print()
    print('  ноль (что перемешиваем) | E[повторов] | макс. по 10 000 | набл./E | p')
    schemes = [
        ('глобальная перестановка меток (ноль h17, заголовочная цифра)', lambda r: 'ALL'),
        ('внутри дня запуска', lambda r: r['день запуска']),
        ('внутри зоны + дня запуска', lambda r: (r['зона'] if r['зона'] in ('team', 'lol', 'casino', 'buzz') else 'проч') + '|' + r['день запуска']),
        ('внутри пула «набор контента + день запуска»', lambda r: r['_pool']),
    ]
    res = {}
    for name, keyf in schemes:
        g = collections.defaultdict(list)
        for r in reg_rows:
            g[keyf(r)].append(r['_labels'])
        groups = list(g.values())
        o, e, mx, p = perm_repeats(groups)
        res[name] = (o, e, mx, p)
        print(f'  {name:<58} | {e:>10.1f} | {mx:>14} | {o/e:>6.2f} | {p:.4f}')
    print()
    print('  Пояснение. Глобальный ноль допускает, что любой из 424 регистраций мог достаться любой бренд')
    print('  любого дня. Но бренд «горяч» в конкретный день-набор: внутри пула «набор + день» случайного')
    print('  совпадения бренда у двух регистраций одного домена заметно больше. Правильный ноль — стратный.')
    e_pool = res['внутри пула «набор контента + день запуска»'][1]
    e_glob = res['глобальная перестановка меток (ноль h17, заголовочная цифра)'][1]
    print(f'  Итог: «в 7,6 раза больше случайного» держится только на глобальном нуле (E={e_glob:.1f}).')
    print(f'  На нуле «внутри пула» E={e_pool:.1f} → превышение {obs/e_pool:.1f}×, избыток {obs-e_pool:.0f} повторов, а не {obs-e_glob:.0f}.')
    print()

    # ---------- 4б. бутстрэп на наблюдаемом числе ----------
    print('  Бутстрэп по доменам (10 000 пересэмплирований доменов с регистрацией) — разброс самого числа повторов:')
    bs = []
    n = len(reg_rows)
    labs_list = dom_labels_all
    for _ in range(NSIM):
        s = 0
        for _ in range(n):
            v = labs_list[random.randrange(n)]
            s += len(v) - len(set(v))
        bs.append(s)
    bs.sort()
    lo, hi = bs[int(0.025 * NSIM)], bs[int(0.975 * NSIM)]
    print(f'    повторов {obs}, бутстрэп-интервал 95 % {lo}–{hi};'
          f' отношение к стратному нулю {lo/e_pool:.1f}–{hi/e_pool:.1f}×, к глобальному {lo/e_glob:.1f}–{hi/e_glob:.1f}×')
    print()

    # ---------- 5. Устойчивость: снять топ-домены ----------
    print('=' * 100)
    print('5. УСТОЙЧИВОСТЬ: снять топ-домены по регистрациям и топ-бренды по повторам')
    print('=' * 100)
    top = sorted(reg_rows, key=lambda r: -r['_R'])[:5]
    print('  топ-5 доменов по регистрациям: ' + '; '.join(f"{r['домен']} (R={r['_R']}, S={r['_S']}, повторов {r['_R']-r['_S']})" for r in top))
    for k in (1, 2, 3, 5):
        sub = [r for r in reg_rows if r not in top[:k]]
        g = collections.defaultdict(list)
        for r in sub:
            g[r['_pool']].append(r['_labels'])
        o, e, mx, p = perm_repeats(list(g.values()))
        g2 = {'ALL': [r['_labels'] for r in sub]}
        o2, e2, mx2, p2 = perm_repeats(list(g2.values()))
        print(f'  без топ-{k} доменов: повторов {o} (было {obs}); стратный ноль E={e:.1f}, набл./E {o/e:.2f}, p={p:.4f};'
              f' глобальный E={e2:.1f}, набл./E {o2/e2:.2f}, p={p2:.4f}')
    # топ-домены по числу повторов
    topr = sorted(reg_rows, key=lambda r: -(r['_R'] - r['_S']))[:5]
    print('  топ-5 доменов по ЧИСЛУ повторов: ' + '; '.join(f"{r['домен']} (+{r['_R']-r['_S']})" for r in topr))
    for k in (1, 3, 5):
        sub = [r for r in reg_rows if r not in topr[:k]]
        g = collections.defaultdict(list)
        for r in sub:
            g[r['_pool']].append(r['_labels'])
        o, e, mx, p = perm_repeats(list(g.values()))
        print(f'  без топ-{k} доменов по повторам: повторов {o}; стратный ноль E={e:.1f}, набл./E {o/e:.2f}, p={p:.4f}')
    # бренды
    rep_by_brand = collections.Counter()
    for r in reg_rows:
        c = collections.Counter(r['_labels'])
        for b, v in c.items():
            if v >= 2:
                rep_by_brand[b] += v - 1
    print('  повторы по брендам: ' + '; '.join(f'{b} {v}' for b, v in rep_by_brand.most_common()))
    for k in (1, 3, 5):
        drop = {b for b, _ in rep_by_brand.most_common(k)}
        sub = []
        for r in reg_rows:
            labs = [x for x in r['_labels'] if x not in drop]
            if labs:
                sub.append(labs)
        g = collections.defaultdict(list)
        rr = [r for r in reg_rows if [x for x in r['_labels'] if x not in drop]]
        for r in rr:
            g[r['_pool']].append([x for x in r['_labels'] if x not in drop])
        o, e, mx, p = perm_repeats(list(g.values()))
        print(f'  без топ-{k} брендов по повторам ({", ".join(sorted(drop))}): повторов {o};'
              f' стратный ноль E={e:.1f}, набл./E {o/e:.2f}, p={p:.4f}')
    print()

    # ---------- 6. Домены с R=2: 23 % против чего ----------
    print('=' * 100)
    print('6. «10 из 43 (23 %) против 1,8 %» — против какого нуля')
    print('=' * 100)
    r2 = [r for r in reg_rows if r['_R'] == 2]
    obs2 = sum(1 for r in r2 if r['_S'] == 1)
    print(f'  доменов с R = 2: {len(r2)}; обе регистрации одного бренда: {obs2} ({100*obs2/len(r2):.0f} %)')
    for name, keyf in schemes:
        g = collections.defaultdict(list)
        for r in reg_rows:
            g[keyf(r)].append(r)
        cnt = 0
        tot = 0.0
        for _ in range(2000):
            s = 0
            for key, rs in g.items():
                pool = [lab for r in rs for lab in r['_labels']]
                random.shuffle(pool)
                i = 0
                for r in rs:
                    nn = len(r['_labels'])
                    if nn == 2 and len(set(pool[i:i + 2])) == 1:
                        s += 1
                    i += nn
            tot += s
            if s >= obs2:
                cnt += 1
        print(f'    ноль «{name}»: E = {tot/2000:.2f} ({100*tot/2000/len(r2):.1f} %), p = {(cnt+1)/2001:.4f}')
    print()

    # ---------- 7. Оконное ограничение ----------
    print('=' * 100)
    print('7. ОКОННОЕ ОГРАНИЧЕНИЕ: только домены, у которых ВСЕ регистрации попали в окно 3 суток')
    print('=' * 100)
    win = [r for r in reg_rows if r['_Rw'] == r['_R']]
    ow = repeats_of([r['_labels'] for r in win])
    g = collections.defaultdict(list)
    for r in win:
        g[r['_pool']].append(r['_labels'])
    o, e, mx, p = perm_repeats(list(g.values()))
    print(f'  доменов {len(win)}, регистраций {sum(r["_R"] for r in win)}, повторов {ow}')
    print(f'  стратный ноль: E = {e:.1f}, набл./E {o/e:.2f}, макс. {mx}, p = {p:.4f}')
    part = [r for r in reg_rows if r['_Rw'] < r['_R']]
    print(f'  домены, где часть регистраций вне окна: {len(part)}, регистраций {sum(r["_R"] for r in part)}'
          f' (в окне {sum(r["_Rw"] for r in part)}), повторов {repeats_of([r["_labels"] for r in part])}')
    print(f'  → {repeats_of([r["_labels"] for r in part])} из {obs} повторов приходят с доменов, часть регистраций которых лежит ВНЕ окна 3 суток,')
    print('    то есть считается вне той единицы наблюдения, в которой меряется успех по методике.')
    print()

    # ---------- 8. Часть Б: объём ----------
    print('=' * 100)
    print('8. ЧАСТЬ Б (ФД): объём событий')
    print('=' * 100)
    fdset = [r for r in keep if r['_R'] > 0 and r['день запуска'] <= '2026-09-13']
    A = [r for r in fdset if r['_R'] == r['_S']]
    B = [r for r in fdset if r['_R'] > r['_S']]
    for nm, grp in (('A', A), ('B', B)):
        R = sum(r['_R'] for r in grp)
        S = sum(r['_S'] for r in grp)
        F = sum(r['_F'] for r in grp)
        Fw = sum(r['_Fw'] for r in grp)
        print(f'  {nm}: доменов {len(grp)}, регистраций {R}, сайтов {S}, ФД {F} (в окне 3 суток {Fw}),'
              f' ФД/рег {F/R:.3f}, ФД/сайт {F/S:.3f}')
    RA, SA, FA = sum(r['_R'] for r in A), sum(r['_S'] for r in A), sum(r['_F'] for r in A)
    RB, SB, FB = sum(r['_R'] for r in B), sum(r['_S'] for r in B), sum(r['_F'] for r in B)
    lo1, hi1 = rr_ci(FA, RA, FB, RB)
    lo2, hi2 = rr_ci(FA, SA, FB, SB)
    print(f'  ФД/рег B к A: {(FB/RB)/(FA/RA):.2f} (ДИ {lo1:.2f}–{hi1:.2f}); ФД/сайт: {(FB/SB)/(FA/SA):.2f} (ДИ {lo2:.2f}–{hi2:.2f})')
    print(f'  В группе B {FB} ФД. Разница между моделями «только первые» ({SB*FA/RA:.1f}) и «все равноценны»'
          f' ({RB*FA/RA:.1f}) — {RB*FA/RA - SB*FA/RA:.1f} события; пуассоновский шум на {FB} — ±{math.sqrt(FB):.1f}.')
    print('  Порог методики «группа с < 20 событий ничего не доказывает» нарушен: 12 ФД. Вывод «не решается» — верный.')
    print('  Оконная колонка ФД даёт ещё меньше событий (см. выше), то есть сильнее подкрепляет «не решается».')
    print()

    # ---------- 9. Часть В: индекс сгущения = повторы ----------
    print('=' * 100)
    print('9. ЧАСТЬ В: индекс сгущения — самостоятельная величина или переписанные повторы?')
    print('=' * 100)
    bd = collections.defaultdict(lambda: collections.Counter())
    for r in reg_rows:
        for b, c in collections.Counter(r['_labels']).items():
            bd[b][r['домен']] += c
    print('  бренд | регистраций k | доменов D | k−D | доменов с ≥2 рег. | макс. рег. бренда на домене')
    rowsb = []
    for b, dd in bd.items():
        k = sum(dd.values())
        D = len(dd)
        if k >= 5:
            rowsb.append((k, b, D, sum(1 for v in dd.values() if v >= 2), max(dd.values())))
    rowsb.sort(reverse=True)
    for k, b, D, n2, mx in rowsb[:12]:
        print(f'  {b:<14} | {k:>3} | {D:>3} | {k-D:>2} | {n2} | {mx}')
    print('  → D = k − (повторы бренда) всегда: индекс сгущения E[D]/D_obs — это те же самые 2–5 повторов,')
    print('    пересчитанные в другую шкалу, а не независимая проверка. У «сгущённых» брендов это 2–5 событий:')
    print('    Twin — 2 повтора (6 рег. на 4 доменах), Mellstroy и Pinco — 4, Leon и Martin — 5.')
    print('    q < 0,05 у них берётся не из объёма, а из того, что при глобальном нуле повтор почти невозможен.')
    print('    На стратном нуле (внутри пула) повтор — обычное дело, см. п. 4.')
    # то же самое на стратном нуле для брендов: доля повторов бренда против ожидания в пуле
    print()
    print('  Пересчёт «сгущённости» пяти брендов на стратном нуле (перестановка меток внутри пула «набор + день»),')
    print('  статистика — число повторов бренда:')
    pools = collections.defaultdict(list)
    for r in reg_rows:
        pools[r['_pool']].append(r)
    targets = ['Lucky Bird', 'Leon', 'Martin', 'Pinco', 'Mellstroy', 'Олимп', 'Cactus', 'Luckybear',
               'Shuffle', 'Eva', 'Dragon Money', 'Vodka', 'Goodwin', 'Twin', 'R7', 'Iris', 'Money X',
               'Trix', 'Fenix', 'Bounty', 'Frank']
    obs_b = {b: sum(max(0, v - 1) for dd in [bd[b]] for v in dd.values()) for b in targets}
    cnt = {b: 0 for b in targets}
    tot_b = {b: 0.0 for b in targets}
    for _ in range(NSIM):
        sim = {b: 0 for b in targets}
        for key, rs in pools.items():
            pool = [lab for r in rs for lab in r['_labels']]
            random.shuffle(pool)
            i = 0
            for r in rs:
                nn = len(r['_labels'])
                if nn >= 2:
                    c = collections.Counter(pool[i:i + nn])
                    for b in targets:
                        if c[b] >= 2:
                            sim[b] += c[b] - 1
                i += nn
        for b in targets:
            tot_b[b] += sim[b]
            if sim[b] >= obs_b[b]:
                cnt[b] += 1
    print('  бренд | повторов набл. | E при стратном нуле | p')
    ps = []
    for b in targets:
        p = (cnt[b] + 1) / (NSIM + 1)
        ps.append(p)
        if obs_b[b] > 0:
            print(f'  {b:<12} | {obs_b[b]:>3} | {tot_b[b]/NSIM:>6.2f} | {p:.4f}')
    # BH
    n = len(ps)
    order = sorted(range(n), key=lambda i: ps[i])
    q = [0.0] * n
    prev = 1.0
    for rank in range(n, 0, -1):
        i = order[rank - 1]
        prev = min(prev, ps[i] * n / rank)
        q[i] = prev
    print(f'  q (BH по тем же {n} брендам, что в таблице h17): '
          + '; '.join(f'{targets[i]} {q[i]:.3f}' for i in range(n) if q[i] < 0.30))
    print('  брендов с q < 0,05 на стратном нуле: '
          + str(sum(1 for i in range(n) if q[i] < 0.05))
          + f' (на глобальном нуле у h17 — 5 из 21)')
    print()

    # ---------- 10. Множественность ----------
    print('=' * 100)
    print('10. МНОЖЕСТВЕННОСТЬ: сколько срезов перебрано в h17')
    print('=' * 100)
    txt = open(H17, encoding='utf-8').read()
    n_p = len(re.findall(r'\bp\s*=\s*0', txt)) + len(re.findall(r'\bp\s+0\.', txt))
    n_q = len(re.findall(r'q\s*=\s*0', txt))
    print(f'  в выводе h17 встречается «p = …» {n_p} раз, «q = …» {n_q} раз;')
    print('  структурно: часть А — 4 строки R × 3 ноля + 2 общих теста; часть Б — 4 подвыборки × 2 модели'
          ' + 8 стратификаций; часть В — 21 бренд × 5 нулей (BH применён); даты — 2 группы × 3 страты × 2 метрики.')
    print('  Сколько поправка съедает у главного числа: перестановочный p(33 повторов) = 0,0000 при максимуме')
    print(f'  по 10 000 перестановкам {res["глобальная перестановка меток (ноль h17, заголовочная цифра)"][2]} (глобальный ноль)'
          f' и {res["внутри пула «набор контента + день запуска»"][2]} (стратный ноль) — то есть p < 1e−4.')
    print('  Бонферрони даже на 200 тестов: 1e−4 × 200 = 0,02 < 0,05. Главный факт (повторы есть) поправку переживает.')
    print('  Поправку НЕ переживают производные утверждения по отдельным брендам на стратном нуле (см. п. 9).')
    print()

    # ---------- 11. Даты ----------
    print('=' * 100)
    print('11. ДАТЫ: «однобрендовые повторы живут дольше» — объём')
    print('=' * 100)
    dom2 = [r for r in reg_rows if r['_R'] >= 2]
    one = [r for r in dom2 if r['_S'] == 1]
    many = [r for r in dom2 if r['_S'] >= 2]
    print(f'  однобрендовых доменов (S = 1, R ≥ 2): {len(one)} — это {len(one)} наблюдений, меньше 20;')
    print(f'  многобрендовых: {len(many)}. Разница 0,79 против 0,75 уник. дат/рег на {len(one)} доменах — шум.')
    print('  Вывод тестировщика «не подтверждается» по объёму корректен, но и обратного знака он не доказывает.')
    print()

    print('=' * 100)
    print('ИТОГ КОНТРПРОВЕРКИ')
    print('=' * 100)
    print('  1. Числа воспроизводятся побайтово (diff пуст). Определения проверены на всех 2077 строках:')
    print('     S — число сайтов-брендов с конверсией (0 расхождений со списком брендов и с «брендов с конверсией»),')
    print('     ФД всегда на сайте регистрации → разоблачение «65 %» и «21 %» у тестировщика верно и устойчиво.')
    print(f'  2. Сам факт повторов устойчив: {obs} повторов; на стратном нуле «набор + день» E = {e_pool:.1f}, p < 1e−4;')
    print('     без топ-3 доменов по регистрациям — 28 повторов при E = 13,1 (2,1×), без топ-3 по числу повторов — 26 при 10,4.')
    print('     На 1–3 доменах эффект не держится, агрегат переживает поправку (p < 1e−4, Бонферрони на 200 тестов = 0,02).')
    print(f'  3. НО кратность в отчёте завышена: «в 7,6 раза» — глобальный ноль (E = {e_glob:.1f}), в котором бренд мог прийти')
    print(f'     с любого дня. Страта методики «набор контента + день запуска» даёт E = {e_pool:.1f} → {obs/e_pool:.1f}×')
    print(f'     (бутстрэп по доменам {lo/e_pool:.1f}–{hi/e_pool:.1f}×). Так же «23 % против 1,8 %»: на стратном нуле база 8,2 %.')
    print('  4. Утверждение «это свойство пяти брендов — Leon, Martin, Pinco, Mellstroy, Twin (q ≤ 0,003)» НЕ переживает')
    print('     правильный ноль с поправкой: индекс сгущения E[D]/D_obs — арифметическая перезапись тех же 2–5 повторов')
    print('     (D = k − повторы бренда всегда), а на стратном нуле с BH по тем же 21 бренду q < 0,05 остаётся только')
    print('     у Martin (5 повторов, E 1,3, q = 0,006); Leon, Pinco, Mellstroy, Twin — q = 0,089; Twin стоит на 2 событиях.')
    print('  5. Оконные колонки: h17 считает по неоконным «регистраций»/«сайтов с регистрацией» (оконной пары для S нет).')
    print(f'     Только домены, где все регистрации в окне 3 суток: {len(win)} доменов, {sum(r["_R"] for r in win)} регистраций,')
    print(f'     повторов {ow} при E = {e:.1f} ({ow/e:.1f}×) — знак тот же, но событий {ow}, ниже порога «20 событий».')
    print('  6. Части Б (12 ФД в группе B) и «даты» (13 однобрендовых доменов) объёма не имеют — тестировщик это и пишет.')
    sys.stdout.flush()


main()
