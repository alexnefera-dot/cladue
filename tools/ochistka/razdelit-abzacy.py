# -*- coding: utf-8 -*-
"""Разделить выбранные абзацы по первой границе предложения, сохраняя разметку."""
import re, io, sys

def razdelit(put, nomera):
    s = io.open(put, encoding='utf-8').read()
    bloki = list(re.finditer(r'<p>(.*?)</p>', s, re.S))
    dlinnye = [m for m in bloki if len(re.sub(r'<[^>]+>', '', m.group(1)).strip()) > 40]
    sdvig = 0
    sdelano = 0
    for i in sorted(nomera):
        if i >= len(dlinnye):
            continue
        m = dlinnye[i]
        nutro = m.group(1)
        # первая точка вне тега, после которой идёт пробел и заглавная
        kand = [k.start() for k in re.finditer(r'(?<![.])[.!?](?=\s+[А-ЯЁ])', nutro)
                if nutro.count('<', 0, k.start()) == nutro.count('>', 0, k.start())]
        if not kand:
            continue
        r = kand[0] + 1
        levo, pravo = nutro[:r].strip(), nutro[r:].strip()
        if not pravo:
            continue
        # незакрытый <strong> в левой половине закрываем, в правой открываем
        if levo.count('<strong>') > levo.count('</strong>'):
            levo += '</strong>'
            pravo = '<strong>' + pravo
        novo = '<p>' + levo + '</p>\n<p>' + pravo + '</p>'
        a, b = m.start() + sdvig, m.end() + sdvig
        s = s[:a] + novo + s[b:]
        sdvig += len(novo) - (b - a)
        sdelano += 1
    io.open(put, 'w', encoding='utf-8').write(s)
    return sdelano

if __name__ == '__main__':
    put = sys.argv[1]
    nomera = [int(x) for x in sys.argv[2].split(',')]
    print(f"  {put.split('/')[-2]}/{put.split('/')[-1]}: разделено {razdelit(put, nomera)}")
