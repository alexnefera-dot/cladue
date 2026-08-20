import io, openpyxl, hashlib, pickle, collections, re, json
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
        doms=[str(c).strip().lower() for c in rows[h][1:] if c not in (None,'')]
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
        out.append({"label":lbl,"doms":doms,"data":data})
    return [b for b in out if b["label"]]   # только помеченные снимки

wb=openpyxl.load_workbook(io.BytesIO(open("launches3.xlsx",'rb').read()), data_only=True)
NEW=["12pages_withdate · Theme2","12pages_withdate · Theme1","12pages_nodate",
     "7pages_nodate","doregn.net 7 page","dorgen.net 12 page"]
NAME={"doregn.net 7 page":"kostoreznaya1 · имена 7стр","dorgen.net 12 page":"nabor28gotovyi · набор 12стр"}
CFG={"12pages_withdate · Theme2":"12 стр · даты · Theme2",
     "12pages_withdate · Theme1":"12 стр · даты · Theme1",
     "12pages_nodate":"12 стр · без дат · Theme1",
     "7pages_nodate":"7 стр · без дат · Theme2 · проба зон",
     "doregn.net 7 page":"7 стр · именованные контенты",
     "dorgen.net 12 page":"12 стр · наборы"}
res={}
for sn in NEW:
    bs=blocks(wb[sn]); assert len(bs)==1, (sn,len(bs))
    b=bs[0]; per={}
    for d in b["doms"]:
        c=collections.Counter(); brs={}; keys=[]
        for q,p in b["data"][d].items():
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
        per[d]={"t10":sum(c[(t,10)] for t in ("ВЧ","СЧ","НЧ")),
                "t30":sum(c[(t,30)] for t in ("ВЧ","СЧ","НЧ")),
                "t100":sum(c[(t,100)] for t in ("ВЧ","СЧ","НЧ")),
                "t3":sum(c[(t,3)] for t in ("ВЧ","СЧ","НЧ")),
                "vch":c[("ВЧ",10)],"sch":c[("СЧ",10)],"nch":c[("НЧ",10)],
                "brands":sorted(brs.values(),key=lambda x:(x["best"],-x["v"])),
                "keys":sorted(keys,key=lambda x:x["p"])}
    res[sn]={"label":b["label"].replace('Снимок ','').replace(' XML',''),
             "name":NAME.get(sn,sn),"cfg":CFG[sn],"per":per,"doms":b["doms"]}
pickle.dump(res,open("m3res.pkl","wb"))

print("=== ЗАМЕР 1 · 20.08 17:34-17:35 (запуски созданы в 17:21-17:22) ===")
print(f"{'группа':30s} {'конф':32s} {'n':>2s} {'Т10/дом':>8s} {'Т30/дом':>8s} {'Т100/дом':>9s} {'ВЧ':>3s} {'СЧ':>3s} {'Т3':>3s} {'пусто':>6s}")
for sn in NEW:
    r=res[sn]; per=r["per"]; n=len(per)
    S=lambda k: sum(v[k] for v in per.values())
    z=sum(1 for v in per.values() if v["t30"]==0)
    print(f"{r['name'][:30]:30s} {r['cfg']:32s} {n:2d} {S('t10')/n:8.1f} {S('t30')/n:8.1f} "
          f"{S('t100')/n:9.1f} {S('vch'):3d} {S('sch'):3d} {S('t3'):3d} {z}/{n:>3}")
