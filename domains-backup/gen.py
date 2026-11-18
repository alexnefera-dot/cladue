#!/usr/bin/env python3
"""Генератор коротких доменов. Все имена 4 символа, без слова casino.

  python3 gen.py 150 lol          -> 150 имён .lol, файл batches/<tld>-<N>-<дата>
  python3 gen.py 100 team         -> 100 имён .team

Уникальность обеспечивается реестром USED.txt (имена без TLD, по одному в строке).
Новые имена дописываются в USED.txt автоматически.
"""
import random, sys, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
USED = os.path.join(HERE, 'USED.txt')

n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
tld = sys.argv[2].lstrip('.') if len(sys.argv) > 2 else 'lol'

used = set(open(USED).read().split()) if os.path.exists(USED) else set()
seen = set()
digits = '0123456789'
letters = 'abcdefghijklmnopqrstuvwxyz'

def name():
    while True:
        r = random.random()
        if r < 0.60:
            s = ''.join(random.choice(digits) for _ in range(4))
        elif r < 0.85:
            s = ''.join(random.choice(letters) for _ in range(4))
        else:
            s = ''.join(random.choice(letters) if i % 2 == 0 else random.choice(digits)
                        for i in range(4))
        if s in used or s in seen:
            continue
        seen.add(s)
        return s

names = [name() for _ in range(n)]
os.makedirs(os.path.join(HERE, 'batches'), exist_ok=True)
stamp = datetime.date.today().isoformat()
out = os.path.join(HERE, 'batches', f'{tld}-{n}-{stamp}')
with open(out, 'w') as f:
    f.write('\n'.join(s + '.' + tld for s in names) + '\n')
with open(USED, 'a') as f:
    f.write('\n'.join(sorted(seen)) + '\n')
print('\n'.join(s + '.' + tld for s in names))
print(f'\n-- {n} шт. записано в {out}', file=sys.stderr)
