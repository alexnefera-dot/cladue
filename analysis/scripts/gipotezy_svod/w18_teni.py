#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №18 (угол ТЕНИ / конфаундинг).

Вердикт тестировщика: «опровергнута» — зона и семейство контента не «выбирают»
бренды; таблица бренд × зона после стратификации по пулу «набор контента + день»
даже ровнее случайной (хи2 25,3 при 30,0 ожидаемых, p = 0,70).

Скептический вопрос здесь ОБРАТНЫЙ обычному: это НЕ эффект, который может быть
тенью конфаундера, а ОТСУТСТВИЕ эффекта, которое само может быть тенью
конструкции — стратификация по «набор контента + день» почти нацело обнуляет
контраст зоны (зона сцеплена с партией постановки), после чего тест перестаёт
что-либо различать. Проверяем:
  1) сколько контрастной информации о зоне переживает страту (не событий, а
     информационного веса n*p*(1-p));
  2) что даёт БОЛЕЕ ЖЁСТКАЯ страта (+ блок часа для зоны; день+зона и
     день+зона+час для семейства) — исчезает ли «намёк», меняет ли знак;
  3) периоды (август / сентябрь), «КОНТЕНТ НЕ ЗАПИСАН», выбросы 3615/3286.team,
     самый крупный пул — устойчив ли нуль к ним, не собран ли он из
     разнонаправленных кусков;
  4) парные сравнения внутри пула (Мантель–Хензель + кластерный бутстрап по
     доменам) — какие ИНТЕРВАЛЫ на самом деле совместимы с данными;
  5) МОЩНОСТЬ: подсаживаем настоящий эффект «зона выбирает бренд» заданной
     силы R в наблюдённую структуру (объёмы доменов, зон и брендов сохранены)
     и смотрим, как часто главный тест тестировщика его ловит.
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
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w18_teni.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
ZONES = ['team', 'lol', 'casino']
FAM_MAIN = ['content-дата', 'NEW', 'archive', 'nabory', 'прочие']
FAM_OTHER = {'Generator', 'clean', 'script', 'контроль', 'тест', 'прочее'}
MIN_BRAND = 7
MIN_SINGLE = 5
BRAND_RE = re.compile(r'^\s*(.+?)\s*\((\d+)\)\s*$')
NPERM = 5000
random.seed(20260922)


class Tee(object):
    def __init__(self, path):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def __call__(self, *a):
        s = ' '.join(str(x) for x in a)
        print(s)
        self.f.write(s + '\n')

    def close(self):
        self.f.close()


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


def fp(p):
    if p is None:
        return '   —'
    return '%.4f' % p if p >= 1e-4 else '<1e-4'


def bh(ps):
    m = len(ps)
    if not m:
        return []
    order = sorted(range(m), key=lambda i: ps[i])
    q = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        prev = min(prev, ps[i] * m / rank)
        q[i] = prev
    return q


# ------------------------------------------------------------------ движок
class Design(object):
    """Стратифицированная таблица бренд x метка. Повторяет расчёт тестировщика:
    E = сумма по стратам (события бренда в страте x доля метки среди событий страты),
    вклад дают только смешанные страты; нуль — перестановка метки между доменами
    (или между 'единицами' — наборами контента) внутри страты."""

    def __init__(self, doms, labels):
        self.labels = labels
        L = len(labels)
        self.L = L
        self.doms = doms
        self.tot = [sum(n for _, n in d['recs']) for d in doms]
        cnt_b = collections.Counter()
        for d in doms:
            for b, n in d['recs']:
                cnt_b[b] += n
        self.cnt_b = cnt_b
        self.brands = sorted([b for b in cnt_b if cnt_b[b] >= MIN_BRAND],
                             key=lambda b: (-cnt_b[b], b))
        self.bidx = {b: i for i, b in enumerate(self.brands)}
        self.nb = len(self.brands)
        self.recs = [[(self.bidx[b], n) for b, n in d['recs'] if b in self.bidx] for d in doms]
        strata = collections.OrderedDict()
        for i, d in enumerate(doms):
            strata.setdefault(d['stratum'], []).append(i)
        self.mixed = []
        self.units = []
        for s, idx in strata.items():
            labs = set(doms[i]['label'] for i in idx)
            ev = sum(self.tot[i] for i in idx)
            if len(labs) >= 2 and ev > 0:
                self.mixed.append(idx)
                g = collections.OrderedDict()
                for i in idx:
                    g.setdefault(doms[i].get('unit') or i, []).append(i)
                self.units.append(list(g.values()))
        self.n_str = len(strata)
        self.mixed_dom = sum(len(i) for i in self.mixed)
        self.mixed_ev = sum(self.tot[i] for idx in self.mixed for i in idx)
        self.n_ev = sum(self.tot)
        self.lab0 = [d['label'] for d in doms]

    def compute(self, lab, recs=None):
        recs = self.recs if recs is None else recs
        L = self.L
        O = [[0.0] * L for _ in range(self.nb)]
        E = [[0.0] * L for _ in range(self.nb)]
        tot = self.tot
        for idx in self.mixed:
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
                    Ei = E[bi]
                    for l in range(L):
                        Ei[l] += n * share[l]
        return O, E

    @staticmethod
    def chi(O, E):
        tot = 0.0
        per = []
        for bi in range(len(O)):
            s = 0.0
            for l in range(len(O[bi])):
                e = E[bi][l]
                if e > 0:
                    s += (O[bi][l] - e) ** 2 / e
            per.append(s)
            tot += s
        return tot, per

    def perm_labels(self, lab, by_unit=False):
        new = lab[:]
        if not by_unit:
            for idx in self.mixed:
                vals = [lab[i] for i in idx]
                random.shuffle(vals)
                for i, v in zip(idx, vals):
                    new[i] = v
        else:
            for us in self.units:
                vals = [lab[u[0]] for u in us]
                random.shuffle(vals)
                for u, v in zip(us, vals):
                    for i in u:
                        new[i] = v
        return new

    def run(self, nperm=NPERM, by_unit=False):
        O, E = self.compute(self.lab0)
        chi0, per0 = self.chi(O, E)
        ge = 0
        geb = [0] * self.nb
        mean = 0.0
        lab = self.lab0
        for _ in range(nperm):
            pl = self.perm_labels(lab, by_unit)
            Op, Ep = self.compute(pl)
            c, pb = self.chi(Op, Ep)
            mean += c
            if c >= chi0 - 1e-9:
                ge += 1
            for bi in range(self.nb):
                if pb[bi] >= per0[bi] - 1e-9:
                    geb[bi] += 1
        p = (ge + 1.0) / (nperm + 1.0)
        pb = [(g + 1.0) / (nperm + 1.0) for g in geb]
        return {'O': O, 'E': E, 'chi': chi0, 'chi_mean': mean / nperm, 'p': p,
                'pb': pb, 'per0': per0, 'q': bh(pb)}


def build(rows, labels, lab_fn, str_fn, unit_fn=None):
    out = []
    for r in rows:
        l = lab_fn(r)
        if l is None or l not in labels:
            continue
        out.append({'name': r['домен'], 'label': labels.index(l), 'stratum': str_fn(r),
                    'unit': unit_fn(r) if unit_fn else None, 'recs': r['_recs']})
    return out


def brief(log, tag, des, res, note=''):
    log('  %-52s страт %4d, смеш. %3d, доменов в них %4d, событий %3d из %3d (%2.0f%%) | хи2 %6.1f при %6.1f на перестановках, p = %s %s' % (
        tag, des.n_str, len(des.mixed), des.mixed_dom, des.mixed_ev, des.n_ev,
        100.0 * des.mixed_ev / max(1, des.n_ev), res['chi'], res['chi_mean'], fp(res['p']), note))


def main():
    log = Tee(OUT)
    log('КОНТРПРОВЕРКА №18 (ТЕНИ). Источник: %s' % os.path.relpath(SRC, REPO))
    log('Вердикт тестировщика: «опровергнута» (зона и семейство не выбирают бренды).')
    log('Скептическая версия: НУЛЬ САМ — тень конструкции. Страта «набор контента + день» почти')
    log('нацело съедает контраст зоны (зона сцеплена с партией постановки), и тест перестаёт различать.')
    log('')

    rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
    for r in rows:
        r['_recs'] = parse_brands(r['какие бренды конвертили'])
    base = [r for r in rows if r['окно закрыто'] == 'да' and r['дней'] != '1']
    ev = lambda rs: sum(n for r in rs for _, n in r['_recs'])
    log('Фильтр тестировщика воспроизведён: %d доменов, %d событий (рег + ФД за всё время).' % (len(base), ev(base)))
    bz = [r for r in base if r['зона'] in ZONES]
    log('Зоны team/lol/casino: %d доменов, %d событий.' % (len(bz), ev(bz)))
    log('')

    # ========================================================== 1. информация
    log('=' * 100)
    log('(1) СКОЛЬКО КОНТРАСТА ЗОНЫ ПЕРЕЖИВАЕТ СТРАТУ «набор контента + день»')
    log('=' * 100)
    log('Информационный вес пула для контраста «team против прочих» = n_событий x p x (1-p),')
    log('где p — доля team среди событий пула. Это то, чем тест реально располагает.')
    pools = collections.OrderedDict()
    for r in bz:
        k = (r['набор контента'], r['день запуска'])
        p = pools.setdefault(k, {'dom': [0, 0, 0], 'ev': [0, 0, 0]})
        p['dom'][ZONES.index(r['зона'])] += 1
        p['ev'][ZONES.index(r['зона'])] += sum(n for _, n in r['_recs'])
    mixed = [(k, v) for k, v in pools.items() if sum(1 for x in v['dom'] if x) >= 2 and sum(v['ev']) > 0]
    tot_ev = ev(bz)
    gp = sum(v['ev'][0] for v in pools.values()) / float(tot_ev)
    info_naive = tot_ev * gp * (1 - gp)
    info_mixed = 0.0
    rowsinf = []
    for k, v in mixed:
        n = float(sum(v['ev']))
        p = v['ev'][0] / n
        w = n * p * (1 - p)
        info_mixed += w
        rowsinf.append((w, k, v, n, p))
    rowsinf.sort(reverse=True, key=lambda x: x[0])
    log('Без страты: событий %d, доля team %.2f -> информационный вес %.1f.' % (tot_ev, gp, info_naive))
    log('В 45 смешанных пулах: событий %d, информационный вес %.1f — это %.0f%% от наивного.' % (
        int(sum(x[3] for x in rowsinf)), info_mixed, 100.0 * info_mixed / info_naive))
    log('Иначе говоря: тест, объявленный «главным», работает примерно как выборка в %.0f эффективных событий' % (
        info_mixed / (gp * (1 - gp))))
    log('вместо 492 — при 21 бренде и поправке на множественность.')
    log('Пулы по вкладу (вес, события team/lol/casino, домены team/lol/casino):')
    for w, k, v, n, p in rowsinf[:12]:
        log('  вес %5.1f  %s %-34s события %3d/%3d/%3d  домены %3d/%3d/%3d' % (
            w, k[1], k[0][:34], v['ev'][0], v['ev'][1], v['ev'][2], v['dom'][0], v['dom'][1], v['dom'][2]))
    single_pools = [k for k, v in pools.items() if sum(1 for x in v['dom'] if x) == 1]
    dom_single = sum(sum(v['dom']) for k, v in pools.items() if sum(1 for x in v['dom'] if x) == 1)
    ev_single = sum(sum(v['ev']) for k, v in pools.items() if sum(1 for x in v['dom'] if x) == 1)
    nab = collections.defaultdict(set)
    for r in bz:
        nab[r['набор контента']].add(r['зона'])
    log('')
    log('Почему так: зона почти ВЛОЖЕНА в партию постановки.')
    log('  Однозонных пулов «набор + день»: %d из %d (%.0f%%); в них %d доменов из %d и %d событий из %d.' % (
        len(single_pools), len(pools), 100.0 * len(single_pools) / len(pools), dom_single, len(bz), ev_single, tot_ev))
    log('  Наборов контента, целиком лежащих в одной зоне: %d из %d.' % (
        sum(1 for v in nab.values() if len(v) == 1), len(nab)))
    log('  То есть «зона» и «набор контента + день» на этих данных почти неразличимы: стратификация по')
    log('  пулу не «очищает» зону от контента, она вычитает почти всю зону. Нулевой результат такого')
    log('  теста означает «не идентифицируется», а не «эффекта нет».')
    dead = [x for x in rowsinf if x[0] < 1.0]
    log('Пулов с весом < 1,0 (фактически нулевой вклад): %d из %d; они несут %d событий.' % (
        len(dead), len(rowsinf), int(sum(x[3] for x in dead))))
    log('')

    # ========================================================== 2. жёсткие страты
    log('=' * 100)
    log('(2) БОЛЕЕ ЖЁСТКИЕ СТРАТЫ')
    log('=' * 100)
    zl = lambda r: r['зона']
    log('Зона (метка = team/lol/casino):')
    runs = []
    for tag, sfn in [
        ('набор + день (главная у тестировщика)', lambda r: (r['набор контента'], r['день запуска'])),
        ('набор + день + блок часа', lambda r: (r['набор контента'], r['день запуска'], r['блок часа'])),
        ('набор + день + час запуска', lambda r: (r['набор контента'], r['день запуска'], r['час запуска'])),
        ('день', lambda r: r['день запуска']),
    ]:
        d = Design(build(bz, ZONES, zl, sfn), ZONES)
        res = d.run()
        runs.append((tag, d, res))
        brief(log, tag, d, res)
    log('')
    log('Семейство (метка = %s), жёсткие страты:' % '/'.join(FAM_MAIN))
    bf = [r for r in base if fam_of(r['семейство']) in FAM_MAIN]
    fl = lambda r: fam_of(r['семейство'])
    fam_runs = []
    for tag, sfn, byu in [
        ('день (главная у тестировщика)', lambda r: r['день запуска'], False),
        ('день, перестановка между наборами', lambda r: r['день запуска'], True),
        ('день + зона', lambda r: (r['день запуска'], r['зона']), False),
        ('день + зона, между наборами', lambda r: (r['день запуска'], r['зона']), True),
        ('день + зона + блок часа', lambda r: (r['день запуска'], r['зона'], r['блок часа']), False),
    ]:
        d = Design(build(bf, FAM_MAIN, fl, sfn, unit_fn=lambda r: r['набор контента']), FAM_MAIN)
        res = d.run(by_unit=byu)
        fam_runs.append((tag, d, res))
        brief(log, tag, d, res)
    log('')
    log('Бренды «одного семейства» при >=5 конверсиях при жёсткой страте день + зона:')
    dfz = Design(build(bf, FAM_MAIN, fl, lambda r: (r['день запуска'], r['зона']), unit_fn=lambda r: r['набор контента']), FAM_MAIN)
    # считаем «одной метки» по всем стратам (как тестировщик) — только диагностика
    cnt = collections.Counter()
    cell = collections.defaultdict(collections.Counter)
    for r in bf:
        for b, n in r['_recs']:
            cnt[b] += n
            cell[b][fam_of(r['семейство'])] += n
    single = [b for b in cnt if cnt[b] >= MIN_SINGLE and len(cell[b]) == 1]
    log('  наблюдаются: %s' % ', '.join('%s (%d в %s)' % (b, cnt[b], list(cell[b])[0]) for b in sorted(single, key=lambda b: -cnt[b])))
    log('  (в жёсткой страте день+зона у них смешанных страт: %s)' % ', '.join(
        '%s %d' % (b, sum(1 for idx in dfz.mixed if any(dfz.bidx.get(bb) is not None and bb == b for i in idx for bb, _ in dfz.doms[i]['recs'])))
        for b in sorted(single, key=lambda b: -cnt[b])))
    log('')

    # ========================================================== 3. куски
    log('=' * 100)
    log('(3) ПЕРИОД, «НЕ ЗАПИСАН», ВЫБРОСЫ, САМЫЙ КРУПНЫЙ ПУЛ — не собран ли нуль из разнонаправленных кусков')
    log('=' * 100)
    poolfn = lambda r: (r['набор контента'], r['день запуска'])
    subsets = [
        ('всё (как у тестировщика)', bz),
        ('только август (день < 2026-09-01)', [r for r in bz if r['день запуска'] < '2026-09-01']),
        ('только сентябрь', [r for r in bz if r['день запуска'] >= '2026-09-01']),
        ('без «КОНТЕНТ НЕ ЗАПИСАН»', [r for r in bz if r['набор контента'] != NOCONTENT]),
        ('без выбросов 3615/3286.team', [r for r in bz if r['домен'] not in OUTLIERS]),
        ('без самого тяжёлого пула', None),
    ]
    heavy = rowsinf[0][1] if rowsinf else None
    for name, sub in subsets:
        if sub is None:
            sub = [r for r in bz if (r['набор контента'], r['день запуска']) != heavy]
            name = 'без пула %s %s' % (heavy[1], heavy[0][:26])
        if not sub:
            continue
        d = Design(build(sub, ZONES, zl, poolfn), ZONES)
        if not d.mixed:
            log('  %-52s смешанных пулов нет' % name)
            continue
        res = d.run(nperm=3000)
        brief(log, name, d, res)
    log('')

    # ========================================================== 4. интервалы
    log('=' * 100)
    log('(4) ЧТО НА САМОМ ДЕЛЕ СОВМЕСТИМО С ДАННЫМИ: O/E по главной страте с кластерным бутстрапом по доменам')
    log('=' * 100)
    d_main = runs[0][1]
    res_main = runs[0][2]
    O, E = res_main['O'], res_main['E']
    # кластерный бутстрап: внутри каждого смешанного пула пересэмплируем домены с возвратом
    NB = 2000
    boot = collections.defaultdict(list)
    for _ in range(NB):
        Ob = [[0.0] * 3 for _ in range(d_main.nb)]
        Eb = [[0.0] * 3 for _ in range(d_main.nb)]
        for idx in d_main.mixed:
            pick = [random.choice(idx) for _ in idx]
            evl = [0, 0, 0]
            for i in pick:
                evl[d_main.lab0[i]] += d_main.tot[i]
            S = float(sum(evl))
            if S <= 0:
                continue
            share = [x / S for x in evl]
            for i in pick:
                li = d_main.lab0[i]
                for bi, n in d_main.recs[i]:
                    Ob[bi][li] += n
                    for l in range(3):
                        Eb[bi][l] += n * share[l]
        for bi in range(d_main.nb):
            for l in range(3):
                if Eb[bi][l] > 0:
                    boot[(bi, l)].append(Ob[bi][l] / Eb[bi][l])
    log('Интервал осмыслен только при E >= 3 (иначе он мусорный) — такие строки помечены «*».')
    log('бренд          N  Nсм | зона  |   O     E    O/E | 95% интервал O/E (бутстрап по доменам) | p-пер   q')
    for bi, b in enumerate(d_main.brands):
        nsm = sum(n for idx in d_main.mixed for i in idx for bb, n in d_main.recs[i] if bb == bi)
        for l, z in enumerate(ZONES):
            if E[bi][l] <= 0:
                continue
            v = sorted(boot[(bi, l)])
            if len(v) < 50:
                lo = hi = float('nan')
            else:
                lo = v[int(0.025 * len(v))]
                hi = v[int(0.975 * len(v)) - 1]
            star = ''
            if l == 0:
                star = ' | %s %s' % (fp(res_main['pb'][bi]), fp(res_main['q'][bi]))
            mark = '*' if E[bi][l] >= 3 else ' '
            log('%-13s %3d %4d | %-6s | %4.0f %6.1f %5.2f |%s%5.2f .. %5.2f %s' % (
                b if l == 0 else '', d_main.cnt_b[b] if l == 0 else 0, nsm if l == 0 else 0,
                z, O[bi][l], E[bi][l], O[bi][l] / E[bi][l], mark, lo, hi, star))
    log('')

    # ========================================================== 5. мощность
    log('=' * 100)
    log('(5) МОЩНОСТЬ: подсаживаем НАСТОЯЩИЙ эффект «зона выбирает бренд» силы R и смотрим, что скажет тест')
    log('=' * 100)
    log('Генератор альтернативы: внутри каждой смешанной страты события раздаются по слотам доменов')
    log('заново; объёмы доменов, зон, страт и число событий каждого бренда сохранены точно; вес слота')
    log('для бренда = R, если зона слота — «любимая» для этого бренда, иначе 1. Половина брендов тянет')
    log('в .team, половина в .lol — ровно та альтернатива, что описана в гипотезе (Martin/Shuffle в .team,')
    log('Money X/Селектор в .lol). R = 1 — контроль калибровки (эффекта нет).')
    log('Смотрим не только «поймал/не поймал», но и выполнение КРИТЕРИЯ ТЕСТИРОВЩИКА')
    log('(«альтернатива»: глобальный p > 0,2 и ни один бренд не проходит FDR q < 0,05) — если этот')
    log('критерий выполняется и тогда, когда эффект ЕСТЬ, он ничего не различает.')

    def power(des, tag, Rs, nsim, npw, log):
        pref = {bi: (0 if bi % 2 == 0 else 1) for bi in range(des.nb)}
        pool_slots = []
        for idx in des.mixed:
            slots = []
            for i in idx:
                slots.extend([i] * des.tot[i])
            tokens = []
            for i in idx:
                for bi, n in des.recs[i]:
                    tokens.extend([bi] * n)
            pool_slots.append((slots, tokens))

        def simulate(R):
            acc = [collections.Counter() for _ in des.doms]
            for slots, tokens in pool_slots:
                free = slots[:]
                random.shuffle(free)
                toks = tokens[:]
                random.shuffle(toks)
                for bi in toks:
                    pz = pref[bi]
                    tw = 0.0
                    ws = []
                    for i in free:
                        w = R if des.lab0[i] == pz else 1.0
                        ws.append(w)
                        tw += w
                    x = random.random() * tw
                    c = 0.0
                    sel = len(free) - 1
                    for j, w in enumerate(ws):
                        c += w
                        if x <= c:
                            sel = j
                            break
                    acc[free.pop(sel)][bi] += 1
            return [list(a.items()) for a in acc]

        log('')
        log('  Страта: %s — смешанных страт %d, событий в них %d.' % (tag, len(des.mixed), des.mixed_ev))
        log('  Симуляций на R: %d, перестановок в каждой: %d.' % (nsim, npw))
        log('   R  | O/E «любимой» зоны | доля p<0,05 | брендов q<0,10 | клеток x1,4 при E>=3 | ВЫПОЛНЕН КРИТЕРИЙ «опровергнуто»')
        for R in Rs:
            hit = 0
            qn = 0.0
            oe = 0.0
            cells = 0.0
            crit = 0
            for _ in range(nsim):
                recs = simulate(R)
                O1, E1 = des.compute(des.lab0, recs)
                c0, p0 = des.chi(O1, E1)
                ge = 0
                geb = [0] * des.nb
                for _ in range(npw):
                    pl = des.perm_labels(des.lab0)
                    Op, Ep = des.compute(pl, recs)
                    c, pbv = des.chi(Op, Ep)
                    if c >= c0 - 1e-9:
                        ge += 1
                    for bi in range(des.nb):
                        if pbv[bi] >= p0[bi] - 1e-9:
                            geb[bi] += 1
                pglob = (ge + 1.0) / (npw + 1.0)
                if pglob < 0.05:
                    hit += 1
                qs = bh([(g + 1.0) / (npw + 1.0) for g in geb])
                qn += sum(1 for q in qs if q < 0.10)
                if pglob > 0.2 and not any(q < 0.05 for q in qs):
                    crit += 1
                num = den = 0.0
                for bi in range(des.nb):
                    l = pref[bi]
                    if E1[bi][l] > 0:
                        num += O1[bi][l]
                        den += E1[bi][l]
                oe += num / den if den else 0.0
                for bi in range(des.nb):
                    for l in range(des.L):
                        if E1[bi][l] >= 3 and O1[bi][l] / E1[bi][l] >= 1.4:
                            cells += 1
            log('  %3.1f |%18.2f |%11.0f%% |%15.2f |%21.2f | %.0f%% симуляций' % (
                R, oe / nsim, 100.0 * hit / nsim, qn / nsim, cells / nsim, 100.0 * crit / nsim))

    d_day = Design(build(bz, ZONES, zl, lambda r: r['день запуска']), ZONES)
    d_none = Design(build(bz, ZONES, zl, lambda r: 'все'), ZONES)
    power(d_main, 'набор контента + день (ГЛАВНАЯ у тестировщика)', (1.0, 2.0, 3.0, 5.0, 9.0), 200, 300, log)
    power(d_day, 'день запуска (90% событий — максимум информации при контроле дня)', (1.0, 2.0, 3.0, 5.0, 9.0), 100, 200, log)
    power(d_none, 'без страты (все 492 события — верхняя граница того, что вообще можно)', (1.0, 2.0, 3.0, 5.0, 9.0), 80, 150, log)
    log('')
    log('Наблюдённое в данных: хи2 %.1f при %.1f на перестановках, p = %s; клеток x1,4 при E>=3: 0.' % (
        res_main['chi'], res_main['chi_mean'], fp(res_main['p'])))
    log('')
    log('=' * 100)
    log('ИТОГ КОНТРПРОВЕРКИ')
    log('=' * 100)
    log('1. ЭФФЕКТ НЕ ОЖИВАЕТ НИ ПРИ КАКОЙ СТРАТЕ. Жёстче тестировщика: набор+день+блок часа')
    log('   (p = 0,29), набор+день+час (p = 0,36); семейство при день+зона (p = 0,82; между наборами')
    log('   0,95) и день+зона+час (p = 0,92). По кускам: только август p = 0,24, только сентябрь')
    log('   p = 0,39, без «КОНТЕНТ НЕ ЗАПИСАН» p = 0,49, без выбросов 3615/3286.team p = 0,69, без')
    log('   самого тяжёлого пула p = 0,27. Ни знака, ни значимости нигде не появляется. Вердикт')
    log('   «гипотеза не подтверждается» в этом смысле переживает все тени.')
    log('2. НО «ГЛАВНЫЙ» ПРОГОН ТЕСТИРОВЩИКА НИЧЕГО НЕ ДОКАЗЫВАЕТ. Зона почти вложена в партию')
    log('   постановки: 574 из 633 пулов однозонные, 544 из 593 наборов лежат в одной зоне; страта')
    log('   оставляет 30% контраста (инф. вес 32 из 108, 35 из 45 смешанных пулов с весом < 1).')
    log('   Мощность: подсаженный настоящий эффект с O/E 1,14 ловится в 7% случаев, 1,22 — в 16%,')
    log('   1,31 — в 37%; а объявленный самим тестировщиком критерий «опровергнуто» (p > 0,2 и никто')
    log('   не проходит FDR) выполняется в 64% миров с эффектом O/E 1,14, в 42% — с 1,22, в 20% —')
    log('   с 1,31. Фраза «таблица даже ровнее случайной, p = 0,70» — свойство конструкции, а не данных.')
    log('3. РАБОТАЕТ ДРУГОЙ ПРОГОН — наивный, на всех 492 событиях: там эффект с O/E 1,43 ловится в')
    log('   96% случаев (критерий «опровергнуто» выполнился бы лишь в 1% таких миров), с O/E 1,28 — в')
    log('   42%. Он дал p = 0,27. По дню (445 событий): O/E 1,28 ловится в 52%, дало p = 0,39-0,41.')
    log('   Значит исключены КРУПНЫЕ сдвиги (порядка x1,4 сразу у нескольких брендов), а не любые.')
    log('4. ЧТО НЕ ИСКЛЮЧЕНО. Бутстрап по доменам в главной страте: Martin team 1,26 (0,84-1,55),')
    log('   Pinco 1,30 (1,00-1,77), Twin 1,37 (1,00-2,67), Luckybear 1,19 (0,96-1,70) — сдвиг x1,4')
    log('   у отдельного бренда данные не исключают. Фразы «ни одна клетка не сдвинута на x1,4» и')
    log('   «.lol сокращать можно, не теряя своих брендов» из чисел не следуют.')
    log('')
    log('ВЫВОД КОНТРПРОВЕРКИ: результат тестировщика по существу устоял (гипотеза не подтверждается,')
    log('теней не найдено), но обоснование надо переставить — решает наивный прогон и прогон по дню,')
    log('а не стратифицированный; и формулировать надо границей, а не отсутствием.')
    log.close()


if __name__ == '__main__':
    main()
