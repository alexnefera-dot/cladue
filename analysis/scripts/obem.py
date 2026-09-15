"""Сроки как функция объёма запусков. Ставка конверсии на сабдомен держится."""
import math
from statistics import NormalDist
N=NormalDist()
SUBS=186
RATE_REG=190/(82*7*SUBS)     # регистраций на сабдомен, по текущему замеру
RATE_FD =28 /(82*7*SUBS)

def power(p0,OR,n,alpha=.05):
    p1=OR*p0/(1-p0+OR*p0)
    if n*p0<5: return None
    se0=math.sqrt(p0*(1-p0)/n); se1=math.sqrt(p1*(1-p1)/n)
    z=N.inv_cdf(1-alpha/2)
    return 1-N.cdf((z*se0-abs(p1-p0))/se1)+N.cdf((-z*se0-abs(p1-p0))/se1)

def weeks_to(p0,OR,reg_week,target=.80,cap=52):
    for w in range(1,cap+1):
        p=power(p0,OR,int(reg_week*w))
        if p and p>=target: return w
    return None

print(f"ставка: {100*RATE_REG:.4f}% регистраций на сабдомен\n")
print(f"{'запусков/сут':>13}{'сабдом/нед':>12}{'рег/нед':>9}{'ФД/нед':>8}"
      f"{'1 парам 1.3x':>14}{'пара 1.5x':>11}{'тройка 2.0x':>13}")
for L in (50,82,150,200,300):
    subs=L*7*SUBS; reg=subs*RATE_REG; fd=subs*RATE_FD
    a=weeks_to(1/3, 1.3, reg); b=weeks_to(1/12,1.5,reg); c=weeks_to(1/36,2.0,reg)
    f=lambda w: f"{w} нед" if w else ">год"
    print(f"{L:>13}{subs:>12,}{reg:>9.0f}{fd:>8.1f}{f(a):>14}{f(b):>11}{f(c):>13}")

print("\n=== контент при ротации имён ===")
print("если имена меняются, на каждое копится столько, сколько оно в обороте")
for L in (82,200):
    reg=L*7*SUBS*RATE_REG
    for names in (140,):
        for weeks_live in (2,4,8):
            per=reg*weeks_live/names
            print(f"  {L:>3} зап/сут, {names} имён, имя живёт {weeks_live} нед -> "
                  f"{per:.1f} конверсий на имя")
print("\nтест на уровне одного имени недостижим при любой ротации.")
print("Имя ранжируется; переносимый вывод даёт группировка постфактум.")
