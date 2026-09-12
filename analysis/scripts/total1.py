# Сводный сценарный расчёт: что даёт каждое решение и все вместе.
nD=559; DEPV=40.0
dep=27; reg=179; cost=1238.0
base_rev=dep*DEPV/nD          # $1.93 на домен
r2d=dep/reg                   # рег -> деп
vch=54/(50*nD)*r2d*DEPV       # $ на домен за один бренд ВЧ
nch=62/(92*nD)*r2d*DEPV
lol_rate=3/110                # факт. ставка деп/домен в .lol
lol_rev=lol_rate*DEPV
print(f"выручка/домен сейчас  ${base_rev:.2f}   средняя цена ${cost/nD:.2f}   ROI {base_rev/(cost/nD):.2f}x")
print(f"один бренд ВЧ: +${vch:.4f}/домен   НЧ: +${nch:.4f}/домен")
print(f"факт. выручка .lol: ${lol_rev:.2f}/домен (3 деп на 110 доменов)\n")
SC=[
 ('как есть (микс зон, 200 брендов)', cost/nD, base_rev),
 ('только .lol, зона не влияет',      1.0,     base_rev),
 ('только .lol, факт. ставка .lol',   1.0,     lol_rev),
 ('.lol + 50 ВЧ, зона не влияет',     1.0,     base_rev+50*vch),
 ('.lol + 50 ВЧ, факт. ставка .lol',  1.0,     lol_rev*(base_rev+50*vch)/base_rev),
 ('.lol + 100 ВЧ, зона не влияет',    1.0,     base_rev+100*vch),
 ('.lol + 100 ВЧ, факт. ставка .lol', 1.0,     lol_rev*(base_rev+100*vch)/base_rev),
]
print(f"{'сценарий':<36}{'цена$':>7}{'выручка$':>10}{'итог/дом':>10}{'ROI':>8}")
for lab,c,r in SC:
    print(f"{lab:<36}{c:>7.2f}{r:>10.2f}{r-c:>+10.2f}{r/c:>7.2f}x")
lo=min(r/c for lab,c,r in SC if '.lol + 50' in lab)
hi=max(r/c for lab,c,r in SC if '.lol + 50' in lab)
print(f"\nдиапазон для '.lol + 50 ВЧ': {lo:.2f}x – {hi:.2f}x против 0.87x сегодня")
print("оба конца диапазона положительны")
print(f"\nна недельном объёме (587 доменов) это разница в деньгах:")
for lab,c,r in SC:
    print(f"  {lab:<36} итог ${(r-c)*587:>+8.0f} в неделю")
