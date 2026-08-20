import pickle, io, openpyxl, collections
import core
KW=core.KW; BR=core.B["brands"]
# 1) ядро 1570 из выгрузки позиций
wb=openpyxl.load_workbook(io.BytesIO(open("launches2.xlsx",'rb').read()), data_only=True)
rows=list(wb["группа 1"].iter_rows(values_only=True))
coreset={str(r[0]).strip().lower() for r in rows[2:1572] if r[0] not in (None,'')}
print("ключей в ядре:", len(coreset))

tests=["gates of olympus demo","demo gates of olympus","demo slot gates of olympus",
       "slot demo gates of olympus","gates of olympus slot demo",
       "demo slot pragmatic gates of olympus","gates of olympus free demo"]
print("\n-- есть ли эти ключи в ядре 1570? --")
for t in tests:
    print(f"  {t:38s} ядро: {'ДА' if t in coreset else 'нет':3s}  справочник брендов: {'ДА' if t in KW else 'нет'}")

print("\n-- есть ли 'olympus'/'gates' где-либо? --")
inc=[k for k in coreset if 'olymp' in k or 'gates' in k or 'олимп' in k]
print("  в ядре:", inc[:10], "всего", len(inc))
inb=[k for k in KW if 'olymp' in k or 'gates' in k][:10]
print("  в справочнике брендов:", inb, "...")
brands=[b for b,_ in BR.values() if 'olymp' in b.lower() or 'gates' in b.lower()]
print("  бренды со словом olympus/gates:", brands)

print("\n-- язык ядра --")
lat=sum(1 for k in coreset if all(ord(c)<128 for c in k))
print(f"  чисто латиница: {lat} из {len(coreset)} ({lat/len(coreset)*100:.0f}%)")
print("  примеры латинских:", [k for k in coreset if all(ord(c)<128 for c in k)][:6])
print("\n-- есть ли в ядре вообще слово demo/демо? --")
d=[k for k in coreset if 'demo' in k or 'демо' in k]
print(f"  {len(d)} ключей:", d[:10])
