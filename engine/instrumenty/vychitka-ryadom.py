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

НАШИ_ГУСТЫЕ = ['nabor-711', 'nabor-713']
НАШИ_ОБЫЧНЫЕ = ['nabor-715', 'nabor-712', 'nabor-714']

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

def собрать(выход, соседей=3):
    врем = os.path.join(os.path.dirname(выход) or '.', '.vychitka-gruppy')
    густ, обыч = деление()
    рангГ = порядок(ссылки(густ, os.path.join(врем, 'gustye')))[0][:соседей]
    рангО = порядок(ссылки(обыч, os.path.join(врем, 'obychnye')))[0][:соседей]

    Г = таблица(os.path.join(КОРЕНЬ, 'docs/shirokoe/shire-gustye-711-713.md'))
    О = таблица(os.path.join(КОРЕНЬ, 'docs/shirokoe/shire-obychnye-712-715.md'))
    ряды = []
    for к in ОПОРНЫЕ:
        г, о = Г.get(к), О.get(к)
        if not (г and о): continue
        кл = lambda т: 'miss' if т[5] else 'ok'
        ряды.append('<tr><td>%s</td><td>%s <span>(%s)</span></td><td class="%s">%s</td>'
                    '<td>%s <span>(%s)</span></td><td class="%s">%s</td></tr>'
                    % (H.escape(к), о[2], о[3], кл(о), о[0], г[2], г[3], кл(г), г[0]))
    сводка = ('<table class="svod"><thead><tr><th>параметр</th>'
              '<th>корпус обычные<br><span>%d наборов, p10–p90</span></th>'
              '<th>наши обычные<br><span>712, 714, 715</span></th>'
              '<th>корпус густые<br><span>%d наборов, p10–p90</span></th>'
              '<th>наши густые<br><span>711, 713</span></th></tr></thead>'
              '<tbody>%s</tbody></table>'
              '<p class="note">Вне полосы по всей широкой таблице: обычная манера — '
              '%d параметра из %d, густая — %d из %d. Полный список в '
              '<code>docs/shirokoe/</code>.</p>'
              % (len(обыч), len(густ), '\n'.join(ряды),
                 sum(1 for v in О.values() if v[5]), len(О),
                 sum(1 for v in Г.values() if v[5]), len(Г)))

    пары = []
    for метка, ранг, наши in (('густая', рангГ, НАШИ_ГУСТЫЕ), ('обычная', рангО, НАШИ_ОБЫЧНЫЕ)):
        for i, (имя, оценка) in enumerate(ранг):
            наш = наши[i % len(наши)]
            код = '%s-%s' % ('g' if метка == 'густая' else 'o', имя)
            пары.append((код, '%s манера · %s' % (метка.capitalize(), имя),
                         os.path.join(КОРПУС, имя), os.path.join(НАШ, наш),
                         'корпус ' + имя, 'наш ' + наш.replace('nabor-', 'набор '),
                         'Отклонение %s от медианы своей группы — %.2f (место %d из %d по близости '
                         'к медиане). Чем больше отклонение, тем сильнее сосед сам отличается от '
                         'типичного набора группы.' % (имя, оценка, i + 1, len(ранг))))

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
<title>Вычитка рядом, партия 711–715</title>
<style>%s</style></head><body><div class="wrap">
<h1>Вычитка рядом: корпус NEW100 против партии 711–715</h1>
<p class="sub">Слева страница корпусного набора, справа наша страница того же типа.
По %d соседа на манеру, выбранных счётом: это наборы, ближе всех стоящие к медиане своей
группы. Бренд-переменные подсвечены, метрики каждой страницы — под её заголовком.</p>
%s
<p class="legend"><mark class="br">%%brand_name_ru%%</mark> — бренд-переменная,
<span class="a">подчёркнутое</span> — ссылка.</p>
<nav>%s</nav>
%s
</div></body></html>''' % (CSS, соседей, сводка, ' '.join(nav), '\n'.join(блоки))
    open(выход, 'w', encoding='utf-8').write(html)
    return выход, len(html), пары

if __name__ == '__main__':
    выход = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S, 'vychitka.html')
    сколько = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    п, н, пары = собрать(выход, сколько)
    print('%s, %d знаков, пар %d:' % (п, н, len(пары)))
    for код, имя, _, _, кн, нн, _ in пары:
        print('  %-28s %s против %s' % (имя, кн, нн))
