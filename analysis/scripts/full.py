import io, openpyxl, collections, re, json, statistics, pickle
import core
KW=core.KW; EXCL_BRAND=core.EXCL_BRAND
def tier(v): return "ВЧ" if v>=1_000_000 else ("СЧ" if v>=700_000 else "НЧ")
PAT=[("зеркало",r"зеркал|mirror"),("вход",r"\bвход\b|войти|log ?in"),
     ("регистрация",r"регистрац|\bреги\b|sign ?up|создать аккаунт"),
     ("офиц. сайт",r"официальн|\bофиц\b|official"),
     ("бонус/промокод",r"бонус|промокод|промо|фриспин|freespin|бездеп|no ?deposit"),
     ("играть/деньги",r"играть|на деньги|на реальные|игровые автоматы|слоты|игра\b"),
     ("приложение",r"приложени|скачать|apk|андроид|android|\bios\b|мобильн|download|app\b"),
     ("отзывы",r"отзыв|review|развод|вывод"),("личный кабинет",r"кабинет|личный|аккаунт|account|профил"),
     ("бренд + казино",r"казино|casino|kazino")]
def cls(q):
    for n,rx in PAT:
        if re.search(rx,q): return n
    return "бренд без добавок" if len(q.split())<=3 else "прочее"

def blocks(ws):
    rows=list(ws.iter_rows(values_only=True))
    idx=[i for i,r in enumerate(rows) if r[0] and isinstance(r[0],str) and r[0].startswith('Ключ')]
    out=[]
    for j,h in enumerate(idx):
        end=idx[j+1]-1 if j+1<len(idx) else len(rows)
        lbl=rows[h-1][0] if h>0 and rows[h-1][0] and isinstance(rows[h-1][0],str) and 'Снимок' in rows[h-1][0] else None
        if not lbl: continue
        doms=[str(c).strip().lower() for c in rows[h][1:] if c not in (None,'') and str(c).strip().lower()!="базовый домен"]
        data={d:{} for d in doms}
        for r in rows[h+1:end]:
            q=r[0]
            if q in (None,'') or (isinstance(q,str) and ('Снимок' in q or q.startswith('Ключ'))): continue
            q=str(q).strip().lower()
            for i,d in enumerate(doms):
                v=r[1+i]
                if v is None: continue
                try: p=int(v)
                except: continue
                if p>=1: data[d][q]=p
        out.append({"label":lbl.replace('Снимок ','').replace(' XML',''),"doms":doms,"data":data})
    return out

NAME={"группа 3":["Generator_11page","11 стр · генератор","ночь"],
      "группа 1":["7page_yandex","7 стр · из выдачи","ночь"],
      "группа 4":["Generator_11page_2","11 стр · генератор","ночь"],
      "группа 5":["Generator_v5","7 стр · v5 · Theme2","ночь"],
      "группа 6":["Generator_v4_2","7 стр · v4_2 · Theme1","ночь"],
      "группа 2":["generator v4","7 стр · v4","ночь"],
      "12pages_withdate · Theme1":["12pages_withdate · Theme1","12 стр · даты · Theme1","день"],
      "12pages_withdate · Theme2":["12pages_withdate · Theme2","12 стр · даты · Theme2","день"],
      "12pages_nodate":["12pages_nodate","12 стр · без дат · Theme1","день"],
      "7pages_nodate":["7pages_nodate","7 стр · без дат · Theme2","день"],
      "doregn.net 7 page":["kostoreznaya1 · имена","7 стр · именованные","день"],
      "dorgen.net 12 page":["nabor28gotovyi · наборы","12 стр · наборы","день"],
      "Generation 50":["Generation 50","50 доменов · .team","вечер"]}
ORD=["группа 3","группа 1","группа 4","группа 5","группа 6","группа 2",
     "12pages_withdate · Theme1","12pages_withdate · Theme2","12pages_nodate",
     "7pages_nodate","doregn.net 7 page","dorgen.net 12 page","Generation 50"]

wb=openpyxl.load_workbook(io.BytesIO(open("launches4.xlsx",'rb').read()), data_only=True)
G={}
for sn in ORD:
    bs=blocks(wb[sn])
    doms=bs[0]["doms"]
    snaps=[]
    for b in bs:
        per={}
        for d in doms:
            c=collections.Counter(); brs={}; keys=[]
            for q,p in b["data"].get(d,{}).items():
                m=KW.get(q)
                if not m: continue
                br,vol,_=m
                if br in EXCL_BRAND: continue
                t=tier(vol)
                for tp in (3,10,30,50,100):
                    if p<=tp: c[(t,tp)]+=1
                if p<=10:
                    keys.append({"q":q,"b":br,"v":vol,"t":t,"c":cls(q),"p":p})
                    e=brs.setdefault(br,{"b":br,"v":vol,"t":t,"best":999,"n":0,"t3":0})
                    e["best"]=min(e["best"],p); e["n"]+=1
                    if p<=3: e["t3"]+=1
            per[d]={"t3":sum(c[(t,3)] for t in ("ВЧ","СЧ","НЧ")),
                    "t10":sum(c[(t,10)] for t in ("ВЧ","СЧ","НЧ")),
                    "t30":sum(c[(t,30)] for t in ("ВЧ","СЧ","НЧ")),
                    "t100":sum(c[(t,100)] for t in ("ВЧ","СЧ","НЧ")),
                    "vch":c[("ВЧ",10)],"sch":c[("СЧ",10)],"nch":c[("НЧ",10)],
                    "brands":sorted(brs.values(),key=lambda x:(x["best"],-x["v"])),
                    "keys":sorted(keys,key=lambda x:x["p"])}
        snaps.append({"label":b["label"],"per":per})
    G[sn]={"name":NAME[sn][0],"cfg":NAME[sn][1],"wave":NAME[sn][2],"doms":doms,"snaps":snaps}
pickle.dump(G,open("full.pkl","wb"))

T=lambda d: d.endswith(".team")
print("=== ПОСЛЕДНИЙ ЗАМЕР 22:29-22:30 ===")
print(f"{'группа':28s} {'конфигурация':26s} {'n':>2s} {'.tm':>3s} {'Т10/дом':>8s} {'мед':>4s} {'б/лид':>6s} {'ВЧ':>3s} {'СЧ':>3s} {'Т3':>3s} {'нет в Т100':>10s}")
for sn in ORD:
    g=G[sn]; per=g["snaps"][-1]["per"]
    tm=[d for d in g["doms"] if T(d)] or g["doms"]
    v=sorted([per[d]["t10"] for d in tm],reverse=True); n=len(tm)
    S=lambda k,ds=None: sum(per[d][k] for d in (ds or g["doms"]))
    z=sum(1 for d in g["doms"] if per[d]["t100"]==0)
    wo=sum(v[1:])/(n-1) if n>1 else 0
    print(f"{g['name'][:28]:28s} {g['cfg']:26s} {len(g['doms']):2d} {n:3d} {sum(v)/n:8.2f} "
          f"{statistics.median(v):4.0f} {wo:6.2f} {S('vch'):3d} {S('sch'):3d} {S('t3'):3d} {z:5d}/{len(g['doms']):<4}")
