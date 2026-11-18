#!/usr/bin/env python3
"""Разбор чека Spaceship (PDF) и сверка с выданной партией.

  python3 reconcile.py чек.pdf batches/lol-150-2026-11-18

Печатает чистый список доменов из чека в исходном порядке, затем — какие
имена из партии в чек не попали. Второй аргумент необязателен: без него
просто печатается список из чека.
"""
import re, sys, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
pdf = sys.argv[1]
pool_files = sys.argv[2:]

raw = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'extract_pdf.py'), pdf],
                     capture_output=True, text=True, cwd=HERE)
if raw.returncode:
    sys.exit(raw.stderr or 'не удалось разобрать PDF')
s = open(os.path.join(HERE, 'raw.txt')).read()

used_path = os.path.join(HERE, 'USED.txt')
known = set(open(used_path).read().split()) if os.path.exists(used_path) else set()

pool = {}
for f in pool_files:
    for x in open(f).read().split():
        pool[x.rsplit('.', 1)[0]] = x

doms = re.findall(r'[a-z0-9][a-z0-9-]{0,40}\.(?:team|lol|casino|buzz)\b', s)

# в чеке к имени домена иногда приклеивается колонка с ценой — срезаем 1..4 символа
fixed = []
for d in doms:
    if d.rsplit('.', 1)[0] in known:
        fixed.append(d); continue
    cand = None
    for k in (1, 2, 3, 4):
        if d[k:].rsplit('.', 1)[0] in known:
            cand = d[k:]; break
    fixed.append(cand or d)

got = set(fixed)
missing = [v for v in pool.values() if v not in got]

# обрезанные имена восстанавливаем по совпадению окончания с ещё не найденными
res = []
for d in fixed:
    base, tld = d.rsplit('.', 1)
    if base in known:
        res.append(d); continue
    cands = [m for m in missing
             if m.endswith('.' + tld) and m.rsplit('.', 1)[0].endswith(base)]
    if len(cands) == 1:
        res.append(cands[0]); missing.remove(cands[0])
    else:
        res.append(d + f'   <-- не распознано, варианты: {cands}')

print('всего в чеке:', len(res))
print('\n'.join(res))
if pool_files:
    print('\n--- не попали в чек:', len(missing))
    print(' '.join(sorted(missing)))
