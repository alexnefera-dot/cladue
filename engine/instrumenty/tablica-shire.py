# -*- coding: utf-8 -*-
"""Широкая сравнительная таблица: все параметры, которые мы когда-либо мерили.

usage: python3 engine/instrumenty/tablica-shire.py <шаблон наших> <шаблон их> [метка1] [метка2]

Собирает в одну таблицу четыре замера: шаблон (zamer-shablona), SEO и лексика
(zamer-seo), бренд-переменные и числа/повторы (sverka-v5.php). Все величины —
медианы по наборам, не по страницам и не пулом.
"""
import os, sys, glob, json, subprocess, statistics as st

КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ИНСТР = os.path.join(КОРЕНЬ, 'engine', 'instrumenty')

def _модуль(имя, обрез):
    """Подключает инструмент, отрезая его собственный CLI-хвост."""
    src = open(os.path.join(ИНСТР, имя), encoding='utf-8').read()
    src = src.split(обрез)[0]
    ns = {'__name__': 'замер'}
    exec(compile(src, имя, 'exec'), ns)
    return ns

ШАБЛОН = _модуль('zamer-shablona.py', 'def svod(dirs)')
СЕО    = _модуль('zamer-seo.py', 'def свод(')
БРЕНД  = _модуль('brend-svod.py', 'def svod(')

СВЕРКА = ['paragraphs','words_per_para','stakes_max','package_uniq','jackpot_uniq',
          'rtp_uniq','rtp_spread','payout_uniq','mantra_max','mantra_total',
          'short_dup_max','fragments']

def сверка(папки):
    """Медианы по страницам для каждого набора: числа площадки и повторы."""
    итог = {}
    for i in range(0, len(папки), 20):
        часть = папки[i:i+20]
        вывод = subprocess.run(['php', 'engine/sverka-v5.php', *часть, '--json'],
                               capture_output=True, text=True, cwd=КОРЕНЬ).stdout
        for набор, v in json.loads(вывод).items():
            стр = v.get('страницы', {})
            if not стр: continue
            строка = {}
            for k in СВЕРКА:
                vals = [p[k] for p in стр.values() if k in p]
                if vals: строка['сверка: ' + k] = st.median(vals)
            строка['сверка: обрывков на набор'] = sum(p.get('fragments', 0) for p in стр.values())
            итог[набор] = строка
    return итог

def собрать(узор):
    папки = [d for d in sorted(glob.glob(узор)) if os.path.isdir(d)]
    св = сверка(папки)
    строки = []
    for d in папки:
        r = {}
        for замер, префикс in ((ШАБЛОН['nabor'], ''), (СЕО['набор'], ''), (БРЕНД['nabor'], '')):
            часть = замер(d)
            if часть:
                for k, v in часть.items():
                    r.setdefault(префикс + k, v)
        r.update(св.get(os.path.basename(d), {}))
        if r: строки.append(r)
    return строки

def полоса(v):
    """Децили: у чужого корпуса min–max растянут сломанными наборами."""
    v = sorted(v)
    if len(v) < 5: return v[0], v[-1]
    def q(p):
        i = p * (len(v) - 1)
        lo, hi = int(i), min(int(i) + 1, len(v) - 1)
        return v[lo] + (v[hi] - v[lo]) * (i - lo)
    return q(0.1), q(0.9)

def свод(строки):
    ключи = []
    for r in строки:
        for k in r:
            if k not in ключи: ключи.append(k)
    out = {}
    for k in ключи:
        v = [r[k] for r in строки if k in r]
        if not v: continue
        н, в = полоса(v)
        out[k] = (round(st.median(v), 2), round(н, 2), round(в, 2))
    return out

if __name__ == '__main__':
    A = свод(собрать(sys.argv[1])); B = свод(собрать(sys.argv[2]))
    м1 = sys.argv[3] if len(sys.argv) > 3 else 'наши'
    м2 = sys.argv[4] if len(sys.argv) > 4 else 'их'
    print('| параметр | %s: медиана | %s: полоса | %s: медиана | %s: полоса (p10–p90) | отношение | вне полосы |'
          % (м1, м1, м2, м2))
    print('|---|---|---|---|---|---|---|')
    for k in A:
        if k not in B: continue
        a, b = A[k], B[k]
        отн = round(a[0] / b[0], 2) if b[0] else ('—' if not a[0] else '∞')
        вне = '⚠' if not (b[1] <= a[0] <= b[2]) else ''
        print('| %s | %s | %s–%s | %s | %s–%s | %s | %s |' % (k, a[0], a[1], a[2], b[0], b[1], b[2], отн, вне))
