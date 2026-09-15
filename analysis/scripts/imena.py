"""Разбор имени контента в вектор параметров.
Имя контента — главный источник параметров разреза 1. Каталог парсит его
на 5 токенов, но соглашение об именах менялось 4 раза, и часть параметров
(даты на странице, семейство генератора) пятью токенами не ловится.
"""
import re, sys, glob, collections

def parse(name):
    n = name.strip(); low = n.lower()
    f = {}

    # 1 · семейство / эпоха именования — прокси версии генератора
    if   re.match(r'^nabory', low):                f['family']='nabory'
    elif re.match(r'^nabor[-\d]', low):            f['family']='nabor'
    elif re.match(r'^content-\d{4}-\d{2}-\d{2}',low): f['family']='content-dated'
    elif re.match(r'^new\d+', low):                f['family']='NEW'
    elif re.match(r'^generator_', low):            f['family']='Generator'
    elif re.match(r'^content_script', low):        f['family']='script'
    else:                                          f['family']='custom'

    # 2 · число страниц  (граница слева обязательна: archive37строформлено ≠ 37 страниц)
    m = re.search(r'(?:^|[-_ ])(\d+)\s*(?:str|pages?|стр)', low)
    f['pages'] = int(m.group(1)) if m else None

    # 3 · оформление
    if   'styled_img' in low:                      f['oform']='styled_img'
    elif 'bez_img' in low:                         f['oform']='bez_img'
    elif re.search(r'oform-2|oform_2', low):       f['oform']='oform-2'
    elif re.search(r'оформлен|[-_]oform', low):    f['oform']='oform'
    else:                                          f['oform']=None

    # 4 · даты на странице — параметра нет ни в каталоге, ни в прежнем плане
    if   re.search(r'withdate|сдатой|с дат',  low): f['dates']='with'
    elif re.search(r'nodate|бездаты|без дат', low): f['dates']='without'
    else:                                           f['dates']=None

    # 5 · прочие флаги имени
    f['archive'] = bool(re.search(r'archive', low))
    m = re.search(r'unique(\d+)', low); f['unique'] = m.group(1) if m else None
    m = re.search(r'^content-(\d{4}-\d{2}-\d{2})([a-z]?)', low)
    f['pack_date'], f['pack_series'] = (m.group(1), m.group(2) or None) if m else (None, None)
    m = re.search(r'_(\d+)$', n); f['serial'] = m.group(1) if m else None
    return f

if __name__ == '__main__':
    names = sorted({re.sub(r' — id.*','',l[3:]).strip()
                    for p in glob.glob('analysis/launch_*.txt')
                    for l in open(p) if l.startswith('## ')})
    rows = [(n, parse(n)) for n in names]
    print(f"имён контента в реестре: {len(rows)}\n")
    for key in ('family','pages','oform','dates'):
        c = collections.Counter(f[key] for _, f in rows)
        total_known = sum(v for k,v in c.items() if k is not None)
        print(f"-- {key} -- (заполнено у {total_known} из {len(rows)})")
        for k, v in sorted(c.items(), key=lambda x: (-x[1], str(x[0]))):
            print(f"   {str(k):<16} {v:>4}")
        print()
    # пары: что с чем реально встречается
    print("-- оформление × даты: есть ли перекрёстные ячейки --")
    cross = collections.Counter((f['oform'], f['dates']) for _, f in rows
                                if f['oform'] and f['dates'])
    for (o, d), v in sorted(cross.items(), key=lambda x: -x[1]):
        print(f"   {o:<12} {d:<8} {v:>3}")
    print("\n-- страницы × оформление --")
    cross = collections.Counter((f['pages'], f['oform']) for _, f in rows
                                if f['pages'] and f['oform'])
    for (p, o), v in sorted(cross.items(), key=lambda x: -x[1]):
        print(f"   {p:<4} стр  {o:<12} {v:>3}")
