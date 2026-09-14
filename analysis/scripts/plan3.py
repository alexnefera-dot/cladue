# Что вытянет наш объём после запуска сбора: мощность по каждому типу параметра.
import math
from statistics import NormalDist
Z=NormalDist()
DOM_WK=587          # доменов в неделю
SUB=200             # брендов на домен
REG_WK=188          # регистраций в неделю (0.32 на домен)
FD_WK=28            # ФД в неделю
def pw_count(n,m1,m2,od):
    # сравнение двух средних счётчиков, дисперсия = od*среднее
    se=math.sqrt(od*(m1+m2)/n)
    return Z.cdf((abs(m1-m2)-1.959964*se)/se)
def pw_prop(n,p1,p2):
    pb=(p1+p2)/2
    se0=math.sqrt(2*pb*(1-pb)/n); se1=math.sqrt(p1*(1-p1)/n+p2*(1-p2)/n)
    return Z.cdf((abs(p1-p2)-1.959964*se0)/se1)

print("=== СКОЛЬКО ЧЕГО В НЕДЕЛЮ ===")
print(f"доменов {DOM_WK}, поддоменов {DOM_WK*SUB}, регистраций ~{REG_WK}, ФД ~{FD_WK}")
for c2r in (0.05,0.10,0.20):
    cl=REG_WK/c2r
    print(f"  при клик→рег {100*c2r:.0f}%: кликов ~{cl:.0f}/нед, {cl/DOM_WK:.1f} на домен, "
          f"{100*cl/(DOM_WK*SUB):.2f}% на поддомен")

print("\n=== ПАРАМЕТРЫ ДОМЕНА (страниц, контент, зона, предел) ===")
print("вся сотня поддоменов домена делит один и тот же параметр,")
print("поэтому размер выборки = число ДОМЕНОВ, а не поддоменов.")
print(f"{'метрика':<22}{'разница':>9}{'1 нед':>8}{'2 нед':>8}{'4 нед':>8}{'8 нед':>8}")
for c2r,lab in ((0.10,'кликов на домен'),):
    m=REG_WK/c2r/DOM_WK
    for lift in (1.2,1.3,1.5):
        row=[]
        for w in (1,2,4,8):
            n=DOM_WK*w//2
            row.append(f"{100*pw_count(n,m*lift,m,2.0):>7.0f}%")
        print(f"{lab:<22}{lift:>8.1f}x{''.join(row)}")
for lab,base in (('регистраций на домен',REG_WK/DOM_WK),('ФД на домен',FD_WK/DOM_WK)):
    for lift in (1.3,1.5):
        row=[]
        for w in (1,2,4,8):
            n=DOM_WK*w//2
            row.append(f"{100*pw_count(n,base*lift,base,1.6):>7.0f}%")
        print(f"{lab:<22}{lift:>8.1f}x{''.join(row)}")

print("\n=== ПАРАМЕТРЫ ПОДДОМЕНА (волна, бренд, уровень вложенности) ===")
print("различаются ВНУТРИ домена, поэтому выборка = поддомены и клики.")
print(f"{'что':<28}{'разница':>9}{'1 нед':>8}{'2 нед':>8}{'4 нед':>8}")
p_click=REG_WK/0.10/(DOM_WK*SUB)
for lift in (1.1,1.2,1.3):
    row=[]
    for w in (1,2,4):
        n=DOM_WK*SUB*w//2
        row.append(f"{100*pw_prop(n,p_click*lift,p_click):>7.0f}%")
    print(f"{'доля поддоменов с кликом':<28}{lift:>8.1f}x{''.join(row)}")
for lift in (1.2,1.3,1.5):
    row=[]
    for w in (1,2,4):
        nc=REG_WK/0.10*w//2
        row.append(f"{100*pw_prop(int(nc),0.10*lift,0.10):>7.0f}%")
    print(f"{'клик→регистрация':<28}{lift:>8.1f}x{''.join(row)}")

print("\n=== ДЕНЬГИ: когда ФД станут читаемыми ===")
for w in (1,2,4,8,12,26):
    print(f"{w:>3} нед: ФД ~{FD_WK*w:>4}, на ветку {FD_WK*w//2:>4}, "
          f"мощность на 1.5x {100*pw_count(DOM_WK*w//2,FD_WK/DOM_WK*1.5,FD_WK/DOM_WK,1.6):>3.0f}%")
