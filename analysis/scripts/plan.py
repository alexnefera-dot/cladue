# Сколько доменов в сутки нужно выкладывать ради заданного числа регистраций.
# Модель: домен приносит Y регистраций за 6 суток жизни; Y разный у разных партий
# (наблюдённый разброс по дням запуска), поэтому считаем не только среднее, но и провалы.
import json,random,statistics as st
random.seed(7)
RAW=[0.684,1.000,0.190,0.321,0.238,0.573]   # Y по дням запуска 21,22,24,25,26,27.08
K=0.420/st.mean(RAW)                        # калибровка на фактическую отдачу 0,42 рег/домен
YDAY=[y*K for y in RAW]
W=[0.18,0.31,0.26,0.15,0.05,0.04]           # прирост регистраций по возрасту 1..6 суток
def sim(N,parts,n=20000):
    out=[]
    for _ in range(n):
        out.append(sum((N/parts)*random.choice(YDAY)*w for w in W for _ in range(parts)))
    out.sort(); return out
ROWS=[]
for N in [40,60,80,100,120,140,160,180,200]:
    for p in (1,3,5):
        r=sim(N,p)
        ROWS.append(dict(n=N,parts=p,med=round(r[len(r)//2]),
            p10=round(r[int(.10*len(r))]),p90=round(r[int(.90*len(r))]),
            hit40=round(100*sum(1 for x in r if x>=40)/len(r)),live=N*6))
W_=json.load(open('wk.json')); W_['plan']=dict(rows=ROWS,Y=0.42,yday=[round(y,3) for y in YDAY],
    curve=W, now=dict(n=39,fact=15.8))
json.dump(W_,open('wk.json','w'),ensure_ascii=False)
for r in ROWS:
    if r['parts']==1: print(r)
