# Сроки выводов, если мерить конверсиями, а не кликами.
import math
from statistics import NormalDist
Z=NormalDist()
BASES=587; SUB_PER=186; SUBS=BASES*SUB_PER
REG=190; FD=28
def pw_prop(n,p,lift):
    p1,p2=p*lift,p; pb=(p1+p2)/2
    se0=math.sqrt(2*pb*(1-pb)/n); se1=math.sqrt(p1*(1-p1)/n+p2*(1-p2)/n)
    return Z.cdf((abs(p1-p2)-1.959964*se0)/se1)
def pw_cnt(n,m,lift,od=1.6):
    se=math.sqrt(od*(m*lift+m)/n)
    return Z.cdf((abs(m*lift-m)-1.959964*se)/se)

print("=== A. ЧТО ПРИНОСИТ КОНВЕРСИИ — параметры УРОВНЯ БАЗЫ ===")
print("выборка = базы, 587 в неделю\n")
print(f"{'метрика':<22}{'разница':>9}{'1 нед':>8}{'2 нед':>8}{'4 нед':>8}{'8 нед':>8}{'12 нед':>8}")
for lab,tot in (('регистраций на базу',REG),('ФД на базу',FD)):
    m=tot/BASES
    for lift in (1.3,1.5,2.0):
        row="".join(f"{100*pw_cnt(BASES*w//2,m,lift):>7.0f}%" for w in (1,2,4,8,12))
        print(f"{lab:<22}{lift:>8.1f}x{row}")

print("\n=== A. параметры УРОВНЯ САБДОМЕНА (волна, уровень, бренд) ===")
print("выборка = сабдомены, различаются внутри базы\n")
p=REG/SUBS
print(f"ставка регистраций на сабдомен {100*p:.4f}%")
print(f"{'метрика':<22}{'разница':>9}{'1 нед':>8}{'2 нед':>8}{'4 нед':>8}{'8 нед':>8}")
for lift in (1.2,1.3,1.5):
    row="".join(f"{100*pw_prop(SUBS*w//2,p,lift):>7.0f}%" for w in (1,2,4,8))
    print(f"{'доля с регистрацией':<22}{lift:>8.1f}x{row}")

print("\n=== A. СВЯЗКИ: сколько ячеек выдержит конверсионная метрика ===")
print(f"{'глубина':<12}{'ячеек':>7}{'рег/ячейку/нед':>16}{'рег/ячейку/мес':>16}{'вывод'}")
for k,cells in ((1,3),(2,12),(3,36)):
    wk=REG/cells; mo=REG*4/cells
    v = 'читается за месяц' if mo>=60 else ('только накопительно' if mo>=25 else 'нечитаемо')
    print(f"{k:<12}{cells:>7}{wk:>16.0f}{mo:>16.0f}   {v}")

print("\n=== B. ПОЧЕМУ НЕ ЗАШЛО — статистика не нужна, это деление ===")
subs = 306_000
done  = 289_000                       # yandex_pipeline_stage = done
term  = {'ждут квоту':840,'ошибка пайплайна':448,
         'верификация FAILED':554,'исчерпали 3/3 попыток':439}
recrawled_pct = 95.0                  # yandex_webmaster_recrawled ~95%
added_pct     = 96.0                  # yandex_webmaster_added     ~96%

term_sum = sum(term.values())
tail     = subs - done - term_sum     # verify/recrawl/meta хвост: в полёте или залип
print(f"всего сабдоменов в снимке {subs}")
print(f"  {'дошли до done':<26}{done:>8}   {100*done/subs:>7.3f}%")
for k,v in term.items():
    print(f"  {k:<26}{v:>8}   {100*v/subs:>7.3f}%")
print(f"  {'хвост verify/recrawl/meta':<26}{tail:>8}   {100*tail/subs:>7.3f}%")
print(f"\nтерминальные отказы в БД: {term_sum} = {100*term_sum/subs:.2f}%")
print(f"переобход реально ушёл:   {recrawled_pct:.0f}%  (added {added_pct:.0f}%)")
print(f"значит до переобхода не дошли ~{100-recrawled_pct:.0f}% ≈ {int(subs*(100-recrawled_pct)/100):,} сабдоменов,")
print( "и это хвост, а не явная ошибка: в БД он не помечен как отказ.")
print("\nвывод: жёстких отказов меньше процента, тихого хвоста ~5%,")
print("а остальные 94% переобход прошли успешно. Значит 'не зашло в индекс'")
print("для подавляющего большинства происходит ПОСЛЕ успешного переобхода")
print("и в статусе БД не видно вообще — ловится только отсутствием обращений")
print("робота и отсутствием кликов с яндексовым реферером.")
