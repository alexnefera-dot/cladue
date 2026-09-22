#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ТЕНИ к гипотезе №22 (наборы-выбросы: Generator_* 04-06.09, script_yandex_12page,
Content_script_12page_08.09).

Что проверяем. Тестировщик считал O/E набора против соседей по страте
«день запуска x зона» и получил для Generator_* 04-06.09 O/E 0.46 при
перестановочном p = 0.0001 (44 домена, 577 выходов при ожидании 1265).
Здесь проверяется, не является ли это тенью:
  (1) часа/партии постановки — наборы ставятся сплошными партиями по часам,
      номер аккаунта вебмастера идёт подряд с порядком постановки;
  (2) состава базы — кого именно выкинули из базы («КОНТЕНТ НЕ ЗАПИСАН»
      на 04.09 .team это 13 доменов, поставленных за 1-3 часа ДО Generator)
      и кто остался (наборы по 1-3 домена);
  (3) единицы наблюдения — перестановка метки по доменам считает 44 домена
      независимыми, хотя известно, что выходом управляет набор; настоящая
      репликация — 3 дня/4 блока «день x зона» и 8 наборов;
  (4) семейства — «нумерованные генерированные наборы» вообще (Generator_NNNNNN
      и nabory-NNN), а не ветка генератора как таковая.

Только stdlib. random.seed(22).
"""
import collections
import csv
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w22_teni.txt')

OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
NPERM = 10000
GEN_DAYS = ('2026-09-04', '2026-09-05', '2026-09-06')
random.seed(22)


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


say = Tee(OUT)


def num(s, d=0.0):
    s = (s or '').strip()
    try:
        return float(s)
    except ValueError:
        return d


def zone_group(z):
    return z if z in ('team', 'lol', 'casino', 'buzz') else 'прочие'


def dm(day):
    return day[8:10] + '.' + day[5:7]


def blk(h):
    h = int(h)
    return '00-05' if h < 6 else '06-11' if h < 12 else '12-17' if h < 18 else '18-23'


def is_gen4_6(r):
    """Набор ветки генератора 04-06.09, как её назвала гипотеза."""
    s = r['набор контента']
    return r['день запуска'] in GEN_DAYS and s.startswith('Generator')


def quant(vals, p):
    s = sorted(vals)
    if not s:
        return float('nan')
    i = int(round(p * (len(s) - 1)))
    return s[max(0, min(len(s) - 1, i))]


def perm_p(null, obs, side):
    if side == 'low':
        k = sum(1 for v in null if v <= obs + 1e-12)
    else:
        k = sum(1 for v in null if v >= obs - 1e-12)
    return (k + 1) / (len(null) + 1)


def f2(x, nd=2):
    return 'н/д' if x != x else f'{x:.{nd}f}'


# ----------------------------------------------------------------- данные
rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
base_all = [r for r in rows
            if r['окно закрыто'] == 'да'
            and r['дней'].strip() != '1'
            and r['домен'] not in OUTLIERS]
for r in base_all:
    r['_z'] = zone_group(r['зона'])
    r['_s'] = num(r['сайтов в окне'])
    r['_o'] = num(r['вышли за 3 суток'])
    r['_reg'] = num(r['регистраций в окне 3 суток'])
    r['_blk'] = blk(r['час запуска']) if r['час запуска'].strip() else '?'
    r['_h'] = int(num(r['час запуска'], -1))
    r['_nc'] = (r['набор контента'] == NOCONTENT)
    r['_acc'] = num(r['аккаунт вебмастера'], -1)

named = [r for r in base_all if not r['_nc']]

say('ТЕНИ №22. Конфаундинг: час/партия постановки, состав базы, единица наблюдения, семейство набора')
say('=' * 126)
say(f'Строк в своде: {len(rows)}. После фильтров тестировщика (окно закрыто, дней != 1, без 3615/3286): {len(base_all)}.')
say(f'Из них с именем набора: {len(named)}; «{NOCONTENT}»: {len(base_all) - len(named)}.')
say('Выход = «вышли за 3 суток» / «сайтов в окне». Деньги = «регистраций в окне 3 суток».')
say('')

# ------------------------------------------------- 0. «КОНТЕНТ НЕ ЗАПИСАН» не сцеплен с датой
say('=' * 126)
say('0. ПЕРВАЯ ТЕНЬ: «КОНТЕНТ НЕ ЗАПИСАН» — НЕ ТОЛЬКО ДО 24.08, И ЭТО БЛИЖАЙШИЕ СОСЕДИ Generator')
say('=' * 126)
nc_by_day = collections.Counter((r['день запуска'], r['_z']) for r in base_all if r['_nc'])
late_nc = {k: v for k, v in nc_by_day.items() if k[0] >= '2026-08-24'}
say(f'Доменов «{NOCONTENT}» после 24.08 включительно: {sum(late_nc.values())} в {len(late_nc)} стратах:')
for k in sorted(late_nc):
    sub = [r for r in base_all if r['_nc'] and r['день запуска'] == k[0] and r['_z'] == k[1]]
    s = sum(r['_s'] for r in sub); o = sum(r['_o'] for r in sub)
    hrs = sorted(set(r['_h'] for r in sub))
    say(f'  {dm(k[0])} .{k[1]}: {len(sub):3d} дом, {s:6.0f} сайтов, выход {100*o/s:5.1f}%, часы {hrs}')
say('Тестировщик выкинул их и из наборов, и ИЗ БАЗЫ страт. Ниже видно, чем это оборачивается.')
say('')

# ------------------------------------------------- 1. структура пула по часам
say('=' * 126)
say('1. СТРУКТУРА ПУЛА: Generator СТАВИЛСЯ СПЛОШНЫМИ ПАРТИЯМИ ПО ЧАСАМ')
say('=' * 126)
gen_strata = sorted({(r['день запуска'], r['_z']) for r in base_all if is_gen4_6(r)})
say('Страта, блок часа: сколько доменов Generator и сколько НЕ-Generator рядом (в скобках — без «НЕ ЗАПИСАН»).')
say(f"{'страта':14s} {'блок':6s} {'Gen дом':>7s} {'Gen сайт':>8s} {'Gen вых':>7s} {'Gen вых%':>8s} "
    f"{'чуж дом':>7s} {'чуж вых%':>8s} {'из них им.дом':>13s} {'им.вых%':>8s}  часы Gen / часы чужих")
say('-' * 126)
cells = []
for key in gen_strata:
    sub = [r for r in base_all if r['день запуска'] == key[0] and r['_z'] == key[1]]
    for b in sorted({r['_blk'] for r in sub}):
        g = [r for r in sub if r['_blk'] == b and is_gen4_6(r)]
        o_all = [r for r in sub if r['_blk'] == b and not is_gen4_6(r)]
        o_nm = [r for r in o_all if not r['_nc']]
        if not g and not o_all:
            continue
        gs = sum(r['_s'] for r in g); go = sum(r['_o'] for r in g)
        os_ = sum(r['_s'] for r in o_all); oo = sum(r['_o'] for r in o_all)
        ns = sum(r['_s'] for r in o_nm); no_ = sum(r['_o'] for r in o_nm)
        say(f'{dm(key[0])+" ."+key[1]:14s} {b:6s} {len(g):7d} {gs:8.0f} {go:7.0f} '
            f'{(100*go/gs if gs else float("nan")):8.1f} {len(o_all):7d} '
            f'{(100*oo/os_ if os_ else float("nan")):8.1f} {len(o_nm):13d} '
            f'{(100*no_/ns if ns else float("nan")):8.1f}  '
            f'{sorted(set(r["_h"] for r in g))} / {sorted(set(r["_h"] for r in o_all))}')
        if g:
            cells.append((key, b, g, o_all, o_nm))
say('')
gen_all = [r for r in base_all if is_gen4_6(r)]
no_neigh_named = sum(len(g) for k, b, g, oa, on in cells if not on)
no_neigh_any = sum(len(g) for k, b, g, oa, on in cells if not oa)
say(f'Всего доменов Generator 04-06.09: {len(gen_all)}.')
say(f'  Из них БЕЗ единого не-Generator соседа с именем набора в том же дне+зоне+блоке часа: {no_neigh_named} '
    f'({100*no_neigh_named/len(gen_all):.0f}%).')
say(f'  Из них без единого не-Generator соседа вообще (даже «НЕ ЗАПИСАН»): {no_neigh_any} '
    f'({100*no_neigh_any/len(gen_all):.0f}%).')
say('Номер аккаунта вебмастера идёт подряд с порядком постановки — метка набора и партия постановки')
say('различаются только по названию. Диапазоны аккаунтов по наборам в стратах Generator:')
for key in gen_strata:
    sub = [r for r in base_all if r['день запуска'] == key[0] and r['_z'] == key[1]]
    byset = collections.defaultdict(list)
    for r in sub:
        byset[r['набор контента']].append(r)
    parts = []
    for s, v in sorted(byset.items(), key=lambda x: min(r['_acc'] for r in x[1])):
        parts.append(f'{s[:26]}[{min(r["_acc"] for r in v):.0f}-{max(r["_acc"] for r in v):.0f}]')
    say(f'  {dm(key[0])} .{key[1]}: ' + ' → '.join(parts))
say('')

# ------------------------------------------------- 2. час как фактор
say('=' * 126)
say('2. БЛОК ЧАСА САМ ПО СЕБЕ — ФАКТОР (Generator из расчёта исключён)')
say('=' * 126)


def block_oe(pool, exclude_gen=True):
    agg = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0])
    strat = collections.defaultdict(list)
    for r in pool:
        if exclude_gen and is_gen4_6(r):
            continue
        strat[(r['день запуска'], r['_z'])].append(r)
    for k, v in strat.items():
        tot_s = sum(r['_s'] for r in v); tot_o = sum(r['_o'] for r in v)
        byb = collections.defaultdict(list)
        for r in v:
            byb[r['_blk']].append(r)
        if len(byb) < 2:
            continue
        for b, vv in byb.items():
            s = sum(r['_s'] for r in vv); o = sum(r['_o'] for r in vv)
            ss = tot_s - s; oo = tot_o - o
            if ss <= 0:
                continue
            agg[b][0] += o; agg[b][1] += (oo / ss) * s; agg[b][2] += s; agg[b][3] += len(vv)
    return agg


for title, pool in (('все домены с именем набора + «НЕ ЗАПИСАН»', base_all), ('только с именем набора', named)):
    agg = block_oe(pool)
    say(f'  [{title}]  O/E блока против других блоков того же дня и зоны:')
    for b in sorted(agg):
        o, e, s, n = agg[b]
        say(f'    {b}: {n:4d} дом, {s:7.0f} сайтов, O {o:6.0f}, E {e:7.1f}, O/E {o/e:5.3f}')
say('Вывод: ночь и утро (00-05, 06-11) сами по себе дают ~0.88-0.90, день (12-17) ~1.18 —')
say('то есть часть провала Generator покупается просто тем, в какой блок часа он попал.')
say('')

# ------------------------------------------------- 3. жёсткая страта
say('=' * 126)
say('3. ЖЁСТКАЯ СТРАТА: ДЕНЬ + ЗОНА + БЛОК ЧАСА (и отдельно + ТОЧНЫЙ ЧАС)')
say('=' * 126)


def hard_oe(level, base_mode):
    """level: 'blk' или 'hour'; base_mode: 'named' (без НЕ ЗАПИСАН) или 'all'."""
    rowsout = []
    O = E = S = 0.0
    ndom = 0
    strat = collections.defaultdict(list)
    for r in base_all:
        k = (r['день запуска'], r['_z'], r['_blk'] if level == 'blk' else r['_h'])
        strat[k].append(r)
    for k in sorted(strat):
        v = strat[k]
        g = [r for r in v if is_gen4_6(r)]
        if not g:
            continue
        ob = [r for r in v if not is_gen4_6(r)]
        if base_mode == 'named':
            ob = [r for r in ob if not r['_nc']]
        bs = sum(r['_s'] for r in ob); bo = sum(r['_o'] for r in ob)
        gs = sum(r['_s'] for r in g); go = sum(r['_o'] for r in g)
        if bs <= 0:
            rowsout.append((k, len(g), gs, go, 0, 0.0, float('nan'), float('nan')))
            continue
        e = (bo / bs) * gs
        O += go; E += e; S += gs; ndom += len(g)
        rowsout.append((k, len(g), gs, go, len(ob), 100 * bo / bs, e, go / e if e else float('nan')))
    return rowsout, O, E, S, ndom


for level, lname in (('blk', 'блок часа'), ('hour', 'точный час')):
    for base_mode, bname in (('named', 'база без «НЕ ЗАПИСАН» (как у тестировщика)'),
                             ('all', 'база включая «НЕ ЗАПИСАН» (ближайшие соседи)')):
        rowsout, O, E, S, ndom = hard_oe(level, base_mode)
        say(f'--- страта день+зона+{lname}; {bname}')
        say(f"  {'ячейка':26s} {'Gen дом':>7s} {'сайт':>6s} {'вых':>5s} {'чуж дом':>7s} {'чуж вых%':>8s} {'E':>8s} {'O/E':>6s}")
        for k, gd, gs, go, bd, bp, e, oe in rowsout:
            lab = f'{dm(k[0])} .{k[1]} {k[2]}'
            if bd == 0:
                say(f'  {lab:26s} {gd:7d} {gs:6.0f} {go:5.0f} {0:7d} {"—":>8s} {"—":>8s} {"НЕ ОЦЕНИВАЕТСЯ":>6s}')
            else:
                say(f'  {lab:26s} {gd:7d} {gs:6.0f} {go:5.0f} {bd:7d} {bp:8.1f} {e:8.1f} {oe:6.2f}')
        say(f'  ИТОГО оцениваемых доменов Generator: {ndom} из {len(gen_all)}; '
            f'O = {O:.0f}, E = {E:.1f}, O/E = {f2(O/E if E else float("nan"))}')
        say('')

# --- перестановка внутри жёсткой страты (домены)
def perm_hard(level, base_mode, nperm=NPERM):
    strat = collections.defaultdict(list)
    for r in base_all:
        k = (r['день запуска'], r['_z'], r['_blk'] if level == 'blk' else r['_h'])
        strat[k].append(r)
    cells_ = []
    for k, v in strat.items():
        g = [r for r in v if is_gen4_6(r)]
        if not g:
            continue
        ob = [r for r in v if not is_gen4_6(r)]
        if base_mode == 'named':
            ob = [r for r in ob if not r['_nc']]
        if not ob:
            continue
        cells_.append((g, ob, len(g)))
    obs_O = obs_E = 0.0
    for g, ob, ng in cells_:
        gs = sum(r['_s'] for r in g); go = sum(r['_o'] for r in g)
        bs = sum(r['_s'] for r in ob); bo = sum(r['_o'] for r in ob)
        obs_O += go; obs_E += (bo / bs) * gs
    obs = obs_O / obs_E if obs_E else float('nan')
    null = []
    for _ in range(nperm):
        tO = tE = 0.0
        for g, ob, ng in cells_:
            pool = g + ob
            pick = random.sample(pool, ng)
            ps = set(id(x) for x in pick)
            rest = [x for x in pool if id(x) not in ps]
            gs = sum(r['_s'] for r in pick); go = sum(r['_o'] for r in pick)
            bs = sum(r['_s'] for r in rest); bo = sum(r['_o'] for r in rest)
            if bs <= 0:
                continue
            tO += go; tE += (bo / bs) * gs
        if tE:
            null.append(tO / tE)
    return obs, null, sum(ng for _, _, ng in cells_)


say('--- перестановочный тест ВНУТРИ жёсткой страты (метка Generator мешается между доменами ячейки)')
for level, lname in (('blk', 'день+зона+блок часа'), ('hour', 'день+зона+точный час')):
    for base_mode, bname in (('named', 'без «НЕ ЗАПИСАН»'), ('all', 'с «НЕ ЗАПИСАН»')):
        obs, null, nd = perm_hard(level, base_mode)
        say(f'  {lname}, {bname}: доменов {nd}, O/E = {f2(obs)}, '
            f'коридор {f2(quant(null,0.025))}–{f2(quant(null,0.975))}, p(<=) = {perm_p(null, obs, "low"):.4f}')
say('')

# ------------------------------------------------- 4. единица наблюдения
say('=' * 126)
say('4. ЕДИНИЦА НАБЛЮДЕНИЯ: 44 ДОМЕНА — ЭТО НЕ 44 НЕЗАВИСИМЫХ НАБЛЮДЕНИЯ')
say('=' * 126)
say('Известно: выходом управляет набор (хи-кв 4447 против 113 на перестановках), а наборы ставятся')
say('партиями. Перестановка метки по доменам внутри страты считает домены обменимыми и поэтому')
say('занижает разброс. Ниже — те же данные при перестановке НАБОРАМИ и при взгляде на дни.')
say('')

# 4a. блоки день x зона
say('4а. Уровень «день x зона» (мягкая страта тестировщика), Generator против не-Generator с именем набора:')
blocks = []
for key in gen_strata:
    sub = [r for r in named if r['день запуска'] == key[0] and r['_z'] == key[1]]
    g = [r for r in sub if is_gen4_6(r)]
    ob = [r for r in sub if not is_gen4_6(r)]
    if not g or not ob:
        continue
    gs = sum(r['_s'] for r in g); go = sum(r['_o'] for r in g)
    bs = sum(r['_s'] for r in ob); bo = sum(r['_o'] for r in ob)
    e = (bo / bs) * gs
    blocks.append((key, len(g), gs, go, e, go / e))
    say(f'  {dm(key[0])} .{key[1]:6s}: Gen {len(g):2d} дом, O {go:4.0f}, E {e:7.1f}, O/E {go/e:.2f}')
tO = sum(b[3] for b in blocks); tE = sum(b[4] for b in blocks)
say(f'  суммарно: O {tO:.0f}, E {tE:.1f}, O/E {tO/tE:.2f} (у тестировщика 0.46)')
nb = len(blocks); nlow = sum(1 for b in blocks if b[5] < 1)
say(f'  Блоков всего {nb}, ниже 1 — {nlow}. Знаковый тест по блокам: p(одност.) = {0.5**nb:.4f}, '
    f'p(двуст.) = {min(1.0, 2*0.5**nb):.4f}.')
say(f'  Независимых дней постановки — 3 (04.09, 05.09, 06.09). Знаковый тест по дням: '
    f'p(одност.) = {0.5**3:.3f}.')
say('')

# 4b. джекнайф по блокам и наборам
say('4б. Джекнайф: сколько держится на одной партии.')
for i, b in enumerate(blocks):
    O2 = tO - b[3]; E2 = tE - b[4]
    say(f'  без {dm(b[0][0])} .{b[0][1]}: O/E = {O2/E2:.2f} (убрано {b[1]} доменов)')
gsets = collections.defaultdict(list)
for r in gen_all:
    gsets[(r['день запуска'], r['_z'], r['набор контента'])].append(r)
say('  по наборам (внутри страты), O/E против не-Generator соседей с именем набора:')
setrows = []
for k, v in sorted(gsets.items()):
    sub = [r for r in named if r['день запуска'] == k[0] and r['_z'] == k[1] and not is_gen4_6(r)]
    if not sub:
        continue
    bs = sum(r['_s'] for r in sub); bo = sum(r['_o'] for r in sub)
    gs = sum(r['_s'] for r in v); go = sum(r['_o'] for r in v)
    e = (bo / bs) * gs
    setrows.append((k, len(v), gs, go, e, go / e if e else float('nan')))
for k, n, gs, go, e, oe in sorted(setrows, key=lambda x: x[5]):
    O2 = tO - go; E2 = tE - e
    say(f'    {dm(k[0])} .{k[1]:6s} {k[2][:30]:30s} {n:2d} дом  O/E {oe:5.2f}   без него итог {O2/E2:.2f}')
say('')

# 4в. перестановка НАБОРАМИ внутри страты
say('4в. Перестановка НАБОРАМИ: внутри каждой страты метка «Generator» раздаётся целым наборам,')
say('    случайный поднабор наборов подбирается так, чтобы число доменов совпало с наблюдаемым.')


def perm_sets(pool_rows, target_pred, nperm=NPERM, allow_nc_base=False):
    """Перестановка метки целыми наборами внутри страт день x зона."""
    strat = collections.defaultdict(list)
    for r in pool_rows:
        strat[(r['день запуска'], r['_z'])].append(r)
    units = []
    for k, v in strat.items():
        tgt = [r for r in v if target_pred(r)]
        if not tgt:
            continue
        rest = [r for r in v if not target_pred(r)]
        if not rest:
            continue
        bysets = collections.defaultdict(list)
        for r in v:
            bysets[r['набор контента']].append(r)
        units.append((k, list(bysets.values()), len(tgt)))
    obs_O = obs_E = 0.0
    for k, sets_, ntgt in units:
        v = [r for s in sets_ for r in s]
        tgt = [r for r in v if target_pred(r)]
        rest = [r for r in v if not target_pred(r)]
        gs = sum(r['_s'] for r in tgt); go = sum(r['_o'] for r in tgt)
        bs = sum(r['_s'] for r in rest); bo = sum(r['_o'] for r in rest)
        obs_O += go; obs_E += (bo / bs) * gs
    obs = obs_O / obs_E if obs_E else float('nan')
    null = []
    for _ in range(nperm):
        tO = tE = 0.0
        ok = True
        for k, sets_, ntgt in units:
            order = sets_[:]
            random.shuffle(order)
            pick, cnt = [], 0
            for s in order:
                if cnt >= ntgt:
                    break
                pick.append(s); cnt += len(s)
            picked = [r for s in pick for r in s]
            ps = set(id(r) for r in picked)
            rest = [r for s in sets_ for r in s if id(r) not in ps]
            if not rest or not picked:
                ok = False
                break
            gs = sum(r['_s'] for r in picked); go = sum(r['_o'] for r in picked)
            bs = sum(r['_s'] for r in rest); bo = sum(r['_o'] for r in rest)
            tO += go; tE += (bo / bs) * gs
        if ok and tE:
            null.append(tO / tE)
    return obs, null


obs_s, null_s = perm_sets(named, is_gen4_6)
say(f'    наблюдено O/E = {f2(obs_s)}; при случайной раздаче метки НАБОРАМ коридор '
    f'{f2(quant(null_s,0.025))}–{f2(quant(null_s,0.975))}, p(<=) = {perm_p(null_s, obs_s, "low"):.4f}')
say(f'    (для сравнения: у тестировщика при перестановке ДОМЕНАМИ коридор 0.68–1.47, p = 0.0001)')
say('')

# ------------------------------------------------- 5. семейство
say('=' * 126)
say('5. СЕМЕЙСТВО: «ВЕТКА ГЕНЕРАТОРА» ИЛИ ВООБЩЕ НУМЕРОВАННЫЕ ГЕНЕРИРОВАННЫЕ НАБОРЫ?')
say('=' * 126)


def family(s):
    ls = s
    if ls.startswith('Generator_11page') or ls.startswith('ТЕСТ B Generator'):
        return 'Generator_11page (старый)'
    if ls.startswith('Generator'):
        return 'Generator 04-06.09'
    for pref in ('nabory', 'nabor'):
        if ls.startswith(pref):
            return 'nabory-NNN (нумерованные)'
    for pref in ('NEW102', 'NEW50', 'NEW33', 'NEW21', 'NEW20', 'NEW17', 'КОНТРОЛЬ'):
        if ls.startswith(pref):
            return 'NEW*/КОНТРОЛЬ'
    if ls.startswith('archive'):
        return 'archive*'
    if ls.startswith('clean'):
        return 'clean*'
    if ls.startswith('content-2026'):
        return 'content-2026-*'
    if ls.startswith('script_yandex'):
        return 'script_yandex'
    if ls.startswith('Content_script'):
        return 'Content_script'
    return 'именные/прочие'


fam_rows = {}
for f in sorted({family(r['набор контента']) for r in named}):
    O = E = S = 0.0
    nd = 0
    nst = 0
    strat = collections.defaultdict(list)
    for r in named:
        strat[(r['день запуска'], r['_z'])].append(r)
    for k, v in strat.items():
        tgt = [r for r in v if family(r['набор контента']) == f]
        rest = [r for r in v if family(r['набор контента']) != f]
        if not tgt or not rest:
            continue
        bs = sum(r['_s'] for r in rest); bo = sum(r['_o'] for r in rest)
        gs = sum(r['_s'] for r in tgt); go = sum(r['_o'] for r in tgt)
        O += go; E += (bo / bs) * gs; S += gs; nd += len(tgt); nst += 1
    if nd:
        fam_rows[f] = (nd, S, O, E, O / E if E else float('nan'), nst)
say(f"{'семейство':30s} {'дом':>4s} {'сайтов':>8s} {'O':>6s} {'E':>8s} {'O/E':>6s} {'страт':>6s}")
for f, (nd, S, O, E, oe, nst) in sorted(fam_rows.items(), key=lambda x: x[1][4]):
    say(f'{f:30s} {nd:4d} {S:8.0f} {O:6.0f} {E:8.1f} {oe:6.2f} {nst:6d}')
say('')
say('Прямое сравнение внутри одной страты: Generator против nabory-NNN там, где они стоят рядом:')
for key in gen_strata:
    sub = [r for r in named if r['день запуска'] == key[0] and r['_z'] == key[1]]
    g = [r for r in sub if is_gen4_6(r)]
    nb_ = [r for r in sub if family(r['набор контента']) == 'nabory-NNN (нумерованные)']
    if g and nb_:
        gs = sum(r['_s'] for r in g); go = sum(r['_o'] for r in g)
        bs = sum(r['_s'] for r in nb_); bo = sum(r['_o'] for r in nb_)
        say(f'  {dm(key[0])} .{key[1]}: Gen {len(g)} дом выход {100*go/gs:.1f}%, '
            f'nabory {len(nb_)} дом выход {100*bo/bs:.1f}%, отношение {(go/gs)/(bo/bs):.2f}')
say('  (в остальных стратах Generator нумерованных соседей нет — сравнение идёт только с NEW*/именными)')
say('')
say('Все нумерованные наборы (Generator_NNNNNN + nabory-NNN) одним куском против НЕнумерованных соседей')
say('в тех же стратах день+зона:')


def num_family(r):
    f = family(r['набор контента'])
    return f in ('Generator 04-06.09', 'nabory-NNN (нумерованные)')


O = E = S = 0.0
nd = 0
strat = collections.defaultdict(list)
for r in named:
    strat[(r['день запуска'], r['_z'])].append(r)
for k, v in strat.items():
    tgt = [r for r in v if num_family(r)]
    rest = [r for r in v if not num_family(r)]
    if not tgt or not rest:
        continue
    bs = sum(r['_s'] for r in rest); bo = sum(r['_o'] for r in rest)
    gs = sum(r['_s'] for r in tgt); go = sum(r['_o'] for r in tgt)
    O += go; E += (bo / bs) * gs; S += gs; nd += len(tgt)
say(f'  нумерованные: {nd} дом, {S:.0f} сайтов, O {O:.0f}, E {E:.1f}, O/E {O/E:.2f}')
obs_n, null_n = perm_sets(named, num_family)
say(f'  перестановка НАБОРАМИ: коридор {f2(quant(null_n,0.025))}–{f2(quant(null_n,0.975))}, '
    f'p(<=) = {perm_p(null_n, obs_n, "low"):.4f}')
say('')

# ------------------------------------------------- 6. парные сравнения
say('=' * 126)
say('6. ПАРНЫЕ СРАВНЕНИЯ ВНУТРИ ПУЛА (домен Generator против соседей того же дня+зоны+блока часа)')
say('=' * 126)
for base_mode, bname in (('named', 'соседи с именем набора'), ('all', 'соседи включая «НЕ ЗАПИСАН»')):
    diffs = []
    skipped = 0
    for r in gen_all:
        nb_ = [x for x in base_all
               if x['день запуска'] == r['день запуска'] and x['_z'] == r['_z']
               and x['_blk'] == r['_blk'] and not is_gen4_6(x)]
        if base_mode == 'named':
            nb_ = [x for x in nb_ if not x['_nc']]
        if not nb_:
            skipped += 1
            continue
        bs = sum(x['_s'] for x in nb_); bo = sum(x['_o'] for x in nb_)
        diffs.append((r['_o'] / r['_s']) - (bo / bs))
    pos = sum(1 for d in diffs if d > 0); neg = sum(1 for d in diffs if d < 0)
    n = pos + neg
    p = 0.0
    for k in range(0, min(pos, neg) + 1):
        p += math.comb(n, k) * 0.5 ** n
    p = min(1.0, 2 * p)
    say(f'  [{bname}] сопоставимых доменов {len(diffs)} (без пары {skipped}); '
        f'ниже соседей {neg}, выше {pos}; знаковый тест p = {p:.4f}; '
        f'медиана разницы выхода {100*sorted(diffs)[len(diffs)//2]:+.1f} п.п.')
say('')

# ------------------------------------------------- 7. Content_script и script_yandex
say('=' * 126)
say('7. Content_script_12page_08.09 И script_yandex_12page ПОД ЖЁСТКОЙ СТРАТОЙ')
say('=' * 126)


def set_hard(setname, days=None):
    say(f'--- {setname}')
    sel = [r for r in named if r['набор контента'] == setname and (days is None or r['день запуска'] in days)]
    say(f'  доменов {len(sel)}; страты: '
        + ', '.join(sorted({dm(r["день запуска"]) + " ." + r["_z"] for r in sel})))
    for level, lname in (('blk', 'день+зона+блок часа'), ('hour', 'день+зона+точный час')):
        O = E = 0.0
        nd = 0
        skipped = 0
        lines = []
        strat = collections.defaultdict(list)
        for r in base_all:
            strat[(r['день запуска'], r['_z'], r['_blk'] if level == 'blk' else r['_h'])].append(r)
        for k in sorted(strat):
            v = strat[k]
            g = [r for r in v if r['набор контента'] == setname and (days is None or r['день запуска'] in days)]
            if not g:
                continue
            ob = [r for r in v if r not in g and not r['_nc']]
            gs = sum(r['_s'] for r in g); go = sum(r['_o'] for r in g)
            if not ob:
                skipped += len(g)
                lines.append(f'    {dm(k[0])} .{k[1]} {k[2]}: {len(g)} дом, выход {100*go/gs:.1f}% — соседей нет')
                continue
            bs = sum(r['_s'] for r in ob); bo = sum(r['_o'] for r in ob)
            e = (bo / bs) * gs
            O += go; E += e; nd += len(g)
            lines.append(f'    {dm(k[0])} .{k[1]} {k[2]}: {len(g)} дом, выход {100*go/gs:5.1f}%, '
                         f'соседей {len(ob)} выход {100*bo/bs:5.1f}%, O/E {go/e:.2f}')
        say(f'  страта {lname}:')
        for ln in lines:
            say(ln)
        say(f'    итого оцениваемых {nd} дом (без пары {skipped}), O {O:.0f}, E {E:.1f}, '
            f'O/E {f2(O/E if E else float("nan"))}')
    # часы
    byh = collections.defaultdict(list)
    for r in sel:
        byh[(dm(r['день запуска']), r['_z'], r['_h'])].append(r['домен'])
    say('  часы постановки набора: ' + '; '.join(f'{k[0]} .{k[1]} ч{k[2]:02d}×{len(v)}' for k, v in sorted(byh.items())))
    say('')


set_hard('Content_script_12page_08.09')
set_hard('script_yandex_12page')

say('Деньги Content_script_12page_08.09: 6 регистраций у тестировщика. Разбивка по доменам:')
cs = [r for r in named if r['набор контента'] == 'Content_script_12page_08.09']
for r in sorted(cs, key=lambda r: -r['_reg']):
    say(f'  {r["домен"]:16s} {dm(r["день запуска"])} .{r["_z"]:6s} ч{r["_h"]:02d} '
        f'сайтов {r["_s"]:.0f}, вышли {r["_o"]:.0f}, рег {r["_reg"]:.0f}')
tot_reg = sum(r['_reg'] for r in cs)
say(f'  всего регистраций {tot_reg:.0f}; доменов с регистрацией {sum(1 for r in cs if r["_reg"]>0)} из {len(cs)}.')
say(f'  Без одного домена 3237.lol (3 рег): {tot_reg-3:.0f} регистрации на {len(cs)-1} доменах.')
say('')

# ------------------------------------------------- 8. общий каркас 17/72
say('=' * 126)
say('8. ОБЩИЙ КАРКАС «17 НАБОРОВ ВНЕ КОРИДОРА ПРИ 3.5 ОЖИДАЕМЫХ» — ТОЖЕ ЧАСТЬ ТЕНИ')
say('=' * 126)
say('Перестановка тестировщика мешает домены внутри дня и зоны, игнорируя блок часа. Если наборы')
say('ставятся партиями по часам, а блок часа сам даёт разброс O/E, часть «выбросов» — это часы.')
say('Считаем те же наборы (>=5 доменов в страте и >=5 чужих), но коридор строим перестановкой')
say('ВНУТРИ день+зона+блок часа (метка набора мешается только среди доменов того же блока).')

strat_soft = collections.defaultdict(list)
for r in named:
    strat_soft[(r['день запуска'], r['_z'])].append(r)
targets = []
for k, v in strat_soft.items():
    bysets = collections.defaultdict(list)
    for r in v:
        bysets[r['набор контента']].append(r)
    for s, vv in bysets.items():
        if len(vv) >= 5 and len(v) - len(vv) >= 5:
            targets.append((k, s, vv, v))
say(f'  наборов в проверке: {len(targets)}')


def oe_of(vv, others):
    gs = sum(r['_s'] for r in vv); go = sum(r['_o'] for r in vv)
    bs = sum(r['_s'] for r in others); bo = sum(r['_o'] for r in others)
    if bs <= 0 or gs <= 0:
        return float('nan')
    return go / ((bo / bs) * gs)


NP2 = 3000
out_soft = out_hard = 0
res = []
for k, s, vv, v in targets:
    others = [r for r in v if r['набор контента'] != s]
    obs = oe_of(vv, others)
    # мягкий коридор: мешаем по всей страте
    null1 = []
    for _ in range(NP2):
        pick = random.sample(v, len(vv))
        ps = set(id(x) for x in pick)
        rest = [x for x in v if id(x) not in ps]
        val = oe_of(pick, rest)
        if val == val:
            null1.append(val)
    # жёсткий коридор: мешаем внутри блоков часа
    byb = collections.defaultdict(list)
    for r in v:
        byb[r['_blk']].append(r)
    cnt = collections.Counter(r['_blk'] for r in vv)
    null2 = []
    for _ in range(NP2):
        pick = []
        for b, n in cnt.items():
            pool = byb[b]
            pick += random.sample(pool, min(n, len(pool)))
        ps = set(id(x) for x in pick)
        rest = [x for x in v if id(x) not in ps]
        val = oe_of(pick, rest)
        if val == val:
            null2.append(val)
    lo1, hi1 = quant(null1, 0.025), quant(null1, 0.975)
    lo2, hi2 = quant(null2, 0.025), quant(null2, 0.975)
    o1 = not (lo1 <= obs <= hi1)
    o2 = not (lo2 <= obs <= hi2)
    out_soft += o1; out_hard += o2
    res.append((k, s, len(vv), obs, lo1, hi1, o1, lo2, hi2, o2))
say(f'  вне мягкого коридора (день+зона): {out_soft} из {len(targets)}')
say(f'  вне ЖЁСТКОГО коридора (день+зона+блок часа): {out_hard} из {len(targets)}')
say('  наборы, которые «выброс» только при мягкой страте (часовая тень):')
for k, s, n, obs, lo1, hi1, o1, lo2, hi2, o2 in sorted(res, key=lambda x: x[3]):
    if o1 and not o2:
        say(f'    {dm(k[0])} .{k[1]:6s} {s[:38]:38s} O/E {obs:5.2f}  мягкий [{lo1:.2f}–{hi1:.2f}]  '
            f'жёсткий [{lo2:.2f}–{hi2:.2f}]')
say('  названные гипотезой наборы:')
for k, s, n, obs, lo1, hi1, o1, lo2, hi2, o2 in sorted(res, key=lambda x: x[3]):
    if s.startswith('Generator') or s in ('script_yandex_12page', 'Content_script_12page_08.09'):
        say(f'    {dm(k[0])} .{k[1]:6s} {s[:38]:38s} O/E {obs:5.2f}  мягкий [{lo1:.2f}–{hi1:.2f}] '
            f'{"ВНЕ" if o1 else "внутри":6s}  жёсткий [{lo2:.2f}–{hi2:.2f}] {"ВНЕ" if o2 else "внутри"}')
say('')

# ------------------------------------------------- 9. деньги
say('=' * 126)
say('9. ДЕНЬГИ ПО GENERATOR 04-06.09')
say('=' * 126)
gr = sum(r['_reg'] for r in gen_all)
gfd = sum(num(r['ФД в окне 3 суток']) for r in gen_all)
say(f'  Generator 04-06.09: {len(gen_all)} доменов, регистраций в окне {gr:.0f}, ФД {gfd:.0f}.')
say('  Тестировщик: 3 при ожидании 3.56, P(<=3) = 0.47 — не различимо. Это единственная величина,')
say('  ради которой ветку стоило бы закрывать, и она пустая в обе стороны.')
say('')


# ------------------------------------------------- 10. интервалы
say('=' * 126)
say('10. ИНТЕРВАЛЫ: НАСКОЛЬКО ТОЧНО ВООБЩЕ ИЗВЕСТНО ЭТО «В 2,2 РАЗА»')
say('=' * 126)
say('Бутстрэп НАБОРАМИ (единица — «набор x страта», их у Generator 9): 10 000 пересборок с возвращением.')


def boot_oe(units, nboot=10000):
    vals = []
    for _ in range(nboot):
        pick = [random.choice(units) for _ in units]
        O = sum(u[0] for u in pick); E = sum(u[1] for u in pick)
        if E:
            vals.append(O / E)
    return vals


gen_units = [(go, e) for k, n, gs, go, e, oe in setrows]
bv = boot_oe(gen_units)
say(f'  Generator 04-06.09 (мягкая страта день+зона): O/E = {tO/tE:.2f}, '
    f'бутстрэп-интервал 95% {quant(bv,0.025):.2f}–{quant(bv,0.975):.2f} '
    f'(в разах: в {1/quant(bv,0.975):.1f}–{1/quant(bv,0.025):.1f} раза ниже соседей)')

# бутстрэп по блокам день x зона
blk_units = [(b[3], b[4]) for b in blocks]
bv2 = boot_oe(blk_units)
say(f'  то же, бутстрэп БЛОКАМИ «день x зона» (их 4): интервал 95% {quant(bv2,0.025):.2f}–{quant(bv2,0.975):.2f}')

# жёсткая страта, блок часа, с НЕ ЗАПИСАН — по ячейкам
rowsout, O_h, E_h, S_h, nd_h = hard_oe('blk', 'all')
cell_units = [(go, e) for k, gd, gs, go, bd, bp, e, oe in rowsout if bd > 0]
bv3 = boot_oe(cell_units)
say(f'  жёсткая страта день+зона+блок часа, база с «НЕ ЗАПИСАН» (26 из 44 доменов): '
    f'O/E = {O_h/E_h:.2f}, бутстрэп по ячейкам (их {len(cell_units)}) '
    f'{quant(bv3,0.025):.2f}–{quant(bv3,0.975):.2f}')
say('')
say('Интервалы по семействам (бутстрэп наборами внутри семейства, 10 000):')


def family_units(pred):
    units = []
    strat = collections.defaultdict(list)
    for r in named:
        strat[(r['день запуска'], r['_z'])].append(r)
    for k, v in strat.items():
        tgt = [r for r in v if pred(r)]
        rest = [r for r in v if not pred(r)]
        if not tgt or not rest:
            continue
        bs = sum(r['_s'] for r in rest); bo = sum(r['_o'] for r in rest)
        bysets = collections.defaultdict(list)
        for r in tgt:
            bysets[r['набор контента']].append(r)
        for sname, vv in bysets.items():
            gs = sum(r['_s'] for r in vv); go = sum(r['_o'] for r in vv)
            units.append((go, (bo / bs) * gs))
    return units


fams = {
    'Generator 04-06.09': lambda r: family(r['набор контента']) == 'Generator 04-06.09',
    'nabory-NNN (нумерованные)': lambda r: family(r['набор контента']) == 'nabory-NNN (нумерованные)',
    'archive*': lambda r: family(r['набор контента']) == 'archive*',
    'script_yandex': lambda r: family(r['набор контента']) == 'script_yandex',
    'NEW*/КОНТРОЛЬ': lambda r: family(r['набор контента']) == 'NEW*/КОНТРОЛЬ',
    'content-2026-*': lambda r: family(r['набор контента']) == 'content-2026-*',
}
fam_ci = {}
for f, pred in fams.items():
    u = family_units(pred)
    O = sum(x[0] for x in u); E = sum(x[1] for x in u)
    b = boot_oe(u)
    fam_ci[f] = (O / E, quant(b, 0.025), quant(b, 0.975), len(u))
    say(f'  {f:28s} наборов-страт {len(u):3d}  O/E {O/E:.2f}  95% {quant(b,0.025):.2f}–{quant(b,0.975):.2f}')
say('')
say('Разница «Generator против nabory-NNN» (оба — нумерованные генерированные наборы):')
ug = family_units(fams['Generator 04-06.09'])
un = family_units(fams['nabory-NNN (нумерованные)'])
d = []
for _ in range(10000):
    a = [random.choice(ug) for _ in ug]
    b_ = [random.choice(un) for _ in un]
    oa = sum(x[0] for x in a) / sum(x[1] for x in a) if sum(x[1] for x in a) else float('nan')
    ob = sum(x[0] for x in b_) / sum(x[1] for x in b_) if sum(x[1] for x in b_) else float('nan')
    if oa == oa and ob == ob and ob:
        d.append(oa / ob)
obs_ratio = (sum(x[0] for x in ug) / sum(x[1] for x in ug)) / (sum(x[0] for x in un) / sum(x[1] for x in un))
say(f'  отношение O/E: {obs_ratio:.2f}, бутстрэп 95% {quant(d,0.025):.2f}–{quant(d,0.975):.2f}; '
    f'доля пересборок с отношением >= 1: {sum(1 for x in d if x >= 1)/len(d):.3f}')
say('  Если интервал накрывает 1 — «ветка генератора» не отделима от нумерованных наборов вообще.')
say('')
say('=' * 126)
say('ИТОГ')
say('=' * 126)
say('1. Ядро гипотезы ПЕРЕЖИВАЕТ жёсткую страту, но не в тех числах. Generator_* 04-06.09:')
say('   мягкая страта день+зона — O/E 0.46 (577 выходов при 1264,5 на 9063 сайтах, 44 домена);')
say('   бутстрэп НАБОРАМИ (9 единиц «набор x страта») 95% 0.32-0.60, БЛОКАМИ «день x зона» (4 единицы) 0.35-0.63;')
say('   жёсткая страта день+зона+блок часа при базе с ближайшими соседями («НЕ ЗАПИСАН») — 0.57,')
say('   бутстрэп по 4 ячейкам 0.34-1.01; при точном часе — 0.41 на 19 доменах.')
say('   То есть «в 2,2 раза» — это на деле «в 1,7-3,1 раза», а верхняя граница жёсткой страты упирается в 1,0.')
say('2. p = 0,0001 не защищается. Он получен перестановкой ДОМЕНОВ, то есть в предположении, что')
say('   44 домена независимы, хотя выходом управляет набор, а наборы ставятся сплошными партиями')
say('   (номера аккаунтов вебмастера идут подряд с порядком постановки). Тот же эффект:')
say('   перестановка НАБОРАМИ — p = 0,0010 (коридор 0,56-1,48); жёсткая страта по блоку часа с полной')
say('   базой — p = 0,0039; по точному часу — p = 0,015; знаковый тест по 4 блокам «день x зона» —')
say('   p = 0,063 (одност.), по 3 дням постановки — p = 0,125. Репликаций 3-4, а не 44.')
say('3. 18 из 44 доменов Generator (41%) вообще не с чем сравнивать: 13 доменов Generator_370382 вышли')
say('   05.09 в 00 и 08 часов, 5 доменов Generator_392396 — 06.09 в 09 часов, а все не-Generator домены')
say('   тех же дней и зон поставлены с 12 часов и позже. Для них метка набора и партия постановки —')
say('   одно и то же; перестановочный коридор вырождается в точку (0.37-0.37 и 0.65-0.65).')
say('   Блок часа сам по себе не нейтрален: 00-05 даёт O/E 0,88-0,90, 06-11 — 0,87-0,89, 12-17 — 1,16.')
say('4. Состав базы решает почти столько же, сколько сам набор. Generator_346353 (8 доменов, 04.09 .team,')
say('   час 17): против базы тестировщика — O/E 0,40 (вся база = 1 домен kruzhevnaya с выходом 30,1%);')
say('   против базы с 13 доменами «КОНТЕНТ НЕ ЗАПИСАН», поставленными в тот же день и зону в 14-16 часов,')
say('   — O/E 1,08. Утверждение «КОНТЕНТ НЕ ЗАПИСАН полностью сцеплен с датой (до 24.08)» неверно:')
say('   117 из 335 таких доменов стоят 24.08 и позже, в 15 стратах, в том числе 13 на 04.09 .team и')
say('   15 на 04.09 .lol — это ближайшие по времени соседи Generator.')
say('5. «Ветка генератора» не отделяется от нумерованных генерированных наборов вообще. По семействам')
say('   (O/E против не-семейных соседей той же страты, бутстрэп наборами):')
say('   Generator 04-06.09 0,46 [0,32-0,60]; nabory-NNN 0,65 [0,56-0,76]; script_yandex 0,73 [0,52-1,13];')
say('   archive* 0,74 [0,50-1,23]; NEW*/КОНТРОЛЬ 1,34 [1,20-1,49]; content-2026-* 1,48 [1,34-1,63].')
say('   Отношение Generator/nabory 0,70 [0,48-0,96] — Generator в нижнем краю той же полосы, а не')
say('   отдельная «мёртвая ветка». Прямо рядом в одной страте: 05.09 .team Generator/nabory = 1,22,')
say('   06.09 .team = 0,78.')
say('6. ОПРОВЕРГНУТО отдельно: Content_script_12page_08.09. Его 2,61 в 08.09 .lol — тень блока часа:')
say('   при коридоре, построенном внутри день+зона+блок часа, случайные домены тех же часов дают')
say('   1,29-2,79, то есть 2,61 лежит ВНУТРИ. В жёсткой страте день+зона+блок часа набор даёт O/E 1,10')
say('   (312 выходов при 282,5) — ровно столько же, сколько против clean7. Деньги: 6 регистраций,')
say('   из них 3 у одного домена 3237.lol, и всего 4 домена из 11 с регистрацией.')
say('7. ОПРОВЕРГНУТО отдельно: «худшие во всей сети» nabory-500-509_styled_img (0,21) — тоже тень часа:')
say('   жёсткий коридор 0,17-0,86, наблюдённые 0,21 внутри него. Часовая тень снимает 3 «выброса» из 17')
say('   (14 из 72 остаются вне коридора при 3,5 ожидаемых) — общий каркас «наборы расходятся сильнее')
say('   случайного» выживает, но конкретные имена в списке худших/лучших зависят от часа постановки.')
say('8. script_yandex_12page — как и у тестировщика, ничего: жёсткая страта по блоку часа даёт 0,85')
say('   (15 доменов), по точному часу 0,66 (10 доменов), 6-11 доменов из 21 сравнивать не с чем.')
say('9. Деньги Generator: 3 регистрации и 0 ФД на 44 доменах при ожидании 3,56 — пусто в обе стороны.')
say('')
say('ЧТО ЭТО ЗНАЧИТ. Вывод «наборы Generator 04-06.09 — мёртвая ветка» не опровергнут по знаку:')
say('в каждой из 4 страт и в каждой из 9 пар «набор x страта» выход ниже соседского, 24 из 26')
say('сопоставимых доменов ниже своих соседей по дню+зоне+блоку часа (знаковый тест p < 0,001;')
say('с полной базой 21 из 26, p = 0,003). Но опровергнуты три вещи: точность («в 2,2 раза» → в 1,7-3,1),')
say('уверенность (p 0,0001 → 0,001-0,015, а по дням постановки 0,13) и причина: разделить «контент')
say('генератора» и «партию постановки 04-06.09» эти данные не позволяют — 41% доменов ветки стоят')
say('в часах, где не-Generator доменов нет вовсе.')
say.f.flush()
