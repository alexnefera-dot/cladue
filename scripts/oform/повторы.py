#!/usr/bin/env python3
"""Снимает удвоенные подряд идущие абзацы: ленты выплат приходят продублированными."""
import os, re, sys

АБЗАЦ = re.compile(r'(?is)<p\b[^>]*>.*?</p>')

def почистить(html: str) -> tuple[str, int]:
    куски = list(АБЗАЦ.finditer(html))
    убрано = 0
    # ищем максимальные цепочки соседних абзацев (между ними только пробелы)
    цепи, текущая = [], []
    for i, m in enumerate(куски):
        if текущая and html[куски[i - 1].end():m.start()].strip() == '':
            текущая.append(m)
        else:
            if len(текущая) > 1: цепи.append(текущая)
            текущая = [m]
    if len(текущая) > 1: цепи.append(текущая)

    ИМЯ = re.compile(r'^[А-ЯЁA-Z][\w-]*(?:\s+[А-ЯЁA-Z][\w-]*)?$')   # «Ольга» — заголовок повторной ленты
    правки = []
    for цепь in цепи:
        тексты = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', m.group(0))).strip() for m in цепь]
        n = len(тексты)
        нашли = True
        while нашли:
            нашли = False
            for k in range(n // 2, 3, -1):              # длина повторяющегося куска
                for a in range(0, n - 2 * k + 1):
                    for b in range(a + k, n - k + 1):
                        if тексты[a:a + k] != тексты[b:b + k]:
                            continue
                        нач = b
                        # имя перед повтором — это его же начало, снимаем вместе с ним
                        if нач > 0 and ИМЯ.match(тексты[нач - 1] or ' ') and тексты[нач - 1] != тексты[a - 1 if a else 0]:
                            нач -= 1
                        правки.append((цепь[нач].start(), цепь[b + k - 1].end()))
                        убрано += b + k - нач
                        del тексты[нач:b + k]; del цепь[нач:b + k]
                        n = len(тексты); нашли = True
                        break
                    if нашли: break
                if нашли: break
    правки.sort()
    for a, b in reversed(правки):
        html = html[:a] + html[b:]
    return html, убрано

if __name__ == '__main__':
    корень = sys.argv[1]
    всего = 0
    for путь, _, файлы in os.walk(корень):
        for f in файлы:
            if not f.endswith('.html'): continue
            p = os.path.join(путь, f)
            s = open(p, encoding='utf-8').read()
            s2, n = почистить(s)
            if n:
                open(p, 'w', encoding='utf-8').write(s2)
                всего += n
    print('снято повторов абзацев:', всего)
