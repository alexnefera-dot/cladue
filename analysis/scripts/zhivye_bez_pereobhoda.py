import collections, glob, os

ZONY = {'lol', 'team', 'buzz', 'casino'}
VLAD = [('tracker_clicks_2026-10-11_2026-10-21.jsonl','2026-10-11','2026-10-21'),
        ('tracker_clicks_2026-10-22_2026-10-23.jsonl','2026-10-22','2026-10-23'),
        ('tracker_clicks_2026-10-24_2026-10-24.jsonl','2026-10-24','2026-10-24'),
        ('tracker_clicks_2026-10-25_2026-10-30.jsonl','2026-10-25','2026-10-30'),
        ('tracker_clicks_2026-10-31_2026-11-09.jsonl','2026-10-31','2026-11-07'),
        ('tracker_clicks_2026-11-08_2026-11-09.jsonl','2026-11-08','2026-11-09'),
        ('tracker_clicks_2026-11-10_2026-11-10.jsonl','2026-11-10','2026-11-10'),
        ('tracker_clicks_2026-11-11_2026-11-12.jsonl','2026-11-11','2026-11-11'),
        ('tracker_clicks_2026-11-12_2026-11-16.jsonl','2026-11-12','2026-11-16')]


def pole(ln, imya):
    k = ln.find('"' + imya + '":')
    if k < 0: return ''
    j = k + len(imya) + 3
    while j < len(ln) and ln[j] == ' ': j += 1
    if ln[j:j+1] == '"': return ln[j+1:ln.find('"', j+1)]
    return ln[j:min(x for x in (ln.find(',', j), ln.find('}', j), len(ln)) if x > 0)].strip()


rec, baza_rec, baza_sozd = {}, collections.Counter(), {}
for put in sorted(glob.glob('api/dorgen_subdomains_*.jsonl')):
    if not os.path.getsize(put): continue
    for ln in open(put):
        s = pole(ln, 'subdomain')
        if not s: continue
        b = pole(ln, 'recrawl_sent_at')[:1].isdigit()
        if s not in rec or b: rec[s] = b
        bd = pole(ln, 'content_domain_url')
        if b: baza_rec[bd] += 1
        d = pole(ln, 'domain_created')[:10]
        if bd and d[:1].isdigit(): baza_sozd[bd] = min(baza_sozd.get(bd, '9999'), d)

zh = collections.Counter(); dni = collections.defaultdict(set)
for f, o, d in VLAD:
    put = 'api/' + f
    if not os.path.exists(put): continue
    for ln in open(put):
        k = ln.find('"subdomain": "')
        if k < 0 or '"is_bot": true' in ln: continue
        dt = ln[8:18]
        if not (o <= dt <= d): continue
        s = ln[k+14:ln.find('"', k+14)]
        if rec.get(s, True): continue          # нужны только без переобхода
        rk = ln.find('"referer": "')
        if rk < 0 or 'yandex.' not in ln[rk+12:ln.find('"', rk+12)]: continue
        zh[s] += 1; dni[s].add(dt)

print(f'{"сайт":<32} {"база":<14} {"создана":<12} {"переобх. на базе":>17} {"живых":>6} {"дней":>5}')
for s, n in zh.most_common():
    b = '.'.join(s.split('.')[-2:])
    print(f'{s:<32} {b:<14} {baza_sozd.get(b, "—"):<12} {baza_rec.get(b, 0):>17} {n:>6} {len(dni[s]):>5}')
print()
print('сайтов:', len(zh), ' живых кликов:', sum(zh.values()))
sb = collections.Counter('.'.join(s.split('.')[-2:]) for s in zh)
print('баз:', len(sb))
bezrec = [b for b in sb if baza_rec.get(b, 0) == 0]
print('из них баз, где переобхода не было вообще ни на одном сайте:', len(bezrec), bezrec[:12])
