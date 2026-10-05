# -*- coding: utf-8 -*-
"""Вычитка рядом: страница корпуса слева, наша того же типа справа.

usage: python3 engine/instrumenty/vychitka-ryadom.py <выходной html> [соседей на манеру]

Три решения, которые отличают эту сборку от прежней.

Корпус делится на манеры тем же правилом, что даёт полосы приёмки — медиана
бренд-переменных на страницу больше восьми. Иначе вычитка мерила бы одним
делением, а приёмка судила другим.

Соседи выбираются счётом (predstavitel.py): берутся наборы с наименьшим
отклонением от медианы своей группы. По одному соседу мало — один набор можно
подобрать под любой вывод, и по нему не видно, насколько группа сама разнородна;
поэтому по умолчанию их три, и рядом с каждым стоит его отклонение.

Сводка в шапке берётся из широкой таблицы (tablica-shire.py), а не пишется
руками, и флаг «вне полосы» в ней тот же, что в таблице.
"""
import os, re, sys, html as H
S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, S)
from ryadom import para
from predstavitel import порядок

КОРЕНЬ = os.path.dirname(os.path.dirname(S))
КОРПУС = os.path.join(КОРЕНЬ, 'samples/v5-konkurent/NEW100')
НАШ = os.path.join(КОРЕНЬ, 'samples/v5-final')
ТИПЫ = ['main','obzor','slots','bonus','promo','registracia','vhod','zerkalo','app','news','partnery','info']

НАШИ_ГУСТЫЕ = ['nabor-741', 'nabor-744']
НАШИ_ОБЫЧНЫЕ = ['nabor-743', 'nabor-745', 'nabor-742']

def деление():
    """Густые и обычные наборы корпуса: медиана бренд-переменных на страницу > 8."""
    import statistics as st
    густ, обыч = [], []
    for н in sorted(os.listdir(КОРПУС)):
        d = os.path.join(КОРПУС, н)
        if not os.path.isdir(d): continue
        бр = []
        for т in ТИПЫ:
            f = os.path.join(d, т + '.html')
            if not os.path.isfile(f): continue
            s = re.sub(r'(?is)<(script|style)\b.*?</\1>', ' ',
                       open(f, encoding='utf-8', errors='replace').read())
            бр.append(len(re.findall(r'%brand_name_(?:ru|en)%', s)))
        if бр: (густ if st.median(бр) > 8 else обыч).append(н)
    return густ, обыч

def ссылки(имена, куда):
    """Группа как каталог ссылок: predstavitel ранжирует содержимое каталога."""
    os.makedirs(куда, exist_ok=True)
    for н in имена:
        ц = os.path.join(куда, н)
        if not os.path.exists(ц): os.symlink(os.path.join(КОРПУС, н), ц)
    return куда

def таблица(путь):
    строки = {}
    for l in open(путь, encoding='utf-8'):
        ч = [x.strip() for x in l.strip().strip('|').split('|')]
        if len(ч) != 7 or ч[0] in ('параметр', '---'): continue
        строки[ч[0]] = ч[1:]
    return строки

# Опорные строки сводки: то, чем манеры различаются между собой. Все девяносто
# восемь параметров лежат в docs/shirokoe целиком.
ОПОРНЫЕ = ['слов на страницу', 'абзацев на страницу', 'сверка: words_per_para',
           'ссылок на страницу', 'h3 на h2', 'бренд на страницу',
           'вода (стоп-слова), %', 'классическая тошнота', 'цифр на 100 слов',
           'FAQ-меток на набор', 'таблиц на набор', 'доля вы, %']

def собрать(выход, соседей=3, наши_густые=None, наши_обычные=None,
            табл_густ=None, табл_обыч=None, заголовок=None):
    # Наши наборы и широкие таблицы — аргументами: прежде они были вписаны
    # в файл партией 741–745, и вычитка следующей партии требовала правки кода.
    наши_густые = НАШИ_ГУСТЫЕ if наши_густые is None else наши_густые
    наши_обычные = НАШИ_ОБЫЧНЫЕ if наши_обычные is None else наши_обычные
    табл_густ = табл_густ or os.path.join(КОРЕНЬ, 'docs/shirokoe/shire-gustye-741-744.md')
    табл_обыч = табл_обыч or os.path.join(КОРЕНЬ, 'docs/shirokoe/shire-obychnye-742-745.md')
    врем = os.path.join(os.path.dirname(выход) or '.', '.vychitka-gruppy')
    густ, обыч = деление()
    рангГ = порядок(ссылки(густ, os.path.join(врем, 'gustye')))[0][:соседей] if наши_густые else []
    рангО = порядок(ссылки(обыч, os.path.join(врем, 'obychnye')))[0][:соседей] if наши_обычные else []

    Г = таблица(табл_густ) if наши_густые else {}
    О = таблица(табл_обыч) if наши_обычные else {}
    кратко = lambda имена: ', '.join(x.replace('nabor-', '') for x in имена)
    ряды = []
    for к in ОПОРНЫЕ:
        г, о = Г.get(к), О.get(к)
        if not (г or о): continue
        кл = lambda т: 'miss' if т[5] else 'ok'
        строка = '<tr><td>%s</td>' % H.escape(к)
        if О:
            строка += ('<td>%s <span>(%s)</span></td><td class="%s">%s</td>'
                       % (о[2], о[3], кл(о), о[0])) if о else '<td>—</td><td>—</td>'
        if Г:
            строка += ('<td>%s <span>(%s)</span></td><td class="%s">%s</td>'
                       % (г[2], г[3], кл(г), г[0])) if г else '<td>—</td><td>—</td>'
        ряды.append(строка + '</tr>')
    шапка = '<th>параметр</th>'
    if О:
        шапка += ('<th>корпус обычные<br><span>%d наборов, p10–p90</span></th>'
                  '<th>наши обычные<br><span>%s</span></th>' % (len(обыч), кратко(наши_обычные)))
    if Г:
        шапка += ('<th>корпус густые<br><span>%d наборов, p10–p90</span></th>'
                  '<th>наши густые<br><span>%s</span></th>' % (len(густ), кратко(наши_густые)))
    хвост = []
    if О: хвост.append('обычная манера — %d параметра из %d'
                       % (sum(1 for v in О.values() if v[5]), len(О)))
    if Г: хвост.append('густая — %d из %d'
                       % (sum(1 for v in Г.values() if v[5]), len(Г)))
    сводка = ('<table class="svod"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
              '<p class="note">Вне полосы по всей широкой таблице: %s. Полный список в '
              '<code>docs/shirokoe/</code>.</p>'
              % (шапка, '\n'.join(ряды), ', '.join(хвост)))

    пары = []
    for метка, ранг, наши in (('густая', рангГ, наши_густые), ('обычная', рангО, наши_обычные)):
        if not наши: continue
        for i, (имя, оценка) in enumerate(ранг):
            наш = наши[i % len(наши)]
            код = '%s-%s' % ('g' if метка == 'густая' else 'o', имя)
            пары.append((код, '%s манера · %s' % (метка.capitalize(), имя),
                         os.path.join(КОРПУС, имя), os.path.join(НАШ, наш),
                         'корпус ' + имя, 'наш ' + наш.replace('nabor-', 'набор '),
                         'Отклонение %s от медианы своей группы — %.2f (место %d из %d по близости '
                         'к медиане). Чем больше отклонение, тем сильнее сосед сам отличается от '
                         'типичного набора группы.' % (имя, оценка, i + 1, len(ранг))))

    заг = заголовок or 'партии 741–745'
    CSS = open(os.path.join(S, 'vychitka-ryadom.css'), encoding='utf-8').read()
    блоки, nav = [], []
    for код, имя, кд, нд, кн, нн, примечание in пары:
        nav.append('<a href="#%s">%s</a>' % (код, имя))
        блоки.append('<h2 class="pair" id="%s">%s — %s против %s</h2>' % (код, имя, кн, нн))
        блоки.append('<p class="note">%s</p>' % H.escape(примечание))
        блоки.append(para(код, кд, нд, кн, нн))

    html = '''<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Вычитка рядом: %s</title>
<style>%s</style></head><body><div class="wrap">
<h1>Вычитка рядом: корпус NEW100 против %s</h1>
<p class="sub">Слева страница корпусного набора, справа наша страница того же типа.
По %d соседа на манеру, выбранных счётом: это наборы, ближе всех стоящие к медиане своей
группы. Бренд-переменные подсвечены, метрики каждой страницы — под её заголовком.</p>
%s
<p class="legend"><mark class="br">%%brand_name_ru%%</mark> — бренд-переменная,
<span class="a">подчёркнутое</span> — ссылка.</p>
<nav>%s</nav>
%s
</div></body></html>''' % (заг, CSS, заг, соседей, сводка, ' '.join(nav), '\n'.join(блоки))
    open(выход, 'w', encoding='utf-8').write(html)
    return выход, len(html), пары

if __name__ == '__main__':
    опции = {}
    for a in sys.argv[1:]:
        if a.startswith('--'):
            k, _, v = a[2:].partition('=')
            опции[k] = v
    позиц = [a for a in sys.argv[1:] if not a.startswith('--')]
    выход = позиц[0] if позиц else os.path.join(S, 'vychitka.html')
    сколько = int(позиц[1]) if len(позиц) > 1 else 3
    спис = lambda v: [x for x in v.split(',') if x]
    п, н, пары = собрать(
        выход, сколько,
        наши_густые=спис(опции['наши-густые']) if 'наши-густые' in опции else None,
        наши_обычные=спис(опции['наши-обычные']) if 'наши-обычные' in опции else None,
        табл_густ=опции.get('таблица-густая'), табл_обыч=опции.get('таблица-обычная'),
        заголовок=опции.get('заголовок'))
    print('%s, %d знаков, пар %d:' % (п, н, len(пары)))
    for код, имя, _, _, кн, нн, _ in пары:
        print('  %-28s %s против %s' % (имя, кн, нн))
