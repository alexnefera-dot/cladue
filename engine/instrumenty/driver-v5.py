# -*- coding: utf-8 -*-
"""Четыре работника гонятся за один набор: у каждого своя песочница журнала,
сиды разбираются шагом 4. Побеждает первый прошедший ворота — его журнал
становится общим, и партия идёт к следующему набору. Наборы строго по
одному: иначе куски пулов повторятся между соседними наборами."""
import json, os, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

КОРЕНЬ = '/home/user/cladue'
БАЗА   = os.environ.get('V5_BAZA', '/tmp/v5-partiya')
МАСТЕР = os.path.join(КОРЕНЬ, 'engine/data-v5')
РАБОТНИКОВ = 4

# Ворота манеры: густая страница у корпуса — другой формат, и мерить её
# полосами обычной манеры значит требовать того, чего у её образцов нет.
ВОРОТА = dict(fragments=0, mantra_max=2.2, rtp_spread=4.0, paragraphs=23.0,
              words_per_para=46.0, stakes_max=1.0, jackpot_uniq=9, payout_uniq=5.0)
ВОРОТА_ГУСТЫЕ = dict(ВОРОТА, paragraphs=45.0, words_per_para=12.0)

def песочница(i):
    d = os.path.join(БАЗА, 'w%d' % i)
    os.makedirs(d, exist_ok=True)
    for имя in os.listdir(МАСТЕР):
        цель = os.path.join(d, имя)
        if имя == 'vydano.json':
            continue
        if not os.path.exists(цель):
            os.symlink(os.path.join(МАСТЕР, имя), цель)
    return d

def синхр(d):
    shutil.copyfile(os.path.join(МАСТЕР, 'vydano.json'), os.path.join(d, 'vydano.json'))

def php(*арг, таймаут=900):
    return subprocess.run(['php'] + list(арг), cwd=КОРЕНЬ, capture_output=True,
                          text=True, timeout=таймаут)

def ворота(папка, густой=False):
    В = ВОРОТА_ГУСТЫЕ if густой else ВОРОТА
    r = php('engine/sverka-v5.php', папка, '--json')
    try:
        стр = list(json.loads(r.stdout).values())[0]['страницы']
    except Exception:
        return False, 'сверка не прочиталась'
    зн = list(стр.values())
    ср = lambda k: sum(v[k] for v in зн) / len(зн)
    if sum(v['fragments'] for v in зн) > 0:       return False, 'обрывки'
    if ср('mantra_max')   > В['mantra_max']: return False, 'мантра %.2f' % ср('mantra_max')
    if ср('rtp_spread')   > В['rtp_spread']: return False, 'rtp %.2f' % ср('rtp_spread')
    if ср('paragraphs')   > В['paragraphs']: return False, 'абзацы %.2f' % ср('paragraphs')
    if ср('words_per_para') < В['words_per_para']: return False, 'слов в абзаце %.2f' % ср('words_per_para')
    if ср('stakes_max')   > В['stakes_max']: return False, 'ставки %.2f' % ср('stakes_max')
    if max(v['jackpot_uniq'] for v in зн) > В['jackpot_uniq']: return False, 'джекпоты'
    if ср('payout_uniq')  > В['payout_uniq']: return False, 'выплаты %.2f' % ср('payout_uniq')
    r = php('engine/priyomka-v5.php', папка)
    if 'провалов' in r.stdout and 'провалов: 0' not in r.stdout:
        строка = [l for l in r.stdout.split('\n') if 'провалов' in l]
        return False, 'приёмка: ' + (строка[-1] if строка else '?')
    r = php('engine/smysl-v5.php', папка, '--json')
    try:
        if json.loads(r.stdout).get('находки'):
            return False, 'смысл'
    except Exception:
        pass
    return True, 'ок'

# Манера назначается партии заранее, долей корпуса: густых 28 %. Гонка сидов
# сама её не сохранит — густой набор проходит ворота реже, и за десять наборов
# густых могло не оказаться ни одного.
ГУСТЫЕ = {int(x) for x in os.environ.get('V5_GUSTYE', '').split(',') if x.strip()}

def попытка(i, номер, сид):
    d = песочница(i)
    синхр(d)
    папка = os.path.join(БАЗА, 'try%d-%d' % (i, сид))
    shutil.rmtree(папка, ignore_errors=True)
    try:
        r = php('engine/generator-v5.php', '--выход=' + папка, '--сид=%d' % сид,
                '--данные=' + d, '--тихо',
                '--манера=' + ('густая' if номер in ГУСТЫЕ else 'обычная'))
        if not os.path.isdir(папка) or len(os.listdir(папка)) < 12:
            return None, сид, 'генератор: ' + (r.stderr.strip()[:120] or 'пусто')
        r = php('engine/perekrut-v5.php', папка, '--сид=%d' % сид, '--тихо')
        ок, почему = ворота(папка, номер in ГУСТЫЕ)
        if not ок:
            shutil.rmtree(папка, ignore_errors=True)
            return None, сид, почему
        return (папка, d), сид, 'ок'
    except subprocess.TimeoutExpired:
        shutil.rmtree(папка, ignore_errors=True)
        return None, сид, 'таймаут'

def набор(номер, сид0, журнал):
    попыток = 0
    сид = сид0
    while попыток < 2000:
        задания = [(i, номер, сид + i) for i in range(РАБОТНИКОВ)]
        with ThreadPoolExecutor(max_workers=РАБОТНИКОВ) as пул:
            итоги = list(пул.map(lambda з: попытка(*з), задания))
        попыток += РАБОТНИКОВ
        for итог, с, почему in итоги:
            if итог:
                папка, d = итог
                цель = os.path.join(КОРЕНЬ, 'samples/v5-final/nabor-%d' % номер)
                shutil.rmtree(цель, ignore_errors=True)
                shutil.move(папка, цель)
                shutil.copyfile(os.path.join(d, 'vydano.json'),
                                os.path.join(МАСТЕР, 'vydano.json'))
                журнал.write('набор %d: сид %d, попыток %d\n' % (номер, с, попыток))
                журнал.flush()
                # остальные победители этого круга не нужны
                for и2, _, _ in итоги:
                    if и2 and и2[0] != папка:
                        shutil.rmtree(и2[0], ignore_errors=True)
                return с, попыток
        if попыток % 40 == 0:
            журнал.write('  %d: %d попыток, последнее — %s\n' % (номер, попыток, почему))
            журнал.flush()
        сид += РАБОТНИКОВ
    журнал.write('набор %d: не собрался за %d попыток\n' % (номер, попыток))
    журнал.flush()
    return None, попыток

if __name__ == '__main__':
    от, до, сид0 = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    with open(os.path.join(БАЗА, 'log.txt'), 'a', buffering=1) as журнал:
        журнал.write('=== партия %d–%d, старт %s\n' % (от, до, time.strftime('%H:%M:%S')))
        всего = 0
        for n in range(от, до + 1):
            с, п = набор(n, сид0 + (n - от) * 400, журнал)
            всего += п
        журнал.write('=== готово, попыток всего %d, %s\n' % (всего, time.strftime('%H:%M:%S')))
