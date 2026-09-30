# -*- coding: utf-8 -*-
"""Вычитка рядом для партии 711–715.

Два отличия от прошлой сборки. Сосед выбран счётом, а не рукой: это набор с
наименьшим отклонением от медианы своей группы (predstavitel.py), поэтому
рядом стоит типичный набор корпуса, а не подобранный под вывод. Сводка в шапке
берётся из широкой таблицы (tablica-shire.py), а не пишется руками, и флаг «вне
полосы» в ней тот же, что в таблице.
"""
import os, re, sys, html as H
S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, S)
from ryadom import para

НАШ = '/home/user/cladue/samples/v5-final'
КОРПУС = '/home/user/cladue/samples/v5-konkurent/NEW100'
ПАРЫ = [
    ('gustaya', 'Густая манера', os.path.join(КОРПУС, 'trix'),
     os.path.join(НАШ, 'nabor-713'), 'корпус trix', 'наш набор 713',
     'trix — представитель густой группы: отклонение от её медианы 0.24 по пяти '
     'опорным величинам, то есть почти точное попадание. Выбран счётом, не рукой.'),
    ('obychnaya', 'Обычная манера', os.path.join(КОРПУС, 'drip'),
     os.path.join(НАШ, 'nabor-715'), 'корпус drip', 'наш набор 715',
     'drip — представитель обычной группы, отклонение 0.57.'),
]

# Опорные строки сводки: то, чем манеры различаются между собой, а не весь
# список из девяноста восьми параметров — он лежит в shire-*.md целиком.
ОПОРНЫЕ = ['слов на страницу', 'абзацев на страницу', 'сверка: words_per_para',
           'ссылок на страницу', 'h3 на h2', 'бренд на страницу',
           'вода (стоп-слова), %', 'классическая тошнота', 'цифр на 100 слов',
           'FAQ-меток на набор', 'таблиц на набор', 'доля вы, %']

def таблица(путь):
    строки = {}
    for l in open(путь, encoding='utf-8'):
        ч = [x.strip() for x in l.strip().strip('|').split('|')]
        if len(ч) != 7 or ч[0] in ('параметр', '---'): continue
        строки[ч[0]] = ч[1:]
    return строки

КОРЕНЬ = os.path.dirname(os.path.dirname(S))
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

ВНЕГ = sum(1 for v in Г.values() if v[5])
ВНЕО = sum(1 for v in О.values() if v[5])
СВОДКА = ('<table class="svod"><thead><tr><th>параметр</th>'
          '<th>корпус обычные<br><span>79 наборов, p10–p90</span></th>'
          '<th>наши обычные<br><span>712, 714, 715</span></th>'
          '<th>корпус густые<br><span>21 набор, p10–p90</span></th>'
          '<th>наши густые<br><span>711, 713</span></th></tr></thead><tbody>%s</tbody></table>'
          '<p class="note">Вне полосы по всей широкой таблице: обычная манера — '
          '%d параметра из %d, густая — %d из %d. Полный список в '
          '<code>shire-o711.md</code> и <code>shire-g711.md</code>.</p>'
          % ('\n'.join(ряды), ВНЕО, len(О), ВНЕГ, len(Г)))

CSS = open(os.path.join(S, 'vychitka-ryadom.css'), encoding='utf-8').read()

блоки, nav = [], []
for код, имя, кд, нд, кн, нн, примечание in ПАРЫ:
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
Сосед в каждой паре — представитель своей группы по счёту, а не подобранный вручную.
Бренд-переменные подсвечены, метрики каждой страницы — под её заголовком.</p>
%s
<p class="legend"><mark class="br">%%brand_name_ru%%</mark> — бренд-переменная,
<span class="a">подчёркнутое</span> — ссылка.</p>
<nav>%s</nav>
%s
</div></body></html>''' % (CSS, СВОДКА, ' '.join(nav), '\n'.join(блоки))

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S, 'vychitka-711-715.html')
open(out, 'w', encoding='utf-8').write(html)
print(out, len(html), 'знаков')
