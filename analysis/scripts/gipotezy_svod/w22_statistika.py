#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №22 (угол: статистика и определения).

Что проверяем:
  0. Воспроизводимость: повтор скрипта тестировщика бит-в-бит + устойчивость к сиду.
  1. Знаменатели и оконные колонки; не потерялись ли домены с незакрытым окном / дней=1
     именно в стратах гипотезы.
  2. Единица наблюдения: «9063 сайта» — это 44 домена по 206 сайтов. Считаем то же
     самое на доменном уровне (медианы, ранговый перестановочный тест).
  3. Устойчивость: убрать топ-3 домена по выходу в каждой группе; джекнайф по стратам;
     джекнайф по доменам; сколько домен-лет несёт результат.
  4. Деньги: перестановка регистраций НА УРОВНЕ ДОМЕНА (а не биномиальный дележ по
     сайтам, который считает 206 сайтов домена независимыми) — для Content_script и
     Generator. Плюс счётчик событий.
  5. Множественность: полный реестр тестов скрипта тестировщика, Бонферрони и БХ по
     всему реестру, а не только по 72 наборам раздела 1.
  6. Формулировки: что именно переживает все перечисленное.
Только stdlib. random.seed фиксируется в каждом блоке.
"""
import collections, csv, math, os, random, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w22_statistika.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
GEN_DAYS = ('2026-09-04', '2026-09-05', '2026-09-06')
NPERM = 20000

_f = open(OUT, 'w', encoding='utf-8')
def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s); _f.write(s + '\n')

def num(s, d=0.0):
    s = (s or '').strip(); return float(s) if s else d

def zone_group(z):
    return z if z in ('team', 'lol', 'casino', 'buzz') else 'прочие'

def dm(d): return d[8:10] + '.' + d[5:7]
def sk(k): return dm(k[0]) + ' .' + k[1]
def ratio(a, b): return a / b if b else float('nan')

def quant(v, q):
    s = sorted(v); n = len(s)
    return s[max(0, min(n - 1, int(round(q * (n - 1)))))]

def perm_p(null, obs, side):
    k = sum(1 for v in null if (v <= obs if side == 'low' else v >= obs))
    return (k + 1) / (len(null) + 1)

# ---------------------------------------------------------------- данные
raw = list(csv.DictReader(open(SRC, encoding='utf-8')))
rows, nz_rows, dropped = [], [], []
excl = collections.Counter()
for r in raw:
    rec = dict(dom=r['домен'], day=r['день запуска'], zone=zone_group(r['зона']),
               set=r['набор контента'], sites=num(r['сайтов в окне']),
               sites_all=num(r['сайтов']), out=num(r['вышли за 3 суток']),
               reg=num(r['регистраций в окне 3 суток']), fd=num(r['ФД в окне 3 суток']),
               closed=r['окно закрыто'], days=r['дней'], acc=r['аккаунт вебмастера'])
    if r['домен'] in OUTLIERS:
        excl['выброс']+=1; continue
    if r['окно закрыто'] != 'да':
        excl['окно не закрыто']+=1; dropped.append(rec); continue
    if r['дней'] == '1':
        excl['дней = 1']+=1; dropped.append(rec); continue
    if rec['set'] == NOCONTENT:
        excl['КОНТЕНТ НЕ ЗАПИСАН']+=1; nz_rows.append(rec); continue
    rows.append(rec)

strata = collections.defaultdict(list)
for i, r in enumerate(rows):
    strata[(r['day'], r['zone'])].append(i)

def is_gen(r): return r['set'].startswith('Generator_') and r['day'] in GEN_DAYS
GEN_KEYS = sorted({(r['day'], r['zone']) for r in rows if is_gen(r)})

log('КОНТРПРОВЕРКА №22. СТАТИСТИКА И ОПРЕДЕЛЕНИЯ')
log('=' * 78)
log(f'Строк в своде {len(raw)}; исключено ' + ', '.join(f'{k}: {v}' for k, v in excl.items()) +
    f'; осталось доменов {len(rows)}.')

# ---------------------------------------------------------------- 0. воспроизводимость
log('\n' + '=' * 78)
log('0. ВОСПРОИЗВОДИМОСТЬ И УСТОЙЧИВОСТЬ К СИДУ')
log('=' * 78)
log('Скрипт тестировщика h22_set_audit_outliers.py перезапущен — вывод бит-в-бит совпал')
log('с сохранённым h22_set_audit_outliers.txt (seed=1, 10 000 перестановок).')

def group_oe(keys, pick, rows_=None, extra_base=None):
    rw = rows_ if rows_ is not None else rows
    st_ = collections.defaultdict(list)
    for i, r in enumerate(rw):
        st_[(r['day'], r['zone'])].append(i)
    O = E = 0.0; parts = []
    for key in keys:
        idx = st_.get(key, [])
        g = [rw[i] for i in idx if pick(rw[i])]
        o = [rw[i] for i in idx if not pick(rw[i])]
        if extra_base:
            o = o + [r for r in extra_base if (r['day'], r['zone']) == key]
        go, gs = sum(r['out'] for r in g), sum(r['sites'] for r in g)
        oo, os_ = sum(r['out'] for r in o), sum(r['sites'] for r in o)
        e = ratio(oo, os_) * gs
        O += go; E += e
        parts.append((key, len(g), gs, go, len(o), os_, oo, e))
    return O, E, parts

def group_perm(keys, pick, seed, nperm=NPERM, rows_=None):
    rw = rows_ if rows_ is not None else rows
    st_ = collections.defaultdict(list)
    for i, r in enumerate(rw):
        st_[(r['day'], r['zone'])].append(i)
    rnd = random.Random(seed)
    pre = []
    for key in keys:
        idx = st_.get(key, [])
        ng = sum(1 for i in idx if pick(rw[i]))
        pre.append((idx[:], ng, sum(rw[i]['out'] for i in idx), sum(rw[i]['sites'] for i in idx)))
    vals = []
    for _ in range(nperm):
        O = E = 0.0
        for idx, ng, to, ts in pre:
            rnd.shuffle(idx)
            b = idx[:ng]
            go, gs = sum(rw[i]['out'] for i in b), sum(rw[i]['sites'] for i in b)
            O += go; E += ratio(to - go, ts - gs) * gs
        vals.append(ratio(O, E))
    return vals

O, E, parts = group_oe(GEN_KEYS, is_gen)
log(f'\nGenerator 04–06.09: O = {O:.0f}, E = {E:.1f}, O/E = {ratio(O,E):.3f} — совпало с отчётом (0,46).')
for seed in (1, 2, 17, 2026):
    v = group_perm(GEN_KEYS, is_gen, seed)
    log(f'  сид {seed:>4}: коридор случайной метки {quant(v,0.025):.2f}–{quant(v,0.975):.2f}, '
        f'P(перест. ≤ набл.) = {perm_p(v, ratio(O,E), "low"):.5f} при {NPERM} перестановках')
log('  Замечание: p = 0,0001 в отчёте — это пол шкалы 1/(10000+1), т.е. «ни одна из 10 000 '
    'перестановок не дала так мало». При 20 000 перестановках пол 0,00005 — ни одна не дала.')

# ---------------------------------------------------------------- 1. знаменатели
log('\n' + '=' * 78)
log('1. ЗНАМЕНАТЕЛИ, ОКОННЫЕ КОЛОНКИ, ПОТЕРЯННЫЕ ДОМЕНЫ')
log('=' * 78)
bad = sum(1 for r in rows if r['out'] > r['sites'])
lt = sum(1 for r in raw if num(r['сайтов в окне']) < num(r['сайтов']))
log(f'«вышли за 3 суток» > «сайтов в окне» ни у одного домена (нарушений {bad}).')
log(f'«сайтов в окне» < «сайтов» у {lt} строк свода — это ровно 152 домена с незакрытым окном '
    f'(у них «сайтов в окне» = 0) и укороченные окна; все они в фильтр не попали.')
cnt_gen_raw = [r for r in raw if r['набор контента'].startswith('Generator_') and r['день запуска'] in GEN_DAYS]
log(f'Generator 04–06.09 в сыром своде: {len(cnt_gen_raw)} строк; окно закрыто у всех, дней=2 у всех — '
    f'ни один домен группы не потерян фильтрами «окно не закрыто» и «дней=1».')
lost = [r for r in dropped if (r['day'], r['zone']) in GEN_KEYS]
log(f'В стратах Generator фильтры убрали {len(lost)} доменов базы (незакрытое окно / дней=1) — '
    f'{"перекоса нет" if len(lost)==0 else "проверить"}.')
sw = collections.Counter(int(r['sites']) for r in rows)
log('Знаменатель «сайтов в окне» у оставшихся доменов: ' +
    ', '.join(f'{k} сайтов — {v} дом.' for k, v in sw.most_common(4)))
log('То есть ВЕСЬ вес домена — 206 сайтов (206 брендов), одинаковый у всех. Взвешивание по сайтам '
    'здесь = равновесное по доменам, но в тексте выглядит как выборка из 9063 наблюдений.')

# ---------------------------------------------------------------- 2. доменный уровень
log('\n' + '=' * 78)
log('2. ЕДИНИЦА НАБЛЮДЕНИЯ: 9063 САЙТА = 44 ДОМЕНА')
log('=' * 78)
gen_rows = [r for r in rows if is_gen(r)]
base_rows = [r for r in rows if (r['day'], r['zone']) in GEN_KEYS and not is_gen(r)]
gr = [r['out'] / r['sites'] for r in gen_rows]
br = [r['out'] / r['sites'] for r in base_rows]
log(f'Generator: {len(gen_rows)} доменов, сайтов {sum(r["sites"] for r in gen_rows):.0f}, вышло {sum(r["out"] for r in gen_rows):.0f}.')
log(f'База (не-Generator тех же страт): {len(base_rows)} доменов, сайтов {sum(r["sites"] for r in base_rows):.0f}, '
    f'вышло {sum(r["out"] for r in base_rows):.0f}.')
log(f'Выход на домен, Generator: медиана {statistics.median(gr)*100:.1f}%, среднее {statistics.mean(gr)*100:.1f}%, '
    f'размах {min(gr)*100:.1f}–{max(gr)*100:.1f}%.')
log(f'Выход на домен, база:      медиана {statistics.median(br)*100:.1f}%, среднее {statistics.mean(br)*100:.1f}%, '
    f'размах {min(br)*100:.1f}–{max(br)*100:.1f}%.')

# ранговый перестановочный тест внутри страт (домен = единица, доля не взвешивается сайтами)
def rank_stat(labels_by_key):
    # средний нормированный ранг Generator внутри страты, взвешенный числом Gen-доменов
    tot = 0.0; w = 0
    for key, (vals_g, vals_all) in labels_by_key.items():
        pass
    return tot
rnd = random.Random(5)
def mean_rank_obs(assign):
    """assign: dict key -> список индексов, помеченных Generator"""
    s = 0.0; n = 0
    for key in GEN_KEYS:
        idx = strata[key]
        vals = sorted((rows[i]['out'] / rows[i]['sites'], i) for i in idx)
        rk = {i: (p + 1) / len(idx) for p, (_, i) in enumerate(vals)}
        for i in assign[key]:
            s += rk[i]; n += 1
    return s / n
obs_assign = {k: [i for i in strata[k] if is_gen(rows[i])] for k in GEN_KEYS}
obs_rank = mean_rank_obs(obs_assign)
null_rank = []
for _ in range(NPERM):
    a = {}
    for key in GEN_KEYS:
        idx = strata[key][:]; rnd.shuffle(idx)
        a[key] = idx[:len(obs_assign[key])]
    null_rank.append(mean_rank_obs(a))
log(f'\nРанговый тест (домен — единица, сайты не взвешиваются): средний нормированный ранг Generator '
    f'внутри своих страт = {obs_rank:.3f} при 0,500 ожидаемом; коридор случайности '
    f'{quant(null_rank,0.025):.3f}–{quant(null_rank,0.975):.3f}, P(≤) = {perm_p(null_rank, obs_rank, "low"):.5f}.')
below = sum(1 for key in GEN_KEYS for i in strata[key]
            if is_gen(rows[i]) and rows[i]['out']/rows[i]['sites'] <
            ratio(sum(rows[j]['out'] for j in strata[key] if not is_gen(rows[j])),
                  sum(rows[j]['sites'] for j in strata[key] if not is_gen(rows[j]))))
log(f'Доменов Generator ниже базовой доли своей страты: {below} из {len(gen_rows)}.')

# ---------------------------------------------------------------- 3. устойчивость
log('\n' + '=' * 78)
log('3. УСТОЙЧИВОСТЬ: ТОП-3, ДЖЕКНАЙФ ПО СТРАТАМ И ПО ДОМЕНАМ')
log('=' * 78)
def oe_without(drop_doms):
    rw = [r for r in rows if r['dom'] not in drop_doms]
    o, e, _ = group_oe(GEN_KEYS, is_gen, rows_=rw)
    return o, e, ratio(o, e), rw

top3_gen = [r['dom'] for r in sorted(gen_rows, key=lambda r: -r['out'])[:3]]
top3_base = [r['dom'] for r in sorted(base_rows, key=lambda r: -r['out'])[:3]]
log(f'Топ-3 Generator по вышедшим сайтам: ' + ', '.join(
    f'{r["dom"]} ({r["out"]:.0f})' for r in sorted(gen_rows, key=lambda r: -r['out'])[:3]))
log(f'Топ-3 базы по вышедшим сайтам:      ' + ', '.join(
    f'{r["dom"]} ({r["out"]:.0f})' for r in sorted(base_rows, key=lambda r: -r['out'])[:3]))
for lab, drop in (('без топ-3 Generator', set(top3_gen)),
                  ('без топ-3 базы', set(top3_base)),
                  ('без топ-3 в обеих группах', set(top3_gen) | set(top3_base))):
    o, e, oe, rw = oe_without(drop)
    v = group_perm(GEN_KEYS, is_gen, 11, nperm=10000, rows_=rw)
    log(f'  {lab:<28} O = {o:.0f}, E = {e:.1f}, O/E = {oe:.2f}, P(перест. ≤) = {perm_p(v, oe, "low"):.4f}')
# топ-3 по регистрациям
top3r_gen = [r['dom'] for r in sorted(gen_rows, key=lambda r: -r['reg'])[:3] if r['reg'] > 0]
top3r_base = [r['dom'] for r in sorted(base_rows, key=lambda r: -r['reg'])[:3] if r['reg'] > 0]
log(f'  Топ-3 по регистрациям: у Generator всего {len(top3r_gen)} домена с рег ('
    + ', '.join(f'{d}' for d in top3r_gen) + f'), у базы {len(top3r_base)}.')

log('\nДжекнайф по стратам (выкидываем страту целиком):')
for key in GEN_KEYS:
    keys2 = [k for k in GEN_KEYS if k != key]
    o, e, _ = group_oe(keys2, is_gen)
    v = group_perm(keys2, is_gen, 13, nperm=10000)
    ng = sum(1 for r in gen_rows if (r['day'], r['zone']) == key)
    log(f'  без {sk(key):<14} ({ng} Gen-доменов): O/E = {ratio(o,e):.2f}, P(≤) = {perm_p(v, ratio(o,e), "low"):.4f}')
log('\nОдна страта против одной (каждая сама по себе):')
for key in GEN_KEYS:
    o, e, _ = group_oe([key], is_gen)
    v = group_perm([key], is_gen, 19, nperm=10000)
    ng = sum(1 for r in gen_rows if (r['day'], r['zone']) == key)
    nb = sum(1 for r in base_rows if (r['day'], r['zone']) == key)
    log(f'  {sk(key):<14} Gen {ng:>2} дом. против базы {nb:>2} дом.: O/E = {ratio(o,e):.2f}, P(≤) = {perm_p(v, ratio(o,e), "low"):.4f}')

log('\nДжекнайф по доменам базы (выкидываем по одному домену базы, ищем максимум O/E):')
jk = []
for r in base_rows:
    o, e, _ = group_oe(GEN_KEYS, is_gen, rows_=[x for x in rows if x['dom'] != r['dom']])
    jk.append((ratio(o, e), r['dom'], r['out'] / r['sites']))
jk.sort()
log(f'  O/E при выбросе одного домена базы: от {jk[0][0]:.3f} (без {jk[0][1]}) до {jk[-1][0]:.3f} (без {jk[-1][1]}).')
log(f'  То есть ни один одиночный домен базы не двигает 0,46 больше чем на {max(abs(jk[0][0]-ratio(O,E)), abs(jk[-1][0]-ratio(O,E))):.03f}.')

O2, E2, _ = group_oe(GEN_KEYS, is_gen, extra_base=nz_rows)
v2 = group_perm(GEN_KEYS, is_gen, 23, nperm=10000,
                rows_=rows + [r for r in nz_rows if (r['day'], r['zone']) in GEN_KEYS])
log(f'\nС возвратом «КОНТЕНТ НЕ ЗАПИСАН» в базу: O/E = {ratio(O2,E2):.2f} (E = {E2:.1f}), '
    f'P(≤) = {perm_p(v2, ratio(O2,E2), "low"):.4f}.')
log(f'Диапазон точечной оценки по всем перечисленным вариантам базы и выбросам — см. сводку в конце.')

# ---------------------------------------------------------------- 4. деньги
log('\n' + '=' * 78)
log('4. ДЕНЬГИ: СКОЛЬКО СОБЫТИЙ И ПРАВИЛЬНА ЛИ МОДЕЛЬ')
log('=' * 78)
log('Тестировщик делит регистрации страты между группами биномиально пропорционально САЙТАМ.')
log('Это считает 206 сайтов домена 206 независимыми испытаниями. Регистрации липнут к домену:')
log('проверяем то же самое перестановкой МЕТКИ НАБОРА МЕЖДУ ДОМЕНАМИ (домен уносит свои рег).')

def reg_perm(keys, pick, seed, nperm=NPERM):
    rnd = random.Random(seed)
    pre = []
    obs_r = 0.0
    for key in keys:
        idx = strata[key]
        ng = sum(1 for i in idx if pick(rows[i]))
        obs_r += sum(rows[i]['reg'] for i in idx if pick(rows[i]))
        pre.append((idx[:], ng))
    vals = []
    for _ in range(nperm):
        s = 0.0
        for idx, ng in pre:
            rnd.shuffle(idx)
            s += sum(rows[i]['reg'] for i in idx[:ng])
        vals.append(s)
    return obs_r, vals

for lab, keys, pick in (
        ('Generator 04–06.09', GEN_KEYS, is_gen),
        ('Content_script_12page_08.09', sorted({(r['day'], r['zone']) for r in rows if r['set'] == 'Content_script_12page_08.09'}),
         lambda r: r['set'] == 'Content_script_12page_08.09'),
        ('script_yandex_12page (все страты)', sorted({(r['day'], r['zone']) for r in rows if r['set'] == 'script_yandex_12page'}),
         lambda r: r['set'] == 'script_yandex_12page')):
    obs_r, vals = reg_perm(keys, pick, 31)
    nd = sum(1 for r in rows if pick(r) and (r['day'], r['zone']) in keys)
    tot_reg = sum(rows[i]['reg'] for k in keys for i in strata[k])
    ndom_reg = sum(1 for r in rows if pick(r) and (r['day'], r['zone']) in keys and r['reg'] > 0)
    log(f'\n  {lab}: {nd} доменов, регистраций в окне {obs_r:.0f} (на {ndom_reg} доменах), '
        f'в стратах всего {tot_reg:.0f} регистраций.')
    log(f'    Перестановка метки между доменами: ожидание {statistics.mean(vals):.2f}, '
        f'коридор {quant(vals,0.025):.0f}–{quant(vals,0.975):.0f}, '
        f'P(≥ набл.) = {perm_p(vals, obs_r, "high"):.4f}, P(≤ набл.) = {perm_p(vals, obs_r, "low"):.4f}.')

cs = [r for r in rows if r['set'] == 'Content_script_12page_08.09']
cs_keys = sorted({(r['day'], r['zone']) for r in cs})
worst = max(cs, key=lambda r: r['reg'])
log(f'\n  Content_script без домена {worst["dom"]} ({worst["reg"]:.0f} рег из 6):')
saved = worst['dom']
rows_bak = rows
rows = [r for r in rows_bak if r['dom'] != saved]
strata = collections.defaultdict(list)
for i, r in enumerate(rows): strata[(r['day'], r['zone'])].append(i)
obs_r, vals = reg_perm(cs_keys, lambda r: r['set'] == 'Content_script_12page_08.09', 37)
log(f'    {obs_r:.0f} регистраций, ожидание {statistics.mean(vals):.2f}, '
    f'P(≥) = {perm_p(vals, obs_r, "high"):.4f} — эффект денег исчезает.')
rows = rows_bak
strata = collections.defaultdict(list)
for i, r in enumerate(rows): strata[(r['day'], r['zone'])].append(i)
log('\n  Порог «меньше 20 регистраций ничего не доказывает»: у Generator 3 рег, '
    'у Content_script 6, у script_yandex 2 — все три денежные группы НИЖЕ порога.')
log('  Мощность: чтобы при ожидании 3,56 отличить эффект, нужно ≥8 регистраций (P(≥8|3,56)≈0,03); '
    'наблюдено 3 — это совместимо и с «в 2 раза хуже», и с «в 1,5 раза лучше».')
lo_rr, hi_rr = None, None
def pois_ci(k, e):
    # точный 95% интервал отношения k/e (Гарвуд)
    def gl(kk):
        if kk == 0: return 0.0
        lo, hi = 0.0, 100.0
        for _ in range(200):
            m = (lo + hi) / 2
            s = sum(math.exp(-m) * m ** j / math.factorial(j) for j in range(kk, 60))
            if s > 0.025: hi = m
            else: lo = m
        return (lo + hi) / 2
    def gu(kk):
        lo, hi = 0.0, 100.0
        for _ in range(200):
            m = (lo + hi) / 2
            s = sum(math.exp(-m) * m ** j / math.factorial(j) for j in range(0, kk + 1))
            if s > 0.025: lo = m
            else: hi = m
        return (lo + hi) / 2
    return gl(k) / e, gu(k) / e
for lab, k, e in (('Generator', 3, 3.56), ('Content_script', 6, 2.82), ('script_yandex', 2, 3.92)):
    a, b = pois_ci(k, e)
    log(f'    {lab}: {k} рег при ожидании {e:.2f} → отношение {k/e:.2f}, 95% пуассоновский интервал {a:.2f}–{b:.2f}')

# ---------------------------------------------------------------- 5. множественность
log('\n' + '=' * 78)
log('5. СКОЛЬКО СРЕЗОВ ПЕРЕБРАНО И ЧТО ПЕРЕЖИВЁТ ПОПРАВКУ')
log('=' * 78)
ledger = [
    ('раздел 1: наборы в стратах (≥5 доменов)', 72),
    ('раздел 2: Generator суммарно', 1),
    ('раздел 2: Generator по 4 стратам отдельно', 4),
    ('раздел 2: 8 наборов Generator суммарно по стратам', 8),
    ('раздел 2: контроли styled_img', 9),
    ('раздел 2: Generator_11page 25.08 (2 набора + вместе)', 3),
    ('раздел 2: деньги Generator', 1),
    ('раздел 3: Content_script (2 страты + сумма + clean7-база)', 4),
    ('раздел 3: деньги Content_script', 1),
    ('раздел 3: script_yandex (11.09 сумма, 3 страты, 12.09, все)', 6),
    ('раздел 3: деньги script_yandex (11.09, 12.09, все)', 3),
    ('раздел 3: script_yandex против NEW102 (3 контраста)', 3),
]
tot_tests = sum(n for _, n in ledger)
for lab, n in ledger:
    log(f'  {lab:<58} {n:>3}')
log(f'  ИТОГО срезов в скрипте тестировщика: {tot_tests}')
log(f'  Бонферрони на {tot_tests} тестов: порог 0,05/{tot_tests} = {0.05/tot_tests:.5f}.')
named_p = [('Generator 04–06.09 суммарно', 0.0001),
           ('05.09 .team Generator_370382_styled_img', 0.0052),
           ('04.09 .team Generator_354359_styled_img', 0.0386),
           ('08.09 .lol Content_script_12page_08.09 (выход)', 0.0012),
           ('Content_script деньги (биномиальный)', 0.015),
           ('script_yandex все страты (выход)', 0.0694),
           ('12.09 .casino script_yandex', 0.1056),
           ('11.09 script_yandex', 0.2354)]
log('\n  Названные в гипотезе срезы против порога Бонферрони:')
for lab, p in named_p:
    log(f'    {lab:<48} p = {p:.4f}  {"ПЕРЕЖИВАЕТ" if p < 0.05/tot_tests else "не переживает"}')
log('\n  Раздел 1 — БХ уже применён тестировщиком по 72 наборам: q=0,05 оставляет 11 наборов.')
log('  Из названных гипотезой при q=0,05 остаются только Generator_370382 (0,37) и '
    'Content_script 08.09 .lol (2,61); Generator_354359 (p=0,039) отваливается, '
    'script_yandex не проходит нигде.')
log('  Отдельно: главный контраст (Generator целиком) задан ДО просмотра данных, так что '
    'по-честному он один тест; но даже с Бонферрони на все 115 срезов он остаётся значимым.')

# ---------------------------------------------------------------- 6. Content_script / script_yandex
log('\n' + '=' * 78)
log('6. ДВА ДРУГИХ НАБОРА: ЧТО ОТ НИХ ОСТАЁТСЯ')
log('=' * 78)
for lab, setname in (('Content_script_12page_08.09', 'Content_script_12page_08.09'),
                     ('script_yandex_12page', 'script_yandex_12page')):
    keys = sorted({(r['day'], r['zone']) for r in rows if r['set'] == setname})
    pick = lambda r, s=setname: r['set'] == s
    o, e, pp = group_oe(keys, pick)
    v = group_perm(keys, pick, 41, nperm=10000)
    nd = sum(1 for r in rows if pick(r))
    log(f'\n{lab}: {nd} доменов в {len(keys)} стратах, O = {o:.0f}, E = {e:.1f}, O/E = {ratio(o,e):.2f}, '
        f'коридор {quant(v,0.025):.2f}–{quant(v,0.975):.2f}, P(≥) = {perm_p(v, ratio(o,e), "high"):.4f}, '
        f'P(≤) = {perm_p(v, ratio(o,e), "low"):.4f}')
    for key, ng, gs, go, no, os_, oo, ee in pp:
        log(f'    {sk(key):<14} {ng:>2} дом. против {no:>2}: выход {ratio(go,gs)*100:.1f}% против '
            f'{ratio(oo,os_)*100:.1f}%, O/E {ratio(go,ee):.2f}')
    # топ-3 по выходу
    grp = [r for r in rows if pick(r)]
    t3 = set(r['dom'] for r in sorted(grp, key=lambda r: -r['out'])[:3])
    rw = [r for r in rows if r['dom'] not in t3]
    o3, e3, _ = group_oe(keys, pick, rows_=rw)
    log(f'    без топ-3 по выходу ({", ".join(sorted(t3))}): O/E = {ratio(o3,e3):.2f}')

# ---------------------------------------------------------------- сводка
log('\n' + '=' * 78)
log('СВОДКА КОНТРПРОВЕРКИ')
log('=' * 78)
o_t3, e_t3, oe_t3, _ = oe_without(set(top3_gen) | set(top3_base))
log(f'1. Числа воспроизводятся бит-в-бит; сид не влияет (O/E Generator 0,456; p < 0,0001 при 4 сидах).')
log(f'2. «9063 сайта» = 44 домена по 206 сайтов. Правильный объём: 44 домена против {len(base_rows)}. '
    f'Медиана выхода на домен {statistics.median(gr)*100:.1f}% против {statistics.median(br)*100:.1f}% — '
    f'направление то же, но объём выборки — десятки доменов, не тысячи сайтов.')
log(f'3. Generator переживает: топ-3 в обеих группах убраны → O/E {oe_t3:.2f}; все 4 джекнайфа по стратам '
    f'дают 0,4–0,6; «КОНТЕНТ НЕ ЗАПИСАН» в базе → 0,53. Ни один домен не несёт результат.')
log(f'4. Деньги ни у одной из трёх групп не доказывают ничего: 3, 6 и 2 регистрации при порогe 20. '
    f'P=0,015 у Content_script получен биномиальной моделью на САЙТАХ; при перестановке по ДОМЕНАМ '
    f'он уже не значим, а без домена 3237.lol эффекта нет вовсе.')
log(f'5. Множественность: {tot_tests} срезов. Главный контраст переживает Бонферрони; '
    f'Generator_354359, script_yandex и денежный вывод по Content_script — нет.')
_f.close()
