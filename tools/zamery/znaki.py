"""Проверка страниц на посторонние знаки.

Разрешены кириллица, латиница, цифры, типографика, валюта и эмодзи;
всё прочее — повод посмотреть глазами.
"""
import io
import glob
import unicodedata

RAZRESHENO = ('LATIN', 'CYRILLIC', 'DIGIT', 'SPACE', 'QUOTATION', 'DASH',
              'HYPHEN', 'RUBLE', 'EURO', 'DOLLAR', 'NUMERO', 'PERCENT',
              'MULTIPLICATION', 'ELLIPSIS', 'BULLET', 'DOT', 'EMOJI')

bad = 0
for f in sorted(glob.glob('samples/v6/*/*.html')):
    s = io.open(f, encoding='utf-8').read()
    plohie = set()
    for c in s:
        if c.isascii() or c.isspace():
            continue
        try:
            imya = unicodedata.name(c)
        except ValueError:
            plohie.add(c)
            continue
        if not any(k in imya for k in RAZRESHENO) and ord(c) < 0x1F000:
            plohie.add(c)
    if plohie:
        print(f, sorted(plohie))
        bad += 1
print('файлов с посторонними знаками:', bad)
