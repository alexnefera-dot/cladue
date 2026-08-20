import pickle
snaps=pickle.load(open("snaps2.pkl","rb"))
for sn,bs in snaps.items():
    b1,b2,b3=bs[0],bs[1],bs[2]
    # union of b1,b2 with b2 winning
    u={}
    for d in b3["doms"]:
        m=dict(b1["data"].get(d,{})); m.update(b2["data"].get(d,{}))
        u[d]=m
    nu=sum(len(v) for v in u.values())
    same=all(u[d]==b3["data"][d] for d in b3["doms"])
    # also test b1-wins union
    u2={}
    for d in b3["doms"]:
        m=dict(b2["data"].get(d,{})); m.update(b1["data"].get(d,{}))
        u2[d]=m
    same2=all(u2[d]==b3["data"][d] for d in b3["doms"])
    # best position wins
    u3={}
    for d in b3["doms"]:
        m=dict(b1["data"].get(d,{}))
        for q,p in b2["data"].get(d,{}).items(): m[q]=min(m.get(q,999),p)
        u3[d]=m
    same3=all(u3[d]==b3["data"][d] for d in b3["doms"])
    print(f"{sn}: b3={b3['npos']} union={nu} | b2-wins:{same} b1-wins:{same2} best-wins:{same3}")
