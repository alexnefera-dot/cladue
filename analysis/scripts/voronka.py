#!/usr/bin/env python3
"""Воронка по ступеням: индекс -> клики -> регистрации, каждая ступень условная.

Показов мы не видим. Поле `views_sum` заполнено у 35 437 сайтов из 426 825 и
не согласовано с кликами (есть строки с показами и без кликов и наоборот), так
что за показы его брать нельзя. Значит про попадание в индекс мы знаем только
одно: пришёл ли с поиска хотя бы один клик.

Отсюда три ступени, и каждая считается на своём знаменателе:

1. **вышли в поиск** — доля сайтов с первым поисковым кликом в первые трое
   суток. Это индексация и заметность вместе, разделить их нечем.
2. **кликов на вышедший сайт** — среди тех, кто вышел. Сайты, не попавшие в
   индекс, сюда не входят и цифру не разбавляют.
3. **регистраций на десять тысяч кликов** — среди кликов. Сайты без трафика
   не входят.

Сравнивать наборы контента, зоны и бренды по первой ступени и по третьей —
разные вопросы, и ответы у них расходятся.

    python3 voronka.py <панель.jsonl> <клики-по-сабдоменам.jsonl>
                       <свежие-клики.jsonl> <последний-день>
"""
import sys, re, collections

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from svodka_mesyacy import load


def stage(rs, level, stratum=None, title='', minn=600):
    """Три ступени по уровням фактора. Страта применяется к первой ступени."""
    e = [r for r in rs if r['ok']]
    sp = collections.defaultdict(lambda: [0, 0])
    if stratum:
        for r in e:
            k = stratum(r)
            if k is None:
                continue
            t = sp[k]
            t[0] += r['hit']
            t[1] += 1
    g = collections.defaultdict(lambda: [0, 0, 0.0, 0, 0, 0, 0])
    for r in e:
        v = level(r)
        if v is None:
            continue
        if stratum:
            k = stratum(r)
            if k is None:
                continue
            hh, nn = sp[k]
            if nn < 60:
                continue
            g[v][2] += hh / nn
        t = g[v]
        t[0] += r['hit']
        t[1] += 1
        t[3] += r['cl']
        t[4] += r['reg']
        t[5] += r['fd']
        if r['hit']:
            t[6] += r['cl']
    o = [(v, t) for v, t in g.items() if t[1] >= minn]
    if len(o) < 2:
        return
    o.sort(key=lambda x: -(x[1][4] / x[1][3] if x[1][3] else 0))
    print('\n' + title)
    print('  %-26s %8s %9s %9s %11s %7s %5s %9s'
          % ('уровень', 'сайтов', '1: вышли', 'к страте', '2: кл/вышедший',
             'кликов', 'рег', '3: рег/10т'))
    for v, t in o:
        print('  %-26s %8d %8.1f%% %9s %11.1f %7d %5d %9.1f'
              % (str(v)[:26], t[1], 100 * t[0] / t[1],
                 '%.2f' % (t[0] / t[2]) if t[2] else '—',
                 t[6] / t[0] if t[0] else 0, t[3], t[4],
                 10000 * t[4] / t[3] if t[3] else 0))


def main(panel, subsclicks, fresh, last):
    rows = load(panel, subsclicks, fresh, last)
    pd = lambda r: (r['pack'], r['day']) if r['pack'] != 'КОНТЕНТ НЕ ЗАПИСАН' else None
    for nm, rs in (('АВГУСТ', [r for r in rows if r['day'][:7] == '2026-08']),
                   ('СЕНТЯБРЬ', [r for r in rows if r['day'][:7] == '2026-09']),
                   ('ВСЯ СЕТЬ', rows)):
        print('\n' + '#' * 104 + '\n# ' + nm + '\n' + '#' * 104)
        e = [r for r in rs if r['ok']]
        hh = sum(r['hit'] for r in e)
        cl_all = sum(r['cl'] for r in e)
        cl_hit = sum(r['cl'] for r in e if r['hit'])
        reg = sum(r['reg'] for r in e)
        print('\nсайтов досмотрено %d, вышли в поиск %d (%.1f%%)'
              % (len(e), hh, 100 * hh / len(e)))
        print('кликов всего %d, из них на вышедших сайтах %d (%.1f%%)'
              % (cl_all, cl_hit, 100 * cl_hit / cl_all if cl_all else 0))
        print('кликов на вышедший сайт %.1f; регистраций на десять тысяч кликов %.1f'
              % (cl_hit / hh if hh else 0, 10000 * reg / cl_all if cl_all else 0))
        stage(rs, lambda r: r['tld'], pd, 'ЗОНА (страта первой ступени: контент + день)')
        stage(rs, lambda r: 'первая волна' if r['wave'] == 0 else 'вторая волна', pd,
              'ВОЛНА ПЕРЕОБХОДА')
        stage(rs, lambda r: '12 страниц' if re.search(r'12(page|str|стр)', r['pack'], re.I)
              else '7 страниц' if re.search(r'7(page|str|стр)', r['pack'], re.I) else None,
              lambda r: r['day'], 'СТРАНИЦ В САЙТЕ (страта: день — внутри контента неразличимо)')
        stage(rs, lambda r: '<4k' if (r['kw'] or 0) < 4000 else '4-8k' if r['kw'] < 8000
              else '8k+', pd, 'ДЛИНА СПИСКА КЛЮЧЕЙ — она же бренд, см. оговорку')
        if nm != 'АВГУСТ':
            stage(rs, lambda r: r['pack'] if r['pack'] != 'КОНТЕНТ НЕ ЗАПИСАН' else None, None,
                  'НАБОРЫ КОНТЕНТА', minn=2000)
        stage(rs, lambda r: r['brand'], None, 'БРЕНДЫ', minn=1200)


if __name__ == '__main__':
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
