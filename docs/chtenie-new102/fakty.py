# -*- coding: utf-8 -*-
"""Формула раздела: роли блоков и согласованность фактов внутри раздела (h2-блока).
Использование: python3 fakty.py <корпус=путь> ... ; печатает сводку по корпусам."""
import sys, os, re, glob, json, statistics as st
from html.parser import HTMLParser
from collections import Counter, defaultdict

NAMES = set('''Александр Алексей Анатолий Андрей Антон Аркадий Арсений Артём Артем Артур Борис Вадим Валентин Валерий Василий Виктор Виталий Владимир Владислав Всеволод Вячеслав Геннадий Георгий Герман Глеб Григорий Даниил Данил Данила Денис Дмитрий Евгений Егор Захар Иван Игнат Игорь Илья Кирилл Константин Лев Леонид Макар Максим Марат Марк Матвей Михаил Никита Николай Олег Павел Пётр Петр Роман Ростислав Руслан Савелий Семён Семен Сергей Станислав Степан Тимофей Тимур Фёдор Федор Филипп Эдуард Юрий Ярослав Яков Ян
Александра Алина Алиса Алла Анастасия Ангелина Анна Антонина Арина Валентина Валерия Варвара Вера Вероника Виктория Галина Дарья Диана Ева Евгения Екатерина Елена Елизавета Жанна Зоя Инна Ирина Карина Кира Кристина Ксения Лариса Лидия Лилия Любовь Людмила Маргарита Марина Мария Марья Милана Надежда Наталья Наталия Нина Оксана Олеся Ольга Полина Раиса Регина Светлана Снежана София Софья Таисия Тамара Татьяна Ульяна Юлия Яна'''.split())
NAME_RE = re.compile(r'(?<![А-ЯЁа-яё-])(' + '|'.join(sorted(NAMES, key=len, reverse=True)) + r')(?:а|у|е|ом|ем|ой|ей|ы|и|ю|я)?(?![А-ЯЁа-яё])')

def facts(t):
    f = defaultdict(set)
    for m in re.finditer(r'(\d{2}[.,]\d{1,2})\s*%', t): f['rtp'].add(m.group(1).replace(',', '.'))
    for m in re.finditer(r'(?<![\d.,])(\d{2,4})\s*%', t): f['проц'].add(m.group(1))
    for m in re.finditer(r'(\d+(?:[.,]\d+)?)\s*млн', t):
        pre = t[max(0, m.start()-40):m.start()].lower()
        (f['джекпот'] if 'джекпот' in pre else f['сумма']).add(m.group(1).replace(',', '.'))
    for m in re.finditer(r'(\d+(?:\s*[-–]\s*\d+)?)\s*(минут|мин\b|часа|часов|час\b|секунд|сек\b|суток)', t):
        f['время'].add(re.sub(r'\s', '', m.group(1)) + ('м' if m.group(2).startswith('м') else 'ч' if m.group(2).startswith('ч') else 'с' if m.group(2).startswith('се') else 'д'))
    for m in re.finditer(r'(\d[\d\s]{0,9}\d|\d)\s*(?:к\b|k\b|₽|руб)', t): f['сумма'].add(re.sub(r'\s', '', m.group(1)))
    for m in NAME_RE.finditer(t): f['имя'].add(m.group(1))
    return f

class P(HTMLParser):
    """Последовательность блоков: (тег, класс-контекст, текст)."""
    SKIP = ('hero-value', 'slots-dashboard', 'recent-payouts-block', 'jackpot-strip', 'stats-grid', 'value-pillars', 'hero-quicklinks', 'review-quotes-block', 'page-thematic-block', 'layout-block', 'info-block', 'nav', 'table', 'aside', 'details')
    def __init__(s):
        super().__init__(); s.blocks = []; s.stack = []; s.cur = None; s.buf = []; s.faq = 0; s.skip = 0
    def handle_starttag(s, t, a):
        a = dict(a); cls = a.get('class', '')
        first = cls.split()[0] if cls else ''
        if first.startswith('faq') and 'faq-section' in cls: s.faq += 1
        if first in s.SKIP or t in ('nav', 'table', 'aside', 'details', 'style', 'script', 'button'): s.skip += 1
        s.stack.append((t, first))
        if t in ('h2', 'h3', 'p', 'li') and s.cur is None and not s.skip:
            s.cur = (t, first); s.buf = []
    def handle_endtag(s, t):
        while s.stack and s.stack[-1][0] != t: s.stack.pop()
        if s.stack:
            tg, first = s.stack.pop()
            if first in s.SKIP or t in ('nav', 'table', 'aside', 'details', 'style', 'script', 'button'): s.skip = max(0, s.skip-1)
        if s.cur and s.cur[0] == t:
            txt = re.sub(r'\s+', ' ', ''.join(s.buf)).strip()
            if txt: s.blocks.append((t, s.cur[1], txt, s.faq > 0))
            s.cur = None
    def handle_data(s, d):
        if s.cur is not None: s.buf.append(d)

def sections(html):
    p = P(); p.feed(html)
    secs = []; cur = None
    for t, cls, txt, infaq in p.blocks:
        if cls and t == 'h2' and cls not in ('',): continue  # классные заголовки виджетов
        if t == 'h2':
            cur = {'h2': txt, 'blocks': [], 'faq': infaq}; secs.append(cur); continue
        if cur is None: continue
        if cls and t != 'li': continue
        cur['blocks'].append((t, txt))
    return secs

def roles(sec):
    seen = set(); out = []; ps = [b for b in sec['blocks'] if b[0] == 'p']
    for i, (t, txt) in enumerate(sec['blocks']):
        if t == 'h3': out.append('H3'); continue
        if t == 'li': out.append('•'); continue
        f = facts(txt); names = f['имя'] & NAMES
        nf = sum(len(f[k]) for k in ('rtp', 'проц', 'джекпот', 'время'))
        if names and (names & seen): r = 'ВОЗВРАТ'
        elif names and (f['сумма'] or re.search(r'заш[её]л|зашла|поставил|закинул|открыл|крутанул|поймал|забрал|вывел|ушёл|ушла', txt)): r = 'ИСТОРИЯ'
        elif txt.startswith('Факт') or nf >= 2: r = 'ФАКТЫ'
        elif ('?' in txt or re.search(r'^(Хочешь|Не заходи|Жми|Открывай|Смотри|Если)', txt)) and (t, txt) == ps[-1] if ps else False: r = 'CTA'
        else: r = 'ПРОЗА'
        seen |= names; out.append(r)
    # список сжимаем
    s = []; 
    for r in out:
        if r == '•' and s and s[-1].startswith('СПИСОК'): s[-1] = 'СПИСОК' + str(int(s[-1][6:] or 1) + 1)
        elif r == '•': s.append('СПИСОК1')
        else: s.append(r)
    return s

def measure(sec):
    ps = [txt for t, txt in sec['blocks'] if t == 'p']; lis = [txt for t, txt in sec['blocks'] if t == 'li']
    h2f = facts(sec['h2']); pf = defaultdict(set); lf = defaultdict(set); perp = []
    for x in ps:
        f = facts(x); perp.append(f)
        for k, v in f.items(): pf[k] |= v
    for x in lis:
        f = facts(x)
        for k, v in f.items(): lf[k] |= v
    m = {}
    for k in ('rtp', 'проц', 'джекпот', 'время'):
        allv = pf[k] | lf[k]
        m['distinct_' + k] = len(allv)
        m['has_' + k] = int(bool(allv))
    # фактчек: доля числовых фактов абзацев, повторённых в списке того же раздела
    pnum = set((k, v) for k in ('rtp', 'проц', 'джекпот', 'время') for v in pf[k])
    lnum = set((k, v) for k in ('rtp', 'проц', 'джекпот', 'время') for v in lf[k])
    m['p_facts'] = len(pnum); m['l_facts'] = len(lnum)
    m['фактчек'] = (len(pnum & lnum) / len(pnum)) if pnum else None
    m['список_свои'] = (len(lnum - pnum) / len(lnum)) if lnum else None   # доля фактов списка, которых нет в абзацах
    # повтор факта в другом абзаце
    rep = 0; tot = 0
    for i, f in enumerate(perp):
        for k in ('rtp', 'проц', 'джекпот', 'время'):
            for v in f[k]:
                tot += 1
                if any(v in g[k] for j, g in enumerate(perp) if j != i) or v in lf[k]: rep += 1
    m['повтор_факта'] = rep / tot if tot else None
    names = (pf['имя'] | lf['имя']) & NAMES
    m['героев'] = len(names)
    m['герой_x2'] = int(len(names) >= 1 and sum(1 for f in perp if f['имя'] & NAMES) >= 2)
    h2num = set((k, v) for k in ('rtp', 'проц', 'джекпот', 'время') for v in h2f[k])
    m['h2_факт'] = int(bool(h2num)); m['h2_в_теле'] = (int(bool(h2num & (pnum | lnum))) if h2num else None)
    m['абз'] = len(ps); m['пунктов'] = len(lis)
    return m

def corpus(paths):
    R = []; RS = Counter(); n = 0
    for d in paths:
        for f in sorted(glob.glob(d + '/*.html')):
            page = os.path.basename(f)[:-5]
            html = open(f, encoding='utf-8', errors='ignore').read()
            for sec in sections(html):
                if sec['faq'] or not sec['blocks']: continue
                if len([b for b in sec['blocks'] if b[0] == 'p']) < 2: continue
                m = measure(sec); m['page'] = page; m['set'] = os.path.basename(d); m['h2'] = sec['h2']
                r = roles(sec); m['roles'] = ' '.join(r); R.append(m); RS[m['roles']] += 1; n += 1
    return R, RS

def summary(name, R, RS):
    def mean(k, cond=lambda m: True):
        v = [m[k] for m in R if m[k] is not None and cond(m)]
        return round(st.mean(v), 2) if v else None
    print(f'\n=== {name}: разделов {len(R)} ===')
    print('роли (топ-8):')
    for r, c in RS.most_common(8): print(f'  {c:4d}  {r}')
    for k in ('rtp', 'проц', 'джекпот', 'время'):
        v = [m['distinct_' + k] for m in R if m['has_' + k]]
        one = sum(1 for x in v if x == 1)
        print(f'  {k:8s}: разделов с фактом {len(v)} ({round(100*len(v)/len(R))}%), одно значение в {round(100*one/len(v)) if v else 0}%, среднее различных {round(st.mean(v),2) if v else 0}')
    print(f"  фактчек (доля фактов абзацев, повторённых в списке): {mean('фактчек')}; своих фактов списка: {mean('список_свои')}; повтор факта где-либо в разделе: {mean('повтор_факта')}")
    print(f"  героев на раздел: {mean('героев')}; герой в ≥2 абзацах: {mean('герой_x2')}; h2 с фактом: {mean('h2_факт')}; факт h2 повторён в теле: {mean('h2_в_теле')}")
    print(f"  абзацев: {mean('абз')}, пунктов: {mean('пунктов')}, фактов в абзацах: {mean('p_facts')}, в списке: {mean('l_facts')}")

if __name__ == '__main__':
    out = {}
    for arg in sys.argv[1:]:
        name, pat = arg.split('=', 1)
        paths = [p.rstrip('/') for p in sorted(glob.glob(pat)) if os.path.isdir(p)]
        R, RS = corpus(paths); summary(name, R, RS); out[name] = R
    json.dump(out, open('/tmp/p27/formula/fakty.json', 'w'), ensure_ascii=False)
