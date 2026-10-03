# -*- coding: utf-8 -*-
"""Признаки, которые видно глазами, но нет среди девяноста восьми параметров.

Собраны по вычитке четырёх страниц рядом с корпусными. Каждый — то, чем наш
текст на вид отличается от их текста, переведённое в число, чтобы отличие можно
было подтвердить или снять замером, а не впечатлением.

usage: python3 engine/instrumenty/vychitka-priznaki.py <каталог наборов> [метка]
"""
import os, re, sys, glob, statistics as st

ТИПЫ = ['main','obzor','slots','bonus','promo','registracia','vhod','zerkalo','app','news','partnery','info']
ВАЛЕНТНОСТЬ = re.compile(r'^\s*(?:✅|❌)?\s*(плюс|минус|важно|честно|риск|совет|итог)\b[:—-]', re.I)
ТЕМА_МЕТКА = re.compile(r'^\s*[А-ЯЁ][^:.!?]{3,40}:\s+\S')
ЭМОДЗИ = re.compile('[\U0001F000-\U0001FAFF←-⇿☀-➿⬀-⯿️]')
МЫ = re.compile(r'\b(мы|нас|нам|нами|наш\w*)\b', re.I)

def страница(путь):
    s = re.sub(r'(?is)<(script|style)\b.*?</\1>', ' ', open(путь, encoding='utf-8', errors='replace').read())
    чисто = lambda x: re.sub(r'\s+', ' ', re.sub(r'(?s)<[^>]+>', ' ', x)).strip()
    пункты = [чисто(x) for x in re.findall(r'(?is)<li\b[^>]*>(.*?)</li>', s)]
    абзацы = [чисто(x) for x in re.findall(r'(?is)<p\b[^>]*>(.*?)</p>', s)]
    весь = ' '.join(абзацы + пункты + [чисто(x) for x in re.findall(r'(?is)<h[1-6]\b[^>]*>(.*?)</h[1-6]>', s)])
    слов = len(re.findall(r'[А-Яа-яЁёA-Za-z%]+', весь))
    # Абзац до первого h2: у корпуса страница часто открывается вводным абзацем.
    первыйH2 = s.find('<h2')
    зачинДоH2 = 1 if (первыйH2 > 0 and re.search(r'(?is)<p\b', s[:первыйH2])) else 0
    return {
        'эмодзи на страницу': len(ЭМОДЗИ.findall(весь)),
        'страниц с зачином до h2, %': зачинДоH2 * 100.0,
        'пунктов с меткой «плюс/минус», %': (100.0 * sum(1 for п in пункты if ВАЛЕНТНОСТЬ.match(п)) / len(пункты)) if пункты else 0.0,
        'пунктов с тематической меткой, %': (100.0 * sum(1 for п in пункты if ТЕМА_МЕТКА.match(п)) / len(пункты)) if пункты else 0.0,
        '«мы» на 1000 слов': (1000.0 * len(МЫ.findall(весь)) / слов) if слов else 0.0,
        'слов в пункте списка': st.median([len(п.split()) for п in пункты]) if пункты else 0.0,
    }

def набор(д):
    по = {}
    for т in ТИПЫ:
        f = os.path.join(д, т + '.html')
        if os.path.isfile(f):
            for k, v in страница(f).items(): по.setdefault(k, []).append(v)
    return {k: st.median(v) for k, v in по.items()} if по else None

def свод(узор):
    строки = [r for d in sorted(glob.glob(узор)) if os.path.isdir(d) for r in [набор(d)] if r]
    if not строки: return {}, 0
    ключи = list(строки[0])
    из = {}
    for k in ключи:
        v = sorted(r[k] for r in строки)
        n = len(v)
        дец = lambda q: v[0] if n == 1 else v[min(n - 1, max(0, int(round((n - 1) * q))))]
        из[k] = (round(st.median(v), 2), round(дец(.10), 2), round(дец(.90), 2))
    return из, len(строки)

if __name__ == '__main__':
    A, nA = свод(sys.argv[1]); B, nB = свод(sys.argv[2])
    м1 = sys.argv[3] if len(sys.argv) > 3 else 'наши'
    м2 = sys.argv[4] if len(sys.argv) > 4 else 'они'
    print('| параметр | %s (%d) | %s (%d), p10–p90 | отношение | вне полосы |' % (м1, nA, м2, nB))
    print('|---|---|---|---|---|')
    for k in A:
        a, b = A[k], B[k]
        отн = round(a[0] / b[0], 2) if b[0] else ('—' if not a[0] else '∞')
        вне = '⚠' if not (b[1] <= a[0] <= b[2]) else ''
        print('| %s | %s | %s (%s–%s) | %s | %s |' % (k, a[0], b[0], b[1], b[2], отн, вне))
