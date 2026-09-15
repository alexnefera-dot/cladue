"""Где вмешиваться: разбор воронки по шагам и потолок каждого вмешательства."""
import re, os, collections

PRICE = {'team':2,'lol':1,'casino':7,'buzz':3}
FD_PAY = 40
WEEK = ['09.09','10.09','11.09','12.09','13.09','14.09','15.09']

z = collections.Counter()
for d in WEEK:
    f = f'analysis/launch_{d}.txt'
    if not os.path.exists(f): continue
    for l in open(f):
        l = l.strip()
        if re.fullmatch(r'[a-z0-9][a-z0-9.-]*\.[a-z]+', l):
            z[l.rsplit('.',1)[1]] += 1

n      = sum(z.values())
spend  = sum(PRICE.get(k,3)*v for k,v in z.items())
FD_W   = 28
income = FD_W*FD_PAY
print(f"=== НЕДЕЛЯ: {n} доменов, расход ${spend}, доход ${income}, итог ${income-spend} ===\n")

# что домен должен отдавать, чтобы окупиться
per_domain = income/n
print(f"домен отдаёт в среднем ${per_domain:.2f}\n")
print(f"{'зона':<8}{'дом':>5}{'цена':>6}{'расход':>8}{'доля расхода':>14}"
      f"{'нужно ФД на 1 дом':>20}{'во сколько раз лучше .team':>28}")
base = PRICE['team']
for k, v in z.most_common():
    p = PRICE.get(k,3)
    need = p/FD_PAY                      # ФД на домен для самоокупаемости
    print(f"{k:<8}{v:>5}{p:>6}{p*v:>8}{100*p*v/spend:>13.1f}%"
          f"{need:>20.3f}{p/base:>28.1f}")

print("\n=== ЕСЛИ УБРАТЬ .casino ===")
z2 = {k:v for k,v in z.items() if k!='casino'}
n2, spend2 = sum(z2.values()), sum(PRICE.get(k,3)*v for k,v in z2.items())
# консервативно: конверсии падают пропорционально числу доменов
fd2 = FD_W * n2/n
print(f"доменов {n2} (-{n-n2}), расход ${spend2} (-${spend-spend2})")
print(f"ФД при пропорциональном падении {fd2:.1f}, доход ${fd2*FD_PAY:.0f}")
print(f"итог ${fd2*FD_PAY-spend2:+.0f}  против ${income-spend:+d} сейчас")
print(f"средняя цена домена ${spend2/n2:.2f} против ${spend/n:.2f}")

print("\n=== ПОТОЛОК ВМЕШАТЕЛЬСТВА В ПАЙПЛАЙН ===")
print(f"сейчас переобход проходят 94%, терминальных отказов 0.75%")
print(f"полное исправление: +6% объёма = +{FD_W*0.06:.1f} ФД/нед = +${FD_W*0.06*FD_PAY:.0f}/нед")
print(f"для сравнения, отказ от .casino: +${(fd2*FD_PAY-spend2)-(income-spend):.0f}/нед")

print("\n=== ЧТО ДАЁТ СДВИГ НА 12 СТРАНИЦ ===")
print("замер по конверсиям (194 события): 0.20 против 0.03 рег/дом/день, 6x, P=0.0002")
print("с поправкой на видимость (рег на 100 ключей в Т10): 4.0 против 2.3, 1.7x")
for mult,label in ((1.7,'осторожно, только эффект видимости'),(6.0,'сырой разрыв')):
    print(f"  при {mult}x на половине объёма: ФД {FD_W:.0f} -> {FD_W*(0.5+0.5*mult):.0f}/нед,"
          f" доход ${FD_W*(0.5+0.5*mult)*FD_PAY:.0f}  ({label})")
