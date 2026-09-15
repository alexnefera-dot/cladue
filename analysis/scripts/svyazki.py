# Сколько связок параметров различимо при нашем объёме.
import math, itertools
from statistics import NormalDist
Z=NormalDist()
BASES_WK=587; SUBS_PER_BASE=186; SUBS_WK=BASES_WK*SUBS_PER_BASE
P_SEARCH=0.016      # доля сабдоменов, вышедших в поиск (оценка)
def pw_prop(n,p1,p2):
    pb=(p1+p2)/2
    se0=math.sqrt(2*pb*(1-pb)/n); se1=math.sqrt(p1*(1-p1)/n+p2*(1-p2)/n)
    return Z.cdf((abs(p1-p2)-1.959964*se0)/se1)

DIM = [('пак', 3, 'база'), ('оформление', 3, 'база'), ('зона', 4, 'база'),
       ('возраст YA', 2, 'база'), ('волна', 2, 'сабдомен'), ('уровень в выдаче', 4, 'сабдомен')]
print(f"объём: {BASES_WK} баз и {SUBS_WK} сабдоменов в неделю\n")
print("=== СКОЛЬКО ЯЧЕЕК ДАЁТ СВЯЗКА И СКОЛЬКО В НЕЙ НАБЛЮДЕНИЙ ===")
print(f"{'связка из':<44}{'ячеек':>7}{'баз/ячейку':>12}{'сабдом/ячейку':>15}{'мощность 1.3x':>15}")
for k in (1,2,3,4):
    best=None
    for combo in itertools.combinations(DIM,k):
        cells=1
        for _,n,_ in combo: cells*=n
        bpc=BASES_WK/cells; spc=SUBS_WK/cells
        pw=pw_prop(spc, P_SEARCH*1.3, P_SEARCH)
        name=' × '.join(c[0] for c in combo)
        if best is None or cells>best[1]: pass
        print(f"{name[:42]:<44}{cells:>7}{bpc:>12.0f}{spc:>15.0f}{100*pw:>14.0f}%")
    print()
