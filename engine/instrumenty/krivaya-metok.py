# -*- coding: utf-8 -*-
"""Кривая «порог мечения → доля помеченных пунктов в наборе».

Пороги в v5PorogMecheniya() нельзя подбирать на глаз: их калибровка стареет
каждый раз, когда меняется состояние — запас помеченных записей в пулах, набор
ключей «хуже», охват рычага. Разборы в docs/tematicheskie-metki.md: одна и та же
прикидка «на три точки» успела устареть дважды.

Инструмент снимает кривую целиком. Он делает копию движка, в которой
v5PorogMecheniya() читает порог из переменной среды POROG, и прогоняет по
нескольким парным наборам на каждое значение порога. Рабочее дерево не
трогается.

    python3 engine/instrumenty/krivaya-metok.py --наборов=3 \
        --журнал=/tmp/vydano-model.json --пороги=-100,-95,-85,0,50,100

Журнал нужен ОСЕВШИЙ: на журнале с невыданными записями замер мерит переходное
состояние, потому что невыданное идёт вне очереди — выше ключа «хуже», в котором
живёт рычаг. Свежим записям нужно наборов сорок, чтобы осесть; для замера это
состояние моделируют, раздавая им номера наборов из распределения уже выданных
записей той же прорези.

Кривая — только середина полосы. Разброс набора вокруг неё около 2.5 п.п., и
ширину полос задаёт он, а не форма порога; это печатается вместе с кривой.
"""
import argparse, importlib.util, json, os, re, shutil, statistics as st, subprocess, sys, tempfile

КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ИСХОД = """    $разброс = crc32('порог-меток|' . $сид) % 100;"""
ВСТАВКА = """    $фикс = getenv('POROG');
    if ($фикс !== false && $фикс !== '') { return (int) $фикс; }
""" + ИСХОД


def копия(куда: str) -> str:
    """Копия движка, где порог читается из POROG."""
    shutil.copytree(os.path.join(КОРЕНЬ, 'engine'), os.path.join(куда, 'engine'))
    п = os.path.join(куда, 'engine/src/V5Blocks.php')
    с = open(п, encoding='utf-8').read()
    if с.count(ИСХОД) != 1:
        sys.exit('не нашёл одного места для врезки POROG в V5Blocks.php — разметка функции сменилась')
    open(п, 'w', encoding='utf-8').write(с.replace(ИСХОД, ВСТАВКА))
    пров = subprocess.run(['php', '-l', п], capture_output=True, text=True)
    if пров.returncode:
        sys.exit(пров.stdout + пров.stderr)
    return os.path.join(куда, 'engine')


def main() -> None:
    р = argparse.ArgumentParser()
    р.add_argument('--пороги', default='-100,-95,-85,-75,-65,-55,-45,-25,0,25,50,75,90,100')
    р.add_argument('--наборов', type=int, default=3)
    р.add_argument('--сид', type=int, default=810001)
    р.add_argument('--номер', type=int, default=900, help='номер первого набора: манера берётся из него')
    р.add_argument('--журнал', default='')
    р.add_argument('--выход', default='/tmp/krivaya-metok.json')
    р.add_argument('--сухо', action='store_true', help='только собрать копию движка и показать план')
    а = р.parse_args()

    пороги = [int(x) for x in а.пороги.split(',')]
    врем = tempfile.mkdtemp(prefix='krivaya-metok-')
    движок = копия(врем)
    харнесс = os.path.join(КОРЕНЬ, 'engine/instrumenty/zamer-metok.py')
    if not os.path.exists(харнесс):
        sys.exit('нет харнесса %s' % харнесс)
    print('копия движка: %s' % движок)
    print('пороги: %s, наборов на точку: %d, сиды с %d, номера с %d'
          % (', '.join(map(str, пороги)), а.наборов, а.сид, а.номер))
    if а.сухо:
        print('сухой прогон — ничего не считалось')
        return

    среда = dict(os.environ)
    кривая = []
    for п in пороги:
        среда['POROG'] = str(п)
        ж = os.path.join(врем, 'p%d.jsonl' % п)
        subprocess.run([sys.executable, харнесс, os.path.join(врем, 'b%d' % п), str(а.сид),
                        str(а.наборов), ж, 'обычная', '', а.журнал,
                        os.path.join(движок, 'generator-v5.php'),
                        os.path.join(движок, 'perekrut-v5.php'), str(а.номер)],
                       env=среда, cwd=КОРЕНЬ, check=True)
        доли = []
        for с in open(ж, encoding='utf-8'):
            r = json.loads(с)
            доли.append(100.0 * r['пер']['темат'] / max(1, r['пер']['пунктов']))
        кривая.append({'порог': п, 'доля': round(st.mean(доли), 1), 'наборов': len(доли),
                       'доли': [round(x, 1) for x in доли]})
        print('  порог %+5d → %5.1f %% (%s)' % (п, кривая[-1]['доля'],
                                                ' '.join('%.1f' % x for x in доли)))

    # Разброс считается от середины точки, поэтому при одном наборе на точку он
    # нулевой по построению — тогда его не печатаем, чтобы не принять за замер.
    линия = [x - т['доля'] for т in кривая if т['наборов'] > 1 for x in т['доли']]
    if линия:
        print('\nразброс набора вокруг кривой: сигма %.2f п.п. (n=%d)' % (st.pstdev(линия), len(линия)))
    else:
        print('\nразброс набора не считался: на точку меньше двух наборов')
    json.dump(кривая, open(а.выход, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('кривая записана: %s' % а.выход)


if __name__ == '__main__':
    main()
