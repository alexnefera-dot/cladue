# -*- coding: utf-8 -*-
"""Доводчик плотностей транша.

Тела пунктов пишутся руками, но попадать семью плотностями сразу в полосы
существующих пунктов на глаз не выходит: на bonus ушло четыре прохода, на
slots три, на news четыре. Текст вставок тоже написан руками — здесь только
расстановка: куда именно добавить хвост со ссылкой, прорезь, цифру, слово
honest или термин, чтобы длина пункта осталась в полосе типа.

  python3 dover.py <тип>            — подогнать и переписать файл типа

Вставка идёт только в пункт, который после неё остаётся в полосе слов и не
выходит за потолок терминов. Ничего не удаляется: если плотность выше полосы,
доводчик об этом говорит, а правит её человек.
"""
import os, importlib.util, io, json, re, subprocess, sys

КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SB = os.path.dirname(os.path.abspath(__file__))
ТЕГИ = re.compile(r'(?s)<[^>]+>')
HONEST = re.compile(r'\b(минус\w*|недостат\w*|риск\w*|осторожн\w*|не советую|не стоит|проигр\w*'
                    r'|потер\w*|обман\w*|развод\w*|ловушк\w*|подвох\w*|честно говоря|на самом деле'
                    r'|важно понимать)\b', re.I)

# Хвосты со ссылками, прорезями, цифрами, honest и терминами — по типу.
# Это язык, а не механика: каждый хвост написан под свой тип.
СЛОВАРИ = json.load(open(SB + '/slovari.json', encoding='utf-8'))


def php(код, вход):
    r = subprocess.run(['php', '-r', код], input=json.dumps(вход), capture_output=True,
                       text=True, cwd=КОРЕНЬ)
    if r.returncode != 0:
        raise SystemExit('php: ' + r.stderr[:300])
    return json.loads(r.stdout)


def термы(тексты):
    if not тексты:
        return []
    return php('require_once "engine/src/PageMetrics.php";'
               '$in=json_decode(file_get_contents("php://stdin"),true);$o=[];'
               'foreach($in as $t){$o[]=NicheLexicon::termsTotal($t);}echo json_encode($o);', тексты)


def собрать(я, т, в):
    return ('<strong>%s:</strong> %s' % (я, т)) if в else ('%s: %s' % (я, т))


def слов(т):
    return len(ТЕГИ.sub('', т).split())


def главная(тип):
    d = json.load(open(КОРЕНЬ + '/engine/data-v5/pools.json', encoding='utf-8'))
    сп = importlib.util.spec_from_file_location('y_' + тип, '%s/%s.py' % (SB, тип))
    m = importlib.util.module_from_spec(сп); сп.loader.exec_module(m)
    П = {k: list(v) for k, v in m.ПУНКТЫ.items()}
    разделы = list(d['разделы'][тип].keys())
    мои = {собрать(*п) for v in П.values() for п in v}
    стар = [str(x.get('т', '')) for h2 in разделы for x in d['разделы'][тип][h2]['пункты']
            if str(x.get('т', '')) not in мои]
    дл = sorted(слов(x) for x in стар)
    низ, верх = дл[int(.10 * (len(дл) - 1))], дл[int(.90 * (len(дл) - 1))]
    тс = sorted(термы(стар))
    потолокТерм = тс[int(.9 * (len(тс) - 1))]
    цельТерм = sum(тс) / len(тс)

    мерки = {
        'ссылок':   (lambda t: len(re.findall(r'<a\s', t)), 0.75),
        'цифр':     (lambda t: len(re.findall(r'\d', ТЕГИ.sub('', t))), 0.70),
        'прорезей': (lambda t: len(re.findall(r'\{[^}]+\}', t)), 0.70),
        'honest':   (lambda t: len(HONEST.findall(ТЕГИ.sub('', t))), 0.85),
        'терминов': (None, 0.85),
    }
    цели = {}
    for имя, (f, к) in мерки.items():
        цели[имя] = (цельТерм if f is None else sum(f(x) for x in стар) / len(стар)) * к
    мерки['терминов'] = (lambda t: термы([t])[0], 0.85)

    сл = СЛОВАРИ[тип]
    порядок = [(ин, i) for ин in sorted(П) for i in range(len(П[ин]))]

    def тексты():
        return [собрать(*П[ин][i]) for ин, i in порядок]

    for имя in ('ссылок', 'прорезей', 'цифр', 'honest', 'терминов'):
        f = мерки[имя][0]
        хвосты = сл[имя]
        шаг = 0
        while True:
            т = тексты()
            сейчас = (sum(термы(т)) / len(т)) if имя == 'терминов' else (sum(f(x) for x in т) / len(т))
            if сейчас >= цели[имя]:
                break
            # берём самый короткий пункт, которому вставка не сломает полосу
            кандидаты = sorted(range(len(порядок)), key=lambda k: слов(т[k]))
            поставили = False
            for k in кандидаты:
                ин, i = порядок[k]
                я, тело, в = П[ин][i]
                х = хвосты[шаг % len(хвосты)]
                новое = тело.rstrip('.') + х + '.' if х.startswith((',', ' —')) else тело.rstrip() + ' ' + х
                полн = собрать(я, новое, в)
                if не_годится(полн, низ, верх, потолокТерм):
                    continue
                if f(полн) <= f(т[k]):
                    continue
                П[ин][i] = (я, новое, в)
                шаг += 1
                поставили = True
                break
            if not поставили:
                print('  %s: некуда ставить, остаёмся на %.3f при цели %.3f' % (имя, сейчас, цели[имя]))
                break
    записать(тип, П, m)


def не_годится(полн, низ, верх, потолокТерм):
    с = слов(полн)
    if not (низ <= с <= верх):
        return True
    return термы([полн])[0] > потолокТерм


def записать(тип, П, m):
    шапка = getattr(m, '__doc__', None)
    out = io.StringIO()
    out.write('# -*- coding: utf-8 -*-\n')
    out.write('# Пункты с тематическим ярлыком для типа %s. Плотности доведены доводчиком.\n' % тип)
    out.write('ПУНКТЫ = {\n')
    for ин in sorted(П):
        out.write(' %d: [\n' % ин)
        for я, т, в in П[ин]:
            out.write("  (%r, %r, %d),\n" % (я, т, в))
        out.write(' ],\n')
    out.write('}\n')
    open('%s/%s.py' % (SB, тип), 'w', encoding='utf-8').write(out.getvalue())
    print('%s: записано %d пунктов' % (тип, sum(len(v) for v in П.values())))


if __name__ == '__main__':
    главная(sys.argv[1])
