import json, re, sys
pat = re.compile(r'\b([a-z0-9][a-z0-9-]{1,40})\.(lol|team|casino|buzz)\b')
found = set()
def walk(o):
    if isinstance(o, str):
        for m in pat.finditer(o):
            found.add((m.group(1), m.group(2)))
    elif isinstance(o, dict):
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
for line in open(sys.argv[1], errors='replace'):
    line = line.strip()
    if not line: continue
    try: walk(json.loads(line))
    except Exception: pass
full = sorted(f'{n}.{t}' for n, t in found)
open('full.txt','w').write('\n'.join(full) + '\n')
names = sorted({n for n, t in found})
open('names.txt','w').write('\n'.join(names) + '\n')
from collections import Counter
print('полных доменов:', len(full), '| уникальных имён:', len(names))
print('по зонам:', dict(Counter(t for _, t in found)))
print('длина имени:', dict(sorted(Counter(len(n) for n in names).items())))
print('начинаются с n:', sum(1 for n in names if n.startswith('n')))
