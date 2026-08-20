import pickle, collections
snaps=pickle.load(open("snaps2.pkl","rb"))
bs=snaps["группа 3"]; b1,b2,b3=bs
diff=[]; stats=collections.Counter()
for d in b3["doms"]:
    for q,p3 in b3["data"][d].items():
        p1=b1["data"].get(d,{}).get(q); p2=b2["data"].get(d,{}).get(q)
        if p1 is None and p2 is None: stats["только в b3"]+=1
        elif p3==p2 and p2 is not None: stats["= b2"]+=1
        elif p3==p1 and p1 is not None: stats["= b1"]+=1
        else: stats["другое"]+=1; diff.append((d,q,p1,p2,p3))
print(stats)
print("\nпримеры расхождений:")
for d,q,p1,p2,p3 in diff[:12]: print(f"  {d:12s} {q[:34]:34s} b1={p1} b2={p2} b3={p3}")
print("\nпримеры 'только в b3':")
n=0
for d in b3["doms"]:
    for q,p3 in b3["data"][d].items():
        if b1["data"].get(d,{}).get(q) is None and b2["data"].get(d,{}).get(q) is None:
            print(f"  {d:12s} {q[:34]:34s} b3={p3}"); n+=1
            if n>=6: break
    if n>=6: break
